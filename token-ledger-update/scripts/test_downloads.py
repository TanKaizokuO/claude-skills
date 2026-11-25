import time, json, sys
from playwright.sync_api import sync_playwright
import os
S = os.environ.get("SHOT_DIR", ".")  # where screenshots go
PAGE_PATH = os.path.abspath(os.environ.get("PAGE", "artifact-page.html"))
URL = os.environ.get("PAGE_URL") or "file://" + PAGE_PATH
# Allowed request prefixes: local file/data/blob, plus the page origin when PAGE_URL is http.
ALLOW = ("file://", "data:", "blob:") + ((URL.rsplit("/", 1)[0] + "/",) if URL.startswith("http") else ())
KEYS = list("1234567890")
INIT = """
window.__saved = [];
window.claude = { use: async function (n) { return n === 'downloads' ? { save: async function (r) {
  window.__saved.push({filename: r.filename, size: (r.data.size ?? r.data.length)});
  return {status: 'saved'};
} } : null; } };
"""
failures = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond: failures.append(msg)

def has_button(pg, label):
    # buttons carry an emoji icon in text; match the accessible name (aria-label) instead
    return pg.evaluate("label => [...document.querySelectorAll('button')].some(b => (b.getAttribute('aria-label') || '') === label)", label)

def find_view(pg, label):
    for k in KEYS:
        pg.keyboard.press(k); time.sleep(2.5)
        if has_button(pg, label):
            return k
    return None

def click_button(pg, label):
    loc = pg.get_by_role("button", name=label, exact=True).first
    try:
        loc.scroll_into_view_if_needed(timeout=3000)
        loc.click(timeout=5000)
    except Exception as e:
        print("  real click failed, using DOM click:", str(e)[:120].replace("\n", " "), flush=True)
        loc.evaluate("e => e.click()")

def saved(pg):
    return pg.evaluate("window.__saved || []")

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    # ---- with mocked window.claude ----
    ctx = b.new_context(viewport={"width": 1400, "height": 900}, accept_downloads=True)
    netreqs = []
    def route(r):
        u = r.request.url
        if u.startswith(ALLOW): return r.continue_()
        netreqs.append(u); return r.abort()
    ctx.route("**/*", route)
    ctx.add_init_script(INIT)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append("pageerror: " + str(e)[:200]))
    pg.on("console", lambda m: errors.append("console: " + m.text[:200]) if m.type == "error" else None)
    pg.goto(URL, wait_until="load"); time.sleep(4)

    # The app defines DataTable's "Export CSV" button, but no page renders DataTable (also true in the real app),
    # so no view has it. Probe the CSV save path with a blob: CSV anchor instead.
    view = find_view(pg, "Export CSV")
    print(f"INFO: 'Export CSV' button in any view: key {view} (DataTable is not rendered by any page)", flush=True)
    before = len(saved(pg))
    pg.evaluate("""() => { const b = new Blob(['a,b\\n1,2\\n'], {type: 'text/csv'}); const a = document.createElement('a');
      a.href = URL.createObjectURL(b); a.download = 'token_export.csv'; document.body.appendChild(a); a.click(); a.remove(); }""")
    try:
        pg.wait_for_function("(window.__saved||[]).length >= %d" % (before + 1), timeout=8000)
    except Exception:
        pass
    new = saved(pg)[before:]
    check(len(new) == 1, f"one save from a blob CSV anchor (got {len(new)})")
    check(bool(new) and new[0]["filename"].endswith(".csv"), f"CSV save filename .csv: {new[0]['filename'] if new else None}")
    check(bool(new) and new[0]["size"] > 0, f"CSV save size > 0: {new[0]['size'] if new else None}")

    view = find_view(pg, "Export chart image")
    check(view is not None, f"found a view with a chart 'Export chart image' button (key {view})")
    if view:
        before = len(saved(pg))
        click_button(pg, "Export chart image")
        try:
            pg.wait_for_function("(window.__saved||[]).length >= %d" % (before + 1), timeout=8000)
        except Exception:
            pass
        new = saved(pg)[before:]
        check(len(new) == 1, f"one save after chart Export (got {len(new)})")
        check(bool(new) and new[0]["filename"].endswith(".png"), f"PNG save filename .png: {new[0]['filename'] if new else None}")
        check(bool(new) and new[0]["size"] > 0, f"PNG save size > 0: {new[0]['size'] if new else None}")

    # capture-phase listener path: a real dispatched click on a download anchor (no patched click())
    before = len(saved(pg))
    pg.evaluate("""() => { const a = document.createElement('a'); a.href = 'data:text/plain,hello';
      a.download = 'probe.txt'; document.body.appendChild(a);
      a.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true})); a.remove(); }""")
    try:
        pg.wait_for_function("(window.__saved||[]).length >= %d" % (before + 1), timeout=5000)
    except Exception:
        pass
    new = saved(pg)[before:]
    check(len(new) == 1 and new[0]["filename"] == "probe.txt" and new[0]["size"] == 5,
          f"listener path saves data: anchor as probe.txt size 5 (got {new})")
    check(not errors, f"no page errors with window.claude ({errors[:3]})")
    check(not netreqs, f"no external requests ({len(netreqs)})")
    ctx.close()

    # ---- without window.claude: page loads, no errors ----
    ctx2 = b.new_context(viewport={"width": 1400, "height": 900})
    ctx2.route("**/*", lambda r: r.continue_() if r.request.url.startswith(ALLOW) else r.abort())
    pg2 = ctx2.new_page()
    errs2 = []
    pg2.on("pageerror", lambda e: errs2.append(str(e)[:200]))
    pg2.on("console", lambda m: errs2.append("console: " + m.text[:200]) if m.type == "error" else None)
    pg2.goto(URL, wait_until="load"); time.sleep(4)
    has_claude = pg2.evaluate("typeof window.claude")
    check(has_claude == "undefined", f"no window.claude in plain context (typeof={has_claude})")
    check(not errs2, f"no page errors without window.claude ({errs2[:3]})")
    ctx2.close()
    b.close()

print("RESULT:", "ALL PASS" if not failures else f"{len(failures)} FAILED")
