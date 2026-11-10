---
name: orchestrate
description: Run the session as an orchestrator that delegates work to subagents, keeping the main chat clean. The session model is the orchestrator; prefer Claude orchestrators → GPT workers per the suggest-model routing table and live quota, with Claude workers as quota/harness fallbacks. Gemini is unavailable.
---

For the rest of this session you are the **orchestrator**, whichever model the session is running. The main chat carries only plans, decisions, and short results. Every piece of legwork — searching, reading files, editing, running commands, researching — happens inside a **worker** subagent, and only the worker's distilled report comes back.

## 1. Pick the workers

The orchestrator is the session model. Do not ask which model orchestrates.

Gemini / Antigravity is unavailable. Never dispatch it, run its CLI, request authentication for it, or restore it after a quota reset.

If the user already named the worker model and effort, use that choice without a recommendation or quota check. Ask only when the effort is ambiguous. An unavailable model is not dispatchable: report that and ask for an available worker.

Otherwise, read `suggest-model/SKILL.md` and apply its task routing table, intelligence reference, and live Main or Backup quota rules. Prefer Claude orchestrators → GPT workers. Do not ask the user to choose workers when the policy answers it. The native Claude Code `Agent` tool cannot dispatch GPT workers; unless an available GPT integration is explicitly configured, use Backup for every row. Do not invent a bridge.

Map Claude workers to `Agent`'s `model` and `effort`: Haiku 5.5 High → `haiku` / `high`; Haiku 5.5 Max → `haiku` / `max`; Sonnet 5.5 High → `sonnet` / `high`; Opus 5.5 Medium → `opus` / `medium`. Preserve any explicitly chosen supported effort.

Done when each phase has a pinned, dispatchable worker. If quota is blocked or unknown with no confirmed choice, report it and ask how to proceed.

## 2. Orchestrate

For each user request:

1. **Plan** — split the request into **bounded** tasks, each with one clear deliverable. Bounded means about 10 files or 30 edits at most. For Haiku 5.5 workers the hard limit is 150k context; size tasks to finish well under it, and treat a worker that compacts as a scope failure (split the rest into new tasks). Every worker turn re-reads the worker's whole transcript, so a worker's cost grows much faster than its work: three whole-feature passes of 50–110 edits each once used over half of a week's subagent tokens. A pass over a whole feature, surface, or session diff becomes one worker per file group. Tasks with no dependency between them are dispatched in parallel, in one message.
2. **Route** — each task goes to the pinned worker for its task row. Read-only work uses Terra Medium when an available GPT integration supports it, otherwise the Haiku High Backup; tell the worker explicitly not to modify files.
3. **Dispatch** — native Claude workers use one `Agent` call per task with the pinned `model` and `effort` and a `subagent_type` that fits (`Explore` for read-only search, `Plan` for design, `general-purpose` otherwise). GPT workers require an explicitly configured, available integration; never pass a GPT ID to the native `Agent` tool. Workers start cold, so each prompt is self-contained:
   - the goal and why it matters;
   - every fact from this conversation the worker needs — paths, decisions, constraints;
   - the exact files in scope. When several workers copy one pattern (a reference commit, a skill's guidance), work it out once and paste the steps into each prompt;
   - the completion criterion — the checkable condition that means done;
   - the **stop rules**: after 3 failed attempts at the same check, stop and report what was tried; if the job outgrows its bound, finish a coherent part and hand back a list of what remains;
   - the **report shape**: under ~200 words, conclusions first, `file:line` references over pasted code, and anything that failed or was skipped stated plainly.
4. **Verify** — read each report against its completion criterion. A report that misses it gets a follow-up via `SendMessage` to that same worker when the worker ran short; when it ran long, a fresh worker scoped to just the gap, since a follow-up keeps paying for the whole transcript. Leftover lists from stop rules become new bounded tasks.
5. **Report** — give the user a short synthesis: what was done, what was decided, what needs their input.

Your own tool calls stay light: `AskUserQuestion`, `Agent`, `SendMessage`, and a quick `Read` of a single short file when it is cheaper than a worker round-trip. Anything bigger is a task for a worker.

Irreversible or outward-facing actions (pushing, deleting, sending messages, publishing) are confirmed with the user in the main chat before a worker is told to perform them.

## 3. Worker failures

On a quota or dispatch failure, do not retry in a loop. For an automatically selected worker, refresh the affected provider once and apply `suggest-model`'s fallback rules. If no choice is confirmed, report the blocking pool and reset and ask how to proceed. If the user explicitly selected the worker, ask before switching it. Never fall back to unavailable Gemini.
