"""extract: файлы гульні → local/<гульня>/source/.

Чытае табліцы мовы гульні (`strings_<культура>.csv`), будуе ключы-хэшы і
аднаўляе англійскую крыніцу з даных, субтытраў, DLL і сцэн. Вынік — у
`local/<гульня>/source/` (тэкст гульні ў рэпазіторый не трапляе).
"""
from __future__ import annotations

import json
import os
import time

from ...config import Loc
from ...install.target import Target
from .common import NORM, SECTION, TABLE, csv_path, scanned_langs
from .english import recover
from .norm import key_hash, normalize
from .table import read_rows


def _write_json(path: str, data):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=0, sort_keys=True)
        f.write("\n")


def _version(data_dir: str) -> dict:
    path = os.path.join(data_dir, "StreamingAssets", "version.json")
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return {}


def extract(loc: Loc, out: str | None = None):
    s = loc.section(SECTION)
    out = out or loc.source
    os.makedirs(out, exist_ok=True)
    game = loc.game_dir
    data_dir = loc.game(s["data_dir"])
    target_lang = s.get("target", "ru")
    t0 = time.time()

    by_lang: dict[str, dict[str, str]] = {}
    row_index: dict[str, int] = {}
    keys: dict[str, str] = {}             # нармалізаваны ключ → хэш
    key_text: dict[str, str] = {}         # хэш → нармалізаваны ключ
    duplicates = nonnorm = 0
    for lang, culture in scanned_langs(s):
        path = csv_path(game, s, culture)
        if not os.path.exists(path):
            raise SystemExit(f"няма табліцы гульні {path}")
        # чытаем арыгінал: у гульні можа стаяць наш патч (або спайк) з .orig
        path = Target(path).source()
        header, rows, bad = read_rows(path)
        if not header.upper().startswith("KEY"):
            raise SystemExit(f"{path}: загаловак «{header}» — чакаўся KEY,…")
        if bad:
            print(f"{culture}: радкоў з непадыходнай колькасцю калонак: {bad} (гульня іх адкідае)")
        values: dict[str, str] = {}
        for n, raw_key, value in rows:
            if not raw_key:
                continue
            norm = normalize(raw_key)
            h = key_hash(norm)
            if raw_key != norm:
                nonnorm += 1
            if h in values:
                duplicates += 1
                continue
            values[h] = value
            if lang == target_lang:
                keys.setdefault(norm, h)
                key_text.setdefault(h, norm)
                row_index.setdefault(h, n - 2)
        by_lang[lang] = values
        print(f"{culture}: радкоў {len(rows)}, ключоў {len(values)}")
    target = by_lang[target_lang]
    if len(set(keys.values())) != len(keys):
        raise SystemExit("key_hash: калізія ключоў")

    stats = {"json_files": 0, "json_bad": 0, "dll_files": 0, "dll_bad": 0,
             "srt_files": 0, "asset_files": 0}
    print("пошук англійскай крыніцы…")
    found = recover(data_dir, os.path.join(data_dir, "StreamingAssets", "data"),
                    loc.game(s.get("subtitles", "")), keys, key_text, stats,
                    s.get("scan"))

    missing = {h: {"key": key_text[h], "chars": len(key_text[h])}
               for h in target if h not in found}
    for lang, values in by_lang.items():
        _write_json(os.path.join(out, f"{lang}.json"), {TABLE: values})
    _write_json(os.path.join(out, "en.json"), {TABLE: {h: r["en"] for h, r in found.items()}})

    # нашы заўвагі для працоўных файлаў (ctx: …): якасць англійскай крыніцы або
    # адсутнасць любой крыніцы. Гэта не тэкст гульні.
    ctx, prov = {}, {}
    de = by_lang.get("de", {})
    last = by_lang.get(loc.last_resort or "", {})
    for h in target:
        rec = found.get(h)
        use = "en" if rec else ("de" if de.get(h) else ("ru" if last.get(h) else ""))
        if rec:
            prov[h] = {"src": rec["src"], "at": rec["at"], "q": rec["q"], "hits": rec["hits"]}
        prov.setdefault(h, {})["use"] = use
        # ctx: машыначытальныя ключы для пачак (at=, use=, q=) і чалавечы хвост.
        # Гэта не тэкст гульні: толькі шляхі, коды і нашыя заўвагі. `at` — шлях
        # крыніцы (json#/…, dll#us@…, resources.assets@…), `use` — адкуль радок.
        parts = []
        if rec:
            parts.append(f"at={rec['at']}")
        parts.append(f"use={use}")
        if rec:
            parts.append(f"q={rec['q']}")
        text = rec["en"] if rec else (de.get(h) or last.get(h) or "")
        parts.append(f"len={len(text)}")
        line = "; ".join(parts)
        if rec and rec["q"] == "keylike":
            line += " — прабелы страчаныя"
        elif not use:
            line += " — няма крыніцы, патрэбна ru"
        ctx[h] = line
    _write_json(os.path.join(out, "context.json"), {TABLE: ctx} if ctx else {})
    _write_json(os.path.join(out, "provenance.json"), {TABLE: prov})
    _write_json(os.path.join(out, "rows.json"), {TABLE: row_index})
    _write_json(os.path.join(out, "keys.json"), {h: key_text[h] for h in key_text})
    _write_json(os.path.join(out, "missing.json"), missing)

    ver = _version(data_dir)
    by_src = {}
    for rec in found.values():
        by_src[rec["src"]] = by_src.get(rec["src"], 0) + 1
    meta = {
        "engine": "battletech-csv",
        "norm": NORM,
        "game_version": ver.get("ProductVersion") or ver.get("Version") or ver.get("version"),
        "build_number": ver.get("BuildNumber"),
        "build_revision": ver.get("BuildRevision"),
        "build_date": ver.get("BuildDate"),
        "steam_buildid": loc.steam_buildid(),
        "rows": {lang: len(values) for lang, values in by_lang.items()},
        "keys": len(target),
        "key_duplicates": duplicates,
        "key_not_normalized": nonnorm,
        "en": {
            "found": len(found),
            "missing": len(missing),
            "by_src": by_src,
            "keylike": sum(1 for r in found.values() if r["q"] == "keylike"),
        },
        "scan": stats,
        "seconds": round(time.time() - t0, 1),
    }
    _write_json(os.path.join(out, "meta.json"), meta)

    pct = len(found) / max(1, len(target))
    lines = [
        "# BATTLETECH — англійская крыніца (генераваны файл)",
        "",
        "радкоў: " + ", ".join(f"{k} {v}" for k, v in sorted(meta["rows"].items())),
        f"ключаў: {len(target)} (паўтораў {duplicates}, не нармалізаваных {nonnorm})",
        f"англійская знойдзеная: **{len(found)}** ({pct:.1%}), няма {len(missing)}",
        "адкуль: " + ", ".join(f"{k} {v}" for k, v in sorted(by_src.items())),
        f"key-like (без прабелаў): {meta['en']['keylike']}",
        "скан: " + ", ".join(f"{k} {v}" for k, v in stats.items()),
        f"час: {meta['seconds']} с",
        "",
        "Без англійскай — крыніца нямецкая (fallback_lang); зусім без крыніцы — "
        "спіс у context.json і ў рабоце праз `src_lang: ru` (спрэчны выпадак).",
    ]
    with open(os.path.join(out, "report.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"запісана: {out}")
