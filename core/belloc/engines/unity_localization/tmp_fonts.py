"""TextMeshPro-шрыфты ў Unity-бандлах: справаздача і беларускія літары.

Статычны атлас (m_AtlasPopulationMode = 0) малюе толькі тыя літары, што ў
ім ужо ёсць. У рускіх шрыфтах звычайна няма І/і і Ў/ў. Калі TTF у гульні
няма, літары можна сабраць з таго, што ўжо ёсць у атласе:

  і, І  — новыя сімвалы ў m_CharacterTable, якія паказваюць на гліфы
          лацінскіх i, I (начартанне тое самае);
  ў, Ў  — новы гліф: SDF літары у/У + брэвіс, выразаны з й/Й (поле й мінус
          поле и). SDF-палі складаюцца праз max — гэта аб'яднанне фігур.

Новыя гліфы кладуцца ў дапісаную зверху паласу атласа: вышыня тэкстуры
расце, а старыя прастакутнікі гліфаў (адлік знізу) не зрушваюцца;
_TextureHeight матэрыялу правіцца разам з ёй.

Секцыя "unity" у game.json: font_bundles — спіс бандлаў, у якіх
патчыць кірылічныя шрыфты (астатнія не чапаюцца); font_assets — класічныя
файлы (адносна data_dir), у якіх ляжаць свае копіі тых жа шрыфтоў
(resources.assets). Копіі шукаць праз Resources: `belloc fonts` бачыць толькі бандлы.
"""
from __future__ import annotations

import glob
import os

import numpy as np
import UnityPy
from PIL import Image
from UnityPy.enums import TextureFormat

from ..unity.bundles import monobehaviours, save

ALIASES = {"і": "i", "І": "I"}          # новы сімвал → гліф лацінкі
COMPOSE = {"ў": ("у", "й", "и"),        # новы → (аснова, донар брэвіса, донар без яго)
           "Ў": ("У", "Й", "И")}
NEW_GLYPH_BASE = 60000                   # індэксы новых гліфаў (у атласах не заняты)
BEL = "ІіЎўЁё’"


# ---------------------------------------------------------------- справаздача

def report(bundles_dir: str, need: set[int] | None = None):
    pats = ["fonts*.bundle", "localization-assets-*.bundle", "*font*.bundle"]
    paths = sorted({p for pat in pats for p in glob.glob(os.path.join(bundles_dir, pat))})
    for p in paths:
        for _, t in monobehaviours(p):
            if "m_CharacterTable" not in t:
                continue
            cs = {c["m_Unicode"] for c in t["m_CharacterTable"]}
            cyr = "кірыліца" if 0x0410 in cs else "без кірыліцы"
            bel = "".join(ch for ch in BEL if ord(ch) in cs) or "—"
            mode = "дынам." if t.get("m_AtlasPopulationMode") else "стат."
            line = (f"{t['m_Name'][:34]:34} {mode:6} {len(cs):4} сімв.  {cyr:12} "
                    f"з «{BEL}»: {bel:8} [{os.path.basename(p)[:45]}]")
            if need and 0x0410 in cs:
                miss = "".join(sorted(chr(c) for c in need - cs))
                line += f"\n    не хапае для перакладу: {miss or '—'}"
            print(line)


# ---------------------------------------------------------------- патч атласаў

class Atlas:
    """SDF-атлас як масіў uint8, радок 0 — нізам (як у TMP)."""

    def __init__(self, img: Image.Image):
        self.a = np.flipud(np.array(img.getchannel("A"), dtype=np.uint8)).copy()

    def tile(self, rect, pad):
        x, y, w, h = rect["m_X"], rect["m_Y"], rect["m_Width"], rect["m_Height"]
        return self.a[y - pad:y + h + pad, x - pad:x + w + pad].astype(np.int16)

    def image(self) -> Image.Image:
        a = np.flipud(self.a)
        img = Image.new("RGBA", (a.shape[1], a.shape[0]), (255, 255, 255, 0))
        img.putalpha(Image.fromarray(a, "L"))
        return img


def place(canvas, org, tile, tile_org):
    """Кладзе tile (пачатак tile_org у прасторы гліфа) у canvas праз max."""
    y0, x0 = tile_org[1] - org[1], tile_org[0] - org[0]
    # абрэзаць па межах canvas (у рукапісных шрыфтах й і и бываюць рознай шырыні)
    ty, tx = max(0, -y0), max(0, -x0)
    y0, x0 = max(0, y0), max(0, x0)
    h = min(tile.shape[0] - ty, canvas.shape[0] - y0)
    w = min(tile.shape[1] - tx, canvas.shape[1] - x0)
    if h <= 0 or w <= 0:
        return
    region = canvas[y0:y0 + h, x0:x0 + w]
    canvas[y0:y0 + h, x0:x0 + w] = np.maximum(region, tile[ty:ty + h, tx:tx + w])


