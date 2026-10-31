"""Лаўнчар — акно (PySide6): бібліятэка (гульні на камп'ютары) і каталог перакладаў.

Уверсе — цёмная панэль: «Бібліятэка» / «Каталог», пошук, абнаўленне спісу. Бібліятэка —
гульні Steam (і папкі, пазначаныя ўручную) з перакладам: паставіць / абнавіць / выдаліць.
Каталог — усе пераклады і іх стан на гэтым камп'ютары. Унізе — журнал.

Логіка — games.py (тая ж, што ў кансольным main.py); тут толькі інтэрфейс. Каталог і
сканаванне — у асобным патоку, усталёўка і выдаленне — у асобным працэсе (start_process).
Вокладкі — з лакальнага кэша Steam (steam.cover), у сетку лаўнчар ходзіць толькі
па каталог і пакет перакладу.

    python launcher/app.py [--catalog <url|файл>]
"""
from __future__ import annotations

import argparse
import multiprocessing
import queue
import sys
import traceback

from PySide6.QtCore import QObject, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (QApplication, QButtonGroup, QFileDialog, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea,
                               QSplitter, QStackedWidget, QVBoxLayout, QWidget)

from belloc import catalog, steam

import games

TITLE = "Беларускія пераклады гульняў"
VERSION = "0.1"                         # версія лаўнчара (у загалоўку акна; каталог: "launcher")
COVER_W, COVER_H = 230, 107             # прапорцыі header.jpg Steam (460×215)

# цёмная тэма ў духу Steam; акцэнт брэнда — чырвоны квадрат у назве
STYLE = """
QMainWindow, #page, QScrollArea { background: #1b2838; }
QWidget { color: #c7d5e0; font-size: 13px; }
#topbar { background: #171a21; }
#brand { color: #ffffff; font-size: 15px; font-weight: 700; letter-spacing: 1px; }
#brandMark { background: #c8102e; border-radius: 2px; }
QPushButton#nav { background: transparent; border: none; border-bottom: 3px solid transparent;
                  color: #8f98a0; font-size: 13px; font-weight: 700; letter-spacing: 1px;
                  padding: 14px 10px 11px 10px; border-radius: 0; }
QPushButton#nav:hover { color: #ffffff; }
QPushButton#nav:checked { color: #ffffff; border-bottom: 3px solid #1a9fff; }
QLineEdit#search { background: #2a3f5a; border: 1px solid #2a3f5a; border-radius: 4px; color: #ffffff;
                   padding: 5px 10px; min-width: 200px; }
QLineEdit#search:focus { border: 1px solid #1a9fff; }
QPushButton#icon { background: #2a3f5a; border: none; border-radius: 4px; color: #ffffff; font-size: 16px;
                   min-width: 32px; min-height: 28px; padding: 0; }
QPushButton#icon:hover { background: #3d5a80; }
#subbar { background: #1b2838; }
#sub { color: #8f98a0; }
#section { color: #8f98a0; font-size: 12px; font-weight: 700; letter-spacing: 1px; margin-top: 6px; }
#empty { color: #ffffff; font-size: 18px; font-weight: 600; margin-top: 30px; }
#card { background: #16202d; border-radius: 6px; }
#card:hover { background: #1e2b3a; }
#name { color: #ffffff; font-size: 16px; font-weight: 600; }
#status { color: #8f98a0; }
#status[state="installed"], #status[state="unknown"] { color: #a1cd44; }
#status[state="wiped"] { color: #e05a5a; }
#note { color: #d9a441; }
#cover { background: #0e141b; border-radius: 4px; color: #556772; font-weight: 600; }
#chip { border-radius: 3px; padding: 2px 8px; font-size: 11px; font-weight: 700; background: #2a3f5a; color: #8f98a0; }
#chip[state="installed"] { background: #4c6b22; color: #d2efa9; }
#chip[state="update"] { background: #1a9fff; color: #ffffff; }
#chip[state="wiped"] { background: #6e2b2b; color: #f3c0c0; }
#chip[state="available"] { background: #3d5a80; color: #ffffff; }
QPushButton { background: #3d4450; color: #dfe3e6; border: none; border-radius: 3px; padding: 7px 16px; }
QPushButton:hover { background: #4c5563; }
QPushButton#primary { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #75b022, stop:1 #588a1b);
                      color: #ffffff; font-weight: 700; }
QPushButton#primary:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8ed629, stop:1 #6aa621); }
QPushButton:disabled, QPushButton#primary:disabled { background: #2a2f38; color: #5d6670; }
QPushButton#link { background: transparent; color: #66c0f4; text-align: left; padding: 6px 2px; }
QPushButton#link:hover { color: #ffffff; }
QScrollBar:vertical { background: #1b2838; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #3d4450; border-radius: 5px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QSplitter::handle { background: #171a21; height: 4px; }
#log { background: #0e0e0e; color: #c7d5e0; font-family: Consolas, monospace; font-size: 12px; border: none; }
QStatusBar { background: #171a21; color: #8f98a0; }
QMessageBox { background: #1b2838; }
QMessageBox QLabel { color: #c7d5e0; }
"""

