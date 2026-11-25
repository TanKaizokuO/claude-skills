import time, re, sys
from playwright.sync_api import sync_playwright
import os
S = os.environ.get("SHOT_DIR", ".")  # where screenshots go
PAGE_PATH = os.path.abspath(os.environ.get("PAGE", "artifact-page.html"))
URL = os.environ.get("PAGE_URL") or "file://" + PAGE_PATH
# Allowed request prefixes: local file/data/blob, plus the page origin when PAGE_URL is http.
ALLOW = ("file://", "data:", "blob:") + ((URL.rsplit("/", 1)[0] + "/",) if URL.startswith("http") else ())
page_file = sys.argv[1]
with sync_playwright() as p:
    b = p.chromium.launch(headless=True); ctx = b.new_context(viewport={"width":1400,"height":900})
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(ALLOW) else r.abort())
    pg = ctx.new_page(); pg.goto(URL if URL.startswith("http") else "file://" + os.path.abspath(page_file), wait_until="load"); time.sleep(4)
    for key, label in [("1","overview"), ("5","providers")]:
        pg.keyboard.press(key); time.sleep(3)
        txt = pg.evaluate("document.body.innerText")
        hits = [m for m in re.findall(r"[^\n]{0,50}(?:₹|INR|3,670|3670|349|3,49)[^\n]{0,40}", txt) if "pricing.json" not in m]
        print(label, hits[:6])
    b.close()
