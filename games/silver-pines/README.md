# Silver Pines — беларускі пераклад

Пераклад гульні **Silver Pines** (Wych Elm / Team17, Steam appid 2333000). Агульныя
правілы — [AGENTS.md](../../AGENTS.md) і [docs/](../../docs/); стыль перакладу —
[STYLE.md](STYLE.md) (тон, ты/вы, галасы персанажаў, лаянка, тыпаграфіка пад шрыфты
гульні); пачкі для паралельнай працы — `batches.json`.

> Нейрапераклад: мадэль Claude (Anthropic), чалавекам цалкам не вычытаны.
> Кіраўнік праекта: Віталь Аляхновіч.

## Спампаваць

Апошняя версія перакладу — **[1.1](https://github.com/stopthatnoise/belloc/releases/tag/silver-pines-v1.1)**, што змянілася — [CHANGELOG.md](CHANGELOG.md).

- **[Лаўнчар belloc](https://github.com/stopthatnoise/belloc/releases/latest)** — сам знойдзе гульню, паставіць пераклад і будзе
  яго абнаўляць.
- Або ўсталёўшчык толькі для гэтай гульні: з рэліза спампуйце `SilverPines_BE_1.1.zip`,
  запусціце exe і выберыце «Усталяваць». Пасля абнаўлення гульні ў Steam пераклад
  знікае — запусціце ўсталёўшчык (або лаўнчар) яшчэ раз.

## Праца з перакладам

```bash
python -X utf8 -m belloc extract silver-pines   # бандлы гульні → local/silver-pines/source/
python -X utf8 -m belloc sync silver-pines      # і stats / lint / glossary / fonts / patch
```

## Гульня

| | |
|---|---|
| exe | `Carpenter.exe` (унутраная назва праекта — Carpenter) |
| рухавік | Unity **6000.3.15f1**, **IL2CPP** (`GameAssembly.dll`) |
| Steam buildid | 25964535 (на 2026-10-19; бягучы — `local/silver-pines/source/meta.json`) |
| лакалізацыя | штатны пакет **Unity Localization** у Addressables 2.9.1 |
| лог | `%USERPROFILE%/AppData/LocalLow/Wych Elm/Silver Pines/Player.log` |
| рухавік у belloc | `unity-localization` (`core/belloc/engines/unity_localization/`) |

## Як уладкаваная лакалізацыя ў гульні

Усё ляжыць у бандлах `Carpenter_Data/StreamingAssets/aa/StandaloneWindows64/`
(агульная схема — docstring рухавіка):

| бандл | што ўнутры |
|---|---|
| `localization-locales_…` | 10 моў: en, zh, zh-Hant, fr, de, ja, pt-BR, **ru**, es, es-MX |
| `localization-assets-shared_…` | Shared Data 25 калекцый; плюс агульныя шрыфты |
| `localization-string-tables-<мова>_…` | 24 StringTable на мову (`Dialogue_ru`, …) |
| `localization-asset-tables-<мова>_…` | AssetTable `Fonts`: 4 ролі шрыфтоў → GUID TMP-шрыфта для мовы |
| `localization-assets-russian(ru)_…`, `fonts-russian_…` | рускія TMP-шрыфты (Montserrat, Vollkorn SC, Bad Script) |

Ролі шрыфтоў (`Fonts`): `NoticiaText` (асноўны тэкст), `ImpactLabelReversed`,
`Caveat`, `PermanentMarker`. Для `ru` апошнія дзве паказваюць на адзін асет.

Ключы — чытэльныя і сталыя: `Dialogue_<сцэна>_<n>_<хто кажа>`,
`Melee_Crowbar_Name` / `…_Description`, `Notification_LoreAdded`.
**Апошні кавалак ключа ў Dialogue — гэта той, хто кажа** — па ім вызначаць род
дзеясловаў. Галоўны герой — **Red Walker** (`…_Walker`, 437 рэплік), мужчына (так у
рускім перакладзе). Род іншых — у `glossary.json` (`gender`).

Частка надпісаў намалявана ў тэкстурах (шыльды, коміксы) — праз табліцы радкоў яны не
перакладаюцца, і **іх не перакладаем** (рашэнне 2026-10-31). Галаваломка з праектарам
у офісе шэрыфа (`Lore_Sheriff_WordPuzzle`): тэкст на сцяне і нумарны знак — англійскія
тэкстуры, рашэнне залічваецца па становішчы знака — пераклад яе не ламае.

## Аб'ём

3469 радкоў (3462 непустыя), ~25,8 тыс. англійскіх слоў, 142 тыс. сімвалаў: Dialogue
1188, Items 722, Examinable 326, Levels 222, SystemMenu 185, Lore 160, UIGame 149,
Television 87, астатняе — дробныя табліцы. Рускі пераклад поўны, апроч 24 службовых
пропускаў (`Misc_NullItem_*` і пад.).

## Асаблівасці тэксту

- Плэйсхолдары: `{0}`, `{input_0}`, `{input_1}`, `{ManualInput:ClimbUp/Display:Up}` —
  62 радкі. Тэгі: `<b> <i> <u> <color=white> <color=#da0033> <sprite name="Rotate_Clockwise">`;
  у EN ёсць бітыя `<color="white>` — капіяваць як ёсць.
- Сапраўдныя `\r\n` унутры тэксту: `Hints/MenuHint_ItemBoxStorage_Description`,
  `SystemMenu/Difficulty_Setting_Easy_Description` — захоўваюцца ў CSV байт у байт
  (`-text` у `.gitattributes`).
- У RU 125 радкоў з неразрыўным прабелам перад «—» — так і ў нас.
- Брэнды пішам лацінкай: Conmag, OpCo, Thelend, Omega, Terminal Drive (`glossary.json`,
  `lint_allow.txt`).

## Шрыфты

`belloc fonts silver-pines` паказвае: **усе TMP-шрыфты гульні — статычныя атласы**.

- рускія Montserrat / Vollkorn SC / Bad Script: 160–163 сімвалы, кірыліца і `Ёё` ёсць,
  `І і Ў ў` няма — дадаюцца пры `patch` (атлас 512→576, 1024→1152);
- у рускіх атласах няма і `«»` (у RU яны ёсць, гульня бярэ іх з fallback);
- Noticia Text, Impact Label, Caveat, Permanent Marker — без кірыліцы; для `ru` іх ролі ў
  AssetTable `Fonts` займаюць рускія шрыфты;
- ёсць адзін дынамічны `LiberationSans SDF - Fallback` (пусты атлас).
- у `resources.assets` — свае копіі рускіх Montserrat Regular/Bold (без `І і Ў ў`):
  іх бяруць экраны вынікаў праходжання і бонусаў «Новай гульні+». `belloc fonts` іх не
  бачыць (глядзіць толькі бандлы) — патчацца праз `font_assets` у game.json (заўвага
  гульца 2026-10-31: на гэтых экранах прападалі «і» і «ў»).

## Дастаўка ў гульню

```bash
python -X utf8 -m belloc patch silver-pines --out local/silver-pines/build/check   # праверка
python -X utf8 -m belloc patch silver-pines                                        # у гульню
python -X utf8 -m belloc patch silver-pines --restore                              # арыгіналы
```

- У гульні выбраць мову «Русский» — пасля патча яна завецца «Беларуская»;
  неперакладзенае застаецца рускім.
- Табліца `Save` у рускім бандле пустая (няма запісаў) — не трапляе.
- CRC у `catalog.bin` для ўсіх трох бандлаў = 0 — гульня змены не правярае.
- Праверана ў гульні 2026-10-19: меню налад з «ў»/«і» выглядае чыста.
- Абнаўленне гульні або праверка цэласнасці ў Steam вяртае арыгінальныя бандлы —
  пераклад ставіцца нанова ўсталёўшчыкам або `patch`.

**Для гульцоў** — `belloc package silver-pines` (усталёўшчык + ЧЫТАЙ.txt) і `belloc
catalog silver-pines` (пакет для лаўнчара). Тэкст гайда для Steam — `release/steam_guide.txt`
(версія 1.0, са спасылкамі на стары рэпазіторый; пры наступным рэлізе — абнавіць).

## Стан (2026-10-31)

- **Перакладзена 3462 / 3462 (100%)**; фінальная вычытка — 2026-10-20 (нататкі `?:`
  разабраныя, назвы адзіныя, `idioms` — праўкі ў 5 месцах). Рашэнні: канцоўкі Leave
  «Уцёкі», Rest «Спакой», Live «Жыццё»; складанасці «Спакойны», «Напружаны»,
  «Выжыванне і жах», «Кашмар»; Memento — «памятная рэч»; Reverse — «Наадварот».
- Лінтэр са слоўнікамі: spell/names/ruwords — 0; астатнія знаходкі ілжывыя (літары ў
  нумарах, Укл./Выкл., двукоссе перад «ў», «Cat»/«TV»/«Man» унутры складаных назваў).
- **Рэліз 1.0 — 2026-10-20** у старым рэпазіторыі stopthatnoise/silver-pines-bel-translation.
  Пасля яго — рэдактура (CHANGELOG.md), наступны рэліз — **1.1**.
