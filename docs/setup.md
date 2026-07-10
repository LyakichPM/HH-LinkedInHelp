# Setup Guide

## Prerequisites

- Python 3.10+
- Git
- Telegram bot token (from @BotFather)
- Proxy (опционально, для доступа к hh.ru из-за границы)

## Installation

```bash
# 1. Clone
git clone https://github.com/yourusername/hh-agent.git
cd hh-agent

# 2. Install package
pip install -e .

# 3. Install Playwright browser
playwright install chromium

# 4. Configure
cp config/config.example.json config.local.json
```

## Configuration

Отредактируй `config.local.json`:

```json
{
  "telegram": {
    "bot_token": "123456:ABC-DEF...",
    "chat_id": "123456789",
    "inbox_file": "tg_inbox.jsonl"
  },
  "proxy": {
    "url": "http://user:pass@host:port"
  },
  "hh": {
    "cookie_file": "hh_cookies.json",
    "resume_url": "https://hh.ru/resume/..."
  },
  "candidate": {
    "name": "Your Name"
  }
}
```

### Telegram setup

1. Создай бота у [@BotFather](https://t.me/BotFather), получи токен
2. Напиши боту `/start`
3. Узнай свой `chat_id`: `hh tg inbox --clear`, отправь ещё одно сообщение боту, снова `hh tg inbox`

### Proxy

Для доступа к hh.ru из-за границы нужен российский прокси.
Формат: `http://user:password@host:port`.
Оставь `"url": ""` если прокси не нужен.

## First Run

```bash
# Проверка конфигурации
hh setup

# Авторизация на hh.ru
hh auth login
# Откроется браузер — войди в аккаунт hh.ru
# После входа нажми Ctrl+C
```

## Verify

```bash
hh auth status
hh search --query "Python" --salary 100000 --limit 5
```

## Starting Telegram Bridge

Для приёма команд через Telegram:

```bash
# В отдельном терминале:
python tg-bridge/tg_bot.py

# Или:
hh tg listen
```

## Common Issues

- `playwright install chromium` → Убедись, что Chromium установлен
- `hh setup` показывает ❌ → Проверь config.local.json
- Прокси не работает → Проверь формат `http://user:pass@host:port`
- hh.ru показывает капчу → Запусти с `--headless` или реши вручную
