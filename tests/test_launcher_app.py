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
from test_launcher import Fixture  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
