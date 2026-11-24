"""payload, apply, restore, installed: наш пераклад → strings_<культура>.csv
і субтытры `<відэа>-Russian.srt` (гл. subtitles.py), а таксама І/і/Ў/ў у
TMP 1.x шрыфтах і `RussianFontLocTable` (fonts.py)."""
from __future__ import annotations

import json
import os
import shutil
import tempfile

from ... import tables as ttables
from ...config import Loc
from ...install.paths import inside, name as one
from ...install.target import Target
from . import subtitles as subs
from .common import SECTION, TABLE, csv_path, scanned_langs, target_path
from .norm import key_hash, normalize
from .table import escape, read_rows, write_rows


def payload(loc: Loc) -> dict:
    """Хэшы крыніцы толькі перакладзеных радкоў: apply прапусціць тыя, чый
    арыгінал змяніўся. Самога тэксту гульні ў payload няма. Для радкоў не з
    асноўнай крыніцы пішацца src_lang — каб apply ведаў, што зверыць у гульні
    (EN у файлах гульні няма, яго зверка — па source/ пасля extract)."""
    hashes, langs = {}, {}
    rows = ttables.load_all(loc).get(TABLE, []) if ttables.has_source(loc) else []
    if not rows:
        rows = ttables.load_repo(loc).get(TABLE, [])
    for r in rows:
        if not r["bel"] or not r["src_hash"]:
            continue
        hashes[r["key"]] = r["src_hash"]
        lang = r.get("src_lang") or loc.source_lang
        if lang != loc.source_lang:
            langs[r["key"]] = lang
    s = dict(loc.section(SECTION))
    fontmap = _fontmap(loc, s)
    s.pop("fontmap", None)                 # у payload — пары, а не шлях рэпазіторыя
    p = {"battletech_csv": s, "source_lang": loc.source_lang}
    if fontmap:
        p["fontmap"] = fontmap
    if loc.fallback_lang:
        p["fallback_lang"] = loc.fallback_lang
    if hashes:
        p["src_hash"] = {TABLE: hashes}
    if langs:
        p["src_lang"] = {TABLE: langs}
    sub = subs.payload(loc, s)
    if sub:
        p["subtitles"] = sub
    return p


def _fontmap(loc: Loc, s: dict) -> dict | None:
    """Пары FontLocTable з games/<гульня>/fontmap.json — толькі назвы шрыфтоў."""
    rel = s.get("fontmap")
    if not rel:
        return None
    path = loc.path(one(rel))
    if not os.path.exists(path):
        raise SystemExit(f"{loc.id}: няма {rel}")
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    pairs = []
    for pair in raw.get("pairs", []):
        if not isinstance(pair, list) or len(pair) != 2:
            raise SystemExit(f"{loc.id}: {rel}: пара мусіць быць [база, замена]")
        pairs.append([one(pair[0]), one(pair[1])])
    return {"table": raw.get("table", "RussianFontLocTable"),
            "culture": raw.get("culture", "ru-RU"), "pairs": pairs}


def _font_files(game_dir: str, s: dict) -> list[tuple[str, str]]:
    """(assets, resS) для ўсіх файлаў са шрыфтамі; шляхі — праз inside()."""
    names = s.get("font_assets") or []
    if not names:
        return []
    data = s.get("data_dir")
    res = s.get("font_resS") or {}
    if not data:
        raise SystemExit("battletech_csv: font_assets ёсць, а data_dir няма")
    out = []
    for a in names:
        a = one(a)
        r = res.get(a)
        if not r:
            raise SystemExit(f"battletech_csv: у font_resS няма запісу для {a}")
        out.append((inside(game_dir, data, a), inside(game_dir, data, one(r))))
    return out


def _apply_fonts(game_dir: str, s: dict, fontmap: dict | None,
                 out: str | None, log) -> int:
    from . import fonts

    files = _font_files(game_dir, s)
    if not files:
        return 0
    log("Шрыфты (І і Ў)…")
    changed = 0
    for assets_rel, resS_rel in files:
        ta, tr = Target(assets_rel), Target(resS_rel)
        base_a, base_r = ta.source(), tr.source()
        env, slices, n = fonts.patch_pair(base_a, base_r, fontmap, log,
                                          resS_name=os.path.basename(resS_rel))
        if not n:
            log(f"  {os.path.basename(assets_rel)}: змен няма")
            continue
        if out:
            os.makedirs(out, exist_ok=True)
            dst_a = os.path.join(out, os.path.basename(assets_rel))
            dst_r = os.path.join(out, os.path.basename(resS_rel))
        else:
            ta.base(), tr.base()                     # .orig перад запісам
            dst_a, dst_r = ta.path, tr.path
        with tempfile.TemporaryDirectory() as tmp:
            env.save(out_path=tmp)
            src = os.path.join(tmp, os.path.basename(assets_rel))
            if not os.path.exists(src):
                cand = [n for n in os.listdir(tmp) if not n.endswith(".resS")]
                if len(cand) != 1:
                    raise SystemExit(f"{os.path.basename(assets_rel)}: UnityPy не запісаў файл")
                src = os.path.join(tmp, cand[0])
            shutil.copyfile(src, dst_a)
        if out:
            shutil.copyfile(base_r, dst_r)
        with open(dst_r, "r+b") as f:
            for offset, blob, size in slices:
                if len(blob) != size:
                    raise SystemExit(f"{os.path.basename(resS_rel)}: слайс не таго памеру")
                f.seek(offset)
                f.write(blob)
        if not out:
            ta.written()
            tr.written()
        changed += n
    return changed


