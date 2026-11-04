"""id Tech (Motor) .resources IDCL v13: табліца рэсурсаў (тып, імя, зрушэнне, сціск).

Запіс 144 байты, як у DOOM Eternal; тып/імя — адносныя індэксы ў масіве радкоў
ад поля strings; канец масіва індэксаў — u32 у загалоўку @0x78.
python -I idcl.py <файл.resources>…
"""
import struct, sys, collections


def read(fn):
    f = open(fn, 'rb')
    h = f.read(0x88)
    assert h[:4] == b'IDCL'
    nres, = struct.unpack_from('<I', h, 0x24)
    nstridx, = struct.unpack_from('<I', h, 0x30)
    strsize, = struct.unpack_from('<I', h, 0x3c)
    stroff, metaoff, entoff, depoff, shoff, dataoff = struct.unpack_from('<6Q', h, 0x44)
    idxend, = struct.unpack_from('<I', h, 0x78)
    f.seek(stroff)
    st = f.read(strsize)
    n, = struct.unpack_from('<Q', st, 0)
    offs = struct.unpack_from('<%dQ' % n, st, 8)
    base = 8 + 8 * n
    names = [st[base + o:st.index(b'\0', base + o)].decode('utf-8', 'replace') for o in offs]
    f.seek(idxend - 8 * nstridx)
    idx = struct.unpack('<%dQ' % nstridx, f.read(8 * nstridx))
    f.seek(entoff)
    E = f.read(144 * nres)
    res = []
    for i in range(nres):
        e = E[i * 144:(i + 1) * 144]
        (t, nm, desc, dep, strs, sh, me, doff, dsize, usize, cks, ts, dh) = struct.unpack_from('<qqqQQQQQQQQQQ', e, 0)
        ver, flags, comp, r0, var = struct.unpack_from('<IIBBH', e, 104)
        res.append(dict(type=names[idx[strs + t]], name=names[idx[strs + nm]], off=doff, size=dsize,
                        usize=usize, comp=comp, ver=ver, flags=flags, file=fn))
    return res


if __name__ == '__main__':
    for fn in sys.argv[1:]:
        r = read(fn)
        c = collections.Counter(x['type'] for x in r)
        print('==', fn, len(r))
        print(dict(c.most_common(80)))
        for x in r:
            if x['type'] in ('lang', 'credits') or 'font' in x['type'] or 'string' in x['type']:
                print(x)
