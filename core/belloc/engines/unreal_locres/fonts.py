"""Кірыліца ў шрыфты UE, у якіх яе няма (Dispatch: загалоўкі Tomorrow, Barlow, SCHABO).

Такія шрыфты ў CompositeFont маюць запасным NotoSansCJK: кірыліцу рускай
мовы ён малюе, а І і Ў ў у ім няма — літара проста знікае («ПАЗА»). Дадаць
гліфы ў CJK нельга (65 535 гліфаў — мяжа), таму дадаём увесь кірылічны блок
у сам шрыфт загалоўка: рухавік бярэ сімвал з асноўнага шрыфту, калі ён там
ёсць, і да запаснога не даходзіць.

Секцыя "unreal" у game.json:

  font_patches [{"target": "Dispatch/Content/…/Tomorrow-Black.ufont",
                 "source": "Dispatch/Content/…/NotoSans-Black.ufont",
                 "xscale": 0.5}]       — па жаданні: дадатковае звужэнне (SCHABO XCondensed)
  font_patches_target "Shared"         — мэта (пак), дзе ляжаць шрыфты

Гліфы бяруцца з source, маштабуюцца па вышыні вялікай літары (OS/2 sCapHeight)
і дадаюцца ў target, калі іх там няма; TrueType (glyf) і CFF.
"""
from __future__ import annotations

import io

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

CHARS = [*range(0x0400, 0x0460), 0x0490, 0x0491, 0x00AB, 0x00BB, 0x2019, 0x2014, 0x2026]


def _cap(font: TTFont) -> int:
    os2 = font["OS/2"]
    return getattr(os2, "sCapHeight", 0) or round(font["head"].unitsPerEm * 0.7)


def add_glyphs(target: bytes, source: bytes, xscale: float = 1.0) -> tuple[bytes, int]:
    """target з дададзенымі гліфамі CHARS са source; вяртае (шрыфт, колькі дададзена)."""
    # recalcTimestamp=False: вынік не залежыць ад часу запуску (байт у байт)
    tf, sf = TTFont(io.BytesIO(target), recalcTimestamp=False), TTFont(io.BytesIO(source))
    tcmap, scmap = tf.getBestCmap(), sf.getBestCmap()
    sgs = sf.getGlyphSet()
    ys = _cap(tf) / _cap(sf)
    xs = ys * xscale
    order = list(tf.getGlyphOrder())
    cff = tf["CFF "].cff if "CFF " in tf else None
    added = {}
    for cp in CHARS:
        if cp in tcmap or cp not in scmap:
            continue
        name = f"uni{cp:04X}"
        while name in order:
            name += ".bel"
        rec = DecomposingRecordingPen(sgs)
        sgs[scmap[cp]].draw(rec)
        adv = round(sf["hmtx"][scmap[cp]][0] * xs)
        if cff is None:
            pen = TTGlyphPen(None)
            rec.replay(TransformPen(pen, (xs, 0, 0, ys, 0, 0)))
            g = pen.glyph()
            g.recalcBounds(tf["glyf"])
            tf["glyf"].glyphs[name] = g
            lsb = getattr(g, "xMin", 0)
        else:
            td = cff.topDictIndex[0]
            pen = T2CharStringPen(adv - td.Private.nominalWidthX, None)
            rec.replay(TransformPen(pen, (xs, 0, 0, ys, 0, 0)))
            cs = pen.getCharString(private=td.Private, globalSubrs=cff.GlobalSubrs)
            idx = td.CharStrings.charStringsIndex
            idx.append(cs)
            td.CharStrings.charStrings[name] = len(idx) - 1
            td.charset.append(name)
            bp = BoundsPen(None)
            rec.replay(TransformPen(bp, (xs, 0, 0, ys, 0, 0)))
            lsb = round(bp.bounds[0]) if bp.bounds else 0
        tf["hmtx"].metrics[name] = (adv, lsb)
        order.append(name)
        added[cp] = name
    if not added:
        return target, 0
    tf.setGlyphOrder(order)
    if cff is None:
        tf["glyf"].glyphOrder = order
    for t in tf["cmap"].tables:
        if t.isUnicode():
            t.cmap.update({cp: n for cp, n in added.items() if t.format != 4 or cp <= 0xFFFF})
    out = io.BytesIO()
    tf.save(out)
    return out.getvalue(), len(added)
