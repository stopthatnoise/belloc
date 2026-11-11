#!/usr/bin/env python3
"""Лінтэр беларускіх перакладаў.

Моўныя праверкі (працуюць на любым беларускім тэксце):
  spell     — невядомыя слоўніку словы з малой літары (патрабуе --dict)
  names     — тое самае, але словы з вялікай літары: уласныя назвы, якіх
              слоўнік не ведае паводле азначэння (--skip names, калі не трэба)
  ruwords   — словы, якія ёсць у рускім слоўніку, але не ў беларускім (патрабуе --ru-dict)
  ruletters — рускія літары (и, щ, ъ)
  rusuffix  — рускія канчаткі (-ть, -тся, -ться)
  ushort    — кандыдаты на памылкі у/ў на стыку слоў
  latin     — лацінскія словы ў перакладзе

Білінгвальныя праверкі (патрабуюць пары арыгінал → пераклад):
  tags         — разыходжанне тэгаў (<b>, <color=...>) паміж арыгіналам і перакладам
  placeholders — разыходжанне плэйсхолдэраў ({0}, %s); фарматары Smart Strings
                 Unity ({0:plural:…}, {0:choose(…):…}) — формы перакладу, не лічацца
  ws           — вядучыя/хвастовыя прабелы не супадаюць з арыгіналам
  endpunct     — канчатковая пунктуацыя не супадае з арыгіналам
  lenratio     — падазроныя суадносіны даўжыні пераклад/арыгінал
  dupes        — аднолькавы арыгінал перакладзены па-рознаму
  untranslated — пераклад супадае з арыгіналам або пусты (іншамоўныя рэплікі,
                 дзе няма ніводнага ангельскага службовага слова, прапускаюцца:
                 «Ah. Bon.» так і мусіць застацца)
  glossary     — тэрмін з гласарыя не знойдзены ў перакладзе (патрабуе --glossary;
                 з --ink-prefix глядзіць толькі на цела радка, бо ва ўмовах
                 флагаў уласныя назвы наўмысна застаюцца англійскімі;
                 поле "alt" у гласарыі дадае іншыя законныя перадачы тэрміна)
  prefix       — службовая ink-умова ў пачатку радка зменена (патрабуе --ink-prefix)

--paradox (CK3 і іншыя гульні Paradox): placeholders параўноўвае разметку
  [Scope.Func('ключ', 'тэкст')|E], $KEY$, #T … #!, @icon!, \n — у [...]
  першы аргумент у двукоссі (ключ) мусіць супадаць, астатнія (бачны тэкст) — не;
  слоўныя праверкі глядзяць толькі на бачны тэкст.

--marks CHARS: службовыя знакі, колькасць якіх мусіць супадаць з арыгіналам
  (праверка placeholders; Dispatch: «|^» — разрыў субцітра і вылучэнне).

--tag-re REGEX: што лічыць тэгам замест <…> (Pony Island: <START GAME> і
  <None> — бачны тэкст, тэгі — толькі <color=…>, <b> і пад.).

Фарматы ўваходу:
  --pairs FILE...  JSON {"strings": {арыгінал: пераклад}} або {арыгінал: пераклад}
  --mono FILE...   той жа JSON, але ключы — гэта ID: правяраюцца толькі значэнні
  --text FILE...   звычайны тэкст, правяраецца цалкам (толькі моўныя праверкі)

Прыклад:
  python -m belloc.lint --pairs local/<гульня>/build/pairs.json \
      --dict local/dicts/be_BY --ru-dict local/dicts/ru_RU --wordlist local/dicts/slovy.txt \
      --glossary games/<гульня>/glossary.json --allow games/<гульня>/lint_allow.txt --report lint_report.md
"""

from __future__ import annotations

import argparse
import gzip
import shutil
import json
import re
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass

CYR_VOWELS = "аеёіоуыэюя"
CYR_VOWELS_ALL = CYR_VOWELS + CYR_VOWELS.upper()
TAG_RE = re.compile(r"<[^<>]+>")
PLACEHOLDER_RE = re.compile(r"\{[^{}]*\}|%[sdif]")
CYR_WORD_RE = re.compile(r"[А-Яа-яЁёІіЎў][А-Яа-яЁёІіЎў'’-]*")
# лацінскае слова разам з дыякрытыкай: без яе «Dâr» распадалася б
# на «D» і «r» і давала два ілжэспрацоўванні замест аднаго слова
LAT_WORD_RE = re.compile(r"[A-Za-zÀ-ɏ][A-Za-zÀ-ɏ'-]*")
RU_LETTERS_RE = re.compile(r"[иИщЩъЪ]")
RU_SUFFIX_RE = re.compile(r"[А-Яа-яЁёІіЎў]+(?:ть|тся|ться)\b")

