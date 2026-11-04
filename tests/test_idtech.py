"""Рухавік idtech на выдуманых даных: FarmHash, lang/strings, кантэйнер IDCL v13,
прэфіксы рэплік і імёны над субтытрамі.

    python -X utf8 -m unittest discover -s tests
"""
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from belloc.engines.idtech import farm, lang, resources  # noqa: E402
from belloc.engines.idtech.apply import build_lang  # noqa: E402
from belloc.engines.idtech.common import NAMES, split_prefix, table_of  # noqa: E402


def data(n: int) -> bytes:
    return bytes((i * 37 + n * 7) & 255 for i in range(n))


def container(blobs: list[tuple[str, str, int, bytes]]) -> bytes:
    """IDCL v13: рэсурсы (тып, імя, variation, даныя) без сціску, хэшы — як у гульні."""
    names = []
    for t, n, _, _ in blobs:
        names += [t, n]
    pool = b"".join(s.encode() + b"\0" for s in names)
    offs, o = [], 0
    for s in names:
        offs.append(o)
        o += len(s.encode()) + 1
    st = struct.pack("<Q", len(names)) + struct.pack(f"<{len(names)}Q", *offs) + pool
    st += bytes(-len(st) % 8)
    nres = len(blobs)
    entoff = 0x88
    stroff = entoff + resources.ENTRY * nres
    idxoff = stroff + len(st)
    idx = struct.pack(f"<{len(names)}Q", *range(len(names)))
    idxend = idxoff + len(idx)
    dataoff = (idxend + 4 + 0xf) & ~0xf
    ent, body = bytearray(), bytearray()
    for i, (_, _, var, d) in enumerate(blobs):
        e = bytearray(resources.ENTRY)
        struct.pack_into("<qqq", e, 0, 0, 1, -1)
        struct.pack_into("<Q", e, 32, 2 * i)
        struct.pack_into("<3Q", e, 56, dataoff + len(body), len(d), len(d))
        h = farm.fingerprint64(d)
        struct.pack_into("<QQQ", e, 80, h, 0, h)
        struct.pack_into("<IIBBH", e, 104, 5, 4, 0, 0, var)
        ent += e
        body += d
    head = bytearray(0x88)
    head[:4] = b"IDCL"
    struct.pack_into("<I", head, 4, 13)
    struct.pack_into("<I", head, 0x24, nres)
    struct.pack_into("<I", head, 0x30, len(names))
    struct.pack_into("<I", head, 0x3c, len(st))
    struct.pack_into("<6Q", head, 0x44, stroff, idxend, entoff, idxend, idxend, dataoff)
    struct.pack_into("<I", head, 0x78, idxend)
    f = bytearray(head + ent + st + idx + b"IDCL")
    f += bytes(dataoff - len(f)) + body
    struct.pack_into("<Q", f, 0x80, farm.fingerprint64(bytes(f[0x88:idxend + 4])))
    struct.pack_into("<Q", f, 0x08, farm.fingerprint64(bytes(f[0x14:0x88])))
    return bytes(f)


class FarmTest(unittest.TestCase):
    def test_vectors(self):
        # farmhash::Fingerprint64 (бібліятэка farmhash на C) ад data(n)
        want = {0: 0x9ae16a3b2f90404f, 3: 0x574f36f33d67ad1f, 8: 0x4548b5fcd426b891,
                20: 0xce7991fec11e9317, 40: 0xbeff301b7043d132, 64: 0x6c330b73df7045ee,
                65: 0x7ee01a4bf1fb30fb, 200: 0x2af51d652a18bf49, 1000: 0x89dc15a2b4c518f9}
        for n, h in want.items():
            self.assertEqual(farm.fingerprint64(data(n)), h, n)


class LangTest(unittest.TestCase):
    def test_roundtrip(self):
        items = [(1, "#str_a", "Play"), (2, "#str_b", ""), (3, "#str_c", "Радок\nдругі")]
        b = lang.build(items)
        self.assertEqual(struct.unpack_from("<I", b, 0)[0], len(b) - 4)
        self.assertEqual(lang.parse(b), items)


