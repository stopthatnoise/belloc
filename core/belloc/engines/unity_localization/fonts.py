"""Справаздача па шрыфтах гульні (`belloc fonts`)."""
from __future__ import annotations

from ...config import Loc
from .common import SECTION


def fonts_report(loc: Loc, need: set[int] | None = None):
    from .tmp_fonts import report
    report(loc.game(loc.section(SECTION)["bundles"]), need)
