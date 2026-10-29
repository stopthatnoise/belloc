"""Файл гульні, які мы перапісваем: <файл>.orig і <файл>.bel побач.

  .orig — арыгінал; ЗАЎСЁДЫ бярэцца за аснову, таму ўсталёўку можна паўтараць
          колькі заўгодна, а restore вяртае ўсё як было;
  .bel  — SHA-256 таго, што мы запісалі. Калі файл у гульні ўжо іншы (Steam абнавіў
          гульню або праверыў цэласнасць), .orig састарэў: за аснову бярэцца бягучы
          файл, інакш патч адкаціў бы абнаўленне.

Рэжым праверкі (`out`): аснова чытаецца без пабочных эфектаў (source), вынік
пішацца ў іншае месца, гульня не чапаецца.
"""
from __future__ import annotations

import hashlib
import os
import shutil


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Target:
    def __init__(self, path: str):
        self.path, self.orig, self.mark = path, path + ".orig", path + ".bel"

    def ours(self) -> bool:
        """Ці ляжыць у гульні менавіта наш вынік."""
        if not (os.path.exists(self.mark) and os.path.exists(self.path)):
            return False
        with open(self.mark) as f:
            return f.read().strip() == sha256(self.path)

    def replaced(self) -> bool:
        """Steam падмяніў наш файл (абнаўленне, праверка цэласнасці): .orig састарэў."""
        return os.path.exists(self.mark) and not self.ours()

    def installed(self) -> bool:
        return os.path.exists(self.orig) and not self.replaced()

    def source(self) -> str:
        """Арыгінал для чытання, нічога не мяняючы: .orig, калі ён сапраўдны, інакш файл гульні."""
        return self.orig if self.installed() else self.path

    def base(self) -> str:
        """Арыгінал для патча ў гульні: сапраўдны .orig або свежая копія бягучага файла."""
        if self.installed():
            return self.orig
        if os.path.exists(self.orig):
            os.remove(self.orig)
            print("файл абноўлены Steam — стары .orig адкінуты:", os.path.basename(self.path))
        shutil.copyfile(self.path, self.orig)
        return self.orig

    def written(self):
        with open(self.mark, "w") as f:
            f.write(sha256(self.path))

    def restore(self) -> str:
        if self.installed():
            shutil.copyfile(self.orig, self.path)
            state = "вернуты арыгінал"
        elif os.path.exists(self.orig):
            state = "у гульні ўжо арыгінал (Steam абнавіў файл)"
        else:
            state = "пераклад не ўсталяваны"
        for p in (self.orig, self.mark):
            if os.path.exists(p):
                os.remove(p)
        return state


def write_to(target: Target, out_dir: str | None, write, name: str | None = None) -> str:
    """Запісаць файл: у гульню (з .orig і .bel) або, з out_dir, у іншую папку.

    write(base, dst) — чытае арыгінал base і піша вынік у dst.
    """
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        dst = os.path.join(out_dir, name or os.path.basename(target.path))
        write(target.source(), dst)
        return dst
    write(target.base(), target.path)
    target.written()
    return target.path
