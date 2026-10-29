"""Лакалізацыя UE праз .locres (engine = "unreal-locres": Expedition 33, Dispatch).

Секцыя "unreal" у game.json (aes_key можна трымаць у local.json):

  pak      "Sandfall/Content/Paks/pakchunk0-Windows.pak"          — пак гульні з locres
  locres   "Sandfall/Content/Localization/Game/{lang}/Game.locres" — шлях унутры пака
  langs    {"en": "en-US", "ru": "ru", "uk": "uk"}                 — мова CSV → культура UE
  target   "ru"                                                    — чыю культуру падмяняем
  mod      "Sandfall/Content/Paks/~mods/Belarusian_P.pak"         — куды класці мод-пак
  aes_key  "0x…"                                                  — калі індэкс пака зашыфраваны (Dispatch)
  font_patches                                                     — кірыліца ў шрыфты без яе, у той жа мод-пак (fonts.py)

Некалькі мэтаў лакалізацыі (Dispatch: Shared, 101…108 — кожная ў сваім паку):

  loc_targets {"Shared": "Dispatch/Content/Paks/pakchunk0-WindowsNoEditor.pak", …}
              — замест pak; у locres і po — {target}
  po       "Dispatch/Content/Localization/{target}/{lang}/{target}.po" — па жаданні:
           з .po мовы source_lang бяруцца Speaker, Loc Note, SourceLocation
           (→ source/context.json, «ctx: …» у note) і SortingString (парадак
           дыялогаў у CSV)

Табліца CSV = прастора імёнаў locres (ST_…), ключ = ключ радка. З мэтамі —
«<мэта>/<прастора>», кропкі прасторы — падпапкі (101/LV_Shift01/Scenario_SC_01_),
пустая прастора — «_» (101/_), знакі, што не могуць быць у імені файла, — «_».

Дастаўка — мод-пак: адзін файл у ~mods з locres культуры target (з мэтамі —
па адным на мэту), у якім перакладзеныя радкі замененыя на bel
(неперакладзенае — мовы target). Файлы гульні не мяняюцца: ні .orig, ні .bel;
restore проста выдаляе мод.
"""
from __future__ import annotations

import json
import os
import re

from ..config import Loc
from ..unreal import pak
from ..unreal.locres import Locres

NAME = "unreal-locres"
SECTION = "unreal"


def sec(loc: Loc) -> dict:
    return loc.section(SECTION)


def targets(s: dict) -> dict[str | None, str]:
    """{мэта: пак}; без loc_targets — адна мэта None."""
    return s.get("loc_targets") or {None: s["pak"]}


def locres_path(s: dict, lang: str, target: str | None = None) -> str:
    return s["locres"].format(lang=s["langs"].get(lang, lang), target=target)


def table_name(target: str | None, ns: str) -> str:
    """Імя табліцы для прасторы ns; толькі ў гэты бок — build_mod шукае
    тэксты па імені табліцы кожнай прасторы locres."""
    if target is None:
        return ns
    segs = [re.sub(r'[<>:"\|?*/]', "_", x).rstrip(" .") or "_" for x in ns.split(".")] if ns else ["_"]
    return "/".join([target] + segs)


def read_locres(game_dir: str, s: dict, lang: str, target: str | None = None,
                p: pak.Pak | None = None) -> Locres:
    own = p is None
    p = p or pak.Pak(os.path.join(game_dir, targets(s)[target]), s.get("aes_key"))
    try:
        return Locres(p.read(locres_path(s, lang, target)))
    finally:
        if own:
            p.close()


def _natural(s: str) -> list:
    return [int(x) if x.isdigit() else x.lower() for x in re.split(r"(\d+)", s)]


def key_order(key: str) -> tuple:
    """Парадак радкоў у CSV. У locres яны ідуць па алфавіце англійскага тэксту,
    што рве дыялогі; ключы ж выгляду «20A_RdSc1Stories_Sciel» (нумар, размова,
    хто кажа) або «ST_Dialog_GestralVillage_Golgra_07» дазваляюць сабраць
    размову па парадку: размова → нумар рэплікі → літара."""
    m = re.match(r"(\d+)([A-Za-z]*)_(.*)$", key)
    if m:
        conv = m.group(3).rsplit("_", 1)[0] if "_" in m.group(3) else ""
        return (_natural(conv), int(m.group(1)), m.group(2).lower(), _natural(key))
    return (_natural(key),)


