# CLI Commands Reference

## Global Options

Все команды поддерживают:
- `--help` — справка

## `hh search`

Поиск вакансий на hh.ru.

```bash
hh search --query "Product Manager" --salary 200000 --period 7 --max-pages 3
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `-q, --query` | string | required | Поисковый запрос |
| `-s, --salary` | int | — | Минимальная зарплата |
| `-p, --period` | int | 14 | Период поиска (дней) |
| `-m, --max-pages` | int | 2 | Количество страниц |
| `--json` | flag | — | Вывод в JSON |
| `--headless` | flag | — | Без GUI (сервер) |

## `hh apply`

Отклик на вакансию с сопроводительным.

```bash
hh apply 123456789 --letter cover.txt
```

| Argument | Description |
|----------|-------------|
| `VID` | ID вакансии (число из URL) |

| Option | Type | Description |
|--------|------|-------------|
| `-l, --letter` | string | Путь к файлу с сопроводительным (required) |
| `--headless` | flag | Без GUI |

## `hh verify`

Проверка статуса вакансии.

```bash
hh verify 123456789
```

## `hh negotiations`

Просмотр активных переговоров.

```bash
hh negotiations
hh negotiations --json
```

## `hh auth`

Управление авторизацией.

```bash
hh auth login      # Войти в браузере
hh auth status     # Проверить cookies
```

## `hh tg`

Telegram интеграция.

```bash
hh tg send "Текст"          # Отправить сообщение
hh tg inbox                 # Прочитать входящие
hh tg inbox --clear         # Прочитать и очистить
hh tg count                 # Количество непрочитанных
```

## `hh setup`

Проверка готовности системы.

```bash
hh setup
```

Проверяет: config → Telegram → hh.ru auth → Playwright → Proxy.
