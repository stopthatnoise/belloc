"""Гласарый у два слаі: games/<гульня>/glossary.json + local/<гульня>/glossary.local.json.

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

from belloc import cli, config, glossary  # noqa: E402

PUBLIC = {"_about": "…", "characters": {"Gustave": {"bel": "Густаў", "gender": "м"}},
          "places": {"Lumière": {"bel": "Люм’ер"}}}
LOCAL = {"story": {"Tomorrow comes": {"bel": "Заўтра настане"}},
         "places": {"Lumière": {"bel": "Люм’ер", "note": "лакальная заўвага"}}}


def dump(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


class GlossaryLayersTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        game = os.path.join(self.tmp, "games", "demo")
        dump(os.path.join(game, "game.json"), {"name": "Demo", "engine": "csv-folder", "hint_lang": None})
        dump(os.path.join(game, "glossary.json"), PUBLIC)
        os.environ["BELLOC_LOCAL"] = os.path.join(self.tmp, "local")
        self.local = os.path.join(self.tmp, "local", "demo")
        os.makedirs(self.local)
        self.loc = config.load(game)

    def tearDown(self):
        os.environ.pop("BELLOC_LOCAL", None)
        shutil.rmtree(self.tmp)

    def test_without_local_layer(self):
        self.assertEqual(self.loc.glossaries, [self.loc.glossary])

    def test_merge(self):
        dump(os.path.join(self.local, "glossary.local.json"), LOCAL)
        data = glossary.load_layers(self.loc.glossaries)
        self.assertEqual(set(data), {"_about", "characters", "places", "story"})
        self.assertEqual(data["places"]["Lumière"]["note"], "лакальная заўвага")   # лакальны перамагае
        self.assertEqual(glossary.validate(data), [])

    def test_lint_sees_local_layer(self):
        # тэрмін толькі ў лакальным слоі: без яго лінтэр яго не ведае, з ім — бачыць, што яго няма
        pairs = os.path.join(self.tmp, "pairs.json")
        dump(pairs, {"Tomorrow comes, Gustave.": "Наступіць ранак, Густаў."})
        report = os.path.join(self.tmp, "report.md")

        def findings():
            with redirect_stdout(io.StringIO()):
                cli.run_lint(self.loc, pairs, report, ["--checks", "glossary"])
            with open(report, encoding="utf-8") as f:
                return f.read()

        self.assertNotIn("Tomorrow comes", findings())
        dump(os.path.join(self.local, "glossary.local.json"), LOCAL)
        self.assertIn("Tomorrow comes", findings())


if __name__ == "__main__":
    unittest.main()
