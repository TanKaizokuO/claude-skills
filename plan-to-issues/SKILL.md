---
name: plan-to-issues
description: Plan a feature or refactor as GitHub issues, each with a full implementation plan, or file a plan the user supplies as those issues. Use when the user wants work broken into actionable GitHub issues, says "plan this as issues", or asks to file, turn, or publish a plan as issues.
---

# Plan To Issues

Turn a feature, refactor, or supplied plan into GitHub issues. Each issue body is the complete plan: a reader with no other context can implement it from the body alone. The issue is the final artifact. A local file is written only when the user asks for one.

This skill plans and files. It never implements, edits code, commits, pushes, or creates branches. Body structure: `ISSUE-TEMPLATE.md` (sibling file, read it before step 4).

## Inputs

- **Request**: the feature or refactor, or the plan the user supplied (inline text or a file path).
- **Target**: resolve the repo from the current checkout with `gh repo view --json nameWithOwner,defaultBranchRef`, which reads the origin remote and gh auth. Use that `owner/repo` explicitly in every `gh` call. Ask only when the target is materially ambiguous (for example, two plausible repos that would receive different issues). Multiple remotes alone are not a question.

## 1. Load the repo's rules

Completion: each source below is read, or recorded as absent in the report.

- `AGENTS.md` or `CLAUDE.md` at the repo root, and every rule file they name (for example `CONTRIBUTING.md`). Apply their git, release, auth, secret, and member-data gates to the plan.
- The docs index they name (for example `docs/README.md`), and the root `README.md` when it is the API catalog.
- `docs/agents/issue-tracker.md`, `docs/agents/triage-labels.md`, and `docs/agents/domain.md` when present. Use the domain docs' terms exactly.

Rules:
- A missing `docs/agents/*` file does not block. Use GitHub through `gh` on the git remote, and take labels from step 5.
- If a rule file a doc names is missing, or two rule files conflict, stop and report. Do not choose a workflow silently.
- If `docs/agents/issue-tracker.md` names a tracker other than GitHub, stop. This skill files GitHub issues only.
- Never read secret folders or member data to answer a planning question. Record such evidence as an unknown.

## 2. Check existing work

Completion: every requested behaviour has a classification with evidence.

1. Read the code that implements or should implement each behaviour. For a code symbol, use LSP definition and references when available. Use grep only for text targets such as routes, strings, config keys, and doc phrases.
2. Search open and closed issues and PRs with focused queries, not bulk fetches. For each keyword set run `gh issue list --repo <owner>/<repo> --state all --search "<terms>" --limit 50 --json number,title,state,url,closedAt` and the matching `gh pr list --repo <owner>/<repo> --state all --search "<terms>" --limit 50 --json number,title,state,url,closedAt`. Fetch full bodies and comments (`gh issue view <n> --repo <owner>/<repo> --json body,comments`) only for candidates whose title or state plausibly covers the same behaviour.
   - If a search returns exactly `--limit` results, it is truncated. Narrow the terms, or page with `gh api --paginate 'repos/<owner>/<repo>/issues?state=all&per_page=100'` and filter with jq. Record any truncation left unresolved as an unknown.
3. Classify each behaviour as **complete**, **partial**, **implemented but disabled/unreleased**, or **absent**. Cite file paths, symbols, doc paths, and issue or PR links. A closed issue, merged PR, or documented plan does not prove the behaviour is enabled in production.
4. Reuse tracking: if an open issue or PR already covers a behaviour, do not draft a duplicate. Report it with its URL. If a behaviour is complete, report the evidence and draft nothing for it.

## 3. Shape the issues

Completion: an ordered list where each entry has a title, a one-sentence outcome, and its blockers.

- Default to **one** coherent issue. Split only where two or more slices are independently actionable, each demoable or verifiable on its own.
- A wide mechanical change (rename, retype, or move across many callers) defaults to one coherent clean cutover: migrate every caller in the same issue and remove the old form. Use phased compatibility (expand, migrate in batches, contract) only when a real release or consumer constraint requires it, and name that constraint in the issue's Approach and tradeoffs.
- Do not explode the plan into one issue per file. File-level steps live inside the body.
- Make every dependency explicit. Order issues so blockers come first.
- Resolve genuine scope or design decisions before drafting bodies. Batch related material decisions into one question, each with a recommended answer. Ask with the session's question tool when one is available; otherwise list the batch in your reply and wait. Do not force one decision per turn.
- Never ask about facts that the repo, docs, or GitHub can answer. Look them up.

## 4. Draft the bodies

Completion: each body has every section of `ISSUE-TEMPLATE.md`; every existing path, symbol, doc, issue, and PR it cites was verified; every new path or symbol is labelled `(proposed)`.

- Write each body from `ISSUE-TEMPLATE.md`. Save drafts to a unique per-run directory: `mktemp -d "${TMPDIR:-/tmp}/plan-to-issues-XXXXXX"`, outside the repo. Save a local plan file in the repo only if the user asks for it, at the path they name.
- Verify each existing reference with LSP or `read`/`grep`. Label anything that does not exist yet `(proposed)`. Do not invent symbols, measurements, or test results.
- Each body stands alone. The parent summary, if any, is extra; it never replaces content.
- Acceptance criteria are measurable and observable. Each has a focused test or a behavioural smoke step.
- Record every unverified fact under **Unknowns**.
- Run step 5 first. Then show the user the full set: order, titles, verified labels, blockers, and the duplicate check from step 2. Wait for approval.

