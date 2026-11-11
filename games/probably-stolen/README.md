# Probably Stolen — беларускі пераклад

Пераклад гульні **Probably Stolen** (Questing Goose Studio, Steam appid 4348910).
Агульныя правілы — [AGENTS.md](../../AGENTS.md) і [docs/](../../docs/); стыль —
[STYLE.md](STYLE.md); ацэнка і доследы — [RESEARCH.md](RESEARCH.md); пачкі — `batches.json`.

> Нейрапераклад: тэкст перакладзены моўнай мадэллю, чалавекам цалкам не вычытаны.
> Нейрапераклад: мадэль Claude (Anthropic). Кіраўнік праекта: Віталь Аляхновіч.

## Спампаваць

Апошняя версія перакладу — **[0.9](https://github.com/stopthatnoise/belloc/releases/tag/probably-stolen-v0.9)**, што змянілася — [CHANGELOG.md](CHANGELOG.md).

- **[Лаўнчар belloc](https://github.com/stopthatnoise/belloc/releases/latest)** — сам знойдзе гульню, паставіць пераклад і будзе
  яго абнаўляць.
- Або ўсталёўшчык толькі для гэтай гульні: з рэліза спампуйце `ProbablyStolen_BE_0.9.zip`,
  запусціце exe і выберыце «Усталяваць». Пасля абнаўлення гульні ў Steam пераклад
  знікае — запусціце ўсталёўшчык (або лаўнчар) яшчэ раз.

Беларуская займае месца рускай: у выпадным спісе моў (правы верхні кут галоўнага
меню) — пункт «Russian».

## Гульня

| | |
|---|---|
| exe | `Probably Stolen.exe` |
| рухавік | Unity 2021.3.45f2, Mono |
| лакалізацыя | Unity Localization у Addressables, `catalog.json` з CRC бандлаў |
| рухавік у belloc | `unity-localization`, `crc_catalog` абнуляе CRC |
| лог | `%USERPROFILE%/AppData/LocalLow/Questing Goose Studio/Probably Stolen/Player.log` |
| стан | 2026-11-11: **уся гульня перакладзена** — 6896 / 6896 (15 пачак у 3 хвалях), вычытка па лінтэры. **Рэліз 0.9**; праверка ў гульні працягваецца — гл. «Праверана ў гульні» |

Спіс моў зашыты ў коде гульні, новую мову туды не дадаць. Два радкі (дзверы і перк
пра агарафобію) у рускай табліцы гульні адсутнічаюць — там застаецца тэкст гульні.

## Ключы і табліцы

14 табліц, 6896 радкоў, ~51 тыс. слоў: Dialogue 2544, Mechanic 1578, Item 980,
UI 804, MainMenu 203, ClientName 192, RepPerkTable 141, NetworkUpgrade 119,
PerkTable 104, PhoneDialogue 82, NewGame 77, Hint 34, Tutorial 26, Interactable 12.

- Dialogue: `dialog_<персанаж або тып>_<сцэна>_<n>`; рэплікі гульца — з `_player`.
- Item: `item_<рэч>_name` / `_desc` / `_flavor`.
- Гульня сама ўключае Smart Strings для радкоў з `:plural:` / `:choose(` і падстаўляе
  пол (`[g:…]`) і рэгістр (`[r:…]`) кліента — гл. STYLE.md.

## Праца з перакладам

```bash
python -X utf8 -m belloc extract probably-stolen
python -X utf8 -m belloc sync probably-stolen
python -X utf8 -m belloc lint probably-stolen
python -X utf8 -m belloc patch probably-stolen --out local/probably-stolen/build/patch
```

UnityPy ёсць у `local/venv-release` (каманды — з `PYTHONPATH=core`).

## Праверана ў гульні

2026-11-11, build 26525552: пачатак гульні — меню, каляндар, навучанне. Кнопка
«Зводка за ноч» скарочана, каб улезла. Астатняе правяраецца — 0.9, пакуль гульня не
пройдзена: шрыфты без кірыліцы (Oxanium, Pixelary і інш.), апостраф у Noto
Variable/Italic, падстаноўка `[g:…]` і `:plural:` у краме.
