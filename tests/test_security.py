"""Шкодны каталог, пакет або game.json не пішуць і не выдаляюць нічога па-за
папкай гульні, а файлы машыны мейнтейнера не трапляюць у пакет.

    python -X utf8 -m unittest discover -s tests
"""
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "core"))
sys.path.insert(0, HERE)

from belloc import catalog, cli, config, payload, tables  # noqa: E402
from belloc.engines import csv_folder, paradox, unreal_locres  # noqa: E402
from belloc.install import paths  # noqa: E402
from belloc.install.process import tasklist  # noqa: E402
from test_launcher import Fixture  # noqa: E402

BAD = ["../x", "a/../../x", "/x", "\\x", "C:/x", "C:x", "\\\\srv\\share\\x", "a:b"]


class InsideTest(unittest.TestCase):
    def test_inside(self):
        root = tempfile.gettempdir()
        self.assertEqual(paths.inside(root, "a/b"), os.path.join(root, "a/b"))
        paths.inside(root, "a/../b")
        for p in BAD:
            with self.subTest(p), self.assertRaises(SystemExit):
                paths.inside(root, p)
        with self.assertRaises(SystemExit):
            paths.inside(root, "a", "..", strict=True)

    def test_name_and_id(self):
        self.assertEqual(paths.name("menu.yml"), "menu.yml")
        for p in BAD + ["a/b", "..", ""]:
            with self.subTest(p), self.assertRaises(SystemExit):
                paths.name(p)
        paths.game_id("the-wolf-among-us")
        for g in ["..", "../x", "A", "", "a/b", "a..b", 7]:
            with self.subTest(g), self.assertRaises(SystemExit):
                paths.game_id(g)

    def test_tasklist_full_path(self):
        self.assertTrue(os.path.isabs(tasklist()))


class RegexTest(unittest.TestCase):
    """Рэгуляркі з game.json і batches.json: паўтор у паўторы (ReDoS) — памылка."""

    def test_regex(self):
        for p in (r"(?s)\A(?:\[\]|.{1000,})\Z", r"\[[^\]]*\]", r"^Fables[0-9]+/(?!ui_)",
                  r"<[^>]*>|\{[^}]*\}", r"(?:ab)+", r"(?>a+)+"):
            tables.regex(p)
        for p in (r"(a+)+$", r"(.*)*", r"(?:\w+\s?)+$", r"((a|b)+c?)*", r"(?=(a+)+)b", "(", 7):
            with self.subTest(p), self.assertRaises(SystemExit):
                tables.regex(p)
        with self.assertRaises(SystemExit):
            tables.from_original(r"(\[\]+)+")

    def test_lint_args(self):
        self.assertEqual(cli.game_lint_args(["--tag-re", "<[^>]*>", "--marks", "|^", "--paradox"]),
                         ["--tag-re", "<[^>]*>", "--marks", "|^", "--paradox"])
        for bad in (["--report", "C:/x.bat"], ["--dict=x"], ["--rep", "x"], ["--marks", "--report", "x"],
                    ["--tag-re", "(a+)+"]):
            with self.subTest(bad), self.assertRaises(SystemExit):
                cli.game_lint_args(bad)


