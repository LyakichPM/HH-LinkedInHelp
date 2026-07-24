# -*- coding: utf-8 -*-
"""Open a LinkedIn profile (or company page) and send a DM via the
Message button. Prints what happened; does not retry / does not guess.

Usage: li_send_message.py <url> <msg_file> name=<ExpectedName> [company] [dry]

Safety (added after the 2026-07-13 wrong-thread incident):
- ALL open floating chat panels are closed first (Playwright locators,
  which pierce LinkedIn's shadow DOM - raw JS querySelectorAll does not).
- Requires ZERO visible compose boxes before clicking Message, and exactly
  ONE after. If the panel does not open, we ABORT instead of typing into
  whatever stale panel .last happens to match.
- The open panel's close-button aria-label must contain the expected name
  (name= arg) before anything is typed.
"""
import sys, io, re, time, json
from playwright.sync_api import sync_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PROFILE = r"C:\Users\Ilya\.claude\hh-agent\li_profile"
URL = sys.argv[1]
MSG_FILE = sys.argv[2]
FLAGS = sys.argv[3:]
IS_COMPANY = "company" in FLAGS
DRY = "dry" in FLAGS
EXPECT_NAME = None
for f in FLAGS:
    if f.startswith("name="):
        EXPECT_NAME = f[5:]
if not EXPECT_NAME:
    print(json.dumps({"ok": False, "error": "name=<ExpectedName> arg is required"}))
    sys.exit(1)

with io.open(MSG_FILE, "r", encoding="utf-8") as f:
    MESSAGE = f.read()

CLOSE_SEL = ('button[aria-label^="Закрыть обсуждение"], '
             'button[aria-label^="Close conversation"], '
             'button[aria-label^="Sluit gesprek"]')

p = sync_playwright().start()
ctx = p.chromium.launch_persistent_context(
    PROFILE, channel="chrome", headless=True, locale="en-US",
    viewport={"width": 1400, "height": 1200},
    args=["--disable-blink-features=AutomationControlled"],
    ignore_default_args=["--enable-automation"],
)
page = ctx.pages[0] if ctx.pages else ctx.new_page()

def visible_boxes():
    out = []
    for b in page.locator('div[role="textbox"][contenteditable="true"]').all():
        try:
            if b.is_visible():
                out.append(b)
        except Exception:
            pass
    return out

