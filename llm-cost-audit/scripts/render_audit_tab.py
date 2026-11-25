#!/usr/bin/env python3
"""Rewrite the Audit tab of the Token Ledger HTML from an audit.py --json run.

usage: render_audit_tab.py <ledger.html> <audit.json> <notes.json|-> <out.html>

Money in the tab comes from audit.json. The parity check recomputes the same date range and
sources from the ledger's own DATA.cells, so any disagreement with the Overview is flagged, and
archived rows (logs deleted, kept from an older artifact) are shown as an explicit exclusion.
notes.json holds this audit's judgement text:
  {"findings": [["Label", "text"], ...],      # appended after the generated rows
   "suggestions": [["Title", "text"], ...],   # proposals, never applied
   "verdicts": {"<MM-DD>|<inr>": "research"|"waste"}}  # only verdicts the user gave
Only the block from '    <!-- Audit View -->' to the end of the content panel is replaced; the UI
and the DATA payload are left byte-for-byte alone.
"""
import collections
import html
import json
import sys

START = "    <!-- Audit View -->"
END = '\n\n  </div>\n</div>\n<div id="tip"'
DATA_MARK = "const DATA = "
SWATCHES = ["var(--warn)", "var(--accent)", "var(--ink-3)", "var(--chart-primary)", "var(--ok)", "var(--bad)"]
TOOLS = {"cc": "Claude Code", "omp": "omp"}
SOURCE_LABEL = {"omp": "omp", "claude-code": "Claude Code"}
PARITY_PCT = 1.0  # warn when the audit and the ledger cells differ by more than this


def e(s):
    return html.escape(str(s), quote=True)


def inr(n):
    """Rupees with Indian digit grouping: 2,93,104."""
    n = round(n)
    sign = "-" if n < 0 else ""
    s = str(abs(n))
    if len(s) <= 3:
        return f"₹{sign}{s}"
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return f"₹{sign}{','.join(parts)},{tail}"


def pretty_model(m):
    m = m.removeprefix("claude-")
    if m.startswith("gemini-") and "flash" in m:
        return "Gemini Flash"
    if m.startswith("gpt-"):
        ver, _, role = m[4:].partition("-")
        return f"GPT-{ver} {role.capitalize()}".strip()
    words = m.replace("-", " ").split()
    out, ver = [], []
    for w in words:
        (ver if w.isdigit() else out).append(w)
    name = " ".join(w if w.startswith("gpt") else w.capitalize() for w in out)
    return (name + " " + ".".join(ver)).strip()


def model_badge(m):
    tone = ' data-tone="accent"' if "opus" in m else ' data-tone="warn"' if "flash" in m else ""
    return f'<span class="badge"{tone}>{e(pretty_model(m))}</span>'


def spike_text(s):
    drv = s["driver"]
    ratio = f" ({s['ratio']}x median)" if s["ratio"] else ""
    tool = TOOLS.get(drv["tool"], drv["tool"])
    return f"{s['day']} {inr(s['inr'])}{ratio}, driver {tool} {drv['project']} {drv['model']} {inr(drv['inr'])}"


def extract_data(page):
    """The payload after 'const DATA = ' in a built page. Refuses the unbuilt template."""
    if page.count(DATA_MARK) != 1:
        sys.exit(f"expected exactly one '{DATA_MARK.strip()}' in the ledger, found {page.count(DATA_MARK)}")
    try:
        data, _ = json.JSONDecoder().raw_decode(page, page.index(DATA_MARK) + len(DATA_MARK))
    except ValueError as err:
        sys.exit(f"DATA is not a JSON payload ({err}); build the page before rendering the audit")
    return data


def is_archived(row):
    return len(row) > 10 and bool(row[10])


