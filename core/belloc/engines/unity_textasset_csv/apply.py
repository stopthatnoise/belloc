"""payload, apply, restore, installed: наш пераклад → файлы гульні (або --out)."""
from __future__ import annotations

import os
import shutil

from ...config import Loc
from ...install.target import Target
from .common import SECTION


def payload(loc: Loc) -> dict:
    return {"textasset_csv": loc.section(SECTION), "source_lang": loc.source_lang}


def check_path(payload: dict) -> str:
    return payload["textasset_csv"]["data_dir"]


def _paths(game_dir: str, payload: dict) -> dict[str, str]:
    from .textasset_csv import files
    s = payload["textasset_csv"]
    return {rel: os.path.join(game_dir, s["data_dir"], rel) for rel in files(s)}


def apply(game_dir: str, payload: dict, out: str | None = None, log=print) -> dict:
    """Тэкст, шрыфты, назва мовы, надпісы сцэн. out — папка для вынікаў, гульня не чапаецца."""
    from .textasset_csv import key_hash, patch_file
    s, tr = payload["textasset_csv"], payload["strings"]
    seen: set[str] = set()

    def keyf(key: str) -> str:
        k = key_hash(key)
        seen.add(k)
        return k

    targets = {}
    for rel, path in _paths(game_dir, payload).items():
        if not os.path.exists(path):
            raise SystemExit(f"Няма файла гульні {rel} у {os.path.dirname(path)}")
        targets[rel] = Target(path)
    # спачатку ўсе арыгіналы (свежыя .orig, калі Steam падмяніў файлы): надпісы
    # сцэн шукаюцца па арыгіналах усіх файлаў адразу
    bases = {rel: (t.source() if out else t.base()) for rel, t in targets.items()}
    log("Тэкст, шрыфты (І і Ў), назва мовы, надпісы ў сцэнах…")
    for rel, target in targets.items():
        base = bases[rel]
        dest = os.path.join(out, rel) if out else target.path
        lines = patch_file(s, payload["source_lang"], rel, base, dest, tr, keyf)
        if not out:
            if not lines:                   # у гэтай версіі гульні мяняць няма чаго
                shutil.copyfile(base, target.path)
            target.written()
        log(f"  {rel}: " + ("; ".join(lines) if lines else "без змен"))
    missing = sum(1 for rows in tr.values() for k in rows if k not in seen)
    if missing:
        log(f"  не знойдзена ў гэтай версіі гульні радкоў: {missing}")
    return {"missing": missing}


def restore(game_dir: str, payload: dict, log=print):
    for rel, path in _paths(game_dir, payload).items():
        if os.path.exists(path) or os.path.exists(path + ".orig"):
            log(f"  {rel}: {Target(path).restore()}")


def installed(game_dir: str, payload: dict) -> bool:
    s = payload["textasset_csv"]
    return Target(os.path.join(game_dir, s["data_dir"], s["assets"])).installed()
