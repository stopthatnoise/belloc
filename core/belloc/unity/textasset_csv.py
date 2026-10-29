"""CSV-табліца ў TextAsset — класічныя .assets Unity без пакета Localization.

Так зроблена ў Pony Island (Unity 2017): адзін TextAsset (`Data/localization`
у resources.assets) — CSV, дзе слупок 0 — заўвага для перакладчыка,
слупок 1 — STRING ID (рэдка), далей — па слупку на мову. Гульня чытае яго
сваім CsvReader (`ReadLine` + рэгулярка па коскам па-за двукоссямі +
`Csv.Unescape`), ключ — англійскі тэкст: першы радок, чый ENGLISH супадае
пасля выдалення `\\n` і прабелаў без уліку рэгістра; ID — толькі для
`LocalizeTextById`.

Канфіг (секцыя "textasset_csv") і вынік extract — у engines/unity_textasset_csv.py.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import struct

import UnityPy

from . import scene_text
from .bundles import save

# CsvReader гульні (Assembly-CSharp): коска па-за двукоссямі; радок, дзе
# двукоссяў няцотна, — працяг на наступным фізічным радку
SPLIT = re.compile(r',(?=(?:[^"]*"[^"]*")*(?![^"]*"))')
RUN_ON = re.compile(r'^[^"]*(?:"[^"]*"[^"]*)*"[^"]*$')
MUST_QUOTE = (",", '"', "\n")


def unescape(s: str) -> str:
    if s.startswith('"') and s.endswith('"'):
        s = s[1:-1].replace('""', '"')
    return s


def escape(s: str) -> str:
    """Csv.Escape гульні."""
    s = s.replace('"', '""')
    return f'"{s}"' if any(c in s for c in MUST_QUOTE) else s


def records(text: str) -> list[tuple[str, str]]:
    """[(лагічны радок, сыры тэкст запісу)] — як ReadLine + склейка праз \\n.

    Сыры тэкст — з арыгінальнымі канчаткамі радкоў (\\r\\n, \\n, \\r): пры
    запісе нязменныя запісы ідуць байт у байт.
    """
    parts = re.split(r"(\r\n|\r|\n)", text)
    lines = list(zip(parts[0::2], parts[1::2] + [""]))
    if lines and lines[-1] == ("", ""):
        lines.pop()
    out, i = [], 0
    while i < len(lines):
        s, end = lines[i]
        raw = s + end
        i += 1
        while RUN_ON.match(s) and i < len(lines):
            nxt, end = lines[i]
            s += "\n" + nxt
            raw += nxt + end
            i += 1
        out.append((s, raw))
    return out


def norm(s: str) -> str:
    """Localization.FormatString: так гульня параўноўвае англійскі тэкст."""
    return s.replace("\n", "").replace(" ", "").lower()


def find_textasset(env, name: str):
    for o in env.objects:
        if o.type.name == "TextAsset":
            d = o.read()
            if d.m_Name == name:
                return o, d
    raise SystemExit(f"TextAsset «{name}» не знойдзены")


def read_table(path: str, name: str):
    env = UnityPy.load(path)
    o, d = find_textasset(env, name)
    return env, o, d, d.m_Script


def layout(s: dict, src: str, text: str):
    """Радкі CSV з тэкстам → [(нумар, табліца, ключ, {слупок: тэкст}, заўвага)].

    s — секцыя textasset_csv, src — мова арыгінала (ключ — яе тэкст)."""
    recs = [[unescape(v) for v in SPLIT.split(r)] for r, _ in records(text)]
    hdr = recs[s.get("header_row", 1)]
    col = {c: i for i, c in enumerate(hdr)}
    langs = s["langs"]
    for c in [s["id_column"], *langs.values()]:
        if c not in col:
            raise SystemExit(f"у шапцы CSV няма слупка «{c}»: {hdr}")
    sections = s.get("sections", {})
    i_en, i_id, i_note = col[langs[src]], col[s["id_column"]], s.get("note_column", 0)
    table = next(iter(sections.values()), "strings")
    seen: dict[str, int] = {}
    first: dict[str, tuple[str, str]] = {}
    out = []
    for n, r in enumerate(recs):
        if n <= s.get("header_row", 1):
            continue
        note = r[i_note].strip() if i_note is not None else ""
        if note in sections:
            table, note = sections[note], ""
        en = r[i_en]
        if not en.strip():
            continue
        if r[i_id].strip():
            key = r[i_id].strip()
        else:
            seen[en] = seen.get(en, 0) + 1
            key = en if seen[en] == 1 else f"{en} #{seen[en]}"
        ctx = [note] if note else []
        k = norm(en)
        if k in first and not r[i_id].strip():
            t0, k0, en0 = first[k]
            where = f"{t0}: {k0[:40]!r}"
            ctx.append(f"дубль: гульня бярэ першы такі радок ({where})" if en0 == en else
                       f"≈ {where} (розніца ў рэгістры/прабелах): надпісы бяруць той радок, "
                       f"гэты — толькі дакладны пошук (ключавыя словы ўводу)")
        first.setdefault(k, (table, key, en))
        vals = {lang: r[col[c]] for lang, c in langs.items()}
        out.append((n, table, key, vals, "; ".join(ctx)))
    return out


def scan_scenes(s: dict, src: str, rows, data_dir: str) -> dict[str, list[str]]:
    """Надпісы TextMesh у сцэнах data_dir, якіх гульня не знойдзе ў CSV (rows —
    layout CSV гэтай жа гульні).

    «Ёсць у CSV» — як у гульні (першы радок з тым жа тэкстам без \n і
    прабелаў, без уліку рэгістра), АЛЕ калі такі першы радок — слова-ўзор
    уводу ў ніжнім рэгістры (ticket → «лет»), надпіс ідзе ў 19-scenes:
    інакш кнопка TICKET паказала б аснову ўзору."""
    first: dict[str, str] = {}
    exact = set()
    for _, _, _, vals, _ in rows:
        en = vals[src]
        exact.add(en)
        first.setdefault(norm(en), en)

    def known(t):
        en = first.get(norm(t))
        return t in exact or (en is not None and not (en.islower() and en != t))

    c = s.get("scenes", {})
    return scene_text.scan(data_dir, known, c.get("ignore", []), c.get("ignore_re", []))


def key_hash(key: str) -> str:
    """Публічны ключ радка: ключ CSV — часта англійскі тэкст гульні, а тэкст гульні
    не публікуецца — у рэпазіторыі і ў payload толькі хэш."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def patched_text(s: dict, src: str, text: str, tr: dict[str, dict[str, str]],
                 keyf=None) -> tuple[str, int]:
    """CSV, дзе слупок target — bel (дзе ён ёсць). Астатнія байты — як былі.

    tr — {табліца: {ключ: bel}}; keyf(ключ CSV) → ключ у tr (усталёўшчык: key_hash)."""
    keyf = keyf or (lambda k: k)
    recs = records(text)
    hdr = [unescape(v) for v in SPLIT.split(recs[s.get("header_row", 1)][0])]
    i_t = hdr.index(s["langs"][s["target"]])
    # для дубляў без уласнага bel бярэцца пераклад аднолькавага тэксту
    by_norm: dict[str, str] = {}
    rows = layout(s, src, text)
    for _, table, key, vals, _ in rows:
        bel = tr.get(table, {}).get(keyf(key))
        if bel:
            by_norm.setdefault(norm(vals[src]), bel)
    n_done = 0
    for n, table, key, vals, _ in rows:
        bel = tr.get(table, {}).get(keyf(key)) or by_norm.get(norm(vals[src]))
        if not bel:
            continue
        line, raw = recs[n]
        fields = SPLIT.split(line)
        fields[i_t] = escape(bel.replace("\r\n", "\n").replace("\r", "\n"))
        end = re.search(r"(\r\n|\r|\n)?$", raw).group(0)
        recs[n] = (line, ",".join(fields) + end)
        n_done += 1
    return "".join(raw for _, raw in recs), n_done


