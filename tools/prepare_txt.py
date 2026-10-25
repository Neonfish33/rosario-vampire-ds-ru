# -*- coding: utf-8 -*-
# Чистая подготовка txt: копия переводов + все нормализации, одной операцией.
import glob, os, re, shutil

SRC = r'.\translation'
DST = r'.\extracted\mpc'

TRANSLIT = {
    'A':'А','B':'Б','C':'С','D':'Д','E':'Е','F':'Ф','G':'Г','H':'Х','I':'И','J':'Дж',
    'K':'К','L':'Л','M':'М','N':'Н','O':'О','P':'П','Q':'К','R':'Р','S':'С','T':'Т',
    'U':'У','V':'В','W':'У','X':'Кс','Y':'Й','Z':'З',
    'a':'а','b':'б','c':'с','d':'д','e':'е','f':'ф','g':'г','h':'х','i':'и','j':'й',
    'k':'к','l':'л','m':'м','n':'н','o':'о','p':'п','q':'к','r':'р','s':'с','t':'т',
    'u':'у','v':'в','w':'в','x':'кс','y':'и','z':'з',
}
def tr(m):
    return ''.join(TRANSLIT.get(c, c) for c in m.group())

for src in sorted(glob.glob(os.path.join(SRC, '*.txt'))):
    name = os.path.basename(src)
    lines = open(src, encoding='utf-8-sig').read().splitlines()
    out = []
    for line in lines:
        if line.startswith('//'):
            out.append(line)
            continue
        parts = re.split(r'(\[[A-Za-z0-9]+\])', line)
        for i, p in enumerate(parts):
            if not p.startswith('['):
                parts[i] = re.sub(r'[A-Za-z]+', tr, p)
        line = ''.join(parts)
        for a, b in (('«','"'), ('»','"'), ('–','-'), ('—','-'), ('’',"'"),
                     ('№','номер '), ('～','-'), ('♪',''), ('「','"'), ('」','"'),
                     ('・','-'), ('\u3000',' ')):
            line = line.replace(a, b)
        # '#' отдельно: '#'+цифра -> 'номер ', иначе имя игрока [CNTR]
        line = re.sub(r'#(?=\d)', 'номер ', line)
        line = line.replace('#', '[CNTR]')
        out.append(line)
    dst = os.path.join(DST, name)
    with open(dst, 'w', encoding='utf-8') as f:
        f.write('\r\n'.join(out) + '\r\n')
    print(name, 'ok', len(out), 'строк')
