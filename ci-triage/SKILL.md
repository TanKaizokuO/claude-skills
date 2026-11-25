---
name: ci-triage
description: Diagnose GitHub Actions CI at an exact commit, PR, or run — status, the failed step and its cause, job durations, and local reproduction of a CI job. Use when the user asks why CI or a check is red, what a workflow run or job shows, how long CI takes or what is slow, or how to reproduce a CI job locally. Fixing or rerunning happens only when explicitly requested.
---

Investigate GitHub Actions at one exact commit. Default is authenticated and read-only: nothing is rerun, pushed, or edited unless the user asks for that mode. CI validates a commit; a deployment changes a running system. A deploy workflow or environment deployment is not CI, and a green CI run is not evidence of deployment. Keep the two apart in every report.

**Modes** — pick from the request; default to `status` plus `diagnose` for any failure. Run only the named modes: `status`, `diagnose`, `duration`, `parity`, `fix`.

**Hard lines.**
- Never `gh run rerun` to confirm a reported error. Read the existing logs.
- Never run untrusted PR code with secrets or on an open runner. Never run deploy, release, or publish commands locally.
- Never disable, skip, or weaken a CI step (`if: false`, `continue-on-error`, deleted job, removed check) to make it pass. Never add retries, caching, or runner changes unless the user scopes them.
- Never report a remote success you did not observe.

## 1. Pin the target

- Resolve to a full SHA. Remote inspection needs no fetch and works from any checkout. When the cwd is not the repo, name it explicitly: `-R <owner>/<repo>` for `gh`, `repos/<owner>/<repo>/…` for `gh api`.
  - PR → `gh pr view <n> --json headRefOid,url`. This is the authoritative remote head; do not compare it with local HEAD.
  - Exact SHA given → use it as is, and confirm it on the remote with `gh api repos/<owner>/<repo>/commits/<sha> --jq .sha`.
  - Branch, tag, or other ref → `gh api repos/<owner>/<repo>/commits/<ref> --jq .sha`.
  - Local replay or fix only → if `git cat-file -e <sha>^{commit}` fails, run `git fetch --prune origin`. Replay in a detached worktree (`git worktree add --detach <path> <sha>`) and remove it when done; never checkout or reset the user's dirty work.
- Runs at that SHA: `gh run list --commit <sha> --limit 50 --json databaseId,workflowName,event,headBranch,headSha,status,conclusion,createdAt,updatedAt,url`.
- A run whose `headSha` differs from the target is stale for it: report it separately.
- Read the workflow files at that SHA without a checkout: `gh api repos/<owner>/<repo>/contents/.github/workflows?ref=<sha> --jq '.[].path'`, then each file with `gh api repos/<owner>/<repo>/contents/<path>?ref=<sha> --jq .content | base64 -d`. Use `git show <sha>:<path>` only when that object exists locally. Their `on:` triggers classify CI versus deploy. `workflow_run` means another run triggered it: follow the chain.

Completion: SHA; runs for it (id, workflow, event, status, conclusion, URL); stale runs listed. Zero runs → "no run exists for <sha>", which is not green.

## 2. Status

`gh run view <id> --json status,conclusion,headSha,event,url,jobs` → each job's name, status, conclusion. An in-progress run is reported as in progress, with the duration lower bound from §4.

Completion: every job of every run at the SHA has a stated status.

## 3. Diagnose a failure

1. **Locate.** Failing jobs: `gh run view <id> --json jobs --jq '.jobs[] | select(.conclusion=="failure") | .name'`. Failing steps: `gh api --paginate repos/{owner}/{repo}/actions/runs/<id>/jobs --jq '.jobs[] | select(.conclusion=="failure") | {name, steps: [.steps[] | select(.conclusion=="failure") | .name]}'`.
2. **Log.** Completed run: `gh run view <id> --log-failed`. Single job: `gh run view --job <jobId> --log`. Save the output to a temp file and search it with the grep tool. Do not paste whole logs.
3. **Sanitize** before quoting. Mask tokens, passwords, keys, credentialed URLs, and env values. Quote only the failing lines, labelled with job and step.
4. **Classify** each failure by the log line that proves it:

| Class | Proving evidence in the log |
|---|---|
| application/test | a failing test name, assertion, compile or type error, or runtime error in files the commit touches |
| workflow/environment | missing env var or secret name, action input or version error, toolchain version unavailable, dependency or registry fetch failure, timeout, unhealthy service container, wrong path or working directory |
| permissions/runner/queue | 401/403 or "Resource not accessible by integration", token scope, fork PR without secrets, self-hosted runner offline or label mismatch, job waiting for a runner |

   No proving line → `unknown`.
5. **Cause.** State only a cause that a log line proves. Otherwise write "cause unproven" and name the single datum needed next.
6. **Deep application bug.** Hand the failing test to the `diagnosing-bugs` skill. This skill keeps ownership of the CI question until §6 proves the result.

Completion: failing job and step; classification with its masked proving line; cause or "unproven"; next action.

## 4. Duration

Use API timestamps only; do not estimate.

- Per job: `gh api --paginate repos/{owner}/{repo}/actions/runs/<id>/jobs --jq '.jobs[] | [.name, .created_at, .started_at, .completed_at, .conclusion] | @tsv'`.
- Queue = `started_at − created_at`. Execution = `completed_at − started_at`.
- Run elapsed = latest `completed_at` − earliest `created_at`.
- Parallel jobs: elapsed follows the longest chain of `needs:` dependencies, not the sum of job durations. Report the sum separately as total runner time.
- In progress: `now − start` (`date -u +%FT%TZ`) is a lower bound on the final duration. Label it so.
- Compare only runs of the same workflow and trigger. One run is not a trend.

Completion: table per job (queue, execution, conclusion); run elapsed; critical path; lower-bound flag where it applies.

## 5. Local parity

Scope to the named job. Read its definition first: `runs-on` (OS, arch), `container`, toolchain `setup-*` versions, `services:`, `env:`, `secrets.*` names, `if:` gates, `github.event_name` and base context, `working-directory`, and the `run:` commands in order.

Parity table: step | CI command | local equivalent | differences (OS/arch, version, service, secret, event, network).

Run locally only when asked and safe: the same commands, in a clean checkout of the SHA, with no secrets, no untrusted PR code given credentials, and no deploy or publish steps. Label each result "local — differences: …". Never present it as a CI pass.

Completion: parity table; any local results with their labelled differences.

## 6. Fix or rerun (only when asked)

1. The §3 diagnosis must exist first. Fix only what it proves. Workflow-level changes (versions, permissions, paths) are in scope only when the user names them.
2. Application code → `diagnosing-bugs` owns the fix investigation; this skill verifies the result.
3. Post-fix smoke: run the failing test or command locally and confirm it passes. Then run the repo's full suite once — the command CI runs — not repeatedly.
4. Remote proof needs push authority for the branch (see the `finish-pr` check stage). A push starts new runs at the new SHA; read them with §2. Run `gh run rerun <id> --failed` only when the user asks for a rerun.

Completion: fix commit SHA; smoke result; full-suite result (pass/fail counts); remote run status if pushed.

## 7. Report

- **Target:** SHA, PR or ref, mode run.
- **Runs and jobs:** table of status and conclusion, with timestamps where §4 ran.
- **Evidence:** masked failing lines with job and step.
- **Classification and cause:** proven cause, or "unproven" with the datum needed.
- **Actions:** "read-only", or each exact command and change.
- **Next action:** one concrete step.
