"""CRC32 бандлаў у бінарным каталогу Addressables (catalog.bin) і MD5 у catalog.hash.

`crc.py` абнуляе m_Crc у catalog.json (тэкставы каталог). У гэтай гульні каталог
бінарны, і m_Crc ляжыць у запісе AssetBundleRequestOptions кожнага бандла:

    "<імя>.bundle"  u32 32  "<32 hex m_Hash>"  u32 a  u32 b  u32 m_Crc  u32 m_BundleSize

Перад гэтым блокам (пасля радка ўнутранага адрасу) можа стаяць 16-байтавы
ідэнтыфікатар тыпу — ён бывае не заўсёды, таму пошук спрабуе абодва варыянты.

Калі m_Crc не 0, гульня правярае ім файл і зменены бандл не грузіць
(«CRC Mismatch … Will not load AssetBundle»). Абнуленне — той самы прыём, што і ў
`crc.py`: даўжыня файла не мяняецца, таму зрухі ў каталогу застаюцца слушнымі.

`catalog.hash` — md5 каталога радком з 32 hex без пераносу радка. Па ім гульня
пазнае, што каталог у яе кэшы (LocalLow) састарэў; без новага значэння яна
возьме стары кэш, дзе m_Crc яшчэ нянулявыя. Таму пішам md5 ад новага catalog.bin.

Памер бандла гульня не правярае, і лакальны патч яго не мяняў; ён служыць якарам:
імя бандла ў каталогу сустракаецца двойчы (m_BundleName і ўнутраны адрас), а
памер — адзін раз. Няма запісу памеру — значыць, для гэтага бандла CRC у каталогу
не захоўваецца (так у большасці), і абнуляць няма чаго.

Фармат: `ContentCatalogData` у Addressables 2.x (тут — 2.9.1).
"""
from __future__ import annotations

import hashlib
import re

_HEX32 = re.compile(rb"[0-9a-f]{32}")
_TYPE_TAG = 16          # 16-байтавы ідэнтыфікатар тыпу запісу (бывае перад блокам)


def _record(data: bytes, name: bytes, size: int) -> int | None:
    """Зрух поля m_Crc для бандла `name` памерам `size`; None — запісу няма."""
    found = []
    for m in re.finditer(re.escape(name), data):
        for skip in (0, _TYPE_TAG):
            p = m.end() + skip
            if p + 52 > len(data) or int.from_bytes(data[p:p + 4], "little") != 32:
                continue
            if not _HEX32.fullmatch(data[p + 4:p + 36]):
                continue
            if int.from_bytes(data[p + 48:p + 52], "little") != size:
                continue
            found.append(p + 44)
    if len(found) > 1:
        raise ValueError(f"запіс «{name.decode(errors='replace')}» у каталогу неадназначны")
    return found[0] if found else None


def zero_crc(data: bytes, bundles: dict[str, int]) -> tuple[bytes, int, list[str]]:
    """catalog.bin → (той жа каталог з m_Crc = 0, колькасць, бандлы без запісу CRC).

    bundles — {імя файла бандла: памер АРЫГІНАЛА (да нашай праўкі)}.
    """
    out = bytearray(data)
    done, absent = 0, []
    for name, size in bundles.items():
        raw = name.encode("utf-8")
        off = _record(data, raw, size)
        if off is None:
            if raw in data:
                raise ValueError(f"«{name}»: у каталогу ёсць, але запіс з m_Crc не "
                                 f"распазнаны — магчыма, іншая версія Addressables")
            absent.append(name)
            continue
        if int.from_bytes(out[off:off + 4], "little"):
            out[off:off + 4] = b"\0\0\0\0"
            done += 1
    return bytes(out), done, absent


def hash_hex(data: bytes) -> bytes:
    """Змест catalog.hash для гэтага catalog.bin: md5 радком, без пераносу."""
    return hashlib.md5(data).hexdigest().encode("ascii")
