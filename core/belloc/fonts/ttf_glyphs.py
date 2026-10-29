"""Дадае беларускія І/і у TTF-шрыфты, дзе іх няма (з Esoteric Ebb).

Шмат лацінска-кірылічных шрыфтоў (Jost з Google Fonts і інш.) не мае
І/і (U+0406/U+0456), хоць гэта адна з самых частых літар у беларускім
тэксце. Формы І/і супадаюць з лацінскімі I/i, таму дастаткова дапісаць
запісы ў cmap, паказаўшы на тыя ж гліфы. Ў/ў так не зробіш — калі іх няма,
скрыпт толькі паведамляе (для TMP-атласаў ёсць belloc.engines.unity_localization.tmp_fonts).

    python -m belloc ttf-glyphs <папка>            # праверыць (нічога не мяняе)
    python -m belloc ttf-glyphs <папка> --apply    # запісаць змены

Патрабуе fonttools.
"""
from __future__ import annotations

import glob
import os

ALIASES = {
    0x0406: 0x0049,  # І → I
    0x0456: 0x0069,  # і → i
}

BEL_ALPHABET = (
    "АБВГДЕЁЖЗІЙКЛМНОПРСТУЎФХЦЧШЫЬЭЮЯ"
    "абвгдеёжзійклмнопрстуўфхцчшыьэюя"
    "’"
)


def patch(path, apply_changes):
    from fontTools.ttLib import TTFont

    font = TTFont(path)
    cmap = font.getBestCmap()
    added = []
    for target, source in ALIASES.items():
        if target in cmap:
            continue
        glyph = cmap.get(source)
        if glyph is None:
            print(f"  {os.path.basename(path)}: няма нават U+{source:04X} — прапускаю")
            continue
        for table in font["cmap"].tables:
            table.cmap[target] = glyph
        added.append((target, glyph))

    missing = [c for c in BEL_ALPHABET if ord(c) not in font.getBestCmap()]
    name = os.path.basename(path)
    if added:
        chars = ", ".join(f"U+{u:04X}→{g}" for u, g in added)
        print(f"  {name}: {'дадана' if apply_changes else 'трэба дадаць'} {chars}")
        if apply_changes:
            font.save(path)
    if missing:
        print(f"  {name}: усё яшчэ няма {''.join(missing)}")
    return bool(added), bool(missing)


def run(fonts_dir: str, apply_changes: bool) -> int:
    paths = sorted(glob.glob(os.path.join(fonts_dir, "*.ttf")) +
                   glob.glob(os.path.join(fonts_dir, "*.otf")))
    if not paths:
        raise SystemExit(f"Шрыфтоў не знойдзена ў {fonts_dir}")
    print(f"Шрыфтоў: {len(paths)} у {fonts_dir}")
    changed = False
    for path in paths:
        c, _ = patch(path, apply_changes)
        changed = changed or c
    if changed and not apply_changes:
        print("\nЗапусці з --apply, каб запісаць змены.")
    elif not changed:
        print("Усе шрыфты ўжо маюць беларускія І/і.")
    return 1 if (changed and not apply_changes) else 0
