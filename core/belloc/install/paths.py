"""Шляхі з payload і каталога — толькі ўнутры папкі гульні.

payload і каталог прыходзяць з сеткі (або з PR у game.json): шлях накшталт
"../../Users/…", "C:/Windows/…" ці "\\\\server\\share" даў бы рухавіку пісаць і
выдаляць файлы па-за гульнёй. Таму кожны шлях з payload, які склейваецца з папкай
гульні, — праз inside(): абсалютныя шляхі, дыскі і `..`, што выводзяць за root,
адкідаюцца яшчэ да таго, як нешта прачытана ці запісана.
"""
from __future__ import annotations

import os
import re

# id гульні ў каталогу і імя папкі ў games/: ідзе ў шляхі (кэш, часовая папка)
GAME_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")


def _bad(part) -> bool:
    if not isinstance(part, str):
        return True
    p = part.replace("\\", "/")
    return p.startswith("/") or bool(os.path.splitdrive(part)[0]) or ":" in p or "\0" in p


def inside(root: str, *parts: str, strict: bool = False) -> str:
    """os.path.join(root, *parts), калі вынік не выходзіць за root; інакш SystemExit.
    strict — вынік не можа быць самім root (тое, што выдаляецца цалкам)."""
    if any(_bad(p) for p in parts):
        raise SystemExit(f"недапушчальны шлях у апісанні перакладу: {'/'.join(map(str, parts))}")
    path = os.path.join(root, *parts)
    base = os.path.normcase(os.path.abspath(root))
    full = os.path.normcase(os.path.abspath(path))
    if full != base and not full.startswith(base.rstrip(os.sep) + os.sep) or strict and full == base:
        raise SystemExit(f"шлях па-за папкай гульні ў апісанні перакладу: {'/'.join(parts)}")
    return path


def name(part: str) -> str:
    """Адзін кампанент шляху (імя файла або мовы) — без падзельнікаў і `..`."""
    if _bad(part) or not part or "/" in part or "\\" in part or part in (".", ".."):
        raise SystemExit(f"недапушчальнае імя ў апісанні перакладу: {part}")
    return part


def game_id(gid: str) -> str:
    if not isinstance(gid, str) or not GAME_ID.fullmatch(gid) or ".." in gid:
        raise SystemExit(f"недапушчальны id гульні: {gid!r}")
    return gid