def cells_side(data, rng, sources):
    """The audit's range and sources, recomputed from DATA.cells. Archived rows are kept apart."""
    models = data.get("models")
    pricing = (data.get("pricing") or {}).get("models")
    if models is None and pricing is None:
        sys.exit("DATA has neither models nor pricing.models; cannot tell priced cells from unpriced ones")

    def status(model, archived=False):
        if models is not None and model in models:
            m_info = models[model]
            if archived and "archived_priced" in m_info:
                st = m_info["archived_priced"]
            else:
                st = m_info.get("priced")
        elif pricing is not None:
            st = model in pricing
        else:
            st = False
        if st not in (True, False, "estimated"):
            sys.exit(f"unknown priced status {st!r} for model {model}")
        return st

    rows = [c for c in data["cells"] if rng["start"] <= c[0] <= rng["end"] and c[1] in sources]
    unpriced = collections.Counter()
    live, arch, est, pri = [], [], [], []
    for c in rows:
        archived = is_archived(c)
        st = status(c[2], archived=archived)
        if archived:
            arch.append(c)
        else:
            live.append(c)
            if st is False:
                unpriced[c[2]] += c[4]
            elif st == "estimated":
                est.append(c)
            else:
                pri.append(c)

    def usd(cs):
        return sum(c[9] for c in cs)

    return {
        "live_usd": usd(live),
        "archived_usd": usd(arch),
        "archived_rows": len(arch),
        "archived_requests": sum(c[4] for c in arch),
        "priced_usd": usd(pri),
        "priced_requests": sum(c[4] for c in pri),
        "estimated_usd": usd(est),
        "estimated_requests": sum(c[4] for c in est),
        "unpriced": dict(unpriced),
    }


def discrepancy_pct(audit_usd, cells_usd):
    if cells_usd == 0:
        return 0.0 if audit_usd == 0 else float("inf")
    return 100 * abs(audit_usd - cells_usd) / cells_usd