class ContainerTest(unittest.TestCase):
    def test_replace(self):
        old = lang.build([(1, "#str_a", "Play")])
        f = container([("file", "x", 0, b"abc"), ("lang", "strings", 0x1aa, old)])
        self.assertTrue(resources.hashes_ok(f))
        new = lang.build([(1, "#str_a", "Гуляць")])
        g = resources.replace(f, 1, new)
        self.assertTrue(resources.hashes_ok(g))
        self.assertEqual(g[:len(f)][0x88 + resources.ENTRY * 2:], f[0x88 + resources.ENTRY * 2:])
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "c.resources")
            with open(p, "wb") as fh:
                fh.write(g)
            t = resources.read_table(p)
            self.assertEqual([(r.type, r.name, r.variation) for r in t],
                             [("file", "x", 0), ("lang", "strings", 0x1aa)])
            self.assertEqual(resources.read_data(p, t[1]), new)
            self.assertEqual(resources.read_data(p, t[0]), b"abc")
            e = 0x88 + resources.ENTRY
            self.assertEqual(struct.unpack_from("<Q", g, e + 80)[0], farm.fingerprint64(new))


class LinesTest(unittest.TestCase):
    def test_prefix(self):
        self.assertEqual(split_prefix("[name:Guard][p-5][force]Stop![1.2]Now."),
                         ("[name:Guard][p-5][force]", "Stop![1.2]Now."))
        self.assertEqual(split_prefix("[2]Hm."), ("", "[2]Hm."))

    def test_tables(self):
        self.assertEqual(table_of("#str_vo_nl_hero_ch04se01_150_hint_ne_01"), "vo/nl/ch04se01")
        self.assertEqual(table_of("#str_vo_sl_guardone_combat_ne_02"), "vo/sl/guardone")
        self.assertEqual(table_of("#str_mission_Rome_intro_desc"), "ui/mission/rome")
        self.assertEqual(table_of("#str_code_menu_play"), "ui/code")

    def test_build_lang(self):
        en = {"#a": "[name:Guard][p-5]Stop!", "#b": "[name: Guard]Go.", "#c": "Hi", "#d": "Menu"}
        items = [(1, "#a", "[name:Страж]Стой!"), (2, "#b", "[name:Страж]Иди."),
                 (3, "#c", "Привет"), (4, "#d", "Меню")]
        out, n = build_lang(items, en, {"vo/x": {"#a": "Стой!", "#c": "[name:X]Вітаю"},
                                        NAMES: {}}, {"#d": "Беларуская"})
        self.assertEqual(n, 2)
        self.assertEqual([t for _, _, t in out],
                         ["[name:Страж][p-5]Стой!", "[name:Страж]Иди.", "Вітаю", "Беларуская"])
        out, _ = build_lang(items, en, {"vo/x": {"#a": "Стой!"}, NAMES: {"Guard": "Вартавы"}}, {})
        self.assertEqual(out[0][2], "[name:Вартавы][p-5]Стой!")
        self.assertEqual(out[1][2], "[name:Страж]Иди.")         # неперакладзенае — як было

    def test_from_original(self):
        from belloc import tables
        pat = tables.from_original(r"(?s)\A.+\Z")
        en = {"#a": "[name:Guard]Halt!", "#b": "TEMP text"}
        items = [(1, "#a", "[name:Страж]Halt!"), (2, "#b", "TEMP")]
        out, _ = build_lang(items, en, {"vo/x": {"#a": "[]", "#b": "[]"}, NAMES: {}}, {}, pat)
        self.assertEqual([t for _, _, t in out], ["[name:Страж]Halt!", "TEMP text"])
        self.assertEqual(tables.collapse("Halt!", "Halt!", pat), "[]")
        self.assertEqual(tables.collapse("Стой!", "Halt!", pat), "Стой!")


if __name__ == "__main__":
    unittest.main()
