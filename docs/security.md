# Security Model

## Threat model

hh-agent хранит:
- **Telegram bot token** — полный доступ к боту
- **hh.ru session cookies** — доступ к аккаунту hh.ru от имени пользователя
- **Proxy credentials** — доступ к прокси
- **Переписка** — `tg_inbox.jsonl` может содержать личные сообщения

## Secrets protection

### .gitignore

Следующие файлы находятся в `.gitignore` и **никогда не попадают в репозиторий**:

| File | Contents |
|------|----------|
| `config.local.json` | Telegram token, proxy, chat_id |
| `hh_cookies.json` | hh.ru session cookies |
| `tg_inbox.jsonl` | Telegram переписка |

### Config separation

```
config/
  config.example.json    ← в репозитории (шаблон с плейсхолдерами)
config.local.json       ← только локально (в .gitignore)
```

### Cookie permissions

hh.ru cookies авторизуют действия от имени пользователя.
- Хранятся только локально
- Не передаются третьим лицам
- Истекают через ~30 дней

## First-run permission setup

При первом запуске через Claude Code:
1. `hh setup` проверяет конфигурацию
2. Пользователю предлагается подтвердить права: Bash (python/playwright), Read (конфиги), Write (файлы)
3. Всё прозрачно — никаких скрытых операций

## Recommendations

### For GitHub public repo

Перед публикацией убедись:

```bash
# Проверка, что secrets не попали в коммит
git status
grep -r "bot_token" --include="*.json" .
grep -r "proxy" --include="*.json" .

# Удалить из истории если случайно закоммитил
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch config.local.json hh_cookies.json" \
  --prune-empty --tag-name-filter cat -- --all
```

### GPG signing

```bash
# Настройка подписи коммитов
git config --global user.signingkey YOUR_KEY
git config --global commit.gpgsign true
```

### Environment variables (альтернатива)

Вместо `config.local.json` можно использовать переменные окружения:

```bash
export HH_TG_TOKEN="..."
export HH_CHAT_ID="..."
export HH_PROXY="..."
```

## Known limitations

- Cookies хранятся в открытом виде — не используй на общих компьютерах
- Playwright запускает полноценный браузер — временные файлы остаются на диске
- Telegram Bot API использует HTTPS, но метаданные (кто кому пишет) видны Telegram
