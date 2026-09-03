# -*- coding: utf-8 -*-
"""Аудит перед публикацией: секреты, доступы и личные данные.

Проверяет РОВНО тот набор файлов, который уйдёт в коммит: отслеживаемые плюс
неотслеживаемые из `git status --porcelain`. Смысл именно в этом - проверять
рабочий каталог целиком бесполезно, там лежит всё подряд, а проверять только
отслеживаемое поздно: новый секрет приходит с новым файлом.

    py tools/audit_pii.py                # отчёт в консоль
    py tools/audit_pii.py --out a.txt    # отчёт файлом (консоль Windows рубит
                                         # кириллицу в cp1251)
    py tools/audit_pii.py --phone 79001234567 --email me@example.com --name Иванов

Личных литералов в самом файле нет: то, что искать дополнительно, передаётся
аргументами. Ненулевой код возврата = нашлось что-то, что публиковать нельзя.
"""
import argparse
import io
import os
import re
import subprocess
import sys

# Доступы. Находка здесь - стоп-сигнал, публиковать нельзя.
SECRET = [
    ("telegram_bot_token", r"\b\d{8,10}:[A-Za-z0-9_-]{30,}"),
    ("linkedin_li_at", r"li_at[\"'\s:=]{1,6}[A-Za-z0-9_\-]{40,}"),
    ("hh_session_cookie",
     r"\b(hhtoken|hhuid|crypted_id|_xsrf|hhrole)\b[\"'\s:=]{1,6}[A-Za-z0-9_\-%]{10,}"),
    ("bearer", r"Bearer\s+[A-Za-z0-9_\-\.]{20,}"),
    ("password_kv", r"(password|passwd|пароль)[\"'\s]*[:=][\"'\s]*[^\s\"',}]{4,}"),
    ("api_key_kv",
     r"(api[_-]?key|secret|access[_-]?token)[\"'\s]*[:=][\"'\s]*[A-Za-z0-9_\-]{16,}"),
    ("private_key", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ("aws_access_key", r"AKIA[0-9A-Z]{16}"),
]

# Личные данные. Находка здесь - повод посмотреть глазами: часть таких
# совпадений законна (автор в LICENSE), часть - утечка (телефон в примере кода).
PII = [
    ("email", r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),
    ("phone_ru", r"(?<![\d\-])(?:\+7|8)[\s\-(]*9\d{2}[\s\-)]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}\b"),
    ("telegram_handle", r"(?<![\w/@])@[A-Za-z][A-Za-z0-9_]{4,31}\b"),
    ("home_path", r"[A-Za-z]:\\Users\\[^\\\"'\s]+|/home/[a-z0-9_\-]+/|/Users/[^/\"'\s]+/"),
]

# Двоичное регуляркой не проверить - такие файлы просто перечисляются, чтобы
# их пересмотрели глазами: на скриншоте бывает переписка, а в pdf - паспорт.
SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".exe", ".dll",
            ".zip", ".gz", ".ico", ".woff", ".woff2", ".ttf", ".mp4", ".sqlite"}
MAX_BYTES = 2 * 1024 * 1024


def pending_files(repo):
    """Отслеживаемое + новое неотслеживаемое, каталоги развёрнуты в файлы."""
    tracked = subprocess.check_output(
        ["git", "ls-files"], cwd=repo).decode("utf-8", "replace").splitlines()
    status = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=repo).decode("utf-8", "replace").splitlines()

    out = set(p.strip() for p in tracked if p.strip())
    for line in status:
        if not line.strip():
            continue
        path = line[3:].strip().strip('"')
        full = os.path.join(repo, path)
        if path.endswith("/") or os.path.isdir(full):
            for root, _dirs, files in os.walk(full):
                for f in files:
                    rel = os.path.relpath(os.path.join(root, f), repo)
                    out.add(rel.replace(chr(92), "/"))
        else:
            out.add(path)
    return sorted(out)


