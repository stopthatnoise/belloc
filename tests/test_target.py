""".orig і .bel файлаў гульні (core/belloc/install/target.py).

    python -X utf8 -m unittest discover -s tests
"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from belloc.install.target import Target, write_to  # noqa: E402


def put(path, data):
    with open(path, "wb") as f:
        f.write(data)


def get(path):
    with open(path, "rb") as f:
        return f.read()


def upper(base, dst):
    put(dst, get(base).upper())


class TargetTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "data.bundle")
        put(self.path, b"original")
        self.t = Target(self.path)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_install_twice_and_restore(self):
        write_to(self.t, None, upper)
        write_to(self.t, None, upper)                 # паўтор бярэ .orig, а не наш файл
        self.assertEqual(get(self.path), b"ORIGINAL")
        self.assertTrue(self.t.installed())
        self.assertEqual(self.t.restore(), "вернуты арыгінал")
        self.assertEqual(get(self.path), b"original")
        self.assertFalse(os.path.exists(self.t.orig) or os.path.exists(self.t.mark))

    def test_steam_update(self):
        write_to(self.t, None, upper)
        put(self.path, b"updated")                    # Steam абнавіў гульню
        self.assertFalse(self.t.installed())
        write_to(self.t, None, upper)                 # аснова — новы файл, стары .orig адкінуты
        self.assertEqual(get(self.path), b"UPDATED")
        self.assertEqual(get(self.t.orig), b"updated")

    def test_steam_verify_then_restore(self):
        write_to(self.t, None, upper)
        put(self.path, b"original")                   # «праверка цэласнасці» вярнула арыгінал
        self.assertEqual(self.t.restore(), "у гульні ўжо арыгінал (Steam абнавіў файл)")
        self.assertEqual(get(self.path), b"original")

    def test_out_does_not_touch_game(self):
        out = os.path.join(self.tmp, "out")
        dst = write_to(self.t, out, upper)
        self.assertEqual(get(dst), b"ORIGINAL")
        self.assertEqual(get(self.path), b"original")
        self.assertFalse(os.path.exists(self.t.orig) or os.path.exists(self.t.mark))


if __name__ == "__main__":
    unittest.main()
