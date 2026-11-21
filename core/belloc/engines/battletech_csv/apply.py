"""payload, apply, restore, installed: наш пераклад → strings_<культура>.csv."""
from __future__ import annotations

import os

from ... import tables as ttables
from ...config import Loc
from ...install.target import Target
from .common import SECTION, TABLE, csv_path, scanned_langs, target_path
from .norm import key_hash, normalize
from .table import escape, read_rows, write_rows


def payload(loc: Loc) -> dict:
    """Хэшы крыніцы толькі перакладзеных радкоў: apply прапусціць тыя, чый
    арыгінал змяніўся. Самога тэксту гульні ў payload няма. Для радкоў не з
    асноўнай крыніцы пішацца src_lang — каб apply ведаў, што зверыць у гульні
    (EN у файлах гульні няма, яго зверка — па source/ пасля extract)."""
    hashes, langs = {}, {}
    rows = ttables.load_all(loc).get(TABLE, []) if ttables.has_source(loc) else []
    if not rows:
        rows = ttables.load_repo(loc).get(TABLE, [])
    for r in rows:
        if not r["bel"] or not r["src_hash"]:
            continue
        hashes[r["key"]] = r["src_hash"]
        lang = r.get("src_lang") or loc.source_lang
        if lang != loc.source_lang:
            langs[r["key"]] = lang
    p = {"battletech_csv": loc.section(SECTION), "source_lang": loc.source_lang}
    if loc.fallback_lang:
        p["fallback_lang"] = loc.fallback_lang
    if hashes:
        p["src_hash"] = {TABLE: hashes}
    if langs:
        p["src_lang"] = {TABLE: langs}
    return p


def check_path(payload: dict) -> str:
    return payload["battletech_csv"]["csv_dir"]


def _source_tables(game_dir: str, s: dict) -> dict[str, dict[str, str]]:
    """Ключ → тэкст для ўсіх моў гульні."""
    out = {}
    for lang, culture in scanned_langs(s):
        path = csv_path(game_dir, s, culture)
        if not os.path.exists(path):
            continue
        _, rows, _ = read_rows(Target(path).source())
        out[lang] = {key_hash(normalize(k)): v for _, k, v in rows if k}
    return out


def apply(game_dir: str, payload: dict, out: str | None = None, log=print) -> dict:
    s = payload["battletech_csv"]
    target = Target(target_path(game_dir, s))
    base = target.source() if out else target.base()
    header, rows, bad = read_rows(base)
    if bad:
        log(f"  у табліцы гульні {bad} радкоў з непадыходнай колькасцю калонак — прапушчаны")
    sources = _source_tables(game_dir, s)
    expected = payload.get("src_hash", {}).get(TABLE, {})
    src_lang = payload.get("src_lang", {}).get(TABLE, {})
    tr = payload["strings"].get(TABLE, {})

    done = stale = unknown = 0
    written = []
    for _, raw_key, value in rows:
        if not raw_key:
            written.append((raw_key, value))
            continue
        h = key_hash(normalize(raw_key))
        if h not in tr:
            written.append((raw_key, value))
            continue
        want = expected.get(h)
        lang = src_lang.get(h, payload.get("source_lang", "en"))
        if want and lang not in sources:
            # англійскай табліцы ў гульні няма: зверка толькі праз source/ пасля extract
            if lang != payload.get("source_lang", "en"):
                unknown += 1
                written.append((raw_key, value))
                continue
            written.append((raw_key, escape(tr[h])))
            done += 1
            continue
        current = sources[lang].get(h)
        if want and (current is None or ttables.src_hash(current) != want):
            stale += 1
            written.append((raw_key, value))       # гульня абнавілася пасля перакладу
            continue
        written.append((raw_key, escape(tr[h])))
        done += 1

    name = os.path.basename(target.path)
    if out:
        os.makedirs(out, exist_ok=True)
        dest = os.path.join(out, name)
        write_rows(dest, header, written)
        log(f"запісана {done} радкоў у {dest}")
    else:
        write_rows(target.path, header, written)
        target.written()
        log(f"запісана {done} радкоў у {target.path}")
    if stale:
        log(f"  арыгінал змяніўся ў {stale} — `extract` і `sync`, радкі пакінутыя як у гульні")
    if unknown:
        log(f"  не праверыць крыніцу ў {unknown} — у гульні няма адпаведнай табліцы")
    return {"strings": done, "stale": stale, "unknown": unknown}


def restore(game_dir: str, payload: dict, log=print):
    path = target_path(game_dir, payload["battletech_csv"])
    if os.path.exists(path) or os.path.exists(path + ".orig"):
        log(f"  {os.path.basename(path)}: {Target(path).restore()}")


def installed(game_dir: str, payload: dict) -> bool:
    return Target(target_path(game_dir, payload["battletech_csv"])).installed()
