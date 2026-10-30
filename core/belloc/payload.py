"""Payload — тое, што ідзе ў гульню: наш пераклад па ключах і апісанне гульні.

Адзін фармат для `belloc patch`, усталёўшчыка exe і лаўнчара. Толькі наш тэкст —
ні радка з файлаў гульні; шляхоў машыны распрацоўшчыка таксама няма.

  schema        версія фармату (SCHEMA); новы фармат — новы нумар
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
    """Шлях да файла assets (абсалютны шлях з local.json — як ёсць)."""
    root = p.get("assets_root")
    return os.path.join(root, rel) if root else rel


def dump(p: dict) -> dict:
    """Payload для запісу ў файл — без assets_root."""
    return {k: v for k, v in p.items() if k != "assets_root"}


def load(path: str) -> dict:
    """payload.json з дыска; assets — у папцы assets/ побач з ім (exe, пакет перакладу)."""
    with open(path, encoding="utf-8") as f:
        p = json.load(f)
    if p.get("assets"):
        p["assets_root"] = os.path.join(os.path.dirname(os.path.abspath(path)), "assets")
    return p
