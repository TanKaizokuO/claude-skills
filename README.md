# claude-skills

Personal skills for [Claude Code](https://claude.com/claude-code) and omp (oh-my-pie). Each skill is a directory with a `SKILL.md`: YAML frontmatter (`name`, `description`) followed by the instructions the agent loads when the skill is invoked.

Skills marked **manual** set `disable-model-invocation: true`. They only run when you type the slash command; the model never triggers them on its own.

## Skills

### Project workflow

| Skill | Mode | What it does |
|---|---|---|
| `whats-next` | manual | Brief report of what is done, what is next, and what is blocked. Read-only. |
| `plan-doc` | auto | Creates a `PLAN.md` / `ROADMAP.md` / goals file in house style. Plan only, no implementation. |
| `sync-docs` | manual | Updates the project's state docs to match current progress, with proof for each change. Leaves the commit to `push-to-gh`. |
| `handoff` | manual | Writes a self-contained handoff file to `/tmp` so a fresh session can resume. Run before `/clear`. |
| `orchestrate` | auto | Runs the session as an orchestrator that delegates to subagents, including Gemini agents through Antigravity CLI (`agy`). |

### Planning and design

| Skill | Mode | What it does |
|---|---|---|
| `grill-engine` | auto | Stress-tests a plan or decision through `AskUserQuestion`. |
| `converge-with-me` | manual | A relentless interview to sharpen a plan or design. |
| `converge-with-docs` | manual | Same interview, and writes ADRs and a glossary as it goes. |
| `design-help` | auto | Iterative UI/UX workflow: design brief, low-fidelity prototypes, refinement rounds. |

### Git and review

| Skill | Mode | What it does |
|---|---|---|
| `push-to-gh` | auto | Fixes `.gitignore`, secret-scans, commits, and pushes. Creates the GitHub repo if there is none. |
| `pull-from-gh` | auto | Pulls with rebase + autostash, in the current repo or in each sub-repo you approve. |
| `lock-in-code-review` | manual | Very strict maintainability review (abstractions, giant files, condition sprawl) fanned out across parallel reviewers. Rubric in `RUBRIC.md`. |

### Machine and personal

| Skill | Mode | What it does |
|---|---|---|
| `declutter` | manual | Read-only storage report or folder-bucketing plan first, then cleans or moves only what you pick, with an undo log. |
| `sway` | auto | Edits this machine's Sway/Wayland config (keybindings, monitors, lockscreen, waybar, fuzzel, mako). |
| `lab` | manual | Takes a college lab from handout to zipped submission, using Colab via colab-mcp for Python. |
| `llm-cost-audit` | auto | Weekly read-only audit of LLM spend (omp and Claude Code) in INR. Prices in `prices.json`, logic in `scripts/audit.py`. |
| `token-ledger-update` | auto | Refreshes the "Token Ledger" Claude artifact from omp and Claude Code usage. |

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
