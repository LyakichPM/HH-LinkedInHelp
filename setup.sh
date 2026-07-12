#!/usr/bin/env bash
set -e

echo "=== hh-agent setup ==="

# Create config if not exists
if [ ! -f config.local.json ]; then
    cp config/config.example.json config.local.json
    echo "Created config.local.json — edit it with your tokens"
else
    echo "config.local.json already exists"
fi

# Install Python deps
echo ""
echo "Installing Python dependencies..."
if pip install -e . 2>/dev/null; then
    echo "Dependencies installed via pip install -e ."
else
    echo "Falling back to manual install..."
    pip install playwright requests pyyaml python-dotenv
fi

# Install Playwright + Chromium
echo ""
echo "Installing Playwright Chromium..."
python -m playwright install chromium

echo ""
echo "=== Done ==="
echo "Next:"
echo "  1. Edit config.local.json with your Telegram token, proxy"
echo "  2. Run: hh auth login   (to save hh.ru cookies)"
echo "  3. Run: hh search 'product manager igaming'   (test)"