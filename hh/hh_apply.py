"""Apply to hh.ru vacancies with cover letters via Playwright.

╔══════════════════════════════════════════════════════════════════════╗
║ DANGER: `applicant/vacancy_response?vacancyId=` is a WRITE endpoint. ║
║ For vacancies WITHOUT screening questions, merely LOADING this URL   ║
║ AUTO-SUBMITS an empty application. NEVER use it to probe             ║
║ applied-status — use hh_verify.py (read-only /vacancy/<vid> and      ║
║ /applicant/negotiations) or inspect the employer chat instead.       ║
║ (2026-07-12: probing this URL created ~10 empty applications.)       ║
╚══════════════════════════════════════════════════════════════════════╝

CRITICAL: Cover letter textarea uses AJAX auto-save on blur.
.fill() only fills local DOM — server never receives it unless blur triggers AJAX.

PRIMARY METHOD (2026-07-13, letter-first): click "Откликнуться" on the
/vacancy/<vid> page and fill the cover letter inside the response POPUP
before submitting — the application is created WITH the letter and it
lands as the first employer-chat bubble. Never navigate to
vacancy_response directly for the initial apply: for question-less
vacancies that page auto-submits an EMPTY application on load.

Flow (apply_to_vacancy → _apply_via_vacancy_page):
  1. Go to vacancy page → check if already applied ("Вы откликнулись")
  2. Click the apply button → one of three outcomes:
     a. response POPUP appears → fill letter textarea → submit  (best path)
     b. navigation to vacancy_response (screening questions) →
        _fill_and_submit_response_page fills questions + letter → submit
     c. quick-apply, no popup ("Вы откликнулись" without a form) →
        application went WITHOUT letter → caller MUST repair via chat
  3. If already applied → letter via employer chat message, not the
     response-record toggle (the record letter never reaches the chat)
  4. NEVER let a submit go through without letter_filled=True verification

RESULT-FLAG RELIABILITY (verified 2026-07-12, see agent/instructions.md):
  - Question-FUL vacancies: letter lands in the employer chat, but the
    post-submit readback often returns a FALSE NEGATIVE
    ("Letter not persisted after submit"). Don't trust the failure flag.
  - Question-LESS vacancies: page-load auto-submits empty, then the letter
    saved via the response-record toggle does NOT reach the employer chat
    (chat still shows "Без сопроводительного письма") — success flag lies.
    Repair by sending the letter as a chat MESSAGE (hh.ru/chat/<chatId>,
    textarea [data-qa="chatik-new-message-text"]).
  - The ONLY source of truth: the first chat bubble
    ([data-qa^="chatik-chat-message-"][data-qa$="-text"]) contains the
    letter text, not "Без сопроводительного письма".
"""

import sys
import time
import re

from hh.browser import new_page
from hh.utils import normalize
from hh.config import get


# ── helpers ───────────────────────────────────────────────────────────

def _visible_textarea_indices(page):
    """Return set of indices of visible textareas on the page."""
    result = set()
    for i, ta in enumerate(page.locator("textarea").all()):
        try:
            if ta.is_visible(timeout=200):
                result.add(i)
        except Exception:
            pass
    return result


def _handle_radio_questions(page):
    """Handle radio-button questions (data-qa='task-body') on the response page."""
    for task in page.locator('[data-qa="task-body"]').all():
        try:
            if not task.is_visible(timeout=300):
                continue
        except Exception:
            continue
        try:
            if task.locator("textarea").count() > 0:
                continue
        except Exception:
            continue
        try:
            question_text = task.locator('[data-qa="task-question"]').inner_text().lower()
        except Exception:
            continue

        cells = task.locator('[data-qa="cell"]').all()
        opt_map = {}
        for opt in cells:
            try:
                opt_text = opt.inner_text().strip().lower()
                opt_map[opt_text] = opt
            except Exception:
                pass
        if not opt_map:
            continue

        clicked = False
        if "опыт" in question_text:
            for pref in ["1-3 года", "более 3 лет", "менее 1 года", "нет опыта"]:
                if pref in opt_map:
                    try:
                        opt_map[pref].click()
                        time.sleep(0.2)
                        clicked = True
                        break
                    except Exception:
                        pass
        if not clicked:
            for pref in ["нет", "да"]:
                if pref in opt_map:
                    try:
                        opt_map[pref].click()
                        time.sleep(0.2)
                        clicked = True
                        break
                    except Exception:
                        pass
        if not clicked:
            try:
                list(opt_map.values())[0].click()
                time.sleep(0.2)
            except Exception:
                pass


