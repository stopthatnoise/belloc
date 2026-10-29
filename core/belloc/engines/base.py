"""Інтэрфейс рухавіка і тое, што агульнае для ўсіх рухавікоў.

Рухавік — папка belloc/engines/<рухавік>/ (common.py, extract.py, apply.py, фарматы);
яе __init__.py выстаўляе такія імёны:

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

Новы рухавік — новая папка з той жа раскладкай і радок у ENGINES (engines/__init__.py).
Payload — payload.py.
"""
from __future__ import annotations

from ..config import Loc
from ..payload import build_payload  # noqa: F401 — base.build_payload для выклікаў


def patch(loc: Loc, engine, out: str | None = None):
    """Пераклад у гульню або, з out, у іншую папку (арыгіналы чытаюцца з гульні)."""
    return engine.apply(loc.game_dir, build_payload(loc, engine), out)


def restore(loc: Loc, engine):
    engine.restore(loc.game_dir, build_payload(loc, engine))
