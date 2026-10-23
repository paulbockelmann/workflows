#!/usr/bin/env python3
"""Serve a built walkthrough page and write submitted answers next to it.

Usage: python3 serve.py <walkthrough.html> [--port 8765] [--open] [--session <id>] [--model sonnet] [--no-agent]

Questions sent from the page are answered by a fork of the Claude Code session that built the walkthrough:
`claude -p --resume <session> --fork-session`, read-only tools, answer written to walkthrough-replies.json.

The server exits CLOSE_GRACE seconds after the last open page closed (a reload reopens within that time), after
POLL_TIMEOUT seconds without a request once a page was open (the page polls every 3 s; covers a blocked close signal or
a quit browser), or after IDLE_TIMEOUT seconds without any request, and prints which walkthrough files exist.
"""
import argparse
import errno
import json
import os
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT_ATTEMPTS = 21
AGENT_TIMEOUT = 240
REPLY_LOCK = threading.Lock()
CLOSE_GRACE = 15
IDLE_TIMEOUT = 30 * 60
POLL_TIMEOUT = 120  # after a page said hello: no request this long means every page is gone, even without /closed


class Pages:
    """Open page ids from /hello and /closed, and the time of the last request."""

    def __init__(self):
        self.lock = threading.Lock()
        self.open = set()
        self.seen = False
        self.last_request = time.monotonic()
        self.empty_since = None

    def touch(self):
        with self.lock:
            self.last_request = time.monotonic()

    def hello(self, page):
        with self.lock:
            self.open.add(page)
            self.seen = True
            self.empty_since = None

    def closed(self, page):
        with self.lock:
            self.open.discard(page)
            if self.seen and not self.open and self.empty_since is None:
                self.empty_since = time.monotonic()

    def exit_reason(self):
        with self.lock:
            now = time.monotonic()
            if self.empty_since is not None and now - self.empty_since >= CLOSE_GRACE:
                return "page closed"
            if self.seen and now - self.last_request >= POLL_TIMEOUT:
                return f"no request from the page for {POLL_TIMEOUT} s"
            if now - self.last_request >= IDLE_TIMEOUT:
                return f"no request for {IDLE_TIMEOUT // 60} minutes"
            return None


