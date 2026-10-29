"""Лакалізацыя UE праз .locres (engine = "unreal-locres": Expedition 33, Dispatch).

Секцыя "unreal" у game.json (aes_key можна трымаць у local.json):

  pak      "Sandfall/Content/Paks/pakchunk0-Windows.pak"          — пак гульні з locres
  locres   "Sandfall/Content/Localization/Game/{lang}/Game.locres" — шлях унутры пака
  langs    {"en": "en-US", "ru": "ru", "uk": "uk"}                 — мова CSV → культура UE
  target   "ru"                                                    — чыю культуру падмяняем
  mod      "Sandfall/Content/Paks/~mods/Belarusian_P.pak"         — куды класці мод-пак
  aes_key  "0x…"                                                  — калі індэкс пака зашыфраваны (Dispatch)
  font_patches                                                     — кірыліца ў шрыфты без яе, у той жа мод-пак (fonts.py)

Некалькі мэтаў лакалізацыі (Dispatch: Shared, 101…108 — кожная ў сваім паку):

  loc_targets {"Shared": "Dispatch/Content/Paks/pakchunk0-WindowsNoEditor.pak", …}
              — замест pak; у locres і po — {target}
  po       "Dispatch/Content/Localization/{target}/{lang}/{target}.po" — па жаданні:
           з .po мовы source_lang бяруцца Speaker, Loc Note, SourceLocation
           (→ source/context.json, «ctx: …» у note) і SortingString (парадак
           дыялогаў у CSV)

Табліца CSV = прастора імёнаў locres (ST_…), ключ = ключ радка. З мэтамі —
«<мэта>/<прастора>», кропкі прасторы — падпапкі (101/LV_Shift01/Scenario_SC_01_),
пустая прастора — «_» (101/_), знакі, што не могуць быць у імені файла, — «_».

Дастаўка — мод-пак: адзін файл у ~mods з locres культуры target (з мэтамі —
па адным на мэту), у якім перакладзеныя радкі замененыя на bel
(неперакладзенае — мовы target). Файлы гульні не мяняюцца: ні .orig, ні .bel;
restore проста выдаляе мод.
"""
from .common import NAME, SECTION  # noqa: F401
from .extract import extract  # noqa: F401
from .apply import payload, check_path, apply, restore, installed  # noqa: F401