ACTION_LABEL = {"install": "Усталяваць", "update": "Абнавіць да {v}", "reinstall": "Паставіць нанова"}


def cover_label(appid, name: str, w: int = COVER_W, h: int = COVER_H) -> QLabel:
    """Вокладка з лакальнага кэша Steam або назва на цёмным фоне."""
    cover = QLabel()
    cover.setObjectName("cover")
    cover.setFixedSize(w, h)
    cover.setAlignment(Qt.AlignCenter)
    path = steam.cover(appid) if appid else None
    pix = QPixmap(path) if path else QPixmap()
    if not pix.isNull():
        cover.setPixmap(pix.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
    else:
        cover.setText(name)
        cover.setWordWrap(True)
    return cover


def repolish(w: QWidget, state: str):
    """Змяніць уласцівасць state і перамаляваць па стылях (#status[state=…], #chip[state=…])."""
    w.setProperty("state", state)
    w.style().unpolish(w)
    w.style().polish(w)


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
    """Гульня ў бібліятэцы: стан перакладу і кнопкі."""

    def __init__(self, row: dict, window: "Window"):
        super().__init__()
        self.row, self.window = row, window
        self.setObjectName("card")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 12, 14, 12)
        lay.setSpacing(16)
        lay.addWidget(cover_label(row.get("appid"), row["entry"]["name"]))

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
        self.primary.setCursor(Qt.PointingHandCursor)
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
        repolish(self.status, st)
        info = f"У каталогу — версія {e['version']}" + (f" ад {catalog.show_date(e['date'])}" if e.get("date") else "")
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


def catalog_state(row: dict | None) -> tuple[str, str]:
    """(state, тэкст) пазнакі ў каталогу: што з гэтым перакладам на камп'ютары."""
    if row is None:
        return "absent", "Гульні няма на камп'ютары"
    if row["state"] == "installed":
        if games.update_available(row):
            return "update", "Ёсць абнаўленне"
        return "installed", f"Усталявана · {games.installed_version(row)}"
    if row["state"] == "unknown":
        return "installed", "Усталявана"
    if row["state"] == "wiped":
        return "wiped", "Зляцеў пасля абнаўлення гульні"
    return "available", "Гульня ёсць — можна паставіць"


