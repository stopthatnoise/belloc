"""Праверка placeholders і фарматары Smart Strings Unity (core/belloc/lint).

    python -X utf8 -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from belloc.lint import Segment, check_placeholders  # noqa: E402


def problems(src, dst):
    return list(check_placeholders(Segment("f", "k", src, dst)))


class SmartPlaceholdersTest(unittest.TestCase):
    def test_plural_is_a_form(self):
        self.assertEqual(problems("Pay {0} Credits", "Заплаціць {0} {0:plural:крэдыт|крэдыты|крэдытаў}"), [])

    def test_choose_is_a_form(self):
        self.assertEqual(problems("{1} left", "{1} {0:choose(1|2):застаўся|засталіся}"), [])

    def test_number_still_required(self):
        self.assertTrue(problems("Pay {0} Credits", "Заплаціць {0:plural:крэдыт|крэдыты|крэдытаў}"))

    def test_other_format_kept(self):
        self.assertEqual(problems("{0:P0} of value", "{0:P0} кошту"), [])
        self.assertTrue(problems("{0:P0} of value", "{0} кошту"))


if __name__ == "__main__":
    unittest.main()
