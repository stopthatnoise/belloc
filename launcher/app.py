"""Лаўнчар — акно (PySide6): гульні Steam з беларускім перакладам, паставіць / абнавіць / выдаліць.

Логіка — games.py (тая ж, што ў кансольным main.py); тут толькі інтэрфейс. Доўгія
справы (каталог, сканаванне, усталёўка) ідуць у асобным патоку, журнал — унізе акна.
Вокладкі — з лакальнага кэша Steam (steam.cover), у сетку лаўнчар ходзіць толькі
па каталог і пакет перакладу.

    python launcher/app.py [--catalog <url|файл>]
"""
from __future__ import annotations

import argparse
import sys
import traceback

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
                               QPlainTextEdit, QPushButton, QScrollArea, QSplitter, QVBoxLayout, QWidget)

from belloc import catalog, steam

import games

TITLE = "Беларускія пераклады гульняў"
COVER_W, COVER_H = 230, 107

STYLE = """
QMainWindow, QScrollArea, #list { background: #f4f2ee; }
#card { background: white; border: 1px solid #e0dcd4; border-radius: 10px; }
#name { font-size: 16px; font-weight: 600; color: #222; }
#status { color: #555; }
#status[state="installed"] { color: #2e7d32; }
#status[state="wiped"] { color: #c62828; }
#note { color: #b26a00; }
#cover { background: #ddd8cf; border-radius: 6px; color: #888; }
QPushButton { padding: 6px 14px; border-radius: 6px; border: 1px solid #c9c3b8; background: #fbfaf7; }
QPushButton:hover { background: #f0ece4; }
QPushButton#primary { background: #c8102e; color: white; border: none; font-weight: 600; }
QPushButton#primary:hover { background: #a60d26; }
QPushButton:disabled { color: #aaa; background: #eee; }
#log { background: #1f1f1f; color: #ddd; font-family: Consolas, monospace; font-size: 12px; border: none; }
#header { font-size: 20px; font-weight: 600; color: #222; }
#sub { color: #777; }
"""

ACTION_LABEL = {"install": "Усталяваць", "update": "Абнавіць да {v}", "reinstall": "Паставіць нанова"}


class Job(QObject):
    """Справа ў асобным патоку: fn(log) → вынік; журнал — сігналам."""
    log = Signal(str)
    done = Signal(object)
    failed = Signal(str, bool)          # тэкст, ці гэта Busy (гульня запушчаная)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        try:
            self.done.emit(self.fn(self.log.emit))
        except games.Busy as e:
            self.failed.emit(str(e), True)
        except SystemExit as e:
            self.failed.emit(str(e), False)
        except Exception:
            self.failed.emit(traceback.format_exc(), False)


