"""Штатная CSV-лакалізацыя гульні: папка мовы з CSV па ID (Esoteric Ebb 1.3).

Гульня чытае мовы з `<dir>/<папка>/*.csv`: тыя ж файлы і ключы, што ў
`Template/`, апошні слупок — код мовы. Арыгінал — у `Official/*.csv`
(слупкі мовы, напр. `EN`, `CH`). Слупкі паміж ID і першай мовай (`Area`,
`Speaker`, `Type`, `GAME_DATA`) — кантэкст: extract кладзе іх у context.json
(`Speaker=…, Type=LINE`).

Секцыя "csv_folder" у game.json:
  dir       "Esoteric Ebb_Data/StreamingAssets/Localization"
  official  "Official"           — арыгінал
  template  "Template"           — шаблон папкі мовы (апошні слупок — пусты)
  target    "Belarusian"         — наша папка (цалкам наша; restore выдаляе)
  code      "BE"                 — код мовы ў загалоўку CSV
  langs     {"en": "EN"}         — мова CSV → слупок Official
  fixed     {"LanguageDropdown": "Беларуская", …} — радкі канфігурацыі мовы,
            пішуцца як ёсць і ў source/ не трапляюць
  skip      "^Glossary_…$"       — ID, якія пакідаем пустымі (бярэцца запасная
            мова гульні); у source/ таксама не трапляюць

Табліца = імя файла без .csv, ключ = ID (першы слупок).

apply: шаблон гульні + наш bel → папка target. Радок, чый арыгінал у гульні
змяніўся пасля перакладу (src_hash у payload не супадае), застаецца пустым —
гульня возьме запасную мову; трэба `extract` і `sync`.
"""
from __future__ import annotations

import csv
import glob
import json
import os
import re
import shutil

from .. import tables as ttables
from ..config import Loc

NAME = "csv-folder"
SECTION = "csv_folder"


def _read(path: str) -> list[list[str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.reader(f))


def _write_json(path: str, data):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def _tables(path: str) -> list[tuple[str, str]]:
    return [(os.path.basename(p)[:-4], p) for p in sorted(glob.glob(os.path.join(path, "*.csv")))]


def _folder(game_dir: str, s: dict, name: str) -> str:
    return os.path.join(game_dir, s["dir"], s[name])


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


# ---------------------------------------------------------------- payload і apply

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
            row[-1] = bel[row[0]]
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
