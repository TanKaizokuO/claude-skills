import time
from playwright.sync_api import sync_playwright
import os
S = os.environ.get("SHOT_DIR", ".")  # where screenshots go
PAGE_PATH = os.path.abspath(os.environ.get("PAGE", "artifact-page.html"))
URL = os.environ.get("PAGE_URL") or "file://" + PAGE_PATH
# Allowed request prefixes: local file/data/blob, plus the page origin when PAGE_URL is http.
ALLOW = ("file://", "data:", "blob:") + ((URL.rsplit("/", 1)[0] + "/",) if URL.startswith("http") else ())
netreqs = []
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1400, "height": 900})
    def route(r):
        u = r.request.url
        if u.startswith(ALLOW):
            return r.continue_()
        netreqs.append(u); return r.abort()
    ctx.route("**/*", route)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)[:200]))
    pg.on("console", lambda m: errors.append("console:" + m.text[:200]) if m.type == "error" else None)
    pg.goto(URL, wait_until="load"); time.sleep(4)
    names = {"1":"overview","2":"models","3":"tokens","4":"speed","5":"providers","6":"projects","7":"sessions","8":"harness","9":"efficiency","0":"reports"}
    for k, n in names.items():
        if k != "1": pg.keyboard.press(k); time.sleep(2.5)
        pg.screenshot(path=f"{S}/" + __import__("os").environ.get("SHOT", "offline") + f"-{n}.png")
        txt = pg.evaluate("document.body.innerText")
        print(n, "chars", len(txt), "has $3,670:", "3,670" in txt, "has 3,50,736:", "3,50,736" in txt, "unpriced mentions:", txt.count("Unpriced"))
    misses = pg.evaluate("window.__offlineMisses || []")
    print("snapshot misses:", len(misses), misses[:5])
    print("external network requests blocked:", len(netreqs), netreqs[:5])
    print("errors:", errors[:6])
    b.close()
