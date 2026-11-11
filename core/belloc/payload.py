"""Payload — тое, што ідзе ў гульню: наш пераклад па ключах і апісанне гульні.

Адзін фармат для `belloc patch`, усталёўшчыка exe і лаўнчара. Толькі наш тэкст —
ні радка з файлаў гульні; шляхоў машыны распрацоўшчыка таксама няма.

  schema        версія фармату, якую павінен разумець той, хто ставіць: 1 — базавы;
                рухавік падымае яе, калі стары код прапусціў бы новае поле і
                зламала б гульню (2 — unity-localization з crc_catalog). SCHEMA —
                найбольшая версія, якую разумее гэты код
  engine        імя рухавіка ("engine" з game.json)
  game_id, game імя папкі ў games/ і назва гульні
  steam_appid, steam_buildid
                па чым шукаць гульню і пад якую яе версію сабраны пераклад
  version       версія перакладу (release.version у game.json; без яе — None)
  strings       {табліца: {ключ: bel}} — толькі перакладзенае
  from_original рэгулярка кавалкаў арыгінала (tables.py): у strings яны — заглушка `[]`,
                рухавік (FROM_ORIGINAL = True) падстаўляе іх з файлаў гульні
  assets        [шлях адносна games/<гульня>/] — нашы файлы, патрэбныя apply (вольныя
                шрыфты і іх ліцэнзіі); усталёўшчык нясе іх побач з payload
  …             палі рухавіка (engines/<рухавік>/apply.py: payload)

assets_root, from_package — толькі ў памяці, у файл payload не пішуцца: адкуль чытаць
assets (games/<гульня>/ у `belloc patch`, папка з файламі ў усталёўшчыку) і ці payload
прыйшоў з пакета/exe (тады абсалютныя шляхі assets не дапушчаюцца).
"""
from __future__ import annotations

import json
import os

from . import tables
from .config import Loc

SCHEMA = 2


def build_payload(loc: Loc, engine) -> dict:
    """Payload гульні: агульныя палі + палі рухавіка."""
    meta_path = os.path.join(loc.source, "meta.json")
    meta = {}
    if os.path.exists(meta_path):
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
    p = {"schema": 1, "engine": engine.NAME, "game_id": loc.id, "game": loc.name,
         "steam_appid": loc.steam_appid, "steam_buildid": meta.get("steam_buildid"),
         "version": loc.raw.get("release", {}).get("version"),
         "strings": {t: rows for t, rows in tables.translation_by_key(loc).items() if rows}}
    if loc.raw.get("from_original"):
        if not getattr(engine, "FROM_ORIGINAL", False):
            raise SystemExit(f"{engine.NAME}: from_original рухавік не падтрымлівае")
        p["from_original"] = loc.raw["from_original"]
    p.update(engine.payload(loc))
    if p.get("assets"):
        p["assets_root"] = loc.dir
    return p


def asset(p: dict, rel: str) -> str:
    """Шлях да файла assets (абсалютны шлях з local.json — як ёсць). Адносны шлях не
    выходзіць за assets_root: інакш `../../…` у game.json занёс бы ў публічны пакет
    любы файл машыны, на якой ён збіраецца."""
    root = p.get("assets_root")
    if not root:
        return rel
    if os.path.isabs(rel) and not p.get("from_package"):
        return rel
    path = os.path.join(root, rel)
    base = os.path.normcase(os.path.abspath(root)).rstrip(os.sep) + os.sep
    if not os.path.normcase(os.path.abspath(path) + os.sep).startswith(base):
        raise SystemExit(f"файл assets па-за {root}: {rel}")
    return path


def dump(p: dict) -> dict:
    """Payload для запісу ў файл — без assets_root."""
    return {k: v for k, v in p.items() if k not in ("assets_root", "from_package")}


def load(path: str) -> dict:
    """payload.json з дыска; assets — у папцы assets/ побач з ім (exe, пакет перакладу)."""
    with open(path, encoding="utf-8") as f:
        p = json.load(f)
    p["assets_root"] = os.path.join(os.path.dirname(os.path.abspath(path)), "assets")
    p["from_package"] = True                # абсалютных шляхоў assets тут не бывае
    return p
