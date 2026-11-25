---
name: finish-pr
description: Prepare, check, merge, or clean up a GitHub pull request for the current repo — open or update the PR for a task branch, judge readiness on its exact head SHA, squash-merge when authorized, then remove owned merged branches and worktrees. Use when the user asks to open or update a PR, check whether a PR is ready to merge, land or merge a PR, or clean up branches and worktrees after a PR merged or closed.
---

Run only the stages the user named, in order: `prepare` → `check` → `merge` → `cleanup`. "Finish", "land", or "ready" alone means `prepare` + `check`, never `merge`. Each stage has an entry test and a completion criterion; a failed entry test stops the run and is reported.

**Authority.** The named stage authorizes its own outward actions: `prepare` may push the task branch and open or update its PR; `merge` may merge that PR. Anything beyond — force-push, closing someone else's PR, deleting a remote branch that is not owned, editing branch protection, releasing — needs explicit approval in this conversation.

**Hard lines, every stage.** The repo's contribution rules add to these and never loosen them.
- Never push to, merge into, or delete the default branch or any release branch.
- Never release to production.
- Never bypass a check: no `--admin`, no required-check edits, no self-approval, no skipped hooks.
- Force-push only `--force-with-lease` to your own unmerged task branch, and only if the rules allow it.

## 1. Resolve context (every run, read-only)

- `gh repo view --json nameWithOwner,defaultBranchRef` and `gh api user -q .login` → repo, base, actor.
- `git status --porcelain=v1 -b`, `git rev-parse --abbrev-ref HEAD`, `git rev-parse HEAD`, `git worktree list --porcelain`, `git remote -v`.
- Read the repo's contribution rules if present (`CONTRIBUTING.md`, `.github/pull_request_template.md`): branch name, PR title style, merge method, required checks, docs-only definition, draft policy.
- Stop and report on: detached HEAD; merge, rebase, or cherry-pick in progress; no `origin`; `gh` not authenticated; HEAD on the base branch with unpushed commits.

Completion: a resolved table — repo, actor, base, head branch, head SHA, worktree path, dirty files, rules applied. Dirty files are listed and left untouched unless the user says what to do with them.

## 2. Prepare

Entry: `prepare` requested, §1 complete.

1. **Branch.** If HEAD is the base branch and only uncommitted changes exist, `git switch -c <task branch>` (no reset, no discard). Name it per the repo's rules, else `task/<actor>-<topic>`. Renaming a branch that already has an upstream → stop and ask.
2. **Existing PR.** `gh pr list --head <branch> --state all --json number,url,state,isDraft,baseRefName,headRefOid`. One OPEN PR → reuse it (edit its body only if asked). MERGED or CLOSED → report it; do not open a second PR for the same branch without asking.
3. **Commit and push.** If anything is uncommitted or unpushed, run the `push-to-gh` skill (commit, secret scan, push). Stop instead if: there is no remote; `push-to-gh` would push to the base or a release branch; or `push-to-gh`'s `.gitignore` edits would pull unrelated files into this PR.
4. **Validate the complete diff.** `git fetch --prune origin`; `git diff --stat origin/<base>...HEAD`; read `git diff origin/<base>...HEAD` in full; `git diff --check origin/<base>...HEAD`. Behind base (`git merge-base --is-ancestor origin/<base> HEAD` fails) → report; rebase only when asked.
5. **Create or update the PR.**
   - Create: `gh pr create --base <base> --head <branch> --title <title> --body-file <file>`, plus `--draft` if the work is unfinished or the rules say drafts. Title in the repo's style (Conventional Commits if the rules or log say so). Write the body to a temp file outside the repo and delete it afterwards.
   - Body, one short section each: `## What` (the change) · `## Why` (reason, linked issue) · `## Test` (exact commands run and their results) · `## Evidence` (observed output, CI run URL). Write "not run" for anything not run.

Completion: exactly one PR for this head branch is OPEN, or its non-open state is reported; its URL and number are recorded; the body has What, Why, Test, Evidence.

## 3. Check (read-only verdict)

Entry: PR number known (from §2 or the user).

