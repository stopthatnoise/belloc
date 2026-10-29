"""LOCR — тэксты інтэрфейсу Glacier 2 (007 First Light).

  u8 версія (0 або 1), u32 зрушэнне × мовы (0xFFFFFFFF — мовы ў рэсурсе няма);
  мова: u32 колькасць, [u32 хэш, u32 даўжыня, XTEA(тэкст + нулі да кратнага 8), 0].

Радкі трымаюцца зашыфраванымі — расшыфроўваюцца толькі патрэбныя мовы
(rpkg.decrypt_many), build збірае арыгінал байт у байт.
"""
from __future__ import annotations

import struct

LANGS = ["xx", "en", "fr", "it", "de", "es", "ru", "mx", "br", "pl", "cn", "jp", "tc", "kr", "tr", "uk"]


class Locr:
    def __init__(self, d: bytes):
        if d[0] not in (0, 1):
            raise ValueError(f"LOCR: версія {d[0]}")
        self.version = d[0]
        nl = (struct.unpack_from("<I", d, 1)[0] - 1) // 4
        # мова → {хэш: зашыфраваны блок} або None
        self.langs: list[dict[int, bytes] | None] = []
        for o in struct.unpack_from(f"<{nl}I", d, 1):
            if o == 0xFFFFFFFF:
                self.langs.append(None)
                continue
            res = {}
            n = struct.unpack_from("<I", d, o)[0]
            p = o + 4
            for _ in range(n):
                h, l = struct.unpack_from("<II", d, p)
                res[h] = d[p + 8:p + 8 + l]
                p += 8 + l + 1
            self.langs.append(res)

    def lang(self, code: str) -> dict[int, bytes] | None:
        i = LANGS.index(code)
        return self.langs[i] if i < len(self.langs) else None

    def build(self) -> bytes:
        blocks, offs = [], []
        pos = 1 + 4 * len(self.langs)
        for res in self.langs:
            if res is None:
                offs.append(0xFFFFFFFF)
                continue
            b = bytearray(struct.pack("<I", len(res)))
            for h, enc in res.items():
                b += struct.pack("<II", h, len(enc)) + enc + b"\0"
            offs.append(pos)
            pos += len(b)
            blocks.append(bytes(b))
        return bytes([self.version]) + struct.pack(f"<{len(offs)}I", *offs) + b"".join(blocks)
