---
name: update-profile-readme
description: Update the TanKaizokuO GitHub profile repo (README featured projects, profile.json card rows, refresh the profile card) and suggest new updates from recent GitHub activity, stack drift, and stale or broken bits. Use for "update my profile README", "update TanKaizokuO", "what should I add to my GitHub profile", or /update-profile-readme.
---

Keep the GitHub profile repo `TanKaizokuO/TanKaizokuO` current. The skill suggests changes, you pick which ones to keep, and then it applies and pushes them. Typing `/update-profile-readme` authorizes the commit and push to `main` **only for the changes the user picks** in step 3.

Text after `/update-profile-readme`: `$ARGUMENTS`. A concrete request ("add daypane", "drop Go from languages") skips the menu: apply it in step 4, though the step 2 report is still shown for context.

## Repo facts

- Local clone: `~/Code/archive/TanKaizokuO`. If it's missing, `gh repo clone TanKaizokuO/TanKaizokuO` it there.
- `README.md` holds the card `<picture>` and then `# Featured Projects`, written as `### [title](https://github.com/TanKaizokuO/<repo>)` followed by one sentence. Keep **6** projects (commit `65f342b` trimmed it to 6).
- `profile.json` holds the neofetch-style rows (OS, Shell, Languages, Backend, AI / ML, Frontend, Contact). `luffy.txt` is the art.
- `generate.py` renders `dark_mode.svg` / `light_mode.svg` / `loc_cache.json`. **Never hand-edit those three files.** The `Profile card` workflow regenerates them daily at 00:15 UTC, on `workflow_dispatch`, and on any push that touches `generate.py`, `profile.json`, `luffy.txt` or the workflow file.
- Never commit stray files such as `activity.txt` or `development.log`. On 2026-11-14 the user chose to discard backdated contribution-filler commits. If they show up again, stop and ask.

## 1. Sync

```bash
cd ~/Code/archive/TanKaizokuO && git fetch --prune && git status -sb
```

- If the clone is clean and only behind, run `git pull --rebase`.
- If it's ahead or dirty, show `git log --oneline origin/main..HEAD` and `git status --short`, then ask whether to keep or discard those changes. Never reset without asking. Before any reset, back up to `backup/<date>`.

## 2. Scan and report

```bash
python3 ~/.claude/skills/update-profile-readme/scan.py ~/Code/archive/TanKaizokuO --days 60
```

The script is read-only and prints JSON. Turn it into a short numbered list of suggestions, grouped as follows. Only list items that are real findings.

**New or active repos**
- Each `candidates` entry is a possible addition. Before you suggest one, read its README (`gh api repos/<repo>/readme --jq .content | base64 -d | head -60`) and draft the one-sentence description in the existing style: name the concrete mechanism, use no hype, and end with a period. Skip dotfiles, configs, forks, skill and agent-config repos (such as `claude-skills`), course homework, and repos with an empty README, unless the user asks for them.
- A featured repo with `days_since_push` > 120, `archived`, `exists: false` or `renamed_to` should be suggested for swapping out or fixing its link. Pair each swap-out with a candidate so the list stays at 6.
- If a featured description differs from the repo's GitHub description, offer to sync them in whichever direction is better.

**Tech stack drift**
- `stack.used_but_not_listed` can be added to Languages. `stack.listed_but_unused_recently` are languages to *consider* removing. Say that "unused in the last 60 days" doesn't mean the user no longer knows the language, and don't push hard for removal.
- Check Backend / AI / ML / Frontend against the candidates' READMEs, dependency files, and topics, for frameworks that show up repeatedly but aren't listed.

**Broken or stale**
- If any of the last 5 `workflow` runs failed, show the failed run's log (`gh run view <id> --log-failed | tail -40`) and diagnose it.
- Check every `profile_rows` value: make sure the version strings are current (`zsh --version`, OS on this machine), the LinkedIn handle and email are still right, and no README link 404s.

End the report with "Nothing else found" if the list is short. Don't pad it.

## 3. Pick

Use `AskUserQuestion` with `multiSelect: true` and up to 4 options per question. Batch them by group, and show each proposed README line or row value in the option description. The user can type edits through "Other". Apply nothing they didn't pick.

## 4. Apply

- Edit only `README.md` and `profile.json` (and `luffy.txt` or `generate.py` if the user asks for them).
- Validate the JSON with `python3 -m json.tool profile.json >/dev/null`. Preview the card locally with `python3 generate.py --demo`, then `git checkout -- dark_mode.svg light_mode.svg loc_cache.json` so the demo SVGs never get committed.
- Show `git diff`.

## 5. Commit and push

```bash
git add README.md profile.json   # plus any other file the user asked to change
git commit -m "docs: <what changed>"   # e.g. "docs: feature daypane, drop MCP_2"
git push
```

Only use `git push`. Never force-push. If the push is rejected because the bot pushed a card refresh in the meantime, run `git pull --rebase` and push again.

- If `profile.json` changed, the push already starts the workflow. If only `README.md` changed and the user wants fresh stats, run `gh workflow run "Profile card" -R TanKaizokuO/TanKaizokuO`.
- Wait for the run with `gh run watch <id> -R TanKaizokuO/TanKaizokuO --exit-status` (one blocking call, no sleep loop), then report the result.

## Done when

The picked changes are on `origin/main`, the card workflow (if one was started) succeeded, and the user has a 3–5 line summary: what changed, what was suggested but skipped, and the run URL.
