"""Агульнае для extract і apply: імя рухавіка, секцыя канфіга, дапаможныя функцыі."""
from __future__ import annotations

import glob
import os


NAME = "unity-localization"


SECTION = "unity"


def key_of(entry: dict) -> str:
    # запіс з пустым ключом (бывае) не губляем — бярэм ID
    return entry["m_Key"] or f"#{entry['m_Id']}"


def _string_bundles(bundles: str, lang: str) -> list[str]:
    return glob.glob(os.path.join(bundles, f"localization-string-tables-*({lang})_assets_all.bundle"))


def _string_bundle(bundles: str, lang: str) -> str:
    found = _string_bundles(bundles, lang)
    if len(found) != 1:
        raise SystemExit(f"мова {lang}: знойдзена бандлаў радкоў {len(found)} у {bundles}")
    return found[0]


def _shared(bundles: str) -> dict[str, dict[str, int]]:
    """{калекцыя: {ключ: m_Id}} з Shared Data."""
    from ..unity.bundles import monobehaviours
    shared = {}
    for p in glob.glob(os.path.join(bundles, "localization-assets-shared*.bundle")):
        for _, t in monobehaviours(p):
            if "m_Entries" in t and "m_TableCollectionName" in t:
                shared[t["m_TableCollectionName"]] = {key_of(e): e["m_Id"] for e in t["m_Entries"]}
    return dict(sorted(shared.items()))
