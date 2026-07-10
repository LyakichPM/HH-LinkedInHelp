"""hh.ru authentication: login via browser, save/check cookies."""

import json
import sys

from hh.browser import create_context, DEFAULT_UA
from hh.config import get
from hh.utils import normalize


HH_LOGIN_URL = "https://hh.ru/account/login"
HH_MAIN_URL = "https://hh.ru/"


def login():
    """Open browser for user to log in manually, then save cookies."""
    cookie_file = get("hh", "cookie_file", default="hh_cookies.json")

    p, b, context = create_context(headless=False)
    page = context.new_page()

    print("Opening hh.ru login page...", file=sys.stderr)
    print("Please log in manually in the browser window.", file=sys.stderr)
    print("After successful login, press Ctrl+C in this terminal.", file=sys.stderr)
    print("Cookies will be saved automatically.", file=sys.stderr)

    page.goto(HH_LOGIN_URL, wait_until="domcontentloaded", timeout=60000)

    try:
        # Wait until user presses Ctrl+C or the hh.ru main page is reached
        import time as _time
        while True:
            _time.sleep(2)
            current = page.url
            if "/login" not in current and "hh.ru" in current:
                # Check if actually logged in
                body = normalize(page.locator("body").inner_text())
                if "Войти" not in body[:300]:
                    break
    except KeyboardInterrupt:
        pass

    # Save cookies
    cookies = context.cookies()
    with open(cookie_file, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    print(f"Cookies saved to {cookie_file}", file=sys.stderr)

    context.close()
    b.close()
    p.stop()


def check_auth():
    """Return True if cookies look valid (can load hh.ru)."""
    cookie_file = get("hh", "cookie_file", default="hh_cookies.json")
    try:
        with open(cookie_file, encoding="utf-8") as f:
            cookies = json.load(f)
        if not cookies:
            return False
        # Check for hh.ru session cookies
        hh_domain = any("hh.ru" in c.get("domain", "") for c in cookies)
        return hh_domain
    except (FileNotFoundError, json.JSONDecodeError):
        return False


def status():
    """Print auth status message."""
    if check_auth():
        print("Auth: ✅ Cookies found")
    else:
        print("Auth: ❌ Not logged in. Run: hh auth login")
