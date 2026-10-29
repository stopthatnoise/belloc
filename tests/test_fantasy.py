"""Разбор «Выніковага слоўніка» (core/belloc/fantasy.py) на выдуманых запісах.

    python -X utf8 -m unittest discover -s tests
"""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from belloc import config, fantasy, tables  # noqa: E402

HEAD = ["англ.", "бел.", "ст.-бел.", "рус.", "пол.", "укр.", "чэш.", "ням.", "фр.", "іншыя мовы"]
ROWS = [
    ["moon blade", "(чароўная зброя) месяцо́вы клі́нок, -а м.", "", "", "", "", "", "", "", ""],
    ["glimmer", "1) (у D&D3) блі́скаўка ж.; 2) мігаце́нне", "", "", "", "", "", "", "", ""],
    ["sparkle", "гл. glimmer", "", "", "", "", "", "", "", ""],
    ["warden (WD)", "вартаўні́к, -а́ м. / вартаўні́ца ж.", "", "", "", "", "", "", "", ""],
    ["grim, grimness", "панура́сць ж. гл. тс. glimmer", "", "", "", "", "", "", "", ""],
    ["", "", "", "", "", "", "", "", "", ""],
]


class FantasyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["BELLOC_LOCAL"] = os.path.join(self.tmp, "local")
        os.makedirs(os.path.join(self.tmp, "local", "dicts"))
        with open(os.path.join(self.tmp, "local", "dicts", "fantasy.tsv"), "w", encoding="utf-8", newline="") as f:
            f.write("\r\n".join("\t".join(r) for r in [HEAD] + ROWS) + "\r\n")
        self.rows = fantasy.load()
        self.idx = fantasy.index(self.rows)

    def tearDown(self):
        os.environ.pop("BELLOC_LOCAL", None)
        shutil.rmtree(self.tmp)

    def v(self, term):
        return fantasy.variants(self.idx[term], self.idx)

    def test_variants(self):
        self.assertEqual(len(self.rows), 5)                    # пусты радок прапушчаны
        self.assertEqual(self.v("moon blade"), ["месяцовы клінок"])
        self.assertEqual(self.v("glimmer"), ["бліскаўка", "мігаценне"])
        self.assertEqual(self.v("sparkle"), ["бліскаўка", "мігаценне"])        # «гл.»
        self.assertEqual(self.v("warden"), ["вартаўнік", "вартаўніца"])
        self.assertEqual(self.v("grim"), ["панурасць", "бліскаўка", "мігаценне"])

    def test_en_forms(self):
        self.assertEqual(fantasy.en_forms("warden (WD)"), ["warden", "WD"])
        self.assertEqual(fantasy.en_forms("grim, grimness"), ["grim", "grimness"])
        self.assertEqual(fantasy.en_forms("acid (damage)"), ["acid"])

    def test_covered(self):
        vs = self.v("moon blade")
        self.assertTrue(fantasy.covered("Ён выцягнуў месяцовым клінком", vs))   # іншы склон
        self.assertFalse(fantasy.covered("Ён выцягнуў меч", vs))

    def test_report(self):
        game = os.path.join(self.tmp, "games", "demo")
        os.makedirs(game)
        with open(os.path.join(game, "game.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "Demo", "engine": "test", "hint_lang": None}, f)
        with open(os.path.join(game, "glossary.json"), "w", encoding="utf-8") as f:
            json.dump({"terms": {"warden": {"bel": "стораж"}}}, f, ensure_ascii=False)
        loc = config.load(game)
        os.makedirs(loc.source)
        with open(os.path.join(loc.source, "en.json"), "w", encoding="utf-8") as f:
            json.dump({"t": {"1": "Draw the moon blade", "2": "The wardens wait", "3": "A WD sign",
                             "4": "A glimmer in the dark", "5": "Glimmers again"}}, f)
        with redirect_stdout(io.StringIO()):
            tables.sync(loc)
        rows = tables.load_all(loc)["t"]
        for r, bel in zip(rows, ["Выцягні месяцовы клінок", "Стаража чакае", "Знак вартаўніка",
                                 "Святло ў цемры", "Зноў мігаценне"]):
            r["bel"] = bel
        tables.save(loc, "t", rows)
        out = os.path.join(loc.build, "fantasy.md")
        with redirect_stdout(io.StringIO()):
            fantasy.report(loc, out)
        with open(out, encoding="utf-8") as f:
            md = f.read()
        self.assertIn("| warden | стораж | вартаўнік, вартаўніца |", md)    # гласарый ≠ слоўнік
        self.assertNotIn("### warden", md)                 # тэрмін гласарыя — толькі ў раздзеле 1
        self.assertIn("### glimmer — 1 з 2", md)            # «Glimmers» таксама знойдзена
        self.assertNotIn("### moon blade", md)

    def test_qualifiers(self):
        self.assertEqual(fantasy.qualifiers("fire (damage)"), ["damage"])
        self.assertEqual(fantasy.qualifiers("cast (a spell)"), ["spell"])
        self.assertEqual(fantasy.qualifiers("dexterity (DEX)"), [])


if __name__ == "__main__":
    unittest.main()
