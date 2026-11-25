"""Range dropdown check for the offline snapshot.

Overview, scope Combined: selects each of Last 24 Hours, Last 7 Days, Last 30 Days, All History
in #filter-preset and records the TOTAL TOKENS and REQUESTS headline numbers and delta badges.
PASS needs: exactly those 4 options; totals all different; 24h <= 7d <= 30d <= All (tokens and
requests); no "Not in the offline snapshot" banner; no POST /api/v1/query entries in
window.__offlineMisses. Then Models, Tokens & Cache, Speed and Projects are visited once on 7d;
their misses are reported (not a failure).

Env: PAGE (single html, file:// mode) or PAGE_URL (http page URL, e.g. http://127.0.0.1:PORT/index.html),
SHOT_DIR for screenshots. Exit 0 on PASS, 1 on FAIL.
"""
import os, re, sys, time
from playwright.sync_api import sync_playwright

S = os.environ.get("SHOT_DIR", ".")
PAGE_PATH = os.path.abspath(os.environ.get("PAGE", "artifact-page.html"))
URL = os.environ.get("PAGE_URL") or "file://" + PAGE_PATH
ALLOW = ("file://", "data:", "blob:") + ((URL.rsplit("/", 1)[0] + "/",) if URL.startswith("http") else ())
BANNER = "Not in the offline snapshot"
RANGES = [("24h", "Last 24 Hours"), ("7d", "Last 7 Days"), ("30d", "Last 30 Days"), ("all", "All History")]
OTHER = [("2", "models"), ("3", "tokens"), ("4", "speed"), ("6", "projects")]
failures = []

def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        failures.append(msg)

def to_num(s):
    if not s:
        return None
    m = re.search(r"(\d[\d,]*\.?\d*)\s*([KMBkmb]?)", s)
    if not m:
        return None
    return float(m.group(1).replace(",", "")) * {"": 1, "k": 1e3, "m": 1e6, "b": 1e9}[m.group(2).lower()]

KPI_JS = """() => {
  const cards = [...document.querySelectorAll('.kpi-card')];
  const get = (name) => {
    const c = cards.find(c => (c.querySelector('.kpi-header span') || {}).textContent?.trim() === name);
    if (!c) return null;
    const d = c.querySelector('.kpi-delta');
    return { value: c.querySelector('.kpi-value')?.textContent.trim() ?? null, delta: d ? d.textContent.trim() : null };
  };
  return { tokens: get('Total Tokens'), requests: get('Requests & Sessions') };
}"""
CHANGED_JS = """prev => { const c = [...document.querySelectorAll('.kpi-card')].find(c => (c.querySelector('.kpi-header span') || {}).textContent?.trim() === 'Total Tokens');
  const v = c && c.querySelector('.kpi-value'); return !!v && v.textContent.trim() !== prev; }"""

