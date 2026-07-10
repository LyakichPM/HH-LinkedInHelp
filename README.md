# hh-agent

**Инструмент для поиска и отклика на вакансии hh.ru с ИИ-агентом.**

hh-agent — это набор Python-инструментов и инструкций для ИИ-агента (Claude Code),
автоматизирующий поиск, проверку и отклик на вакансии hh.ru.

```
╔══════════════════════════════════════╗
║          hh-agent toolkit           ║
╠══════════════════════════════════════╣
║  CLI  ──  hh search / apply / auth  ║
║  Agent ── instructions + reference  ║
║  TG    ── send / inbox / bridge     ║
╚══════════════════════════════════════╝
```

## Возможности

- 🔍 **Поиск** — поиск вакансий по запросу, зарплате, дате
- 📝 **Отклик** — отклик с сопроводительным (popup-first: письмо до отправки)
- ✅ **Проверка** — проверка статуса отклика, просмотр переговоров
- 🔐 **Авторизация** — логин через браузер, сохранение cookies
- 🤖 **Telegram** — отправка уведомлений, приём команд через inbox
- 🧠 **Agent-ready** — инструкции для Claude Code с референсами

## Быстрый старт

```bash
# 1. Установка
pip install -e .
playwright install chromium

# 2. Настройка
cp config/config.example.json config.local.json
# Отредактируй config.local.json: Telegram токен, chat_id, прокси

# 3. Авторизация hh.ru
hh auth login

# 4. Проверка
hh setup

# 5. Поиск
hh search --query "Product Manager" --salary 200000 --period 7
```

## Использование

### CLI

```bash
# Поиск вакансий
hh search --query "Python" --salary 150000 --json

# Проверка статуса
hh verify <vacancy_id>

# Отклик с сопроводительным
hh apply <vacancy_id> --letter cover.txt

# Просмотр переговоров
hh negotiations

# Telegram
hh tg send "Привет!"
hh tg inbox
```

### ИИ-агент (Claude Code)

hh-agent включает инструкции для Claude Code в `agent/`:

- `agent/instructions.md` — загружается при старте, содержит полный порядок работы
- `agent/reference/selectors.json` — CSS-селекторы hh.ru
- `agent/reference/errors.md` — частые ошибки и их решения

При запросе «найди вакансии и откликнись» агент:
1. Ищет свежие вакансии → 2. Проверяет статус → 3. Показывает список → 4. Откликается с письмом → 5. Отправляет отчёт

### Telegram bridge

```bash
# Запуск слушателя входящих сообщений
python tg-bridge/tg_bot.py

# Или через CLI
hh tg listen
```

Слушатель пишет входящие сообщения в `tg_inbox.jsonl`.
Агент читает их командой `hh tg inbox`.

## Структура проекта

```
hh-agent/
├── hh/                      # Python пакет
│   ├── __init__.py
│   ├── __main__.py          # python -m hh
│   ├── cli.py               # click entry point
│   ├── config.py            # конфиг-лоадер
│   ├── browser.py           # Playwright browser factory
│   ├── hh_auth.py           # авторизация
│   ├── hh_search.py         # поиск вакансий
│   ├── hh_apply.py          # отклик с письмом
│   ├── hh_verify.py         # проверка статуса
│   └── telegram.py          # Telegram send + inbox
├── tg-bridge/
│   └── tg_bot.py            # долгоживущий слушатель Telegram
├── agent/
│   ├── skill.json           # манифест скила
│   ├── instructions.md      # инструкция для ИИ-агента
│   └── reference/
│       ├── selectors.json   # селекторы hh.ru
│       └── errors.md        # частые ошибки
├── config/
│   └── config.example.json  # шаблон конфига
├── docs/
│   ├── architecture.md      # архитектура
│   ├── setup.md             # установка
│   ├── commands.md          # команды CLI
│   └── security.md          # безопасность
├── pyproject.toml           # package definition
├── setup.sh                 # скрипт установки
└── .gitignore
```

## Безопасность

- **Секреты в `.gitignore`**: `config.local.json`, `hh_cookies.json`, `tg_inbox.jsonl`
- В публичный репозиторий попадает только код
- Коммиты подписываются через `git config commit.gpgsign true`
- Подробнее: [docs/security.md](docs/security.md)
