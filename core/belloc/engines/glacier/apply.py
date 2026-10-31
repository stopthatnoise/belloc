"""payload, apply, restore, installed: наш пераклад → файлы гульні (або --out)."""
from __future__ import annotations

import os
import re
import shutil

from ... import tables
from ...config import Loc
from ...install.paths import inside
from . import rpkg
from .dlge import CODE, SPEAKER, Dlge, join, segments, split
from .locr import Locr
from .common import SPEAKERS, base_packagedefinition, sec, speaker_key, voice_gender


def build_rt(rt: str, texts: dict[str, dict[str, str]], dest: str, target: str, source_lang: str,
             text_key, pkg_key, pat=None) -> list[str]:
    """Патчы chunkNpatchM.rpkg і packagedefinition.txt у dest. Вяртае імёны файлаў.

    pat — рэгулярка кавалкаў арыгінала (tables.from_original): заглушкі `[]` у
    інтэрфейсе бяруцца з радка мовы source_lang той жа LOCR."""
    arc = rpkg.Archive(rt)
    header, pd = rpkg.read_packagedefinition(base_packagedefinition(rt), pkg_key)
    levels = rpkg.patchlevels(pd)

    out: dict[int, list[tuple[rpkg.Entry, bytes]]] = {}
    n_ui = n_sub = miss = left = 0
    for table, kv in texts.items():
        if not table.startswith("ui/") or not kv:
            continue
        e = arc.entries.get(int(table[3:], 16))
        if e is None:
            miss += len(kv)
            continue
        lc = Locr(rpkg.read(e))
        tgt = lc.lang(target)
        src = (lc.lang(source_lang) or {}) if pat else {}
        changed = False
        for key, bel in kv.items():
            h = int(key, 16)
            if tgt is None or h not in tgt:
                miss += 1
                continue
            if pat and tables.PLACEHOLDER in bel:
                orig = rpkg.blob_text(rpkg.decrypt(src[h], text_key)) if h in src else ""
                bel = tables.expand(bel, orig, pat)
                left += tables.PLACEHOLDER in bel
            enc = rpkg.encrypt(rpkg.text_blob(bel), text_key)
            changed |= enc != tgt[h]
            tgt[h] = enc
            n_ui += 1
        if changed:
            out.setdefault(arc.chunk_of[e.hash], []).append((e, lc.build()))

    speakers = {k: v for k, v in texts.get(SPEAKERS, {}).items() if v}
    lines: dict[int, dict[int, str]] = {}
    for table, kv in texts.items():
        if table.startswith("dlg/") and table != SPEAKERS:
            for key, bel in kv.items():
                h, _, i = key.partition(":")
                lines.setdefault(int(h, 16), {})[int(i)] = bel
    want = arc.of_type("DLGE") if speakers else [arc.entries[h] for h in lines if h in arc.entries]
    miss += sum(len(v) for h, v in lines.items() if h not in arc.entries)
    parsed = [(e, Dlge(d)) for e, d in arc.read_all(want)]
    blobs = []
    for _, g in parsed:
        for w in g.wavs:
            blobs += [w.enc(source_lang), w.enc(target)]
    plain = iter(rpkg.decrypt_many(blobs, text_key))
    n_reseg = 0
    for e, g in parsed:
        mine = lines.get(e.hash, {})
        changed = False
        for i, w in enumerate(g.wavs):
            en, cur = rpkg.blob_text(next(plain)), rpkg.blob_text(next(plain))
            if not en:
                continue
            en_head, en_segs = segments(en)
            head, cur_segs = segments(cur or en)
            en_head = en_head or split(en)[0]
            sp, code = SPEAKER.search(en_head), CODE.search(en_head)
            bel_sp = sp and speakers.get(speaker_key(sp.group(1), voice_gender(code.group(1) if code else "")))
            if bel_sp:
                head = SPEAKER.sub(lambda m: "//{" + bel_sp.replace("\\", "") + "}\\\\", head, count=1)
            if i in mine:                     # пераклад — на таймінгах англійскага
                bel_lines = mine[i].replace("\r\n", "\n").split("\n")
                n_sub += 1
                n_reseg += len(bel_lines) != len(en_segs) and len(en_segs) > 1
                new = join(head, bel_lines, en_segs)
            elif cur_segs:
                new = head + "".join(f"//({a},{b})\\\\{t}" for a, b, t in cur_segs)
            else:
                new = head + split(cur or en)[1]
            if new != cur:
                w.set_enc(target, rpkg.encrypt(rpkg.text_blob(new), text_key))
                changed = True
        miss += sum(1 for i in mine if i >= len(g.wavs))
        if changed:
            out.setdefault(arc.chunk_of[e.hash], []).append((e, g.build()))

    os.makedirs(dest, exist_ok=True)
    written = []
    for c, res in sorted(out.items()):
        n = max(arc.latest_patch(c), levels[c][1]) + 1
        name = f"chunk{c}patch{n}.rpkg"
        rpkg.write_patch(os.path.join(dest, name), c, n, res)
        pd = rpkg.set_patchlevel(pd, c, n)
        written.append(name)
    if written:
        rpkg.write_packagedefinition(os.path.join(dest, "packagedefinition.txt"), header, pd, pkg_key)
        written.append("packagedefinition.txt")
    print(f"  інтэрфейс: {n_ui} радкоў, субтытры: {n_sub}, прамоўцаў: {len(speakers)}"
          + (f", радкоў не па кавалках арыгінала (таймінгі прапарцыйна): {n_reseg}" if n_reseg else "")
          + (f", ключоў няма ў гульні: {miss}" if miss else "")
          + (f", заглушак без кавалкаў арыгінала: {left}" if left else "")
          + f"; рэсурсаў: {sum(len(v) for v in out.values())}")
    return written


