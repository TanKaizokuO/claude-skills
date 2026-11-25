#!/usr/bin/env python3
"""Offline checks for capture.py window generation. No server, no network.

Run: python3 -I /home/tankaizokuo/.claude/skills/token-ledger-update/scripts/test_capture_windows.py
"""
import json
import os
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capture  # noqa: E402

ANCHOR = "2026-10-30T02:51:00Z"
NOW = capture.parse_now(ANCHOR)

# Derived by hand from the anchor, following App.tsx:297-304 and Overview.tsx:150-160.
EXPECTED = [
    ("all", None, None),
    ("30d", "2026-09-30", "2026-10-31"),
    ("30d_prev", "2026-08-30T00:00:00Z", "2026-09-30T00:00:00Z"),
    ("7d", "2026-10-23", "2026-10-31"),
    ("7d_prev", "2026-10-15T00:00:00Z", "2026-10-23T00:00:00Z"),
    ("24h", "2026-10-29T02:51:00Z", "2026-10-30T02:51:00Z"),
    ("24h_prev", "2026-10-28T02:51:00Z", "2026-10-29T02:51:00Z"),
]
LABELS = [w for w, _, _ in EXPECTED]
ENC = dict(sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def speed_key():
    body = {"contract_version": "1", "family": "speed", "group_by": ["day"],
            "harness_scope": "combined", "metric_id": "speed"}
    return capture.PFX + json.dumps(body, **ENC)


def models_key():
    body = {"contract_version": "1", "family": "tokens", "group_by": ["model"],
            "harness_scope": "combined", "metric_id": "tokens"}
    return capture.PFX + json.dumps(body, **ENC)


def group_key(g):
    body = json.loads(speed_key()[len(capture.PFX):])
    body["group_by"] = [g]
    return capture.PFX + json.dumps(body, **ENC)


def parse_bound(s):
    if len(s) == 10:
        return datetime.strptime(s, "%Y-%m-%d")
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")


def test_window_table():
    got = capture.compute_windows(NOW)
    assert got == EXPECTED, got


def test_time_range_format():
    assert capture.time_range_for(None, None) == {"timezone": "UTC"}
    assert capture.time_range_for("2026-10-23", "2026-10-31") == {
        "timezone": "UTC", "start": "2026-10-23", "end": "2026-10-31"}


def test_prev_windows_abut_main():
    table = {w: (s, e) for w, s, e in EXPECTED}
    for main in ("30d", "7d", "24h"):
        assert parse_bound(table[main + "_prev"][1]) == parse_bound(table[main][0]), main
        dur_main = parse_bound(table[main][1]) - parse_bound(table[main][0])
        dur_prev = parse_bound(table[main + "_prev"][1]) - parse_bound(table[main + "_prev"][0])
        assert dur_main == dur_prev, main


def test_build_work_shape_and_counts():
    post = [speed_key(), models_key()]
    get = [capture.FX_KEY]
    work = capture.build_work(post, get, NOW)
    # 2 POST keys x 3 scopes x 7 windows, 3 speed groupings x 3 scopes x 7 windows, 1 GET key.
    assert len(work) == 2 * 3 * 7 + 3 * 3 * 7 + 1, len(work)
    for r in work:
        assert set(r) == {"key", "s", "e", "w"}, r
    assert len({(r["key"], r["w"]) for r in work}) == len(work), "duplicate (key, window)"

    base = [r for r in work if r["key"] == speed_key()]
    assert [(r["w"], r["s"], r["e"]) for r in base] == EXPECTED

    for g in capture.SPEED_GROUPS:
        recs = [r for r in work if r["key"] == group_key(g)]
        assert [r["w"] for r in recs] == LABELS, g
        assert [(r["w"], r["s"], r["e"]) for r in recs] == EXPECTED, g

    gets = [r for r in work if r["key"] == capture.FX_KEY]
    assert gets == [{"key": capture.FX_KEY, "s": None, "e": None, "w": None}], gets


def scoped(key, scope):
    body = json.loads(key[len(capture.PFX):])
    body["harness_scope"] = scope
    return capture.PFX + json.dumps(body, **ENC)


def test_every_post_key_has_every_scope_and_every_window():
    work = capture.build_work([models_key(), speed_key()], [], NOW)
    for scope in ("combined", "claude-code", "omp"):
        key = scoped(models_key(), scope)
        assert [r["w"] for r in work if r["key"] == key] == LABELS, scope
    assert {scoped(models_key(), s) for s in capture.HARNESS_SCOPES} <= {r["key"] for r in work}


def test_scope_expansion_only_changes_harness_scope():
    key = models_key()
    got = capture.expand_harness_scopes([key])
    assert got == [scoped(key, s) for s in ("combined", "claude-code", "omp")], got
    for k in got:
        body = json.loads(k[len(capture.PFX):])
        assert body.get("metric_id") == "tokens", k
        assert "time_range" not in body, k
    # include_archive is not expanded: a key that has it keeps its value, and no false variant appears.
    with_arc = capture.expand_harness_scopes([capture.PFX + ser_key_sorted({
        "harness_scope": "combined", "include_archive": True, "metric_id": "models"})])
    assert all(json.loads(k[len(capture.PFX):])["include_archive"] is True for k in with_arc), with_arc
    assert len(with_arc) == 3, with_arc


def test_error_key_from_app_is_expanded():
    # The key the owner saw missing from the snapshot (claude-code scope, models, limit 100).
    body = {"contract_version": "1", "filters": {}, "harness_scope": "claude-code",
            "include_archive": True, "metric_id": "models", "pagination": {"limit": 100, "offset": 0}}
    key = capture.PFX + ser_key_sorted(body)
    work = capture.build_work([key, speed_key()], [capture.FX_KEY], NOW)
    assert any(r["key"] == key and r["w"] == "30d" for r in work), "claude-code models key missing"


def ser_key_sorted(body):
    # Same bytes as build.py's shim: canon() sorts keys, no spaces, time_range removed.
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def test_stored_keys_match_shim_form():
    # build.py keyOf: delete time_range, strip date paths, canon (sorted keys, compact JSON).
    work = capture.build_work([models_key(), speed_key(), capture.PFX + ser_key_sorted({
        "contract_version": "1", "comparison_periods": {"period_a": {"start": "x"}},
        "harness_scope": "omp", "include_archive": True, "metric_id": "comparisons",
        "filters": {}})], [], NOW)
    for r in work:
        if not r["key"].startswith(capture.PFX):
            continue
        body = json.loads(r["key"][len(capture.PFX):])
        assert "time_range" not in body, r["key"]
        # Only the date leaves go (DATE_PATHS); empty period objects stay, as in the shim's stripDates.
        for path in capture.DATE_PATHS:
            parent = body
            for p in path[:-1]:
                parent = parent.get(p, {}) if isinstance(parent, dict) else {}
            assert path[-1] not in parent, (path, r["key"])
        assert r["key"] == capture.PFX + ser_key_sorted(body), r["key"]


def test_speed_day_per_scope_gets_groups():
    work = capture.build_work([speed_key()], [], NOW)
    for scope in capture.HARNESS_SCOPES:
        dk = scoped(speed_key(), scope)
        for g in capture.SPEED_GROUPS:
            b = json.loads(dk[len(capture.PFX):])
            b["group_by"] = [g]
            nk = capture.PFX + ser_key_sorted(b)
            assert [r["w"] for r in work if r["key"] == nk] == LABELS, (scope, g)


def test_fx_appended_when_missing():
    work = capture.build_work([speed_key()], [], NOW)
    fx = [r for r in work if r["key"] == capture.FX_KEY]
    assert fx == [{"key": capture.FX_KEY, "s": None, "e": None, "w": None}], fx


def test_speed_key_required():
    try:
        capture.build_work([models_key()], [], NOW)
    except RuntimeError:
        return
    raise AssertionError("expected RuntimeError without a speed/day key")


def test_keys_json_loader():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "keys.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"post": [speed_key()], "get": [capture.FX_KEY]}, f)
        post, get = capture.load_keys(path)
    assert post == [speed_key()] and get == [capture.FX_KEY], (post, get)


def test_parse_now_rejects_naive():
    try:
        capture.parse_now("2026-10-30T02:51:00")
    except ValueError:
        return
    raise AssertionError("naive --now must be rejected")


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print("PASS", t.__name__)
        except Exception as exc:  # report every failure, then exit non-zero
            failed += 1
            print("FAIL", t.__name__, repr(exc))
    print("%d passed, %d failed" % (len(tests) - failed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
