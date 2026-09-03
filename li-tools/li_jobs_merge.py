# -*- coding: utf-8 -*-
"""Свести выдачи поиска в один список и разложить по ярусам.

Ярус считаем по ЗАПРОСУ-ИСТОЧНИКУ (домен — это отдельный запрос), а не по
словам в заголовке: название компании о домене ничего не говорит.
"""
import glob, io, json, os, sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def _dir(name, env):
    """Каталог рядом с репозиторием; путь не зашит, логина ОС в коде нет."""
    return os.environ.get(env) or os.path.join(_ROOT, name)

DIR = sys.argv[1] if len(sys.argv) > 1 else _dir("li_jobs", "LI_JOBS")

NOT_FOR_HIM = ("аналитик", "analyst", "affiliate manager", "intern", "стажер",
               "junior", "designer", "дизайнер", "engineer", "developer",
               "разработчик", "scientist", "marketing manager", "sales")
PRODUCT = ("product manager", "product owner", "head of product", "product lead",
           "chief product officer", "cpo", "продукт", "продакт", "product director",
           "director of product", "vp product", "vp of product", "product head")

rows = {}
for f in glob.glob(os.path.join(DIR, "*.json")):
    src = os.path.basename(f)[:-5]
    if src == "probe" or src.startswith("_"):
        continue
    for r in json.load(open(f, encoding="utf-8")):
        jid = r["id"]
        if jid in rows:
            rows[jid]["src"].append(src)
        else:
            r["src"] = [src]
            rows[jid] = r

out = []
for r in rows.values():
    t = (r.get("title") or "").lower()
    if any(w in t for w in NOT_FOR_HIM) and not any(w in t for w in PRODUCT):
        continue
    if not any(w in t for w in PRODUCT):
        continue
    domain = any(s.startswith("dom_") for s in r["src"])
    lead = any(w in t for w in ("head", "chief", "director", "cpo", "vp", "lead",
                                "директор", "руководител"))
    r["tier"] = "A домен+руководство" if (domain and lead) else \
                "B домен" if domain else \
                "C руководство" if lead else "D продакт"
    out.append(r)

order = {"A домен+руководство": 0, "B домен": 1, "C руководство": 2, "D продакт": 3}
out.sort(key=lambda r: (order[r["tier"]], r["company"]))
json.dump(out, open(os.path.join(DIR, "_merged.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

from collections import Counter
print("всего продуктовых:", len(out))
for k, v in sorted(Counter(r["tier"] for r in out).items()):
    print(f"  {k}: {v}")
for r in out:
    print(f"[{r['tier'][0]}] {r['id']} | {r['title'][:60]} | {r['company'][:28]} | "
          f"{r['location'][:45]} | {','.join(s[:12] for s in r['src'])}")
