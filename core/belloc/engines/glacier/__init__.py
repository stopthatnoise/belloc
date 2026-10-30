"""Лакалізацыя гульняў Glacier 2 (engine = "glacier": 007 First Light).

Секцыя "glacier" у game.json (ключы можна трымаць у local.json):

  runtime   "Runtime"                    — папка chunk*.rpkg і packagedefinition.txt (адносна game_dir)
  exe       "Retail/007FirstLight.exe"   — для версіі ў meta.json
  target    "ru"                         — слот мовы, які займае беларуская (гулец выбірае
                                           гэтую мову; англійскі шрыфт кірыліцы не мае)
  keys      {"text": "…", "packagedefinition": "…"}
                                         — ключы XTEA гульні (4 hex-словы)
  missions  [["/clover/", "M01_clover"], …]
                                         — місіі ў храналагічным парадку: рэгулярка па шляху
                                           сцэны → назва (scenes.py); без іх — табліцы па катэгорыях

Тэкст (формат — rpkg.py, locr.py, dlge.py):
  ui/<рэсурс>                 LOCR — інтэрфейс; ключ = хэш радка (8 hex)
  dlg/<місія>/<сцэна>         DLGE — субтытры адной сцэны ў парадку гульні (scenes.py);
                              `dlg/<місія>/_shared` — з некалькіх сцэн місіі;
  dlg/_common/<катэгорыя>/<голас>
                              — з розных місій (баркі NPC); катэгорыя — %DX_…% без «DX_»,
                              голас — код без нумара (CIVUKF01 → CIVUKF, MI6EMPLOYEE_CIVUKM07 → MI6EMPLOYEE)
                              ключ субтытра = «<рэсурс>:<нумар WavFile>»
  dlg/_speakers               імёны прамоўцаў з `{…}` загалоўка (ключ — «імя|пол»);
                              build падстаўляе пераклад ва ўсе субтытры слота target
Хто кажа → source/context.json: «CIVUKF01 ж · Civilian · NPC_Story» (м/ж — па канцы
кода голасу; апошняе — катэгорыя).

apply: слот target ← bel (неперакладзенае застаецца як было) →
chunkNpatchM.rpkg (M = афіцыйны patchlevel + 1) і patchlevel у packagedefinition.txt.
Нашы файлы пазначаюцца <файл>.bel (SHA-256); packagedefinition.txt — .orig + .bel:
калі Steam абнавіў файл, за аснову бярэцца новы. restore выдаляе патчы і вяртае
packagedefinition.txt; з out — тое ж у папку, гульня не чапаецца.
"""
from .common import NAME, SECTION  # noqa: F401
from .extract import extract  # noqa: F401
from .apply import payload, check_path, apply, restore, installed  # noqa: F401

# усталёўшчык (release.py): numpy (XTEA) і lz4 PyInstaller бачыць сам
PYINSTALLER = ["--exclude-module", "UnityPy", "--exclude-module", "cv2", "--exclude-module", "spylls",
               "--exclude-module", "fontTools", "--exclude-module", "PIL"]
