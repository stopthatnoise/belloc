"""Маналітная табліца лакалізацыі: усе радкі мовы — у адным MonoBehaviour.

Некаторыя гульні на com.unity.localization не робяць бандлаў
`localization-string-tables-<мова>` (гл. common.py): радкі адной мовы ляжаць у
адным MonoBehaviour з іменем `<…>LocalizationTable`, у полі `m_data`:

    m_keys    ["<картка>/<поле>", "<табліца>/<ключ>", …]
    m_values  ["тэкст", …]                       # тым жа парадку

Ключ — радок, а не m_Id, таму:
  - парадак радкоў у source/<мова>.json — як у табліцы гульні (ён жа — парадак
    нашых CSV пасля sync);
  - раскладка па табліцах (`translation/<табліца>.csv`) — правіламі з game.json,
    бо адзін маналіт трымае некалькі лагічных табліц:

    "monolithic_table": "ruLocalizationTable",
    "table_bundle":    "g5ibkj7vdwf2g67g_assets_all*.bundle",   # дзе табліца (glob)
    "tables":  {"dialogue": "/dialog_lines$",
                "entities": "/(?:character_full_name|fullDescription)$|\\.gearModifiers\\."},
    "rest_table":      "system"        # усё, што не падыходзіць пад правілы

Правілы — рэгуляркі tables.regex (без паўтору ў паўторы): ключ правяраецца па
чарзе, перамагае першае; падыходзіць — search, а не fullmatch.

Запіс: значэнне па ключы замяняецца толькі там, дзе ключ ёсць у табліцы гульні.
Ключоў, якіх у гэтай версіі гульні няма, і радкоў, дзе `[]` не ўдалося
падставіць, лічыць асобна: яны не губляюцца моўчкі, як у рэжыме StringTable.
"""
from __future__ import annotations

from ... import tables


def table_of(bundle: str, name: str) -> dict[str, str]:
    """{ключ: тэкст} маналітнай табліцы `name` з бандла; парадак — як у гульні."""
    from ..unity.bundles import monobehaviours
    for _, t in monobehaviours(bundle):
        if t.get("m_Name") == name:
            if "m_data" not in t:
                raise SystemExit(f"«{name}»: няма поля m_data — гэта не маналітная табліца")
            data = t["m_data"]
            return dict(zip(data.get("m_keys", []), data.get("m_values", [])))
    raise SystemExit(f"у бандле няма аб'екта «{name}»")


def split(rows: dict[str, str], rules: dict[str, str], rest: str) -> dict[str, dict[str, str]]:
    """{табліца: {ключ: тэкст}} па правілах game.json; парадак радкоў захоўваецца."""
    if not rules:
        return {rest: dict(rows)}
    compiled = [(name, tables.regex(pat, f"tables.{name}")) for name, pat in rules.items()]
    out: dict[str, dict[str, str]] = {name: {} for name in [*rules, rest]}
    for key, text in rows.items():
        table = next((name for name, pat in compiled if pat.search(key)), rest)
        out[table][key] = text
    return {name: vals for name, vals in out.items() if vals}


def original(src: dict[str, str], key: str, current: str) -> str:
    """Крыніца для `[]`: англійскі тэкст гульні, інакш бягучае значэнне табліцы.

    У гэтай версіі гульні частка радкоў вядзецца толькі на мове табліцы (англійскай
    у даных няма), і менавіта яе бачыць гулец — гэта і ёсць арыгінал для такой пары.
    """
    return src[key] if key in src else current


def write(base: str, dst: str, name: str, want: dict[str, str], orig=None,
          pat=None) -> tuple[int, int, int]:
    """Запісаць пераклад у табліцу `name` → (запісана, няма ў гульні, без пары для `[]`).

    orig(env) -> {ключ: тэкст арыгінала} — калі ёсць, `[]` у перакладзе замяняюцца
    кавалкамі арыгінала (from_original, tables.expand) з таго ж бандла; радок, дзе
    пара не знайшлася, лічыцца асобна — гэта памылка перакладу, а не гульні.
    """
    import UnityPy
    from ..unity.bundles import save
    env = UnityPy.load(base)
    src = orig(env) if orig is not None and pat is not None else {}
    for o in env.objects:
        if o.type.name != "MonoBehaviour":
            continue
        try:
            t = o.read_typetree()
        except Exception:
            continue
        if t.get("m_Name") != name:
            continue
        data = t.get("m_data", {})
        keys, values = data.get("m_keys", []), data.get("m_values", [])
        have = set(keys)
        done = left = 0
        for i, key in enumerate(keys):
            text = want.get(key)
            if text is None:
                continue
            if pat is not None:
                # крыніца для `[]` — англійскі тэкст гульні; калі яго няма (у гэтай
                # версіі гульні радок вядзецца толькі на мове табліцы), бярэм
                # бягучае значэнне табліцы: гэта і ёсць арыгінал для гульца
                text = tables.expand(text, original(src, key, values[i]), pat)
                left += tables.PLACEHOLDER in text
            values[i] = text
            done += 1
        o.save_typetree(t)
        save(env, dst)
        return done, sum(1 for k in want if k not in have), left
    raise SystemExit(f"у бандле няма аб'екта «{name}»")
