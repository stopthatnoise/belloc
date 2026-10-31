"""Ці запушчаная гульня: па імені exe і шляху працэсу (Windows)."""
from __future__ import annotations

import os
import subprocess


def process_path(pid: int) -> str | None:
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(0x1000, False, pid)        # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return None
        try:
            buf, size = ctypes.create_unicode_buffer(32768), wintypes.DWORD(32768)
            return buf.value if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)) else None
        finally:
            k32.CloseHandle(h)
    except Exception:
        return None


def tasklist() -> str:
    """Поўны шлях: голае "tasklist" Windows шукае і ў папцы exe (напр. «Спампоўкі»
    побач з усталёўшчыкам), а там можа ляжаць чужы tasklist.exe."""
    return os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "tasklist.exe")


def game_running(exe: str, game: str) -> bool:
    """Ці запушчаная гульня з гэтага каталога (копія ў іншым месцы не замінае).
    Калі шлях працэсу не ўдалося даведацца — лічым, што запушчаная."""
    try:
        # вывад — у кодавай старонцы OEM (памяць з неразрыўным прабелам): патрэбныя толькі імя і PID
        out = subprocess.run([tasklist(), "/FO", "CSV", "/NH", "/FI", f"IMAGENAME eq {exe}"],
                             capture_output=True, timeout=10).stdout.decode("ascii", "replace")
    except Exception:
        return False
    root = os.path.normcase(os.path.abspath(game)) + os.sep
    for line in out.splitlines():
        cols = [c.strip('"') for c in line.split('","')]
        if len(cols) < 2 or cols[0].lower() != exe.lower() or not cols[1].isdigit():
            continue
        path = process_path(int(cols[1]))
        if path is None or os.path.normcase(os.path.abspath(path)).startswith(root):
            return True
    return False
