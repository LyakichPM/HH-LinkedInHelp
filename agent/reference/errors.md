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

## Формы работодателя (вне hh)

- **Поле телефона с маской не терпит `fill`.** `page.fill("input[name=phone]",
  "9990001122")` даёт на выходе перепутанный номер: маска дописывает свои
  символы поверх вставленного значения. Работает только посимвольный ввод -
  `page.click(sel)` и `page.type(sel, DIGITS, delay=60)` десятью цифрами. Перед
  отправкой обязателен ассерт: собрать цифры из `input_value` и сравнить с
  ожидаемым. Без ассерта работодатель получает чужой номер, и узнать об этом
  уже нельзя.

## LinkedIn

- **Модалка приглашения: две кнопки со словом «заметка».** Окно «Добавить
  заметку в приглашение?» содержит «Персонализировать» и «Отправить без
  заметки». Отбор кнопки по подстроке `заметк` ловит ВТОРУЮ и молча отправляет
  пустое приглашение. Матчить только явные варианты
  (`персонализировать|добавить заметку|add a note|personalize`) и отдельно
  отбрасывать `без заметки|without`.
- **Отзыв приглашения хуже пустого приглашения.** После отзыва LinkedIn не даёт
  пригласить того же человека около трёх недель.
- **Кнопка «Ещё» в карточке профиля бывает без текста** - только
  `aria-label="Еще"` (без ё). Искать по всей странице нельзя: первым совпадает
  колокол в глобальной шапке. Брать `a[href*='/messaging/compose']`, подниматься
  на несколько родителей вверх и искать кнопку там; шапку и `aside` отсекать.
- **Личка есть не всем.** Для 3-го круга кнопка «Отправить сообщение» ведёт на
  апселл `composeOptionType=PREMIUM_INMAIL`. Свободных каналов нет - только
  приглашение в контакты или комментарий под постом.
- **Ссылку из вакансии открывать ДО написания письма.** Пост в LinkedIn
  отдаётся обычным `curl` без логина (`meta name="description"` и блок
  `attributed-text-segment-list__content`), и там регулярно оказывается то, чего
  нет в пересланном тексте: настоящее название роли, домен компании, отрасль.

## Windows-окружение

- **Два интерпретатора, и они не взаимозаменяемы.** В окружении Playwright нет
  PIL, поэтому сборка резюме кладёт фото несжатым PNG и PDF раздувается вчетверо.
  Сборку документов гонять интерпретатором с PIL, браузерные шаги - тем, где
  стоит Playwright. Слово `python` без пути на Windows может оказаться заглушкой
  из Microsoft Store, которая молча ничего не делает.
- **Heredoc в bash съедает обратные слэши** даже при закавыченном разделителе:
  `newline="\\n"` превращается в реальный перевод строки внутри литерала.
  Патч-скрипты писать без единого обратного слэша (`chr(10)`, `chr(92)`,
  прямые слэши в путях) и проверять результат поиском по файлу. Длинный
  кириллический скрипт через heredoc не проходит вовсе - класть файлом.