def main():
    ledger, audit_path, notes_path, out = sys.argv[1:5]
    page = open(ledger, encoding="utf-8").read()
    a = json.load(open(audit_path, encoding="utf-8"))
    notes = {} if notes_path == "-" else json.load(open(notes_path, encoding="utf-8"))
    if page.count(START) != 1 or page.count(END) != 1:
        sys.exit("audit block markers not found exactly once; page layout changed, not writing")
    i, j = page.index(START), page.index(END)
    data = extract_data(page)

    rng, sources = a["range"], a["sources"]
    period = f"{rng['start']} → {rng['end']}"
    days, tz = rng["days"], rng["timezone"]
    pricing = a["pricing"]
    pricing_cur = (data.get("pricing") or {}).get("currency")
    if pricing_cur is None:
        sys.exit("DATA.pricing.currency is missing; cannot convert the cells to INR, not writing")
    per_usd = pricing_cur["per_usd"]  # pricing currency, not the display currency --usd/--rate can override
    if per_usd != pricing["currency"]["per_usd"]:
        sys.exit(f"audit used {pricing['currency']['per_usd']} INR per USD, ledger pricing uses {per_usd}; "
                 "rerun the audit after the build, not writing")

    cells = cells_side(data, rng, sources)
    gap = discrepancy_pct(a["total_usd"], cells["live_usd"])
    data_tz = data.get("timezone")
    tz_ok = data_tz is None or data_tz == tz
    payload_version = (data.get("pricing") or {}).get("version")
    version_ok = payload_version is None or payload_version == pricing["version"]
    warn = gap > PARITY_PCT or not version_ok or not tz_ok
    pct_txt = "no ledger cells" if gap == float("inf") else f"{gap:.2f}%"
    cells_inr = cells["live_usd"] * per_usd
    all_inr = (cells["live_usd"] + cells["archived_usd"]) * per_usd
    omp = a["by_source"].get("omp", 0)
    cc = a["by_source"].get("claude-code", 0)
    total = a["total_inr"]
    src_label = " + ".join(SOURCE_LABEL.get(s, s) for s in sources)
    cov = a["coverage"]
    unpriced = a["unpriced"]
    sa = a["session_analytics"]

    models = sorted(a["by_model"].items(), key=lambda kv: -kv[1][1])
    shares = [(m, round(100 * v[1] / total)) for m, v in models if total]
    top_m, top_share = shares[0] if shares else ("-", 0)

    proj = sorted(a["by_project"].items(), key=lambda kv: -kv[1])
    top_p, top_p_inr = proj[0] if proj else ("none", 0)
    top_p_tool, _, top_p_name = top_p.partition(" ")
    top_p_share = round(100 * top_p_inr / total) if total else 0

    d = a["detectors"]
    review = d["readonly_expensive_subagent_inr"] + d["cache_read_above_100k_inr"] + d["sleep_poll_inr"]
    tri = a["triage"]
    tri_inr = sum(t["inr"] for t in tri)
    min_cost = a["min_cost"]
    verdicts = notes.get("verdicts", {})
    pending = sum(1 for t in tri if f'{t["date"]}|{t["inr"]}' not in verdicts)

    by_day = a["by_day"]
    peak_day = max(by_day, key=by_day.get) if by_day else None
    spikes = a["spikes"]
    top = a["top_sessions"]

    mix_segs = "".join(
        f'<div class="share-bar-seg" style="flex:{s};background:{SWATCHES[k % len(SWATCHES)]}"></div>'
        for k, (_, s) in enumerate(shares))
    mix_legend = "".join(
        f'<span class="legend-item"><span class="audit-swatch" style="background:{SWATCHES[k % len(SWATCHES)]}"></span>'
        f'{e(pretty_model(m))} <span class="legend-value">{s}</span></span>'
        for k, (m, s) in enumerate(shares))
    mix_label = ", ".join(f"{pretty_model(m)} {s}" for m, s in shares) + " percent"

    if warn:
        if not tz_ok:
            parity_msg = f"timezone mismatch: audit is {tz}, ledger is {data_tz or 'unset'}; days cut differently"
        elif not version_ok:
            parity_msg = "pricing version differs from the ledger payload"
        else:
            parity_msg = f"audit differs {pct_txt} from ledger cells"
        parity_badge = f'<span class="badge" data-tone="warn" data-mono="true">Warning: {e(parity_msg)}</span>'
    else:
        parity_badge = f'<span class="badge" data-tone="ok" data-mono="true">Matches ledger cells ({pct_txt})</span>'

    excl = []
    if cells["archived_rows"]:
        excl.append(f"{cells['archived_rows']} archived ledger rows ({inr(cells['archived_usd'] * per_usd)}, "
                    f"{cells['archived_requests']:,} requests) restored from an older artifact; their logs are gone, "
                    "so they are not in the audit total and cannot be re-checked")
    for m, n in sorted(unpriced.items()):
        excl.append(f"{m}: {n:,} requests with no rate in pricing.json, excluded and shown as unpriced, not ₹0")
    excl_txt = "; ".join(excl) if excl else "none in range"

    if not tz_ok:
        parity_txt = (f"Audit timezone ({tz}) differs from ledger ({data_tz or 'unset'}); "
                      f"day boundaries are incompatible, parity check cannot be verified without re-bucketing.")
    else:
        parity_txt = (f"Recheckable audit subtotal {inr(total)} against ledger nonarchive cells {inr(cells_inr)} for the same range and sources "
                      f"(archived rows excluded from parity check): difference {pct_txt}"
                      + (", above 1%, check before trusting these figures" if warn else ", within 1%")
                      + f". Inclusive canonical Overview total for the same range: {inr(all_inr)}"
                      + (f" (including {cells['archived_rows']} archived rows totaling {inr(cells['archived_usd'] * per_usd)})" if cells["archived_rows"] else "")
                      + ".")

    if spikes:
        spike_txt = "; ".join(spike_text(s) for s in spikes)
    elif peak_day:
        spike_txt = f"none above 2x median and ₹1,000. Busiest day {peak_day} at {inr(by_day[peak_day])}."
    else:
        spike_txt = "no ledger days in range."

    rows = [
        ("Range and sources", f"{period}, {days} calendar days in {tz}. Sources: {src_label}. "
                              "Days are calendar days, the same grouping as the ledger cells."),
        ("Pricing", f"tokentrack pricing.json version {pricing['version']}; {per_usd} INR per USD; "
                    f"{pricing['models']} models. Canonical rates only, no separate price table."),
        ("Spend", f"{inr(all_inr)} Overview total in range ({inr(total)} recheckable audit subtotal: omp {inr(omp)}, Claude Code {inr(cc)}"
                  + (f"; plus {inr(cells['archived_usd'] * per_usd)} archived" if cells["archived_rows"] else "")
                  + f"). Top project: {top_p_name} ({TOOLS.get(top_p_tool, top_p_tool)}) at {inr(top_p_inr)}, {top_p_share}%."),
        ("Coverage", f"priced {inr(cov['priced']['cost_usd'] * per_usd)} over {cov['priced']['requests']:,} requests; "
                     f"estimated {inr(cov['estimated']['cost_usd'] * per_usd)} over {cov['estimated']['requests']:,} requests; "
                     f"unpriced {cov['unpriced']['requests']:,} requests."),
        ("Exclusions", excl_txt),
        ("Parity", parity_txt),
        ("Model mix", ", ".join(f"{pretty_model(m)} {s}%" for m, s in shares)
                      + f". Avoidable old-model spend after a newer model shipped: "
                        f"{inr(d['old_model_after_availability_avoidable_inr'])}."),
    ]
    if top:
        lo, hi = min(t["inr"] for t in top), max(t["inr"] for t in top)
        t0 = top[0]
        rows.append(("Biggest sessions",
                     f"top {len(top)} sessions {inr(lo)}–{inr(hi)}. Largest: {pretty_model(t0['model'])} in "
                     f"{TOOLS.get(t0['tool'], t0['tool'])} on {t0['date']}, {t0['calls']} requests, {inr(t0['inr'])}."))
    rows.append(("Session logs", f"{sa['sessions']} sessions and {sa['requests']:,} requests, {inr(sa['inr'])}. "
                                 "Triage, detectors and top sessions read these logs; they are not the headline total."))
    sleep_txt = "none" if not d["sleep_turns"] else f"{inr(d['sleep_poll_inr'])} over {d['sleep_turns']} turns"
    rows.append(("Needs review", f"flags for the user to judge, not proof of waste. Subagent sessions with no edits on "
                                 f"premium or mid models {inr(d['readonly_expensive_subagent_inr'])}. Cache reads above "
                                 f"100k context {inr(d['cache_read_above_100k_inr'])}. Sleep-poll loops: {sleep_txt}. "
                                 "The detectors can overlap, so their sum is an upper bound."))
    if d.get("untiered_models"):
        rows.append(("Tier gaps", "no tier in the audit for " + ", ".join(d["untiered_models"])
                                  + "; subagent sessions on those models were not classified."))
    rows.append(("Spike", spike_txt))
    rows += [tuple(r) for r in notes.get("findings", [])]

    li = "\n".join(f'          <li><span class="audit-row-label">{e(k)}</span><span class="audit-row-text">{e(v)}</span></li>'
                   for k, v in rows)
    sugg = notes.get("suggestions", [])
    callouts = "\n".join(
        f'          <li class="callout"><span class="callout-num">{n}</span><div class="callout-body">'
        f'<div class="callout-title">{e(t)}</div><div class="callout-text">{e(x)}</div></div></li>'
        for n, (t, x) in enumerate(sugg, 1)) or '          <li class="callout"><div class="callout-body"><div class="callout-text">None this week.</div></div></li>'

    tmax = max((t["inr"] for t in tri), default=1)
    trs = []
    for t in tri:
        p = t.get("prompt") or "(subagent)"
        if p.startswith("(subagent"):
            p = "(subagent)"
        v = verdicts.get(f'{t["date"]}|{t["inr"]}', "open")
        vt = ' data-tone="bad"' if v == "waste" else ' data-tone="ok"' if v == "research" else ""
        trs.append(
            f'          <tr><td class="mono">{e(t["date"])}</td>'
            f'<td><span class="tool-chip" data-tool="{e(t["tool"])}"><span class="tool-dot"></span>{e(TOOLS.get(t["tool"], t["tool"]))}</span></td>'
            f'<td>{model_badge(t["model"])}</td>'
            f'<td data-align="right" class="num"><div class="meter-cell"><span>{inr(t["inr"])}</span>'
            f'<span class="meter" aria-hidden="true"><span class="meter-fill" style="width:{100 * t["inr"] / tmax:.1f}%"></span></span></div></td>'
            f'<td data-align="right" class="num">{t["tool_calls"]}</td>'
            f'<td class="prompt-cell"><span class="prompt-text" title="{e(p)}">{e(p)}</span></td>'
            f'<td><span class="badge"{vt}>{e(v)}</span></td></tr>')

    src_title = e(src_label)
    block = f"""    <!-- Audit View -->
    <div id="view-audit" class="view-section audit-view" hidden>
      <div class="audit-strip">
        <span class="badge" data-tone="accent" data-mono="true">Audit period {e(period)}</span>
        <span class="badge" data-mono="true">{days} days · {e(tz)}</span>
        <span class="badge" data-mono="true">Sources: {src_title}</span>
        <span class="badge" data-mono="true">Pricing {e(pricing['version'])}</span>
        {parity_badge}
      </div>
      <div class="stat-grid audit-stats" id="audit-findings">
        <div class="stat">
          <div class="stat-label">Spend</div>
          <div class="stat-value">{inr(all_inr)}</div>
          <div class="share-bar" role="img" aria-label="omp {inr(omp)} and Claude Code {inr(cc)}">
            <div class="share-bar-seg" style="flex:{omp};background:var(--chart-primary)"></div>
            <div class="share-bar-seg" style="flex:{cc};background:var(--chart-secondary)"></div>
          </div>
          <div class="stat-foot">{e(f"Overview {inr(all_inr)} · recheckable audit {inr(total)} (omp {inr(omp)}, Claude Code {inr(cc)})" + (f" · archived {inr(cells['archived_usd'] * per_usd)}" if cells["archived_rows"] else ""))}</div>
        </div>
        <div class="stat">
          <div class="stat-label">Top project</div>
          <div class="stat-value">{top_p_share}%</div>
          <div class="meter" aria-hidden="true"><div class="meter-fill" style="width:{top_p_share}%"></div></div>
          <div class="stat-foot">{e(top_p_name)} · {e(TOOLS.get(top_p_tool, top_p_tool))} · {inr(top_p_inr)}</div>
        </div>
        <div class="stat">
          <div class="stat-label">Model mix</div>
          <div class="stat-value">{top_share}%</div>
          <div class="share-bar" role="img" aria-label="{e(mix_label)}">
            {mix_segs}
          </div>
          <div class="legend">
            {mix_legend}
          </div>
        </div>
        <div class="stat">
          <div class="stat-label">Needs review</div>
          <div class="stat-value audit-bad">{inr(review)}</div>
          <div class="stat-foot">subagents with no edits {inr(d['readonly_expensive_subagent_inr'])} · cache reads above 100k {inr(d['cache_read_above_100k_inr'])} · sleep-poll {inr(d['sleep_poll_inr'])}; detectors can overlap</div>
        </div>
        <div class="stat">
          <div class="stat-label">Edit-free triage</div>
          <div class="stat-value">{inr(tri_inr)}</div>
          <div class="stat-foot">{len(tri)} sessions at or above {inr(min_cost)}, {pending} awaiting a verdict</div>
        </div>
      </div>
      <div class="card" id="recent-findings">
        <div class="card-header">
          <div class="card-titles">
            <div class="card-title">Recent findings</div>
            <div class="card-description">Audit of {e(period)} ({days} days, {e(src_label)}). Totals are API-equivalent value, not cash.</div>
          </div>
        </div>
        <div class="card-body">
          <ul class="audit-rows">
{li}
          </ul>
        </div>
      </div>
      <div class="card" id="suggestions">
        <div class="card-header">
          <div class="card-titles">
            <div class="card-title">Suggested changes (not applied)</div>
            <div class="card-description">Proposals only. Nothing here has been applied.</div>
          </div>
        </div>
        <div class="card-body">
          <ul class="callout-list">
{callouts}
          </ul>
        </div>
      </div>
      <div class="card" id="triage">
        <div class="card-header">
          <div class="card-titles">
            <div class="card-title">Triage: edit-free sessions ≥ {inr(min_cost)}</div>
            <div class="card-description">{len(tri)} sessions, {inr(tri_inr)} total. A session with no edits can be successful research; verdicts are the user's call.</div>
          </div>
        </div>
        <div class="card-body" data-flush="true">
          <div class="table-wrap">
            <table class="table audit-table" data-dense="true">
              <thead><tr><th>Date</th><th>Tool</th><th>Model</th><th data-align="right">₹</th><th data-align="right">Calls</th><th>Prompt (redacted)</th><th>Verdict</th></tr></thead>
              <tbody>
{chr(10).join(trs)}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>"""

    open(out, "w", encoding="utf-8").write(page[:i] + block + page[j:])
    print(f"audit tab: {period}, {inr(total)}, parity {pct_txt}{' WARNING' if warn else ''}, "
          f"{len(tri)} triage rows, {len(sugg)} suggestions -> {out}")


if __name__ == "__main__":
    main()
