# Probably Stolen — ацэнка

Steam 4348910, Questing Goose Studio. Праверана на buildid 26525552 (2026-11-11).

## Вердыкт

Браць варта: рухавік — `unity-localization`, як у Silver Pines; `extract` спрацаваў
без змен у кодзе. Шрыфты асноўнага тэксту ўжо маюць І і Ў ў. Адзіная новая праца ў
ядры — CRC бандлаў у каталогу Addressables (гл. ніжэй). Аб'ём — каля двух Silver Pines.

## Рухавік і фармат

- Unity 2021.3.45f2, Mono (Assembly-CSharp.dll, ёсць 0Harmony, пустая папка `Mods/`).
- Пакет com.unity.localization, Addressables:
  `Probably Stolen_Data/StreamingAssets/aa/StandaloneWindows64/`
  - `localization-assets-shared_assets_all.bundle` — Shared Data;
  - `localization-string-tables-<мова>_assets_all.bundle` — 11 моў: en, ru, de, fr, es,
    pl, ja, zh, ko, it, ptbr (it/ko/ptbr — пустыя, ~3.7 КБ);
  - `localization-locales_assets_all.bundle`; asset tables (шрыфты па мовах) няма.
- Каталог — `aa/catalog.json` (JSON, не catalog.bin).
- Беларуская займае слот рускай (`preview_locale: "ru"`).

## Аб'ём

14 табліц, 6896 радкоў, ~51 100 слоў арыгінала (Silver Pines: 3469 / ~26 200).

| табліца | радкі | словы |
|---|---:|---:|
| Dialogue | 2544 | 18 744 |
| Item | 980 | 8 948 |
| Mechanic | 1578 | 8 704 |
| UI | 804 | 7 566 |
| NetworkUpgrade | 119 | 1 640 |
| RepPerkTable | 141 | 1 475 |
| MainMenu, PerkTable, NewGame, PhoneDialogue, ClientName, Hint, Tutorial, Interactable | 849 | 4 028 |

- Афіцыйная руская ёсць: 6894 з 6896 (не хапае па адным радку ў Interactable і PerkTable).
- Медыяна радка — 30 сімвалаў, 90-ы перцэнтыль — 92, максімум — 1215.
- Разметка: TMP-тэгі `<i>` (96), `<b>` (92), `<u>`, `<color>`, `<sprite>`, тэгі
  Febucci TextAnimator `<wave>`, `<slide>`; плэйсхолдэры `{0}` (936), `{0:PN}` (2),
  `{count}`. Для лінтэра — `--tag-re` з тэгамі TMP і Febucci.

## Шрыфты

TMP_FontAsset у класічных `sharedassets0/1.assets` і `resources.assets` (тыпавога дрэва
няма; дрэва з бандла Silver Pines не падыходзіць — іншая версія TMP). Табліцы сімвалаў
прачытаныя эўрыстычна з сырых байтаў:

- **з кірыліцай і І і Ў ў:** NotoSans-Bold/Medium/…Italic, NotoSans-Variable,
  NotoSerif-Medium/Bold/Variable, Tektur-Bold/SemiBold, RubikMonoOne, Caveat-Medium;
- **без кірыліцы:** Oxanium, OfficeCodePro, LiberationSans SDF, LcdSolid, LcdPhone,
  Pixelary, Mx437_Tandy2K (TTF без кірыліцы), CJK-шрыфты. Дзе імі пішацца тэкст — у
  рускай версіі там, відаць, fallback або лацінскія надпісы; праверыць у гульні.
- `«»` ёсць у большасці кірылічных; `’` і `—` няма ў Variable/Italic Noto — апостраф
  у беларускім тэксце трэба праверыць на экране (магчыма, `'`).

Патч шрыфтоў, хутчэй за ўсё, не патрэбны.

## Рызыкі

1. **CRC — правяраецца, абыходзіцца (праверана 2026-11-11).** У `catalog.json` усе 13
   бандлаў маюць ненулявы `m_Crc`. Табліцы en і ru з тэставымі радкамі MainMenu гульня
   адкінула: у `Player.log` — `CRC Mismatch … Will not load AssetBundle`, далей
   `RemoteProviderException`. Пасля абнулення `m_Crc` у каталогу тыя ж бандлы
   загрузіліся, лог чысты, тэкст з І і Ў на экране (Tektur і NotoSans — гліфы ёсць).
   Як абнуляць: `m_ExtraDataString` — base64 бінарнага патоку, JSON запісаў у UTF-16LE;
   лічбы `"m_Crc":<n>` замяняюцца на `0` і прабелы той жа даўжыні — даўжыні і зрушэнні
   ў `m_EntryDataString` не мяняюцца, base64 той жа даўжыні. Абнулялі ўсе 13 (прасцей,
   чым шукаць запіс па `m_InternalIds`).
   **Зроблена:** поле `crc_catalog` у секцыі `unity` (`unity_localization/crc.py`):
   `apply` піша `catalog.json` праз `Target` (`.orig`/`.bel`), `restore` вяртае.
   Праверана `belloc patch` → гульня → `--restore`: CRC-памылак няма, тэкст на экране,
   арыгіналы вернуты байт у байт.