status = {"url": URL, "ok": False, "step": "start", "expect_name": EXPECT_NAME}
try:
    page.goto(URL, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(3000)

    # 1. Close ALL open floating chat panels (Playwright pierces shadow DOM).
    closed = 0
    for _ in range(12):
        btns = page.locator(CLOSE_SEL).all()
        if not btns:
            # the label often lives in a hidden span inside the button,
            # not in an aria-label attribute
            btns = page.locator('button', has_text=re.compile(
                r"Закрыть обсуждение|Close conversation|Sluit gesprek")).all()
        if not btns:
            break
        try:
            btns[0].evaluate("el => el.click()")
            closed += 1
            page.wait_for_timeout(700)
        except Exception:
            break
    status["closed_panels"] = closed

    # 2. Hard precondition: no compose boxes may remain.
    boxes_before = visible_boxes()
    status["boxes_before"] = len(boxes_before)
    if boxes_before:
        raise Exception(f"{len(boxes_before)} compose box(es) still open after closing panels - aborting")

    # 3. Find and click the Message button.
    if IS_COMPANY:
        found = page.evaluate("""() => {
            const all = Array.from(document.querySelectorAll('a, button'));
            const el = all.find(e => {
                const al = (e.getAttribute('aria-label') || '').toLowerCase();
                return al.includes('отправить сообщение организации') || al.includes('message');
            });
            if (!el) return false;
            el.setAttribute('data-li-target', '1');
            return true;
        }""")
    else:
        found = page.evaluate("""() => {
            const all = Array.from(document.querySelectorAll('a, button'));
            const wanted = ['bericht', 'message', 'отправить сообщение'];
            const el = all.find(e => {
                const rect = e.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) return false;
                const al = (e.getAttribute('aria-label') || '').trim();
                if (al) return false;
                const txt = (e.innerText || '').trim().toLowerCase();
                return wanted.includes(txt);
            });
            if (!el) return false;
            el.setAttribute('data-li-target', '1');
            return true;
        }""")

    status["step"] = "button found: " + str(found)
    if not found:
        raise Exception("no message button found")

    btn = page.locator('[data-li-target="1"]').first
    btn.wait_for(state="visible", timeout=15000)
    btn.scroll_into_view_if_needed()
    page.wait_for_timeout(300)
    page.evaluate("document.querySelector('[data-li-target=\"1\"]').click()")
    status["step"] = "clicked message button"

    # 4. Wait for EXACTLY ONE compose box to appear.
    deadline = time.time() + 15
    boxes = []
    while time.time() < deadline:
        boxes = visible_boxes()
        if len(boxes) >= 1:
            break
        page.wait_for_timeout(500)
    status["boxes_after"] = len(boxes)
    if len(boxes) == 0:
        raise Exception("compose panel did NOT open - aborting (would have typed into a stale panel)")
    if len(boxes) > 1:
        raise Exception(f"{len(boxes)} compose boxes visible - ambiguous, aborting")
    box = boxes[0]

    # 5. Ownership check: walk UP from the compose box we will type into and
    # read ITS OWN panel header - the box is tied directly to its owner.
    page.wait_for_timeout(1000)
    panel_text = box.evaluate("""el => {
        const p = el.closest('.msg-overlay-conversation-bubble, .msg-convo-wrapper, [class*="msg-overlay-conversation"]');
        if (!p) return '';
        const h = p.querySelector('header');
        return (h ? h.innerText : p.innerText).slice(0, 200);
    }""").replace("\n", " ")
    status["panel_owner_header"] = panel_text
    name_token = EXPECT_NAME.split()[0].lower()
    if name_token not in panel_text.lower():
        raise Exception(f"compose box's own panel header does not contain {EXPECT_NAME!r} (header: {panel_text!r}) - aborting")

    status["step"] = "compose box open + ownership verified"
    try:
        box.click(timeout=5000)
    except Exception:
        box.evaluate("el => el.focus()")
    page.wait_for_timeout(400)
    page.keyboard.press("Control+A")
    page.keyboard.press("Delete")
    page.wait_for_timeout(300)
    box.type(MESSAGE, delay=8)
    page.wait_for_timeout(800)
    status["step"] = "typed message"

    if DRY:
        status["step"] = "dry-run: message typed, NOT sent"
        status["typed_text"] = box.inner_text()
        status["ok"] = True
    else:
        box_rect = box.bounding_box()
        send_candidates = page.locator('button').all()
        send_words = ["отправить", "send", "verzenden", "versturen"]
        send_btn = None
        for el in send_candidates:
            try:
                if not el.is_visible():
                    continue
                txt = (el.inner_text() or "").strip().lower()
                if txt not in send_words:
                    continue
                b = el.bounding_box()
                if b is None or box_rect is None:
                    continue
                if not (box_rect["x"] - 100 <= b["x"] <= box_rect["x"] + box_rect["width"] + 100):
                    continue
                if b["y"] < box_rect["y"] or b["y"] > box_rect["y"] + box_rect["height"] + 150:
                    continue
                send_btn = el
                break
            except Exception:
                continue
        if send_btn is None:
            for el in send_candidates:
                try:
                    if not el.is_visible():
                        continue
                    aria = (el.get_attribute("aria-label") or "").strip()
                    txt = (el.inner_text() or "").strip()
                    if aria or txt:
                        continue
                    b = el.bounding_box()
                    if b is None or box_rect is None:
                        continue
                    if not (28 <= b["width"] <= 36 and 28 <= b["height"] <= 36):
                        continue
                    if not (box_rect["x"] - 100 <= b["x"] <= box_rect["x"] + box_rect["width"] + 100):
                        continue
                    if b["y"] < box_rect["y"] or b["y"] > box_rect["y"] + box_rect["height"] + 150:
                        continue
                    send_btn = el
                    break
                except Exception:
                    continue
        if send_btn is None:
            raise Exception("no send button candidate found")
        try:
            send_btn.click(timeout=5000)
        except Exception:
            send_btn.evaluate("el => el.click()")
        page.wait_for_timeout(2000)

        # 6. Post-send verification: compose box should be empty now.
        try:
            leftover = box.inner_text().strip()
        except Exception:
            leftover = ""
        status["leftover_in_box"] = leftover[:80]
        if leftover:
            raise Exception("compose box still contains text after send click - send likely FAILED")
        status["step"] = "clicked send + box emptied"
        status["ok"] = True
except Exception as e:
    status["error"] = str(e)

page.screenshot(path=MSG_FILE + ".png")
ctx.close()
p.stop()
print(json.dumps(status, ensure_ascii=False), flush=True)
