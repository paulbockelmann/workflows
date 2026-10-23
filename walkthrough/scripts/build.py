#!/usr/bin/env python3
"""Validate a walkthrough JSON document and inject it into template.html.

Usage: python3 build.py <steps.json> [--out <path>] [--template <path>] [--strict]
"""
import argparse
import datetime
import json
import re
import sys
from pathlib import Path

MARKER = "/*__WALKTHROUGH_DATA__*/null"
MODES = {"design", "commit", "history", "repo"}
VISUAL_TYPES = {"diagram", "diff", "code"}
INTERACTION_TYPES = {"choice", "review", "note"}
NODE_KINDS = {"service", "store", "client", "external", "queue", "infra"}
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)#\s]+)#L(\d+)(?:-L?(\d+))?\)")
MAX_TEXT_WORDS = 40
MAX_NARRATION_WORDS = 25
MAX_STEPS = 12
MAX_LINES = 20
MAX_NODES = 12


def words(s):
    return len(s.split())


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def is_pos_int(v):
    return isinstance(v, int) and not isinstance(v, bool) and v > 0


def validate(doc):
    errors, warnings = [], []
    err = errors.append
    warn = warnings.append

    if not isinstance(doc, dict):
        return ["document: top level must be a JSON object"], []

    for key in ("mode", "title", "steps"):
        if key not in doc:
            err(f"document: missing required field '{key}'")
    mode = doc.get("mode")
    if "mode" in doc and mode not in MODES:
        err(f"document: unknown mode {mode!r}, expected one of {sorted(MODES)}")
    if "title" in doc and (not isinstance(doc["title"], str) or not doc["title"].strip()):
        err("document: 'title' must be a non-empty string")
    if "subtitle" in doc and not isinstance(doc["subtitle"], str):
        err("document: 'subtitle' must be a string")

    # Collect declared diagram ids.
    diagram = doc.get("diagram")
    declared = set()
    node_ids = set()
    if diagram is not None:
        if not isinstance(diagram, dict):
            err("diagram: must be an object")
            diagram = None
    if diagram is not None:
        for key in ("width", "height"):
            if key in diagram and not (is_num(diagram[key]) and diagram[key] > 0):
                err(f"diagram.{key}: must be a positive number")

        def declare(path, ident):
            if not isinstance(ident, str) or not ident:
                err(f"{path}: id must be a non-empty string")
                return False
            if ident in declared:
                err(f"{path}: duplicate diagram id {ident!r}")
                return False
            declared.add(ident)
            return True

        nodes = diagram.get("nodes", [])
        if not isinstance(nodes, list):
            err("diagram.nodes: must be a list")
            nodes = []
        for i, n in enumerate(nodes):
            path = f"diagram.nodes[{i}]"
            if not isinstance(n, dict):
                err(f"{path}: must be an object")
                continue
            for key in ("id", "label", "x", "y"):
                if key not in n:
                    err(f"{path}: missing required field '{key}'")
            if "id" in n and declare(path, n["id"]):
                node_ids.add(n["id"])
            for key in ("x", "y", "w", "h"):
                if key in n and not is_num(n[key]):
                    err(f"{path}.{key}: must be a number")
            if "kind" in n and n["kind"] not in NODE_KINDS:
                err(f"{path}.kind: unknown kind {n['kind']!r}, expected one of {sorted(NODE_KINDS)}")
            if "files" in n and not (isinstance(n["files"], list) and all(isinstance(f, str) and f for f in n["files"])):
                err(f"{path}.files: must be a list of non-empty path strings")
        if len(nodes) > MAX_NODES:
            warn(f"diagram: {len(nodes)} nodes, limit is {MAX_NODES}")

        edges = diagram.get("edges", [])
        if not isinstance(edges, list):
            err("diagram.edges: must be a list")
            edges = []
        for i, e in enumerate(edges):
            path = f"diagram.edges[{i}]"
            if not isinstance(e, dict):
                err(f"{path}: must be an object")
                continue
            for key in ("from", "to"):
                if key not in e:
                    err(f"{path}: missing required field '{key}'")
                elif e[key] not in node_ids:
                    err(f"{path}.{key}: {e[key]!r} is not a declared node")
            if "id" in e:
                declare(path, e["id"])
            elif "from" in e and "to" in e:
                declare(path, f"{e['from']}->{e['to']}")

        groups = diagram.get("groups", [])
        if not isinstance(groups, list):
            err("diagram.groups: must be a list")
            groups = []
        for i, g in enumerate(groups):
            path = f"diagram.groups[{i}]"
            if not isinstance(g, dict):
                err(f"{path}: must be an object")
                continue
            for key in ("id", "x", "y", "w", "h"):
                if key not in g:
                    err(f"{path}: missing required field '{key}'")
            if "id" in g:
                declare(path, g["id"])
            for key in ("x", "y", "w", "h"):
                if key in g and not is_num(g[key]):
                    err(f"{path}.{key}: must be a number")

    steps = doc.get("steps")
    if "steps" in doc and not isinstance(steps, list):
        err("document: 'steps' must be a list")
        steps = None
    if not steps:
        if isinstance(steps, list):
            err("document: fewer than 3 steps (found 0)")
        return errors, warnings
    if len(steps) < 3:
        err(f"document: fewer than 3 steps (found {len(steps)})")
    if len(steps) > MAX_STEPS:
        warn(f"document: {len(steps)} steps, limit is {MAX_STEPS}")

    seen_ids = set()
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            err(f"steps[{i}]: must be an object")
            continue
        sid = step.get("id")
        where = f"step {sid}" if isinstance(sid, str) and sid else f"steps[{i}]"
        for key in ("id", "title", "text", "narration", "visual"):
            if key not in step:
                err(f"{where}: missing required field '{key}'")
        for key in ("id", "title", "text", "narration"):
            if key in step and (not isinstance(step[key], str) or not step[key].strip()):
                err(f"{where}: '{key}' must be a non-empty string")
        if isinstance(sid, str) and sid:
            if sid in seen_ids:
                err(f"steps[{i}]: duplicate step id {sid!r}")
            seen_ids.add(sid)
        if isinstance(step.get("text"), str) and words(step["text"]) > MAX_TEXT_WORDS:
            warn(f"{where}: text has {words(step['text'])} words, limit is {MAX_TEXT_WORDS}")
        if isinstance(step.get("narration"), str) and words(step["narration"]) > MAX_NARRATION_WORDS:
            warn(f"{where}: narration has {words(step['narration'])} words, limit is {MAX_NARRATION_WORDS}")

        if "visual" in step:
            check_visual(step["visual"], where, diagram is not None, declared, err, warn)
        if "interaction" in step:
            check_interaction(step["interaction"], where, err)

    return errors, warnings


