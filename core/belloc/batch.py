"""Пачкі — каб некалькі агентаў перакладалі паралельна, не чапаючы адны файлы.

Пачка — набор радкоў з розных табліц, апісаны ў games/<гульня>/batches.json:

  {
    "terms": {"wave": 1, "title": "Тэрміны",
              "rows": [{"table": "Items", "match": "_Name\\\\s*$"},
                       {"table": "Levels"}]},
    "dlg1":  {"wave": 1, "rows": [{"table": "Dialogue", "match": "^Dialogue_(Phone|Handler)_"}]}
  }

  match / exclude — рэгулярныя выразы па ключы (re.search); без match — уся табліца.
  note — рэгулярны выраз па заўвазе разам з `ctx: …` гульні (re.search): калі ключы
  дыялогаў — GUID, сцэну можна ўзяць з «ctx: Speaker @ SCENE_0010…».
  tables — рэгулярны выраз па імені табліцы (re.search) замест table: {"tables": "^101/(?!Line$)"}.
  slice — [ад, да] па нумары радка ў табліцы (як у Python, да — не ўключна; null — да канца):
  вялікую сцэну без чытэльных ключоў (ключ — лічбавы ID) дзеліць на кавалкі па парадку.
  Радок належыць ПЕРШАЙ пачцы (у парадку файла), якая яго ўзяла, — так
  «рэшта табліцы» апісваецца проста апошнім правілам без match.

Паўторы — "_repeats": [{"tables": "^dlg/(?!_)", "by": ["en"], "note": "^ctx: (?:\\\\S+ ([мж]) |(\\\\S+?)\\\\d* )"}, …].
Для табліц правіла радок мае подпіс: палі `by` (па змаўчанні — арыгінал) + групы
рэгуляркі `note`. Радок з подпісам, які ўжо быў раней (у парадку пачак), у пачку не
трапляе — ён «паўтор» першага; apply пераносіць пераклад першага на ўсе яго паўторы з
пустым bel.

Працоўны файл пачкі — local/<гульня>/work/<пачка>.csv (слупкі table, key, en, падказкі,
bel, note з `ctx: …` гульні ў пачатку): у ім ёсць тэкст гульні, таму ён толькі лакальны.
Агент правіць ТОЛЬКІ яго; у translation/*.csv пераносіць каардынатар — apply піша
толькі наш тэкст (ctx выразаецца):

    python -m belloc batch status silver-pines          # пакрыццё і прагрэс
    python -m belloc batch export silver-pines dlg1     # work/dlg1.csv (не перазапісвае)
    python -m belloc batch lint   silver-pines dlg1     # лінтэр па пачцы → build/lint-dlg1.md
    python -m belloc batch apply  silver-pines dlg1     # bel/note → translation/*.csv

Усім камандам патрэбны тэкст гульні — спачатку extract.
"""
from __future__ import annotations

import json
import os
import re

from . import tables
from .config import Loc


