#!/usr/bin/env bash
# Build the classic Token Ledger page from token-tracker main.
# Usage: build.sh <work dir>   -> writes <work dir>/out/token-ledger-classic.html
set -euo pipefail
W=${1:?usage: build.sh <work dir>}
REPO=/home/tankaizokuo/Code/projects/token-tracker
SKILL=$(cd "$(dirname "$0")/.." && pwd)
rm -rf "$W/src" && mkdir -p "$W/src" "$W/out"
git -C "$REPO" fetch -q origin main || echo "warn: fetch failed, using local main"
REF=$(git -C "$REPO" rev-parse -q --verify origin/main || git -C "$REPO" rev-parse main)
git -C "$REPO" archive "$REF" | tar -x -C "$W/src"
python3 -I - "$W/src/pricing.json" "$SKILL/pricing-overrides.json" "$W/pricing.merged.json" <<'PY'
import json, sys
base, over, out = sys.argv[1:4]
b = json.load(open(base)); o = json.load(open(over))
for k, v in o.get("models", {}).items():
    print(("override " if k in b["models"] else "add ") + k)
    b["models"][k] = v
json.dump(b, open(out, "w"), indent=2, ensure_ascii=False)
PY
cd "$W/src"
python3 -I tokentrack.py dashboard all --no-open --pricing "$W/pricing.merged.json" --html "$W/out/token-ledger-classic.html"
# Owner removed the "What changed" and "Change tracking" cards. Keep the nodes (the page JS still
# writes into them) but hide them. Fails loudly if main's template stops matching.
python3 -I - "$W/out/token-ledger-classic.html" <<'PY'
import sys
p = sys.argv[1]; h = open(p, encoding="utf-8").read()
for card in ('id="compare-card"', 'id="events-card"'):
    old = '<div class="card" ' + card + '>'
    if h.count(old) != 1:
        sys.exit("card strip failed: " + card + " not found once; template changed")
    h = h.replace(old, '<div class="card" hidden ' + card + '>')
open(p, "w", encoding="utf-8").write(h)
print("hid cards: compare-card, events-card")
PY
# 1d shows the rolling last 24 hours as hourly bars in the Activity chart (owner request).
python3 -I "$SKILL/scripts/patch-hourly.py" "$W/out/token-ledger-classic.html"
# Models tables default to Tokens, descending (owner request); caption matches.
python3 -I - "$W/out/token-ledger-classic.html" <<'PY'
import sys
p = sys.argv[1]; h = open(p, encoding="utf-8").read()
for old, new in (("let modelsSortBy = 'cost', modelsSortDesc = true", "let modelsSortBy = 'tok', modelsSortDesc = true"),
                 ('<div class="card-description">Models ranked by cost</div>', '<div class="card-description">Models ranked by tokens</div>')):
    if h.count(old) != 1:
        sys.exit("models sort patch failed: " + old[:40] + " not found once; template changed")
    h = h.replace(old, new)
open(p, "w", encoding="utf-8").write(h)
print("patched: models default sort = tokens desc")
PY
python3 -I tokentrack.py json all --pricing "$W/pricing.merged.json" 2>/dev/null \
  | python3 -I -c 'import json,sys; print("unpriced requests:", json.load(sys.stdin)["coverage"]["unpriced"]["requests"])'
python3 -I tokentrack.py all --pricing "$W/pricing.merged.json" 2>/dev/null | sed -n '2p;8p' | sed 's/\x1b\[[0-9;]*m//g'
echo "source commit: $REF"
