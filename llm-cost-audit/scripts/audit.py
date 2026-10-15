#!/usr/bin/env python3
"""Read-only LLM spend audit (omp + Claude Code) for the Token Ledger.

Headline money (spend, its split by source, model, project and day, coverage and exclusions)
comes from the canonical tokentrack module in CANONICAL_DIR: tokentrack.collect() records,
priced by tokentrack.price() from its pricing.json, grouped by the same day as the ledger cells.
Session analytics (triage, detectors, supersessions) read omp's stats.db and the Claude Code
JSONL, and are priced with the same canonical rates. Nothing is written except a temp copy of
stats.db (deleted on exit) and the text mirror at LATEST.
"""
import argparse, collections, datetime as dt, glob, json, os, re, shutil, sqlite3, statistics, sys, tempfile

CANONICAL_DIR = "/home/tankaizokuo/Code/projects/token-tracker"
if not os.path.isfile(os.path.join(CANONICAL_DIR, "tokentrack.py")):
    sys.exit(f"canonical tokentrack.py not found in {CANONICAL_DIR}; refusing to price with another table")
sys.dont_write_bytecode = True  # the audit is read-only; do not drop __pycache__ into the canonical repo
sys.path.insert(0, CANONICAL_DIR)
import tokentrack as tk  # noqa: E402  canonical pricing, day grouping and record collection

PRICING_PATH = os.path.join(CANONICAL_DIR, "pricing.json")
RATES, CURRENCY = tk.load_pricing(PRICING_PATH)
if CURRENCY.get("code") != "INR":
    sys.exit(f"canonical currency is {CURRENCY.get('code')}; the Audit tab renders INR only")
R = CURRENCY["per_usd"]
SOURCES = ("omp", "claude-code")  # canonical source names
TOOL = {"omp": "omp", "claude-code": "cc"}  # short keys used by session rows and the Audit tab

EDIT_TOOLS = {"edit", "write", "Edit", "Write", "MultiEdit", "NotebookEdit"}
SLEEP_RE = re.compile(r"\bsleep\s+\d")
SECRET_RE = re.compile(r"password|passwd|pwd|secret|token|api[_-]?key|bearer", re.I)
BLOB_RE = re.compile(r"[A-Za-z0-9+/=_-]{32,}|\b[0-9a-fA-F]{24,}\b|\bsk-[A-Za-z0-9]{8,}")
from zoneinfo import ZoneInfo

def dynamic_tz(tz=None):
    name = tk.timezone_name(tz)
    if name != "local":
        try:
            return ZoneInfo(name)
        except Exception:
            pass
    resolved = tk.resolve_tz(tz)
    if resolved is not None:
        return resolved
    return dt.datetime.now().astimezone().tzinfo
CACHE_CTX = 100_000  # cache reads on a context above this are flagged
HAIKU_CTX_LIMIT = 150_000  # user's hard limit for Haiku: requests with a context above this are flagged
SLEEP_MIN_TURNS = 5

# Audit policy, not prices. TIER drives the subagent detector; SUPERSESSIONS says when a newer model shipped.
TIER = {
    "claude-opus-5-5": "premium", "claude-opus-5": "premium", "claude-opus-4-8": "premium",
    "claude-opus-4-7": "premium", "claude-opus-4-6": "premium", "claude-fable-5-1": "premium",
    "claude-sonnet-5-5": "mid", "claude-sonnet-5": "mid", "claude-sonnet-4-6": "mid",
    "gemini-3.1-pro": "mid", "gpt-6.1-sol": "mid",
    "claude-haiku-5-5": "cheap", "claude-haiku-4-5": "cheap", "gpt-6-luna": "cheap",
    "gemini-3.5-flash": "cheap", "gemini-3.6-flash": "cheap", "gemini-3.7-flash": "cheap",
    "gemini-3.8-flash": "cheap", "gemini-3.1-flash-lite": "cheap",
}
SUPERSESSIONS = [
    {"new": "claude-opus-5-5", "old": ["claude-opus-5", "claude-opus-4-8", "claude-opus-4-6"],
     "available_utc": "2026-09-22T18:53:00Z"},
    {"new": "claude-sonnet-5-5", "old": ["claude-sonnet-5", "claude-sonnet-4-6"],
     "available_utc": "2026-09-29T17:48:00Z"},
]


