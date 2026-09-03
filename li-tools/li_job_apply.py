# -*- coding: utf-8 -*-
"""Отклик через LinkedIn Easy Apply («Простая подача заявки»).

Форма живёт в нативном <dialog data-testid="dialog"> — классы у LinkedIn
обфусцированы, поэтому цепляемся за data-testid и за подписи полей.
Поля файла в DOM нет: «Загрузить резюме» открывает системный диалог, ловим
его через expect_file_chooser.

Кнопку отклика ищем только на карточке вакансии; прямых переходов по адресам
форм нет.

  py li_job_apply.py <jobId> dry|go [resume.pdf]

`dry` печатает поля и кнопки и НИЧЕГО не отправляет; `go` при заданном резюме
загружает его и жмёт «Отправить заявку».
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
SHOTS = _dir("li_jobs", "LI_JOBS")
JID = sys.argv[1]
MODE = sys.argv[2] if len(sys.argv) > 2 else "dry"
RESUME = sys.argv[3] if len(sys.argv) > 3 else ""

SUBMIT = ("отправить заявку", "submit application", "подать заявку")
NEXT = ("далее", "next", "continue to next step", "просмотреть", "review")


def buttons(dlg):
    out = []
    for b in dlg.locator("button:visible").all():
        try:
            lab = ((b.get_attribute("aria-label") or "") + " " + (b.inner_text() or "")).strip()
            out.append((b, lab, lab.lower()))
        except Exception:
            continue
    return out


def dump(dlg, step):
    print(f"\n=== шаг {step} ===")
    for el in dlg.locator("input:visible, textarea:visible, select:visible").all():
        try:
            t = (el.get_attribute("type") or el.evaluate("e => e.tagName.toLowerCase()"))
            if t == "hidden":
                continue
            lab = (el.get_attribute("aria-label") or el.get_attribute("name")
                   or el.get_attribute("id") or "")
            if t in ("radio", "checkbox"):
                print(f"  [{t}] {lab[:70]!r} checked={el.is_checked()}")
            else:
                print(f"  [{t}] {lab[:70]!r} = {str(el.input_value())[:60]!r}")
        except Exception:
            continue
    txt = dlg.inner_text()
    print("  --- текст ---")
    print("  " + "\n  ".join(x.strip() for x in txt.split("\n") if x.strip())[:1200])


p = sync_playwright().start()
ctx = p.chromium.launch_persistent_context(
    PROFILE, channel="chrome", headless=False, locale="en-US",
    viewport={"width": 1500, "height": 1100},
    args=["--disable-blink-features=AutomationControlled"],
    ignore_default_args=["--enable-automation"],
)
page = ctx.pages[0] if ctx.pages else ctx.new_page()
try:
    page.goto(f"https://www.linkedin.com/jobs/view/{JID}/",
              wait_until="domcontentloaded", timeout=60000)
    time.sleep(5)
    if "/authwall" in page.url or "/login" in page.url:
        print("STOP: не авторизован, url=", page.url); sys.exit(3)

    btn = None
    for sel in ('button:has-text("Простая подача заявки")', 'button:has-text("Easy Apply")',
                'button.jobs-apply-button'):
        b = page.locator(sel).first
        if b.count() and b.is_visible(timeout=2000):
            btn = b; break
    if btn is None:
        print("STOP: кнопки отклика нет — возможно, уже откликались"); sys.exit(2)
    btn.click(); time.sleep(6)

    dlg = page.locator('dialog[data-testid="dialog"]').first
    if not dlg.count():
        print("STOP: форма не открылась, url=", page.url); sys.exit(2)

    step = 0
    while step < 10:
        step += 1
        dump(dlg, step)
        head = dlg.inner_text()[:200].lower()

        if RESUME and "resume" in dlg.inner_text().lower() and MODE == "go":
            up = [b for b in buttons(dlg) if "загрузить резюме" in b[2] or "upload resume" in b[2]]
            if up:
                with page.expect_file_chooser(timeout=15000) as fc:
                    up[0][0].click()
                fc.value.set_files(RESUME)
                time.sleep(5)
                print("  >> загружено резюме:", RESUME.rsplit("\\", 1)[-1])

        bs = buttons(dlg)
        print("  кнопки:", [b[1][:45] for b in bs if b[1]])
        sub = [b for b in bs if any(w in b[2] for w in SUBMIT)]
        nxt = [b for b in bs if any(w in b[2] for w in NEXT)]

        if sub:
            if MODE == "go":
                sub[0][0].click(); time.sleep(6)
                page.screenshot(path=f"{SHOTS}\\_apply_{JID}_after.png")
                print("\nОТПРАВЛЕНО. состояние после:")
                print(page.locator("body").inner_text()[:500])
            else:
                page.screenshot(path=f"{SHOTS}\\_apply_{JID}_dry.png")
                print("\nDRY: кнопка отправки на месте —", sub[0][1], "— не жму.")
            break
        if not nxt:
            print("\nSTOP: ни «далее», ни «отправить»."); break
        nxt[0][0].click(); time.sleep(4)
finally:
    ctx.close(); p.stop()
