"""Тэкстуры .d3dtx (MSV6, T3Texture) і беларускія надпісы на іх.

Чытанне — па тым жа разборы T3Texture, што ў шрыфтах (`font.Font._tex`);
пікселі — BC1/BC3: дэкодуе texture2ddecoder, кадуе etcpak (абодва — залежнасці
UnityPy). Запіс мяняе толькі пікселі ўсіх mip-узроўняў, памеры і загаловак
застаюцца, таму файл даўжынёй байт у байт як арыгінал.

Надпісы — `games/<гульня>/textures.json`:

  {"textures": {
     "obj_letterToad.d3dtx": {
       "note": "ліст пана Жабы Крэйну (эпізод 3)",
       "blocks": [
         {"erase": [90, 220, 960, 960],             # дзе ляжаць старыя літары (x0, y0, x1, y1)
          "font": "fonts/ptmono/PTM55FT.ttf",       # адносна games/<гульня>/; ":Варыяцыя" — як у telltale.fonts
          "size": 34, "x": 100, "y": 250, "line": 39,
          "color": "auto",                          # колер старых літар або [r, g, b]
          "text": ["Пан Крэйн,", "", "  Вы казалі…"],  # абзацы, перанос па "width"
          "width": 820}]}}}                         # або "lines": гатовыя радкі

Блок: маска старых літар — пікселі цямнейшыя (або ярчэйшыя, "light": true)
за фон каля іх (медыянны фільтр) — залівацца фонам (OpenCV inpaint), потым
радкі малююцца з (x, y) праз `line` пікселяў: "text" (абзацы) пераносіцца па
"width", гатовыя "lines", што не ўлазяць у "width", сціскаюцца па гарызанталі.
Дадаткова: "stroke" — таўшчыня (px), "soft" — размыццё, "opacity", "light" —
старыя літары святлейшыя за фон, "thresh" — парог маскі. Каардынаты — у пікселях
найбольшага mip.
"""
from __future__ import annotations

import os
import struct

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import font as tfont

FMT_BC1, FMT_BC3 = 0x40, 0x42


class Texture:
    def __init__(self, data: bytes):
        assert data[:4] == b"6VSM", data[:4]
        self.data = data
        self.size, _, self.async_size = struct.unpack_from("<III", data, 4)
        ncls = struct.unpack_from("<I", data, 16)[0]
        self.data0 = 20 + ncls * 12
        self.add_info = bytes.fromhex("7aba6e8789886cfa") in data[20:self.data0]
        self.tex, _, _ = tfont.Font._tex(self, data, self.data0, self.data0 + self.size)
        assert self.tex.fmt in (FMT_BC1, FMT_BC3), tfont.FORMATS.get(self.tex.fmt, hex(self.tex.fmt))

    @property
    def width(self):
        return self.tex.width

    @property
    def height(self):
        return self.tex.height

    def image(self) -> Image.Image:
        """Найбольшы mip як RGBA."""
        import texture2ddecoder
        t = self.tex
        size, _, off = t.mips[0]
        dec = texture2ddecoder.decode_bc1 if t.fmt == FMT_BC1 else texture2ddecoder.decode_bc3
        return Image.frombytes("RGBA", (t.width, t.height), dec(self.data[off:off + size], t.width, t.height),
                               "raw", "BGRA")

    def build(self, img: Image.Image) -> bytes:
        """Новыя байты .d3dtx: img (памер найбольшага mip) у кожны mip-узровень."""
        import etcpak
        t = self.tex
        assert img.size == (t.width, t.height), (img.size, t.width, t.height)
        img = img.convert("RGBA")
        enc = etcpak.compress_bc1 if t.fmt == FMT_BC1 else etcpak.compress_bc3
        d = bytearray(self.data)
        for i, (size, _, off) in enumerate(t.mips):
            w, h = max(1, t.width >> i), max(1, t.height >> i)
            m = img if i == 0 else img.resize((w, h), Image.LANCZOS)
            bw, bh = (w + 3) // 4 * 4, (h + 3) // 4 * 4  # BC — блокі 4×4
            if (bw, bh) != (w, h):
                pad = Image.new("RGBA", (bw, bh))
                pad.paste(m, (0, 0))
                m = pad
            raw = enc(m.tobytes(), bw, bh)
            assert len(raw) == size, (i, len(raw), size)
            d[off:off + size] = raw
        return bytes(d)


def _load_font(path: str, size: int):
    path, _, var = path.rpartition(":")
    if not path or "/" in var or "\\" in var:
        path, var = path + (":" if path else "") + var, ""
    f = ImageFont.truetype(path, size)
    if var:
        f.set_variation_by_name(var)
    return f


def erase(img: Image.Image, box, light=False, thresh=28, grow=3) -> tuple[Image.Image, tuple]:
    """Сцерці літары ў box (inpaint). Вяртае (новую выяву, колер старых літар)."""
    import cv2
    x0, y0, x1, y1 = box
    rgb = np.array(img.convert("RGB"))
    crop = rgb[y0:y1, x0:x1]
    gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY).astype(np.int16)
    bg = cv2.medianBlur(gray.astype(np.uint8), 31).astype(np.int16)
    diff = gray - bg if light else bg - gray
    mask = (diff > thresh).astype(np.uint8) * 255
    ink = crop[diff > thresh * 2]
    color = tuple(int(c) for c in np.median(ink, 0)) if len(ink) else (40, 40, 40)
    mask = cv2.dilate(mask, np.ones((2 * grow + 1, 2 * grow + 1), np.uint8))
    crop[:] = cv2.inpaint(np.ascontiguousarray(crop), mask, 5, cv2.INPAINT_TELEA)
    out = Image.fromarray(rgb)
    if img.mode == "RGBA":
        out.putalpha(img.getchannel("A"))
    return out, color


