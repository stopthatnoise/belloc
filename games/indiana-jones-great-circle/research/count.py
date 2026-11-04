"""Аб'ём англійскага тэксту па групах (ui, vo_nl — сюжэт, vo_sl — баркі),
без [name:…], [1.78] і разметкі; унікальныя тэксты.
python -I -X utf8 count.py <папка research> (чакае out/patch1_2199_lang.bin)
"""
import sys, re, collections
sys.path.insert(0, sys.argv[1]); import lang
_, en = lang.parse(open(sys.argv[1] + '/out/patch1_2199_lang.bin', 'rb').read())
clean = lambda t: re.sub(r'\[name:[^\]]*\]|\[[\d.]+\]|\[[a-z]+\]|<[^>]*>|%[sd]', ' ', t)
W = lambda t: len(re.findall(r"[A-Za-z][A-Za-z'’-]*", clean(t)))
def grp(k):
    k = k.lstrip('#')
    if k.startswith('str_vo_'): return 'vo_' + k.split('_')[2]
    return 'ui'
G = collections.defaultdict(lambda: [0, 0, set(), 0])
seen = set()
for k, t in en.items():
    g = grp(k); b = G[g]; b[0] += 1; w = W(t); b[1] += w
    c = clean(t).strip()
    if c and c not in seen: seen.add(c); b[3] += w
for g, b in sorted(G.items()): print(g, b[0], b[1], 'unique', b[3])
print('total unique words', sum(b[3] for b in G.values()), 'unique texts', len(seen))
temp = [k for k, t in en.items() if re.search(r'\bTEMP\b|\bPLACEHOLDER\b|^TBD', t)]
print('TEMP', len(temp), sum(W(en[k]) for k in temp))
names = collections.Counter(m for t in en.values() for m in re.findall(r'\[name:([^\]]*)\]', t))
print('speaker names', len(names), names.most_common(15))
print('timing splits', sum(1 for t in en.values() if re.search(r'\[\d+(\.\d+)?\]', t)))
print('chars unique', sum(len(clean(t)) for t in seen))
dlc = {k for k in en if '_dlc' in k}
print('dlc', len(dlc), sum(W(en[k]) for k in dlc))
