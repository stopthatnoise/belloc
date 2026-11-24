"""TMP 1.x кодэк, складанне Ў/ў і FontLocTable — без гульні і без яе тэксту.

    python -X utf8 -m unittest discover -s tests -p "test_battletech_fonts.py"
"""
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from belloc.engines.battletech_csv import fonts  # noqa: E402

FONT_NAME = "Demo SDF RU"
ATLAS = 128


def _glyph(code, x, y, w, h):
    return {"id": code, "x": float(x), "y": float(y), "width": float(w),
            "height": float(h), "x_offset": 1.0, "y_offset": float(h),
            "x_advance": float(w + 2), "scale": 1.0}


def _font(glyphs):
    face = {"name": "Demo", "point_size": 16.0, "scale": 1.0,
            "character_count": len(glyphs), "line_height": 20.0, "baseline": 0.0,
            "ascender": 16.0, "cap_height": 12.0, "descender": -4.0,
            "center_line": 0.0, "superscript_offset": 0.0, "subscript_offset": 0.0,
            "sub_size": 0.0, "underline": 0.0, "underline_thickness": 0.0,
            "strikethrough": 0.0, "strikethrough_thickness": 0.0, "tab_width": 0.0,
            "padding": 5.0, "atlas_width": float(ATLAS), "atlas_height": float(ATLAS)}
    cs = {"source_font_file_name": "demo", "source_font_file_guid": "",
          "point_size_sampling_mode": 0, "point_size": 16, "padding": 5,
          "packing_mode": 0, "atlas_width": ATLAS, "atlas_height": ATLAS,
          "character_set_selection_mode": 0, "character_sequence": "",
          "referenced_font_asset_guid": "", "referenced_text_asset_guid": "",
          "font_style": 0, "font_style_modifier": 0.0, "render_mode": 0,
          "include_font_features": 1}
    return {"m_GameObject": {"file": 0, "path": 1}, "m_Enabled": 1,
            "m_Script": {"file": 0, "path": 2}, "m_Name": FONT_NAME,
            "hash_code": 0, "material": {"file": 0, "path": 4},
            "material_hash_code": 0, "font_asset_type": 0, "face": face,
            "atlas": {"file": 0, "path": 3}, "glyphs": glyphs, "kerning": [],
            "kerning_pair": b"\0" * fonts.KERNING_SIZE, "fallback": [],
            "creation_settings": cs, "font_weights": [], "normal_style": 0.0,
            "normal_spacing_offset": 0.0, "bold_style": 0.75, "bold_spacing": 7.0,
            "italic_style": 0, "tab_size": 0}


def _atlas():
    from PIL import Image, ImageDraw
    img = Image.new("L", (ATLAS, ATLAS), 0)
    d = ImageDraw.Draw(img)
    # у: дзве паласы; й: брэвіс (верхнія 4 радкі) + ніз; и: ніз; У/Й/И — тое ж
    d.line([(4, 4), (8, 16), (12, 4)], fill=220, width=2)             # у
    d.rectangle([16, 4, 24, 7], fill=220)                              # й: брэвіс
    d.line([(17, 8), (20, 20), (23, 8)], fill=220, width=2)
    d.line([(26, 8), (30, 18), (34, 8)], fill=220, width=2)            # и
    d.line([(40, 4), (44, 16), (48, 4)], fill=220, width=2)            # У
    d.rectangle([52, 4, 60, 7], fill=220)                              # Й: брэвіс
    d.line([(53, 8), (56, 20), (59, 8)], fill=220, width=2)
    d.line([(64, 8), (68, 18), (72, 8)], fill=220, width=2)            # И
    d.rectangle([4, 40, 14, 52], fill=180)                             # щ
    d.rectangle([16, 40, 22, 50], fill=180)                            # ъ
    d.rectangle([26, 40, 36, 52], fill=180)                            # Щ
    d.rectangle([40, 40, 48, 50], fill=180)                            # Ъ
    d.line([(80, 40), (82, 52)], fill=200, width=2)                    # i
    d.line([(90, 40), (92, 52)], fill=200, width=2)                    # I
    return img


def _demo():
    glyphs = [
        _glyph(ord("у"), 4, 4, 10, 13),
        _glyph(ord("й"), 16, 4, 9, 17),
        _glyph(ord("и"), 26, 8, 9, 11),
        _glyph(ord("У"), 40, 4, 9, 13),
        _glyph(ord("Й"), 52, 4, 9, 17),
        _glyph(ord("И"), 64, 8, 9, 11),
        _glyph(ord("щ"), 4, 40, 11, 13),
        _glyph(ord("ъ"), 16, 40, 7, 11),
        _glyph(ord("Щ"), 26, 40, 11, 13),
        _glyph(ord("Ъ"), 40, 40, 9, 11),
        _glyph(ord("i"), 80, 40, 3, 13),
        _glyph(ord("I"), 90, 40, 3, 13),
    ]
    return fonts.parse(fonts.build(_font(glyphs)))


