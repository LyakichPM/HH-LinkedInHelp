# -*- coding: utf-8 -*-
"""Send a message to a COMPANY page via its 'Новое сообщение' modal
(topic dropdown + textarea, 750 char limit).

Usage: li_company_modal.py <company_url> <expect_company> <msg_file> [topic=<substr>] [dry]

dry mode: opens the modal, dumps topic options + state, does NOT send.
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
URL = sys.argv[1]
EXPECT = sys.argv[2].lower()
MSG_FILE = sys.argv[3]
DRY = "dry" in sys.argv[4:]
TOPIC = None
for f in sys.argv[4:]:
    if f.startswith("topic="):
        TOPIC = f[6:].lower()

with io.open(MSG_FILE, "r", encoding="utf-8") as f:
    MESSAGE = f.read().strip()

status = {"url": URL, "expect": EXPECT, "ok": False, "step": "start",
          "dry": DRY, "msg_len": len(MESSAGE)}
if len(MESSAGE) > 750:
    print(json.dumps({**status, "error": f"message is {len(MESSAGE)} chars, limit 750"}, ensure_ascii=False))
    sys.exit(1)

p = sync_playwright().start()
ctx = p.chromium.launch_persistent_context(
    PROFILE, channel="chrome", headless=True, locale="en-US",
    viewport={"width": 1400, "height": 1200},
    args=["--disable-blink-features=AutomationControlled"],
    ignore_default_args=["--enable-automation"],
)
page = ctx.pages[0] if ctx.pages else ctx.new_page()
try:
    page.goto(URL, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(4000)

    # close any dock panels so nothing stale interferes
    for _ in range(10):
        btns = page.locator('button', has_text=re.compile(
            r"Закрыть обсуждение|Close conversation|Sluit gesprek")).all()
        if not btns:
            break
        try:
            btns[0].evaluate("el => el.click()")
            page.wait_for_timeout(600)
        except Exception:
            break

    # click the company message button
    found = page.evaluate("""() => {
        const all = Array.from(document.querySelectorAll('a, button'));
        const el = all.find(e => {
            const r = e.getBoundingClientRect();
            if (!r.width || !r.height) return false;
            const al = (e.getAttribute('aria-label') || '').toLowerCase();
            const tx = (e.innerText || '').trim().toLowerCase();
            return al.includes('отправить сообщение организации') ||
                   al.includes('message') && al.includes('organization') ||
                   tx.startsWith('отправить сообщение') || tx === 'message' || tx === 'bericht';
        });
        if (!el) return false;
        el.click();
        return true;
    }""")
    if not found:
        raise Exception("company message button not found")
    status["step"] = "clicked message button"

    # wait for the modal
    dlg = page.locator('div[role="dialog"], .artdeco-modal').first
    dlg.wait_for(state="visible", timeout=15000)
    head = dlg.inner_text(timeout=3000).replace("\n", " ")
    status["modal_head"] = head[:150]
    if EXPECT not in head.lower():
        raise Exception(f"modal is not addressed to {EXPECT!r}: {head[:100]!r}")
    status["step"] = "modal open + addressee verified"

    # topic dropdown: try native <select> first, else artdeco dropdown button
    topics = []
    sel_el = dlg.locator("select")
    if sel_el.count():
        for op in sel_el.first.locator("option").all():
            topics.append((op.get_attribute("value") or "", (op.inner_text() or "").strip()))
        status["topics"] = [t[1] for t in topics]
        want = None
        for val, lbl in topics:
            ll = lbl.lower()
            if TOPIC and TOPIC in ll:
                want = (val, lbl); break
            if not TOPIC and any(k in ll for k in ("карьер", "ваканс", "career", "job")):
                want = (val, lbl); break
        if want is None and topics:
            usable = [t for t in topics if t[0]]
            want = usable[0] if usable else None
        if want is None:
            raise Exception("no usable topic option")
        sel_el.first.select_option(value=want[0])
        status["topic_selected"] = want[1]
    else:
        trig = dlg.locator('button', has_text=re.compile(r"Выберите тему|Select a topic")).first
        trig.click()
        page.wait_for_timeout(1000)
        opts = page.locator('[role="listbox"] [role="option"], .artdeco-dropdown__content li, ul[role="listbox"] li')
        cand = None
        for el in opts.all():
            try:
                if not el.is_visible():
                    continue
                t = (el.inner_text() or "").strip()
                if not t:
                    continue
                topics.append(t)
                tl = t.lower()
                if cand is None and (
                        (TOPIC and TOPIC in tl) or
                        (not TOPIC and any(k in tl for k in ("карьер", "ваканс", "career", "job")))):
                    cand = el
            except Exception:
                continue
        status["topics"] = topics[:10]
        if cand is None:
            raise Exception(f"no matching topic option among {topics[:10]}")
        cand.click()
        status["topic_selected"] = True
    page.wait_for_timeout(800)
    status["step"] = "topic selected"

    # fill the textarea
    ta = dlg.locator("textarea").first
    ta.wait_for(state="visible", timeout=8000)
    ta.click()
    ta.fill(MESSAGE)
    page.wait_for_timeout(500)
    typed = ta.input_value()
    status["typed_len"] = len(typed)
    if len(typed) < len(MESSAGE) * 0.9:
        raise Exception(f"textarea holds {len(typed)}/{len(MESSAGE)} chars")
    status["step"] = "message filled"

    if DRY:
        status["modal_text_after"] = dlg.inner_text().replace("\n", " | ")[:400]
        status["step"] = "dry-run: filled, NOT sent"
        status["ok"] = True
    else:
        btn = dlg.locator('button', has_text=re.compile(r"Отправить сообщение|Send message")).first
        if btn.is_disabled():
            raise Exception("send button is disabled")
        btn.click()
        page.wait_for_timeout(3000)
        # modal should close (or show confirmation)
        still = False
        try:
            still = dlg.is_visible()
        except Exception:
            pass
        status["modal_still_open"] = still
        if still:
            txt = ""
            try:
                txt = dlg.inner_text().replace("\n", " ")[:200]
            except Exception:
                pass
            status["modal_after_send"] = txt
            if "Написать сообщение" in txt and MESSAGE[:30] in txt:
                raise Exception("modal still open with the draft - send likely FAILED")
        status["step"] = "sent (modal closed)" if not still else "sent? (modal showed: " + status.get("modal_after_send", "")[:60] + ")"
        status["ok"] = True
except Exception as e:
    status["error"] = str(e)

page.screenshot(path="company_" + re.sub(r"\W", "", EXPECT)[:12] + ".png")
ctx.close()
p.stop()
print(json.dumps(status, ensure_ascii=False), flush=True)
