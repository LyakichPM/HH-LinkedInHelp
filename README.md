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

# Установка зависимостей (Python 3.10+)
pip install -e .
# или вручную:
pip install playwright requests pyyaml python-dotenv

# Установка браузера Playwright
playwright install chromium

# Конфигурация
cp config/config.example.json config/config.local.json
# Отредактируйте config.local.json — вставьте свои токены/куки
```

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
hh apply 134646797

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
```

---

## Slash-команды (для ИИ-агента)

| Команда | Описание |
|---------|----------|
| `/hh-search "query" salary days` | Поиск вакансий |
| `/hh-apply vacancy_id [cover_file]` | Отклик с сопроводительным |
| `/hh-verify vacancy_id` | Проверка статуса |
| `/hh-negotiations` | Активные чаты |
| `/hh-auth login\|status` | Авторизация |
| `/hh-tg "text"` | Отправить в TG |
| `/hh-tg-inbox` | Прочитать входящие |
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
```

---

## Важные детали реализации

### hh.ru Magritte (новый дизайн 2024)
- Селекторы на `data-qa` атрибутах
- Toggle «Добавить сопроводительное» **создаёт новый textarea** (не переиспользует старый) — дельта по индексам
- Non-breaking space (`\xa0`) в русском тексте («Вы\xa0откликнулись») — нормализация через `.replace('\xa0', ' ')`
- Автосохранение письма на `blur` — требуется `Tab` + ожидание 5-7 сек + **reload страницы для верификации**

### Telegram (PowerShell 5.1 bug)
- `ConvertTo-Json` + `Invoke-RestMethod` ломает кириллицу
- **Решение**: пишем UTF-8 JSON в файл → `curl.exe -d "@file" -H "Content-Type: application/json; charset=utf-8"`

### Python Sandbox (exit code 49)
- Системный `python`/`python3` в изолированной песочнице (нет сети/файлов)
- Используйте `pw_env` Python (Playwright bundled) или `curl.exe` для HTTP

---

## Безопасность

- **Никаких секретов в git**: `.gitignore` исключает `config.local.json`, `hh_cookies.json`, `tg_inbox.jsonl`, `*.exe`, `__pycache__/`, `.env`
- `cloudflared.exe` (51 MB) удалён из истории, добавлен в `.gitignore`
- Лицензия: **MIT** — свободное использование, модификация, распространение

---

## Требования

- Python 3.10+
- Playwright + Chromium (автоустановка: `playwright install chromium`)
- Windows / Linux / macOS
- Прокси с российским IP (для доступа к hh.ru из-за границы)

---

## Автор

**Ilia Kovalev** — Senior Product Manager (iGaming, FinTech, Data)
- SQL (ClickHouse, PostgreSQL), Python (pandas, analytics), Tableau/Power BI/Excel VBA
- A/B тесты, метрики продукта, дашборды для C-level
- Telegram: [@lyaki4](https://t.me/lyaki4)

---

## Лицензия

MIT License — см. [LICENSE](LICENSE)