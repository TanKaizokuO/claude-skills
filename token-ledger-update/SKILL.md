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
   - Timezone: days are cut in `DATA.timezone` (Asia/Kolkata since 2026-10-15; absent = legacy UTC). If the artifact's zone differs from the payload's, the script aborts; rerun with a 4th arg, `./tokentrack.py json --tz <artifact zone> > $SCRATCH/data_old_tz.json`. It then adds back only the missing part of each pruned day. Never merge mismatched zones any other way: comparing day buckets across zones "restores" dozens of days and double-counts (≈ +$585 seen on 2026-10-15).
   - Sanity-check the printed line: `span[1]` is today, `messages` ≥ the old artifact's count, both sources present.
   - UI changes in `dashboard_template.html` don't reach the artifact through this step (it keeps the old page's UI). To ship them: `./tokentrack.py dashboard all --html $SCRATCH/new.html --no-open`, then put the merged `DATA` JSON from step 5 in place of `new.html`'s `const DATA = …` value, and publish that.
   - The Audit tab is static HTML outside `DATA`; this skill carries it over unchanged. Only `llm-cost-audit` rewrites it. When invoked with args `audit-tab` (from `llm-cost-audit`), run its `render_audit_tab.py` on the merged file now, as that skill's step 6 says, before republishing.
6. **Republish** with Artifact `file_path=<out>`, `url=https://claude.ai/artifact/Y1iiTF4oWh5ANAqhfZR3gY`. Same url, no `icon`, no `description` changes, and no `capabilities` (leaving it out keeps the stored `db` declaration; review labels live in its `reviews` collection, one doc per session id). Put the temp files in the scratchpad dir.
7. Report new totals (INR) and span in one or two lines. Do not print the llm-cost-audit report.

## Notes
- Parse cache: `~/.cache/token-tracker/parse-v2`; `./tokentrack.py clear-cache` if numbers look stale.
- Show money in INR (₹).
