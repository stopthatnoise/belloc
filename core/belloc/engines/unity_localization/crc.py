"""CRC бандлаў у каталогу Addressables (catalog.json).

Калі ў каталогу ў бандла ненулявы `m_Crc`, Unity правярае ім файл і змененую табліцу
не грузіць (`CRC Mismatch … Will not load AssetBundle`). `m_Crc: 0` — праверкі няма.

Дзе ляжыць: `m_ExtraDataString` — base64 бінарнага патоку Addressables; у ім JSON
`AssetBundleRequestOptions` (UTF-16LE або ASCII). Лічбы `"m_Crc":<n>` замяняюцца на `0`
і прабелы да той жа даўжыні: даўжыні запісаў і зрушэнні ў `m_EntryDataString` не
мяняюцца, base64 атрымліваецца той жа даўжыні, астатні файл — байт у байт.
Абнуляюцца ўсе бандлы: прасцей і надзейней, чым шукаць запіс па `m_InternalIds`.
"""
from __future__ import annotations

import base64
import re

_KEY = '"m_Crc":'
_EXTRA = re.compile(rb'"m_ExtraDataString"\s*:\s*"([A-Za-z0-9+/=]*)"')


def _zero_in(blob: bytearray, enc: str) -> int:
    """Абнуліць "m_Crc":<лічбы> у blob, запісаных кадоўкай enc; колькі знойдзена."""
    key, unit = _KEY.encode(enc), len("0".encode(enc))
    digits = {str(d).encode(enc) for d in range(10)}
    n = i = 0
    while (i := blob.find(key, i)) != -1:
        j = k = i + len(key)
        while bytes(blob[k:k + unit]) in digits:
            k += unit
        if k > j:
            count = (k - j) // unit
            blob[j:k] = ("0" + " " * (count - 1)).encode(enc)
            n += 1
        i = k
    return n


def zero_crc(data: bytes) -> tuple[bytes, int]:
    """catalog.json → (той жа файл з m_Crc = 0, колькасць запісаў)."""
    m = _EXTRA.search(data)
    if not m:
        raise ValueError("у каталогу няма m_ExtraDataString")
    blob = bytearray(base64.b64decode(m.group(1)))
    n = _zero_in(blob, "utf-16-le") + _zero_in(blob, "ascii")
    encoded = base64.b64encode(bytes(blob))
    assert len(encoded) == len(m.group(1))
    return data[:m.start(1)] + encoded + data[m.end(1):], n


def zero_crc_file(base: str, dst: str) -> int:
    with open(base, "rb") as f:
        data, n = zero_crc(f.read())
    with open(dst, "wb") as f:
        f.write(data)
    return n
