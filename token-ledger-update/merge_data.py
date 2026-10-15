#!/usr/bin/env python3
"""Splice a fresh tokentrack.py json payload into the Token Ledger artifact HTML.

Usage: python3 -I merge_data.py <saved-artifact.html> <data.json> <out.html>

Claude Code (and omp) delete old session logs, so a fresh parse can be missing
days the artifact already has. For any (day, source) where the old artifact has
more messages than the fresh payload, its cells/sub_cells are restored and marked
archived (cells[10], sub_cells[11] = true); fresh rows are marked false. Archived
rows are never re-priced: they keep the status recorded by the previous artifact,
else the current payload's status for that model (True only when it is priced there;
otherwise False = not recorded). Never "estimated" by default. A previous artifact's
default stamp (estimated or False, with the old no-provenance basis) is not a recorded
status and is replaced the same way (models[m].archived_priced, archived_cost_basis;
archived_rate when the old rate is known). A cost > 0 never makes a row verified. Aggregates, coverage and span are rebuilt from cells. Fresh pricing is
carried unchanged. Sessions: fresh only; restored days are recorded in archive with
sessions "unavailable". Events: old only if fresh has none.
Only the DATA JSON is replaced; the UI is untouched.

Timezone change: when the artifact's days (DATA.timezone, absent = legacy UTC) differ
from the payload's, comparing day buckets would "restore" every day the shift moved
messages out of. Pass a 4th arg, `tokentrack.py json --tz <artifact zone>` output:
pruned pairs are found in that same-zone parse, and only the missing part of each
old cell (old minus same-zone fresh) is added as archived rows on its old day; fresh
rows stay. Without it a mismatch aborts.
"""
import json, sys, collections as C
src, new, out = sys.argv[1:4]
s = open(src).read(); i = s.index("const DATA = ") + len("const DATA = ")
o, n = json.JSONDecoder().raw_decode(s[i:])
d = json.load(open(new))
assert all(r["total"] == r["in"]+r["out"]+r["cr"]+r["cw"] for r in d["by_day"])
old_tz, fresh_tz = o.get("timezone") or "UTC", d.get("timezone") or "UTC"
ref = d  # payload bucketed like the old artifact, used to find pruned pairs
if old_tz != fresh_tz:
    if len(sys.argv) < 5:
        sys.exit(f"artifact days are {old_tz}, payload days are {fresh_tz}: add a 4th arg, "
                 f"the output of `tokentrack.py json --tz {old_tz}`")
    ref = json.load(open(sys.argv[4]))
    assert (ref.get("timezone") or "UTC") == old_tz, f"4th arg must be bucketed in {old_tz}"
def nby(cells):
    m = C.Counter()
    for r in cells: m[(r[0], r[1])] += r[4]
    return m
on, nn = nby(o["cells"]), nby(ref["cells"])
# day/source pairs whose logs were pruned: old artifact has more messages than the fresh parse
end = (ref.get("span") or [None, None])[1]  # None: fresh has no records, so no partial last day to exclude
keep = {k for k in on if on[k] > nn.get(k, 0) and (end is None or k[0] < end)}
print("restoring", sorted(keep))
def flag(rows, width, archived):
    # cells keep 0-9 and get archived at [10]; sub_cells keep 0-10 (subrepo at [10]) and get archived at [11]
    return [list(r[:width]) + [archived] for r in rows]
def missing(rows, ref_rows, width):
    # old cells minus what the same-zone parse still has, per (day, source, model, project[, subrepo])
    key = lambda r: tuple(r[:4]) + tuple(r[10:width])
    have = C.defaultdict(lambda: [0] * 6)
    for r in ref_rows:
        if (r[0], r[1]) in keep:
            for j in range(6): have[key(r)][j] += r[4 + j]
    res = []
    for r in rows:
        if (r[0], r[1]) not in keep: continue
        h = have[key(r)]; v = [max(0, r[4 + j] - h[j]) for j in range(6)]
        for j in range(6): h[j] = max(0, h[j] - r[4 + j])  # an old key can appear more than once
        if v[0] > 0: res.append(list(r[:4]) + v + list(r[10:width]))
    return res
for f, w in (("cells", 10), ("sub_cells", 11)):
    if ref is d:
        d[f] = [r for r in flag(d[f], w, False) if (r[0], r[1]) not in keep] + flag([r for r in o.get(f, []) if (r[0], r[1]) in keep], w, True)
    else:
        d[f] = flag(d[f], w, False) + flag(missing(o.get(f, []), ref.get(f, []), w), w, True)
def agg(keyfn):
    b = C.defaultdict(lambda: {"n": 0, "in": 0, "out": 0, "cr": 0, "cw": 0, "total": 0, "cost": 0.0})
    for r in d["cells"]:
        x = b[keyfn(r)]
        for j, k in enumerate(("n", "in", "out", "cr", "cw"), 4): x[k] += r[j]
        x["total"] += r[5]+r[6]+r[7]+r[8]; x["cost"] += r[9]
    return b
