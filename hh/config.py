"""Load config.local.json — secrets (TG token, proxy, cookies path)."""

import json
import os
import sys

_CONFIG = None

CONFIG_PATHS = [
    "config.local.json",
    os.path.join(os.path.dirname(__file__), "..", "config.local.json"),
]


def load():
    """Find and load config.local.json. Exits with error if missing."""
    global _CONFIG
    if _CONFIG is not None:
        return _CONFIG

    for path in CONFIG_PATHS:
        expanded = os.path.expanduser(path)
        if os.path.exists(expanded):
            with open(expanded, encoding="utf-8") as f:
                _CONFIG = json.load(f)
            return _CONFIG

    print("Error: config.local.json not found.", file=sys.stderr)
    print("  Run: cp config/config.example.json config.local.json", file=sys.stderr)
    print("  Then fill in your Telegram token, proxy, etc.", file=sys.stderr)
    sys.exit(1)


def get(*keys, default=None):
    """Safely traverse nested keys, e.g. config.get('telegram', 'bot_token')."""
    cfg = load()
    val = cfg
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k)
            if val is None:
                return default
        else:
            return default
    return val
