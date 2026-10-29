"""«Антыкалька» — Новы расейска-беларускі слоўнік Алега Мінкіна (TSV).

~101 тыс. артыкулаў «рускае слова / выраз → беларускія адпаведнікі без калькі».
Карысны як даведнік: што сказаць замест русізма (запонка → запінка,
ожидаемый → чаканы) і як перадаць устойлівы выраз (а ему нипочём → а ён
і ня лыс). Аўтаматычнай праверкай ён быць не можа: словы толькі ў пачатковай
форме, шмат амонімаў (ад, да, бура), а прапановы бываюць пурысцкія або
дыялектныя (рычаг → асвер).

**Правапіс слоўніка — тарашкевіца** (ня, -ньне, сьн, э ў запазычаннях:
газэта, парамэтр). Нашы пераклады — афіцыйны правапіс, таму варыянт трэба
пераносіць у яго (ня → не, -ньне → -нне, газэта → газета).

Файл — аўтарская праца, у рэпазіторый не кладзецца: local/dicts/antykalka.tsv
(`python -m belloc dicts` спампоўвае яго з antykalka.org).

    python -m belloc antykalka запонка              # артыкулы, што пачынаюцца з «запонка»
    python -m belloc antykalka "а ему" --exact      # толькі дакладнае супадзенне рускага
    python -m belloc antykalka чаканы --reverse     # дзе гэта слова ёсць сярод адпаведнікаў
"""
from __future__ import annotations

import os
import re
import unicodedata

from . import dicts

STRESS = "̀́"


def plain(s: str) -> str:
    """Без націскаў, ніжні рэгістр, ё→е — для пошуку."""
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if c not in STRESS)
    return unicodedata.normalize("NFC", s).replace("ё", "е").replace("’", "'")


def loose(s: str) -> str:
    """Для адваротнага пошуку: зводзіць тарашкевіцу і наркамаўку да аднаго.

    Мяккі знак асіміляцыі (сьнег, зьвер, цьвёрды) прыбіраецца, -ньне → -нне,
    э → е (газэта ≈ газета), «(ь)» і іншыя дужкі раскрываюцца (запін(ь)ка ≈ запінка).
    """
    s = plain(s).replace("(ь)", "").replace("(", " ").replace(")", " ")
    s = re.sub(r"(?<=[сзц])ь(?=[бвгджзклмнпрстфхцчш])", "", s)
    s = re.sub(r"дзь(?=[бвгджзклмнпрстфхцчш])", "дз", s)
    s = re.sub(r"([нлсзц])ь\1", r"\1\1", s)
    return s.replace("э", "е")


def head_key(ru: str) -> str:
    """Загаловак без памет у дужках: «выглядеть (иметь вид)» → «выглядеть»."""
    return plain(re.sub(r"\s*\(.*?\)", "", ru)).strip()


def load(path: str | None = None) -> list[tuple[str, str]]:
    path = path or dicts.path("antykalka.tsv")
    if not os.path.exists(path):
        raise SystemExit(f"няма {path} — спампуйце: python -m belloc dicts antykalka")
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\r\n").split("\t")
            if len(p) >= 2 and p[0].strip() and p[1].strip():
                rows.append((p[0].strip(), p[1].strip()))
    return rows


def search(queries: list[str], exact=False, reverse=False, limit=30, no_stress=False):
    rows = load()
    for q in queries:
        qk = plain(q).strip()
        if reverse:
            word = re.compile(r"(?<![а-яёіўґ'-])" + re.escape(loose(q).strip()) + r"(?![а-яёіўґ'-])")
            hits = [(ru, be) for ru, be in rows if word.search(loose(be))]
        elif exact:
            hits = [(ru, be) for ru, be in rows if head_key(ru) == qk]
        else:
            hits = [(ru, be) for ru, be in rows if head_key(ru).startswith(qk)]
            # спачатку дакладныя, потым даўжэйшыя выразы
            hits.sort(key=lambda h: (head_key(h[0]) != qk, len(h[0])))
        print(f"── {q}: {len(hits)}" + (f" (паказана {limit})" if len(hits) > limit else ""))
        for ru, be in hits[:limit]:
            if no_stress:
                be = "".join(c for c in unicodedata.normalize("NFD", be) if c not in STRESS)
                be = unicodedata.normalize("NFC", be)
            print(f"   {ru:38} → {be}")


