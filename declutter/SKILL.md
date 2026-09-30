---
name: declutter
description: Read-only storage report or folder-bucketing plan first, then clean or move only what the user picks, with space-freed numbers and an undo log.
disable-model-invocation: true
---

Two modes, one **gate**: measure, show a **report**, then wait for the user's **picks**. Disk stays untouched until the user names items; a "read only" or "analysis" request ends at the report.

Every shell command starts with `export _ZO_DOCTOR=0;` (silences a zoxide warning). You have no sudo: any root command goes to the user as a `! sudo …` line for them to run.

## 0. Pick the mode

- `/declutter` or `/declutter storage [path]`, or wording about space, cache, "free up" → **storage**, scoped to the given path, else the **current working directory**. Scan the whole system only when the user says so explicitly ("whole system", "everything", `/declutter storage /`).
- `/declutter organise <dir>`, or wording about clutter, buckets, sorting → **organise**.
- Anything else: ask which mode and which path.

Done when the mode and target path are fixed.

## Storage

1. **Measure.** `<target>` is the path from step 0 (default: the current working directory). Record `df -h <target>` as the **baseline**. Size only what lies inside `<target>`: run the first bullet, plus any later bullet whose paths fall inside `<target>`. Nothing outside `<target>` goes in the report. Run every bullet only for an explicit whole-system request:
   - `du -xh --max-depth=2 <target> 2>/dev/null | sort -rh | head -25`
   - `du -sh ~/.cache/* ~/.npm ~/.local/share/Trash | sort -rh` — huggingface, pip, uv, npm, pnpm, yarn, camoufox, puppeteer, ms-playwright, browser caches
   - `docker system df` and `docker ps -a --format '{{.Names}}\t{{.Status}}'`
   - `journalctl --disk-usage`; `du -sh /var/cache/apt/archives`; `snap list --all | grep disabled` or `flatpak list --runtime`, whichever is installed
   - `find ~/.local/share ~ -maxdepth 1 \( -name '*.old' -o -name '*.tar.gz' \)`; files over 200 MB in `~/Downloads` with their dates
   - `.venv` / `node_modules` under `~/Code` whose project's last commit (`git -C <proj> log -1 --format=%cr`) is older than 60 days

   Done when every source above has a size or is noted absent.
2. **Report.** One table, biggest first: item · size · what it is in plain words · risk (`safe cache` / `re-downloadable` / `user data`) · exact command. Close with the total reclaimable and "pick items by name or number". Then stop.
   - **Protected**: `~/Code/Research/BioMedical_QA`, `~/Code/Research/LLM_Finetune`, and any project touched in the last 60 days stay out of the table unless the user names them.
   - **uv cache** is hardlinked into project `.venv`s, so `du` overstates it. Report the exclusive size: `find ~/.cache/uv -type f -links 1 -printf '%s\n' | awk '{s+=$1}END{print s}' | numfmt --to=iec`.
   - **Docker** volumes can hold database data: mark them `user data`; stopped containers and build cache are `safe cache`.

   Done when the table is shown and the user has replied with picks.
3. **Clean** exactly the picked items:
   - caches → `rm -rf` (or the tool's own `uv cache clean`, `npm cache clean --force`, `docker builder prune -f`)
   - user files → `gio trash`; trash frees space only once emptied, so offer `gio trash --empty` alongside
   - root-owned items, apt packages, journals → hand over `! sudo apt purge …`, `! sudo apt autoremove`, `! sudo journalctl --vacuum-size=100M`, `! sudo apt clean`, and wait for the user to confirm they ran them

   Done when every pick is removed or its `! sudo` line is confirmed run.
4. **Re-measure.** Run the same `df -h` again; report freed = new Avail − baseline Avail, plus a line per item. On "analyse again", rerun steps 1–2 against this new baseline.

   Done when the freed number is reported.

## Organise

1. **Survey** `<dir>` one level deep (plus one more inside folders that are clearly loose piles). Dotfiles, `.desktop` launchers, and old undo logs stay where they are. A git repo (`git -C <path> rev-parse` succeeds) moves only as one unit, its insides untouched.

   Done when every top-level entry is classed as file, folder, repo, or stays.
2. **Plan.** Reuse buckets already present in `<dir>` first; add new ones only for leftovers (by type, then subject — e.g. `Hollywood/`, `Bollywood/`, `Screenshots/`, `Academics/`). Show `bucket → entries` for every entry that moves, plus the list that stays. Then stop.

   Done when the user approves or edits the plan.
3. **Move with an undo log**, in a single bash command so the log variable survives:
   ```bash
   U="<dir>/.declutter-undo-$(date +%Y%m%d-%H%M%S).sh"; : > "$U"
   m() { mkdir -p "$(dirname "$2")"; [ -e "$2" ] && { echo "SKIP $1"; return; }
         mv -- "$1" "$2" && printf 'mv -- %q %q\n' "$2" "$1" >> "$U"; }
   m "<dir>/a.mp4" "<dir>/Hollywood/a.mp4"   # one line per planned move
   ```
   Done when every planned move is either logged in `$U` or printed as `SKIP` (name collision).
4. **Report** counts moved per bucket, the skips, and the undo command: `tac <undo-file> | bash`. On "undo", run it, then remove any bucket folders left empty (`rmdir`).

   Done when the counts and the undo command are shown.

**Repo variant** — when the target is itself a git repo ("find stale files"): report only. List untracked and ignored clutter (`git status --short --ignored`), build outputs, duplicate or superseded files, and files untouched for 90+ days with no references (`git grep -l <name>`), each with size and reason. Stop for picks, then `gio trash` exactly those.

Done when the report is shown, and after picks, every picked file is in the trash.
