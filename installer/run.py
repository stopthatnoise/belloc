"""Усталёўшчык беларускага перакладу: адзін .exe на гульню, адзін скрыпт на ўсе рухавікі.

Збіраецца `python -m belloc package <гульня>` (core/belloc/release.py, PyInstaller):
у exe — гэты скрыпт, belloc з рухавіком гульні і побач

  payload.json  наш пераклад па ключах і апісанне гульні (core/belloc/payload.py)
  assets/       нашы файлы з games/<гульня>/, патрэбныя рухавіку (вольныя шрыфты)

Файлы гульні не распаўсюджваюцца: усё робіцца на камп'ютары гульца тым жа кодам,
што `belloc patch` (engine.apply / restore), — вынік байт у байт аднолькавы.
Пасля ўсталёўкі ў каталогу гульні застаецца метка belloc.json (install/state.py) — па
ёй лаўнчар бачыць пераклад. Пры запуску exe правярае каталог перакладаў (catalog.py):
калі ёсць навейшая версія — кажа, адкуль яе ўзяць; без сеткі — проста працуе далей.

    <exe>                       меню
    <exe> --install [--yes]     усталяваць / абнавіць
    <exe> --uninstall [--yes]   выдаліць
    <exe> --game "D:/…/Гульня"  калі гульня не знайшлася сама
"""
from __future__ import annotations

import argparse
import os
import sys

from belloc import catalog, engines, payload as payload_mod, steam
from belloc.install import state
from belloc.install.process import game_running

PAYLOAD = "payload.json"


def here(*parts):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


def ask(prompt: str, auto: bool) -> bool:
    if auto:
        return True
    return input(f"{prompt} [т/н]: ").strip().lower() in ("т", "так", "y", "yes", "д", "да")


def pause(auto: bool):
    if not auto:
        try:
            input("\nНацісніце Enter, каб закрыць акно…")
        except EOFError:
            pass


def remind(payload: dict, src: str = catalog.CATALOG_URL):
    """Калі ў каталогу ёсць навейшая версія гэтага перакладу — сказаць пра яе."""
    e = (catalog.fetch(src, timeout=3) or {}).get("games", {}).get(payload["game_id"])
    if e and catalog.newer(e.get("version"), payload["release"]["version"]):
        print(f"Ёсць новая версія перакладу: {e['version']} (ад {catalog.show_date(e.get('date'))}).")
        if e.get("changes"):
            print(f"  {e['changes']}")
        print(f"  Спампаваць: {e.get('page') or catalog.RELEASES}\n")


def main(argv=None, payload_path: str | None = None, catalog_src: str = catalog.CATALOG_URL) -> int:
    # кірыліца ў кансолі: калі вывад перанакіраваны, Python бярэ cp1252 і падае
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    payload = payload_mod.load(payload_path or here(PAYLOAD))
    rel = payload["release"]
    engine = engines.get(payload["engine"])
    ap = argparse.ArgumentParser(description=f"{rel['title']} — усталёўшчык")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--install", action="store_true")
    g.add_argument("--uninstall", action="store_true")
    ap.add_argument("--game", help="каталог гульні")
    ap.add_argument("--yes", action="store_true", help="без пытанняў")
    args = ap.parse_args(argv)
    auto = args.yes

    print(f"{rel['title']}, версія {rel['version']} ад {catalog.show_date(rel['date'])}")
    print(f"{rel['credits']}\n")
    remind(payload, catalog_src)

    game, buildid = (args.game, None) if args.game else steam.find_game(payload["steam_appid"])
    while not game or not os.path.isdir(os.path.join(game, engine.check_path(payload))):
        if auto:
            raise SystemExit("Гульня не знойдзена. Пакажыце каталог: --game \"…\"")
        game = input(f"Не знайшоў {payload['game']} у Steam. Устаўце шлях да каталога гульні\n"
                     f"(там, дзе {rel['exe']}): ").strip().strip('"')
    print(f"Гульня: {game}")
    if buildid and payload.get("steam_buildid") and buildid != payload["steam_buildid"]:
        print(f"Увага: версія гульні ({buildid}) не тая, пад якую рабіўся пераклад "
              f"({payload['steam_buildid']}). Пераклад ставіцца па ключах — новыя радкі,\n"
              + (f"калі яны ёсць, застануцца на мове «{rel['replaces']}»." if rel.get("replaces")
                 else "калі яны ёсць, застануцца на мове арыгінала."))
    if game_running(rel["exe"], game):
        print(f"\nЗачыніце {payload['game']} і запусціце ўсталёўшчык нанова.")
        pause(auto)
        return 1

    action = "install" if args.install else "uninstall" if args.uninstall else None
    if not action:
        now = "пераклад усталяваны" if engine.installed(game, payload) else "пераклад не ўсталяваны"
        print(f"Стан: {now}\n")
        print("  1 — усталяваць / абнавіць пераклад")
        print("  2 — выдаліць пераклад (вярнуць арыгінал)")
        print("  0 — выхад")
        action = {"1": "install", "2": "uninstall"}.get(input("> ").strip())
        if not action:
            return 0

    try:
        if action == "install":
            if rel.get("replaces"):
                print(f"\nУвага: пераклад ставіцца замест мовы «{rel['replaces']}» — пакуль ён усталяваны, "
                      "гэтай мовы ў гульні не будзе.")
            if ask("Усталяваць?", auto):
                engine.apply(game, payload, None, print)
                state.write(game, payload, "installer")
                print(f"\nГатова. У наладах гульні выберыце мову «{rel['language_name']}».")
        elif ask("Выдаліць пераклад?", auto):
            engine.restore(game, payload, print)
            state.remove(game)
            print("\nГатова: гульня зноў з арыгінальнымі файламі.")
    except PermissionError as e:
        print(f"\nНе атрымалася запісаць файл ({e.filename}). Зачыніце гульню; калі гульня ў "
              "Program Files — запусціце ўсталёўшчык ад імя адміністратара.")
        pause(auto)
        return 1
    pause(auto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
