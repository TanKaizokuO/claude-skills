---
name: handoff
description: Write a self-contained handoff file to /tmp so a fresh session can resume the work. Use when the user runs /handoff, or before /clear at a task boundary or when context is large.
disable-model-invocation: true
---

Write `/tmp/handoff-<short-slug>.md` (slug: 2-4 lowercase words describing the task). The file must let a fresh session with zero context resume from it alone: use absolute paths, exact commands, concrete numbers, and no references to "above" or "earlier".

Structure (use these headings exactly):

# Handoff: <title>

## Task
What the user asked, the goal, definition of done, constraints, and current status (done / in progress / not started). Include user preferences that shape the work.

## Data sources
Files, databases, URLs, repos, scratchpad paths, and scripts used, with absolute paths and how to re-run them.

## Key results
Findings, decisions made, changes made (file paths), and numbers. Facts only.

## Unresolved
Open questions, blockers, unverified claims, and the next concrete step.

## Suggested skills
Skills or tools the next agent should use, each with one line on why.

## Notes for the next agent
Gotchas, dead ends already ruled out, what must not be modified, and anything the user said not to do.

Rules:
- NEVER copy secrets, passwords, API keys, tokens, or credentials into the file. If one matters, say it exists and where (path/field name only) and that it should be rotated if exposed.
- Verify the file exists after writing (ls it).
- Finish by telling the user exactly: "Run /clear, then paste this path: /tmp/handoff-<slug>.md" (with the real path).
