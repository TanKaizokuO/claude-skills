#!/usr/bin/env python3
"""Build the offline Token Ledger snapshot from a capture JSON and the offline vite bundle.

Usage:
  build.py --capture <capture.json> --dist <dist-offline dir> --out <out dir>
           [--pricing <pricing.json>] [--limit-bytes 15000000] [--part-limit 12000000]
           [--total-limit 200000000]

Writes into --out:
- index.html: the page (CSS and JS inlined, GET snapshot inline as gzip+base64, manifest inline).
  It holds no POST data.
- data/<label>-<n>.txt: POST data per range label. Each file is base64 text of the gzip of
  {key: {"s","e","t"}} (artifacts do not serve .gz) and is <= --part-limit bytes; a label may
  have several parts. A key with several records in one label (old captures) stores a list of
  such objects; the shim picks the nearest start.
- keys.json: {"post": [...], "get": [...]} distinct keys of the capture, for the next capture.

Capture records are {"key","s","e","w","t"}. "w" is all, 30d, 30d_prev, 7d, 7d_prev, 24h or
24h_prev for POST /api/v1/query keys and null for GET keys. A missing "w" (old captures) means 30d.

Long lists are trimmed per record. N is the largest of 2000, 1500, 1000, 500 for which the page is
<= --limit-bytes, every data part is <= --part-limit and the data total is <= --total-limit.
Speed points are strided to 10k. The banner's currency and rate come from pricing.json.
"""
import argparse
import base64
import datetime
import gzip
import json
import os
import re
import sys

DEFAULT_PRICING = os.path.join(
    os.environ.get("TOKEN_TRACKER_REPO", "/home/tankaizokuo/Code/projects/token-tracker"),
    "pricing.json",
)
SPEED_POINTS = 10_000
NS = [2000, 1500, 1000, 500]
QP = "POST /api/v1/query "
MAIN_LABEL = "30d"
TRIM_METRICS = ("outcomes", "traces", "model_profiles")
RULES = {
    "outcomes": [("tasks", "top")],
    "traces": [("events", "first"), ("rows", "first"), ("session_level_events", "first"),
               ("mcp_events", "first"), ("context_occupancy.per_turn_history", "stride")],
    "model_profiles": [("switching_timeline.events", "first")],
    "speed": [("anomaly_baseline.groups", "first")],  # speed points handled separately (10k stride)
}


def ser(o):
    return json.dumps(o, separators=(",", ":"), ensure_ascii=False)


def stride(arr, N):
    n = len(arr)
    if N >= n:
        return arr
    idx = sorted({round(i * (n - 1) / (N - 1)) for i in range(N)})
    return [arr[i] for i in idx]


def pick(arr, mode, N):
    if mode == "first":
        return arr[:N]
    if mode == "top":
        return sorted(arr, key=lambda t: ((t.get("cost_usd") or 0), (t.get("request_count") or 0)),
                      reverse=True)[:N]
    if mode == "stride":
        return stride(arr, N)
    raise ValueError(mode)


def apply_rules(obj, metric, N):
    for path, mode in RULES.get(metric, []):
        parts = path.split(".")
        parent = obj
        for p in parts[:-1]:
            parent = parent.get(p) if isinstance(parent, dict) else None
        if not isinstance(parent, dict):
            continue
        arr = parent.get(parts[-1])
        if isinstance(arr, list) and len(arr) > N:
            parent[parts[-1]] = pick(arr, mode, N)
    return obj


def generic(o, N):
    if isinstance(o, dict):
        return {k: generic(v, N) for k, v in o.items()}
    if isinstance(o, list):
        if len(o) > 200:
            o = o[:N]
        return [generic(x, N) for x in o]
    return o


def trim_text(key, t, N):
    """Text to store for one record. Only trimmed POST records are re-serialized."""
    if not key.startswith(QP):
        return t
    b = json.loads(key[len(QP):])
    m = b.get("metric_id")
    if m == "speed":
        obj = json.loads(t)
        pts = obj.pop("points", None) if isinstance(obj, dict) else None
        obj = generic(apply_rules(obj, "speed", N), N)
        if isinstance(pts, list) and isinstance(obj, dict):
            obj["points"] = stride(pts, SPEED_POINTS)
        return ser(obj)
    if m in TRIM_METRICS:
        return ser(generic(apply_rules(json.loads(t), m, N), N))
    return t


