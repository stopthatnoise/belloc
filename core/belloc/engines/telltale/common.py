"""Агульнае для extract і apply: імя рухавіка, секцыя канфіга, наборы і архівы гульні."""
from __future__ import annotations

import glob
import hashlib
import os
import re
from pathlib import Path

from .lenc import Blowfish7, decrypt_lua
from .luac import Chunk
from .ttarch2 import TTArch2
from ...config import Loc

NAME = "telltale"


SECTION = "telltale"


TAG = "BelLoc"


def sec(loc: Loc) -> dict:
    return loc.section(SECTION)


def key_hash(text: str) -> str:
    """Ключ радка, зашытага ў Lua: у гульні ключа няма, ёсць толькі сам англійскі радок."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def set_of(arc_name: str) -> str:
    """Fables_pc_PC-Mac_TTG_Update_03_Episode_05_Menu_all → Menu,
    Fables_pc_Fables101_ar_data → Fables101, Fables_pc_105_all → Fables105."""
    s = re.sub(r"^Fables_pc_", "", Path(arc_name).stem)
    s = re.sub(r"^PC-Mac[-_]TTG_Update_\d+_(Episode_\d+_)?", "", s)
    s = re.sub(r"_(ar_)?(data|all|ms|anichore|txmesh|tx|mesh|voice)$", "", s)
    return "Fables" + s if s.isdigit() else s


def decode(b: bytes) -> str:
    """Рэмастэр — UTF-8, арыгінал 2013 г. — cp1252."""
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("cp1252")


def archives(folder: str) -> list[Path]:
    """Архівы гульні ў папцы — без нашага мода, калі ён стаіць у гульні."""
    return [p for p in sorted(Path(folder).glob("*.ttarch2")) if TAG not in p.name]


def lua_strings(data: bytes, bf: Blowfish7) -> list[bytes]:
    """Радковыя канстанты зашыфраванага Lua."""
    return [s for _, _, s in Chunk(decrypt_lua(data, bf)).strings]


def set_archives(lua: str) -> list[str]:
    """Імёны архіваў набору ў парадку спісу gameDataArchives."""
    block = re.search(r"set\.gameDataArchives\s*=\s*\{(.*?)\}", lua, re.S)
    return re.findall(r'"([^"]+\.ttarch2)"', block.group(1)) if block else []


def game_sets(game: str) -> dict[str, str]:
    """{набор: Lua дэскрыптара} — усе дэскрыптары гульні ў папцы (без нашых)."""
    out = {}
    for p in sorted(glob.glob(os.path.join(game, "_resdesc_50_*.lua"))):
        name = os.path.basename(p)[len("_resdesc_50_"):-4]
        if TAG not in name:
            out[name] = open(p, "rb").read().decode("utf-8")
    return out


def is_language_set(lua: str) -> bool:
    return re.search(r'set\.enableMode\s*=\s*"localization"', lua) is not None


def from_other_sets(game: str, sets: dict[str, str], name: str, skip: str,
                    like: bytes | None = None) -> bytes | None:
    """Файл name з агульнага (не моўнага) набору: той, што памерам роўны `like`
    (тэкстура той жа раздзяляльнасці — у TWAU лісты ёсць і ў Fables103 1024², і ў
    рэмастэрным ReFables103 2048², як у моўных наборах), інакш — з першага, дзе ён ёсць."""
    found = []
    for set_name, lua in sets.items():
        if set_name == skip or is_language_set(lua):
            continue
        for a in set_archives(lua):
            p = os.path.join(game, a)
            if os.path.exists(p):
                arc = TTArch2(p)
                if name in arc.files:
                    data = arc.get(name)
                    if like is None or len(data) == len(like):
                        return data
                    found.append(data)
    return found[0] if found else None
