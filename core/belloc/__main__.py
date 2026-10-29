"""belloc — агульныя інструменты беларускіх лакалізацый гульняў.

    python -X utf8 -m belloc <каманда> <гульня> [опцыі]

<гульня> — імя папкі ў games/ (silver-pines) або шлях да яе. Тэкст гульні,
працоўныя файлы і даклады — у local/<гульня>/, у рэпазіторыі — толькі наш пераклад.

Пераклад (любы рухавік):
  sync       local/<гульня>/source/ → games/<гульня>/translation/*.csv + прагрэс
  stats      прагрэс перакладу па табліцах (працуе і без тэксту гульні)
  pairs      {арыгінал: bel} у build/pairs.json
  lint       pairs + лінтэр з гласарыем, белымі спісамі і слоўнікамі → build/lint_report.md
             (лішнія опцыі ідуць у лінтэр: --checks, --skip, --max-print …)
  glossary   праверыць glossary.json і сабраць build/glossary.md (--check)
  idioms     выразы «Антыкалькі» ў рускім слупку → build/idioms.md (для вычыткі; --only-idioms)
  fantasy-report  тэрміны «Дапаможніка для перакладчыкаў фэнтэзі» ў гульні → build/fantasy.md
  batch      пачкі для паралельнай працы: batch status|export|lint|apply <гульня> [пачкі…]

Без гульні:
  list                  спіс гульняў
  dicts [--force] [імёны…]  спампаваць слоўнікі ў local/dicts/
  antykalka СЛОВЫ… [--exact|--reverse]  рус.→бел. слоўнік без калек
  fantasy СЛОВЫ… [--exact|--reverse|--all]  англ.→бел. тэрміны фэнтэзі і D&D
"""
from __future__ import annotations

import argparse
import os
import sys

from . import batch, config, dicts, glossary, tables


