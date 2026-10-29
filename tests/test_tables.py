"""Два слаі перакладу (core/belloc/tables.py) на выдуманых радках.

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

EN = {"menu": {"start": "Start the engine", "quit": "Quit"},
      "dlg/intro": {"1": "Line with\r\nCRLF inside", "2": "", "3": "Hello there"}}
RU = {"menu": {"start": "Завести мотор", "quit": "Выйти"},
      "dlg/intro": {"1": "Строка с\r\nCRLF", "2": "", "3": "Привет"}}
CTX = {"dlg/intro": {"1": "HERO", "3": "GUIDE"}}


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False)


class TablesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.game = os.path.join(self.tmp, "games", "demo")
        write_json(os.path.join(self.game, "game.json"),
                   {"name": "Demo", "engine": "test", "source_lang": "en", "hint_lang": "ru"})
        os.environ["BELLOC_LOCAL"] = os.path.join(self.tmp, "local")
        self.loc = config.load(self.game)
        write_json(os.path.join(self.loc.source, "en.json"), EN)
        write_json(os.path.join(self.loc.source, "ru.json"), RU)
        write_json(os.path.join(self.loc.source, "context.json"), CTX)
        self.sync()

    def tearDown(self):
        os.environ.pop("BELLOC_LOCAL", None)
        shutil.rmtree(self.tmp)

    def sync(self):
        with redirect_stdout(io.StringIO()) as out:
            tables.sync(self.loc)
        return out.getvalue()

    def repo_bytes(self):
        data = b""
        for root, _, files in os.walk(self.game):
            for f in files:
                data += open(os.path.join(root, f), "rb").read()
        return data.decode("utf-8")

    def translate(self, table, key, bel, note=""):
        rows = tables.load_all(self.loc)[table]
        for r in rows:
            if r["key"] == key:
                r["bel"], r["note"] = bel, note
        tables.save(self.loc, table, rows)

    def test_no_game_text_in_repo(self):
        self.translate("dlg/intro", "1", "Радок з\r\nCRLF", tables.with_ctx("HERO", "?: сумненне"))
        text = self.repo_bytes()
        for strings in (*EN.values(), *RU.values(), *CTX.values()):
            for s in strings.values():
                if s:
                    self.assertNotIn(s, text)
        self.assertNotIn("ctx:", text)

    def test_repo_columns(self):
        rows = tables.read_csv(tables.table_path(self.loc, "dlg/intro"))
        self.assertEqual(list(rows[0]), tables.REPO_COLS)
        self.assertEqual(rows[1]["src_hash"], "")             # пусты арыгінал
        self.assertEqual(rows[0]["src_hash"], tables.src_hash(EN["dlg/intro"]["1"]))

    def test_join(self):
        self.translate("menu", "start", "Завесці матор")
        r = {x["key"]: x for x in tables.load_all(self.loc)["menu"]}["start"]
        self.assertEqual((r["en"], r["ru"], r["bel"]), ("Start the engine", "Завести мотор", "Завесці матор"))
        c = {x["key"]: x for x in tables.load_all(self.loc)["dlg/intro"]}
        self.assertEqual(c["3"]["ctx"], "GUIDE")

    def test_crlf_kept(self):
        self.translate("dlg/intro", "1", "Радок з\r\nCRLF")
        raw = open(tables.table_path(self.loc, "dlg/intro"), "rb").read()
        self.assertIn("Радок з\r\nCRLF".encode("utf-8"), raw)
        self.assertNotIn(b"\r\n" + b"1,", raw)                # канцы радкоў CSV — \n

    def test_stale(self):
        self.translate("menu", "start", "Завесці матор", "?: праверыць")
        EN2 = json.loads(json.dumps(EN))
        EN2["menu"]["start"] = "Start the car"
        del EN2["menu"]["quit"]
        write_json(os.path.join(self.loc.source, "en.json"), EN2)
        out = self.sync()
        self.assertIn("састарэла 1, выдалена 1", out)
        rows = tables.read_csv(tables.table_path(self.loc, "menu"))
        self.assertEqual([r["key"] for r in rows], ["start"])
        self.assertEqual(rows[0]["bel"], "")
        self.assertEqual(rows[0]["note"], "stale: Завесці матор | ?: праверыць")

    def test_without_source(self):
        self.translate("menu", "quit", "Выйсці")
        shutil.rmtree(self.loc.source)
        with redirect_stdout(io.StringIO()) as out:
            tables.stats(self.loc)
        self.assertIn("1/4", out.getvalue().split("УСЯГО")[1])
        self.assertEqual(tables.translation_by_key(self.loc), {"dlg/intro": {}, "menu": {"quit": "Выйсці"}})
        rows = tables.load_all(self.loc)["menu"]
        tables.save(self.loc, "menu", rows)                  # без source хэш не губляецца
        self.assertTrue(all(r["src_hash"] for r in tables.read_csv(tables.table_path(self.loc, "menu"))))
        with self.assertRaises(SystemExit):
            tables.sync(self.loc)

    def test_pairs(self):
        self.translate("menu", "quit", "Выйсці")
        out = os.path.join(self.loc.build, "pairs.json")
        with redirect_stdout(io.StringIO()):
            tables.pairs(self.loc, out)
        self.assertEqual(json.load(open(out, encoding="utf-8")), {"strings": {"Quit": "Выйсці"}})
        self.assertTrue(out.startswith(self.loc.local))       # тэкст гульні — толькі лакальна


if __name__ == "__main__":
    unittest.main()
