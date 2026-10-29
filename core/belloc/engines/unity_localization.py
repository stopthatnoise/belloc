"""Unity Localization (com.unity.localization) у Addressables-бандлах.

Як уладкавана ў гульні:
  localization-assets-shared_…            Shared Data калекцый: m_Id (int64) → m_Key
  localization-string-tables-<мова>_…     StringTable на калекцыю: m_Id → m_Localized
  localization-asset-tables-<мова>_…      AssetTable (шрыфты, тэкстуры) па мовах
  localization-locales_…                  спіс моў

Секцыя "unity" у game.json:
  data_dir        "Carpenter_Data"            — дзе globalgamemanagers
  bundles         "…/StreamingAssets/aa/StandaloneWindows64"
  extract_langs   ["en", "ru"]                — што выцягваць у source/
  preview_locale  "ru"                        — чыю табліцу перапісвае apply
  font_bundles    ["fonts_….bundle"]          — дзе ў кірылічныя TMP-шрыфты дадаюцца І/і, Ў/ў

Ключ табліцы — m_Key з Shared Data (чытэльны і сталы); m_Id для запісу apply
бярэ з Shared Data гульні гульца. Радкі без перакладу застаюцца на мове локалі.

Вынік extract (local/<гульня>/source/):
  <мова>.json   {табліца: {ключ: тэкст}}, ключы ў парадку Shared Data
  shared.json   {табліца: {ключ: m_Id}}
  meta.json     версія Unity, buildid Steam, колькасці
"""
from __future__ import annotations

import glob
import json
import os

from ..config import Loc
from ..install.target import Target, write_to

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


def _write_json(path: str, data):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- extract

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


# ---------------------------------------------------------------- payload і apply

def payload(loc: Loc) -> dict:
    sec = loc.section(SECTION)
    return {"bundles_dir": sec["bundles"], "locale": sec["preview_locale"],
            "font_bundles": sec.get("font_bundles", [])}


def check_path(payload: dict) -> str:
    return payload["bundles_dir"]


def _patch_strings(base: str, dst: str, want: dict) -> int:
    import UnityPy
    from ..unity.bundles import save
    env = UnityPy.load(base)
    done = 0
    for o in env.objects:
        if o.type.name != "MonoBehaviour":
            continue
        try:
            t = o.read_typetree()
        except Exception:
            continue
        if "m_TableData" not in t:
            continue
        table = t["m_Name"].rsplit("_", 1)[0]
        changed = False
        for e in t["m_TableData"]:
            text = want.get((table, e["m_Id"]))
            if text is not None:
                e["m_Localized"] = text
                changed = True
                done += 1
        if changed:
            o.save_typetree(t)
    save(env, dst)
    return done


def apply(game_dir: str, payload: dict, out: str | None = None, log=print) -> dict:
    """Радкі локалі + І/і/Ў/ў у шрыфтах. out — папка для вынікаў, гульня не чапаецца."""
    from ..unity.tmp_fonts import patch_bundle
    bundles = os.path.join(game_dir, payload["bundles_dir"])
    strings = _string_bundle(bundles, payload["locale"])
    shared = _shared(bundles)
    want, missing = {}, 0
    for table, rows in payload["strings"].items():
        ids = shared.get(table, {})
        for key, text in rows.items():
            if key in ids:
                want[(table, ids[key])] = text
            else:
                missing += 1

    log("Тэкст…")
    done = [0]

    def write_strings(base, dst):
        done[0] = _patch_strings(base, dst, want)
    write_to(Target(strings), out, write_strings)
    log(f"  перакладзена радкоў: {done[0]}"
        + (f" (няма ў гэтай версіі гульні: {missing})" if missing else ""))

    log("Шрыфты (І і Ў)…")
    for name in payload["font_bundles"]:
        path = os.path.join(bundles, name)
        if not os.path.exists(path):
            log(f"  няма {name} — прапускаю")
            continue
        write_to(Target(path), out, lambda base, dst: patch_bundle(base, dst, None))
    return {"strings": done[0], "missing": missing}


def _targets(game_dir: str, payload: dict) -> list[Target]:
    bundles = os.path.join(game_dir, payload["bundles_dir"])
    paths = _string_bundles(bundles, payload["locale"])
    paths += [os.path.join(bundles, n) for n in payload["font_bundles"]]
    return [Target(p) for p in paths]


def restore(game_dir: str, payload: dict, log=print):
    for t in _targets(game_dir, payload):
        if os.path.exists(t.path) or os.path.exists(t.orig):
            log(f"  {os.path.basename(t.path)}: {t.restore()}")


def installed(game_dir: str, payload: dict) -> bool:
    bundles = os.path.join(game_dir, payload["bundles_dir"])
    strings = _string_bundles(bundles, payload["locale"])
    return bool(strings) and Target(strings[0]).installed()


def fonts_report(loc: Loc, need: set[int] | None = None):
    from ..unity.tmp_fonts import report
    report(loc.game(loc.section(SECTION)["bundles"]), need)