def records(text):
    dec = json.JSONDecoder()
    i = text.index("[") + 1
    n = len(text)
    while True:
        while i < n and text[i] in " \r\n\t,":
            i += 1
        if i >= n or text[i] == "]":
            return
        rec, i = dec.raw_decode(text, i)
        yield rec


def group_records(recs, N):
    """Trim and group the capture records.

    Returns (windows, gets, dupes, trimmed). windows: {label: {key: value}} for POST keys,
    gets: {key: value} for GET keys. value is {"s","e","t"}, or a list of those when one key
    has several records in the same table.
    """
    windows, gets = {}, {}
    seen, dupes, trimmed = set(), 0, 0
    for rec in recs:
        key, s, e = rec["key"], rec.get("s"), rec.get("e")
        is_post = key.startswith(QP)
        label = (rec.get("w") or MAIN_LABEL) if is_post else None
        sig = (label, key, s, e)
        if sig in seen:
            dupes += 1
            continue
        seen.add(sig)
        t = trim_text(key, rec["t"], N)
        if t is not rec["t"]:
            trimmed += 1
        table = windows.setdefault(label, {}) if is_post else gets
        table.setdefault(key, []).append({"s": s, "e": e, "t": t})
    for table in [gets, *windows.values()]:
        for key, entries in table.items():
            table[key] = entries[0] if len(entries) == 1 else entries
    return windows, gets, dupes, trimmed


def pack_table(table, part_limit):
    """Split {key: value} into base64 gzip blobs of at most part_limit bytes, keys kept in order."""
    inners = [ser(k) + ":" + ser(v) for k, v in table.items()]
    blobs, i, n = [], 0, len(inners)
    while i < n:
        # Greedy guess: about 6x compression (4.5x after base64), then shrink until it fits.
        j, raw = i, 0
        while j < n and (j == i or raw + len(inners[j]) <= part_limit * 4.5):
            raw += len(inners[j]) + 1
            j += 1
        while True:
            blob = base64.b64encode(gzip.compress(("{" + ",".join(inners[i:j]) + "}").encode("utf-8"), 9, mtime=0))
            if len(blob) <= part_limit or j - i == 1:
                break
            j = i + max(1, int((j - i) * part_limit / len(blob) * 0.95))
        if len(blob) > part_limit:
            sys.exit("one key is %d bytes as base64 gzip, over --part-limit %d" % (len(blob), part_limit))
        blobs.append(blob)
        i = j
    return blobs


def build_parts(windows, part_limit):
    """Return ({relative path: base64 gzip bytes}, {label: [relative path, ...]})."""
    files, manifest_windows = {}, {}
    for label in sorted(windows):
        names = []
        for idx, blob in enumerate(pack_table(windows[label], part_limit)):
            rel = "data/%s-%d.txt" % (label, idx)
            files[rel] = blob
            names.append(rel)
        manifest_windows[label] = names
    return files, manifest_windows