def write_reply(replies_path, qid, text):
    with REPLY_LOCK:
        try:
            replies = json.loads(replies_path.read_text(encoding="utf-8")) if replies_path.exists() else {}
        except (OSError, ValueError):
            replies = {}
        replies[qid] = text
        replies_path.write_text(json.dumps(replies, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def answer_with_agent(question, session, model, replies_path):
    """Ask a fork of the building session. The fork has the whole conversation, so it knows the walkthrough and the
    code; --no-session-persistence keeps the fork out of the session list."""
    prompt = (f"A reader of the walkthrough page asks on step \"{question.get('title', '')}\": "
              f"{question.get('question', '')}\n\n"
              "Answer for understanding, not technical completeness: one or two sentences, or two to four short "
              "bullet lines starting with \"- \" when they read better. Plain text, no headers, no bold, no code "
              "blocks. Active voice, concrete names, say why. No praise, no preamble, no closing line, no em-dashes, "
              "none of: delve, leverage, robust, seamless, crucial, essentially, notably, ultimately. "
              "You may read files; change nothing.")
    cmd = ["claude", "-p", "--resume", session, "--fork-session", "--no-session-persistence", "--model", model,
           "--output-format", "text", "--allowedTools", "Read", "Grep", "Glob"]
    # The page server runs inside a Claude Code Bash tool; the child must not look like a nested session.
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE" and not k.startswith("CLAUDE_CODE_")}
    try:
        run = subprocess.run(cmd, input=prompt, capture_output=True, text=True, env=env, timeout=AGENT_TIMEOUT)
        text = run.stdout.strip()
        if run.returncode != 0 or not text:
            text = "The agent could not answer: " + (run.stderr.strip().splitlines() or ["no output"])[-1]
    except subprocess.TimeoutExpired:
        text = f"The agent did not answer within {AGENT_TIMEOUT} s."
    except OSError as e:
        text = f"The agent could not be started: {e.strerror}"
    write_reply(replies_path, question.get("id", ""), text)
    print(f"answer {question.get('id')}: {text}", flush=True)


def make_handler(html_path, answers_path, questions_path, replies_path, session, model, pages):
    class Handler(BaseHTTPRequestHandler):
        def handle_one_request(self):
            pages.touch()
            super().handle_one_request()

        def send_body(self, status, body, content_type):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def send_json(self, status, obj):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_body(status, body, "application/json; charset=utf-8")

        def path_only(self):
            return self.path.split("?", 1)[0]

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Max-Age", "600")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self):
            path = self.path_only()
            if path in ("/", "/index.html"):
                # Read on every request so a rebuild shows up on reload.
                try:
                    body = html_path.read_bytes()
                except OSError as e:
                    self.log_error("cannot read %s: %s", html_path, e.strerror)
                    self.send_json(500, {"ok": False, "error": "cannot read walkthrough file"})
                    return
                self.send_body(200, body, "text/html; charset=utf-8")
            elif path == "/answers":
                if not answers_path.exists():
                    self.send_json(404, {"ok": False, "error": "no answers yet"})
                    return
                self.send_body(200, answers_path.read_bytes(), "application/json; charset=utf-8")
            elif path == "/replies":
                # Written by the agent as {"<question id>": "<answer>"}; the page polls this every 3 s.
                try:
                    body = replies_path.read_bytes() if replies_path.exists() else b"{}"
                    json.loads(body)
                except (OSError, ValueError):
                    body = b"{}"
                self.send_body(200, body, "application/json; charset=utf-8")
            else:
                self.send_json(404, {"ok": False, "error": "not found"})

        def do_POST(self):
            path = self.path_only()
            if path not in ("/answers", "/ask", "/hello", "/closed"):
                self.send_json(404, {"ok": False, "error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length > 0 else b""
                data = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as e:
                self.log_error("bad %s body: %s", path, e)
                self.send_json(400, {"ok": False, "error": f"invalid JSON: {e}"})
                return
            if path in ("/hello", "/closed"):
                (pages.hello if path == "/hello" else pages.closed)(str(data.get("page", "")))
                print(f"page {'opened' if path == '/hello' else 'closed'} {data.get('page', '')}", flush=True)
                self.send_json(200, {"ok": True})
                return
            if path == "/ask":
                with questions_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(data, ensure_ascii=False) + "\n")
                print(f"question {data.get('id')} on step {data.get('step')} ({data.get('title')}): {data.get('question')}",
                      flush=True)
                if session:
                    threading.Thread(target=answer_with_agent, args=(data, session, model, replies_path),
                                     daemon=True).start()
                self.send_json(200, {"ok": True, "path": str(questions_path), "agent": bool(session)})
                return
            answers_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"answers written {answers_path}", flush=True)
            self.send_json(200, {"ok": True, "path": str(answers_path)})

        def log_message(self, format, *args):
            pass

        def log_error(self, format, *args):
            print("error: " + (format % args), file=sys.stderr, flush=True)

    return Handler


def bind(port, handler):
    for candidate in range(port, port + PORT_ATTEMPTS):
        try:
            return ThreadingHTTPServer(("127.0.0.1", candidate), handler)
        except OSError as e:
            if e.errno != errno.EADDRINUSE:
                raise
    return None


def open_browser(url):
    try:
        if webbrowser.open(url):
            return
    except webbrowser.Error:
        pass
    print(f"Open {url} in a browser", flush=True)


def main():
    ap = argparse.ArgumentParser(description="Serve a walkthrough page and collect answers.")
    ap.add_argument("html", help="built walkthrough HTML file")
    ap.add_argument("--port", type=int, default=8765, help="first port to try (default 8765)")
    ap.add_argument("--open", action="store_true", help="open the page in the default browser")
    ap.add_argument("--session", default=os.environ.get("CLAUDE_CODE_SESSION_ID"),
                    help="Claude Code session to fork for answering page questions (default: $CLAUDE_CODE_SESSION_ID)")
    ap.add_argument("--model", default="sonnet", help="model for the answering fork (default sonnet)")
    ap.add_argument("--no-agent", action="store_true", help="only record questions, do not answer them")
    args = ap.parse_args()
    session = None if args.no_agent else args.session

    html_path = Path(args.html).resolve()
    if not html_path.is_file():
        print(f"error: {html_path} is not a file", file=sys.stderr)
        return 1
    answers_path = html_path.parent / "walkthrough-answers.json"
    questions_path = html_path.parent / "walkthrough-questions.jsonl"
    replies_path = html_path.parent / "walkthrough-replies.json"

    pages = Pages()
    server = bind(args.port, make_handler(html_path, answers_path, questions_path, replies_path, session, args.model,
                                          pages))
    if server is None:
        print(f"error: ports {args.port} to {args.port + PORT_ATTEMPTS - 1} are all in use", file=sys.stderr)
        return 1
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"Serving {url}", flush=True)
    print(f"Answers will be written to {answers_path}", flush=True)
    print(f"Questions from the page go to {questions_path}; answers to {replies_path}", flush=True)
    if session:
        print(f"Page questions are answered by a fork of session {session} with model {args.model}", flush=True)
    else:
        print("No session to fork: page questions wait until the agent is told to check them", flush=True)

    if args.open:
        open_browser(url)

    reason = []

    def watch():
        while not reason:
            time.sleep(1)
            found = pages.exit_reason()
            if found:
                reason.append(found)
                server.shutdown()

    def stop(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    threading.Thread(target=watch, daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        reason.append("stopped")
    finally:
        server.server_close()
    steps_path = html_path.with_suffix(".json")
    files = [p for p in (html_path, steps_path, answers_path, questions_path, replies_path) if p.exists()]
    print(f"Server exited ({reason[0] if reason else 'stopped'}). Walkthrough files:", flush=True)
    for p in files:
        print(f"  {p}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