dump = lambda b: [dict(key=k, **v) for k, v in sorted(b.items(), key=lambda kv: -kv[1]["cost"])]
d["totals"] = agg(lambda r: "all")["all"]
d["messages"] = d["totals"]["n"]
days = sorted({r[0] for r in d["cells"]}); d["span"] = [days[0], days[-1]] if days else None
d["by_day"] = dump(agg(lambda r: r[0])); d["by_model"] = dump(agg(lambda r: r[2]))
d["by_source"] = dump(agg(lambda r: r[1])); d["by_project"] = dump(agg(lambda r: r[3]))
d["by_day_source"] = [dict(key=list(k), **v) for k, v in sorted(agg(lambda r: (r[0], r[1])).items())]
fresh_models = d.get("models") or {}
old_models = o.get("models") or {}
old_rates = (o.get("pricing") or {}).get("models") or {}
old_rate_version = (o.get("pricing") or {}).get("version")
OLD_STAMP_BASIS = "archived: stored cost only; no price provenance, not re-priced"  # written by the old default
def est(rows): return "estimated" if any(r[9] > 0 for r in rows) else False
models = {}
for m in sorted(set(fresh_models) | {r[2] for r in d["cells"]}):
    live = [r for r in d["cells"] if r[2] == m and not r[10]]
    arch = [r for r in d["cells"] if r[2] == m and r[10]]
    prior = old_models.get(m) or {}
    # an old default stamp (estimated or False, with OLD_STAMP_BASIS) is not a recorded status
    stamp = prior.get("archived_cost_basis") == OLD_STAMP_BASIS and prior.get("archived_priced") in ("estimated", False)
    e = dict(fresh_models[m]) if m in fresh_models else (dict(prior) if not live else {})
    if arch:  # archived rows never take live status
        if "priced" in prior and not stamp:
            e["archived_priced"] = prior.get("archived_priced", prior["priced"])
            e["archived_cost_basis"] = prior.get("archived_cost_basis", "archived: stored cost only; status from previous artifact, not re-verified")
        else:  # no recorded status: current payload's status (True only), never "estimated"
            cur = (fresh_models.get(m) or {}).get("priced") is True
            e["archived_priced"] = cur
            e["archived_cost_basis"] = ("archived: stored cost only; status from current payload, not re-priced" if cur
                                        else "archived: stored cost only; no recorded price status, not re-priced")
        if "archived_rate" in prior: e["archived_rate"], e["archived_pricing_version"] = prior["archived_rate"], prior.get("archived_pricing_version")
        elif m in old_rates: e["archived_rate"], e["archived_pricing_version"] = old_rates[m], old_rate_version
    if arch and not live:
        e["priced"] = e["archived_priced"]
        if not prior: e["inferred"] = True
    elif live and "priced" not in e:
        e["priced"], e["inferred"] = est(live), True
    models[m] = e
def bucket(r):
    e = models[r[2]]
    p = e["archived_priced"] if r[10] else e["priced"]
    return "priced" if p is True else "estimated" if p == "estimated" else "unpriced"
cov = {"priced": {"requests": 0, "cost_usd": 0.0}, "estimated": {"requests": 0, "cost_usd": 0.0}, "unpriced": {"requests": 0}}
for r in d["cells"]:
    k = bucket(r)
    cov[k]["requests"] += r[4]
    if k != "unpriced": cov[k]["cost_usd"] += r[9]
for k in ("priced", "estimated"): cov[k]["cost_usd"] = round(cov[k]["cost_usd"], 8)
d["models"], d["coverage"] = models, cov
if keep:  # restored days: stored cost only; session and hour details are not carried
    old_tz, fresh_tz = o.get("timezone"), d.get("timezone")
    d["archive"] = {"restored": [list(k) for k in sorted(keep)], "sessions": "unavailable",
                    "hours": "unavailable",
                    "timezone": old_tz or "UTC", "timezone_source": "artifact" if old_tz else "assumed legacy UTC",
                    "fresh_timezone": fresh_tz, "timezone_mismatch": (old_tz or "UTC") != fresh_tz,
                    "day_grouping": "same timezone as fresh" if old_tz and old_tz == fresh_tz else "legacy day buckets; cannot rebucket without timestamps",
                    "restore_mode": "whole day rows" if ref is d else "missing part only: old cells minus a same-zone parse"}
    if d["archive"]["timezone_mismatch"]:
        print(f"warning: archived days bucketed as {d['archive']['timezone']}, fresh as {fresh_tz}; mixed legacy buckets")
    d["hours_coverage"] = {"complete": False, "archived": "unavailable", "hours": len(d.get("hours", []))}
else:
    if "hours_coverage" not in d:
        d["hours_coverage"] = {"complete": True, "archived": None}
# Events: fresh payload is authoritative (even [] allows deliberate clearing; never resurrect deleted events)
if "events" not in d: d["events"] = []
d["initial_days"] = 0
open(out, "w").write(s[:i] + json.dumps(d) + s[i+n:])
print(d["span"], d["messages"], round(d["totals"]["cost"], 2), [(r["key"], r["n"], round(r["cost"], 2)) for r in d["by_source"]], d["coverage"])
