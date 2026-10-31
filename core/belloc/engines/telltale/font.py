"""Бітмапавы .font рэмастэра The Wolf Among Us (MSV6) — па FontEditor.cs і
TextureWorker.cs з TTG Tools.

MetaStream: "6VSM", u32 памер даных, u32 памер debug (0), u32 памер async (тэкстуры),
u32 колькасць класаў, класы па 12 байт. Даныя:
  [u32 L+8][u32 L][імя], байт '0'/'1' — Unicode-шрыфт (пры '0' гульня
  дэкадуе тэкст пабайтава: UTF-8 ператвараецца ў «Ð¿Ð°»), f32, f32 BaseSize,
  u32 памер блока гліфаў (8 + 48·N), u32 N, гліфы па 48 байт
    (u32 код Unicode, u32 TexNum, u32 Channel, f32 XStart, XEnd, YStart, YEnd
     — доля шырыні/вышыні тэкстуры —, f32 CharWidth, CharHeight, XOffset,
     YOffset, XAdvance — у пікселях),
  u32 памер блока тэкстур, u32 колькасць тэкстур, загалоўкі d3dtx, хвост.
Пікселі тэкстур — у async-секцыі ў канцы файла, mip ад меншага да большага.

Скрыпт разбірае загаловак да гліфаў і загалоўкі тэкстур (шырыня, вышыня,
фармат, памеры mip), дамалёўвае гліфы з TTF (`add_glyphs`: у вольнае месца
апошняй старонкі, калі месца няма — старонка расце ўніз) і збірае файл
нанова (`build`). Фарматы: BC3 (DXT5) — маска гліфа ў альфе, колер белы;
BC1 (DXT1) — белае на чорным у колеры, без альфы. Раскладка: Channel 15 —
шчыльная рамка гліфа са зрухамі (як BMFont), Channel 0 (старыя шрыфты з
арыгінала) — ячэйка на ўсю вышыню радка, базавая лінія ўнутры.

  python -m belloc.engines.telltale.font info <файл.font>
  python -m belloc.engines.telltale.font png <файл.font> <выхад.png> [старонка]   # альфа → PNG
  python -m belloc.engines.telltale.font add <файл.font> <шрыфт.ttf> <выхад.font> [сімвалы]
"""
import struct, sys
from dataclasses import dataclass

BEL_CHARS = ("АБВГДЕЁЖЗІЙКЛМНОПРСТУЎФХЦЧШЫЬЭЮЯабвгдеёжзійклмнопрстуўфхцчшыьэюя"
             "ИЩЪищъ«»’—–…„“")

FORMATS = {0: "ARGB8", 4: "ARGB4", 0x10: "A8", 0x11: "IL8", 0x40: "BC1", 0x41: "BC2",
           0x42: "BC3", 0x43: "BC4", 0x44: "BC5", 0x46: "BC7"}


@dataclass
class Glyph:
    code: int
    tex: int
    channel: int
    x0: float
    x1: float
    y0: float
    y1: float
    w: float
    h: float
    xoff: float
    yoff: float
    adv: float

    def pack(self):
        return struct.pack("<3I9f", self.code, self.tex, self.channel, self.x0, self.x1,
                           self.y0, self.y1, self.w, self.h, self.xoff, self.yoff, self.adv)


@dataclass
class Tex:
    version: int
    name: str
    width: int
    height: int
    fmt: int
    mips: list          # [(MipSize, BlockSize, абсалютны зрух пікселяў)] ад 0 (большы)
    mip_size_pos: list  # пазіцыі поля MipSize у файле для кожнага mip
    h_pos: int          # пазіцыя поля Height
    texsize_pos: int    # пазіцыя поля TexSize


