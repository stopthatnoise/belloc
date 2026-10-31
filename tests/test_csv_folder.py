"""Рухавік csv-folder на выдуманай «гульні»: Official/ + Template/ → наша папка мовы.

    python -X utf8 -m unittest discover -s tests
"""
import csv
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from belloc import config, tables  # noqa: E402
from belloc.engines import base, csv_folder  # noqa: E402

SEC = {"dir": "Data/Loc", "official": "Official", "template": "Template", "target": "Belarusian",
       "code": "BE", "langs": {"en": "EN"}, "fixed": {"LanguageDropdown": "Беларуская"},
       "skip": "^Skip_"}


def write_csv(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f, lineterminator="\r\n").writerows(rows)


class CsvFolderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        g = os.path.join(self.tmp, "game", "Data", "Loc")
        write_csv(os.path.join(g, "Official", "Menu.csv"),
                  [["ID", "Speaker", "EN"], ["Start", "", "Start game"], ["Hello", "Guide", "Hello there"],
                   ["Skip_1", "", "skip me"], ["LanguageDropdown", "", "English"]])
        write_csv(os.path.join(g, "Template", "Menu.csv"),
                  [["ID", "XX"], ["Start", ""], ["Hello", ""], ["Skip_1", ""], ["LanguageDropdown", ""]])
        game = os.path.join(self.tmp, "games", "demo")
        os.makedirs(game)
        with open(os.path.join(game, "game.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "Demo", "engine": "csv-folder", "hint_lang": None, "csv_folder": SEC}, f)
        os.environ["BELLOC_LOCAL"] = os.path.join(self.tmp, "local")
        os.makedirs(os.path.join(self.tmp, "local", "demo"))
        with open(os.path.join(self.tmp, "local", "demo", "local.json"), "w") as f:
            json.dump({"game_dir": os.path.join(self.tmp, "game")}, f)
        self.loc = config.load(game)
        with redirect_stdout(io.StringIO()):
            csv_folder.extract(self.loc)
            tables.sync(self.loc)
        rows = tables.load_all(self.loc)["Menu"]
        for r in rows:
            r["bel"] = {"Start": "Пачаць гульню", "Hello": "Прывітанне"}[r["key"]]
        tables.save(self.loc, "Menu", rows)

    def tearDown(self):
        os.environ.pop("BELLOC_LOCAL", None)
        shutil.rmtree(self.tmp)

    def out(self):
        with open(os.path.join(self.tmp, "out", "Menu.csv"), encoding="utf-8", newline="") as f:
            return list(csv.reader(f))

    def test_extract(self):
        src = tables.load_all(self.loc)["Menu"]
        self.assertEqual([r["key"] for r in src], ["Start", "Hello"])          # skip і fixed — не
        self.assertEqual(src[1]["ctx"], "Speaker=Guide")

    def test_apply(self):
        with redirect_stdout(io.StringIO()):
            base.patch(self.loc, csv_folder, os.path.join(self.tmp, "out"))
        self.assertEqual(self.out(), [["ID", "BE"], ["Start", "Пачаць гульню"], ["Hello", "Прывітанне"],
                                      ["Skip_1", ""], ["LanguageDropdown", "Беларуская"]])
        self.assertFalse(csv_folder.installed(self.loc.game_dir, base.build_payload(self.loc, csv_folder)))

    def test_stale_left_empty(self):
        g = os.path.join(self.tmp, "game", "Data", "Loc", "Official", "Menu.csv")
        write_csv(g, [["ID", "Speaker", "EN"], ["Start", "", "Begin the game"], ["Hello", "Guide", "Hello there"]])
        with redirect_stdout(io.StringIO()) as log:
            base.patch(self.loc, csv_folder, os.path.join(self.tmp, "out"))
        self.assertIn("арыгінал змяніўся ў 1", log.getvalue())
        self.assertEqual(self.out()[1], ["Start", ""])

    def test_from_original(self):
        # радок, пакінуты як у арыгінале: у рэпазіторыі — заглушка, у гульні — тэкст Official
        self.loc.raw["from_original"] = r"(?s)\A(?:\[\]|.+)\Z"
        rows = tables.load_all(self.loc)["Menu"]
        rows[1]["bel"] = rows[1]["en"]
        tables.save(self.loc, "Menu", rows)
        self.assertEqual([r["bel"] for r in tables.load_repo(self.loc)["Menu"]], ["Пачаць гульню", "[]"])
        with redirect_stdout(io.StringIO()):
            base.patch(self.loc, csv_folder, os.path.join(self.tmp, "out"))
        self.assertEqual(self.out()[2], ["Hello", "Hello there"])


if __name__ == "__main__":
    unittest.main()
