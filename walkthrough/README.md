# walkthrough

A Claude Code skill that explains code work as a step-by-step visual page: a diagram that builds up per step, short text, optional narration, and clickable answers that go back to the agent. You step through at your own pace with the arrow keys.

Modes: `design` (derive an architecture before code exists), `commit` (one commit), `history N` (last N commits), `repo` (architecture of an existing repo).

## Requirements

- Claude Code
- Python 3.8+ (standard library only)
- A modern browser. Narration uses the Web Speech API and needs a system voice.
- Optional: the `claude` CLI on `PATH` for answering "Ask the agent" questions from the page. Without it, start `serve.py` with `--no-agent` and answer in chat.

## Narration privacy

Narration uses the browser's built-in speech engine (`window.speechSynthesis`). The page sends nothing to a server of its own, but whether speech is generated on your machine depends on the voice the browser picks:

- Local: Firefox, Safari and macOS voices, Windows desktop voices.
- Online: Chrome's "Google ..." voices send the narration text to Google; Edge's "Microsoft ... Online (Natural)" voices send it to Microsoft.

Only the short narration lines leave the machine, nothing else from the page. The agent asks at the start whether to turn narration on.

## Install

As a plugin (Claude Code updates it for you):

```
/plugin install walkthrough --marketplace paulbockelmann/workflows
```

On older Claude Code versions, add the marketplace first, then install:

```
/plugin marketplace add paulbockelmann/workflows
/plugin install walkthrough@workflows
```

As a plain skill: copy the `walkthrough` folder of this repo to `~/.claude/skills/walkthrough/` (all projects) or `.claude/skills/walkthrough/` (one project).

```
git clone https://github.com/paulbockelmann/workflows
cp -r workflows/walkthrough ~/.claude/skills/
```

## Use

Say "walk me through the last 3 commits", "explain this commit visually", "visualize the repo architecture", or type the command: `/walkthrough:walkthrough` when installed as a plugin, `/walkthrough` when installed as a plain skill.

## Third-party code

`vendor/` contains highlight.js 11.9.0, BSD 3-Clause, see `vendor/LICENSE-highlight.js`.
