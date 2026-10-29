"""Рухавікі гульняў: імя з game.json → модуль (інтэрфейс — engines/base.py)."""
from __future__ import annotations

import importlib

ENGINES = {
    "unity-localization": "unity_localization",
    "glacier": "glacier",
    "unity-textasset-csv": "unity_textasset_csv",
    "csv-folder": "csv_folder",
    "unreal-locres": "unreal_locres",
}


def get(name: str):
    if name not in ENGINES:
        raise SystemExit(f"рухавік «{name}» яшчэ не перанесены; ёсць: {', '.join(ENGINES)}")
    return importlib.import_module(f"{__name__}.{ENGINES[name]}")
