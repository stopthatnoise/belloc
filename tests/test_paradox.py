"""Рухавік paradox на выдуманай «гульні»: yml з BOM → source/, пераклад → replace/.

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

from belloc import config, tables  # noqa: E402
from belloc.engines import base, paradox  # noqa: E402

SEC = {"roots": ["game", "jomini"], "langs": {"en": "english", "ru": "russian"},
       "extract_langs": ["en", "ru"], "target": "russian",
       "replace_dir": "game/localization/replace/russian/bel"}


def yml(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="\n") as f:
        f.write(text)


class ParadoxTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        g = os.path.join(self.tmp, "game")
        yml(os.path.join(g, "game", "localization", "english", "ui", "menu_l_english.yml"),
            'l_english:\n # каментар\n START:0 "Start the "big" game" # хвост\n QUIT: "Quit"\n')
        yml(os.path.join(g, "game", "localization", "english", "replace", "old_l_english.yml"),
            'l_english:\n START:0 "ignored"\n')
        yml(os.path.join(g, "jomini", "localization", "english", "core_l_english.yml"),
            'l_english:\n OK:0 "OK"\n')
        yml(os.path.join(g, "game", "localization", "russian", "other_l_russian.yml"),
            'l_russian:\n START:0 "Начать"\n OK:0 "Ладно"\n')
        self.gamedir = g
        game = os.path.join(self.tmp, "games", "demo")
        os.makedirs(game)
        with open(os.path.join(game, "game.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "Demo", "engine": "paradox", "paradox": SEC}, f)
        os.environ["BELLOC_LOCAL"] = os.path.join(self.tmp, "local")
        os.makedirs(os.path.join(self.tmp, "local", "demo"))
        with open(os.path.join(self.tmp, "local", "demo", "local.json"), "w") as f:
            json.dump({"game_dir": g}, f)
        self.loc = config.load(game)
        with redirect_stdout(io.StringIO()):
            paradox.extract(self.loc)
            tables.sync(self.loc)

    def tearDown(self):
        os.environ.pop("BELLOC_LOCAL", None)
        shutil.rmtree(self.tmp)

    def translate(self, table, bel):
        rows = tables.load_all(self.loc)[table]
        for r in rows:
            r["bel"] = bel.get(r["key"], "")
        tables.save(self.loc, table, rows)

    def test_extract(self):
        full = tables.load_all(self.loc)
        self.assertEqual(sorted(full), ["@jomini/core", "ui/menu"])          # replace/ — не
        menu = {r["key"]: r for r in full["ui/menu"]}
        self.assertEqual(menu["START"]["en"], 'Start the "big" game')         # да апошняга "
        self.assertEqual(menu["START"]["ru"], "Начать")                       # падказка па ключы
        self.assertEqual(full["@jomini/core"][0]["ru"], "Ладно")

    def test_apply_and_restore(self):
        self.translate("ui/menu", {"START": 'Пачаць "вялікую" гульню', "QUIT": "Выйсці"})
        self.translate("@jomini/core", {"OK": "Добра"})
        with redirect_stdout(io.StringIO()):
            base.patch(self.loc, paradox)
        dest = os.path.join(self.gamedir, SEC["replace_dir"])
        with open(os.path.join(dest, "ui", "menu_l_russian.yml"), "rb") as f:
            self.assertEqual(f.read().decode("utf-8"),
                             '﻿l_russian:\n START:0 "Пачаць "вялікую" гульню"\n QUIT:0 "Выйсці"\n')
        self.assertTrue(os.path.exists(os.path.join(dest, "jomini", "core_l_russian.yml")))
        payload = base.build_payload(self.loc, paradox)
        self.assertTrue(paradox.installed(self.gamedir, payload))
        with redirect_stdout(io.StringIO()):
            base.restore(self.loc, paradox)
        self.assertFalse(os.path.exists(os.path.join(self.gamedir, "game", "localization", "replace")))

    def test_out_keeps_other_files(self):
        self.translate("ui/menu", {"QUIT": "Выйсці"})
        out = os.path.join(self.tmp, "out")
        os.makedirs(out)
        with open(os.path.join(out, "mine.txt"), "w") as f:
            f.write("x")
        with redirect_stdout(io.StringIO()):
            base.patch(self.loc, paradox, out)
        self.assertTrue(os.path.exists(os.path.join(out, "mine.txt")))
        self.assertTrue(os.path.exists(os.path.join(out, "ui", "menu_l_russian.yml")))
        self.assertFalse(os.path.exists(os.path.join(self.gamedir, SEC["replace_dir"])))


if __name__ == "__main__":
    unittest.main()
