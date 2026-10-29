"""extract: файлы гульні → local/<гульня>/source/."""
from __future__ import annotations

import json
import os

from ...config import Loc
from ...install.target import Target
from .common import SECTION, _shared, _string_bundle


def _write_json(path: str, data):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def extract(loc: Loc, out: str | None = None):
    from ..unity.bundles import monobehaviours, unity_version
    sec = loc.section(SECTION)
    bundles = loc.game(sec["bundles"])
    out = out or loc.source
    os.makedirs(out, exist_ok=True)

    shared = _shared(bundles)
    id2key = {coll: {i: k for k, i in keys.items()} for coll, keys in shared.items()}
    _write_json(os.path.join(out, "shared.json"), shared)

    counts = {}
    for lang in sec.get("extract_langs", [loc.source_lang, loc.hint_lang]):
        if not lang:
            continue
        # перапісаны намі бандл чытаць нельга — там ужо наш bel
        bundle = Target(_string_bundle(bundles, lang)).source()
        tables: dict[str, dict[str, str]] = {}
        for _, t in monobehaviours(bundle):
            if "m_TableData" not in t:
                continue
            coll = t["m_Name"].rsplit("_", 1)[0]
            vals = {e["m_Id"]: e["m_Localized"] for e in t["m_TableData"]}
            ids = id2key.get(coll, {})
            # парадак — як у Shared Data; запісы без ключа ідуць у канец
            table = {k: vals[i] for i, k in ids.items() if i in vals}
            table.update({f"#{i}": v for i, v in vals.items() if i not in ids})
            tables[coll] = table
        tables = dict(sorted(tables.items()))
        _write_json(os.path.join(out, f"{lang}.json"), tables)
        counts[lang] = sum(len(v) for v in tables.values())
        print(f"{lang}: табліц {len(tables)}, радкоў {counts[lang]}")

    meta = {"unity": unity_version(loc.game(sec["data_dir"])),
            "steam_buildid": loc.steam_buildid(), "strings": counts,
            "shared_keys": sum(len(v) for v in shared.values())}
    _write_json(os.path.join(out, "meta.json"), meta)
    print("meta:", meta)
