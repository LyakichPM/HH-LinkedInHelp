"""Telegram module — send messages and read inbox via Bot API.

Thin wrapper around requests to Telegram Bot API.
Inbox uses a JSONL file (tg_inbox.jsonl) as a cross-session queue.
"""

import json
import os
import sys
import time

import requests

from hh.config import get, resolve_path


# --- paths ---

def _inbox_path():
    """Path to the inbox JSONL file.

    Must match where tg-bridge/tg_bot.py (the canonical listener) writes,
    otherwise reader and writer split-brain and messages look 'lost'.
    """
    return resolve_path(
        get("telegram", "inbox_file", default="tg-bridge/tg_inbox.jsonl")
    )


def _bot_token():
    """Get bot token from config."""
    token = get("telegram", "bot_token")
    if not token:
        print("Error: telegram.bot_token not set in config.local.json", file=sys.stderr)
        sys.exit(1)
    return token


def _chat_id():
    """Get default chat ID from config."""
    cid = get("telegram", "chat_id")
    if not cid:
        print("Error: telegram.chat_id not set in config.local.json", file=sys.stderr)
        sys.exit(1)
    return cid


def _thread_id(thread=None):
    """Resolve a forum topic id.

    The shared group is a forum: without message_thread_id the message lands in
    the group's general stream instead of the topic, where nobody reads it.
    `thread` may be a topic name from telegram.threads ("hh", "linkedin") or a
    bare number; None falls back to telegram.thread_id.
    """
    names = get("telegram", "threads", default={}) or {}
    if thread is None:
        thread = get("telegram", "thread_id")
    if thread is None or thread == "":
        return None
    if isinstance(thread, str):
        if thread in names:
            thread = names[thread]
        elif thread.lstrip("-").isdigit():
            thread = int(thread)
        else:
            print(f"Error: unknown topic {thread!r}; known: {sorted(names)}",
                  file=sys.stderr)
            sys.exit(1)
    return int(thread)


# --- send ---

def send_message(text, chat_id=None, parse_mode=None, thread=None):
    """Send a plain text message to a Telegram chat.

    Returns requests.Response object.
    """
    token = _bot_token()
    chat_id = chat_id or _chat_id()
    thread_id = _thread_id(thread)

    payload = {"chat_id": chat_id, "text": text}
    if thread_id is not None:
        payload["message_thread_id"] = thread_id
    if parse_mode:
        payload["parse_mode"] = parse_mode

    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    return resp


def send_document(file_path, caption=None, chat_id=None, thread=None):
    """Send a file as a document to a Telegram chat."""
    token = _bot_token()
    chat_id = chat_id or _chat_id()
    thread_id = _thread_id(thread)

    with open(file_path, "rb") as f:
        files = {"document": f}
        data = {"chat_id": chat_id}
        if thread_id is not None:
            data["message_thread_id"] = thread_id
        if caption:
            data["caption"] = caption

        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendDocument",
            data=data,
            files=files,
            timeout=60,
        )
        resp.raise_for_status()
        return resp


# --- inbox ---

def write_inbox(text):
    """Append a message to the inbox JSONL file.

    Each line is a JSON object: {text, timestamp, source}
    Used by Claude Code session to pick up out-of-band instructions.
    """
    path = _inbox_path()
    entry = {
        "text": text,
        "timestamp": time.time(),
        "source": "telegram",
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return path


def read_inbox(clear=False):
    """Read all messages from the inbox JSONL file.

    Returns list of dicts: [{text, timestamp, source}]
    If clear=True, empties the file after reading.
    """
    path = _inbox_path()
    messages = []

    if not os.path.exists(path):
        return messages

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    if clear:
        open(path, "w", encoding="utf-8").close()

    return messages


def inbox_count():
    """Return number of unread inbox messages."""
    return len(read_inbox(clear=False))


# --- CLI ---

def send_cli(text, chat_id, thread=None):
    """CLI handler — send a message."""
    result = send_message(text, chat_id=chat_id, thread=thread)
    if result.ok:
        r = result.json().get("result", {})
        where = f", топик {r.get('message_thread_id')}" if r.get("message_thread_id") else ""
        print(f"✅ Message sent (id={r.get('message_id', '?')}{where})")
    else:
        print(f"❌ Failed: {result.text}")
        sys.exit(1)


def inbox_cli(clear):
    """CLI handler — read inbox."""
    messages = read_inbox(clear=clear)
    if not messages:
        print("Inbox is empty.")
        return

    print(f"Inbox ({len(messages)} messages):\n")
    for m in messages:
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(m.get("timestamp", 0)))
        print(f"[{ts}] {m['text']}")
        print()

    if clear:
        print("Inbox cleared.")
