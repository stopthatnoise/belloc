"""TMP 1.x шрыфты BATTLETECH: кодэк, І/і/Ў/ў, атласы, FontLocTable.

Unity 2018.4 трымае ў гульні TMP 1.x: у MonoBehaviour няма тыпавога дрэва, а
гліфы ляжаць у `m_glyphInfoList` (не TMP 2.x `m_CharacterTable`). Таму тут свой
сыры кодэк (parse/build, build(parse(raw)) == raw), а не UnityPy-дрэва.

Што робіць apply:
  * І/і — новыя запісы, што паказваюць на гліфы лацінскіх I/i;
  * Ў/ў — новы гліф: SDF асновы У/у + брэвіс, выразаны з Й/й (поле Й/й мінус
    поле И/и); пікселі кладуцца ў атлас 512×512 (Alpha8 у `.resS`, сырыя байты
    знізу ўверх);
  * чатыры непатрэбныя беларускай мове слаты `щ ъ Щ Ъ` перанакіроўваюцца на
    новыя знакі (варыянт «на месцы»: памер аб'екта не мяняецца); іх старое
    чарніла заціраецца разам з 5 px падушкі, каб было дзе размясціць складовыя
    гліфы;
  * у `resources.assets` дапаўняецца `RussianFontLocTable`: базавыя UnitedSans*
    (галоўнае меню) пераключаюцца на Kairos RU, дзе ёсць І/і/Ў/ў. Пары — з
    `games/<гульня>/fontmap.json` (толькі назвы шрыфтоў; pathID бяруцца з гульні).

Кожны складовы прастакутнік мусіць мець 5 px чыстай падушкі (m_AtlasPadding):
атлас трымае 11 px паміж запісамі, бо TMP пашырае UV на падушку; пры 2 px
суседні Ў прасвечвае ў правым краі ў (знайшлося ў гульні 2026-11-23).

Секцыя "battletech_csv" у game.json:
  data_dir    "BattleTech_Data"                      — дзе .assets
  font_assets ["resources.assets", "sharedassets0.assets"]
  font_resS   {"resources.assets": "resources.assets.resS", …}
  fontmap     "fontmap.json"                         — адносна папкі гульні ў games/

Праверка без гульні — `belloc fonts <гульня>` (сюды ж прыходзіць --text).
"""
from __future__ import annotations

import os
import struct

import numpy as np
from PIL import Image

from ...install.paths import name as one

ALIGN = 4

# слаты, якіх няма ў беларускай азбуцы; пасля перанакіравання іх чарніла мёртвае
SLOTS = "\u0449\u044A\u0429\u042A"          # щ ъ Щ Ъ
COMPOSE = (
    ("\u0443", "\u0439", "\u0438", "\u0449", 0x045E),   # у й и → ў
    ("\u0423", "\u0419", "\u0418", "\u042A", 0x040E),   # У Й И → Ў
)
ALIASES = (("i", "\u044A", 0x0456), ("I", "\u0429", 0x0406))  # i → ъ = і, I → Щ = І
NEW_IDS = (0x0406, 0x0456, 0x040E, 0x045E)
BEL = "\u0406\u0456\u040E\u045E\u0401\u0451\u2019"
FONT_SUFFIXES = (" SDF", " SDF RU")
GLYPH_MIN_BYTES = 1000


# ---------------------------------------------------------------- кодэк TMP 1.x

FACE_FLOATS = (
    "point_size", "scale", "character_count", "line_height", "baseline",
    "ascender", "cap_height", "descender", "center_line", "superscript_offset",
    "subscript_offset", "sub_size", "underline", "underline_thickness",
    "strikethrough", "strikethrough_thickness", "tab_width", "padding",
    "atlas_width", "atlas_height",
)

GLYPH_FIELDS = ("id", "x", "y", "width", "height", "x_offset", "y_offset",
                "x_advance", "scale")
