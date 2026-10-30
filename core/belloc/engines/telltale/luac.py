"""Lua 5.2 bytecode (Telltale): чытанне і замена радковых канстант.

Загаловак — 18 байтаў (`\\x1bLua`, 0x52, фармат, endianness, памеры int /
size_t / Instruction / lua_Number, integral, LUAC_TAIL). У Telltale size_t і
lua_Number — па 4 байты. Функцыя: лініі, параметры, код, канстанты (nil /
bool / number / string: size_t даўжыня з \\0 + байты), укладзеныя функцыі,
upvalue, адладка (крыніца, радкі, лакальныя, імёны upvalue). Зрушэнняў
паміж часткамі няма — радок можна замяніць іншым любой даўжыні.

    python -m belloc.engines.telltale.luac strings <файл.lua>   # хэш і канстанта-радок (Lua расшыфраваны)
"""
from __future__ import annotations

import struct
import sys

HEADER = 18


class Chunk:
    def __init__(self, data: bytes):
        if data[:5] != b"\x1bLua\x52":
            raise ValueError(f"не Lua 5.2: {data[:5]!r}")
        self.data = data
        self.le = data[6] == 1
        self.int_size, self.size_t, self.instr, self.num = data[7:11]
        self.strings: list[tuple[int, int, bytes]] = []   # (пачатак поля даўжыні, канец, радок) — толькі канстанты
        self.p = HEADER
        self._function()
        if self.p != len(data):
            raise ValueError(f"лішнія байты: {len(data) - self.p}")

    def _u(self, size: int) -> int:
        v = int.from_bytes(self.data[self.p:self.p + size], "little" if self.le else "big")
        self.p += size
        return v

    def _string(self) -> bytes | None:
        n = self._u(self.size_t)
        if not n:
            return None
        s = self.data[self.p:self.p + n - 1]
        self.p += n
        return s

    def _function(self):
        self.p += 2 * self.int_size + 3                    # linedefined, lastlinedefined, params, vararg, stack
        n = self._u(self.int_size)                          # код
        self.p += n * self.instr
        for _ in range(self._u(self.int_size)):             # канстанты
            t = self.data[self.p]
            self.p += 1
            if t == 1:
                self.p += 1
            elif t == 3:
                self.p += self.num
            elif t == 4:
                start = self.p
                s = self._string()
                self.strings.append((start, self.p, s or b""))
            elif t != 0:
                raise ValueError(f"невядомы тып канстанты {t} @ {self.p - 1}")
        for _ in range(self._u(self.int_size)):             # укладзеныя функцыі
            self._function()
        n = self._u(self.int_size)                          # upvalue: instack, idx
        self.p += n * 2
        self._string()                                      # source
        n = self._u(self.int_size)                          # lineinfo
        self.p += n * self.int_size
        for _ in range(self._u(self.int_size)):             # locvars
            self._string()
            self.p += 2 * self.int_size
        for _ in range(self._u(self.int_size)):             # імёны upvalue
            self._string()

    def replace(self, mapping: dict[bytes, bytes]) -> tuple[bytes, int]:
        """Новы bytecode: радковыя канстанты з mapping заменены. Вяртае (дадзеныя, колькі замен)."""
        out, last, n = [], 0, 0
        order = "little" if self.le else "big"
        for start, end, s in self.strings:
            if s in mapping:
                new = mapping[s]
                out += [self.data[last:start], (len(new) + 1).to_bytes(self.size_t, order), new, b"\0"]
                last, n = end, n + 1
        out.append(self.data[last:])
        return b"".join(out), n


if __name__ == "__main__":
    from .common import key_hash
    c = Chunk(open(sys.argv[2], "rb").read())
    for _, _, s in c.strings:
        text = s.decode("utf-8", "replace")
        print(key_hash(text), text)
