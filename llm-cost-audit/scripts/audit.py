#!/usr/bin/env python3
"""Read-only LLM spend audit over omp (~/.omp/stats.db + session JSONL) and Claude Code (~/.claude/projects JSONL).

Costs are recomputed from raw tokens with prices.json; stored costs are ignored.
Nothing is written except a temp copy of stats.db, which is deleted on exit.
"""
import argparse, collections, datetime as dt, glob, json, os, re, shutil, sqlite3, statistics, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PR = json.load(open(os.path.join(HERE, "..", "prices.json")))
R = PR["usd_inr"]
MODELS = PR["models"]
CW = PR["cache_write_mult"]
EDIT_TOOLS = {"edit", "write", "Edit", "Write", "MultiEdit", "NotebookEdit"}
SLEEP_RE = re.compile(r"\bsleep\s+\d")
SECRET_RE = re.compile(r"password|passwd|pwd|secret|token|api[_-]?key|bearer", re.I)
BLOB_RE = re.compile(r"[A-Za-z0-9+/=_-]{32,}|\b[0-9a-fA-F]{24,}\b|\bsk-[A-Za-z0-9]{8,}")
LOCAL_TZ = dt.datetime.now().astimezone().tzinfo


def norm_model(m):
    m = (m or "?").split("[")[0]
    for p in PR["model_aliases"]["prefixes_stripped"]:
        if m.startswith(p):
            m = m[len(p):]
    for s in PR["model_aliases"]["suffixes_stripped"]:
        if m.endswith(s):
            m = m[: -len(s)]
    m = re.sub(r"(claude-[a-z]+-\d)\.(\d)", r"\1-\2", m)  # opus-5.5 -> opus-5-5
    m = re.sub(r"-20\d{6}$", "", m)
    return m


def cost_usd(model, i, o, cr, cw5, cw1=0):
    p = MODELS.get(model)
    if not p:
        return None
    m = p.get("cache_write_mult")
    w5, w1 = (CW["5m"], CW["1h"]) if m is None else (m, m)
    return (i * p["in"] + o * p["out"] + cr * p["cache_read"] + cw5 * p["in"] * w5 + cw1 * p["in"] * w1) / 1e6