def _handle_text_questions(page):
    """Fill visible textarea questions (before cover letter toggle)."""
    for ta in page.locator("textarea").all():
        try:
            if not ta.is_visible(timeout=300):
                continue
        except Exception:
            continue
        near = ""
        try:
            near = ta.locator("xpath=ancestor::*[@data-qa='task-body']").inner_text().lower()
        except Exception:
            try:
                near = ta.locator("xpath=ancestor::div[4]").inner_text().lower()
            except Exception:
                pass
        answer = "Готов обсудить на собеседовании."
        if "зарплат" in near:
            answer = "400 000 - 500 000 рублей"
        elif "b2c" in near or "в2с" in near or "продукт" in near:
            answer = "Управлял B2C-продуктами для 100+ партнерских команд в 50+ GEO."
        elif "опыт" in near:
            answer = "Teamlead PM (2 года) в iGaming, Lead Financial Analyst (2.5 года) в FinTech."
        elif "ожидан" in near:
            answer = "400 000 - 500 000 рублей"
        try:
            ta.fill(answer)
            time.sleep(0.2)
        except Exception:
            pass


def _blur_and_wait(page, wait_sec=5):
    """Trigger blur on focused element and wait for AJAX auto-save."""
    try:
        page.keyboard.press("Tab")
    except Exception:
        pass
    time.sleep(wait_sec)


def _get_letter_text(page):
    """Get current cover letter text from textarea, or None.

    Strategy (Magritte-aware):
    1. If toggle is visible and says 'Добавить' → no letter exists → return None
    2. If toggle is visible and says something else → letter exists, click to reveal, read textarea
    3. If toggle is NOT visible → letter may have been saved (toggle collapses after save).
       Read all visible textareas; if any has content > 20 chars, it's the cover letter.
    4. If nothing found → return None
    """
    toggle_found = False
    try:
        toggle = page.locator('[data-qa="vacancy-response-letter-toggle"]').first
        toggle_found = toggle.is_visible(timeout=1000)
        if toggle_found:
            toggle_text = toggle.inner_text().lower().replace('\xa0', ' ')
            # Toggle showing "Добавить" means no letter saved
            if "добавить" in toggle_text:
                return None
            # Letter exists — click to reveal and read
            toggle.click()
            time.sleep(1.5)
    except Exception:
        pass

    # Read all visible textareas
    for ta in page.locator("textarea").all():
        try:
            if ta.is_visible(timeout=200):
                val = ta.input_value()
                if val and len(val) > 20:
                    return val
        except Exception:
            pass
    return None


def _normalize_body(page):
    """Get body text with non-breaking spaces normalized to regular spaces."""
    return page.locator("body").inner_text().lower().replace('\xa0', ' ')


def _toggle_and_fill(page, expected_text):
    """Click the letter toggle then fill the newly-visible textarea.

    Returns True if filled, False if toggle or textarea couldn't be found.
    """
    toggle = page.locator('[data-qa="vacancy-response-letter-toggle"]').first
    try:
        if toggle.is_visible(timeout=2000):
            toggle.click()
            time.sleep(1.5)
        else:
            return False
    except Exception:
        return False

    for ta in page.locator("textarea").all():
        try:
            if ta.is_visible(timeout=200):
                ta.fill(expected_text)
                time.sleep(0.5)
                print(f"  Textarea filled after toggle", file=sys.stderr)
                return True
        except Exception:
            continue
    return False


