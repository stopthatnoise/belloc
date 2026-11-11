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
    "Red Shirts": {"desc": "Volunteers of a made-up army", "be": "Чырвонакашульнікі", "ru": "Краснорубашечники",
                   "qid": "Q901"},
    "Lake Nowhere": {"desc": "Made-up lake", "ru": "Озеро Нигде", "qid": "Q902"},
    "Mercury": {"disambig": True},
}
REDIRECTS = {"Redshirts": "Red Shirts"}
# выдуманыя элементы Вікіданых; Q903 — без артыкула ў en.wikipedia, Q904 — з двума P21
ITEMS = {
    "Q901": {"label": "Red Shirts", "be": "Чырвонакашульнікі", "beWiki": "Чырвонакашульнікі",
             "types": "military unit|volunteer army"},
    "Q902": {"label": "Lake Nowhere", "be": "Возера Нідзе", "tarask": "Возера Нідзе", "types": "lake"},
    "Q903": {"label": "Ann Nowhere", "desc": "made-up writer", "be": "Ганна Нідзе",
             "sex": "http://www.wikidata.org/entity/Q6581072", "types": "human"},
}


def fake_api(calls):
    def api(src, params):
        calls.append(params)
        if src == "sparql":
            ids = [x[3:] for x in params["query"].split("VALUES ?item {", 1)[1].split("}", 1)[0].split()]
            rows = []
            for q in ids:
                if q in ITEMS:
                    row = {"item": f"http://www.wikidata.org/entity/{q}", **ITEMS[q]}
                    rows.append({k: {"type": "literal", "value": v} for k, v in row.items()})
            return {"results": {"bindings": rows + rows[:1]}}       # паўтор радка — як пры двух P21
        if src == "wikidata":
            hit = [{"id": "Q903", "label": "Ann Nowhere", "description": "made-up writer"}]
            return {"search": hit if "Ann" in params["search"] else []}
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
            page = {"title": r, "description": p.get("desc", ""), "pageprops": {}}
            if p.get("disambig"):
                page["pageprops"]["disambiguation"] = ""
            if p.get("qid"):
                page["pageprops"]["wikibase_item"] = p["qid"]
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
        self.assertIn("Lake Nowhere → Возера Нідзе  (метка Вікіданых; беларускага артыкула няма)", out)
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

    def test_wikidata_fields(self):
        rc, out = self.run_("Red Shirts", "Lake Nowhere")
        e = wiki.load(self.path)["entries"]
        red, lake = e["en:Red Shirts"], e["en:Lake Nowhere"]
        self.assertEqual(red["qid"], "Q901")
        self.assertEqual(red["type"], "military unit, volunteer army")
        self.assertNotIn("be_label", red)                           # метка = артыкул — не дублюем
        self.assertNotIn("tarask", red)                             # артыкул ёсць — тарашкевіца не трэба
        self.assertEqual(lake["be_label"], "Возера Нідзе")
        self.assertEqual(lake["tarask"], "Возера Нідзе")
        self.assertIn("Lake Nowhere → Возера Нідзе  (метка Вікіданых", out)
        self.assertIn("https://www.wikidata.org/wiki/Q901", out)
        self.assertEqual(sum(c.get("query", "").count("wd:Q") for c in self.calls), 2)   # адзін SPARQL на абодва
        rc, out = self.run_("Возера", reverse=True)
        self.assertIn("Lake Nowhere", out)

    def test_wikidata_only_item(self):
        rc, out = self.run_("Ann Nowhere")                          # артыкула няма — элементы Вікіданых
        self.assertEqual(rc, 1)
        self.assertIn("у Вікіданых: Q903 Ann Nowhere — made-up writer", out)
        rc, out = self.run_("q903", aliases=["Ann Nowhere"])
        self.assertEqual(rc, 0)
        e = wiki.load(self.path)["entries"]["wd:Q903"]
        self.assertEqual((e["label"], e["lang"], e["be"], e["be_label"], e["sex"]),
                         ("Ann Nowhere", "en", None, "Ганна Нідзе", "ж"))
        self.assertIn("што гэта: human; жанчына", out)
        n = len(self.calls)
        rc, out = self.run_("ann nowhere")                          # псеўданім → wd:Q903, без сеткі
        self.assertEqual(len(self.calls), n)
        self.assertIn("Ann Nowhere → Ганна Нідзе", out)
        self.run_("Red Shirts")
        rc, out = self.run_("Q901", offline=True)                   # QID знаходзіць і en-запіс
        self.assertIn("Red Shirts → Чырвонакашульнікі", out)

    def test_wikidata_down(self):
        self.run_("Lake Nowhere")
        base = self.api

        def down(src, params):
            if src == "sparql":
                raise SystemExit("Вікіданыя: 503 Service Unavailable (sparql)")
            return base(src, params)
        self.api = down
        rc, out = self.run_("Lake Nowhere", refresh=True)
        self.assertIn("далей без Вікіданых", out)                    # працуем без іх, палі не губляюцца
        self.assertEqual(wiki.load(self.path)["entries"]["en:Lake Nowhere"]["be_label"], "Возера Нідзе")

    def test_refresh_all(self):
        self.run_("Red Shirts", note="наша")
        self.run_("Q903")
        n = len(self.calls)
        rc, out = self.run_(refresh=True)
        self.assertEqual(rc, 0)
        self.assertGreater(len(self.calls), n)
        e = wiki.load(self.path)["entries"]
        self.assertEqual(set(e), {"en:Red Shirts", "wd:Q903"})
        self.assertEqual(e["en:Red Shirts"]["note"], "наша")

    def test_bad_lang(self):
        with self.assertRaises(SystemExit):
            self.run_("x", src='en"}')

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