def norm_model(m):
    """Canonical model id. A bracket suffix such as '[1m]' is dropped first."""
    return tk.normalize_model((m or "").split("[")[0])


def usd(model, i, o, cr, cw5, cw1=0):
    """USD via canonical price(); None when pricing.json has no rate for the model."""
    if model not in RATES:
        return None
    return tk.price({"model": model, "in": i, "out": o, "cr": cr, "cw5m": cw5, "cw1h": cw1}, RATES)


def cr_above(model, ctx, cr):
    """USD of cache-read cost attributable to context above CACHE_CTX, at the rate the request was billed."""
    if model not in RATES or ctx <= CACHE_CTX:
        return 0.0
    return (ctx - CACHE_CTX) * (cr / ctx) * tk.rate_for(model, ctx, RATES)["cr"] / 1e6


def safe_snippet(text, n=80):
    if not text:
        return "(no user prompt recorded)"
    one = " ".join(text.split())
    if SECRET_RE.search(one) or BLOB_RE.search(one):
        return "[redacted]"
    return one[:n]


def short_proj(p):
    p = p.rstrip("/")
    p = re.sub(r"^-home-tankaizokuo-?", "~", p)
    p = re.sub(r"^-Code-", "Code/", p)
    return p[-38:] or "~"


def fmt(x):
    return f"{x:,.0f}"


class Msg:
    __slots__ = ("ts", "tool", "model", "sess", "proj", "i", "o", "cr", "cw5", "cw1", "usd", "side", "ctx", "id", "calls")


def load_omp(cut_ms, tmp):
    src = os.path.expanduser("~/.omp/stats.db")
    dst = os.path.join(tmp, "stats.db")
    for ext in ("", "-wal", "-shm"):
        if os.path.exists(src + ext):
            shutil.copy2(src + ext, dst + ext)
    c = sqlite3.connect(dst)
    c.row_factory = sqlite3.Row
    msgs = []
    for r in c.execute("select * from messages where timestamp>=? order by timestamp", (cut_ms,)):
        m = Msg()
        m.ts = dt.datetime.fromtimestamp(r["timestamp"] / 1000, dt.timezone.utc)
        m.tool = "omp"
        m.model = norm_model(r["model"])
        m.sess = r["session_file"]
        m.proj = r["folder"]
        m.i, m.o, m.cr, m.cw5, m.cw1 = r["input_tokens"], r["output_tokens"], r["cache_read_tokens"], r["cache_write_tokens"], 0
        m.usd = usd(m.model, m.i, m.o, m.cr, m.cw5, m.cw1)
        m.side = r["agent_type"] == "subagent"
        m.ctx = m.i + m.cr + m.cw5
        m.id = r["entry_id"]
        m.calls = []
        msgs.append(m)
    tools = collections.defaultdict(lambda: [0, 0])  # sess -> [calls, edits]
    for r in c.execute("select session_file, tool_name, count(*) n from tool_calls where timestamp>=? group by 1,2", (cut_ms,)):
        t = tools[r["session_file"]]
        t[0] += r["n"]
        if r["tool_name"] in EDIT_TOOLS:
            t[1] += r["n"]
    first = {}
    for r in c.execute("select session_file, prose from user_messages order by timestamp"):
        if r["session_file"] not in first and r["prose"]:
            first[r["session_file"]] = r["prose"]
    prompts = {k: safe_snippet(v) for k, v in first.items()}  # redact immediately; raw prose is not kept
    c.close()
    # sleep calls straight from the session JSONL (tool_calls table has no arguments)
    by_sess = collections.defaultdict(list)
    for m in msgs:
        by_sess[m.sess].append(m)
    for sf, ms in by_sess.items():
        if not os.path.exists(sf):
            continue
        ids = {m.id: m for m in ms}
        try:
            with open(sf, errors="ignore") as fh:
                for line in fh:
                    if "sleep" not in line:
                        continue
                    try:
                        j = json.loads(line)
                    except ValueError:
                        continue
                    m = ids.get(j.get("id"))
                    if not m:
                        continue
                    content = (j.get("message") or {}).get("content")
                    for b in content if isinstance(content, list) else []:
                        if b.get("type") == "toolCall" and b.get("name") == "bash":
                            if SLEEP_RE.search(str((b.get("arguments") or {}).get("command", ""))):
                                m.calls.append("sleep")
        except OSError:
            pass
    return msgs, tools, prompts


