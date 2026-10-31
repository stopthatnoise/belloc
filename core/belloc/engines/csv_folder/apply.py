"""payload, apply, restore, installed: наш пераклад → файлы гульні (або --out)."""
from __future__ import annotations

import csv
import os
import shutil

from ... import tables as ttables
from ...config import Loc
from .common import SECTION, _folder, _read, _tables


def payload(loc: Loc) -> dict:
    # src_hash перакладзеных радкоў: apply прапусціць тыя, чый арыгінал змяніўся
    hashes = {t: {r["key"]: r["src_hash"] for r in rows if r["bel"]}
              for t, rows in ttables.load_repo(loc).items()}
    return {"csv_folder": loc.section(SECTION), "source_lang": loc.source_lang,
            "src_hash": {t: h for t, h in hashes.items() if h}}


def check_path(payload: dict) -> str:
    s = payload["csv_folder"]
    return os.path.join(s["dir"], s["official"])


def apply(game_dir: str, payload: dict, out: str | None = None, log=print) -> dict:
    s = payload["csv_folder"]
    target = out or _folder(game_dir, s, "target")
    src_col = s["langs"][payload["source_lang"]]
    official = {}
    for t, p in _tables(_folder(game_dir, s, "official")):
        rows = _read(p)
        i = rows[0].index(src_col)
        official[t] = {r[0]: r[i] for r in rows[1:] if r}
    fixed, tr, hashes = s.get("fixed", {}), payload["strings"], payload.get("src_hash", {})
    pat = ttables.from_original(payload.get("from_original"))   # заглушкі [] ← кавалкі арыгінала
    os.makedirs(target, exist_ok=True)
    done = total = stale = 0
    for table, path in _tables(_folder(game_dir, s, "template")):
        rows = _read(path)
        rows[0][-1] = s["code"]
        bel, h = tr.get(table, {}), hashes.get(table, {})
        for row in rows[1:]:
            if not row or not row[0]:
                continue
            if row[0] in fixed:
                row[-1] = fixed[row[0]]
                continue
            if row[0] not in bel:
                continue
            total += 1
            en = official.get(table, {}).get(row[0])
            if en is not None and h.get(row[0]) and ttables.src_hash(en) != h[row[0]]:
                stale += 1          # гульня абнавілася пасля перакладу
                continue
            row[-1] = ttables.expand(bel[row[0]], en or "", pat) if pat else bel[row[0]]
            done += 1
        with open(os.path.join(target, f"{table}.csv"), "w", encoding="utf-8", newline="") as f:
            csv.writer(f, lineterminator="\r\n").writerows(rows)
    log(f"запісана {done}/{total} у {target}"
        + (f"; арыгінал змяніўся ў {stale} — `extract` і `sync`" if stale else ""))
    return {"strings": done, "stale": stale}


def restore(game_dir: str, payload: dict, log=print):
    target = _folder(game_dir, payload["csv_folder"], "target")
    if os.path.isdir(target):
        shutil.rmtree(target)
        log(f"выдалена {target}")
    else:
        log("  пераклад не ўсталяваны")


def installed(game_dir: str, payload: dict) -> bool:
    return os.path.isdir(_folder(game_dir, payload["csv_folder"], "target"))
