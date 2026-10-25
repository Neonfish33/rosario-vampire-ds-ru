# -*- coding: utf-8 -*-
"""font_all_ru7.fnt: кириллица рисуется IN-PLACE (офсеты оригинала не меняются!).

Проверено в игре: замена блобов на месте + правка len/width рендерится корректно,
любое изменение офсетов - ломает рендер (фрагменты). Поэтому глиф рисуем
адаптивным кеглем (11..5), пока LZ10 не влезет в слот (= до офсета следующего).
"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont
from lz10 import lz10_compress

OUT = r'.\font\font_all_ru7.fnt'
PREVIEW = r'.\font\ru7_glyphs_quad.png'
TSV = r'.\font\cyr_slots.tsv'
ROM = r'rosario_eng.nds'

SS, THRESH, X_OFF, BASELINE = 4, 128, 1, 12
CANVAS_W = 16  # x-сжатие 0.8

from ndspy.rom import NintendoDSRom
rom = NintendoDSRom.fromFile(ROM)
f = bytearray(bytes(rom.getFileByName('fnt/font_all.fnt')))
NGlyph = struct.unpack_from('<H', f, 6)[0]
entries = [struct.unpack_from('<HHI', f, 0xD80 + 8 * k) for k in range(NGlyph)]
# слот k = off[k+1] - off[k] (по отсортированным офсетам); для последнего - до конца данных
offs_sorted = sorted(e[2] for e in entries)
slot_of = {}
for k in range(NGlyph):
    off = entries[k][2]
    nxt = min([o for o in offs_sorted if o > off] or [len(f)])
    slot_of[k] = nxt - off

mapping = []
for ln in open(TSV, encoding='utf-8').read().splitlines()[1:]:
    if ln.strip():
        ch, idx, code = ln.split('\t')
        mapping.append((ch, int(idx)))

fonts = {s: ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf', s * SS) for s in (12, 11, 10, 9, 8, 7, 6, 5)}


def neighbors(body, x, y):
    return sum(1 for dx in (-1, 0, 1) for dy in (-1, 0, 1)
               if (dx or dy) and (x + dx, y + dy) in body)


def render(ch, size):
    font = fonts[size]
    big = Image.new('L', (CANVAS_W * SS, 16 * SS), 0)
    ImageDraw.Draw(big).text((X_OFF * SS, BASELINE * SS + SS - 1), ch, font=font, fill=255, anchor='ls')
    small = big.resize((16, 16), Image.LANCZOS)
    body = None
    for th in (THRESH, 100, 80, 60):
        body = {(x, y) for y in range(16) for x in range(16) if small.getpixel((x, y)) > th}
        if body:
            break
    if not body:
        return None, 0
    for _ in range(2):
        drop = {(x, y) for x, y in body if neighbors(body, x, y) == 0}
        if not drop:
            break
        body -= drop
    if not body:
        return None, 0
    minx = min(x for x, _ in body)
    dx = X_OFF - minx
    body = {(x + dx, y) for x, y in body if 0 <= x + dx < 16}
    grid = [[0] * 16 for _ in range(16)]
    for x, y in body:
        if x + 1 < 16 and y + 1 < 16:
            grid[y + 1][x + 1] = 2
    for x, y in body:
        grid[y][x] = 1
    raw = bytearray()
    for ty in (0, 1):
        for tx in (0, 1):
            for y in range(8):
                for x in range(0, 8, 2):
                    raw.append(grid[ty * 8 + y][tx * 8 + x] | (grid[ty * 8 + y][tx * 8 + x + 1] << 4))
    width = max(x for x, _ in body) + 1
    return bytes(raw), min(15, max(2, width))


ok = skipped = 0
for ch, idx in mapping:
    slot = slot_of[idx]
    done = False
    for size in (12, 11, 10, 9, 8, 7, 6, 5):
        raw, width = render(ch, size)
        if raw is None:
            continue
        comp = lz10_compress(raw)
        if len(comp) <= slot:
            off = entries[idx][2]
            f[off:off + slot] = comp + b'\x00' * (slot - len(comp))
            struct.pack_into('<H', f, 0xD80 + 8 * idx + 2, len(comp))
            f[0x20 + idx] = width
            ok += 1
            done = True
            print('%s: size %d, %d/%d байт' % (ch, size, len(comp), slot))
            break
    if not done:
        skipped += 1
        print('НЕ ВЛЕЗ ни в одном кегле:', ch, 'slot', slot)
print('влезло', ok, '/ не влезло', skipped)
assert skipped == 0
open(OUT, 'wb').write(bytes(f))
print('written', OUT, len(f), 'bytes (size unchanged: %s)' % (len(f) == 351328))


def lz10d(data):
    size = data[1] | data[2] << 8 | data[3] << 16
    o = bytearray(); i = 4
    while len(o) < size:
        flg = data[i]; i += 1
        for bit in range(8):
            if len(o) >= size: break
            if flg & (0x80 >> bit):
                b1, b2 = data[i], data[i+1]; i += 2
                ln = (b1 >> 4) + 3
                disp = ((b1 & 0xF) << 8 | b2) + 1
                for _ in range(ln): o.append(o[-disp])
            else:
                o.append(data[i]); i += 1
    return bytes(o[:size])


bad = 0
for k in range(NGlyph):
    unk, ln, off = struct.unpack_from('<HHI', f, 0xD80 + 8 * k)
    try:
        assert len(lz10d(f[off:off + ln])) == 128
    except Exception:
        bad += 1
        if bad <= 3: print('BAD', k)
print('glyphs OK:', NGlyph - bad, '/ 3387')
assert bad == 0

# превью
def gimg(idx):
    unk, ln, off = struct.unpack_from('<HHI', f, 0xD80 + 8 * idx)
    raw = lz10d(f[off:off + ln])
    img = Image.new('RGB', (16, 16), (255, 255, 255))
    px = img.load()
    for ty in (0, 1):
        for tx in (0, 1):
            for y in range(8):
                for x in range(0, 8, 2):
                    b = raw[(ty * 2 + tx) * 32 + y * 4 + (x >> 1)]
                    for nib, dx in ((b & 15, 0), (b >> 4, 1)):
                        if nib:
                            px[tx * 8 + x + dx, ty * 8 + y] = (0, 0, 0) if nib == 1 else (120, 150, 255)
    return img.resize((80, 80), Image.NEAREST)

CELL = 98
cols = 12
rows = (len(mapping) + cols - 1) // cols
img = Image.new('RGB', (cols * CELL, rows * (CELL + 2)), (230, 230, 230))
dr = ImageDraw.Draw(img)
lf = ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf', 11)
for i, (ch, idx) in enumerate(mapping):
    r, c = divmod(i, cols)
    img.paste(gimg(idx), (c * CELL + 9, r * (CELL + 2) + 9))
    dr.text((c * CELL + 2, r * (CELL + 2) + 2), ch, font=lf, fill=(180, 0, 0))
img.save(PREVIEW)
print('preview saved')
