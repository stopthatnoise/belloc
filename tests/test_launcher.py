"""Каталог і лаўнчар на выдуманай гульні paradox: пакет перакладу, усталёўка з
каталога, метка belloc.json, «ёсць новая версія», «зляцеў», выдаленне, напамін у exe.

    python -X utf8 -m unittest discover -s tests
"""
import atexit
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
import games as launcher_games  # noqa: E402
import main as launcher  # noqa: E402
import run as installer  # noqa: E402

SEC = {"roots": ["game"], "langs": {"en": "english"}, "extract_langs": ["en"],
       "target": "russian", "replace_dir": "game/localization/replace/russian/bel"}
REL = {"title": "Беларускі пераклад Demo", "version": "1.0", "exe": "demo.exe", "file": "Demo_BE",
       "language_name": "Беларуская", "replaces": "Русский", "menu": "Налады",
       "contents": "{strings} радкоў.", "how": "Дадае папку."}

# ключ подпісу каталога — толькі для тэстаў; Fixture падстаўляе яго замест PUBLIC_KEY
KEYS = tempfile.mkdtemp()
atexit.register(shutil.rmtree, KEYS, True)
KEY = os.path.join(KEYS, "test-key.pem")
PUB = catalog.keygen(KEY)


def write_catalog_file(path: str, cat: dict, sign: bool = True):
    """catalog.json + подпіс тэставым ключом (лаўнчар правярае яго, як сапраўдны)."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cat, f, ensure_ascii=False)
    if sign:
        catalog.sign_file(path, KEY)


class VersionTest(unittest.TestCase):
    def test_newer(self):
        self.assertTrue(catalog.newer("1.10", "1.9"))
        self.assertTrue(catalog.newer("1.1", "1.0"))
        self.assertFalse(catalog.newer("1.0", "1.0"))
        self.assertTrue(catalog.newer("1.0", None))

    def test_show_date(self):
        self.assertEqual(catalog.show_date("2026-10-31"), "31.10.2026")
        self.assertEqual(catalog.show_date("2026-1-5"), "05.01.2026")
        self.assertEqual(catalog.show_date(None), "")


class Fixture(unittest.TestCase):
    """Выдуманая гульня paradox, яе пакет і лакальны каталог (без тэстаў — для LauncherTest і AppTest)."""

    def setUp(self):
        self.real_key, catalog.PUBLIC_KEY = catalog.PUBLIC_KEY, PUB
        self.tmp = tempfile.mkdtemp()
        g = os.path.join(self.tmp, "game")
        yml = os.path.join(g, "game", "localization", "english", "menu_l_english.yml")
        os.makedirs(os.path.dirname(yml))
        with open(yml, "w", encoding="utf-8-sig", newline="\n") as f:
            f.write('l_english:\n START:0 "Start"\n')
        self.gamedir = g
        os.makedirs(os.path.join(g, "binaries"))
        open(os.path.join(g, "binaries", "demo.exe"), "w").close()     # па exe гульню пазнае выбар папкі
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
        catalog.PUBLIC_KEY = self.real_key
        os.environ.pop("BELLOC_LOCAL", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write_catalog(self, e, sign: bool = True):
        write_catalog_file(self.cat, {"schema": 1, "games": {"demo": e}}, sign)

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

    def test_others_and_folders(self):
        sys.path.insert(0, os.path.join(HERE, "..", "launcher"))
        import games
        with open(self.cat, encoding="utf-8") as f:
            cat = json.load(f)
        self.assertEqual(games.scan(cat, {}), [])
        self.assertEqual([o["id"] for o in games.others(cat, [])], ["demo"])
        self.assertEqual(games.match_folder(cat, self.gamedir), ["demo"])
        self.assertEqual(games.match_folder(cat, os.path.join(self.gamedir, "game")), [])   # не тая папка
        games.remember("demo", self.gamedir)
        self.assertEqual([r["dir"] for r in games.scan(cat, {})], [self.gamedir])
        self.assertEqual(games.others(cat, games.scan(cat, {})), [])
        self.assertEqual(games.store_url(7), "https://store.steampowered.com/app/7/")

    def test_no_network(self):
        self.assertIsNone(catalog.fetch(os.path.join(self.tmp, "missing.json")))

    def test_signature(self):
        e = self.entry()
        self.assertIn("demo", catalog.fetch(self.cat)["games"])
        self.write_catalog({**e, "version": "9.9"}, sign=False)        # стары подпіс, новы файл
        self.assertIsNone(catalog.fetch(self.cat))
        os.remove(self.cat + catalog.SIG)                                # подпісу няма
        self.assertIsNone(catalog.fetch(self.cat))
        self.write_catalog(e)
        catalog.PUBLIC_KEY = self.real_key                               # падпісаны не нашым ключом
        self.assertIsNone(catalog.fetch(self.cat))
        catalog.PUBLIC_KEY = PUB
        with open(self.cat + catalog.SIG, "wb") as f:
            f.write(b"not base64!")
        self.assertIsNone(catalog.fetch(self.cat))

    def write_with_launcher(self, launcher):
        write_catalog_file(self.cat, {"schema": 1, "launcher": launcher, "games": {"demo": self.entry()}})

    def test_launcher_field(self):
        page = f"{catalog.RELEASES}/tag/launcher-v9.9"
        ok = {"version": "9.9", "page": page, "changes": "новае",
              "package": {"url": f"{catalog.RELEASES}/download/launcher-v9.9/belloc-launcher_9.9.zip",
                          "sha256": "a" * 64, "size": 10}}
        self.assertEqual(catalog.launcher_info(ok)["package"]["size"], 10)
        for bad in (None, "0.3", {"version": "9.9"}, {**ok, "page": "http://evil.example/x"},
                    {**ok, "page": "file:///C:/x.exe"}, {**ok, "version": "9.9; rm"}):
            self.assertIsNone(catalog.launcher_info(bad), bad)
        bad_pkg = catalog.launcher_info({**ok, "package": {**ok["package"], "url": "https://evil.example/x.zip"}})
        self.assertNotIn("package", bad_pkg)                              # кнопка застаецца, пакета няма

        self.write_with_launcher(ok)
        cat = catalog.fetch(self.cat)
        self.assertEqual(catalog.launcher_update(cat, "0.3")["version"], "9.9")
        self.assertIsNone(catalog.launcher_update(cat, "9.9"))
        self.assertIsNone(catalog.launcher_update(cat, "10.0"))
        _, out = self.run_launcher("list")
        self.assertIn(f"Ёсць новы лаўнчар 9.9 (у вас {launcher_games.VERSION}): {page}", out)

        self.write_with_launcher({**ok, "page": "http://evil.example/x"})   # дзіўная спасылка — моўчкі
        self.assertIsNone(catalog.fetch(self.cat)["launcher"])
        _, out = self.run_launcher("list")
        self.assertNotIn("новы лаўнчар", out)
        self.write_with_launcher(None)                                       # каталог без лаўнчара
        _, out = self.run_launcher("list")
        self.assertNotIn("новы лаўнчар", out)

    def test_publish_launcher(self):
        z = os.path.join(self.tmp, "belloc-launcher_9.9.zip")
        with open(z, "wb") as f:
            f.write(b"zip")
        os.environ["BELLOC_CATALOG_KEY"] = KEY
        try:
            with redirect_stdout(io.StringIO()):
                info = catalog.publish_launcher(z, "выпраўленні", self.cat)
        finally:
            os.environ.pop("BELLOC_CATALOG_KEY")
        self.assertEqual(info["page"], f"{catalog.RELEASES}/tag/launcher-v9.9")
        got = catalog.fetch(self.cat)                                        # падпісаны і прачытаны
        self.assertEqual(got["launcher"]["package"]["sha256"], catalog.sha256(z))
        self.assertIn("demo", got["games"])                                  # гульні не крануты
        bad = os.path.join(self.tmp, "launcher.zip")
        open(bad, "wb").close()
        with self.assertRaises(SystemExit):
            catalog.publish_launcher(bad, "", self.cat)


if __name__ == "__main__":
    unittest.main()
