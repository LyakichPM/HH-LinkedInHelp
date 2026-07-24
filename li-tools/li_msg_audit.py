# -*- coding: utf-8 -*-
"""Audit LinkedIn conversations via the FULL messaging page (not the dock).
Dumps the conversation list (names + snippets), then opens the first
conversation matching each given name and dumps its full message history."""
import sys, io
from playwright.sync_api import sync_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PROFILE = r"C:\Users\Ilya\.claude\hh-agent\li_profile"
OUT = sys.argv[1]
NAMES = sys.argv[2:]  # names to open, e.g. "First Last" "FirstName"

p = sync_playwright().start()
ctx = p.chromium.launch_persistent_context(
    PROFILE, channel="chrome", headless=True, locale="en-US",
    viewport={"width": 1600, "height": 1200},
    args=["--disable-blink-features=AutomationControlled"],
    ignore_default_args=["--enable-automation"],
)
page = ctx.pages[0] if ctx.pages else ctx.new_page()
buf = []

page.goto("https://www.linkedin.com/messaging/", wait_until="domcontentloaded", timeout=45000)
page.wait_for_timeout(5000)

# conversation list items
convs = page.locator('li.msg-conversation-listitem, li[class*="conversation-listitem"]')
n = convs.count()
buf.append(f"=== CONVERSATION LIST ({n} items) ===")
for i in range(min(n, 25)):
    try:
        t = convs.nth(i).inner_text(timeout=1000).replace("\n", " | ")
        buf.append(f"[{i}] {t[:300]}")
    except Exception as e:
        buf.append(f"[{i}] ERR {str(e)[:80]}")

for name in NAMES:
    buf.append(f"\n=== OPEN THREAD: {name} ===")
    opened = False
    for i in range(min(n, 25)):
        try:
            t = convs.nth(i).inner_text(timeout=1000)
        except Exception:
            continue
        if name.lower() in t.lower():
            convs.nth(i).click()
            page.wait_for_timeout(3000)
            opened = True
            break
    if not opened:
        buf.append("NOT FOUND in conversation list")
        continue
    # scroll thread up to load history
    try:
        ml = page.locator('.msg-s-message-list-container, [class*="message-list"]').first
        for _ in range(6):
            ml.evaluate("el => el.scrollTop = 0")
            page.wait_for_timeout(500)
    except Exception:
        pass
    try:
        body = page.locator('.msg-s-message-list-container, [class*="message-list"]').first.inner_text(timeout=5000)
    except Exception as e:
        body = f"ERR reading thread: {str(e)[:120]}"
    buf.append(body)

with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(buf))
page.screenshot(path=OUT + ".png")
ctx.close()
p.stop()
print("done, wrote", OUT, flush=True)
