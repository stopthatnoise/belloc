"""«Выніковы слоўнік» з «Дапаможніка для перакладчыкаў фэнтэзі» (МТГ «RэЗервацыЯ»).

~750 тэрмінаў фэнтэзі і D&D: англійскі тэрмін → беларускія адпаведнікі (+ старабеларускі,
рускі, польскі, украінскі, чэшскі, нямецкі, французскі). Ліцэнзія — CC BY-SA 4.0: тэрмін,
узяты ў гласарый гульні, пазначаем у note «паводле „Дапаможніка“». Файл — local/dicts/fantasy.tsv
(`python -m belloc dicts fantasy`), у рэпазіторый не кладзецца: слоўнік — рабочы праект і
абнаўляецца.

    python -m belloc fantasy lich halberd          # па пачатку англійскага тэрміна
    python -m belloc fantasy ettin --exact          # толькі дакладны тэрмін
    python -m belloc fantasy кальчуга --reverse     # дзе слова ёсць сярод беларускіх адпаведнікаў
    python -m belloc fantasy-report <гульня>        # тэрміны слоўніка ў гульні → build/fantasy.md

Ячэйка `бел.` — як у слоўніках: націскі, значэнні «1) … 2) …», заўвагі ў дужках, граматыка
(«-а м.», «Р сце́ню м.»), варыянты праз «,» і « / », спасылкі «гл. <тэрмін>». variants()
дастае з яе самі адпаведнікі — для справаздачы, ці ўжыты ў перакладзе хоць адзін.
"""
from __future__ import annotations

import csv
import os
import re
import unicodedata

from . import dicts

SOURCE = ("«Дапаможнік для перакладчыкаў фэнтэзі», МТГ «RэЗервацыЯ» "
          "(patreon.com/by_reservation), CC BY-SA 4.0")
STRESS = "\u0300\u0301"
OTHER = ("ст.-бел.", "рус.", "пол.", "укр.", "чэш.", "ням.", "фр.", "іншыя мовы")


def plain(s: str) -> str:
    """Без націскаў, ніжні рэгістр, ё→е."""
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if c not in STRESS)
    return unicodedata.normalize("NFC", s).replace("ё", "е").replace("’", "'")


def no_stress(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    return unicodedata.normalize("NFC", "".join(c for c in s if c not in STRESS))


def load(path: str | None = None) -> list[dict]:
    """Радкі слоўніка: {"англ.": …, "бел.": …, …}; пустыя прапускаюцца."""
    path = path or dicts.path("fantasy.tsv")
    if not os.path.exists(path):
        raise SystemExit(f"няма {path} — спампуйце: python -m belloc dicts fantasy")
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f, delimiter="\t"))
    head = [h.strip() for h in rows[0]]
    out = []
    for r in rows[1:]:
        e = {h: (r[i].strip() if i < len(r) else "") for i, h in enumerate(head)}
        if e.get("англ.") and e.get("бел."):
            out.append(e)
    return out


# ---------------------------------------------------------------- разбор ячэек

REF = re.compile(r"\bгл\.(?:\s*тс\.)?\s+(.+)")
# «1) … 2) …», «а) … б) …», але не «(у D&D3) …»: нумар — у пачатку або пасля прабелу/«;»
MEANING = re.compile(r"(?:^|(?<=[\s;]))(?:\d|[а-я])\)\s*")
GRAMMAR = re.compile(r"\s*(?:,\s*)?(?:-\S+|Р\s+\S+)?\s+(?:м|ж|н|мн)\.(?=\s|$|,)")
LABELS = re.compile(r"^(?:жарг|разм|памянш|павял|уст|абрэв)\.\s*")


def en_forms(term: str) -> list[str]:
    """«shadow, shade» → [shadow, shade]; «dexterity (DEX)» → [dexterity, DEX]."""
    forms = []
    for part in term.split(","):
        abbr = re.findall(r"\(([A-Z][A-Za-z&]*)\)", part)
        base = re.sub(r"\s*\(.*?\)", "", part).strip()
        if base:
            forms.append(base)
        forms += abbr
    return forms


ARTICLES = {"a", "an", "the", "of", "to"}


def qualifiers(term: str) -> list[str]:
    """Удакладненні ў дужках, без абрэвіятур: «fire (damage)» → [damage]; «cast (a spell)» → [spell]."""
    out = []
    for q in re.findall(r"\(([^()]*)\)", term):
        if not re.fullmatch(r"[A-Z][A-Za-z&]*", q.strip()):
            out += [w.lower() for w in re.findall(r"[A-Za-z]+", q) if w.lower() not in ARTICLES]
    return out


