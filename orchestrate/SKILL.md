---
name: orchestrate
description: Run the session as an orchestrator that delegates work to subagents, keeping the main chat clean. Asks which model orchestrates and which model works, and offloads suitable tasks to Gemini agents through Antigravity CLI (agy).
---

For the rest of this session you are the **orchestrator**. The main chat carries only plans, decisions, and short results. Every piece of legwork — searching, reading files, editing, running commands, researching — happens inside a **worker** subagent, and only the worker's distilled report comes back.

## 1. Pick the roles

Call `AskUserQuestion` with three single-select questions:

- **Orchestrator** (header `Orchestrator`) — options: Opus 5.5, Sonnet 5.5, Fable 5.1, Haiku 4.5.
- **Worker** (header `Worker`) — options: Sonnet 5.5, Opus 5.5, Haiku 4.5, Fable 5.1.
- **Gemini offload** (header `Gemini`) — options: "Read-only tasks (Recommended)", "Read-only + mechanical edits", "Off". See section 3.

`AskUserQuestion` caps options at four, so Opus 5 and Sonnet 5 are not listed; accept them when typed as "Other".

Map the worker answer to the `Agent` tool's `model` value: Opus 5.5 → `opus`, Opus 5 → `opus` (the alias resolves to the current Opus, so Opus 5 cannot be pinned), Sonnet 5.5 → `sonnet`, Sonnet 5 → `sonnet` (same alias caveat), Haiku 4.5 → `haiku`, Fable 5.1 → `fable`. A custom "Other" answer that names none of these: ask once more.

The orchestrator is the model running this main session — you cannot switch yourself. Compare the answer with your own model:

- **Match** — continue.
- **Mismatch** — tell the user to run `/model <choice>` and re-invoke `/orchestrate`, then stop.

If Gemini offload is on, run `agy models` once. If `agy` is missing or the call fails on auth, tell the user to run `! agy auth login` (interactive; never log in for them) and treat Gemini as Off until they confirm.

Done when the orchestrator matches your model, a worker `model` value is fixed, and the Gemini mode is known.

## 2. Orchestrate

For each user request:

