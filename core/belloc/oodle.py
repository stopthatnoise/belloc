"""ooz.pyd у exe і лаўнчары — толькі наша зборка pyooz, з зыходнікамі побач.

pyooz (распакоўка Oodle для рухавіка unreal-locres) — натыўны модуль пад GPL. Кола з
PyPI — бінарнік без зыходнікаў, таму ў exe яго не кладзём: belloc збірае сваё ў CI з
замацаваных камітаў арыгіналаў (.github/workflows/pyooz.yml) і кладзе ў той жа рэліз
belloc поўныя зыходнікі (pyooz + ooz + simde). Перад зборкай exe і лаўнчара check()
параўноўвае SHA-256 усталяванага ooz.pyd з OOZ_SHA256 гэтай зборкі.

Распрацоўка і CI працуюць і з колам з PyPI (той жа код); праверка — толькі перад зборкай.

    gh release download pyooz-0.0.8.1 --repo stopthatnoise/belloc -p "*.whl" -D local/wheels
    python -m pip install --force-reinstall --no-deps local/wheels/pyooz-0.0.8-cp38-abi3-win_amd64.whl

Пробная зборка з колам з PyPI (не для выкладкі): BELLOC_ALLOW_PYPI_OOZ=1.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os

RELEASE = "pyooz-0.0.8.1"            # рэліз belloc з колам і зыходнікамі
OOZ_SHA256 = "42d8641268b1d3b6a64bcc560bb4269be024e4bc0ac63435307490966abb8519"   # ooz.pyd.sha256.txt з RELEASE


def installed_sha256() -> str | None:
    spec = importlib.util.find_spec("ooz")
    if spec is None or not spec.origin or not os.path.exists(spec.origin):
        return None
    with open(spec.origin, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def check(log=print):
    """Перад зборкай exe: ooz.pyd — з нашага рэліза RELEASE, інакш SystemExit."""
    have = installed_sha256()
    if have and OOZ_SHA256 and have == OOZ_SHA256:
        return
    why = ("pyooz не ўсталяваны" if have is None else
           "наша зборка pyooz яшчэ не зацверджана (oodle.OOZ_SHA256)" if not OOZ_SHA256 else
           "ooz.pyd — не з нашага рэліза (мабыць, кола з PyPI)")
    if os.environ.get("BELLOC_ALLOW_PYPI_OOZ") == "1" and have:
        log(f"УВАГА: {why} — пробная зборка, не для выкладкі (BELLOC_ALLOW_PYPI_OOZ=1)")
        return
    raise SystemExit(f"{why}. Для exe трэба кола з рэліза {RELEASE} (зыходнікі побач, GPL) — "
                     f"гл. core/belloc/oodle.py; пробная зборка — BELLOC_ALLOW_PYPI_OOZ=1")
