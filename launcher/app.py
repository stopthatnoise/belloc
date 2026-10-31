"""Лаўнчар — акно (PySide6): гульні Steam з беларускім перакладам, паставіць / абнавіць / выдаліць.

Логіка — games.py (тая ж, што ў кансольным main.py); тут толькі інтэрфейс. Каталог і
сканаванне — у асобным патоку, усталёўка і выдаленне — у асобным працэсе (start_process),
журнал — унізе акна.
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
from PySide6.QtWidgets import (QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow,
                               QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSplitter, QVBoxLayout,
                               QWidget)

from belloc import catalog, steam

import games

TITLE = "Беларускія пераклады гульняў"
VERSION = "0.1"                         # версія лаўнчара (у загалоўку акна; каталог: "launcher")
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
#section { font-size: 14px; font-weight: 600; color: #555; margin-top: 8px; }
#empty { font-size: 17px; font-weight: 600; color: #333; margin-top: 24px; }
#other { background: #faf8f4; border: 1px dashed #d6d0c5; border-radius: 10px; }
#otherName { font-size: 14px; font-weight: 600; color: #444; }
QPushButton#link { border: none; background: transparent; color: #1a5fb4; text-align: left; padding: 6px 2px; }
QPushButton#link:hover { text-decoration: underline; }
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


class OtherCard(QFrame):
    """Пераклад ёсць, гульні на камп'ютары няма: што перакладзена і спасылка на краму."""

    def __init__(self, row: dict):
        super().__init__()
        self.row = row
        e = row["entry"]
        self.setObjectName("other")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        text = QVBoxLayout()
        text.setSpacing(2)
        name = QLabel(e["name"])
        name.setObjectName("otherName")
        info = QLabel(f"Пераклад {e['version']}" + (f" ад {catalog.show_date(e['date'])}" if e.get("date") else ""))
        info.setObjectName("sub")
        text.addWidget(name)
        text.addWidget(info)
        if e.get("contents"):
            about = QLabel(e["contents"])
            about.setObjectName("sub")
            about.setWordWrap(True)
            text.addWidget(about)
        lay.addLayout(text, 1)
        url = games.store_url(row.get("appid"))
        if url:
            self.store = QPushButton("Старонка ў Steam")
            self.store.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(url)))
            lay.addWidget(self.store, 0, Qt.AlignTop)


class Window(QMainWindow):
    def __init__(self, catalog_src: str = catalog.CATALOG_URL, apps: dict | None = None):
        super().__init__()
        self.catalog_src, self.apps = catalog_src, apps
        self.cards: list[Card] = []
        self.thread: QThread | None = None
        self.setWindowTitle(f"{TITLE} — лаўнчар {VERSION}")
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
            # з падстаўленым спісам гульняў (тэсты) Steam не правяраем
            steam_ok = True if self.apps is not None else games.steam_found()
            return cat, games.scan(cat, self.apps), steam_ok

        def failed(text, busy):
            self.refresh_btn.setEnabled(True)
            self.sub.setText("Каталог недаступны")
            self.show_error(text, busy)
        self.start(work, self.show_games, failed)

    def add(self, w: QWidget):
        self.list_lay.addWidget(w)

    def label(self, text: str, name: str, center=False) -> QLabel:
        lb = QLabel(text)
        lb.setObjectName(name)
        lb.setWordWrap(True)
        if center:
            lb.setAlignment(Qt.AlignCenter)
        return lb

    def show_games(self, result):
        cat, rows, steam_ok = result
        self.cat = cat
        self.refresh_btn.setEnabled(True)
        while self.list_lay.count():
            item = self.list_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        rest = games.others(cat, rows)
        self.cards = [Card(r, self) for r in rows]

        if not cat.get("games"):
            self.add(self.label("Каталог перакладаў пакуль пусты", "empty", True))
            self.add(self.label("Пераклады з'явяцца тут, як толькі выйдуць. Каб праверыць зноў — "
                                "«Абнавіць спіс».", "sub", True))
            self.list_lay.addStretch()
            self.sub.setText("У каталогу яшчэ няма перакладаў")
            return
        if not steam_ok and not rows:
            self.add(self.label("Steam не знойдзены", "empty", True))
            self.add(self.label("Лаўнчар шукае гульні ў бібліятэках Steam. Калі гульня ўсталявана "
                                "іначай — пакажыце яе папку.", "sub", True))
        elif not rows:
            self.add(self.label("Пакуль няма гульняў з беларускім перакладам", "empty", True))
            self.add(self.label("Ніводнай гульні з каталога няма на гэтым камп'ютары. Пераклады, "
                                "якія ёсць, — ніжэй.", "sub", True))
        else:
            self.add(self.label("Вашы гульні", "section"))
        for c in self.cards:
            self.add(c)
        if rest:
            self.add(self.label("Ёсць пераклад, але гульні няма на гэтым камп'ютары" if rows
                                else "Пераклады", "section"))
            for r in rest:
                self.add(OtherCard(r))
        folder = QPushButton("Гульня ўсталявана ў іншае месца? Пазначыць папку")
        folder.setObjectName("link")
        folder.setCursor(Qt.PointingHandCursor)
        folder.clicked.connect(self.pick_folder)
        self.add(folder)
        self.list_lay.addStretch()
        n_upd = sum(1 for r in rows if games.action(r) in ("update", "reinstall"))
        self.sub.setText(f"Знойдзена гульняў з перакладам: {len(rows)} з {len(cat.get('games', {}))}"
                         + (f" · абнаўленняў: {n_upd}" if n_upd else ""))

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
