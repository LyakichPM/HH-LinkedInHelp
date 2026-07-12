"""Playwright browser context factory — proxy, user-agent, cookies."""

import json
import sys

from playwright.sync_api import sync_playwright

from hh.config import get, resolve_path

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def create_context(headless=False):
    """Create a Playwright browser context with proxy, UA, and cookies.

    Returns (playwright, browser, context). Caller MUST clean up:
        context.close()
        browser.close()
        p.stop()
    """
    proxy_url = get("proxy", "url")
    proxy = {"server": proxy_url} if proxy_url else None

    p = sync_playwright().start()
    b = p.chromium.launch(headless=headless, proxy=proxy)
    context = b.new_context(
        user_agent=DEFAULT_UA,
        locale="ru-RU",
        viewport={"width": 1400, "height": 1000},
    )

    # Load cookies if they exist
    cookie_file = resolve_path(get("hh", "cookie_file", default="hh_cookies.json"))
    try:
        with open(cookie_file, encoding="utf-8") as f:
            context.add_cookies(json.load(f))
    except FileNotFoundError:
        # Not fatal, but MUST be visible: without cookies the browser is a
        # guest and hh.ru silently redirects to login/signup walls.
        print(
            f"WARNING: no cookies loaded ({cookie_file} not found) — "
            "browser is a GUEST session. Run 'hh auth login' first.",
            file=sys.stderr,
        )

    return p, b, context


def new_page(headless=False):
    """Convenience: returns (playwright, browser, context, page)."""
    p, b, context = create_context(headless=headless)
    page = context.new_page()
    return p, b, context, page
