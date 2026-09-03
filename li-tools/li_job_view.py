# -*- coding: utf-8 -*-
"""Read-only: открыть карточку вакансии LinkedIn и напечатать описание.

Ничего не жмёт кроме «See more» — кнопка отклика не трогается.

  py li_job_view.py <jobId> [chars]
"""
import os
import io, sys, time
from playwright.sync_api import sync_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def _dir(name, env):
    """Каталог рядом с репозиторием; путь не зашит, логина ОС в коде нет."""
    return os.environ.get(env) or os.path.join(_ROOT, name)

PROFILE = _dir("li_profile", "LI_PROFILE")
JID = sys.argv[1]
LIM = int(sys.argv[2]) if len(sys.argv) > 2 else 2500

p = sync_playwright().start()
ctx = p.chromium.launch_persistent_context(
    PROFILE, channel="chrome", headless=True, locale="en-US",
    viewport={"width": 1600, "height": 1200},
    args=["--disable-blink-features=AutomationControlled"],
    ignore_default_args=["--enable-automation"],
)
page = ctx.pages[0] if ctx.pages else ctx.new_page()
try:
    page.goto(f"https://www.linkedin.com/jobs/view/{JID}/",
              wait_until="domcontentloaded", timeout=60000)
    time.sleep(5)
    for sel in ['button:has-text("See more")', 'button:has-text("Показать еще")',
                'button.jobs-description__footer-button']:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=1500):
                el.click(); time.sleep(1.5); break
        except Exception:
            continue
    try:
        head = page.locator('.job-details-jobs-unified-top-card__job-title, h1').first.inner_text()
        print("TITLE:", head.strip()[:120])
    except Exception:
        pass
    try:
        meta = page.locator('.job-details-jobs-unified-top-card__primary-description-container,'
                            ' .job-details-jobs-unified-top-card__tertiary-description-container'
                            ).first.inner_text()
        print("META:", " | ".join(x.strip() for x in meta.split("\n") if x.strip())[:200])
    except Exception:
        pass
    d = ""
    for sel in ['#job-details', '.jobs-description__content', '.jobs-box__html-content',
                'article', 'main']:
        try:
            el = page.locator(sel).first
            if el.count() and el.is_visible(timeout=2000):
                d = el.inner_text(timeout=8000)
                if len(d.strip()) > 200:
                    print("(взято из", sel, ")")
                    break
        except Exception:
            continue
    if not d.strip():
        d = "описание не прочитано ни одним селектором"
    print("--- DESCRIPTION ---")
    print("\n".join(x for x in d.split("\n") if x.strip())[:LIM])
finally:
    ctx.close(); p.stop()
