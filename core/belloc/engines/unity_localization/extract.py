"""extract: файлы гульні → local/<гульня>/source/.

Два рэжымы (які — па game.json):
  - StringTable у бандлах `localization-string-tables-<мова>` (звычайны);
  - маналітная табліца `<…>LocalizationTable`: тады яе тэкст — у source/<мова>.json,
    англійскі арыгінал — з даных гульні (english.py), гл. monolithic.py.
"""
from __future__ import annotations

import glob
import json
import os

from ...config import Loc
from ...install.paths import name as one
from ...install.target import Target
from .common import SECTION, _shared, _string_bundle


def _write_json(path: str, data):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def _one_bundle(bundles: str, pattern: str) -> str:
    found = glob.glob(os.path.join(bundles, one(pattern)))
    if len(found) != 1:
        raise SystemExit(f"бандл «{pattern}»: знойдзена файлаў {len(found)} у {bundles}")
    return found[0]


def _extract_monolithic(loc: Loc, sec: dict, bundles: str, out: str, meta: dict) -> None:
    """Маналітная табліца + англійскі арыгінал з даных гульні."""
    from . import english, monolithic
    table_name = sec["monolithic_table"]
    bundle = _one_bundle(bundles, sec["table_bundle"])
    base = Target(bundle).source()          # патчаны намі бандл чытаць нельга
    table = monolithic.table_of(base, table_name)
    rules = sec.get("tables") or {}
    rest = sec.get("rest_table", "system")
    if rest in rules:
        raise SystemExit(f"tables: «{rest}» — гэта ж rest_table, правіла для яе не патрэбна")

    hint = sec.get("preview_locale") or loc.hint_lang
    if not hint:
        raise SystemExit("monolithic_table: патрэбен preview_locale або hint_lang "
                         "(якая мова ляжыць у табліцы)")
    _write_json(os.path.join(out, f"{hint}.json"), monolithic.split(table, rules, rest))

    # англійская — з даных; дзе яе няма (літаральна няма ў гэтай версіі гульні),
    # застаецца тэкст маналітнай табліцы: гэта падказка, а не арыгінал, і хэш такога
    # радка не змяняецца ад пераходу на англійскую крыніцу
    eng = english.all_texts(base)
    no_source = [key for key in table if key not in eng]
    rows = {key: eng[key] if key in eng else table[key] for key in table}
    _write_json(os.path.join(out, f"{loc.source_lang}.json"), monolithic.split(rows, rules, rest))
    meta.update(strings={hint: len(table), loc.source_lang: len(table)},
                no_source={loc.source_lang: len(no_source)}, source_lang=loc.source_lang)
    print(f"{hint}: табліца «{table_name}», радкоў {len(table)}"
          f" | {loc.source_lang}: англійская ёсць у {len(table) - len(no_source)},"
          f" няма ў {len(no_source)}")
    for name, part in monolithic.split(table, rules, rest).items():
        print(f"  {name:12} {len(part):6}")


def extract(loc: Loc, out: str | None = None):
    from ..unity.bundles import monobehaviours, unity_version
    sec = loc.section(SECTION)
    bundles = loc.game(sec["bundles"])
    out = out or loc.source
    os.makedirs(out, exist_ok=True)
    meta = {"unity": unity_version(loc.game(sec["data_dir"])),
            "steam_buildid": loc.steam_buildid()}

    if sec.get("monolithic_table"):
        _extract_monolithic(loc, sec, bundles, out, meta)
        _write_json(os.path.join(out, "meta.json"), meta)
        print("meta:", meta)
        return

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

    meta.update(strings=counts, shared_keys=sum(len(v) for v in shared.values()))
    _write_json(os.path.join(out, "meta.json"), meta)
    print("meta:", meta)
