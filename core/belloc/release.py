"""Рэліз для гульцоў: усталёўшчык .exe + ЧЫТАЙ.txt у zip.

Секцыя "release" у game.json:

  "release": {"title": "Беларускі пераклад Silver Pines", "version": "1.0",
              "exe": "Carpenter.exe", "file": "SilverPines_BE",
              "language_name": "Беларуская", "replaces": "Русский",   — без replaces: асобная
                                                         мова, нічога не замяняе (Esoteric Ebb)
              "url": "https://…/releases",
              "menu": "Налады → Мова",                — дзе ў гульні выбіраецца мова
              "contents": "Перакладзена … (усяго радкоў: {strings}) …",  — што перакладзена
              "how": "Ён змяняе … Арыгіналы … .orig.",  — якія файлы гульні мяняюцца
              "readme": "release/readme.txt",          — свой шаблон ЧЫТАЙ.txt (неабавязкова,
                                                         шлях адносна games/<гульня>/)
              "files_readme": "…"}                     — тое ж для архіва ручной усталёўкі
  подпіс — "credits" у game.json (тое ж, што ў README гульні)

Што трапляе ў exe: installer/run.py, belloc з рухавіком гульні (аргументы
PyInstaller — PYINSTALLER у engines/<рухавік>/__init__.py), payload.json (толькі
наш тэкст па ключах і апісанне гульні, payload.py) і assets/ (нашы файлы з
games/<гульня>/: вольныя шрыфты з ліцэнзіямі). Файлы гульні не распаўсюджваюцца —
усталёўшчык патчыць іх на камп'ютары гульца.

Архіў ручной усталёўкі (<file>_<version>_files.zip) — толькі для рухавікоў, дзе
вынік цалкам наш і не залежыць ад файлаў гульні (engine.files_dir: Paradox).
Перад упакоўкай кожны файл правяраецца: калі ў ім ёсць радок арыгінала або
падказкі з local/<гульня>/source/ (не роўны нашаму перакладу) — архіў не збіраецца.
Гатовыя пратчаныя файлы гульні ў рэліз не кладуцца ніколі: у іх тэкст і
іншае змесціва гульні.

    python -m belloc package silver-pines      # → local/<гульня>/build/release/<file>_<version>.zip
"""
from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

from . import catalog, engines, oodle, payload as payload_mod, tables
from .config import ROOT, Loc
from .install import paths

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

FILES_README = """{title} — ручная ўсталёўка
Версія {version} ({date})
{credits}

Неафіцыйны фанацкі пераклад гульні {game} на беларускую мову.
Гэта нейрапераклад (зроблены моўнай мадэллю): чалавек яго цалкам не
вычытваў, таму магчымыя памылкі і няўдалыя фразы — паведамляйце пра іх.
{contents}

У архіве — толькі файлы перакладу, без усталёўшчыка. Файлы гульні не
мяняюцца: пераклад ляжыць у асобнай папцы.

УСТАЛЁЎКА
1. Зачыніце гульню.
2. Адкрыйце каталог гульні: у Steam правая кнопка на гульні →
   Кіраванне → Праглядзець лакальныя файлы (там ляжыць {game_exe}).
3. Перацягніце папку {top_dir} з гэтага архіва ў каталог гульні. Калі
   Windows спытае пра аб'яднанне папак — пагадзіцеся.
4. У гульні: {menu} → «{language_name}».

Пераклад ставіцца замест мовы «{replaces}»: пакуль ён ляжыць у гульні,
гэтай мовы ў гульні не будзе.

ВЫДАЛЕННЕ
Выдаліце папку {files_dir} у каталогу гульні.

ПАСЛЯ АБНАЎЛЕННЯ ГУЛЬНІ
Пераклад застаецца на месцы. Радкі, што з'явіліся ў новай версіі, будуць
на мове «{replaces}», пакуль не выйдзе новая версія перакладу.

Пераклад зроблены пад версію гульні (Steam build) {buildid}.
Новыя версіі і зваротная сувязь: {url}
"""

