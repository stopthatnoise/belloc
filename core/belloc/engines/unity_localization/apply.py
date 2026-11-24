"""payload, apply, restore, installed: наш пераклад → файлы гульні (або --out).

Рэжым — па game.json:
  - StringTable: перапісваецца бандл мовы + шрыфты (+ m_Crc у catalog.json, crc.py);
  - маналітная табліца: адзін бандл з табліцай (monolithic.py) + CRC у catalog.bin
    і md5 у catalog.hash (catalog_bin.py) + шрыфты.
"""
from __future__ import annotations

import glob
import os

from ...config import Loc
from ...install.paths import inside, name as one
from ...install.target import Target, write_to
from .common import SECTION, _shared, _string_bundle, _string_bundles


def payload(loc: Loc) -> dict:
    sec = loc.section(SECTION)
    p = {"bundles_dir": sec["bundles"], "locale": sec["preview_locale"],
         "font_bundles": sec.get("font_bundles", []),
         "data_dir": sec.get("data_dir"), "font_assets": sec.get("font_assets", []),
         "crc_catalog": sec.get("crc_catalog")}
    if sec.get("crc_catalog"):
        p["schema"] = 2  # стары лаўнчар не абнуліў бы CRC — гульня адкінула б пераклад
    if sec.get("monolithic_table"):
        if not sec.get("table_bundle"):
            raise SystemExit("unity: з monolithic_table патрэбен table_bundle (дзе табліца)")
        p.update(monolithic_table=sec["monolithic_table"],
                 table_bundle=sec["table_bundle"], schema=3)
    if sec.get("crc_catalog_bin"):
        if not sec.get("hash_file"):
            raise SystemExit("unity: з crc_catalog_bin патрэбен hash_file (catalog.hash)")
        # стары лаўнчар не ведае ні catalog.bin, ні catalog.hash: паставіў бы
        # пераклад, які гульня адкідвае на старце
        p.update(crc_catalog_bin=sec["crc_catalog_bin"], hash_file=sec["hash_file"], schema=3)
    return p


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


def _one(bundles: str, pattern: str) -> str:
    """Адзін файл па glob у бандлах (імя з game.json — праз install.paths.name)."""
    found = glob.glob(os.path.join(bundles, one(pattern)))
    if len(found) != 1:
        raise SystemExit(f"бандл «{pattern}»: знойдзена файлаў {len(found)} у {bundles}")
    return found[0]


def _want(payload: dict) -> tuple[dict[str, str], int]:
    """{ключ: bel} з усіх табліц payload + колькасць ключоў з рознымі перакладамі."""
    want, clash = {}, 0
    for rows in payload["strings"].values():
        for key, text in rows.items():
            if key in want and want[key] != text:
                clash += 1
                continue
            want[key] = text
    return want, clash


def _apply_monolithic(game_dir: str, payload: dict, out: str | None, log) -> dict:
    from ... import tables
    from . import catalog_bin, english, monolithic
    from .tmp_fonts import font_type_tree, patch_assets, patch_bundle
    bundles = inside(game_dir, payload["bundles_dir"])
    table = _one(bundles, payload["table_bundle"])
    want, clash = _want(payload)
    pat = tables.from_original(payload.get("from_original"))

    # памеры арыгіналаў — да запісу: па ім catalog_bin шукае запіс бандла ў каталогу
    targets = [table] + [os.path.join(bundles, one(n)) for n in payload["font_bundles"]]
    sizes = {os.path.basename(p): os.path.getsize(Target(p).source())
             for p in targets if os.path.exists(p)}

    log("Тэкст…")
    done = [0, 0, 0]

    def write_table(base, dst):
        done[:] = monolithic.write(base, dst, payload["monolithic_table"], want,
                                   orig=english.all_texts if pat is not None else None,
                                   pat=pat)

    write_to(Target(table), out, write_table)
    log(f"  запісана радкоў: {done[0]}"
        + (f" (няма ў гэтай версіі гульні: {done[1]})" if done[1] else "")
        + (f" (без пары для {tables.PLACEHOLDER}: {done[2]})" if done[2] else "")
        + (f" (адзін ключ з розным перакладам у розных табліцах: {clash})" if clash else ""))
    res = {"strings": done[0], "missing": done[1], "placeholders": done[2]}

    if payload.get("crc_catalog_bin"):
        log("CRC бандлаў у catalog.bin і md5 у catalog.hash…")
        crcs = [0, []]

        def write_catalog(base, dst):
            with open(base, "rb") as f:
                data = f.read()
            new, crcs[0], crcs[1] = catalog_bin.zero_crc(data, sizes)
            with open(dst, "wb") as f:
                f.write(new)

        catalog = write_to(Target(inside(game_dir, payload["crc_catalog_bin"])), out, write_catalog)
        log(f"  абнулена CRC: {crcs[0]}"
            + (f" (без запісу CRC у каталогу: {', '.join(crcs[1])})" if crcs[1] else ""))
        with open(catalog, "rb") as f:
            digest = catalog_bin.hash_hex(f.read())
        hash_path = inside(game_dir, payload["hash_file"])
        write_to(Target(hash_path), out, lambda base, dst: _write_bytes(dst, digest))
        res["crc"] = crcs[0]

    log("Шрыфты (І і Ў)…")
    for name in payload["font_bundles"]:
        path = os.path.join(bundles, one(name))
        if not os.path.exists(path):
            log(f"  няма {name} — прапускаю")
            continue
        write_to(Target(path), out, lambda base, dst: patch_bundle(base, dst, None))
    if payload.get("font_assets"):
        nodes = next((font_type_tree(Target(os.path.join(bundles, one(n))).source())
                      for n in payload["font_bundles"]
                      if os.path.exists(os.path.join(bundles, one(n)))), None)
        if nodes is None:
            log("  няма бандла шрыфтоў для тыпавога дрэва — font_assets прапускаю")
        for name in payload["font_assets"] if nodes is not None else []:
            path = inside(game_dir, payload["data_dir"], one(name))
            if not os.path.exists(path):
                log(f"  няма {name} — прапускаю")
                continue
            write_to(Target(path), out, lambda base, dst: patch_assets(base, dst, nodes))
    return res


