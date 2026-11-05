# Pony Island — беларускі пераклад

Пераклад гульні **Pony Island** (Daniel Mullins Games, 2016; Steam appid 405640).
Агульныя правілы — [AGENTS.md](../../AGENTS.md) і [docs/](../../docs/); стыль —
[STYLE.md](STYLE.md); ацэнка, з якой пачыналася праца, — [RESEARCH.md](RESEARCH.md)
(аб'ём, шрыфты, кошт; `research/` — аднаразовыя скрыпты, не падтрымліваюцца).

> Нейрапераклад: тэкст перакладзены моўнай мадэллю, чалавекам цалкам не вычытаны.
> Нейрапераклад: мадэль Claude (Anthropic). Кіраўнік праекта: Віталь Аляхновіч.

## Спампаваць

Апошняя версія перакладу — **[1.0](https://github.com/stopthatnoise/belloc/releases/tag/pony-island-v1.0)**, што змянілася — [CHANGELOG.md](CHANGELOG.md).

- **[Лаўнчар belloc](https://github.com/stopthatnoise/belloc/releases/latest)** — сам знойдзе гульню, паставіць пераклад і будзе
  яго абнаўляць.
- Або ўсталёўшчык толькі для гэтай гульні: з рэліза спампуйце `PonyIsland_BE_1.0.zip`,
  запусціце exe і выберыце «Усталяваць». Пасля абнаўлення гульні ў Steam пераклад
  знікае — запусціце ўсталёўшчык (або лаўнчар) яшчэ раз.

## Праца з перакладам

```bash
python -X utf8 -m belloc extract pony-island   # TextAsset гульні → local/pony-island/source/ (з .orig, калі ёсць)
python -X utf8 -m belloc sync pony-island      # → translation/*.csv
python -X utf8 -m belloc lint pony-island      # --tag-re у lint_args: <START GAME> — бачны тэкст
```

## Гульня

| | |
|---|---|
| exe | `PonyIsland.exe`, дадзеныя `PonyIsland_Data/` |
| рухавік | Unity **2017.4.40f1**, **Mono** (`Managed/Assembly-CSharp.dll`) |
| Steam buildid | 25928685 (на 2026-10-20; бягучы — `local/pony-island/source/meta.json`) |
| дадзеныя | класічныя `level0…19`, `sharedassets*.assets`, `resources.assets`; без Addressables |
| рухавік у belloc | `unity-textasset-csv` (`core/belloc/engines/unity_textasset_csv/`) |

Код гульні чытаецца `ilspycmd`: `Localization`, `CsvReader`, `Csv`, `OSScreen`,
`SatanFace*`, `AsmodeusScreen`, `PITextBasedScreen`, `SoulOSScreen*`, `UserProfiles`,
`GameStrings`.

## Як уладкаваная лакалізацыя

- **Адна табліца** — TextAsset `Data/localization` у `resources.assets` (path_id 526):
  CSV, слупкі `заўвага, STRING ID, ENGLISH, …, RUSSIAN, …`. Гульня чытае яго сваім
  `CsvReader` (рэгулярка па коскам + `ReadLine`); экстрактар паўтарае гэты парсер, а
  `patch` перапісвае **толькі** поле RUSSIAN змененых запісаў — астатнія байты файла
  застаюцца як былі.
- **Ключ — англійскі тэкст.** `LocalizeText(en)` бярэ **першы** радок, чый ENGLISH
  супадае пасля выдалення `\n` і прабелаў без уліку рэгістра; `exactMatch` (ключавыя
  словы ўводу) — дакладнае супадзенне. ID — толькі ў 12 радкоў (`LocalizeTextById`).
  Пусты пераклад або роўны EN → паказваецца EN. Калі ў EN няма `\n`, гульня выкідае
  `\n` з перакладу. **У нашых CSV ключ — хэш** англійскага ключа (`key_hash`): тэкст
  гульні ў рэпазіторый не трапляе.
- Мову выбірае кнопка ў наладах; беларуская падмяняе **рускую** (`target: "ru"`).
  Кнопка мовы — UI Text «Pусский» (першая P лацінская) у `level0` і `resources.assets`.
- Тытры зашытыя ў код (`MainMenuCredits`): без праўкі DLL наш подпіс туды не дадаць.
- Карцінкі з тэкстам лакалізаваныя толькі для кітайскай — у нас, як і ў RU,
  застаюцца англійскімі. Лагатыпы PONY ISLAND / DEVIL ISLAND з `LocalizeText` таксама
  толькі для кітайскай (`onlyForLanguages`).

### Табліцы

`extract` рэжа CSV на 18 табліц па загалоўках раздзелаў у слупку заўваг (`sections` у
`game.json`): `01-menu`, `02-intro`, `03-act1`, …, `15-code`, `16-store` (крама Steam, у
гульні не відаць), `17-achievements` (дасягненні Steam), `18-misc`. Паўторы
англійскага ключа — `тэкст #2`. Заўвагі распрацоўшчыка — лакальна ў `note` як
`ctx: …`, у рэпазіторый не трапляюць; туды ж — пазнака дубля.

### Надпісы ў сцэнах — `19-scenes`

Каля 180 надпісаў TextMesh ляжыць прама ў сцэнах і ў CSV гульні не трапіў (радкі кода,
подпісы вокнаў, назвы зменных) — RU іх таксама не перакладаў. `extract` знаходзіць іх
(`scene_text.py`) і кладзе ў табліцу `19-scenes` (у `note` — файл і GameObject). Патч
ставіць іх двума спосабамі адразу:

- `TextMesh.m_Text` у файлах сцэн (`patch.files`: level3…13) — для дэкаратыўных
  радкоў (CodeLine тыпу Nothing, подпісы);
- радкі ў канец CSV гульні — для таго, што гульня перакладае сама: назвы зменных
  (VariableLineBuilder, CodeVariable), рэплікі DialogueSequencer, радкі CodeEvent.

Тэкст, які гульня перабудоўвае з назвы зменнай (аб'екты `(ChangeVar)`,
`(Conditional)`, `CodeVariable`), не перакладаецца — з яго бяруцца толькі назвы
зменных. Плэйсхолдары, нікі, назвы файлаў лацінкай і пасхалкі — у `scenes.ignore` /
`ignore_re`.

Надпісы, якія гульня знайшла б у CSV толькі праз слова-ўзор уводу (`TICKET` → радок
`ticket` = «лет»), таксама ідуць у `19-scenes`, інакш кнопка паказала б аснову. Радкі
кода ў `level5` і `level7` складаюць біблейскія цытаты (Лявіт 16, 1 Пятра 5:8) — гл. `note`.

**Дублі.** Радок з такім жа EN (або адрозным толькі рэгістрам/прабеламі), што ідзе
ніжэй, гульня ніколі не пакажа — пераклад бярэцца з першага. `patch` для дубля без
уласнага `bel` бярэ пераклад першага.

## Аб'ём

1053 радкі CSV (1033 унікальныя EN), 4,9 тыс. слоў EN + 179 надпісаў сцэн. Рускі
пераклад поўны (1044 радкі). Медыяна — 3 словы на радок.

## Увод гульца

Гулец шмат разоў піша з клавіятуры, а гульня шукае ў напісаным пераклад ключавога
слова. Таму радкі `was`, `pony`, `start`… — **не надпісы, а ўзоры**:

- большасць праверак — `Contains` (увод у ніжнім рэгістры змяшчае слова): можна даваць
  **аснову** без канчатка і без `і`/`ў`, каб падыходзілі і склоны, і руская раскладка
  (у ёй няма `і`, `ў`): `пон` ловіць «поні» і «пони», `лет` — «білет»/«билет»;
- імёны ў чаце (`jesus`, `bojack`, …) — **роўнасць** з уведзеным імем;
- `asmodeus` (адказ «назаві маё імя») бярэцца з радка `ASMODEUS` (07-act2-broken), а
  `hello`/`yes`/`no`/`password` — з першых радкоў з такім тэкстам (`Hello`,
  `OPTIONS_YES` «Так», `OPTIONS_NO` «Не», `Password`): гэтыя надпісы і ёсць ключавыя словы;
- англійскія словы, якіх няма ў CSV (`facade`, `menu`, `hi`, `ok`, `satan`, `error`,
  `iamerror`, `hisfatherpureevil`), працуюць і далей.

| дзе | EN | bel | праверка |
|---|---|---|---|
| Бафамет: пытанні | was / when / killed / where / how | бы / кал / заб / дзе / як | Contains |
| Бафамет | back, vision, show, yes, password, david | назад, дзеж, пакаж, так, пароль, давід | Contains |
| чат Hopeless Soul | hello, how, where, prophet, years, devil, lucifer, password | прывітанне, як, дзе, прарок, гад, д'ябал, люцыфер, пароль | Contains |
| чат: імя гульца | jesus, god, david, chara, sans, bojack, daniel, tasha, louey, lucifer, zeon, omar, bunk, solaire | ісус, бог, давід, чара, санс, боджэк, даніэль, таша, луі, люцыфер, зеон, омар, банк, салер | роўнасць |
| тэкставая гульня | start, game, options, credits | пач, гульн, налад, тытр | Contains |
| — налады | snowman, cheerful, aliasing, advanced, physics, app, obscure, ticket, fix, back | снег, фасад, згладж, пашыр, фіз, пакуп, схаван, лет, паправ, назад | Contains, па чарзе |
| — скачкі | jump, shoot, nothing | скак, страл, чака | Contains |
| Асмадэй | asmodeus (ASMODEUS), buer, infernal, pony, rememberthis | асмадэй, буэр, пякельны, пон, запамятай | Contains |
| профіль Люцыфера | ponies | пон (у файле пароляў — «поні») | Contains |

Ключавыя словы правераныя адно супраць аднаго (ніводнае не ўваходзіць у чужы варыянт
адказу). Мяняючы надпіс-падказку (`<ПАЧАЦЬ ГУЛЬНЮ>`, `'ПЯКЕЛЬНЫ'`, `'КІМ Я БЫЎ?'`),
правяраць адпаведны ўзор.

## Шрыфты

Усе шрыфты — **дынамічныя TTF** у асетах Font (`m_FontData`), атласаў няма. Асноўны
MINECRAFT (91 % TextMesh) мае ўсю беларускую кірыліцу. У Crumbled-Pixels, 04B_30__,
dpcomic (`resources.assets`) не было `І і Ў ў`; іх фолбэкі (BoutiqueBitmap, Chusung) —
таксама без іх. Патч (`dyn_fonts.py`): І/і — у cmap на I/i, Ў/ў — новы гліф з контураў
У/у і брэвіса з Й/й. `—` і `«»` у трох шрыфтах няма — гл. STYLE.md.

## Дастаўка ў гульню

```bash
python -X utf8 -m belloc patch pony-island --out local/pony-island/build/check   # праверка: копіі ў папку
python -X utf8 -m belloc patch pony-island                                       # у гульню
python -X utf8 -m belloc patch pony-island --restore                             # вярнуць арыгіналы
```

Тэкст, шрыфты і назва мовы ляжаць у адным `resources.assets` — усё ставіцца адным
праходам: секцыя `patch` у game.json — `files` (`level0`, сцэны), `fonts`, `ui_text`
(«Pусский» → «Беларуская»; радок у UI Text пачынаецца з `\n` — замена захоўвае яго).
Аснова — `.orig`, адбітак — `.bel`. CRC/подпісаў у класічных assets няма. Вынік
дэтэрмінаваны: праверачная копія і гульня — байт у байт.

**Для гульцоў** — `belloc package pony-island` (exe + ЧЫТАЙ.txt) і `belloc catalog
pony-island` (пакет для лаўнчара). У payload ключы — хэшы, англійскага тэксту няма.
Усталёўшчык правераны на копіі гульні (2026-10-20 — старым belloc, 2026-10-30/31 —
новым): усталёўка, паўтор, праверка цэласнасці, выдаленне — вынік байт у байт як
`patch --out`.

## Стан (2026-10-31)

- **Перакладзена 1053 / 1053** радкі CSV гульні + **179 / 179** надпісаў сцэн.
- Лінтэр: tags, placeholders, ws, spell, ruwords — чыста; застаюцца `latin` (назвы
  файлаў, Pony Island), `endpunct` (коскі ў канцы кавалкаў), `untranslated` (3 радкі
  наўмысна па-англійску: «INSERT … TO CONTINUE» — просьба распрацоўшчыка, ARG «HIS
  FATHER, PURE EVIL», «I Am Error»); у `19-scenes` spell/ushort ловяць наўмысныя
  «хакерскія» скарачэнні кода.
- **У гульні яшчэ не правяралася**: ці лезе «Беларуская» ў кнопку мовы; ці бачныя Ў/ў
  у дынамічных шрыфтах Unity 2017; кавалкі рэплік і кароткія надпісы (меню, аркада,
  код); увод ключавых слоў (табліца вышэй); ці не вылазяць радкі кода сцэн за панэль і
  ці бачныя кавалкі кнопак налад (`FIX STA` + `RT MENU`) у неангельскім экране.
- Рэліз не выкладаўся. Не зроблена: подпіс у тытрах (зашыты ў DLL), Steam-гайд.