# радок гульні карацейшы за гэта ў праверцы ўцечак не лічыцца (імёны, «OK», «Yes»)
LEAK_MIN = 12

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
    for k in ("version", "exe", "file"):        # ідуць у імёны файлаў і ў каталог
        if k in rel:
            paths.name(str(rel[k]))
    p = payload_mod.build_payload(loc, engine)
    p["release"] = {
        "title": rel["title"], "version": rel["version"], "credits": credits(loc),
        "date": datetime.date.today().isoformat(), "exe": rel["exe"],
        "language_name": rel["language_name"], "replaces": rel.get("replaces"),   # None — асобная мова
        "url": rel.get("url") or catalog.RELEASES,     # старонка рэліза: па змаўчанні — Releases каталога
    }
    return p


def readme(loc: Loc, p: dict, exe_name: str) -> str:
    rel = loc.section("release")
    tpl = README
    if rel.get("readme"):
        with open(loc.path(rel["readme"]), encoding="utf-8") as f:
            tpl = f.read()
    n = sum(len(v) for v in p["strings"].values())
    return tpl.format(**{**p["release"], "date": catalog.show_date(p["release"]["date"])},
                      game=p["game"], game_exe=p["release"]["exe"], exe_name=exe_name,
                      menu=rel["menu"], contents=rel["contents"].format(strings=n), how=rel["how"],
                      buildid=p.get("steam_buildid"))


def game_texts(loc: Loc) -> set[str]:
    """Радкі арыгінала і падказак з local/<гульня>/source/, якіх няма сярод нашых перакладаў."""
    ours = {v for kv in tables.translation_by_key(loc).values() for v in kv.values()}
    out = set()
    for lang in [loc.source_lang] + tables.hint_langs(loc):
        p = os.path.join(loc.source, f"{lang}.json")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                out |= {v for kv in json.load(f).values() for v in kv.values()
                        if len(v) >= LEAK_MIN and v not in ours}
    return out


def leaks(folder: str, texts: set[str]) -> list[tuple[str, str]]:
    """(файл, радок гульні) — што з texts трапіла ў файлы папкі."""
    found = []
    for dirpath, _, names in os.walk(folder):
        for n in names:
            p = os.path.join(dirpath, n)
            with open(p, "rb") as f:
                # yml і падобныя: перанос радка ў файле — літаральнае \n
                data = f.read().decode("utf-8-sig", "ignore").replace("\\n", "\n")
            found += [(os.path.relpath(p, folder), t) for t in texts if t in data]
    return found


