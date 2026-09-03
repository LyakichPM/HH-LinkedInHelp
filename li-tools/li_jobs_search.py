# -*- coding: utf-8 -*-
"""Read-only поиск вакансий на LinkedIn.

Ничего не отправляет и ни на что не откликается — только собирает карточки.
Профиль тот же персистентный, что у остальных li_*.py.

  py li_jobs_search.py <out.json> "<keywords>" [location] [f_TPR] [pages]

f_TPR: r604800 — неделя, r2592000 — месяц. Пустая строка — без фильтра.
"""
import io, json, os, re, sys, time
from playwright.sync_api import sync_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def _dir(name, env):
    """Каталог рядом с репозиторием; путь не зашит, логина ОС в коде нет."""
    return os.environ.get(env) or os.path.join(_ROOT, name)

PROFILE = _dir("li_profile", "LI_PROFILE")
OUT = sys.argv[1]
KW = sys.argv[2]
LOC = sys.argv[3] if len(sys.argv) > 3 else ""
TPR = sys.argv[4] if len(sys.argv) > 4 else "r2592000"
PAGES = int(sys.argv[5]) if len(sys.argv) > 5 else 2

from urllib.parse import quote

p = sync_playwright().start()
ctx = p.chromium.launch_persistent_context(
    PROFILE, channel="chrome", headless=True, locale="en-US",
    viewport={"width": 1600, "height": 1200},
    args=["--disable-blink-features=AutomationControlled"],
    ignore_default_args=["--enable-automation"],
)
page = ctx.pages[0] if ctx.pages else ctx.new_page()
rows = {}
try:
    for pg in range(PAGES):
        url = (f"https://www.linkedin.com/jobs/search/?keywords={quote(KW)}"
               f"&location={quote(LOC)}&start={pg * 25}")
        if TPR:
            url += f"&f_TPR={TPR}"
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(5)
        if "/authwall" in page.url or "/login" in page.url:
            print("STOP: не авторизован, url=", page.url)
            sys.exit(3)
        # прокрутить список, чтобы догрузились карточки
        try:
            lst = page.locator('div.scaffold-layout__list, ul.jobs-search__results-list').first
            for _ in range(8):
                lst.evaluate("el => el.scrollTop = el.scrollTop + 900")
                time.sleep(0.8)
        except Exception:
            for _ in range(8):
                page.mouse.wheel(0, 900); time.sleep(0.6)

        cards = page.locator('li[data-occludable-job-id], div.job-card-container')
        n = cards.count()
        print(f"стр {pg + 1}: карточек {n}", file=sys.stderr)
        for i in range(n):
            c = cards.nth(i)
            try:
                txt = c.inner_text(timeout=1500)
            except Exception:
                continue
            jid = c.get_attribute("data-occludable-job-id") or ""
            if not jid:
                try:
                    href = c.locator('a[href*="/jobs/view/"]').first.get_attribute("href") or ""
                    m = re.search(r"/jobs/view/(\d+)", href)
                    jid = m.group(1) if m else ""
                except Exception:
                    pass
            if not jid:
                continue
            lines = [x.strip() for x in txt.split("\n") if x.strip()]
            # LinkedIn дублирует заголовок скрытым span — снимаем повтор
            ded = []
            for x in lines:
                if not ded or ded[-1] != x:
                    ded.append(x)
            rows[jid] = {
                "id": jid,
                "title": ded[0] if ded else "",
                "company": ded[1] if len(ded) > 1 else "",
                "location": ded[2] if len(ded) > 2 else "",
                "raw": " | ".join(ded[:7]),
                "url": f"https://www.linkedin.com/jobs/view/{jid}/",
                "query": KW,
            }
        if n == 0:
            break
finally:
    json.dump(list(rows.values()), open(OUT, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    ctx.close(); p.stop()
print(f"собрано {len(rows)} -> {OUT}")
