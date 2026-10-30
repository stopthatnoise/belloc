"""Payload — тое, што ідзе ў гульню: наш пераклад па ключах і апісанне гульні.

Адзін фармат для `belloc patch`, усталёўшчыка exe і лаўнчара. Толькі наш тэкст —
ні радка з файлаў гульні; шляхоў машыны распрацоўшчыка таксама няма.

  schema        версія фармату (SCHEMA); новы фармат — новы нумар
  engine        імя рухавіка ("engine" з game.json)
  game_id, game імя папкі ў games/ і назва гульні
  steam_appid, steam_buildid
                па чым шукаць гульню і пад якую яе версію сабраны пераклад
  strings       {табліца: {ключ: bel}} — толькі перакладзенае
  assets        [шлях адносна games/<гульня>/] — нашы файлы, патрэбныя apply (вольныя
                шрыфты і іх ліцэнзіі); усталёўшчык нясе іх побач з payload
  …             палі рухавіка (engines/<рухавік>/apply.py: payload)

assets_root — толькі ў памяці, у файл payload не пішацца: адкуль чытаць assets
(games/<гульня>/ у `belloc patch`, папка з файламі ў усталёўшчыку).
"""
from __future__ import annotations

import json
import os

from . import tables
from .config import Loc

SCHEMA = 1


def build_payload(loc: Loc, engine) -> dict:
    """Payload гульні: агульныя палі + палі рухавіка."""
    meta_path = os.path.join(loc.source, "meta.json")
    meta = {}
    if os.path.exists(meta_path):
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
    p = {"schema": SCHEMA, "engine": engine.NAME, "game_id": loc.id, "game": loc.name,
         "steam_appid": loc.steam_appid, "steam_buildid": meta.get("steam_buildid"),
         "strings": {t: rows for t, rows in tables.translation_by_key(loc).items() if rows}}
    p.update(engine.payload(loc))
    if p.get("assets"):
        p["assets_root"] = loc.dir
    return p


def asset(p: dict, rel: str) -> str:
    """Шлях да файла assets (абсалютны шлях з local.json — як ёсць)."""
    root = p.get("assets_root")
    return os.path.join(root, rel) if root else rel


def dump(p: dict) -> dict:
    """Payload для запісу ў файл — без assets_root."""
    return {k: v for k, v in p.items() if k != "assets_root"}
