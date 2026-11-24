"""Субтытры: табліца перакладу ў рэпазіторыі → `.srt` гульні.

Гульня выбірае файл па культуры (BinkMediaPlayer): `Video/Subtitles/<відэа>-
<Strings.GetCultureNameEnglish(culture)>.srt`; для `ru-RU` гэта `Russian`.
Таму мы перапісваем рускія субтытры — тым жа механізмам `.orig`/`.bel`, што і
табліцу (install/target.py).

Пераклад жыве ў `games/<гульня>/<subtitle_table>` (па змаўчанні
`subtitles.csv`): слупкі `file, idx, bel, note`, дзе `file` — ключ відэа
(`1A-prologue`), `idx` — нумар рэплікі. Ні часу, ні тэксту гульні там няма.
Payload: `{"<відэа>": ["тэкст рэплікі", …], …}` — час бярэцца з файла гульні
пры apply, таму абнаўленне таймінгаў Steam не ламае пераклад, пакуль
колькасць рэплік тая самая. Калі колькасць іншая — файл прапускаецца цалкам
(лепш руская рэпліка, чым збітыя аздабленні).
"""
from __future__ import annotations

import csv
import os

from ...config import Loc
from ...install.paths import inside, name as one
from ...install.target import Target


def target_name(s: dict, video: str) -> str:
    """`<відэа>-<subtitle_lang>.srt` — імя, якое шукае BinkMediaPlayer."""
    if not s.get("subtitle_lang"):
        raise SystemExit("battletech_csv: у game.json няма subtitle_lang")
    return f"{one(video)}-{one(s['subtitle_lang'])}.srt"


def srt_path(game_dir: str, s: dict, file_name: str) -> str:
    """Файл субтытраў унутры <game_dir>; шляхі з game.json — праз inside."""
    return inside(game_dir, s["subtitles"], one(file_name))


def parse(path: str) -> list[tuple[str, str, list[str]]]:
    """[(нумар, радок часу, [радкі тэксту])] — структура захоўваецца як ёсць."""
    with open(path, "rb") as f:
        text = f.read().decode("utf-8-sig")
    text = text.replace("\r\n", "\n").replace("\n\r", "\n").replace("\r", "\n").strip()
    cues = []
    for block in text.split("\n\n"):
        lines = block.split("\n")
        while lines and lines[-1] == "":
            lines.pop()
        if len(lines) < 3 or " --> " not in lines[1]:
            continue
        cues.append((lines[0].strip(), lines[1].strip(), lines[2:]))
    return cues


def render(path: str, cues: list[tuple[str, str, list[str]]], texts: list[str]):
    """Запісаць .srt: нумар і час з гульні, тэкст наш; BOM, CRLF, пусты радок."""
    blocks = []
    for (num, time, _), text in zip(cues, texts):
        blocks.append("\r\n".join([num, time, *text.split("\n")]))
    data = "\ufeff" + "\r\n\r\n".join(blocks) + "\r\n\r\n"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(data)


def payload(loc: Loc, s: dict) -> dict:
    """Табліца `subtitle_table` → {відэа: [тэкст рэплікі, …]}."""
    rel = s.get("subtitle_table")
    if not rel:
        return {}
    path = loc.path(rel)
    if not os.path.exists(path):
        raise SystemExit(f"{path}: няма табліцы субтытраў (subtitle_table)")
    by_video: dict[str, dict[int, str]] = {}
    with open(path, encoding="utf-8", newline="") as f:
        for n, row in enumerate(csv.DictReader(f), 2):
            video = (row.get("file") or "").strip()
            idx = (row.get("idx") or "").strip()
            bel = row.get("bel") or ""
            if not video or not idx:
                raise SystemExit(f"{path}:{n}: пустыя file/idx")
            one(video)
            try:
                i = int(idx)
            except ValueError:
                raise SystemExit(f"{path}:{n}: idx «{idx}» — не лік")
            if i < 1:
                raise SystemExit(f"{path}:{n}: idx «{idx}» — мусіць быць ≥ 1")
            cues = by_video.setdefault(video, {})
            if i in cues:
                raise SystemExit(f"{path}:{n}: паўтор {video} #{i}")
            if not bel:
                raise SystemExit(f"{path}:{n}: пусты bel для {video} #{i}")
            cues[i] = bel
    out = {}
    for video, cues in sorted(by_video.items()):
        last = max(cues)
        if sorted(cues) != list(range(1, last + 1)):
            missing = sorted(set(range(1, last + 1)) - set(cues))
            raise SystemExit(f"{path}: {video}: няма рэплік {missing}")
        out[video] = [cues[i] for i in range(1, last + 1)]
    return out


def apply(game_dir: str, payload: dict, out: str | None, log) -> dict:
    """Запісаць субтытры ў гульню (`.orig`/`.bel`) або, з out, у іншую папку."""
    subs = payload.get("subtitles") or {}
    s = payload["battletech_csv"]
    if not subs:
        return {"subtitles": 0, "sub_stale": 0}
    if not s.get("subtitles"):
        raise SystemExit("battletech_csv: у game.json няма шляху subtitles")
    if out and not game_dir:
        raise SystemExit("субтытры: для --out патрэбны каталог гульні")

    done = stale = 0
    for video, texts in sorted(subs.items()):
        file_name = target_name(s, video)
        target = Target(srt_path(game_dir, s, file_name))
        if not os.path.exists(target.path):
            log(f"  субтытры {file_name}: у гульні няма — прапушчаны")
            stale += 1
            continue
        # Не рабіць .orig з нашага ж файла: калі пераклад ужо скапіяваны рукамі,
        # вярнуць арыгінал будзе нечым. Няхай уласнік спачатку аднавіць файл.
        if not out and not os.path.exists(target.orig):
            ours = parse(target.path)
            if len(ours) == len(texts) and ["\n".join(c[2]) for c in ours] == texts:
                log(f"  субтытры {file_name}: ужо наш пераклад без .orig — спачатку "
                    "вярніце арыгінал (Steam → праверка цэласнасці), файл прапушчаны")
                stale += 1
                continue
        cues = parse(target.source())
        if len(cues) != len(texts):
            log(f"  субтытры {file_name}: у гульні {len(cues)} рэплік, у перакладзе "
                f"{len(texts)} — файл прапушчаны")
            stale += 1
            continue
        base = target.source() if out else target.base()
        dest = os.path.join(out, file_name) if out else target.path
        render(dest, cues, texts)
        if not out:
            target.written()
        done += 1
    if done:
        log(f"  субтытры: запісана {done} файлаў" + (f" у {out}" if out else ""))
    if stale:
        log(f"  субтытры: прапушчана {stale} файлаў")
    return {"subtitles": done, "sub_stale": stale}


def restore(game_dir: str, payload: dict, log):
    s = payload["battletech_csv"]
    for video in sorted(payload.get("subtitles") or {}):
        file_name = target_name(s, video)
        target = Target(srt_path(game_dir, s, file_name))
        if os.path.exists(target.path) or os.path.exists(target.orig):
            log(f"  субтытры {file_name}: {target.restore()}")


def installed(game_dir: str, payload: dict) -> bool:
    s = payload["battletech_csv"]
    return all(Target(srt_path(game_dir, s, target_name(s, v))).installed()
               for v in payload.get("subtitles") or {})
