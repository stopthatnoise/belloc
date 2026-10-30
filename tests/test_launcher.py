"""Каталог і лаўнчар на выдуманай гульні paradox: пакет перакладу, усталёўка з
каталога, метка belloc.json, «ёсць новая версія», «зляцеў», выдаленне, напамін у exe.

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

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "core"))
sys.path.insert(0, os.path.join(HERE, "..", "installer"))
sys.path.insert(0, os.path.join(HERE, "..", "launcher"))

from belloc import catalog, config, payload, release, tables  # noqa: E402
from belloc.engines import paradox  # noqa: E402
from belloc.install import state  # noqa: E402
import main as launcher  # noqa: E402
import run as installer  # noqa: E402

SEC = {"roots": ["game"], "langs": {"en": "english"}, "extract_langs": ["en"],
       "target": "russian", "replace_dir": "game/localization/replace/russian/bel"}
REL = {"title": "Беларускі пераклад Demo", "version": "1.0", "exe": "demo.exe", "file": "Demo_BE",
       "language_name": "Беларуская", "replaces": "Русский", "menu": "Налады",
       "contents": "{strings} радкоў.", "how": "Дадае папку."}


class VersionTest(unittest.TestCase):
    def test_newer(self):
        self.assertTrue(catalog.newer("1.10", "1.9"))
        self.assertTrue(catalog.newer("1.1", "1.0"))
        self.assertFalse(catalog.newer("1.0", "1.0"))
        self.assertTrue(catalog.newer("1.0", None))


class Fixture(unittest.TestCase):
    """Выдуманая гульня paradox, яе пакет і лакальны каталог (без тэстаў — для LauncherTest і AppTest)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        g = os.path.join(self.tmp, "game")
        yml = os.path.join(g, "game", "localization", "english", "menu_l_english.yml")
        os.makedirs(os.path.dirname(yml))
        with open(yml, "w", encoding="utf-8-sig", newline="\n") as f:
            f.write('l_english:\n START:0 "Start"\n')
        self.gamedir = g
        game = os.path.join(self.tmp, "games", "demo")
        os.makedirs(game)
        with open(os.path.join(game, "game.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "Demo", "engine": "paradox", "steam_appid": 7, "paradox": SEC,
                       "release": REL, "credits": "Нейрапераклад."}, f)
        os.environ["BELLOC_LOCAL"] = os.path.join(self.tmp, "local")
        os.makedirs(os.path.join(self.tmp, "local", "demo"))
        with open(os.path.join(self.tmp, "local", "demo", "local.json"), "w") as f:
            json.dump({"game_dir": g}, f)
        self.loc = config.load(game)
        with redirect_stdout(io.StringIO()):
            paradox.extract(self.loc)
            tables.sync(self.loc)
        rows = tables.load_all(self.loc)["menu"]
        rows[0]["bel"] = "Пачаць"
        tables.save(self.loc, "menu", rows)
        # пакет і каталог — лакальныя файлы замест GitHub
        p = release.release_payload(self.loc, paradox)
        self.pkg = os.path.join(self.tmp, "demo-1.0.zip")
        catalog.build_package(p, self.pkg)
        self.cat = os.path.join(self.tmp, "catalog.json")
        self.write_catalog(catalog.entry(self.loc, p, self.pkg, self.pkg))
        self.apps = {7: {"dir": g, "buildid": None, "name": "Demo"}}
        os.environ["LOCALAPPDATA"] = os.path.join(self.tmp, "appdata")

    def tearDown(self):
        os.environ.pop("BELLOC_LOCAL", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write_catalog(self, e):
        with open(self.cat, "w", encoding="utf-8") as f:
            json.dump({"schema": 1, "games": {"demo": e}}, f, ensure_ascii=False)

    def entry(self):
        with open(self.cat, encoding="utf-8") as f:
            return json.load(f)["games"]["demo"]

    def run_launcher(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = launcher.main([*argv, "--catalog", self.cat], self.apps)
        return code, out.getvalue()


class LauncherTest(Fixture):
    def test_package_is_stable(self):
        p = release.release_payload(self.loc, paradox)
        again = os.path.join(self.tmp, "again.zip")
        catalog.build_package(p, again)
        self.assertEqual(catalog.sha256(again), catalog.sha256(self.pkg))
        e = self.entry()
        self.assertNotIn("strings", e["probe"])
        self.assertEqual(e["stores"], {"steam": 7})

    def test_install_update_remove(self):
        code, out = self.run_launcher("list")
        self.assertIn("Demo: пераклад не ўсталяваны; можна паставіць 1.0", out)
        self.assertEqual(self.run_launcher("install", "demo", "--yes")[0], 0)
        self.assertEqual(state.read(self.gamedir)["version"], "1.0")
        self.assertEqual(state.read(self.gamedir)["by"], "launcher")
        _, out = self.run_launcher("list")
        self.assertIn("усталяваны — 1.0", out)
        self.assertNotIn("новая версія", out)

        e = self.entry()
        self.write_catalog({**e, "version": "1.1"})
        _, out = self.run_launcher("list")
        self.assertIn("ёсць новая версія 1.1", out)

        # Steam затёр нашы файлы, а метка засталася
        shutil.rmtree(os.path.join(self.gamedir, "game", "localization", "replace"))
        _, out = self.run_launcher("list")
        self.assertIn("зляцеў", out)

        self.run_launcher("install", "demo", "--yes")
        self.assertEqual(self.run_launcher("remove", "demo", "--yes")[0], 0)
        self.assertIsNone(state.read(self.gamedir))
        self.assertFalse(paradox.installed(self.gamedir, e["probe"]))

    def test_newer_launcher_needed(self):
        e = self.entry()
        self.write_catalog({**e, "payload_schema": payload.SCHEMA + 1})
        _, out = self.run_launcher("list")
        self.assertIn("патрэбна новая версія лаўнчара", out)

    def test_bad_package_refused(self):
        e = self.entry()
        self.write_catalog({**e, "package": {**e["package"], "sha256": "0" * 64}})
        with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            launcher.main(["install", "demo", "--yes", "--catalog", self.cat], self.apps)
        self.assertIsNone(state.read(self.gamedir))

    def test_installer_reminds_and_marks(self):
        p = release.release_payload(self.loc, paradox)
        path = os.path.join(self.tmp, "exe", "payload.json")
        os.makedirs(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload.dump(p), f, ensure_ascii=False)
        e = self.entry()
        self.write_catalog({**e, "version": "1.2", "changes": "выпраўленні"})
        out = io.StringIO()
        with redirect_stdout(out):
            installer.main(["--game", self.gamedir, "--yes", "--install"], path, self.cat)
        self.assertIn("Ёсць новая версія перакладу: 1.2", out.getvalue())
        self.assertEqual(state.read(self.gamedir)["by"], "installer")
        with redirect_stdout(io.StringIO()):
            installer.main(["--game", self.gamedir, "--yes", "--uninstall"], path, self.cat)
        self.assertIsNone(state.read(self.gamedir))

    def test_no_network(self):
        self.assertIsNone(catalog.fetch(os.path.join(self.tmp, "missing.json")))


if __name__ == "__main__":
    unittest.main()
