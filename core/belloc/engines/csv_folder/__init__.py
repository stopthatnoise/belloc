"""Штатная CSV-лакалізацыя гульні: папка мовы з CSV па ID (Esoteric Ebb 1.3).

Гульня чытае мовы з `<dir>/<папка>/*.csv`: тыя ж файлы і ключы, што ў
`Template/`, апошні слупок — код мовы. Арыгінал — у `Official/*.csv`
(слупкі мовы, напр. `EN`, `CH`). Слупкі паміж ID і першай мовай (`Area`,
`Speaker`, `Type`, `GAME_DATA`) — кантэкст: extract кладзе іх у context.json
(`Speaker=…, Type=LINE`).

Секцыя "csv_folder" у game.json:
  dir       "Esoteric Ebb_Data/StreamingAssets/Localization"
  official  "Official"           — арыгінал
  template  "Template"           — шаблон папкі мовы (апошні слупок — пусты)
  target    "Belarusian"         — наша папка (цалкам наша; restore выдаляе)
  code      "BE"                 — код мовы ў загалоўку CSV
  langs     {"en": "EN"}         — мова CSV → слупок Official
  fixed     {"LanguageDropdown": "Беларуская", …} — радкі канфігурацыі мовы,
            пішуцца як ёсць і ў source/ не трапляюць
  skip      "^Glossary_…$"       — ID, якія пакідаем пустымі (бярэцца запасная
            мова гульні); у source/ таксама не трапляюць

Табліца = імя файла без .csv, ключ = ID (першы слупок).

apply: шаблон гульні + наш bel → папка target. Радок, чый арыгінал у гульні
змяніўся пасля перакладу (src_hash у payload не супадае), застаецца пустым —
гульня возьме запасную мову; трэба `extract` і `sync`.
"""
from .common import NAME, SECTION  # noqa: F401
from .extract import extract  # noqa: F401
from .apply import payload, check_path, apply, restore, installed  # noqa: F401

# усталёўшчык (release.py): толькі стандартная бібліятэка
PYINSTALLER = ["--exclude-module", "UnityPy", "--exclude-module", "cv2", "--exclude-module", "spylls",
               "--exclude-module", "fontTools", "--exclude-module", "PIL", "--exclude-module", "numpy"]
