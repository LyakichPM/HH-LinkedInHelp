# HH-LinkedInHelp — Автоматизация поиска работы на hh.ru и LinkedIn

Python-агент для автоматизации поиска вакансий, отправки откликов с сопроводительными письмами, ведения переговоров и генерации CV.

## Возможности

### 🔍 Поиск вакансий (`hh search`)
- Поиск по ключевым словам, зарплате, опыту, региону
- Фильтрация: только с контактами, без тестовых заданий, удалёнка
- Экспорт в JSON/CSV для анализа

### 📝 Отклики с сопроводительными (`hh apply`)
- Автоматическая генерация персонализированных сопроводительных писем под вакансию
- Отправка отклика + письма в один запрос (нет пустых откликов)
- Поддержка нового дизайна hh.ru (Magritte) — корректная работа с toggle и textarea
- **Жёсткое правило**: никогда не отправляем пустые отклики — обязательная проверка наличия сопроводительного

### ✅ Верификация откликов (`hh verify`)
- Проверка статуса: «Отклик отправлен», «Просмотрено», «Приглашение», «Отказ»
- Чтение чатов hh.ru (chatik.hh.ru) — проверка прочитанных сообщений
- Добавление сопроводительных в уже отправленные отклики через чат (fallback)

### 💬 Переговоры (`hh negotiations`)
- Список активных чатов с рекрутерами
- Чтение последних сообщений
- Ответы в чаты

### 🔐 Авторизация (`hh auth`)
- Логин через браузер (Playwright + Chromium) с сохранением cookies
- Проверка валидности сессии
- Поддержка прокси (нужно для доступа к hh.ru из-за границы)

### 💼 LinkedIn-аутрич (`li-tools/`)
Отдельный набор Playwright-скриптов поверх персонального профиля браузера
(`li_profile/`, не в git — сессия LinkedIn). Все инструменты работают через
**полную страницу мессенджера** (`/messaging/`), а не через плавающий док
внизу экрана — док на LinkedIn может тихо переиспользовать чужую открытую
панель вместо новой (инцидент 2026-07-13, с тех пор в каждом инструменте
обязательная проверка «шапка/панель принадлежит ожидаемому адресату» перед
вводом текста, иначе — abort, а не отправка не туда).

| Скрипт | Назначение |
|---|---|
| `li_send_message.py` | DM в первый контакт (профиль/компания) через кнопку «Message»; закрывает все плавающие панели, требует ровно одно compose-поле после клика |
| `li_compose_new.py` | Новый диалог через компоузер `/messaging/` (recipient typeahead + проверка пилюли получателя) |
| `li_reply_thread.py` | Ответ в существующей переписке, с опциональным вложением файла |
| `li_connect_note.py` | Заявка на коннект с сопроводительной запиской; определяет уже-отправлено/уже-в-контактах/email-gate и останавливается |
| `li_company_modal.py` | Сообщение странице компании через модалку «Новое сообщение» (topic-дропдаун, лимит 750 знаков) |
| `li_msg_audit.py` | Дамп списка диалогов + полной истории конкретных тредов для сверки перед отправкой |

Известные ограничения LinkedIn (не баг инструментов): 2-я степень связи
закрыта для бесплатных сообщений — доступен только InMail; страница
компании даёт 750-значную модалку, не полноценный диалог. Плавающий док
LinkedIn пронизан shadow DOM — закрывать его панели нужно Playwright-локаторами
(`page.locator(...)`), «сырой» `document.querySelectorAll` их не видит.

### 🤖 Telegram-бот (`hh tg`)
- Long-poll слушатель входящих сообщений
- Очередь команд в `tg_inbox.jsonl` (cross-session)
- Отправка отчётов, списков вакансий, статусов

### 🎨 CV-дизайн (`hh cv-design`)
- Генерация PDF-резюме (Split layout: левая колонка — навыки/контакты, правая — опыт)
- Headless Chrome → PDF (print-to-PDF)
- Доставка в Telegram как документ

### 📊 Оценка вакансий (`hh eval`)
- Матрица соответствия: стек, домен (iGaming/FinTech), уровень, зарплата, локация
- Приоритизация: топ-вакансии → сначала

---

## Установка

```bash
# Клонирование
git clone https://github.com/LyakichPM/HH-LinkedInHelp.git
cd HH-LinkedInHelp

# Рекомендуется: виртуальное окружение
python -m venv .venv
source .venv/bin/activate    # Linux/macOS
# .venv\Scripts\activate     # Windows (PowerShell)
# .venv\Scripts\activate.bat # Windows (cmd)

# Установка зависимостей (Python 3.10+)
pip install -e .
# или вручную:
pip install playwright requests pyyaml python-dotenv

# Установка браузера Playwright
playwright install chromium

# Конфигурация
cp config/config.example.json config/config.local.json
# Windows (cmd): copy config\config.example.json config\config.local.json
# Windows (PowerShell): Copy-Item config\config.example.json config\config.local.json
# Отредактируйте config.local.json — вставьте свои токены/куки
```

