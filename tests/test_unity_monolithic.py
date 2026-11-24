"""Маналітная табліца лакалізацыі і бінарны каталог Addressables.

    python -X utf8 -m unittest discover -s tests

Усё — на сінтэтычных даных: ключы, тэксты і байты каталога сабраныя тут, у тэсце;
ніводнага файла гульні і ніводнага радка яе тэксту.
"""
import hashlib
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from belloc import payload as payload_mod  # noqa: E402
from belloc.engines import unity_localization  # noqa: E402
from belloc.engines.unity_localization import catalog_bin, english, monolithic  # noqa: E402
from belloc.engines.unity_localization.apply import _targets, payload  # noqa: E402

RULES = {"dialogue": "/dialog_lines$",
         "entities": r"/(?:character_full_name|fullDescription)$"}


class FakeLoc:
    def __init__(self, sec):
        self.sec = sec

    def section(self, name):
        return self.sec


class SplitTest(unittest.TestCase):
    def test_rules_and_rest(self):
        rows = {"card1/dialog_lines": "a", "item/fullName_": "b",
                "item/character_full_name": "c", "menu/button_back": "d"}
        out = monolithic.split(rows, RULES, "system")
        self.assertEqual(list(out), ["dialogue", "entities", "system"])
        self.assertEqual(list(out["dialogue"]), ["card1/dialog_lines"])
        self.assertEqual(list(out["entities"]), ["item/character_full_name"])
        self.assertEqual(list(out["system"]), ["item/fullName_", "menu/button_back"])

    def test_first_rule_wins(self):
        rows = {"x/dialog_lines_fullDescription": "a"}
        out = monolithic.split(rows, {"dialogue": "dialog_lines", "entities": "fullDescription"},
                               "system")
        self.assertEqual(out, {"dialogue": rows})

    def test_no_rules(self):
        rows = {"a": "1", "b": "2"}
        self.assertEqual(monolithic.split(rows, {}, "system"), {"system": rows})

    def test_bad_regex_refused(self):
        with self.assertRaises(SystemExit):
            monolithic.split({}, {"dialogue": "(a+)+"}, "system")


def entry(name: bytes, crc: int, size: int, *, tag: bool = False) -> bytes:
    """Запіс бандла ў бінарным каталогу, як яго піша Addressables 2.x."""
    body = (struct.pack("<I", 32) + b"0" * 32          # m_Hash (32 hex)
            + struct.pack("<II", 1, 2)                  # два зрухі
            + struct.pack("<I", crc) + struct.pack("<I", size))
    head = b"\x11" * 16 if tag else b""
    return name + head + body


def catalog(*entries: bytes) -> bytes:
    return b"\x01\x02\x03\x04" + b"".join(entries) + b"\xff" * 8


class CatalogBinTest(unittest.TestCase):
    NAME = b"aaaa_assets_all_0000.bundle"
    OTHER = b"bbbb_assets_all_1111.bundle"

    def data(self, crc=0xDEADBEEF, tag=False):
        return catalog(entry(self.NAME, crc, 1000, tag=tag),
                       entry(self.OTHER, 0x0BADF00D, 2000))

    def test_zero_only_asked(self):
        for tag in (False, True):
            with self.subTest(tag=tag):
                src = self.data(tag=tag)
                out, n, absent = catalog_bin.zero_crc(src, {self.NAME.decode(): 1000})
                self.assertEqual(n, 1)
                self.assertEqual(absent, [])
                self.assertEqual(len(out), len(src))
                self.assertEqual(out.count(b"\0" * 4), src.count(b"\0" * 4) + 1)
                # другі бандл не чапаецца
                self.assertIn(struct.pack("<I", 0x0BADF00D), out)
                self.assertNotIn(struct.pack("<I", 0xDEADBEEF), out)

    def test_idempotent(self):
        src = self.data()
        once, n, _ = catalog_bin.zero_crc(src, {self.NAME.decode(): 1000})
        twice, m, _ = catalog_bin.zero_crc(once, {self.NAME.decode(): 1000})
        self.assertEqual((n, m), (1, 0))
        self.assertEqual(once, twice)

    def test_unknown_bundle(self):
        out, n, absent = catalog_bin.zero_crc(self.data(), {"cccc_assets_all_2222.bundle": 5})
        self.assertEqual((n, absent), (0, ["cccc_assets_all_2222.bundle"]))
        self.assertEqual(out, self.data())

    def test_name_without_record_refused(self):
        # імя ёсць, але памер не той — значыць фармат каталога не такі, як чакалі
        with self.assertRaises(ValueError):
            catalog_bin.zero_crc(self.data(), {self.NAME.decode(): 999})

    def test_ambiguous_refused(self):
        src = catalog(entry(self.NAME, 1, 1000), entry(self.NAME, 2, 1000))
        with self.assertRaises(ValueError):
            catalog_bin.zero_crc(src, {self.NAME.decode(): 1000})

    def test_hash_is_md5_hex(self):
        self.assertEqual(catalog_bin.hash_hex(b""), hashlib.md5(b"").hexdigest().encode())
        self.assertEqual(len(catalog_bin.hash_hex(b"x")), 32)
        self.assertTrue(catalog_bin.hash_hex(b"x").isalnum())