def our_patches(rt: str) -> list[str]:
    return [os.path.join(rt, n) for n in os.listdir(rt)
            if re.fullmatch(r"chunk\d+patch\d+\.rpkg", n) and rpkg.ours(os.path.join(rt, n))]


def restore_rt(rt: str) -> bool:
    did = False
    for p in our_patches(rt):
        os.remove(p)
        os.remove(p + ".bel")
        print("выдалены:", os.path.basename(p))
        did = True
    pd = os.path.join(rt, "packagedefinition.txt")
    if os.path.exists(pd + ".orig"):
        if rpkg.ours(pd):
            shutil.copyfile(pd + ".orig", pd)
            print("packagedefinition.txt вернуты")
        else:
            print("packagedefinition.txt ужо абноўлены Steam — пакінуты як ёсць")
        os.remove(pd + ".orig")
        did = True
    if os.path.exists(pd + ".bel"):
        os.remove(pd + ".bel")
    for p in [os.path.join(rt, n) for n in os.listdir(rt) if n.endswith(".rpkg.bel")]:
        os.remove(p)                       # адзнакі файлаў, якія Steam падмяніў
    return did


def install_rt(rt: str, texts, target: str, source_lang: str, text_key, pkg_key, pat=None) -> list[str]:
    """Патч у гульню: заўсёды ад арыгінала, packagedefinition.txt — з .orig, нашы файлы — з .bel."""
    restore_rt(rt)
    pd = os.path.join(rt, "packagedefinition.txt")
    shutil.copyfile(pd, pd + ".orig")
    written = build_rt(rt, texts, rt, target, source_lang, text_key, pkg_key, pat)
    for name in written:
        rpkg.mark_ours(os.path.join(rt, name))
    if not written:
        os.remove(pd + ".orig")
    return written


def payload(loc: Loc) -> dict:
    # ключы XTEA — канстанты exe гульні; ключы радкоў — хэшы, англійскага тэксту ў payload няма
    s = sec(loc)
    return {"glacier": {"runtime": s.get("runtime", "Runtime"), "target": s.get("target", "ru"),
                        "keys": {k: s["keys"][k] for k in ("text", "packagedefinition")}},
            "source_lang": loc.source_lang}


def check_path(payload: dict) -> str:
    return payload["glacier"]["runtime"]


def _args(game_dir: str, payload: dict):
    g = payload["glacier"]
    return (inside(game_dir, g["runtime"]), g["target"], payload["source_lang"],
            rpkg.parse_key(g["keys"]["text"]), rpkg.parse_key(g["keys"]["packagedefinition"]))


def apply(game_dir: str, payload: dict, out: str | None = None, log=print) -> dict:
    rt, target, source_lang, text_key, pkg_key = _args(game_dir, payload)
    pat = tables.from_original(payload.get("from_original"))
    log("Збіраю патч з файлаў гульні (хвіліна-дзве)…")
    if out:
        written = build_rt(rt, payload["strings"], out, target, source_lang, text_key, pkg_key, pat)
    else:
        written = install_rt(rt, payload["strings"], target, source_lang, text_key, pkg_key, pat)
    log(f"→ {out or rt}: {', '.join(written) or 'нічога'}")
    return {"written": written}


def restore(game_dir: str, payload: dict, log=print):
    if not restore_rt(inside(game_dir, payload["glacier"]["runtime"])):
        log("  пераклад не ўсталяваны")


def installed(game_dir: str, payload: dict) -> bool:
    return bool(our_patches(inside(game_dir, payload["glacier"]["runtime"])))
