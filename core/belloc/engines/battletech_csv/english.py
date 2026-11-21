"""Аднаўленне англійскага арыгінала з файлаў гульні (стратэгія C).

Ключ табліцы — нармалізаваны англійскі радок, таму англійскую крыніцу можна
знайсці ў самой гульні: у JSON даных, у субтытрах, у DLL і ў тэкстах сцэн.
Кожны знойдзены радок параўноўваецца з ключом па тым жа `_NormalizeString`.

Парадак якасці: JSON > SRT > DLL > тэкст у `.assets` > там жа key-like
(кандыдат роўны ключу без прабелаў і рэгістру — такія радкі патрабуюць
аднаўлення прабелаў перад перакладам).
"""
from __future__ import annotations

import json
import os
import re

from .norm import normalize

RANK = {"json": 5, "srt": 4, "dll": 3, "asset": 2, "asset-key": 1}

ASCII_RUN = re.compile(rb"[\x20-\x7e]{4,4000}")

SRT_TIME = re.compile(r"^\d\d:\d\d:\d\d[,.]\d\d\d -->")


def _walk_json(obj, path: str, out: list[tuple[str, str]]):
    if isinstance(obj, dict):
        for k, v in obj.items():
            _walk_json(v, path + "/" + str(k), out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _walk_json(v, path + "/" + str(i), out)
    elif isinstance(obj, str):
        out.append((path, obj))


def _offer(found: dict, keys: dict, key_text: dict, text: str, src: str, at: str):
    text = text.strip()
    h = keys.get(normalize(text))
    if h is None:
        return
    quality = "keylike" if text.lower() == key_text[h] else "text"
    score = RANK["asset-key" if quality == "keylike" else src]
    rec = found.get(h)
    if rec is None or score > rec["score"]:
        found[h] = {"en": text, "src": src, "at": at, "q": quality,
                    "score": score, "hits": 1}
    elif rec["score"] == score:
        rec["hits"] += 1


def scan_json(root: str, keys, key_text, found, stats, prio_src="json"):
    for dirpath, _, names in os.walk(root):
        for name in names:
            if not name.lower().endswith(".json"):
                continue
            p = os.path.join(dirpath, name)
            rel = os.path.relpath(p, root).replace("\\", "/")
            try:
                with open(p, encoding="utf-8-sig") as f:
                    data = json.load(f)
            except Exception:
                stats["json_bad"] += 1
                # зламаны JSON (каментары, канечная коска): пакідаем радкі ў двукоссях
                try:
                    with open(p, encoding="utf-8-sig", errors="replace") as f:
                        raw = f.read()
                except OSError:
                    continue
                for i, m in enumerate(re.finditer(r'"(?:[^"\\]|\\.)*"', raw)):
                    try:
                        s = json.loads(m.group())
                    except Exception:
                        continue
                    _offer(found, keys, key_text, s, prio_src, f"{rel}#frag{i}")
                continue
            strs = []
            _walk_json(data, "", strs)
            for pointer, s in strs:
                _offer(found, keys, key_text, s, prio_src, rel + "#" + pointer)
            stats["json_files"] += 1


def scan_srt(root: str, keys, key_text, found, stats):
    if not os.path.isdir(root):
        return
    for name in sorted(os.listdir(root)):
        if not (name.lower().endswith(".srt") and "english" in name.lower()):
            continue
        p = os.path.join(root, name)
        try:
            with open(p, encoding="utf-8-sig", errors="replace") as f:
                lines = f.read().splitlines()
        except OSError:
            continue
        block = []
        for line in lines + [""]:
            if not line.strip():
                if block:
                    _offer(found, keys, key_text, " ".join(block), "srt", name)
                    block = []
                continue
            if line.strip().isdigit() or SRT_TIME.match(line):
                continue
            block.append(line.strip())
        stats["srt_files"] += 1


def scan_dlls(managed: str, keys, key_text, found, stats):
    from .netus import us_strings
    if not os.path.isdir(managed):
        return
    for name in sorted(os.listdir(managed)):
        if not name.lower().endswith(".dll"):
            continue
        p = os.path.join(managed, name)
        try:
            for at, s in us_strings(p):
                _offer(found, keys, key_text, s, "dll", f"{name}#us@{at}")
        except Exception:
            stats["dll_bad"] += 1
            continue
        stats["dll_files"] += 1


def scan_assets(data_dir: str, keys, key_text, found, stats, levels=True):
    names = [n for n in sorted(os.listdir(data_dir)) if n.endswith(".assets")]
    if levels:
        names += [n for n in sorted(os.listdir(data_dir))
                  if n.startswith("level") and not n.endswith(".resS")]
    for name in names:
        p = os.path.join(data_dir, name)
        if not os.path.isfile(p):
            continue
        try:
            with open(p, "rb") as f:
                b = f.read()
        except OSError:
            continue
        seen = set()
        for m in ASCII_RUN.finditer(b):
            run = m.group()
            if run in seen:
                continue
            seen.add(run)
            try:
                s = run.decode("ascii")
            except UnicodeDecodeError:
                continue
            if normalize(s) not in keys:
                continue
            _offer(found, keys, key_text, s, "asset", f"{name}@{m.start()}")
        stats["asset_files"] += 1


def recover(data_dir: str, stream_dir: str, subtitles: str, keys, key_text, stats: dict,
            scan: dict | None = None) -> dict:
    """Знайсці англійскую крыніцу для як мага большай колькасці ключоў."""
    scan = scan or {}
    found: dict[str, dict] = {}
    if scan.get("json", True):
        scan_json(stream_dir, keys, key_text, found, stats)
    if scan.get("srt", True):
        scan_srt(subtitles, keys, key_text, found, stats)
    if scan.get("dll", True):
        scan_dlls(os.path.join(data_dir, "Managed"), keys, key_text, found, stats)
    if scan.get("assets", True):
        scan_assets(data_dir, keys, key_text, found, stats, levels=scan.get("levels", True))
    return found