def check_highlight_lines(v, where, err):
    hl = v.get("highlight")
    if hl is None:
        return
    if not isinstance(hl, list) or not all(is_pos_int(x) for x in hl):
        err(f"{where}: visual.highlight must be a list of positive integers")


def check_visual(v, where, has_diagram, declared, err, warn):
    if not isinstance(v, dict):
        err(f"{where}: visual must be an object")
        return
    vtype = v.get("type")
    if "type" not in v:
        err(f"{where}: visual missing required field 'type'")
        return
    if vtype not in VISUAL_TYPES:
        err(f"{where}: unknown visual type {vtype!r}, expected one of {sorted(VISUAL_TYPES)}")
        return
    if "caption" in v and not isinstance(v["caption"], str):
        err(f"{where}: visual.caption must be a string")

    if vtype == "diagram":
        if not has_diagram:
            err(f"{where}: diagram visual requires a top-level 'diagram'")
        for key in ("add", "highlight", "remove"):
            ids = v.get(key)
            if ids is None:
                continue
            if not isinstance(ids, list):
                err(f"{where}: visual.{key} must be a list")
                continue
            for ident in ids:
                if has_diagram and ident not in declared:
                    err(f"{where}: visual.{key} references undeclared diagram id {ident!r}")
        return

    field = "hunk" if vtype == "diff" else "code"
    if field not in v:
        err(f"{where}: {vtype} visual missing required field '{field}'")
    elif not isinstance(v[field], str):
        err(f"{where}: visual.{field} must be a string")
    else:
        n = len(v[field].rstrip("\n").split("\n"))
        if n > MAX_LINES:
            warn(f"{where}: {field} has {n} lines, limit is {MAX_LINES}")
    for key in ("file", "lang"):
        if key in v and not isinstance(v[key], str):
            err(f"{where}: visual.{key} must be a string")
    check_highlight_lines(v, where, err)


def check_interaction(it, where, err):
    if not isinstance(it, dict):
        err(f"{where}: interaction must be an object")
        return
    itype = it.get("type")
    if "type" not in it:
        err(f"{where}: interaction missing required field 'type'")
        return
    if itype not in INTERACTION_TYPES:
        err(f"{where}: unknown interaction type {itype!r}, expected one of {sorted(INTERACTION_TYPES)}")
        return
    if "prompt" in it and not isinstance(it["prompt"], str):
        err(f"{where}: interaction.prompt must be a string")
    if itype != "choice":
        return
    if "prompt" not in it:
        err(f"{where}: choice missing required field 'prompt'")
    options = it.get("options")
    if not isinstance(options, list) or len(options) < 2:
        err(f"{where}: choice with fewer than 2 options")
        options = options if isinstance(options, list) else []
    option_ids = set()
    for j, opt in enumerate(options):
        path = f"{where}: options[{j}]"
        if not isinstance(opt, dict):
            err(f"{path} must be an object")
            continue
        for key in ("id", "label"):
            if key not in opt:
                err(f"{path} missing required field '{key}'")
        oid = opt.get("id")
        if oid is not None:
            if oid in option_ids:
                err(f"{path} duplicate option id {oid!r}")
            option_ids.add(oid)
    if "recommended" in it and it["recommended"] not in option_ids:
        err(f"{where}: choice.recommended {it['recommended']!r} is not an option id")
    if "note" in it and not isinstance(it["note"], bool):
        err(f"{where}: choice.note must be true or false")