ADAPTER = r"""
(function () {
  var GET_B64 = "__B64__";
  var MANIFEST = __MANIFEST__;
  var CURRENCY = __CODE__;
  var FX = __FX__;
  var ROWS = __N__;
  var QP = "POST /api/v1/query ";
  // Request-body paths that hold dates (capture.py DATE_PATHS). They are removed from the key;
  // the window label comes from period_b when present (comparisons), else from time_range.
  var DATE_PATHS = [["comparison_periods", "period_a", "start"], ["comparison_periods", "period_a", "end"],
                    ["comparison_periods", "period_b", "start"], ["comparison_periods", "period_b", "end"]];
  window.__TL_OFFLINE_RANGES__ = ["24h", "7d", "30d", "all"];
  var nativeFetch = window.fetch.bind(window);

  async function gunzipText(bytes) {
    var stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
    return new Response(stream).text();
  }
  // GET snapshot, inline. Each key maps to {s,e,t}, or to a list of those.
  var ready = (async function () {
    var bin = Uint8Array.from(atob(GET_B64), function (c) { return c.charCodeAt(0); });
    return JSON.parse(await gunzipText(bin));
  })();
  // POST data per range label. Parts are fetched on first use and cached per label.
  var loads = {};
  function hasLabel(label) { return Object.prototype.hasOwnProperty.call(MANIFEST.windows, label); }
  function loadWindow(label) {
    if (!loads[label]) {
      var files = hasLabel(label) ? MANIFEST.windows[label] : [];
      loads[label] = Promise.all(files.map(function (p) {
        return nativeFetch(new URL(p, location.href)).then(function (r) {
          if (!r.ok) throw new Error("offline data " + p + " HTTP " + r.status);
          return r.arrayBuffer();
        }).then(function (buf) {
          var bytes = new Uint8Array(buf);
          if (bytes[0] === 0x1f && bytes[1] === 0x8b) return gunzipText(bytes);
          var text = new TextDecoder().decode(bytes);
          var c = text.charAt(0);
          if (c === "{" || c === "[") return text;
          // data/*.txt: base64 of gzip.
          return gunzipText(Uint8Array.from(atob(text.trim()), function (ch) { return ch.charCodeAt(0); }));
        }).then(function (text) { return JSON.parse(text); });
      })).then(function (maps) {
        return maps.reduce(function (acc, m) { return Object.assign(acc, m); }, {});
      });
      loads[label].catch(function () { delete loads[label]; });
    }
    return loads[label];
  }
  function canon(o) {
    if (Array.isArray(o)) return o.map(canon);
    if (o && typeof o === "object") {
      var out = {};
      Object.keys(o).sort().forEach(function (k) { out[k] = canon(o[k]); });
      return out;
    }
    return o;
  }
  function stripDates(b) {
    DATE_PATHS.forEach(function (path) {
      var parent = b;
      for (var i = 0; i < path.length - 1; i++) parent = parent && parent[path[i]];
      if (parent && typeof parent === "object") delete parent[path[path.length - 1]];
    });
    return b;
  }
  // The body that picks the window: period_b for comparisons, otherwise the body itself.
  function windowBody(body) {
    var pb = body && body.comparison_periods && body.comparison_periods.period_b;
    return pb ? { time_range: pb } : body;
  }
  function keyOf(method, url, body) {
    var u = new URL(url, location.href);
    if (method === "POST" && u.pathname === "/api/v1/query" && body) {
      var b = JSON.parse(body);
      delete b.time_range;
      return QP + JSON.stringify(canon(stripDates(b)));
    }
    return method + " " + u.pathname + u.search;
  }
  function json(text, status) {
    return new Response(text, { status: status || 200, headers: { "Content-Type": "application/json" } });
  }
  // Range label for a query body: all, 24h, 7d or 30d, with _prev when the window ended
  // before the midpoint of its span (relative to now).
  function rangeLabel(body) {
    var DAY = 86400000;
    var tr = body && body.time_range;
    if (!tr || !tr.start) return "all";
    var s = Date.parse(tr.start), e = Date.parse(tr.end);
    var dur = e - s;
    var base = dur <= 2 * DAY ? "24h" : dur <= 10 * DAY ? "7d" : "30d";
    return base + (e < Date.now() - dur / 2 ? "_prev" : "");
  }
  // Several records for one key in one table (old captures): the nearest start wins.
  function pickVariant(v, method, body) {
    if (!Array.isArray(v)) return v;
    var want = null;
    if (method === "POST" && body) {
      var tr = JSON.parse(body).time_range;
      want = tr && tr.start ? Date.parse(tr.start.slice(0, 10)) : null;
    }
    if (want === null) return v[0];
    function dist(x) { return Math.abs(Date.parse(String(x.s || "").slice(0, 10)) - want); }
    return v.reduce(function (a, x) { return dist(x) < dist(a) ? x : a; });
  }
  window.fetch = async function (input, init) {
    init = init || {};
    var url = typeof input === "string" ? input : input.url;
    var method = String(init.method || (input && input.method) || "GET").toUpperCase();
    var body = init.body ? String(init.body) : null;
    var k = keyOf(method, url, body);
    var table;
    if (k.indexOf(QP) === 0) {
      var label = rangeLabel(windowBody(JSON.parse(body)));
      table = await loadWindow(hasLabel(label) ? label : "30d");
    } else {
      table = await ready;
    }
    if (Object.prototype.hasOwnProperty.call(table, k)) {
      return json(pickVariant(table[k], method, body).t, 200);
    }
    window.__offlineMisses = window.__offlineMisses || [];
    window.__offlineMisses.push(k);
    return json(JSON.stringify({ error: "Not in the offline snapshot: " + k }), 404);
  };
  loadWindow("30d").catch(function () {});  // prefetch the default window

  // ---- Downloads inside the claude.ai artifact viewer ----
  // Anchor downloads of blob:/data: URLs are not saved by the viewer. When the host provides
  // window.claude.use("downloads"), the bytes are handed to the host instead.
  var origAnchorClick = HTMLAnchorElement.prototype.click;
  var bypassing = false;
  function hostDownloads() { return !!(window.claude && typeof window.claude.use === "function"); }
  function isDownloadAnchor(a) {
    var href = a.getAttribute("href") || "";
    return a.hasAttribute("download") || /^(blob|data):/i.test(href);
  }
  function nativeClick(a) {
    bypassing = true;
    try { origAnchorClick.call(a); } finally { bypassing = false; }
  }
  async function saveWithHost(a, readP) {
    var d = null;
    try { d = await window.claude.use("downloads"); }
    catch (err) { console.warn("[offline-download]", err && err.code); return false; }
    if (!d) return false;
    var href = a.getAttribute("href") || "";
    var blob = await readP;
    if (!blob) { console.warn("[offline-download]", "read-failed"); return false; }
    var name = a.getAttribute("download");
    if (!name && !/^data:/i.test(href)) name = href.split(/[?#]/)[0].split("/").pop();
    name = name || "export";
    try { await d.save({ filename: name, data: blob }); }
    catch (err) {
      var code = err && err.code;
      if (code !== "declined") console.warn("[offline-download]", code);
    }
    return true;
  }
  function routeDownload(a) {
    var href = a.getAttribute("href") || "";
    // Start reading now: the app revokes blob: URLs synchronously right after click().
    var readP = nativeFetch(href).then(function (r) { return r.blob(); }, function () { return null; });
    return saveWithHost(a, readP).then(function (handled) {
      if (handled) return;
      return readP.then(function (blob) {
        if (blob && /^blob:/i.test(href)) a.href = URL.createObjectURL(blob);
        nativeClick(a);
      });
    });
  }
  HTMLAnchorElement.prototype.click = function () {
    if (bypassing || !hostDownloads() || !isDownloadAnchor(this)) return origAnchorClick.apply(this, arguments);
    routeDownload(this);
  };
  document.addEventListener("click", function (e) {
    if (bypassing || !hostDownloads()) return;
    var t = e.target;
    var a = t && t.closest ? t.closest("a") : null;
    if (!a || !isDownloadAnchor(a)) return;
    e.preventDefault();
    routeDownload(a);
  }, true);

  document.addEventListener("DOMContentLoaded", function () {
    var bar = document.createElement("div");
    bar.setAttribute("style", "position:fixed;left:0;right:0;bottom:0;z-index:99999;font:12px/1.4 system-ui,sans-serif;padding:6px 12px;background:#1b1f24;color:#e6e6e6;opacity:.92");
    bar.textContent = "Offline snapshot captured " + MANIFEST.captured + ". Ranges available: Last 24 Hours, Last 7 Days, Last 30 Days, All History (other ranges need the live app). Costs priced from pricing.json, shown in " + CURRENCY + " at " + FX + "/USD. Outcomes, Traces and model profiles show up to " + ROWS + " rows each; Speed charts show a 10k-point sample.";
    document.body.appendChild(bar);
  });
})();
"""


