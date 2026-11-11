"""Лаўнчар у кансолі: знаходзіць гульні Steam, для якіх ёсць беларускі пераклад, і
ставіць, абнаўляе або выдаляе яго. Акно — app.py; логіка — games.py.

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
import sys

from belloc import catalog

import games


def confirm(prompt: str, auto: bool) -> bool:
    return auto or input(f"{prompt} [т/н]: ").strip().lower() in ("т", "так", "y", "yes")


def install(row: dict, auto: bool) -> int:
    e = row["entry"]
    print(f"\n{e['name']} {e['version']}" + (f": пераклад ставіцца замест мовы «{e['replaces']}»."
                                              if e.get("replaces") else "."))
    if not confirm("Усталяваць?", auto):
        return 0
    try:
        games.install(row)
    except games.Busy as err:
        print(err)
        return 1
    return 0


def remove(row: dict, auto: bool) -> int:
    if not confirm(f"Выдаліць пераклад {row['entry']['name']}?", auto):
        return 0
    try:
        games.remove(row)
    except games.Busy as err:
        print(err)
        return 1
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
    notice = games.launcher_notice(cat)
    if notice:
        print(notice + "\n")
    rows = games.scan(cat, apps)
    if not rows:
        print("На гэтым камп'ютары не знайшлося гульняў Steam, для якіх ёсць беларускі пераклад.")
        return 0
    if args.action in (None, "list"):
        for i, r in enumerate(rows, 1):
            print(f"  {i} — {games.describe(r)}")
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