def cr_above(model, ctx, cr, thresh=100_000):
    """USD of cache-read cost attributable to context above thresh."""
    p = MODELS.get(model)
    if not p or ctx <= thresh or ctx == 0:
        return 0.0
    return (ctx - thresh) * (cr / ctx) * p["cache_read"] / 1e6


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
        m.usd = cost_usd(m.model, m.i, m.o, m.cr, m.cw5)
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
        except OSError:
            continue
        proj = os.path.relpath(f, base).split(os.sep)[0]
        side_file = "/subagents/" in f
        by_id = {}
        try:
            fh = open(f, errors="ignore")
        except OSError:
            continue
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
                key = (m.get("id"), j.get("requestId"))
                u = m.get("usage")
                if key in seen or not u or ts < cut:
                    if key in by_id:
                        by_id[key].calls += [n for n, cmd in names if n == "Bash" and SLEEP_RE.search(cmd)] and ["sleep"] or []
                    continue
                seen.add(key)
                x = Msg()
                x.ts, x.tool, x.model = ts, "cc", norm_model(m.get("model"))
                x.sess, x.proj = f, proj
                cc = u.get("cache_creation") or {}
                w1 = cc.get("ephemeral_1h_input_tokens", 0)
                cw = u.get("cache_creation_input_tokens", 0)
                x.i, x.o, x.cr, x.cw1, x.cw5 = u.get("input_tokens", 0), u.get("output_tokens", 0), u.get("cache_read_input_tokens", 0), w1, max(cw - w1, 0)
                if x.model == "<synthetic>":
                    continue
                x.usd = cost_usd(x.model, x.i, x.o, x.cr, x.cw5, x.cw1)
                x.side = side_file or bool(j.get("isSidechain"))
                x.ctx = x.i + x.cr + cw
                x.id = key
                x.calls = ["sleep"] if any(n == "Bash" and SLEEP_RE.search(cmd) for n, cmd in names) else []
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


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--min-cost", type=float, default=100, help="INR threshold for the triage table")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    now = dt.datetime.now(dt.timezone.utc)
    cut = now - dt.timedelta(days=a.days)
    tmp = tempfile.mkdtemp(prefix="llm-audit-")
    try:
        om, ot, op = load_omp(int(cut.timestamp() * 1000), tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    cm, ct, cp = load_cc(cut)
    msgs = om + cm
    tools = {**ot, **ct}
    prompts = {**op, **cp}
    priced = [m for m in msgs if m.usd is not None]
    unpriced = collections.Counter(m.model for m in msgs if m.usd is None)
    inr = lambda m: m.usd * R
    total = sum(map(inr, priced))
    day = lambda m: m.ts.astimezone(LOCAL_TZ).strftime("%Y-%m-%d")
    out = {"window_days": a.days, "since": cut.isoformat(), "total_inr": round(total), "unpriced_msgs": dict(unpriced)}

    def group(key):
        g = collections.defaultdict(lambda: [0, 0.0])
        for m in priced:
            x = g[key(m)]
            x[0] += 1
            x[1] += inr(m)
        return sorted(g.items(), key=lambda kv: -kv[1][1])

    sess = collections.defaultdict(lambda: {"inr": 0.0, "n": 0, "tool": "", "model": collections.Counter(), "first": None, "proj": "", "side": False, "ctxmax": 0})
    for m in priced:
        s = sess[m.sess]
        s["inr"] += inr(m); s["n"] += 1; s["tool"] = m.tool; s["model"][m.model] += inr(m)
        s["first"] = min(s["first"] or m.ts, m.ts); s["proj"] = m.proj; s["side"] = m.side; s["ctxmax"] = max(s["ctxmax"], m.ctx)

    d_tool = {k: round(v[1]) for k, v in group(lambda m: m.tool)}
    out["by_tool"] = d_tool
    out["by_model"] = {k: [v[0], round(v[1])] for k, v in group(lambda m: m.model)}
    out["by_project"] = {k: round(v[1]) for k, v in group(lambda m: (m.tool, short_proj(m.proj)))[:15]} if False else None
    days = sorted(group(lambda m: day(m)), key=lambda kv: kv[0])
    out["by_day"] = {k: round(v[1]) for k, v in days}

    # ---- spikes: days > 2x median and > Rs 1000
    dv = [v[1] for _, v in days]
    med = statistics.median(dv) if dv else 0
    spikes = []
    for k, v in days:
        if v[1] > max(2 * med, 1000):
            ms = [m for m in priced if day(m) == k]
            drv = collections.Counter()
            for m in ms:
                drv[(m.tool, short_proj(m.proj), m.model)] += inr(m)
            (tl, pj, md), c0 = drv.most_common(1)[0]
            spikes.append((k, fmt(v[1]), f"{v[1]/med:.1f}x" if med else "-", f"{tl} {pj} {md} Rs{fmt(c0)}"))
    out["spikes"] = [list(s) for s in spikes]

    # ---- detectors
    sleep_turns = [m for m in priced if m.calls and m.ctx >= 100_000]
    sl = collections.defaultdict(lambda: [0, 0.0, 0])
    for m in sleep_turns:
        x = sl[m.sess]; x[0] += 1; x[1] += inr(m); x[2] = max(x[2], m.ctx)
    sleep_rows = [(s[0][-2:] if False else (sess[k]["first"].astimezone(LOCAL_TZ).strftime("%m-%d")), sess[k]["tool"], v[0], v[2] // 1000, fmt(v[1]), short_proj(sess[k]["proj"]))
                  for k, v in sorted(sl.items(), key=lambda kv: -kv[1][1]) if v[0] >= 5 for s in [("",)]][:8]
    sleep_total = sum(v[1] for v in sl.values() if v[0] >= 5)
    sleep_n = sum(v[0] for v in sl.values() if v[0] >= 5)

    cr_by_tool = collections.defaultdict(float)
    for m in priced:
        cr_by_tool[m.tool] += cr_above(m.model, m.ctx, m.cr) * R
    cr_total = sum(cr_by_tool.values())

    ro_rows, ro_total = [], 0.0
    for k, s in sess.items():
        if not s["side"]:
            continue
        top = s["model"].most_common(1)[0][0]
        if MODELS[top]["tier"] != "premium" and MODELS[top]["tier"] != "mid":
            continue
        if tools.get(k, [0, 0])[1] == 0:
            ro_total += s["inr"]
    ro_by_model = collections.defaultdict(float)
    for k, s in sess.items():
        if s["side"] and tools.get(k, [0, 0])[1] == 0:
            top = s["model"].most_common(1)[0][0]
            if MODELS[top]["tier"] in ("premium", "mid"):
                ro_by_model[(s["tool"], top)] += s["inr"]

    after_rows, after_total = [], 0.0
    for sup in PR["supersessions"]:
        av = dt.datetime.fromisoformat(sup["available_utc"].replace("Z", "+00:00"))
        for tl in ("omp", "cc"):
            ms = [m for m in priced if m.tool == tl and m.model in sup["old"] and m.ts >= av]
            if not ms:
                continue
            cur = sum(map(inr, ms))
            new = sum(cost_usd(sup["new"], m.i, m.o, m.cr, m.cw5, m.cw1) * R for m in ms)
            after_rows.append((tl, "/".join(sorted({m.model for m in ms})), f"-> {sup['new']}", len(ms), fmt(cur), fmt(new), fmt(cur - new)))
            after_total += cur - new

    # ---- triage
    tri = []
    for k, s in sess.items():
        if s["inr"] >= a.min_cost and tools.get(k, [0, 0])[1] == 0:
            tri.append((s["inr"], s["first"].astimezone(LOCAL_TZ).strftime("%m-%d"), s["tool"], s["model"].most_common(1)[0][0],
                        tools.get(k, [0, 0])[0], prompts.get(k, "(subagent / no prompt)" if s["side"] else "(no user prompt recorded)")))
    tri.sort(reverse=True)
    out["triage"] = [dict(inr=round(t[0]), date=t[1], tool=t[2], model=t[3], tool_calls=t[4], prompt=t[5]) for t in tri]
    out["detectors"] = {"sleep_poll_inr": round(sleep_total), "sleep_turns": sleep_n, "cache_read_above_100k_inr": round(cr_total),
                        "readonly_expensive_subagent_inr": round(ro_total), "old_model_after_availability_avoidable_inr": round(after_total)}
    top5 = sorted(sess.items(), key=lambda kv: -kv[1]["inr"])[:5]
    out["top_sessions"] = [dict(inr=round(s["inr"]), tool=s["tool"], date=s["first"].astimezone(LOCAL_TZ).strftime("%m-%d"), calls=s["n"], model=s["model"].most_common(1)[0][0], project=short_proj(s["proj"])) for _, s in top5]
    pj = group(lambda m: (m.tool, short_proj(m.proj)))[:12]
    out["by_project"] = {f"{k[0]} {k[1]}": round(v[1]) for k, v in pj}

    if a.json:
        json.dump(out, sys.stdout, indent=1)
        print()
        return

    print(f"LLM spend audit: last {a.days} day(s) since {cut.astimezone(LOCAL_TZ):%Y-%m-%d %H:%M}; {len(priced)} priced requests, {len(sess)} sessions")
    print(f"Caveat: Rs is API-equivalent value at {R}/USD recomputed from raw tokens; it may not be cash if you are on a subscription.")
    print(f"\nTOTAL Rs {fmt(total)}   " + "  ".join(f"{k}: Rs {fmt(v)}" for k, v in d_tool.items()))
    if unpriced:
        print("unpriced (not in prices.json, excluded):", dict(unpriced))
    table("per model", [(k, v[0], fmt(v[1]), f"{v[1]/total:.0%}" if total else "-") for k, v in group(lambda m: m.model)], ["model", "reqs", "Rs", "share"])
    table("per project (top 12)", [(k[0], k[1], v[0], fmt(v[1])) for k, v in pj], ["tool", "project", "reqs", "Rs"])
    table("per day", [(k, v[0], fmt(v[1])) for k, v in days], ["day", "reqs", "Rs"])
    table("top 5 sessions", [(fmt(s["inr"]), s["tool"], s["first"].astimezone(LOCAL_TZ).strftime("%m-%d"), s["n"], s["model"].most_common(1)[0][0], short_proj(s["proj"])) for _, s in top5], ["Rs", "tool", "date", "reqs", "model", "project"])
    table("spikes (day > 2x median and > Rs 1000)", spikes, ["day", "Rs", "vs median", "top driver"])
    print("\n== waste detectors ==")
    print(f"sleep-poll loops (sessions with >=5 sleep turns at >=100k ctx): {sleep_n} turns, Rs {fmt(sleep_total)} floor (turn cost only)")
    for r in sleep_rows:
        print("   ", " | ".join(map(str, ("date " + r[0], r[1], f"{r[2]} turns", f"max ctx {r[3]}k", "Rs " + r[4], r[5]))))
    print(f"cache reads above 100k context: Rs {fmt(cr_total)}  (" + ", ".join(f"{k} Rs {fmt(v)}" for k, v in cr_by_tool.items()) + ")")
    print(f"premium/mid models on subagent sessions with zero edit/write: Rs {fmt(ro_total)}  (" + ", ".join(f"{k[0]} {k[1]} Rs {fmt(v)}" for k, v in sorted(ro_by_model.items(), key=lambda kv: -kv[1])[:5]) + ")")
    table("old-model use AFTER the newer model was available (avoidable part only)", after_rows, ["tool", "old model(s)", "new", "reqs", "paid Rs", "at new Rs", "avoidable Rs"])
    print(f"\n== TRIAGE: sessions >= Rs {fmt(a.min_cost)} with zero edit/write calls ({len(tri)} sessions, Rs {fmt(sum(t[0] for t in tri))}) ==")
    print("Judge research vs waste; prompts are redacted if they look like they contain secrets.")
    for t in tri:
        print(f"{t[1]}  {t[2]:<3}  {t[3]:<18} Rs {fmt(t[0]):>7}  calls {t[4]:>4}  | {t[5]}")
    if not tri:
        print("(none)")


if __name__ == "__main__":
    main()
