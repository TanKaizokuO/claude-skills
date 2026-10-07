---
name: pull-from-gh
description: Pull the latest GitHub changes into the current repo (rebase + autostash), or into each sub repo the user approves when the current directory is not a repo.
---

Bring the current repo up to date with its GitHub remote in one run. Typing `/pull-from-gh` is the user's standing authorization to pull: pull without asking, and pause only at the stops named below. Local work is never discarded: plain `git pull --rebase --autostash` only (no `--force`, no `reset --hard`, no `checkout -- .`, no `stash drop`), from the remote already configured.

Text after `/pull-from-gh`: `$ARGUMENTS` — a follow-on task ("then run the tests") runs after step 4.

## 1. Find the repo(s)

First check whether the current directory is inside a repo: `git rev-parse --show-toplevel`.

- **Inside a repo** → continue with that repo from its root.
- **Not inside a repo** → look for sub repos (see below). Never `git init` or `gh repo clone` here.

**Sub-repo discovery** (current directory is not a repo). List repos up to three levels down, without descending into a repo once found:

```bash
find . -maxdepth 3 \( -name node_modules -o -name .venv -o -name .cache \) -prune -o -name .git -print0 | xargs -r -0 -n1 dirname | sort
```

- **One or more found** → ask once per sub repo with `AskUserQuestion` (up to 4 questions per call; batch the rest in further calls): "Pull `<path>`?" with options Pull / Skip, showing the path relative to the current directory. Then run steps 2–3 for each repo answered Pull, one after another, from that repo's root (`git -C <path>` or `cd` into it). A stop condition in one repo (conflict, no upstream, diverged state) is reported for that repo and does not block the others. All answered Skip → report "nothing selected" and stop.
- **None found** → report "no git repo found" and stop.

## 2. Inspect

From the repo root: `git status -sb`, `git remote -v`, `git branch -vv`.

- **No remote** → report "no remote configured" and stop.
- **Mid-merge, mid-rebase, or detached HEAD** → stop and report.
- **Branch without upstream** → if `origin/<branch>` exists, `git branch -u origin/<branch>`; otherwise stop and report that the branch has no remote counterpart.

Done when you know the branch, its upstream, and whether the tree is dirty.

## 3. Pull

```bash
git fetch --prune
git pull --rebase --autostash
```

- **Rebase conflict** → `git rebase --abort`, stop, and list the conflicting files; the tree returns to its pre-pull state. If `--autostash` left a stash behind after a failed pop, leave it and report `git stash list`.
- **Any other failure** (network, auth) → report the error and change nothing.

Done when `git status -sb` shows the branch with no `behind`.

## 4. Report

One line per repo: `<branch> ← <remote URL>: <N> new commits (<old hash>..<new hash>)`, or `already up to date` (prefix the sub-repo path when more than one repo was in play), followed by anything stopped on and the sub repos skipped. Then run the follow-on task from `$ARGUMENTS`, if any, once after all repos are done.
