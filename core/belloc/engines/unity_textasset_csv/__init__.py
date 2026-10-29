"""CSV-табліца ў TextAsset класічных .assets Unity (Pony Island) — фармат у textasset_csv.py.

Секцыя "textasset_csv" у game.json:
  data_dir     "PonyIsland_Data"
  assets       "resources.assets"           — файл з TextAsset (адносна data_dir)
  textasset    "localization"               — m_Name
  header_row   1                            — радок шапкі (з 0); ён і вышэй — не тэкст
  id_column    "STRING ID"
  note_column  0                            — заўвагі (кантэкст) і загалоўкі раздзелаў
  langs        {"en": "ENGLISH", "ru": "RUSSIAN"}
  target       "ru"                         — чый слупок перапісвае apply
  sections     {"MAIN MENU": "01-menu", …}  — загаловак у слупку заўваг → табліца
  scenes       {"ignore": […], "ignore_re": […]}  — надпісы сцэн па-за CSV (scene_text.py)
  patch        {"files": ["level0", …],      — іншыя файлы, апроч assets
                "fonts": ["…"],              — Font-асеты, куды дадаць І/і/Ў/ў (dyn_fonts.py)
                "ui_text": {"Pусский": "Беларуская"}}  — замены радкоў у MonoBehaviour

**Ключ радка — хэш** (textasset_csv.key_hash): у CSV гульні ключ — англійскі тэкст
(STRING ID ёсць рэдка; паўторы — «тэкст #2»), а тэкст гульні ў рэпазіторый не трапляе.
apply шукае радкі гульні па тым жа хэшы.

Вынік extract (local/<гульня>/source/):
  <мова>.json   {табліца: {хэш ключа: тэкст}}
  context.json  {табліца: {хэш: заўвага}} — заўвагі слупка 0 і пазнакі дубляў
  rows.json     {табліца: {хэш: нумар радка CSV}} — для даведкі
  meta.json     версія Unity, buildid Steam, колькасці

apply піша ўсё адным праходам: bel → слупок target TextAsset-а, І/і/Ў/ў у TTF шрыфтоў
patch.fonts, patch.ui_text (назва мовы), надпісы сцэн (табліца 19-scenes) — усе правы
трапляюць у адны і тыя ж файлы.
"""
from .common import NAME, SECTION  # noqa: F401
from .extract import extract  # noqa: F401
from .apply import payload, check_path, apply, restore, installed  # noqa: F401
