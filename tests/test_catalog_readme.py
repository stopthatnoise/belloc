"""belloc catalog: спасылкі на рэліз у README гульні і агульным README — на новую версію.

    python -X utf8 -m unittest discover -s tests
"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from belloc import catalog, config  # noqa: E402

R = catalog.RELEASES


class UpdateReadmesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        d = os.path.join(self.tmp, "demo")
        os.makedirs(d)
        self.loc = config.Loc(id="demo", dir=d, local=os.path.join(self.tmp, "local"),
                              name="Demo", engine="paradox",
                              raw={"release": {"version": "1.1", "file": "Demo_BE"}})

    def write(self, name, text):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        return path

    def read(self, path):
        with open(path, encoding="utf-8", newline="") as f:
            return f.read()

    def test_links_and_file_name(self):
        game = self.write("demo/README.md",
                          f"Апошняя — **[1.0]({R}/tag/demo-v1.0)**.\r\n"
                          "спампуйце `Demo_BE_1.0.zip`\n"
                          f"чужая: **[1.0]({R}/tag/demo2-v1.0)**, `Demo_BE2_1.0.zip`\n")
        root = self.write("README.md", f"| Demo | **[1.0]({R}/tag/demo-v1.0)** |\n")
        changed = catalog.update_readmes(self.loc, "1.1", [game, root, self.tmp + "/няма.md"])
        self.assertEqual(changed, [game, root])
        self.assertEqual(self.read(game),
                         f"Апошняя — **[1.1]({R}/tag/demo-v1.1)**.\r\n"
                         "спампуйце `Demo_BE_1.1.zip`\n"
                         f"чужая: **[1.0]({R}/tag/demo2-v1.0)**, `Demo_BE2_1.0.zip`\n")
        self.assertEqual(self.read(root), f"| Demo | **[1.1]({R}/tag/demo-v1.1)** |\n")

    def test_unchanged(self):
        game = self.write("demo/README.md", f"**[1.1]({R}/tag/demo-v1.1)** `Demo_BE_1.1.zip`\n")
        self.assertEqual(catalog.update_readmes(self.loc, "1.1", [game]), [])


if __name__ == "__main__":
    unittest.main()
