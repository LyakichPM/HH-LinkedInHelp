# -*- coding: utf-8 -*-
"""Read-only: реально ли можно написать человеку, а не «есть ли кнопка».

Кнопка «Отправить сообщение» в профиле есть почти у всех, но для не-контакта
LinkedIn подменяет её апселлом Premium InMail — и понять это можно только
дойдя до поля ввода. Судим по окну «Новое сообщение»: если после выбора
адресата адрес страницы уехал в PREMIUM_INMAIL/upsell — канала нет.

Ничего не печатает и не отправляет.

  py li_can_message.py "<имя как в LinkedIn>" [токен_для_сверки]
"""
import os
import io, json, sys, time
from playwright.sync_api import sync_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def _dir(name, env):
    """Каталог рядом с репозиторием; путь не зашит, логина ОС в коде нет."""
    return os.environ.get(env) or os.path.join(_ROOT, name)

PROFILE = _dir("li_profile", "LI_PROFILE")
NAME = sys.argv[1]
EXPECT = (sys.argv[2] if len(sys.argv) > 2 else NAME.split()[-1]).lower()

st = {"name": NAME, "expect": EXPECT, "verdict": "unknown"}
p = sync_playwright().start()
ctx = p.chromium.launch_persistent_context(
    PROFILE, channel="chrome", headless=True, locale="en-US",
    viewport={"width": 1600, "height": 1200},
    args=["--disable-blink-features=AutomationControlled"],
    ignore_default_args=["--enable-automation"],
)
page = ctx.pages[0] if ctx.pages else ctx.new_page()
try:
    page.goto("https://www.linkedin.com/messaging/thread/new/",
              wait_until="domcontentloaded", timeout=45000)
    time.sleep(5)
    fld = page.locator('input[placeholder*="Введите имя"], input[placeholder*="Type a name"],'
                       ' .msg-connections-typeahead__search-field').first
    fld.click(); fld.type(NAME, delay=60)
    time.sleep(4)
    pick = None
    for el in page.locator('ul[role="listbox"] li, div[role="option"], li[role="option"],'
                           ' .msg-connections-typeahead__search-results li').all():
        try:
            t = (el.inner_text() or "").lower()
        except Exception:
            continue
        if EXPECT in t:
            pick = el; st["suggestion"] = t.replace("\n", " ")[:90]; break
    if pick is None:
        st["verdict"] = "not_found"
        raise SystemExit
    pick.click(); time.sleep(6)
    st["url"] = page.url[:120]
    low = page.url.lower()
    box = page.locator('div[role="textbox"][contenteditable="true"]')
    if "premium_inmail" in low or "upsell=true" in low:
        st["verdict"] = "blocked_inmail"
    elif box.count() and box.first.is_visible():
        st["verdict"] = "can_message"
    else:
        st["verdict"] = "no_box"
except SystemExit:
    pass
except Exception as e:
    st["error"] = str(e)
ctx.close(); p.stop()
print(json.dumps(st, ensure_ascii=False))