def compose(atlas, pad, g_base, g_donor, g_ref):
    """Вяртае (tile, metrics) для асновы з брэвісам донара."""
    def origin(g):  # пачатак пліткі (з падушкай) у прасторы гліфа, пікселі
        m = g["m_Metrics"]
        return (round(m["m_HorizontalBearingX"]) - pad,
                round(m["m_HorizontalBearingY"] - m["m_Height"]) - pad)

    base, donor, ref = (atlas.tile(g["m_GlyphRect"], pad) for g in (g_base, g_donor, g_ref))
    # брэвіс = поле донара там, дзе яно мацнейшае за поле літары без брэвіса
    ref_al = np.zeros_like(donor)
    place(ref_al, origin(g_donor), ref, origin(g_ref))
    breve = np.where(donor > ref_al + 2, donor, 0)
    # і толькі вышэй за верх літары: у рукапісным Bad Script й і И
    # намаляваныя па-рознаму, і рознасць палёў чапляе цела літары
    ref_top = round(g_ref["m_Metrics"]["m_HorizontalBearingY"])
    rows = origin(g_donor)[1] + np.arange(donor.shape[0])
    breve[rows < ref_top - 2, :] = 0

    def center(g):
        m = g["m_Metrics"]
        return m["m_HorizontalBearingX"] + m["m_Width"] / 2
    dx = round(center(g_base) - center(g_donor))
    bo, do = origin(g_base), origin(g_donor)
    do = (do[0] + dx, do[1])

    lo = (min(bo[0], do[0]), min(bo[1], do[1]))
    hi = (max(bo[0] + base.shape[1], do[0] + breve.shape[1]),
          max(bo[1] + base.shape[0], do[1] + breve.shape[0]))
    canvas = np.zeros((hi[1] - lo[1], hi[0] - lo[0]), dtype=np.int16)
    place(canvas, lo, base, bo)
    place(canvas, lo, breve, do)

    ink = np.argwhere(canvas >= 128)
    y_top = lo[1] + ink[:, 0].max() + 1           # верх фарбы ў прасторы гліфа
    mb = g_base["m_Metrics"]
    rw, rh0 = g_base["m_GlyphRect"]["m_Width"], g_base["m_GlyphRect"]["m_Height"]
    bottom = bo[1] + pad                           # ніз прастакутніка асновы
    rh = max(rh0, y_top - bottom)
    x0, y0 = bo[0] - lo[0], bo[1] - lo[1]
    tile = canvas[y0:y0 + rh + 2 * pad, x0:x0 + rw + 2 * pad]
    if tile.shape != (rh + 2 * pad, rw + 2 * pad):  # брэвіс шырэйшы за аснову — рэдка
        full = np.zeros((rh + 2 * pad, rw + 2 * pad), dtype=np.int16)
        full[:tile.shape[0], :tile.shape[1]] = tile
        tile = full
    bottom_f = mb["m_HorizontalBearingY"] - mb["m_Height"]
    metrics = dict(mb)
    metrics["m_HorizontalBearingY"] = float(y_top)
    metrics["m_Height"] = float(y_top - bottom_f)
    return tile.clip(0, 255).astype(np.uint8), metrics