def _verify_letter_persisted(page, resp_url, expected_text, max_retries=2):
    """Toggle → fill → blur → wait → reload → verify → retry if needed.

    This is the ONLY reliable way to verify a cover letter saved.
    input_value() after fill reads local DOM — not server state.
    The toggle starts collapsed ('Добавить'), so we MUST click it first.
    """
    for attempt in range(max_retries + 1):
        print(f"  Letter verify attempt {attempt + 1}/{max_retries + 1}...", file=sys.stderr)

        filled = _toggle_and_fill(page, expected_text)
        if not filled:
            print(f"  Could not toggle or find textarea", file=sys.stderr)
            if attempt < max_retries:
                page.goto(resp_url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(1)
                continue
            return False

        _blur_and_wait(page, wait_sec=5)

        try:
            page.goto(resp_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)
        except Exception as e:
            print(f"  Reload failed: {e}", file=sys.stderr)
            continue

        saved = _get_letter_text(page)
        if saved and expected_text[:50] in saved:
            print(f"  Letter VERIFIED (persisted after reload)", file=sys.stderr)
            return True
        else:
            print(f"  Letter NOT persisted", file=sys.stderr)
            if attempt < max_retries:
                print(f"  Retrying...", file=sys.stderr)
                time.sleep(1)
    return False


def _fill_and_submit_response_page(page, resp_url, cover_letter):
    """Fill response form (questions + letter) and submit.

    Called when vacancy is NOT yet applied and response page shows the apply form.
    Returns dict: {success, letter_filled, method, error}
    """
    # Phase 1: Handle radio questions
    _handle_radio_questions(page)

    # Phase 2: Save textarea indices BEFORE toggle
    indices_before = _visible_textarea_indices(page)

    # Phase 3: Fill text questions (before toggle)
    _handle_text_questions(page)

    # Phase 4: Toggle for cover letter
    letter_toggle = page.locator('[data-qa="vacancy-response-letter-toggle"]').first
    has_toggle = False
    try:
        has_toggle = letter_toggle.is_visible(timeout=3000)
    except Exception:
        pass
    if has_toggle:
        letter_toggle.click()
        page.wait_for_timeout(1500)

    # Phase 5: Fill cover letter
    indices_after = _visible_textarea_indices(page)
    new_indices = indices_after - indices_before
    if not new_indices:
        total_ta = len(page.locator("textarea").all())
        new_indices = set(range(total_ta)) - indices_before

    letter_filled = False
    for i, ta in enumerate(page.locator("textarea").all()):
        try:
            if i in new_indices or (i not in indices_before and ta.is_visible(timeout=200)):
                ta.fill(cover_letter)
                letter_filled = True
                page.wait_for_timeout(500)
                print(f"  Letter filled in textarea #{i}", file=sys.stderr)
                break
        except Exception:
            continue

    if not letter_filled:
        for ta in page.locator("textarea").all():
            try:
                if ta.is_visible(timeout=200):
                    ta.fill(cover_letter)
                    letter_filled = True
                    page.wait_for_timeout(500)
                    print(f"  Letter filled via fallback", file=sys.stderr)
                    break
            except Exception:
                continue

    # Blur to trigger any AJAX
    if letter_filled:
        _blur_and_wait(page, wait_sec=3)

    # Find and click submit
    submit_btn = page.locator('[data-qa="vacancy-response-submit-popup"]').first
    if not submit_btn.is_visible(timeout=2000):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(500)

    if submit_btn.is_visible(timeout=5000):
        try:
            submit_btn.scroll_into_view_if_needed(timeout=1000)
        except Exception:
            pass
        page.wait_for_timeout(200)
        submit_btn.click()
        page.wait_for_timeout(3000)

        # Wait for success
        for _ in range(15):
            try:
                body_text = page.locator("body").inner_text().lower().replace('\xa0', ' ')
                has_success = "вы откликнулись" in body_text
                has_chat = page.locator(
                    '[data-qa="vacancy-response-link-view-topic"]'
                ).first.is_visible(timeout=500)
                if has_success or has_chat:
                    # Verify letter persisted
                    if letter_filled and cover_letter:
                        page.goto(resp_url, wait_until="domcontentloaded", timeout=30000)
                        time.sleep(2)
                        saved = _get_letter_text(page)
                        if saved and cover_letter[:50] in saved:
                            return {"success": True, "letter_filled": True, "method": "response_page_submit"}
                        else:
                            return {"success": False, "letter_filled": False, "error": "Letter not persisted after submit"}
                    return {"success": True, "letter_filled": letter_filled, "method": "response_page_submit"}
            except Exception:
                pass
            page.wait_for_timeout(1000)

        return {"success": False, "letter_filled": letter_filled, "error": "Submit clicked but no success indicator"}

    # No submit button — might auto-submit (quick apply via response page)
    has_chat = page.locator(
        '[data-qa="vacancy-response-link-view-topic"]'
    ).first.is_visible(timeout=2000)
    if has_chat:
        return {"success": True, "letter_filled": letter_filled, "method": "auto_submit"}

    return {"success": False, "letter_filled": letter_filled, "method": "no_submit_btn",
            "error": "Submit button not found and no success indicator"}


# ── main apply logic ──────────────────────────────────────────────────

def _kill_cookie_banner(page):
    """The cookie banner intercepts clicks on lower-page elements."""
    try:
        page.evaluate("document.getElementById('bottom-cookies-policy-informer')?.remove()")
    except Exception:
        pass


def _apply_via_vacancy_page(page, vid, cover_letter):
    """Letter-first apply: click 'Откликнуться' on /vacancy/<vid> and fill
    the cover letter BEFORE the application is created.

    Outcomes (see module docstring):
      a. popup with letter textarea → fill → submit        (best)
      b. navigation to vacancy_response (screening q's)    → reuse form filler
      c. quick-apply, no popup → application went EMPTY    → caller repairs via chat

    Returns dict: {success, method, letter_filled, error}
    """
    vacancy_url = f"https://hh.ru/vacancy/{vid}"
    resp_url = f"https://hh.ru/applicant/vacancy_response?vacancyId={vid}"

    page.goto(vacancy_url, wait_until="domcontentloaded", timeout=45000)
    time.sleep(3)
    body_text = _normalize_body(page)
    if "captcha" in body_text:
        return {"success": False, "method": "captcha", "letter_filled": False,
                "error": "Captcha on vacancy page — stop and ask the user"}
    if "вы откликнулись" in body_text:
        return {"success": False, "method": "already_applied", "letter_filled": False,
                "error": "Already applied — send the letter as an employer-chat MESSAGE, "
                         "not via the response-record toggle (it never reaches the chat)"}

    _kill_cookie_banner(page)
    btn = page.locator('[data-qa="vacancy-response-link-top"]').first
    try:
        btn.wait_for(state="visible", timeout=10000)
    except Exception:
        return {"success": False, "method": "no_apply_button", "letter_filled": False,
                "error": "Apply button [vacancy-response-link-top] not found"}
    btn.click()
    time.sleep(3)

    # Outcome d: предупреждение о релокации. У вакансий с локацией вне региона
    # соискателя hh вклинивает модалку между кликом и формой отклика. Её кнопка
    # живёт вне dialog-контейнеров, поэтому ищем по data-qa. Не нажать — значит
    # получить no_popup_no_result и НЕ отправить ничего. Дальше ход обычный:
    # либо форма с вопросами, либо всплывашка с письмом.
    try:
        warn = page.locator('[data-qa="relocation-warning-confirm"]').first
        if warn.is_visible(timeout=3000):
            print("  Relocation warning → confirming", file=sys.stderr)
            warn.click()
            time.sleep(3)
    except Exception:
        pass

    # Outcome b: navigated to the full response form (screening questions)
    if "vacancy_response" in page.url:
        print("  Navigated to response form (screening questions)", file=sys.stderr)
        return _fill_and_submit_response_page(page, resp_url, cover_letter)

    # Outcome a: response popup. Observed data-qa's are the SAME as the full
    # response page: letter toggle 'vacancy-response-letter-toggle' and submit
    # 'vacancy-response-submit-popup' (selectors.json's popup-form-* variants
    # kept as fallback).
    submit = page.locator(
        '[data-qa="vacancy-response-submit-popup"], '
        '[data-qa="vacancy-response-popup-form-submit"]').first
    popup_open = False
    try:
        popup_open = submit.is_visible(timeout=8000)
    except Exception:
        pass

    if popup_open:
        # letter textarea: dedicated popup field → any visible textarea → toggle first
        ta = page.locator('[data-qa="vacancy-response-popup-form-letter"]').first
        try:
            ta_visible = ta.is_visible(timeout=1500)
        except Exception:
            ta_visible = False
        if not ta_visible:
            for cand in page.locator("textarea").all():
                try:
                    if cand.is_visible(timeout=300):
                        ta = cand
                        ta_visible = True
                        break
                except Exception:
                    pass
        if not ta_visible:
            try:
                tog = page.locator('[data-qa="vacancy-response-letter-toggle"]').first
                if tog.is_visible(timeout=2000):
                    tog.click()
                    time.sleep(1.5)
                    for cand in page.locator("textarea").all():
                        if cand.is_visible(timeout=300):
                            ta = cand
                            ta_visible = True
                            break
            except Exception:
                pass
        if not ta_visible:
            return {"success": False, "method": "popup_no_letter_field", "letter_filled": False,
                    "error": "Popup open but no letter textarea found — NOT submitted"}

        ta.fill(cover_letter)
        time.sleep(0.5)
        submit.click()
        for _ in range(15):
            time.sleep(1)
            try:
                body_text = _normalize_body(page)
                if "вы откликнулись" in body_text:
                    return {"success": True, "method": "popup_letter_first", "letter_filled": True}
            except Exception:
                pass
        return {"success": False, "method": "popup_letter_first", "letter_filled": True,
                "error": "Popup submitted but no 'вы откликнулись' confirmation — verify via chat"}

    # Outcome c: quick-apply — application already went, without a letter
    body_text = _normalize_body(page)
    if "вы откликнулись" in body_text:
        return {"success": True, "method": "quick_apply_NO_letter", "letter_filled": False,
                "error": "Quick-apply sent WITHOUT letter — repair via employer-chat message NOW"}

    return {"success": False, "method": "no_popup_no_result", "letter_filled": False,
            "error": "Apply clicked but neither popup, nor navigation, nor confirmation appeared"}


def apply_to_vacancy(vid, cover_letter, headless=False):
    """Apply to a single vacancy with cover letter — LETTER-FIRST.

    PRIMARY: _apply_via_vacancy_page (popup flow) — the letter is part of
    the application from the start and lands in the first chat bubble.
    NEVER navigates to vacancy_response directly (question-less vacancies
    auto-submit an EMPTY application on page load).

    Only call this when you INTEND to apply, never to check status.
    After it returns, verify the letter in the employer CHAT (first bubble):
    method 'quick_apply_NO_letter' means the caller MUST send the letter
    as a chat message immediately.

    Returns dict: {success, method, letter_filled, error}
    """
    p, b, context, page = new_page(headless=headless)
    try:
        return _apply_via_vacancy_page(page, vid, cover_letter)
    except Exception as e:
        return {"success": False, "method": "error", "error": str(e), "letter_filled": False}
    finally:
        try:
            context.close()
            b.close()
            p.stop()
        except Exception:
            pass


def _add_letter_internal(page, resp_url, cover_letter):
    """Internal: add letter to already-applied vacancy (reuses open page/browser)."""
    try:
        page.goto(resp_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)
    except Exception:
        pass
    success = _verify_letter_persisted(page, resp_url, cover_letter, max_retries=3)
    if success:
        return {"success": True, "method": "verify_save", "letter_filled": True, "error": None}
    return {"success": False, "method": "letter_not_saved", "error": "Could not save cover letter", "letter_filled": False}


def add_letter_to_vacancy(vid, cover_letter, headless=False):
    """Add/edit cover letter on an already-applied vacancy.

    Uses _verify_letter_persisted: fill → blur → wait → reload → verify.
    Only returns success after verification.
    """
    resp_url = f"https://hh.ru/applicant/vacancy_response?vacancyId={vid}"
    p, b, context, page = new_page(headless=headless)

    try:
        print(f"  Opening {vid} response page...", file=sys.stderr)
        page.goto(resp_url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(2000)

        success = _verify_letter_persisted(page, resp_url, cover_letter, max_retries=3)
        if success:
            return {"success": True, "method": "verify_save", "letter_filled": True, "error": None}

        return {"success": False, "method": "letter_not_saved", "error": "Could not save cover letter after retries", "letter_filled": False}

    except Exception as e:
        return {"success": False, "method": "error", "error": str(e), "letter_filled": False}

    finally:
        context.close()
        b.close()
        p.stop()


# ── Batch apply ───────────────────────────────────────────────────────

def apply_batch(vacancies, cover_letters, headless=False):
    """Apply to multiple vacancies with cover letters.

    If letter_filled is False and cover_letter is not empty, the apply
    is considered FAILED even if "Вы откликнулись" appeared.
    """
    for v in vacancies:
        vid = v["vid"]
        title = v.get("title", vid)
        letter = cover_letters.get(vid, "")

        print(f"\n{'='*60}", file=sys.stderr)
        print(f"Applying to: {title} ({vid})", file=sys.stderr)

        result = apply_to_vacancy(vid, letter, headless=headless)

        yield {
            "vid": vid,
            "title": title,
            "success": result["success"],
            "method": result.get("method", "unknown"),
            "letter_filled": result.get("letter_filled", False),
            "error": result.get("error"),
        }

        if result["success"]:
            lf = "YES" if result.get("letter_filled") else "NO LETTER"
            print(f"  OK ({result.get('method')}) letter={lf}", file=sys.stderr)
        else:
            print(f"  FAIL ({result.get('method')}): {result.get('error') or 'N/A'}", file=sys.stderr)

        time.sleep(3)


# ── CLI ───────────────────────────────────────────────────────────────

def apply_cli(vid, letter_file, headless):
    """CLI handler — apply to a single vacancy with letter from file."""
    with open(letter_file, encoding="utf-8") as f:
        letter = f.read()

    result = apply_to_vacancy(vid, letter, headless=headless)

    if result["success"]:
        if result.get("letter_filled"):
            print(f"OK Applied ({result.get('method')}) with letter")
        else:
            print(f"OK Applied ({result.get('method')}) NO LETTER")
    else:
        err = result.get('error', 'N/A')
        method = result.get('method', 'unknown')
        print(f"FAIL {method}: {err}")
        sys.exit(1)