def replace_serialized(raw: bytes, old: str, new: str) -> tuple[bytes, int]:
    """Замяняе ў сырых дадзеных аб'екта серыялізаваны радок Unity
    (int32 даўжыня + UTF-8 + выраўноўванне да 4), чый тэкст без прабелаў па
    краях роўны old; прабелы/\r па краях захоўваюцца. Вяртае (дадзеныя, колькасць)."""
    ob, n, pos = old.encode(), 0, 0
    while (i := raw.find(ob, pos)) >= 0:
        pos = i + 1
        for q in range(i - 4, max(i - 12, -1), -1):
            if q % 4:
                continue
            ln = struct.unpack_from("<i", raw, q)[0]
            end = q + 4 + ln
            if not (i + len(ob) <= end <= len(raw)):
                continue
            try:
                text = raw[q + 4:end].decode("utf-8")
            except UnicodeDecodeError:
                continue
            if text.strip() != old:
                continue
            nb = text.replace(old, new).encode()
            tail = raw[(end + 3) & ~3:]
            body = struct.pack("<i", len(nb)) + nb
            body += bytes(1) * (-len(body) % 4)
            raw = raw[:q] + body + tail
            pos = q + len(body)
            n += 1
            break
    return raw, n


def patch_file(s: dict, src: str, rel: str, base: str, dest: str, tr: dict,
               keyf=None, previews: dict | None = None,
               scene: dict[str, str] | None = None) -> list[str]:
    """Адзін файл гульні: base (арыгінал) → dest. rel — шлях адносна data_dir
    (TextAsset шукаецца толькі ў s["assets"]). Вяртае, што зроблена; пусты
    спіс — нічога не мяняецца і dest не пішацца. Гэты ж код — у ўсталёўшчыку.

    Надпісы сцэн (табліца 19-scenes, ключ — англійскі тэкст): TextMesh.m_Text
    у кожным файле, а ў TextAsset — радкі ў канец CSV; англійскі тэкст для
    іх бярэцца сканам сцэн побач з base. scene — гатовы {англійскі тэкст: bel}
    (усталёўшчык сканіруе гульню адзін раз, калі ўсе .orig ужо свежыя); без
    яго patch_file шукае сам праз tr + keyf."""
    from . import dyn_fonts
    pure = (lambda k: k) if keyf is None else key_hash
    keyf = keyf or (lambda k: k)
    p = s.get("patch", {})
    fonts_wanted, ui_text = set(p.get("fonts", [])), p.get("ui_text", {})
    env = UnityPy.load(base)
    log = []
    scene_tr = tr.get(scene_text.TABLE, {})
    # кожны TextMesh правяраецца па 19-scenes; keyf ва ўсталёўшчыку запамінае
    # «бачаныя» ключы ўсіх табліц, таму шукаем «чыстым» хэшам (keyf — толькі
    # на трапленні), інакш тэкст, які знік з CSV гульні, лічыўся б знойдзеным

    def scene_bel(en: str) -> str | None:
        if scene is not None:
            bel = scene.get(en)
        else:
            bel = scene_tr.get(pure(en))
            if bel:
                keyf(en)
        return bel if bel and bel != en else None

    for o in env.objects:
        kind = o.type.name
        if kind == "TextAsset" and rel == s["assets"]:
            d = o.read()
            if d.m_Name != s["textasset"]:
                continue
            new, n = patched_text(s, src, d.m_Script, tr, keyf)
            got = {(t, k): v[s["target"]] for _, t, k, v, _ in layout(s, src, new)}
            bad = [k for k, v in got.items() if tr.get(k[0], {}).get(keyf(k[1])) not in (None, v)]
            if bad:
                raise SystemExit(f"пасля запісу не супадае: {bad[:3]}")
            log.append(f"тэкст: {n} радкоў")
            if (scene or scene is None and scene_tr) and "scenes" in s:
                found = scene if scene is not None else                     scan_scenes(s, src, layout(s, src, d.m_Script), os.path.dirname(base))
                pairs = sorted((en, scene_bel(en)) for en in found if scene_bel(en))
                hdr = [unescape(v) for v in SPLIT.split(records(new)[s.get("header_row", 1)][0])]
                cols = {"en": hdr.index(s["langs"][src]), "target": hdr.index(s["langs"][s["target"]])}
                before = len(records(new))
                new = scene_text.append_rows(new, hdr, cols, pairs, escape)
                added = len(records(new)) - before
                if added != len(pairs):
                    raise SystemExit(f"дапісана {added} радкоў з {len(pairs)}")
                if added:
                    log.append(f"радкі сцэн у CSV: {added}")
            d.m_Script = new
            d.save()
        elif kind == "Font" and fonts_wanted:
            f = o.read()
            if f.m_Name not in fonts_wanted or not f.m_FontData:
                continue
            data, done = dyn_fonts.add_bel_glyphs(bytes(f.m_FontData))
            if done:
                f.m_FontData = list(data)
                f.save()
                log.append(f"шрыфт {f.m_Name}: {', '.join(done)}")
            if previews is not None:
                previews[f.m_Name] = data
        elif kind == "MonoBehaviour" and ui_text:
            raw = o.get_raw_data()
            total = 0
            for old, new in ui_text.items():
                raw, n = replace_serialized(raw, old, new)
                total += n
            if total:
                o.set_raw_data(raw)
                log.append(f"надпіс: {total} (path_id {o.path_id})")
    if scene or scene is None and scene_tr:
        n = scene_text.patch_textmeshes(env, scene_bel)
        if n:
            log.append(f"надпісы сцэны: {n}")
    if log:
        os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
        save(env, dest)
    return log


def files(s: dict) -> list[str]:
    """Файлы, якія патчацца (адносна data_dir)."""
    return list(dict.fromkeys([s["assets"], *s.get("patch", {}).get("files", [])]))

