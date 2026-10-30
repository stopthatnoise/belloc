"""Аналіз лакалізацыі Pony Island: CSV, шрыфты, кампаненты, TextMesh.

    PONY_DATA=…/PonyIsland_Data python -X utf8 games/pony-island/research/analyze.py [<out-dir>]

Друкуе аб'ём табліцы `Data/localization` (TextAsset у resources.assets),
пакрыццё шрыфтоў (І і Ў ў « » — ’), колькасць кампанентаў лакалізацыі і
тэксты TextMesh, якіх няма ў CSV. З <out-dir> — захоўвае CSV і TTF шрыфтоў.
"""
import collections
import csv
import io
import os
import re
import struct
import sys

import UnityPy
from fontTools.ttLib import TTFont

DATA = os.environ.get("PONY_DATA", "PonyIsland_Data")   # каталог дадзеных гульні: PONY_DATA=…/PonyIsland_Data
CHECK = "ІіЎўЁё«»—’"
W = lambda s: len(re.findall(r"[^\W\d_]+", s))
norm = lambda s: s.replace("\n", "").replace(" ", "").lower()  # як Localization.FormatString

out = sys.argv[1] if len(sys.argv) > 1 else None
env = UnityPy.load(DATA)
objs = {(o.assets_file.name, o.path_id): o for o in env.objects}
scripts = {k: o.read().m_ClassName for k, o in objs.items() if o.type.name == "MonoScript"}

def ext_name(af, fid):
    return af.name if fid == 0 else af.externals[fid - 1].path.split("/")[-1]

# --- CSV
csv_bytes = None
for o in env.objects:
    if o.type.name == "TextAsset" and o.read().m_Name == "localization":
        s = o.read().m_Script
        csv_bytes = s.encode("utf-8", "surrogateescape") if isinstance(s, str) else bytes(s)
rows = list(csv.reader(io.StringIO(csv_bytes.decode("utf-8"), newline="")))
hdr = rows[1]
iE, iR = hdr.index("ENGLISH"), hdr.index("RUSSIAN")
data = [r for r in rows[2:] if len(r) > iE and r[iE].strip()]
en = [r[iE] for r in data]
print("CSV:", hdr[1:])
print(f"  радкоў {len(data)}, унікальных EN {len(set(en))}, слоў {sum(map(W, en))}, "
      f"сімвалаў {sum(map(len, en))}; з ID {sum(1 for r in data if r[1].strip())}; "
      f"з заўвагай у слупку 0 {sum(1 for r in data if r[0].strip())}; RU запоўнена "
      f"{sum(1 for r in data if r[iR].strip())}")
if out:
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, "localization.csv"), "wb").write(csv_bytes)

# --- шрыфты
print("Шрыфты (дынамічныя TTF):")
for o in env.objects:
    if o.type.name != "Font":
        continue
    f = o.read()
    blob = bytes(f.m_FontData or b"")
    if not blob:
        print(f"  {f.m_Name:30} (убудаваны)")
        continue
    cm = TTFont(io.BytesIO(blob)).getBestCmap()
    cov = "".join(ch if ord(ch) in cm else "·" for ch in CHECK)
    print(f"  {f.m_Name:30} {o.assets_file.name:22} гліфаў {len(cm):6} {cov}")
    if out:
        open(os.path.join(out, f"{f.m_Name}.ttf"), "wb").write(blob)

# --- кампаненты і TextMesh
comp = collections.Counter()
for o in env.objects:
    if o.type.name == "MonoBehaviour":
        raw = o.get_raw_data()
        fid, pid = struct.unpack_from("<iq", raw, 16)
        comp[scripts.get((ext_name(o.assets_file, fid), pid), "?")] += 1
print("Кампаненты:", {k: v for k, v in comp.items()
                     if re.search(r"Locali|Language|English|FontSwap", k)})

keys = {norm(s) for s in en}
fonts, missing = collections.Counter(), []
for o in env.objects:
    if o.type.name == "TextMesh":
        tm = o.read()
        try:
            fonts[tm.m_Font.read().m_Name] += 1
        except Exception:
            fonts["?"] += 1
        if re.search("[A-Za-z]{2,}", tm.m_Text) and norm(tm.m_Text) not in keys:
            missing.append(tm.m_Text)
print("TextMesh па шрыфтах:", fonts.most_common())
u = set(missing)
print(f"TextMesh з тэкстам, якога няма ў CSV: {len(missing)} ({len(u)} унікальных, {sum(map(W, u))} слоў)")