class EngineTest(unittest.TestCase):
    """Payload з шляхамі па-за гульнёй: рухавік спыняецца да любога запісу або выдалення."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.game = os.path.join(self.tmp, "game")
        self.victim = os.path.join(self.tmp, "victim")
        os.makedirs(self.game)
        os.makedirs(self.victim)
        open(os.path.join(self.victim, "keep.txt"), "w").close()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def assert_victim(self):
        self.assertTrue(os.path.exists(os.path.join(self.victim, "keep.txt")))

    def test_paradox(self):
        log = io.StringIO()
        for rd in ("../victim", self.victim, ".", "game/.."):
            p = {"paradox": {"target": "russian", "replace_dir": rd, "roots": ["game"]},
                 "strings": {"menu": {"A": "Б"}}}
            with self.subTest(rd):
                with self.assertRaises(SystemExit):
                    paradox.apply(self.game, p, log=log.write)
                with self.assertRaises(SystemExit):
                    paradox.restore(self.game, p, log=log.write)
                self.assert_victim()
        p = {"paradox": {"target": "russian", "replace_dir": "game/bel", "roots": ["game"]},
             "strings": {"../../../victim/x": {"A": "Б"}}}
        with self.assertRaises(SystemExit):
            paradox.apply(self.game, p, log=log.write)
        self.assertEqual(os.listdir(self.victim), ["keep.txt"])
        p["paradox"]["target"] = "../x"
        with self.assertRaises(SystemExit):
            paradox.apply(self.game, p, log=log.write)

    def test_csv_folder(self):
        for target in ("../../victim", self.victim):
            p = {"csv_folder": {"dir": "data", "official": "Official", "template": "Template",
                                "target": target}}
            with self.subTest(target), self.assertRaises(SystemExit):
                csv_folder.restore(self.game, p, log=lambda s: None)
            self.assert_victim()

    def test_unreal_mod(self):
        for mod in ("../victim/keep.txt", os.path.join(self.victim, "keep.txt"), "Paks/evil.bat",
                    "../../AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup/x.pak"):
            p = {"unreal": {"pak": "Paks/a.pak", "mod": mod, "target": "ru"}}
            with self.subTest(mod), self.assertRaises(SystemExit):
                unreal_locres.restore(self.game, p, log=lambda s: None)
            self.assert_victim()


class PackageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def zip(self, members: dict) -> str:
        path = os.path.join(self.tmp, "pkg.zip")
        with zipfile.ZipFile(path, "w") as z:
            for n, data in members.items():
                z.writestr(n, data)
        return path

    def test_open_package(self):
        good = {"payload.json": "{}", "assets/fonts/a.ttf": "x"}
        dest = os.path.join(self.tmp, "unpack")
        catalog.open_package(self.zip(good), dest)
        self.assertTrue(os.path.exists(os.path.join(dest, "assets", "fonts", "a.ttf")))
        for extra in ("../evil.txt", "assets/../../evil.txt", "evil.dll", "assets/C:x"):
            with self.subTest(extra), self.assertRaises(SystemExit):
                catalog.open_package(self.zip({**good, extra: "x"}), dest)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "evil.txt")))

    def test_zip_bomb(self):
        old = catalog.MAX_PACKAGE
        catalog.MAX_PACKAGE = 1000
        try:
            with self.assertRaises(SystemExit):
                catalog.open_package(self.zip({"payload.json": "{}", "assets/big": "0" * 5000}),
                                     os.path.join(self.tmp, "u"))
        finally:
            catalog.MAX_PACKAGE = old

    def test_unpack_dir(self):
        for gid in ("..", "../..", "x/../.."):
            with self.subTest(gid), self.assertRaises(SystemExit):
                catalog.unpack_dir(gid)

    def test_download_refuses(self):
        sha = "0" * 64
        for url, s in [("http://example.com/a.zip", sha), ("file:///C:/Windows/win.ini", sha),
                       ("https://example.com/C:evil.zip", sha), ("https://example.com/a.exe", sha),
                       ("https://example.com/a.zip", "x")]:
            with self.subTest(url), self.assertRaises(SystemExit):
                catalog.download({"package": {"url": url, "sha256": s}}, self.tmp)

    def test_get_https_only(self):
        for url in ("http://example.com/c.json", "ftp://example.com/c.json", "file:///etc/passwd"):
            with self.subTest(url), self.assertRaises(ValueError):
                catalog._get(url, 1, 100)

    def test_fetch_drops_bad_ids(self):
        path = os.path.join(self.tmp, "catalog.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"games": {"ok-game": {"name": "A"}, "../..": {"name": "B"}, "x": "не слоўнік"}}, f)
        self.assertEqual(list(catalog.fetch(path)["games"]), ["ok-game"])

    def test_payload_asset(self):
        p = {"assets_root": os.path.join(self.tmp, "assets"), "from_package": True}
        self.assertTrue(payload.asset(p, "fonts/a.ttf").endswith("a.ttf"))
        for rel in ("../../secret", os.path.join(self.tmp, "secret")):
            with self.subTest(rel), self.assertRaises(SystemExit):
                payload.asset(p, rel)
        # local.json мейнтейнера: абсалютны шлях — як ёсць
        self.assertEqual(payload.asset({"assets_root": self.tmp}, "C:/Windows/Fonts/a.ttf"),
                         "C:/Windows/Fonts/a.ttf")
        with self.assertRaises(SystemExit):
            payload.asset({"assets_root": self.tmp}, "../../.ssh/id_ed25519")


class GameJsonTest(Fixture):
    def test_loc_path(self):
        self.assertTrue(self.loc.path("glossary.json").endswith("glossary.json"))
        with self.assertRaises(SystemExit):
            self.loc.path("../../../.ssh/id_ed25519")
        self.loc.raw["glossary"] = "../../secret.json"
        with self.assertRaises(SystemExit):
            self.loc.glossary

    def test_release_names(self):
        from belloc import release
        loc = config.load(self.loc.dir)
        for k, v in (("file", "../../x"), ("version", "1.0/../../x"), ("exe", "C:/x.exe")):
            loc.raw["release"] = {**self.loc.raw["release"], k: v}
            with self.subTest(k), redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
                release.release_payload(loc, paradox)

    def test_package_for_other_game_refused(self):
        sys.path.insert(0, os.path.join(HERE, "..", "launcher"))
        import games
        with open(self.cat, encoding="utf-8") as f:
            cat = json.load(f)
        cat["games"] = {"other": cat["games"]["demo"]}     # чужы пакет пад іншым id
        rows = games.scan(cat, self.apps)
        with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            games.install(rows[0], log=lambda s: None)


if __name__ == "__main__":
    unittest.main()