MAX_FILE_CHARS = 200_000
HLJS_CSS_MARKER = "/*__HLJS_CSS__*/"
HLJS_JS_MARKER = "/*__HLJS_JS__*/"
HLJS_LANGUAGES = ("python", "javascript", "typescript", "bash", "dockerfile", "json", "diff", "yaml", "go")


def inline_highlighter(html, vendor):
    """Inline highlight.js and its two GitHub themes from vendor/ so the page colours code offline. Without the
    files the page still works, uncoloured."""
    core = vendor / "highlight.min.js"
    if not core.is_file():
        print(f"warning: {core} missing, code is not coloured (see SKILL.md for the download)", file=sys.stderr)
        return html
    js = [core.read_text(encoding="utf-8")]
    for lang in HLJS_LANGUAGES:
        f = vendor / f"{lang}.min.js"
        if f.is_file():
            js.append(f.read_text(encoding="utf-8"))
        else:
            print(f"warning: {f} missing, {lang} is not coloured", file=sys.stderr)
    css = ""
    light, dark = vendor / "github.min.css", vendor / "github-dark.min.css"
    if light.is_file():
        css += light.read_text(encoding="utf-8")
    if dark.is_file():
        css += "\n@media (prefers-color-scheme: dark) {\n" + dark.read_text(encoding="utf-8") + "\n}"
    script = "\n".join(js).replace("</script", "<\\/script")
    return html.replace(HLJS_CSS_MARKER, css, 1).replace(HLJS_JS_MARKER, script, 1)


def embed_files(doc, root, warn, err):
    """Read every path listed in a node's `files` or linked from a step's text ([label](path#L3-9)) relative to root
    into doc['files'], so the page can show the code without a server. A link to a missing file or line is an error."""
    paths = []
    for n in (doc.get("diagram") or {}).get("nodes", []):
        for p in n.get("files", []):
            if p not in paths:
                paths.append(p)
    links = []
    for step in doc.get("steps", []):
        for m in LINK_RE.finditer(step.get("text", "")):
            start = int(m.group(3))
            links.append((step.get("id"), m.group(2), start, int(m.group(4) or start)))
            if m.group(2) not in paths:
                paths.append(m.group(2))
    if not paths:
        return
    linked = {p for _, p, _, _ in links}
    files = {}
    for p in paths:
        full = root / p
        try:
            text = full.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            (err if p in linked else warn)(f"files: cannot read {full}: {getattr(e, 'strerror', None) or e}")
            continue
        if len(text) > MAX_FILE_CHARS:
            warn(f"files: {p} is {len(text)} characters, showing the first {MAX_FILE_CHARS}")
            text = text[:MAX_FILE_CHARS] + "\n[truncated]\n"
        files[p] = text
    for sid, p, start, end in links:
        if p in files and not 1 <= start <= end <= len(files[p].splitlines()):
            err(f"step {sid}: link {p}#L{start}-{end} is outside the file's {len(files[p].splitlines())} lines")
    doc["files"] = files


def main():
    ap = argparse.ArgumentParser(description="Validate a walkthrough JSON and build the HTML page.")
    ap.add_argument("steps", help="walkthrough JSON document")
    ap.add_argument("--out", help="output HTML path (default ./.walkthrough/<mode>-<timestamp>.html)")
    ap.add_argument("--template", help="template HTML (default ../template.html next to this script)")
    ap.add_argument("--root", help="directory that node 'files' and text link paths are relative to (default: current directory)")
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = ap.parse_args()

    try:
        doc = json.loads(Path(args.steps).read_text(encoding="utf-8"))
    except OSError as e:
        print(f"error: {args.steps}: {e.strerror}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"error: {args.steps}: invalid JSON at line {e.lineno} column {e.colno}: {e.msg}", file=sys.stderr)
        return 1

    errors, warnings = validate(doc)
    if not errors:
        embed_files(doc, Path(args.root).resolve() if args.root else Path.cwd(), warnings.append, errors.append)
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    for e in errors:
        print(f"error: {e}", file=sys.stderr)
    if errors or (args.strict and warnings):
        return 1

    template_path = Path(args.template) if args.template else Path(__file__).resolve().parent.parent / "template.html"
    try:
        template = template_path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"error: template {template_path}: {e.strerror}", file=sys.stderr)
        return 1
    if MARKER not in template:
        print(f"error: template {template_path}: marker {MARKER} not found", file=sys.stderr)
        return 1

    data = json.dumps(doc, ensure_ascii=False).replace("</", "<\\/")
    html = template.replace(MARKER, data, 1)
    html = inline_highlighter(html, template_path.parent / "vendor")

    if args.out:
        out = Path(args.out)
    else:
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        out = Path.cwd() / ".walkthrough" / f"{doc['mode']}-{stamp}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(out.resolve())
    return 0


if __name__ == "__main__":
    sys.exit(main())
