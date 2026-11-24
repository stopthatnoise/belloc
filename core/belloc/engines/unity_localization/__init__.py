"""Unity Localization (com.unity.localization) у Addressables-бандлах.

Два рэжымы — які ўключаны, вызначае ключ `monolithic_table` у секцыі "unity".

1. StringTable у асобных бандлах (звычайны):

  localization-assets-shared_…            Shared Data калекцый: m_Id (int64) → m_Key
  localization-string-tables-<мова>_…     StringTable на калекцыю: m_Id → m_Localized
  localization-asset-tables-<мова>_…      AssetTable (шрыфты, тэкстуры) па мовах
  localization-locales_…                  спіс моў

  Ключ табліцы — m_Key з Shared Data (чытэльны і сталы); m_Id для запісу apply
  бярэ з Shared Data гульні гульца. Радкі без перакладу застаюцца на мове локалі.

2. Маналітная табліца (`monolithic_table`, гл. monolithic.py): радкі ўсіх табліц
   ляжаць у адным MonoBehaviour, ключ — радок (`<картка>/<поле>`), а англійская
   крыніца — у даных гульні (english.py). Для яе дадаткова:

    "monolithic_table"  "ruLocalizationTable"  — імя MonoBehaviour з табліцай
    "table_bundle"      "g5ib…_assets_all*.bundle"  — дзе табліца (glob у bundles)
    "tables"            {"dialogue": "…", "entities": "…"}  — правілы «ключ → табліца»
    "rest_table"        "system"               — табліца для ўсяго астатняга;
                                                 калі `tables` няма — усе радкі сюды

3. Секцыя "unity" (агульнае для абодвух):

  data_dir        "Carpenter_Data"            — дзе globalgamemanagers
  bundles         "…/StreamingAssets/aa/StandaloneWindows64"
  extract_langs   ["en", "ru"]                — што выцягваць у source/
  preview_locale  "ru"                        — чыю табліцу перапісвае apply
  font_bundles    ["fonts_….bundle"]          — дзе ў кірылічныя TMP-шрыфты дадаюцца І/і, Ў/ў
  font_assets     ["resources.assets"]        — тое ж у класічных файлах (адносна data_dir):
                                                копіі шрыфтоў з Resources (Silver Pines: вынікі
                                                праходжання, «Новая гульня+»)
  crc_catalog     "…/StreamingAssets/aa/catalog.json" — калі ў каталогу Addressables у
                                                бандлаў ненулявы m_Crc, гульня змененыя
                                                бандлы не грузіць: apply абнуляе m_Crc
                                                (crc.py). catalog.bin — не.
  crc_catalog_bin "…/StreamingAssets/aa/catalog.bin"  — тое ж для бінарнага каталога
                                                (catalog_bin.py); разам з ім — "hash_file"
  hash_file       "…/StreamingAssets/aa/catalog.hash" — md5 каталога: без новага
                                                значэння гульня возьме каталог са свайго
                                                кэша, дзе m_Crc яшчэ нянулявыя

Калі гульня мае `from_original` у game.json, apply падстаўляе кавалкі арыгінала
замест `[]` з файлаў гульні (у рэжыме маналітнай табліцы — з англійскіх даных).

Вынік extract (local/<гульня>/source/):
  <мова>.json   {табліца: {ключ: тэкст}}, ключы ў парадку Shared Data або табліцы
  shared.json   {табліца: {ключ: m_Id}}          — толькі рэжым StringTable
  meta.json     версія Unity, buildid Steam, колькасці; у маналітным рэжыме яшчэ
                `no_source` — у колькіх радкоў англійскай у гульні няма (у
                source_lang.json такія радкі — падказка з табліцы, не арыгінал)

Лаўнчар і ўсталёўшчык: новыя палі (crc_catalog_bin, hash_file, monolithic_table) —
payload schema 3; стары лаўнчар іх не ведае і паставіў бы пераклад, які гульня
адкідвае на старце.
"""
from .common import NAME, SECTION  # noqa: F401
from .extract import extract  # noqa: F401
from .apply import payload, check_path, apply, restore, installed  # noqa: F401
from .fonts import fonts_report  # noqa: F401

# apply падстаўляе кавалкі арыгінала на месца заглушак `[]` (tables.py)
FROM_ORIGINAL = True

# усталёўшчык (release.py)
from ..unity import PYINSTALLER as _UNITY  # noqa: E402
PYINSTALLER = [*_UNITY, "--collect-submodules", "belloc.engines.unity",
               "--exclude-module", "cv2", "--exclude-module", "spylls", "--exclude-module", "fontTools"]
