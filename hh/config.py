"""Load config.local.json — secrets (TG token, proxy, cookies path)."""

import json
import os
import sys

_CONFIG = None

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

CONFIG_PATHS = [
    "config.local.json",
    os.path.join(REPO_ROOT, "config.local.json"),
]


def resolve_path(path):
    """Anchor a relative path at the repo root, not the process cwd.

    Scripts are often launched from other directories; a bare relative
    path like 'hh_cookies.json' would then silently resolve to a
    non-existent file (e.g. cookies not loading -> guest session).
    """
    return path if os.path.isabs(path) else os.path.join(REPO_ROOT, path)


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
