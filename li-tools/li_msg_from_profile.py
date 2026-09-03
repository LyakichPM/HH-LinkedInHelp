# -*- coding: utf-8 -*-
"""Написать человеку из его профиля — через полную страницу /messaging/compose/.

Кнопка «Отправить сообщение» в шапке профиля это <a href="/messaging/compose/
?recipient=…">, поэтому плавающий док не нужен: берём ссылку и открываем её как
обычную страницу. Перед вводом текста сверяем, что в шапке треда именно тот
человек, иначе выходим.

У 2-го круга без Premium ссылки в шапке может не быть вовсе (LinkedIn уводит на
апселл InMail) — тогда путь один: приглашение в контакты с запиской,
`li_connect_note.py`.

  py li_msg_from_profile.py <profile_url> <expect_token> <msg_file> [dry]
"""
import os
import io, json, re, sys, time
from playwright.sync_api import sync_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def _dir(name, env):
    """Каталог рядом с репозиторием; путь не зашит, логина ОС в коде нет."""
    return os.environ.get(env) or os.path.join(_ROOT, name)

PROFILE = _dir("li_profile", "LI_PROFILE")
URL, EXPECT, MSG_FILE = sys.argv[1], sys.argv[2].lower(), sys.argv[3]
DRY = "dry" in sys.argv[4:]
MESSAGE = open(MSG_FILE, encoding="utf-8").read().strip()

st = {"url": URL, "expect": EXPECT, "dry": DRY, "ok": False, "step": "start"}
p = sync_playwright().start()
ctx = p.chromium.launch_persistent_context(
    PROFILE, channel="chrome", headless=True, locale="en-US",
    viewport={"width": 1600, "height": 1200},
    args=["--disable-blink-features=AutomationControlled"],
    ignore_default_args=["--enable-automation"],
)
page = ctx.pages[0] if ctx.pages else ctx.new_page()
try:
    page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(6000)
    if "/authwall" in page.url or "/login" in page.url:
        raise Exception("не авторизован")

    # у профиля h1 бывает не в main; заголовок вкладки называет владельца страницы
    name = page.title()
    st["profile_name"] = name
    if EXPECT not in name.lower():
        raise Exception(f"заголовок страницы {name!r} не содержит {EXPECT!r}")

    # ссылка ЭТОГО профиля идёт без aria-label; у карточек «вы можете знать»
    # aria-label всегда назван адресатом — по этому и различаем
    href = ""
    for a in page.locator('a[href*="/messaging/compose/"]').all():
        try:
            if (a.get_attribute("aria-label") or "").strip():
                continue
            h = a.get_attribute("href") or ""
            if "recipient=" in h:
                href = h; break
        except Exception:
            continue
    if not href:
        raise Exception("ссылки «Отправить сообщение» в шапке нет — только приглашение в контакты")
    st["compose_href"] = href[:120]

    page.goto("https://www.linkedin.com" + href, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(7000)
    st["compose_url"] = page.url[:160]
    if "premium" in page.url.lower() or "upsell" in page.url.lower():
        raise Exception("LinkedIn увёл на апселл Premium InMail — писать нечем")

    detail = page.locator(".scaffold-layout__detail").first.inner_text()[:400]
    st["detail_head"] = detail.replace("\n", " | ")[:200]
    if EXPECT not in detail.lower():
        raise Exception(f"в шапке треда нет {EXPECT!r}: {detail[:120]!r}")
    st["step"] = "адресат подтверждён"

    box = page.locator('div.msg-form__contenteditable[role="textbox"],'
                       ' div[role="textbox"][contenteditable="true"]').first
    box.wait_for(state="visible", timeout=15000)
    box.click(); page.wait_for_timeout(300)
    lines = MESSAGE.split("\n")
    for i, line in enumerate(lines):
        if line:
            page.keyboard.insert_text(line)
        if i < len(lines) - 1:
            page.keyboard.press("Shift+Enter")
    page.wait_for_timeout(800)
    typed = box.inner_text().strip()
    st["typed_len"] = len(typed)
    if len(typed) < len(MESSAGE) * 0.7:
        raise Exception(f"текст набрался не полностью ({len(typed)}/{len(MESSAGE)})")

    if DRY:
        st["step"] = "dry: набрано, НЕ отправлено"; st["ok"] = True
    else:
        send = None
        for el in page.locator('.msg-form button, form button').all():
            try:
                if not el.is_visible():
                    continue
                t = (el.inner_text() or "").strip().lower()
                cls = el.get_attribute("class") or ""
                if t in ("отправить", "send") or "msg-form__send-button" in cls:
                    send = el; break
            except Exception:
                continue
        if send is None:
            raise Exception("кнопка отправки не найдена")
        send.click(); page.wait_for_timeout(4000)
        left = box.inner_text().strip()
        st["leftover"] = left[:60]
        if left:
            raise Exception("текст остался в поле — не отправилось")
        try:
            body = page.locator('.msg-s-message-list-container').first.inner_text(timeout=6000)
            st["in_thread"] = MESSAGE[:50] in body
        except Exception:
            st["in_thread"] = "unknown"
        st["step"] = "отправлено"; st["ok"] = True
except Exception as e:
    st["error"] = str(e)

try:
    shot = "_msg_" + re.sub(r"\W", "", EXPECT)[:12] + ".png"
    page.screenshot(path=os.path.join(_dir("li_jobs", "LI_JOBS"), shot))
except Exception:
    pass
ctx.close(); p.stop()
print(json.dumps(st, ensure_ascii=False))
