"""Справаздача па шрыфтах гульні (`belloc fonts`)."""
from __future__ import annotations

import os
import re

from ...config import Loc
from .common import SECTION


FONT_FILES = ("game/fonts/fonts.font", "clausewitz/fonts/cw_fonts.font")


BEL_CHARS = "ІіЎў«»’—"


def font_groups(game_dir: str, lang: str):
    """(файл .font, імя fontfiles, [шляхі шрыфтоў]) для груп з l_<lang>."""
    for ff in FONT_FILES:
        p = os.path.join(game_dir, ff)
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8-sig") as f:
            text = f.read()
        name = None
        for m in re.finditer(r'name\s*=\s*"([^"]+)"|languages\s*=\s*\{([^}]*)\}\s*files\s*=\s*\{([^}]*)\}',
                             text):
            if m.group(1):
                name = m.group(1)
            elif f'"l_{lang}"' in m.group(2):
                yield ff, name, re.findall(r'"([^"]+)"', m.group(3))


def find_font(game_dir: str, s: dict, rel: str) -> str | None:
    for root in s.get("roots", ["game"]):
        p = os.path.join(game_dir, root, rel)
        if os.path.exists(p):
            return p
    return None


def fonts_report(loc: Loc, chars: set[int] | None = None):
    """Для кожнай групы шрыфтоў падменнай мовы: які шрыфт дае кожную літару."""
    from fontTools.ttLib import TTFont
    s = loc.section(SECTION)
    want = sorted(chars) if chars else [ord(c) for c in BEL_CHARS]
    cmaps: dict[str, set[int]] = {}
    bad = 0
    for ff, name, chain in font_groups(loc.game_dir, s["target"]):
        missing = set(want)
        first_missing = None
        for rel in chain:
            p = find_font(loc.game_dir, s, rel)
            if p is None:
                print(f"  {name}: файла няма — {rel}")
                continue
            if p not in cmaps:
                cmaps[p] = set(TTFont(p, lazy=True).getBestCmap())
            if first_missing is None:
                first_missing = "".join(chr(c) for c in want if c not in cmaps[p])
            missing -= cmaps[p]
        head = os.path.basename(chain[0]) if chain else "—"
        status = "ok" if not missing else "НЯМА: " + "".join(chr(c) for c in sorted(missing))
        if missing:
            bad += 1
        note = f" (асноўны {head} без: {first_missing})" if first_missing else ""
        print(f"  {os.path.basename(ff):14} {name:24} {status}{note}")
    print("усе групы пакрываюць літары" if not bad else f"груп з дзіркамі: {bad}")
