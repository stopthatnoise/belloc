"""Працяжнік у сказе — з неразрыўным прабелам перад ім (праверка dash).

    python -X utf8 -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from belloc.lint import Segment, check_dash  # noqa: E402


def msgs(text):
    return list(check_dash(Segment("f", "k", "src", text)))


class DashTest(unittest.TestCase):
    def test_plain_space_is_a_finding(self):
        self.assertEqual(len(msgs("тэкст \u2014 далей")), 1)

    def test_nbsp_is_fine(self):
        self.assertEqual(msgs("тэкст\u00a0\u2014 далей"), [])

    def test_several_plain_spaces(self):
        found = msgs("а \u2014 б \u2014 в")
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0].startswith("2×"), found[0])

    def test_space_after_dash_is_not_checked(self):
        # пасля працяжніка прабел звычайны — гэта правільна
        self.assertEqual(msgs("тэкст\u00a0\u2014 далей"), [])

    def test_line_start_dash_is_not_checked(self):
        # працяжнік на пачатку радка (рэпліка дыялогу) — неразрыўны прабел
        # перад ім не патрэбны, бо перад ім няма тэксту
        self.assertEqual(msgs("\u2014 Прывітанне"), [])
        self.assertEqual(msgs("слова\n\u2014 далей"), [])
        self.assertEqual(msgs("\u2014 Прывітанне\n\u2014 І табе"), [])

    def test_dash_without_spaces_is_not_this_check(self):
        self.assertEqual(msgs("тэкст\u2014далей"), [])

    def test_hyphen_is_not_a_dash(self):
        self.assertEqual(msgs("ультра-віялета"), [])


if __name__ == "__main__":
    unittest.main()
