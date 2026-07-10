"""hh — CLI tool for hh.ru job search and application.

Usage:
    hh search --query "Python" --salary 150000
    hh apply <vid> --letter cover.txt
    hh verify <vid>
    hh negotiations
    hh auth login
    hh auth status
    hh tg send "Hello"
    hh tg inbox
    hh setup
"""

import sys
import os

import click

from hh.config import get, load as load_config


# ──────────────────────────── search ────────────────────────────

@click.group()
def cli():
    """hh.ru job search and application toolkit."""
    pass


@cli.command()
@click.option("-q", "--query", required=True, help="Search query")
@click.option("-s", "--salary", type=int, help="Minimum salary")
@click.option("-p", "--period", default=14, show_default=True, help="Search period (days)")
@click.option("-m", "--max-pages", default=2, show_default=True, help="Max pages to scan")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--headless", is_flag=True, help="Run browser headless (no GUI)")
def search(query, salary, period, max_pages, json_output, headless):
    """Search vacancies on hh.ru."""
    from hh.hh_search import search_cli
    search_cli(query, salary, period, max_pages, json_output, headless)


# ──────────────────────────── apply ────────────────────────────

@cli.command()
@click.argument("vid")
@click.option("-l", "--letter", required=True, help="Cover letter file path")
@click.option("--headless", is_flag=True, help="Run browser headless (no GUI)")
def apply(vid, letter, headless):
    """Apply to a vacancy with a cover letter.

    VID is the vacancy ID (number from hh.ru/vacancy/NNNNN).
    """
    from hh.hh_apply import apply_cli
    apply_cli(vid, letter, headless)


# ──────────────────────────── auth ────────────────────────────

@cli.group()
def auth():
    """Manage hh.ru authentication."""
    pass


@auth.command("login")
def auth_login():
    """Open browser for manual login and save cookies."""
    from hh.hh_auth import login
    login()


@auth.command("status")
def auth_status():
    """Check if cookies are valid."""
    from hh.hh_auth import status
    status()


# ──────────────────────────── verify ────────────────────────────

@cli.command()
@click.argument("vid")
@click.option("--headless", is_flag=True, help="Run browser headless (no GUI)")
def verify(vid, headless):
    """Check if already applied to a vacancy."""
    from hh.hh_verify import status_cli
    status_cli(vid, headless)


@cli.command()
@click.option("--headless", is_flag=True, help="Run browser headless (no GUI)")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def negotiations(headless, json_output):
    """List active negotiations."""
    from hh.hh_verify import negotiations_cli
    negotiations_cli(headless, json_output)


# ──────────────────────────── telegram ────────────────────────────

@cli.group()
def tg():
    """Telegram integration."""
    pass


@tg.command()
@click.argument("text")
@click.option("-c", "--chat-id", help="Override chat ID")
def send(text, chat_id):
    """Send a Telegram message."""
    from hh.telegram import send_cli
    send_cli(text, chat_id)


@tg.command()
@click.option("--clear", is_flag=True, help="Clear inbox after reading")
def inbox(clear):
    """Read incoming Telegram messages."""
    from hh.telegram import inbox_cli
    inbox_cli(clear)


@tg.command()
def count():
    """Show number of unread inbox messages."""
    from hh.telegram import inbox_count
    count = inbox_count()
    print(f"Unread messages: {count}")


# ──────────────────────────── setup ────────────────────────────

@cli.command()
def setup():
    """Run first-time setup (check config, cookies, dependencies)."""
    print("hh-agent setup check\n")

    # 1. Config
    print("1. Config file...", end=" ")
    try:
        load_config()
        print("✅")
    except SystemExit:
        print("❌")
        print(f"   Create config.local.json from config/config.example.json")
        return

    # 2. Telegram
    token = get("telegram", "bot_token")
    cid = get("telegram", "chat_id")
    if token and cid:
        print(f"2. Telegram config... ✅ (bot + chat_id)")
    else:
        print(f"2. Telegram config... ❌ (fill telegram.bot_token and telegram.chat_id)")

    # 3. Auth
    from hh.hh_auth import check_auth
    if check_auth():
        print("3. hh.ru auth cookies... ✅")
    else:
        print("3. hh.ru auth cookies... ❌")
        print("   Run: hh auth login")

    # 4. Playwright
    print("4. Playwright browsers...", end=" ")
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "--dry-run"],
        capture_output=True, text=True, timeout=30,
    )
    if "chromium" in result.stdout or "No packages to install" in result.stdout:
        print("✅")
    else:
        print("⚠️  (run: playwright install chromium)")

    # 5. Proxy (optional)
    proxy = get("proxy", "url")
    if proxy:
        print(f"5. Proxy... ✅ ({proxy})")
    else:
        print("5. Proxy... ⚠️  not set (optional)")

    print("\nSetup check complete.")


# ──────────────────────────── main ────────────────────────────

if __name__ == "__main__":
    cli()
