"""Payload — тое, што ідзе ў гульню: наш пераклад па ключах і апісанне гульні.

Адзін фармат для `belloc patch`, усталёўшчыка exe і лаўнчара. Толькі наш тэкст —
ні радка з файлаў гульні; шляхоў машыны распрацоўшчыка таксама няма.

  schema        версія фармату (SCHEMA); новы фармат — новы нумар
  engine        імя рухавіка ("engine" з game.json)
  game_id, game імя папкі ў games/ і назва гульні
  steam_appid, steam_buildid
                па чым шукаць гульню і пад якую яе версію сабраны пераклад
  strings       {табліца: {ключ: bel}} — толькі перакладзенае
  …             палі рухавіка (engines/<рухавік>/apply.py: payload)
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
    return p
