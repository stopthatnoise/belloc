"""Пачкі для batches.json: ~TARGET унікальных слоў на пачку (паўторы — па правілах _repeats,
як у core/belloc/batch.py). Сюжэт рэжацца толькі на мяжы размовы (апісанне ў ключы
…_ch02lw00_673_before_ernesto_three_ne_01 → «before_ernesto_three»).

    PYTHONPATH=core python -X utf8 games/…/research/make_batches.py indiana-jones-great-circle
"""
import json
import re
import sys

from belloc import config, tables

TARGET = 3000

REPEATS = [
    {"tables": "^(ui/|vo/name$)", "by": ["en", "ru"]},
    {"tables": "^vo/sl/", "by": ["en"],
     "note": "^ctx: (?:(officer|cultist|sister|father|brother|priest|nun|mrs|mr|ms)|(\\S+))"},
    {"tables": "^vo/(nl|tp)/|^vo/ef$", "by": ["en"], "note": "^ctx: (\\S+)"},
]
WAVES = [
    ("u", 1, "Інтэрфейс", lambda t: t in ("vo/_names", "vo/name") or t.startswith("ui/")),
    ("s", 2, "Сюжэт", lambda t: t.startswith("vo/nl/") or t.startswith("vo/tp/")),
    ("b", 3, "Баркі", lambda t: t.startswith("vo/sl/") or t == "vo/ef"),
]
FIRST = {"vo/_names": 0, "vo/name": 1, "vo/sl/indy": 2, "vo/sl/gina": 3}


def conv(key: str) -> str:
    p = key.lower().lstrip("#").split("_")
    return "_".join(p[6:-2]) if len(p) > 8 and p[2] == "nl" else ""


def clean_words(t: str) -> int:
    t = re.sub(r"\[[\d.]+\]|<[^>]*>|\^C\"[^\"]*\"|\^.|%\S+|(?<!\w)_[a-z][a-z0-9_]*", " ", t)
    return len(re.findall(r"[A-Za-z][A-Za-z'’-]*", t))


def main(game: str):
    loc = config.load(game)
    data = tables.load_all(loc)
    seen = set()

    def sig(table, r):
        for i, rule in enumerate(REPEATS):
            if re.search(rule["tables"], table):
                s = [r.get(f, "") for f in rule["by"]]
                if rule.get("note"):
                    m = re.search(rule["note"], r["ctx"] and "ctx: " + r["ctx"])
                    s += [g for g in m.groups() if g] if m else [r["ctx"]]
                return (i, *s)
        return None

    out = {"_about": (f"Пачкі Indiana Jones and the Great Circle (core/belloc/batch.py), ~{TARGET} унікальных "
                      "слоў на пачку (паўторы — _repeats; генератар — research/make_batches.py). Хваля 1 (u) — "
                      "імёны над субтытрамі, імёны персанажаў, інтэрфейс, нататкі (з іх папаўняецца гласарый); "
                      "2 (s) — сюжэт па раздзелах (vo/nl/<раздзел>, рэплікі па нумары з ключа) і размовы ў дарозе "
                      "(vo/tp); 3 (b) — сістэмныя баркі (vo/sl, адзін тэкст на ўсе аднолькавыя галасы) і гукі."),
           "_repeats": REPEATS}
    for prefix, wave, title, want in WAVES:
        names = sorted((t for t in data if want(t)), key=lambda t: (FIRST.get(t, 9), t))
        n, cur, words, total = 0, [], 0, 0

        def close():
            nonlocal n, cur, words
            if cur:
                out[f"{prefix}{n:02d}"] = {"wave": wave, "title": f"{title} {n} (~{words} слоў)", "rows": cur}
                n, cur, words = n + 1, [], 0

        for t in names:
            rows = data[t]
            start = 0
            for i, r in enumerate(rows):
                w = 0
                if r["en"].strip():
                    s = sig(t, r)
                    if s is None or s not in seen:
                        w = clean_words(r["en"])
                    if s is not None:
                        seen.add(s)
                boundary = i > start and (not conv(r["key"]) or conv(r["key"]) != conv(rows[i - 1]["key"]))
                if words >= TARGET and (boundary or words >= TARGET * 1.6) and i > start:
                    cur.append({"table": t, "slice": [start, i]})
                    close()
                    start = i
                words += w
                total += w
            cur.append({"table": t} if start == 0 else {"table": t, "slice": [start, None]})
        close()
        print(f"хваля {wave} ({prefix}): пачак {n}, слоў {total}")
    with open(loc.path("batches.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")


if __name__ == "__main__":
    main(sys.argv[1])
