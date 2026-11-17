"""Глітч-тэкст (камбайнавыя дыякрытыкі): лінтэр здымае іх, але не націск.

    python -X utf8 -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from belloc.lint import clean_markup  # noqa: E402

ACUTE = "\u0301"      # націск — пакідаем
GRAVE = "\u0300"      # дыякрытык эфекту — здымаем
DOT_BELOW = "\u0323"


class GlitchTextTest(unittest.TestCase):
    def test_combining_marks_removed(self):
        self.assertEqual(clean_markup("К" + GRAVE + "а" + DOT_BELOW + "л"), "Кал")

    def test_stress_kept(self):
        self.assertEqual(clean_markup("зава" + ACUTE + "нгаць"), "зава" + ACUTE + "нгаць")

    def test_marks_do_not_split_words(self):
        self.assertEqual(clean_markup("сло" + GRAVE + "ва").split(), ["слова"])

    def test_letters_with_breve_survive(self):
        # «й» у NFC — адна літара; зняцце дыякрытыкаў не павінна рабіць з яе «и»
        self.assertEqual(clean_markup("тво" + GRAVE + "й"), "твой")


if __name__ == "__main__":
    unittest.main()
