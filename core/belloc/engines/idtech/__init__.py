"""Лакалізацыя гульняў id Tech 7 / Motor (engine = "idtech": Indiana Jones and the Great Circle).

Секцыя "idtech" у game.json:

  base     "base"                       — папка *.resources і packagemapspec_pc.json (адносна game_dir)
  langs    {"en": 407, "ru": 426}       — variation рэсурсу lang/strings для кожнай мовы
                                          (source_lang, hint_lang і target)
  target   "ru"                         — мова, якую займае беларуская (толькі ў яе
                                          шрыфтах ёсць кірыліца)
  rename   {"#str_…": "…"}              — радкі, якія ставяцца як ёсць (назва мовы ў меню)
  original ["#str_menu_eula_content"]   — радкі, якія застаюцца на мове source_lang (юрыдычныя
                                          тэксты): у табліцы не трапляюць, apply бярэ іх з гульні

Тэкст (фармат — resources.py, lang.py): адзін рэсурс lang/strings на мову; апошняя
версія — у першым кантэйнеры карты common (packagemapspec_pc.json), дзе ён ёсць.
Табліцы — па ключы (common.table_of):

  vo/nl/<раздзел>      сюжэтныя рэплікі (…_ch04se01_…), па нумары з ключа
  vo/sl/<прамоўца>     сістэмныя баркі; vo/tp/<прамоўца>, vo/ef, vo/name
  ui/<група>           інтэрфейс; ui/mission/<месца>
  vo/_names            імёны над субтытрамі ([name:Fascist] → ключ «Fascist»)

Пачатак рэплікі — [name:…] і дырэктывы [p-5], [force], [dist:10] — extract зразае,
apply бярэ з арыгінала і падстаўляе імёны з vo/_names. Радкі [none] і пустыя ў
табліцы не трапляюць. Унутры тэксту застаюцца: [1.78] (кавалкі субтытра па часе),
^I…^I (курсіў), ^U, ^S, ^C"…", <JOY…>, %d, %s, \\( \\) — іх трэба захоўваць.
Хто кажа → source/context.json: «officerluigi · Fascist».

apply: lang/strings мовы target ← bel (неперакладзенае застаецца рускім) → новыя
даныя дапісваюцца ў канец таго ж кантэйнера без сціску, тры хэшы FarmHash
пералічваюцца (resources.py). Кантэйнер — <файл>.orig + .bel (install/target.py):
калі Steam абнавіў файл, за аснову бярэцца новы. З out — кантэйнер у папку, гульня
не чапаецца.

Кавалкі арыгінала (`"from_original"` у game.json, гл. tables.py): заглушка `[]` у bel ←
тэкст арыгінала без пачатку рэплікі. Great Circle: `(?s)\\A.+\\Z` — радок, які пераклад
пакідае як у арыгінале (нарыхтоўкі, коды, нямецкія рэплікі), у рэпазіторыі — `[]`.
"""
from .common import NAME, SECTION  # noqa: F401
from .extract import extract  # noqa: F401
from .apply import payload, check_path, apply, restore, installed  # noqa: F401

FROM_ORIGINAL = True

# усталёўшчык (release.py): Oodle — модуль ooz (пакет pyooz)
PYINSTALLER = ["--collect-all", "ooz",
               "--exclude-module", "UnityPy", "--exclude-module", "cv2", "--exclude-module", "spylls",
               "--exclude-module", "fontTools", "--exclude-module", "PIL"]
