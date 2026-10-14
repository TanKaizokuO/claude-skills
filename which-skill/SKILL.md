---
name: which-skill
description: Ask which of your skills or flows fits your situation. A router over your own skill set.
disable-model-invocation: true
---

# Which skill?

You don't remember every skill, so ask. Find the row that matches the situation, then run that skill.

## Main flow: idea → ship

1. **Sharpen the idea.** `/converge-with-docs` when you have a codebase (leaves ADRs and a glossary); `/converge-with-me` when you don't. Want every open decision up front, tiered, with a recommendation each? `/ask-me`. Saying "grill me" fires `/grill-engine`.
2. **Detour if a question needs a runnable answer** (state model, business logic, a UI you must see): `/handoff` out, `/prototype` to answer it with throwaway code, `/handoff` back with what you learned.
3. **Multi-session build?**
   - **Yes** → `/create-spec`, then `/spec-to-tickets`, then `/build-and-review` per ticket, clearing context between tickets.
   - **No** → `/build-and-review` right here.

   `/build-and-review` drives `/tdd` slice by slice, runs `/code-review` on the diff, then commits on the working branch. Use `/tdd` alone for one test-first behaviour, `/code-review` alone to review a branch or PR.

Prefer a plan as a file? `/plan-doc`. Keep state docs honest with `/sync-docs`.

## On-ramps

- **Issues from other people piling up** → `/triage-issues`. Not for tickets `/spec-to-tickets` made; those are already agent-ready.
- **Hard bug** → `/diagnosing-bugs`. **Merge or rebase conflict** → `/resolving-merge-conflicts`.

## Codebase health

- `/improve-architecture` surfaces deepening opportunities; take one into `/converge-with-docs`.
- `/codebase-design` (module shape) and `/domain-modeling` (domain language) are vocabulary layers; the skills above pull them in.

## Review

- `/code-review` for standards + spec since a fixed point. `/lock-in-code-review` for the strict, parallel maintainability pass.

## Delegation and context

- `/orchestrate` to run the session as an orchestrator over subagents.
- At ~100k tokens or a task boundary: `/handoff`, then `/clear`. Never `/compact`.
- Hand a decision to someone else → `/lets-delegate-this-decision`. Spec a recurring loop → `/create-workflow`. Walk a manual procedure → `/auto-mato`.

## Status and upkeep

`/whats-next` (read-only status), `/sync-docs`, `/push-to-gh`, `/pull-from-gh`, `/llm-cost-audit`, `/token-ledger-update`, `/declutter`.

## Learning and skill writing

`/teach-me` for a multi-session learning workspace. `/my-writing-great-skills` when writing or editing a skill. `/research` for a cited primary-source brief.

## College

`/lab` for a lab from handout to zip, `/remote-run` for a GPU job on a lab box.

## Precondition

Run `/setup-repo-skills` once per repo before the first engineering flow: it records the issue tracker, triage labels and docs layout the flow skills read.
