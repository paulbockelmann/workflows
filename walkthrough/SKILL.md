---
name: walkthrough
description: Builds a step-by-step visual walkthrough as one self-contained HTML page (SVG diagram that grows per step, diff hunks, optional voice narration, clickable answers that come back to the agent) for four kinds of code work, then opens it in the default browser. Modes are design (derive an architecture before code exists, user picks options), commit (explain one commit), history N (last N commits as a story), repo (explain an existing repo's architecture). Use when the user says "walk me through", "explain this commit visually", "visualize the repo architecture", "show me the last N commits", "design discussion", "whiteboard this", or types /walkthrough.
---

# Walkthrough

Teacher-at-a-whiteboard explanation for a visual learner: few words per step, one visual per step, the diagram builds up, the user steps through with arrow keys. Answers the user gives on the page are written to `walkthrough-answers.json` and drive what happens next.

## Modes

| Mode | Argument | Use |
|---|---|---|
| `design` | topic | Before code exists. One architecture decision per step, user picks options. |
| `commit` | sha, default `HEAD` | Explain one commit the agent just made. |
| `history` | N | Last N commits as a progressive story. |
| `repo` | none | Build up the architecture diagram of the current repo. |

Pick the mode from the request. Ask only if it is unclear whether the user wants a commit or a design discussion.

## Workflow

Paths below are relative to this skill's directory (the base directory shown when the skill loads), written as `<skill dir>`.

1. Ask with AskUserQuestion whether to turn on narration (read-aloud). Say in one line that Chrome's Google voices and Edge's Online voices send the narration text to Google or Microsoft; Firefox, Safari and Windows desktop voices stay local. Set the top-level `narration` in the JSON to the answer.
   Then gather material and pick 5 to 12 ideas following the mode section in [MODES.md](MODES.md).
2. Write the steps JSON per [STEP_SCHEMA.md](STEP_SCHEMA.md). Copy the shape from the matching file in `examples/`. Declare the full diagram once, then reveal it with `add` per step.
3. Run the "Checklist before building" in MODES.md over the JSON. Fix, then build:

   ```bash
   mkdir -p .walkthrough
   STEM=.walkthrough/<mode>-$(date +%Y%m%d-%H%M%S)
   # write $STEM.json, then:
   python3 <skill dir>/scripts/build.py $STEM.json --out $STEM.html --root <project dir>
   ```

   `--root` is the directory that each diagram node's `files` list is relative to; `build.py` embeds those files so the page can show the code behind a box. Give every node that maps to code a `files` list (2 to 6 paths). Link a key statement in a step's `text` to its code (`[label](path#L12-30)`, see STEP_SCHEMA.md) only when one exact place in the code shows it; at most two links per step, none for general statements. Read the file for the line numbers right before building. `build.py` fails on schema errors and prints warnings for word and size limits. Fix errors; treat warnings as cuts to make. If the cwd is not a project, use the session scratchpad directory instead of `.walkthrough/`.
4. Serve and open, as a background Bash process:

   ```bash
   python3 <skill dir>/scripts/serve.py $STEM.html --open
   ```

   It prints the URL and the answers path, opens the default browser and keeps running. Do not open the file yourself.
5. Tell the user in two or three lines: the page is open, arrow keys or Next step through, narration is on or off as chosen and the speaker button or `m` toggles it, hovering a diagram box lists its files and a click opens the code, "Ask the agent" under the notes sends a question, press "Finish / send answers" at the end and paste the note it offers here.
6. Questions from the page: "Ask the agent" posts to `/ask`. `serve.py` appends the question to `walkthrough-questions.jsonl`, then runs `claude -p --resume <session> --fork-session` (read-only tools, model sonnet by default) and writes the answer to `walkthrough-replies.json`; the page polls `/replies` and shows it under the question within a few seconds. The session id comes from `$CLAUDE_CODE_SESSION_ID`, which the Bash tool sets, so nothing extra is needed; pass `--session <id>` when serving from elsewhere, `--model opus` for harder material, `--no-agent` to only record questions. With `--no-agent` or no session, the user says "check questions" here, you read the jsonl, answer in chat and write `{"<question id>": "<answer>"}` into the replies file (merge, never drop earlier ids). Questions and answers also sit in those two files when the user says done; read them before acting on the answers.
7. When the user pastes the review note (or says done): read `walkthrough-answers.json` next to the HTML, stop the server (kill the background process), then act on the answers as the mode section in MODES.md says (design: restate the chosen architecture and continue; commit and history: answer flags and notes; repo: answer notes). State positions and proposed changes first; implement nothing until the user confirms. If the file is missing, ask the user to paste the JSON the page showed under "Copy answers".

8. The server exits 15 s after the last page tab closes (a reload keeps it running), 2 minutes after the page stops polling (close signal blocked, browser quit), or after 30 minutes without any request, and prints the walkthrough files that exist. Its exit re-invokes you. If the user pressed Finish but has not pasted the review note yet, say so first. Then ask with AskUserQuestion what to keep: everything (default), the answers only (delete the HTML and steps JSON), or nothing. Delete only what the user picks, only the files the server listed.

`.walkthrough/` is a scratch folder. Do not commit it; add it to `.gitignore` if the repo has one and it is not already ignored.

## Content rules

Apply the writing rules at the top of MODES.md to every title, text, narration, caption, option and prompt. In short: no em-dashes, no banned words, no praise, active voice, name files and identifiers, say why. Write in terms a software engineer outside the project understands; no coined shorthand (MODES.md, "Plain terms").

Limits: 5 to 12 steps, text at most 40 words, narration at most 25 words and a summary rather than a reading of the text, title at most 8 words, diagram at most 12 nodes, hunks and code at most 20 lines. Core ideas only: architecture, technologies, data flow, the reason behind a change. Every step has a visual.

## Files

- `template.html`: renderer. `build.py` injects the JSON at `/*__WALKTHROUGH_DATA__*/null`. Works from `file://` (answers via copy button) and from `serve.py` (answers posted to `/answers`).
- `scripts/build.py <steps.json> [--out p] [--template p] [--root dir] [--strict]`: validate, embed node files, build.
- `scripts/serve.py <html> [--port 8765] [--open] [--session id] [--model m] [--no-agent]`: serve on localhost until the page closes, write `walkthrough-answers.json` next to the HTML on POST `/answers`, append questions to `walkthrough-questions.jsonl` on POST `/ask` and answer them through a fork of the building session into `walkthrough-replies.json`, served on GET `/replies`.
- `examples/{design,commit,history,repo}.json`: one valid document per mode.
- `vendor/`: highlight.js 11.9.0 (`highlight.min.js`, language files, `github.min.css`, `github-dark.min.css`), inlined by `build.py` so code views, diff hunks and the file panel are coloured offline. If the folder is missing, the page builds uncoloured and `build.py` warns; restore it with: `mkdir -p <skill dir>/vendor && cd $_ && for f in highlight.min.js languages/dockerfile.min.js styles/github.min.css styles/github-dark.min.css; do curl -sSf -o "$(basename $f)" "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/$f"; done`.

Page keys: ArrowRight, Space or j next; ArrowLeft or k prev; Home, End; r replay narration; m toggle narration; Escape closes the file panel; Cmd-Enter in the question box sends it. `#step-N` or `?step=N` (1-based, hash wins) opens a given step; the page updates the hash as the user moves.
