"""Лакалізацыя гульняў Telltale Tool (engine = "telltale": The Wolf Among Us Remastered).

Фарматы — ttarch2.py (архівы), landb.py (тэкст), font.py (бітмапавыя шрыфты),
lenc.py і luac.py (Lua), texture.py (надпісы на тэкстурах). Шыфр Lua і разбор
фарматаў — па TTG Tools (Den Em, GPL), гл. README.

Секцыя "telltale" у game.json:

  archive     "Archive"        — папка архіваў гульні (адносна game_dir), куды
                                 кладзецца мод і адкуль бярэцца аснова для патча
  source      "…/Pack"         — адкуль `extract` бярэ тэксты (па змаўчанні = archive;
                                 лакальны шлях — толькі ў local.json)
  lang        "english"        — мова landb, з якой перакладаем
  target      "spanish"        — мову якой падмяняем (па змаўчанні = lang). Калі
                                 іншая: перапісваюцца ўсе `*_<target>.landb` гульні,
                                 неперакладзенае — тэкстам мовы lang; шрыфты
                                 дамалёўваюцца і ў моўных наборах (French, German,
                                 Spanish), а d3dtx набору target, якія ёсць у
                                 агульных наборах, бяруцца адтуль (кнопкі меню)
  rename      {"Menu/ui_menu": {"Spanish": "Беларуская"}}
                               — радкі з такім тэкстам (мова lang) замяніць ва ўсіх
                                 мовах табліцы: назва мовы ў наладах
  hints       {"fr": "french"} — дадатковыя мовы landb у local/…/source (падказкі)
  fonts       {"Gotham Light": "fonts/montserrat/Montserrat[wght].ttf:Light", "": "…:Regular"}
                               — шрыфт гульні (пачатак імя ўнутры .font) → TTF[:варыяцыя]
                                 адносна games/<гульня>/ (вольныя шрыфты з ліцэнзіяй
                                 OFL.txt побач — едуць у payload як assets); "" — для
                                 астатніх. Без "fonts" шрыфты не патчацца
  font_chars  "…"              — якія сімвалы дамалёўваць (па змаўчанні font.BEL_CHARS)
  wrap        {"^Fables[0-9]+/(?!ui_)": 80}
                               — рэгулярка табліцы → колькі бачных сімвалаў у радку:
                                 даўжэйшыя радкі падзяляюцца `\\n` (apply.wrap_text) —
                                 сам рухавік пераносіць кірыліцу пасярод слова
  lua_key     "85ca8f…"        — ключ Blowfish для Lua гульні (hex; TTG Tools, lenc.py)
  lua_text    {"Menu_pause.lua": ["<хэш>", …]}
                               — бачныя радкі, зашытыя ў Lua (не ў landb): табліца
                                 «<набор>/<файл.lua>», ключ — common.key_hash радка
                                 (англійскі тэкст у рэпазіторый не трапляе); хэшы
                                 радкоў файла паказвае
                                 `python -m belloc.engines.telltale.luac strings <файл>`;
                                 apply мяняе радковыя канстанты bytecode (luac.py)

Тэкст — .landb (LanguageDB), файл на сцэну і мову: `<сцэна>_<мова>.landb`.
Табліца CSV = «<набор>/<сцэна>» (Fables101/env_bigbyapartment), ключ = ID
запісу. Набор — частка ключа: адно імя landb у розных эпізодах — розныя сцэны.
Хто кажа → source/context.json.

Наборы і дэскрыптары. Гульня чытае ўсе `_resdesc_50_<набор>.lua` з папкі архіваў
(адкрыты Lua, у арыгінале 2013 г. — зашыфраваны .lenc) і мантуе архівы
набору; у межах набору выйграе архіў, які ў спісе раней. Моўныя наборы
(`enableMode = "localization"`: french, german, spanish) мантуюцца, толькі калі
выбрана гэтая мова. Мод для кожнага набору, які трэба змяніць, кладзе:
  Fables_pc_BelLoc_<набор>_ar_all.ttarch2  — NCTT: landb, шрыфты з кірыліцай, d3dtx
  _resdesc_50_BelLoc_<набор>.lua           — копія дэскрыптара гульні з тым жа
                                             set.name, descriptionPriority + 100 і
                                             нашым архівам першым у спісе
Так перакрываецца менавіта той набор, які гульня ўключае для эпізоду, —
калізій паміж эпізодамі няма. Праверана ў дэма 2026-10-25: новы набор з
`enableMode = "localization"` гульня не мантуе, "constant" мантуе (але адзін
на ўсе эпізоды), наш архіў у канцы спісу набору — не выйграе, у пачатку —
выйграе. Дэскрыптар збіраецца з бягучага дэскрыптара гульні — пасля
абнаўлення гульні мод трэба перазабраць.

Тэкстуры з надпісамі мовы target (кнопкі, лісты) мод бярэ з агульных набораў
(англійскія); калі ў папцы гульні ў games/ ёсць textures.json — малюе на іх
беларускія надпісы (texture.py; прэв'ю — `belloc textures <гульня>`).

Файлы гульні не мяняюцца; restore выдаляе ўсе файлы *BelLoc*.
"""
from .common import NAME, SECTION, key_hash  # noqa: F401
from .extract import extract  # noqa: F401
from .apply import payload, check_path, apply, restore, installed, textures_preview  # noqa: F401
