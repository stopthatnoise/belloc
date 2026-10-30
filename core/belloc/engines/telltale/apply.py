"""payload, apply, restore, installed: наш пераклад → мод у папцы архіваў гульні (або --out)."""
from __future__ import annotations

import glob
import json
import os
import re

from ... import payload as payload_mod
from ...config import Loc
from . import font as tfont
from .common import (TAG, decode, from_other_sets, game_sets, is_language_set, key_hash,
                     sec, set_archives)
from .landb import Landb
from .lenc import Blowfish7, decrypt_lua, encrypt_lua
from .luac import Chunk
from .ttarch2 import TTArch2, write_nctt


def patch_lua(data: bytes, texts: dict[str, str], bf: Blowfish7) -> tuple[bytes, int]:
    """Зашыфраваны Lua з замененымі радковымі канстантамі: texts — {хэш радка: bel}."""
    chunk = Chunk(decrypt_lua(data, bf))
    mapping = {}
    for _, _, s in chunk.strings:
        text = s.decode("utf-8", "replace")
        bel = texts.get(key_hash(text))
        if bel and bel != text:
            mapping[s] = bel.encode("utf-8")
    code, n = chunk.replace(mapping)
    return encrypt_lua(code, bf), n


def override_lua(lua: str, arc_name: str) -> str:
    """Дэскрыптар гульні → той жа набор з нашым архівам першым."""
    lua, n = re.subn(r"set\.descriptionPriority\s*=\s*(-?\d+)",
                     lambda m: f"set.descriptionPriority = {int(m.group(1)) + 100}", lua)
    nl = "\r\n" if "\r\n" in lua else "\n"
    lua, k = re.subn(r"(set\.gameDataArchives\s*=\s*\{\s*)",
                     lambda m: f'{m.group(1)}_currentDirectory .. "{arc_name}",{nl}    ', lua, count=1)
    if n != 1 or k != 1:
        raise SystemExit("дэскрыптар не падобны на чаканы (descriptionPriority / gameDataArchives)")
    return lua


def _font_ttf(fonts: dict, font_name: str) -> str | None:
    best = max((k for k in fonts if k and font_name.startswith(k)), key=len, default="")
    return fonts.get(best) or fonts.get("")


def font_file(spec: str) -> str:
    """"fonts/x/X[wght].ttf:Bold" → "fonts/x/X[wght].ttf" (варыяцыя — пасля апошняга «:»)."""
    path, _, var = spec.rpartition(":")
    return spec if not path or "/" in var or "\\" in var else path