def _raw(loc: Loc) -> dict:
    path = loc.path("batches.json")
    if not os.path.exists(path):
        raise SystemExit(f"няма {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def spec(loc: Loc) -> dict:
    return {k: v for k, v in _raw(loc).items() if not k.startswith("_")}


def _load(loc: Loc) -> dict[str, list[dict]]:
    """Табліцы ў працоўным выглядзе: note з `ctx: …` гульні ў пачатку."""
    if not tables.has_source(loc):
        raise SystemExit(f"{loc.id}: пачкам патрэбны тэкст гульні — спачатку extract")
    res = tables.load_all(loc)
    for rows in res.values():
        for r in rows:
            r["note"] = tables.with_ctx(r.pop("ctx"), r["note"])
    return res


def _signature(loc: Loc, rules: list[dict], table: str, r: dict):
    """Подпіс радка для пошуку паўтораў (або None — табліца не пад правілам)."""
    for i, rule in enumerate(rules):
        if re.search(rule["tables"], table):
            sig = [r.get(f, "") for f in rule.get("by", [loc.source_lang])]
            if rule.get("note"):
                m = re.search(rule["note"], r["note"])
                sig += [g for g in m.groups() if g] if m else [r["note"]]
            return (i, *sig)
    return None


def work_path(loc: Loc, name: str) -> str:
    return os.path.join(loc.work, f"{name}.csv")


def fields(loc: Loc) -> list[str]:
    return ["table"] + tables.fields(loc)


def assign(loc: Loc, repeats: dict | None = None, data: dict | None = None
           ) -> tuple[dict[str, list[tuple[str, dict]]], list[tuple[str, str]]]:
    """{пачка: [(табліца, радок)]} і спіс радкоў без пачкі. repeats (калі дадзены)
    запаўняецца {(табліца, ключ) першага: [(табліца, ключ) паўтораў]}."""
    data = _load(loc) if data is None else data
    rules = _raw(loc).get("_repeats", [])
    first: dict[tuple, tuple[str, str]] = {}
    repeats = {} if repeats is None else repeats
    claimed: set[tuple[str, str]] = set()
    out: dict[str, list[tuple[str, dict]]] = {}
    for name, b in spec(loc).items():
        rows = []
        for rule in b["rows"]:
            if "tables" in rule:
                names = [t for t in data if re.search(rule["tables"], t)]
            elif rule["table"] in data:
                names = [rule["table"]]
            else:
                raise SystemExit(f"{name}: няма табліцы {rule['table']}")
            m = re.compile(rule["match"]) if rule.get("match") else None
            x = re.compile(rule["exclude"]) if rule.get("exclude") else None
            nt = re.compile(rule["note"]) if rule.get("note") else None
            lo, hi = rule.get("slice") or [None, None]
            for table in names:
                for r in data[table][lo:hi]:
                    k = (table, r["key"])
                    if (k in claimed or (m and not m.search(r["key"])) or (x and x.search(r["key"]))
                            or (nt and not nt.search(r["note"]))):
                        continue
                    claimed.add(k)
                    sig = _signature(loc, rules, table, r) if rules and r[loc.source_lang].strip() else None
                    if sig is not None and sig in first:
                        repeats.setdefault(first[sig], []).append(k)
                        continue
                    if sig is not None:
                        first[sig] = k
                    rows.append((table, r))
        out[name] = rows
    free = [(t, r["key"]) for t, rows in data.items() for r in rows
            if (t, r["key"]) not in claimed and r[loc.source_lang].strip() and not r["bel"].strip()]
    return out, free


def read_work(loc: Loc, name: str) -> list[dict]:
    path = work_path(loc, name)
    if not os.path.exists(path):
        raise SystemExit(f"няма {path} — спачатку batch export")
    return tables.read_csv(path)


def words(s: str) -> int:
    return len(s.split())


def status(loc: Loc):
    batches, free = assign(loc)
    sp = spec(loc)
    print(f"  {'пачка':10} {'хваля':5} {'радкоў':>7} {'слоў':>6} {'зроблена':>9}  work/")
    for name, rows in batches.items():
        need = [r for _, r in rows if r[loc.source_lang].strip()]
        done_main = sum(1 for r in need if r["bel"].strip())
        w = sum(words(r[loc.source_lang]) for r in need if not r["bel"].strip())
        work = ""
        if os.path.exists(work_path(loc, name)):
            wr = [r for r in tables.read_csv(work_path(loc, name)) if r[loc.source_lang].strip()]
            work = f"{sum(1 for r in wr if r['bel'].strip())}/{len(wr)}"
        print(f"  {name:10} {sp[name].get('wave', ''):>5} {len(need):7} {w:6} {done_main:4}/{len(need):<4}  {work}")
    print(f"  радкоў без пачкі (неперакладзеных): {len(free)}"
          + (f" — {free[:5]}…" if free else ""))


def export(loc: Loc, names: list[str], force=False):
    batches, _ = assign(loc)
    for name in names:
        if name not in batches:
            raise SystemExit(f"пачкі «{name}» няма ў batches.json")
        path = work_path(loc, name)
        if os.path.exists(path) and not force:
            print(f"{name}: {path} ужо ёсць — не перазапісваю (--force)")
            continue
        rows = [{"table": t, **r} for t, r in batches[name]]
        tables.write_csv(path, rows, fields(loc))
        todo = sum(1 for r in rows if r[loc.source_lang].strip() and not r["bel"].strip())
        print(f"{name}: {len(rows)} радкоў ({todo} перакладаць) → {path}")


def apply(loc: Loc, names: list[str], dry_run=False):
    data = _load(loc)
    repeats: dict[tuple[str, str], list[tuple[str, str]]] = {}
    if _raw(loc).get("_repeats"):
        assign(loc, repeats, data)
    index = {(t, r["key"]): r for t, rows in data.items() for r in rows}
    touched: set[str] = set()
    for name in names:
        changed = skipped = rep = 0
        for w in read_work(loc, name):
            r = index.get((w["table"], w["key"]))
            if r is None:
                print(f"  {name}: {w['table']}/{w['key']} — няма ў translation, прапушчана")
                skipped += 1
                continue
            if r[loc.source_lang] != w[loc.source_lang]:
                print(f"  {name}: {w['table']}/{w['key']} — арыгінал змяніўся, прапушчана")
                skipped += 1
                continue
            if w["bel"] and (w["bel"], w["note"]) != (r["bel"], r["note"]):
                r["bel"], r["note"] = w["bel"], w["note"]
                touched.add(w["table"])
                changed += 1
            if w["bel"]:
                for t, k in repeats.get((w["table"], w["key"]), []):
                    rr = index[(t, k)]
                    if not rr["bel"].strip():
                        rr["bel"] = w["bel"]
                        touched.add(t)
                        rep += 1
        print(f"{name}: перанесена {changed}" + (f", на паўторы {rep}" if rep else "")
              + f", прапушчана {skipped}")
    if dry_run:
        print("(--dry-run: нічога не запісана)")
        return
    for t in sorted(touched):
        tables.save(loc, t, data[t])         # толькі наш тэкст: ctx выразаецца
    tables.stats(loc)


def pairs(loc: Loc, name: str) -> str:
    res, clash = {}, 0
    for w in read_work(loc, name):
        if w["bel"].strip():
            src = w[loc.source_lang]
            if src in res and res[src] != w["bel"]:
                clash += 1
                continue
            res[src] = w["bel"]
    out = os.path.join(loc.build, f"batch-{name}-pairs.json")
    os.makedirs(loc.build, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"strings": res}, f, ensure_ascii=False, indent=1)
    print(f"{name}: пар {len(res)}, адзін арыгінал з розным перакладам: {clash}")
    return out
