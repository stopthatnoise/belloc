"""Лакалізацыя гульняў Paradox (Clausewitz/Jomini: Crusader Kings 3 і інш.).

Як уладкавана ў гульні:
  <корань>/localization/<мова>/**/<імя>_l_<мова>.yml
    UTF-8 з BOM (без BOM гульня падае: «Missing UTF8 BOM»), першы радок
    `l_<мова>:`, далей ` ключ:N "тэкст"` (N — нумар версіі, гульня яго
    ігнаруе; бывае і без N). Значэнне — ад першага да АПОШНЯГА двукосся
    радка: унутраныя " не экрануюцца. Пасля — магчымы каментар `# …`.
  Ключы глабальныя: файл/папка ролі не грае.
  Каранёў некалькі (віртуальная ФС): game/, jomini/, clausewitz/.
  `localization/replace/` — файлы адтуль перазапісваюць ключы, што ўжо ёсць.

Лаўнчар скідае невядомыя мовы, таму мы падмяняем рускую: пішам беларускі
тэкст у `game/localization/replace/russian/bel/…_l_russian.yml`, толькі
перакладзеныя ключы — астатняе застаецца рускім.

Секцыя "paradox" у game.json:
  roots          ["game", "jomini", "clausewitz"] — дзе шукаць localization/
  langs          {"en": "english", "ru": "russian"} — код → папка/суфікс
  extract_langs  ["en", "ru"]
  target         "russian"                         — якую мову падмяняем
  replace_dir    "game/localization/replace/russian/bel" — наша папка (цалкам наша)

Табліцы — шлях англійскага файла без `_l_english.yml` адносна
localization/<мова>/; файлы не з каранёвай `game/` атрымліваюць прэфікс
`@jomini/`, `@clausewitz/`. Падказка (ru) бярэцца па ключы з усіх рускіх
файлаў, не па імені файла.

Напісана і праверана на Crusader Kings III 1.20.1.1.
"""
from __future__ import annotations

import json
import os
import re
import shutil

from ..config import Loc

NAME = "paradox"
SECTION = "paradox"

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


# ---------------------------------------------------------------- payload і apply

def yml_value(text: str) -> str:
    """Сапраўдныя пераносы (калі трапілі ў пераклад) → \\n, як у файлах гульні."""
    return text.replace("\r\n", "\\n").replace("\n", "\\n")


def write_yml(path: str, lang: str, items: list[tuple[str, str]]):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="\n") as f:
        f.write(f"l_{lang}:\n")
        for key, text in items:
            f.write(f' {key}:0 "{yml_value(text)}"\n')


def remove_tree(path: str):
    if os.path.isdir(path):
        shutil.rmtree(path)
    # пустыя replace/<мова>/, replace/ — таксама нашы
    parent = os.path.dirname(path)
    for _ in range(2):
        if os.path.isdir(parent) and not os.listdir(parent):
            os.rmdir(parent)
            parent = os.path.dirname(parent)


def payload(loc: Loc) -> dict:
    s = loc.section(SECTION)
    return {"paradox": {"target": s["target"], "replace_dir": s["replace_dir"],
                        "roots": s.get("roots", ["game"])}}


def check_path(payload: dict) -> str:
    return payload["paradox"]["roots"][0]


def apply(game_dir: str, payload: dict, out: str | None = None, log=print) -> dict:
    """bel → <replace_dir>/<табліца>_l_<target>.yml. Ключы глабальныя: ключ, які
    ўжо запісаны з іншай табліцы, другі раз не пішацца. out — у гэтую папку."""
    s = payload["paradox"]
    target = s["target"]
    if out:
        dest = os.path.abspath(out)
    else:
        dest = os.path.join(game_dir, s["replace_dir"])
        remove_tree(dest)                   # наша папка — пішам нанова
    seen: set[str] = set()
    n_files = n_keys = 0
    for table, strings in sorted(payload["strings"].items()):
        items = [(k, v) for k, v in strings.items() if k not in seen]
        seen.update(k for k, _ in items)
        if not items:
            continue
        write_yml(os.path.join(dest, table.lstrip("@") + f"_l_{target}.yml"), target, items)
        n_files += 1
        n_keys += len(items)
    log(f"запісана {n_keys} радкоў у {n_files} файлаў → {dest}")
    return {"strings": n_keys, "files": n_files}


def restore(game_dir: str, payload: dict, log=print):
    dest = os.path.join(game_dir, payload["paradox"]["replace_dir"])
    if os.path.isdir(dest):
        remove_tree(dest)
        log(f"папка перакладу выдаленая: {dest}")
    else:
        log("  пераклад не ўсталяваны")


def installed(game_dir: str, payload: dict) -> bool:
    return os.path.isdir(os.path.join(game_dir, payload["paradox"]["replace_dir"]))


# ---------------------------------------------------------------- шрыфты

FONT_FILES = ("game/fonts/fonts.font", "clausewitz/fonts/cw_fonts.font")
BEL_CHARS = "ІіЎў«»’—"


def font_groups(game_dir: str, lang: str):
    """(файл .font, імя fontfiles, [шляхі шрыфтоў]) для груп з l_<lang>."""
    for ff in FONT_FILES:
        p = os.path.join(game_dir, ff)
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8-sig") as f:
            text = f.read()
        name = None
        for m in re.finditer(r'name\s*=\s*"([^"]+)"|languages\s*=\s*\{([^}]*)\}\s*files\s*=\s*\{([^}]*)\}',
                             text):
            if m.group(1):
                name = m.group(1)
            elif f'"l_{lang}"' in m.group(2):
                yield ff, name, re.findall(r'"([^"]+)"', m.group(3))


def find_font(game_dir: str, s: dict, rel: str) -> str | None:
    for root in s.get("roots", ["game"]):
        p = os.path.join(game_dir, root, rel)
        if os.path.exists(p):
            return p
    return None


def fonts_report(loc: Loc, chars: set[int] | None = None):
    """Для кожнай групы шрыфтоў падменнай мовы: які шрыфт дае кожную літару."""
    from fontTools.ttLib import TTFont
    s = loc.section(SECTION)
    want = sorted(chars) if chars else [ord(c) for c in BEL_CHARS]
    cmaps: dict[str, set[int]] = {}
    bad = 0
    for ff, name, chain in font_groups(loc.game_dir, s["target"]):
        missing = set(want)
        first_missing = None
        for rel in chain:
            p = find_font(loc.game_dir, s, rel)
            if p is None:
                print(f"  {name}: файла няма — {rel}")
                continue
            if p not in cmaps:
                cmaps[p] = set(TTFont(p, lazy=True).getBestCmap())
            if first_missing is None:
                first_missing = "".join(chr(c) for c in want if c not in cmaps[p])
            missing -= cmaps[p]
        head = os.path.basename(chain[0]) if chain else "—"
        status = "ok" if not missing else "НЯМА: " + "".join(chr(c) for c in sorted(missing))
        if missing:
            bad += 1
        note = f" (асноўны {head} без: {first_missing})" if first_missing else ""
        print(f"  {os.path.basename(ff):14} {name:24} {status}{note}")
    print("усе групы пакрываюць літары" if not bad else f"груп з дзіркамі: {bad}")