MONO_CHECKS = ["spell", "names", "ruwords", "ruletters", "rusuffix", "ushort", "latin"]
BI_CHECKS = ["tags", "placeholders", "ws", "endpunct", "lenratio", "dupes",
             "untranslated", "glossary", "prefix"]
ALL_CHECKS = MONO_CHECKS + BI_CHECKS


@dataclass
class Segment:
    file: str
    key: str          # ключ у JSON або нумар радка ў тэксце
    src: str | None   # арыгінал (None для монамоўных крыніц)
    dst: str          # беларускі тэкст
    dst_body: str = None  # dst без службовага прэфікса — для слоўных праверак
    src_body: str = None  # тое самае для арыгінала — для праверкі glossary

    def __post_init__(self):
        if self.dst_body is None:
            self.dst_body = self.dst
        if self.src_body is None:
            self.src_body = self.src


# службовы прэфікс ink-радка: умовы флагаў / кідкоў, якія не перакладаюцца
# (.QP3_Folio==1-, DC10 cha-, ROLL1 wis-, .LEVEL<=3-, .Simii's_Hole_Seen==1-).
# Дэфіс ідзе ўшчыльную да ўмовы: «DC10 - ТЭКСТ» з прабелам — гэта ўжо тэкст.
_COND = (r"(?:\.[A-Za-z_][\w.'’]*(?:\s*[=<>!]=?\s*-?[\w.]+)?"
         r"|[A-Z]{2,4}\d+(?:\s+\w+)?)")
INK_PREFIX_RE = re.compile(rf"^{_COND}(?:\s*[&|]{{1,2}}\s*{_COND})*-")

# службовыя токены ў сярэдзіне і ў канцы ink-радка: усталёўка флагаў
# (.NATIONALIST+=1), умовы (.CB_RatGiven==0) і каманды рухавіка
# (PCTrigger Squatting, AddItem Speak_with_Dead, FadeToClear, ADV).
# Флаг з нагрузкай (.SnurreInfo-Інфармацыя_Снурэ) абразаецца да дэфіса:
# нагрузка — гэта тэкст, які перакладаецца і мусіць правярацца.
#
# Ідэнтыфікатары ў радках-апавяшчэннях («Unlock QP6_Ebb» → «Разблакаваць
# QP6_Эб») перакладзены наўмысна — гульня іх не разбірае, гэтак жа робіць
# і рускі мод. Таму правіла ідэнтыфікатара прымае і кірыліцу: такі радок
# не мусіць даваць ніводнай знаходкі. Умовы ў пачатку радка — іншая справа,
# іх правярае check_prefix.
INK_TOKEN_RE = re.compile(r"""
    \.[A-Za-z_][\w.'’]*(?:\s*[-+]?[=<>!]=?\s*-?[\w.]+)?  # .Flag, .Flag+=1, .Flag==0
  | \b[A-Za-z][A-Za-z0-9]*_[\w'’]+                       # QP1_Man, QP6_Эб (гл. ніжэй)
  | (?:\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]*)+               # AddItem, FadeToClear
      |\b[A-Z]{2,}[a-z0-9]+\w*                           # PCTrigger, ASIncrease
      |\b[A-Z]{2,}\d*\b                                  # ADV, DIS, SPELL, VOTE
      |\bUnlock(?:ing)?\b)                               # Unlock QP1_Man
    (?:\s+[A-Za-z0-9_'’]+)?                              # аргумент каманды: PCTrigger Praying
  | \b[A-Z]\b                                            # адзіночныя маркеры: Q, R
  | \b\d*[dD]\d+\b                                       # кубікі: 1d6, d20
  | :[A-Za-z]\.?$                                        # хвастовы маркер «:y.»
""", re.X | re.M)


# Paradox (CK3): [Scope.Func(..)|E] — код, акрамя радкоў у '…', што не
# першы аргумент (Concept('key', 'бачны тэкст'), Select_CString(c, 'а', 'б'))
PDX_BRACKET_RE = re.compile(r"\[[^\[\]]*\]")
PDX_QUOTED_RE = re.compile(r"(\(\s*)?'([^']*)'")
PDX_TOKEN_RE = re.compile(r"\$[^$\s]+\$|@[\w-]+!|#[A-Za-z_]+\b|#!|\\n")
PARADOX = False


PDX_CONCEPT_RE = re.compile(r"Concept\(\s*'([^']*)'\s*,\s*'[^']*'\s*\)")
PDX_MOD_RE = re.compile(r"\|[A-Za-z0-9=+%-]*(?=\])")


def pdx_skeleton(block: str) -> str:
    """[..] без бачнага тэксту і без таго, што пераклад мяняе законна:
    [liege|E] ≡ [Concept('liege', 'сюзерэну')|E] (склон паняцця),
    мадыфікатары |E |U |l (рэгістр), прабелы."""
    block = PDX_CONCEPT_RE.sub(r"\1", block)
    block = PDX_QUOTED_RE.sub(lambda m: m.group(0) if m.group(1) else "''", block)
    return PDX_MOD_RE.sub("", re.sub(r"\s+", "", block))


