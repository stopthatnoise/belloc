"""Мяккі перанос <shy> — частка слова, а не тэг вакол яго.

    python -X utf8 -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from belloc.lint import Segment, check_tags, clean_markup  # noqa: E402


class ShyTest(unittest.TestCase):
    def test_shy_stays_inside_word(self):
        self.assertEqual(clean_markup("Утрымлі<shy>вайце, каб"), "Утрымлівайце, каб")

    def test_shy_is_not_a_word_break(self):
        words = clean_markup("Перазапі<shy>саць").split()
        self.assertEqual(words, ["Перазапісаць"])

    def test_other_tags_still_separate(self):
        self.assertEqual(clean_markup("тэкст<br>далей"), "тэкст далей")

    def test_inline_tags_do_not_split_words(self):
        self.assertEqual(clean_markup("<i>пера</i>прызначыць"), "перапрызначыць")
        self.assertEqual(clean_markup("тэкст <i>курсіў</i> далей"), "тэкст курсіў далей")

    def test_case_and_spaces_inside_tag(self):
        self.assertEqual(clean_markup("слова<SHY>злучэнне"), "словазлучэнне")
        self.assertEqual(clean_markup("слова< shy >злучэнне"), "словазлучэнне")

    def test_shy_is_not_compared_between_languages(self):
        # у англійскім радку <shy> няма, у беларускім ён пастаўлены па-свойму —
        # гэта не разыходжанне тэгаў
        seg = Segment("f.csv", "k", "Утрымлівайце, каб", "Утрымлі<shy>вайце, каб")
        self.assertEqual(list(check_tags(seg)), [])

    def test_other_tags_still_compared(self):
        seg = Segment("f.csv", "k", "<b>тэкст</b>", "тэкст")
        self.assertTrue(list(check_tags(seg)))


if __name__ == "__main__":
    unittest.main()
