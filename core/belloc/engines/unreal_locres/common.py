"""Агульнае для extract і apply: імя рухавіка, секцыя канфіга, дапаможныя функцыі."""
from __future__ import annotations

import os
import re

from ...config import Loc
from . import pak
from .locres import Locres


NAME = "unreal-locres"


SECTION = "unreal"


def sec(loc: Loc) -> dict:
    return loc.section(SECTION)


def targets(s: dict) -> dict[str | None, str]:
    """{мэта: пак}; без loc_targets — адна мэта None."""
    return s.get("loc_targets") or {None: s["pak"]}


def locres_path(s: dict, lang: str, target: str | None = None) -> str:
    return s["locres"].format(lang=s["langs"].get(lang, lang), target=target)


def table_name(target: str | None, ns: str) -> str:
    """Імя табліцы для прасторы ns; толькі ў гэты бок — build_mod шукае
    тэксты па імені табліцы кожнай прасторы locres."""
    if target is None:
        return ns
    segs = [re.sub(r'[<>:"\|?*/]', "_", x).rstrip(" .") or "_" for x in ns.split(".")] if ns else ["_"]
    return "/".join([target] + segs)


def read_locres(game_dir: str, s: dict, lang: str, target: str | None = None,
                p: pak.Pak | None = None) -> Locres:
    own = p is None
    p = p or pak.Pak(os.path.join(game_dir, targets(s)[target]), s.get("aes_key"))
    try:
        return Locres(p.read(locres_path(s, lang, target)))
    finally:
        if own:
            p.close()
