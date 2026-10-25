# -*- coding: utf-8 -*-
"""Сборка Rosario_RU_v4.nds: новый шрифт (font_all_ru4) + все 9 русских MPC в bb/adv_msg.bb."""
import struct, os
from ndspy.rom import NintendoDSRom

BASE = r'.'
ROM_IN = r'rosario_eng.nds'
ROM_OUT = os.path.join(BASE, 'roms', 'Rosario_RU_v4.nds')

rom = NintendoDSRom.fromFile(ROM_IN)

mpcs = []
for k in range(9):
    p = os.path.join(BASE, 'extracted', 'mpc', '%03d_ru.mpc' % k)
    m = open(p, 'rb').read()
    assert m[:3] == b'MPC', p
    mpcs.append(m)

bb = bytearray(b'BB\x00\x00' + struct.pack('<I', len(mpcs)))
off = 8 + 8 * len(mpcs)
table = b''
body = b''
for m in mpcs:
    table += struct.pack('<II', off, len(m))
    body += m
    off += len(m)
bb += table + body
rom.setFileByName('bb/adv_msg.bb', bytes(bb))

font = open(os.path.join(BASE, 'font', 'font_all_ru7.fnt'), 'rb').read()
rom.setFileByName('fnt/font_all.fnt', font)

os.makedirs(os.path.dirname(ROM_OUT), exist_ok=True)
rom.saveToFile(ROM_OUT)
print('saved', ROM_OUT, os.path.getsize(ROM_OUT), 'bytes; bb =', len(bb), 'font =', len(font))
