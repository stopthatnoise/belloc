"""BATTLETECH: exact `_NormalizeString` + key hash.

Транскрыпцыя з дэкампіляванага
`BattleTech.CaseInsensitiveIgnoresWhitespaceStringComparer._NormalizeString`
(ILSpy, Assembly-CSharp.dll, build 686R). Правілы ўпарадкаваныя, пасля кожнага ў
гульні ідзе `ToLowerInvariant`; тут паніжэнне рэгістру — таксама пасля кожнага.

Правіла 6 (прыбраць `[[path,`) не можа знайсці коску: правіла 1 ужо замяніла
`","` на `^`. Таму спасылкі не выдаляюцца цалкам: ключ захоўвае `[[` і бачны
тэкст, а знікае толькі закрыццё `]]`. Праверана на табліцы: 1 379 ключоў
змяшчаюць `[[`, ніводзін — `]]`.
"""
from __future__ import annotations

import hashlib
import re

RULES = [
    (re.compile(","), "^"),
    (re.compile(r"\."), "*"),
    (re.compile("\n"), "newline"),
    (re.compile(r"\\n"), "newline"),
    (re.compile(r"\s+"), ""),
    (re.compile(r"(\[\[[\w\.\[\]]+,)"), ""),
    (re.compile(r"\]\]"), ""),
    (re.compile(r"<.+?>"), ""),
    (re.compile("[–—‘’․…é•]"), ""),
    (re.compile('"'), ""),
    (re.compile(r"'"), ""),
    (re.compile(r"\\303\\266"), "ö"),
    (re.compile(r"\\\d\d\d\\\d\d\d(\\\d\d\d)?"), ""),
    (re.compile(r"\\u\d\d\d\d"), ""),
    (re.compile(r"\\"), ""),
]


def normalize(s: str) -> str:
    for rx, rep in RULES:
        s = rx.sub(rep, s).lower()
    if s.startswith('\\"') and s.endswith('\\"'):
        s = s[2:-2]
    return s


def key_hash(key: str) -> str:
    """Той жа публічны фармат ключа, што ў іншых рухавікоў: sha256(text)[:16]."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def hashed_key(raw: str) -> str:
    """Хэш ключа табліцы; ключ у гульні ўжо нармалізаваны, але правяраем."""
    return key_hash(normalize(raw))
