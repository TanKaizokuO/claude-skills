---
name: update-token-ledger-classic
description: Refresh the "Token Ledger" classic artifact (https://claude.ai/artifact/8NtpSyfFhHjrT1qtpCwRQW), built by tokentrack.py from the token-tracker repo's main branch, then open it. Use when the user says "update the classic token ledger", "refresh token ledger classic", or "update the old token ledger". Not for the React Token Ledger (token-ledger-update).
---

# Update Token Ledger Classic

The page is one self-contained HTML file that `tokentrack.py dashboard` renders from `dashboard_template.html` on token-tracker `main`, with fresh Claude Code and omp logs baked in. Prices come from main's `pricing.json` with `pricing-overrides.json` (in this skill) merged on top.

- `URL=https://claude.ai/artifact/8NtpSyfFhHjrT1qtpCwRQW`
- `W=<session scratchpad>/token-ledger-classic`

Rules:
- Never switch branches or edit files in `~/Code/projects/token-tracker`. The build works on a `git archive` export.
- Money is INR (₹), rate from `currency.per_usd` in pricing.json.

## Steps

1. **Build.**
   ```
   ~/.claude/skills/update-token-ledger-classic/scripts/build.sh $W
   ```
   It hides the "What changed" and "Change tracking" cards (owner removed them; do not restore). It exports `origin/main` (falls back to local `main`), merges the overrides, writes `$W/out/token-ledger-classic.html`, and prints unpriced requests, the date span and the INR total. It takes about a minute.

2. **Check prices.** If `unpriced requests` is not 0, find the models (`python3 -I tokentrack.py json all --pricing $W/pricing.merged.json` in `$W/src`, look under `coverage`) and ask the user for their rates. Add them to `pricing-overrides.json` in the same shape (in, out, cw5m, cw1h, cr per M tokens in USD, plus `verified_on` and a `note` with the source). Rebuild. Drop an override once main's pricing.json has the model.

3. **Publish to the same url.** Do Artifact `action: read` on `$URL` first if this session has not published it, then publish `file_path=$W/out/token-ledger-classic.html`, `url=$URL`. No `icon`, no `capabilities`. The page has optional `db` label-sync code; the owner chose to leave `db` undeclared, so ignore that warning.

4. **Open it.** Right after the publish succeeds, open the artifact in the browser: Artifact `action: open`, `url=$URL`. If that does not launch a browser, run `xdg-open $URL`.

5. **Report** in one or two lines: INR total, date span, unpriced count.
