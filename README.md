# claude-skills

Personal skills for [Claude Code](https://claude.com/claude-code) and omp (oh-my-pie). Each skill is a directory with a `SKILL.md`: YAML frontmatter (`name`, `description`) followed by the instructions the agent loads when the skill is invoked.

Skills marked **manual** set `disable-model-invocation: true`. They only run when you type the slash command; the model never triggers them on its own.

## Skills

### Project workflow

| Skill | Mode | What it does |
|---|---|---|
| [`whats-next`](whats-next/SKILL.md) | manual | Brief report of what is done, what is next, and what is blocked. Read-only. |
| [`plan-doc`](plan-doc/SKILL.md) | auto | Creates a `PLAN.md` / `ROADMAP.md` / goals file in house style. Plan only, no implementation. |
| [`sync-docs`](sync-docs/SKILL.md) | manual | Updates the project's state docs to match current progress, with proof for each change. Leaves the commit to `push-to-gh`. |
| [`handoff`](handoff/SKILL.md) | manual | Writes a self-contained handoff file to `/tmp` so a fresh session can resume. Run before `/clear`. |
| [`orchestrate`](orchestrate/SKILL.md) | auto | Runs the session as an orchestrator that delegates to subagents, including Gemini agents through Antigravity CLI (`agy`). |
| [`which-skill`](which-skill/SKILL.md) | manual | Interactive router that recommends the right skill or flow for your current situation. |
| [`setup-repo-skills`](setup-repo-skills/SKILL.md) | manual | Scaffolds repository configuration (issue tracker, triage labels, domain docs layout) for engineering skills. |
| [`create-spec`](create-spec/SKILL.md) | manual | Synthesizes the current conversation into a local specification document without interviewing. |
| [`spec-to-tickets`](spec-to-tickets/SKILL.md) | manual | Breaks a spec or plan into tracer-bullet tickets with explicit blocking dependencies. |
| [`build-and-review`](build-and-review/SKILL.md) | auto | Builds work from a spec, ticket set, or description test-first, reviews the diff, and commits on the working branch. |
| [`triage-issues`](triage-issues/SKILL.md) | manual | Triages issues and PRs through a state machine, verifying claims and writing agent-ready briefs. |
| [`auto-mato`](auto-mato/SKILL.md) | auto | Generates an interactive bash wizard for human-guided manual procedures, setups, and state transitions. |

### Planning and design

| Skill | Mode | What it does |
|---|---|---|
| [`grill-engine`](grill-engine/SKILL.md) | auto | Stress-tests a plan or decision through `AskUserQuestion`. |
| [`converge-with-me`](converge-with-me/SKILL.md) | manual | A relentless interview to sharpen a plan or design. |
| [`converge-with-docs`](converge-with-docs/SKILL.md) | manual | Same interview, and writes ADRs and a glossary as it goes. |
| [`design-help`](design-help/SKILL.md) | auto | Iterative UI/UX workflow: design brief, low-fidelity prototypes, refinement rounds. |
| [`ask-me`](ask-me/SKILL.md) | manual | Surfaces open decisions up front tiered with recommendations, then executes without further questions. |
| [`create-workflow`](create-workflow/SKILL.md) | manual | Grills the user to design, specify, and store recurring loop workflows. |
| [`lets-delegate-this-decision`](lets-delegate-this-decision/SKILL.md) | manual | Turns an open decision into a targeted questionnaire for another stakeholder to answer. |

### Git and review

| Skill | Mode | What it does |
|---|---|---|
| [`push-to-gh`](push-to-gh/SKILL.md) | auto | Fixes `.gitignore`, secret-scans, commits, and pushes. Creates the GitHub repo if there is none. |
| [`pull-from-gh`](pull-from-gh/SKILL.md) | auto | Pulls with rebase + autostash, in the current repo or in each sub-repo you approve. |
| [`lock-in-code-review`](lock-in-code-review/SKILL.md) | manual | Very strict maintainability review (abstractions, giant files, condition sprawl) fanned out across parallel reviewers. Rubric in `RUBRIC.md`. |
| [`improve-architecture`](improve-architecture/SKILL.md) | manual | Scans codebase for deepening refactor opportunities and presents them as an interactive visual HTML report. |

### Machine and personal

| Skill | Mode | What it does |
|---|---|---|
| [`declutter`](declutter/SKILL.md) | manual | Read-only storage report or folder-bucketing plan first, then cleans or moves only what you pick, with an undo log. |
| [`sway`](sway/SKILL.md) | auto | Edits this machine's Sway/Wayland config (keybindings, monitors, lockscreen, waybar, fuzzel, mako). |
| [`lab`](lab/SKILL.md) | manual | Takes a college lab from handout to zipped submission, using Colab via colab-mcp for Python. |
| [`llm-cost-audit`](llm-cost-audit/SKILL.md) | auto | Weekly read-only audit of LLM spend (omp and Claude Code) in INR. Prices in `prices.json`, logic in `scripts/audit.py`. |
| [`token-ledger-update`](token-ledger-update/SKILL.md) | auto | Refreshes the "Token Ledger" Claude artifact from omp and Claude Code usage. |
| [`teach-me`](teach-me/SKILL.md) | manual | Creates a multi-session learning workspace to teach a new skill or concept with mission and reference materials. |
| [`my-writing-great-skills`](my-writing-great-skills/SKILL.md) | manual | Reference vocabulary and principles for authoring reliable, predictable skills. |

`_shared/project-state.md` is not a skill. It is the discovery and evidence procedure shared by `whats-next` and `sync-docs`.

## Install

Clone into the Claude Code skills directory:

```sh
git clone git@github.com:TanKaizokuO/claude-skills.git ~/.claude/skills
```

Claude Code picks up every directory that contains a `SKILL.md`. Invoke a skill with `/<name>`.

### omp

omp reads skills from `~/.omp/agent/skills`. Symlink the ones you want:

```sh
ln -s ~/.claude/skills/<name> ~/.omp/agent/skills/<name>
```

If omp already has its own copy of a skill (some have diverged), check before replacing it.

## Credits

`grill-engine`, `converge-with-me`, `converge-with-docs` and `handoff` are inspired by skills in Matt Pocock's [mattpocock/skills](https://github.com/mattpocock/skills). They are adapted to my own workflow, so they differ from the originals.

## What is not tracked

`.gitignore` leaves out everything that is not authored here:

- Third-party skills: `heroui-react`, `impeccable`, `teach`, and the installed AWS skills.
- `synced/`, which holds skills mirrored from claude.ai.
- `remote-run/`, which contains local SSH credentials.
- Local and agent files: `.venv/`, `.env*`, `.omp/`, `.claude/`, caches.

## Writing a new skill

1. Create `<name>/SKILL.md` with `name` and a `description` that says what it does and when to use it.
2. Add `disable-model-invocation: true` if it should only run when you ask.
3. Put helper scripts and data next to it (see `llm-cost-audit/`). Shared reference material goes in `_shared/`.
4. Add a row to the table above.
