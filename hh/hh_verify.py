"""Verify vacancy status and check negotiations on hh.ru."""

import sys
import time
import json

from hh.browser import new_page
from hh.utils import normalize


def check_vacancy_status(vid, headless=False):
    """Check if already applied to a vacancy.

    Returns dict: {vid, applied, applied_text_found, title, employer}
    """
    url = f"https://hh.ru/vacancy/{vid}"
    p, b, context, page = new_page(headless=headless)

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(2000)

        body = normalize(page.locator("body").inner_text())

        title = ""
        try:
            title = page.locator("h1").first.inner_text().strip()
        except Exception:
            pass

        employer = ""
        try:
            el = page.locator(
                '[data-qa="vacancy-company-name"]'
            ).first
            employer = normalize(el.inner_text()).strip()
        except Exception:
            pass

        applied = "Вы откликнулись" in body

        return {
            "vid": vid,
            "applied": applied,
            "applied_text_found": applied,
            "title": title,
            "employer": employer,
        }

    finally:
        context.close()
        b.close()
        p.stop()


def check_negotiations(headless=False):
    """Check negotiations page for active conversations.

    Returns list of dicts: {vid, title, employer, status, date}
    """
    url = "https://hh.ru/applicant/negotiations"
    p, b, context, page = new_page(headless=headless)

    results = []

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(3000)

        cards = page.locator('[data-qa="negotiations-list-item"]').all()

        for card in cards:
            try:
                title = ""
                try:
                    title = card.locator(
                        '[data-qa="vacancy-title"]'
                    ).first.inner_text().strip()
                except Exception:
                    pass

                employer = ""
                try:
                    el = card.locator(
                        '[data-qa="employer-name"]'
                    ).first
                    employer = normalize(el.inner_text()).strip()
                except Exception:
                    pass

                status = ""
                try:
                    status = card.locator(
                        '[data-qa="negotiations-list-item-status"]'
                    ).first.inner_text().strip()
                except Exception:
                    pass

                link = ""
                try:
                    link = card.locator(
                        'a[data-qa="vacancy-title"]'
                    ).first.get_attribute("href") or ""
                except Exception:
                    pass

                vid = ""
                import re
                m = re.search(r"/vacancy/(\d+)", link)
                if m:
                    vid = m.group(1)

                results.append({
                    "vid": vid,
                    "title": title,
                    "employer": employer,
                    "status": status,
                    "link": link,
                })
            except Exception:
                continue

    finally:
        context.close()
        b.close()
        p.stop()

    return results


# --- CLI ---

def status_cli(vid, headless):
    """CLI handler — check single vacancy status."""
    result = check_vacancy_status(vid, headless=headless)
    status = "✅ Applied" if result["applied"] else "⬜ Not applied"
    print(f"{result['title'] or 'N/A'}")
    print(f"  Employer: {result['employer'] or 'N/A'}")
    print(f"  Status: {status}")


def negotiations_cli(headless, json_output):
    """CLI handler — list negotiations."""
    results = check_negotiations(headless=headless)

    if json_output:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    if not results:
        print("No active negotiations found.")
        return

    print(f"\nActive negotiations: {len(results)}\n")
    for n in results:
        print(f'  {n["title"]}')
        print(f'    {n["employer"]} | {n["status"]}')
        print(f'    {n["link"]}')
        print()