def _split(cell: str) -> tuple[list[str], list[str]]:
    """(адпаведнікі, спасылкі «гл.») з ячэйкі `бел.`."""
    words, refs = [], []
    for meaning in MEANING.split(no_stress(cell)):
        meaning = re.sub(r"\([^()]*\)", " ", re.sub(r"\([^()]*\)", " ", meaning))   # і ўкладзеныя
        for alt in re.split(r"\s*(?:;|\|\||/)\s*", meaning):
            m = REF.search(alt)
            if m:                              # «сервельер гл. тс. skull cap» — і слова, і спасылка
                refs += [x.strip() for x in m.group(1).split(",") if x.strip()]
                alt = alt[:m.start()]
            alt = GRAMMAR.sub("", alt)
            for v in alt.split(","):
                v = LABELS.sub("", v.strip()).strip(" .—–")
                if v and not v.startswith("-") and re.search(r"[а-яёіў]", v.lower()):
                    words.append(v)
    return words, refs


def index(rows: list[dict]) -> dict[str, dict]:
    """{англ. тэрмін (ніжні рэгістр, кожная форма): радок}."""
    res = {}
    for e in rows:
        for f in en_forms(e["англ."]) + [e["англ."]]:
            res.setdefault(f.lower(), e)
    return res


def variants(e: dict, idx: dict[str, dict], depth: int = 0) -> list[str]:
    """Беларускія адпаведнікі тэрміна, разам з тымі, на якія ён спасылаецца «гл.»."""
    words, refs = _split(e["бел."])
    if depth < 2:
        for ref in refs:
            target = idx.get(ref.lower()) or idx.get(re.sub(r"\s*\(.*?\)", "", ref).lower())
            if target is not None and target is not e:
                words += variants(target, idx, depth + 1)
    seen, out = set(), []
    for w in words:
        if plain(w) not in seen:
            seen.add(plain(w))
            out.append(w)
    return out


def _stems(variant: str) -> list[str]:
    return [w[:max(4, len(w) - 2)] for w in re.findall(r"[а-яеіў'-]+", plain(variant)) if len(w) >= 3]


def covered(bel: str, vs: list[str]) -> bool:
    """Ці ўжыты ў перакладзе хоць адзін адпаведнік (па аснове кожнага слова)."""
    text = plain(bel)
    return any(st and all(s in text for s in st) for st in map(_stems, vs))


# ---------------------------------------------------------------- пошук

def search(queries: list[str], exact=False, reverse=False, all_langs=False, limit=30):
    rows = load()
    for q in queries:
        qk = plain(q).strip()
        if reverse:
            word = re.compile(r"(?<![а-яеіў'-])" + re.escape(qk) + r"(?![а-яеіў'-])")
            hits = [e for e in rows if word.search(plain(e["бел."]))]
        elif exact:
            hits = [e for e in rows if qk in (f.lower() for f in en_forms(e["англ."]) + [e["англ."]])]
        else:
            hits = [e for e in rows if any(f.lower().startswith(qk) for f in en_forms(e["англ."]))]
            hits.sort(key=lambda e: (e["англ."].lower() != qk, len(e["англ."])))
        print(f"── {q}: {len(hits)}" + (f" (паказана {limit})" if len(hits) > limit else ""))
        for e in hits[:limit]:
            print(f"   {e['англ.']:32} → {e['бел.']}")
            for col in OTHER if all_langs else ("ст.-бел.",):
                if e.get(col):
                    print(f"   {'':32}   {col} {e[col]}")
    print(f"(крыніца: {SOURCE})")


# ---------------------------------------------------------------- даклад па гульні

