"""Акно лаўнчара (PySide6) без экрана: спіс з каталога, усталёўка і выдаленне праз кнопкі.

    python -X utf8 -m unittest discover -s tests
"""
import io
import os
import sys
import time
import unittest
from contextlib import redirect_stdout

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "launcher"))

try:
    from PySide6.QtWidgets import QApplication, QMessageBox
except ImportError:                      # PySide6 — толькі для лаўнчара (extra "launcher")
    QApplication = None

from belloc.install import state  # noqa: E402
from belloc import steam  # noqa: E402
from test_launcher import Fixture, write_catalog_file  # noqa: E402


def wait(cond, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        QApplication.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


@unittest.skipIf(QApplication is None, "няма PySide6")
class AppTest(Fixture):
    def setUp(self):
        super().setUp()
        steam.cover = lambda appid: None        # вокладкі — з кэша Steam; у тэсце Steam не чытаем
        import app
        self.qapp = QApplication.instance() or QApplication([])
        self.answers = []
        QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
        QMessageBox.information = staticmethod(lambda *a, **k: self.answers.append(a[2]))
        QMessageBox.critical = QMessageBox.warning = staticmethod(lambda *a, **k: self.answers.append(a[2]))
        self.w = app.Window(self.cat, self.apps)
        self.w.load()
        self.assertTrue(wait(lambda: self.w.cards))

    def tearDown(self):
        self.w.close()
        super().tearDown()

    def idle(self):
        return wait(lambda: self.w.refresh_btn.isEnabled())

    def test_install_and_remove(self):
        card = self.w.cards[0]
        self.assertEqual(card.primary.text(), "Усталяваць")
        self.assertFalse(card.remove.isVisibleTo(card))
        with redirect_stdout(io.StringIO()):
            card.primary.click()
            self.assertTrue(self.idle())
        self.assertEqual(state.read(self.gamedir)["version"], "1.0")
        self.assertIn("версія 1.0", card.status.text())
        self.assertFalse(card.primary.isVisibleTo(card))          # усё стаіць — няма чаго ставіць
        self.assertTrue(card.remove.isVisibleTo(card))
        self.assertIn("Беларуская", self.answers[-1])
        with redirect_stdout(io.StringIO()):
            card.remove.click()
            self.assertTrue(self.idle())
        self.assertIsNone(state.read(self.gamedir))
        self.assertEqual(card.primary.text(), "Усталяваць")
        self.assertEqual(self.w.cat_cards[0].chip.text(), "Гульня ёсць — можна паставіць")

    def test_catalog_tab(self):
        w = self.w
        self.assertEqual(w.nav_cat.text(), "КАТАЛОГ  1")
        cc = w.cat_cards[0]
        self.assertEqual(cc.gid, "demo")
        self.assertEqual(cc.chip.text(), "Гульня ёсць — можна паставіць")
        w.nav_cat.click()
        self.assertEqual(w.pages.currentIndex(), 1)
        self.assertIn("Перакладаў у каталогу: 1", w.sub.text())
        cc.button.click()                                  # «У бібліятэку»
        self.assertEqual(w.pages.currentIndex(), 0)
        w.search.setText("няма такой")
        self.assertFalse(w.cards[0].isVisibleTo(w.list))
        w.search.setText("dem")
        self.assertTrue(w.cards[0].isVisibleTo(w.list))

    def test_update_offered(self):
        with redirect_stdout(io.StringIO()):
            self.w.cards[0].primary.click()
            self.assertTrue(self.idle())
        e = self.entry()
        self.write_catalog({**e, "version": "1.1", "changes": "выпраўленні"})
        self.w.load()
        self.assertTrue(wait(lambda: self.w.cards and self.w.cards[0].primary.text() == "Абнавіць да 1.1"))
        self.assertIn("Што новага: выпраўленні", self.w.cards[0].info.text())
        self.assertIn("абнаўленняў: 1", self.w.sub.text())

    def test_no_games_and_manual_folder(self):
        import app
        from PySide6.QtWidgets import QFileDialog
        w = app.Window(self.cat, {})                       # у Steam гульні няма
        w.load()
        self.assertTrue(wait(lambda: w.refresh_btn.isEnabled() and hasattr(w, "cat")))
        self.assertEqual(w.cards, [])
        self.assertEqual([c.gid for c in w.cat_cards], ["demo"])
        self.assertEqual(w.cat_cards[0].button.text(), "Старонка ў Steam")
        self.assertEqual(w.cat_cards[0].chip.text(), "Гульні няма на камп'ютары")
        texts = [lb.text() for lb in w.list.findChildren(app.QLabel)]
        self.assertIn("Пакуль няма гульняў з беларускім перакладам", texts)
        # гулец паказвае папку — гульня з'яўляецца ў «Вашы гульні» і застаецца пасля перазапуску
        QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: self.gamedir)
        w.pick_folder()
        self.assertTrue(wait(lambda: w.cards))
        self.assertEqual(w.cards[0].row["dir"], self.gamedir)
        w2 = app.Window(self.cat, {})
        w2.load()
        self.assertTrue(wait(lambda: w2.cards))
        w.close()
        w2.close()

    def test_empty_catalog(self):
        import app
        self.write_catalog_raw({"schema": 1, "games": {}})
        w = app.Window(self.cat, {})
        w.load()
        self.assertTrue(wait(lambda: w.refresh_btn.isEnabled() and hasattr(w, "cat")))
        texts = [lb.text() for lb in w.list.findChildren(app.QLabel)]
        self.assertIn("Каталог перакладаў пакуль пусты", texts)
        self.assertEqual(w.sub.text(), "У каталогу яшчэ няма перакладаў")
        w.close()

    def test_new_launcher_button(self):
        import app
        self.assertFalse(self.w.launcher_btn.isVisibleTo(self.w))
        page = "https://github.com/stopthatnoise/belloc/releases/tag/launcher-v9.9"
        self.write_catalog_raw({"schema": 1, "launcher": {"version": "9.9", "page": page},
                                "games": {"demo": self.entry()}})
        opened = []
        app.QDesktopServices.openUrl = staticmethod(lambda u: opened.append(u.toString()))
        self.w.load()
        self.assertTrue(wait(lambda: self.w.launcher_btn.isVisibleTo(self.w)))
        self.assertEqual(self.w.launcher_btn.text(), "Ёсць новы лаўнчар 9.9 — спампаваць")
        self.w.launcher_btn.click()
        self.assertEqual(opened, [page])

    def write_catalog_raw(self, cat):
        write_catalog_file(self.cat, cat)


if __name__ == "__main__":
    unittest.main()
