"""Слоўнік назваў з Вікіпедыі (core/belloc/wiki.py) — без сеткі, на падробленым API.

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

from belloc import wiki  # noqa: E402

# выдуманыя артыкулы: «Redshirts» перанакіроўвае на «Red Shirts», «Mercury» — неадназначнасць
PAGES = {
    "Red Shirts": {"desc": "Volunteers of a made-up army", "be": "Чырвонакашульнікі", "ru": "Краснорубашечники"},
    "Lake Nowhere": {"desc": "Made-up lake", "ru": "Озеро Нигде"},
    "Mercury": {"disambig": True},
}
REDIRECTS = {"Redshirts": "Red Shirts"}


def fake_api(calls):
    def api(src, params):
        calls.append(params)
        if params.get("list") == "search":
            return {"query": {"search": [{"title": "Lake Nowhere"}]}}
        q = {"redirects": [], "pages": []}
        for t in params["titles"].split("|"):
            r = REDIRECTS.get(t, t)
            if r != t:
                q["redirects"].append({"from": t, "to": r})
            p = PAGES.get(r)
            if p is None:
                q["pages"].append({"title": r, "missing": True})
                continue
            page = {"title": r, "description": p.get("desc", "")}
            if p.get("disambig"):
                page["pageprops"] = {"disambiguation": ""}
            if params["lllang"] in p:
                page["langlinks"] = [{"lang": params["lllang"], "title": p[params["lllang"]]}]
            q["pages"].append(page)
        return {"query": q}
    return api


class WikiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "dicts", "wikipedia.json")
        self.calls = []
        self.api = fake_api(self.calls)
        wiki.PAUSE = 0

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_(self, *terms, **kw):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = wiki.run(list(terms), path=self.path, api=self.api, **kw)
        return rc, buf.getvalue()

    def test_fetch_and_cache(self):
        rc, out = self.run_("Redshirts", "Lake Nowhere")
        self.assertEqual(rc, 0)
        self.assertIn("Red Shirts → Чырвонакашульнікі", out)
        self.assertIn("Lake Nowhere → (беларускага артыкула няма)", out)
        data = wiki.load(self.path)
        self.assertEqual(data["entries"]["en:Red Shirts"]["be"], "Чырвонакашульнікі")
        self.assertEqual(data["entries"]["en:Red Shirts"]["desc"], "Volunteers of a made-up army")
        self.assertIsNone(data["entries"]["en:Lake Nowhere"]["be"])
        self.assertEqual(data["aliases"], {"en:redshirts": "en:Red Shirts"})   # перанакіраванне запомнена
        self.assertTrue(data["_about"])

        n = len(self.calls)
        rc, out = self.run_("redshirts", "RED SHIRTS")               # са слоўніка, без сеткі
        self.assertEqual(len(self.calls), n)
        self.assertEqual(out.count("[слоўнік"), 2)

    def test_note_alias_reverse(self):
        self.run_("Red Shirts")
        self.run_("Red Shirts", note="у нас — інакш", aliases=["Camicie rosse"])
        rc, out = self.run_("camicie rosse", offline=True)
        self.assertIn("заўвага: у нас — інакш", out)
        rc, out = self.run_("Краснорубашеч", reverse=True)
        self.assertIn("Red Shirts", out)
        self.run_("Red Shirts", refresh=True)                       # заўвага не губляецца
        self.assertEqual(wiki.load(self.path)["entries"]["en:Red Shirts"]["note"], "у нас — інакш")

    def test_missing_and_disambig(self):
        rc, out = self.run_("Lake Nowher", "Mercury")
        self.assertEqual(rc, 1)
        self.assertIn("артыкула ў en.wikipedia няма; блізкія: Lake Nowhere", out)
        self.assertIn("старонка неадназначнасці", out)
        self.assertFalse(os.path.exists(self.path))                  # нічога не запісана

    def test_offline(self):
        rc, out = self.run_("Red Shirts", offline=True)
        self.assertIn("у слоўніку няма (--offline)", out)
        self.assertEqual(self.calls, [])

    def test_repo_dictionary(self):
        """dicts/wikipedia.json рэпазіторыя: ключы «мова:загаловак», псеўданімы вядуць на запісы."""
        with open(wiki.FILE, encoding="utf-8") as f:
            data = json.load(f)
        for k, e in data["entries"].items():
            self.assertRegex(k, r"^[a-z]{2,3}:.+")
            self.assertTrue({"be", "desc", "note", "checked"} <= set(e), k)
        for a, k in data["aliases"].items():
            self.assertIn(k, data["entries"], a)
            self.assertEqual(a, a.casefold(), a)


if __name__ == "__main__":
    unittest.main()
