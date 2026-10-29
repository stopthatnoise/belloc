"""extract: файлы гульні → local/<гульня>/source/."""
from __future__ import annotations

import json
import os
import re

from ...config import Loc
from . import pak
from .common import read_locres, sec, table_name, targets


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
