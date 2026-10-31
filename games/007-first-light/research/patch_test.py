"""Тэст дастаўкі: ці прымае 007 First Light патч-архіў chunk0patch1.rpkg.

Мяняе ў слотах en і ru радкі меню паўзы (па англійскім тэксце, ва ўсіх LOCR chunk0),
піша Runtime/chunk0patch1.rpkg і ставіць patchlevel=1 партыцыі super у
packagedefinition.txt (арыгінал — packagedefinition.txt.orig).

    python -X utf8 games/007-first-light/research/patch_test.py "D:/…/Runtime"
    … patch_test.py "D:/…/Runtime" --restore     # вярнуць як было
"""
import hashlib
import re
import shutil
import sys
from pathlib import Path

from glacier import (LANGS, build_locr, parse_locr, read_index, read_packagedefinition, read_res,
                     write_packagedefinition, write_patch_rpkg)

# англійскі тэкст -> беларускі; 2026-10-26 у меню паўзы: Resume game, Retry, Restart checkpoint…
CHANGES = {
    'Resume game': 'Працягнуць гульню',
    'Retry': 'Паспрабаваць зноў',
    'Restart checkpoint': 'Вярнуцца да кантрольнага пункта',
    'b3033b4b1f604758':   # падказка ў меню паўзы (sha256[:16] англійскага)
        'Пры вяртанні да кантрольнага пункта частка прагрэсу можа згубіцца.',
    'Photo mode': 'Фотарэжым',
    'Exit to menu': 'Выйсці ў меню',
    'Pause menu': 'Паўза',
    'Options': 'Налады',
    'Tutorials': 'Навучанне',
    'Select': 'Выбраць',
    'Exit': 'Выйсці',
    'Restart mission': 'Пачаць місію нанова',
    'Restart': 'Нанова',
}
SLOTS = ('en', 'ru')

rt = Path(sys.argv[1])
chunk, patch = rt / 'chunk0.rpkg', rt / 'chunk0patch1.rpkg'
pd, pd_orig = rt / 'packagedefinition.txt', rt / 'packagedefinition.txt.orig'

if '--restore' in sys.argv:
    if pd_orig.exists():
        shutil.copy2(pd_orig, pd)
        pd_orig.unlink()
    patch.unlink(missing_ok=True)
    print('вернута')
    sys.exit()

if not pd_orig.exists():
    shutil.copy2(pd, pd_orig)

res = []
for e in read_index(chunk):
    if e['typ'] != 'LOCR':
        continue
    d = read_res(chunk, e)
    langs = parse_locr(d)
    en = langs[LANGS.index('en')]
    n = 0
    for k, s in (en or {}).items():
        new = CHANGES.get(s) or CHANGES.get(hashlib.sha256(s.encode()).hexdigest()[:16])
        if new:
            for slot in SLOTS:
                langs[LANGS.index(slot)][k] = new
            n += 1
    if n:
        print(f'{e["hash"]:#018x}: {n} радк.')
        res.append((e, build_locr(langs, d[0])))
write_patch_rpkg(patch, 0, 1, res)

text = read_packagedefinition(pd_orig)
text, k = re.subn(r'(@partition name=super\b[^\r\n]*patchlevel=)\d+', r'\g<1>1', text)
assert k == 1
write_packagedefinition(pd, text, pd_orig.read_bytes())

# праверка: чытаем запісанае назад
for e in read_index(patch):
    langs = parse_locr(read_res(patch, e))
    print(f'  {e["hash"]:#018x} у патчы:', [s for s in langs[LANGS.index('en')].values()
                                              if s in CHANGES.values()])
print([l for l in read_packagedefinition(pd).splitlines() if l.startswith('@')])
print(f'{patch} — {patch.stat().st_size} байт')
