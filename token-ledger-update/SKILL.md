---
name: token-ledger-update
description: Refresh the data in the "Token Ledger" Claude artifact (https://claude.ai/artifact/Y1iiTF4oWh5ANAqhfZR3gY) from omp and Claude Code usage. Use when the user says "update the token ledger", "refresh Token Ledger", "update the data of the artifact", or "republish the token dashboard".
---

# Token Ledger update

The artifact is the `dashboard_template.html` UI from `~/Code/projects/token-tracker` with one payload inlined: `const DATA = {...};`. Updating = regenerate that payload and swap only that JSON. Never touch the UI.

## Steps

1. **Sync omp** (stats.db is lazy; token-tracker reads session logs directly, but keep it fresh):
   `export _ZO_DOCTOR=0; omp stats -s`
2. **Generate the payload** (both sources by default: `omp` + `claude-code`):
   `cd ~/Code/projects/token-tracker && ./tokentrack.py json > $SCRATCH/data.json`
   - Keys: `generated, currency, messages, span, totals, by_day, by_model, by_source, by_project, by_day_source, cells, sub_cells`. The `json` command does not emit `initial_days`; `merge_data.py` adds `"initial_days": 0` (the dashboard command sets it; 0 = open on "All").
   - `cells` rows: `[day, source, model, project, n, in, out, cr, cw, cost]`. Cost is USD; the UI multiplies by `currency.per_usd` (INR, 95.56, from `pricing.json`).
   - Don't pass `--usd`/`--rate`. Don't use `--harness` unless the artifact currently has a `harness` key.
3. **100x cost issue: no correction needed.** The 100x inflation (gemini-3.x-flash, claude-opus-5, claude-sonnet-5, claude-opus-4-6) is in omp's own recorded `cost_*` columns. token-tracker ignores those and prices from `pricing.json` (verified: opus-5 $5/$25, sonnet-5 $2/$10, gemini flash $0.75/$3.75, per 1M tokens). Do NOT divide by 100 or the numbers will be 100x too low. Only if `pricing.json` itself is found wrong, fix it there. If a run ever reads costs from omp stats.db, divide those models by 100 instead.
4. **Read the artifact**: Artifact `action: read`, url above. It saves the full HTML to a file; use that path.
5. **Merge and splice DATA** with the bundled script (the DATA line is ~150KB; never hand-edit or Read it whole):
   `python3 -I ~/.claude/skills/token-ledger-update/merge_data.py <saved.html> $SCRATCH/data.json $SCRATCH/token-ledger.html`
   - Session logs get pruned (Claude Code `cleanupPeriodDays`, set to 90 on 2026-10-14), so a fresh parse loses old days. For each `(day, source)` where the old artifact has more messages than the fresh payload, the script keeps the old `cells`/`sub_cells`, rebuilds `totals`, `messages`, `span` and every `by_*` from the merged cells, and sets `initial_days: 0`. It prints the restored pairs. Days in the past changing a little (not dropping) is normal; a large unexpected list of restored days means something else broke, so investigate before publishing.
   - Sanity-check the printed line: `span[1]` is today, `messages` ≥ the old artifact's count, both sources present.
6. **Republish** with Artifact `file_path=<out>`, `url=https://claude.ai/artifact/Y1iiTF4oWh5ANAqhfZR3gY`. Same url, no `icon`, no `description` changes. Put the temp files in the scratchpad dir.
7. Report new totals (INR) and span in one or two lines.

## Notes
- Parse cache: `~/.cache/token-tracker/parse-v2`; `./tokentrack.py clear-cache` if numbers look stale.
- Show money in INR (₹).
