# -*- coding: utf-8 -*-
"""Сборка русских MPC из перевод\\*.txt.

Конвейер: txt -> коды (tbl) -> поток (X,00) -> паддинг -> 3<->4 упаковка -> MPC.
Таблицы ptr/LC/LL пересобираются из текста (rel = накопительное смещение в кодах).
"""
import glob, os, re, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mpc_codec import parse_mpc, codes_of, encode_stream, validate

BASE = r'.'
SRC = os.path.join(BASE, 'translation')
ORIG = r'work/orig_mpc'
OUT = os.path.join(BASE, 'extracted', 'mpc')

EL, EL2 = 0x0CCD, 0x0D3D
NL, NL2 = 0x0CCB, 0x0D3B

# --- переразбивка строк под бюджет ширины ---
BUDGET = 228  # макс ширина строки в оригинале: 227px
NO_WIDTH_TAGS = {'[EL]', '[EL2]', '[NL]', '[NL2]', '[YLOW]', '[WHITE]', '[TRIG]', '[CNTR]',
                 '[WHITE2]', '[YLOW2]', '[CNTR2]', '[TRIG2]'}

_font_widths = None
def font_widths():
    global _font_widths
    if _font_widths is None:
        f = open(os.path.join(BASE, 'font', 'font_all_ru5.fnt'), 'rb').read()
        _font_widths = [f[0x20 + k] for k in range(3387)]
    return _font_widths


def code_width(code):
    if code in (0x0CCD, 0x0D3D, 0x0CCB, 0x0D3B, 0x0CCF, 0x0CCE, 0x0CD2, 0x0CD1,
                0x0D3E, 0x0D3F, 0x0D41, 0x0D42):
        return 0
    if code < 3387:
        return font_widths()[code]
    return 8


def chunk_width(chunk):
    w = 0
    pos = 0
    for mt in TAG_RE.finditer(chunk):
        for ch in chunk[pos:mt.start()]:
            w += code_width(struct.unpack('<H', TBL[ch])[0])
        if mt.group() not in NO_WIDTH_TAGS:
            w += code_width(struct.unpack('<H', TBL.get(mt.group(), b'\x00\x00'))[0])
        pos = mt.end()
    for ch in chunk[pos:]:
        w += code_width(struct.unpack('<H', TBL[ch])[0])
    return w


def split_units(line):
    # '[NL2]'-маркеров внутри строки уже нет (строка - кусок после разбиения)
    # unit = [текст, glue] - glue=True: продолжение разрезанного слова, пробел не нужен
    return [[c, False] for c in line.split(' ') if c]


def lw(units, a, b):
    w = 0
    first = True
    for t, glue in units[a:b]:
        if not first and not glue:
            w += 5
        w += chunk_width(t)
        first = False
    return w


def join_units(units):
    out = []
    for t, glue in units:
        if out and not glue:
            out.append(' ')
        out.append(t)
    return ''.join(out)


VOWELS = set('аеёиоуыэюяАЕЁИОУЫЭЮЯ')
HYPH = '-'


def hyph_bounds(word):
    """Возможные границы переноса (индекс, перед которым режем) по гласным."""
    out = []
    for i, ch in enumerate(word):
        if ch in VOWELS and i >= 3 and len(word) - i >= 2 and word[i - 1] not in 'йьъЙЬЪ':
            out.append(i)
    return out


def rewrap(text, term, split_tag, report, where):
    """Гарантирует, что обе строки <= BUDGET: оптимальная точка [NL2]; при
    невозможности - перенос длинного слова по слоговому boundary."""
    m = None
    for mt in TAG_RE.finditer(text):
        if mt.group() == term:
            m = mt
    body, tail = text[:m.start()], m.group()
    parts = body.split(split_tag)
    one_line = len(parts) == 1
    if one_line:
        units = split_units(parts[0].strip())
        if lw(units, 0, len(units)) <= BUDGET:
            return text
    else:
        n1 = len(split_units(parts[0].strip()))
        units = split_units(parts[0].strip()) + split_units(parts[1].strip())
        if lw(units, 0, n1) <= BUDGET and lw(units, n1, len(units)) <= BUDGET:
            return text
    for attempt in range(8):
        best = None
        for i in range(1, len(units)):
            score = max(lw(units, 0, i), lw(units, i, len(units)))
            if best is None or score < best[0]:
                best = (score, i)
        if best is None or best[0] <= BUDGET:
            break
        # режем самое длинное разложимое слово в длинной строке
        i = best[1]
        left_long = lw(units, 0, i) >= lw(units, i, len(units))
        seg = range(0, i) if left_long else range(i, len(units))
        cand_local = -1
        cand_len = 0
        for j in seg:
            u = units[j][0]
            if '[' in u:
                continue
            if hyph_bounds(u) and len(u) > cand_len:
                cand_local, cand_len = j, len(u)
        if cand_local < 0:
            break
        word = units[cand_local][0]
        b = min(hyph_bounds(word), key=lambda x: abs(x - len(word) / 2))
        if chunk_width(word[:b] + HYPH) < 4 or chunk_width(word[b:]) < 4:
            break
        units[cand_local:cand_local + 1] = [[word[:b] + HYPH, False], [word[b:], True]]
    best = None
    for i in range(1, len(units)):
        score = max(lw(units, 0, i), lw(units, i, len(units)))
        if best is None or score < best[0]:
            best = (score, i)
    if best is None or best[0] > BUDGET:
        report.append((where, 'не влезает даже с переносом', best[0] if best else 0))
    if best is None:
        return text
    i = best[1]
    return join_units(units[:i]) + split_tag + join_units(units[i:]) + tail

