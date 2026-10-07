---
name: plan-doc
description: Create a plan, roadmap, or goals markdown file (PLAN.md, ROADMAP.md, Upcoming_goals.md, lesson_plan.md, feature-list.md, CONNECTION_PLAN.md) in the user's house style. Plan only, no implementation. Later updates go to /sync-docs.
---

Create one plan doc. A plan doc is a file another agent can run without asking questions. Write the plan and stop: do not build, edit code, or commit.

Text after `/plan-doc`: `$ARGUMENTS` — the topic, and often the file name.

## 1. Pick the shape

| Request | Default file | Shape |
|---|---|---|
| "plan to fix/build X" | `PLAN.md`, or `<TOPIC>_PLAN.md` when a plan exists | Steps with order and reasons |
| "roadmap", "milestones" | `ROADMAP.md` (`ROADMAP_2.md` when one exists) | Dated milestones |
| "upcoming goals", "next targets" | `Upcoming_goals.md` | Prioritized goals with context |
| "course / lesson plan" | `lesson_plan.md` | One table row per lesson |
| "feature list", "stages" | `feature-list.md` | Features grouped by delivery stage |
| "changes to make" | `changes-to-be-made.md` | Flat task list, one owner per task |

Use the file name the user gave. If the file exists, ask once whether to replace it or write a new numbered file. Never overwrite without that answer.

## 2. Gather facts first

Read `CONTEXT.md`, `AGENTS.md`/`CLAUDE.md`, and any status doc (`HANDOFF.md`, `STATUS.md`, `TODO.md`) the repo has. Use the terms from `CONTEXT.md` exactly (ubiquitous language). Check `git log --oneline -10` and open issues (`gh issue list`) when the repo has a remote. Delegate bulk reading to the `scout` subagent.

If the goal, the done state, or a constraint is missing, ask with `AskUserQuestion` before you write. Do not guess.

## 3. Write the doc

Write in ASD-STE100 Simplified Technical English: short sentences, one idea each, active voice, no idioms. Open with 2-4 lines of context: what this is for and the current state.

Every item has:
- **What**: one imperative sentence.
- **Why**: the reason it comes at this place in the order.
- **Done when**: a check an agent can run or see (a command, a test, a file that exists).
- **Depends on**: item numbers, or `none`. Mark items with `none` as parallel-safe.

Then add:
- **Out of scope**: what the plan will not do.
- **Open questions**: decisions that need the user, each with a recommended answer.

Rules:
- Order by impact, then by dependency. Put blockers first.
- Dates: absolute (`October 7, 2026`), never "next week".
- Use checkbox or table style that matches the repo's other plan docs. Copy their shape when one exists.
- Add "Future agents: ignore `<path>`" lines only for paths the user named.
- Money in INR (₹) unless the user says otherwise.

## 4. Finish

Done when the file exists, every item has the four fields, and the shape table row matches the request.

Reply with the path, the item count, and the open questions. End with: run the plan with `/orchestrate execute <file>`, and update it later with `/sync-docs`.
