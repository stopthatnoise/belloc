"""Рухавік battletech-csv на выдуманай гульні: ключы-хэшы, гібрыдная крыніца,
табліца з `U+001F` і `\\n`, apply/restore.

    python -X utf8 -m unittest discover -s tests
"""
import csv
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from belloc import config, tables  # noqa: E402
from belloc.engines import base, battletech_csv  # noqa: E402
from belloc.engines.battletech_csv import norm, table, subtitles  # noqa: E402

DATA = "BattleTech_Data"
LOC = "StreamingAssets/data/localization"
CSV_DIR = f"{DATA}/{LOC}"
SUB_DIR = f"{DATA}/StreamingAssets/Video/Subtitles"

ROWS = [
    ("", ""),                                       # пусты радок у пачатку
    ("start the engine", "Завести мотор"),
    ("quit", "Выйсці"),
    ("text^ with comma", "Тэкст, з коскай"),
    ("only german", "Толькі нямецкая"),
    ("only key like", "Толькі key-like"),
    ("ru only row", "Толькі руская"),
    ("no source at all", "Зусім без крыніцы"),
    ("nothing here", ""),
    ("say it", "Скажы \"так\""),
]
DE = {
    "start the engine": "Motor starten",
    "quit": "Beenden",
    "text^ with comma": "Text, mit Komma",
    "only german": "Nur Deutsch",
}
FR = {k: f"FR {v}" for k, v in DE.items()}


def write_csv(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(header + "\n")
        for key, value in rows:
            f.write(f"{key},{value}\n")


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False)


def write_srt(path, cues):
    """Cues: [(нумар, час, тэкст)] → UTF-8 BOM + CRLF, як у файлах гульні."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    blocks = [f"{n}\r\n{t}\r\n{x.replace(chr(10), chr(13) + chr(10))}" for n, t, x in cues]
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("\ufeff" + "\r\n\r\n".join(blocks) + "\r\n\r\n")


def write_subtitles(path, rows):
    """Табліца перакладу субтытраў: file, idx, bel, note."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["file", "idx", "bel", "note"])
        w.writerows(rows)


class BattleTechTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.game = os.path.join(self.tmp, "game")
        write_csv(os.path.join(self.game, CSV_DIR, "strings_ru-RU.csv"), "KEY,ru-RU", ROWS)
        write_csv(os.path.join(self.game, CSV_DIR, "strings_de-DE.csv"), "KEY,de-DE",
                  [(k, DE.get(k, "")) for k, _ in ROWS])
        write_csv(os.path.join(self.game, CSV_DIR, "strings_fr-FR.csv"), "KEY,fr-FR",
                  [(k, FR.get(k, "")) for k, _ in ROWS])
        write_json(os.path.join(self.game, DATA, "StreamingAssets/data/items/Thing.json"),
                   {"Name": "Start the engine", "Other": "starttheengine",
                    "Fourth": "onlykeylike"})
        write_json(os.path.join(self.game, DATA, "StreamingAssets/version.json"),
                   {"ProductVersion": "1.0", "BuildNumber": "1R"})
        game_dir = os.path.join(self.tmp, "games", "demo")
        os.makedirs(game_dir)
        write_json(os.path.join(game_dir, "game.json"),
                   {"name": "Demo", "engine": "battletech-csv", "source_lang": "en",
                    "fallback_lang": "de", "last_resort": "ru", "hint_lang": "ru",
                    "battletech_csv": {
                        "data_dir": DATA, "csv_dir": CSV_DIR, "locale": "ru-RU",
                        "target": "ru", "other_langs": ["de", "fr"],
                        "subtitles": f"{DATA}/StreamingAssets/Video/Subtitles",
                        "subtitle_table": "subtitles.csv", "subtitle_lang": "Russian",
                        "scan": {"assets": False, "levels": False}}})
        os.environ["BELLOC_LOCAL"] = os.path.join(self.tmp, "local")
        os.makedirs(os.path.join(self.tmp, "local", "demo"))
        write_json(os.path.join(self.tmp, "local", "demo", "local.json"),
                   {"game_dir": self.game})
        write_srt(os.path.join(self.game, SUB_DIR, "demo-Russian.srt"),
                  [("1", "00:00:01,000 --> 00:00:02,000", "Оригинал"),
                   ("2", "00:00:03,000 --> 00:00:04,000", "Оригинал\nвторая строка")])
        write_subtitles(os.path.join(game_dir, "subtitles.csv"),
                        [("demo", "1", "Пераклад", ""),
                         ("demo", "2", "Пераклад\nдругі радок", "")])
        self.loc = config.load(game_dir)
        with redirect_stdout(io.StringIO()):
            battletech_csv.extract(self.loc)
            tables.sync(self.loc)

    def tearDown(self):
        os.environ.pop("BELLOC_LOCAL", None)
        shutil.rmtree(self.tmp)

    def rows(self):
        return {r["key"]: r for r in tables.load_all(self.loc)["strings"]}

    def out_csv(self, name="strings_ru-RU.csv"):
        return os.path.join(self.tmp, "out", name)

    def patch(self):
        with redirect_stdout(io.StringIO()) as log:
            base.patch(self.loc, battletech_csv, os.path.join(self.tmp, "out"))
        return log.getvalue()

    def set_bel(self, key, bel, lang=None):
        h = norm.hashed_key(key)
        rows = tables.load_all(self.loc)["strings"]
        for r in rows:
            if r["key"] == h:
                r["bel"] = bel
                if lang:
                    r["src_lang"] = lang
        tables.save(self.loc, "strings", rows)

    def test_normalize(self):
        self.assertEqual(norm.normalize("Start, the  Engine."), "start^theengine*")
        self.assertEqual(norm.normalize("Go <i>now</i>"), "gonow")
        self.assertEqual(norm.normalize("See [[Path,thing"), "see[[path^thing")
        self.assertEqual(norm.normalize("What's  это"), "whatsэто")
        self.assertEqual(norm.normalize("A"), norm.normalize("a"))
        self.assertEqual(norm.hashed_key("A"), norm.key_hash("a"))

    def test_extract_sources(self):
        src = tables.load_all(self.loc)["strings"]
        start = next(r for r in src if r["en"] == "Start the engine")
        self.assertEqual(start["src_lang"], "en")
        self.assertEqual(start["ru"], "Завести мотор")
        # англійскай няма — крыніца нямецкая (fallback_lang)
        german = next(r for r in src if r["de"] == "Nur Deutsch")
        self.assertEqual(german["src_lang"], "de")
        self.assertEqual(tables.effective_text(self.loc, german), "Nur Deutsch")
        # зусім без англійскай і нямецкай — апошняя крыніца RU, са сцягам у note
        ru_only = next(r for r in src if r["ru"] == "Толькі руская")
        self.assertEqual(ru_only["src_lang"], "ru")
        self.assertIn("крыніца: ru", ru_only["note"])
        # няма ніводнай крыніцы — радок ёсць, але перакладаць няма з чаго
        none = next(r for r in src if r["key"] == norm.hashed_key("nothing here"))
        self.assertEqual(none["src_lang"], "")
        self.assertEqual(tables.effective_text(self.loc, none), "")
        # key-like англійская пазначана ў ctx (наша заўвага, не тэкст гульні);
        # ctx — машыначытальныя ключы для пачак: at=, use=, q=, len=
        keylike = next(r for r in src if r["en"] == "onlykeylike")
        self.assertIn("q=keylike", keylike["ctx"])
        self.assertIn("use=en", keylike["ctx"])
        self.assertIn("len=11", keylike["ctx"])
        self.assertIn("прабелы страчаныя", keylike["ctx"])

    def test_apply_and_escape(self):
        self.set_bel("start the engine", "Завесці мотор")
        self.set_bel("text^ with comma", "Тэкст, з коскай")
        self.set_bel("only german", "Толькі нямецкая")
        self.set_bel("say it", "Скажы \"так\"")
        self.patch()
        with open(self.out_csv(), "rb") as f:
            raw = f.read()
        self.assertTrue(raw.startswith(b"KEY,ru-RU\n"))
        self.assertIn("Тэкст\x1f з коскай".encode("utf-8"), raw)      # коска → U+001F
        self.assertIn("Толькі нямецкая".encode("utf-8"), raw)
        self.assertIn(b'\xd0\xa1\xd0\xba\xd0\xb0\xd0\xb6\xd1\x8b ""'
                      b'\xd1\x82\xd0\xb0\xd0\xba""', raw)             # двукоссі → ""
        self.assertTrue(raw.endswith(b"\n"))
        header, rows, bad = table.read_rows(self.out_csv())
        self.assertEqual(header, "KEY,ru-RU")
        self.assertEqual([k for _, k, _ in rows], [k for k, _ in ROWS])
        self.assertEqual(rows[0][2], "")                              # пусты радок на месцы
        self.assertEqual(rows[3][2], "Тэкст, з коскай")
        self.assertEqual(rows[-1][2], "Скажы \"\"так\"\"")            # як у файле гульні
        self.assertEqual(bad, 0)

    def test_stale_german_source(self):
        self.set_bel("only german", "Толькі нямецкая")
        write_csv(os.path.join(self.game, CSV_DIR, "strings_de-DE.csv"), "KEY,de-DE",
                  [(k, "Neu" if k == "only german" else DE.get(k, "")) for k, _ in ROWS])
        log = self.patch()
        self.assertIn("арыгінал змяніўся ў 1", log)
        _, rows, _ = table.read_rows(self.out_csv())
        value = next(v for _, k, v in rows if k == "only german")
        self.assertEqual(value, "Толькі нямецкая")                    # арыгінал з гульні

    def test_ru_edge_case_hash(self):
        self.set_bel("no source at all", "Свой варыянт", lang="ru")
        key = norm.hashed_key("no source at all")
        repo = {r["key"]: r for r in tables.read_csv(tables.table_path(self.loc, "strings"))}
        self.assertEqual(repo[key]["src_hash"],
                         tables.src_hash("Зусім без крыніцы"))
        with redirect_stdout(io.StringIO()):
            tables.sync(self.loc)                                     # src_hash пазнаецца як RU
        repo = {r["key"]: r for r in tables.read_csv(tables.table_path(self.loc, "strings"))}
        self.assertEqual(repo[key]["bel"], "Свой варыянт")
        self.assertIn("крыніца: ru", repo[key]["note"])
        row = next(r for r in tables.load_all(self.loc)["strings"] if r["key"] == key)
        self.assertEqual(row["src_lang"], "ru")

    def test_subtitles(self):
        p = base.build_payload(self.loc, battletech_csv)
        self.assertEqual(p["subtitles"]["demo"],
                         ["Пераклад", "Пераклад\nдругі радок"])
        # --out: наш .srt побач з табліцай, гульня не чапаецца
        self.patch()
        out = os.path.join(self.tmp, "out", "demo-Russian.srt")
        self.assertTrue(os.path.exists(out))
        out_cues = subtitles.parse(out)
        self.assertEqual(out_cues[0][2], ["Пераклад"])
        self.assertEqual(out_cues[1][2], ["Пераклад", "другі радок"])
        self.assertFalse(os.path.exists(os.path.join(self.game, SUB_DIR,
                                                     "demo-Russian.srt.orig")))
        # у гульню: .orig/.bel, нумары і час з файла гульні, тэкст наш
        with redirect_stdout(io.StringIO()) as log:
            base.patch(self.loc, battletech_csv)
        self.assertIn("субтытры: запісана 1 файлаў", log.getvalue())
        self.assertTrue(battletech_csv.installed(self.loc.game_dir, p))
        game_srt = os.path.join(self.game, SUB_DIR, "demo-Russian.srt")
        self.assertTrue(os.path.exists(game_srt + ".orig"))
        self.assertTrue(os.path.exists(game_srt + ".bel"))
        cues = subtitles.parse(game_srt)
        self.assertEqual(cues[0][1], "00:00:01,000 --> 00:00:02,000")
        self.assertEqual(cues[0][2], ["Пераклад"])
        self.assertEqual(cues[1][2], ["Пераклад", "другі радок"])
        # restore: зноў рускі тэкст, .orig/.bel прыбраныя
        with redirect_stdout(io.StringIO()):
            base.restore(self.loc, battletech_csv)
        cues = subtitles.parse(game_srt)
        self.assertEqual(cues[0][2], ["Оригинал"])
        self.assertEqual(cues[1][2], ["Оригинал", "вторая строка"])
        self.assertFalse(os.path.exists(game_srt + ".orig"))
        self.assertFalse(battletech_csv.installed(self.loc.game_dir, p))

    def test_restore(self):
        self.set_bel("quit", "Выхад")
        with redirect_stdout(io.StringIO()):
            base.patch(self.loc, battletech_csv)                      # у гульню
        self.assertTrue(battletech_csv.installed(self.loc.game_dir,
                                                 base.build_payload(self.loc, battletech_csv)))
        _, rows, _ = table.read_rows(os.path.join(self.game, CSV_DIR, "strings_ru-RU.csv"))
        self.assertEqual(rows[2][2], "Выхад")
        with redirect_stdout(io.StringIO()):
            base.restore(self.loc, battletech_csv)
        _, rows, _ = table.read_rows(os.path.join(self.game, CSV_DIR, "strings_ru-RU.csv"))
        self.assertEqual(rows[2][2], "Выйсці")
        self.assertFalse(os.path.exists(os.path.join(self.game, CSV_DIR, "strings_ru-RU.csv.orig")))


if __name__ == "__main__":
    unittest.main()