def parse_po(data: bytes) -> dict[str, dict[str, list[str]]]:
    """{msgctxt: {поле каментара «#. Поле: …»: [значэнні]}} — толькі каментары."""
    out, cur = {}, {}
    for line in data.decode("utf-8-sig").splitlines():
        m = re.match(r"#\. ([A-Za-z ]+):\t?\s*(.*)$", line)
        if m:
            cur.setdefault(m.group(1), []).append(m.group(2).strip())
        elif line.startswith('msgctxt "'):
            out[line[9:-1].replace('\\"', '"').replace("\\\\", "\\")] = cur
        elif not line.strip():
            cur = {}
    return out


def _short_source(src: str) -> str:
    """/DispatchEp102/Shifts/Levels/LV_Shift02.Default__LV_Shift02_C.ScenarioComms(0)
    .ScenarioComms.Responses_45_<guid>(1).Responses_45_<guid>.Text_9_<guid>
    → «LV_Shift02 ScenarioComms(0).Responses(1).Text»; для табліц радкоў — «»."""
    src = re.sub(r"_\d+_[0-9A-F]{32}", "", src.rsplit("/", 1)[-1])
    src = re.sub(r"(\w+)(\(\d+\))\.\1\b", r"\1\2", src)
    asset, _, rest = src.partition(".")
    rest = re.sub(rf"^(Default__)?{re.escape(asset)}(_C)?(:PersistentLevel)?[.:]?(WidgetTree\.)?", "", rest)
    return f"{asset} {rest}" if rest else ""


def _po_context(po: dict, ns: str, key: str) -> tuple[str, tuple]:
    """(заўвага для перакладчыка, ключ сартавання) з каментараў .po."""
    c = po.get(f"{ns},{key}", {})
    first = lambda f: (c.get(f) or [""])[0]
    sort, speaker = first("SortingString"), first("Speaker")
    parts = []
    if speaker:
        node = re.sub(r"^Gem_Node_|_?Line_\d+$", "", sort)
        parts.append(speaker + (f" @ {node}" if node else ""))
    elif first("SourceLocation"):
        short = _short_source(first("SourceLocation"))
        if short:
            parts.append(short)
    parts += [x.replace('" : "', ": ").strip('"') for x in c.get("InfoMetaData", [])]
    if first("Loc Note"):
        parts.append("note: " + first("Loc Note").replace('\\"', '"'))
    order = (0, _natural(sort)) if sort else (1, _natural(first("SourceLocation")), _natural(key))
    return "; ".join(parts).replace(" | ", " / "), order


def write_json(path: str, data):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def extract(loc: Loc, out: str | None = None):
    out = out or loc.source
    os.makedirs(out, exist_ok=True)
    s = sec(loc)
    meta = {"steam_buildid": loc.steam_buildid(), "langs": {}}
    res = {lang: {} for lang in s["langs"]}
    context, order = {}, {}
    for target, pak_path in targets(s).items():
        p = pak.Pak(loc.game(pak_path), s.get("aes_key"))
        try:
            po = parse_po(p.read(s["po"].format(lang=s["langs"][loc.source_lang], target=target))) \
                if s.get("po") else {}
            for lang in s["langs"]:
                for ns, kv in read_locres(loc.game_dir, s, lang, target, p).to_dict().items():
                    if not kv:
                        continue
                    t = table_name(target, ns)
                    if lang == loc.source_lang and t in res[lang]:
                        raise SystemExit(f"дзве прасторы ў адной табліцы {t}")
                    res[lang][t] = kv
                    if po and lang == loc.source_lang:
                        for k in kv:
                            note, order[t, k] = _po_context(po, ns, k)
                            if note:
                                context.setdefault(t, {})[k] = note
        finally:
            p.close()
    sort = (lambda t: lambda k: order.get((t, k)) or (2, key_order(k))) if order else \
        (lambda t: key_order)
    for lang, d in res.items():
        d = {t: dict(sorted(kv.items(), key=lambda x, f=sort(t): f(x[0])))
             for t, kv in sorted(d.items())}
        write_json(os.path.join(out, f"{lang}.json"), d)
        meta["langs"][lang] = sum(len(kv) for kv in d.values())
        print(f"{lang}: {meta['langs'][lang]} радкоў у {len(d)} табліцах")
    if context:
        write_json(os.path.join(out, "context.json"), context)
        print(f"кантэкст з .po: {sum(len(v) for v in context.values())} радкоў")
    write_json(os.path.join(out, "meta.json"), meta)
    print(f"buildid {meta['steam_buildid']}")


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
    """Шрыфты з дададзенай кірыліцай (font_patches, гл. unreal/fonts.py) — {шлях у паку: байты}."""
    if not s.get("font_patches"):
        return {}
    from ..unreal import fonts
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


# ---------------------------------------------------------------- інтэрфейс рухавіка

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
