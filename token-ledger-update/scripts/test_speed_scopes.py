import time, os, re
from playwright.sync_api import sync_playwright
import os
S = os.environ.get("SHOT_DIR", ".")  # where screenshots go
PAGE_PATH = os.path.abspath(os.environ.get("PAGE", "artifact-page.html"))
URL = os.environ.get("PAGE_URL") or "file://" + PAGE_PATH
# Allowed request prefixes: local file/data/blob, plus the page origin when PAGE_URL is http.
ALLOW = ("file://", "data:", "blob:") + ((URL.rsplit("/", 1)[0] + "/",) if URL.startswith("http") else ())
BANNER = "Not in the offline snapshot"
SCOPES = ["Combined", "Claude", "OMP"]
GRAINS = ["hour", "week", "month", "day"]
failures = []

def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond: failures.append(msg)

def misses(pg):
    return pg.evaluate("window.__offlineMisses || []")

# Sets the grain select (the select whose options include "Month") through the value setter plus a bubbling change event.
SET_GRAIN_JS = """g => {
  const s = [...document.querySelectorAll('select')].find(s => [...s.options].some(o => o.text === 'Month'));
  if (!s) return 'nosel';
  const o = [...s.options].find(o => o.text.toLowerCase() === g);
  if (!o) return 'noopt';
  const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;
  set.call(s, o.value);
  s.dispatchEvent(new Event('change', { bubbles: true }));
  return s.value;
}"""

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1400, "height": 900})
    netreqs = []
    def route(r):
        u = r.request.url
        if u.startswith(ALLOW): return r.continue_()
        netreqs.append(u); return r.abort()
    ctx.route("**/*", route)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)[:200]))
    pg.goto(URL, wait_until="load"); time.sleep(3)

    # ---- scope tabs on the Speed view ----
    for scope in SCOPES:
        pg.keyboard.press("4"); time.sleep(2)
        before = len(misses(pg))
        try:
            pg.get_by_role("tab", name=scope, exact=True).first.click(timeout=3000)
            clicked = True
        except Exception as e:
            clicked = str(e)[:120]
        time.sleep(2.5)
        txt = pg.evaluate("document.body.innerText")
        after = len(misses(pg))
        check(clicked is True and BANNER not in txt and after == before,
              f"speed scope={scope} tab click={clicked is True} banner={BANNER in txt} misses {before}->{after}")

    # ---- grain selector x scope (Combined, Claude, OMP) ----
    for scope in SCOPES:
        pg.keyboard.press("4"); time.sleep(2)
        try:
            pg.get_by_role("tab", name=scope, exact=True).first.click(timeout=3000)
        except Exception as e:
            print("scope click failed", scope, str(e)[:100], flush=True)
        time.sleep(2)
        for g in GRAINS:
            before = len(misses(pg))
            res = pg.evaluate(SET_GRAIN_JS, g)
            time.sleep(2.5)
            txt = pg.evaluate("document.body.innerText")
            after = len(misses(pg))
            ok = (res not in ("nosel", "noopt")) and BANNER not in txt and after == before
            check(ok, f"grain scope={scope} grain={g} select={res!r} banner={BANNER in txt} misses {before}->{after}")

    # ---- Harness Comparison: OMP sessions ----
    pg.keyboard.press("8"); time.sleep(3)
    htxt = pg.evaluate("document.body.innerText")
    omp_zero = [l for l in htxt.splitlines() if "OMP" in l and re.search(r"\b0 sessions\b", l)]
    has_2767 = "2,767" in htxt
    snippet = [l for l in htxt.splitlines() if "OMP" in l or "ession" in l][:8]
    print("harness OMP/session lines:", [s[:120] for s in snippet], flush=True)
    check(has_2767 and not omp_zero, f"harness OMP sessions show 2,767 (found={has_2767}) and no '0 sessions' for OMP (lines={len(omp_zero)})")

    print("page errors", errors[:5], flush=True)
    check(not errors, f"speed/harness page errors ({len(errors)})")
    check(not netreqs, f"speed/harness external requests ({len(netreqs)})")
    print("total snapshot misses", len(misses(pg)), misses(pg)[:3], flush=True)
    b.close()

print("RESULT:", "ALL PASS" if not failures else f"{len(failures)} FAILED", flush=True)