def render_page(css, js, get_b64, manifest, code, fx_text, n):
    manifest_js = ser(manifest).replace("</", "<\\/")
    adapter = (ADAPTER.replace("__B64__", get_b64)
               .replace("__MANIFEST__", manifest_js)
               .replace("__CODE__", ser(code))
               .replace("__FX__", ser(fx_text))
               .replace("__N__", str(n)))
    head_inject = ("<style>" + css + "</style>\n<script>"
                   + adapter.replace("</script", "<\\/script") + "</script>")
    return ('<meta charset="UTF-8">\n<title>Token Ledger</title>\n' + head_inject
            + '\n<div id="root"></div>\n'
            + '<script type="module">' + js + "</script>\n")


def write_out(outdir, page, data_files, keys):
    data_dir = os.path.join(outdir, "data")
    os.makedirs(data_dir, exist_ok=True)
    for name in os.listdir(data_dir):
        if name.endswith(".json.gz") or name.endswith(".txt"):
            os.remove(os.path.join(data_dir, name))
    for rel, blob in data_files.items():
        with open(os.path.join(outdir, rel), "wb") as f:
            f.write(blob)
    with open(os.path.join(outdir, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)
    with open(os.path.join(outdir, "keys.json"), "w", encoding="utf-8") as f:
        f.write(ser(keys) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capture", required=True)
    ap.add_argument("--dist", required=True, help="vite output dir (dist-offline) with index.html")
    ap.add_argument("--out", required=True, help="output directory: index.html, data/, keys.json")
    ap.add_argument("--pricing", default=DEFAULT_PRICING)
    ap.add_argument("--limit-bytes", type=int, default=15_000_000, help="max page (index.html) bytes")
    ap.add_argument("--part-limit", type=int, default=12_000_000, help="max bytes per data/*.txt (base64)")
    ap.add_argument("--total-limit", type=int, default=200_000_000, help="max total bytes of data files")
    args = ap.parse_args()

    with open(args.pricing, encoding="utf-8") as f:
        cur = json.load(f).get("currency") or {}
    code, fx = cur.get("code"), cur.get("per_usd")
    if not code or not isinstance(fx, (int, float)):
        sys.exit("pricing.json currency.code / per_usd missing")
    fx_text = ("%g" % fx)

    with open(args.capture, encoding="utf-8") as f:
        recs = list(records(f.read()))
    post_recs = [r for r in recs if r["key"].startswith(QP)]
    labels = sorted({(r.get("w") or MAIN_LABEL) for r in post_recs})
    print("capture records", len(recs), "POST", len(post_recs), "GET", len(recs) - len(post_recs),
          "labels", labels, flush=True)

    # captured: capture file mtime. anchor: latest window end in the records (null for "all").
    mtime = datetime.datetime.fromtimestamp(os.path.getmtime(args.capture))
    ends = [r["e"] for r in post_recs if r.get("e")]
    manifest_meta = {
        "captured": mtime.strftime("%Y-%m-%d %H:%M"),
        "anchor": max(ends) if ends else mtime.isoformat(timespec="minutes"),
    }
    keys = {
        "post": sorted({r["key"] for r in post_recs}),
        "get": sorted({r["key"] for r in recs if not r["key"].startswith(QP)}),
    }

    html = open(os.path.join(args.dist, "index.html"), encoding="utf-8").read()
    css_name = re.search(r'href="\./(assets/[^"]+\.css)"', html).group(1)
    js_name = re.search(r'src="\./(assets/[^"]+\.js)"', html).group(1)
    css = open(os.path.join(args.dist, css_name), encoding="utf-8").read()
    js = open(os.path.join(args.dist, js_name), encoding="utf-8").read().replace("</script", "<\\/script")

    # Offline fix: .tl-chart-canvas height:100% resolves to 0 inside the flex card (blank chart).
    if not re.search(r"\.tl-chart-canvas\s*\{[^}]*position:\s*absolute", css):
        css = css + ".tl-chart-canvas{position:absolute;inset:0}"
        print("css: appended .tl-chart-canvas fix", flush=True)
    else:
        print("css: bundle already positions .tl-chart-canvas; no append", flush=True)

    chosen, result = None, None
    for N in NS:
        windows, gets, dupes, trimmed = group_records(recs, N)
        data_files, manifest_windows = build_parts(windows, args.part_limit)
        del windows
        get_b64 = base64.b64encode(gzip.compress(ser(gets).encode("utf-8"), 9, mtime=0)).decode()
        del gets
        manifest = {"windows": manifest_windows, **manifest_meta}
        page = render_page(css, js, get_b64, manifest, code, fx_text, N)
        page_bytes = len(page.encode("utf-8"))
        total = sum(len(b) for b in data_files.values())
        biggest = max((len(b) for b in data_files.values()), default=0)
        fits = page_bytes <= args.limit_bytes and biggest <= args.part_limit and total <= args.total_limit

        print(f"N={N} dupes_dropped={dupes} trimmed_records={trimmed}", flush=True)
        print(f"  index.html {page_bytes:,} bytes", flush=True)
        for rel in sorted(data_files):
            print(f"  {rel} {len(data_files[rel]):,} bytes", flush=True)
        print(f"  keys.json {len(ser(keys)) + 1:,} bytes", flush=True)
        print(f"  data total {total:,} (limit {args.total_limit:,}); largest part {biggest:,} "
              f"(limit {args.part_limit:,}); page {page_bytes:,} (limit {args.limit_bytes:,}); "
              f"fits {fits}", flush=True)
        result = (page, data_files, keys)
        if fits:
            chosen = N
            break

    page, data_files, keys = result
    write_out(args.out, page, data_files, keys)
    if chosen is None:
        print("NO N FITS; wrote the N=%d attempt to %s anyway" % (NS[-1], args.out), flush=True)
    print("CHOSEN N =", chosen, "out", args.out, "files", len(data_files) + 2, flush=True)
    return 0 if chosen is not None else 1


if __name__ == "__main__":
    sys.exit(main())
