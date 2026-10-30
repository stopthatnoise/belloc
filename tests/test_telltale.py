"""Рухавік telltale на выдуманых даных: радкі Lua па хэшах, перанос радкоў,
дэскрыптар набору, assets у payload (шрыфты з ліцэнзіяй).

    python -X utf8 -m unittest discover -s tests
"""
import json
import os
import shutil
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from belloc import config, payload  # noqa: E402
from belloc.engines import telltale  # noqa: E402
from belloc.engines.telltale.apply import font_file, override_lua, patch_lua, wrap_text  # noqa: E402
from belloc.engines.telltale.common import key_hash, set_archives, set_of  # noqa: E402
from belloc.engines.telltale.lenc import Blowfish7, decrypt_lua, encrypt_lua  # noqa: E402
from belloc.engines.telltale.luac import Chunk  # noqa: E402


def lua_chunk(*strings: bytes) -> bytes:
    """Lua 5.2 bytecode: адна функцыя з адной інструкцыяй і радковымі канстантамі."""
    u = lambda v: struct.pack("<I", v)  # noqa: E731
    head = b"\x1bLua\x52\x00\x01\x04\x04\x04\x04\x00\x19\x93\r\n\x1a\n"
    consts = b"".join(b"\x04" + u(len(s) + 1) + s + b"\0" for s in strings)
    return (head + u(0) + u(0) + b"\x00\x01\x02" + u(1) + u(0x1F) + u(len(strings)) + consts
            + u(0) + u(0) + u(0) + u(0) + u(0) + u(0))


class LuaTest(unittest.TestCase):
    def test_patch_by_hash(self):
        bf = Blowfish7(bytes.fromhex("0123456789abcdef"))
        data = encrypt_lua(lua_chunk(b"RESTART", b"Menu_Pause", b"PLAY"), bf)
        out, n = patch_lua(data, {key_hash("RESTART"): "ПАЧАЦЬ НАНОВА",
                                         key_hash("PLAY"): "PLAY"}, bf)
        self.assertEqual(n, 1)                      # пераклад, роўны арыгіналу, не мяняецца
        got = [s for _, _, s in Chunk(decrypt_lua(out, bf)).strings]
        self.assertEqual(got, ["ПАЧАЦЬ НАНОВА".encode(), b"Menu_Pause", b"PLAY"])


class TextTest(unittest.TestCase):
    def test_wrap(self):
        self.assertEqual(wrap_text("кароткі радок", 80), "кароткі радок")
        w = wrap_text("{Angry}[shouts] адзін два тры чатыры пяць шэсць", 20)
        self.assertEqual(w, "{Angry}[shouts] адзін два тры\nчатыры пяць шэсць")

    def test_set_of(self):
        self.assertEqual(set_of("Fables_pc_PC-Mac_TTG_Update_03_Episode_05_Menu_all.ttarch2"), "Menu")
        self.assertEqual(set_of("Fables_pc_Fables101_ar_data.ttarch2"), "Fables101")
        self.assertEqual(set_of("Fables_pc_105_all.ttarch2"), "Fables105")

    def test_override_lua(self):
        lua = ('local set = {}\r\nset.descriptionPriority = 20\r\n'
               'set.gameDataArchives = {\r\n    _currentDirectory .. "A.ttarch2"\r\n}\r\n')
        out = override_lua(lua, "Fables_pc_BelLoc_X_ar_all.ttarch2")
        self.assertIn("set.descriptionPriority = 120", out)
        self.assertEqual(set_archives(out), ["Fables_pc_BelLoc_X_ar_all.ttarch2", "A.ttarch2"])

    def test_font_file(self):
        self.assertEqual(font_file("fonts/a/A[wght].ttf:Bold"), "fonts/a/A[wght].ttf")
        self.assertEqual(font_file("fonts/b/B.ttf"), "fonts/b/B.ttf")
        self.assertEqual(font_file("C:/Windows/Fonts/x.ttf"), "C:/Windows/Fonts/x.ttf")


class PayloadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        game = os.path.join(self.tmp, "games", "demo")
        for d in ("arimo", "caveat"):
            os.makedirs(os.path.join(game, "fonts", d))
            for f in ("X.ttf", "OFL.txt"):
                open(os.path.join(game, "fonts", d, f), "w").close()
        sec = {"archive": "Archives", "target": "spanish", "lua_key": "00",
               "lua_text": {"Menu_pause.lua": [key_hash("RESTART")]},
               "fonts": {"": "fonts/arimo/X.ttf:Regular"}}
        with open(os.path.join(game, "game.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "Demo", "engine": "telltale", "telltale": sec}, f)
        with open(os.path.join(game, "textures.json"), "w", encoding="utf-8") as f:
            json.dump({"textures": {"a.d3dtx": {"blocks": [{"font": "fonts/caveat/X.ttf"}]}}}, f)
        os.environ["BELLOC_LOCAL"] = os.path.join(self.tmp, "local")
        self.game = game

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_assets(self):
        loc = config.load(self.game)
        p = payload.build_payload(loc, telltale)
        self.assertEqual(p["assets"], ["fonts/arimo/OFL.txt", "fonts/arimo/X.ttf",
                                       "fonts/caveat/OFL.txt", "fonts/caveat/X.ttf"])
        self.assertEqual(p["telltale"]["lua_files"], ["Menu_pause.lua"])
        self.assertEqual(p["telltale"]["lang"], "english")
        self.assertNotIn("lua_text", p["telltale"])
        self.assertEqual(payload.asset(p, "fonts/arimo/X.ttf:Regular"),
                         os.path.join(self.game, "fonts/arimo/X.ttf:Regular"))
        self.assertNotIn("assets_root", payload.dump(p))
        self.assertEqual(telltale.check_path(p), "Archives")


if __name__ == "__main__":
    unittest.main()
