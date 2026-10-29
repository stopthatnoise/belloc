"""Беларускія літары ў дынамічных TTF-шрыфтах Unity (Font.m_FontData).

Дынамічны шрыфт Unity — гэта проста TTF унутры асета Font: гліфы гульня
растрыруе сама, атласа няма. Таму дастаткова дапісаць гліфы ў сам TTF:

  І/і  — запісы cmap на гліфы лацінскіх I/i (як belloc.ttf_glyphs);
  Ў/ў  — новы гліф: контуры У/у + брэвіс, узяты з Й/й як тыя контуры,
         якіх няма ў И/и (у піксельных шрыфтах Pony Island брэвіс — асобныя
         квадраты), і зрушаны на розніцу цэнтраў У і И.

Толькі TrueType-контуры (glyf); CFF не падтрымліваецца. Пасля правак
выдаляюцца hdmx/LTSH/VDMX (кэшы шырынь па гліфах — састарэлі б).
"""
from __future__ import annotations

import io

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import ttProgram
from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphCoordinates

ALIASES = {0x0406: 0x0049, 0x0456: 0x0069}          # І → I, і → i
# новы гліф: (код, база, з брэвісам, без брэвіса)
BREVE = [(0x040E, 0x0423, 0x0419, 0x0418),          # Ў = У + (Й − И)
         (0x045E, 0x0443, 0x0439, 0x0438)]          # ў = у + (й − и)
CHECK = "ІіЎў"
STALE_TABLES = ("hdmx", "LTSH", "VDMX")


def _contours(glyf, name):
    g = glyf[name]
    if g.isComposite():
        raise ValueError(f"{name}: складаны гліф")
    if g.numberOfContours <= 0:
        return [], []
    coords, ends, flags = g.getCoordinates(glyf)
    out, start = [], 0
    for e in ends:
        out.append((tuple((int(x), int(y)) for x, y in coords[start:e + 1]),
                    tuple(int(f) & 1 for f in flags[start:e + 1])))
        start = e + 1
    return out


def _bounds(contours):
    xs = [x for c, _ in contours for x, _ in c]
    ys = [y for c, _ in contours for _, y in c]
    return min(xs), min(ys), max(xs), max(ys)


def _make_glyph(contours) -> Glyph:
    g = Glyph()
    g.numberOfContours = len(contours)
    pts, flags, ends = [], [], []
    for c, fl in contours:
        pts += c
        flags += fl
        ends.append(len(pts) - 1)
    g.coordinates = GlyphCoordinates(pts)
    g.flags = bytearray(flags)
    g.endPtsOfContours = ends
    g.program = ttProgram.Program()
    g.program.fromBytecode(b"")
    return g


def add_bel_glyphs(data: bytes) -> tuple[bytes, list[str]]:
    """TTF → TTF з І/і/Ў/ў, калі іх не было. Вяртае (байты, што зроблена)."""
    # recalcTimestamp=False: вынік не залежыць ад часу запуску (байт у байт)
    font = TTFont(io.BytesIO(data), recalcTimestamp=False)
    cmap = font.getBestCmap()
    done = []
    unicode_tables = [t for t in font["cmap"].tables if t.isUnicode()]

    for target, source in ALIASES.items():
        if target not in cmap and source in cmap:
            for t in unicode_tables:
                t.cmap[target] = cmap[source]
            done.append(f"{chr(target)}→{cmap[source]}")

    if "glyf" in font:
        glyf = font["glyf"]
        hmtx = font["hmtx"]
        order = font.getGlyphOrder()
        for target, base, with_b, without_b in BREVE:
            if target in cmap or not all(c in cmap for c in (base, with_b, without_b)):
                continue
            plain = {c for c, _ in _contours(glyf, cmap[without_b])}
            breve = [(c, f) for c, f in _contours(glyf, cmap[with_b]) if c not in plain]
            body = _contours(glyf, cmap[base])
            if not breve or not body:
                continue
            bx0, _, bx1, _ = _bounds(_contours(glyf, cmap[without_b]))
            ux0, _, ux1, _ = _bounds(body)
            dx = round((ux0 + ux1) / 2 - (bx0 + bx1) / 2)
            moved = [(tuple((x + dx, y) for x, y in c), f) for c, f in breve]
            name = f"uni{target:04X}"
            g = _make_glyph(body + moved)
            g.recalcBounds(glyf)
            order.append(name)
            font.setGlyphOrder(order)
            glyf.glyphOrder = order
            glyf[name] = g
            hmtx[name] = (hmtx[cmap[base]][0], g.xMin)
            for t in unicode_tables:
                t.cmap[target] = name
            done.append(f"{chr(target)}=у+брэвіс(dx={dx})")
        for t in STALE_TABLES:
            if t in font and done:
                del font[t]

    if not done:
        return data, []
    out = io.BytesIO()
    font.save(out)
    return out.getvalue(), done


def missing(data: bytes, chars: str = CHECK) -> str:
    cm = TTFont(io.BytesIO(data)).getBestCmap()
    return "".join(c for c in chars if ord(c) not in cm)


def preview(fonts: dict[str, bytes], path: str, text: str = "ІіЎў УуЙй БЕЛАРУСКАЯ: ЎСЁ ЎЗРОВЕНЬ"):
    """PNG: па радку на шрыфт (рэндэр PIL/FreeType — як і ў гульні)."""
    from PIL import Image, ImageDraw, ImageFont
    size, pad = 32, 8
    rows = []
    for name, data in fonts.items():
        f = ImageFont.truetype(io.BytesIO(data), size)
        rows.append((name, f))
    label = ImageFont.load_default()
    w = 40 + max(int(f.getlength(text)) for _, f in rows)
    img = Image.new("RGB", (w, len(rows) * (size + pad * 3) + pad), "white")
    d = ImageDraw.Draw(img)
    y = pad
    for name, f in rows:
        d.text((pad, y), name, fill="gray", font=label)
        d.text((pad, y + 10), text, fill="black", font=f)
        y += size + pad * 3
    img.save(path)
