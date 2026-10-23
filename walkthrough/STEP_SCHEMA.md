# Walkthrough step schema

A walkthrough is one JSON document. `scripts/build.py` validates it and injects it into `template.html`. The renderer reads `WALKTHROUGH` (the whole document) and shows one step at a time.

## Top level

```json
{
  "mode": "design | commit | history | repo",
  "title": "Short name, 3 to 6 words",
  "subtitle": "Optional one line of context (repo name, commit sha, date)",
  "narration": true,
  "diagram": { "nodes": [], "edges": [], "groups": [] },
  "steps": []
}
```

`narration` is optional. `true` or `false` sets whether read-aloud starts on when the page loads, overriding the last toggle saved in the browser. Absent, the saved toggle applies (on by default).

`diagram` is optional, but required if any step uses a `diagram` visual. It declares every node, edge and group once. Steps then add, highlight or remove them by id. The renderer keeps the diagram state across steps, so a step only names what is new.

## Diagram definition

```json
{
  "width": 800,
  "height": 450,
  "nodes": [
    { "id": "api", "label": "API", "sub": "FastAPI", "x": 320, "y": 80, "w": 160, "h": 60, "kind": "service" }
  ],
  "edges": [
    { "id": "api-db", "from": "api", "to": "db", "label": "SQL", "dashed": false }
  ],
  "groups": [
    { "id": "cloud", "label": "GCP", "x": 280, "y": 40, "w": 480, "h": 360 }
  ]
}
```

Rules:
- `width` and `height` default to 800 x 450. Coordinates are in that viewBox. `x, y` is the top-left corner. `w` defaults to 150, `h` to 56.
- `kind` is optional and picks a fill: `service` (default), `store`, `client`, `external`, `queue`, `infra`.
- `files` is an optional list of paths, relative to `build.py --root`, that implement the node (`"files": ["src/pen/config.py"]`). The page lists them when the box is hovered and opens the code in a left panel on click. `build.py` embeds each file's text under the top-level `files` key (`{path: text}`); files over 200,000 characters are cut.
- Edge `id` is optional; default is `"<from>-><to>"`. `label` and `dashed` are optional.
- Groups are background rectangles with a label in the corner. They are added and removed like nodes.
- Keep the whole diagram under about 12 nodes. More than that is not a walkthrough.

## Step

```json
{
  "id": "s1",
  "title": "Max eight words",
  "text": "Up to 40 words. Plain text. Backticks mark `identifiers`.",
  "narration": "Up to 25 words. Spoken by the browser. Summarize the step, do not repeat the text.",
  "visual": { "type": "diagram | diff | code" },
  "interaction": { "type": "choice | review | note" }
}
```

`id`, `title`, `text`, `narration`, `visual` are required. `interaction` is optional. Step ids must be unique.

`text` may link a key statement to the code that shows it: `[CaGuard checks every 5 s](pen/src/pen/broker.py#L273-284)`. The path is relative to `build.py --root`, lines are 1-based (`#L12` for one line). The page shows the label as a link; a click opens the file panel scrolled to the range with those lines highlighted. `build.py` embeds the file and fails if it is missing or the range is outside it.

## Visual types

### diagram (cumulative)

```json
{ "type": "diagram", "add": ["api", "db", "api->db"], "highlight": ["db"], "remove": [], "caption": "optional one line" }
```

Ids refer to nodes, edges or groups in the top-level `diagram`. State carries over: elements added in step 2 are still visible in step 5 unless removed. Within one step `add` applies before `remove`. An edge is hidden whenever either of its endpoints is hidden. Elements in `highlight` get the accent color for this step only and everything else is dimmed; when `highlight` is absent the elements added this step are highlighted; `highlight: []` means no accent and no dimming. The renderer animates new elements in and keeps old ones at reduced emphasis, which gives the whiteboard build-up effect.

### diff

```json
{
  "type": "diff",
  "file": "src/auth/session.py",
  "lang": "python",
  "hunk": "@@ -12,6 +12,9 @@ def create_session(user):\n     token = secrets.token_urlsafe(32)\n-    store[token] = user.id\n+    store[token] = SessionRecord(user.id, expires=now() + TTL)\n",
  "highlight": [4],
  "caption": "optional one line"
}
```

`hunk` is unified diff text with `+`, `-` and space prefixes. Keep it under 20 lines; pick the lines that carry the idea. `highlight` lists 1-based line numbers inside the hunk to emphasize. The `@@` header counts as line 1, so in the example `[4]` is the `+` line.

### code

```json
{ "type": "code", "file": "main.go", "lang": "go", "code": "func main() {\n ...\n}", "highlight": [2, 3], "caption": "optional one line" }
```

Same as diff without prefixes. Under 20 lines.

## Interaction types

All answers are collected and written to `walkthrough-answers.json` (see `scripts/serve.py`).

### choice (design mode)

```json
{
  "type": "choice",
  "prompt": "Which database?",
  "options": [
    { "id": "postgres", "label": "Postgres", "pros": "Relational, mature, one service", "cons": "Needs a managed instance" },
    { "id": "sqlite", "label": "SQLite", "pros": "No server, trivial local dev", "cons": "Single writer" }
  ],
  "recommended": "postgres",
  "note": true
}
```

One option is picked. `recommended` is optional and marks the agent's suggestion. `note: true` shows a free-text field.

### review (commit and history modes)

```json
{ "type": "review", "prompt": "Does this step make sense?" }
```

Shows two buttons: approve, flag, plus a free-text note. `prompt` is optional.

### note (repo mode and anywhere)

```json
{ "type": "note", "prompt": "Unclear? Write what to explain." }
```

Free text only.

## Questions file

Each "Ask the agent" click posts one object to `/ask`; `serve.py` appends it as one line to `walkthrough-questions.jsonl`:

```json
{"id": "qm2x1k9z", "step": "s3", "title": "Mounts hide secrets", "question": "Why not hide .envrc too?", "asked": "2026-10-21T09:40:12Z"}
```

The agent answers in `walkthrough-replies.json`, keyed by question id; the page polls `/replies` and shows the text under the question:

```json
{ "qm2x1k9z": "direnv on the host executes .envrc, so pen hides it since today." }
```

## Answers file

```json
{
  "title": "Session store redesign",
  "mode": "design",
  "submitted": "2026-10-21T14:03:11Z",
  "answers": {
    "s3": { "step": "Pick the database", "type": "choice", "choice": "postgres", "note": "we already run Cloud SQL" },
    "s5": { "step": "Token rotation", "type": "review", "verdict": "flag", "note": "why 32 bytes?" },
    "s7": { "step": "Request path", "type": "note", "skipped": true }
  }
}
```

Only steps with an interaction appear. A step counts as answered when it has a choice, a verdict, or non-empty note text. Otherwise the entry has `"skipped": true` and no `choice`, `verdict` or `note`.

## Limits the builder enforces

Errors (build fails): missing required field, unknown mode, unknown visual or interaction type, duplicate step id, diagram id not declared, fewer than 3 steps, choice with fewer than 2 options, text link to a missing file or a line range outside it.

Warnings (build continues, prints them): text over 40 words, narration over 25 words, more than 12 steps, hunk or code over 20 lines, diagram over 12 nodes.