def run_lint(loc, pairs, report, extra):
    """Лінтэр з гласарыем, белымі спісамі і слоўнікамі гэтай гульні."""
    from . import lint
    argv = ["belloc.lint", "--pairs", pairs, "--report", report, *dicts.lint_args()]
    if os.path.exists(loc.glossary):
        argv += ["--glossary", loc.glossary]
    if loc.lint_allow:
        argv += ["--allow", *loc.lint_allow]
    argv += loc.raw.get("lint_args", []) + extra
    if not dicts.lint_args():
        print("(слоўнікаў няма — spell/names/ruwords выключаныя; `python -m belloc dicts`)")
    sys.argv = argv
    return lint.main()


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m belloc", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def with_loc(name, help_):
        p = sub.add_parser(name, help=help_)
        p.add_argument("loc", help="імя ў games/ або шлях")
        return p

    sub.add_parser("list", help="спіс гульняў")
    p = sub.add_parser("dicts", help="спампаваць слоўнікі")
    p.add_argument("names", nargs="*", help=f"толькі гэтыя: {', '.join(dicts.NAMES)}")
    p.add_argument("--force", action="store_true")
    p = sub.add_parser("antykalka", help="слоўнік «Антыкалька»: рус. → бел.")
    p.add_argument("words", nargs="+", help="рускае слова/выраз (пачатак) або, з --reverse, беларускае")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--exact", action="store_true", help="толькі дакладны загаловак")
    g.add_argument("--reverse", action="store_true", help="шукаць сярод беларускіх адпаведнікаў")
    p.add_argument("--limit", type=int, default=30)
    p.add_argument("--no-stress", action="store_true", help="не паказваць націскі")
    p = sub.add_parser("fantasy", help="«Дапаможнік для перакладчыкаў фэнтэзі»: англ. → бел.")
    p.add_argument("words", nargs="+", help="англійскі тэрмін (пачатак) або, з --reverse, беларускае слова")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--exact", action="store_true", help="толькі дакладны тэрмін")
    g.add_argument("--reverse", action="store_true", help="шукаць сярод беларускіх адпаведнікаў")
    p.add_argument("--all", action="store_true", help="паказаць усе мовы слоўніка")
    p.add_argument("--limit", type=int, default=30)

    with_loc("sync", "абнавіць CSV")
    with_loc("stats", "прагрэс")
    p = with_loc("pairs", "пары для лінтэра")
    p.add_argument("--out")
    with_loc("lint", "лінтэр")
    p = with_loc("glossary", "гласарый")
    p.add_argument("--check", action="store_true")
    p = with_loc("idioms", "устойлівыя выразы ў RU → даклад")
    p.add_argument("--only-idioms", action="store_true", help="толькі выразы з паметай перан./разм.")
    p.add_argument("--out", help="іншы файл даклада")
    p = with_loc("fantasy-report", "тэрміны фэнтэзі ў гульні → даклад")
    p.add_argument("--out", help="іншы файл даклада")
    p.add_argument("--examples", type=int, default=5, help="колькі радкоў паказваць на тэрмін")
    p = sub.add_parser("batch", help="пачкі для паралельнай працы")
    p.add_argument("action", choices=["status", "export", "lint", "apply"])
    p.add_argument("loc")
    p.add_argument("names", nargs="*", help="пачкі (або ўсе пачкі хвалі --wave)")
    p.add_argument("--wave", type=int, help="усе пачкі гэтай хвалі")
    p.add_argument("--force", action="store_true", help="export: перазапісаць work/")
    p.add_argument("--dry-run", action="store_true", help="apply: толькі паказаць")

    args, extra = ap.parse_known_args(argv)
    if extra and args.cmd not in ("lint", "batch"):
        ap.error(f"невядомыя аргументы: {' '.join(extra)}")

    if args.cmd == "list":
        if os.path.isdir(config.GAMES):
            for name in sorted(os.listdir(config.GAMES)):
                if os.path.exists(os.path.join(config.GAMES, name, "game.json")):
                    loc = config.load(name)
                    print(f"  {name:20} {loc.name} ({loc.engine})")
        return 0
    if args.cmd == "dicts":
        dicts.fetch(args.force, args.names)
        return 0
    if args.cmd == "antykalka":
        from . import antykalka
        antykalka.search(args.words, args.exact, args.reverse, args.limit, args.no_stress)
        return 0
    if args.cmd == "fantasy":
        from . import fantasy
        fantasy.search(args.words, args.exact, args.reverse, args.all, args.limit)
        return 0

    loc = config.load(args.loc)
    if args.cmd == "sync":
        tables.sync(loc)
    elif args.cmd == "stats":
        tables.stats(loc)
    elif args.cmd == "pairs":
        tables.pairs(loc, args.out or os.path.join(loc.build, "pairs.json"))
    elif args.cmd == "lint":
        pairs = os.path.join(loc.build, "pairs.json")
        tables.pairs(loc, pairs)
        return run_lint(loc, pairs, os.path.join(loc.build, "lint_report.md"), extra)
    elif args.cmd == "idioms":
        from . import antykalka
        return antykalka.idioms_report(loc, args.out or os.path.join(loc.build, "idioms.md"),
                                       args.only_idioms)
    elif args.cmd == "fantasy-report":
        from . import fantasy
        return fantasy.report(loc, args.out or os.path.join(loc.build, "fantasy.md"), args.examples)
    elif args.cmd == "batch":
        names = args.names
        if args.wave is not None:
            names += [n for n, b in batch.spec(loc).items() if b.get("wave") == args.wave]
        if args.action != "status" and not names:
            ap.error("пазначце пачкі або --wave N")
        if extra and args.action != "lint":
            ap.error(f"невядомыя аргументы: {' '.join(extra)}")
        if args.action == "status":
            batch.status(loc)
        elif args.action == "export":
            batch.export(loc, names, args.force)
        elif args.action == "apply":
            batch.apply(loc, names, args.dry_run)
        else:
            code = 0
            for n in names:
                code |= run_lint(loc, batch.pairs(loc, n),
                                 os.path.join(loc.build, f"lint-{n}.md"), extra) or 0
            return code
    elif args.cmd == "glossary":
        return glossary.run(loc.glossary, os.path.join(loc.build, "glossary.md"),
                            loc.name, args.check)
    return 0


if __name__ == "__main__":
    sys.exit(main())