2. Smart Strings (`{0:PN}`) — паглядзець, што за фарматар, і як ён скланяе для `ru`.
3. Надпісы на тэкстурах — не правяраліся.
4. У галоўным меню ёсць кнопка **Mods** — гл. «Сістэма модаў» ніжэй.
5. Мова гульні мяняецца выпадным спісам у правым верхнім куце галоўнага меню.

## Сістэма модаў (вывучана 2026-11-11, дэкампіляцыя Assembly-CSharp — толькі ў scratchpad)

Афіцыйная: кіраўніцтва распрацоўшчыкаў — github.com/dragonpan2/probably-stolen-modding
(README, ModdingGuide, APIChanges; ліцэнзіі няма — код адтуль не браць, толькі чытаць).

- Мод — папка ў `<гульня>/Mods/<мод>/` або Steam Workshop (`ModWorkshop`): `manifest.xml`
  (`ID`, `Name`, `Author`, `ModVersion`, `GameVersions`, `Assemblies`, `Capabilities`) і
  DLL з класам `IMod` (`Init`, `OnEnable`, `OnDisable`). Без DLL мод не грузіцца.
  Гулец сам уключае мод у меню Mods (акно з capabilities; для лакальнага —
  «не з Workshop»).
- Даныя мода, якія гульня чытае сама (capability `files` не трэба): `Localization/<код>.csv`
  (`ключ,значэнне`, адзін радок; `"…"` захоўвае прабелы, `\n` — перанос), `*.png/jpg`,
  гукі. Слоўнік — толькі для ключоў самога мода (`ModHelper.GetLocalized(modId, key)`),
  таблицы гульні ён **не** падмяняе.
- Сканер (`ModScanner`, Mono.Cecil): capabilities `files`, `network`, `process`, `steam`…
  Выклікі API `UnityEngine.Localization` напрасткі не абмяжоўваюцца. Harmony-патчы
  тыпаў гульні (Assembly-CSharp) — дазволеныя; патч тыпаў Unity/System лічыцца
  `reflection-external` — з 10.12.2026 такія моды адмаўляюцца.
- Мова: `LocHelper` → `LocalizationSettings.StringDatabase`; спіс у меню — статычны
  масіў `MainMenuUIController.LOCALE_DROPDOWN` (8 моў: en, zh, ru, de, ja, fr, es, pl);
  выбар захоўваецца ў ES3 (`locale`); `LocHelper.SetLocale` шукае локаль у
  `AvailableLocales`. Двукоссі для ru — «», для іншых кодаў — `"`.
- Трэба ведаць: ёсць аддалены trust-list распрацоўшчыкаў з kill switch — моды можна
  выключыць цэнтралізавана.

**Як мог бы выглядаць пераклад-мод** (без capabilities):
`Localization/be.csv` з ключамі `<табліца>/<ключ>` (наш тэкст; гульня грузіць сама) +
невялікая DLL: Harmony-патч `MainMenuUIController` дадае ў спіс «Беларуская», якая
ўключае локаль `ru` і ў загружаных `StringTable` (`StringDatabase.GetTable`) замяняе
`entry.Value` нашым тэкстам; пры выбары іншай мовы — `ReleaseTable`, каб вярнуліся
арыгіналы. Новую локаль `be` у `AvailableLocales` не дадаць: табліц для яе ў
Addressables няма.

| | патч файлаў (бандлы + CRC) | мод |
|---|---|---|
| файлы гульні | мяняюцца, `.orig`; праверка цэласнасці Steam вяртае | не чапаюцца |
| руская ў меню | знікае | застаецца, «Беларуская» — асобна |
| абнаўленне гульні | `extract`/`patch` нанова | ключы стабільныя — працуе далей |
| дастаўка | наш exe / лаўнчар | Workshop або папка `Mods/`; можна і праз лаўнчар |
| праца ў ядры | абнуленне CRC у `apply` (малая) | новы рухавік: зборка `be.csv` + C# DLL (пад GPL), зборка праз `dotnet` супраць DLL гульні (у рэпазіторый не кладуцца) |
| рызыкі | — | гулец мусіць уключыць мод; kill switch; не правераны: TMPLocalizer/LocalizeStringEvent абнаўляюцца пасля замены `entry.Value`? |

Не праверана ў гульні — толькі чытанне кода. Пераклад-моду патрэбны прататып.

## Што зроблена

1. Дастаўка — патч файлаў з `crc_catalog` (мод — запасны варыянт).
2. Пераклад: 15 пачак у 3 хвалях (`batches.json`), вычытка па лінтэры і GrammarDB.
3. Рэліз 0.9 — 2026-11-11.

Шлях да гульні — `local/probably-stolen/local.json`. Пробныя скрыпты (сканер шрыфтоў) —
у рэпазіторый не ішлі.