> **Windows:** Можно запустить `.\setup.ps1` — он создаст конфиг, установит зависимости и Playwright.
> **Linux/macOS:** Можно запустить `./setup.sh` (требует `chmod +x setup.sh`).

---

## Установка по платформам

### 🍎 macOS

```bash
# 1. Системные зависимости (Homebrew — https://brew.sh)
brew install python@3.10 git
# опционально, для TG WebApp через HTTPS-туннель:
brew install cloudflared

# 2. Клонирование и окружение
git clone https://github.com/LyakichPM/HH-LinkedInHelp.git
cd HH-LinkedInHelp
python3 -m venv .venv
source .venv/bin/activate

# 3. Зависимости + браузер
pip install -e .
playwright install chromium          # на macOS системные библиотеки не нужны

# 4. Конфиг
cp config/config.example.json config/config.local.json
# отредактируйте config.local.json — токены/куки/прокси

# (либо всё разом)
chmod +x setup.sh && ./setup.sh
```

> **Apple Silicon (M1/M2/M3):** всё работает нативно на arm64, Rosetta не требуется. Если `playwright install` ругается — обновите: `pip install -U playwright`.

### 🐧 Linux (Debian / Ubuntu)

```bash
# 1. Системные зависимости
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git

# 2. Клонирование и окружение
git clone https://github.com/LyakichPM/HH-LinkedInHelp.git
cd HH-LinkedInHelp
python3 -m venv .venv
source .venv/bin/activate

# 3. Зависимости + браузер
pip install -e .
playwright install-deps chromium     # системные libs для Chromium (нужен sudo)
playwright install chromium

# 4. Конфиг
cp config/config.example.json config/config.local.json
# отредактируйте config.local.json — токены/куки/прокси

# (либо всё разом)
chmod +x setup.sh && ./setup.sh
```

