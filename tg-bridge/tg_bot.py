"""tg-bot — Telegram bot that listens for messages and writes to inbox.

Runs as a long-lived process, polling Telegram for new messages.
Writes each incoming message to tg_inbox.jsonl for Claude Code to consume.

Usage:
    python tg_bot.py [--poll-interval 5]

Or via hh CLI:
    hh tg listen
"""

import json
import os
import sys
import time
import argparse

import requests


def load_config():
    """Load config from config.local.json (walk up to hh-agent dir)."""
    start = os.path.dirname(os.path.abspath(__file__))
    for _ in range(3):
        path = os.path.join(start, "config.local.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        start = os.path.dirname(start)
    return None


def get_inbox_path(config):
    """Get inbox file path from config or default.

    Relative paths resolve against the REPO ROOT (parent of tg-bridge/),
    same anchor as hh.config.resolve_path — keep them in sync, or the
    listener writes to one file while `hh tg inbox` reads another.
    """
    inbox = config.get("telegram", {}).get("inbox_file", "tg-bridge/tg_inbox.jsonl")
    if not os.path.isabs(inbox):
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(repo_root, inbox)
    return inbox


def write_inbox(text, inbox_path):
    """Append a message to the inbox JSONL file."""
    entry = {
        "text": text,
        "timestamp": time.time(),
        "source": "telegram",
    }
    with open(inbox_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Telegram inbox listener")
    parser.add_argument(
        "--poll-interval", type=int, default=5,
        help="Polling interval in seconds (default: 5)",
    )
    args = parser.parse_args()

    config = load_config()
    if not config:
        print("Error: config.local.json not found", file=sys.stderr)
        sys.exit(1)

    token = config.get("telegram", {}).get("bot_token")
    allowed_chat_id = str(config.get("telegram", {}).get("chat_id", ""))
    inbox_path = get_inbox_path(config)

    if not token or not allowed_chat_id:
        print(
            "Error: telegram.bot_token and telegram.chat_id must be set",
            file=sys.stderr,
        )
        sys.exit(1)

    url = f"https://api.telegram.org/bot{token}"
    last_update_id = 0

    print(f"Listening for messages (poll every {args.poll_interval}s)...", file=sys.stderr)
    print(f"Inbox: {inbox_path}", file=sys.stderr)
    print(f"Allowed chat: {allowed_chat_id}", file=sys.stderr)
    print("Press Ctrl+C to stop.", file=sys.stderr)

    while True:
        try:
            resp = requests.get(
                f"{url}/getUpdates",
                params={
                    "offset": last_update_id + 1,
                    "timeout": args.poll_interval,
                },
                timeout=args.poll_interval + 5,
            )
            resp.raise_for_status()
            updates = resp.json().get("result", [])

            for update in updates:
                update_id = update.get("update_id", 0)
                if update_id <= last_update_id:
                    continue
                last_update_id = update_id

                msg = update.get("message") or update.get("callback_query", {}).get("message", {})
                chat_id = str(msg.get("chat", {}).get("id", ""))

                if chat_id != allowed_chat_id:
                    continue

                text = msg.get("text", "")
                if text and text.strip():
                    write_inbox(text.strip(), inbox_path)
                    print(f"\n📩 {text[:60]}{'...' if len(text) > 60 else ''}", file=sys.stderr)

        except requests.exceptions.Timeout:
            pass  # expected on long poll
        except KeyboardInterrupt:
            print("\nStopped.", file=sys.stderr)
            break
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            time.sleep(5)


if __name__ == "__main__":
    main()