class CatalogCard(QFrame):
    """Пераклад з каталога: што перакладзена, версія, стан на камп'ютары."""

    def __init__(self, gid: str, e: dict, row: dict | None, window: "Window"):
        super().__init__()
        self.gid, self.row = gid, row
        self.setObjectName("card")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 12, 14, 12)
        lay.setSpacing(16)
        appid = e.get("stores", {}).get("steam")
        lay.addWidget(cover_label(appid, e["name"], 184, 86))

        text = QVBoxLayout()
        text.setSpacing(4)
        head = QHBoxLayout()
        name = QLabel(e["name"])
        name.setObjectName("name")
        head.addWidget(name)
        state, label = catalog_state(row)
        self.chip = QLabel(label)
        self.chip.setObjectName("chip")
        repolish(self.chip, state)
        head.addWidget(self.chip)
        head.addStretch()
        text.addLayout(head)
        ver = QLabel(f"Версія {e['version']}" + (f" ад {catalog.show_date(e['date'])}" if e.get("date") else "")
                     + (f" · што новага: {e['changes']}" if e.get("changes") else ""))
        ver.setObjectName("sub")
        ver.setWordWrap(True)
        text.addWidget(ver)
        if e.get("contents"):
            about = QLabel(e["contents"])
            about.setWordWrap(True)
            text.addWidget(about)
        text.addStretch()
        lay.addLayout(text, 1)

        if row is not None:
            self.button = QPushButton("У бібліятэку")
            self.button.clicked.connect(lambda: window.show_in_library(gid))
        else:
            url = games.store_url(appid)
            self.button = QPushButton("Старонка ў Steam")
            self.button.setEnabled(bool(url))
            self.button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(url)))
        lay.addWidget(self.button, 0, Qt.AlignTop)