1. `gh pr view <n> --json number,url,state,isDraft,baseRefName,headRefName,headRefOid,mergeable,mergeStateStatus,reviewDecision,author`.
2. **Target head.** `headRefOid` from step 1 is the authoritative remote head, read from gh from any checkout; never compare it with a checkout you are not working in, and never switch checkout just to inspect. Compare it with local `git rev-parse HEAD` and `git rev-parse @{u}` only when this run pushes or edits the branch. In such a run, a mismatch, unpushed commits, or a behind upstream means the PR is not judged at the current HEAD: push if `prepare` authority covers it, otherwise report stale.
3. **Checks at that SHA.** `gh run list --commit <headRefOid> --json databaseId,workflowName,headSha,status,conclusion,url` and `gh pr checks <n>`. Required checks are those the repo's rules or branch protection name; if neither names any, treat every check on the PR as required.
4. **Green is binary.** A check is green only when its conclusion is `success` on `headRefOid`. Pending, queued, in progress, failure, cancelled, timed out, action required, stale (another SHA), or missing (no run for the head) is not green. Skipped or neutral is green only if the repo's rules say so.
5. **Docs-only exception.** Applies only when the repo's rules define one and every file in `git diff --name-only origin/<base>...HEAD` fits that definition. Then the rules' lightweight checks (diff whitespace, relative links, secret scan) replace CI. Any non-doc file, or a mixed PR, uses normal CI.
6. **Mergeability.** State OPEN; not draft (if draft, ask whether to mark ready); `mergeable` MERGEABLE; `mergeStateStatus` clean under the rules; `reviewDecision` satisfies any required approvals. Any block → NOT READY.
7. **Failed or pending check.** Diagnose with the `ci-triage` skill at `headRefOid`. Do not rerun it here.

Completion: verdict READY or NOT READY; a row per required check (name, short SHA, state, run URL); each blocker listed.

## 4. Merge (only when the user asked to merge or land this PR)

Entry: verdict READY at the current head, and a merge request in the conversation.

1. Repeat §3 immediately before merging. If `headRefOid` moved, return to §3.
2. `gh pr merge <n> --squash --match-head-commit <headRefOid>`, where `headRefOid` is the exact remote SHA verified in §3; local HEAD does not matter here. Squash unless the rules name another method. No `--admin`; no `--auto` unless asked. `--match-head-commit` binds the merge to the verified head.
3. Observe: `gh pr view <n> --json state,mergedAt,mergeCommit,url`. Report MERGED only when this output says MERGED.

Completion: observed state MERGED with its merge commit SHA. If gh refuses, quote its message and stop; do not work around it.

## 5. Cleanup (only after an observed MERGED or CLOSED)

Entry: `gh pr view` shows MERGED or CLOSED. Run `git fetch --prune origin` first, and quote counts only after it.

**Owned** means: this run created the branch or worktree, or the PR's author login equals the actor.

Eligibility, for every branch, worktree, or remote branch deleted here. All must hold:
- Observed state: `gh pr view` shows MERGED or CLOSED in this run. Never infer a merge from `git branch --merged`; it misses squash merges.
- Owned, and not the default, base, or release branch.
- No dirty work: its worktree, if any, is clean (`git -C <path> status --porcelain` empty) and holds no ignored data that is not regenerable build output (e.g. `.env`, local databases).
- No local-only commits: `git merge-base --is-ancestor <branch> <headRefOid>` succeeds. Squash merges make `git branch -d` refuse, so use `git branch -D` only after this check passes.

Policy by observed state:
- **MERGED, owned, eligible** → delete the local branch, its worktree, and the remote branch. The repo's contribution rules (CONTRIBUTING.md, Branches) say the author deletes these after a merge, with no approval needed.
- **CLOSED unmerged, owned, eligible, repo rules present** → delete the same way. The rules say the author deletes its own local and remote branch after the PR closes, and the requested cleanup stage is explicit cleanup intent. Without repo rules, retain and report.
- **Foreign or unrelated branches, or any failed gate** → retain and list the reason. Deleting one needs explicit approval for that branch. Dirty work is never deleted, with or without approval; report it and ask.

Worktree: `git worktree remove <path>` only after its branch is deleted under the rules above. Never `--force`. Then `git worktree prune`.
Remote branch: `git push origin --delete <branch>` only for owned branches under the rules above; skip if already gone.

Completion: `git worktree list`, `git branch -vv` for the head branch, and branch and worktree counts after fetch; every deleted item and every retained item listed with its reason.

## 6. Report

Compact, in this order:
- **PR:** URL, number, base ← head, observed state (from gh).
- **CI evidence:** table of required checks at `headRefOid` (name, state, run URL).
- **Actions performed:** each outward or destructive command and its result.
- **Retained:** each item and why.
- **Blockers and unknowns:** exact missing input, or "none".
