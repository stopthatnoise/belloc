"""payload, apply, restore, installed: наш пераклад → файлы гульні (або --out)."""
from __future__ import annotations

import os

from ...config import Loc
from . import pak
from .common import locres_path, read_locres, sec, table_name, targets


def build_mod(game_dir: str, s: dict, source_lang: str, texts: dict[str, dict[str, str]],
              dest: str, log=print) -> int:
    """Мод-пак з locres культуры target (па адным на мэту), дзе texts замяняюць арыгінал."""
    files, n = {}, 0
    for target, pak_path in targets(s).items():
        p = pak.Pak(os.path.join(game_dir, pak_path), s.get("aes_key"))
        try:
            base = read_locres(game_dir, s, source_lang, target, p)
            t = {ns: texts[table_name(target, ns)] for ns in base.to_dict()
                 if table_name(target, ns) in texts}
            if not t:
                continue
            lr = read_locres(game_dir, s, s["target"], target, p)
            n += lr.replace(t)
            n += lr.add_missing(base, t)
        finally:
            p.close()
        files[locres_path(s, s["target"], target)] = lr.save()
    files.update(patched_fonts(game_dir, s, log))
    pak.write(dest, files)
    return n


def patched_fonts(game_dir: str, s: dict, log=print) -> dict[str, bytes]:
    """Шрыфты з дададзенай кірыліцай (font_patches, гл. fonts.py) — {шлях у паку: байты}."""
    if not s.get("font_patches"):
        return {}
    from . import fonts
    p = pak.Pak(os.path.join(game_dir, targets(s)[s.get("font_patches_target")]), s.get("aes_key"))
    out = {}
    try:
        for fp in s["font_patches"]:
            data, n = fonts.add_glyphs(p.read(fp["target"]), p.read(fp["source"]), fp.get("xscale", 1.0))
            if n:
                out[fp["target"]] = data
            log(f"шрыфт {fp['target'].rsplit('/', 1)[-1]}: +{n} гліфаў")
    finally:
        p.close()
    return out


def payload(loc: Loc) -> dict:
    return {"unreal": sec(loc), "source_lang": loc.source_lang}


def check_path(payload: dict) -> str:
    return next(iter(targets(payload["unreal"]).values()))


def apply(game_dir: str, payload: dict, out: str | None = None, log=print) -> dict:
    """Мод-пак у ~mods (файлы гульні не мяняюцца) або, з out, у гэтую папку."""
    s = payload["unreal"]
    mod = os.path.join(game_dir, s["mod"])
    dest = os.path.join(out, os.path.basename(mod)) if out else mod
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    n = build_mod(game_dir, s, payload["source_lang"], payload["strings"], dest, log)
    log(f"падменена радкоў: {n} → {dest} ({os.path.getsize(dest) // 1024} КБ)")
    return {"strings": n}


def restore(game_dir: str, payload: dict, log=print):
    mod = os.path.join(game_dir, payload["unreal"]["mod"])
    if os.path.exists(mod):
        os.remove(mod)
        log(f"выдалена: {mod}")
    else:
        log(f"мода няма: {mod}")


def installed(game_dir: str, payload: dict) -> bool:
    return os.path.exists(os.path.join(game_dir, payload["unreal"]["mod"]))
