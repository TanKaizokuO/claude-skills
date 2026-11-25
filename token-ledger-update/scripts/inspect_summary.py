import re, gzip, base64, json, glob
import os
S = os.environ.get("SHOT_DIR", ".")  # where screenshots go
PAGE_PATH = os.path.abspath(os.environ.get("PAGE", "artifact-page.html"))
s = open(PAGE_PATH, encoding="utf-8").read()
# Older builds embedded SNAP_B64 in the page; builds ship data/*.json.gz or base64 data/*.txt next to it.
m = re.search(r'var SNAP_B64 = "([^"]+)"', s)
if m:
    db = json.loads(gzip.decompress(base64.b64decode(m.group(1))).decode("utf-8"))
else:
    db = {}
    d = os.path.join(os.path.dirname(PAGE_PATH), "data")
    for f in sorted(glob.glob(os.path.join(d, "*.json.gz")) + glob.glob(os.path.join(d, "*.txt"))):
        raw = open(f, "rb").read()
        raw = gzip.decompress(raw if f.endswith(".gz") else base64.b64decode(raw))
        for k, v in json.loads(raw.decode("utf-8")).items():
            db.setdefault(k, []).extend(v if isinstance(v, list) else [v])
for k, v in db.items():
    if '"metric_id":"summary"' in k and '"combined"' in k:
        for var in (v if isinstance(v, list) else [v]):
            print(k[:200], var["s"], var["e"])
            j = json.loads(var["t"])
            def walk(o, path=""):
                if isinstance(o, dict):
                    for kk, vv in o.items(): walk(vv, path + "." + kk)
                elif isinstance(o, list):
                    for i, vv in enumerate(o[:3]): walk(vv, path + f"[{i}]")
                else:
                    if re.search(r"inr|usd|cost|fx|rate|currency", path, re.I): print("  ", path, o)
            walk(j)
