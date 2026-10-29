"""Надпісы ў сцэнах, якіх няма ў CSV-табліцы гульні (Pony Island).

Частка тэксту ў Unity-сцэнах — TextMesh з тэкстам прама ў сцэне: радкі кода ў
галаваломках (`SOME_FLAG`, `OTHER_FLAG`), подпісы вокнаў, назвы зменных.
Гульня шукае ў табліцы толькі частку з іх (LocalizeText, радкі CodeEvent,
VariableLineBuilder, DialogueSequencer), астатнія — проста тэкст сцэны. Таму
пераклад ставіцца двума спосабамі адразу:

  - TextMesh.m_Text: англійскі тэкст → bel у файлах сцэн (дэкаратыўныя радкі);
  - радкі ў канец CSV-TextAsset (ENGLISH = en, target = bel) — для таго, што
    гульня перакладае сама ў час гульні: назвы зменных, рэплікі, радкі CodeEvent.

Тэкст, які гульня перабудоўвае з назвы зменнай (аб'екты `(ChangeVar)`,
`(Conditional)`, `CodeVariable`), не перакладаецца — з яго бяруцца толькі
назвы зменных (`FLAG = 1` → `FLAG`).

scan() працуе на файлах любой копіі гульні — і ў распрацоўшчыка (extract), і
ва ўсталёўшчыку (там англійскі тэкст бярэцца з гульні гульца, у exe яго няма).
"""
from __future__ import annotations

import os
import re
from collections import defaultdict

import UnityPy

TABLE = "19-scenes"
DEFAULT_FILES = r"level\d+|resources\.assets|sharedassets\d+\.assets"
REBUILT = ("(ChangeVar)", "(Conditional)", "CodeVariable")
VAR_RE = re.compile(r"^(\S(?:.*\S)?) = -?\d+$")
LETTERS = re.compile(r"[A-Za-z]{2,}")


def scene_files(data_dir: str, pattern: str = DEFAULT_FILES) -> list[str]:
    """Імёны файлаў сцэн/асетаў у data_dir (без .orig/.bel)."""
    return sorted(f for f in os.listdir(data_dir) if re.fullmatch(pattern, f))


def base_path(data_dir: str, rel: str) -> str:
    """Арыгінал файла: .orig, калі ён ёсць (у самім файле ўжо наш bel)."""
    p = os.path.join(data_dir, rel)
    return p + ".orig" if os.path.exists(p + ".orig") else p


def _go_name(tm) -> str:
    try:
        return tm.m_GameObject.read().m_Name
    except Exception:
        return "?"


def scan(data_dir: str, known, ignore=(), ignore_re=(), pattern: str = DEFAULT_FILES
         ) -> dict[str, list[str]]:
    """{англійскі тэкст: [«файл: GameObject», …]} — тое, што трэба перакласці.

    known(text) → True, калі тэкст ужо ёсць у CSV гульні (параўнанне — як у
    гульні, Localization.FormatString). ignore / ignore_re — тэксты і
    рэгулярныя выразы для тэкстаў, якія не чапаем (плэйсхолдары, імёны).
    """
    skip_re = [re.compile(r) for r in ignore_re]
    ignore = set(ignore)

    def skip(t):
        return t in ignore or any(r.search(t) for r in skip_re)

    found: dict[str, list[str]] = defaultdict(list)
    for rel in scene_files(data_dir, pattern):
        env = UnityPy.load(base_path(data_dir, rel))
        for o in env.objects:
            if o.type.name != "TextMesh":
                continue
            tm = o.read()
            text, go = tm.m_Text, _go_name(tm)
            if any(r in go for r in REBUILT):
                m = VAR_RE.match(text) if "CodeVariable" in go else None
                if m and not known(m.group(1)) and not skip(m.group(1)):
                    found[m.group(1)].append(f"{rel}: зменная ({text})")
                continue
            if not LETTERS.search(text) or known(text) or skip(text):
                continue
            found[text].append(f"{rel}: {go}")
    return dict(found)


def context(where: list[str]) -> str:
    """«level7: Thread1 / Line 3 (Nothing); level4: blank ×2» для note."""
    count: dict[str, int] = {}
    for w in where:
        count[w] = count.get(w, 0) + 1
    return "; ".join(w + (f" ×{n}" if n > 1 else "") for w, n in count.items())


def append_rows(text: str, header: list[str], cols: dict[str, int],
                pairs: list[tuple[str, str]], escape) -> str:
    """CSV гульні + радкі (en, bel) у канцы: ENGLISH = en, target = bel.

    cols — {"en": індэкс, "target": індэкс}; escape — Csv.Escape гульні.
    Гульня бярэ першы радок з такім тэкстам, таму дапісаныя радкі нічога
    з існых не засланяюць.
    """
    if not pairs:
        return text
    out = [text if text.endswith(("\n", "\r")) else text + "\n"]
    for en, bel in pairs:
        row = [""] * len(header)
        row[cols["en"]] = escape(en)
        row[cols["target"]] = escape(bel.replace("\r\n", "\n").replace("\r", "\n"))
        out.append(",".join(row) + "\n")
    return "".join(out)


def patch_textmeshes(env, lookup) -> int:
    """TextMesh.m_Text: en → lookup(en) па ўсім env (None — не чапаць)."""
    n = 0
    for o in env.objects:
        if o.type.name != "TextMesh":
            continue
        tm = o.read()
        bel = lookup(tm.m_Text)
        if bel and bel != tm.m_Text:
            tm.m_Text = bel
            tm.save()
            n += 1
    return n