class Font:
    def __init__(self, data: bytes):
        self.data = data
        self.magic = data[:4]
        assert self.magic == b"6VSM", self.magic
        self.size, self.debug_size, self.async_size = struct.unpack_from("<III", data, 4)
        assert self.debug_size == 0
        ncls = struct.unpack_from("<I", data, 16)[0]
        self.data0 = 20 + ncls * 12
        # клас з гэтым crc64 дадае 4 байты ў блок d3dtx (AddInfo у TTG Tools)
        self.add_info = bytes.fromhex("7aba6e8789886cfa") in data[20:self.data0]
        p = self.data0
        b, n = struct.unpack_from("<II", data, p)
        assert b == n + 8
        self.name = data[p + 8:p + 8 + n].decode("latin-1")
        p += b
        self.one_pos = p
        self.one = data[p]
        p += 1
        self.f1, self.base = struct.unpack_from("<ff", data, p)
        p += 8
        half = struct.unpack_from("<f", data, p)[0]
        if half in (0.5, 1.0) and struct.unpack_from("<I", data, p + 4)[0] != \
                struct.unpack_from("<I", data, p + 8)[0] * 48 + 8:
            p += 4
        self.glyph_blk_pos = p
        blk, cnt = struct.unpack_from("<II", data, p)
        assert blk == cnt * 48 + 8, "блок гліфаў"
        p += 8
        self.glyphs = [Glyph(*struct.unpack_from("<3I9f", data, p + i * 48)) for i in range(cnt)]
        p += cnt * 48
        self.after_glyphs = p
        self.tex_blk, ntex = struct.unpack_from("<II", data, p)
        p += 8
        self.textures = []
        apos = self.data0 + self.size            # пачатак async
        for _ in range(ntex):
            t, p, apos = self._tex(data, p, apos)
            self.textures.append(t)

    def _tex(self, d, p, apos):
        version = struct.unpack_from("<i", d, p)[0]
        p += 4 + 8 + 8                           # unknownFlags, platform
        p += 4
        n = struct.unpack_from("<i", d, p)[0]
        name = d[p + 4:p + 4 + n].decode("latin-1")
        p += 4 + n
        p += 4
        n = struct.unpack_from("<i", d, p)[0]
        p += 4 + n                               # SubObjectName
        p += 4                                   # OneValue
        one = d[p]
        p += 1
        if one == 0x31:
            p += 8
            p += struct.unpack_from("<i", d, p)[0]
        mip, w, h = struct.unpack_from("<iii", d, p)
        h_pos = p + 8
        p += 12
        if version >= 8:
            faces, arr = struct.unpack_from("<ii", d, p)
            p += 8
        fmt = struct.unpack_from("<I", d, p)[0]
        p += 8
        p += {3: 0x28, 4: 0x28, 5: 0x34, 7: 0x34, 8: 0x38, 9: 0x38}.get(version, 0x24) + 4 * self.add_info
        if version >= 8:
            p += struct.unpack_from("<i", d, p)[0]
        p += struct.unpack_from("<i", d, p)[0]
        mipcount, somedata, texsize = struct.unpack_from("<iiI", d, p)
        texsize_pos = p + 8
        p += 12
        mips, mpos = [None] * mipcount, [None] * mipcount
        for i in range(mipcount - 1, -1, -1):
            if version >= 5:
                p += 4
            p += 4                               # CurrentMip
            v = struct.unpack_from("<i", d, p)[0]
            if v == 1:
                p += 4
            mpos[i] = p
            msize, bsize = struct.unpack_from("<ii", d, p)
            p += 8
            if version >= 8:
                p += 4
            mips[i] = [msize, bsize, None]
        for _ in range(somedata):
            p += struct.unpack_from("<i", d, p)[0]
        for i in range(mipcount - 1, -1, -1):
            mips[i][2] = apos
            apos += mips[i][0]
        return Tex(version, name, w, h, fmt, mips, mpos, h_pos, texsize_pos), p, apos

    def pixels(self, ti=0):
        t = self.textures[ti]
        size, _, off = t.mips[0]
        return self.data[off:off + size]

    def build(self, glyphs=None, pages=None):
        """Файл з новай табліцай гліфаў і/або старонкамі {нумар: (шырыня, вышыня, пікселі)}.
        Старонка, якую мяняем, мусіць мець адзін mip."""
        pages = pages or {}
        d = bytearray(self.data[:self.data0 + self.size])
        d[self.one_pos] = 0x31                    # кірыліца — толькі ў Unicode-шрыфце
        for ti, (w, h, px) in pages.items():
            t = self.textures[ti]
            assert len(t.mips) == 1, "толькі адзін mip"
            struct.pack_into("<ii", d, t.h_pos - 4, w, h)
            struct.pack_into("<i", d, t.mip_size_pos[0] + 4, w // 4 * (8 if t.fmt == 0x40 else 16))
            struct.pack_into("<I", d, t.texsize_pos, len(px))
            struct.pack_into("<i", d, t.mip_size_pos[0], len(px))
            if t.version >= 8:
                struct.pack_into("<i", d, t.mip_size_pos[0] + 8, len(px))
        if glyphs is not None:
            blob = struct.pack("<II", len(glyphs) * 48 + 8, len(glyphs)) + b"".join(g.pack() for g in glyphs)
            d[self.glyph_blk_pos:self.after_glyphs] = blob
        asyn = b"".join(pages[i][2] if i in pages else self.pixels(i) for i in range(len(self.textures)))
        struct.pack_into("<III", d, 4, len(d) - self.data0, 0, len(asyn))
        return bytes(d) + asyn


def decode_a(t: Tex, raw: bytes):
    """Альфа (або яркасць) тэкстуры ў bytearray w×h — для A8, BC4, BC3, ARGB8."""
    w, h = t.width, t.height
    out = bytearray(w * h)
    if t.fmt == 0x10:
        return bytearray(raw[:w * h])
    if t.fmt == 0:
        return bytearray(raw[3::4][:w * h])
    if t.fmt == 0x40:
        i = 0
        for by in range(0, h, 4):
            for bx in range(0, w, 4):
                c0, c1 = struct.unpack_from("<HH", raw, i)
                bits = struct.unpack_from("<I", raw, i + 4)[0]
                i += 8
                r0, r1 = (c0 >> 11) * 255 // 31, (c1 >> 11) * 255 // 31
                pal = [r0, r1, (2 * r0 + r1) // 3, (r0 + 2 * r1) // 3] if c0 > c1 else [r0, r1, (r0 + r1) // 2, 0]
                for py in range(4):
                    for px in range(4):
                        out[(by + py) * w + bx + px] = pal[(bits >> (2 * (py * 4 + px))) & 3]
        return out
    if t.fmt in (0x43, 0x42):
        bs = 8 if t.fmt == 0x43 else 16
        i = 0
        for by in range(0, h, 4):
            for bx in range(0, w, 4):
                blk = raw[i:i + 8]
                i += bs
                a0, a1 = blk[0], blk[1]
                bits = int.from_bytes(blk[2:8], "little")
                pal = [a0, a1] + ([((6 - k) * a0 + k * a1) // 7 for k in range(1, 7)] if a0 > a1
                                  else [((4 - k) * a0 + k * a1) // 5 for k in range(1, 5)] + [0, 255])
                for py in range(4):
                    for px in range(4):
                        out[(by + py) * w + bx + px] = pal[(bits >> (3 * (py * 4 + px))) & 7]
        return out
    raise NotImplementedError(FORMATS.get(t.fmt, hex(t.fmt)))


def bc3_alpha_block(vals):
    """16 значэнняў альфы → 8 байт BC4/DXT5-альфы (рэжым 8 узроўняў)."""
    hi, lo = max(vals), min(vals)
    if hi == lo:
        return bytes([hi, lo]) + bytes(6)
    pal = [hi, lo] + [((7 - k) * hi + k * lo) // 7 for k in range(1, 7)]
    bits = 0
    for i, v in enumerate(vals):
        bits |= min(range(8), key=lambda k: abs(pal[k] - v)) << (3 * i)
    return bytes([hi, lo]) + bits.to_bytes(6, "little")


WHITE = bytes([255, 255, 255, 255, 0, 0, 0, 0])   # колер BC3: c0 = c1 = белы, індэксы 0


def bc1_gray_block(vals):
    """16 значэнняў яркасці → BC1: c0 белы, c1 чорны, 4 узроўні (255, 0, 170, 85)."""
    if max(vals) == 0:
        return bytes(4) + b"\xaa" * 4
    lv = (255, 0, 170, 85)
    bits = 0
    for i, v in enumerate(vals):
        bits |= min(range(4), key=lambda k: abs(lv[k] - v)) << (2 * i)
    return struct.pack("<HHI", 0xFFFF, 0x0000, bits)
PAD = 1                                           # поле вакол гліфа, як у арыгінале


def broken_glyphs(font: Font) -> set[int]:
    """Коды гліфаў, чые прастакутнікі ў атласе налазяць на чужыя. У старых шрыфтах
    (AvantGarde, Rockwell Std) запісы сімвалаў, якіх у атласе няма (0xAA–0xC0 без
    © ®, Ý Þ ð ÷…), паказваюць у сярэдзіну суседніх ячэек — «» там малююцца смеццем.
    У мностве — і бітыя, і цэлыя суседзі, на якія яны налазяць."""
    rects = []
    for g in font.glyphs:
        if g.code < 0x20 or g.w < 1 or g.h < 1:
            continue
        t = font.textures[g.tex]
        x, y = round(g.x0 * t.width), round(g.y0 * t.height)
        rects.append((g.code, g.tex, x, y, x + round(g.w), y + round(g.h)))
    bad = set()
    for i, a in enumerate(rects):
        for b in rects[i + 1:]:
            if (a[1] == b[1] and min(a[4], b[4]) - max(a[2], b[2]) > 2
                    and min(a[5], b[5]) - max(a[3], b[3]) > 2):
                bad |= {a[0], b[0]}
    return bad


def add_glyphs(font: Font, ttf: str, chars: str, ref="H"):
    """Дамаляваць сімвалы `chars` шрыфтам `ttf`, падагнаўшы памер і зрухі
    пад гліф `ref` шрыфта гульні. Сімвалы з `chars`, чые гліфы ў шрыфце бітыя
    (broken_glyphs), перамалёўваюцца нанова. Вяртае новыя байты .font."""
    from PIL import Image, ImageDraw, ImageFont
    redraw = broken_glyphs(font) & {ord(c) for c in chars}
    have = {g.code for g in font.glyphs} - redraw
    chars = [c for c in dict.fromkeys(chars) if ord(c) not in have]
    if not chars:
        return font.data
    rg = next(g for g in font.glyphs if g.code == ord(ref))
    # два віды шрыфтоў: Channel 15 — шчыльная рамка гліфа са зрухамі (як BMFont);
    # Channel 0 (старыя, з арыгінала) — ячэйка на ўсю вышыню радка, xoff = yoff = 0,
    # базавая лінія — унутры ячэйкі; яе і вышыню H мераем па пікселях атласа
    cell = all(g.channel == 0 and g.yoff == 0 for g in font.glyphs)
    assert cell or all(g.channel == 15 for g in font.glyphs), "Channel не 0/15"
    if cell:
        rt_ = font.textures[rg.tex]
        al = decode_a(rt_, font.pixels(rg.tex))
        cx0, cy0 = round(rg.x0 * rt_.width), round(rg.y0 * rt_.height)
        rows = [yy for yy in range(int(rg.h)) if any(
            al[(cy0 + yy) * rt_.width + cx0 + xx] > 96 for xx in range(int(rg.w)))]
        cols = [xx for xx in range(int(rg.w)) if any(
            al[(cy0 + yy) * rt_.width + cx0 + xx] > 96 for yy in range(int(rg.h)))]
        ink_top, baseline, ink_left = rows[0], rows[-1] + 1, cols[0]
        target = baseline - ink_top
    else:
        target = rg.h - 2 * PAD

    path, _, var = ttf.rpartition(":")          # "bahnschrift.ttf:SemiBold" — варыяцыйны шрыфт
    if not path or "/" in var or "\\" in var:   # без варыяцыі (або толькі «C:»)
        path, var = ttf, ""

    def load(s):
        f = ImageFont.truetype(path, s)
        if var:
            f.set_variation_by_name(var)
        return f

    def cap(s):
        b = load(s).getbbox(ref, anchor="ls")
        return b[3] - b[1]
    size = min(range(6, 400), key=lambda s: abs(cap(s) - target))
    pf = load(size)
    rl, rt, rr, rb = pf.getbbox(ref, anchor="ls")
    dx = rg.xoff - (rl - PAD)
    dy = rg.yoff - (font.base + rt - PAD)
    k = rg.adv / pf.getlength(ref)
    ti = len(font.textures) - 1
    t = font.textures[ti]
    assert t.fmt in (0x40, 0x42) and len(t.mips) == 1, (font.name, FORMATS.get(t.fmt), len(t.mips))
    bs = 8 if t.fmt == 0x40 else 16
    W, H = t.width, t.height
    old = font.pixels(ti)
    empty = bc1_gray_block([0] * 16) if t.fmt == 0x40 else bc3_alpha_block([0] * 16) + WHITE
    oldW = W
    if W < 256:                                   # вузкую старонку пашыраем да 512
        W, ob, nb = 512, oldW // 4, 512 // 4
        old = b"".join(old[r * ob * bs:(r + 1) * ob * bs] + empty * (nb - ob) for r in range(H // 4))
    used = max([g.y1 * H for g in font.glyphs if g.tex == ti] + [0])
    y0 = (int(used) + 2 + 3) // 4 * 4
    # раскладка паліцамі; у ячэйкавых шрыфтах выносныя элементы і брэвіс
    # могуць выйсці за ячэйку — запас над і пад паліцай, каб не лезлі ў суседнюю
    up = down = 0
    if cell:
        bb = [pf.getbbox(c, anchor="ls") for c in chars]
        up = max(0, -min(baseline + b[1] for b in bb))
        down = max(0, max(baseline + b[3] for b in bb) - int(rg.h))
    boxes, x, y, row = [], 2, y0 + 1 + up, 0
    for c in chars:
        l, tp, r, b = pf.getbbox(c, anchor="ls")
        if cell:
            w, h = max(1, round(pf.getlength(c) * k)), int(rg.h)
        else:
            w, h = r - l + 2 * PAD, b - tp + 2 * PAD
        if x + w + 2 > W:
            x, y, row = 2, y + row + 2 + down + up, 0
        boxes.append((c, x, y, w, h, l, tp))
        x += w + 2
        row = max(row, h)
    need = y + row + 2 + down
    newH = max(H, 1)
    while need > newH:
        newH *= 2
    img = Image.new("L", (W, newH - y0), 0)
    dr = ImageDraw.Draw(img)
    glyphs = []
    for g in font.glyphs:
        if g.code in redraw:
            continue
        if g.tex == ti and (newH != H or W != oldW):
            g = Glyph(**{**g.__dict__, "y0": g.y0 * H / newH, "y1": g.y1 * H / newH,
                         "x0": g.x0 * oldW / W, "x1": g.x1 * oldW / W})
        glyphs.append(g)
    for c, x, y, w, h, l, tp in boxes:
        if cell:
            dr.text((x + ink_left - rl, y - y0 + baseline), c, font=pf, fill=255, anchor="ls")
            glyphs.append(Glyph(ord(c), ti, 0, x / W, (x + w) / W, y / newH, (y + h) / newH,
                                float(w), float(h), 0.0, 0.0, float(w)))
            continue
        dr.text((x + PAD - l, y - y0 + PAD - tp), c, font=pf, fill=255, anchor="ls")
        glyphs.append(Glyph(ord(c), ti, 15, x / W, (x + w) / W, y / newH, (y + h) / newH,
                            float(w), float(h), float(round(l - PAD + dx)),
                            float(round(font.base + tp - PAD + dy)), float(round(pf.getlength(c) * k))))
    glyphs.sort(key=lambda g: g.code)
    keep = y0 // 4 * (W // 4) * bs                # блокі вышэй за y0 не чапаем
    a = img.tobytes()
    out = bytearray(old[:keep])
    for by in range(0, newH - y0, 4):
        for bx in range(0, W, 4):
            vals = [a[(by + py) * W + bx + px] for py in range(4) for px in range(4)]
            out += bc1_gray_block(vals) if t.fmt == 0x40 else bc3_alpha_block(vals) + WHITE
    return font.build(glyphs, {ti: (W, newH, bytes(out))})


if __name__ == "__main__":
    cmd, path = sys.argv[1], sys.argv[2]
    f = Font(open(path, "rb").read())
    if cmd == "info":
        codes = [g.code for g in f.glyphs]
        print(f"{f.name}: base {f.base}, гліфаў {len(f.glyphs)} (U+{min(codes):04X}…U+{max(codes):04X}), тэкстур {len(f.textures)}")
        for t in f.textures:
            print(f"  {t.name}: v{t.version} {t.width}×{t.height} {FORMATS.get(t.fmt, hex(t.fmt))}, mip {[m[0] for m in t.mips]}")
        ys = max(g.y1 for g in f.glyphs)
        print(f"  ніз апошняга гліфа: {ys:.3f} вышыні; каналы {sorted({g.channel for g in f.glyphs})}, TexNum {sorted({g.tex for g in f.glyphs})}")
        print(f"  памер: файл {len(f.data)}, загаловак+даныя+async {f.data0 + f.size + f.async_size}")
    elif cmd == "png":
        from PIL import Image
        ti = int(sys.argv[4]) if len(sys.argv) > 4 else 0
        t = f.textures[ti]
        Image.frombytes("L", (t.width, t.height), bytes(decode_a(t, f.pixels(ti)))).save(sys.argv[3])
    elif cmd == "add":
        chars = sys.argv[5] if len(sys.argv) > 5 else BEL_CHARS
        open(sys.argv[4], "wb").write(add_glyphs(f, sys.argv[3], chars))
