"""Glacier 2 (007 First Light 1.3.1.0): чытанне rpkg, LOCR, DLGE, packagedefinition.

Даследчы код для RESEARCH.md, не belloc. Што вядома пра фарматы:

- chunkN.rpkg — RPKG v2 ("2KPR"), як у Hitman 3, але запіс рэсурснай табліцы
  на 4 байты карацейшы: type(4, задам наперад), refs_size, size, mem, vmem.
  Даныя: XOR KEY_XOR, калі ўзведзены біт 31 памеру; LZ4 block, калі size != 0.
- LOCR: байт версіі (0/1), 16 зрушэнняў моў (LANGS), у кожнай — u32 колькасць,
  [u32 хэш, u32 даўжыня, XTEA(LOC_KEY) з нулявой падбіўкай, 0].
- DLGE: субтытры — [u32 даўжыня][XTEA(LOC_KEY)], па 16 моў на радок запар;
  тэкст пачынаецца загалоўкам //[..]\\//{прамоўца}\\//##колер#\\…\\ — бачны
  тэкст пасля апошняга "\\". Зрушэнняў у фармаце няма (ідзе паслядоўна).
- packagedefinition.txt / thumbs.dat: 16 байт загалоўка + CRC32 (LE) ад
  расшыфраванага тэксту без нулёў + XTEA(PKG_KEY).
Ключы XTEA знойдзеныя перабором 16-байтавых вокнаў .rdata 007FirstLight.exe.
"""
import struct
import lz4.block

LANGS = ['xx', 'en', 'fr', 'it', 'de', 'es', 'ru', 'mx', 'br', 'pl', 'cn', 'jp', 'tc', 'kr', 'tr', 'uk']
KEY_XOR = bytes([0xDC, 0x45, 0xA6, 0x9C, 0xD3, 0x72, 0x4C, 0xAB])
LOC_KEY = (0x68AC3361, 0x562B4AA0, 0xB9F2771F, 0x28EB3CE7)   # .rdata, файл. зрушэнне 0x2B9DA60
PKG_KEY = (0x71482CF0, 0x5FDC4B9F, 0x86CE569D, 0x0509FC1E)   # .rdata, файл. зрушэнне 0x2B75DF0
DELTA = 0x9E3779B9


def xtea_dec(data, key, rounds=32):
    out = bytearray()
    for i in range(0, len(data) - len(data) % 8, 8):
        v0, v1 = struct.unpack_from('<II', data, i)
        s = (DELTA * rounds) & 0xFFFFFFFF
        for _ in range(rounds):
            v1 = (v1 - ((((v0 << 4) ^ (v0 >> 5)) + v0) ^ (s + key[(s >> 11) & 3]))) & 0xFFFFFFFF
            s = (s - DELTA) & 0xFFFFFFFF
            v0 = (v0 - ((((v1 << 4) ^ (v1 >> 5)) + v1) ^ (s + key[s & 3]))) & 0xFFFFFFFF
        out += struct.pack('<II', v0, v1)
    return bytes(out)


def xtea_enc(data, key, rounds=32):
    out = bytearray()
    for i in range(0, len(data), 8):
        v0, v1 = struct.unpack_from('<II', data, i)
        s = 0
        for _ in range(rounds):
            v0 = (v0 + ((((v1 << 4) ^ (v1 >> 5)) + v1) ^ (s + key[s & 3]))) & 0xFFFFFFFF
            s = (s + DELTA) & 0xFFFFFFFF
            v1 = (v1 + ((((v0 << 4) ^ (v0 >> 5)) + v0) ^ (s + key[(s >> 11) & 3]))) & 0xFFFFFFFF
        out += struct.pack('<II', v0, v1)
    return bytes(out)


def read_index(path):
    with open(path, 'rb') as f:
        hdr = f.read(13)
        assert hdr[:4] == b'2KPR', hdr
        n, hsize, rsize = struct.unpack('<III', f.read(12))
        if 'patch' in str(path):     # спіс выдаленых хэшаў
            f.seek(struct.unpack('<I', f.read(4))[0] * 8, 1)
        ht, rt = f.read(hsize), f.read(rsize)
    ents, pos = [], 0
    for i in range(n):
        h, off, sz = struct.unpack_from('<QQI', ht, i * 20)
        typ = rt[pos:pos + 4][::-1].decode('latin1')
        refsz, size, mem, vmem = struct.unpack_from('<IIII', rt, pos + 4)
        ents.append(dict(hash=h, off=off, csize=sz & 0x3FFFFFFF, xor=bool(sz & 0x80000000),
                         typ=typ, size=size, mem=mem, vmem=vmem, refs=rt[pos + 20:pos + 20 + refsz]))
        pos += 20 + refsz
    return ents


