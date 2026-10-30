"""Пераклад па табліцах: два слаі — наш тэкст у рэпазіторыі, тэкст гульні лакальна.

**У рэпазіторыі** — games/<гульня>/translation/<табліца>.csv, слупкі
`key, src_hash, bel, note`. Тэксту гульні тут няма (гл. CLAUDE.md):

  - src_hash — 16 hex SHA-256 арыгінала (пуста, калі арыгінал пусты): па ім
    sync бачыць, што радок у гульні змяніўся, не захоўваючы самога тэксту;
  - note — толькі нашы заўвагі (`?: …`, `stale: …`); заўвагі распрацоўшчыка
    `ctx: …` сюды не пішуцца — save() іх выразае.

**Лакальна** — local/<гульня>/source/<мова>.json ({табліца: {ключ: тэкст}}) і
context.json ({табліца: {ключ: заўвага}}), якія кладзе extract рухавіка.
load_all() далучае іх у памяці: радок = key, <source_lang>, <падказкі…>, bel,
note, ctx, src_hash. Без source/ тэкст гульні пусты, а прагрэс і пераклад
па ключах усё роўна працуюць.

**Кавалкі арыгінала** (`"from_original"` у game.json — рэгулярка, напр. `\\[[^\\]]*\\]`):
нябачныя ў гульні кавалкі (рэмаркі акцёрам у TWAU), якія пераклад пакідае як у
арыгінале, у рэпазіторыі захоўваюцца заглушкай `[]`. Адпаведнасць — па парадку:
k-ты збег у bel ↔ k-ты ў арыгінале. save() згортвае (collapse), load_all()
разгортвае (expand), рухавік пры зборцы падстаўляе кавалкі з файлаў гульні.

Табліца можа быць з падпапкамі (activities/coronation_activity →
translation/activities/coronation_activity.csv); імя — шлях праз «/».

CSV — UTF-8 без BOM, `newline=""` пры чытанні і запісе, канцы радкоў `\\n`.
У перакладзе бываюць сапраўдныя `\\r\\n` унутры тэксту (як у арыгінале) — таму
ў .gitattributes для CSV стаіць -text.
"""
from __future__ import annotations

import csv
import glob
import hashlib
import json
import os
import re

from .config import Loc

REPO_COLS = ["key", "src_hash", "bel", "note"]


def src_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16] if text else ""


# ---------------------------------------------------------------- заўвагі

def own_note(note: str) -> str:
    """Толькі нашы часткі заўвагі — без `ctx: …` з гульні."""
    return " | ".join(p for p in note.split(" | ") if p and not p.startswith("ctx: "))


def with_ctx(ctx: str, note: str) -> str:
    """Заўвага для працоўных файлаў: `ctx: …` гульні ў пачатку."""
    return " | ".join(([f"ctx: {ctx}"] if ctx else []) + ([note] if note else []))


# ---------------------------------------------------------------- кавалкі арыгінала

PLACEHOLDER = "[]"


def from_original(pattern: str | None) -> re.Pattern | None:
    """Рэгулярка кавалкаў арыгінала; заглушка мусіць ёй адпавядаць (парадак збегаў)."""
    if not pattern:
        return None
    pat = re.compile(pattern)
    if not pat.fullmatch(PLACEHOLDER):
        raise SystemExit(f"from_original: «{pattern}» не адпавядае заглушцы {PLACEHOLDER}")
    return pat


def _swap(bel: str, src: str, pat: re.Pattern | None, to_placeholder: bool) -> str:
    if not pat or not bel or not src:
        return bel
    orig = [m.group(0) for m in pat.finditer(src)]
    if len(orig) != sum(1 for _ in pat.finditer(bel)):
        return bel
    k = iter(orig)

    def one(m):
        o = next(k)
        if to_placeholder:
            return PLACEHOLDER if m.group(0) == o else m.group(0)
        return o if m.group(0) == PLACEHOLDER else m.group(0)
    return pat.sub(one, bel)


