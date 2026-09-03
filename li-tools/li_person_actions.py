# -*- coding: utf-8 -*-
"""Read-only: что вообще можно сделать с человеком — написать или только позвать в контакты.

LinkedIn для 2-го круга без Premium подменяет «Написать» на апселл InMail, и
узнать это можно только по кнопкам на профиле. Скрипт ничего не жмёт из
действий — только читает.

  py li_person_actions.py <profile_url|имя для поиска>

Печатает: имя, заголовок, круг, список кнопок и вердикт can_message / connect_only.
"""
import os
import io, sys, time
from urllib.parse import quote
from playwright.sync_api import sync_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def _dir(name, env):
    """Каталог рядом с репозиторием; путь не зашит, логина ОС в коде нет."""
    return os.environ.get(env) or os.path.join(_ROOT, name)

PROFILE = _dir("li_profile", "LI_PROFILE")
WHO = sys.argv[1]

p = sync_playwright().start()
ctx = p.chromium.launch_persistent_context(
    PROFILE, channel="chrome", headless=True, locale="en-US",
    viewport={"width": 1500, "height": 1100},
    args=["--disable-blink-features=AutomationControlled"],
    ignore_default_args=["--enable-automation"],
)
page = ctx.pages[0] if ctx.pages else ctx.new_page()
try:
    if WHO.startswith("http"):
        url = WHO
    else:
        page.goto("https://www.linkedin.com/search/results/people/?keywords=" + quote(WHO),
                  wait_until="domcontentloaded", timeout=60000)
        time.sleep(6)
        link = page.locator('a[href*="/in/"]').first
        if not link.count():
            print("STOP: профиль не найден по имени"); sys.exit(2)
        url = (link.get_attribute("href") or "").split("?")[0]
        print("нашёл профиль:", url)
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    time.sleep(6)
    if "/authwall" in page.url or "/login" in page.url:
        print("STOP: не авторизован"); sys.exit(3)

    try:
        top = page.locator("main section").first.inner_text()
        print("--- шапка профиля ---")
        print("\n".join(x.strip() for x in top.split("\n") if x.strip())[:500])
    except Exception:
        pass

    labs = []
    for b in page.locator("main button:visible, main a:visible").all():
        try:
            t = ((b.get_attribute("aria-label") or "") + " / " +
                 (b.inner_text() or "").strip()).replace("\n", " ").strip(" /")
            if t and len(t) < 90:
                labs.append(t)
        except Exception:
            continue
    acts = [t for t in labs if any(w in t.lower() for w in
            ("сообщени", "message", "установить контакт", "connect",
             "подписаться", "follow", "inmail", "еще", "more"))]
    print("\n--- кнопки действий ---")
    for t in dict.fromkeys(acts):
        print("  ", t)

    low = " ".join(acts).lower()
    if "сообщени" in low or "message" in low:
        print("\nВЕРДИКТ: can_message — есть прямая кнопка сообщения")
    elif "контакт" in low or "connect" in low:
        print("\nВЕРДИКТ: connect_only — только запрос в контакты с запиской (≤300 симв.)")
    else:
        print("\nВЕРДИКТ: unknown — кнопок действий не видно, смотреть руками")
finally:
    ctx.close(); p.stop()