1. **Plan** — split the request into **bounded** tasks, each with one clear deliverable. Bounded means about 10 files or 30 edits at most. Every worker turn re-reads the worker's whole transcript, so a worker's cost grows much faster than its work: three whole-feature passes of 50–110 edits each once used over half of a week's subagent tokens. A pass over a whole feature, surface, or session diff becomes one worker per file group. Tasks with no dependency between them are dispatched in parallel, in one message.
2. **Route** — decide per task whether it goes to a Claude worker or a Gemini agent (section 3). Default to Claude when unsure.
3. **Dispatch** — Gemini tasks go out as in section 3. Claude tasks: one `Agent` call per task with `model` set to the worker value and a `subagent_type` that fits (`Explore` for read-only search, `Plan` for design, `general-purpose` otherwise). Workers start cold, so each prompt is self-contained:
   - the goal and why it matters;
   - every fact from this conversation the worker needs — paths, decisions, constraints;
   - the exact files in scope. When several workers copy one pattern (a reference commit, a skill's guidance), work it out once and paste the steps into each prompt;
   - the completion criterion — the checkable condition that means done;
   - the **stop rules**: after 3 failed attempts at the same check, stop and report what was tried; if the job outgrows its bound, finish a coherent part and hand back a list of what remains;
   - the **report shape**: under ~200 words, conclusions first, `file:line` references over pasted code, and anything that failed or was skipped stated plainly.
4. **Verify** — read each report against its completion criterion. A report that misses it gets a follow-up via `SendMessage` to that same worker when the worker ran short; when it ran long, a fresh worker scoped to just the gap, since a follow-up keeps paying for the whole transcript. Leftover lists from stop rules become new bounded tasks.
5. **Report** — give the user a short synthesis: what was done, what was decided, what needs their input.

Your own tool calls stay light: `AskUserQuestion`, `Agent`, `SendMessage`, the `agy` dispatch and `jq` read-back from section 3, `git status`/`git diff --stat` to check a Gemini agent's footprint, and a quick `Read` of a single short file when it is cheaper than a worker round-trip. Anything bigger is a task for a worker.

Irreversible or outward-facing actions (pushing, deleting, sending messages, publishing) are confirmed with the user in the main chat before a worker is told to perform them.

## 3. Gemini agents (agy)

Antigravity CLI (`agy`) runs Google's agent on the user's Google AI Pro plan, which is a separate budget from Claude subagent tokens. Gemini 3.8 Flash (high) scores 41 on the Artificial Analysis Intelligence Index, against Sonnet 5.5 at 47, Opus 5.5 at 51–54 and Sonnet 5 at 32. That makes it a capable worker for bounded tasks, but not a replacement for Opus on judgement-heavy work.

### Routing

Send to Gemini (when the mode allows it):
- **Read-only, any mode** — first-pass or second-opinion review of one slice, scope waves ("list what changed in this diff, grouped by area"), finding usages, recon or survey of a repo, extracting tables or strings, checking a Claude worker's report against the code, drafting doc or state-file text that you then apply.
- **Mechanical edits, only in "Read-only + mechanical edits" mode** — a rename across a few files, string-table or i18n conversion, removing a known symbol, a formatting pass. The edit must be fully specified, so there is no design choice left to Gemini.

Keep on Claude:
- anything that needs shell commands (builds, tests, git, deploys), since `agy` cannot run most commands headlessly;
- feature builds, refactors and decomposition;
- final or merge-gating review (the Opus review waves);
- architecture work, skill writing, and anything irreversible or outward-facing.

When the same slice gets both a Gemini review and an Opus review, a disagreement between them is a signal to look closer, not a vote.

### Models

Use IDs exactly as `agy models` prints them:
- `gemini-3.8-flash-high` is the default.
- `gemini-3.8-flash-low` is for trivial extraction.
- `gemini-3.1-pro-high` is for images and screenshots.

`agy` also offers `claude-sonnet-4-6` and `claude-opus-4-6-thinking`, but with very low usage limits, and they are older than the Claude workers available here. Don't route to them unless the user asks. If they do, make one call at a time and expect a 429.

### Dispatch

One Bash call per task, with `run_in_background: true` so independent tasks run in parallel and you are notified when each exits. Run it from the repo the task concerns, and record `git status --porcelain` first:

```
agy -p "<self-contained prompt>" --model gemini-3.8-flash-high --mode plan \
  --output-format json --print-timeout 300s > <scratchpad>/gem-<task>.json 2>&1
```

- Use `--mode plan` for read-only tasks and `--mode accept-edits` for mechanical edits. Never use `--dangerously-skip-permissions`.
- Use `--add-dir <path>` for each extra directory it needs.
- Write the prompt like a Claude worker prompt: goal, facts, exact files, completion criterion, report shape. Also add "do not run shell commands", plus "do not modify any files" for read-only tasks. Gemini starts cold too.
- Ask for the report as JSON or as short text with `file:line` references, under about 200 words.

### Read-back

Don't read the whole output file. Run `jq -r '.status, .response' <file>`.

The exit code is 0 even on failure. Treat the task as **failed** if any of these hold:
- the file isn't JSON;
- `.status` isn't `SUCCESS`;
- the response says a tool was "auto-denied";
- the response asks for approval ("click Proceed") instead of answering.

A failed or rate-limited (429) task goes to a Claude worker. Don't retry `agy` in a loop. After two Gemini failures in a session, stop routing to Gemini and tell the user.

### Verify

Gemini output is a lead, not a fact:
- Spot-check its `file:line` claims before acting on them, or hand them to a Claude worker to confirm.
- `--mode plan` is not a sandbox, because it has run read-only commands like `ls` before. After every task, compare `git status --porcelain` with the snapshot. A read-only task that changed files gets those changes reverted only after showing the user. A mechanical edit gets its diff checked with `git diff --stat`, then the build and tests run by a Claude worker, before it counts as done.
