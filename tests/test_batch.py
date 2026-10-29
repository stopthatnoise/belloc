"""Пачкі (core/belloc/batch.py) на выдуманых радках: export → праўка агента → apply.

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

from belloc import batch, config, tables  # noqa: E402

EN = {"scene": {"1": "Open the door", "2": "Who is there?", "3": "Open the door", "4": "Go away"}}
CTX = {"scene": {"1": "HERO", "2": "GUARD", "3": "HERO", "4": "GUARD"}}
BATCHES = {"_repeats": [{"tables": "^scene$", "by": ["en"], "note": "^ctx: (\\S+)"}],
           "a": {"wave": 1, "rows": [{"table": "scene", "slice": [0, 2]}]},
           "b": {"wave": 1, "rows": [{"table": "scene"}]}}


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False)


class BatchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        game = os.path.join(self.tmp, "games", "demo")
        write_json(os.path.join(game, "game.json"),
                   {"name": "Demo", "engine": "test", "source_lang": "en", "hint_lang": None})
        write_json(os.path.join(game, "batches.json"), BATCHES)
        os.environ["BELLOC_LOCAL"] = os.path.join(self.tmp, "local")
        self.loc = config.load(game)
        write_json(os.path.join(self.loc.source, "en.json"), EN)
        write_json(os.path.join(self.loc.source, "context.json"), CTX)
        with redirect_stdout(io.StringIO()):
            tables.sync(self.loc)

    def tearDown(self):
        os.environ.pop("BELLOC_LOCAL", None)
        shutil.rmtree(self.tmp)

    def quiet(self, fn, *a):
        with redirect_stdout(io.StringIO()) as out:
            fn(*a)
        return out.getvalue()

    def test_export_apply(self):
        self.quiet(batch.export, self.loc, ["a", "b"])
        a = tables.read_csv(batch.work_path(self.loc, "a"))
        b = tables.read_csv(batch.work_path(self.loc, "b"))
        self.assertEqual([r["key"] for r in a], ["1", "2"])
        self.assertEqual([r["key"] for r in b], ["4"])        # 3 — паўтор 1 (той жа en і гаворца)
        self.assertEqual(a[0]["note"], "ctx: HERO")            # працоўны файл — з ctx
        self.assertTrue(batch.work_path(self.loc, "a").startswith(self.loc.local))

        a[0]["bel"], a[0]["note"] = "Адчыні дзверы", "ctx: HERO | ?: ты ці вы"
        a[1]["bel"] = "Хто там?"
        tables.write_csv(batch.work_path(self.loc, "a"), a, batch.fields(self.loc))
        out = self.quiet(batch.apply, self.loc, ["a"])
        self.assertIn("перанесена 2, на паўторы 1", out)

        repo = {r["key"]: r for r in tables.read_csv(tables.table_path(self.loc, "scene"))}
        self.assertEqual(repo["1"]["note"], "?: ты ці вы")    # ctx у рэпа не трапляе
        self.assertEqual(repo["3"]["bel"], "Адчыні дзверы")
        self.assertEqual(repo["4"]["bel"], "")
        with open(tables.table_path(self.loc, "scene"), encoding="utf-8") as f:
            raw = f.read()
        self.assertNotIn("Open the door", raw)
        self.assertNotIn("ctx:", raw)

    def test_changed_source_skipped(self):
        self.quiet(batch.export, self.loc, ["a"])
        a = tables.read_csv(batch.work_path(self.loc, "a"))
        a[0]["bel"] = "Адчыні дзверы"
        tables.write_csv(batch.work_path(self.loc, "a"), a, batch.fields(self.loc))
        EN2 = {"scene": {**EN["scene"], "1": "Open the gate"}}
        write_json(os.path.join(self.loc.source, "en.json"), EN2)
        self.quiet(tables.sync, self.loc)
        out = self.quiet(batch.apply, self.loc, ["a"])
        self.assertIn("арыгінал змяніўся", out)

    def test_needs_source(self):
        shutil.rmtree(self.loc.source)
        with self.assertRaises(SystemExit):
            batch.status(self.loc)


if __name__ == "__main__":
    unittest.main()
