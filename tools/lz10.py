# -*- coding: utf-8 -*-
# ВАЖНО: декодер игры копирует ссылки по 2 байта и не поддерживает disp=1
# (в оригинальных блобах минимальный disp = 2). Поэтому j <= i-2.
def lz10_compress(data: bytes) -> bytes:
    n = len(data)
    out = bytearray([0x10, n & 0xFF, (n >> 8) & 0xFF, (n >> 16) & 0xFF])
    i = 0
    while i < n:
        flag_pos = len(out)
        out.append(0)
        flags = 0
        for bit in range(8):
            if i >= n:
                break
            best_len = 0
            best_disp = 0
            start = max(0, i - 4096)
            for j in range(start, i - 1):
                ln = 0
                while ln < 18 and i + ln < n and data[j + ln] == data[i + ln]:
                    ln += 1
                if ln > best_len:
                    best_len = ln
                    best_disp = i - j
            if best_len >= 3:
                flags |= 0x80 >> bit
                v = ((best_len - 3) << 12) | (best_disp - 1)
                out.append((v >> 8) & 0xFF)
                out.append(v & 0xFF)
                i += best_len
            else:
                out.append(data[i])
                i += 1
        out[flag_pos] = flags
    return bytes(out)
