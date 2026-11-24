"""Агульнае для extract і apply: імя рухавіка, секцыя канфіга, шляхі."""
from __future__ import annotations

from ...install.paths import inside, name as one


NAME = "battletech-csv"

SECTION = "battletech_csv"

TABLE = "strings"                 # адна табліца гульні: strings_<культура>.csv

NORM = "battletech-v1"            # версія _NormalizeString (norm.py)


def csv_path(game_dir: str, s: dict, locale: str) -> str:
    """strings_<культура>.csv унутры <csv_dir> гульні."""
    return inside(game_dir, s["csv_dir"], f"strings_{one(locale)}.csv")


def target_path(game_dir: str, s: dict) -> str:
    return csv_path(game_dir, s, s["locale"])


def scanned_langs(s: dict) -> list[tuple[str, str]]:
    """[(мова, культура)] для ўсіх файлаў, якія чытае extract: target і other_langs.

    Культуры бяруцца з канфіга, а не з імёнаў файлаў: імя з game.json — даныя,
    але яно мусіць прайсці paths.name (яно трапляе ў шлях)."""
    out = [(s.get("target", "ru"), s["locale"])]
    for lang in s.get("other_langs", []):
        if lang == s.get("target"):
            continue
        out.append((one(lang), f"{one(lang)}-{one(lang.upper())}"))
    return out