def check_path(payload: dict) -> str:
    return payload["battletech_csv"]["csv_dir"]


def _source_tables(game_dir: str, s: dict) -> dict[str, dict[str, str]]:
    """Ключ → тэкст для ўсіх моў гульні."""
    out = {}
    for lang, culture in scanned_langs(s):
        path = csv_path(game_dir, s, culture)
        if not os.path.exists(path):
            continue
        _, rows, _ = read_rows(Target(path).source())
        out[lang] = {key_hash(normalize(k)): v for _, k, v in rows if k}
    return out


def apply(game_dir: str, payload: dict, out: str | None = None, log=print) -> dict:
    s = payload["battletech_csv"]
    target = Target(target_path(game_dir, s))
    base = target.source() if out else target.base()
    header, rows, bad = read_rows(base)
    if bad:
        log(f"  у табліцы гульні {bad} радкоў з непадыходнай колькасцю калонак — прапушчаны")
    sources = _source_tables(game_dir, s)
    expected = payload.get("src_hash", {}).get(TABLE, {})
    src_lang = payload.get("src_lang", {}).get(TABLE, {})
    tr = payload["strings"].get(TABLE, {})

    done = stale = unknown = 0
    written = []
    for _, raw_key, value in rows:
        if not raw_key:
            written.append((raw_key, value))
            continue
        h = key_hash(normalize(raw_key))
        if h not in tr:
            written.append((raw_key, value))
            continue
        want = expected.get(h)
        lang = src_lang.get(h, payload.get("source_lang", "en"))
        if want and lang not in sources:
            # англійскай табліцы ў гульні няма: зверка толькі праз source/ пасля extract
            if lang != payload.get("source_lang", "en"):
                unknown += 1
                written.append((raw_key, value))
                continue
            written.append((raw_key, escape(tr[h])))
            done += 1
            continue
        current = sources[lang].get(h)
        if want and (current is None or ttables.src_hash(current) != want):
            stale += 1
            written.append((raw_key, value))       # гульня абнавілася пасля перакладу
            continue
        written.append((raw_key, escape(tr[h])))
        done += 1

    name = os.path.basename(target.path)
    if out:
        os.makedirs(out, exist_ok=True)
        dest = os.path.join(out, name)
        write_rows(dest, header, written)
        log(f"запісана {done} радкоў у {dest}")
    else:
        write_rows(target.path, header, written)
        target.written()
        log(f"запісана {done} радкоў у {target.path}")
    if stale:
        log(f"  арыгінал змяніўся ў {stale} — `extract` і `sync`, радкі пакінутыя як у гульні")
    if unknown:
        log(f"  не праверыць крыніцу ў {unknown} — у гульні няма адпаведнай табліцы")
    res = {"strings": done, "stale": stale, "unknown": unknown}
    res["fonts"] = _apply_fonts(game_dir, s, payload.get("fontmap"), out, log)
    res.update(subs.apply(game_dir, payload, out, log))
    return res


def restore(game_dir: str, payload: dict, log=print):
    s = payload["battletech_csv"]
    path = target_path(game_dir, s)
    if os.path.exists(path) or os.path.exists(path + ".orig"):
        log(f"  {os.path.basename(path)}: {Target(path).restore()}")
    for assets, resS in _font_files(game_dir, s):
        for p in (assets, resS):
            if os.path.exists(p) or os.path.exists(p + ".orig"):
                log(f"  {os.path.basename(p)}: {Target(p).restore()}")
    subs.restore(game_dir, payload, log)


def installed(game_dir: str, payload: dict) -> bool:
    s = payload["battletech_csv"]
    path = target_path(game_dir, s)
    ok = Target(path).installed() and subs.installed(game_dir, payload)
    for assets, resS in _font_files(game_dir, s):
        ok = ok and Target(assets).installed() and Target(resS).installed()
    return ok


def fonts_report(loc: Loc, need: set[int] | None = None):
    """`belloc fonts <гульня> [--text]`: што ёсць у TMP 1.x шрыфтах."""
    from . import fonts

    s = loc.section(SECTION)
    for assets, resS in _font_files(loc.game_dir, s):
        print(os.path.basename(assets) + ":")
        live = assets if os.path.exists(assets) else Target(assets).source()
        fonts.report(live, resS, need)

