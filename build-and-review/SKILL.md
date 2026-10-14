---
name: build-and-review
description: Build a piece of work from a spec, a ticket set or a plain description, test-first, then review it and commit on the working branch. Use when asked to implement a spec or ticket, or when delegated a build task.
---

Implement the work described in the spec, tickets or plain description.

## Before starting

- If the input has no checkable definition of done (acceptance criteria or a clear end state), ask with `AskUserQuestion` before building. Do not guess one.
- Read and search through the `scout` subagent, not in the main context.
- If the current branch is the default branch, create a working branch first.

## Build

- Use `/tdd` where possible, at pre-agreed seams.
- Run typechecking regularly, single test files regularly, and the full test suite once at the end.
- After ~100 tool calls without finishing, stop, summarise progress and ask whether to continue.

## Finish

1. Run `/code-review` on the work.
2. Commit to the working branch.

Never push, open a PR or merge from this skill; those belong to the caller.
