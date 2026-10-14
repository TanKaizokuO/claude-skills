#!/usr/bin/env python3
"""Splice a fresh tokentrack.py json payload into the Token Ledger artifact HTML.

Usage: python3 -I merge_data.py <saved-artifact.html> <data.json> <out.html>

Claude Code (and omp) delete old session logs, so a fresh parse can be missing
days the artifact already has. For any (day, source) where the old artifact
has more messages than the fresh payload, the old cells/sub_cells are kept,
and every aggregate (totals, by_*, span, messages) is rebuilt from the merged
cells. Only the DATA JSON is replaced; the UI is untouched.
"""
import json, sys, collections as C
src, new, out = sys.argv[1:4]
s = open(src).read(); i = s.index("const DATA = ") + len("const DATA = ")
o, n = json.JSONDecoder().raw_decode(s[i:])
d = json.load(open(new))
assert all(r["total"] == r["in"]+r["out"]+r["cr"]+r["cw"] for r in d["by_day"])
def nby(cells):
    m = C.Counter()
    for r in cells: m[(r[0], r[1])] += r[4]
    return m
on, nn = nby(o["cells"]), nby(d["cells"])
# day/source pairs whose logs were pruned: old artifact has more messages than the fresh parse
keep = {k for k in on if on[k] > nn.get(k, 0) and k[0] < d["span"][1]}
print("restoring", sorted(keep))
for f in ("cells", "sub_cells"):
    d[f] = [r for r in d[f] if (r[0], r[1]) not in keep] + [r for r in o[f] if (r[0], r[1]) in keep]
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
days = sorted({r[0] for r in d["cells"]}); d["span"] = [days[0], days[-1]]
d["by_day"] = dump(agg(lambda r: r[0])); d["by_model"] = dump(agg(lambda r: r[2]))
d["by_source"] = dump(agg(lambda r: r[1])); d["by_project"] = dump(agg(lambda r: r[3]))
d["by_day_source"] = [dict(key=list(k), **v) for k, v in sorted(agg(lambda r: (r[0], r[1])).items())]
d["initial_days"] = 0
open(out, "w").write(s[:i] + json.dumps(d) + s[i+n:])
print(d["span"], d["messages"], round(d["totals"]["cost"], 2), [(r["key"], r["n"], round(r["cost"], 2)) for r in d["by_source"]])
