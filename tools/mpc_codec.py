# -*- coding: utf-8 -*-
"""MPC codec: 3<->4 byte packing + container parse/build.

Layout (verified on originals 000-008):
  0x00 magic 'MPC\0' + 6 bytes (ca0c0b00 0000)
  0x0A u16 string count, 0x0C same, 0x0E u16 total line count
  0x10 u32 = 0x20 (ptr table offset)
  0x14 u32 LC offset   (line counts: u16 nlines, u16 str_idx, 4 bytes per string)
  0x18 u32 LL offset   (line lengths: u32 code-count per line, 4 bytes per line)
  0x1C u32 data offset (packed stream)
  ptr table @0x20: per string (u16 kind=1, u16 str_idx, u32 start_code)
  data: 4 decoded bytes <-> 3 packed bytes (ParseThreeBytes)
"""
import struct

def dec4(p0, p1, p2):
    return bytes((p0, p1 & 0x0F, ((p1 >> 4) & 0x0F) | ((p2 & 0x0F) << 4), p2 >> 4))

def enc4(d0, d1, d2, d3):
    return bytes((d0, ((d2 & 0x0F) << 4) | (d1 & 0x0F), ((d3 & 0x0F) << 4) | (d2 >> 4)))

def decode_stream(packed):
    out = bytearray()
    n = len(packed) // 3
    for i in range(n):
        out += dec4(packed[3 * i], packed[3 * i + 1], packed[3 * i + 2])
    return bytes(out)

def encode_stream(decoded):
    assert len(decoded) % 4 == 0, 'decoded stream must be padded to multiple of 4'
    out = bytearray()
    for i in range(0, len(decoded), 4):
        out += enc4(*decoded[i:i + 4])
    return bytes(out)

def parse_mpc(path):
    d = open(path, 'rb').read()
    assert d[:3] == b'MPC', 'not an MPC file: %r' % path[:64]
    n_str = struct.unpack_from('<H', d, 0x0A)[0]
    n_lines = struct.unpack_from('<H', d, 0x0E)[0]
    lc_off, ll_off, da_off = struct.unpack_from('<III', d, 0x14)
    ptrs = [struct.unpack_from('<HHI', d, 0x20 + 8 * k) for k in range(n_str)]
    lc = [struct.unpack_from('<HH', d, lc_off + 4 * k) for k in range(n_str)]
    # LL: variable size - 1-line string: u32 len1; 2-line: u32 len1, u32 (start2<<16|len2)
    ll = []          # flat list of (len) per line
    ll_entries = []  # per string: (len1, len2 or None)
    off = ll_off
    for k in range(n_str):
        len1 = struct.unpack_from('<I', d, off)[0]; off += 4
        if lc[k][0] == 2:
            x = struct.unpack_from('<I', d, off)[0]; off += 4
            ll.append(len1); ll.append(x & 0xFFFF)
            ll_entries.append((len1, x & 0xFFFF))
        else:
            ll.append(len1)
            ll_entries.append((len1, None))
    assert off == da_off, 'LL end %X != data offset %X' % (off, da_off)
    packed = d[da_off:]
    return dict(raw=d, n_str=n_str, n_lines=n_lines, lc_off=lc_off, ll_off=ll_off,
                da_off=da_off, ptrs=ptrs, lc=lc, ll=ll, ll_entries=ll_entries,
                packed=packed, decoded=decode_stream(packed))

def codes_of(m):
    dec = m['decoded']
    return [struct.unpack_from('<H', dec, 2 * k)[0] for k in range(len(dec) // 2)]

TERMS = (0x0CCD, 0x0D3D)  # [EL], [EL2]
SPLITS = (0x0CCB, 0x0D3B)  # [NL], [NL2]

def validate(m, name='', allow_tail=False):
    ok = True
    codes = codes_of(m)
    total = len(codes)
    cum = 0
    for si in range(m['n_str']):
        lines, lidx = m['lc'][si]
        start = m['ptrs'][si][2]
        len1, len2 = m['ll_entries'][si]
        llen = len1 + (len2 or 0)
        if m['ptrs'][si][0] != 1:
            print('%s ptr[%d] kind=%d' % (name, si, m['ptrs'][si][0])); ok = False
        if m['ptrs'][si][1] != si:
            print('%s ptr[%d] idx=%d' % (name, si, m['ptrs'][si][1])); ok = False
        if start != cum:
            print('%s ptr[%d].start=%d expected %d' % (name, si, start, cum)); ok = False
        cl = sum(m['lc'][k][0] for k in range(si))
        if lidx != cl:
            print('%s lc[%d].lineidx=%d expected %d' % (name, si, lidx, cl)); ok = False
        window = codes[start:start + llen + 2]
        if not window or window[llen - 1] not in TERMS:
            print('%s s%d: код %d не терминатор (окно %s)'
                  % (name, si, llen - 1, ' '.join('%04X' % c for c in window[:llen + 2]))); ok = False
        if lines == 2 and (len(window) < len1 or window[len1 - 1] not in SPLITS):
            print('%s s%d: граница строки 1 не на %d' % (name, si, len1)); ok = False
        if lines == 1 and len2 is not None:
            print('%s s%d: len2 у 1-строчной' % (name, si)); ok = False
        cum += llen
    if cum > total or (cum != total and not allow_tail):
        print('%s stream codes %d != LL sum %d' % (name, total, cum)); ok = False
    elif cum < total:
        print('%s note: %d trailing pad code(s) after content' % (name, total - cum))
    return ok

if __name__ == '__main__':
    import os
    ddir = r'work/orig_mpc'
    allok = True
    for k in range(9):
        p = os.path.join(ddir, '%03d.mpc' % k)
        m = parse_mpc(p)
        codes = codes_of(m)
        need = (2 * len(codes) + 2) // 3 * 3
        my = encode_stream(m['decoded'][:4 * (len(m['decoded']) // 4)])
        match = my == m['packed'][:len(my)]
        tail = m['packed'][len(my):]
        v = validate(m, '%03d' % k)
        el2 = sum(1 for c in codes if c == 0x0D3D)
        nl2 = sum(1 for c in codes if c == 0x0D3B)
        nl = sum(1 for c in codes if c == 0x0CCB)
        allok &= v
        print('%03d: strs=%d lines=%d codes=%d packed=%d(need %d) pad=%s reenc=%s valid=%s EL2=%d NL2=%d NL=%d'
              % (k, m['n_str'], m['n_lines'], len(codes), len(m['packed']), need,
                 tail.hex(), match, v, el2, nl2, nl))
    print('ALL OK' if allok else 'ISSUES FOUND')
