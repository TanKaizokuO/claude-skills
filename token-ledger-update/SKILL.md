---
name: token-ledger-update
description: Refresh the data in the "Token Ledger" Claude artifact (https://claude.ai/artifact/Y1iiTF4oWh5ANAqhfZR3gY) from omp and Claude Code usage. Use when the user says "update the token ledger", "refresh Token Ledger", "update the data of the artifact", or "republish the token dashboard".
---

# Token Ledger update

The artifact is one offline React build of `~/Code/projects/token-tracker/web/src` plus a captured API snapshot of the local Token Ledger server. The page (`index.html`) inlines the bundle, the GET snapshot and a manifest. POST query data ships beside it as `data/<range>-<n>.txt` files (base64 of gzip; artifacts do not serve `.gz`), one set per range: 24h, 7d, 30d, all, and the `_prev` comparison windows. Updating means: copy the verified DB, reprice and backfill the copy, capture the API from a server on that copy, build the page and data files, test them over http, and publish to the same url.

Paths used below:
- `REPO=/home/tankaizokuo/Code/projects/token-tracker`
- `SKILL=/home/tankaizokuo/.claude/skills/token-ledger-update`
- `VERIFIED=/home/tankaizokuo/.local/share/token-ledger/rollout-<date>/verified/token-ledger.sqlite3` (use the newest rollout date)
- `W=<session scratchpad>/token-ledger-build` (all temp files live here)
- `URL=https://claude.ai/artifact/Y1iiTF4oWh5ANAqhfZR3gY`

Rules:
- Never write the verified DB. Work only on the copy at `$W/token-ledger.sqlite3`.
- Never print, log or store the bootstrap CSRF token or the session cookie. The capture replaces the token with `offline`.
- Long steps run in the background with a log and a done flag. Check each flag once. Do not sleep-poll.
- Money is shown in INR (₹). The rate is `currency.per_usd` in `$REPO/pricing.json`. Nothing hardcodes it.

## Steps

1. **Bundle the offline web build.**
   ```
   mkdir -p $W && cd $W
   rm -rf src && cp -r $REPO/web/src ./src
   cp $REPO/web/index.html $REPO/web/package.json $REPO/web/tsconfig.json .
   cp $SKILL/scripts/vite.offline.config.ts .
   ln -sfn $REPO/web/node_modules node_modules   # run `npm ci` in $REPO/web first if missing
   npx tsc --noEmit -p tsconfig.json
   npx vite build --config vite.offline.config.ts   # writes $W/dist-offline
   ```

2. **Populate a copy of the verified DB and reprice it.** The source is opened read-only with the sqlite backup API.
   ```
   python3 $SKILL/scripts/populate.py --src $VERIFIED --db $W/token-ledger.sqlite3 --pricing $REPO/pricing.json
   ```
   The script refuses any path under `/verified/`. It prints the FX rate it read, the priced and unpriced row counts, and the total in USD and INR.

3. **Migrate the copy, then run the backfill CLIs on it.** Do this before any CLI, because some CLI paths open with `run_migrations=False`.
   ```
   export PYTHONPATH=$REPO/src
   python3 -c "import sys; from token_ledger.store.database import open_database; open_database(sys.argv[1], run_migrations=True).close()" $W/token-ledger.sqlite3
   python3 -m token_ledger backfill-session-ids --db $W/token-ledger.sqlite3
   python3 -m token_ledger backfill-omp-project-ids --db $W/token-ledger.sqlite3
   python3 -m token_ledger backfill-project-names --db $W/token-ledger.sqlite3
   python3 -m token_ledger recompute-overlap-flags --db $W/token-ledger.sqlite3
   ```
   Run the CLIs in the background with a log. All are idempotent. Run `recompute-overlap-flags` last. `backfill-omp-project-ids` attributes omp requests to projects; without it every omp request shows as Unattributed. `backfill-project-names` sets `project_name` to the folder basename and folds `.claude/worktrees/<name>` projects into their parent repo. It refuses any `/verified/` path, so run it only on the working copy.

   Steps 2 to 5 can run as one background script with a log and a done flag. The v95 run used `pipeline.sh` in that shape (populate, migrate, backfills, anchor, serve plus capture, build).

4. **Capture the API snapshot from a local server on the copy.**
   - Keys: `$SKILL/keys.json` holds the request keys of the last build (`{"post": [...], "get": [...]}`). Pages built since v95 carry no POST keys, so do not take keys from the live page.
   - Anchor: the windows end at the newest request in the copy, not at the current time. Read it read-only:
     ```
     ANCHOR=$(python3 -I -c 'import sqlite3,sys; from datetime import datetime,timezone; c=sqlite3.connect("file:%s?mode=ro"%sys.argv[1],uri=True); print(max(datetime.fromisoformat(r[0]).astimezone(timezone.utc) for r in c.execute("select request_timestamp from canonical_requests")).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ"))' $W/token-ledger.sqlite3)
     ```
   - Start the server (background, with log):
     ```
     cd $REPO && PYTHONPATH=$REPO/src python3 -m token_ledger serve --db $W/token-ledger.sqlite3 --port 18790 > $W/server.log 2>&1 &
     ```
   - Capture (background, with log). It writes `$W/capture.json` (about 4.2 GB, about 13 minutes) and the flag `$W/capture.json.done`. It captures every POST key for each range and for each harness scope (combined, claude-code, omp):
     ```
     python3 $SKILL/scripts/capture.py --keys-from $SKILL/keys.json --out $W/capture.json --port 18790 --now $ANCHOR > $W/capture.log 2>&1 &
     ```
   - When the done flag reads `exit 0`, stop the server (`kill` its pid). Check `capture.log` for `non200 0`.

5. **Build the page and data files.**
   ```
   python3 $SKILL/scripts/build.py --capture $W/capture.json --dist $W/dist-offline --out $W/out --pricing $REPO/pricing.json
   ```
   It writes `$W/out/index.html`, `$W/out/data/*.txt` and `$W/out/keys.json`. Long lists are trimmed to N=2000 (falling back to 1500, 1000, 500). N=2000 is normal. Limits: page 15 MB, each data file 12 MB, data total 200 MB. Check the last `data total ...` line says `fits True`. Then copy `$W/out/keys.json` to `$SKILL/keys.json` for the next run.

6. **Run the page tests over http (background, with log and flag).** The page fetches `data/*.txt` with relative URLs, which fail from `file://`, so serve `$W/out` first:
   ```
   (cd $W/out && python3 -m http.server 18796 --bind 127.0.0.1 > $W/tests/http.log 2>&1) &
   PAGE_URL=http://127.0.0.1:18796/index.html $SKILL/scripts/run_tests.sh $W/out/index.html $W/tests
   cd $SKILL/scripts && SHOT_DIR=$W/tests PAGE=$W/out/index.html python3 test_ranges.py > $W/tests/ranges.log 2>&1
   ```
   Wrap these in one background script that writes a done flag, then kill the http server. The tests need Python with Playwright and Chromium. Set `PYTHON=<that python>` if `python3` lacks them. Pass means: 0 page errors, 0 external network requests (the only snapshot miss allowed is `GET /api/v1/health`), `RESULT: ALL PASS` from `test_downloads` and `test_speed_scopes` (Combined, Claude and OMP), and `RESULT: PASS` from `test_ranges`. `test_artifact` and `money2` print values for review.

7. **Publish to the same url.** First do Artifact `action: read` on `$URL` (a publish to an artifact not read in this session is refused). Then publish:
   - `file_path=$W/out/index.html`, `url=$URL`, `root=$W/out`, and `files` mapping each `data/<name>.txt` to itself. `.txt` is served as text, so no `contentType` is needed.
   - `$W` must be under the session scratchpad or the working directory; the publish refuses other roots.
   - One publish sends at most 64 MB. The data is about 76 MB, so send the page plus the first data files in one call, then the rest in a second call to the same `url` (files left out are kept).
   - Pass no `capabilities` (the stored `downloads` and `db` capabilities carry forward). Do not pass `icon`.
   - After the last publish, open the artifact and check that each range (24h, 7d, 30d, All) loads.

8. **Clean up the large files.** Delete `$W/capture.json` (about 4.2 GB) and `$W/token-ledger.sqlite3`. Keep the page and the test output if the user wants them.

9. **Report** the new INR total and the span in one or two lines. Do not print the llm-cost-audit report.

## Notes
- Costs come from `pricing.json`, never from omp's own cost columns.
- If the numbers look stale when working from the live app, clear the token-tracker parse cache: `~/.cache/token-tracker/parse-v2`.
