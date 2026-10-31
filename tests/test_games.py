"""Змесціва games/: тое, што CI правярае ў кожным PR без файлаў і тэкстаў гульняў.

game.json чытаецца, payload збіраецца (з ім — праверкі шляхоў і рэгулярак), CSV —
толькі наш слой (key, src_hash, bel, note; без ctx: з гульні), гласарый без памылак,
у файлах няма лакальных шляхоў машыны.

    python -X utf8 -m unittest discover -s tests
"""
import csv
import glob
import io
import json
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "core"))

from belloc import config, engines, glossary, payload, tables  # noqa: E402

GAMES = sorted(os.path.basename(os.path.dirname(p))
               for p in glob.glob(os.path.join(ROOT, "games", "*", "game.json")))
HASH = re.compile(r"[0-9a-f]{16}")
LOCAL_PATH = re.compile(r"\b[A-Za-z]:[\\/]+(?:Users|SteamLibrary|GamePass|Program Files|bel-localization|belloc)"
                        r"|/home/[a-z]|/Users/[A-Za-z]")
RELEASE = ("title", "version", "exe", "file", "language_name", "menu", "contents", "how")


class GamesTest(unittest.TestCase):
    """Па гульні на тэст — subTest, каб бачыць усе памылкі адразу."""

    @classmethod
    def setUpClass(cls):
        # без local/ гэтай машыны: CI бачыць толькі рэпазіторый
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ["BELLOC_LOCAL"] = cls.tmp.name

    @classmethod
    def tearDownClass(cls):
        os.environ.pop("BELLOC_LOCAL", None)
        cls.tmp.cleanup()

    def test_games_found(self):
        self.assertGreaterEqual(len(GAMES), 1)

    def test_config_and_payload(self):
        for gid in GAMES:
            with self.subTest(gid):
                loc = config.load(os.path.join(ROOT, "games", gid))
                self.assertEqual(loc.id, gid)
                engine = engines.get(loc.engine)
                p = payload.build_payload(loc, engine)
                self.assertTrue(p["strings"], "пусты пераклад")
                for rel in p.get("assets", []):
                    self.assertTrue(os.path.exists(payload.asset(p, rel)), rel)
                rel = loc.raw.get("release")
                if rel:
                    self.assertEqual([k for k in RELEASE if not rel.get(k)], [])

    def test_translation_csv(self):
        for gid in GAMES:
            with self.subTest(gid):
                base = os.path.join(ROOT, "games", gid, "translation")
                paths = glob.glob(os.path.join(base, "**", "*.csv"), recursive=True)
                self.assertTrue(paths)
                for p in paths:
                    with open(p, encoding="utf-8", newline="") as f:
                        rows = list(csv.reader(f))
                    rel = os.path.relpath(p, base)
                    self.assertEqual(rows[0], tables.REPO_COLS, rel)
                    for r in rows[1:]:
                        self.assertEqual(len(r), 4, f"{rel}: {r[:1]}")
                        key, h, bel, note = r
                        self.assertTrue(key, rel)
                        self.assertTrue(not h or HASH.fullmatch(h), f"{rel} {key}: src_hash")
                        self.assertFalse(any(x.startswith("ctx: ") for x in note.split(" | ")),
                                         f"{rel} {key}: ctx: з гульні ў note")

    def test_glossary(self):
        for gid in GAMES:
            with self.subTest(gid):
                path = os.path.join(ROOT, "games", gid, "glossary.json")
                if os.path.exists(path):
                    self.assertEqual(glossary.validate(glossary.load(path)), [])

    def test_no_local_paths(self):
        for gid in GAMES:
            with self.subTest(gid):
                for p in glob.glob(os.path.join(ROOT, "games", gid, "**", "*"), recursive=True):
                    if os.path.isdir(p) or p.endswith((".ttf", ".otf", ".png", ".ico", ".csv")):
                        continue
                    with open(p, encoding="utf-8", errors="ignore") as f:
                        m = LOCAL_PATH.search(f.read())
                    self.assertIsNone(m, f"{os.path.relpath(p, ROOT)}: {m and m.group()}")


if __name__ == "__main__":
    unittest.main()
