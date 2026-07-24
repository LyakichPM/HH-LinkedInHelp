# -*- coding: utf-8 -*-
"""Send a LinkedIn connection request WITH a note from a profile URL.

Usage: li_connect_note.py <profile_url> <expect_token> <msg_file> [dry]

Safety:
- Verifies the profile top-card contains <expect_token> BEFORE any click.
- Finds Connect top-level or under the More/Ещё overflow menu.
- Opens the "Add a note" panel, reports the textarea maxlength and any
  "invitations left" messaging, fills the note.
- dry: reports everything, does NOT click Send, closes the modal.
- Detects already-pending / already-connected / email-gate and aborts safely.
"""
import sys, io, re, time, json
from playwright.sync_api import sync_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PROFILE = r"C:\Users\Ilya\.claude\hh-agent\li_profile"
URL = sys.argv[1]
EXPECT = sys.argv[2].lower()
MSG_FILE = sys.argv[3]
DRY = "dry" in sys.argv[4:]

with io.open(MSG_FILE, "r", encoding="utf-8") as f:
    MESSAGE = f.read().strip()

CONNECT_RE = re.compile(r"установить контакт|connect|пригласить|invite", re.I)
PENDING_RE = re.compile(r"ожидает|pending|отменить приглашение|withdraw", re.I)
MORE_RE = re.compile(r"^(ещё|more|другие действия)", re.I)

p = sync_playwright().start()
ctx = p.chromium.launch_persistent_context(
    PROFILE, channel="chrome", headless=True, locale="en-US",
    viewport={"width": 1400, "height": 1200},
    args=["--disable-blink-features=AutomationControlled"],
    ignore_default_args=["--enable-automation"],
)
page = ctx.pages[0] if ctx.pages else ctx.new_page()
st = {"url": URL, "expect": EXPECT, "ok": False, "dry": DRY, "step": "start", "sent": False}

def human(a=250, b=650):
    page.wait_for_timeout(__import__("random").randint(a, b))

