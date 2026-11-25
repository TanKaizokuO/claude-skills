#!/usr/bin/env python3
"""Replay the dashboard's API snapshot keys against a running local Token Ledger server.

Usage (server must already be running on 127.0.0.1:PORT, see SKILL.md step 4):
  capture.py --keys-from <keys.json | artifact-page.html> --out <capture.json> [--port 18790] [--now ISO]

- --keys-from: either
    * a keys.json = {"post": [key, ...], "get": [key, ...]} (written by build.py), or
    * an HTML page that carries the dashboard snapshot (SNAP_B64). Use the saved file
      from an Artifact `read` of the live artifact, or a previous build.
  Only its request keys are used; its data is not reused.
- POST keys are replayed once per labelled window: all, 30d, 30d_prev, 7d, 7d_prev,
  24h, 24h_prev. The windows are generated from one anchor time (UTC now, or --now ISO
  for tests) and mirror web/src/App.tsx computeTimeRange and web/src/pages/Overview.tsx
  computePriorTimeRange.
- Every POST key is also replayed for each harness_scope the app can send: combined,
  claude-code, omp (App.tsx HarnessScope toggle; Harness.tsx loads all three). The speed
  key also gets its hour, week and month groupings for each scope.
  include_archive is not expanded: the app sends true for every query (App.tsx default, no
  UI control sets false), so the key keeps whatever value the snapshot key has.
- comparisons keys carry their dates in comparison_periods, so their stored key has the dates
  removed (DATE_PATHS). They are replayed for 30d, 7d and 24h only, with period_a/period_b
  computed from each window the way Harness.tsx does.
- GET keys are replayed once, with no window (s = e = w = null).
- Each record is {"key", "s", "e", "w", "t"}.
- Writes <capture.json> and a done-flag <capture.json>.done containing "exit 0" or "exit 1".
- The bootstrap CSRF token is replaced with "offline" in every stored response.
  The session cookie and real token are kept in memory only and never written.
"""
import argparse
import gzip
import base64
import json
import re
import sys
import traceback
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

PFX = "POST /api/v1/query "
GET_PFX = "GET "
FX_KEY = "GET /api/v1/pricing/fx"
REPLACEMENT_CSRF = "offline"
WINDOW_LABELS = ("all", "30d", "30d_prev", "7d", "7d_prev", "24h", "24h_prev")
SPEED_GROUPS = ("hour", "week", "month")
DAY = timedelta(days=1)
COMPARISON_METRIC = "comparisons"
# Request-body paths that hold dates. The stored key drops them; the window label is taken from
# period_b (same rule as time_range). Mirror of DATE_PATHS in build.py's ADAPTER shim.
DATE_PATHS = (
    ("comparison_periods", "period_a", "start"),
    ("comparison_periods", "period_a", "end"),
    ("comparison_periods", "period_b", "start"),
    ("comparison_periods", "period_b", "end"),
)
# Harness.tsx and Efficiency.tsx send comparisons for the current range only, never a _prev one.
COMPARISON_LABELS = ("30d", "7d", "24h")
# Harness scopes the app sends (App.tsx harness toggle; Harness.tsx and Overview.tsx request all three).
HARNESS_SCOPES = ("combined", "claude-code", "omp")


class Client:
    def __init__(self, origin):
        self.origin = origin
        self.base = origin
        self.cookie = None
        self.csrf = None

    def req(self, method, path, body=None, csrf=None):
        headers = {"Origin": self.origin}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if csrf:
            headers["X-CSRF-Token"] = csrf
        if self.cookie:
            headers["Cookie"] = self.cookie
        r = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(r, timeout=900) as resp:
                return resp.status, resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")

    def bootstrap(self):
        r = urllib.request.Request(self.base + "/api/v1/bootstrap", method="GET", headers={"Origin": self.origin})
        with urllib.request.urlopen(r, timeout=900) as resp:
            status = resp.status
            set_cookie = resp.headers.get("Set-Cookie") or ""
            text = resp.read().decode("utf-8")
        if status != 200:
            raise RuntimeError("bootstrap status %s" % status)
        self.cookie = set_cookie.split(";")[0].strip()
        if not self.cookie.startswith("tl_session="):
            raise RuntimeError("no session cookie in bootstrap")
        self.csrf = find_csrf(json.loads(text))
        if not self.csrf:
            raise RuntimeError("no csrf token in bootstrap")


