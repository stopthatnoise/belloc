"""Unity Localization (com.unity.localization) у Addressables-бандлах.

Як уладкавана ў гульні:
  localization-assets-shared_…            Shared Data калекцый: m_Id (int64) → m_Key
  localization-string-tables-<мова>_…     StringTable на калекцыю: m_Id → m_Localized
  localization-asset-tables-<мова>_…      AssetTable (шрыфты, тэкстуры) па мовах
  localization-locales_…                  спіс моў

Секцыя "unity" у game.json:
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

Ключ табліцы — m_Key з Shared Data (чытэльны і сталы); m_Id для запісу apply
бярэ з Shared Data гульні гульца. Радкі без перакладу застаюцца на мове локалі.

Вынік extract (local/<гульня>/source/):
  <мова>.json   {табліца: {ключ: тэкст}}, ключы ў парадку Shared Data
  shared.json   {табліца: {ключ: m_Id}}
  meta.json     версія Unity, buildid Steam, колькасці
"""
from .common import NAME, SECTION  # noqa: F401
from .extract import extract  # noqa: F401
from .apply import payload, check_path, apply, restore, installed  # noqa: F401
from .fonts import fonts_report  # noqa: F401

# усталёўшчык (release.py)
from ..unity import PYINSTALLER as _UNITY  # noqa: E402
PYINSTALLER = [*_UNITY, "--collect-submodules", "belloc.engines.unity",
               "--exclude-module", "cv2", "--exclude-module", "spylls", "--exclude-module", "fontTools"]