try:
    page.goto(URL, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(4000)

    # 1. ownership check on the top card (try several selectors; fall back to <title>)
    topcard = ""
    for sel in ["h1.inline.t-24", "h1.text-heading-xlarge", "section.artdeco-card h1",
                "div.ph5 h1", "main h1", "h1"]:
        try:
            loc = page.locator(sel)
            for i in range(min(loc.count(), 5)):
                t = loc.nth(i).inner_text(timeout=1500).strip()
                if t:
                    topcard = t
                    break
        except Exception:
            pass
        if topcard:
            break
    if not topcard:
        try:
            topcard = (page.title() or "").split("|")[0].strip()
        except Exception:
            topcard = ""
    st["topcard_name"] = topcard
    if EXPECT not in topcard.lower():
        raise Exception(f"top-card {topcard!r} does not contain {EXPECT!r} - aborting")

    # already-pending?
    body_txt = page.locator("main").first.inner_text()
    if PENDING_RE.search(body_txt or ""):
        st["step"] = "invitation already pending - skipping"
        st["ok"] = True
        st["already_pending"] = True
        raise SystemExit

    # 2. locate the PROFILE-OWNER's Connect control.
    # It is an <a> (not a <button>), NOT inside <aside>, and its aria-label
    # names the profile owner ("Пригласить участника <Name> установить контакт").
    # Requiring aside=False AND the expected name makes a wrong-person click
    # impossible (every sidebar connect is aside=True with a different name).
    def find_connect_owner():
        for tag in ("a", "button"):
            for el in page.locator(tag).all():
                try:
                    if not el.is_visible():
                        continue
                    al = (el.get_attribute("aria-label") or "")
                    txt = (el.inner_text() or "").strip()
                    if not (CONNECT_RE.search(al) or CONNECT_RE.search(txt)):
                        continue
                    if re.search(r"отслеж|follow|сообщени|message", (al + " " + txt), re.I):
                        continue
                    if el.evaluate("e=> !!e.closest('aside')"):
                        continue  # sidebar suggestion for someone else
                    if EXPECT not in al.lower():
                        continue  # aria must name THIS profile's owner
                    return el
                except Exception:
                    continue
        return None

    btn = find_connect_owner()
    st["connect_toplevel"] = btn is not None

    if btn is None:
        # fallback: open the More / Ещё overflow menu on the top card
        more = None
        for el in page.locator("button, a").all():
            try:
                if not el.is_visible():
                    continue
                al = (el.get_attribute("aria-label") or "")
                txt = (el.inner_text() or "").strip()
                if el.evaluate("e=> !!e.closest('aside')"):
                    continue
                if txt.strip().lower() in ("ещё", "more") or re.search(r"другие действия|more actions", al, re.I):
                    more = el
                    break
            except Exception:
                continue
        if more is None:
            raise Exception("no owner Connect (aside=False + name) and no top-card More menu - maybe only Follow available")
        more.evaluate("e=>e.click()")
        human(500, 900)
        for el in page.locator('div[role="menu"] *, .artdeco-dropdown__content *').all():
            try:
                if not el.is_visible():
                    continue
                txt = (el.inner_text() or "").strip()
                al = (el.get_attribute("aria-label") or "")
                if CONNECT_RE.search(txt) or CONNECT_RE.search(al):
                    if re.search(r"отслеж|follow|сообщени|message", (al+" "+txt), re.I):
                        continue
                    btn = el
                    break
            except Exception:
                continue
        st["connect_in_menu"] = btn is not None
        if btn is None:
            raise Exception("Connect not found in top-card More menu")

    btn.scroll_into_view_if_needed()
    human()
    btn.evaluate("e=>e.click()")
    human(800, 1300)
    st["step"] = "clicked Connect"

    # 3. the connect modal: click "Персонализировать" / "Add a note" (NOT "send without note")
    NOTE_BTN_RE = re.compile(r"персонализировать|добавить заметку|добавить записку|add a note|personalize|customize", re.I)
    add_note = None
    for el in page.locator('div[role="dialog"] button, .artdeco-modal button').all():
        try:
            if not el.is_visible():
                continue
            txt = (el.inner_text() or "").strip().lower()
            al = (el.get_attribute("aria-label") or "").lower()
            if re.search(r"без заметки|without", txt + " " + al):
                continue
            if NOTE_BTN_RE.search(txt) or NOTE_BTN_RE.search(al):
                add_note = el
                break
        except Exception:
            continue
    st["add_note_found"] = add_note is not None

    # capture any "invitations left" quota text in the dialog
    try:
        dlg_txt = page.locator('div[role="dialog"], .artdeco-modal').first.inner_text(timeout=3000)
    except Exception:
        dlg_txt = ""
    m = re.search(r"([^\n]*осталось[^\n]*|[^\n]*invitation[^\n]*left[^\n]*|[^\n]*приглашени[^\n]*)", dlg_txt, re.I)
    st["quota_hint"] = (m.group(1).strip()[:160] if m else "")
    if re.search(r"эл\. адрес|email|подтвердите", dlg_txt, re.I):
        st["email_gate"] = True
        raise Exception("modal asks for email verification - aborting (would need Ilia)")

    if add_note is None:
        raise Exception("'Add a note' button not present - only send-without-note offered; aborting to avoid noteless invite")
    add_note.evaluate("e=>e.click()")
    human(500, 900)

    # 4. the note textarea
    ta = None
    for sel in ['textarea#custom-message', 'textarea[name="message"]',
                'div[role="dialog"] textarea', '.artdeco-modal textarea']:
        loc = page.locator(sel)
        if loc.count() and loc.first.is_visible():
            ta = loc.first
            break
    if ta is None:
        raise Exception("note textarea not found")
    maxlen = ta.get_attribute("maxlength")
    st["note_maxlength"] = maxlen
    st["msg_len"] = len(MESSAGE)
    if maxlen and len(MESSAGE) > int(maxlen):
        st["WILL_TRUNCATE"] = True
        raise Exception(f"message {len(MESSAGE)} > maxlength {maxlen} - would truncate, aborting")

    ta.click()
    human()
    ta.type(MESSAGE, delay=6)
    human(400, 700)
    typed = ta.input_value()
    st["typed_len"] = len(typed)
    st["typed_ok"] = typed.strip() == MESSAGE.strip()
    if not st["typed_ok"]:
        raise Exception(f"typed note mismatch (typed {len(typed)} vs {len(MESSAGE)})")

    if DRY:
        st["step"] = "DRY: note typed, NOT sent"
        st["ok"] = True
    else:
        send = None
        for el in page.locator('div[role="dialog"] button, .artdeco-modal button').all():
            try:
                if not el.is_visible():
                    continue
                txt = (el.inner_text() or "").strip().lower()
                al = (el.get_attribute("aria-label") or "").lower()
                if re.search(r"без заметки|without", txt + " " + al):
                    continue  # never the send-without-note button
                if txt in ("отправить", "send") or "отправить приглашение" in al or "send invitation" in al or "send now" in txt:
                    send = el
                    break
            except Exception:
                continue
        if send is None:
            raise Exception("Send button not found in modal")
        send.evaluate("e=>e.click()")
        page.wait_for_timeout(2500)
        # verify modal gone
        try:
            still = page.locator('div[role="dialog"] textarea').first.is_visible(timeout=1500)
        except Exception:
            still = False
        st["modal_still_open"] = bool(still)
        if still:
            raise Exception("modal still open after Send - send likely FAILED")
        st["step"] = "invitation SENT"
        st["sent"] = True
        st["ok"] = True
except SystemExit:
    pass
except Exception as e:
    st["error"] = str(e)

try:
    page.screenshot(path="connect_" + re.sub(r"\W", "", EXPECT)[:14] + (".dry" if DRY else "") + ".png")
except Exception:
    pass
ctx.close()
p.stop()
print(json.dumps(st, ensure_ascii=False), flush=True)