def collapse(bel: str, src: str, pat: re.Pattern | None) -> str:
    """Кавалкі bel, роўныя кавалкам арыгінала на тым жа месцы, → заглушка."""
    return _swap(bel, src, pat, True)


def expand(bel: str, src: str, pat: re.Pattern | None) -> str:
    """Заглушкі → кавалкі арыгінала (калі колькасць збегаў не супала — як ёсць)."""
    return _swap(bel, src, pat, False)


# ---------------------------------------------------------------- CSV

def hint_langs(loc: Loc) -> list[str]:
    """hint_lang і дадатковыя падказкі (extra_hints: напр. ["uk"])."""
    return ([loc.hint_lang] if loc.hint_lang else []) + loc.raw.get("extra_hints", [])


def fields(loc: Loc) -> list[str]:
    """Слупкі поўнага выгляду — для лакальных працоўных файлаў (пачкі)."""
    return ["key", loc.source_lang] + hint_langs(loc) + ["bel", "note"]


def read_csv(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: str, rows: list[dict], cols: list[str]):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, cols, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def table_path(loc: Loc, table: str) -> str:
    return os.path.join(loc.translation, f"{table}.csv")


def load_repo(loc: Loc) -> dict[str, list[dict]]:
    """{табліца: радкі key, src_hash, bel, note} — толькі тое, што ў рэпазіторыі."""
    paths = glob.glob(os.path.join(loc.translation, "**", "*.csv"), recursive=True)
    return {os.path.relpath(p, loc.translation)[:-4].replace(os.sep, "/"): read_csv(p)
            for p in sorted(paths)}


def save(loc: Loc, table: str, rows: list[dict]):
    """Запісаць табліцу ў рэпазіторый: толькі key, src_hash, bel, note.

    src_hash лічыцца з арыгінала, калі ён ёсць у радку, інакш застаецца
    стары; ctx з note выразаецца; кавалкі арыгінала ў bel → заглушка.
    """
    out = []
    pat = from_original(loc.raw.get("from_original"))
    for r in rows:
        text = r.get(loc.source_lang) or ""
        out.append({"key": r["key"], "src_hash": src_hash(text) if text else r.get("src_hash", ""),
                    "bel": collapse(r.get("bel", ""), text, pat), "note": own_note(r.get("note", ""))})
    write_csv(table_path(loc, table), out, REPO_COLS)


# ---------------------------------------------------------------- тэкст гульні

