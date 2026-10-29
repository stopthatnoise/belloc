"""Агульнае для extract і apply: імя рухавіка, секцыя канфіга, дапаможныя функцыі."""
from __future__ import annotations

import os
import re

from ...config import Loc
from . import rpkg


NAME = "glacier"


SECTION = "glacier"


SPEAKERS = "dlg/_speakers"


def sec(loc: Loc) -> dict:
    return loc.section(SECTION)


def voice_gender(code: str) -> str:
    """CIVUKF01 → ж, MERCMRM03 → м; імёны (BOND, M, Q) — пуста (род — у гласарыі)."""
    m = re.fullmatch(r"[A-Z]{3,}([MF])\d+", code.split("_")[-1])
    return {"M": "м", "F": "ж"}[m.group(1)] if m else ""


def speaker_key(name: str, gender: str) -> str:
    """Ключ dlg/_speakers: імя на экране + пол голасу — «Civilian» па-руску
    «Гражданский» і «Гражданская», па-беларуску таксама па-рознаму."""
    return f"{name}|{gender}" if gender else name


def base_packagedefinition(rt: str) -> str:
    """Арыгінал packagedefinition.txt: .orig, пакуль у гульні ляжыць наш запіс
    (калі Steam яго падмяніў — бягучы файл)."""
    pd = os.path.join(rt, "packagedefinition.txt")
    return pd + ".orig" if os.path.exists(pd + ".orig") and rpkg.ours(pd) else pd
