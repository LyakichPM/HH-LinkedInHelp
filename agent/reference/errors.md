# Common errors and fixes

## Playwright

| Error | Cause | Fix |
|-------|-------|-----|
| `BrowserType.launch` - Executable doesn't exist | Chromium not installed | `playwright install chromium` |
| `Timeout 30000ms exceeded` | Page load timeout | Increase timeout or check proxy |
| `Target closed` | Browser/context closed prematurely | Check `finally` block cleanup |
| `Error: page.goto: net::ERR_CONNECTION_RESET` | Proxy not working | Check proxy in config.local.json |

## hh.ru

| Error | Cause | Fix |
|-------|-------|-----|
| Captcha page | hh.ru detected automation | Use headless=False, slow down, solve manually |
| `Вы откликнулись` not detected | Page didn't fully load | Add `page.wait_for_timeout(2000)` |
| Apply button not visible | Page not scrolled | `page.evaluate("window.scrollTo(0, 300)")` |
| Letter textarea not found | Popup failed to open | Fall back to quick apply or try again |
| 403 / redirect to login | Cookies expired | Run `hh auth login` again |

## Telegram

| Error | Cause | Fix |
|-------|-------|-----|
| `chat not found` | Wrong chat_id | Check config.local.json |
| 403 Forbidden | Bot blocked by user | User must unblock bot |
| Timeout | Network issue | Check internet connection |

## Config

| Error | Cause | Fix |
|-------|-------|-----|
| `config.local.json not found` | Missing config | `cp config/config.example.json config.local.json` |
| `telegram.bot_token not set` | Missing token | Fill in token from BotFather |
| `telegram.chat_id not set` | Missing chat_id | Send /start to bot, check `hh tg inbox` |