# ---------------------------------------------------------------- устойлівыя выразы

# памета ў дужках → выраз — тэрмін, а не ідыёма; такія не шукаем
TERM_LABELS = re.compile(r"\((?:бот|зоол|мат|тех|техн|хим|физ|анат|мед|муз|опт|геол|"
                         r"астр|биол|грам|лингв|юр|эк|воен|мор|ж\.-д|спец|ист|полигр|"
                         r"архит|горн|с\.-х|рел|церк|фин|торг|стр|радио|эл|элек)\.?\)")
# памета, што выраз вобразны/гутарковы — такія ставім вышэй
IDIOM_LABELS = re.compile(r"\((?:перен|разг|прост|погов|посл|идиом|фам|шутл|ирон|бран|груб)\.?")
STOP = set("а и в во на не ни с со к ко у о об от до по за из изо без для что как же ли бы "
           "то это он она оно они мы вы ты я его ее её их мне меня тебе тебя себе так все всё "
           "но да или уж вот там тут где".split())
WILD = re.compile(r"^(?:кого|кому|кем|чего|чему|чем|что|кто|какой|где|куда)-л(?:ибо)?\.?$|^\.\.\.$")
WORD = re.compile(r"[а-яё]+(?:-[а-яё]+)*")


def _ru(s: str) -> str:
    return s.lower().replace("ё", "е")


def _base(w: str) -> str:
    return w[:-2] if len(w) > 5 and w[-2:] in ("ся", "сь") else w


def word_match(p: str, t: str) -> bool:
    """Слова выразу і тэксту — адно слова з улікам склону/спражэння (груба)."""
    a, b = _base(p), _base(t)
    if p in STOP or len(a) <= 4 or len(b) <= 4:
        return a == b
    if abs(len(a) - len(b)) > 3:
        return False
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n >= max(4, min(len(a), len(b)) - 2)


def phrases(rows) -> dict[str, list]:
    """{першыя 3 літары першага слова: [(токены, загаловак, адпаведнікі, ідыёма?)]}"""
    index: dict[str, list] = {}
    for ru, be in rows:
        if TERM_LABELS.search(ru):
            continue
        idiom = bool(IDIOM_LABELS.search(ru))
        base = re.sub(r"\s*\(.*?\)", "", ru)
        for variant in base.split("/") if "/" in base and " " not in base else [base]:
            toks = [_ru(t) for t in re.findall(r"[а-яёА-ЯЁ]+(?:-[а-яёА-ЯЁ]+)*(?:-л\.)?|\.\.\.", variant)]
            if len(toks) < 2:
                continue
            content = [t for t in toks if t not in STOP and not WILD.match(t)]
            fixed = [t for t in toks if not WILD.match(t)]
            exclaim = variant.rstrip().endswith(("!", "?", "…"))
            # хаця б два «сапраўдныя» словы, або памета ідыёмы, або выклічнік
            if len(fixed) < 2 or not content or max(len(t) for t in content) < 4:
                continue
            if len(content) < 2 and not (idiom or exclaim):
                continue
            first = next(t for t in toks if not WILD.match(t))
            key = first if first in STOP else first[:3]
            index.setdefault(key, []).append((toks, ru, be, idiom))
    return index


def find(text: str, index) -> list[tuple[int, int, str, str, bool]]:
    """(пачатак, канец у словах, загаловак, адпаведнікі, ідыёма?) — найдаўжэйшыя."""
    words = [_ru(w) for w in WORD.findall(_ru(text))]
    hits = []
    for i, w in enumerate(words):
        for key in {w if w in STOP else w[:3]}:
            for toks, ru, be, idiom in index.get(key, ()):
                j, k, ok = i, 0, True
                for t in toks:
                    if WILD.match(t):
                        j += 1          # «кого-л.» — адно любое слова
                        continue
                    # дапускаем адно ўстаўное слова паміж словамі выразу
                    if j < len(words) and word_match(t, words[j]):
                        j += 1
                    elif k == 0 and j + 1 < len(words) and t != toks[0] and word_match(t, words[j + 1]):
                        j += 2
                        k = 1
                    else:
                        ok = False
                        break
                if ok:
                    hits.append((i, j, ru, be, idiom))
    # унутры большага супадзення меншае не паказваем
    hits.sort(key=lambda h: (h[0], -(h[1] - h[0])))
    out = []
    for h in hits:
        if any(o[0] <= h[0] and h[1] <= o[1] and (o[1] - o[0]) > (h[1] - h[0]) for o in out):
            continue
        if any(o[0] == h[0] and o[1] == h[1] and o[2] == h[2] for o in out):
            continue
        out.append(h)
    return out


