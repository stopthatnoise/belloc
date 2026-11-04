"""Шрыфты гульні скампіляваныя ў Slug (магія "guls"): з 0x1c0 табліца
старонак 256 x u16 (код >> 8 → блок, 0xffff — няма), за ёй блокі па
256 x u32 (індэкс гліфа, 0 — няма). Шрыфт — рэсурс rs_emb_sfile
"font#<шлях>#0" (Oodle), памер распакаванага — u32 у заглушцы рэсурсу font.
Друкуе пакрыццё кірыліцы.
python -I -X utf8 slugcmap.py <папка research> <base гульні>
"""
import sys, struct
sys.path.insert(0, sys.argv[1]); import idcl, ooz

TBL = 0x1c0


def cmap(d):
    pages = struct.unpack_from('<256H', d, TBL)
    base = TBL + 512
    cps = set()
    for page, b in enumerate(pages):
        if b == 0xffff: continue
        g = struct.unpack_from('<256I', d, base + b * 1024)
        cps |= {page * 256 + i for i, x in enumerate(g) if x}
    return cps


if __name__ == '__main__':
    G = sys.argv[2]; stub = {}; data = {}
    for fn in ['gameresources_pc.resources', 'gameresources_patch1_pc.resources', 'gameresources_patch2_pc.resources']:
        for x in idcl.read(G + '/' + fn):
            if x['type'] == 'font': stub[x['name']] = x
            if x['type'] == 'rs_emb_sfile' and x['name'].startswith('font#'): data[x['name'].split('#')[1]] = x
    need = 'ІіЎў«»’—…'
    for name, s in sorted(stub.items()):
        f = open(s['file'], 'rb'); f.seek(s['off']); st = f.read(s['size'])
        if s['size'] == 8 and name in data:
            usize, = struct.unpack_from('<I', st, 0)
            x = data[name]; f = open(x['file'], 'rb'); f.seek(x['off'])
            d = ooz.decompress(f.read(x['size']), usize)
        elif s['size'] > 8:
            d = ooz.decompress(st, s['usize']) if s['comp'] else st
        else:
            print(f'{name:58} ?'); continue
        if d[:4] != b'guls': print(f'{name:58} не Slug'); continue
        c = cmap(d)
        cyr = sum(1 for u in c if 0x400 <= u < 0x500)
        print(f'{name:58} glyphs={len(c):4} cyr={cyr:3} missing={"".join(ch for ch in need if ord(ch) not in c)}')