def pdx_tokens(text: str) -> list[str]:
    return ([pdx_skeleton(b) for b in PDX_BRACKET_RE.findall(text)]
            + PDX_TOKEN_RE.findall(PDX_BRACKET_RE.sub(" ", text)))


def pdx_body(text: str) -> str:
    def visible(m):
        return " ".join(q.group(2) for q in PDX_QUOTED_RE.finditer(m.group(0)) if not q.group(1))
    return PDX_TOKEN_RE.sub(" ", PDX_BRACKET_RE.sub(lambda m: f" {visible(m)} ", text))


@dataclass
class Finding:
    check: str
    file: str
    key: str
    msg: str


def clean_markup(text: str) -> str:
    return PLACEHOLDER_RE.sub(" ", TAG_RE.sub(" ", text))


def excerpt(s: str, limit: int = 70) -> str:
    s = s.replace("\n", "⏎")
    return s if len(s) <= limit else s[: limit - 1] + "…"


# ---------------------------------------------------------------- уваход

def load_kv_json(path: str, mono: bool) -> list[Segment]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    strings = data.get("strings", data) if isinstance(data, dict) else data
    if not isinstance(strings, dict):
        sys.exit(f"{path}: чакаўся JSON-аб'ект з парамі ключ→значэнне")
    segs = []
    for k, v in strings.items():
        if not isinstance(v, str):
            continue
        segs.append(Segment(path, k, None if mono else k, v))
    return segs


def load_text(path: str) -> list[Segment]:
    segs = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if line.strip():
                segs.append(Segment(path, f"радок {i}", None, line.rstrip("\n")))
    return segs


# ---------------------------------------------------------------- hunspell

_SPYLLS: dict[str, object] = {}


def hunspell_unknown(words: set[str], dict_path: str) -> set[str]:
    """Вяртае словы, якіх няма ў слоўніку.

    Праграма hunspell, калі яна ёсць у PATH (Linux), інакш — spylls, порт
    hunspell на чыстым Python (Windows, ставіцца ў .venv з requirements.txt).
    """
    if not words:
        return set()
    if not shutil.which("hunspell"):
        try:
            from spylls.hunspell import Dictionary
        except ImportError:
            sys.exit("няма ні hunspell у PATH, ні spylls (pip install spylls)")
        if dict_path not in _SPYLLS:
            _SPYLLS[dict_path] = Dictionary.from_files(dict_path)
        d = _SPYLLS[dict_path]
        return {w for w in words if not d.lookup(w)}
    proc = subprocess.run(
        ["hunspell", "-l", "-d", dict_path, "-i", "UTF-8"],
        input="\n".join(sorted(words)), capture_output=True, text=True)
    if proc.returncode not in (0, 1):
        sys.exit(f"hunspell -d {dict_path}: {proc.stderr.strip()}")
    return set(proc.stdout.split())


def load_wordlist(path: str) -> set[str]:
    """Дадатковы спіс вядомых словаў: адна форма на радок (можна .gz)."""
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        return {w.strip().lower().replace("’", "'") for w in f if w.strip()}


def wordlist_knows(word: str, wordlist: set[str]) -> bool:
    """Ці ёсць слова ў спісе — з ростанню на дзве законныя разыходнасці.

    ў → у: гэта пазіцыйны варыянт адной літары, а правільнасць пазіцыі
    правярае асобная праверка ushort, дубляваць яе тут няма сэнсу.
    -аў/-яў: родны склон множнага ліку клясычнага правапісу (мэтаў,
    жыццяў), якога няма ў наркамаўскіх парадыгмах GrammarDB.
    """
    w = word.lower()
    cands = {w, w.replace("ў", "у")}
    for c in list(cands):
        if c.endswith("аў"):
            cands.add(c[:-2] + "а")
        elif c.endswith("яў"):
            cands |= {c[:-2] + "я", c[:-2] + "ё"}
    return any(c in wordlist for c in cands)


class Allowlist:
    def __init__(self):
        self.exact: set[str] = set()
        self.prefixes: set[str] = set()

    def load_file(self, path: str):
        with open(path, encoding="utf-8") as f:
            for line in f:
                w = line.strip().lower().replace("’", "'")
                if not w or w.startswith("#"):
                    continue
                if w.endswith("*"):
                    self.prefixes.add(w[:-1])
                else:
                    self.exact.add(w)

    def add_glossary_stem(self, word: str):
        stem = word.lower().replace("’", "'").rstrip(CYR_VOWELS + "ьй")
        if len(stem) >= 3:
            self.prefixes.add(stem)

    def allows(self, word: str) -> bool:
        w = word.lower().replace("’", "'")
        if w in self.exact:
            return True
        return any(w.startswith(p) for p in self.prefixes)


