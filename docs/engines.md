# Рухавікі

Рухавік — папка `core/belloc/engines/<рухавік>/`: як дастаць тэкст з файлаў гульні
(`extract`) і як пакласці пераклад назад (`apply`). Поля секцыі game.json і ўсе
асаблівасці фармату — у docstring `__init__.py` рухавіка.

| `engine` у game.json | гульні | як пераклад трапляе ў гульню |
|---|---|---|
| `unity-localization` | Silver Pines | пакет com.unity.localization: табліца мовы-падказкі ў Addressables-бандле перапісваецца нашым тэкстам; І/і/Ў/ў — у TMP-шрыфты |
| `unity-textasset-csv` | Pony Island | CSV-табліца ў TextAsset класічных `.assets`: слупок рускай ← наш тэкст; шрыфты, надпісы сцэн |
| `unreal-locres` | Clair Obscur: Expedition 33, Dispatch | `.locres` з `.pak` → свой мод-пак у `~mods` з культурай, якую займае беларуская |
| `glacier` | 007 First Light | LOCR/DLGE у `.rpkg` → свой `chunkNpatchM.rpkg` і `patchlevel` |
| `telltale` | The Wolf Among Us | `.landb` у `.ttarch2` → наборы-перавызначэнні BelLoc побач з архівамі гульні; бітмапавыя шрыфты, Lua, надпісы на тэкстурах |
| `csv-folder` | Esoteric Ebb | гульня сама чытае папку мовы з CSV па ID — пішам сваю папку |
| `paradox` | (Crusader Kings III — праверана, перакладу няма) | `localization/replace/…` — толькі нашы `.yml` |

Файлы гульні, якія мы перапісваем, захоўваюцца побач як `<файл>.orig`, а `<файл>.bel` —
SHA-256 таго, што мы запісалі (`core/belloc/install/target.py`). Калі Steam абнавіў
гульню або праверыў цэласнасць, `.bel` не супадае — за аснову бярэцца свежы файл, а
не стары `.orig`. Рухавікі-моды (`telltale`, `glacier`, `unreal-locres`, `paradox`,
`csv-folder`) файлы гульні не мяняюць — толькі дадаюць свае.

## Новы рухавік

Інтэрфейс — `core/belloc/engines/base.py`. Новая папка з той жа раскладкай
(`common.py`, `extract.py`, `apply.py`, фарматы) і радок у `ENGINES`
(`engines/__init__.py`):

- `extract(loc, out)` кладзе ў `local/<гульня>/source/` `<мова>.json` у фармаце
  `{табліца: {ключ: тэкст}}`; заўвагі гульні для перакладчыка — `context.json`
  (`sync` дапісвае іх у `note` як `ctx: …` толькі лакальна); `meta.json` — версія,
  `steam_buildid`. Усё астатняе (CSV, пачкі, лінтэр, гласарый) працуе як ёсць.
- **Ключ радка не можа быць тэкстам гульні.** Калі ў гульні ключа няма (ключ —
  англійскі радок), ключ — хэш (`unity_textasset_csv`: `key_hash`, `telltale`: `lua_text`).
- `payload(loc)` — палі, патрэбныя `apply`, без шляхоў машыны і без тэксту гульні;
  нашы файлы (вольныя шрыфты) — у `assets` (`core/belloc/payload.py`).
- `apply(game_dir, payload, out, log)` — адзін код для `belloc patch`, усталёўшчыка і
  лаўнчара; з `out` — вынік у папку, гульня не чапаецца. `restore`, `installed`,
  `check_path` — для меню ўсталёўшчыка.
- `PYINSTALLER` — аргументы для зборкі exe (`core/belloc/release.py`);
  `files_dir(payload)` — толькі калі вынік `apply(out=…)` цалкам наш (архіў ручной
  усталёўкі); `fonts_report`, `textures_preview` — неабавязкова.
- Чужы код — толькі з ліцэнзіяй, сумяшчальнай з GPL, і з падзякай у README.
- Тэсты — на сінтэтычных фікстурах (`tests/`), без тэкстаў і файлаў гульняў.
- Праверка на гульні: `extract --out` і `patch --out` у папку, гульня не чапаецца.

## Шрыфты

Кірылічныя шрыфты гульняў амаль заўсёды рускія: **няма `І і Ў ў`** (часам і `«»`, `’`).
`belloc fonts <гульня> --text` — якія сімвалы перакладу шрыфтам не пакрытыя.

| сітуацыя | прыём |
|---|---|
| ёсць TTF/OTF (мод кладзе свае шрыфты) | `belloc ttf-glyphs <папка> --apply`: І/і → гліфы лацінскіх I/i у cmap. Ў/ў так не зробіш |
| дынамічны шрыфт Unity (TTF у асеце Font) | `unity_textasset_csv/dyn_fonts.py`: І/і — cmap, Ў/ў — у + брэвіс з й |
| статычны TMP-атлас у бандле (TTF няма) | `unity_localization/tmp_fonts.py`: І/і — спасылкі на гліфы I/i; Ў/ў — SDF у/У + брэвіс з й/Й; атлас расце ўверх |
| шрыфты ў `.ufont` Unreal | `unreal_locres/fonts.py`: гліфы з іншага шрыфта гульні з кірыліцай |
| бітмапавыя шрыфты (Telltale `.font`) | `telltale/font.py`: літары малююцца з вольнага TTF (OFL) у атлас; TTF ляжаць у `games/<гульня>/fonts/` з `OFL.txt` і едуць ва ўсталёўшчык як `assets` |

Вольныя шрыфты — з Google Fonts (OFL); з чаго выбіралі і чаму — у README папкі шрыфтоў
гульні. Шрыфты гульні ў рэпазіторый не кладуцца.

## Надпісы на тэкстурах

`textures.json` гульні: тэкстура, дзе сцерці старыя літары, межы новага тэксту, шрыфт
(адносна папкі гульні), радкі. Старыя літары сціраюцца OpenCV inpaint па масцы, новыя
малююцца колерам старых. Прэв'ю — `belloc textures <гульня>` → `local/<гульня>/build/textures/`.
Зараз — толькі `telltale` (`telltale/texture.py`); Unity-варыянт (шыльды Silver Pines)
пераносіцца разам з гульнёй. Тэкстуры гульні ў рэпазіторый не кладуцца — толькі
`textures.json`.

## Unity: асаблівасці

- Перад першай праўкай праверыць CRC бандла ў `catalog.bin`: калі не 0, гульня
  патчаны бандл адкіне.
- Абнаўленне гульні ў Steam перазапісвае бандлы — `extract`, `sync`, `patch` нанова.
