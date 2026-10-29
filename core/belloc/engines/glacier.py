"""Лакалізацыя гульняў Glacier 2 (engine = "glacier": 007 First Light).

Секцыя "glacier" у game.json (ключы можна трымаць у local.json):

  runtime   "Runtime"                    — папка chunk*.rpkg і packagedefinition.txt (адносна game_dir)
  exe       "Retail/007FirstLight.exe"   — для версіі ў meta.json
  target    "ru"                         — слот мовы, які займае беларуская (гулец выбірае
                                           гэтую мову; англійскі шрыфт кірыліцы не мае)
  keys      {"text": "…", "packagedefinition": "…"}
                                         — ключы XTEA гульні (4 hex-словы)
  missions  [["/clover/", "M01_clover"], …]
                                         — місіі ў храналагічным парадку: рэгулярка па шляху
                                           сцэны → назва (scenes.py); без іх — табліцы па катэгорыях

Тэкст (формат — rpkg.py, locr.py, dlge.py):
  ui/<рэсурс>                 LOCR — інтэрфейс; ключ = хэш радка (8 hex)
  dlg/<місія>/<сцэна>         DLGE — субтытры адной сцэны ў парадку гульні (scenes.py);
                              `dlg/<місія>/_shared` — з некалькіх сцэн місіі;
  dlg/_common/<катэгорыя>/<голас>
                              — з розных місій (баркі NPC); катэгорыя — %DX_…% без «DX_»,
                              голас — код без нумара (CIVUKF01 → CIVUKF, MI6EMPLOYEE_CIVUKM07 → MI6EMPLOYEE)
                              ключ субтытра = «<рэсурс>:<нумар WavFile>»
  dlg/_speakers               імёны прамоўцаў з `{…}` загалоўка (ключ — «імя|пол»);
                              build падстаўляе пераклад ва ўсе субтытры слота target
Хто кажа → source/context.json: «CIVUKF01 ж · Civilian · NPC_Story» (м/ж — па канцы
кода голасу; апошняе — катэгорыя).

apply: слот target ← bel (неперакладзенае застаецца як было) →
chunkNpatchM.rpkg (M = афіцыйны patchlevel + 1) і patchlevel у packagedefinition.txt.
Нашы файлы пазначаюцца <файл>.bel (SHA-256); packagedefinition.txt — .orig + .bel:
калі Steam абнавіў файл, за аснову бярэцца новы. restore выдаляе патчы і вяртае
packagedefinition.txt; з out — тое ж у папку, гульня не чапаецца.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from collections import Counter

from .. import tables
from ..config import Loc
from ..glacier import rpkg, scenes
from ..glacier.dlge import CATEGORY, CODE, SPEAKER, Dlge, join, segments, split
from ..glacier.locr import Locr

NAME = "glacier"
SECTION = "glacier"

SPEAKERS = "dlg/_speakers"


def sec(loc: Loc) -> dict:
    return loc.section(SECTION)


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


def voice_gender(code: str) -> str:
    """CIVUKF01 → ж, MERCMRM03 → м; імёны (BOND, M, Q) — пуста (род — у гласарыі)."""
    m = re.fullmatch(r"[A-Z]{3,}([MF])\d+", code.split("_")[-1])
    return {"M": "м", "F": "ж"}[m.group(1)] if m else ""


def dlg_key(h: int, i: int) -> str:
    return f"{h:016X}:{i}"


def speaker_key(name: str, gender: str) -> str:
    """Ключ dlg/_speakers: імя на экране + пол голасу — «Civilian» па-руску
    «Гражданский» і «Гражданская», па-беларуску таксама па-рознаму."""
    return f"{name}|{gender}" if gender else name


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


# --- запіс

def base_packagedefinition(rt: str) -> str:
    """Арыгінал packagedefinition.txt: .orig, пакуль у гульні ляжыць наш запіс
    (калі Steam яго падмяніў — бягучы файл)."""
    pd = os.path.join(rt, "packagedefinition.txt")
    return pd + ".orig" if os.path.exists(pd + ".orig") and rpkg.ours(pd) else pd


def build_rt(rt: str, texts: dict[str, dict[str, str]], dest: str, target: str, source_lang: str,
             text_key, pkg_key) -> list[str]:
    """Патчы chunkNpatchM.rpkg і packagedefinition.txt у dest. Вяртае імёны файлаў."""
    arc = rpkg.Archive(rt)
    header, pd = rpkg.read_packagedefinition(base_packagedefinition(rt), pkg_key)
    levels = rpkg.patchlevels(pd)

    out: dict[int, list[tuple[rpkg.Entry, bytes]]] = {}
    n_ui = n_sub = miss = 0
    for table, kv in texts.items():
        if not table.startswith("ui/") or not kv:
            continue
        e = arc.entries.get(int(table[3:], 16))
        if e is None:
            miss += len(kv)
            continue
        lc = Locr(rpkg.read(e))
        tgt = lc.lang(target)
        changed = False
        for key, bel in kv.items():
            h = int(key, 16)
            if tgt is None or h not in tgt:
                miss += 1
                continue
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


def install_rt(rt: str, texts, target: str, source_lang: str, text_key, pkg_key) -> list[str]:
    """Патч у гульню: заўсёды ад арыгінала, packagedefinition.txt — з .orig, нашы файлы — з .bel."""
    restore_rt(rt)
    pd = os.path.join(rt, "packagedefinition.txt")
    shutil.copyfile(pd, pd + ".orig")
    written = build_rt(rt, texts, rt, target, source_lang, text_key, pkg_key)
    for name in written:
        rpkg.mark_ours(os.path.join(rt, name))
    if not written:
        os.remove(pd + ".orig")
    return written


# ---------------------------------------------------------------- інтэрфейс рухавіка

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
    return (os.path.join(game_dir, g["runtime"]), g["target"], payload["source_lang"],
            rpkg.parse_key(g["keys"]["text"]), rpkg.parse_key(g["keys"]["packagedefinition"]))


def apply(game_dir: str, payload: dict, out: str | None = None, log=print) -> dict:
    rt, target, source_lang, text_key, pkg_key = _args(game_dir, payload)
    log("Збіраю патч з файлаў гульні (хвіліна-дзве)…")
    if out:
        written = build_rt(rt, payload["strings"], out, target, source_lang, text_key, pkg_key)
    else:
        written = install_rt(rt, payload["strings"], target, source_lang, text_key, pkg_key)
    log(f"→ {out or rt}: {', '.join(written) or 'нічога'}")
    return {"written": written}


def restore(game_dir: str, payload: dict, log=print):
    if not restore_rt(os.path.join(game_dir, payload["glacier"]["runtime"])):
        log("  пераклад не ўсталяваны")


def installed(game_dir: str, payload: dict) -> bool:
    return bool(our_patches(os.path.join(game_dir, payload["glacier"]["runtime"])))