# ---------------------------------------------------------------- моўныя праверкі

def check_spell_and_ruwords(segs, be_dict, ru_dict, allow, enabled, wordlist=()):
    """Адзін праход hunspell на ўнікальных словах для spell, names і ruwords."""
    word_locs: dict[str, list[Segment]] = defaultdict(list)
    parts: dict[str, set[str]] = defaultdict(set)  # частка дэфіснага слова → цэлыя словы
    for seg in segs:
        for w in set(CYR_WORD_RE.findall(clean_markup(seg.dst_body))):
            w = w.replace("’", "'").strip("'-")
            if w:
                word_locs[w].append(seg)
    for w in word_locs:
        for part in w.split("-"):
            if part and part != w:
                parts[part].add(w)

    unknown = hunspell_unknown(set(word_locs), be_dict)
    # hunspell разбівае дэфісныя словы (BREAK -) і вяртае іх часткі —
    # прыпісваем такія часткі назад цэлым словам
    for w in list(unknown):
        if w not in word_locs:
            unknown.discard(w)
            unknown.update(parts.get(w, ()))
    unknown = {w for w in unknown if not allow.allows(w)}
    if wordlist:
        unknown = {w for w in unknown if not wordlist_knows(w, wordlist)}

    russian = set()
    if "ruwords" in enabled and ru_dict:
        known_ru = set(unknown) - hunspell_unknown(unknown, ru_dict)
        russian = {w for w in known_ru if not RU_LETTERS_RE.search(w)}

    findings = []
    def emit(check, words):
        # зліваем варыянты рэгістру («АЛЕЕНАЎ»/«Алеенаў») у адзін запіс
        merged: dict[str, list[str]] = defaultdict(list)
        for w in words:
            # кароткае слова, якое сустракаецца ТОЛЬКІ капсам, — гэта
            # абрэвіятура (КС, ПЭ, ГБШ), а не памылка правапісу
            if len(w) <= 4 and w.isupper() \
                    and all(v.isupper() for v in merged_variants[w.lower()]):
                continue
            merged[w.lower()].append(w)
        def freq(lw):
            return sum(len(word_locs[v]) for v in merged[lw])
        for lw in sorted(merged, key=lambda x: (-freq(x), x)):
            variants = sorted(merged[lw], key=lambda v: -len(word_locs[v]))
            ex = word_locs[variants[0]][0]
            findings.append(Finding(
                check, ex.file, ex.key,
                f"«{'/'.join(variants)}» ×{freq(lw)} — {excerpt(ex.dst)}"))

    def looks_like_name(lw):
        """Слова з вялікай літары, якое ніводнага разу не бачылі з малой.

        Крык капсам («ПОГЛЯДЗІ») не лічыцца: уласная назва мусіць мець
        хоць адно звычайнае напісанне з вялікай літары.
        """
        variants = merged_variants[lw]
        return (any(v[:1].isupper() and not v.isupper() for v in variants)
                and not any(v[:1].islower() for v in variants))

    merged_variants: dict[str, list[str]] = defaultdict(list)
    for w in unknown:
        merged_variants[w.lower()].append(w)

    if "ruwords" in enabled:
        emit("ruwords", russian)
    rest = unknown - russian
    names = {w for w in rest if looks_like_name(w.lower())}
    if "spell" in enabled:
        emit("spell", rest - names)
    if "names" in enabled:
        emit("names", names)
    return findings


def check_ruletters(seg):
    m = RU_LETTERS_RE.search(seg.dst_body)
    if m:
        yield f"літара «{m.group()}» — {excerpt(seg.dst_body[max(0, m.start()-25):m.start()+25])}"


def check_rusuffix(seg, allow):
    for m in RU_SUFFIX_RE.finditer(clean_markup(seg.dst_body)):
        if not allow.allows(m.group()):
            yield f"«{m.group()}» — {excerpt(seg.dst)}"


def check_ushort(seg):
    text = clean_markup(seg.dst_body)
    # «у» пасля слова на галосную (праз прабелы, без знакаў прыпынку) → мусіць быць «ў»
    for m in re.finditer(r"[" + CYR_VOWELS_ALL + r"]\s+(у[а-яёіў'’-]*)\b", text):
        yield f"галосная + «{m.group(1)}» (можа, «ў»?) — {excerpt(text[max(0,m.start()-25):m.end()+15])}"
    # «ў» у пачатку слова не пасля галоснай → мусіць быць «у»
    for m in re.finditer(r"(?<![А-Яа-яЁёІіЎў'’-])[ўЎ][а-яёіў'’-]*", text):
        k = m.start() - 1
        while k >= 0 and text[k].isspace():
            k -= 1
        if k < 0 or text[k] not in CYR_VOWELS_ALL:
            yield f"«{m.group()}» не пасля галоснай (можа, «у»?) — {excerpt(text[max(0,m.start()-25):m.end()+15])}"


