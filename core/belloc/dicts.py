"""Слоўнікі для лінтэра і «Антыкалькі» — адзін набор на ўсе гульні, у local/dicts/.

У рэпазіторый слоўнікі не кладуцца: кожны спампоўвае іх з першакрыніц сам.

  be_BY.{aff,dic}   hunspell беларускі (github.com/375gnu/hunspell-be), ~83 тыс. асноў —
                    праверкі spell і names
  ru_RU.{aff,dic}   hunspell рускі (github.com/LibreOffice/dictionaries) — толькі для
                    ruwords: слова ёсць у рускім слоўніку, але не ў беларускім
  slovy.txt         усе словаформы GrammarDB (github.com/Belarus/GrammarDB), ~2 млн:
                    hunspell не ведае нават «многае» ці «перастае», без гэтага спіса
                    spell дае тысячы ілжэспрацоўванняў
  antykalka.tsv     «Новы расейска-беларускі слоўнік» Алега Мінкіна (antykalka.org):
                    даведнік `antykalka` і даклад `idioms`. Аўтарская праца — толькі
                    спампоўваецца, не распаўсюджваецца; укладальнік абнаўляе яго
                    прыкладна раз на месяц (`dicts --force antykalka`)
  fantasy.tsv       «Выніковы слоўнік» з «Дапаможніка для перакладчыкаў фэнтэзі»
                    (МТГ «RэЗервацыЯ», patreon.com/by_reservation; CC BY-SA 4.0): ~750
                    тэрмінаў фэнтэзі і D&D — даведнік `fantasy` і даклад `fantasy-report`.
                    Рабочы праект, абнаўляецца (`dicts --force fantasy`); тэрмін, узяты ў
                    гласарый, пазначаем «паводле „Дапаможніка“» (умова ліцэнзіі — аўтарства)

    python -m belloc dicts                    # спампаваць тое, чаго няма
    python -m belloc dicts --force            # усё нанова
    python -m belloc dicts --force antykalka  # толькі адзін слоўнік нанова

Без слоўнікаў лінтэр працуе, але spell/names/ruwords выключаныя.
"""
from __future__ import annotations

import glob
import os
import re
import tempfile
import urllib.request
import zipfile

from .config import local_root

HUNSPELL = {
    "be_BY.aff": "https://raw.githubusercontent.com/375gnu/hunspell-be/master/be_BY.aff",
    "be_BY.dic": "https://raw.githubusercontent.com/375gnu/hunspell-be/master/be_BY.dic",
    "ru_RU.aff": "https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ru_RU/ru_RU.aff",
    "ru_RU.dic": "https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ru_RU/ru_RU.dic",
}
# рэліз замацаваны, каб вынікі spell не змяняліся самі; новы — свядомым абнаўленнем
GRAMMARDB = ("https://github.com/Belarus/GrammarDB/releases/download/"
             "RELEASE-202601/RELEASE-202601.zip")
# кнопка «Спампаваць слоўнік (tsv)» на antykalka.org
ANTYKALKA = ("https://docs.google.com/spreadsheets/d/"
             "1mzx_yVs18m8hHhtteYAUzelgDuEyIz96l2L1jLWOBmU/pub?output=tsv")
# «Выніковы слоўнік» — асобная Google-табліца, на якую спасылаецца «Дапаможнік»
FANTASY = ("https://docs.google.com/spreadsheets/d/"
           "1yVD3Tq9S--IEXN34LHkP4d540Bxx7NtUratawQnT_FA/export?format=tsv")
FORM = re.compile(r"<Form[^>]*>([^<]+)</Form>")
NAMES = ("be_BY", "ru_RU", "slovy", "antykalka", "fantasy")


def path(*parts: str) -> str:
    return os.path.join(local_root(), "dicts", *parts)


def lint_args() -> list[str]:
    """Аргументы лінтэра для слоўнікаў, якія ўжо спампаваныя."""
    args = []
    if os.path.exists(path("be_BY.dic")):
        args += ["--dict", path("be_BY")]
    if os.path.exists(path("ru_RU.dic")):
        args += ["--ru-dict", path("ru_RU")]
    if os.path.exists(path("slovy.txt")):
        args += ["--wordlist", path("slovy.txt")]
    return args


def _get(url: str, dst: str):
    print("спампоўваю", os.path.basename(dst), "…")
    try:
        urllib.request.urlretrieve(url, dst)
    except Exception as e:                 # macOS з python.org: CERTIFICATE_VERIFY_FAILED
        raise SystemExit(f"не спампавалася {url}: {e}\n(macOS: запусціце «Install Certificates.command» "
                         "з папкі Python; за проксі — зменная HTTPS_PROXY)")


def _slovy(dst: str):
    with tempfile.TemporaryDirectory() as tmp:
        z = os.path.join(tmp, "gdb.zip")
        _get(GRAMMARDB, z)
        out = os.path.join(tmp, "gdb")
        zipfile.ZipFile(z).extractall(out)
        words = set()
        for p in glob.glob(os.path.join(out, "*.xml")):
            for line in open(p, encoding="utf-8"):
                for m in FORM.finditer(line):
                    words.add(m.group(1).replace("+", "").strip().lower())
        extra = os.path.join(out, "spellchecker", "slovy-2008.txt")
        if os.path.exists(extra):
            words |= {w.strip().lower() for w in open(extra, encoding="utf-8")}
    with open(dst, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(sorted(w for w in words if w)) + "\n")
    print(f"slovy.txt: {len(words)} формаў")


def fetch(force=False, only: list[str] | None = None):
    for n in only or []:
        if n not in NAMES:
            raise SystemExit(f"невядомы слоўнік «{n}»; ёсць: {', '.join(NAMES)}")
    want = set(only or NAMES)
    os.makedirs(path(), exist_ok=True)
    for name, url in HUNSPELL.items():
        if name.split(".")[0] in want and (force or not os.path.exists(path(name))):
            _get(url, path(name))
    if "slovy" in want and (force or not os.path.exists(path("slovy.txt"))):
        _slovy(path("slovy.txt"))
    if "antykalka" in want and (force or not os.path.exists(path("antykalka.tsv"))):
        _get(ANTYKALKA, path("antykalka.tsv"))
    if "fantasy" in want and (force or not os.path.exists(path("fantasy.tsv"))):
        _get(FANTASY, path("fantasy.tsv"))
    print("слоўнікі:", path())
