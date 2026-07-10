"""Search vacancies on hh.ru via Playwright."""

import json
import sys
import time

from hh.browser import new_page
from hh.utils import normalize


def search(query, salary=None, period=14, max_pages=2, headless=False):
    """Search hh.ru for vacancies matching query.

    Yields dicts: {vid, title, employer, salary, link, applied}
    """
    seen = set()
    base_url = (
        f"https://hh.ru/search/vacancy"
        f"?text={query}"
        f"&area=113"
        f"&ored_clusters=true"
        f"&order_by=publication_time"
        f"&search_period={period}"
        f"&items_on_page=20"
    )
    if salary:
        base_url += f"&salary={salary}"

    p, b, context, page = new_page(headless=headless)

    try:
        for page_num in range(max_pages):
            url = base_url if page_num == 0 else base_url + f"&page={page_num}"
            print(f"  Fetching page {page_num + 1}...", file=sys.stderr)

            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            time.sleep(3)

            body = normalize(page.locator("body").inner_text())

            # Check for captcha
            if "captcha" in body.lower():
                print("  Captcha detected — stopping search", file=sys.stderr)
                break

            cards = page.locator('[data-qa="vacancy-serp__vacancy"]').all()
            if not cards:
                break

            for card in cards:
                try:
                    title_el = card.locator('[data-qa="serp-item__title"]').first
                    title = normalize(title_el.inner_text().strip())
                    link = title_el.get_attribute("href") or ""
                    vid = link.split("/")[-1].split("?")[0] if link else ""

                    if not vid or vid in seen:
                        continue
                    seen.add(vid)

                    employer = ""
                    try:
                        e = card.locator(
                            '[data-qa="vacancy-serp__vacancy-employer"]'
                        ).first
                        if e.is_visible(timeout=500):
                            employer = normalize(e.inner_text()).strip()
                    except Exception:
                        pass

                    salary_text = ""
                    try:
                        s = card.locator(
                            '[data-qa="vacancy-serp__vacancy-compensation"]'
                        ).first
                        if s.is_visible(timeout=500):
                            salary_text = normalize(s.inner_text()).strip()
                    except Exception:
                        pass

                    applied = False
                    try:
                        a = card.locator(
                            '[data-qa="vacancy-serp__vacancy_response"]'
                        )
                        if a.is_visible(timeout=500):
                            applied = True
                    except Exception:
                        pass

                    yield {
                        "vid": vid,
                        "title": title,
                        "employer": employer,
                        "salary": salary_text,
                        "link": f"https://hh.ru/vacancy/{vid}",
                        "applied": applied,
                    }
                except Exception:
                    continue

            time.sleep(2)

    finally:
        context.close()
        b.close()
        p.stop()


# --- CLI ---
def search_cli(query, salary, period, max_pages, json_output, headless):
    """CLI handler — print results."""
    results = list(
        search(
            query,
            salary=salary,
            period=period,
            max_pages=max_pages,
            headless=headless,
        )
    )

    if json_output:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    print(f"\nFound {len(results)} vacancies:\n")
    for v in results:
        status = "✅" if v["applied"] else "⬜"
        print(f'{status} {v["title"]}')
        print(f'   {v["employer"]} | {v["salary"]}')
        print(f'   {v["link"]}')
        print()