def patch_font(t, atlas, pad, log=print):
    chars = {c["m_Unicode"]: c for c in t["m_CharacterTable"]}
    glyphs = {g["m_Index"]: g for g in t["m_GlyphTable"]}
    g_of = lambda ch: glyphs[chars[ord(ch)]["m_GlyphIndex"]]
    added = []

    for new, src in ALIASES.items():
        if ord(new) in chars or ord(src) not in chars:
            continue
        t["m_CharacterTable"].append({"m_ElementType": 1, "m_Unicode": ord(new),
                                      "m_GlyphIndex": chars[ord(src)]["m_GlyphIndex"],
                                      "m_Scale": 1.0})
        added.append(new)

    tiles = []
    for new, (b, d, r) in COMPOSE.items():
        if ord(new) in chars or not all(ord(c) in chars for c in (b, d, r)):
            continue
        tile, metrics = compose(atlas, pad, g_of(b), g_of(d), g_of(r))
        tiles.append((new, tile, metrics, g_of(b)))

    if tiles:
        # дапісаная зверху паласа: пліткі ў радок злева направа
        H, W = atlas.a.shape
        strip_h = max(tl.shape[0] for _, tl, _, _ in tiles) + 2
        new_h = H + -(-strip_h // 32) * 32
        grown = np.zeros((new_h, W), dtype=np.uint8)
        grown[:H] = atlas.a
        atlas.a = grown
        x = 1
        index = max(max(glyphs), NEW_GLYPH_BASE)
        for new, tile, metrics, gb in tiles:
            th, tw = tile.shape
            if x + tw > W:
                raise SystemExit(f"{t['m_Name']}: паласа не ўмяшчае гліфы")
            atlas.a[H + 1:H + 1 + th, x:x + tw] = tile
            index += 1
            rect = {"m_X": x + pad, "m_Y": H + 1 + pad,
                    "m_Width": tw - 2 * pad, "m_Height": th - 2 * pad}
            t["m_GlyphTable"].append({**gb, "m_Index": index, "m_Metrics": metrics,
                                      "m_GlyphRect": rect})
            t["m_UsedGlyphRects"].append({"m_X": x, "m_Y": H + 1,
                                          "m_Width": tw, "m_Height": th})
            t["m_CharacterTable"].append({"m_ElementType": 1, "m_Unicode": ord(new),
                                          "m_GlyphIndex": index, "m_Scale": 1.0})
            added.append(new)
            x += tw + 1
        t["m_AtlasHeight"] = new_h
    log(f"  {t['m_Name']:28} +{''.join(added) or '—'}  атлас {atlas.a.shape[1]}×{atlas.a.shape[0]}")
    return bool(added)


def set_material_height(mat_obj, height):
    m = mat_obj.read_typetree()
    floats = m["m_SavedProperties"]["m_Floats"]
    for i, (name, _) in enumerate(floats):
        if name == "_TextureHeight":
            floats[i] = (name, float(height))
    mat_obj.save_typetree(m)


def _fonts(env, nodes=None):
    """(obj, typetree) кірылічных TMP-шрыфтоў. nodes — тыпавое дрэва TMP_FontAsset для
    файлаў без яго (класічныя .assets гульні)."""
    for o in env.objects:
        if o.type.name != "MonoBehaviour":
            continue
        try:
            t = o.read_typetree(nodes) if nodes is not None else o.read_typetree()
        except Exception:
            continue
        if "m_CharacterTable" in t and 0x0410 in {c["m_Unicode"] for c in t["m_CharacterTable"]}:
            yield o, t


def _patch_env(env, preview: list | None, nodes=None):
    objs = {o.path_id: o for o in env.objects}
    for o, t in list(_fonts(env, nodes)):
        tex_obj = objs[t["m_AtlasTextures"][0]["m_PathID"]]
        tex = tex_obj.read()
        atlas = Atlas(tex.image)
        if not patch_font(t, atlas, t["m_AtlasPadding"]):
            continue
        o.save_typetree(t, nodes) if nodes is not None else o.save_typetree(t)
        tex.set_image(atlas.image(), target_format=TextureFormat.Alpha8)   # дадзеныя — у файле, без .resS
        tex.save()
        set_material_height(objs[t["m_Material"]["m_PathID"]], t["m_AtlasHeight"])
        if preview is not None:
            preview.append((t, atlas))


def patch_bundle(base: str, out: str, preview: list | None):
    """Патчыць кірылічныя шрыфты бандла base і піша вынік у out."""
    env = UnityPy.load(base)
    print(os.path.basename(out))
    _patch_env(env, preview)
    save(env, out)


def font_type_tree(bundle: str):
    """Тыпавое дрэва TMP_FontAsset з бандла (у бандлах Addressables яно ёсць)."""
    for o, _ in _fonts(UnityPy.load(bundle)):
        return o.serialized_type.node
    return None


def patch_assets(base: str, out: str, nodes, preview: list | None = None):
    """Тое ж для класічнага .assets (resources.assets): у ім свае копіі шрыфтоў, тыпавога
    дрэва няма — яго дае font_type_tree. Silver Pines: экраны вынікаў і «Новай гульні+»
    бяруць Montserrat з Resources."""
    env = UnityPy.load(base)
    print(os.path.basename(out))
    _patch_env(env, preview, nodes)
    save(env, out)


def render_preview(items, out):
    """Новыя гліфы побач з асновамі — для вачэй (парог SDF 0.5)."""
    rows = []
    for t, atlas in items:
        chars = {c["m_Unicode"]: c for c in t["m_CharacterTable"]}
        glyphs = {g["m_Index"]: g for g in t["m_GlyphTable"]}
        pad = t["m_AtlasPadding"]
        cells = []
        for ch in "уўУЎiіIІйЙ":
            if ord(ch) not in chars:
                continue
            g = glyphs[chars[ord(ch)]["m_GlyphIndex"]]
            tile = atlas.tile(g["m_GlyphRect"], pad)
            m = g["m_Metrics"]
            # ставім на агульную базавую лінію
            top = int(t["m_FaceInfo"]["m_AscentLine"]) + pad
            cell = np.zeros((top + int(-t["m_FaceInfo"]["m_DescentLine"]) + 2 * pad,
                             tile.shape[1]), dtype=np.int16)
            y0 = top - round(m["m_HorizontalBearingY"]) - pad
            img = np.flipud(tile)
            cell[max(y0, 0):y0 + img.shape[0], :] = img[max(-y0, 0):cell.shape[0] - y0]
            cells.append(np.where(cell >= 128, 0, 255).astype(np.uint8))
        h = max(c.shape[0] for c in cells)
        row = np.hstack([np.pad(c, ((0, h - c.shape[0]), (4, 4)), constant_values=255) for c in cells])
        rows.append(row)
    w = max(r.shape[1] for r in rows)
    sheet = np.vstack([np.pad(r, ((4, 4), (0, w - r.shape[1])), constant_values=255) for r in rows])
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    Image.fromarray(sheet, "L").save(out)
    print("прэв'ю:", out)