class EnglishTest(unittest.TestCase):
    def texts(self, tree):
        return english.texts(tree)

    def test_card_fields(self):
        tree = {"references": {"RefIds": [
            {"rid": 1, "data": {"m_cardId": "card1",
                                "m_cardData": {"m_keys": ["dialog_lines", "character_short_name"],
                                               "m_values": [{"rid": 2}, {"rid": 3}]}}},
            {"rid": 2, "data": {"m_value": "Line"}},
            {"rid": 3, "data": {"m_value": "Name"}},
        ]}}
        self.assertEqual(self.texts(tree),
                         {"card1/dialog_lines": "Line", "card1/character_short_name": "Name"})

    def test_card_modifier_explanation(self):
        tree = {"references": {"RefIds": [
            {"rid": 1, "data": {"m_cardId": "card1",
                                "m_cardData": {"m_keys": ["modifier"], "m_values": [{"rid": 2}]}}},
            {"rid": 2, "data": {"m_childProperties": [{"rid": 3}]}},
            {"rid": 3, "data": {"m_name": "some", "m_childProperties": [{"rid": 4}]}},
            {"rid": 4, "data": {"m_name": "Explanation", "m_value": "Because"}},
        ]}}
        self.assertEqual(self.texts(tree), {"card1.modifier[0]/explanation": "Because"})

    def test_entity_fields(self):
        tree = {"references": {"RefIds": [{"rid": 1, "data": {
            "m_shortName": "item", "m_fullName": "Thing", "m_description": "Long",
            "m_shortDescription": "Short", "m_alternativeNames": ["Alt"],
            "m_gearModifiersCollection": {"SkillModifiers": [{"Description": "Mod"}]},
        }}]}}
        got = self.texts(tree)
        self.assertEqual(got["item/character_full_name"], "Thing")
        self.assertEqual(got["item/fullDescription"], "Long")
        self.assertEqual(got["item/description"], "Short")
        self.assertEqual(got["item/alternativeNames_0"], "Alt")
        self.assertEqual(got["item.gearModifiers.skillModifiers[0]/description"], "Mod")

    def test_entity_listener_and_tasks(self):
        tree = {"references": {"RefIds": [{"rid": 1, "data": {
            "m_shortName": "eff",
            "m_counterListener": {"Description": "More"},
            "m_subTasks": {"m_values": [{"ID": 7, "Name": "Task",
                                         "Updates": {"m_values": [{"ID": 8, "Entry": "Entry"}]}}]},
        }}]}}
        got = self.texts(tree)
        self.assertEqual(got["eff.counter_listener/description"], "More")
        self.assertEqual(got["eff.subTasks{7}/name"], "Task")
        self.assertEqual(got["eff.subTasks{7}.updates{8}/entry"], "Entry")

    def test_entity_source_property_path(self):
        tree = {"references": {"RefIds": [{"rid": 1, "data": {
            "m_shortName": "eff",
            "m_nodes": [{"Description": "Deep", "SourcePropertyPath": "a.b"}],
        }}]}}
        self.assertEqual(self.texts(tree)["eff.a.b/description"], "Deep")

    def test_localization_table(self):
        tree = {"references": {"RefIds": [{"rid": 1, "data": {
            "m_entityType": "localization_table", "m_shortName": "menu",
            "m_entries": {"m_keys": ["button_back", "button_ok"],
                          "m_values": ['{"description": "", "text": "Back"}', "OK"]},
        }}]}}
        got = self.texts(tree)
        self.assertEqual(got["menu/button_back"], "Back")
        self.assertEqual(got["menu/button_ok"], "OK")

    def test_empty_and_non_string_skipped(self):
        tree = {"references": {"RefIds": [
            {"rid": 1, "data": {"m_cardId": "c", "m_cardData": {
                "m_keys": ["a", "b"], "m_values": [{"rid": 2}, {"rid": 3}]}}},
            {"rid": 2, "data": {"m_value": "   "}},
            {"rid": 3, "data": {"m_value": 42}},
        ]}}
        self.assertEqual(self.texts(tree), {})

    def test_first_value_wins(self):
        dup = {"m_shortName": "item", "m_fullName": "First"}
        tree = {"references": {"RefIds": [{"rid": 1, "data": dup},
                                          {"rid": 2, "data": {**dup, "m_fullName": "Second"}}]}}
        self.assertEqual(self.texts(tree)["item/character_full_name"], "First")