def user_text(j):
    m = j.get("message")
    if not isinstance(m, dict) or m.get("role") != "user" or j.get("isMeta"):
        return None
    c = m.get("content")
    if isinstance(c, str):
        t = c
    elif isinstance(c, list):
        if any(b.get("type") == "tool_result" for b in c if isinstance(b, dict)):
            return None
        t = " ".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
    else:
        return None
    t = t.strip()
    if not t or t.startswith(("<command-", "<local-command", "<system-reminder", "Caveat:")):
        return None
    return t


def load_cc(cut):
    msgs, seen = [], set()
    tools = collections.defaultdict(lambda: [0, 0])
    prompts, seen_tu = {}, set()
    base = os.path.expanduser("~/.claude/projects")
    for f in glob.glob(base + "/**/*.jsonl", recursive=True):
        try:
            if dt.datetime.fromtimestamp(os.path.getmtime(f), dt.timezone.utc) < cut:
                continue
            fh = open(f, errors="ignore")
        except OSError:
            continue
        proj = os.path.relpath(f, base).split(os.sep)[0]
        side_file = "/subagents/" in f
        by_id = {}
        with fh:
            for line in fh:
                try:
                    j = json.loads(line)
                except ValueError:
                    continue
                if f not in prompts:
                    t = user_text(j)
                    if t and not j.get("isSidechain") and not side_file:
                        prompts[f] = safe_snippet(t)
                m = j.get("message")
                if not isinstance(m, dict) or m.get("role") != "assistant":
                    continue
                ts_s = j.get("timestamp")
                if not ts_s:
                    continue
                ts = dt.datetime.fromisoformat(ts_s.replace("Z", "+00:00"))
                content = m.get("content") if isinstance(m.get("content"), list) else []
                names = []
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("id") not in seen_tu:
                        seen_tu.add(b.get("id"))
                        names.append((b.get("name"), str((b.get("input") or {}).get("command", ""))))
                        if ts >= cut:
                            tools[f][0] += 1
                            if b.get("name") in EDIT_TOOLS:
                                tools[f][1] += 1
                sleeps = any(n == "Bash" and SLEEP_RE.search(cmd) for n, cmd in names)
                key = (m.get("id"), j.get("requestId"))
                if key in by_id:  # later content block of the same request
                    if sleeps:
                        by_id[key].calls.append("sleep")
                    continue
                u = m.get("usage")
                if key in seen or not u or ts < cut:
                    continue
                seen.add(key)
                x = Msg()
                x.ts, x.tool, x.model = ts, "cc", norm_model(m.get("model"))
                x.sess, x.proj = f, proj
                if x.model == "<synthetic>":
                    continue
                cc = u.get("cache_creation") or {}
                w1 = cc.get("ephemeral_1h_input_tokens", 0)
                cw = u.get("cache_creation_input_tokens", 0)
                x.i, x.o, x.cr, x.cw1, x.cw5 = (u.get("input_tokens", 0), u.get("output_tokens", 0),
                                                u.get("cache_read_input_tokens", 0), w1, max(cw - w1, 0))
                x.usd = usd(x.model, x.i, x.o, x.cr, x.cw5, x.cw1)
                x.side = side_file or bool(j.get("isSidechain"))
                x.ctx = x.i + x.cr + cw
                x.id = key
                x.calls = ["sleep"] if sleeps else []
                by_id[key] = x
                msgs.append(x)
    return msgs, tools, prompts