def check_latin(segs, allow):
    word_locs: dict[str, list[Segment]] = defaultdict(list)
    for seg in segs:
        # радкі, пакінутыя як ёсць (іншамоўныя рэплікі, назвы), — гэта
        # клопат праверкі untranslated, тут яны далі б сотні дублікатаў
        if seg.src is not None and seg.dst.strip() == seg.src.strip():
            continue
        for w in set(LAT_WORD_RE.findall(clean_markup(seg.dst_body))):
            word_locs[w].append(seg)
    findings = []
    for w in sorted(word_locs, key=lambda w: (-len(word_locs[w]), w)):
        if allow.allows(w):
            continue
        locs = word_locs[w]
        findings.append(Finding("latin", locs[0].file, locs[0].key,
                                f"«{w}» ×{len(locs)} — {excerpt(locs[0].dst)}"))
    return findings


# ---------------------------------------------------------------- білінгвальныя праверкі

def check_tags(seg):
    src_tags = Counter(TAG_RE.findall(seg.src))
    dst_tags = Counter(TAG_RE.findall(seg.dst))
    if src_tags != dst_tags:
        missing = list((src_tags - dst_tags).elements())
        extra = list((dst_tags - src_tags).elements())
        parts = []
        if missing:
            parts.append("няма: " + " ".join(missing[:5]))
        if extra:
            parts.append("лішнія: " + " ".join(extra[:5]))
        yield "; ".join(parts)


# Unity {ManualInput:ClimbUp/Display:Up}: подпіс пасля Display: бачыць гулец,
# яго перакладаюць (так зроблена і ў афіцыйным RU) — параўноўваем без яго
DISPLAY_RE = re.compile(r"/Display:[^{}]*(?=\})")
# Smart Strings: {0:plural:крэдыт|крэдыты|крэдытаў} — словы пад лік, сам лік — асобны {0}
SMART_RE = re.compile(r"^\{\w+:(?:plural|choose\([^()]*\)):")
MARKS = ""


def check_placeholders(seg):
    if PARADOX:
        src_ph, dst_ph = Counter(pdx_tokens(seg.src)), Counter(pdx_tokens(seg.dst))
        missing = sorted((src_ph - dst_ph).elements())
        # Select_CString пераклад дадае сам — дзеля роду/склону; не памылка
        extra = [t for t in sorted((dst_ph - src_ph).elements())
                 if not t.startswith("[Select_C")]
        if missing or extra:
            yield f"няма: {missing} | лішняе: {extra}"
        return
    src_ph = Counter(DISPLAY_RE.sub("", p) for p in PLACEHOLDER_RE.findall(seg.src)
                     if not SMART_RE.match(p))
    dst_ph = Counter(DISPLAY_RE.sub("", p) for p in PLACEHOLDER_RE.findall(seg.dst)
                     if not SMART_RE.match(p))
    if src_ph != dst_ph:
        yield (f"арыгінал: {sorted(src_ph.elements())} ≠ "
               f"пераклад: {sorted(dst_ph.elements())}")
    for c in MARKS:
        if seg.src.count(c) != seg.dst.count(c):
            yield f"«{c}»: арыгінал {seg.src.count(c)}, пераклад {seg.dst.count(c)}"


def ws_signature(s: str) -> tuple[str, str]:
    stripped = s.strip()
    if not stripped:
        return ("", "")
    i = s.index(stripped[0])
    return (s[:i], s[i + len(stripped):])


def check_ws(seg):
    src_lead, src_trail = ws_signature(seg.src)
    dst_lead, dst_trail = ws_signature(seg.dst)
    if (src_lead, src_trail) != (dst_lead, dst_trail):
        yield (f"прабелы: арыгінал {src_lead!r}…{src_trail!r}, "
               f"пераклад {dst_lead!r}…{dst_trail!r}")


END_PUNCT_RE = re.compile(r"[.!?…:;,]+$")

def end_punct(s: str) -> str:
    s = TAG_RE.sub("", s).strip().rstrip("«»\"'”“)]")
    s = s.replace("...", "…")
    m = END_PUNCT_RE.search(s)
    return m.group() if m else ""


def check_endpunct(seg):
    sp, dp = end_punct(seg.src), end_punct(seg.dst)
    if sp != dp:
        yield f"{sp or '∅'} → {dp or '∅'} — {excerpt(seg.dst)}"


