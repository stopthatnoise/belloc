"""payload, apply, restore, installed: наш пераклад → файлы гульні (або --out)."""
from __future__ import annotations

import os
import shutil

from ...config import Loc
from ...install.paths import inside, name as one
from .common import SECTION


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


def files_dir(payload: dict) -> str:
    """Архіў для ручной усталёўкі (release.py): apply(out=…) піша толькі наш тэкст
    з payload, файлы гульні не чытае — вынік кладзецца сюды ў каталогу гульні."""
    return payload["paradox"]["replace_dir"]


def check_path(payload: dict) -> str:
    return payload["paradox"]["roots"][0]


def apply(game_dir: str, payload: dict, out: str | None = None, log=print) -> dict:
    """bel → <replace_dir>/<табліца>_l_<target>.yml. Ключы глабальныя: ключ, які
    ўжо запісаны з іншай табліцы, другі раз не пішацца. out — у гэтую папку."""
    s = payload["paradox"]
    target = one(s["target"])
    if out:
        dest = os.path.abspath(out)
    else:
        dest = inside(game_dir, s["replace_dir"], strict=True)
        remove_tree(dest)                   # наша папка — пішам нанова
    seen: set[str] = set()
    n_files = n_keys = 0
    for table, strings in sorted(payload["strings"].items()):
        items = [(k, v) for k, v in strings.items() if k not in seen]
        seen.update(k for k, _ in items)
        if not items:
            continue
        write_yml(inside(dest, table.lstrip("@") + f"_l_{target}.yml"), target, items)
        n_files += 1
        n_keys += len(items)
    log(f"запісана {n_keys} радкоў у {n_files} файлаў → {dest}")
    return {"strings": n_keys, "files": n_files}


def restore(game_dir: str, payload: dict, log=print):
    dest = inside(game_dir, payload["paradox"]["replace_dir"], strict=True)
    if os.path.isdir(dest):
        remove_tree(dest)
        log(f"папка перакладу выдаленая: {dest}")
    else:
        log("  пераклад не ўсталяваны")


def installed(game_dir: str, payload: dict) -> bool:
    return os.path.isdir(inside(game_dir, payload["paradox"]["replace_dir"], strict=True))