def wrap(paragraphs: list[str], fnt, width: float) -> list[str]:
    """Абзацы → радкі не шырэйшыя за width (пачатковыя прабелы — водступ)."""
    out = []
    for para in paragraphs:
        indent = para[:len(para) - len(para.lstrip(" "))]
        line = indent
        for word in para.split():
            cand = line + word if line.strip() == "" else line + " " + word
            if line.strip() and fnt.getlength(cand) > width:
                out.append(line)
                line = word
            else:
                line = cand
        out.append(line if line.strip() else "")
    return out


def draw_block(img: Image.Image, b: dict, base_dir: str) -> Image.Image:
    if b.get("alpha"):
        return _draw_alpha(img, b, base_dir)
    color = None
    if "erase" in b:
        img, color = erase(img, b["erase"], b.get("light", False), b.get("thresh", 28))
    if b.get("color", "auto") != "auto":
        color = tuple(b["color"])
    color = color or (40, 40, 40)
    fnt = _load_font(os.path.join(base_dir, b["font"]), b["size"])
    layer = _text_layer(img.size, b, fnt)
    return _blend(img, layer, b, color)


def _text_layer(size, b: dict, fnt) -> Image.Image:
    W, H = size
    layer = Image.new("L", (W, H), 0)
    dr = ImageDraw.Draw(layer)
    x, y, width = b["x"], b["y"], b.get("width")
    lines = b["lines"] if "lines" in b else wrap(b["text"], fnt, width)
    if "text" in b:
        width = None
    for i, line in enumerate(lines):
        if not line:
            continue
        yy = y + i * b["line"]
        lw = dr.textlength(line, font=fnt)
        if width and lw > width:
            tmp = Image.new("L", (int(lw) + 4, b["line"] * 2), 0)
            ImageDraw.Draw(tmp).text((0, b["line"]), line, font=fnt, fill=255, anchor="ls",
                                     stroke_width=b.get("stroke", 0), stroke_fill=255)
            tmp = tmp.resize((int(width), tmp.height), Image.LANCZOS)
            layer.paste(tmp, (x, yy - b["line"]), tmp)
        else:
            dr.text((x, yy), line, font=fnt, fill=255, anchor="ls",
                    stroke_width=b.get("stroke", 0), stroke_fill=255)
    return layer


def _draw_alpha(img: Image.Image, b: dict, base_dir: str) -> Image.Image:
    """Надпіс у альфа-канале (кнопкі меню: белыя літары з мяккім цёмным ценем на
    празрыстым): у "erase" усё робіцца празрыстым, літары — колерам "color"
    (па змаўчанні белы), цень — "shadow" (непразрыстасць 0–1) і "shadow_grow" (px)."""
    from PIL import ImageFilter
    arr = np.array(img.convert("RGBA"))
    x0, y0, x1, y1 = b["erase"]
    arr[y0:y1, x0:x1] = 0
    fnt = _load_font(os.path.join(base_dir, b["font"]), b["size"])
    layer = _text_layer(img.size, b, fnt)
    grow = b.get("shadow_grow", 2)
    sh = layer.filter(ImageFilter.MaxFilter(2 * grow + 1)).filter(ImageFilter.GaussianBlur(grow))
    t = np.asarray(layer, np.float32) / 255
    sa = np.asarray(sh, np.float32) / 255 * b.get("shadow", 0.3)
    a = t + sa * (1 - t)                          # літары над ценем
    color = np.array(b.get("color", [255, 255, 255]), np.float32)
    rgb = color * (t / np.maximum(a, 1e-6))[..., None]
    old_a = arr[..., 3].astype(np.float32) / 255     # новае паверх старога (у erase старога ўжо няма)
    out_a = a + old_a * (1 - a)
    out = (rgb * a[..., None] + arr[..., :3] * (old_a * (1 - a))[..., None]) / np.maximum(out_a, 1e-6)[..., None]
    arr[..., :3] = out.clip(0, 255).astype(np.uint8)
    arr[..., 3] = (out_a * 255).clip(0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def _blend(img: Image.Image, layer: Image.Image, b: dict, color) -> Image.Image:
    if b.get("soft", 0):
        from PIL import ImageFilter
        layer = layer.filter(ImageFilter.GaussianBlur(b["soft"]))
    a = np.array(layer, np.float32)[..., None] * b.get("opacity", 1.0) / 255
    rgb = np.array(img.convert("RGB"), np.float32)
    rgb = rgb * (1 - a) + np.array(color, np.float32) * a
    out = Image.fromarray(rgb.clip(0, 255).astype(np.uint8))
    if img.mode == "RGBA":
        out.putalpha(img.getchannel("A"))
    return out


def apply(data: bytes, spec: dict, base_dir: str) -> tuple[bytes, Image.Image, Image.Image]:
    """Надпісы spec на тэкстуру data → (байты .d3dtx, выява да, выява пасля)."""
    t = Texture(data)
    before = t.image()
    img = before
    for b in spec["blocks"]:
        img = draw_block(img, b, base_dir)
    if "A" in before.getbands() and not any(b.get("alpha") for b in spec["blocks"]):
        img = img.convert("RGBA")
        img.putalpha(before.getchannel("A"))
    return t.build(img), before, img
