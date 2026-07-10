# Architecture

## Overview

hh-agent состоит из трёх слоёв:

```
┌─────────────────────────────────────────────────────┐
│                    ИИ-агент                          │
│              (Claude Code / любой LLM)               │
│  ┌──────────────────────────────────────────────┐   │
│  │  agent/instructions.md                       │   │
│  │  agent/reference/*.json / *.md               │   │
│  └──────────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────────┘
                       │ CLI / Python API
┌──────────────────────▼──────────────────────────────┐
│                   hh/ (Python)                       │
│  ┌──────────┐ ┌──────────┐ ┌────────────────────┐   │
│  │ search   │ │ apply    │ │ verify             │   │
│  │ hh_search│ │ hh_apply │ │ hh_verify          │   │
│  └──────────┘ └──────────┘ └────────────────────┘   │
│  ┌──────────┐ ┌──────────┐ ┌────────────────────┐   │
│  │ auth     │ │ config   │ │ telegram           │   │
│  │ hh_auth  │ │ config.py│ │ telegram.py        │   │
│  └──────────┘ └──────────┘ └────────────────────┘   │
│  ┌──────────┐                                       │
│  │ browser  │  Playwright factory                   │
│  │ browser. │  proxy, UA, cookies                   │
│  │ py       │                                       │
│  └──────────┘                                       │
└──────┬──────────────────────┬───────────────────────┘
       │                      │
       ▼                      ▼
┌──────────────┐    ┌────────────────────┐
│   hh.ru      │    │  Telegram Bot API  │
│   (браузер)  │    │                    │
└──────────────┘    └────────────────────┘
```

## Data Flow

### Search
1. CLI получает параметры поиска
2. Playwright открывает hh.ru/search/vacancy с фильтрами
3. Парсит карточки вакансий (title, employer, salary, applied)
4. Возвращает JSON-массив результатов

### Apply
1. CLI получает vid и текст сопроводительного
2. Playwright открывает страницу вакансии
3. Проверяет "Вы откликнулись" → пропуск если уже
4. Кликает "Откликнуться"
5. 🔑 **Popup-first**: заполняет textarea в модалке → сабмит
6. Fallback: quick apply без модалки
7. Возвращает результат

### Telegram Bridge
1. `tg_bot.py` — долгоживущий процесс
2. Long-polling Telegram Bot API
3. Новые сообщения → `tg_inbox.jsonl` (JSONL)
4. Claude Code читает `hh tg inbox`, обрабатывает, отвечает `hh tg send`

## Key Decisions

- **Playwright обязателен**: hh.ru не имеет публичного API для откликов
- **Popup-first apply**: письмо заполняется ДО отправки отклика (исправление после фидбека)
- **JSONL для inbox**: файл-очередь переживает между сессиями Claude, не требует БД
- **Cookies для auth**: `context.add_cookies()` + файл, не `storage_state` (hh.ru блокирует storage_state)
- **Unicode normalization**: hh.ru использует неразрывные пробелы — обязательный `normalize()`