def find_csrf(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if "csrf" in k.lower() and isinstance(v, str) and v:
                return v
            r = find_csrf(v)
            if r:
                return r
    elif isinstance(o, list):
        for x in o:
            r = find_csrf(x)
            if r:
                return r
    return None


def parse_now(text):
    """--now ISO (Z or offset) as a whole-second UTC datetime; None means the current time."""
    if text is None:
        return datetime.now(timezone.utc).replace(microsecond=0)
    d = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    if d.tzinfo is None:
        raise ValueError("--now needs a timezone, e.g. 2026-10-30T02:51:00Z")
    return d.astimezone(timezone.utc).replace(microsecond=0)


def _date_str(d):
    return d.strftime("%Y-%m-%d")


def _iso(d):
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def _midnight(d):
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def _prior(start, end):
    """Overview.tsx computePriorTimeRange: [start - duration, start)."""
    return _iso(start - (end - start)), _iso(start)


def compute_windows(now):
    """Return [(label, start, end)] for one anchor. start/end are None for "all".

    - 30d and 7d mirror App.tsx:297-304: date-only strings, start = today minus N days,
      end = tomorrow (exclusive), in UTC here.
    - 24h is a rolling window ending at now, as full ISO datetimes.
    - Each *_prev is Overview.tsx computePriorTimeRange: the window of equal length that
      ends where the main window starts. Its bounds are full ISO datetimes.
    """
    now = now.astimezone(timezone.utc).replace(microsecond=0)
    out = [("all", None, None)]
    for label, days in (("30d", 30), ("7d", 7)):
        start_day = now - days * DAY
        end_day = now + DAY
        out.append((label, _date_str(start_day), _date_str(end_day)))
        out.append((label + "_prev",) + _prior(_midnight(start_day), _midnight(end_day)))
    start_dt = now - timedelta(hours=24)
    out.append(("24h", _iso(start_dt), _iso(now)))
    out.append(("24h_prev",) + _prior(start_dt, now))
    return out


def time_range_for(s, e):
    tr = {"timezone": "UTC"}
    if s is not None:
        tr["start"] = s
    if e is not None:
        tr["end"] = e
    return tr


def ser_key(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def is_comparison(body):
    return isinstance(body, dict) and body.get("metric_id") == COMPARISON_METRIC


def strip_dates(body):
    """Copy of a request body without the DATE_PATHS leaves."""
    out = json.loads(json.dumps(body))
    for path in DATE_PATHS:
        parent = out
        for p in path[:-1]:
            parent = parent.get(p) if isinstance(parent, dict) else None
        if isinstance(parent, dict):
            parent.pop(path[-1], None)
    return out


def _parse_bound(text):
    if len(text) == 10:
        return datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _ms_iso(d):
    return d.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def comparison_periods_for(s, e):
    """Harness.tsx layout for the range [s, e): period_a is the equal span before it, period_b is
    the range. The app reads [s, e) from the server echo and sends toISOString() values."""
    start, end = _parse_bound(s), _parse_bound(e)
    dur = end - start
    return {
        "period_a": {"start": _ms_iso(start - dur), "end": _ms_iso(start), "timezone": "UTC"},
        "period_b": {"start": _ms_iso(start), "end": _ms_iso(end), "timezone": "UTC"},
    }


def load_snapshot_keys(path):
    html = open(path, encoding="utf-8").read()
    m = re.search(r'SNAP_B64\s*=\s*"([A-Za-z0-9+/=]+)"', html)
    if not m:
        raise RuntimeError("no SNAP_B64 in %s" % path)
    return json.loads(gzip.decompress(base64.b64decode(m.group(1))).decode("utf-8"))


def load_keys(path):
    """Return (post_keys, get_keys) from keys.json or from an HTML snapshot page."""
    if path.lower().endswith(".json"):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        post = list(dict.fromkeys(data.get("post") or []))
        get = list(dict.fromkeys(data.get("get") or []))
        for k in post:
            if not k.startswith(PFX):
                raise RuntimeError("keys.json post entry is not a POST query key: %s" % k[:80])
        for k in get:
            if not k.startswith(GET_PFX):
                raise RuntimeError("keys.json get entry is not a GET key: %s" % k[:80])
        return post, get

    db = load_snapshot_keys(path)
    post, get = [], []
    for key, variants in db.items():
        if key.startswith(PFX):
            # Only POST keys whose old variants carried a window get windows.
            if any(v.get("s") and v.get("e") for v in variants):
                post.append(key)
            else:
                print("SKIP POST key with no window in snapshot: %s" % key[:80], flush=True)
        elif key.startswith(GET_PFX):
            get.append(key)
        else:
            raise RuntimeError("unknown key kind in snapshot: %s" % key[:80])
    return post, get


def expand_harness_scopes(post_keys):
    """Each POST key once per harness_scope in HARNESS_SCOPES, in input order, deduplicated.

    The stored form is ser_key(body) (sorted keys, compact), the same canonical form that the
    build.py shim (keyOf: time_range removed, canon()) looks up. include_archive is left as the
    key has it: the app sends true for every query.
    """
    out = []
    for key in post_keys:
        if not key.startswith(PFX):
            out.append(key)
            continue
        body = json.loads(key[len(PFX):])
        for scope in HARNESS_SCOPES:
            b2 = dict(body)
            b2["harness_scope"] = scope
            out.append(PFX + ser_key(b2))
    return list(dict.fromkeys(out))


def is_speed_day(key):
    if not key.startswith(PFX):
        return False
    b = json.loads(key[len(PFX):])
    return b.get("metric_id") == "speed" and b.get("group_by") == ["day"]


def build_work(post_keys, get_keys, now):
    """Plan the capture: one record per (key, window), without the response text.

    Each record is {"key", "s", "e", "w"}. POST records carry a window label. GET records
    have s = e = w = None. Every POST key is expanded to each harness scope first. The speed/day
    key of each scope also gets its hour, week and month groupings, each with every window.
    """
    windows = compute_windows(now)
    work, seen = [], set()

    def add(key, s, e, w):
        if (key, w) in seen:
            return
        seen.add((key, w))
        work.append({"key": key, "s": s, "e": e, "w": w})

    post_keys = expand_harness_scopes(post_keys)
    for key in post_keys:
        body = json.loads(key[len(PFX):]) if key.startswith(PFX) else None
        if is_comparison(body):
            # The dates sit in the body: store the key without them, one record per current window.
            tkey = PFX + ser_key(strip_dates(body))
            for w, s, e in windows:
                if w in COMPARISON_LABELS:
                    add(tkey, s, e, w)
            continue
        for w, s, e in windows:
            add(key, s, e, w)
    for key in get_keys:
        add(key, None, None, None)

    # The speed view also asks for hour, week and month groupings, in every harness scope.
    day_keys = [k for k in post_keys if is_speed_day(k)]
    if len(day_keys) != len(HARNESS_SCOPES):
        raise RuntimeError("expected one speed/day key per scope (%d), found %d"
                           % (len(HARNESS_SCOPES), len(day_keys)))
    for dk in day_keys:
        base_body = json.loads(dk[len(PFX):])
        for g in SPEED_GROUPS:
            b2 = dict(base_body)
            b2["group_by"] = [g]
            nk = PFX + ser_key(b2)
            for w, s, e in windows:
                add(nk, s, e, w)

    if not any(r["key"] == FX_KEY for r in work):
        add(FX_KEY, None, None, None)
    return work


def summarise(out):
    stats = {}
    for r in out:
        label = r["w"] or "get"
        c = stats.setdefault(label, [0, 0])
        c[0] += 1
        c[1] += len(r["t"].encode("utf-8"))
    for label in list(WINDOW_LABELS) + ["get"]:
        if label in stats:
            n, b = stats[label]
            print("window %-8s records %4d bytes %d" % (label, n, b), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--keys-from", required=True,
                    help="keys.json, or an HTML page carrying SNAP_B64 (keys only)")
    ap.add_argument("--out", required=True, help="capture JSON to write")
    ap.add_argument("--port", type=int, default=18790)
    ap.add_argument("--now", default=None,
                    help="window anchor as ISO UTC, e.g. 2026-10-30T02:51:00Z (default: current time; for tests)")
    args = ap.parse_args()

    now = parse_now(args.now)
    origin = "http://127.0.0.1:%d" % args.port
    client = Client(origin)
    post, get = load_keys(args.keys_from)
    client.bootstrap()
    work = build_work(post, get, now)

    out, bad = [], []
    for i, r in enumerate(work):
        key, s, e, w = r["key"], r["s"], r["e"], r["w"]
        if key.startswith(PFX):
            if w is None:
                raise RuntimeError("POST key without a window label: %s" % key[:80])
            b = json.loads(key[len(PFX):])
            if "time_range" in b:
                raise RuntimeError("snapshot key already has time_range")
            b["time_range"] = time_range_for(s, e)
            if is_comparison(b):
                b["comparison_periods"] = comparison_periods_for(s, e)
            st, t = client.req("POST", "/api/v1/query", b, client.csrf)
        else:
            if not (s is None and e is None and w is None):
                raise RuntimeError("unexpected window on GET key %s" % key)
            st, t = client.req("GET", key[len(GET_PFX):], None, None)
        if st == 200:
            # Never store the live CSRF token.
            t = t.replace(client.csrf, REPLACEMENT_CSRF)
        if st != 200:
            bad.append({"i": i, "key": key[:120], "w": w, "s": s, "e": e, "status": st})
        out.append({"key": key, "s": s, "e": e, "w": w, "t": t})
        print("done", i + 1, "/", len(work), "window", w, "status", st, "len", len(t), flush=True)

    summarise(out)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print("records", len(out), "non200", len(bad), flush=True)
    for b in bad:
        print("NON200", b, flush=True)
    return 0


if __name__ == "__main__":
    code = 1
    try:
        code = main()
    except Exception:
        traceback.print_exc()
    done_path = None
    for i, a in enumerate(sys.argv):
        if a == "--out" and i + 1 < len(sys.argv):
            done_path = sys.argv[i + 1] + ".done"
    if done_path:
        with open(done_path, "w") as f:
            f.write("exit %d\n" % code)
    sys.exit(code)
