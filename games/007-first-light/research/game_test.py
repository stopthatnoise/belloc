"""Праверка belloc/glacier у гульні: меню паўзы па-беларуску, усе субтытры —
рускі тэкст з адзнакай «Ў·», імёны прамоўцаў — з «·Ў» (DLGE перазабраныя,
слот ru). Ставіцца тым жа patch_strings, што і пераклад:

    python -X utf8 games/007-first-light/research/game_test.py
    python -X utf8 -m belloc patch-strings 007-first-light --restore
"""
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from belloc import config                                   # noqa: E402
from belloc.glacier import localization as L                # noqa: E402

UI = {   # англійскі тэкст → беларускі (меню паўзы, 2026-10-26)
    "Resume game": "Працягнуць гульню", "Retry": "Паспрабаваць зноў",
    "Restart checkpoint": "Вярнуцца да кантрольнага пункта",
    "b3033b4b1f604758":   # падказка ў меню паўзы (sha256[:16] англійскага)
        "Пры вяртанні да кантрольнага пункта частка прагрэсу можа згубіцца.",
    "Photo mode": "Фотарэжым", "Exit to menu": "Выйсці ў меню", "Pause menu": "Паўза",
    "Options": "Налады", "Tutorials": "Навучанне", "Select": "Выбраць", "Exit": "Выйсці",
}

loc = config.load("007-first-light")
src = {c: json.load(open(os.path.join(loc.source, f"{c}.json"), encoding="utf-8")) for c in ("en", "ru")}
texts = {}
for table, kv in src["en"].items():
    ru = src["ru"][table]
    if table.startswith("ui/"):
        texts[table] = {k: UI.get(v) or UI[hashlib.sha256(v.encode()).hexdigest()[:16]]
                         for k, v in kv.items() if v in UI or hashlib.sha256(v.encode()).hexdigest()[:16] in UI}
    elif table == L.SPEAKERS:
        texts[table] = {k: f"{ru.get(k) or v}·Ў" for k, v in kv.items()}
    else:
        texts[table] = {k: f"Ў· {ru.get(k) or v}" for k, v in kv.items()}
L.patch_strings(loc, texts=texts)
