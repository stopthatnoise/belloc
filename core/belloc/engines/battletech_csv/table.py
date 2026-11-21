"""Чытанне і запіс табліцы гульні `strings_<культура>.csv`.

Фармат (CSVHelper у гульні):
  * дзве калонкі без двукоссяў: `KEY,<культура>`, загаловак — першы радок;
  * канец радка — `\n`, кадаванне UTF-8 без BOM;
  * коска ў тэксце захавана як `U+001F` (адзін сімвал), у гульні вяртаецца ў `,`;
  * перанос радка ў тэксце — два сімвалы `\\n` (не сапраўдны перанос);
  * радок з іншай колькасцю калонак гульня адкідае з памылкай у лог.

Таму чытанне ідзе па радках і дзеліць па **першай** косцы; запіс кадуе коскі ў
`U+001F` і сапраўдныя пераносы — у `\\n`. Парадак і колькасць радкоў захоўваюцца.
"""
from __future__ import annotations


def read_rows(path: str) -> tuple[str, list[tuple[int, str, str]], int]:
    """(загаловак, [(нумар радка, ключ, тэкст)], колькасць бітых радкоў).

    Тэкст вяртаецца з `U+001F` → `,` (як яго бачыць гулец); пустыя радкі і
    пустыя ключы застаюцца — іх трэба запісаць на тое ж месца.
    """
    with open(path, "rb") as f:
        text = f.read().decode("utf-8-sig")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    if not lines:
        return "", [], 0
    rows, bad = [], 0
    for n, line in enumerate(lines[1:], 2):
        key, sep, value = line.partition(",")
        if not sep:
            bad += 1
            continue
        rows.append((n, key, value.replace("\x1f", ",")))
    return lines[0], rows, bad


def escape(value: str) -> str:
    """Наш тэкст → клетка табліцы: сапраўдныя пераносы ў `\\n`, коскі ў `U+001F`."""
    value = value.replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")
    return value.replace(",", "\x1f")


def write_rows(path: str, header: str, rows: list[tuple[str, str]]):
    """Запісаць табліцу цалкам: загаловак, радкі ў тым жа парадку, `\n`, UTF-8."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(header + "\n")
        for key, value in rows:
            f.write(f"{key},{value}\n")
