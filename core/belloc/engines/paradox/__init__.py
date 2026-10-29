"""Лакалізацыя гульняў Paradox (Clausewitz/Jomini: Crusader Kings 3 і інш.).

Як уладкавана ў гульні:
  <корань>/localization/<мова>/**/<імя>_l_<мова>.yml
    UTF-8 з BOM (без BOM гульня падае: «Missing UTF8 BOM»), першы радок
    `l_<мова>:`, далей ` ключ:N "тэкст"` (N — нумар версіі, гульня яго
    ігнаруе; бывае і без N). Значэнне — ад першага да АПОШНЯГА двукосся
    радка: унутраныя " не экрануюцца. Пасля — магчымы каментар `# …`.
  Ключы глабальныя: файл/папка ролі не грае.
  Каранёў некалькі (віртуальная ФС): game/, jomini/, clausewitz/.
  `localization/replace/` — файлы адтуль перазапісваюць ключы, што ўжо ёсць.

Лаўнчар скідае невядомыя мовы, таму мы падмяняем рускую: пішам беларускі
тэкст у `game/localization/replace/russian/bel/…_l_russian.yml`, толькі
перакладзеныя ключы — астатняе застаецца рускім.

Секцыя "paradox" у game.json:
  roots          ["game", "jomini", "clausewitz"] — дзе шукаць localization/
  langs          {"en": "english", "ru": "russian"} — код → папка/суфікс
  extract_langs  ["en", "ru"]
  target         "russian"                         — якую мову падмяняем
  replace_dir    "game/localization/replace/russian/bel" — наша папка (цалкам наша)

Табліцы — шлях англійскага файла без `_l_english.yml` адносна
localization/<мова>/; файлы не з каранёвай `game/` атрымліваюць прэфікс
`@jomini/`, `@clausewitz/`. Падказка (ru) бярэцца па ключы з усіх рускіх
файлаў, не па імені файла.

Напісана і праверана на Crusader Kings III 1.20.1.1.
"""
from .common import NAME, SECTION  # noqa: F401
from .extract import extract  # noqa: F401
from .apply import payload, check_path, apply, restore, installed  # noqa: F401
from .fonts import fonts_report  # noqa: F401
