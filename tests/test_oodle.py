"""ooz.pyd у exe — толькі наша зборка pyooz (core/belloc/oodle.py).

    python -X utf8 -m unittest discover -s tests
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from belloc import oodle  # noqa: E402

OURS = "a" * 64


class OodleTest(unittest.TestCase):
    def check(self, have, expected=OURS, allow=False):
        env = {"BELLOC_ALLOW_PYPI_OOZ": "1"} if allow else {}
        with mock.patch.object(oodle, "installed_sha256", return_value=have), \
                mock.patch.object(oodle, "OOZ_SHA256", expected), \
                mock.patch.dict(os.environ, env, clear=False):
            if not allow:
                os.environ.pop("BELLOC_ALLOW_PYPI_OOZ", None)
            oodle.check(log=lambda *_: None)

    def test_ours(self):
        self.check(OURS)

    def test_pypi_wheel_refused(self):
        with self.assertRaises(SystemExit):
            self.check("b" * 64)

    def test_not_approved_yet(self):
        with self.assertRaises(SystemExit):
            self.check(OURS, expected=None)

    def test_not_installed(self):
        with self.assertRaises(SystemExit):
            self.check(None, allow=True)

    def test_trial_build_allowed(self):
        self.check("b" * 64, allow=True)


if __name__ == "__main__":
    unittest.main()
