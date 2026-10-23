# Walkthrough modes

Per-mode playbook for building the steps JSON. The format is defined in [STEP_SCHEMA.md](STEP_SCHEMA.md); this file decides what goes into it. Every mode follows the same loop: gather material, pick the 5 to 12 ideas that matter, lay out the diagram, write the steps, run the checklist at the bottom, build, then act on `walkthrough-answers.json`.

The reader is a visual learner. Each step teaches one idea with a picture and a few words. Leave out everything the picture does not need.

## Writing rules for step text and narration

- Banned words: delve, dive into, navigate, leverage, harness, foster, unpack, shed light on, pave the way, underscore, bolster, empower, tapestry, testament, pivotal, beacon, crucial, transformative, game-changer, seamless, bespoke, nuanced, multifaceted, robust, scalable, streamline, cutting-edge, elevate, unlock, supercharge, holistic, powerful, essentially, fundamentally, notably, importantly, arguably, ultimately, indeed, in essence, let's, as you can see, keep in mind.
- No em-dashes. Use a comma, colon, period or parentheses.
- No throat-clearing ("Here we look at..."), no praise ("Nice choice"), no closing pull-quotes.
- No false contrasts ("It's not X, it's Y"). State Y.
- Active voice with a subject: "`build.py` validates the JSON", not "the JSON is validated".
- Concrete particulars: name the file, function, table, env var or service. "`session.py` stores a `SessionRecord`" beats "the session logic was improved".
- Say why, not only what. A hunk without its reason is noise.
- One idea per step. If the text needs "and also", split the step or cut the second idea.
- Narration summarizes the step in spoken form. It never reads the text aloud. Text: "`create_session` now stores an expiry with each token, so `get_session` can reject stale ones." Narration: "Sessions now expire on their own."
- A diagram node label is one to three words ("API", "Session store"). Put the technology in `sub` ("FastAPI", "Redis").
- Step titles are at most eight words and say the point: "Tokens now expire after 30 minutes", not "Changes to session.py".

## Plain terms

The reader is a software engineer who knows the usual tools (git, HTTP, Docker, sudo, a firewall) but not this project, its internals or niche networking and OS terms. Every title and sentence must make sense to that reader without asking.

- Use the term an engineer would search for. A niche term gets a few-word explanation the first time, or is replaced by what it does: "automatic IPv6 addresses (`fe80::`)", not "link-local".
- Never coin a compressed phrase. Say what changed: "fewer sudo log entries", not "quieter sudo"; "denies all requests when the config is broken", not "fails closed"; "pen's firewall rules", not "the anchor"; "a read-only mount over the folder", not "an overlay".
- A project name (a class, a Keychain entry, a CLI flag) appears in backticks with what it is: "`CaGuard`, the broker's CA check".
- A title is one statement with a subject and a verb, not a list of fragments: "Firewall now blocks the containers' IPv6 addresses", not "Firewall: link-local, status, quieter sudo". Two topics in a title means two steps or one dropped.
- When a word limit forces shorthand, drop a detail instead.
- Test each title and sentence: would an engineer outside the project understand it on its own and know what to look up?

## Diagram layout

Default grid in the 800 x 450 viewBox, with node `w` 150 and `h` 56:

| | col 1 | col 2 | col 3 |
|---|---|---|---|
| x | 60 | 325 | 590 |
| rows y | 40, 140, 240, 340 | same | same |

Left to right is request direction: clients in column 1, services in column 2, stores and external services in column 3. Top to bottom is layers: entry points on top, infra at the bottom. Draw a group around a column or row with about 20 px margin, for example a cloud boundary around columns 2 and 3: `x: 305, y: 20, w: 455, h: 400`. Two nodes in one cell means the diagram is too dense; merge them or drop one. Declare every node, edge and group up front in the top-level `diagram`, then reveal them with `add` step by step.

## Sizing

5 to 12 steps. The builder warns above 12 and fails below 3. If the material needs more, cut details first (config tweaks, renames, tests that mirror the code). If it still needs more, split into two walkthroughs, for example "request path" and "background jobs", and tell the user the second one exists.

## design

Applies before code exists, when the user wants to work out architecture with the agent.

Gather:
- Ask for the goal only if the conversation does not state it. One question, then proceed.
- Read what exists so options match reality: `package.json`, `pyproject.toml`, `go.mod`, `Dockerfile`, `docker-compose.yml`, `terraform/`, `.github/workflows/`, `firebase.json`, any `.env.example`. An existing Postgres or GCP project is a constraint, not an option to reopen.
- Skip source code reading beyond what reveals the stack.

Arc (one decision per step, open questions become nodes immediately so the picture is complete at the end):

| # | Title example | Visual | Interaction |
|---|---|---|---|
| 1 | Upload receipts, get monthly totals | diagram: client and goal | none |
| 2 | Three constraints shape everything | diagram: highlight constraint group | none |
| 3 | Backend: Python or Node? | diagram: add "Backend?" node | choice |
| 4 | Where the receipts live | diagram: add "Store?" node, edge | choice |
| 5 | Frontend: server pages or SPA? | diagram: add "Frontend?" node | choice |
| 6 | Who may log in | diagram: add "Auth?" node | choice |
| 7 | Hosting on Cloud Run or a VM | diagram: add infra group | choice |
| 8 | Model for receipt extraction | diagram: add "Model?" external node | choice (only if AI features) |
| 9 | Names for services and tables | code: proposed names | note |
| 10 | The whole picture | diagram: highlight request path | none |

