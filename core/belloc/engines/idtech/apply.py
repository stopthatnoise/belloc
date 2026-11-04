"""payload, apply, restore, installed: наш пераклад → кантэйнер .resources гульні (або --out)."""
from __future__ import annotations

import os
from collections import Counter

from ...config import Loc
from ...install.paths import inside
from ...install.target import Target, write_to
from . import lang, resources
from .common import NAME_TAG, NAMES, containers, find_lang, read_lang, sec, split_prefix


def build_lang(items, en: dict[str, str], strings: dict[str, dict[str, str]],
               rename: dict[str, str]) -> tuple[list, int]:
    """Радкі мовы target з нашым перакладам. Пачатак рэплікі ([name:…], [p-5]…) —
    з арыгінала; імёны — з NAMES, а дзе іх няма — як былі ў мове target."""
    cur = {k: t for _, k, t in items}
    names = {k: v for k, v in strings.get(NAMES, {}).items() if v}
    seen: dict[str, Counter] = {}                 # імя ў арыгінале → як яно ў target
    for k, t in en.items():
        a, b = split_prefix(t)[0], split_prefix(cur.get(k, ""))[0]
        for x, y in zip(NAME_TAG.findall(a), NAME_TAG.findall(b)):
            seen.setdefault(x.strip(), Counter())[y] += 1

    def name(m):
        n = m.group(1).strip()
        return "[name:" + (names.get(n) or (seen[n].most_common(1)[0][0] if n in seen else n)) + "]"

    bel = {k: v for t, kv in strings.items() if t != NAMES for k, v in kv.items() if v}
    out, n = [], 0
    for h, k, t in items:
        if k in rename:
            t = rename[k]
        elif k in bel:
            t = NAME_TAG.sub(name, split_prefix(en.get(k, ""))[0]) + split_prefix(bel[k])[1]
            n += 1
        out.append((h, k, t))
    return out, n


def _args(game_dir: str, payload: dict):
    g = payload["idtech"]
    return (inside(game_dir, g.get("base", "base")), {c: int(v) for c, v in g["langs"].items()},
            g.get("target", "ru"), payload["source_lang"], g.get("rename", {}), g.get("original", []))


def apply(game_dir: str, payload: dict, out: str | None = None, log=print) -> dict:
    base, langs, target, source_lang, rename, original = _args(game_dir, payload)
    log("Чытаю тэкст гульні…")
    en = read_lang(base, langs[source_lang])
    rename = {**{k: en[k] for k in original if k in en}, **rename}
    src_path, _ = find_lang(base, langs[target])
    game_path = src_path.removesuffix(".orig")
    n_done = 0

    def write(src: str, dst: str):
        nonlocal n_done
        r = next(r for r in resources.read_table(src)
                 if r.type == "lang" and r.name == "strings" and r.variation == langs[target])
        items, n_done = build_lang(lang.parse(resources.read_data(src, r)), en, payload["strings"], rename)
        with open(src, "rb") as f:
            data = resources.replace(f.read(), r.index, lang.build(items))
        with open(dst, "wb") as f:
            f.write(data)

    dst = write_to(Target(game_path), out, write)
    log(f"  радкоў перакладу: {n_done}; імёнаў: {len([v for v in payload['strings'].get(NAMES, {}).values() if v])}")
    log(f"→ {dst}")
    return {"written": [os.path.basename(game_path)]}


def payload(loc: Loc) -> dict:
    s = sec(loc)
    target = s.get("target", "ru")
    return {"idtech": {"base": s.get("base", "base"), "target": target,
                       "langs": {c: int(s["langs"][c]) for c in (loc.source_lang, target)},
                       "rename": s.get("rename", {}), "original": s.get("original", [])},
            "source_lang": loc.source_lang}


def check_path(payload: dict) -> str:
    return payload["idtech"].get("base", "base") + "/packagemapspec_pc.json"


def _targets(base: str) -> list[Target]:
    return [Target(inside(base, n)) for n in containers(base)]


def restore(game_dir: str, payload: dict, log=print):
    base = _args(game_dir, payload)[0]
    did = False
    for t in _targets(base):
        if os.path.exists(t.orig) or os.path.exists(t.mark):
            log(f"  {os.path.basename(t.path)}: {t.restore()}")
            did = True
    if not did:
        log("  пераклад не ўсталяваны")


def installed(game_dir: str, payload: dict) -> bool:
    return any(t.installed() and t.ours() for t in _targets(_args(game_dir, payload)[0]))
