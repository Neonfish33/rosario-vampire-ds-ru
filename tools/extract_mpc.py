import struct, os, ctypes
from ctypes import wintypes as w
from ndspy.rom import NintendoDSRom
from ndspy import codeCompression as cc

ROM = r'rosario_eng.nds'
OUT = r'work/orig_mpc'
os.makedirs(OUT, exist_ok=True)

rom = NintendoDSRom.fromFile(ROM)
bb = rom.getFileByName('bb/adv_msg.bb')
cnt = struct.unpack_from('<I', bb, 4)[0]
paths = []
for k in range(cnt):
    off, size = struct.unpack_from('<II', bb, 8 + 8 * k)
    e = bytes(bb[off:off + size])
    if e[:1] == b'\x10':
        e = cc.decompress(e)
    p = os.path.join(OUT, '%03d.mpc' % k)
    open(p, 'wb').write(e)
    paths.append(p)
print('\n'.join(paths))
