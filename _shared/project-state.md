# Project state: discovery and evidence

Shared reference for `/whats-next` (reads only) and `/sync-docs` (writes). Both run §1 and §2 against the git repo in the current directory, or the one the user names.

Prefix every shell command with `export _ZO_DOCTOR=0;` (the shell prints a zoxide warning otherwise). The shell is zsh: an unmatched glob such as `docs/*.md` aborts the whole command, so list files with `find`. **Today** is `date +%F`. Take every date you compare or write from it, never from memory or from a doc.

## 1. Discover the state docs

A **state doc** is any file that records progress. Find them by role, not by name: these repos rename them (BioMedical_QA `HANDOFF.md`→`STATUS.md`, `Upcoming_goals.md`→`TODO.md`; learning/backend `HANDOFF.md`→`LOG.md`, `AGENTS.md`→`CONVENTIONS.md`).

1. Record the baseline: `git status --short`.
2. List candidates: `find . -maxdepth 2 -name '*.md' -not -path '*/.*' -not -path '*/node_modules/*'`, plus `docs/adr/` or `adr/` if present.
3. Map old names: `git log --diff-filter=R --name-status --format= | grep -E '^R[0-9]+\s+[^/]+\.md\s'`. When the user names a doc that is gone, use its new name.
4. Read the head of each candidate and give it one role. A doc's own statement about how it changes ("regenerated wholesale", "append-only") wins over this table.

| Role | Names seen | How it changes |
|---|---|---|
| rules | `CLAUDE.md`, `AGENTS.md` (often gitignored), `CONVENTIONS.md`, a "Conventions" / "Rules" section in a status doc | never; obey it |
| glossary | `CONTEXT.md`, `GLOSSARY.md` | never; use its terms in every sentence |
| status | `HANDOFF.md`, `STATUS.md`, `STATE.md`, `WORK.md` | snapshot: rewrite stale lines, bump its date line |
| goals | `Upcoming_goals.md`, `TODO.md`, box prompts (`A4000.md`, `Ideapad.md`) | strike done items with proof, add new items |
| roadmap / plan | `ROADMAP*.md`, `research_roadmap.md`, `docs/research_roadmap.md`, `lesson_plan.md`, `feature-list.md`, `Plan_*.md`, trackers | strike done items, move internal dates |
| log | `LOG.md` | append one dated entry |
| decisions | `docs/adr/*` | never; cite as evidence |
| outside repo | `~/Documents/context.md` | only when the user names it |

READMEs, lessons, papers, and teaching notes are out of scope. Read each rules file in full and note its **ignore list**: paths that are frozen or ignored (learning/backend `STATE.md` "Conventions that must hold": `lessons/js/` frozen, ignore `summaries/`). Ignored paths give no evidence and get no edits.

Done when every candidate has a role or is out of scope, and the ignore list is written down.

## 2. Gather evidence

For each state doc:

1. **Anchor**: the older of `git log -1 --format='%h %cs' -- <doc>` and the doc's own date line ("Last updated", "Current Date", a dated title). The commit can be newer than the text: BioMedical_QA `ROADMAP.md` says Aug 17 but was last committed Aug 23.
2. **Commits since**: `git log --since=<anchor date> --format='%h %cs %s' -- . ':!<ignored path>'`. When a subject does not show that an item is finished, read `git show --stat <hash>`.
3. **Files**: check each output path the doc names with `test -e`; list new results with `git log --since=<anchor date> --name-only --format= -- docs/harvest | sort -u`.
4. **Issues** (only with a GitHub remote): `gh issue list --state all --limit 50 --json number,title,state,closedAt,labels`. Issues go stale too: BioMedical_QA #2 (G1) and #3 (G2) stay open after both gates passed.
5. **Uncommitted work** from the baseline shows work in progress, never proof of done.

**Proof** is a commit hash, an existing file, a result file, or a closed issue. An item without proof stays open.

A **drift** is a line that disagrees with the evidence: an open item that is done, a due date in the past for open work, a stale date line, a pointer to a renamed file (BioMedical_QA's gitignored `CLAUDE.md` still names `Upcoming_goals.md`), or an open issue for finished work.

Done when every open item in every state doc is marked done (with proof), in progress, or not started, and every drift is listed.

## Words

Write output and doc edits in ASD-STE100 Simplified Technical English: short sentences, active voice, one meaning for each word, and the glossary's terms.
