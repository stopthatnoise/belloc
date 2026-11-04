"""Распакоўвае lang і credits (Oodle праз pyooz) у out/.
python -I -X utf8 dump.py <папка research> <base гульні> <out>
"""
import sys, struct
sys.path.insert(0, sys.argv[1])
import idcl, ooz
G = sys.argv[2]; out = sys.argv[3]
for fn in ['gameresources_pc.resources', 'gameresources_patch1_pc.resources', 'gameresources_patch2_pc.resources']:
    p = G + '/' + fn
    f = open(p, 'rb'); h = f.read(0x88)
    entoff = struct.unpack_from('<Q', h, 0x54)[0]
    for i, x in enumerate(idcl.read(p)):
        if x['type'] not in ('lang', 'credits'): continue
        f.seek(entoff + i * 144); e = f.read(144)
        f.seek(x['off']); raw = f.read(x['size'])
        data = raw
        if x['comp']:
            for skip in (0, 12, 16):
                try:
                    d = ooz.decompress(raw[skip:], x['usize'])
                    if len(d) == x['usize']: data = d; break
                except Exception as ex:
                    pass
            else:
                print('fail', fn, i); continue
        tag = fn.split('_')[1].replace('pc.resources', 'base').replace('.resources', '')
        name = f"{out}/{tag}_{i}_{x['type']}.bin"
        open(name, 'wb').write(data)
        print(name, len(data), e[100:144].hex())
