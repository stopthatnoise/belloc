"""extract: файлы гульні → local/<гульня>/source/."""
from __future__ import annotations

import json
import os
import re

from ...config import Loc
from .common import SECTION, _folder, _read, _tables


def _write_json(path: str, data):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def extract(loc: Loc, out: str | None = None):
    s = loc.section(SECTION)
    out = out or loc.source
    os.makedirs(out, exist_ok=True)
    skip = re.compile(s["skip"]) if s.get("skip") else None
    fixed = s.get("fixed", {})
    by_lang: dict[str, dict] = {l: {} for l in s["langs"]}
    ctx: dict[str, dict] = {}
    for table, path in _tables(_folder(loc.game_dir, s, "official")):
        rows = _read(path)
        head = rows[0]
        col = {l: head.index(c) for l, c in s["langs"].items()}
        first = min(col.values())
        extra = list(range(1, first))
        for l in by_lang:
            by_lang[l][table] = {}
        for r in rows[1:]:
            if not r or not r[0] or r[0] in fixed or (skip and skip.match(r[0])):
                continue
            for l, i in col.items():
                by_lang[l][table][r[0]] = r[i]
            note = ", ".join(f"{head[i]}={r[i]}" for i in extra if r[i])
            if note:
                ctx.setdefault(table, {})[r[0]] = note
    for l, data in by_lang.items():
        _write_json(os.path.join(out, f"{l}.json"), data)
    _write_json(os.path.join(out, "context.json"), ctx)
    src = by_lang[loc.source_lang]
    meta = {"steam_buildid": loc.steam_buildid(), "rows": sum(len(v) for v in src.values()),
            "tables": {t: len(v) for t, v in src.items()}}
    _write_json(os.path.join(out, "meta.json"), meta)
    print(f"радкоў {meta['rows']} у {len(src)} табліцах; buildid {meta['steam_buildid']}")
