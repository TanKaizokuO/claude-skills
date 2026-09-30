---
name: whats-next
description: Tell in brief what is done, what to do next, and what is blocked in this project. Reads only; changes no file.
disable-model-invocation: true
---

This skill is a **read-only** status report. Every tool call reads (`git`, `gh`, `find`, `date`, Read), and the only output is the report in chat. When the user also wants the docs changed, finish the report and point them to `/sync-docs`.

## 1. Discover and gather evidence

Read `/home/tankaizokuo/.claude/skills/_shared/project-state.md` and run its §1 and §2. For tests, quote the count the status doc gives.

When the user names an area ("the annotator pipeline"), keep only the items in that area.

Done when you hold the role of every state doc, the open items with their state, and the drift list.

## 2. Rank the next items

Take every open item from the goals, roadmap / plan, and status docs, plus open issues whose work is not done.

1. Order by what blocks what: a blocker comes before the items it blocks. Break ties with `[needs you]` items first, then the nearest due date.
2. Tag each item with where it runs:
   - `[local]`: this laptop can do it now.
   - `[GPU box]`: it needs a GPU. When the rules name the boxes, name the box (BioMedical_QA: `vllm-box` for generation, `a4000-linux` for CPU, verifier, and storage work).
   - `[needs you]`: it needs a decision, an account, a person (such as annotators), or an action only the user can do.
3. Compare each due date with today: mark `late N days` or `ahead N days`.

Done when every open item is ranked or dropped with a reason (ignore list, other area), and every ranked item has exactly one tag.

## 3. Report

Write at most ~10 lines in plain ASD-STE100 words with the glossary's terms:

```
Today 2026-09-15. Docs last updated: TODO.md 09-08, ROADMAP.md 08-23.
Done since then: <item> (<hash>); <item> (<file>)
Next:
1. [needs you] <item>. It blocks 2 and 3.
2. [GPU box: vllm-box] <item>. Due Sep 20, 5 days left.
3. [local] <item>
Blocked: <item>, waits for <blocker>
Docs out of date: <N> drifts. Run /sync-docs.
```

Leave out empty lines ("Blocked: none").

Close with one offer: "Do you want item 1 as a prompt for another agent?" When the user already asked for the next step "in form of a prompt", write that prompt instead of the offer. The prompt is self-contained: goal, repo path, files, the box to use, the repo's rules for that box (such as one-line commands and `uv run python`), and a completion criterion.

Done when the report has at most ~10 lines plus the offer or prompt, every Next line has a tag, and `git status --short` prints the same baseline as in step 1.
