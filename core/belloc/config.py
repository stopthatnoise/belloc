"""Канфіг гульні: games/<гульня>/game.json + лакальнае local/<гульня>/.

У рэпазіторыі (games/<гульня>/) — толькі наша:

    game.json        канфіг (поля — ніжэй і ў docstring рухавіка)
    translation/     пераклад: key, src_hash, bel, note (гл. tables.py)
    glossary.json    назвы
    lint_allow.txt   белы спіс лінтэра (дадаецца да агульнага)

Лакальна (local/<гульня>/, у .gitignore; іншае месца — зменная BELLOC_LOCAL):

    local.json       налады гэтай машыны: {"game_dir": "…"} і перавызначэнні
                     секцый game.json (напр. ключы рухавіка: {"unreal": {"aes_key": …}})
    source/          выцягнутае з гульні: <мова>.json, context.json, meta.json
    glossary.local.json  лакальны слой гласарыя — запісы з цытатамі тэксту гульні (glossary.py)
    build/           прамежкавыя вынікі
    work/            файлы пачак для агентаў

game.json:

    {"name": "Silver Pines", "engine": "unity-localization", "steam_appid": 0,
     "source_lang": "en", "hint_lang": "ru", "<секцыя рухавіка>": {…}}

Каталог гульні: game_dir з local.json, інакш — бібліятэкі Steam па steam_appid.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import cached_property

from . import steam
from .install.paths import inside

PKG = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(PKG))
GAMES = os.path.join(ROOT, "games")


def local_root() -> str:
    return os.environ.get("BELLOC_LOCAL") or os.path.join(ROOT, "local")


@dataclass
class Loc:
    id: str                           # імя папкі: silver-pines
    dir: str                          # games/<id>
    local: str                        # local/<id>
    name: str
    engine: str
    source_lang: str = "en"           # з чаго перакладаем
    hint_lang: str | None = "ru"      # падказка (можа не быць)
    steam_appid: int | None = None
    raw: dict = field(default_factory=dict)
    local_raw: dict = field(default_factory=dict)

    # --- рэпазіторый: games/<id>/
    def path(self, *parts: str) -> str:
        """Файл у games/<id>/; шлях з game.json па-за ёй (`../…`) — памылка: PR з такім
        шляхам інакш чытаў бы файлы машыны мейнтейнера (і нёс бы іх у рэліз)."""
        return inside(self.dir, *parts)

    @property
    def translation(self) -> str:
        return self.path("translation")

    @property
    def glossary(self) -> str:
        return self.path(self.raw.get("glossary", "glossary.json"))

    @property
    def glossaries(self) -> list[str]:
        """Слаі гласарыя, што ёсць: публічны і лакальны (glossary.py)."""
        files = [self.glossary, self.local_path("glossary.local.json")]
        return [f for f in files if os.path.exists(f)]

    @property
    def lint_allow(self) -> list[str]:
        files = [os.path.join(PKG, "lint", "allow_common.txt"),
                 self.path(self.raw.get("lint_allow", "lint_allow.txt"))]
        return [f for f in files if os.path.exists(f)]

    # --- лакальна: local/<id>/
    def local_path(self, *parts: str) -> str:
        return os.path.join(self.local, *parts)

    @property
    def source(self) -> str:
        return self.local_path("source")

    @property
    def build(self) -> str:
        return self.local_path("build")

    @property
    def work(self) -> str:
        return self.local_path("work")

    # --- гульня
    @cached_property
    def game_dir(self) -> str:
        d = self.local_raw.get("game_dir")
        if d:
            return d
        if self.steam_appid:
            found, _ = steam.find_game(self.steam_appid)
            if found:
                return found
        raise SystemExit(
            f"{self.id}: гульня не знойдзена ў Steam — пакладзіце шлях у "
            f"{self.local_path('local.json')}: {{\"game_dir\": \"…\"}}")

    def game(self, *parts: str) -> str:
        return os.path.join(self.game_dir, *parts)

    def steam_buildid(self) -> str | None:
        return steam.buildid(self.game_dir, self.steam_appid)

    def section(self, name: str) -> dict:
        """Секцыя рухавіка (напр. "unity") з game.json, перавызначаная local.json."""
        if name not in self.raw and name not in self.local_raw:
            raise SystemExit(f"{self.id}: у game.json няма секцыі «{name}»")
        return {**self.raw.get(name, {}), **self.local_raw.get(name, {})}


def resolve(name_or_path: str) -> str:
    """'silver-pines' → games/silver-pines; папка з game.json — як ёсць."""
    if os.path.isfile(os.path.join(name_or_path, "game.json")):
        return os.path.abspath(name_or_path)
    cand = os.path.join(GAMES, name_or_path)
    if os.path.isfile(os.path.join(cand, "game.json")):
        return cand
    known = sorted(os.listdir(GAMES)) if os.path.isdir(GAMES) else []
    raise SystemExit(f"гульня «{name_or_path}» не знойдзена; ёсць: {', '.join(known) or '—'}")


def _json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load(name_or_path: str) -> Loc:
    d = resolve(name_or_path)
    gid = os.path.basename(d)
    raw = _json(os.path.join(d, "game.json"))
    local = os.path.join(local_root(), gid)
    return Loc(id=gid, dir=d, local=local, name=raw["name"], engine=raw["engine"],
               source_lang=raw.get("source_lang", "en"), hint_lang=raw.get("hint_lang", "ru"),
               steam_appid=raw.get("steam_appid"), raw=raw,
               local_raw=_json(os.path.join(local, "local.json")))