class Window(QMainWindow):
    def __init__(self, catalog_src: str = catalog.CATALOG_URL, apps: dict | None = None):
        super().__init__()
        self.catalog_src, self.apps = catalog_src, apps
        self.cards: list[Card] = []
        self.cat_cards: list[CatalogCard] = []
        self.thread: QThread | None = None
        self.setWindowTitle(f"{TITLE} — лаўнчар {VERSION}")
        self.resize(900, 680)
        self.setStyleSheet(STYLE)

        # --- верхняя панэль
        top = QFrame()
        top.setObjectName("topbar")
        bar = QHBoxLayout(top)
        bar.setContentsMargins(18, 0, 14, 0)
        bar.setSpacing(6)
        mark = QFrame()
        mark.setObjectName("brandMark")
        mark.setFixedSize(10, 18)
        brand = QLabel("БЕЛАРУСКІЯ ПЕРАКЛАДЫ")
        brand.setObjectName("brand")
        bar.addWidget(mark)
        bar.addWidget(brand)
        bar.addSpacing(26)
        self.nav = QButtonGroup(self)
        self.nav_lib = self.nav_button("БІБЛІЯТЭКА", 0, bar)
        self.nav_cat = self.nav_button("КАТАЛОГ", 1, bar)
        self.nav_lib.setChecked(True)
        bar.addStretch()
        self.search = QLineEdit()
        self.search.setObjectName("search")
        self.search.setPlaceholderText("Пошук гульні")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.apply_filter)
        bar.addWidget(self.search)
        self.refresh_btn = QPushButton("⟳")
        self.refresh_btn.setObjectName("icon")
        self.refresh_btn.setToolTip("Абнавіць спіс")
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.load)
        bar.addWidget(self.refresh_btn)

        sub = QFrame()
        sub.setObjectName("subbar")
        sl = QHBoxLayout(sub)
        sl.setContentsMargins(20, 10, 20, 2)
        self.sub = QLabel("Шукаю гульні…")
        self.sub.setObjectName("sub")
        sl.addWidget(self.sub)

        # --- старонкі: бібліятэка і каталог
        self.pages = QStackedWidget()
        self.list, self.list_lay, lib_scroll = self.page()
        self.catalog_list, self.cat_lay, cat_scroll = self.page()
        self.lib_scroll = lib_scroll
        self.pages.addWidget(lib_scroll)
        self.pages.addWidget(cat_scroll)
        self.nav.idClicked.connect(self.switch)

        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("log")
        self.log_view.setReadOnly(True)
        split = QSplitter(Qt.Vertical)
        split.addWidget(self.pages)
        split.addWidget(self.log_view)
        split.setStretchFactor(0, 4)
        split.setStretchFactor(1, 1)
        split.setSizes([540, 110])

        body = QWidget()
        v = QVBoxLayout(body)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(top)
        v.addWidget(sub)
        v.addWidget(split, 1)
        self.setCentralWidget(body)
        self.statusBar().showMessage("Нейрапераклад: мадэль Claude (Anthropic). Кіраўнік праекта: Віталь Аляхновіч.")

    def nav_button(self, text: str, idx: int, bar: QHBoxLayout) -> QPushButton:
        b = QPushButton(text)
        b.setObjectName("nav")
        b.setCheckable(True)
        b.setCursor(Qt.PointingHandCursor)
        self.nav.addButton(b, idx)
        bar.addWidget(b)
        return b

    def page(self):
        w = QWidget()
        w.setObjectName("page")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20, 10, 20, 20)
        lay.setSpacing(10)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(w)
        return w, lay, scroll

    def switch(self, idx: int):
        self.pages.setCurrentIndex(idx)
        (self.nav_lib if idx == 0 else self.nav_cat).setChecked(True)
        self.update_sub()

    def show_in_library(self, gid: str):
        self.search.clear()
        self.switch(0)
        card = next((c for c in self.cards if c.row["id"] == gid), None)
        if card:
            self.lib_scroll.ensureWidgetVisible(card)

    def apply_filter(self, text: str = ""):
        q = (text or self.search.text()).strip().casefold()
        for c in self.cards:
            c.setVisible(q in c.row["entry"]["name"].casefold())
        for c in self.cat_cards:
            c.setVisible(q in self.cat["games"][c.gid]["name"].casefold())

    def update_sub(self):
        cat = getattr(self, "cat", None)
        if cat is None:
            return
        n_all, rows = len(cat.get("games", {})), [c.row for c in self.cards]
        if not n_all:
            self.sub.setText("У каталогу яшчэ няма перакладаў")
        elif self.pages.currentIndex() == 0:
            n_upd = sum(1 for r in rows if games.action(r) in ("update", "reinstall"))
            self.sub.setText(f"Знойдзена гульняў з перакладам: {len(rows)} з {n_all}"
                             + (f" · абнаўленняў: {n_upd}" if n_upd else ""))
        else:
            self.sub.setText(f"Перакладаў у каталогу: {n_all} · на гэтым камп'ютары: {len(rows)}")

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
            # з падстаўленым спісам гульняў (тэсты) Steam не правяраем
            steam_ok = True if self.apps is not None else games.steam_found()
            return cat, games.scan(cat, self.apps), steam_ok

        def failed(text, busy):
            self.refresh_btn.setEnabled(True)
            self.sub.setText("Каталог недаступны")
            self.show_error(text, busy)
        self.start(work, self.show_games, failed)

    def label(self, text: str, name: str, center=False) -> QLabel:
        lb = QLabel(text)
        lb.setObjectName(name)
        lb.setWordWrap(True)
        if center:
            lb.setAlignment(Qt.AlignCenter)
        return lb

    @staticmethod
    def clear(lay):
        while lay.count():
            item = lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def show_games(self, result):
        cat, rows, steam_ok = result
        self.cat = cat
        self.refresh_btn.setEnabled(True)
        self.clear(self.list_lay)
        self.clear(self.cat_lay)
        self.cards = [Card(r, self) for r in rows]
        by_id = {r["id"]: r for r in rows}
        self.cat_cards = [CatalogCard(gid, e, by_id.get(gid), self)
                          for gid, e in sorted(cat.get("games", {}).items(), key=lambda x: x[1].get("name", x[0]))]

        # бібліятэка
        lib = self.list_lay
        if not cat.get("games"):
            lib.addWidget(self.label("Каталог перакладаў пакуль пусты", "empty", True))
            lib.addWidget(self.label("Пераклады з'явяцца тут, як толькі выйдуць. Каб праверыць зноў — "
                                     "кнопка ⟳ уверсе.", "sub", True))
        elif not rows:
            lib.addWidget(self.label("Steam не знойдзены" if not steam_ok
                                     else "Пакуль няма гульняў з беларускім перакладам", "empty", True))
            lib.addWidget(self.label(
                "Лаўнчар шукае гульні ў бібліятэках Steam. Калі гульня ўсталявана іначай — пакажыце яе папку."
                if not steam_ok else
                f"Ніводнай гульні з каталога няма на гэтым камп'ютары. У каталогу — перакладаў: "
                f"{len(cat['games'])}.", "sub", True))
            to_cat = QPushButton("Глядзець каталог")
            to_cat.setObjectName("primary")
            to_cat.clicked.connect(lambda: self.switch(1))
            row_l = QHBoxLayout()
            row_l.addStretch()
            row_l.addWidget(to_cat)
            row_l.addStretch()
            lib.addLayout(row_l)
        else:
            lib.addWidget(self.label("ВАШЫ ГУЛЬНІ", "section"))
        for c in self.cards:
            lib.addWidget(c)
        if cat.get("games"):
            folder = QPushButton("Гульня ўсталявана ў іншае месца? Пазначыць папку")
            folder.setObjectName("link")
            folder.setCursor(Qt.PointingHandCursor)
            folder.clicked.connect(self.pick_folder)
            lib.addWidget(folder)
        lib.addStretch()

        # каталог
        if not cat.get("games"):
            self.cat_lay.addWidget(self.label("Каталог перакладаў пакуль пусты", "empty", True))
        else:
            self.cat_lay.addWidget(self.label("УСЕ ПЕРАКЛАДЫ", "section"))
        for c in self.cat_cards:
            self.cat_lay.addWidget(c)
        self.cat_lay.addStretch()

        self.nav_lib.setText(f"БІБЛІЯТЭКА  {len(rows)}" if rows else "БІБЛІЯТЭКА")
        self.nav_cat.setText(f"КАТАЛОГ  {len(cat.get('games', {}))}" if cat.get("games") else "КАТАЛОГ")
        self.apply_filter()
        self.update_sub()

    def pick_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Папка гульні")
        if not folder:
            return
        found = games.match_folder(getattr(self, "cat", {}), folder)
        if not found:
            QMessageBox.warning(self, TITLE, "У гэтай папцы не знайшлося гульні, для якой ёсць пераклад.\n"
                                "Пакажыце галоўную папку гульні — тую, дзе ляжыць яе exe.")
            return
        for gid in found:
            games.remember(gid, folder)
            self.log(f"Папка {folder} — {self.cat['games'][gid]['name']}")
        self.load()

    # ------------------------------------------------------------ дзеянні
    def run_action(self, card: Card, what: str):
        e = card.row["entry"]
        if what == "install":
            q = (f"{e['name']} {e['version']}: пераклад ставіцца замест мовы «{e['replaces']}» — "
                 f"пакуль ён усталяваны, гэтай мовы ў гульні не будзе.\n\nУсталяваць?" if e.get("replaces")
                 else f"{e['name']} {e['version']}: усталяваць пераклад?")
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
            for cc in self.cat_cards:          # пазнака ў каталогу — па новым стане
                if cc.gid == card.row["id"]:
                    state, text = catalog_state(card.row)
                    cc.chip.setText(text)
                    repolish(cc.chip, state)
            self.update_sub()

        def done(_):
            finish()
            if what == "install":
                QMessageBox.information(self, TITLE, f"Гатова. У гульні выберыце мову «{e['language_name']}».")

        def failed(text, busy):
            finish()
            self.show_error(text, busy)
        self.start_process(what, card, done, failed)

    def start_process(self, what: str, card: Card, on_done, on_failed):
        """Усталёўка і выдаленне — у асобным працэсе: UnityPy і сціск трымаюць GIL
        секундамі, і акно ў патоку таго ж працэсу «не адказвала» б; а падзенне рухавіка
        не кране лаўнчар. Журнал і вынік прыходзяць праз чаргу, акно правярае яе таймерам."""
        ctx = multiprocessing.get_context("spawn")
        q = ctx.Queue()
        proc = ctx.Process(target=work_process, args=(what, card.row, q), daemon=True)
        proc.start()
        timer = QTimer(self)

        def poll():
            while True:
                try:
                    kind, val = q.get_nowait()
                except queue.Empty:
                    break
                if kind == "log":
                    self.log(val)
                    continue
                timer.stop()
                proc.join(5)
                if kind == "done":
                    card.row.update(val)
                    on_done(val)
                else:
                    on_failed(val, kind == "busy")
                return
            if not proc.is_alive():
                timer.stop()
                on_failed(f"Працэс усталёўкі нечакана спыніўся (код {proc.exitcode}).", False)
        timer.timeout.connect(poll)
        timer.start(100)


