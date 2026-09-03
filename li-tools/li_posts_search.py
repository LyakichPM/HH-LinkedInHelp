# -*- coding: utf-8 -*-
"""Read-only: собрать посты о вакансиях и их авторов.

LinkedIn ищет по постам отдельным разделом /search/results/content/. Классы там
обфусцированы, карточка — это div[componentkey]; они вложены друг в друга,
поэтому одинаковые посты схлопываем по автору и началу текста, оставляя самый
короткий (внутренний) вариант.

Автор, его должность, кусок текста и ссылка на профиль — дальше человека можно
проверить `li_person_actions.py` (можно ли вообще написать) и позвать в
контакты запиской.

  py li_posts_search.py <out.json> "<запрос>" [past-24h|past-week|past-month|all] [прокруток]
"""
import io, json, os, re, sys, time
from urllib.parse import quote, unquote
from playwright.sync_api import sync_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def _dir(name, env):
    """Каталог рядом с репозиторием; путь не зашит, логина ОС в коде нет."""
    return os.environ.get(env) or os.path.join(_ROOT, name)

PROFILE = _dir("li_profile", "LI_PROFILE")
OUT = sys.argv[1]
KW = sys.argv[2]
WHEN = sys.argv[3] if len(sys.argv) > 3 else "past-month"
SCROLLS = int(sys.argv[4]) if len(sys.argv) > 4 else 10

AGE = re.compile(r"\b\d+\s*(мин|ч|дн|нед|мес|г)\.?", re.I)

url = "https://www.linkedin.com/search/results/content/?keywords=" + quote(KW)
if WHEN != "all":
    url += f'&datePosted=%22{WHEN}%22'

p = sync_playwright().start()
ctx = p.chromium.launch_persistent_context(
    PROFILE, channel="chrome", headless=True, locale="en-US",
    viewport={"width": 1500, "height": 1200},
    args=["--disable-blink-features=AutomationControlled"],
    ignore_default_args=["--enable-automation"],
)
page = ctx.pages[0] if ctx.pages else ctx.new_page()
best = {}
try:
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    time.sleep(8)
    if "/authwall" in page.url or "/login" in page.url:
        print("STOP: не авторизован"); sys.exit(3)
    for _ in range(SCROLLS):
        page.mouse.wheel(0, 2200)
        time.sleep(2.5)
        for sel in ('button:has-text("Показать больше результатов")',
                    'button:has-text("Show more results")'):
            try:
                b = page.locator(sel).first
                if b.count() and b.is_visible(timeout=1000):
                    b.click(); time.sleep(3)
            except Exception:
                pass
    time.sleep(3)

    cards = page.locator("main div[componentkey]")
    print("узлов-кандидатов:", cards.count())
    for i in range(cards.count()):
        el = cards.nth(i)
        try:
            txt = el.inner_text()
        except Exception:
            continue
        lines = [x.strip() for x in txt.split("\n") if x.strip()]
        # карточка поста начинается служебной строкой, дальше автор, круг,
        # должность и возраст поста
        if len(lines) < 5 or lines[0] not in ("Публикация в ленте", "Feed post"):
            continue
        if not any(AGE.search(x) for x in lines[1:7]):
            continue
        try:
            a = el.locator('a[href*="/in/"]').first
            if not a.count():
                continue
            href = unquote((a.get_attribute("href") or "").split("?")[0])
        except Exception:
            continue
        author = lines[1][:80]
        age = next((x for x in lines[2:7] if AGE.search(x)), "")
        title = ""
        for ln in lines[2:7]:
            if len(ln) > 10 and not AGE.search(ln) and "-й" not in ln[:5]:
                title = ln[:110]; break
        body = " ".join(lines[2:])
        key = (href, body[:120])
        row = {"author": author, "author_title": title, "profile": href,
               "age": age.split("•")[0].strip(), "text": body[:900], "query": KW}
        if key not in best or len(txt) < best[key]["_len"]:
            row["_len"] = len(txt)
            best[key] = row
finally:
    ctx.close(); p.stop()

rows = []
for r in best.values():
    r.pop("_len", None)
    rows.append(r)
os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
json.dump(rows, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("собрано постов:", len(rows), "->", OUT)
for r in rows[:12]:
    print(f"  {r['author'][:30]} | {r['author_title'][:40]} | {r['text'][:60]}")
