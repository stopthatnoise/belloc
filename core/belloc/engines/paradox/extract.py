"""extract: файлы гульні → local/<гульня>/source/."""
from __future__ import annotations

import json
import os
import re

from ...config import Loc
from .common import SECTION


LINE = re.compile(r'^\s*([^\s:#"]+):(\d*)\s*"(.*)"\s*(?:#.*)?$')


HEADER = re.compile(r'^\s*l_(\w+):\s*(?:#.*)?$')


def parse(path: str) -> dict[str, str]:
    """{ключ: тэкст} аднаго yml, тэкст — як у файле (з \\n і г.д.)."""
    out = {}
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#") or HEADER.match(s):
                continue
            m = LINE.match(line)
            if m:
                out[m.group(1)] = m.group(3)
            else:
                print(f"  ? не разабраны радок: {os.path.basename(path)}: {s[:80]}")
    return out


def files(game_dir: str, s: dict, lang: str):
    """(табліца, шлях) усіх файлаў мовы ва ўсіх каранях."""
    folder = s["langs"][lang]
    suffix = re.compile(rf"[_ ]*l_{folder}\.yml$")
    for root in s.get("roots", ["game"]):
        base = os.path.join(game_dir, root, "localization")
        for dirpath, dirs, names in os.walk(base):
            dirs[:] = sorted(d for d in dirs if d != "replace")
            rel_dir = os.path.relpath(dirpath, base).replace(os.sep, "/")
            parts = [] if rel_dir == "." else rel_dir.split("/")
            in_lang = bool(parts) and parts[0] == folder
            for n in sorted(names):
                if not n.endswith(".yml"):
                    continue
                if suffix.search(n):
                    stem = suffix.sub("", n)
                elif in_lang:              # ru_custom_loc.yml без суфікса
                    stem = n[:-4]
                else:
                    continue
                rel = "/".join((parts[1:] if in_lang else parts) + [stem])
                yield ("" if root == "game" else f"@{root}/") + rel, os.path.join(dirpath, n)


def game_version(game_dir: str) -> str | None:
    p = os.path.join(game_dir, "launcher", "launcher-settings.json")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f).get("rawVersion")
    return None


def extract(loc: Loc, out: str | None = None):
    s = loc.section(SECTION)
    out = out or loc.source
    os.makedirs(out, exist_ok=True)
    langs = s.get("extract_langs", [loc.source_lang])
    src: dict[str, dict[str, str]] = {}
    for table, path in files(loc.game_dir, s, loc.source_lang):
        src.setdefault(table, {}).update(parse(path))
    src = {t: d for t, d in src.items() if d}
    meta = {"game_version": game_version(loc.game_dir), "steam_buildid": loc.steam_buildid(),
            "tables": len(src), "strings": {}}
    for lang in langs:
        if lang == loc.source_lang:
            data = src
        else:
            flat: dict[str, str] = {}
            for _, path in files(loc.game_dir, s, lang):
                flat.update(parse(path))
            data = {t: {k: flat[k] for k in d if k in flat} for t, d in src.items()}
        with open(os.path.join(out, f"{lang}.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=0)
        meta["strings"][lang] = sum(len(d) for d in data.values())
        print(f"{lang}: {meta['strings'][lang]} радкоў у {len(data)} табліцах")
    with open(os.path.join(out, "meta.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print("версія гульні:", meta["game_version"], "buildid:", meta["steam_buildid"])
