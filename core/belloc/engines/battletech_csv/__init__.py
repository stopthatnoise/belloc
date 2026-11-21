"""CSV-табліца лакалізацыі BATTLETECH (Harebrained Schemes, Unity 2018.4, Mono).

Тэкст гульні — плоская табліца
`<csv_dir>/strings_<культура>.csv` з дзвюма калонкамі `KEY,<культура>`.
Беларуская займае месца рускай (`locale: ru-RU`); маніфест, бандлы і код не
чапаюцца. Ключ — англійскі радок пасля `_NormalizeString` (norm.py), таму ў
рэпазіторыі ключ — хэш `sha256(normalize(key))[:16]`.

Секцыя "battletech_csv" у game.json:
  data_dir      "BattleTech_Data"          — дзе .assets і Managed
  csv_dir       "BattleTech_Data/StreamingAssets/data/localization"
  locale        "ru-RU"                    — файл, які перапісвае apply
  target        "ru"                       — мова гэтага файла
  other_langs   ["de", "fr"]               — што яшчэ выцягваць (de-DE, fr-FR)
  subtitles     "…/StreamingAssets/Video/Subtitles" — англійскія .srt
  scan          {"json", "srt", "dll", "assets", "levels": bool} — што сканаваць
                                               (па змаўчанні ўсё; выключаецца
                                               праз local.json, каб паўтарыць
                                               хутка)

Крыніца па радку — гібрыд (game.json: `source_lang: en`, `fallback_lang: de`,
`hint_lang: ru`): англійская, дзе яна знойдзеная ў гульні (JSON, субтытры, DLL,
сцэны; 74 %), інакш нямецкая. Руская — толькі для спрэчных выпадкаў: у працоўным
файле пачкі перакладчык ставіць `src_lang: ru`, `batch apply` піша ў note
`крыніца: ru` і лічыць `src_hash` ад рускага тэксту. Такія радкі відныя ў
рэпазіторыі асобным спісам, а не раствараюцца ў агульнай масе.

Вынік extract (local/<гульня>/source/):
  <мова>.json    {"strings": {хэш: тэкст}} — ru/de/fr, коскі ўжо як у гульні
  en.json        {"strings": {хэш: англійскі радок}} — дзе знойдзены
  context.json   {"strings": {хэш: "at=…; use=…; q=…; len=… — заўвага"}} — кантэкст
                 радка для працоўных файлаў і пачак: шлях крыніцы (at=), мова
                 (use=), якасць (q=), даўжыня крыніцы ў знаках (len=)
  provenance.json  адкуль узяты англійскі радок (json#/шлях, dll#us@зрух…)
  rows.json      {хэш: нумар радка ў табліцы}
  keys.json, missing.json  — для працы, лакальна (у іх тэкст ключоў)
  meta.json      версія гульні, buildid Steam, колькасці, час
  report.md      тыя ж колькасці тэкстам

apply піша толькі наш `bel` ў калонку `locale`: коскі — `U+001F`, сапраўдныя
пераносы — `\\n`, парадак і колькасць радкоў захоўваюцца. Радок, чый арыгінал у
гульні змяніўся пасля перакладу (src_hash у payload не супадае ні з адной моўнай
табліцай), застаецца як у гульні — патрэбны `extract` і `sync`.

Шрыфты (TMP 1.x, `І і Ў ў` у дзевяці кірылічных шрыфтах) — наступны крок
рухавіка; у гэтай версіі іх няма.
"""
from .common import NAME, SECTION  # noqa: F401
from .extract import extract  # noqa: F401
from .apply import payload, check_path, apply, restore, installed  # noqa: F401

# усталёўшчык (release.py): рухавік на стандартнай бібліятэцы
PYINSTALLER = ["--exclude-module", "UnityPy", "--exclude-module", "cv2",
               "--exclude-module", "spylls", "--exclude-module", "fontTools",
               "--exclude-module", "PIL", "--exclude-module", "numpy"]