def check_lenratio(seg):
    src_len = len(clean_markup(seg.src).strip())
    dst_len = len(clean_markup(seg.dst).strip())
    if src_len >= 25 and dst_len:
        ratio = dst_len / src_len
        if ratio < 0.4 or ratio > 2.5:
            yield f"×{ratio:.2f} ({src_len}→{dst_len}) — {excerpt(seg.dst)}"


# скарачэнне стата пасля DC11/ROLL15 дазволена перакладаць (int → інт):
# так робіць і арыгінальны русіфікатар, гульня гэта пераварвае
STAT_WORD_RE = re.compile(r"([A-Z]{2,4}\d+)\s+\w+")


def check_prefix(seg):
    """Службовы ink-прэфікс (умовы флагаў) мусіць застацца без зменаў."""
    m = INK_PREFIX_RE.match(seg.src)
    if not m:
        return
    dm = INK_PREFIX_RE.match(seg.dst)
    src_norm = STAT_WORD_RE.sub(r"\1", m.group())
    dst_norm = STAT_WORD_RE.sub(r"\1", dm.group()) if dm else None
    if src_norm != dst_norm:
        got = dm.group() if dm else excerpt(seg.dst, 40)
        yield f"умова зменена: {m.group()!r} → {got!r}"


# службовыя словы, без якіх ангельскага сказа практычна не бывае: іх
# адсутнасць азначае, што радок і ў арыгінале не ангельскі («Ah. Bon.»,
# «Quis es tu?») і мусіць застацца як ёсць
ENGLISH_FUNC = set("""a an the and or but if is are was were be been am do does did
have has had can could will would shall should may might must not no of to in on at
by for with from into about over you your yours i me my mine we our us he him his
she her hers it its they them their this that these those what who whom which when
where why how all any some more most just like get got go going gone know think
want need let make made take took see saw come came say said tell told there here
""".split())


def check_untranslated(seg):
    if not seg.dst.strip():
        yield "пусты пераклад"
    # у радку без цела перакладаць няма чаго: «SPELL Speak_with_Dead-» —
    # гэта адны службовыя токены (гл. INK_TOKEN_RE)
    elif seg.dst.strip() == seg.src.strip() and CYR_WORD_RE.search(seg.src) is None \
            and LAT_WORD_RE.search(clean_markup(seg.src_body or "")) \
            and LAT_WORD_RE.search(clean_markup(seg.src)):
        words = {w.lower() for w in LAT_WORD_RE.findall(clean_markup(seg.src))}
        if words & ENGLISH_FUNC:
            yield f"пераклад ідэнтычны арыгіналу — {excerpt(seg.dst)}"


def check_dupes(segs):
    groups: dict[str, dict[str, Segment]] = defaultdict(dict)
    for seg in segs:
        if seg.src is None:
            continue
        norm = " ".join(seg.src.split())
        groups[norm].setdefault(seg.dst.strip(), seg)
    findings = []
    for norm, variants in groups.items():
        if len(variants) > 1:
            ex = next(iter(variants.values()))
            vlist = " ⇄ ".join(f"«{excerpt(v, 50)}»" for v in list(variants)[:4])
            findings.append(Finding("dupes", ex.file, ex.key,
                                    f"«{excerpt(norm, 50)}»: {vlist}"))
    return findings