# адна кернінгавая пара: uint + 4 float + uint + 4 float + float
KERNING_SIZE = 44


class Reader:
    def __init__(self, b: bytes):
        self.b = b
        self.p = 0

    def i32(self):
        v = struct.unpack_from("<i", self.b, self.p)[0]
        self.p += 4
        return v

    def u8(self):
        v = self.b[self.p]
        self.p += 1
        return v

    def f32(self):
        v = struct.unpack_from("<f", self.b, self.p)[0]
        self.p += 4
        return v

    def i64(self):
        v = struct.unpack_from("<q", self.b, self.p)[0]
        self.p += 8
        return v

    def raw(self, n):
        v = self.b[self.p:self.p + n]
        self.p += n
        return v

    def align(self):
        self.p = (self.p + ALIGN - 1) & ~(ALIGN - 1)

    def string(self):
        n = self.i32()
        if n < 0 or self.p + n > len(self.b):
            raise ValueError("bad string length")
        s = self.raw(n).decode("utf-8")
        self.align()
        return s

    def pptr(self):
        return {"file": self.i32(), "path": self.i64()}


class Writer:
    def __init__(self):
        self.parts = []

    def i32(self, v):
        self.parts.append(struct.pack("<i", v))

    def i64(self, v):
        self.parts.append(struct.pack("<q", v))

    def f32(self, v):
        self.parts.append(struct.pack("<f", v))

    def u8(self, v):
        self.parts.append(struct.pack("<B", v))

    def raw(self, b):
        self.parts.append(b)

    def align(self):
        size = sum(len(p) for p in self.parts)
        self.parts.append(b"\0" * ((ALIGN - size % ALIGN) % ALIGN))

    def string(self, s):
        b = s.encode("utf-8")
        self.i32(len(b))
        self.raw(b)
        self.align()

    def pptr(self, v):
        self.i32(v["file"])
        self.i64(v["path"])

    def bytes(self):
        return b"".join(self.parts)


def parse(raw: bytes) -> dict:
    r = Reader(raw)
    d = {"m_GameObject": r.pptr(), "m_Enabled": r.u8()}
    r.align()
    d["m_Script"] = r.pptr()
    d["m_Name"] = r.string()
    d["hash_code"] = r.i32()
    d["material"] = r.pptr()
    d["material_hash_code"] = r.i32()
    d["font_asset_type"] = r.i32()
    d["face"] = {"name": r.string()}
    for f in FACE_FLOATS:
        d["face"][f] = r.i32() if f == "character_count" else r.f32()
    d["atlas"] = r.pptr()
    n = r.i32()
    d["glyphs"] = []
    for _ in range(n):
        g = {}
        for f in GLYPH_FIELDS:
            g[f] = r.i32() if f == "id" else r.f32()
        d["glyphs"].append(g)
    n = r.i32()
    d["kerning"] = [r.raw(KERNING_SIZE) for _ in range(n)]
    d["kerning_pair"] = r.raw(KERNING_SIZE)
    n = r.i32()
    d["fallback"] = [r.pptr() for _ in range(n)]
    cs = {}
    cs["source_font_file_name"] = r.string()
    cs["source_font_file_guid"] = r.string()
    for f in ("point_size_sampling_mode", "point_size", "padding", "packing_mode",
              "atlas_width", "atlas_height", "character_set_selection_mode"):
        cs[f] = r.i32()
    cs["character_sequence"] = r.string()
    cs["referenced_font_asset_guid"] = r.string()
    cs["referenced_text_asset_guid"] = r.string()
    cs["font_style"] = r.i32()
    cs["font_style_modifier"] = r.f32()
    cs["render_mode"] = r.i32()
    cs["include_font_features"] = r.u8()
    r.align()
    d["creation_settings"] = cs
    n = r.i32()
    d["font_weights"] = [r.raw(24) for _ in range(n)]
    d["normal_style"] = r.f32()
    d["normal_spacing_offset"] = r.f32()
    d["bold_style"] = r.f32()
    d["bold_spacing"] = r.f32()
    d["italic_style"] = r.u8()
    r.align()
    d["tab_size"] = r.u8()
    r.align()
    d["_end"] = r.p
    d["_size"] = len(raw)
    return d


