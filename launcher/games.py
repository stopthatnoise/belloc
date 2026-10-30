"""Логіка лаўнчара без інтэрфейсу: што знойдзена, у якім стане, паставіць, выдаліць.

Тут няма ні input(), ні print(): кансоль (main.py) і акно (app.py) — абалонкі над
гэтымі функцыямі, паведамленні ідуць праз log.
"""
from __future__ import annotations

from belloc import catalog, engines, steam
from belloc.install import state
from belloc.install.process import game_running

LABELS = {"none": "не ўсталяваны", "installed": "усталяваны", "unknown": "усталяваны (версія невядомая)",
          "wiped": "зляцеў пасля абнаўлення гульні"}


class Busy(Exception):
    """Гульня запушчаная — файлы чапаць нельга."""


def scan(cat: dict, apps: dict | None = None) -> list[dict]:
    """Гульні з каталога, якія ёсць на камп'ютары: id, запіс каталога, каталог гульні, стан."""
    apps = steam.installed_apps() if apps is None else apps
    found = []
    for gid, e in sorted(cat.get("games", {}).items(), key=lambda x: x[1].get("name", x[0])):
        appid = e.get("stores", {}).get("steam")
        if appid not in apps:
            continue
        found.append(refresh({"id": gid, "entry": e, "appid": appid, "dir": apps[appid]["dir"],
                              "buildid": apps[appid]["buildid"], "supported": catalog.supported(e)}))
    return found


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