def _write_bytes(dst: str, data: bytes) -> None:
    with open(dst, "wb") as f:
        f.write(data)


def apply(game_dir: str, payload: dict, out: str | None = None, log=print) -> dict:
    """Радкі локалі + І/і/Ў/ў у шрыфтах. out — папка для вынікаў, гульня не чапаецца."""
    if payload.get("monolithic_table"):
        return _apply_monolithic(game_dir, payload, out, log)
    from .tmp_fonts import font_type_tree, patch_assets, patch_bundle
    bundles = inside(game_dir, payload["bundles_dir"])
    strings = _string_bundle(bundles, one(payload["locale"]))
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

    if payload.get("crc_catalog"):
        from .crc import zero_crc_file
        log("CRC бандлаў у каталогу Addressables…")
        crcs = [0]

        def write_catalog(base, dst):
            crcs[0] = zero_crc_file(base, dst)
        write_to(Target(inside(game_dir, payload["crc_catalog"])), out, write_catalog)
        log(f"  абнулена: {crcs[0]}")

    log("Шрыфты (І і Ў)…")
    for name in payload["font_bundles"]:
        path = os.path.join(bundles, one(name))
        if not os.path.exists(path):
            log(f"  няма {name} — прапускаю")
            continue
        write_to(Target(path), out, lambda base, dst: patch_bundle(base, dst, None))
    if payload.get("font_assets"):
        # тыпавое дрэва TMP_FontAsset — з арыгінальнага бандла шрыфтоў (у .assets яго няма)
        nodes = next((font_type_tree(Target(os.path.join(bundles, one(n))).source())
                      for n in payload["font_bundles"] if os.path.exists(os.path.join(bundles, one(n)))), None)
        if nodes is None:
            log("  няма бандла шрыфтоў для тыпавога дрэва — font_assets прапускаю")
        for name in payload["font_assets"] if nodes is not None else []:
            path = inside(game_dir, payload["data_dir"], one(name))
            if not os.path.exists(path):
                log(f"  няма {name} — прапускаю")
                continue
            write_to(Target(path), out, lambda base, dst: patch_assets(base, dst, nodes))
    return {"strings": done[0], "missing": missing}


def _targets(game_dir: str, payload: dict) -> list[Target]:
    bundles = inside(game_dir, payload["bundles_dir"])
    if payload.get("monolithic_table"):
        paths = [_one(bundles, payload["table_bundle"])]
    else:
        paths = _string_bundles(bundles, one(payload["locale"]))
    paths += [os.path.join(bundles, one(n)) for n in payload["font_bundles"]]
    paths += [inside(game_dir, payload["data_dir"], one(n)) for n in payload.get("font_assets", [])]
    if payload.get("crc_catalog"):
        paths.append(inside(game_dir, payload["crc_catalog"]))
    if payload.get("crc_catalog_bin"):
        paths.append(inside(game_dir, payload["crc_catalog_bin"]))
        paths.append(inside(game_dir, payload["hash_file"]))
    return [Target(p) for p in paths]


def restore(game_dir: str, payload: dict, log=print):
    for t in _targets(game_dir, payload):
        if os.path.exists(t.path) or os.path.exists(t.orig):
            log(f"  {os.path.basename(t.path)}: {t.restore()}")


def installed(game_dir: str, payload: dict) -> bool:
    bundles = inside(game_dir, payload["bundles_dir"])
    if payload.get("monolithic_table"):
        try:
            return Target(_one(bundles, payload["table_bundle"])).installed()
        except SystemExit:
            return False                   # бандла няма (іншая версія гульні)
    strings = _string_bundles(bundles, one(payload["locale"]))
    return bool(strings) and Target(strings[0]).installed()