> **Fedora/RHEL:** замените шаг 1 на `sudo dnf install python3 python3-pip git`.
> **Arch:** `sudo pacman -S python git`.
> **Headless-сервер (без GUI):** `hh auth login` открывает окно браузера — для сохранения куки логиньтесь на машине с дисплеем (или через X-forwarding / `xvfb-run`), затем перенесите `hh_cookies.json`.
> **cloudflared** (только если нужен TG WebApp): скачайте бинарь из [релизов Cloudflare](https://github.com/cloudflare/cloudflared/releases) или установите пакетом дистрибутива. В репозитории его нет (`.gitignore`).

### 🪟 Windows

```powershell
git clone https://github.com/LyakichPM/HH-LinkedInHelp.git
cd HH-LinkedInHelp
.\setup.ps1        # создаёт конфиг, ставит зависимости и Playwright Chromium
```

Затем отредактируйте `config\config.local.json` и запустите `hh auth login`.

---

## Конфигурация (`config/config.local.json`)

```json
{
  "telegram": {
    "bot_token": "YOUR_TG_BOT_TOKEN",
    "chat_id": "YOUR_CHAT_ID"
  },
  "proxy": {
    "url": "http://user:pass@ip:port"
  },
  "hh": {
    "cookie_file": "hh_cookies.json",
    "resume_url": "https://hh.ru/resume/your_resume_id"
  },
  "candidate": {
    "name": "Ваше Имя",
    "profile_note": "Краткий профиль для генерации писем"
  }
}
```

> ⚠️ `config.local.json` в `.gitignore` — секреты не попадают в git.

---

## Быстрый старт (CLI)

```bash
# 1. Авторизация на hh.ru (один раз)
hh auth login

# 2. Поиск iGaming PM вакансий (зарплата от 300к, неделя)
hh search "iGaming Product Manager" 300000 7

# 3. Отклик на вакансию с авто-сопроводительным
hh apply 134646797 cover_134646797.txt

# 4. Проверка статуса отклика
hh verify 134646797

# 5. Список переговоров
hh negotiations

# 6. Генерация PDF-резюме
hh cv-design split

# 7. Отправка сообщения в Telegram
hh tg "Тестовое сообщение"

# 8. Чтение входящих из Telegram
hh tg-inbox

# 9. Запуск Telegram long-poll слушателя (фоновый режим)
hh tg listen
```

---

## Slash-команды (для ИИ-агента)

| Команда | Описание |
|---------|----------|
| `/hh-search "query" salary days` | Поиск вакансий |
| `/hh-apply vacancy_id [cover_file]` | Отклик с сопроводительным |
| `/hh-verify vacancy_id` | Проверка статуса |
| `/hh-negotiations` | Активные чаты |
| `/hh-auth login|status` | Авторизация |
| `/hh-tg "text"` | Отправить в TG |
| `/hh-tg-inbox` | Прочитать входящие |
| `/hh-tg-listen` | Запустить long-poll слушатель |
| `/hh-cv-design split` | Генерация PDF |

---

## Архитектура

```
hh/
├── browser.py      # Playwright wrapper (страницы, навигация, ожидания)
├── cli.py          # CLI entry point (hh search|apply|verify|...)
├── config.py       # Загрузка config.local.json + .env
├── hh_apply.py     # Логика откликов + сопроводительных (Magritte-ready)
├── hh_auth.py      # Логин, cookies, проверка сессии
├── hh_search.py    # Парсинг SERP, фильтры, экспорт
├── hh_verify.py    # Статусы, чаты chatik.hh.ru
├── telegram.py     # Bot API + inbox JSONL
├── utils.py        # Helpers (нормализация текста, даты, зарплаты)
└── __main__.py     # python -m hh

li-tools/            # LinkedIn: send/reply/connect/audit (см. раздел выше)
├── li_send_message.py
├── li_compose_new.py
├── li_reply_thread.py
├── li_connect_note.py
├── li_company_modal.py
└── li_msg_audit.py
```

---

## Важные детали реализации

### hh.ru Magritte (новый дизайн 2024)
- Селекторы на `data-qa` атрибутах
- Toggle «Добавить сопроводительное» **создаёт новый textarea** (не переиспользует старый) — дельта по индексам
- Non-breaking space (`\xa0`) в русском тексте («Вы\xa0откликнулись») — нормализация через `.replace('\xa0', ' ')`
- Автосохранение письма на `blur` — требуется `Tab` + ожидание 5-7 сек + **reload страницы для верификации**

### Telegram (кодировка в CLI)

**Windows (PowerShell 5.1):** `ConvertTo-Json` + `Invoke-RestMethod` ломает кириллицу.
- **Решение**: пишем UTF-8 JSON в файл → `curl.exe -d "@file" -H "Content-Type: application/json; charset=utf-8"`

**Linux/macOS (bash/zsh):** `curl` нативно работает с UTF-8, проблем нет:
```bash
curl -X POST -H "Content-Type: application/json; charset=utf-8" \
  -d '{"chat_id":"...","text":"Привет"}' \
  "https://api.telegram.org/bot<TOKEN>/sendMessage"
```

> В коде (`hh/telegram.py`) используется `requests` — кроссплатформенно, никаких проблем с кодировкой. `curl.exe` используется только в обёртках для запуска из-под системного Python (см. ниже).

### Python Sandbox (exit code 49)
- Системный `python`/`python3` в изолированной песочнице (нет сети/файлов)
- Используйте `pw_env` Python (Playwright bundled) или `curl.exe` для HTTP

---

## Безопасность

- **Никаких секретов в git**: `.gitignore` исключает `config.local.json`, `hh_cookies.json`, `tg_inbox.jsonl`, `*.exe`, `__pycache__/`, `.env`
- `cloudflared.exe` (51 MB) удалён из истории, добавлен в `.gitignore`
- **Секрет-скан на каждый коммит и push**: pre-commit хук + CI на базе [gitleaks](https://github.com/gitleaks/gitleaks) физически не дают токену/куке/ключу попасть в историю
- Лицензия: **MIT** — свободное использование, модификация, распространение

### Настройка защиты от утечек (один раз)

```bash
pip install pre-commit
pre-commit install          # ставит git-хук; теперь gitleaks + ruff бегут при каждом commit
pre-commit run --all-files  # разовая проверка всего репозитория
```

Конфиг — [`.pre-commit-config.yaml`](.pre-commit-config.yaml). CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) дублирует секрет-скан на весь `fetch-depth: 0` (вся история) и гоняет `ruff` на push/PR — падает, если найден секрет или синтаксическая ошибка Python.

---

## Планы (согласованы, ещё не реализованы в коде)

- **Капча-релей через Telegram**: при обнаружении капчи — скриншот боту,
  ждать текстовое решение от пользователя через `tg inbox`, вводить
  посимвольно с человеческими задержками. Сейчас `hh_search.py`/`hh_apply.py`
  капчу только детектируют и останавливаются — решает пользователь вручную
  в открытом браузере.
- **SQLite-кэш откликнутых вакансий** (`applied_cache.db`): быстрый дедуп в
  дополнение к скрейпу `hh negotiations` — не замена проверке письма в чате.
- **Стелс-обвязка браузера** (`playwright-stealth` + человеческий джиттер
  мыши/скролла перед кликом «Откликнуться») — для hh.ru; риск нарушения ToS
  осознанно принят.

## Требования

- Python 3.10+
- Playwright + Chromium (автоустановка: `playwright install chromium`)
- Windows / Linux / macOS
- Прокси с российским IP (для доступа к hh.ru из-за границы)

> ⚠️ **Windows-only:** `cloudflared.exe` (для HTTPS туннеля TG WebApp) — в `.gitignore`, не в репозитории. На Linux/macOS используйте `cloudflared` из пакетного менеджера или Docker.

---

## Автор

**Ilia Kovalev** — Senior Product Manager (iGaming, FinTech, Data)
- SQL (ClickHouse, PostgreSQL), Python (pandas, analytics), Tableau/Power BI/Excel VBA
- A/B тесты, метрики продукта, дашборды для C-level
- Telegram: [@lyaki4](https://t.me/lyaki4)

---

## Лицензия

MIT License — см. [LICENSE](LICENSE)