def misses(pg):
    return pg.evaluate("window.__offlineMisses || []")

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1400, "height": 900})
    netreqs = []
    def route(r):
        u = r.request.url
        if u.startswith(ALLOW):
            return r.continue_()
        netreqs.append(u)
        return r.abort()
    ctx.route("**/*", route)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)[:200]))
    pg.on("console", lambda m: errors.append("console:" + m.text[:200]) if m.type == "error" else None)
    pg.goto(URL, wait_until="load")
    time.sleep(4)
    try:
        pg.get_by_role("tab", name="Combined", exact=True).first.click(timeout=3000)
        print("scope tab Combined clicked", flush=True)
    except Exception as e:
        print("scope tab Combined not clicked:", str(e)[:120], flush=True)
    time.sleep(2)

    txt0 = pg.evaluate("document.body.innerText")
    # innerText applies the CSS uppercase transform, so compare case-insensitively.
    check("total tokens" in txt0.lower(), "Overview headline tiles rendered on load")
    opts = pg.eval_on_selector_all("#filter-preset option", "els => els.map(e => [e.value, e.textContent.trim()])")
    check(opts == [[k, l] for k, l in RANGES], f"range dropdown options exactly 4: {opts}")

    cur = pg.evaluate("document.querySelector('#filter-preset').value")
    prev_tokens = (pg.evaluate(KPI_JS) or {}).get("tokens") or {}
    prev_val = prev_tokens.get("value")
    print(f"initial preset={cur} tokens={prev_val}", flush=True)

    rows = {}
    for key, label in RANGES:
        pg.evaluate("document.activeElement && document.activeElement.blur()")
        before = len(misses(pg))
        if cur != key:
            pg.select_option("#filter-preset", value=key)
            try:
                pg.wait_for_function(CHANGED_JS, arg=prev_val, timeout=180000)
            except Exception as e:
                print(f"wait for change timed out on {key}: {str(e)[:100]}", flush=True)
            cur = key
        time.sleep(4)
        kp = pg.evaluate(KPI_JS)
        txt = pg.evaluate("document.body.innerText")
        after = misses(pg)
        tok = (kp.get("tokens") or {})
        req = (kp.get("requests") or {})
        rows[key] = {"label": label, "tokens": tok.get("value"), "tokens_delta": tok.get("delta"),
                     "requests": req.get("value"), "requests_delta": req.get("delta")}
        prev_val = tok.get("value")
        pg.screenshot(path=f"{S}/range-{key}.png")
        check(BANNER not in txt, f"{key}: no offline banner")
        check(len(after) == before or all(not m.startswith("POST /api/v1/query") for m in after[before:]),
              f"{key}: no new POST /api/v1/query misses (misses {before}->{len(after)})")
        print(f"  {label}: TOTAL TOKENS={rows[key]['tokens']} ({rows[key]['tokens_delta']}) "
              f"REQUESTS={rows[key]['requests']} ({rows[key]['requests_delta']})", flush=True)

    tok_vals = [rows[k]["tokens"] for k, _ in RANGES]
    req_vals = [rows[k]["requests"] for k, _ in RANGES]
    check(len(set(tok_vals)) == 4 and all(tok_vals), f"TOTAL TOKENS all different: {tok_vals}")
    check(len(set(req_vals)) == 4 and all(req_vals), f"REQUESTS all different: {req_vals}")
    tn = [to_num(v) for v in tok_vals]
    rn = [to_num(v) for v in req_vals]
    check(None not in tn and all(tn[i] <= tn[i + 1] for i in range(3)), f"tokens 24h<=7d<=30d<=All: {tn}")
    check(None not in rn and all(rn[i] <= rn[i + 1] for i in range(3)), f"requests 24h<=7d<=30d<=All: {rn}")
    post_misses = [m for m in misses(pg) if m.startswith("POST /api/v1/query")]
    check(not post_misses, f"window.__offlineMisses has no POST /api/v1/query entries ({len(post_misses)})")

    # Other pages on 7d
    # Each other page on every range. Go back to Overview (key 1) before changing the range,
    # because the Total Tokens KPI the change-wait reads only exists on Overview.
    for rkey, rlabel in RANGES:
        if cur != rkey:
            pg.keyboard.press("1"); time.sleep(3)
            prev_now = ((pg.evaluate(KPI_JS) or {}).get("tokens") or {}).get("value")
            pg.select_option("#filter-preset", value=rkey)
            try:
                pg.wait_for_function(CHANGED_JS, arg=prev_now, timeout=180000)
            except Exception as e:
                print(f"wait for change timed out on {rkey}: {str(e)[:100]}", flush=True)
            cur = rkey
            time.sleep(4)
        for pkey, pname in OTHER:
            pg.evaluate("document.activeElement && document.activeElement.blur()")
            before = len(misses(pg))
            pg.keyboard.press(pkey)
            time.sleep(4)
            txt = pg.evaluate("document.body.innerText")
            new = misses(pg)[before:]
            pg.screenshot(path=f"{S}/range-{rkey}-{pname}.png")
            check(BANNER not in txt, f"{rkey} {pname}: no offline banner")
            check(not any(m.startswith("POST /api/v1/query") for m in new),
                  f"{rkey} {pname}: no POST /api/v1/query misses ({len(new)} new)")
            print(f"  {rkey} page {pname}: new misses={len(new)} {[m[:80] for m in new[:3]]}", flush=True)
        pg.keyboard.press("1"); time.sleep(2)

    all_misses = misses(pg)
    print("all misses at end:", len(all_misses), all_misses[:10], flush=True)
    print("external network requests blocked:", len(netreqs), netreqs[:5], flush=True)
    print("errors:", errors[:6], flush=True)
    check(not netreqs, "no external network requests")
    check(not errors, "no page errors")
    b.close()

print("TOTALS (tokens / requests):")
for k, l in RANGES:
    print(f"  {l}: {rows[k]['tokens']} / {rows[k]['requests']}")
print("RESULT: " + ("PASS" if not failures else "FAIL (%d)" % len(failures)), flush=True)
sys.exit(1 if failures else 0)
