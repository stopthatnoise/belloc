"""CSV-табліца ў TextAsset класічных .assets Unity (Pony Island) — фармат у unity/textasset_csv.py.

Секцыя "textasset_csv" у game.json:
  data_dir     "PonyIsland_Data"
  assets       "resources.assets"           — файл з TextAsset (адносна data_dir)
  textasset    "localization"               — m_Name
  header_row   1                            — радок шапкі (з 0); ён і вышэй — не тэкст
  id_column    "STRING ID"
  note_column  0                            — заўвагі (кантэкст) і загалоўкі раздзелаў
  langs        {"en": "ENGLISH", "ru": "RUSSIAN"}
  target       "ru"                         — чый слупок перапісвае apply
  sections     {"MAIN MENU": "01-menu", …}  — загаловак у слупку заўваг → табліца
  scenes       {"ignore": […], "ignore_re": […]}  — надпісы сцэн па-за CSV (unity/scene_text.py)
  patch        {"files": ["level0", …],      — іншыя файлы, апроч assets
                "fonts": ["…"],              — Font-асеты, куды дадаць І/і/Ў/ў (unity/dyn_fonts.py)
                "ui_text": {"Pусский": "Беларуская"}}  — замены радкоў у MonoBehaviour

**Ключ радка — хэш** (unity/textasset_csv.key_hash): у CSV гульні ключ — англійскі тэкст
(STRING ID ёсць рэдка; паўторы — «тэкст #2»), а тэкст гульні ў рэпазіторый не трапляе.
apply шукае радкі гульні па тым жа хэшы.

Вынік extract (local/<гульня>/source/):
  <мова>.json   {табліца: {хэш ключа: тэкст}}
  context.json  {табліца: {хэш: заўвага}} — заўвагі слупка 0 і пазнакі дубляў
  rows.json     {табліца: {хэш: нумар радка CSV}} — для даведкі
  meta.json     версія Unity, buildid Steam, колькасці

apply піша ўсё адным праходам: bel → слупок target TextAsset-а, І/і/Ў/ў у TTF шрыфтоў
patch.fonts, patch.ui_text (назва мовы), надпісы сцэн (табліца 19-scenes) — усе правы
трапляюць у адны і тыя ж файлы.
"""
from __future__ import annotations

import json
import os
import shutil

from ..config import Loc
from ..install.target import Target

NAME = "unity-textasset-csv"
SECTION = "textasset_csv"


def _write_json(path: str, data):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def _hashed(table: str, keys) -> dict[str, str]:
    """{ключ: хэш} з праверкай, што хэшы ў табліцы не супадаюць."""
    from ..unity.textasset_csv import key_hash
    res = {k: key_hash(k) for k in keys}
    if len(set(res.values())) != len(res):
        raise SystemExit(f"{table}: key_hash — калізія ключоў")
    return res


def extract(loc: Loc, out: str | None = None):
    from ..unity import scene_text
    from ..unity.bundles import unity_version
    from ..unity.textasset_csv import layout, read_table, scan_scenes
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


# ---------------------------------------------------------------- payload і apply

def payload(loc: Loc) -> dict:
    return {"textasset_csv": loc.section(SECTION), "source_lang": loc.source_lang}


def check_path(payload: dict) -> str:
    return payload["textasset_csv"]["data_dir"]


def _paths(game_dir: str, payload: dict) -> dict[str, str]:
    from ..unity.textasset_csv import files
    s = payload["textasset_csv"]
    return {rel: os.path.join(game_dir, s["data_dir"], rel) for rel in files(s)}


def apply(game_dir: str, payload: dict, out: str | None = None, log=print) -> dict:
    """Тэкст, шрыфты, назва мовы, надпісы сцэн. out — папка для вынікаў, гульня не чапаецца."""
    from ..unity.textasset_csv import key_hash, patch_file
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
