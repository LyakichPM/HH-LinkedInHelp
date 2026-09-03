# -*- coding: utf-8 -*-
"""Reply in an EXISTING conversation via the full messaging page
(https://www.linkedin.com/messaging/), with optional file attachment.

Usage: li_reply_thread.py <name_token> <msg_file> [attach=<path>] [dry]

Safer than the floating dock: the conversation is clicked by name in the
list, and the thread header is verified to contain the name before typing.
"""
import os
import sys, io, re, time, json
from playwright.sync_api import sync_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def _dir(name, env):
    """Каталог рядом с репозиторием; путь не зашит, логина ОС в коде нет."""
    return os.environ.get(env) or os.path.join(_ROOT, name)

PROFILE = _dir("li_profile", "LI_PROFILE")
NAME = sys.argv[1]
MSG_FILE = sys.argv[2]
ATTACH = None
DRY = False
for f in sys.argv[3:]:
    if f.startswith("attach="):
        ATTACH = f[7:]
    if f == "dry":
        DRY = True

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
status = {"name": NAME, "ok": False, "step": "start", "dry": DRY}
try:
    page.goto("https://www.linkedin.com/messaging/", wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(5000)

    convs = page.locator('li.msg-conversation-listitem, li[class*="conversation-listitem"]')
    opened = False
    for i in range(min(convs.count(), 30)):
        try:
            t = convs.nth(i).inner_text(timeout=1000)
        except Exception:
            continue
        if NAME.lower() in t.lower():
            convs.nth(i).click()
            page.wait_for_timeout(3000)
            opened = True
            break
    if not opened:
        raise Exception(f"conversation matching {NAME!r} not found in list")
    status["step"] = "conversation opened"

    # ownership: thread header must contain the name
    head = ""
    for sel in ['.msg-entity-lockup', '.msg-thread', 'h2']:
        try:
            head = page.locator(sel).first.inner_text(timeout=3000).replace("\n", " ")
            if head:
                break
        except Exception:
            continue
    status["thread_header"] = head[:150]
    if NAME.lower() not in head.lower():
        raise Exception(f"thread header does not contain {NAME!r}: {head[:100]!r}")

    box = page.locator('div.msg-form__contenteditable[role="textbox"], .msg-form div[role="textbox"][contenteditable="true"]').first
    box.wait_for(state="visible", timeout=10000)

    if ATTACH:
        fname = ATTACH.replace("\\", "/").split("/")[-1][:20]
        # a previous dry run may have left the attachment as a draft
        try:
            pre = page.locator('.msg-form, form').first.inner_text(timeout=2000)
        except Exception:
            pre = ""
        if fname.lower() in pre.lower():
            status["attachment_already_present"] = True
        else:
            finputs = page.locator('input[type="file"]')
            n = finputs.count()
            status["file_inputs"] = n
            if n == 0:
                raise Exception("no file input found for attachment")
            done = False
            for i in range(n):
                try:
                    finputs.nth(i).set_input_files(ATTACH)
                    done = True
                    break
                except Exception:
                    continue
            if not done:
                raise Exception("could not set attachment on any file input")
        # wait for the attachment chip to appear
        deadline = time.time() + 40
        seen = False
        while time.time() < deadline:
            try:
                ftxt = page.locator('.msg-form, form').first.inner_text(timeout=2000)
            except Exception:
                ftxt = ""
            if fname.lower() in ftxt.lower():
                seen = True
                break
            page.wait_for_timeout(1000)
        status["attachment_visible"] = seen
        if not seen:
            raise Exception("attachment did not appear in compose form within 40s")

    box.click()
    page.wait_for_timeout(300)
    page.keyboard.press("Control+A")
    page.keyboard.press("Delete")
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
        raise Exception(f"typed text too short ({len(typed)} vs {len(MESSAGE)}) - insert failed")
    status["step"] = "typed message"

    if DRY:
        status["typed_text"] = box.inner_text()[:200]
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
            raise Exception("no send button found in compose form")
        send_btn.click()
        page.wait_for_timeout(3000)
        leftover = box.inner_text().strip()
        status["leftover_in_box"] = leftover[:80]
        if leftover:
            raise Exception("compose box still contains text after send - send likely FAILED")
        # verify the sent text now appears in the thread body
        body = page.locator('.msg-s-message-list-container').first.inner_text(timeout=5000)
        status["sent_text_in_thread"] = MESSAGE[:60] in body
        if ATTACH:
            status["attachment_in_thread"] = fname.lower() in body.lower()
        status["step"] = "sent + verified in thread"
        status["ok"] = True
except Exception as e:
    status["error"] = str(e)

page.screenshot(path="reply_" + re.sub(r"\W", "", NAME)[:12] + ".png")
ctx.close()
p.stop()
print(json.dumps(status, ensure_ascii=False), flush=True)
