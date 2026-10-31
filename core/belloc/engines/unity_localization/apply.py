"""payload, apply, restore, installed: наш пераклад → файлы гульні (або --out)."""
from __future__ import annotations

import os

from ...config import Loc
from ...install.target import Target, write_to
from .common import SECTION, _shared, _string_bundle, _string_bundles


def payload(loc: Loc) -> dict:
    sec = loc.section(SECTION)
    return {"bundles_dir": sec["bundles"], "locale": sec["preview_locale"],
            "font_bundles": sec.get("font_bundles", []),
            "data_dir": sec.get("data_dir"), "font_assets": sec.get("font_assets", [])}


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
    from .tmp_fonts import font_type_tree, patch_assets, patch_bundle
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
    if payload.get("font_assets"):
        # тыпавое дрэва TMP_FontAsset — з арыгінальнага бандла шрыфтоў (у .assets яго няма)
        nodes = next((font_type_tree(Target(os.path.join(bundles, n)).source())
                      for n in payload["font_bundles"] if os.path.exists(os.path.join(bundles, n))), None)
        if nodes is None:
            log("  няма бандла шрыфтоў для тыпавога дрэва — font_assets прапускаю")
        for name in payload["font_assets"] if nodes is not None else []:
            path = os.path.join(game_dir, payload["data_dir"], name)
            if not os.path.exists(path):
                log(f"  няма {name} — прапускаю")
                continue
            write_to(Target(path), out, lambda base, dst: patch_assets(base, dst, nodes))
    return {"strings": done[0], "missing": missing}


def _targets(game_dir: str, payload: dict) -> list[Target]:
    bundles = os.path.join(game_dir, payload["bundles_dir"])
    paths = _string_bundles(bundles, payload["locale"])
    paths += [os.path.join(bundles, n) for n in payload["font_bundles"]]
    paths += [os.path.join(game_dir, payload["data_dir"], n) for n in payload.get("font_assets", [])]
    return [Target(p) for p in paths]


def restore(game_dir: str, payload: dict, log=print):
    for t in _targets(game_dir, payload):
        if os.path.exists(t.path) or os.path.exists(t.orig):
            log(f"  {os.path.basename(t.path)}: {t.restore()}")


def installed(game_dir: str, payload: dict) -> bool:
    bundles = os.path.join(game_dir, payload["bundles_dir"])
    strings = _string_bundles(bundles, payload["locale"])
    return bool(strings) and Target(strings[0]).installed()
