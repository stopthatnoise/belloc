"""Разбор і запіс .landb (Telltale LanguageDB, MSV5/MSV6) — па LandbWorker.cs
з TTG Tools.

MetaStream: "5VSM"/"6VSM", u32 памер секцыі даных, u32 памер async-секцыі,
u32 ?, u32 колькасць класаў, класы па 12 байт (u64 crc імя, u32 crc версіі).
Даныя: 4×u32 (два блокі з паметкамі), u32 памер блока запісаў (сам + count +
запісы), u32 count, запісы, хвост (u32 памер + даныя, 16 байт), async-даныя.

Запіс (для TWAU — з crc64 langres):
  u32 ID, u64 crc64 langres, u32 anmID, u32 0,
  [u32 12][8 байт імя anm], [u32 12][8 байт імя wav],
  [u32 L+8][u32 L][радок], u32 0,
  u32 памер блока langres = 4 + блок імя + блок тэксту + блок 8,
  [u32 L+8][u32 L][імя таго, хто кажа], [u32 L+8][u32 L][тэкст],
  [u32 8][u32 ?], (у рэмастэры — [u32 N][N-4 байт]), u32 флагі.

Тэкст і імя захоўваюцца байтамі (UTF-8 у рэмастэры, cp1252 у арыгінале).

  python -m belloc.engines.telltale.landb roundtrip <файл.landb>…      # разабраць і запісаць — ці тыя ж байты
  python -m belloc.engines.telltale.landb dump <файл.landb>            # ID, хто кажа, тэкст
"""
import struct, sys
from dataclasses import dataclass


@dataclass
class Record:
    id: int
    pre: bytes        # ад crc64 langres да памеру блока langres (не мяняецца)
    speaker: bytes
    text: bytes
    post: bytes       # блок 8, unicode-блок, флагі


class Landb:
    def __init__(self, data: bytes):
        self.magic = data[:4]
        assert self.magic in (b"5VSM", b"6VSM"), self.magic
        self.size, self.async_size, self.unk = struct.unpack_from("<III", data, 4)
        ncls = struct.unpack_from("<I", data, 16)[0]
        p = 20 + ncls * 12
        self.header = data[16:p]                       # count + класы
        self.head = data[p:p + 16]                     # 4×u32 да блока запісаў
        p += 16
        blk, count = struct.unpack_from("<II", data, p)
        p += 8
        self.unicode = self.magic == b"6VSM"           # у MSV6 пасля блока 8 — яшчэ блок
        self.records = []
        for _ in range(count):
            r, p = self._record(data, p)
            self.records.append(r)
        assert p - (20 + ncls * 12 + 16) == blk, "памер блока запісаў не супаў"
        self.tail = data[p:]
        assert len(data) == 20 + ncls * 12 + self.size + self.async_size, "памер файла не супаў"

    def _record(self, d, p):
        start = p
        rid = struct.unpack_from("<I", d, p)[0]
        p += 4 + 8 + 4 + 4 + 12 + 12                   # crc64, anmID, 0, anm, wav
        b, n = struct.unpack_from("<II", d, p)
        assert b == n + 8
        p += 8 + n + 4                                 # невядомы радок + 0
        pre = d[start + 4:p]
        langres = struct.unpack_from("<I", d, p)[0]
        p += 4
        b1, n1 = struct.unpack_from("<II", d, p)
        assert b1 == n1 + 8
        speaker = d[p + 8:p + 8 + n1]
        p += b1
        b2, n2 = struct.unpack_from("<II", d, p)
        assert b2 == n2 + 8
        text = d[p + 8:p + 8 + n2]
        p += b2
        b3 = struct.unpack_from("<I", d, p)[0]
        assert langres == 4 + b1 + b2 + b3, "блок langres"
        q = p + b3
        if self.unicode:
            q += struct.unpack_from("<I", d, q)[0]
        q += 4                                         # флагі
        return Record(rid, pre, speaker, text, d[p:q]), q

    def build(self) -> bytes:
        recs = bytearray()
        for r in self.records:
            b1, b2 = len(r.speaker) + 8, len(r.text) + 8
            b3 = struct.unpack_from("<I", r.post, 0)[0]
            recs += struct.pack("<I", r.id) + r.pre
            recs += struct.pack("<III", 4 + b1 + b2 + b3, b1, len(r.speaker)) + r.speaker
            recs += struct.pack("<II", b2, len(r.text)) + r.text + r.post
        body = self.head + struct.pack("<II", len(recs) + 8, len(self.records)) + bytes(recs)
        size = len(body) + len(self.tail) - self.async_size
        return (self.magic + struct.pack("<III", size, self.async_size, self.unk)
                + self.header + body + self.tail)


if __name__ == "__main__":
    cmd, files = sys.argv[1], sys.argv[2:]
    if cmd == "roundtrip":
        bad = 0
        for f in files:
            data = open(f, "rb").read()
            try:
                lb = Landb(data)
                ok = lb.build() == data
            except AssertionError as e:
                ok, lb = False, None
                print(f"{f}: {e}")
            bad += not ok
            if not ok and lb:
                print(f"{f}: байты не супалі")
        print(f"{len(files) - bad}/{len(files)} супалі")
    elif cmd == "dump":
        lb = Landb(open(files[0], "rb").read())
        print(f"{lb.magic} unicode-блок: {lb.unicode}, запісаў {len(lb.records)}")
        for r in lb.records:
            print(r.id, r.speaker.decode("utf-8", "replace"), "|", r.text.decode("utf-8", "replace"))
