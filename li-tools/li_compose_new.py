# -*- coding: utf-8 -*-
"""Start a NEW conversation via the full messaging page compose flow
(avoids the floating dock entirely - it silently reuses wrong panels).

Usage: li_compose_new.py <recipient_query> <expect_name_token> <msg_file> [dry]

- opens /messaging/, clicks the compose (new message) button
- types recipient_query into the recipient typeahead, picks the suggestion
  containing expect_name_token
- verifies the recipient pill/chip contains expect_name_token before typing
"""
import sys, io, re, time, json
from playwright.sync_api import sync_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PROFILE = r"C:\Users\Ilya\.claude\hh-agent\li_profile"
QUERY = sys.argv[1]
EXPECT = sys.argv[2].lower()
MSG_FILE = sys.argv[3]
DRY = "dry" in sys.argv[4:]
PICK = None  # extra substring the suggestion row must contain (disambiguation)
for f in sys.argv[4:]:
    if f.startswith("pick="):
        PICK = f[5:].lower()

with io.open(MSG_FILE, "r", encoding="utf-8") as f:
    MESSAGE = f.read().strip()

p = sync_playwright().start()
ctx = p.chromium.launch_persistent_context(
    PROFILE, channel="chrome", headless=True, locale="en-US",
    viewport={"width": 1600, "height": 1200},
    args=["--disable-blink-features=AutomationControlled"],
    ignore_default_args=["--enable-automation"],
)
page = ctx.pages[0] if ctx.pages else ctx.new_page()
status = {"query": QUERY, "expect": EXPECT, "ok": False, "step": "start", "dry": DRY}
try:
    page.goto("https://www.linkedin.com/messaging/thread/new/", wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(5000)
    status["step"] = "new-thread compose opened"

    # recipient typeahead
    field = None
    for sel in ['input[placeholder*="Введите имя"]', 'input[placeholder*="Type a name"]',
                '.msg-connections-typeahead__search-field']:
        loc = page.locator(sel)
        for i in range(loc.count()):
            try:
                if loc.nth(i).is_visible():
                    field = loc.nth(i)
                    break
            except Exception:
                continue
        if field:
            break
    if field is None:
        raise Exception("recipient typeahead input not found")
    field.click()
    field.type(QUERY, delay=60)
    page.wait_for_timeout(3500)
    status["step"] = "typed recipient query"

    # suggestions
    sugg = None
    seen = []
    for sel in ['.msg-connections-typeahead__search-results li',
                'ul[role="listbox"] li', 'div[role="option"]', 'li[role="option"]',
                'div[class*="selectable-entity"]', 'li[class*="selectable-entity"]',
                '.msg-connections-typeahead li']:
        for el in page.locator(sel).all():
            try:
                if not el.is_visible():
                    continue
                t = (el.inner_text() or "").replace("\n", " ").strip()
                if not t:
                    continue
                seen.append(t[:80])
                tl = t.lower()
                if EXPECT in tl and (PICK is None or PICK in tl) and sugg is None:
                    sugg = el
            except Exception:
                continue
        if sugg is not None:
            break
    status["suggestions"] = seen[:10]
    if sugg is None:
        raise Exception(f"no suggestion containing {EXPECT!r}")
    sugg.click()
    page.wait_for_timeout(1500)
    status["step"] = "recipient selected"

    # verify the recipient now appears in the compose/detail area
    # (the pane shows a loading spinner for a while after the click - poll)
    pill_txt = ""
    deadline = time.time() + 25
    while time.time() < deadline:
        for sel in ['.msg-connections-typeahead__added-recipients',
                    '[class*="added-recipient"]', '[class*="pill"]',
                    '.scaffold-layout__detail']:
            try:
                t = page.locator(sel).first.inner_text(timeout=2000).replace("\n", " ")
            except Exception:
                continue
            if EXPECT in t.lower():
                pill_txt = t
                break
        if pill_txt:
            break
        page.wait_for_timeout(1500)
    if not pill_txt:
        try:
            pill_txt = page.locator('.scaffold-layout__detail').first.inner_text(timeout=3000).replace("\n", " ")
        except Exception:
            pass
    status["recipient_pill"] = pill_txt[:200]
    if EXPECT not in pill_txt.lower():
        raise Exception(f"compose detail area does not contain {EXPECT!r}: {pill_txt[:120]!r}")

    box = page.locator('div.msg-form__contenteditable[role="textbox"], .msg-form div[role="textbox"][contenteditable="true"]').first
    box.wait_for(state="visible", timeout=10000)
    box.click()
    page.wait_for_timeout(300)
    lines = MESSAGE.split("\n")
    for li_i, line in enumerate(lines):
        if line:
            page.keyboard.insert_text(line)
        if li_i < len(lines) - 1:
            page.keyboard.press("Shift+Enter")
    page.wait_for_timeout(800)
    typed = box.inner_text().strip()
    if len(typed) < len(MESSAGE) * 0.7:
        raise Exception(f"typed too short ({len(typed)}/{len(MESSAGE)})")
    status["step"] = "typed message"

    if DRY:
        status["typed_text"] = typed[:150]
        status["step"] = "dry-run: typed, NOT sent"
        status["ok"] = True
    else:
        send_btn = None
        for el in page.locator('.msg-form button, form button').all():
            try:
                if not el.is_visible():
                    continue
                txt = (el.inner_text() or "").strip().lower()
                cls = el.get_attribute("class") or ""
                if txt in ("отправить", "send", "verzenden") or "msg-form__send-button" in cls or "msg-form__send-btn" in cls:
                    send_btn = el
                    break
            except Exception:
                continue
        if send_btn is None:
            raise Exception("send button not found")
        send_btn.click()
        page.wait_for_timeout(3000)
        leftover = box.inner_text().strip()
        status["leftover_in_box"] = leftover[:80]
        if leftover:
            raise Exception("compose box still has text after send - FAILED")
        try:
            body = page.locator('.msg-s-message-list-container').first.inner_text(timeout=5000)
            status["sent_text_in_thread"] = MESSAGE[:60] in body
        except Exception:
            status["sent_text_in_thread"] = "unknown"
        status["step"] = "sent"
        status["ok"] = True
except Exception as e:
    status["error"] = str(e)

page.screenshot(path="compose_" + re.sub(r"\W", "", EXPECT)[:12] + ".png")
ctx.close()
p.stop()
print(json.dumps(status, ensure_ascii=False), flush=True)
