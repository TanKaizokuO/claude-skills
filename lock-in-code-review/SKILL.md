---
name: lock-in-code-review
description: Run an extremely strict, orchestrated maintainability review for abstraction quality, giant files, and spaghetti-condition growth, fanned out across parallel reviewer workers. Use for a lock-in code review, thermo-nuclear code quality review, deep code quality audit, or especially harsh maintainability review.
disable-model-invocation: true
---

# Lock-In Code Review (Orchestrated)

An unusually strict review of implementation quality, abstraction quality, and codebase health, run as an **orchestrated** review: you are the orchestrator, parallel workers do the reading, you verify and synthesize.

Review standards live in [RUBRIC.md](RUBRIC.md) next to this file. Workers start cold, so every worker prompt MUST tell the worker to read the rubric at its **absolute path** (resolve this skill's directory first) before reviewing. Do not paraphrase the rubric into prompts; point at it.

This skill is **read-only**. No worker edits code. If the user later asks to apply findings, that is a separate orchestrated implementation request.

## 0. Become the orchestrator

Read and follow the `orchestrate` skill (`skill://orchestrate`) first: run its role selection, and use its dispatch, verify, and report rules for everything below. This file only adds the review-specific plan.

## 1. Fix the review target

Default target: the current branch's changes against its merge-base with the default branch (`main`/`master`), plus uncommitted work. If the user named a PR, commit range, or path set, use that instead. Ask only when the target is genuinely ambiguous (e.g. detached HEAD with no obvious base).

## 2. Scope wave (one worker)

Dispatch a single read-only **Scope** worker. It returns:

- base ref and exact diff command used;
- every changed file with lines added/removed and **line count before → after**;
- every file that crosses **1000 lines** in this diff (below before, above after), and every file already above 1000 that grew;
- a proposed partition of the diff into **review slices**: cohesive groups by module/feature/layer, each roughly ≤8 files or ≤600 changed lines; generated files, lockfiles, and snapshots listed separately and excluded;
- a 3–5 sentence description of what the change does as a whole.

This wave is the only serial dependency: review slices consume its partition.

## 3. Review wave (parallel, one message)

Dispatch all of these together:

- **Slice reviewers** — one per slice from step 2. Scope: that slice's files and diff hunks, reading surrounding code as needed to judge fit. Applies the full rubric.
- **Code-judo architect** — one worker over the *whole* change. Ignores line-level issues; asks only whether the change could be reframed so whole branches, modes, helpers, or layers disappear (rubric standards 0 and 3). Must propose concrete alternative structures, not "consider refactoring".
- **Boundary & canonical-helper auditor** — one worker over the whole change. Searches the existing codebase for utilities/helpers/modules the diff duplicates, feature logic leaking into shared paths, logic in the wrong layer/package, and the same conditional repeated across slices (rubric standards 2, 5, 6).
- **File-size auditor** — only if step 2 flagged 1k crossings or growth of >1k files. For each, proposes a concrete decomposition (target modules and what moves where) (rubric standard 1).

Every review worker prompt contains: the target diff command, its scope, the rubric's absolute path, the step-2 change description, "read-only: do not edit files, do not run formatters/linters/tests", and this report shape:

```
Verdict for scope: blocker | request-changes | clean
Findings (max 8, highest conviction first; ≤2 cosmetic nits total):
- [severity: blocker|major|minor] [priority 1–7 from rubric] path:line(-line)
  Problem: one or two sentences, structural not cosmetic.
  Remedy: the concrete restructure (what disappears / moves / merges).
  Behavior preserved because: one sentence.
  Confidence: high|medium
Skipped / could not assess: …
```

## 4. Verify wave (parallel, one message)

Read every report against the rubric and the report shape. Then:

- **Dedupe** findings that multiple workers raised; keep the strongest remedy.
- **Challenge** every `blocker` and every `major` with `medium` confidence: dispatch one adversarial **Verifier** worker per cluster of related findings, all in one message. It re-reads the cited code and answers: is the problem real, does the remedy actually preserve behavior, is there an existing justification (comment, ADR, constraint) that waives it? Verdict per finding: `confirmed | downgraded | rejected` with evidence.
- A report missing `path:line`, a concrete remedy, or its scope gets a follow-up to the **same** worker, not a fresh dispatch.
- Drop rejected findings. Do not add findings yourself without a worker having checked the code.

## 5. Report

Give the user one review, ordered by the rubric's finding priority:

1. **Verdict** — `Approve` only if the rubric's approval bar is fully met; otherwise `Request changes`, naming the presumptive blockers hit.
2. **Blockers** — each with `path:line`, problem, remedy.
3. **Code-judo proposals** — the dramatic simplifications, stated as the target structure.
4. **Remaining findings** — majors, then minors; high-conviction only.
5. **File-size table** — only files near or across 1000 lines: before → after, proposed split.
6. **Not reviewed** — excluded files and anything workers could not assess.

Use the rubric's tone: direct, serious, demanding; no softening of structural problems, no nit floods.