def _options(be: str) -> list[list[str]]:
    """Варыянты адпаведніка → спісы асноў значных слоў (для «ужо ўлічана?»)."""
    out = []
    for opt in re.split(r"[;,]", re.sub(r"\(.*?\)", " ", be)):
        stems = [w[:max(4, len(w) - 2)] for w in re.findall(r"[а-яёіўґ'-]+", loose(opt)) if len(w) >= 3]
        if stems:
            out.append(stems)
    return out


def covered(bel: str, be: str) -> bool:
    """Ці ўжыты ў нашым перакладзе хоць адзін варыянт слоўніка."""
    text = loose(bel)
    return any(all(s in text for s in stems) for stems in _options(be))


def idioms_report(loc, out_md: str, only_idioms=False) -> int:
    """Пошук выразаў «Антыкалькі» ў слупку hint_lang (рускім) → даклад для вычыткі."""
    from . import tables
    index = phrases(load())
    lines, n_rows, n_hits, n_found, n_ok = [], 0, 0, 0, 0
    for table, rows in tables.load_all(loc).items():
        for r in rows:
            ru = r.get(loc.hint_lang or "", "")
            if not ru:
                continue
            hits = [h for h in find(ru, index) if h[4] or not only_idioms]
            n_found += len(hits)
            if r["bel"]:
                # варыянт слоўніка ўжо ў перакладзе — праверка не патрэбна
                ok = [h for h in hits if covered(r["bel"], h[3])]
                n_ok += len(ok)
                hits = [h for h in hits if h not in ok]
            if not hits:
                continue
            n_rows += 1
            n_hits += len(hits)
            words = WORD.findall(_ru(ru))
            lines.append(f"### {table} / `{r['key']}`\n")
            lines.append(f"- EN: {r[loc.source_lang]!r}")
            lines.append(f"- RU: {ru!r}")
            lines.append(f"- **BEL: {r['bel']!r}**" if r["bel"] else "- BEL: — (яшчэ не перакладзена)")
            for i, j, head, be, idiom in hits:
                frag = " ".join(words[i:j])
                be_plain = unicodedata.normalize(
                    "NFC", "".join(c for c in unicodedata.normalize("NFD", be) if c not in STRESS))
                lines.append(f"  - {'★ ' if idiom else ''}«{frag}» ≈ *{head}* → {be_plain}")
            lines.append("")
    head = [f"# Устойлівыя выразы з «Антыкалькі» ў рускім перакладзе — {loc.name}\n",
            f"Знойдзена выразаў: {n_found}; з іх {n_ok} ужо перакладзеныя адным з варыянтаў "
            f"слоўніка і не паказваюцца. Да праверкі — радкоў: {n_rows}, выразаў: {n_hits}. "
            "★ — у слоўніку з паметай "
            "(перан., разм., прост.…), хутчэй за ўсё ідыёма.\n",
            "Пошук па аснове слова, груба: частка супадзенняў — звычайныя спалучэнні. "
            "Задача — праверыць, ці не перадалі мы ідыёму даслоўна. Варыянты слоўніка — "
            "у тарашкевіцы, пераносіць у правапіс перакладу.\n"]
    os.makedirs(os.path.dirname(os.path.abspath(out_md)), exist_ok=True)
    with open(out_md, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(head + lines))
    print(f"знойдзена {n_found}, ужо як у слоўніку {n_ok}; да праверкі: радкоў {n_rows}, "
          f"выразаў {n_hits} → {out_md}")
    return 0