TRANSLIT = {
    'A': 'А', 'B': 'Б', 'C': 'С', 'D': 'Д', 'E': 'Е', 'F': 'Ф', 'G': 'Г', 'H': 'Х',
    'I': 'И', 'J': 'Дж', 'K': 'К', 'L': 'Л', 'M': 'М', 'N': 'Н', 'O': 'О', 'P': 'П',
    'Q': 'К', 'R': 'Р', 'S': 'С', 'T': 'Т', 'U': 'У', 'V': 'В', 'W': 'У', 'X': 'Кс',
    'Y': 'Й', 'Z': 'З',
    'a': 'а', 'b': 'б', 'c': 'с', 'd': 'д', 'e': 'е', 'f': 'ф', 'g': 'г', 'h': 'х',
    'i': 'и', 'j': 'й', 'k': 'к', 'l': 'л', 'm': 'м', 'n': 'н', 'o': 'о', 'p': 'п',
    'q': 'к', 'r': 'р', 's': 'с', 't': 'т', 'u': 'у', 'v': 'в', 'w': 'в', 'x': 'кс',
    'y': 'и', 'z': 'з',
}
REPL = [('«', '"'), ('»', '"'), ('–', '-'), ('—', '-'), ('’', "'"),
        ('№', 'номер '), ('～', '...'), ('~', '...'), ('…', '...'), ('♪', ''),
        ('「', '"'), ('」', '"'), ('・', '-'), ('\u3000', ' ')]


def load_tbl():
    p = r'tools/rosario.tbl'
    m = {' ': b'\x00\x00'}
    for ln in open(p, 'rb').read().decode('cp1251').splitlines():
        if '=' not in ln or not ln.strip():
            continue
        k, v = ln.split('=', 1)
        k = k.strip().upper()
        if not re.fullmatch(r'[0-9A-F]{4}', k) or v == '':
            continue
        m[v] = bytes.fromhex(k)
    return m

TBL = load_tbl()
TAG_RE = re.compile(r'\[[A-Za-z0-9]+\]')
FWD = {}
for ch, b in TBL.items():
    FWD.setdefault(b, ch)


def prepare_line(line):
    parts = re.split(r'(\[[A-Za-z0-9]+\])', line)
    for i, p in enumerate(parts):
        if not p.startswith('['):
            parts[i] = re.sub(r'[A-Za-z]+', lambda m: ''.join(TRANSLIT.get(c, c) for c in m.group()), p)
    line = ''.join(parts)
    for a, b in REPL:
        line = line.replace(a, b)
    line = re.sub(r'#(?=\d)', 'номер ', line)
    line = line.replace('#', '[CNTR]')
    return line


def encode_line(line, where):
    out = bytearray()
    missing = []

    def add(ch):
        if ch in TBL:
            out.extend(TBL[ch])
        else:
            missing.append(ch)

    pos = 0
    for mt in TAG_RE.finditer(line):
        for ch in line[pos:mt.start()]:
            add(ch)
        add(mt.group())
        pos = mt.end()
    for ch in line[pos:]:
        add(ch)
    if missing:
        raise SystemExit('%s: нет в tbl: %r' % (where, sorted(set(missing))))
    return bytes(out)


def to_text(codes):
    out = []
    for c in codes:
        b = struct.pack('<H', c)
        out.append(FWD.get(b, '<?%04X?>' % c))
    return ''.join(out)


