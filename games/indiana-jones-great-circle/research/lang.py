"""Рэсурс lang/strings: u32 памер, u32 BE колькасць, далей
{u32 хэш, u32 даўж., ключ\0, u32 даўж., тэкст\0}. Адзін рэсурс на мову
(variation у запісе: 0x197 en … 0x1aa ru), апошняя версія — у patchN.
python -I -X utf8 lang.py <папка з *_lang.bin>
"""
import struct, sys, glob, os, json
def parse(b):
    size, = struct.unpack_from('<I', b, 0)
    pos = 8; out = {}
    while pos < len(b):
        h, kl = struct.unpack_from('<II', b, pos); pos += 8
        k = b[pos:pos+kl].decode(); pos += kl + 1
        tl, = struct.unpack_from('<I', b, pos); pos += 4
        t = b[pos:pos+tl].decode('utf-8'); pos += tl + 1
        out[k] = t
    return b[4:8], out
if __name__ == '__main__':
    for fn in sorted(glob.glob(sys.argv[1] + '/*_lang.bin')):
        hdr, d = parse(open(fn, 'rb').read())
        k = '#str_vo_nl_antonio_ch05la03_123_breaker_lo_01'
        print(os.path.basename(fn), hdr.hex(), len(d), repr(d.get(k, '')[:50]))