def wrap_text(text: str, width: int) -> str:
    """Радок, у якім бачнага тэксту больш за width, — на роўныя часткі па
    прабелах (`\\n`). Рухавік пераносіць кірыліцу дзе папала, пасярод слова
    («на с / екундачку»), а яўны `\\n` слухае. {…} і […] не лічацца бачнымі
    (эмоцыі, рэмаркі), ^…^ — таксама (^font:…^, ^glyphScale:…^); прабел, за
    якім бачны яшчэ прабел, не бярэцца."""
    out = []
    for seg in text.split("\n"):
        spaces, vis, depth, caret = [], 0, 0, False   # (індэкс прабелу, бачных да яго)
        for i, c in enumerate(seg):
            if c == "^":
                caret = not caret
            elif caret:
                continue
            elif c in "{[":
                depth += 1
            elif c in "}]" and depth:
                depth -= 1
            elif not depth:
                if c == " ":
                    spaces.append((i, vis))
                vis += 1
        if vis <= width:
            out.append(seg)
            continue
        vis_seg = re.sub(r"\{[^}]*\}|\[[^\]]*\]|\^[^^]*\^", "", seg)
        ok = [(i, v) for i, v in spaces if v + 1 < len(vis_seg) and vis_seg[v + 1] != " "]
        n = -(-vis // width)
        cut, last = [], -1
        for k in range(1, n):
            best = min((x for x in ok if x[0] > last), key=lambda x: abs(x[1] - k * vis / n), default=None)
            if best is None:
                break
            cut.append(best[0])
            last = best[0]
        chars = list(seg)
        for i in cut:
            chars[i] = "\n"
        out.append("".join(chars))
    return "\n".join(out)


def _wrap_width(wrap: dict[str, int], table: str) -> int | None:
    return next((w for pat, w in wrap.items() if re.search(pat, table)), None)


def build(game_dir: str, payload: dict, dest: str, log=print) -> list[str]:
    """Мод у dest: па архіве і дэскрыптары на кожны набор, які трэба змяніць
    (landb з перакладам; пры target ≠ lang — усе landb мовы target; шрыфты —
    у Project і моўных наборах). Вяртае імёны запісаных файлаў."""
    s, texts = payload["telltale"], payload["strings"]
    game = os.path.join(game_dir, s["archive"])
    lang, target = s["lang"], s["target"]
    fill = target != lang                        # неперакладзенае — тэкстам мовы lang
    rename = s.get("rename", {})
    wrap = s.get("wrap", {})
    bf = Blowfish7(bytes.fromhex(s["lua_key"])) if s.get("lua_files") else None
    chars = s.get("font_chars", tfont.BEL_CHARS)
    fonts = {k: payload_mod.asset(payload, v) for k, v in s.get("fonts", {}).items()}
    tex_spec = payload.get("textures", {})
    sets = game_sets(game)
    os.makedirs(dest, exist_ok=True)
    written = []
    for set_name, lua in sets.items():
        arcs = [TTArch2(os.path.join(game, a)) for a in set_archives(lua)
                if os.path.exists(os.path.join(game, a))]
        names = {x for a in arcs for x in a.files}

        def first(name):                      # як гульня: першы архіў у спісе выйграе
            return next((a.get(name) for a in arcs if name in a.files), None)

        files: dict[str, bytes] = {}
        n = miss = 0
        suffix = f"_{target}.landb"
        scenes = sorted(x[:-len(suffix)] for x in names if x.endswith(suffix))
        for scene in scenes:
            table = f"{set_name}/{scene}"
            kv = texts.get(table, {})
            width = _wrap_width(wrap, table)
            if width:
                kv = {k: wrap_text(v, width) for k, v in kv.items()}
            ren = rename.get(table, {})
            if not (kv or fill or ren):
                continue
            lb = Landb(first(f"{scene}{suffix}"))
            src = {r.id: r.text for r in Landb(first(f"{scene}_{lang}.landb")).records} \
                if fill or ren else {}
            have = set()
            for r in lb.records:
                key = str(r.id)
                have.add(key)
                if key in kv:
                    r.text = kv[key].encode("utf-8")
                    n += 1
                elif fill and r.id in src:
                    r.text = src[r.id]
                if decode(src.get(r.id, b"")) in ren:
                    r.text = ren[decode(src[r.id])].encode("utf-8")
            miss += sum(1 for k in kv if k not in have)
            files[f"{scene}{suffix}"] = lb.build()
            if ren:                               # назва мовы — ва ўсіх мовах табліцы
                for other in sorted(x for x in names if x.startswith(f"{scene}_")
                                    and x.endswith(".landb") and x != f"{scene}{suffix}"):
                    ol = Landb(first(other))
                    hit = False
                    for r in ol.records:
                        if decode(src.get(r.id, b"")) in ren:
                            r.text = ren[decode(src[r.id])].encode("utf-8")
                            hit = True
                    if hit:
                        files[other] = ol.build()
        nlua = 0
        for name in sorted(x for x in s.get("lua_files", []) if x in names):
            kv = texts.get(f"{set_name}/{name}", {})
            if any(kv.values()):
                files[name], k = patch_lua(first(name), kv, bf)
                nlua += k
        if fonts and (set_name == "Project" or (fill and is_language_set(lua))):
            for name in sorted(x for x in names if x.endswith(".font")):
                f = tfont.Font(first(name))
                try:
                    files[name] = tfont.add_glyphs(f, _font_ttf(fonts, f.name), chars)
                except (AssertionError, StopIteration, NotImplementedError) as e:
                    log(f"  шрыфт {set_name}/{name} ({f.name}): прапушчаны — {e}")
        if fill and set_name == target:          # тэкстуры з надпісамі мовы target — з агульных набораў
            for name in sorted(x for x in names if x.endswith(".d3dtx")):
                base = from_other_sets(game, sets, name, skip=set_name, like=first(name))
                if base is not None and name in tex_spec:
                    from . import texture
                    base = texture.apply(base, tex_spec[name], payload_mod.asset(payload, ""))[0]
                if base is not None:
                    files[name] = base
        if not files:
            continue
        arc_name = f"Fables_pc_{TAG}_{set_name}_ar_all.ttarch2"
        lua_name = f"_resdesc_50_{TAG}_{set_name}.lua"
        write_nctt(os.path.join(dest, arc_name), files)
        with open(os.path.join(dest, lua_name), "wb") as fh:
            fh.write(override_lua(lua, arc_name).encode("utf-8"))
        written += [arc_name, lua_name]
        kinds = {e: sum(1 for x in files if x.endswith(e)) for e in (".landb", ".font", ".d3dtx", ".lua")}
        log(f"  {set_name}: {kinds['.landb']} landb, перакладзена радкоў {n}"
            + (f", шрыфтоў {kinds['.font']}" if kinds[".font"] else "")
            + (f", тэкстур {kinds['.d3dtx']}" if kinds[".d3dtx"] else "")
            + (f", Lua {kinds['.lua']} (радкоў {nlua})" if kinds[".lua"] else "")
            + (f", ID няма ў гульні: {miss}" if miss else ""))
    unknown = sorted({t.partition("/")[0] for t in texts} - set(sets))
    if unknown:
        log(f"  наборы з перакладу, якіх няма ў гульні: {', '.join(unknown)}")
    return written


def texture_spec(loc: Loc) -> dict:
    """{імя.d3dtx: апісанне надпісаў} з textures.json гульні (або {})."""
    p = loc.path("textures.json")
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as fh:
        return json.load(fh).get("textures", {})


def payload(loc: Loc) -> dict:
    # ключ Blowfish — канстанта гульні (вядомы з TTG Tools); радкі Lua — па хэшах,
    # шрыфты — адносна папкі гульні ў games/ (assets)
    s = sec(loc)
    lang = s.get("lang", "english")
    t = {"archive": s.get("archive", "Archive"), "lang": lang, "target": s.get("target", lang)}
    t.update({k: s[k] for k in ("rename", "wrap", "fonts", "font_chars") if k in s})
    if s.get("lua_text"):
        t.update(lua_key=s["lua_key"], lua_files=sorted(s["lua_text"]))
    textures = texture_spec(loc)
    files = {font_file(v) for v in t.get("fonts", {}).values()}
    files |= {font_file(b["font"]) for spec in textures.values() for b in spec["blocks"]}
    assets = set()
    for f in files:
        if os.path.isabs(f):                 # шрыфт з local.json — толькі на гэтай машыне
            continue
        assets.add(f)
        lic = os.path.join(os.path.dirname(f), "OFL.txt")
        if os.path.exists(loc.path(lic)):
            assets.add(lic.replace(os.sep, "/"))
    return {"telltale": t, "textures": textures, "assets": sorted(assets), "source_lang": loc.source_lang}


def check_path(payload: dict) -> str:
    return payload["telltale"]["archive"]


def _ours(game_dir: str, payload: dict) -> list[str]:
    return glob.glob(os.path.join(game_dir, payload["telltale"]["archive"], f"*{TAG}*"))


def apply(game_dir: str, payload: dict, out: str | None = None, log=print) -> dict:
    """Мод у папку архіваў гульні (стары мод спачатку выдаляецца) або, з out, у іншую папку."""
    dest = out or os.path.join(game_dir, payload["telltale"]["archive"])
    if not out:
        for p in _ours(game_dir, payload):
            os.remove(p)                       # наборы, якіх больш няма ў перакладзе
    log("Збіраю мод з архіваў гульні (некалькі хвілін)…")
    written = build(game_dir, payload, dest, log)
    size = sum(os.path.getsize(os.path.join(dest, f)) for f in written)
    log(f"→ {dest}: {len(written)} файлаў, {size // 1024} КБ")
    return {"written": written}


def restore(game_dir: str, payload: dict, log=print):
    old = _ours(game_dir, payload)
    for p in old:
        os.remove(p)
    log(f"выдалена файлаў: {len(old)}" if old else "  пераклад не ўсталяваны")


def installed(game_dir: str, payload: dict) -> bool:
    return bool(_ours(game_dir, payload))


def textures_preview(loc: Loc, out_dir: str | None = None):
    """Прэв'ю надпісаў textures.json: арыгінал і наш варыянт побач → build/textures/."""
    from PIL import Image
    from . import texture
    s = sec(loc)
    game = loc.game(s.get("archive", "Archive"))
    sets = game_sets(game)
    target = s.get("target", s.get("lang", "english"))
    out_dir = out_dir or os.path.join(loc.build, "textures")
    os.makedirs(out_dir, exist_ok=True)
    tarcs = [TTArch2(os.path.join(game, a)) for a in set_archives(sets[target])
             if os.path.exists(os.path.join(game, a))]
    for name, spec in texture_spec(loc).items():
        like = next((a.get(name) for a in tarcs if name in a.files), None)
        base = from_other_sets(game, sets, name, skip=target, like=like)
        if base is None:
            print(f"  {name}: няма ў агульных наборах — прапушчана")
            continue
        _, before, after = texture.apply(base, spec, loc.dir)
        w, h = before.size
        sheet = Image.new("RGB", (w * 2 + 8, h), (30, 30, 30))
        sheet.paste(before.convert("RGB"), (0, 0))
        sheet.paste(after.convert("RGB"), (w + 8, 0))
        p = os.path.join(out_dir, name.replace(".d3dtx", ".png"))
        sheet.save(p)
        print(f"{name}: {w}×{h} → {p}")
