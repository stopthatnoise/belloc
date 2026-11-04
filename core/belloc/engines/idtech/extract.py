"""extract: файлы гульні → local/<гульня>/source/."""
from __future__ import annotations

import json
import os
import re
from collections import Counter

from ... import tables
from ...config import Loc
from .common import (EMPTY, NAMES, containers, find_lang, order, prefix_names, read_lang, sec,
                     speaker, split_prefix, table_of)


def write_json(path: str, data):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def package_name(base: str) -> str | None:
    p = os.path.join(base, "package.cfg")
    if not os.path.exists(p):
        return None
    m = re.search(r'build_packageName\s+"([^"]*)"', open(p, encoding="utf-8", errors="replace").read())
    return m and m.group(1)


def extract(loc: Loc, out: str | None = None):
    s = sec(loc)
    out = out or loc.source
    os.makedirs(out, exist_ok=True)
    base = loc.game(s.get("base", "base"))
    langs = [loc.source_lang] + tables.hint_langs(loc)
    var = {c: int(s["langs"][c]) for c in langs}
    texts = {c: read_lang(base, var[c]) for c in langs}
    src = texts[loc.source_lang]
    target = s.get("target", "ru")
    tgt = texts.get(target) or read_lang(base, int(s["langs"][target]))

    res: dict[str, dict[str, dict[str, str]]] = {c: {} for c in langs}
    context: dict[str, dict[str, str]] = {}
    names: dict[str, dict[str, Counter]] = {c: {} for c in langs}
    skipped = only_target = 0
    original = set(s.get("original", []))
    for key in sorted(src, key=lambda k: (table_of(k), order(k))):
        pre, text = split_prefix(src[key])
        if key in original:
            skipped += 1
            continue
        if EMPTY.match(text):
            # у арыгінале пуста, а мова target паказвае свой тэкст (падзагаловак назвы
            # гульні, рэмаркі «(пыхціць)»): без перакладу ён застаўся б рускім.
            # Толькі ASCII («A» для #str_key_a) — і так не рускі, не бярэм
            own = split_prefix(tgt.get(key, ""))[1]
            if EMPTY.match(own) or own.isascii():
                skipped += 1
                continue
            only_target += 1
        table = table_of(key)
        en_names = prefix_names(pre)
        for c in langs:
            p2, t2 = split_prefix(texts[c].get(key, ""))
            res[c].setdefault(table, {})[key] = t2
            for n, n2 in zip(en_names, prefix_names(p2) if c != loc.source_lang else en_names):
                names[c].setdefault(n, Counter())[n2] += 1
        ctx = " · ".join(x for x in (speaker(key), " ".join(dict.fromkeys(en_names))) if x)
        if ctx:
            context.setdefault(table, {})[key] = ctx
    for c in langs:                           # падказка — найчасцейшы варыянт
        res[c][NAMES] = {n: names[c][n].most_common(1)[0][0] if n in names[c] else ""
                         for n in sorted(names[loc.source_lang])}

    for c in langs:
        write_json(os.path.join(out, f"{c}.json"), res[c])
    write_json(os.path.join(out, "context.json"), context)
    tgt_path, tgt = find_lang(base, int(s["langs"][s.get("target", "ru")]))
    meta = {"package": package_name(base), "steam_buildid": loc.steam_buildid(),
            "containers": containers(base), "target_container": os.path.basename(tgt_path).removesuffix(".orig"),
            "strings": {c: sum(len(kv) for kv in res[c].values()) for c in langs}}
    write_json(os.path.join(out, "meta.json"), meta)
    n = Counter(t.split("/")[0] + ("/" + t.split("/")[1] if t.startswith("vo/") else "") for t in res[loc.source_lang])
    print(f"радкоў: {meta['strings'][loc.source_lang]} у {len(res[loc.source_lang])} табліцах "
          f"({', '.join(f'{k} {v}' for k, v in sorted(n.items()))}); пустых і [none]: {skipped}; "
          f"пустых у арыгінале, але з тэкстам {target}: {only_target}; "
          f"імёнаў над субтытрамі: {len(res[loc.source_lang][NAMES])}")
    print(f"зборка {meta['package']}, мова {s.get('target', 'ru')} — у {meta['target_container']}")