## 5. Check labels

Completion: every label you will apply is confirmed present in the repo.

- List every label with pagination: `gh api --paginate repos/<owner>/<repo>/labels --jq '.[].name'`. Never trust a truncated `gh label list`.
- Readiness label: required only when `docs/agents/triage-labels.md` exists and maps the role for this issue (`ready-for-agent` for an AFK agent, `ready-for-human` for a human). If the mapped label is absent, report a blocker and ask for authorized restoration of that exact label name. Remap to another existing label only if the target repo's rules allow remapping; if they require exact names, do not substitute. Never create a label without approval. Never silently downgrade readiness. A missing custom triage doc is not a blocker: apply no triage label and say so.
- Optional labels (priority, area, and similar) apply only when they exist. If one is absent, omit it and say so in the report.
- Do not assign anyone.

## 6. Publish

Completion: every approved issue is created, its URL is in the ledger, and the native edges are verified or reported as unsupported.

Gate: publish only after the user approves the exact set from step 4 in this conversation, with labels already validated in step 5. Invoking this skill to "file it" states intent; it does not waive this confirmation. A plan-only request stops after step 5 with the drafts saved and makes no GitHub writes.

Ledger: `<run-dir>/ledger.md`, one row per issue: title, status (`planned`, `created #n <URL>`, `failed <error>`). Write each `created` row before the next call that changes GitHub. The ledger is the only record of what this run created.

Order: create issues in dependency order, blockers first.

For each issue:
1. Before creating, check the ledger. A `created #n <URL>` row is re-read with `gh issue view <n> --repo <owner>/<repo> --json number,title,body,state,url`. Reuse it only when its body matches this draft's scope and content and the user authorized reuse; otherwise report the conflict. Without a ledger row, search with focused terms from the outcome (`gh issue list --repo <owner>/<repo> --state all --search "<terms>" --limit 50 --json number,title,state,url`), then inspect each plausible candidate's full body before deciding.
2. Never match on title equality alone. A same-title issue that is closed, unrelated, or of different scope is never reused.
3. Replace each `Blocked by` placeholder with the real blockers already created: `#n` for the same repo, `owner/repo#n` or the full issue URL for another repo. Resolve each blocker in its actual repo; never assume the target repo's number.
4. Create: `gh issue create --repo <owner>/<repo> --title "<title>" --body-file <draft> --label <label>` for each verified label.
5. Record the returned number and URL in the ledger immediately.

Native blocking edges, after all issues exist (GitHub REST issue-dependencies API, verified against docs.github.com/en/rest/issues/issue-dependencies). Use them only for blockers in the same repo as the child, and only where the user authorized this write:
- Read a child's blockers: `gh api --paginate repos/<owner>/<repo>/issues/<child-number>/dependencies/blocked_by`. Each returned issue has `number`, `id`, and `repository_url`. Match exact identity on `repository_url` plus `number`, not on bare number.
- Add an edge: `gh api --method POST repos/<owner>/<repo>/issues/<child-number>/dependencies/blocked_by -F issue_id=<blocker-database-id>`. Get the blocker's database id with `gh api repos/<blocker-owner>/<blocker-repo>/issues/<blocker-number> --jq .id`.
- Cross-repo blockers get no native edge and no write to the other repo. Keep their `owner/repo#n` or URL line in `Blocked by:` and report the capability limit.
- If an edge call fails, record a capability or permission limit. Keep the body's `Blocked by:` links as the explicit graph. Do not re-create issues to work around it.

If any call fails, stop and report the ledger. Retry only after the step 1 check.

## 7. Verify

Completion: every created issue re-read, and the dependency graph matches the approved plan.

- For each issue: `gh issue view <n> --repo <owner>/<repo> --json number,title,body,labels,state,url`. Confirm the title, labels, every template section, and the `Blocked by:` line.
- For each blocked issue: compare each returned blocker's exact identity (`repository_url` and `number`, with `id` for native edges) against the approved plan's full references. Do not compare counts or bare numbers. Use `issue_dependencies_summary` as a secondary check only.
- Fix any mismatch with `gh issue edit <n> --repo <owner>/<repo>` only when the user approved the correction. Otherwise report it.
- If the read endpoint is unavailable, report the native graph as not verified and confirm the `Blocked by:` links by reading each body.

## 8. Report

Lead with the result:

- Issues created, as a dependency-ordered list of number, title, URL, and labels.
- Readiness per issue: ready, blocked (by what), or needs a decision (which one).
- Existing issues or PRs that already cover the request, with their classification.
- Unknowns, and any label or permission blocker.
- Native dependency capability: exact edges verified, or unsupported with the `Blocked by:` links as the graph. Include the run directory and ledger path.
- State plainly: this is a plan filed as issues. No code was implemented, committed, or pushed.