def _gap(a, b):
    def rect(g):
        return (g["x"], g["y"], g["x"] + g["width"], g["y"] + g["height"])
    ax0, ay0, ax1, ay1 = rect(a)
    bx0, by0, bx1, by1 = rect(b)
    return max(0, bx0 - ax1, ax0 - bx1), max(0, by0 - ay1, ay0 - by1)


class FontsTest(unittest.TestCase):
    def test_codec_roundtrip(self):
        font = _demo()
        self.assertEqual(fonts.build(fonts.parse(fonts.build(font))),
                         fonts.build(font))
        self.assertEqual(font["face"]["padding"], 5.0)
        self.assertEqual(font["m_Name"], FONT_NAME)

    def test_compose_keeps_padding(self):
        font = _demo()
        atlas = _atlas()
        changes = fonts.patch_font(font, atlas, FONT_NAME, log=lambda *_: None)
        self.assertEqual({r["id"] for r in changes},
                         {0x045E, 0x040E, 0x0456, 0x0406})
        ids = {int(g["id"]) for g in font["glyphs"]}
        self.assertFalse({ord(c) for c in fonts.SLOTS} & ids)
        pad = int(font["face"]["padding"])
        live = [g for g in font["glyphs"] if g["width"] > 0 and g["height"] > 0]
        for rec in changes:
            if rec["id"] not in (0x045E, 0x040E):
                continue
            for other in live:
                if other is rec:
                    continue
                if (other["x"], other["y"], other["width"], other["height"]) == \
                        (rec["x"], rec["y"], rec["width"], rec["height"]):
                    continue
                dx, dy = _gap(rec, other)
                self.assertGreaterEqual(max(dx, dy), pad + 1,
                                        f"{chr(rec['id'])} занадта блізка да "
                                        f"{chr(other['id'])}: {dx},{dy}")
            x, y = int(rec["x"]), int(rec["y"])
            w, h = int(rec["width"]), int(rec["height"])
            self.assertGreater(atlas.crop((x, y, x + w, y + h)).getextrema()[1], 0)
        # кодэк пасля правак па-ранейшаму складаецца і памер не мяняецца
        raw = fonts.build(font)
        self.assertEqual(fonts.build(fonts.parse(raw)), raw)

    def test_idempotent(self):
        font = _demo()
        atlas = _atlas()
        fonts.patch_font(font, atlas, FONT_NAME, log=lambda *_: None)
        self.assertEqual(fonts.patch_font(font, atlas, FONT_NAME, log=lambda *_: None), [])

    def test_fontloc_table(self):
        name = b"RussianFontLocTable"
        head = b"\0" * 28
        q = (28 + 4 + len(name) + 3) & ~3
        pairs = [(100, 200), (101, 200)]
        raw = (head + struct.pack("<i", len(name)) + name
               + b"\0" * (q - 28 - 4 - len(name))
               + struct.pack("<ii", 6, len(pairs))
               + b"".join(struct.pack("<iqiq", 0, b, 0, r) for b, r in pairs))
        got = fonts.table_parse(raw)
        self.assertEqual(got[0], "RussianFontLocTable")
        self.assertEqual(got[1], 6)
        self.assertEqual(got[2], 2)
        self.assertEqual(got[4], pairs)
        new = fonts.table_patch(raw, [(102, 200), (100, 200)])
        _n, _c, count, _q, got_pairs = fonts.table_parse(new)
        self.assertEqual(count, 3)
        self.assertEqual(got_pairs[-1], (102, 200))
        self.assertEqual(fonts.table_patch(new, [(102, 200)]), new)

    def test_font_paths_stay_inside_game(self):
        from belloc.engines.battletech_csv.apply import _font_files
        self.assertEqual(_font_files("C:/game", {}), [])
        with self.assertRaises(SystemExit):
            _font_files("C:/game", {"data_dir": "Data", "font_assets": ["../x"],
                                    "font_resS": {"../x": "y"}})

    def test_payload_fontmap(self):
        import json
        import tempfile
        from belloc import config
        import importlib
        mod = importlib.import_module("belloc.engines.battletech_csv.apply")
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "fontmap.json"), "w", encoding="utf-8") as f:
                json.dump({"table": "T", "culture": "ru-RU",
                           "pairs": [["Base SDF", "Repl SDF"]]}, f)
            loc = config.Loc(id="demo", dir=d, local=d, name="Demo",
                             engine="battletech-csv")
            got = mod._fontmap(loc, {"fontmap": "fontmap.json"})
            self.assertEqual(got["pairs"], [["Base SDF", "Repl SDF"]])
            with self.assertRaises(SystemExit):
                mod._fontmap(loc, {"fontmap": "../fontmap.json"})


if __name__ == "__main__":
    unittest.main()
