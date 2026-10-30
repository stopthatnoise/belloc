"""Лаўнчар — прататып у кансолі: знаходзіць гульні Steam, для якіх ёсць беларускі
пераклад, і ставіць, абнаўляе або выдаляе яго. Пазней — GUI паверх тых жа функцый.

Што бачыць (каталог — core/belloc/catalog.py, метка — install/state.py):
  гульня ёсць у Steam і ў каталогу → «можна паставіць»;
  стаіць наш пераклад (belloc.json + engine.installed) → версія; калі ў каталогу
  навейшая — «ёсць абнаўленне»; калі Steam затрэ файлы — «пераклад зляцеў».

Пакет перакладу спампоўваецца з каталога (sha256 правяраецца), рухавікі — у самім
лаўнчары. Пакуль толькі Steam; іншыя крамы — праз "stores" у каталогу.

    python launcher/main.py                       меню
    python launcher/main.py list                  што знойдзена
    python launcher/main.py install|remove <id> [--yes]
    python launcher/main.py --catalog <url|файл>  іншы каталог (тэсты, свой)
"""
from __future__ import annotations

import argparse
import os
import sys

from belloc import catalog, engines, steam
from belloc.install import state
from belloc.install.process import game_running

LABELS = {"none": "не ўсталяваны", "installed": "усталяваны", "unknown": "усталяваны (версія невядомая)",
          "wiped": "зляцеў пасля абнаўлення гульні"}


def scan(cat: dict, apps: dict | None = None) -> list[dict]:
    """Гульні з каталога, якія ёсць на камп'ютары: id, запіс каталога, каталог гульні, стан."""
    apps = steam.installed_apps() if apps is None else apps
    found = []
    for gid, e in sorted(cat.get("games", {}).items(), key=lambda x: x[1].get("name", x[0])):
        appid = e.get("stores", {}).get("steam")
        if appid not in apps:
            continue
        game = apps[appid]["dir"]
        row = {"id": gid, "entry": e, "dir": game, "buildid": apps[appid]["buildid"],
               "supported": catalog.supported(e)}
        if row["supported"]:
            row["state"], row["mark"] = state.status(game, engines.get(e["engine"]), e["probe"])
        else:
            row["state"], row["mark"] = "none", state.read(game)
        found.append(row)
    return found


def describe(row: dict) -> str:
    e, mark = row["entry"], row["mark"] or {}
    s = f"{e['name']}: пераклад {LABELS[row['state']]}"
    if row["state"] == "installed":
        s += f" — {mark.get('version')}"
        if catalog.newer(e["version"], mark.get("version")):
            s += f"; ёсць новая версія {e['version']}"
    elif row["state"] in ("none", "wiped", "unknown"):
        s += f"; можна паставіць {e['version']}"
    if not row["supported"]:
        s += " (патрэбна новая версія лаўнчара)"
    elif e.get("steam_buildid") and row["buildid"] and e["steam_buildid"] != row["buildid"]:
        s += " · версія гульні іншая, чым пры перакладзе — новыя радкі могуць быць неперакладзенымі"
    return s


def install(row: dict, auto: bool) -> int:
    e = row["entry"]
    if not row["supported"]:
        print("Гэты пераклад патрабуе навейшага лаўнчара.")
        return 1
    if game_running(e["exe"], row["dir"]):
        print(f"Зачыніце {e['name']} і паспрабуйце нанова.")
        return 1
    print(f"\n{e['name']} {e['version']}: пераклад ставіцца замест мовы «{e['replaces']}».")
    if not auto and input("Усталяваць? [т/н]: ").strip().lower() not in ("т", "так", "y", "yes"):
        return 0
    print("Спампоўваю пакет перакладу…")
    pkg = catalog.download(e, catalog.cache_dir())
    p = catalog.open_package(pkg, catalog.unpack_dir(row["id"]))
    engines.get(p["engine"]).apply(row["dir"], p, None, print)
    state.write(row["dir"], p, "launcher")
    print(f"Гатова. У гульні выберыце мову «{e['language_name']}».")
    return 0


def remove(row: dict, auto: bool) -> int:
    e = row["entry"]
    if game_running(e["exe"], row["dir"]):
        print(f"Зачыніце {e['name']} і паспрабуйце нанова.")
        return 1
    if not auto and input(f"Выдаліць пераклад {e['name']}? [т/н]: ").strip().lower() not in ("т", "так", "y", "yes"):
        return 0
    engines.get(e["engine"]).restore(row["dir"], e["probe"], print)
    state.remove(row["dir"])
    print("Гатова: гульня зноў з арыгінальнымі файламі.")
    return 0


def main(argv=None, apps: dict | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Беларускія пераклады гульняў — лаўнчар")
    ap.add_argument("action", nargs="?", choices=["list", "install", "remove"])
    ap.add_argument("game", nargs="?", help="id гульні з каталога")
    ap.add_argument("--catalog", default=catalog.CATALOG_URL)
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args(argv)

    cat = catalog.fetch(args.catalog)
    if cat is None:
        print("Не атрымалася загрузіць каталог перакладаў — праверце інтэрнэт.")
        return 1
    rows = scan(cat, apps)
    if not rows:
        print("На гэтым камп'ютары не знайшлося гульняў Steam, для якіх ёсць беларускі пераклад.")
        return 0
    if args.action in (None, "list"):
        for i, r in enumerate(rows, 1):
            print(f"  {i} — {describe(r)}")
        if args.action == "list":
            return 0
        choice = input("\nНумар гульні (0 — выхад): ").strip()
        if not choice.isdigit() or not 1 <= int(choice) <= len(rows):
            return 0
        row = rows[int(choice) - 1]
        act = input("  1 — усталяваць / абнавіць, 2 — выдаліць: ").strip()
        return install(row, False) if act == "1" else remove(row, False) if act == "2" else 0
    row = next((r for r in rows if r["id"] == args.game), None)
    if row is None:
        print(f"Гульні «{args.game}» няма сярод знойдзеных: {', '.join(r['id'] for r in rows)}")
        return 1
    return install(row, args.yes) if args.action == "install" else remove(row, args.yes)


if __name__ == "__main__":
    sys.exit(main())