def read_res(path, e):
    with open(path, 'rb') as f:
        f.seek(e['off'])
        d = f.read(e['csize'] or e['size'])
    if e['xor']:
        d = bytes(b ^ KEY_XOR[i & 7] for i, b in enumerate(d))
    if e['csize']:
        d = lz4.block.decompress(d, uncompressed_size=e['size'])
    return d


def parse_locr(d):
    """-> [{хэш: тэкст} або None, калі мовы ў рэсурсе няма] па LANGS."""
    assert d[0] in (0, 1)
    nl = (struct.unpack_from('<I', d, 1)[0] - 1) // 4
    langs = []
    for o in struct.unpack_from(f'<{nl}I', d, 1):
        if o == 0xFFFFFFFF:
            langs.append(None)
            continue
        res = {}
        langs.append(res)
        n = struct.unpack_from('<I', d, o)[0]
        p = o + 4
        for _ in range(n):
            h, l = struct.unpack_from('<II', d, p)
            res[h] = xtea_dec(d[p + 8:p + 8 + l], LOC_KEY).rstrip(b'\0').decode('utf-8', 'replace')
            p += 8 + l + 1
    return langs


def build_locr(langs, version=0):
    """Адваротнае parse_locr: тэкст + нулі да кратнага 8, XTEA, нулявы байт пасля."""
    blocks, offs = [], []
    pos = 1 + 4 * len(langs)
    for res in langs:
        if res is None:
            offs.append(0xFFFFFFFF)
            continue
        b = bytearray(struct.pack('<I', len(res)))
        for h, s in res.items():
            raw = s.encode('utf-8')
            raw += b'\0' * (-len(raw) % 8 or (8 if not raw else 0))
            b += struct.pack('<II', h, len(raw)) + xtea_enc(raw, LOC_KEY) + b'\0'
        offs.append(pos)
        pos += len(b)
        blocks.append(bytes(b))
    return bytes([version]) + struct.pack(f'<{len(offs)}I', *offs) + b''.join(blocks)


def write_patch_rpkg(path, chunk, patch, resources):
    """resources: [(запіс індэкса арыгінала, новыя даныя)] -> RPKG v2 з патч-загалоўкам
    (пусты спіс выдаленых хэшаў), даныя LZ4 + XOR, мета і спасылкі — як у арыгінала."""
    datas = []
    for e, d in resources:
        c = lz4.block.compress(d, store_size=False)
        datas.append((e, len(d), bytes(b ^ KEY_XOR[i & 7] for i, b in enumerate(c))))
    ht_size = 20 * len(datas)
    rt = b''.join(e['typ'][::-1].encode('latin1') + struct.pack('<IIII', len(e['refs']), size, e['mem'], e['vmem'])
                  + e['refs'] for e, size, _ in datas)
    hdr = b'2KPR' + struct.pack('<I', 1) + bytes([chunk, 0, patch]) + b'xx'
    hdr += struct.pack('<III', len(datas), ht_size, len(rt)) + struct.pack('<I', 0)
    off = len(hdr) + ht_size + len(rt)
    ht = b''
    for e, _, c in datas:
        ht += struct.pack('<QQI', e['hash'], off, len(c) | 0x80000000)
        off += len(c)
    with open(path, 'wb') as f:
        f.write(hdr + ht + rt + b''.join(c for _, _, c in datas))


def dlge_texts(d):
    """Эўрыстыка: усе зашыфраваныя субтытры DLGE па парадку (па 16 моў на радок)."""
    out, p, n = [], 0, len(d)
    while p + 12 <= n:
        l = struct.unpack_from('<I', d, p)[0]
        if 8 <= l <= 16384 and l % 8 == 0 and p + 4 + l <= n and xtea_dec(d[p + 4:p + 12], LOC_KEY)[:2] == b'//':
            out.append(xtea_dec(d[p + 4:p + 4 + l], LOC_KEY).rstrip(b'\0').decode('utf-8', 'replace'))
            p += 4 + l
        else:
            p += 1
    return out


def visible(t):
    return t.rsplit('\\', 1)[-1] if t.startswith('//') else t


def read_packagedefinition(path):
    import zlib
    b = open(path, 'rb').read()
    t = xtea_dec(b[20:], PKG_KEY).rstrip(b'\0')
    assert zlib.crc32(t) == struct.unpack_from('<I', b, 16)[0], 'CRC'
    return t.decode('utf-8')


def write_packagedefinition(path, text, header):
    import zlib
    t = text.encode('utf-8')
    with open(path, 'wb') as f:
        f.write(header[:16] + struct.pack('<I', zlib.crc32(t)) + xtea_enc(t + b'\0' * (-len(t) % 8), PKG_KEY))