def scan(repo, files, extra):
    secrets, pii, binaries = {}, {}, []
    rx_secret = [(n, re.compile(p, re.I)) for n, p in SECRET]
    rx_pii = [(n, re.compile(p, re.I)) for n, p in PII] + extra

    for rel in files:
        full = os.path.join(repo, rel)
        if not os.path.isfile(full):
            continue
        if os.path.splitext(rel)[1].lower() in SKIP_EXT:
            binaries.append(rel)
            continue
        if os.path.getsize(full) > MAX_BYTES:
            binaries.append("%s (>%d МБ, не читан)" % (rel, MAX_BYTES // 1048576))
            continue
        try:
            txt = io.open(full, encoding="utf-8", errors="replace").read()
        except OSError as exc:
            binaries.append("%s (не прочитан: %s)" % (rel, exc))
            continue
        for name, rx in rx_secret:
            m = rx.search(txt)
            if m:
                line = txt[:m.start()].count(chr(10)) + 1
                secrets.setdefault(name, []).append((rel, line, m.group(0)[:60]))
        for name, rx in rx_pii:
            m = rx.search(txt)
            if m:
                line = txt[:m.start()].count(chr(10)) + 1
                pii.setdefault(name, []).append((rel, line, m.group(0)[:60]))
    return secrets, pii, binaries


def render(files, secrets, pii, binaries, limit):
    r = ["ФАЙЛОВ К ПУБЛИКАЦИИ: %d (двоичных и пропущенных: %d)" % (len(files), len(binaries)),
         "", "=" * 70, "ДОСТУПЫ - публиковать нельзя", "=" * 70]
    if not secrets:
        r.append("не найдено")
    for name, rows in sorted(secrets.items()):
        r += ["", "[%s] файлов: %d" % (name, len(rows))]
        for rel, line, sample in rows[:limit]:
            r.append("    %s:%d   ->   %s" % (rel, line, sample))
        if len(rows) > limit:
            r.append("    ... ещё %d" % (len(rows) - limit))

    r += ["", "=" * 70, "ЛИЧНЫЕ ДАННЫЕ - посмотреть глазами", "=" * 70]
    if not pii:
        r.append("не найдено")
    for name, rows in sorted(pii.items()):
        r += ["", "[%s] файлов: %d" % (name, len(rows))]
        for rel, line, sample in rows[:limit]:
            r.append("    %s:%d   ->   %s" % (rel, line, sample))
        if len(rows) > limit:
            r.append("    ... ещё %d" % (len(rows) - limit))

    if binaries:
        r += ["", "=" * 70, "ДВОИЧНОЕ - регуляркой не проверено", "=" * 70]
        r += ["    " + b for b in binaries[:limit]]
        if len(binaries) > limit:
            r.append("    ... ещё %d" % (len(binaries) - limit))
    return chr(10).join(r)


def main():
    ap = argparse.ArgumentParser(description="Аудит секретов и личных данных перед публикацией")
    ap.add_argument("--repo", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--out", help="куда писать отчёт (UTF-8); без него - в консоль")
    ap.add_argument("--limit", type=int, default=15, help="сколько находок показывать на шаблон")
    ap.add_argument("--phone", action="append", default=[], help="конкретный номер (можно повторять)")
    ap.add_argument("--email", action="append", default=[], help="конкретная почта")
    ap.add_argument("--name", action="append", default=[], help="конкретное имя или фамилия")
    args = ap.parse_args()

    extra = []
    for value in args.phone:
        digits = re.sub(r"\D", "", value)[-10:]
        if len(digits) == 10:
            # цифры вперемешку с любыми разделителями: 900 000-11-22, (900)0001122
            extra.append(("свой телефон",
                          re.compile(r"\D{0,3}".join(list(digits)))))
    for value in args.email:
        extra.append(("своя почта", re.compile(re.escape(value), re.I)))
    for value in args.name:
        extra.append(("своё имя", re.compile(re.escape(value), re.I)))

    files = pending_files(args.repo)
    secrets, pii, binaries = scan(args.repo, files, extra)
    report = render(files, secrets, pii, binaries, args.limit)

    if args.out:
        io.open(args.out, "w", encoding="utf-8", newline=chr(10)).write(report)
        print("отчёт: %s | файлов: %d | доступов: %d | видов PII: %d"
              % (args.out, len(files), len(secrets), len(pii)))
    else:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        print(report)

    return 1 if secrets else 0


if __name__ == "__main__":
    sys.exit(main())
