"""Агульнае для extract і apply: імя рухавіка, секцыя канфіга, дапаможныя функцыі."""
from __future__ import annotations

import csv
import glob
import os


NAME = "csv-folder"


SECTION = "csv_folder"


def _read(path: str) -> list[list[str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.reader(f))


def _tables(path: str) -> list[tuple[str, str]]:
    return [(os.path.basename(p)[:-4], p) for p in sorted(glob.glob(os.path.join(path, "*.csv")))]


def _folder(game_dir: str, s: dict, name: str) -> str:
    return os.path.join(game_dir, s["dir"], s[name])
