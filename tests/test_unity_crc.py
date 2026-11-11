"""Абнуленне CRC у каталогу Addressables (core/belloc/engines/unity_localization/crc.py).

    python -X utf8 -m unittest discover -s tests
"""
import base64
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from belloc.engines.unity_localization.apply import _targets  # noqa: E402
from belloc.engines.unity_localization.crc import zero_crc  # noqa: E402


def options(crc: int, name: str) -> dict:
    return {"m_Hash": "abc", "m_Crc": crc, "m_BundleName": name, "m_BundleSize": 10}


def blob(entries, enc: str) -> bytes:
    """Падобна на m_ExtraDataString: тып, імёны класа і JSON запісаў, з даўжынямі."""
    out = bytearray()
    for e in entries:
        js = json.dumps(e, separators=(",", ":")).encode(enc)
        out += b"\x07\x05Unity\x07Options" + len(js).to_bytes(4, "little") + js
    return bytes(out)


def catalog(extra: bytes) -> bytes:
    return json.dumps({"m_LocatorId": "Main", "m_EntryDataString": "AAAA",
                       "m_ExtraDataString": base64.b64encode(extra).decode(),
                       "m_InternalIds": ["x"]}, indent=1).encode()


def crcs(data: bytes, enc: str) -> list:
    extra = base64.b64decode(json.loads(data)["m_ExtraDataString"])
    found, i = [], 0
    while (i := extra.find(b"\x07Options", i)) != -1:
        n = int.from_bytes(extra[i + 8:i + 12], "little")
        found.append(json.loads(extra[i + 12:i + 12 + n].decode(enc))["m_Crc"])
        i += 12 + n
    return found


class ZeroCrcTest(unittest.TestCase):
    def check(self, enc):
        entries = [options(1313793996, "a"), options(7, "b"), options(0, "c")]
        data = catalog(blob(entries, enc))
        out, n = zero_crc(data)
        self.assertEqual(n, 3)
        self.assertEqual(len(out), len(data))
        self.assertEqual(crcs(out, enc), [0, 0, 0])
        # астатняе не чапаецца
        a, b = json.loads(data), json.loads(out)
        del a["m_ExtraDataString"], b["m_ExtraDataString"]
        self.assertEqual(a, b)
        # паўтор нічога не мяняе
        self.assertEqual(zero_crc(out)[0], out)

    def test_utf16(self):
        self.check("utf-16-le")

    def test_ascii(self):
        self.check("ascii")

    def test_no_extra(self):
        with self.assertRaises(ValueError):
            zero_crc(b'{"m_LocatorId": "Main"}')


class FakeLoc:
    def __init__(self, sec):
        self.sec = sec

    def section(self, name):
        return self.sec


class SchemaTest(unittest.TestCase):
    """Стары лаўнчар не ведае crc_catalog: такі payload — схема 2, астатнія — без яе."""

    def test_crc_needs_schema_2(self):
        from belloc import payload as payload_mod
        from belloc.engines.unity_localization.apply import payload
        sec = {"bundles": "aa/Win", "preview_locale": "ru"}
        self.assertNotIn("schema", payload(FakeLoc(sec)))
        p = payload(FakeLoc({**sec, "crc_catalog": "aa/catalog.json"}))
        self.assertEqual(p["schema"], 2)
        self.assertLessEqual(p["schema"], payload_mod.SCHEMA)


class TargetsTest(unittest.TestCase):
    def test_catalog_restored(self):
        with tempfile.TemporaryDirectory() as game:
            payload = {"bundles_dir": "aa/Win", "locale": "ru", "font_bundles": [],
                       "data_dir": "D", "crc_catalog": "aa/catalog.json"}
            paths = [t.path for t in _targets(game, payload)]
            self.assertIn(os.path.join(game, "aa", "catalog.json"), [os.path.normpath(p) for p in paths])

    def test_catalog_outside_refused(self):
        with tempfile.TemporaryDirectory() as game:
            payload = {"bundles_dir": "aa/Win", "locale": "ru", "font_bundles": [],
                       "data_dir": "D", "crc_catalog": "../catalog.json"}
            with self.assertRaises(SystemExit):
                _targets(game, payload)


if __name__ == "__main__":
    unittest.main()
