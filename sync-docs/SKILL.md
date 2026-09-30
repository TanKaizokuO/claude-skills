---
name: sync-docs
description: Update the project's state docs (status, goals, roadmap, plan) to match current progress, with proof for each change. Leaves the commit to /ship.
disable-model-invocation: true
---

This skill brings each **state doc** in line with the evidence. Every edit fixes one **drift** and carries its **proof**. It edits state docs only and ends by handing the commit to `/ship`.

## 1. Discover and gather evidence

Read `/home/tankaizokuo/.claude/skills/_shared/project-state.md` and run its §1 and §2. When a status doc quotes a test count, run the test command that doc names and use the new count.

Scope: the docs the user names, mapped through renames ("HANDOFF.md" means `STATUS.md` in BioMedical_QA and `LOG.md` in learning/backend). With no doc named, every state doc that has a drift. A named file outside the repo that does not exist: ask before you create it.

Done when every in-scope doc has its drift list, and each drift has proof or is marked unproven.

## 2. Plan the edits

Before you plan a doc's edits, read two or three of its existing done items and copy their exact shape. Then map each drift to one edit:

- **Done item**: strike it and add the proof in the doc's shape. TODO.md: `~~**Item:** text~~ *(Completed Sep 12, 2026 — <hash>, <file>)*`. Checkbox list: `- [x] ~~item~~`. lesson_plan.md: strike the title cell and move the row to `## Done`.
- **Ahead or behind**: move every later internal due date by the gap between the latest finished milestone's due date and the day it finished. Keep the old date beside the new one, as the doc already does: `~~September 6, 2026~~ — **PASSED August 23, 2026**`. Dates that an outside party or an ADR fixes (a venue deadline) stay; name them in the changelog.
- **Status doc** (`HANDOFF.md`, `STATUS.md`, `STATE.md`): rewrite stale lines to the current state. Delete lines about retired work, rules that a later rule replaced, and problems that are solved. Keep the section order. Set its date line to today.
- **Log doc**: append one dated entry.
- **Date lines** ("Current Date", "Last updated"): today.
- **New next item** (a new issue, a follow-up a commit or result file names): add it open, in the nearest matching section, with its source.
- **Stale pointer**: fix it in a state doc. In a rules or glossary file, report it.
- **Open issue for finished work**: report it with the proof; the user closes issues.
- **Unproven**: leave the item open and report it.

Done when every drift from step 1 maps to exactly one edit or one report line.

## 3. Edit

Apply the plan with Edit. Keep each doc's markup: tables stay tables, strike style stays `~~ ~~`, dates keep the format of their neighbours. Write new text in ASD-STE100 with the glossary's terms. Edit state docs only; code, ADRs, rules, the glossary, and ignored paths keep their content.

Done when every planned edit is applied and `git status --short`, compared with the baseline, shows new changes in state docs only.

## 4. Changelog and hand-off

Print one short block per file, then the report lines:

```
TODO.md: struck 2 (a1b2c3d; docs/harvest/x.json). Added 1 (issue #11). G3 due Sep 20 -> Sep 13, 7 days ahead.
STATUS.md: removed 3 stale lines (copy-paste-only rule, v5-v9 runs). Date -> 2026-09-15.
Report: issues #2, #3 open but G1, G2 passed. CLAUDE.md names Upcoming_goals.md, now TODO.md.
Unproven: <item>
Fixed dates kept: Nov 2 submission (ADR-0001)
```

When the user asked for a handoff prompt, print it next: a self-contained prompt that tells a new agent to read the status doc first, then names the top next item and its completion criterion.

End with: `Run /ship to commit.`

Done when every edited file has a block, every report line from step 2 is printed, and the last line points to `/ship`.
