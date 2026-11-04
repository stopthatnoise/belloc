"""Агульнае для extract і apply: канфіг, кантэйнеры па прыярытэце, табліцы, прэфіксы рэплік."""
from __future__ import annotations

import json
import os
import re

from ...config import Loc
from ...install.paths import inside
from ...install.target import Target
from . import resources

NAME = "idtech"

SECTION = "idtech"


def sec(loc: Loc) -> dict:
    return loc.section(SECTION)

NAMES = "vo/_names"          # імёны над субтытрамі: [name:Fascist] → ключ «Fascist»

# Службовы пачатак рэплікі: імя прамоўцы і дырэктывы субтытраў ([p-5], [force],
# [dist:10]). Перакладчык іх не бачыць: extract зразае, apply бярэ з арыгінала
# (імёны — з NAMES).
PREFIX = re.compile(r"^(?:\[(?:name:[^\]]*|p-\d+|force|dist:\d+)\])+")
NAME_TAG = re.compile(r"\[name:([^\]]*)\]")
# радок, у якім няма чаго перакладаць ([none], пуста) — у табліцы не трапляе
EMPTY = re.compile(r"^(?:\s|\[none\s*\])*$")


def split_prefix(text: str) -> tuple[str, str]:
    m = PREFIX.match(text)
    return (m.group(), text[m.end():]) if m else ("", text)


def prefix_names(prefix: str) -> list[str]:
    return [n.strip() for n in NAME_TAG.findall(prefix)]


def containers(base: str) -> list[str]:
    """Кантэйнеры gameresources ад найноўшага патча да асноўнага — парадак карты
    common у packagemapspec_pc.json (гульня бярэ рэсурс з першага, дзе ён ёсць)."""
    with open(os.path.join(base, "packagemapspec_pc.json"), encoding="utf-8") as f:
        spec = json.load(f)
    by_id = {c["id"]: c for c in spec["containers"]}
    common = next(m for m in spec["maps"] if m["name"] == "common")
    out = []
    for ref in common["container_refs"]:
        c = by_id[ref]
        if c["type"] == "resource" and c["basename"] == "gameresources":
            out.append(c["debug_name"])
    return out


def find_lang(base: str, variation: int) -> tuple[str, resources.Resource]:
    """(шлях кантэйнера, рэсурс) апошняй версіі lang/strings мовы variation.
    Чытаецца арыгінал (.orig, калі ў гульні ўжо наш файл)."""
    for name in containers(base):
        path = Target(inside(base, name)).source()
        for r in resources.read_table(path):
            if r.type == "lang" and r.name == "strings" and r.variation == variation:
                return path, r
    raise SystemExit(f"lang/strings з variation {variation:#x} не знойдзены ў {base}")


def read_lang(base: str, variation: int) -> dict[str, str]:
    from . import lang
    path, r = find_lang(base, variation)
    return {k: t for _, k, t in lang.parse(resources.read_data(path, r))}


def table_of(key: str) -> str:
    """#str_vo_nl_indy_ch04se01_150_… → vo/nl/ch04se01; #str_vo_sl_officerluigi_… →
    vo/sl/officerluigi; #str_mission_vatican_… → ui/mission/vatican; #str_code_… → ui/code.
    Малымі літарамі: у ключах бывае і Gizeh, і gizeh, а на Windows гэта адзін файл CSV."""
    p = key.lower().lstrip("#").split("_")
    if len(p) > 3 and p[0] == "str" and p[1] == "vo":
        kind = p[2]
        if kind == "nl" and len(p) > 4:
            return f"vo/nl/{p[4]}"
        if kind in ("sl", "tp"):
            return f"vo/{kind}/{p[3]}"
        return f"vo/{kind}"
    if len(p) > 2 and p[1] == "mission":
        return f"ui/mission/{p[2]}"
    return f"ui/{p[1] if len(p) > 1 else p[0]}"


def order(key: str):
    """Парадак у табліцы: рэплікі сюжэта — па нумары з ключа (…_ch04se01_150_…)."""
    p = key.lstrip("#").split("_")
    if len(p) > 5 and p[1] == "vo" and p[2] == "nl" and p[5].isdigit():
        return (int(p[5]), key)
    return (0, key)


def speaker(key: str) -> str:
    p = key.lstrip("#").split("_")
    return p[3] if len(p) > 3 and p[1] == "vo" else ""
