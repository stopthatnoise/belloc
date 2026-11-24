"""Англійскі арыгінал: чанкі дыялогаў і DialogueDatabase.

Асобнай табліцы для англійскай у гульні няма (яна — мова распрацоўкі), таму
тэкст бярэцца з даных:

  MonoBehaviour з `references.RefIds` (чанкі `Chunk-*`, `DialogueDatabase`)
      картка — запіс з `m_cardId` і `m_cardData` = {m_keys, m_values}; значэнне —
      спасылка {rid} на запіс `references`, у якога `m_value` і ёсць тэкст.
      Ключы: `<картка>/<поле>` (`…/dialog_lines`), `<картка>/alternative1`,
      `<картка>/description`, `<картка>.modifier[N]/explanation`.

  сутнасці `DialogueDatabase` (у кожнай ёсць `m_shortName`)
      m_fullName → `<імя>/character_full_name`; m_description →
      `<імя>/fullDescription`; m_shortDescription → `<імя>/description`;
      m_source, m_alternativeNames[N], m_counterListener.Description,
      m_subTasks{ID}/name і updates{ID}/entry, поля Description з
      SourcePropertyPath; m_gearModifiersCollection.SkillModifiers[N].Description
      → `<імя>.gearModifiers.skillModifiers[N]/description`.

  сутнасці `m_entityType == "localization_table"` (меню, HUD, статусы…)
      `m_entries` = {m_keys, m_values}, значэнне — радок або JSON
      {"text": …} → `<імя_табліцы>/<ключ>`.

Бярэцца аб'яднанне ўсіх формаў, а залішнія ключы потым адсякаюцца тымі, што ёсць
у маналітнай табліцы: яна — крыніца праўды па складзе і парадку радкоў. Так
вынік не залежыць ад таго, ці распазнаў рухавік канкрэтнае поле.

Тэкст аддаецца як у гульні, без нармалізацыі (двукоссі вакол рэплікі, тэгі
<shy>, зорачкі курсіву застаюцца): гэта крыніца для src_hash, і любая праўка
змяніла б хэшы радкоў.
"""
from __future__ import annotations

import json

# ключ у нашых табліцах → палі сутнасці DialogueDatabase, якія могуць яго даць
ENTITY_FIELDS = {
    "character_full_name": ("m_fullName",),
    "fullDescription": ("m_description", "m_characterDescription"),
    "description": ("m_shortDescription", "m_description"),
    "source": ("m_source",),
    "shortDescription": ("m_shortDescription",),
    "short_description": ("m_shortDescription", "m_short_description"),
    "dissonanceTriggerDescription": ("m_dissonanceTriggerDescription",),
    "uniqueEffectsDescription": ("m_uniqueEffectsDescription",),
    "deactivation_custom_message": ("m_deactivationCustomMessage",),
    "task_alternative_name": ("m_alternativeName",),
    "task_alternative_description": ("m_alternativeDescription",),
}


def _text(value) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _add(out: dict[str, str], key: str, value) -> None:
    text = _text(value)
    if text is not None and key not in out:
        out[key] = text


def _rid(value) -> int | None:
    return value.get("rid") if isinstance(value, dict) else None


def _modifier_explanation(byrid: dict, child) -> str | None:
    """Тэкст «explanation» у дрэве падчыненьх уласцівасцяў мадыфікатара."""
    stack = [(byrid.get(_rid(child)) or {})]
    while stack:
        node = stack.pop()
        if not isinstance(node, dict):
            continue
        if str(node.get("m_name") or "").lower() == "explanation":
            return _text(node.get("m_value"))
        for ch in node.get("m_childProperties") or []:
            stack.append(byrid.get(_rid(ch)) or {})
    return None


def _card(out: dict[str, str], card_id: str, card: dict, byrid: dict) -> None:
    """Усе тэкставыя палі карткі (дыялог, апісанне, варыянты, мадыфікатары)."""
    for field, ref in zip(card.get("m_keys") or [], card.get("m_values") or []):
        target = byrid.get(_rid(ref)) or {}
        if field == "modifier":
            for i, child in enumerate(target.get("m_childProperties") or []):
                _add(out, f"{card_id}.modifier[{i}]/explanation", _modifier_explanation(byrid, child))
            continue
        _add(out, f"{card_id}/{field}", target.get("m_value"))