def build_files(loc: Loc, engine, p: dict, name: str, out_dir: str) -> str | None:
    """Архіў ручной усталёўкі: вынік apply(out=…) пад шляхам engine.files_dir."""
    if not hasattr(engine, "files_dir"):
        return None
    rel_dir = engine.files_dir(p).replace("\\", "/").strip("/")
    tmp = os.path.join(loc.build, "package", "files")
    shutil.rmtree(tmp, ignore_errors=True)
    engine.apply("", p, tmp, lambda *_: None)          # файлы гульні не чытаюцца (files_dir)
    if tables.has_source(loc):
        bad = leaks(tmp, game_texts(loc))
        if bad:
            for f, t in bad[:10]:
                print(f"  {f}: {t[:80]!r}")
            raise SystemExit(f"у архіве ручной усталёўкі — тэкст гульні ({len(bad)}), архіў не сабраны")
    else:
        print("  праверка ўцечак прапушчана: няма local/…/source/ (спачатку extract)")
    rel = loc.section("release")
    tpl = FILES_README
    if rel.get("files_readme"):
        with open(loc.path(rel["files_readme"]), encoding="utf-8") as f:
            tpl = f.read()
    n = sum(len(v) for v in p["strings"].values())
    text = tpl.format(**{**p["release"], "date": catalog.show_date(p["release"]["date"])},
                      game=p["game"], game_exe=p["release"]["exe"], menu=rel["menu"],
                      contents=rel["contents"].format(strings=n), buildid=p.get("steam_buildid"),
                      files_dir=rel_dir, top_dir=rel_dir.split("/")[0])
    zpath = os.path.join(out_dir, f"{name}_files.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for dirpath, _, names in os.walk(tmp):
            for n_ in sorted(names):
                src = os.path.join(dirpath, n_)
                z.write(src, f"{rel_dir}/{os.path.relpath(src, tmp).replace(os.sep, '/')}")
        z.writestr("ЧЫТАЙ.txt", text.replace("\n", "\r\n").encode("utf-8-sig"))
    return zpath


def engine_modules(engine) -> list[str]:
    """Пакет рухавіка і ўсе яго модулі — для --hidden-import."""
    import pkgutil
    return [engine.__name__] + [m.name for m in pkgutil.walk_packages(engine.__path__, engine.__name__ + ".")]


def check_exe(exe: str, modules: list[str]):
    """Усе модулі рухавіка — у PYZ exe: без іх усталёўшчык падае на першым кроку."""
    from PyInstaller.archive.readers import CArchiveReader, ZlibArchiveReader
    pyz = os.path.join(os.path.dirname(exe), "PYZ-check.pyz")
    with open(pyz, "wb") as f:
        f.write(CArchiveReader(exe).extract("PYZ.pyz"))
    try:
        have = set(ZlibArchiveReader(pyz).toc)
    finally:
        os.remove(pyz)
    missing = [m for m in modules if m not in have]
    if missing:
        raise SystemExit(f"у exe няма модуляў рухавіка: {', '.join(missing)}")


LOCK = os.path.join(ROOT, "requirements-release.txt")


def check_lock():
    """Зборка — толькі з залежнасцямі з requirements-release.txt (installer/lock.py): тыя ж
    версіі, што праверылі, і з хэшамі. BELLOC_ALLOW_UNLOCKED=1 — проба, не для выкладкі."""
    from importlib import metadata
    with open(LOCK, encoding="utf-8") as f:
        pins = re.findall(r"^([A-Za-z0-9._-]+)==(\S+)", f.read(), re.M)
    wrong = []
    for name, version in pins:
        try:
            have = metadata.version(name)
        except metadata.PackageNotFoundError:
            have = None
        if have != version:
            wrong.append(f"{name} {have or '—'} (трэба {version})")
    if wrong and os.environ.get("BELLOC_ALLOW_UNLOCKED") != "1":
        raise SystemExit("залежнасці не з requirements-release.txt: " + ", ".join(wrong) +
                         "\nчысты venv: pip install --require-hashes -r requirements-release.txt")


def build(loc: Loc) -> str:
    rel = loc.section("release")
    engine = engines.get(loc.engine)
    check_lock()
    if "ooz" in getattr(engine, "PYINSTALLER", []):
        oodle.check()                    # у exe — толькі наша зборка pyooz (GPL: зыходнікі побач)
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
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--console",
           "--name", name, "--distpath", os.path.join(work, "dist"),
           "--workpath", os.path.join(work, "pyi"), "--specpath", work, "--paths", CORE,
           # рухавік грузіцца па імені з payload (importlib) — PyInstaller яго сам не бачыць;
           # --collect-submodules з --paths модулі не знаходзіць (exe быў без рухавіка), таму яўна
           *[x for m in engine_modules(engine) for x in ("--hidden-import", m)],
           *[x for d in data for x in ("--add-data", d)],
           *getattr(engine, "PYINSTALLER", []), INSTALLER]
    print("PyInstaller…")
    subprocess.run(cmd, check=True, cwd=work, stdout=subprocess.DEVNULL)
    exe = os.path.join(work, "dist", name + ".exe")
    check_exe(exe, engine_modules(engine))

    out_dir = os.path.join(loc.build, "release")
    os.makedirs(out_dir, exist_ok=True)
    zpath = os.path.join(out_dir, f"{name}.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(exe, name + ".exe")
        z.writestr("ЧЫТАЙ.txt", readme(loc, p, name + ".exe").replace("\n", "\r\n").encode("utf-8-sig"))
    shutil.copyfile(exe, os.path.join(out_dir, name + ".exe"))
    print(f"exe: {os.path.getsize(exe) / 1e6:.1f} МБ")
    print("рэліз:", zpath)
    files = build_files(loc, engine, p, name, out_dir)
    if files:
        print("рэліз (ручная ўсталёўка):", files)
    return zpath