def build_file(k):
    orig = parse_mpc(os.path.join(ORIG, '%03d.mpc' % k))
    lines = open(os.path.join(SRC, '%03d.txt' % k), encoding='utf-8-sig').read().splitlines()
    texts = [prepare_line(l) for l in lines if not l.startswith('//') and l.strip()]
    import ru_shorten
    texts = [ru_shorten.apply(t) for t in texts]
    if len(texts) != orig['n_str']:
        raise SystemExit('%03d: строк %d, оригинал %d' % (k, len(texts), orig['n_str']))

    # диалект по частоте терминаторов
    el1 = sum(t.count('[EL]') for t in texts)
    el2 = sum(t.count('[EL2]') for t in texts)
    term_name, TERM = ('[EL]', EL) if el1 > el2 else ('[EL2]', EL2)
    split_name, SPLIT = ('[NL]', NL) if el1 > el2 else ('[NL2]', NL2)

    stream = bytearray()
    ptrs, lc, ll_entries = [], [], []
    clean_texts = []
    rewrap_report = []
    cum_codes = cum_lines = 0
    for si, text0 in enumerate(texts):
        # после последнего терминатора допустимы только пробелы - срезаем
        last = None
        for mt in TAG_RE.finditer(text0):
            if mt.group() in ('[EL]', '[EL2]'):
                last = mt
        if last is None:
            raise SystemExit('%03d s%d: нет терминатора: %r' % (k, si, text0[-40:]))
        tail = text0[last.end():]
        if tail.strip():
            raise SystemExit('%03d s%d: текст после терминатора: %r' % (k, si, tail[:40]))
        text = text0[:last.end()]
        term = '[EL]' if el1 > el2 else '[EL2]'
        splt = '[NL]' if el1 > el2 else '[NL2]'
        text = rewrap(text, term, splt, rewrap_report, '%03d s%d' % (k, si))
        clean_texts.append(text)
        data = encode_line(text, '%03d s%d' % (k, si))
        nc = len(data) // 2
        cl = [struct.unpack_from('<H', data, 2 * i)[0] for i in range(nc)]
        if not cl or cl[-1] != TERM:
            raise SystemExit('%03d s%d: не кончается %s: %r' % (k, si, term_name, text[-40:]))
        nsplit = sum(1 for c in cl if c == SPLIT)
        if nsplit > 1:
            raise SystemExit('%03d s%d: %d переносов %s' % (k, si, nsplit, split_name))
        if nsplit:
            len1 = cl.index(SPLIT) + 1
            len2 = nc - len1
            nlines = 2
        else:
            len1, len2, nlines = nc, None, 1
        ptrs.append((1, si, cum_codes))
        lc.append((nlines, cum_lines))
        ll_entries.append((len1, len2))
        stream += data
        cum_codes += nc
        cum_lines += nlines

    # паддинг потока нулями до кратности 4 (игра читает строго по LL/ptr)
    content_codes = len(stream) // 2
    while len(stream) % 4:
        stream += b'\x00'
    packed = encode_stream(bytes(stream))
    if len(packed) % 4:
        packed += b'\x00' * (4 - len(packed) % 4)

    lc_off = 0x20 + 8 * len(texts)
    ll_off = lc_off + 4 * len(texts)
    ll_bytes = sum(4 if l2 is None else 8 for _, l2 in ll_entries)
    da_off = ll_off + ll_bytes

    out = bytearray(orig['raw'][:0x0A])
    out += struct.pack('<HHH', len(texts), len(texts), cum_lines)
    out += struct.pack('<IIII', 0x20, lc_off, ll_off, da_off)
    for kind, idx, start in ptrs:
        out += struct.pack('<HHI', kind, idx, start)
    for (nlines, lidx), (len1, len2) in zip(lc, ll_entries):
        out += struct.pack('<HH', nlines, lidx)
    for len1, len2 in ll_entries:
        out += struct.pack('<I', len1)
        if len2 is not None:
            out += struct.pack('<I', (len1 << 16) | len2)
    assert len(out) == da_off, (len(out), da_off)
    out += packed

    dst = os.path.join(OUT, '%03d_ru.mpc' % k)
    open(dst, 'wb').write(bytes(out))

    # контроль: свой файл читается своим же кодеком, текст совпадает
    m2 = parse_mpc(dst)
    ok = validate(m2, '%03d_ru' % k, allow_tail=True)
    codes = codes_of(m2)
    rt_ok = True
    for si in range(m2['n_str']):
        s = m2['ptrs'][si][2]
        len1, len2 = m2['ll_entries'][si]
        e = s + len1 + (len2 or 0)
        if to_text(codes[s:e]) != clean_texts[si]:
            rt_ok = False
            print('  RT mismatch s%d: %r' % (si, to_text(codes[s:e])[:60]))
    orig2 = sum(1 for x in orig['lc'] if x[0] == 2)
    my2 = sum(1 for x in lc if x[0] == 2)
    if rewrap_report:
        for r in rewrap_report:
            print('   REWRAP', r)
    print('%03d: strs=%d lines=%d(%d orig 2ln, %d my 2ln) codes=%d packed=%d valid=%s rt=%s rewrap_fix=%d -> %s'
          % (k, len(texts), cum_lines, orig2, my2, cum_codes, len(packed), ok, rt_ok,
             len(rewrap_report), os.path.basename(dst)))
    return ok and rt_ok


if __name__ == '__main__':
    allok = True
    for k in range(9):
        allok &= build_file(k)
    print('DONE', 'OK' if allok else 'WITH ERRORS')
