"""Рэліз без PyInstaller: payload з апісаннем рэліза, ЧЫТАЙ.txt і ўсталёўшчык
installer/run.py на выдуманай гульні paradox (усталёўка, паўтор, выдаленне).

    python -X utf8 -m unittest discover -s tests
"""
import io
import json
import os
import zipfile
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "core"))
sys.path.insert(0, os.path.join(HERE, "..", "installer"))

from belloc import config, payload, release, tables  # noqa: E402
from belloc.engines import paradox  # noqa: E402
import run as installer  # noqa: E402

SEC = {"roots": ["game"], "langs": {"en": "english", "ru": "russian"}, "extract_langs": ["en"],
       "target": "russian", "replace_dir": "game/localization/replace/russian/bel"}
REL = {"title": "Беларускі пераклад Demo", "version": "1.0", "exe": "demo.exe", "file": "Demo_BE",
       "language_name": "Беларуская", "replaces": "Русский", "menu": "Налады → Мова",
       "contents": "Перакладзена ўсё ({strings} радкоў).", "how": "Дадае папку replace/bel."}


def read(path):
    with open(path, "rb") as f:
        return f.read()


class ReleaseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        g = os.path.join(self.tmp, "game")
        yml = os.path.join(g, "game", "localization", "english", "menu_l_english.yml")
        os.makedirs(os.path.dirname(yml))
        with open(yml, "w", encoding="utf-8-sig", newline="\n") as f:
            f.write('l_english:\n START:0 "Start"\n QUIT:0 "Quit and close the game"\n')
        self.gamedir = g
        game = os.path.join(self.tmp, "games", "demo")
        os.makedirs(game)
        with open(os.path.join(game, "game.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "Demo", "engine": "paradox", "steam_appid": 1, "paradox": SEC,
                       "release": REL, "credits": "Нейрапераклад. Кіраўнік праекта: …"}, f)
        os.environ["BELLOC_LOCAL"] = os.path.join(self.tmp, "local")
        os.makedirs(os.path.join(self.tmp, "local", "demo"))
        with open(os.path.join(self.tmp, "local", "demo", "local.json"), "w") as f:
            json.dump({"game_dir": g}, f)
        self.loc = config.load(game)
        with redirect_stdout(io.StringIO()):
            paradox.extract(self.loc)
            tables.sync(self.loc)
        rows = tables.load_all(self.loc)["menu"]
        for r in rows:
            r["bel"] = {"START": "Пачаць"}.get(r["key"], "")
        tables.save(self.loc, "menu", rows)

    def tearDown(self):
        os.environ.pop("BELLOC_LOCAL", None)
        shutil.rmtree(self.tmp)

    def test_payload_and_readme(self):
        p = release.release_payload(self.loc, paradox)
        self.assertEqual(p["release"]["credits"], "Нейрапераклад. Кіраўнік праекта: …")
        self.assertEqual(p["strings"], {"menu": {"START": "Пачаць"}})
        text = release.readme(self.loc, p, "Demo_BE_1.0.exe")
        self.assertIn("Перакладзена ўсё (1 радкоў).", text)
        self.assertIn("Запусціце Demo_BE_1.0.exe", text)
        self.assertNotIn("{", text)

    def test_installer(self):
        p = release.release_payload(self.loc, paradox)
        path = os.path.join(self.tmp, "payload.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload.dump(p), f, ensure_ascii=False)
        dest = os.path.join(self.gamedir, SEC["replace_dir"])
        argv = ["--game", self.gamedir, "--yes"]
        with redirect_stdout(io.StringIO()):
            self.assertEqual(installer.main(argv + ["--install"], path), 0)
            first = read(os.path.join(dest, "menu_l_russian.yml"))
            self.assertEqual(installer.main(argv + ["--install"], path), 0)     # паўтор — той жа вынік
        self.assertEqual(read(os.path.join(dest, "menu_l_russian.yml")), first)
        self.assertIn("Пачаць".encode(), first)
        self.assertTrue(paradox.installed(self.gamedir, p))
        with redirect_stdout(io.StringIO()):
            self.assertEqual(installer.main(argv + ["--uninstall"], path), 0)
        self.assertFalse(paradox.installed(self.gamedir, p))

    def test_assets_next_to_payload(self):
        path = os.path.join(self.tmp, "exe", "payload.json")
        os.makedirs(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"assets": ["fonts/a/A.ttf"]}, f)
        p = payload.load(path)
        self.assertEqual(payload.asset(p, "fonts/a/A.ttf:Bold"),
                         os.path.join(self.tmp, "exe", "assets", "fonts/a/A.ttf:Bold"))

    def test_files_archive(self):
        p = release.release_payload(self.loc, paradox)
        out = os.path.join(self.tmp, "rel")
        os.makedirs(out)
        with zipfile.ZipFile(release.build_files(self.loc, paradox, p, "Demo_BE_1.0", out)) as z:
            names = sorted(z.namelist())
            readme = z.read("ЧЫТАЙ.txt").decode("utf-8-sig")
        self.assertEqual(names, ["game/localization/replace/russian/bel/menu_l_russian.yml", "ЧЫТАЙ.txt"])
        self.assertIn("Выдаліце папку game/localization/replace/russian/bel", readme)
        self.assertIn("Перацягніце папку game", readme)

    def test_files_archive_refuses_game_text(self):
        rows = tables.load_all(self.loc)["menu"]
        for r in rows:
            r["bel"] = {"START": "Пачаць (Quit and close the game)"}.get(r["key"], "")
        tables.save(self.loc, "menu", rows)
        p = release.release_payload(self.loc, paradox)
        with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            release.build_files(self.loc, paradox, p, "Demo_BE_1.0", self.tmp)


if __name__ == "__main__":
    unittest.main()