Each `choice` has 2 to 4 options, pros and cons under ten words each, `recommended` set to the agent's pick, and `note: true`. Put the options in the node's `sub` ("Postgres or SQLite") so the open question reads on the diagram. Keep decisions in dependency order: data store before ORM, hosting after backend.

Afterwards: read the answers. Restate the chosen architecture in chat in three to six lines (component, choice, one reason). Treat a note that contradicts the pick as the stronger signal and ask once. Skipped decisions take the recommended option; say so. Then implement, or build a second, more concrete walkthrough (modules, tables, endpoints) if the user asked for one.

## commit

Applies right after the agent made a commit, to explain it. Default `HEAD`, or the sha the user gave.

Gather:

```bash
git log -1 --format=%B <sha>
git show --stat <sha>
git show <sha> -- <path>
```

Run the last command per touched file that carries logic. Skip lockfiles, generated files, snapshots and pure formatting. Read the surrounding code of each hunk only as far as needed to explain the why.

Arc:

| # | Title example | Visual | Interaction |
|---|---|---|---|
| 1 | Sessions never expired | diagram: affected flow | none |
| 2 | The change lands in auth and store | diagram: highlight touched nodes | none |
| 3 to 7 | Each token now carries an expiry | diff: 2 to 5 hunks, one per step | review |
| last | Logout works; cleanup job is next | diagram or code: what now works | review |

Step 1 states intent: why the commit exists. Hunk steps highlight the two to four lines that carry the idea and explain why they changed. The consequences step covers what now works, what breaks without the commit, and follow-ups.

Afterwards: answer every `flag` and note in chat, quoting the step title. A flag that points at a real defect leads to a fix commit; say what the fix changes before making it. Approvals need no reply.

## history N

Applies when the user wants the last N commits told as one story.

Gather:

```bash
git log --oneline -n N --reverse
git show --stat <sha>              # per commit
git diff <first>^..<last> --stat   # total change
```

Group trivial commits (formatting, version bumps, typo fixes, merge commits) into one step or drop them. One step per meaningful commit or logical group of commits. For each group pick the one hunk that best shows the idea with `git show <sha> -- <path>`.

Arc:

| # | Title example | Visual | Interaction |
|---|---|---|---|
| 1 | Before: one script, no tests | diagram: starting state | none |
| 2 to n-1 | `a1b2c3d` adds the job queue | diagram: add what the commit introduced | review |
| optional | The retry loop in `worker.py` | diff: key hunk of a group | review |
| last | Now: API, queue, two workers | diagram: highlight the full system | none |

Put short shas in titles or `caption` so the user can map steps to the log. Use `remove` when a commit deletes a component.

Afterwards: answer flags and notes in chat per step. If a flag concerns an older commit, propose a fix commit on top; do not rewrite history unless the user asks.

## repo

Applies when the user wants an existing repo's architecture explained.

Gather:
- If `graphify-out/` exists, query its graph first for components and connections, then read files only to confirm.
- `ls`, then `tree -L 2 -I 'node_modules|.git|dist|build|.venv|__pycache__'`, or `find . -maxdepth 2 -not -path '*/.git*' -not -path '*/node_modules*'` if `tree` is missing.
- Read the README, manifests (`package.json`, `pyproject.toml`, `go.mod`), entry points (`main.*`, `app.*`, `index.*`, `cmd/`), config, `Dockerfile`, `docker-compose.yml`, CI under `.github/workflows/`, migrations.
- Skip tests, vendored code and generated clients unless they are the point of the repo.

Arc:

| # | Title example | Visual | Interaction |
|---|---|---|---|
| 1 | Turns invoices into ledger entries | diagram: client and system box | none |
| 2 | Two ways in: web and cron | diagram: add entry points | none |
| 3 to 8 | FastAPI app owns all writes | diagram: add one component and its edges | note |
| next | One upload, start to finish | diagram: highlight the request path | none |
| next | GitHub Actions builds, Cloud Run serves | diagram: add infra group | none |
| last | Where to look first | code: list of file paths with one-line roles | none |

One component per step: client, API, services, stores, queues, external services, infra. The data-flow step adds nothing and highlights the nodes and edges on one concrete path. The last step's `code` visual is a plain list like `api/main.py      # routes`, under 20 lines. Note prompt: "Unclear? Write what to explain."

Afterwards: answer each non-empty note in chat. If a note asks about one component in depth, offer a follow-up walkthrough focused on it.

## Checklist before building

Run over the steps JSON, fix, then build:

1. Step count is 5 to 12.
2. Every step has `id`, `title`, `text`, `narration` and a `visual`.
3. Text is at most 40 words, narration at most 25, title at most 8.
4. Narration differs from the text and summarizes it.
5. Every id in `add`, `highlight` and `remove` is declared in the top-level `diagram`; edge ids match `"<from>-><to>"` unless set explicitly.
6. Diagram has at most 12 nodes and node labels are one to three words.
7. Hunks and code are under 20 lines with `highlight` on the key lines.
8. Interactions sit where the mode says: `choice` on design decisions, `review` on commit and history steps, `note` on repo components.
9. No banned words, no em-dashes, no throat-clearing in any title, text, narration, caption or prompt.
10. Plain terms: no coined shorthand, niche terms explained or replaced, titles are single statements (see "Plain terms").
