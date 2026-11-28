"""Назва з гласарыя, свядома пакінутая лацінкай, — не разыходжанне (праверка glossary).

    python -X utf8 -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from belloc.lint import Segment, check_glossary, compile_glossary  # noqa: E402


def msgs(terms, src, dst):
    return list(check_glossary(Segment("f", "k", src, dst), compile_glossary(terms)))


class GlossaryLatinTest(unittest.TestCase):
    def test_translated_name(self):
        self.assertEqual(msgs([("Corodiz", "Кародзіз", [])], "Go to Corodiz.", "Ляці на Кародзіз."), [])

    def test_missing_name_is_a_finding(self):
        self.assertEqual(len(msgs([("Corodiz", "Кародзіз", [])], "Go to Corodiz.", "Ляці туды.")), 1)

    def test_name_kept_in_latin(self):
        self.assertEqual(msgs([("Corodiz", "Кародзіз", [])], "Go to Corodiz.", "Ляці на Corodiz."), [])

    def test_part_of_another_word_is_not_the_name(self):
        self.assertEqual(len(msgs([("Ash", "Эш", [])], "Ash is here.", "Тут Flash.")), 1)

    def test_placeholder_and_tag_are_not_the_name(self):
        terms = [("Player", "гулец", [])]
        self.assertEqual(len(msgs(terms, "Player {Player} wins.", "{Player} перамагае.")), 1)
        self.assertEqual(len(msgs(terms, "<Player>Player wins.", "<Player>Перамога.")), 1)


if __name__ == "__main__":
    unittest.main()
