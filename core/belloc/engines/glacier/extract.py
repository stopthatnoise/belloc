"""extract: файлы гульні → local/<гульня>/source/."""
from __future__ import annotations

import json
import os
import re
from collections import Counter

from ... import tables
from ...config import Loc
from . import rpkg, scenes
from .dlge import CATEGORY, CODE, SPEAKER, Dlge, split
from .locr import Locr
from .common import SPEAKERS, base_packagedefinition, sec, speaker_key, voice_gender


def runtime(loc: Loc) -> str:
    return loc.game(sec(loc).get("runtime", "Runtime"))


def keys(loc: Loc) -> tuple[tuple[int, ...], tuple[int, ...]]:
    k = sec(loc)["keys"]
    return rpkg.parse_key(k["text"]), rpkg.parse_key(k["packagedefinition"])


def write_json(path: str, data):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def exe_version(path: str) -> str | None:
    if not os.path.exists(path):
        return None
    b = open(path, "rb").read()
    i = b.find("FileVersion".encode("utf-16-le"))
    if i < 0:
        return None
    m = re.match(r"FileVersion\0+([\d.]+)", b[i:i + 80].decode("utf-16-le", "replace"))
    return m and m.group(1)


def voice_group(code: str) -> str:
    return re.sub(r"\d+$", "", code.split("_")[0]) or "-"


def dlg_key(h: int, i: int) -> str:
    return f"{h:016X}:{i}"


def extract(loc: Loc, out: str | None = None):
    text_key, pkg_key = keys(loc)
    out = out or loc.source
    os.makedirs(out, exist_ok=True)
    rt = runtime(loc)
    arc = rpkg.Archive(rt)
    langs = [loc.source_lang] + tables.hint_langs(loc)
    res: dict[str, dict[str, dict[str, str]]] = {c: {} for c in langs}
    context: dict[str, dict[str, str]] = {}

    # LOCR: расшыфроўваем усё патрэбнае адным праходам
    jobs = []                                 # (мова, табліца, ключ, блок)
    for e, d in arc.read_all(arc.of_type("LOCR")):
        lc = Locr(d)
        src = lc.lang(loc.source_lang)
        if not src:
            continue
        table = f"ui/{e.hash:016X}"
        for c in langs:
            for h, enc in (lc.lang(c) or {}).items():
                if h in src:
                    jobs.append((c, table, f"{h:08X}", enc))
    # DLGE
    wav_jobs = []                             # (DLGE, нумар, мова, блок)
    for e, d in arc.read_all(arc.of_type("DLGE")):
        for i, w in enumerate(Dlge(d).wavs):
            if w.enc(loc.source_lang):
                for c in langs:
                    wav_jobs.append((e.hash, i, c, w.enc(c)))
    plain = rpkg.decrypt_many([j[3] for j in jobs] + [j[3] for j in wav_jobs], text_key)

    for (c, table, key, _), p in zip(jobs, plain):
        res[c].setdefault(table, {})[key] = rpkg.blob_text(p)
    # юрыдычныя тэксты (EULA, privacy, правілы сэрвісу): доўгія радкі рэсурсу, дзе
    # ёсць «IO Interactive A/S» — у note «legal», каб пачкі іх абміналі
    legal = 0
    for table, kv in res[loc.source_lang].items():
        if any("IO Interactive A/S" in t for t in kv.values()):
            for key, t in kv.items():
                if len(t) > 3000:
                    context.setdefault(table, {})[key] = "legal"
                    legal += 1

    subs: dict[tuple[int, int], dict[str, str]] = {}
    for (h, i, c, _), p in zip(wav_jobs, plain[len(jobs):]):
        subs.setdefault((h, i), {})[c] = rpkg.blob_text(p)
    _, pd_text = rpkg.read_packagedefinition(base_packagedefinition(rt), pkg_key)
    missions = sec(loc).get("missions", [])
    where = scenes.places(arc, pd_text, missions) if missions else {}
    m_order = {name: n for n, (_, name) in enumerate(missions)}

    def place_key(h: int, i: int):
        p = where.get(h)
        if p is None or p.mission is None:
            return (len(missions), "", 0, h, i)
        return (m_order[p.mission], p.segment or "~", p.order, h, i)

    speakers: dict[str, dict[str, Counter]] = {c: {} for c in langs}
    n_sub = 0
    for (h, i) in sorted(subs, key=lambda x: place_key(*x)):
        by_lang = subs[(h, i)]
        head, text = split(by_lang[loc.source_lang])
        if not text.strip():
            continue
        cat = CATEGORY.search(head)
        cat = cat.group(1).removeprefix("DX_") if cat else "-"
        code = CODE.search(head)
        code = code.group(1) if code else "-"
        p = where.get(h)
        if p is not None and p.mission:
            table = f"dlg/{p.mission}/{p.segment or '_shared'}"
        elif where:
            table = f"dlg/_common/{cat}/{voice_group(code)}"
        else:
            table = f"dlg/{cat}/{voice_group(code)}"
        key = dlg_key(h, i)
        sp = SPEAKER.search(head)
        name = sp.group(1) if sp else ""
        g = voice_gender(code)
        for c in langs:
            res[c].setdefault(table, {})[key] = split(by_lang.get(c, ""))[1]
            if name:
                s2 = SPEAKER.search(split(by_lang.get(c, ""))[0])
                s2 = s2.group(1) if s2 else ""
                if c != loc.source_lang and s2 == code != name:  # у слоце uk замест імя — код голасу
                    s2 = ""
                speakers[c].setdefault(speaker_key(name, g), Counter())[s2] += 1
        nseg = text.count("\n") + 1
        context.setdefault(table, {})[key] = " · ".join(
            x for x in (f"{code} {g}".strip(), name, cat, f"{nseg} кавалкі — {nseg} радкі" if nseg > 1 else "") if x)
        n_sub += 1
    for c in langs:                           # падказка — найчасцейшы варыянт
        res[c][SPEAKERS] = {k: v.most_common(1)[0][0] for k, v in speakers[c].items()}

    for c in langs:
        write_json(os.path.join(out, f"{c}.json"), res[c])
    write_json(os.path.join(out, "context.json"), context)
    meta = {"exe_version": exe_version(loc.game(sec(loc).get("exe", ""))),
            "steam_buildid": loc.steam_buildid(),
            "patchlevel": dict(rpkg.patchlevels(pd_text)),
            "official_patches": {str(c): arc.latest_patch(c) for c in arc.chunks},
            "strings": {c: sum(len(kv) for kv in res[c].values()) for c in langs}}
    write_json(os.path.join(out, "meta.json"), meta)
    n_ui = sum(len(v) for k, v in res[loc.source_lang].items() if k.startswith("ui/"))
    print(f"інтэрфейс (LOCR): {n_ui} радкоў у {sum(1 for k in res[loc.source_lang] if k.startswith('ui/'))} "
          f"табліцах (юрыдычных: {legal}); субтытры (DLGE): {n_sub}; прамоўцаў: {len(speakers[loc.source_lang])}")
    print(f"версія {meta['exe_version']}, patchlevel {meta['patchlevel']}")