def ping(q):
    from belloc import engines
    q.put(f"ok ({len(engines.ENGINES)} рухавікоў)")


def work_process(what: str, row: dict, q):
    """Цела асобнага працэсу: games.install / remove, журнал і вынік — у чаргу."""
    try:
        (games.install if what == "install" else games.remove)(row, lambda s: q.put(("log", s)))
        q.put(("done", {"state": row["state"], "mark": row["mark"]}))
    except games.Busy as e:
        q.put(("busy", str(e)))
    except SystemExit as e:
        q.put(("error", str(e)))
    except Exception:
        q.put(("error", traceback.format_exc()))


def selftest(out: str, catalog_src: str) -> int:
    """Праверка сабранага exe: усе рухавікі імпартуюцца, акно будуецца, каталог чытаецца.
    Вынік — out.txt і здымак акна out.png (exe без кансолі — друкаваць няма куды)."""
    import importlib
    import time
    from belloc import engines
    lines = []
    for name, mod in engines.ENGINES.items():
        try:
            importlib.import_module(f"belloc.engines.{mod}.apply")
            lines.append(f"{name}: ok")
        except Exception as e:
            lines.append(f"{name}: ПАМЫЛКА {type(e).__name__}: {e}")
    # бібліятэкі, якія рухавікі грузяць толькі падчас усталёўкі
    for lib in ("UnityPy", "cv2", "ooz", "Crypto.Cipher.AES", "lz4.block", "numpy", "PIL.Image",
                "fontTools.ttLib", "etcpak", "texture2ddecoder"):
        try:
            importlib.import_module(lib)
            lines.append(f"{lib}: ok")
        except Exception as e:
            lines.append(f"{lib}: ПАМЫЛКА {type(e).__name__}: {e}")
    # дачынны працэс (усталёўка ідзе ў ім): у exe яго запускае сам exe праз freeze_support
    ctx = multiprocessing.get_context("spawn")
    q = ctx.Queue()
    proc = ctx.Process(target=ping, args=(q,), daemon=True)
    proc.start()
    try:
        lines.append(f"працэс усталёўкі: {q.get(timeout=60)}")
    except queue.Empty:
        lines.append("працэс усталёўкі: ПАМЫЛКА — не адказаў")
    proc.join(10)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    w = Window(catalog_src, {})
    w.resize(860, 640)
    w.show()
    w.load()
    end = time.time() + 30
    while time.time() < end and not hasattr(w, "cat"):
        app.processEvents()
        time.sleep(0.05)
    app.processEvents()
    lines.append(f"каталог: {len(getattr(w, 'cat', {}).get('games', {}))} гульняў" if hasattr(w, "cat")
                 else "каталог: не загрузіўся")
    w.grab().save(out + ".png")
    with open(out + ".txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return 0 if all("ПАМЫЛКА" not in x for x in lines) and hasattr(w, "cat") else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=TITLE)
    ap.add_argument("--catalog", default=catalog.CATALOG_URL)
    ap.add_argument("--selftest", metavar="OUT", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest(args.selftest, args.catalog)
    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    w = Window(args.catalog)
    w.show()
    w.load()
    return app.exec()


if __name__ == "__main__":
    multiprocessing.freeze_support()        # exe: дачынны працэс усталёўкі запускае гэты ж exe
    sys.exit(main())
