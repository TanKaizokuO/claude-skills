#!/usr/bin/env python3
"""Tests for build.py's multi-file output. Plain python, no pytest needed.

Run: python3 -I test_build_files.py
Builds a tiny synthetic capture into a new temp dir (never the real pipeline), runs build.py via
subprocess, and checks files, manifest, keys.json, the part split and that the page has no POST data.
If node is on PATH, it also runs the shim's rangeLabel() extracted from the built page.
"""
import base64
import gzip
import json
import os
import random
import re
import shutil
import string
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build.py")
LABELS = ["all", "30d", "30d_prev", "7d", "7d_prev", "24h", "24h_prev"]
PART_LIMIT = 50_000
QP = "POST /api/v1/query "


def canon_key(body):
    return QP + json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def padded(marker, seed, n=45_000):
    # Random letters gzip to about 0.73 of their size, so one key is ~33 KB gzipped.
    rnd = random.Random(seed)
    pad = "".join(rnd.choice(string.ascii_letters) for _ in range(n))
    return json.dumps({"marker": marker, "pad": pad})


def make_capture(path):
    post_a = {"metric_id": "summary", "q": "a"}
    post_b = {"metric_id": "summary", "q": "b"}
    ka, kb = canon_key(post_a), canon_key(post_b)
    g1, g2 = "GET /api/v1/ping", "GET /api/v1/models?x=1"
    spans = {
        "all": (None, None),
        "30d": ("2026-09-30", "2026-10-30"), "30d_prev": ("2026-08-31", "2026-09-30"),
        "7d": ("2026-10-23", "2026-10-30"), "7d_prev": ("2026-10-16", "2026-10-23"),
        "24h": ("2026-10-29", "2026-10-30"), "24h_prev": ("2026-10-28", "2026-10-29"),
    }
    recs = []
    for label, (s, e) in spans.items():
        recs.append({"key": ka, "s": s, "e": e, "w": label, "t": padded("MARK_A_" + label, 1)})
        recs.append({"key": kb, "s": s, "e": e, "w": label, "t": padded("MARK_B_" + label, 2)})
    # Old-capture record: no "w" (means 30d), other start. Same key as B, so B becomes a 2-item list.
    recs.append({"key": kb, "s": "2026-08-01", "e": "2026-08-31", "t": json.dumps({"old": True})})
    recs.append({"key": g1, "s": None, "e": None, "w": None, "t": json.dumps({"ok": 1})})
    recs.append({"key": g2, "s": None, "e": None, "w": None, "t": json.dumps({"models": ["x"]})})
    with open(path, "w", encoding="utf-8") as f:
        json.dump(recs, f)
    return ka, kb, g1, g2


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def gunzip_json(blob):
    return json.loads(gzip.decompress(base64.b64decode(blob)).decode("utf-8"))


def page_get_map(page):
    m = re.search(r'var GET_B64 = "([^"]*)";', page)
    check(m is not None, "GET_B64 not found in page")
    return gunzip_json(m.group(1))


def check_label_fn(page, tmp):
    node = shutil.which("node")
    if not node:
        print("skip: node not on PATH, rangeLabel check not run")
        return
    m = re.search(r"\n  function rangeLabel\(body\) \{.*?\n  \}\n", page, re.S)
    check(m is not None, "rangeLabel not found in page")
    js = m.group(0) + r"""
const DAY = 86400000, now = Date.now();
const iso = (ms) => new Date(ms).toISOString();
const cases = [
  [undefined, "all"],
  [{}, "all"],
  [{time_range: {start: null, end: null}}, "all"],
  [{time_range: {start: iso(now - DAY), end: iso(now)}}, "24h"],
  [{time_range: {start: iso(now - 5 * DAY), end: iso(now)}}, "7d"],
  [{time_range: {start: iso(now - 20 * DAY), end: iso(now)}}, "30d"],
  [{time_range: {start: iso(now - 6 * DAY), end: iso(now - 5 * DAY)}}, "24h_prev"],
  [{time_range: {start: iso(now - 13 * DAY), end: iso(now - 8 * DAY)}}, "7d_prev"],
  [{time_range: {start: iso(now - 45 * DAY), end: iso(now - 25 * DAY)}}, "30d_prev"],
  [{time_range: {start: iso(now - 7 * DAY), end: iso(now - DAY)}}, "7d"],
];
let bad = 0;
for (const [body, want] of cases) {
  const got = rangeLabel(body);
  if (got !== want) { bad++; console.log("MISMATCH", JSON.stringify(body), got, "want", want); }
}
process.exit(bad ? 1 : 0);
"""
    path = os.path.join(tmp, "label_check.js")
    with open(path, "w", encoding="utf-8") as f:
        f.write(js)
    r = subprocess.run([node, path], capture_output=True, text=True)
    check(r.returncode == 0, "rangeLabel mismatches:\n" + r.stdout + r.stderr)
    print("ok: rangeLabel matches the expected label for 10 cases (node)")


