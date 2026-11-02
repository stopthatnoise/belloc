"""Зборка лаўнчара: папка з belloc.exe (PyInstaller --onedir) і zip для гульцоў.

Лаўнчар нясе ўсе рухавікі: аргументы PyInstaller — PYINSTALLER з кожнага
engines/<рухавік>/__init__.py; выключаецца толькі тое, што выключаюць усе рухавікі
(напр. spylls — ён патрэбны толькі лінтэру). --onedir, а не --onefile: з Qt, UnityPy і
OpenCV exe важыць пад 200 МБ, і --onefile распакоўваў бы яго пры кожным запуску.

    python launcher/build.py            → local/launcher/belloc-launcher_<версія>.zip

Праверка зборкі — `belloc.exe --selftest <шлях> --catalog <файл>` (гл. app.selftest):
усе рухавікі імпартуюцца, акно будуецца, каталог чытаецца.
"""
from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "core"))
sys.path.insert(0, HERE)

from belloc import engines, oodle, release  # noqa: E402

NAME = "belloc"


def engine_args() -> list[str]:
    """Аргументы PyInstaller для ўсіх рухавікоў разам."""
    keep, excludes = [], None
    for mod in engines.ENGINES.values():
        args = getattr(importlib.import_module(f"belloc.engines.{mod}"), "PYINSTALLER", [])
        ex, i = set(), 0
        while i < len(args):
            if args[i] == "--exclude-module":
                ex.add(args[i + 1])
            elif args[i].startswith("--"):
                pair = args[i:i + 2]
                if all(pair != keep[j:j + 2] for j in range(0, len(keep), 2)):
                    keep += pair
            i += 2
        excludes = ex if excludes is None else excludes & ex
    return keep + [x for m in sorted(excludes or ()) for x in ("--exclude-module", m)]


def engine_modules() -> list[str]:
    """Усе модулі belloc.engines.* — яўна: рухавік грузіцца па імені з каталога (importlib),
    і --collect-submodules у зборцы з --paths іх не знаходзіць."""
    import pkgutil
    import belloc.engines as pkg
    return [m.name for m in pkgutil.walk_packages(pkg.__path__, "belloc.engines.")]


def build() -> str:
    from app import VERSION
    release.check_lock()                 # тыя ж залежнасці, што ў requirements-release.txt
    oodle.check()                        # лаўнчар нясе ўсе рухавікі, у тым ліку ooz.pyd
    work = os.path.join(ROOT, "local", "launcher")
    shutil.rmtree(os.path.join(work, "dist"), ignore_errors=True)
    os.makedirs(work, exist_ok=True)
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--onedir", "--windowed",
           "--name", NAME, "--distpath", os.path.join(work, "dist"),
           "--workpath", os.path.join(work, "pyi"), "--specpath", work,
           "--paths", os.path.join(ROOT, "core"), "--paths", HERE,
           *[x for m in engine_modules() for x in ("--hidden-import", m)],
           "--exclude-module", "tkinter",
           *engine_args(), os.path.join(HERE, "app.py")]
    print("PyInstaller…")
    subprocess.run(cmd, check=True, cwd=work, stdout=subprocess.DEVNULL)
    folder = os.path.join(work, "dist", NAME)
    # відэа-плагін OpenCV (30 МБ): cv2 патрэбны толькі для надпісаў на тэкстурах (inpaint)
    for d, _, fs in os.walk(folder):
        for f in fs:
            if f.startswith("opencv_videoio_ffmpeg"):
                os.remove(os.path.join(d, f))
    size = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(folder) for f in fs)
    zpath = os.path.join(work, f"belloc-launcher_{VERSION}.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for d, _, fs in os.walk(folder):
            for f in sorted(fs):
                p = os.path.join(d, f)
                z.write(p, os.path.join("belloc-launcher", os.path.relpath(p, folder)))
    print(f"папка: {folder} ({size / 1e6:.0f} МБ)")
    print(f"zip: {zpath} ({os.path.getsize(zpath) / 1e6:.0f} МБ)")
    return zpath


if __name__ == "__main__":
    build()
