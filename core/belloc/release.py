"""Рэліз для гульцоў: усталёўшчык .exe + ЧЫТАЙ.txt у zip.

Секцыя "release" у game.json:

  "release": {"title": "Беларускі пераклад Silver Pines", "version": "1.0",
              "exe": "Carpenter.exe", "file": "SilverPines_BE",
              "language_name": "Беларуская", "replaces": "Русский",
              "url": "https://…/releases",
              "menu": "Налады → Мова",                — дзе ў гульні выбіраецца мова
              "contents": "Перакладзена … (усяго радкоў: {strings}) …",  — што перакладзена
              "how": "Ён змяняе … Арыгіналы … .orig.",  — якія файлы гульні мяняюцца
              "readme": "release/readme.txt"}          — свой шаблон ЧЫТАЙ.txt (неабавязкова,
                                                         шлях адносна games/<гульня>/)
  подпіс — "credits" у game.json (тое ж, што ў README гульні)

Што трапляе ў exe: installer/run.py, belloc з рухавіком гульні (аргументы
PyInstaller — PYINSTALLER у engines/<рухавік>/__init__.py), payload.json (толькі
наш тэкст па ключах і апісанне гульні, payload.py) і assets/ (нашы файлы з
games/<гульня>/: вольныя шрыфты з ліцэнзіямі). Файлы гульні не распаўсюджваюцца —
усталёўшчык патчыць іх на камп'ютары гульца.

    python -m belloc package silver-pines      # → local/<гульня>/build/release/<file>_<version>.zip
"""
from __future__ import annotations

import datetime
import json
import os
import shutil
import subprocess
import sys
import zipfile

from . import engines, payload as payload_mod
from .config import ROOT, Loc

README = """{title}
Версія {version} ({date})
{credits}

Неафіцыйны фанацкі пераклад гульні {game} на беларускую мову.
Гэта нейрапераклад (зроблены моўнай мадэллю): чалавек яго цалкам не
вычытваў, таму магчымыя памылкі і няўдалыя фразы — паведамляйце пра іх.
{contents}

УСТАЛЁЎКА
1. Зачыніце гульню.
2. Запусціце {exe_name} і выберыце «1 — усталяваць».
   Усталёўшчык сам знаходзіць гульню ў Steam. Калі не знайшоў — папросіць
   шлях да каталога гульні (там, дзе {game_exe}).
3. У гульні: {menu} → «{language_name}».

Пераклад ставіцца замест мовы «{replaces}»: пакуль ён усталяваны, гэтай
мовы ў гульні не будзе.

ВЫДАЛЕННЕ
Запусціце {exe_name} і выберыце «2 — выдаліць». Альбо ў Steam:
Уласцівасці гульні → Усталяваныя файлы → Праверыць цэласнасць файлаў.

ПАСЛЯ АБНАЎЛЕННЯ ГУЛЬНІ
Steam перазапіша файлы, і пераклад знікне. Запусціце {exe_name} яшчэ
раз — пераклад усталюецца на новую версію.

ЯК ГЭТА ПРАЦУЕ
Усталёўшчык нічога не спампоўвае і не чапае іншыя гульні. {how}

Windows можа папярэдзіць пра невядомага выдаўца (SmartScreen): «Падрабязней»
→ «Усё роўна выканаць». Праграма не падпісаная, бо гэта аматарскі праект.

Пераклад зроблены пад версію гульні (Steam build) {buildid}.
Новыя версіі і зваротная сувязь: {url}
"""

INSTALLER = os.path.join(ROOT, "installer", "run.py")
CORE = os.path.join(ROOT, "core")


def credits(loc: Loc) -> str:
    c = loc.raw.get("credits") or loc.section("release").get("credits")
    if not c:
        raise SystemExit(f"{loc.id}: няма \"credits\" у game.json — подпіс абавязковы")
    return c


def release_payload(loc: Loc, engine) -> dict:
    """Payload гульні + апісанне рэліза для меню ўсталёўшчыка."""
    rel = loc.section("release")
    p = payload_mod.build_payload(loc, engine)
    p["release"] = {
        "title": rel["title"], "version": rel["version"], "credits": credits(loc),
        "date": datetime.date.today().isoformat(), "exe": rel["exe"],
        "language_name": rel["language_name"], "replaces": rel["replaces"], "url": rel.get("url", ""),
    }
    return p


def readme(loc: Loc, p: dict, exe_name: str) -> str:
    rel = loc.section("release")
    tpl = README
    if rel.get("readme"):
        with open(loc.path(rel["readme"]), encoding="utf-8") as f:
            tpl = f.read()
    n = sum(len(v) for v in p["strings"].values())
    return tpl.format(**p["release"], game=p["game"], game_exe=p["release"]["exe"], exe_name=exe_name,
                      menu=rel["menu"], contents=rel["contents"].format(strings=n), how=rel["how"],
                      buildid=p.get("steam_buildid"))


def build(loc: Loc) -> str:
    rel = loc.section("release")
    engine = engines.get(loc.engine)
    work = os.path.join(loc.build, "package")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    p = release_payload(loc, engine)
    with open(os.path.join(work, "payload.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload_mod.dump(p), f, ensure_ascii=False)
    data = [f"{os.path.join(work, 'payload.json')}{os.pathsep}."]
    for a in p.get("assets", []):
        dst = os.path.join(work, "assets", a)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(payload_mod.asset(p, a), dst)
    if p.get("assets"):
        data.append(f"{os.path.join(work, 'assets')}{os.pathsep}assets")
    n = sum(len(v) for v in p["strings"].values())
    print(f"payload: {n} радкоў, {len(p['strings'])} табліц, assets: {len(p.get('assets', []))}")

    name = f"{rel['file']}_{rel['version']}"
    pkg = engines.ENGINES[loc.engine]
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--console",
           "--name", name, "--distpath", os.path.join(work, "dist"),
           "--workpath", os.path.join(work, "pyi"), "--specpath", work, "--paths", CORE,
           # рухавік грузіцца па імені з payload (importlib) — PyInstaller яго сам не бачыць
           "--collect-submodules", f"belloc.engines.{pkg}",
           *[x for d in data for x in ("--add-data", d)],
           *getattr(engine, "PYINSTALLER", []), INSTALLER]
    print("PyInstaller…")
    subprocess.run(cmd, check=True, cwd=work, stdout=subprocess.DEVNULL)
    exe = os.path.join(work, "dist", name + ".exe")

    out_dir = os.path.join(loc.build, "release")
    os.makedirs(out_dir, exist_ok=True)
    zpath = os.path.join(out_dir, f"{name}.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(exe, name + ".exe")
        z.writestr("ЧЫТАЙ.txt", readme(loc, p, name + ".exe").replace("\n", "\r\n").encode("utf-8-sig"))
    shutil.copyfile(exe, os.path.join(out_dir, name + ".exe"))
    print(f"exe: {os.path.getsize(exe) / 1e6:.1f} МБ")
    print("рэліз:", zpath)
    return zpath