def load_glossary(path: str) -> tuple[list[tuple[str, str]], list[str]]:
    """Вяртае (тэрміны для праверкі glossary, усе беларускія значэнні).

    Правяраюцца толькі адназначныя ўласныя назвы, а вось у белы спіс
    арфаграфіі ідуць значэнні ўсіх артыкулаў: калі слова ёсць у гласарыі,
    яно не памылка, незалежна ад рэгістру англійскага ключа.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    terms, all_bel = [], []
    for cat, entries in data.items():
        if cat.startswith("_") or not isinstance(entries, dict):
            continue
        for en, info in entries.items():
            bel = info.get("bel") if isinstance(info, dict) else info
            if not isinstance(bel, str) or not bel:
                continue
            all_bel.append(bel)
            # «alt» — іншыя законныя перадачы тэрміна (Coast War →
            # Берагавая вайна): іх асновы таксама лічацца за трапленне
            alt = info.get("alt", []) if isinstance(info, dict) else []
            all_bel += alt
            # крыжаваныя спасылкі («гл. …»), агульныя словы (з малой літары)
            # і запісы з некалькімі варыянтамі перакладу не правяраюцца
            if not en[:1].isupper() or bel.startswith("гл.") or "1)" in bel:
                continue
            terms.append((en, bel, alt))
    return terms, all_bel


def strip_stress(s: str) -> str:
    """Здымае знак націску, не чапаючы й/ў/ё.

    Поўны NFD раскладаў бы і іх (й → и + брэве, ё → е + дыярэзіс), таму
    прыбіраем толькі камбінавальныя акут і гравіс.
    """
    return unicodedata.normalize("NFC", s.replace("́", "").replace("̀", ""))


def fold(s: str) -> str:
    """Форма для пошуку асновы ў тэксце: без націску і з ў → у.

    «ў» — пазіцыйны варыянт «у» (Узбярэжжа → на Ўзбярэжжы), таму пры
    супастаўленні асноў літары трэба лічыць за адну.
    """
    return strip_stress(s).replace("ў", "у").replace("Ў", "У")


def glossary_stem(word: str) -> str:
    """Аснова для пошуку ў тэксце — з запасам на чаргаванні зычных.

    Апошняя зычная адкідаецца (азгаліст → азгаліс), бо ў вытворных яна
    чаргуецца: азгалі[сц]кі, Норві[ч]ак. Кароткія словы застаюцца цэлымі.
    """
    stem = word.rstrip(CYR_VOWELS + CYR_VOWELS.upper() + "ьй")
    if len(stem) < 3:
        return word.lower()
    return (stem[:-1] if len(stem) > 5 else stem).lower()


def compile_glossary(terms):
    compiled = []
    for en, bel, alt in terms:
        en_re = re.compile(r"\b" + re.escape(en) + r"\b")
        stems = [glossary_stem(w)
                 for variant in [bel, *alt]
                 for w in CYR_WORD_RE.findall(fold(variant))]
        compiled.append((en, bel, en_re, stems))
    return compiled


def check_glossary(seg, compiled):
    # радок, наўмысна пакінуты па-ангельску, — гэта знаходка untranslated,
    # а не разыходжанне з гласарыем
    if seg.dst.strip() == seg.src.strip():
        return
    # службовыя ink-умовы (.Snell==0-) змяшчаюць уласныя назвы, якія
    # наўмысна НЕ перакладаюцца — правяраем толькі цела радка
    dst_low = fold(seg.dst_body).lower()
    for en, bel, en_re, stems in compiled:
        if en_re.search(seg.src_body) and stems and \
                not any(st in dst_low for st in stems):
            yield f"«{en}» → чакаецца «{bel}» — {excerpt(seg.dst)}"


# ---------------------------------------------------------------- запуск

def main():
    ap = argparse.ArgumentParser(
        description="Лінтэр беларускіх перакладаў",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--pairs", nargs="*", default=[], metavar="FILE",
                    help="JSON: ключ = арыгінал, значэнне = пераклад")
    ap.add_argument("--mono", nargs="*", default=[], metavar="FILE",
                    help="JSON: ключ = ID, правяраюцца толькі значэнні")
    ap.add_argument("--text", nargs="*", default=[], metavar="FILE",
                    help="звычайны тэкставы файл")
    ap.add_argument("--dict", dest="be_dict", metavar="PATH",
                    help="шлях да беларускага hunspell-слоўніка (без пашырэння)")
    ap.add_argument("--ru-dict", metavar="PATH",
                    help="шлях да рускага hunspell-слоўніка (для ruwords)")
    ap.add_argument("--wordlist", metavar="FILE",
                    help="дадатковы спіс вядомых беларускіх формаў "
                         "(адна на радок, можна .gz) — да hunspell-слоўніка")
    ap.add_argument("--glossary", action="append", default=[], metavar="FILE",
                    help="гласарый JSON (можна некалькі: публічны і лакальны слой)")
    ap.add_argument("--allow", nargs="*", default=[], metavar="FILE",
                    help="белы спіс словаў (адзін на радок, * у канцы = прэфікс)")
    ap.add_argument("--ink-prefix", action="store_true",
                    help="радкі ink змяшчаюць службовыя токены (.Flag==1-, "
                         "DC10 cha-, PCTrigger Praying, ADV, 1d6): выкідаць іх "
                         "перад слоўнымі праверкамі і праверкай glossary, "
                         "а ўмову ў пачатку радка яшчэ і правяраць (prefix)")
    ap.add_argument("--paradox", action="store_true",
                    help="разметка Paradox (CK3): [..], $..$, #..#!, @..! — "
                         "параўноўваць як плэйсхолдары і не лічыць словамі")
    ap.add_argument("--tag-re", metavar="REGEX",
                    help="рэгулярны выраз тэга (па змаўчанні <[^<>]+>); "
                         "астатняе ў <…> — бачны тэкст")
    ap.add_argument("--marks", default="", metavar="CHARS",
                    help="знакі, колькасць якіх мусіць супадаць з арыгіналам "
                         "(праверка placeholders; Dispatch: «|^»)")
    ap.add_argument("--checks", metavar="LIST",
                    help="запусціць толькі гэтыя праверкі (праз коску)")
    ap.add_argument("--skip", metavar="LIST", default="",
                    help="прапусціць гэтыя праверкі (праз коску)")
    ap.add_argument("--report", metavar="FILE", help="запісаць поўны markdown-даклад")
    ap.add_argument("--max-print", type=int, default=15,
                    help="колькі знаходак кожнай праверкі паказваць у кансолі")
    args = ap.parse_args()

    if not (args.pairs or args.mono or args.text):
        ap.error("трэба хаця б адзін уваходны файл (--pairs / --mono / --text)")

    if args.tag_re:
        global TAG_RE
        TAG_RE = re.compile(args.tag_re)

    global MARKS
    MARKS = args.marks
    enabled = set(args.checks.split(",")) if args.checks else set(ALL_CHECKS)
    enabled -= set(filter(None, args.skip.split(",")))
    if not args.be_dict:
        enabled -= {"spell", "names", "ruwords"}
    if not args.ru_dict:
        enabled -= {"ruwords"}
    if not args.glossary:
        enabled -= {"glossary"}
    if not args.ink_prefix:
        enabled -= {"prefix"}

    segs: list[Segment] = []
    for p in args.pairs:
        segs += load_kv_json(p, mono=False)
    for p in args.mono:
        segs += load_kv_json(p, mono=True)
    for p in args.text:
        segs += load_text(p)
    if args.ink_prefix:
        def strip_service(text: str) -> str:
            return INK_TOKEN_RE.sub(" ", INK_PREFIX_RE.sub("", text, count=1))
        for seg in segs:
            seg.dst_body = strip_service(seg.dst)
            if seg.src is not None:
                seg.src_body = strip_service(seg.src)
    if args.paradox:
        global PARADOX
        PARADOX = True
        for seg in segs:
            seg.dst_body = pdx_body(seg.dst_body)
            if seg.src is not None:
                seg.src_body = pdx_body(seg.src_body)
    bi_segs = [s for s in segs if s.src is not None]

    allow = Allowlist()
    for path in args.allow:
        allow.load_file(path)
    glossary = []
    if args.glossary:
        by_en, all_bel = {}, []
        for path in args.glossary:          # аднолькавы тэрмін у наступным слоі перамагае
            t, b = load_glossary(path)
            by_en.update((term[0], term) for term in t)
            all_bel += b
        glossary = compile_glossary(list(by_en.values()))
        for bel in all_bel:
            # націск разрэзаў бы слова напалам, таму спачатку strip_stress
            for w in CYR_WORD_RE.findall(strip_stress(bel)):
                allow.add_glossary_stem(w)

    findings: list[Finding] = []

    wordlist = load_wordlist(args.wordlist) if args.wordlist else set()

    if enabled & {"spell", "names", "ruwords"}:
        findings += check_spell_and_ruwords(
            segs, args.be_dict, args.ru_dict, allow, enabled, wordlist)
    if "latin" in enabled:
        findings += check_latin(segs, allow)
    if "dupes" in enabled:
        findings += check_dupes(bi_segs)

    per_seg_mono = {"ruletters": check_ruletters,
                    "rusuffix": lambda s: check_rusuffix(s, allow),
                    "ushort": check_ushort}
    per_seg_bi = {"tags": check_tags, "placeholders": check_placeholders,
                  "ws": check_ws, "endpunct": check_endpunct,
                  "lenratio": check_lenratio, "untranslated": check_untranslated,
                  "glossary": lambda s: check_glossary(s, glossary),
                  "prefix": check_prefix}

    for seg in segs:
        for name, fn in per_seg_mono.items():
            if name in enabled:
                for msg in fn(seg):
                    findings.append(Finding(name, seg.file, seg.key, msg))
    for seg in bi_segs:
        for name, fn in per_seg_bi.items():
            if name in enabled:
                for msg in fn(seg):
                    findings.append(Finding(name, seg.file, seg.key, msg))

    # ---- вывад
    by_check: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        by_check[f.check].append(f)

    order = [c for c in ALL_CHECKS if c in by_check]
    print(f"Сегментаў: {len(segs)} ({len(bi_segs)} з арыгіналам). "
          f"Знаходак: {len(findings)}\n")
    for check in order:
        items = by_check[check]
        print(f"── {check}: {len(items)}")
        for f in items[: args.max_print]:
            print(f"   [{f.key[:50]!r}] {f.msg}")
        if len(items) > args.max_print:
            print(f"   … і яшчэ {len(items) - args.max_print} (гл. --report)")
        print()

    if args.report:
        with open(args.report, "w", encoding="utf-8") as out:
            out.write("# Даклад лінтэра\n\n")
            out.write(f"Сегментаў: {len(segs)}. Знаходак: {len(findings)}\n\n")
            for check in order:
                items = by_check[check]
                out.write(f"## {check} ({len(items)})\n\n")
                for f in items:
                    out.write(f"- `{f.file}` `{f.key[:80]!r}`\n  {f.msg}\n")
                out.write("\n")
        print(f"Поўны даклад: {args.report}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
