"""extract: файлы гульні → local/<гульня>/source/."""
from __future__ import annotations

import json
import os

from ...config import Loc
from .common import archives, decode, key_hash, lua_strings, sec, set_of
from .landb import Landb
from .lenc import Blowfish7
from .ttarch2 import TTArch2


def source_dir(loc: Loc) -> str:
    s = sec(loc)
    return s.get("source") or loc.game(s.get("archive", "Archive"))


def landbs(folder: str, lang: str) -> dict[str, dict[str, TTArch2]]:
    """{набор: {сцэна: архіў}} — `<сцэна>_<lang>.landb` ва ўсіх архівах папкі.
    Без дэскрыптараў (арыгінал): у межах набору — апошні архіў па алфавіце
    (Update_* пасля базавых)."""
    out: dict[str, dict[str, TTArch2]] = {}
    suffix = f"_{lang}.landb"
    for p in archives(folder):
        arc = TTArch2(p)
        for name in arc.files:
            if name.endswith(suffix):
                out.setdefault(set_of(p.name), {})[name[:-len(suffix)]] = arc
    return out


def lua_texts(s: dict, folder: str) -> dict[str, dict[str, str]]:
    """Радкі `lua_text` (хэшы), знойдзеныя ў Lua архіваў папкі: {«набор/файл.lua»: {хэш: радок}}."""
    want = s.get("lua_text", {})
    if not want:
        return {}
    bf = Blowfish7(bytes.fromhex(s["lua_key"]))
    out: dict[str, dict[str, str]] = {}
    for p in archives(folder):
        arc = TTArch2(p)
        for name in sorted(set(want) & set(arc.files)):
            have = {}
            for x in lua_strings(arc.get(name), bf):
                text = x.decode("utf-8", "replace")
                have.setdefault(key_hash(text), text)
            table = f"{set_of(p.name)}/{name}"
            for h in want[name]:
                if h in have:
                    out.setdefault(table, {})[h] = have[h]
                else:
                    print(f"  {table}: радка з хэшам {h} няма")
    return out


def write_json(path: str, data):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def extract(loc: Loc, out: str | None = None):
    s = sec(loc)
    out = out or loc.source
    os.makedirs(out, exist_ok=True)
    src = source_dir(loc)
    langs = {loc.source_lang: s.get("lang", "english"), **s.get("hints", {})}
    meta = {"source": src, "steam_buildid": loc.steam_buildid(), "langs": {}}
    context: dict[str, dict[str, str]] = {}
    for code, lang in langs.items():
        res: dict[str, dict[str, str]] = {}
        dup = 0
        for set_name, scenes in sorted(landbs(src, lang).items()):
            for scene, arc in sorted(scenes.items()):
                table = f"{set_name}/{scene}"
                kv = res.setdefault(table, {})
                for r in Landb(arc.get(f"{scene}_{lang}.landb")).records:
                    key = str(r.id)
                    if key in kv:
                        dup += 1
                        continue
                    kv[key] = decode(r.text)
                    if code == loc.source_lang and r.speaker:
                        context.setdefault(table, {})[key] = decode(r.speaker)
        if code == loc.source_lang:
            res.update(lua_texts(s, src))
        write_json(os.path.join(out, f"{code}.json"), res)
        meta["langs"][code] = sum(len(kv) for kv in res.values())
        print(f"{code} ({lang}): {meta['langs'][code]} радкоў у {len(res)} табліцах"
              + (f", паўтораў ID: {dup}" if dup else ""))
    write_json(os.path.join(out, "context.json"), context)
    write_json(os.path.join(out, "meta.json"), meta)
    print(f"крыніца {src}, buildid {meta['steam_buildid']}")
