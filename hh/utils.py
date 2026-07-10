"""Shared utilities: text normalization, retry helpers."""

import re
import time


def normalize(text: str) -> str:
    """Replace Unicode non-breaking / odd spaces with regular space."""
    return re.sub(r"[     ​　]", " ", text)


def wait(seconds: float = 2):
    """Short sleep with no-op catch."""
    time.sleep(seconds)


def extract_vid(url_or_vid: str) -> str:
    """Extract vacancy ID from URL or return as-is."""
    m = re.search(r"/vacancy/(\d+)", url_or_vid)
    if m:
        return m.group(1)
    m = re.search(r"^(\d+)$", url_or_vid.strip())
    if m:
        return m.group(1)
    return url_or_vid.strip()