def _walk(node, visit) -> None:
    if isinstance(node, dict):
        visit(node)
        for value in node.values():
            _walk(value, visit)
    elif isinstance(node, list):
        for value in node:
            _walk(value, visit)


def _localization_table(out: dict[str, str], table: str, entries: dict) -> None:
    """m_entries сутнасці localization_table: значэнне — радок або {"text": …}."""
    for key, value in zip(entries.get("m_keys") or [], entries.get("m_values") or []):
        if isinstance(value, dict):
            text = value.get("text")
        else:
            text = value
            if isinstance(value, str) and value.lstrip().startswith("{"):
                try:
                    text = json.loads(value).get("text", value)
                except ValueError:
                    pass
        _add(out, f"{table}/{key}" if table else key, text)


def _entity(out: dict[str, str], data: dict) -> None:
    short = data.get("m_shortName")
    if not short:
        return
    if data.get("m_entityType") == "localization_table":
        _localization_table(out, short, data.get("m_entries") or {})
    for field, candidates in ENTITY_FIELDS.items():
        for name in candidates:
            if _text(data.get(name)):
                _add(out, f"{short}/{field}", data.get(name))
                break
    for i, value in enumerate(data.get("m_alternativeNames") or []):
        _add(out, f"{short}/alternativeNames_{i}", value)
    listener = data.get("m_counterListener")
    if isinstance(listener, dict):
        # ключ у гульні — з кропкай: "<сутнасць>.counter_listener/description"
        _add(out, f"{short}.counter_listener/description", listener.get("Description"))
    modifiers = (data.get("m_gearModifiersCollection") or {}).get("SkillModifiers") or []
    for i, modifier in enumerate(modifiers):
        if isinstance(modifier, dict):
            _add(out, f"{short}.gearModifiers.skillModifiers[{i}]/description",
                 modifier.get("Description"))
    seen = set()

    def visit(node):
        path = node.get("SourcePropertyPath")
        if path and "Description" in node and path not in seen:
            seen.add(path)
            _add(out, f"{short}.{path}/description", node.get("Description"))

    _walk(data, visit)
    for sub in (data.get("m_subTasks") or {}).get("m_values") or []:
        if not isinstance(sub, dict):
            continue
        sub_id = sub.get("ID")
        _add(out, f"{short}.subTasks{{{sub_id}}}/name", sub.get("Name"))
        for upd in (sub.get("Updates") or {}).get("m_values") or []:
            if isinstance(upd, dict):
                _add(out, f"{short}.subTasks{{{sub_id}}}.updates{{{upd.get('ID')}}}/entry",
                     upd.get("Entry"))


def texts(tree: dict) -> dict[str, str]:
    """{ключ: англійскі тэкст} з аднаго MonoBehaviour (чанк або DialogueDatabase)."""
    out: dict[str, str] = {}
    refs = (tree.get("references") or {}).get("RefIds") or []
    byrid = {r.get("rid"): (r.get("data") or {}) for r in refs}
    for data in byrid.values():
        if data.get("m_cardId") and isinstance(data.get("m_cardData"), dict):
            _card(out, data["m_cardId"], data["m_cardData"], byrid)
        _entity(out, data)
    return out


def all_texts(bundle: str, names: tuple[str, ...] = ()) -> dict[str, str]:
    """Аб'яднанне `texts` па ўсіх MonoBehaviour бандла (можна абмежаваць імёнамі)."""
    from ..unity.bundles import monobehaviours
    out: dict[str, str] = {}
    for _, tree in monobehaviours(bundle):
        if names and not any((tree.get("m_Name") or "").startswith(n) for n in names):
            continue
        for key, text in texts(tree).items():
            out.setdefault(key, text)
    return out
