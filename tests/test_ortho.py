"""Праверка арфаграфічных спалучэнняў (core/belloc/ortho.py і лінтэр ortho).

    python -X utf8 -m unittest discover -s tests
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from belloc.lint import Allowlist, Segment, check_ortho, load_csv  # noqa: E402
from belloc.ortho import text_problems, word_problems  # noqa: E402


def problems(text):
    return text_problems(text)


class BigramTest(unittest.TestCase):
    def test_ti_di(self):
        self.assertTrue(problems("Антіас"))
        self.assertTrue(problems("Кародіз"))
        self.assertTrue(problems("Анціас") == [])
        self.assertTrue(problems("Кародзіз") == [])

    def test_hard_consonants(self):
        for bad in ("рі", "жі", "ші", "чі", "ре"):
            self.assertTrue(problems("а" + bad + "а"), bad)
        for good in ("ры", "жы", "шы", "чы", "рэ"):
            self.assertEqual(problems("а" + good + "а"), [], good)

    def test_dze_ce(self):
        self.assertTrue(problems("Детроіт"))
        self.assertTrue(problems("Тівертан"))
        self.assertEqual(problems("Дэтройт"), [])
        self.assertEqual(problems("Цівертан"), [])
        self.assertEqual(problems("дзе"), [])

    def test_soft_vowels_are_accepted(self):
        for good in ("дзя", "дзё", "дзю", "ця", "цё", "цю", "цэ", "жэ", "шоу", "чорны"):
            self.assertEqual(problems(good), [], good)


class YotTest(unittest.TestCase):
    def test_yot_after_consonant(self):
        self.assertTrue(problems("Рйанс"))
        self.assertTrue(problems("Фйрэс"))

    def test_yot_after_vowel_is_kept(self):
        self.assertEqual(problems("Майер"), [])
        self.assertEqual(problems("Уйетс"), [])

    def test_yot_a(self):
        self.assertTrue(problems("Майа"))
        self.assertTrue(problems("Пайя"))
        self.assertEqual(problems("Мая"), [])
        self.assertEqual(problems("Пая"), [])


class OneOTest(unittest.TestCase):
    def test_three_o(self):
        self.assertTrue(problems("Коромодзір"))

    def test_compounds_and_interjections(self):
        # два «о» — звычайна склад слова, гэта не памылка
        for good in ("водаправод", "трохвугольнік", "Ого", "Оксімор"):
            self.assertEqual(problems(good), [], good)

    def test_abbreviation_is_skipped(self):
        self.assertEqual(problems("ШІ"), [])


class LintIntegrationTest(unittest.TestCase):
    def findings(self, text, allow=None):
        allow = allow or Allowlist()
        return list(check_ortho(Segment("f", "k", None, text), allow))

    def test_finding_text(self):
        found = self.findings("Планета Кародіз")
        self.assertEqual(len(found), 1)
        self.assertIn("дзі", found[0])

    def test_allowlist(self):
        allow = Allowlist()
        allow.exact.add("антіас")
        self.assertEqual(self.findings("Антіас", allow), [])


class CsvInputTest(unittest.TestCase):
    def test_only_bel_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "places.csv"
            path.write_text(
                "en,bel,ru\n"
                "Corodiz,Кародіз,Кородиз\n"
                "Antias,Анціас,Антиас\n",
                encoding="utf-8", newline="\n")
            segs = load_csv(str(path), "bel")
        self.assertEqual([s.dst for s in segs], ["Кародіз", "Анціас"])
        self.assertEqual([s.key for s in segs], ["Corodiz", "Antias"])
        self.assertTrue(text_problems(segs[0].dst))
        self.assertEqual(text_problems(segs[1].dst), [])

    def test_key_column_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "translation.csv"
            path.write_text(
                "key,src_hash,en,bel,note\n"
                "357558878,abc,Corodiz,Кародіз,\n"
                ",def,Antias,Анціас,\n"
                ",ghi,,Анціас,\n",
                encoding="utf-8", newline="\n")
            segs = load_csv(str(path), "bel")
        self.assertEqual([s.key for s in segs],
                         ["357558878", "Antias", "радок 4"])


if __name__ == "__main__":
    unittest.main()
