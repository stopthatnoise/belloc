"""Тэст у гульні: ці прыме Great Circle зменены рэсурс lang/strings (руская).

Бярэ gameresources_patch1_pc.resources (з .orig, калі ёсць), мяняе ў рускай
табліцы некалькі радкоў меню на беларускія з літарамі ІіЎў «»’—, дапісвае
новыя даныя ў канец файла без сціску (comp=0) і пераводзіць на іх запіс
рэсурсу. Хэшы — FarmHash64 na (farm.py): кантрольная сума даных у запісе
(+80 і +96), табліцы [0x88, idxend+4) → @0x80, загаловак [0x14, 0x88) → @0x08.
Без іх гульня падае адразу пасля адкрыцця асноўнага кантэйнера (тэст 2026-11-04).
packagemapspec_pc.json не чапаецца.

python -I -X utf8 patch_test.py <папка research> <base гульні> --out FILE
python -I -X utf8 patch_test.py <папка research> <base гульні> --install
python -I -X utf8 patch_test.py <папка research> <base гульні> --restore
"""
import os, shutil, struct, sys

sys.path.insert(0, sys.argv[1])
import farm, idcl, ooz

G = sys.argv[2]
NAME = 'gameresources_patch1_pc.resources'
RU = 0x1aa
TEST = {
    '#str_code_settings_language_ru_ru': 'Беларуская',
    '#str_code_mainmenu_root_header_play': 'ГУЛЯЦЬ ІіЎў «»’—',
    '#str_code_mainmenu_start_text': 'Націсніце %s — ІіЎў «тэст»',
    '#str_code_mainmenu_campaign_options': 'НАЛАДЫ',
    '#str_code_mainmenu_campaign_continue_game': 'ПРАЦЯГНУЦЬ',
    '#str_code_mainmenu_campaign_new_game': 'НОВАЯ ГУЛЬНЯ',
    '#str_dlg_quit_to_desktop': 'Выйсці з гульні? Ўсё, што не захавана, — знікне. ІіЎў',
}


def parse(d):
    pos, out = 8, []
    while pos < len(d):
        h, kl = struct.unpack_from('<II', d, pos); pos += 8
        k = d[pos:pos + kl].decode(); pos += kl + 1
        tl, = struct.unpack_from('<I', d, pos); pos += 4
        out.append([h, k, d[pos:pos + tl].decode()]); pos += tl + 1
    return out


def build(items):
    body = bytearray()
    for h, k, t in items:
        kb, tb = k.encode(), t.encode()
        body += struct.pack('<II', h, len(kb)) + kb + b'\0' + struct.pack('<I', len(tb)) + tb + b'\0'
    return struct.pack('<I', len(body) + 4) + struct.pack('>I', len(items)) + bytes(body)


def make(src):
    data = bytearray(open(src, 'rb').read())
    entoff, = struct.unpack_from('<Q', data, 0x54)
    R = idcl.read(src)
    i = next(i for i, x in enumerate(R) if x['type'] == 'lang'
             and struct.unpack_from('<H', data, entoff + i * 144 + 114)[0] == RU)
    x = R[i]
    raw = bytes(data[x['off']:x['off'] + x['size']])
    d = ooz.decompress(raw, x['usize']) if x['comp'] else raw
    items = parse(d)
    assert build(items) == d, 'зборка не супадае з арыгіналам'
    n = 0
    for it in items:
        if it[1] in TEST: it[2] = TEST[it[1]]; n += 1
    new = build(items)
    off = (len(data) + 0xfff) & ~0xfff
    data += b'\0' * (off - len(data)) + new
    e = entoff + i * 144
    struct.pack_into('<QQQ', data, e + 56, off, len(new), len(new))
    flags, = struct.unpack_from('<I', data, e + 108)
    struct.pack_into('<I', data, e + 108, flags & ~2)
    data[e + 112] = 0
    cks = farm.na(new)
    struct.pack_into('<Q', data, e + 80, cks)
    struct.pack_into('<Q', data, e + 96, cks)
    idxend, = struct.unpack_from('<I', data, 0x78)
    struct.pack_into('<Q', data, 0x80, farm.na(bytes(data[0x88:idxend + 4])))
    struct.pack_into('<Q', data, 0x08, farm.na(bytes(data[0x14:0x88])))
    print(f'радкоў зменена: {n}/{len(TEST)}; рэсурс {i}: {x["size"]} → {len(new)} байт @ {off}')
    return bytes(data)


if __name__ == '__main__':
    path = os.path.join(G, NAME)
    orig = path + '.orig'
    if '--restore' in sys.argv:
        shutil.copyfile(orig, path); os.remove(orig); print('вернута', path); sys.exit()
    src = orig if os.path.exists(orig) else path
    out = make(src)
    if '--install' in sys.argv:
        if not os.path.exists(orig): shutil.copyfile(path, orig)
        open(path, 'wb').write(out); print('запісана', path)
    else:
        dst = sys.argv[sys.argv.index('--out') + 1]
        open(dst, 'wb').write(out); print('запісана', dst)