class Card(QFrame):
    def __init__(self, row: dict, window: "Window"):
        super().__init__()
        self.row, self.window = row, window
        self.setObjectName("card")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(14)

        cover = QLabel()
        cover.setObjectName("cover")
        cover.setFixedSize(COVER_W, COVER_H)
        cover.setAlignment(Qt.AlignCenter)
        path = steam.cover(row["appid"]) if row.get("appid") else None
        pix = QPixmap(path) if path else QPixmap()
        if not pix.isNull():
            cover.setPixmap(pix.scaled(COVER_W, COVER_H, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
        else:
            cover.setText(row["entry"]["name"])
            cover.setWordWrap(True)
        lay.addWidget(cover)

        text = QVBoxLayout()
        text.setSpacing(4)
        self.name = QLabel(row["entry"]["name"])
        self.name.setObjectName("name")
        self.status = QLabel()
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        self.info = QLabel()
        self.info.setObjectName("sub")
        self.info.setWordWrap(True)
        self.note = QLabel()
        self.note.setObjectName("note")
        self.note.setWordWrap(True)
        for w in (self.name, self.status, self.info, self.note):
            text.addWidget(w)
        text.addStretch()
        lay.addLayout(text, 1)

        buttons = QVBoxLayout()
        self.primary = QPushButton()
        self.primary.setObjectName("primary")
        self.primary.clicked.connect(lambda: window.run_action(self, "install"))
        self.remove = QPushButton("Выдаліць")
        self.remove.clicked.connect(lambda: window.run_action(self, "remove"))
        buttons.addWidget(self.primary)
        buttons.addWidget(self.remove)
        buttons.addStretch()
        lay.addLayout(buttons)
        self.update_view()

    def update_view(self):
        row, e = self.row, self.row["entry"]
        st = row["state"]
        status = f"Пераклад {games.LABELS[st]}"
        if st == "installed":
            status += f": версія {games.installed_version(row)}"
        self.status.setText(status)
        self.status.setProperty("state", st)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        info = f"У каталогу — версія {e['version']}" + (f" ад {e['date']}" if e.get("date") else "")
        if e.get("changes") and games.update_available(row):
            info += f"\nШто новага: {e['changes']}"
        self.info.setText(info)
        n = games.notes(row)
        self.note.setText("\n".join(n))
        self.note.setVisible(bool(n))
        act = games.action(row)
        self.primary.setVisible(act is not None)
        if act:
            self.primary.setText(ACTION_LABEL[act].format(v=e["version"]))
        self.remove.setVisible(st in ("installed", "unknown", "wiped"))

    def set_busy(self, busy: bool):
        self.primary.setEnabled(not busy)
        self.remove.setEnabled(not busy)


class Window(QMainWindow):
    def __init__(self, catalog_src: str = catalog.CATALOG_URL, apps: dict | None = None):
        super().__init__()
        self.catalog_src, self.apps = catalog_src, apps
        self.cards: list[Card] = []
        self.thread: QThread | None = None
        self.setWindowTitle(TITLE)
        self.resize(820, 640)
        self.setStyleSheet(STYLE)

        top = QWidget()
        head = QHBoxLayout(top)
        head.setContentsMargins(16, 12, 16, 4)
        titles = QVBoxLayout()
        h = QLabel(TITLE)
        h.setObjectName("header")
        self.sub = QLabel("Шукаю гульні…")
        self.sub.setObjectName("sub")
        titles.addWidget(h)
        titles.addWidget(self.sub)
        head.addLayout(titles, 1)
        self.refresh_btn = QPushButton("Абнавіць спіс")
        self.refresh_btn.clicked.connect(self.load)
        head.addWidget(self.refresh_btn)

        self.list = QWidget()
        self.list.setObjectName("list")
        self.list_lay = QVBoxLayout(self.list)
        self.list_lay.setContentsMargins(16, 8, 16, 16)
        self.list_lay.setSpacing(10)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(self.list)

        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("log")
        self.log_view.setReadOnly(True)

        split = QSplitter(Qt.Vertical)
        split.addWidget(scroll)
        split.addWidget(self.log_view)
        split.setStretchFactor(0, 4)
        split.setStretchFactor(1, 1)
        split.setSizes([520, 110])

        body = QWidget()
        v = QVBoxLayout(body)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(top)
        v.addWidget(split, 1)
        self.setCentralWidget(body)
        self.statusBar().showMessage("Нейрапераклад: мадэль Claude (Anthropic). Кіраўнік праекта: Віталь Аляхновіч.")

    # ------------------------------------------------------------ фон
    def start(self, fn, on_done, on_failed=None):
        self.thread = QThread()
        self.job = Job(fn)
        self.job.moveToThread(self.thread)
        self.thread.started.connect(self.job.run)
        self.job.log.connect(self.log)
        self.job.done.connect(on_done)
        self.job.failed.connect(on_failed or self.show_error)
        for sig in (self.job.done, self.job.failed):
            sig.connect(self.thread.quit)
        self.thread.start()

    def log(self, text: str):
        self.log_view.appendPlainText(text)

    def show_error(self, text: str, busy: bool = False):
        self.log(text)
        (QMessageBox.warning if busy else QMessageBox.critical)(self, TITLE, text.strip().splitlines()[-1])

    # ------------------------------------------------------------ спіс
    def load(self):
        self.refresh_btn.setEnabled(False)
        self.sub.setText("Загружаю каталог перакладаў і шукаю гульні Steam…")

        def work(log):
            cat = catalog.fetch(self.catalog_src)
            if cat is None:
                raise SystemExit("Не атрымалася загрузіць каталог перакладаў — праверце інтэрнэт.")
            return cat, games.scan(cat, self.apps)

        def failed(text, busy):
            self.refresh_btn.setEnabled(True)
            self.sub.setText("Каталог недаступны")
            self.show_error(text, busy)
        self.start(work, self.show_games, failed)

    def show_games(self, result):
        cat, rows = result
        self.refresh_btn.setEnabled(True)
        for c in self.cards:
            c.deleteLater()
        while self.list_lay.count():
            item = self.list_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.cards = [Card(r, self) for r in rows]
        for c in self.cards:
            self.list_lay.addWidget(c)
        if not rows:
            names = ", ".join(e["name"] for e in cat.get("games", {}).values()) or "—"
            empty = QLabel(f"На гэтым камп'ютары не знайшлося гульняў Steam з беларускім перакладам.\n\n"
                           f"Пераклады ёсць для: {names}")
            empty.setObjectName("sub")
            empty.setWordWrap(True)
            empty.setAlignment(Qt.AlignCenter)
            self.list_lay.addWidget(empty)
        self.list_lay.addStretch()
        n_upd = sum(1 for r in rows if games.action(r) in ("update", "reinstall"))
        self.sub.setText(f"Знойдзена гульняў з перакладам: {len(rows)}"
                         + (f" · абнаўленняў: {n_upd}" if n_upd else ""))

    # ------------------------------------------------------------ дзеянні
    def run_action(self, card: Card, what: str):
        e = card.row["entry"]
        if what == "install":
            q = (f"{e['name']} {e['version']}: пераклад ставіцца замест мовы «{e['replaces']}» — "
                 f"пакуль ён усталяваны, гэтай мовы ў гульні не будзе.\n\nУсталяваць?")
            fn = games.install
        else:
            q = f"Выдаліць пераклад {e['name']} і вярнуць арыгінальныя файлы гульні?"
            fn = games.remove
        if QMessageBox.question(self, TITLE, q) != QMessageBox.Yes:
            return
        for c in self.cards:
            c.set_busy(True)
        self.refresh_btn.setEnabled(False)
        self.log(f"— {e['name']}: {'усталёўка' if what == 'install' else 'выдаленне'}")

        def finish():
            for c in self.cards:
                c.set_busy(False)
            self.refresh_btn.setEnabled(True)
            card.update_view()

        def done(_):
            finish()
            if what == "install":
                QMessageBox.information(self, TITLE, f"Гатова. У гульні выберыце мову «{e['language_name']}».")

        def failed(text, busy):
            finish()
            self.show_error(text, busy)
        self.start(lambda log: fn(card.row, log), done, failed)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=TITLE)
    ap.add_argument("--catalog", default=catalog.CATALOG_URL)
    args = ap.parse_args(argv)
    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    w = Window(args.catalog)
    w.show()
    w.load()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