def report(loc, out_md: str, examples: int = 5) -> int:
    """Тэрміны слоўніка ў тэксце гульні: ці стаіць у перакладзе адзін з адпаведнікаў."""
    from . import glossary, tables
    if not tables.has_source(loc):
        raise SystemExit(f"{loc.id}: дакладу патрэбны тэкст гульні — спачатку extract")
    rows = load()
    idx = index(rows)
    terms = []
    for e in rows:
        vs = variants(e, idx)
        if not vs:
            continue
        # кароткія словы шумяць, але абрэвіятуры (AC, DM, HP) — важныя
        forms = [f for f in en_forms(e["англ."]) if len(f) >= 3 or (f.isupper() and len(f) >= 2)]
        if not forms:
            continue
        # абрэвіятура (DEX, PC) — з улікам рэгістра, словы — без, з -s/-es
        rx = re.compile("|".join(
            (r"\b" + re.escape(f) + r"\b") if f.isupper() else
            (r"(?i:\b" + re.escape(f) + r"(?:s|es)?\b)") for f in forms))
        # «fire (damage)» — толькі там, дзе ў радку ёсць і «damage»: інакш агонь у каміне
        qs = [re.compile(r"(?i)\b" + re.escape(q)) for q in qualifiers(e["англ."])]
        terms.append((e, vs, rx, qs))

    gloss = {}
    if loc.glossaries:
        for _, entries in glossary.sections(glossary.load_layers(loc.glossaries)):
            for en, info in entries.items():
                if isinstance(info, dict) and info.get("bel"):
                    for f in en_forms(en) + [en]:
                        gloss.setdefault(f.lower(), info["bel"])

    def ours(bel: str) -> list[str]:
        """Варыянты з нашага гласарыя — тым жа разборам, са спасылкамі «гл.» на іншыя запісы."""
        words, refs = _split(bel)
        for ref in refs:
            words += _split(gloss.get(ref.lower(), ""))[0]
        return words

    stats = {}
    for table, trs in tables.load_all(loc).items():
        for r in trs:
            src, bel = r[loc.source_lang], r["bel"]
            if not src or not bel:
                continue
            for e, vs, rx, qs in terms:
                if rx.search(src) and all(q.search(src) for q in qs):
                    s = stats.setdefault(e["англ."], [e, vs, 0, []])
                    s[2] += 1
                    if not covered(bel, vs):
                        s[3].append((table, r["key"], src, bel))

    # 1. гласарый гульні супраць слоўніка: свядомае рашэнне, але варта зверыць
    vs_gloss, in_gloss = [], set()
    for e, vs, _, _ in terms:
        for f in en_forms(e["англ."]):
            if f.lower() not in gloss:
                continue
            in_gloss.add(e["англ."])
            mine = ours(gloss[f.lower()])
            if mine and not any(covered(m, vs) for m in mine):
                vs_gloss.append((f, ", ".join(mine), vs))
            break
    # 2. тэрміны ў тэксце, дзе ў перакладзе ні аднаго адпаведніка; тэрміны гласарыя
    #    тут не паўтараем — іх аднастайнасць правярае праверка glossary лінтэра
    found = sorted(stats.values(), key=lambda s: -len(s[3]))
    miss = [s for s in found if s[3] and s[0]["англ."] not in in_gloss]

    out = [f"# Тэрміны «Дапаможніка» ў перакладзе — {loc.name}\n",
           f"Крыніца: {SOURCE}. Слоўнік — рабочы праект; разыходжанне — не памылка, а месца "
           "праверыць: у гульні тэрмін можа значыць іншае, а слова — мець іншую форму.\n",
           f"Тэрмінаў слоўніка ў тэксце гульні: {len(found)}; з іх у гласарыі гульні — "
           f"{len(in_gloss)}; па-за гласарыем у {len(miss)} ёсць радкі, дзе пераклад не ўжывае "
           "ні аднаго адпаведніка. Тэрмін з удакладненнем у дужках («fire (damage)») "
           "шукаецца толькі ў радках, дзе ёсць і ўдакладненне.\n",
           f"## 1. Гласарый гульні разыходзіцца са слоўнікам ({len(vs_gloss)})\n"]
    out += ["| тэрмін | наш гласарый | «Дапаможнік» |", "|---|---|---|"]
    out += [f"| {f} | {ours} | {', '.join(vs)} |" for f, ours, vs in vs_gloss]
    out += ["", f"## 2. Тэрміны ў тэксце без адпаведніка ў перакладзе ({len(miss)})\n"]
    for e, vs, n, bad in miss:
        out.append(f"### {e['англ.']} — {len(bad)} з {n}\n")
        out.append(f"- «Дапаможнік»: {', '.join(vs)}")
        for table, key, src, bel in bad[:examples]:
            out.append(f"  - `{table}` / `{key}`: {src[:120]!r} → {bel[:120]!r}")
        out.append("")
    os.makedirs(os.path.dirname(os.path.abspath(out_md)), exist_ok=True)
    with open(out_md, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out))
    print(f"тэрмінаў у гульні {len(found)}, без адпаведніка — {len(miss)}, "
          f"гласарый разыходзіцца — {len(vs_gloss)} → {out_md}")
    return 0