def table(title, rows, head):
    print(f"\n== {title} ==")
    if not rows:
        print("(none)")
        return
    w = [max(len(str(x)) for x in col) for col in zip(head, *rows)]
    print("  ".join(str(h).ljust(w[i]) for i, h in enumerate(head)))
    for r in rows:
        print("  ".join(str(c).ljust(w[i]) for i, c in enumerate(r)))


LATEST = "~/.local/share/llm-cost-audit/latest.txt"


class Tee:
    # Mirror the text report to LATEST so other skills can display the last audit without re-running it.
    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            st.write(s)

    def flush(self):
        for st in self.streams:
            st.flush()


def window(days, now, tz):
    """The last `days` calendar days in the effective timezone, today included."""
    end = now.astimezone(tz).date()
    return end - dt.timedelta(days=days - 1), end


def sums(rows, key):
    """key -> [requests, INR] over canonical records."""
    g = collections.defaultdict(lambda: [0, 0.0])
    for r in rows:
        x = g[key(r)]
        x[0] += 1
        x[1] += r["cost"] * R
    return g


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=7, help="calendar days in the effective timezone, today included")
    ap.add_argument("--tz", default=None, help="timezone for day boundaries (default: canonical system zone)")
    ap.add_argument("--min-cost", type=float, default=100, help="INR threshold for the triage table")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.days < 1:
        ap.error("--days must be at least 1")
    if not a.json:
        latest = os.path.expanduser(LATEST)
        os.makedirs(os.path.dirname(latest), exist_ok=True)
        sys.stdout = Tee(sys.stdout, open(latest, "w", buffering=1))

    effective_tz = dynamic_tz(a.tz)
    now = dt.datetime.now(dt.timezone.utc)
    start, end = window(a.days, now, effective_tz)
    lo, hi = start.isoformat(), end.isoformat()
    tz = tk.timezone_name(effective_tz)
    pricing_doc = tk.load_pricing_doc(PRICING_PATH)
    version = pricing_doc["version"]

    # ---- headline money: canonical records, grouped by the same day the ledger cells use
    recs = [r for r in tk.collect(RATES, a.days + 2, SOURCES, tz=effective_tz) if lo <= r["day"] <= hi]
    state = {m: tk.model_status(m, RATES) for m in {r["model"] for r in recs}}  # True | False | "estimated"
    billed = [r for r in recs if state[r["model"]] is not False]
    unpriced = [r for r in recs if state[r["model"]] is False]
    priced_rows = [r for r in billed if state[r["model"]] is True]
    estimated_rows = [r for r in billed if state[r["model"]] == "estimated"]
    total_usd = sum(r["cost"] for r in billed)
    total_inr = total_usd * R
    unp_counts = collections.Counter(r["model"] for r in unpriced)

    src_sum = sums(billed, lambda r: r["source"])
    by_source = {s: round(src_sum[s][1]) for s in SOURCES}
    model_sum = sums(billed, lambda r: r["model"])
    by_model = {k: [v[0], round(v[1])] for k, v in sorted(model_sum.items(), key=lambda kv: -kv[1][1])}
    proj_sum = sums(billed, lambda r: (r["source"], r["project"]))
    by_project = {f"{TOOL[s]} {p}": round(v[1])
                  for (s, p), v in sorted(proj_sum.items(), key=lambda kv: -kv[1][1])[:12]}
    day_sum = sums(billed, lambda r: r["day"])
    by_day = {k: round(v[1]) for k, v in sorted(day_sum.items())}
    coverage = {
        "priced": {"requests": len(priced_rows), "cost_usd": round(sum(r["cost"] for r in priced_rows), 6)},
        "estimated": {"requests": len(estimated_rows), "cost_usd": round(sum(r["cost"] for r in estimated_rows), 6)},
        "unpriced": {"requests": len(unpriced)},
    }

    # spikes: days above 2x the median and above Rs 1000, with the largest driver of that day
    med = statistics.median([v[1] for v in day_sum.values()]) if day_sum else 0
    drivers = collections.defaultdict(collections.Counter)
    for r in billed:
        drivers[r["day"]][(r["source"], r["project"], r["model"])] += r["cost"] * R
    spikes = []
    for d in sorted(day_sum):
        v = day_sum[d][1]
        if v > max(2 * med, 1000):
            (s, pj, md), c0 = drivers[d].most_common(1)[0]
            spikes.append({"day": d, "inr": round(v), "ratio": round(v / med, 1) if med else None,
                           "driver": {"tool": TOOL[s], "project": pj, "model": md, "inr": round(c0)}})

    # ---- session analytics: omp stats.db and Claude Code JSONL, priced with the same canonical rates
    cut = dt.datetime.combine(start, dt.time.min, tzinfo=effective_tz)
    tmp = tempfile.mkdtemp(prefix="llm-audit-")
    try:
        om, ot, op = load_omp(int(cut.timestamp() * 1000), tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    cm, ct, cp = load_cc(cut)
    msgs = [m for m in om + cm if start <= m.ts.astimezone(effective_tz).date() <= end]
    tools = {**ot, **ct}
    prompts = {**op, **cp}
    priced = [m for m in msgs if m.usd is not None]
    inr = lambda m: m.usd * R

    sess = collections.defaultdict(lambda: {"inr": 0.0, "n": 0, "priced_n": 0, "unpriced_n": 0,
                                            "tool": "", "model": collections.Counter(),
                                            "models_count": collections.Counter(),
                                            "first": None, "proj": "", "side": False})
    for m in msgs:
        s = sess[m.sess]
        s["n"] += 1
        s["tool"] = m.tool
        s["first"] = min(s["first"] or m.ts, m.ts)
        s["proj"] = m.proj
        s["side"] = m.side
        s["models_count"][m.model] += 1
        if m.usd is not None:
            s["inr"] += inr(m)
            s["priced_n"] += 1
            s["model"][m.model] += inr(m)
        else:
            s["unpriced_n"] += 1

    def sess_top_model(s):
        if s["model"]:
            return s["model"].most_common(1)[0][0]
        if s["models_count"]:
            return s["models_count"].most_common(1)[0][0]
        return "unknown"
    # sleep-poll loops: sessions with >= SLEEP_MIN_TURNS sleep turns at >= 100k context
    sl = collections.defaultdict(lambda: [0, 0.0, 0])
    for m in priced:
        if m.calls and m.ctx >= 100_000:
            x = sl[m.sess]
            x[0] += 1
            x[1] += inr(m)
            x[2] = max(x[2], m.ctx)
    sleep_rows = [(sess[k]["first"].astimezone(effective_tz).strftime("%m-%d"), sess[k]["tool"], v[0], v[2] // 1000,
                   fmt(v[1]), short_proj(sess[k]["proj"]))
                  for k, v in sorted(sl.items(), key=lambda kv: -kv[1][1]) if v[0] >= SLEEP_MIN_TURNS][:8]
    sleep_total = sum(v[1] for v in sl.values() if v[0] >= SLEEP_MIN_TURNS)
    sleep_n = sum(v[0] for v in sl.values() if v[0] >= SLEEP_MIN_TURNS)

    cr_by_tool = collections.defaultdict(float)
    for m in priced:
        cr_by_tool[m.tool] += cr_above(m.model, m.ctx, m.cr) * R
    cr_total = sum(cr_by_tool.values())

    # Haiku requests over HAIKU_CTX_LIMIT, split by tool and main vs subagent
    hk = collections.defaultdict(lambda: {"sessions": set(), "requests": 0, "inr": 0.0, "max_ctx": 0})
    for m in priced:
        if "haiku" in m.model and m.ctx > HAIKU_CTX_LIMIT:
            h = hk[(m.tool, "subagent" if m.side else "main")]
            h["sessions"].add(m.sess)
            h["requests"] += 1
            h["inr"] += inr(m)
            h["max_ctx"] = max(h["max_ctx"], m.ctx)
    haiku_over = {}
    for (tl, side), h in sorted(hk.items()):
        haiku_over.setdefault(tl, {})[side] = {"sessions": len(h["sessions"]), "requests": h["requests"],
                                               "inr": round(h["inr"]), "max_ctx": h["max_ctx"]}

    # subagent sessions with no edits whose main model is premium or mid tier
    untiered = set()
    ro_total = 0.0
    ro_by_model = collections.defaultdict(float)
    for k, s in sess.items():
        if not s["side"] or tools.get(k, [0, 0])[1] != 0:
            continue
        top = sess_top_model(s)
        tier = TIER.get(top)
        if tier is None:
            untiered.add(top)
            continue
        if tier in ("premium", "mid"):
            ro_total += s["inr"]
            ro_by_model[(s["tool"], top)] += s["inr"]

    after_rows, after_total = [], 0.0
    for sup in SUPERSESSIONS:
        if sup["new"] not in RATES:
            sys.exit(f"supersession target {sup['new']} has no rate in pricing.json")
        av = dt.datetime.fromisoformat(sup["available_utc"].replace("Z", "+00:00"))
        for tl in ("omp", "cc"):
            ms = [m for m in priced if m.tool == tl and m.model in sup["old"] and m.ts >= av]
            if not ms:
                continue
            cur = sum(map(inr, ms))
            new = sum(usd(sup["new"], m.i, m.o, m.cr, m.cw5, m.cw1) * R for m in ms)
            after_rows.append((tl, "/".join(sorted({m.model for m in ms})), f"-> {sup['new']}", len(ms),
                               fmt(cur), fmt(new), fmt(cur - new)))
            after_total += cur - new

    tri = []
    for k, s in sess.items():
        if s["inr"] >= a.min_cost and tools.get(k, [0, 0])[1] == 0:
            tri.append((s["inr"], s["first"].astimezone(effective_tz).strftime("%m-%d"), s["tool"],
                        sess_top_model(s), tools.get(k, [0, 0])[0],
                        prompts.get(k, "(subagent / no prompt)" if s["side"] else "(no user prompt recorded)")))
    tri.sort(reverse=True)
    top5 = sorted(sess.items(), key=lambda kv: -kv[1]["inr"])[:5]

    out = {
        "range": {"start": lo, "end": hi, "days": a.days, "timezone": tz},
        "sources": list(SOURCES),
        "pricing": {
            "version": version,
            "filename": os.path.basename(PRICING_PATH),
            "source": os.path.basename(PRICING_PATH),
            "sources": pricing_doc.get("sources", {}),
            "models": len(RATES),
            "currency": CURRENCY,
        },
        "total_inr": round(total_inr),
        "total_usd": round(total_usd, 6),
        "by_source": by_source,
        "by_model": by_model,
        "by_project": by_project,
        "by_day": by_day,
        "coverage": coverage,
        "unpriced": dict(unp_counts),
        "spikes": spikes,
        "detectors": {
            "sleep_poll_inr": round(sleep_total), "sleep_turns": sleep_n,
            "cache_read_above_100k_inr": round(cr_total),
            "readonly_expensive_subagent_inr": round(ro_total),
            "old_model_after_availability_avoidable_inr": round(after_total),
            "untiered_models": sorted(untiered),
        },
        "haiku_over_limit": haiku_over,
        "triage": [dict(inr=round(t[0]), date=t[1], tool=t[2], model=t[3], tool_calls=t[4], prompt=t[5]) for t in tri],
        "top_sessions": [dict(inr=round(s["inr"]), tool=s["tool"], date=s["first"].astimezone(effective_tz).strftime("%m-%d"),
                              calls=s["n"], model=sess_top_model(s), project=short_proj(s["proj"]))
                         for _, s in top5],
        "session_analytics": {
            "sessions": len(sess),
            "requests": len(msgs),
            "inr": round(sum(s["inr"] for s in sess.values())),
            "priced_requests": len(priced),
            "unpriced_requests": len(msgs) - len(priced),
            "unpriced_sessions": sum(1 for s in sess.values() if s["priced_n"] == 0),
        },
        "min_cost": a.min_cost,
    }

    if a.json:
        json.dump(out, sys.stdout, indent=1)
        print()
        return

    print(f"LLM spend audit: {lo} to {hi} ({a.days} days, {tz}); sources: {', '.join(SOURCES)}")
    print(f"Pricing: canonical tokentrack pricing.json, version {version}, {R} INR per USD. "
          "Values are API-equivalent, not cash on a subscription.")
    print(f"\nTOTAL Rs {fmt(total_inr)}   " + "  ".join(f"{k}: Rs {fmt(v)}" for k, v in by_source.items()))
    print(f"coverage: priced {len(priced_rows)} requests Rs {fmt(coverage['priced']['cost_usd'] * R)}; "
          f"estimated {len(estimated_rows)} requests Rs {fmt(coverage['estimated']['cost_usd'] * R)}; "
          f"unpriced {len(unpriced)} requests (excluded, not Rs 0)")
    if unp_counts:
        print(f"unpriced (no rate in pricing.json, excluded): {dict(unp_counts)}")
    table("per model", [(k, v[0], fmt(v[1]), f"{v[1] / total_inr:.0%}" if total_inr else "-")
                        for k, v in model_sum.items()], ["model", "reqs", "Rs", "share"])
    table("per project (top 12)", [(k, fmt(v)) for k, v in by_project.items()], ["tool project", "Rs"])
    table("per day", [(k, fmt(v)) for k, v in by_day.items()], ["day", "Rs"])
    table("top 5 sessions (session analytics, priced)", [(fmt(s["inr"]), s["tool"], s["first"].astimezone(effective_tz).strftime("%m-%d"),
                                                 s["n"], sess_top_model(s), short_proj(s["proj"]))
                                                for _, s in top5], ["Rs", "tool", "date", "reqs", "model", "project"])
    table("spikes (day > 2x median and > Rs 1000)",
          [(s["day"], fmt(s["inr"]), f"{s['ratio']}x" if s["ratio"] else "-",
            f"{s['driver']['tool']} {s['driver']['project']} {s['driver']['model']} Rs{fmt(s['driver']['inr'])}")
           for s in spikes], ["day", "Rs", "vs median", "top driver"])
    print("\n== waste detectors (flags for review, not proof of waste) ==")
    print(f"sleep-poll loops (sessions with >={SLEEP_MIN_TURNS} sleep turns at >=100k ctx): {sleep_n} turns, "
          f"Rs {fmt(sleep_total)} floor (turn cost only)")
    for r in sleep_rows:
        print("   ", " | ".join(map(str, ("date " + r[0], r[1], f"{r[2]} turns", f"max ctx {r[3]}k", "Rs " + r[4], r[5]))))
    print(f"cache reads above 100k context: Rs {fmt(cr_total)}  ("
          + ", ".join(f"{k} Rs {fmt(v)}" for k, v in cr_by_tool.items()) + ")")
    print(f"Haiku over {HAIKU_CTX_LIMIT // 1000}k context:" + ("" if hk else "  (none)"))
    for (tl, side), h in sorted(hk.items()):
        print(f"   {tl} {side}: {len(h['sessions'])} sessions, {h['requests']} reqs, Rs {fmt(h['inr'])}, "
              f"max ctx {h['max_ctx'] // 1000}k")
    print(f"premium/mid models on subagent sessions with zero edit/write: Rs {fmt(ro_total)}  ("
          + ", ".join(f"{k[0]} {k[1]} Rs {fmt(v)}" for k, v in sorted(ro_by_model.items(), key=lambda kv: -kv[1])[:5]) + ")")
    if untiered:
        print(f"no tier for {', '.join(sorted(untiered))}; those subagent sessions were not classified")
    table("old-model use AFTER the newer model was available (avoidable part only)", after_rows,
          ["tool", "old model(s)", "new", "reqs", "paid Rs", "at new Rs", "avoidable Rs"])
    print(f"\n== TRIAGE: sessions >= Rs {fmt(a.min_cost)} with zero edit/write calls "
          f"({len(tri)} sessions, Rs {fmt(sum(t[0] for t in tri))}) ==")
    print("Judge research vs waste; prompts are redacted if they look like they contain secrets.")
    for t in tri:
        print(f"{t[1]}  {t[2]:<3}  {t[3]:<18} Rs {fmt(t[0]):>7}  calls {t[4]:>4}  | {t[5]}")
    if not tri:
        print("(none)")


if __name__ == "__main__":
    main()
