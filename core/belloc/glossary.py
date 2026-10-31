"""Гласарый уласных назваў — агульны фармат для ўсіх лакалізацый.

glossary.json:
  {
    "_about": "…",                       # секцыі на «_» — каментары
    "<секцыя>": {                        # characters, places, items, terms, …
      "<арыгінал>": {
        "bel": "…",                      # наш варыянт; пуста = не вырашана
        "gender": "м|ж|н|мн",            # неабавязкова
        "note": "…",                     # неабавязкова
        "alt": ["…"],                    # іншыя законныя перадачы (для лінтэра)
        "ru": "…", "key": "…"            # падказкі: як у RU, дзе ў гульні
      }
    }
  }

Крыжаваныя спасылкі: "bel": "гл. <ключ>" — ключ мусіць існаваць.

Два слаі, як у перакладу (гл. AGENTS.md):
  games/<гульня>/glossary.json        публічны — назвы па некалькі слоў, без апісанняў і цытат
  local/<гульня>/glossary.local.json  лакальны, неабавязковы — той жа фармат: рашэнні, дзе
                                      ключ або заўвага — цытата тэксту гульні (дэвізы, рэплікі,
                                      фразы). Лінтэр, `glossary` і даведнікі бачаць абодва;
                                      аднолькавы ключ у той жа секцыі — бярэцца лакальны.

    python -m belloc glossary <гульня>            # праверка + local/<гульня>/build/glossary.md
    python -m belloc glossary <гульня> --check    # код 1, калі md састарэў
"""
from __future__ import annotations

import json
import os
import re

TITLES = {
    "characters": "Персанажы", "places": "Месцы", "items": "Прадметы",
    "organizations": "Арганізацыі", "races": "Расы", "terms": "Тэрміны",
}


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_layers(paths: list[str]) -> dict:
    """Слаі гласарыя (публічны, лакальны) у адзін: секцыі зліваюцца, наступны слой перамагае."""
    data: dict = {}
    for path in paths:
        for key, value in load(path).items():
            if isinstance(value, dict) and isinstance(data.get(key), dict):
                data[key] = {**data[key], **value}
            else:
                data[key] = value
    return data


def sections(data: dict):
    for key, entries in data.items():
        if not key.startswith("_") and isinstance(entries, dict):
            yield key, entries


def validate(data: dict) -> list[str]:
    errors = []
    keys = {en for _, entries in sections(data) for en in entries}
    # «armor class» → ключ «armor class (AC)» / «black mage, black magician»
    heads = {k.lower() for k in keys} | {re.split(r" \(|, ", k.lower())[0] for k in keys}
    for sec, entries in sections(data):
        for en, info in entries.items():
            if not isinstance(info, dict):
                errors.append(f"{sec}/{en}: запіс мусіць быць аб'ектам")
                continue
            if "bel" not in info:
                errors.append(f"{sec}/{en}: няма поля bel")
            # «1) гл. dexterity 2) …» — нумар наступнага значэння не частка ключа
            for ref in re.findall(r"гл\.(?: тс\.)? ([^,;()]+?)(?=\s+\d+\)|[,;()]|$)",
                                  info.get("bel", "")):
                if ref.strip().lower() not in heads:
                    errors.append(f"{sec}/{en}: спасылка на неіснуючы ключ «{ref.strip()}»")
            if info.get("gender", "м") not in ("м", "ж", "н", "мн", ""):
                errors.append(f"{sec}/{en}: невядомы род «{info['gender']}»")
    return errors


def row(*cells: str) -> str:
    return "|" + "|".join(f" {c.replace('|', chr(92) + '|')} " if c else " "
                          for c in cells) + "|"


def render(data: dict, title: str) -> str:
    out = [f"# Гласарый — {title} (беларускі пераклад)\n",
           "> Уласныя назвы і тэрміны. Поле «род»: м/ж/н/мн.",
           "> Файл генеруецца з `glossary.json` — праўкі ўносьце туды.\n"]
    for sec, entries in sections(data):
        if not entries:
            continue
        out += ["---\n", f"## {TITLES.get(sec, sec)}\n",
                "| Арыгінал | Беларуская | Род | Заўвага |", "|---|---|---|---|"]
        for en in sorted(entries):
            info = entries[en]
            out.append(row(en, info.get("bel", ""), info.get("gender", ""), info.get("note", "")))
        out.append("")
    return "\n".join(out)


def run(glossary_paths: list[str], md_path: str, title: str, check: bool) -> int:
    data = load_layers(glossary_paths)
    errors = validate(data)
    for e in errors:
        print("  памылка:", e)
    total = sum(len(e) for _, e in sections(data))
    empty = sum(1 for _, e in sections(data) for i in e.values()
                if isinstance(i, dict) and not i.get("bel"))
    print(f"запісаў {total}, без bel {empty}, памылак {len(errors)}")
    text = render(data, title)
    if check:
        current = open(md_path, encoding="utf-8").read() if os.path.exists(md_path) else None
        if current != text:
            print(f"{md_path} састарэў")
            return 1
        return 1 if errors else 0
    os.makedirs(os.path.dirname(os.path.abspath(md_path)), exist_ok=True)
    with open(md_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("запісана:", md_path)
    return 1 if errors else 0
