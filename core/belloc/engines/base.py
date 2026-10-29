"""Інтэрфейс рухавіка і тое, што агульнае для ўсіх рухавікоў.

Рухавік — модуль у belloc/engines/ з такімі імёнамі:

  NAME = "unity-localization"         — значэнне "engine" у game.json
  SECTION = "unity"                   — секцыя game.json з наладамі рухавіка

  extract(loc, out=None)              — файлы гульні → local/<гульня>/source/:
                                        <мова>.json {табліца: {ключ: тэкст}}, па жаданні
                                        context.json і meta.json (версія, steam_buildid)
  payload(loc) -> dict                — палі payload, патрэбныя apply (без шляхоў машыны);
                                        можа замяніць "strings" (напр. хэшы ключоў)
  apply(game_dir, payload, out=None)  — наш пераклад → файлы гульні на месцы (.orig/.bel,
                                        install/target.py) або, з out, у іншую папку
  restore(game_dir, payload)          — вярнуць арыгіналы
  installed(game_dir, payload) -> bool
  check_path(payload) -> str          — шлях унутры каталога гульні, па якім яна пазнаецца

apply — адзін код для `belloc patch`, усталёўшчыка exe і лаўнчара: вынік у іх
аднолькавы байт у байт. Payload — JSON: толькі наш тэкст і апісанне гульні, ні
радка з файлаў гульні.

Новы рухавік — новы модуль тут і радок у ENGINES (engines/__init__.py).
"""
from __future__ import annotations

import json
import os

from .. import tables
from ..config import Loc

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


def patch(loc: Loc, engine, out: str | None = None):
    """Пераклад у гульню або, з out, у іншую папку (арыгіналы чытаюцца з гульні)."""
    return engine.apply(loc.game_dir, build_payload(loc, engine), out)


def restore(loc: Loc, engine):
    engine.restore(loc.game_dir, build_payload(loc, engine))