def main():
    tmp = tempfile.mkdtemp(prefix="token-ledger-build-test-")
    dist = os.path.join(tmp, "dist")
    os.makedirs(os.path.join(dist, "assets"))
    with open(os.path.join(dist, "index.html"), "w", encoding="utf-8") as f:
        f.write('<!doctype html><html><head><link rel="stylesheet" href="./assets/x.css">'
                '</head><body><script type="module" src="./assets/x.js"></script></body></html>')
    with open(os.path.join(dist, "assets", "x.css"), "w", encoding="utf-8") as f:
        f.write("body{margin:0}\n")
    with open(os.path.join(dist, "assets", "x.js"), "w", encoding="utf-8") as f:
        f.write("window.__APP_RAN__ = true;\n")
    pricing = os.path.join(tmp, "pricing.json")
    with open(pricing, "w", encoding="utf-8") as f:
        json.dump({"currency": {"code": "INR", "per_usd": 95.56}}, f)
    capture = os.path.join(tmp, "capture.json")
    ka, kb, g1, g2 = make_capture(capture)
    out = os.path.join(tmp, "out")

    r = subprocess.run([sys.executable, "-I", BUILD, "--capture", capture, "--dist", dist,
                        "--out", out, "--pricing", pricing, "--part-limit", str(PART_LIMIT)],
                       capture_output=True, text=True)
    check(r.returncode == 0, "build.py failed:\n" + r.stdout + r.stderr)
    print(r.stdout.strip().splitlines()[-1])

    # Files: index.html, keys.json, two parts per label (each key is ~33 KB gzipped).
    index_path = os.path.join(out, "index.html")
    check(os.path.isfile(index_path), "index.html missing")
    check(os.path.isfile(os.path.join(out, "keys.json")), "keys.json missing")
    expected = sorted(f"data/{lab}-{i}.txt" for lab in LABELS for i in (0, 1))
    got_files = sorted(os.path.relpath(os.path.join(d, n), out)
                       for d, _, names in os.walk(os.path.join(out, "data")) for n in names)
    check(got_files == expected, f"data files {got_files} != {expected}")

    page = open(index_path, encoding="utf-8").read()
    page_bytes = os.path.getsize(index_path)
    check(page_bytes <= 15_000_000, "page over 15 MB")
    print(f"page bytes {page_bytes:,}")

    # Manifest inlined in the page.
    m = re.search(r"var MANIFEST = (\{.*?\});", page)
    check(m is not None, "MANIFEST not found in page")
    manifest = json.loads(m.group(1))
    check(sorted(manifest["windows"]) == sorted(LABELS), "manifest labels " + str(manifest["windows"].keys()))
    check(manifest["windows"]["30d"] == ["data/30d-0.txt", "data/30d-1.txt"], "30d parts")
    check("captured" in manifest and manifest["captured"], "manifest captured")
    check(manifest["anchor"] == "2026-10-30", "anchor " + str(manifest["anchor"]))

    # Parts: base64 of gzip, each <= part limit, POST keys complete across parts, shapes right.
    for lab in LABELS:
        seen = {}
        for rel in manifest["windows"][lab]:
            blob = open(os.path.join(out, rel), "rb").read()
            check(base64.b64decode(blob)[:2] == b"\x1f\x8b", rel + " is not base64 gzip")
            check(len(blob) <= PART_LIMIT, f"{rel} is {len(blob)} bytes, over {PART_LIMIT}")
            part = gunzip_json(blob)
            check(not (set(part) & set(seen)), "key repeated across parts in " + lab)
            seen.update(part)
        check(set(seen) == {ka, kb}, f"{lab} keys {set(seen)}")
        for v in seen.values():
            for entry in (v if isinstance(v, list) else [v]):
                check(set(entry) == {"s", "e", "t"}, "entry shape " + lab)
        check(isinstance(seen[kb], list) == (lab == "30d"), f"{lab}: old-capture variants only in 30d")
        first = seen[kb][0] if isinstance(seen[kb], list) else seen[kb]
        check(("MARK_B_" + lab) in first["t"], f"{lab}: wrong payload for key B")

    # Page holds no POST data; GET snapshot inline holds exactly the GET keys.
    for lab in LABELS:
        check(("MARK_A_" + lab) not in page and ("MARK_B_" + lab) not in page, "POST marker in page: " + lab)
    check(sorted(page_get_map(page)) == sorted([g1, g2]), "GET map keys wrong")

    # keys.json for the next capture.
    with open(os.path.join(out, "keys.json"), encoding="utf-8") as f:
        keys = json.load(f)
    check(keys == {"post": sorted([ka, kb]), "get": sorted([g1, g2])}, f"keys.json {keys}")

    # Shim bits: ranges declared before the app, footer text.
    check('window.__TL_OFFLINE_RANGES__ = ["24h", "7d", "30d", "all"];' in page, "ranges not declared")
    check("Ranges available: Last 24 Hours, Last 7 Days, Last 30 Days, All History" in page, "footer text")
    check(page.count("</script>") == 2, "unexpected </script> count (adapter or app script not escaped)")

    check_label_fn(page, tmp)

    h = subprocess.run([sys.executable, "-I", BUILD, "--help"], capture_output=True, text=True)
    check(h.returncode == 0 and "--part-limit" in h.stdout, "--help failed")
    print("PASS test_build_files")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
