"""Пошук гульні ў Steam: рэестр → libraryfolders.vdf → appmanifest_<appid>.acf."""
from __future__ import annotations

import os
import re


def steam_roots() -> list[str]:
    """Каталогі Steam і ўсе яго бібліятэкі, якія ёсць на дыску."""
    roots = []
    try:
        import winreg
        for hive, key in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                          (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")):
            try:
                with winreg.OpenKey(hive, key) as k:
                    for name in ("SteamPath", "InstallPath"):
                        try:
                            roots.append(winreg.QueryValueEx(k, name)[0])
                        except OSError:
                            pass
            except OSError:
                pass
    except ImportError:
        pass
    roots += [r"C:\Program Files (x86)\Steam", os.path.expanduser("~/.steam/steam"),
              os.path.expanduser("~/.local/share/Steam"),
              os.path.expanduser("~/Library/Application Support/Steam")]
    libs = []
    for root in roots:
        vdf = os.path.join(root, "steamapps", "libraryfolders.vdf")
        if os.path.exists(vdf):
            text = open(vdf, encoding="utf-8", errors="replace").read()
            libs += [p.replace("\\\\", "\\") for p in re.findall(r'"path"\s+"([^"]+)"', text)]
        libs.append(root)
    seen, out = set(), []
    for p in libs:
        n = os.path.normcase(os.path.abspath(p))
        if n not in seen and os.path.isdir(p):
            seen.add(n)
            out.append(p)
    return out


def _manifest(path: str) -> str:
    return open(path, encoding="utf-8", errors="replace").read()


def find_game(appid: int) -> tuple[str | None, str | None]:
    """(каталог гульні, buildid) па appmanifest у бібліятэках Steam."""
    for lib in steam_roots():
        acf = os.path.join(lib, "steamapps", f"appmanifest_{appid}.acf")
        if os.path.exists(acf):
            text = _manifest(acf)
            m = re.search(r'"installdir"\s+"([^"]+)"', text)
            b = re.search(r'"buildid"\s+"(\d+)"', text)
            if m:
                path = os.path.join(lib, "steamapps", "common", m.group(1))
                if os.path.isdir(path):
                    return path, b and b.group(1)
    return None, None


def installed_apps() -> dict[int, dict]:
    """Усе ўсталяваныя гульні Steam: {appid: {"dir", "buildid", "name"}} (па appmanifest)."""
    out = {}
    for lib in steam_roots():
        apps = os.path.join(lib, "steamapps")
        if not os.path.isdir(apps):
            continue
        for n in os.listdir(apps):
            m = re.fullmatch(r"appmanifest_(\d+)\.acf", n)
            if not m or int(m.group(1)) in out:
                continue
            text = _manifest(os.path.join(apps, n))
            d = re.search(r'"installdir"\s+"([^"]+)"', text)
            if not d:
                continue
            path = os.path.join(apps, "common", d.group(1))
            if os.path.isdir(path):
                b = re.search(r'"buildid"\s+"(\d+)"', text)
                name = re.search(r'"name"\s+"([^"]+)"', text)
                out[int(m.group(1))] = {"dir": path, "buildid": b and b.group(1),
                                        "name": name.group(1) if name else d.group(1)}
    return out


def buildid(game_dir: str, appid: int | None) -> str | None:
    """buildid гульні з appmanifest побач з яе каталогам (steamapps/common/<гульня>)."""
    if not appid:
        return None
    acf = os.path.join(game_dir, "..", "..", f"appmanifest_{appid}.acf")
    if not os.path.exists(acf):
        return None
    m = re.search(r'"buildid"\s+"(\d+)"', _manifest(acf))
    return m and m.group(1)
