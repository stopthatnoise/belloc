"""Праверка gender: род 2-й асобы па радку-падказцы (звычайна рускай).

    python -X utf8 -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from belloc import lint  # noqa: E402
from belloc.lint import Segment, check_gender  # noqa: E402


def msgs(hint: str, dst: str):
    lint.HINT.clear()
    if hint:
        lint.HINT[dst_src] = hint
    return list(check_gender(Segment("f", dst_src, dst_src, dst)))


dst_src = "Have you ever noticed that?"


class GenderTest(unittest.TestCase):
    def setUp(self):
        # лінтэр будуе гэты слоўнік з корпуса; у тэсце дастаткова пары «-ў/-ла»
        lint.DST_WORDS.update({"заўважала"})

    def tearDown(self):
        lint.HINT.clear()
        lint.DST_WORDS.clear()

    def test_hint_feminine_dst_masculine(self):
        self.assertEqual(len(msgs("Замечала ли ты, что так бывает?", "Ты заўважаў, што так бывае?")), 1)

    def test_hint_feminine_dst_feminine(self):
        self.assertEqual(msgs("Замечала ли ты, что так бывает?", "Ты заўважала, што так бывае?"), [])

    def test_hint_masculine_is_not_a_finding(self):
        self.assertEqual(msgs("Ты заметил, что так бывает?", "Ты заўважыў, што так бывае?"), [])

    def test_no_hint_means_no_check(self):
        self.assertEqual(msgs("", "Ты заўважаў, што так бывае?"), [])

    def test_third_person_is_ignored(self):
        # «ён сказаў» — не 2-я асоба, хаця ў падказцы ёсць жаночая форма
        self.assertEqual(msgs("Ты сказала, что он пришёл.", "Ты сказала, што ён прыйшоў."), [])


if __name__ == "__main__":
    unittest.main()
