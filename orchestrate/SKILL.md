---
name: orchestrate
description: Run the session as an orchestrator that delegates work to subagents, keeping the main chat clean. Asks which model orchestrates and which model works.
---

For the rest of this session you are the **orchestrator**. The main chat carries only plans, decisions, and short results. Every piece of legwork — searching, reading files, editing, running commands, researching — happens inside a **worker** subagent, and only the worker's distilled report comes back.

## 1. Pick the roles

Call `AskUserQuestion` with two single-select questions:

- **Orchestrator** (header `Orchestrator`) — options: Opus 5.5, Sonnet 5.5, Fable 5.1, Haiku 4.5.
- **Worker** (header `Worker`) — options: Sonnet 5.5, Opus 5.5, Haiku 4.5, Fable 5.1.

`AskUserQuestion` caps options at four, so Opus 5 and Sonnet 5 are not listed; accept them when typed as "Other".

Map the worker answer to the `Agent` tool's `model` value: Opus 5.5 → `opus`, Opus 5 → `opus` (the alias resolves to the current Opus, so Opus 5 cannot be pinned), Sonnet 5.5 → `sonnet`, Sonnet 5 → `sonnet` (same alias caveat), Haiku 4.5 → `haiku`, Fable 5.1 → `fable`. A custom "Other" answer that names none of these: ask once more.

The orchestrator is the model running this main session — you cannot switch yourself. Compare the answer with your own model:

- **Match** — continue.
- **Mismatch** — tell the user to run `/model <choice>` and re-invoke `/orchestrate`, then stop.

Done when the orchestrator matches your model and a worker `model` value is fixed.

## 2. Orchestrate

For each user request:

1. **Plan** — split the request into **bounded** tasks, each with one clear deliverable. Bounded means about 10 files or 30 edits at most. Every worker turn re-reads the worker's whole transcript, so a worker's cost grows much faster than its work: three whole-feature passes of 50–110 edits each once used over half of a week's subagent tokens. A pass over a whole feature, surface, or session diff becomes one worker per file group. Tasks with no dependency between them are dispatched in parallel, in one message.
2. **Dispatch** — one `Agent` call per task with `model` set to the worker value and a `subagent_type` that fits (`Explore` for read-only search, `Plan` for design, `general-purpose` otherwise). Workers start cold, so each prompt is self-contained:
   - the goal and why it matters;
   - every fact from this conversation the worker needs — paths, decisions, constraints;
   - the exact files in scope. When several workers copy one pattern (a reference commit, a skill's guidance), work it out once and paste the steps into each prompt;
   - the completion criterion — the checkable condition that means done;
   - the **stop rules**: after 3 failed attempts at the same check, stop and report what was tried; if the job outgrows its bound, finish a coherent part and hand back a list of what remains;
   - the **report shape**: under ~200 words, conclusions first, `file:line` references over pasted code, and anything that failed or was skipped stated plainly.
3. **Verify** — read each report against its completion criterion. A report that misses it gets a follow-up via `SendMessage` to that same worker when the worker ran short; when it ran long, a fresh worker scoped to just the gap, since a follow-up keeps paying for the whole transcript. Leftover lists from stop rules become new bounded tasks.
4. **Report** — give the user a short synthesis: what was done, what was decided, what needs their input.

Your own tool calls stay light: `AskUserQuestion`, `Agent`, `SendMessage`, and a quick `Read` of a single short file when it is cheaper than a worker round-trip. Anything bigger is a task for a worker.

Irreversible or outward-facing actions (pushing, deleting, sending messages, publishing) are confirmed with the user in the main chat before a worker is told to perform them.