def _source(loc: Loc, lang: str) -> dict:
    path = os.path.join(loc.source, f"{lang}.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def has_source(loc: Loc) -> bool:
    return os.path.exists(os.path.join(loc.source, f"{loc.source_lang}.json"))


def load_all(loc: Loc) -> dict[str, list[dict]]:
    """Табліцы рэпазіторыя з далучаным тэкстам гульні (калі source/ ёсць)."""
    src = _source(loc, loc.source_lang)
    hints = {lang: _source(loc, lang) for lang in hint_langs(loc)}
    context = _source(loc, "context")
    pat = from_original(loc.raw.get("from_original"))
    res = {}
    for table, rows in load_repo(loc).items():
        s, c = src.get(table, {}), context.get(table, {})
        full = []
        for r in rows:
            k = r["key"]
            row = {"key": k, loc.source_lang: s.get(k, "")}
            for lang, h in hints.items():
                row[lang] = h.get(table, {}).get(k, "")
            row.update(bel=expand(r["bel"], row[loc.source_lang], pat), note=r["note"],
                       ctx=c.get(k, ""), src_hash=r["src_hash"])
            full.append(row)
        res[table] = full
    return res


def sync(loc: Loc):
    """source/ → translation/: новыя ключы, выдаленыя, змененыя арыгіналы.

    Калі арыгінал змяніўся, а пераклад ужо быў — стары bel пераносіцца ў note
    як «stale: …», bel ачышчаецца. Ключы, якіх у гульні больш няма, выкідаюцца.
    """
    if not has_source(loc):
        raise SystemExit(f"{loc.id}: няма {os.path.join(loc.source, loc.source_lang + '.json')}"
                         " — спачатку extract")
    src = _source(loc, loc.source_lang)
    for table, strings in src.items():
        old = {r["key"]: r for r in read_csv(table_path(loc, table))}
        rows, stale = [], 0
        for key, text in strings.items():
            prev = old.pop(key, None)
            h = src_hash(text)
            bel = prev["bel"] if prev else ""
            note = own_note(prev["note"]) if prev else ""
            if prev and prev["src_hash"] != h and bel:
                note = f"stale: {bel}" + (f" | {note}" if note else "")
                bel = ""
                stale += 1
            rows.append({"key": key, "src_hash": h, "bel": bel, "note": note})
        write_csv(table_path(loc, table), rows, REPO_COLS)
        if stale or old:
            print(f"{table}: састарэла {stale}, выдалена {len(old)}"
                  + (f" ({', '.join(list(old)[:5])}…)" if old else ""))
    orphan = sorted(set(load_repo(loc)) - set(src))
    if orphan:                             # не выдаляем: там можа быць пераклад
        print(f"табліц няма ў крыніцы ({len(orphan)}), CSV засталіся: {', '.join(orphan[:8])}"
              + ("…" if len(orphan) > 8 else ""))
    stats(loc)


# ---------------------------------------------------------------- справаздачы

def stats(loc: Loc, max_rows: int = 40):
    """Прагрэс па табліцах; калі іх больш за max_rows — па верхніх папках."""
    tables = load_repo(loc)
    group = (lambda t: t) if len(tables) <= max_rows else (
        lambda t: t.split("/")[0] if "/" in t else "(корань)")
    agg: dict[str, list[int]] = {}
    for table, rows in tables.items():
        need = [r for r in rows if r["src_hash"]]
        a = agg.setdefault(group(table), [0, 0])
        a[0] += sum(1 for r in need if r["bel"].strip())
        a[1] += len(need)
    w = max([18] + [len(g) for g in agg])
    for g, (ok, n) in agg.items():
        print(f"  {g:{w}} {ok:6}/{n:<6}")
    done, total = sum(a[0] for a in agg.values()), sum(a[1] for a in agg.values())
    print(f"  {'УСЯГО':{w}} {done:6}/{total:<6} ({done * 100 // max(total, 1)}%)")


def pairs(loc: Loc, out: str):
    """{арыгінал: bel} для лінтэра — лакальна, у build/ (патрэбны source/)."""
    if not has_source(loc):
        raise SystemExit(f"{loc.id}: pairs патрабуе тэксту гульні — спачатку extract")
    res, clash = {}, 0
    for rows in load_all(loc).values():
        for r in rows:
            if r["bel"].strip():
                src = r[loc.source_lang]
                if src in res and res[src] != r["bel"]:
                    clash += 1
                    continue
                res[src] = r["bel"]
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"strings": res}, f, ensure_ascii=False, indent=1)
    print(f"пар {len(res)}, адзін арыгінал з розным перакладам: {clash} (бярэцца першы)")


def used_chars(loc: Loc) -> set[int]:
    """Усе непрабельныя сімвалы са слупка bel — каб праверыць шрыфты."""
    cs = set()
    for rows in load_repo(loc).values():
        for r in rows:
            cs |= {ord(c) for c in r["bel"] if not c.isspace()}
    return cs


def translation_by_key(loc: Loc) -> dict[str, dict[str, str]]:
    """{табліца: {ключ: bel}} — толькі перакладзенае."""
    return {table: {r["key"]: r["bel"] for r in rows if r["bel"]}
            for table, rows in load_repo(loc).items()}
