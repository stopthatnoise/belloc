"""UE .locres версіі 3 (Optimized_CityHash64_UTF16): чытанне і запіс.

    магія (16) | версія (1) | зрух масіва радкоў (8) | колькасць запісаў (4)
    прасторы: [хэш, FString] → ключы: [хэш, FString, хэш зыходнага радка, індэкс радка]
    масіў радкоў: [FString, колькасць спасылак]

Хэшы прастор, ключоў і зыходных радкоў пры запісе капіююцца з арыгінала —
таму гульня прымае наш тэкст за пераклад тых жа радкоў. Ключы, якіх у
культуры target няма (новыя радкі з абнаўлення), add_missing() бярэ разам з
хэшамі з англійскага locres.
"""
from __future__ import annotations

import io
import struct

from .pak import _fstr, fstring


class Locres:
    def __init__(self, data: bytes):
        b = io.BytesIO(data)
        self.magic = b.read(16)
        ver = b.read(1)[0]
        if ver != 3:
            raise SystemExit(f".locres версіі {ver}, чакалася 3")
        soff = struct.unpack("<q", b.read(8))[0]
        b.read(4)
        pos = b.tell()
        b.seek(soff)
        strings = []
        for _ in range(struct.unpack("<i", b.read(4))[0]):
            strings.append(_fstr(b))
            b.read(4)
        b.seek(pos)
        # [(хэш прасторы, прастора, [(хэш ключа, ключ, хэш зыходнага, тэкст)])]
        self.ns: list[tuple[int, str, list[list]]] = []
        for _ in range(struct.unpack("<I", b.read(4))[0]):
            nh = struct.unpack("<I", b.read(4))[0]
            name = _fstr(b)
            keys = []
            for _ in range(struct.unpack("<I", b.read(4))[0]):
                kh = struct.unpack("<I", b.read(4))[0]
                k = _fstr(b)
                sh, si = struct.unpack("<Ii", b.read(8))
                keys.append([kh, k, sh, strings[si]])
            self.ns.append((nh, name, keys))

    def to_dict(self) -> dict[str, dict[str, str]]:
        return {name: {k[1]: k[3] for k in keys} for _, name, keys in self.ns}

    def replace(self, texts: dict[str, dict[str, str]]) -> int:
        """Падмяніць тэксты {прастора: {ключ: тэкст}}; вяртае колькасць падменаў."""
        n = 0
        for _, name, keys in self.ns:
            t = texts.get(name, {})
            for k in keys:
                if k[1] in t:
                    k[3] = t[k[1]]
                    n += 1
        return n

    def add_missing(self, base: "Locres", texts: dict[str, dict[str, str]]) -> int:
        """Дадаць ключы з texts, якіх няма тут, але ёсць у base (звычайна en):
        хэшы прасторы, ключа і зыходнага радка бяруцца з base. Так у мод трапляюць
        радкі, якіх культура target яшчэ не мае (новыя ў абнаўленні гульні)."""
        mine = {name: {k[1] for k in keys} for _, name, keys in self.ns}
        by_name = {name: (nh, keys) for nh, name, keys in self.ns}
        n = 0
        for nh, name, keys in base.ns:
            t = texts.get(name, {})
            for kh, k, sh, _ in keys:
                if k in t and k not in mine.get(name, ()):
                    if name not in by_name:
                        by_name[name] = (nh, [])
                        self.ns.append((nh, name, by_name[name][1]))
                        mine[name] = set()
                    by_name[name][1].append([kh, k, sh, t[k]])
                    mine[name].add(k)
                    n += 1
        return n

    def save(self) -> bytes:
        index: dict[str, int] = {}
        refs: list[int] = []
        body = io.BytesIO()
        entries = 0
        body.write(struct.pack("<I", len(self.ns)))
        for nh, name, keys in self.ns:
            body.write(struct.pack("<I", nh) + fstring(name) + struct.pack("<I", len(keys)))
            for kh, k, sh, text in keys:
                i = index.setdefault(text, len(index))
                if i == len(refs):
                    refs.append(0)
                refs[i] += 1
                entries += 1
                body.write(struct.pack("<I", kh) + fstring(k) + struct.pack("<Ii", sh, i))
        head = 16 + 1 + 8 + 4
        soff = head + body.tell()
        out = io.BytesIO()
        out.write(self.magic + bytes([3]) + struct.pack("<qI", soff, entries))
        out.write(body.getvalue())
        out.write(struct.pack("<i", len(index)))
        for text, i in index.items():
            out.write(fstring(text) + struct.pack("<i", refs[i]))
        return out.getvalue()
