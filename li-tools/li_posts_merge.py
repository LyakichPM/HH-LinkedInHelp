# -*- coding: utf-8 -*-
"""Свести посты в один список: убрать чужие роли, старьё и повторы авторов.

Возраст поста берём из карточки («3 нед.», «5 мес.»); всё старше MAXMON
месяцев отбрасываем — вакансия из такого поста давно закрыта.

  py li_posts_merge.py [каталог] [макс_месяцев]
"""
import glob, io, json, os, re, sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def _dir(name, env):
    """Каталог рядом с репозиторием; путь не зашит, логина ОС в коде нет."""
    return os.environ.get(env) or os.path.join(_ROOT, name)

DIR = sys.argv[1] if len(sys.argv) > 1 else _dir("li_posts", "LI_POSTS")
MAXMON = float(sys.argv[2]) if len(sys.argv) > 2 else 3.0

PRODUCT = ("продакт", "продукт", "product manager", "product owner", "head of product",
           "product lead", "cpo", "менеджер продукта")
NOT_FOR_HIM = ("аналитик", "analyst", "affiliate manager", "стажер", "intern",
               "junior", "дизайнер", "designer", "разработчик", "developer",
               "qa ", "тестировщик", "sales manager", "менеджер по продажам")


def months(age):
    m = re.search(r"(\d+)\s*(мин|ч|дн|нед|мес|г)", age or "", re.I)
    if not m:
        return 99.0
    n, u = int(m.group(1)), m.group(2).lower()
    return {"мин": 0, "ч": 0, "дн": n / 30, "нед": n / 4.3, "мес": n, "г": n * 12}[u]


rows = {}
for f in glob.glob(os.path.join(DIR, "*.json")):
    if os.path.basename(f).startswith("_"):
        continue
    for r in json.load(open(f, encoding="utf-8")):
        key = r["profile"] + r["text"][:80]
        if key in rows:
            rows[key].setdefault("queries", []).append(r["query"])
        else:
            r["queries"] = [r["query"]]
            rows[key] = r

out, drop = [], Counter()
for r in rows.values():
    low = (r["text"] + " " + r.get("author_title", "")).lower()
    age = months(r.get("age", ""))
    if age > MAXMON:
        drop["старьё"] += 1; continue
    if not any(w in low for w in PRODUCT):
        drop["не про продукт"] += 1; continue
    if any(w in low for w in NOT_FOR_HIM) and "продакт" not in low[:300]:
        drop["чужая роль"] += 1; continue
    r["months"] = round(age, 1)
    out.append(r)

out.sort(key=lambda r: r["months"])
json.dump(out, open(os.path.join(DIR, "_merged.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"всего постов: {len(rows)}, годных: {len(out)}, отброшено: {dict(drop)}")
for r in out:
    print(f"\n[{r['months']} мес] {r['author']} — {r.get('author_title','')[:60]}")
    print(f"   {r['profile']}")
    print(f"   {r['text'][:220]}")
