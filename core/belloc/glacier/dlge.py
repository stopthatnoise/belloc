"""DLGE — рэплікі з субтытрамі Glacier 2 (007 First Light).

Разабрана 2026-10-26 на ўсіх 42 157 DLGE гульні 1.3.1.0 (кожны файл
спажываецца цалкам, build — байт у байт):

  u32 0, u32 1
  кантэйнеры запар, тып — першы байт:
    1 WavFile   u8 n; n × (i32, u32 cnt, u32 хэш); u32 хэш; u32 хэш; u32 0;
                16 моў (LANGS): i32 wav [+ (cnt−1) × i32, калі wav ≠ −1; cnt = 1 пры n = 0];
                                u8; i32; u32 даўжыня; XTEA(субтытр)
    2 Random    u32, u32, u32 k; k × (u16 спасылка, u32, u32 вага)
    3 Switch    u32 група, u32, u32 k; k × (u16 спасылка, u32 m, m × u32)
    4 Sequence  u32, u32, u32 k; k × (u16 спасылка, u32)
  u16 корань

Спасылка u16: старэйшы паўбайт — тып, астатнія 12 біт — нумар кантэйнера
гэтага тыпу (0x1000 — першы WavFile). Абсалютных зрушэнняў і памераў няма —
субтытр можна замяніць тэкстам іншай даўжыні.

Субтытр: `//[КОД]\\\\//{Прамоўца}\\\\//##B3B3B3#\\\\//||\\\\//%DX_катэгорыя%\\\\//^1^\\\\//(0,30)\\\\тэкст`
— загаловак (код голасу, імя на экране, колер, катэгорыя…), бачны тэкст —
пасля апошняга `\\\\`. Мова без субтытра — толькі загаловак.
"""
from __future__ import annotations

import re
import struct

from .locr import LANGS

SPEAKER = re.compile(r"//\{(.*?)\}\\\\")
CODE = re.compile(r"//\[(.*?)\]\\\\")
CATEGORY = re.compile(r"//%(.*?)%\\\\")


class WavFile:
    def __init__(self, head: bytes, langs: list[list[bytes]]):
        self.head = head
        self.langs = langs          # [префікс (індэксы), зашыфраваны субтытр] × 16

    def enc(self, code: str) -> bytes:
        return self.langs[LANGS.index(code)][1]

    def set_enc(self, code: str, enc: bytes):
        self.langs[LANGS.index(code)][1] = enc

    def build(self) -> bytes:
        return self.head + b"".join(pre + struct.pack("<I", len(enc)) + enc for pre, enc in self.langs)


class Dlge:
    def __init__(self, d: bytes):
        self.head = d[:8]
        self.items: list[WavFile | bytes] = []
        u32 = lambda p: struct.unpack_from("<I", d, p)[0]
        p, end = 8, len(d) - 2
        while p < end:
            t = d[p]
            if t == 1:
                n = d[p + 1]
                cnt = 1
                for i in range(n):
                    cnt = u32(p + 2 + 12 * i + 4)
                q = p + 2 + 12 * n + 12
                if u32(q - 4) != 0:
                    raise ValueError(f"DLGE: WavFile @{p:#x} — нечаканы хвост")
                head = d[p:q]
                langs = []
                for _ in LANGS:
                    s = q
                    wav = struct.unpack_from("<i", d, q)[0]
                    q += 4 + (4 * (cnt - 1) if wav != -1 else 0) + 1 + 4
                    l = u32(q)
                    langs.append([d[s:q], d[q + 4:q + 4 + l]])
                    q += 4 + l
                self.items.append(WavFile(head, langs))
            elif t in (2, 3, 4):
                k = u32(p + 9)
                q = p + 13
                if t == 2:
                    q += 10 * k
                elif t == 4:
                    q += 6 * k
                else:
                    for _ in range(k):
                        q += 2 + 4 + 4 * u32(q + 2)
                self.items.append(d[p:q])
            else:
                raise ValueError(f"DLGE: невядомы кантэйнер {t} @{p:#x}")
            if q > end:
                raise ValueError("DLGE: выйшлі за канец")
            p = q
        if p != end:
            raise ValueError("DLGE: лішнія байты")
        self.root = d[end:]

    @property
    def wavs(self) -> list[WavFile]:
        return [x for x in self.items if isinstance(x, WavFile)]

    def build(self) -> bytes:
        return self.head + b"".join(x.build() if isinstance(x, WavFile) else x for x in self.items) + self.root


TIMING = re.compile(r"//\(([\d.]+),([\d.]+)\)\\\\")


def segments(sub: str) -> tuple[str, list[tuple[str, str, str]]]:
    """Субтытр → (загаловак, [(пачатак, канец, тэкст)]). Субтытр бывае з некалькіх
    кавалкаў са сваімі таймінгамі (11 % у 007: `//(0,2.3)\\\\Першы…//(2.3,4.5)\\\\Другі…`);
    у кожнай мове — свая разбіўка. Канец апошняга кавалка — пачатак + 30."""
    m = TIMING.search(sub)
    if not m:
        return split_plain(sub)[0], []
    parts = TIMING.split(sub[m.start():])          # ['', a, b, тэкст, a, b, тэкст…]
    return sub[:m.start()], [(parts[i], parts[i + 1], parts[i + 2]) for i in range(1, len(parts), 3)]


def split_plain(sub: str) -> tuple[str, str]:
    if not sub.startswith("//"):
        return "", sub
    i = sub.rfind("\\\\")
    return (sub[:i + 2], sub[i + 2:]) if i >= 0 else (sub, "")


def split(sub: str) -> tuple[str, str]:
    """Субтытр → (загаловак, бачны тэкст: кавалкі праз \\n)."""
    head, segs = segments(sub)
    if not segs:
        return split_plain(sub)
    return head, "\n".join(t for _, _, t in segs)


def _fmt(x: float) -> str:
    return f"{round(x, 3):g}"


def join(head: str, lines: list[str], timing: list[tuple[str, str, str]]) -> str:
    """Загаловак + радкі перакладу на таймінгах арыгінала (агучка — англійская).
    Радкоў столькі ж — кожны на свой кавалак; іначай — межы прапарцыйна па кавалках
    арыгінала (апошні кавалак лічыцца па 4 с: яго «канец» — штучныя +30)."""
    if not timing:
        return head + " ".join(lines)
    n, k = len(timing), len(lines)
    if k == n:
        return head + "".join(f"//({a},{b})\\\\{t}" for (a, b, _), t in zip(timing, lines))
    starts = [float(a) for a, _, _ in timing]
    ends = starts[1:] + [starts[-1] + min(4.0, float(timing[-1][1]) - starts[-1])]

    def at(pos: float) -> float:                    # pos — у адзінках кавалкаў арыгінала
        j = min(int(pos), n - 1)
        return starts[j] + (pos - j) * (ends[j] - starts[j])
    out = []
    for i, t in enumerate(lines):
        a = timing[0][0] if i == 0 else _fmt(at(i * n / k))
        b = timing[-1][1] if i == k - 1 else _fmt(at((i + 1) * n / k))
        out.append(f"//({a},{b})\\\\{t}")
    return head + "".join(out)
