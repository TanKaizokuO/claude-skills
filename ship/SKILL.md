---
name: ship
description: Fix .gitignore, secret-scan, commit, and push the current repo to GitHub, creating the GitHub repo when there is none.
---

Ship the working tree of the current repo to GitHub in one run. Typing `/ship` is the user's standing authorization to commit and push: push without asking, and pause only at the stops named below. Published history stays exactly as it is: plain `git push` and `git pull --rebase` only (no `--force`, no amending or rebasing pushed commits), to the remote already configured.

Text after `/ship`: `$ARGUMENTS` — a commit-message hint steers step 4; a follow-on task ("then create lesson 14") runs after step 6.

## 1. Inspect

From the repo root: `git status -sb`, `git remote -v`, `git log --oneline -10`.

- **Not a repo, or no remote** → new-repo path: `git init -b main` (an existing repo on `master` gets `git branch -M main`), then ask once with `AskUserQuestion`: public or private.
- **Mid-merge, mid-rebase, or detached HEAD** → stop and report.
- **Nothing to commit and nothing ahead of upstream** → report "nothing to ship" and stop.

Done when you know the branch, its upstream (or the new-repo path), every changed and untracked file, and the log's message style (`feat(scope):` conventional, or plain imperative sentences).

## 2. Fix `.gitignore`

Baseline for every repo — the user finds committed agent folders unprofessional: `.venv/`, `.env`, `.env.*` with `!.env.example`, `.omp/`, `.claude/`, `__pycache__/`, `node_modules/`, `.DS_Store`, `Thumbs.db`. Probe with git, so existing equivalents count:

```bash
for p in .venv/x .env .env.local .omp/x .claude/x __pycache__/x node_modules/x .DS_Store Thumbs.db; do
  git check-ignore -q --no-index "$p" || echo "missing: $p"; done
git check-ignore -q --no-index .env.example && echo "over-ignored: .env.example"
```

Append the missing entries as one block at the end, in the file's comment style. Existing rules and `!` negations stay untouched — the user un-ignores paths on purpose. Also ignore untracked files that are plainly local: credential notes (SSH host/password files), scratch output, files ≥ 50 MB. Then `git ls-files -ci --exclude-standard` lists tracked files now ignored: `git rm -r --cached` the ones matched by lines you just added (`git check-ignore -v --no-index <path>` names the line); files matched by older rules were force-added deliberately and stay.

Done when the probe prints nothing and no local-only file remains tracked or untracked-and-unignored.

## 3. Stage and secret-scan

Stage with `git add -A` (or by path group when the diff splits into separate logical commits). Scan everything this push publishes — staged changes plus unpushed commits:

```bash
BASE=$(git rev-parse -q --verify '@{u}' || git rev-parse -q --verify origin/HEAD || git hash-object -t tree /dev/null)
git diff --cached -U0 "$BASE" | grep -E '^\+' | grep -iE '(pass(word|wd)?|secret|token|api[_-]?key)\w*\s*[:=]\s*\S{6,}|sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_|AKIA[0-9A-Z]{16}|sb_secret_|eyJ[A-Za-z0-9_-]{10,}\.eyJ|BEGIN [A-Z ]*PRIVATE KEY|://[^/[:space:]:@]+:[^/[:space:]@]+@'
git diff --cached --name-only "$BASE" | grep -E '(^|/)(\.env(\.[^/]*)?|id_(rsa|ed25519|ecdsa)[^/]*|[^/]*\.(pem|key|p12|pfx))$' | grep -v '\.env\.example$'
git diff --cached --name-only --diff-filter=AM "$BASE" | xargs -r -d '\n' du -m | awk '$1 >= 50'
```

Judge every hit. A **secret** is a literal credential: a password, token, private key, or a URL with a password in it. An env-var lookup, a placeholder, or a public anon key is not. A large file goes back to step 2.

A secret in the staged changes → unstage that file and stop, reporting `file:line` with the value masked and the fix (gitignore it, or read it from `.env`). A secret inside an unpushed commit → stop and report; rewriting that commit is the user's call.

Done when the three commands print nothing, or every remaining hit is judged not a secret.

## 4. Commit

Short message saying what changed, in the step-1 style, steered by `$ARGUMENTS`. One commit per logical change — usually one.

Done when nothing is staged and the only uncommitted files are ones you deliberately left out.

## 5. Push

- **Upstream set** → `git push`. Rejected as non-fast-forward (the user often pushes from the remote GPU box) → `git pull --rebase --autostash`, then `git push`. A rebase conflict → `git rebase --abort`, stop, and list the conflicting files; the commit stays local.
- **Branch without upstream** → `git push -u origin HEAD`.
- **New-repo path** → `gh repo create "$(basename "$PWD")" --public|--private --source=. --remote=origin --push`. Name already taken on the account → stop and ask.
- **Any other failure** (network, auth) → keep the commit and report the error.

Done when `git status -sb` shows the branch level with its upstream: no `ahead`, no `behind`.

## 6. Report

One line: `<hash(es)> <branch> → <remote URL>`, followed by any `.gitignore` additions and anything left uncommitted or stopped on. Then run the follow-on task from `$ARGUMENTS`, if any.
