"""Аб'ём тэксту 007 First Light: LOCR (інтэрфейс) і DLGE (субтытры), англійская.

    python -X utf8 games/007-first-light/research/count.py "D:/…/Runtime"

~5 хв (42 тыс. DLGE, XTEA на чыстым Python).
"""
import collections
import re
import sys
from pathlib import Path

from glacier import LANGS, dlge_texts, parse_locr, read_index, read_res, visible

W = lambda s: len(re.findall(r'\w+', s))
rt = Path(sys.argv[1])
locr_en, dlge_en = [], []
types = collections.Counter()
ru_empty = 0
for chunk in sorted(rt.glob('chunk*.rpkg')):
    for e in read_index(chunk):
        types[e['typ']] += 1
        if e['typ'] == 'LOCR':
            langs = parse_locr(read_res(chunk, e))
            locr_en += langs[LANGS.index('en')].values()
        elif e['typ'] == 'DLGE':
            ts = dlge_texts(read_res(chunk, e))
            for i in range(0, len(ts) - len(ts) % 16, 16):
                if visible(ts[i + 1]).strip():
                    dlge_en.append(visible(ts[i + 1]).strip())
                    ru_empty += not visible(ts[i + 6]).strip()
print('LOCR/DLGE/RTLV/LINE:', types['LOCR'], types['DLGE'], types['RTLV'], types['LINE'])
for name, xs in (('LOCR', locr_en), ('DLGE', dlge_en)):
    u = set(xs)
    print(f'{name}: {len(xs)} радкоў, {sum(map(W, xs))} слоў; унікальных {len(u)}, {sum(map(W, u))} слоў')
print('DLGE без рускага субтытра:', ru_empty)
