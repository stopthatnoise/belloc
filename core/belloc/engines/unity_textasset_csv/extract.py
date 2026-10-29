"""extract: файлы гульні → local/<гульня>/source/."""
from __future__ import annotations

import json
import os

from ...config import Loc
from ...install.target import Target
from .common import SECTION


def _write_json(path: str, data):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def _hashed(table: str, keys) -> dict[str, str]:
    """{ключ: хэш} з праверкай, што хэшы ў табліцы не супадаюць."""
    from .textasset_csv import key_hash
    res = {k: key_hash(k) for k in keys}
    if len(set(res.values())) != len(res):
        raise SystemExit(f"{table}: key_hash — калізія ключоў")
    return res


def extract(loc: Loc, out: str | None = None):
    from . import scene_text
    from ..unity.bundles import unity_version
    from .textasset_csv import layout, read_table, scan_scenes
    s = loc.section(SECTION)
    out = out or loc.source
    os.makedirs(out, exist_ok=True)
    data_dir = loc.game(s["data_dir"])
    path = Target(os.path.join(data_dir, s["assets"])).source()     # не наш патч
    _, _, _, text = read_table(path, s["textasset"])
    rows = layout(s, loc.source_lang, text)
    langs = list(s["langs"])
    by_lang: dict[str, dict] = {l: {} for l in langs}
    ctx: dict[str, dict] = {}
    pos: dict[str, dict] = {}
    for n, table, key, vals, note in rows:
        for l in langs:
            by_lang[l].setdefault(table, {})[key] = vals[l]
        pos.setdefault(table, {})[key] = n
        if note:
            ctx.setdefault(table, {})[key] = note
    if "scenes" in s:
        found = scan_scenes(s, loc.source_lang, rows, data_dir)
        for l in langs:
            by_lang[l][scene_text.TABLE] = {t: (t if l == loc.source_lang else "") for t in found}
        ctx[scene_text.TABLE] = {t: scene_text.context(w) for t, w in found.items()}
        print(f"надпісаў у сцэнах па-за CSV: {len(found)}")

    hashes = {t: _hashed(t, kv) for t, kv in by_lang[loc.source_lang].items()}

    def h(d):
        return {t: {hashes[t][k]: v for k, v in kv.items()} for t, kv in d.items()}
    for l in langs:
        _write_json(os.path.join(out, f"{l}.json"), h(by_lang[l]))
    _write_json(os.path.join(out, "context.json"), h(ctx))
    _write_json(os.path.join(out, "rows.json"), h(pos))
    meta = {"unity": unity_version(data_dir), "steam_buildid": loc.steam_buildid(), "rows": len(rows),
            "tables": {t: len(v) for t, v in by_lang[loc.source_lang].items()},
            "with_context": sum(len(v) for v in ctx.values())}
    _write_json(os.path.join(out, "meta.json"), meta)
    print(f"радкоў {len(rows)} у {len(meta['tables'])} табліцах, з кантэкстам "
          f"{meta['with_context']}; Unity {meta['unity']}, buildid {meta['steam_buildid']}")
