#!/usr/bin/env bash
set -e

echo "=== hh-agent setup ==="

# Create config if not exists
if [ ! -f config.local.json ]; then
    cp config/config.example.json config.local.json
    echo "Created config.local.json — edit it with your tokens"
fi

# Install Python deps
pip install -e .

# Install Playwright + Chromium
python -m playwright install chromium

echo ""
echo "=== Done ==="
echo "Next:"
echo "  1. Edit config.local.json with your Telegram token, proxy"
echo "  2. Run: hh auth login   (to save hh.ru cookies)"
echo "  3. Run: hh search 'product manager igaming'   (test)"
