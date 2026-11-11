"""Логіка лаўнчара без інтэрфейсу: што знойдзена, у якім стане, паставіць, выдаліць.

Тут няма ні input(), ні print(): кансоль (main.py) і акно (app.py) — абалонкі над
гэтымі функцыямі, паведамленні ідуць праз log.
"""
from __future__ import annotations

import json
import os

from belloc import catalog, engines, steam
from belloc.install import state
from belloc.install.process import game_running

VERSION = "0.3"                 # версія лаўнчара; каталог: "launcher" — навейшы лаўнчар
LABELS = {"none": "не ўсталяваны", "installed": "усталяваны", "unknown": "усталяваны (версія невядомая)",
          "wiped": "зляцеў пасля абнаўлення гульні"}


class Busy(Exception):
    """Гульня запушчаная — файлы чапаць нельга."""


# ---------------------------------------------------------------- налады лаўнчара

def settings_path() -> str:
    """%LOCALAPPDATA%/belloc/launcher.json: папкі гульняў, пазначаныя ўручную."""
    return os.path.join(os.path.dirname(catalog.cache_dir()), "launcher.json")


def load_settings() -> dict:
    try:
        with open(settings_path(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_settings(s: dict):
    os.makedirs(os.path.dirname(settings_path()), exist_ok=True)
    with open(settings_path(), "w", encoding="utf-8", newline="\n") as f:
        json.dump(s, f, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- пошук гульняў

def steam_found() -> bool:
    """Ці ёсць на камп'ютары Steam (хоць адна бібліятэка)."""
    return any(os.path.isdir(os.path.join(r, "steamapps")) for r in steam.steam_roots())


def has_exe(folder: str, exe: str, depth: int = 2) -> bool:
    """Ці ёсць exe гульні ў папцы або на глыбіні да depth (007: Retail/007FirstLight.exe)."""
    for dirpath, dirs, files in os.walk(folder):
        if exe.lower() in (f.lower() for f in files):
            return True
        if os.path.relpath(dirpath, folder).count(os.sep) + 1 >= depth and dirpath != folder:
            dirs[:] = []
    return False


def fits(e: dict, folder: str) -> bool:
    """Ці падобная папка на каталог гэтай гульні: ёсць тое, па чым яе пазнае рухавік
    (check_path), і exe гульні."""
    if not catalog.supported(e):
        return False
    if not os.path.isdir(os.path.join(folder, engines.get(e["engine"]).check_path(e["probe"]))):
        return False
    return not e.get("exe") or has_exe(folder, e["exe"])


def match_folder(cat: dict, folder: str) -> list[str]:
    """Якім гульням каталога падыходзіць папка, якую пазначыў гулец."""
    return [gid for gid, e in cat.get("games", {}).items() if fits(e, folder)]


def remember(gid: str, folder: str):
    s = load_settings()
    s.setdefault("folders", {})[gid] = folder
    save_settings(s)


def scan(cat: dict, apps: dict | None = None) -> list[dict]:
    """Гульні з каталога, якія ёсць на камп'ютары: Steam і папкі, пазначаныя ўручную."""
    apps = steam.installed_apps() if apps is None else apps
    manual = load_settings().get("folders", {})
    found = []
    for gid, e in sorted(cat.get("games", {}).items(), key=lambda x: x[1].get("name", x[0])):
        appid = e.get("stores", {}).get("steam")
        if appid in apps:
            folder, buildid = apps[appid]["dir"], apps[appid]["buildid"]
        elif gid in manual and os.path.isdir(manual[gid]) and fits(e, manual[gid]):
            folder, buildid = manual[gid], steam.buildid(manual[gid], appid)
        else:
            continue
        try:
            found.append(refresh({"id": gid, "entry": e, "appid": appid, "dir": folder,
                                  "buildid": buildid, "supported": catalog.supported(e)}))
        except (SystemExit, KeyError, TypeError, AttributeError):
            continue                        # бітая запіс каталога не ламае астатнія гульні
    return found


def others(cat: dict, rows: list[dict]) -> list[dict]:
    """Пераклады з каталога для гульняў, якіх на камп'ютары няма."""
    have = {r["id"] for r in rows}
    return [{"id": gid, "entry": e, "appid": e.get("stores", {}).get("steam")}
            for gid, e in sorted(cat.get("games", {}).items(), key=lambda x: x[1].get("name", x[0]))
            if gid not in have]


def store_url(appid) -> str | None:
    """Старонка гульні ў Steam; appid — толькі лік (каталог правярае тое ж)."""
    return f"https://store.steampowered.com/app/{appid}/" if type(appid) is int and appid > 0 else None


def refresh(row: dict) -> dict:
    """Стан перакладу ў гульні — нанова (пасля ўсталёўкі або выдалення)."""
    e = row["entry"]
    if row["supported"]:
        row["state"], row["mark"] = state.status(row["dir"], engines.get(e["engine"]), e["probe"])
    else:
        row["state"], row["mark"] = "none", state.read(row["dir"])
    return row


def installed_version(row: dict) -> str | None:
    return (row["mark"] or {}).get("version") if row["state"] == "installed" else None


def update_available(row: dict) -> bool:
    v = installed_version(row)
    return bool(v) and catalog.newer(row["entry"]["version"], v)


def action(row: dict) -> str | None:
    """Што прапанаваць: "install", "update", "reinstall" (зляцеў) або None (усё стаіць)."""
    if not row["supported"]:
        return None
    if row["state"] == "installed":
        return "update" if update_available(row) else None
    return "reinstall" if row["state"] == "wiped" else "install"


def notes(row: dict) -> list[str]:
    """Папярэджанні для гульца."""
    e, out = row["entry"], []
    if not row["supported"]:
        out.append("патрэбна новая версія лаўнчара")
    if e.get("steam_buildid") and row["buildid"] and e["steam_buildid"] != row["buildid"]:
        out.append("версія гульні іншая, чым пры перакладзе — новыя радкі могуць быць неперакладзенымі")
    return out


def launcher_notice(cat: dict | None) -> str | None:
    """«Ёсць новы лаўнчар» для кансолі і акна, калі ў каталогу ён навейшы за гэты."""
    upd = catalog.launcher_update(cat, VERSION)
    if not upd:
        return None
    return f"Ёсць новы лаўнчар {upd['version']} (у вас {VERSION}): {upd['page']}"


def describe(row: dict) -> str:
    """Адзін радок для кансолі."""
    e = row["entry"]
    s = f"{e['name']}: пераклад {LABELS[row['state']]}"
    if row["state"] == "installed":
        s += f" — {installed_version(row)}"
        if update_available(row):
            s += f"; ёсць новая версія {e['version']}"
    else:
        s += f"; можна паставіць {e['version']}"
    return s + "".join(f" ({n})" for n in notes(row))


def install(row: dict, log=print):
    """Спампаваць пакет (sha256), паставіць, пакінуць метку. Busy — гульня запушчаная."""
    e = row["entry"]
    if not row["supported"]:
        raise SystemExit("Гэты пераклад патрабуе навейшага лаўнчара.")
    if game_running(e["exe"], row["dir"]):
        raise Busy(f"Зачыніце {e['name']} і паспрабуйце нанова.")
    log("Спампоўваю пакет перакладу…")
    pkg = catalog.download(e, catalog.cache_dir())
    p = catalog.open_package(pkg, catalog.unpack_dir(row["id"]))
    if p.get("game_id") != row["id"] or p.get("engine") != e["engine"]:
        raise SystemExit("Пакет перакладу не для гэтай гульні — усталёўка спынена.")
    engines.get(p["engine"]).apply(row["dir"], p, None, log)
    state.write(row["dir"], p, "launcher")
    log(f"Гатова. У гульні выберыце мову «{e['language_name']}».")
    refresh(row)


def remove(row: dict, log=print):
    e = row["entry"]
    if game_running(e["exe"], row["dir"]):
        raise Busy(f"Зачыніце {e['name']} і паспрабуйце нанова.")
    engines.get(e["engine"]).restore(row["dir"], e["probe"], log)
    state.remove(row["dir"])
    log("Гатова: гульня зноў з арыгінальнымі файламі.")
    refresh(row)