class FromOriginalTest(unittest.TestCase):
    """`[]` у перакладзе ← кавалак арыгінала (tables.expand, from_original)."""

    PAT = "(?s)\\[[^]]*\\]|.+"

    def test_source_prefers_english(self):
        self.assertEqual(monolithic.original({"k": "english"}, "k", "табліца"), "english")

    def test_source_falls_back_to_table(self):
        # англійскай у гульні няма — арыгінал для гульца гэта тэкст табліцы
        self.assertEqual(monolithic.original({}, "k", "табліца"), "табліца")

    def test_expand_whole_line(self):
        from belloc import tables
        pat = tables.from_original(self.PAT)
        self.assertEqual(tables.expand("[]", "Original line", pat), "Original line")
        self.assertEqual(tables.expand("Наш радок", "Original line", pat), "Наш радок")


class PayloadTest(unittest.TestCase):
    BASE = {"bundles": "aa/Win", "preview_locale": "ru"}

    def test_schema_three(self):
        p = payload(FakeLoc({**self.BASE, "monolithic_table": "T", "table_bundle": "*.bundle"}))
        self.assertEqual(p["schema"], 3)
        self.assertEqual(p["monolithic_table"], "T")
        self.assertLessEqual(p["schema"], payload_mod.SCHEMA)

    def test_catalog_bin_needs_hash_file(self):
        sec = {**self.BASE, "crc_catalog_bin": "aa/catalog.bin"}
        with self.assertRaises(SystemExit):
            payload(FakeLoc(sec))
        p = payload(FakeLoc({**sec, "hash_file": "aa/catalog.hash"}))
        self.assertEqual(p["schema"], 3)

    def test_monolithic_needs_bundle(self):
        with self.assertRaises(SystemExit):
            payload(FakeLoc({**self.BASE, "monolithic_table": "T"}))

    def test_plain_stays_low(self):
        self.assertNotIn("schema", payload(FakeLoc(self.BASE)))
        self.assertEqual(payload(FakeLoc({**self.BASE, "crc_catalog": "aa/catalog.json"}))["schema"], 2)

    def test_from_original_supported(self):
        self.assertTrue(getattr(unity_localization, "FROM_ORIGINAL", False))


class TargetsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.game = self.tmp.name
        os.makedirs(os.path.join(self.game, "aa", "Win"))
        for name in ("x_assets_all_1.bundle", "font.bundle"):
            with open(os.path.join(self.game, "aa", "Win", name), "wb") as f:
                f.write(b"\0")
        with open(os.path.join(self.game, "aa", "catalog.bin"), "wb") as f:
            f.write(b"\0")
        with open(os.path.join(self.game, "aa", "catalog.hash"), "wb") as f:
            f.write(b"0" * 32)

    def tearDown(self):
        self.tmp.cleanup()

    def payload(self, **extra):
        return {"bundles_dir": "aa/Win", "locale": "ru", "font_bundles": ["font.bundle"],
                "data_dir": None, "crc_catalog": None,
                "table_bundle": "x_assets_all_*.bundle", **extra}

    def test_monolithic_targets(self):
        paths = [os.path.normpath(t.path) for t in _targets(self.game, self.payload(
            monolithic_table="T", crc_catalog_bin="aa/catalog.bin", hash_file="aa/catalog.hash"))]
        win = os.path.join(self.game, "aa", "Win")
        for path in (os.path.join(win, "x_assets_all_1.bundle"),
                     os.path.join(win, "font.bundle"),
                     os.path.join(self.game, "aa", "catalog.bin"),
                     os.path.join(self.game, "aa", "catalog.hash")):
            self.assertIn(path, paths)

    def test_outside_refused(self):
        with self.assertRaises(SystemExit):
            _targets(self.game, self.payload(monolithic_table="T",
                                             crc_catalog_bin="../catalog.bin",
                                             hash_file="aa/catalog.hash"))


if __name__ == "__main__":
    unittest.main()
