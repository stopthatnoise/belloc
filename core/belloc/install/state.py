"""Метка ўсталёўкі: <каталог гульні>/belloc.json — які пераклад і якой версіі стаіць.

Піша і выдаляе ўсё, што ставіць пераклад у гульню: усталёўшчык exe, лаўнчар,
`belloc patch`. Па ёй лаўнчар бачыць пераклад, пастаўлены любым з іх:

  {"game_id": "pony-island", "version": "1.0", "engine": "unity-textasset-csv",
   "installed_at": "2026-10-31", "steam_buildid": "25928685", "by": "installer"}

Метка — толькі што пра гэта памятаем мы. Ці пераклад сапраўды ў гульні,
кажа engine.installed() (па .bel): Steam пры абнаўленні затрэ нашы файлы, а
belloc.json не кране — гл. status().
"""
from __future__ import annotations

import datetime
import json
import os

from .. import steam

MARK = "belloc.json"


def path(game_dir: str) -> str:
    return os.path.join(game_dir, MARK)


def read(game_dir: str) -> dict | None:
    try:
        with open(path(game_dir), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def write(game_dir: str, payload: dict, by: str):
    mark = {"game_id": payload.get("game_id"), "version": payload.get("version"),
            "engine": payload.get("engine"), "installed_at": datetime.date.today().isoformat(),
            "steam_buildid": steam.buildid(game_dir, payload.get("steam_appid")), "by": by}
    with open(path(game_dir), "w", encoding="utf-8", newline="\n") as f:
        json.dump(mark, f, ensure_ascii=False, indent=1)


def remove(game_dir: str):
    if os.path.exists(path(game_dir)):
        os.remove(path(game_dir))


def status(game_dir: str, engine, payload: dict) -> tuple[str, dict | None]:
    """(стан, метка):
      "none"      перакладу няма;
      "installed" стаіць;
      "wiped"     метка ёсць, а нашых файлаў няма (Steam абнавіў або праверыў гульню);
      "unknown"   файлы нашы, а меткі няма (стаіла старая версія ўсталёўшчыка)."""
    mark = read(game_dir)
    if engine.installed(game_dir, payload):
        return ("installed" if mark else "unknown"), mark
    return ("wiped" if mark else "none"), mark
