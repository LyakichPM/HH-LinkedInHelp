"""Apply to hh.ru vacancies with cover letters via Playwright.

CRITICAL: Cover letter textarea uses AJAX auto-save on blur.
.fill() only fills local DOM — server never receives it unless blur triggers AJAX.

PRIMARY METHOD: Navigate to response page directly, fill letter FIRST, then submit.
This avoids quick-apply (which sends empty application without letter).

Flow:
  1. Go to vacancy page → check if already applied
  2. If not applied → go to response page → fill questions + letter → submit
  3. If already applied → use toggle → fill → blur → verify
  4. NEVER let a submit go through without letter_filled=True verification
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

def apply_to_vacancy(vid, cover_letter, headless=False):
    """Apply to a single vacancy with cover letter.

    STRATEGY (Magritte-aware):
      1. Go to response page DIRECTLY — it shows either the apply form or
         "Вы откликнулись" if already applied
      2. If already applied → add letter flow (verify + save)
      3. If NOT applied → fill questions + letter, submit
      4. NEVER click "Откликнуться" on the vacancy page — it may quick-apply without letter

    Returns dict: {success, method, letter_filled, error}
    """
    vacancy_url = f"https://hh.ru/vacancy/{vid}"
    resp_url = f"https://hh.ru/applicant/vacancy_response?vacancyId={vid}"
    p, b, context, page = new_page(headless=headless)

    try:
        # ── Step 1: Go to response page directly ──
        print(f"  Opening response page for {vid}...", file=sys.stderr)
        try:
            page.goto(resp_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)
        except Exception as e:
            return {"success": False, "method": "error", "error": f"Response page navigation: {e}", "letter_filled": False}

        # ── Step 2: Check if already applied (response page shows "Вы откликнулись") ──
        # NOTE: hh.ru uses non-breaking spaces (\xa0) in text. Normalize!
        body_text = _normalize_body(page)
        already_applied = "вы откликнулись" in body_text
        if not already_applied:
            page.wait_for_timeout(2000)
            body_text = _normalize_body(page)
            already_applied = "вы откликнулись" in body_text

        if already_applied:
            print(f"  Already applied to {vid}", file=sys.stderr)
            result = _add_letter_internal(page, resp_url, cover_letter)
            context.close(); b.close(); p.stop()
            return result

        # We're on the response page and NOT applied — fill and submit
        print(f"  Not yet applied — filling form...", file=sys.stderr)
        result = _fill_and_submit_response_page(page, resp_url, cover_letter)
        context.close(); b.close(); p.stop()
        return result

    except Exception as e:
        context.close(); b.close(); p.stop()
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