def build(d: dict) -> bytes:
    w = Writer()
    w.pptr(d["m_GameObject"])
    w.u8(d["m_Enabled"])
    w.align()
    w.pptr(d["m_Script"])
    w.string(d["m_Name"])
    w.i32(d["hash_code"])
    w.pptr(d["material"])
    w.i32(d["material_hash_code"])
    w.i32(d["font_asset_type"])
    w.string(d["face"]["name"])
    for f in FACE_FLOATS:
        (w.i32 if f == "character_count" else w.f32)(d["face"][f])
    w.pptr(d["atlas"])
    w.i32(len(d["glyphs"]))
    for g in d["glyphs"]:
        for f in GLYPH_FIELDS:
            (w.i32 if f == "id" else w.f32)(g[f])
    w.i32(len(d["kerning"]))
    for k in d["kerning"]:
        w.raw(k)
    w.raw(d["kerning_pair"])
    w.i32(len(d["fallback"]))
    for f in d["fallback"]:
        w.pptr(f)
    cs = d["creation_settings"]
    w.string(cs["source_font_file_name"])
    w.string(cs["source_font_file_guid"])
    for f in ("point_size_sampling_mode", "point_size", "padding", "packing_mode",
              "atlas_width", "atlas_height", "character_set_selection_mode"):
        w.i32(cs[f])
    w.string(cs["character_sequence"])
    w.string(cs["referenced_font_asset_guid"])
    w.string(cs["referenced_text_asset_guid"])
    w.i32(cs["font_style"])
    w.f32(cs["font_style_modifier"])
    w.i32(cs["render_mode"])
    w.u8(cs["include_font_features"])
    w.align()
    w.i32(len(d["font_weights"]))
    for f in d["font_weights"]:
        w.raw(f)
    w.f32(d["normal_style"])
    w.f32(d["normal_spacing_offset"])
    w.f32(d["bold_style"])
    w.f32(d["bold_spacing"])
    w.u8(d["italic_style"])
    w.align()
    w.u8(d["tab_size"])
    w.align()
    return w.bytes()


# ---------------------------------------------------------------- гліфы і атлас

def fonts(env):
    """(object, font dict) для кірылічных TMP 1.x шрыфтоў у env."""
    for o in env.objects:
        if o.type.name != "MonoBehaviour":
            continue
        try:
            h = o.parse_monobehaviour_head()
        except Exception:
            continue
        name = getattr(h, "m_Name", "") or ""
        if not name.endswith(FONT_SUFFIXES) or len(o.get_raw_data()) < GLYPH_MIN_BYTES:
            continue
        try:
            font = parse(o.get_raw_data())
        except Exception:
            continue
        if 0x0410 not in {int(g["id"]) for g in font["glyphs"]}:
            continue
        yield o, font


def glyph(font: dict, ch: str):
    return next((g for g in font["glyphs"] if g["id"] == ord(ch)), None)


def atlas_alpha(tex, resS: str):
    """Alpha-масіў атласа (зверху ўніз) і m_StreamData з .resS."""
    td = tex.read_typetree()
    if int(td.get("m_TextureFormat", -1)) != 1:      # Alpha8
        raise SystemExit(f"атлас {td.get('m_Name')!r}: чакаўся Alpha8")
    w, h = int(td["m_Width"]), int(td["m_Height"])
    sd = td.get("m_StreamData") or {}
    if not sd.get("path"):
        raise SystemExit(f"атлас {td.get('m_Name')!r}: пікселі ў .assets, а не ў .resS")
    size = int(sd["size"])
    if size != w * h:
        raise SystemExit(f"атлас {td.get('m_Name')!r}: {size} байт не {w}×{h}")
    with open(resS, "rb") as f:
        f.seek(int(sd["offset"]))
        raw = f.read(size)
    if len(raw) != size:
        raise SystemExit(f"атлас {td.get('m_Name')!r}: пашкоджаны .resS")
    return np.frombuffer(raw, np.uint8).reshape(h, w)[::-1].copy()


def tile(atlas, g):
    x, y, w, h = (int(round(g[k])) for k in ("x", "y", "width", "height"))
    return atlas.crop((x, y, x + w, y + h))


def compose(atlas, font, base, donor, minus):
    gb, gd, gm = (glyph(font, ch) for ch in (base, donor, minus))
    b, d, m = tile(atlas, gb), tile(atlas, gd), tile(atlas, gm)
    breve_h = max(1, d.height - m.height)
    breve = d.crop((0, 0, d.width, breve_h))
    w = max(b.width, breve.width)
    h = b.height + breve_h
    img = Image.new("L", (w, h), 0)
    img.paste(b, ((w - b.width) // 2, breve_h))
    img.paste(breve, ((w - breve.width) // 2, 0))
    return img, breve_h, gb


def free_mask(atlas, thr=8, pad=1):
    free = np.array(atlas) <= thr
    for _ in range(pad):
        f = free.copy()
        free[1:, :] &= f[:-1, :]
        free[:-1, :] &= f[1:, :]
        free[:, 1:] &= f[:, :-1]
        free[:, :-1] &= f[:, 1:]
    return free


def free_rect(mask, w, h):
    if h > mask.shape[0] or w > mask.shape[1]:
        return None
    win = np.lib.stride_tricks.sliding_window_view(mask, (h, w))
    ys, xs = np.nonzero(win.all(axis=(2, 3)))
    return (int(xs[0]), int(ys[0])) if len(xs) else None


def free_rect_fit(mask, w, h, pad):
    """Першы вольны прастакутнік; калі атлас цесны — памяншаем гліф.

    pad — m_AtlasPadding: атлас трымае столькі чыстай падушкі вакол кожнага
    запісу, бо TMP пашырае UV на падушку. Пры 2 px суседні Ў прасвечвае ў
    правым краі ў (так было ў першай праўцы).
    """
    for scale in (1.0, .95, .9, .85, .8, .75, .7, .6, .5):
        tw, th = max(2, int(round(w * scale))), max(2, int(round(h * scale)))
        pos = free_rect(mask, tw + 2 * pad + 2, th + 2 * pad + 2)
        if pos is not None:
            return pos, scale, tw, th
    return None, None, None, None


def patch_font(font: dict, atlas, name: str, log=print):
    """Скласці Ў/ў і перанакіраваць чатыры слаты. Вяртае запісы новых гліфаў."""
    gs = {int(g["id"]): g for g in font["glyphs"]}
    have = {i for i in NEW_IDS if i in gs}
    if len(have) == len(NEW_IDS):
        return []                                  # ужо папраўлены
    if have:
        raise SystemExit(f"{name}: часткова гатовыя ІіЎў — спачатку вярніце арыгіналы")
    need = {ord(c) for c in "\u0443\u0439\u0438\u0423\u0419\u0418" + SLOTS}
    missing = sorted(chr(i) for i in need if i not in gs)
    if missing:
        raise SystemExit(f"{name}: няма гліфаў для складання: {''.join(missing)}")
    pad = int(round(font["face"].get("padding") or 0))

    # слаты мёртвыя пасля перанакіравання; заціраем іх разам з падушкай
    for ch in SLOTS:
        g = glyph(font, ch)
        x, y = int(round(g["x"])), int(round(g["y"]))
        w, h = int(round(g["width"])), int(round(g["height"]))
        atlas.paste(0, (max(0, x - pad), max(0, y - pad),
                        min(atlas.width, x + w + pad), min(atlas.height, y + h + pad)))
    mask = free_mask(atlas)
    changes = []
    for base, donor, minus, slot, code in COMPOSE:
        img, breve_h, gb = compose(atlas, font, base, donor, minus)
        pos, scale, tw, th = free_rect_fit(mask, img.width, img.height, pad)
        if pos is None:
            raise SystemExit(f"{name}: няма вольнага прастакутніка для {base}")
        if scale != 1.0:
            img = img.resize((tw, th), Image.LANCZOS)
            log(f"  {name}: {base} паменшаны да {scale:.2f} ({tw}×{th})")
        x, y = pos[0] + pad + 1, pos[1] + pad + 1
        mask[y - 1:y + th + 1, x - 1:x + tw + 1] = False
        atlas.paste(img, (x, y))
        rec = dict(gb)
        rec.update(id=code, x=x, y=y, width=tw, height=th,
                   y_offset=gb["y_offset"] + breve_h * scale,
                   x_offset=gb["x_offset"] - (tw - gb["width"] * scale) / 2)
        changes.append((slot, rec))
    for src, slot, code in ALIASES:
        rec = dict(glyph(font, src))
        rec["id"] = code
        changes.append((slot, rec))
    for slot, rec in changes:
        target = glyph(font, slot)
        target.clear()
        target.update(rec)
    return [r for _s, r in changes]


def report(assets: str, resS: str, need: set[int] | None = None):
    """Справаздача па кірылічных шрыфтах для `belloc fonts`."""
    import UnityPy
    env = UnityPy.load(assets)
    tex = {o.path_id: o for o in env.objects if o.type.name == "Texture2D"}
    found = False
    for _o, font in fonts(env):
        found = True
        ids = {int(g["id"]) for g in font["glyphs"]}
        bel = "".join(ch for ch in BEL if ord(ch) in ids) or "—"
        td = tex[font["atlas"]["path"]].read_typetree()
        line = (f"{font['m_Name'][:34]:34} стат.  {len(ids):4} сімв.  кірыліца     "
                f"з «{BEL}»: {bel:8} [атлас {int(td['m_Width'])}×{int(td['m_Height'])}]")
        if need is not None:
            missing = "".join(sorted(chr(c) for c in need - ids))
            line += f"\n    не хапае для перакладу: {missing or '—'}"
        print(line)
    if not found:
        print(f"кірылічных TMP 1.x шрыфтоў няма: {assets}")


# ---------------------------------------------------------------- FontLocTable

def _read_string(blob: bytes, p: int) -> str:
    n = struct.unpack_from("<i", blob, p)[0]
    if n < 0 or n > 200:
        raise ValueError(f"bad string at {p}: {n}")
    return blob[p + 4:p + 4 + n].decode("utf-8", "replace")


def table_parse(raw: bytes):
    name = _read_string(raw, 28)
    q = 28 + 4 + len(name.encode())
    q = (q + 3) & ~3
    culture, count = struct.unpack_from("<ii", raw, q)
    pairs = []
    for k in range(count):
        off = q + 8 + k * 24
        pairs.append((struct.unpack_from("<q", raw, off + 4)[0],
                      struct.unpack_from("<q", raw, off + 16)[0]))
    return name, culture, count, q, pairs


def table_patch(raw: bytes, add: list[tuple[int, int]]) -> bytes:
    _name, _culture, count, q, pairs = table_parse(raw)
    have = {b for b, _ in pairs}
    add = [(b, r) for b, r in add if b not in have]
    if not add:
        return raw
    out = bytearray(raw)
    struct.pack_into("<i", out, q + 4, count + len(add))
    for b, r in add:
        out += struct.pack("<iqiq", 0, b, 0, r)
    return bytes(out)


def _font_ids(env) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for o in env.objects:
        if o.type.name != "MonoBehaviour":
            continue
        try:
            h = o.parse_monobehaviour_head()
        except Exception:
            continue
        name = getattr(h, "m_Name", "") or ""
        if name.endswith(FONT_SUFFIXES):
            out.setdefault(name, []).append(o.path_id)
    return out


def patch_fontmap(env, cfg: dict, log=print) -> int:
    """Дапісаць пары з fontmap.json у RussianFontLocTable. Вяртае колькасць."""
    table = None
    for o in env.objects:
        if o.type.name != "MonoBehaviour":
            continue
        try:
            h = o.parse_monobehaviour_head()
        except Exception:
            continue
        if (getattr(h, "m_Name", "") or "") == cfg.get("table", "RussianFontLocTable"):
            table = o
            break
    if table is None:
        return 0                                   # у гэтым файле табліцы няма
    raw = table.get_raw_data()
    name, culture, _count, _q, pairs = table_parse(raw)
    if culture != 6:                                # ru-RU
        raise SystemExit(f"{name}: culture {culture} ≠ ru-RU (6)")
    known = _font_ids(env)
    add = []
    for base, repl in cfg.get("pairs", []):
        bases, repls = known.get(base), known.get(repl)
        if not bases or not repls:
            log(f"  FontLocTable: няма шрыфта {base!r} або {repl!r} — прапускаю пару")
            continue
        target = next((i for i in repls if i in {r for _, r in pairs}), repls[0])
        add += [(b, target) for b in bases]
    new = table_patch(raw, add)
    if new == raw:
        return 0
    table.set_raw_data(new)
    return len(table_parse(new)[4]) - len(pairs)


# ---------------------------------------------------------------- apply

def patch_pair(assets: str, resS: str, fontmap: dict | None, log=print,
               resS_name: str | None = None):
    """Патчыць усе кірылічныя шрыфты аднаго .assets/.resS.

    resS — файл для чытання (можа быць .orig); resS_name — лагічнае імя ў гульні
    (з game.json), каб праверыць, што атлас менавіта ў гэтым .resS.

    Вяртае (env, slices, changed): env з новымі raw-данымі, слайсы .resS
    [(offset, bytes, size)] і колькасць змен. Запіс файлаў — у apply.py.
    """
    import UnityPy
    expected = one(os.path.basename(resS_name or resS))
    env = UnityPy.load(assets)
    textures = {o.path_id: o for o in env.objects if o.type.name == "Texture2D"}
    slices = []
    changed = 0
    for o, font in fonts(env):
        name = font["m_Name"]
        tex = textures.get(font["atlas"]["path"])
        if tex is None:
            raise SystemExit(f"{name}: няма аб'екта атласа")
        td = tex.read_typetree()
        sd = td.get("m_StreamData") or {}
        if (sd.get("path") or "") and one(os.path.basename(sd["path"])) != expected:
            raise SystemExit(f"{name}: атлас у {sd['path']!r}, а чакаўся {expected!r}")
        old = o.get_raw_data()
        img = Image.fromarray(atlas_alpha(tex, resS), "L")
        recs = patch_font(font, img, name, log)
        if not recs:
            continue
        new = build(font)
        if len(new) != len(old):
            raise SystemExit(f"{name}: памер аб'екта змяніўся ({len(old)} → {len(new)})")
        back = parse(new)
        if build(back) != new:
            raise SystemExit(f"{name}: кодэк не склаўся назад")
        if not set(NEW_IDS) <= {int(g["id"]) for g in back["glyphs"]}:
            raise SystemExit(f"{name}: пасля зборкі няма ІіЎў")
        o.set_raw_data(new)
        slices.append((int(sd["offset"]), np.array(img)[::-1].tobytes(), int(sd["size"])))
        changed += 1
        log(f"  {name}: +{''.join(chr(r['id']) for r in recs if r['id'] in NEW_IDS)}")
    if fontmap:
        changed += patch_fontmap(env, fontmap, log)
    return env, slices, changed
