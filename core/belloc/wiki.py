"""Назвы з Вікіпедыі і Вікіданых: артыкул на мове арыгінала → беларускі артыкул (інтэрвікі).

Рэальныя назвы (гістарычныя рухі, арганізацыі, культуры, месцы, людзі) правяраем па
be.wikipedia: знаходзім артыкул на мове арыгінала, бярэм назву беларускага артыкула, на
які ён спасылаецца. Пра той жа элемент Вікіданых (адзін SPARQL-запыт на 50 назваў)
дадаём, што гэта (`type`: human, city…), пол чалавека (`sex`: м/ж — для роду дзеясловаў),
беларускую метку, калі яна іншая, чым артыкул, або артыкула няма (`be_label`), і форму
тарашкевіцай, калі артыкула няма (`tarask`). Што ўжо праверана, ляжыць у слоўніку
dicts/wikipedia.json рэпазіторыя — адзін на ўсе гульні; чаго ў ім няма, `wiki` пытае ў
Вікіпедыі і дапісвае (новыя запісы камітуюцца разам з перакладам, дзе іх ужылі).

    python -m belloc wiki Blackshirts "Holy See"     # са слоўніка, а чаго няма — з Вікіпедыі
    python -m belloc wiki Camicie\\ nere --from it   # артыкул італьянскай Вікіпедыі
    python -m belloc wiki Q<нумар> --alias "<назва>"   # элемент Вікіданых без артыкула
    python -m belloc wiki "Holy See" --note "у нас — Святы Пасад (catholicnews.by)"
    python -m belloc wiki Blackshirts --alias Blackshirt --alias "Camicie Nere"
    python -m belloc wiki Пасад --reverse            # па беларускай / рускай назве ў слоўніку
    python -m belloc wiki Blackshirts --refresh      # спытаць нанова
    python -m belloc wiki --refresh                  # увесь слоўнік нанова
    python -m belloc wiki --list

Калі артыкула на мове арыгінала няма, `wiki` паказвае і падобныя элементы Вікіданых —
іх куды больш, чым артыкулаў (вёскі, малавядомыя людзі). QID з іх даецца назвай, і
ў слоўніку з'яўляецца запіс `wd:Q…` (з `label` — меткай на мове арыгінала, `lang` — якой).

Запіс: `be` — назва беларускага артыкула (null — артыкула няма), `ru` — рускага (толькі
падказка), `desc` — кароткае апісанне (пра што гаворка), `qid` — элемент Вікіданых,
`type`, `sex`, `be_label`, `tarask` — з Вікіданых (гл. вышэй), `note` — наша заўвага
(рашэнне, калі мы пішам інакш), `checked` — калі пыталі. `aliases` — іншыя напісанні
(назвы з гласарыя, перанакіраванні) → запіс.

Назва беларускага артыкула — падказка, а не загад: рашэнне і чаму — у `note` слоўніка
і ў гласарыі гульні. Метку Вікіданых без артыкула мала хто правярае — падказка слабейшая;
тарашкевіца — толькі падказка, мы пішам афіцыйным правапісам. Калі нічога беларускага
няма, форму будуем па правапісе; рускі артыкул — толькі падказка.

Ліцэнзія: назвы і апісанні — з Вікіпедыі (CC BY-SA 4.0, аўтары — удзельнікі Вікіпедыі),
даныя Вікіданых — CC0, нашы заўвагі — CC BY-SA 4.0, як пераклады. Толькі назвы і кароткія
апісанні — без тэксту артыкулаў і без тэксту гульняў.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from . import config

FILE = os.path.join(config.ROOT, "dicts", "wikipedia.json")
ABOUT = ("Назвы артыкулаў Вікіпедыі: мова арыгінала → be/ru (інтэрвікі). Назвы і desc — з "
         "Вікіпедыі, CC BY-SA 4.0; qid, type, sex, be_label, tarask і запісы wd: — з Вікіданых, "
         "CC0; note — нашы заўвагі. Папаўняецца: python -m belloc wiki <назва>")
UA = "belloc-term-check/0.1 (Belarusian game localization tools)"
BATCH = 50                     # MediaWiki: да 50 загалоўкаў у адным запыце
PAUSE = 1.0                    # секунд паміж запытамі — Вікіпедыя адказвае 429 на частыя
QID = re.compile(r"^[Qq][1-9][0-9]*$")
LANG = re.compile(r"^[a-z]{2,3}(-[a-z]+)?$")   # мова ідзе ў адрас і ў SPARQL — толькі код
SEX = {"Q6581097": "м", "Q6581072": "ж", "Q2449503": "м", "Q1052281": "ж"}
SEX_NAME = {"м": "мужчына", "ж": "жанчына"}
TYPES = 3                      # колькі тыпаў (P31) захоўваць
WD_FIELDS = ("type", "sex", "be_label", "tarask")


def norm(s: str) -> str:
    return " ".join(s.replace("_", " ").split()).casefold()


def key(src: str, title: str) -> str:
    return f"{src}:{title}"


def is_qid(s: str) -> bool:
    return bool(QID.match(s.strip()))


# ---------------------------------------------------------------- слоўнік

def load(path: str | None = None) -> dict:
    path = path or FILE
    if not os.path.exists(path):
        return {"_about": ABOUT, "entries": {}, "aliases": {}}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("entries", {})
    data.setdefault("aliases", {})
    return data


def save(data: dict, path: str | None = None):
    path = path or FILE
    data["_about"] = ABOUT
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data["entries"] = dict(sorted(data["entries"].items(), key=lambda kv: kv[0].casefold()))
    data["aliases"] = dict(sorted(data["aliases"].items()))
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, path)


def find(data: dict, src: str, term: str) -> str | None:
    """Ключ запісу для назвы: загаловак артыкула, псеўданім або QID, без уліку рэгістра."""
    if is_qid(term):
        q = term.strip().upper()
        for k, e in data["entries"].items():
            if k == key("wd", q) or e.get("qid") == q:
                return k
        return None
    n = norm(term)
    k = data["aliases"].get(key(src, n))
    if k in data["entries"]:
        return k
    for k in data["entries"]:
        s, _, title = k.partition(":")
        if s == src and norm(title) == n:
            return k
    return None


def add_alias(data: dict, src: str, alias: str, k: str):
    s, _, title = k.partition(":")
    if norm(alias) != norm(title):
        data["aliases"][key(src, norm(alias))] = k


# ---------------------------------------------------------------- сетка

def _url(site: str, params: dict) -> str:
    """site: мова Вікіпедыі, "wikidata" (API Вікіданых) або "sparql" (query.wikidata.org)."""
    if site == "sparql":
        return "https://query.wikidata.org/sparql?" + urllib.parse.urlencode({"format": "json", **params})
    host = "www.wikidata.org" if site == "wikidata" else f"{site}.wikipedia.org"
    return f"https://{host}/w/api.php?" + urllib.parse.urlencode(
        {"action": "query", "format": "json", "formatversion": 2, **params})


def _api(site: str, params: dict) -> dict:
    req = urllib.request.Request(_url(site, params), headers={"User-Agent": UA})
    name = "Вікіданыя" if site in ("wikidata", "sparql") else "Вікіпедыя"
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 3:
                raise SystemExit(f"{name}: {e.code} {e.reason} ({site})")
            time.sleep(int(e.headers.get("Retry-After") or 0) or 5 * (attempt + 1))
        except urllib.error.URLError as e:
            raise SystemExit(f"{name} недаступная: {e.reason}")
    raise AssertionError


# ---------------------------------------------------------------- Вікіпедыя

def fetch(src: str, titles: list[str], api=_api) -> dict[str, dict]:
    """{запыт: {"title", "be", "ru", "desc", "disambig", "qid"} або {"missing": True}}."""
    langs = [lang for lang in ("be", "ru", "en") if lang != src][:2]
    out: dict[str, dict] = {}
    for i in range(0, len(titles), BATCH):
        chunk = titles[i:i + BATCH]
        pages: dict[str, dict] = {}
        resolve: dict[str, str] = {}
        for n, lang in enumerate(langs):
            if i or n:
                time.sleep(PAUSE)
            q = api(src, {"titles": "|".join(chunk), "redirects": 1, "prop": "langlinks|description|pageprops",
                          "lllang": lang, "lllimit": "max",
                          "ppprop": "disambiguation|wikibase_item"})["query"]
            for step in ("normalized", "redirects"):
                for x in q.get(step, []):
                    resolve[x["from"]] = x["to"]
            for p in q.get("pages", []):
                e = pages.setdefault(p["title"], {"title": p["title"], "be": None, "ru": None})
                if p.get("missing") or p.get("invalid"):
                    e["missing"] = True
                    continue
                props = p.get("pageprops", {})
                e["desc"] = p.get("description", "")
                e["disambig"] = "disambiguation" in props
                e["qid"] = props.get("wikibase_item")
                for ll in p.get("langlinks", []):
                    e[ll["lang"]] = ll.get("title") or ll.get("*")
        for t in chunk:
            r = t
            for _ in range(3):                 # нармалізацыя, потым перанакіраванне
                r = resolve.get(r, r)
            out[t] = pages.get(r, {"title": r, "missing": True})
    return out


def suggest(src: str, term: str, api=_api, limit=5) -> list[str]:
    q = api(src, {"list": "search", "srsearch": term, "srlimit": limit, "srprop": ""})["query"]
    return [x["title"] for x in q.get("search", [])]


# ---------------------------------------------------------------- Вікіданыя

SPARQL = """SELECT ?item ?label ?desc ?be ?tarask ?ru ?beWiki ?taraskWiki ?sex
 (GROUP_CONCAT(DISTINCT ?typeLabel; separator="|") AS ?types) WHERE {{
 VALUES ?item {{ {ids} }}
 OPTIONAL {{ ?item rdfs:label ?label FILTER(LANG(?label) = "{src}") }}
 OPTIONAL {{ ?item schema:description ?desc FILTER(LANG(?desc) = "{src}") }}
 OPTIONAL {{ ?item rdfs:label ?be FILTER(LANG(?be) = "be") }}
 OPTIONAL {{ ?item rdfs:label ?tarask FILTER(LANG(?tarask) = "be-tarask") }}
 OPTIONAL {{ ?item rdfs:label ?ru FILTER(LANG(?ru) = "ru") }}
 OPTIONAL {{ ?a schema:about ?item; schema:isPartOf <https://be.wikipedia.org/>; schema:name ?beWiki }}
 OPTIONAL {{ ?t schema:about ?item; schema:isPartOf <https://be-tarask.wikipedia.org/>; schema:name ?taraskWiki }}
 OPTIONAL {{ ?item wdt:P21 ?sex }}
 OPTIONAL {{ ?item wdt:P31 ?type. ?type rdfs:label ?typeLabel FILTER(LANG(?typeLabel) = "en") }}
}} GROUP BY ?item ?label ?desc ?be ?tarask ?ru ?beWiki ?taraskWiki ?sex"""


def wikidata(qids: list[str], src="en", api=_api) -> dict[str, dict]:
    """{QID: {"label", "desc", "be", "be_label", "tarask", "ru", "sex", "type"}}.

    label і desc — на мове src; be — назва артыкула be.wikipedia, be_label — метка."""
    if not LANG.match(src):
        raise SystemExit(f"мова: {src!r}")
    qids = list(dict.fromkeys(q.strip().upper() for q in qids if is_qid(q)))
    out: dict[str, dict] = {}
    for i in range(0, len(qids), BATCH):
        if i:
            time.sleep(PAUSE)
        ids = " ".join(f"wd:{q}" for q in qids[i:i + BATCH])
        res = api("sparql", {"query": SPARQL.format(ids=ids, src=src)})
        for b in res["results"]["bindings"]:
            v = {k: x["value"] for k, x in b.items()}
            q = v["item"].rsplit("/", 1)[-1]
            if q in out:                       # некалькі P21 — некалькі радкоў
                continue
            types = sorted({t for t in v.get("types", "").split("|") if t}, key=str.casefold)
            out[q] = {"label": v.get("label"), "desc": v.get("desc", ""), "be": v.get("beWiki"),
                      "be_label": v.get("be"), "tarask": v.get("taraskWiki") or v.get("tarask"),
                      "ru": v.get("ru"), "sex": SEX.get(v.get("sex", "").rsplit("/", 1)[-1]),
                      "type": ", ".join(types[:TYPES])}
    return out


def wd_search(src: str, term: str, api=_api, limit=5) -> list[tuple[str, str, str]]:
    """Элементы Вікіданых па метцы: [(QID, метка, апісанне)]."""
    r = api("wikidata", {"action": "wbsearchentities", "search": term, "language": src, "uselang": src,
                         "type": "item", "limit": limit})
    return [(x["id"], x.get("label", ""), x.get("description", "")) for x in r.get("search", [])]


def wd_fields(w: dict, be: str | None) -> dict:
    """Палі запісу з Вікіданых; be — назва беларускага артыкула (калі ёсць)."""
    f = {f: w[f] for f in ("type", "sex") if w.get(f)}
    if w.get("be_label") and w["be_label"].casefold() != (be or "").casefold():   # клінапіс = Клінапіс
        f["be_label"] = w["be_label"]
    if not be and w.get("tarask"):
        f["tarask"] = w["tarask"]
    return f


def _safe(fn, *a):
    """Вікіданыя — дадатак: калі не адказваюць, працуем без іх."""
    try:
        return fn(*a)
    except SystemExit as e:
        print(f"({e}; далей без Вікіданых)")
        return None


# ---------------------------------------------------------------- вывад

def title(k: str, e: dict) -> str:
    src, _, t = k.partition(":")
    return (e.get("label") or t) if src == "wd" else t


def show(k: str, e: dict, origin: str):
    src = k.partition(":")[0]
    t, be = title(k, e), e.get("be")
    if be:
        head = f"{t} → {be}"
    elif e.get("be_label"):
        head = f"{t} → {e['be_label']}  (метка Вікіданых; беларускага артыкула няма)"
    else:
        head = f"{t} → (беларускага артыкула няма)"
    extra = [f"ru: {e['ru']}"] if e.get("ru") else []
    if src != "en" and e.get("en"):
        extra.append(f"en: {e['en']}")
    print(head + (f"  ({'; '.join(extra)})" if extra else ""))
    if e.get("desc"):
        print(f"    пра што: {e['desc']}")
    facts = [x for x in (e.get("type"), SEX_NAME.get(e.get("sex"))) if x]
    if facts:
        print(f"    што гэта: {'; '.join(facts)}")
    if be and e.get("be_label"):
        print(f"    метка Вікіданых: {e['be_label']}")
    if e.get("tarask"):
        print(f"    тарашкевіцай: {e['tarask']} (толькі падказка)")
    if e.get("note"):
        print(f"    заўвага: {e['note']}")
    if be:
        print(f"    https://be.wikipedia.org/wiki/{be.replace(' ', '_')}")
    if e.get("qid"):
        print(f"    https://www.wikidata.org/wiki/{e['qid']}")
    where = f"wd/{e.get('lang', '?')}" if src == "wd" else src
    print(f"    [{origin}, {where}, праверана {e.get('checked', '?')}]")


# ---------------------------------------------------------------- каманда

def refresh_all(data: dict, path=None, api=_api) -> int:
    """Увесь слоўнік нанова — па мовах арыгінала; заўвагі і псеўданімы застаюцца."""
    groups: dict[str, list[str]] = {}
    for k, e in data["entries"].items():
        src, _, t = k.partition(":")
        groups.setdefault(e.get("lang", "en") if src == "wd" else src, []).append(t)
    rc = 0
    for src, terms in groups.items():
        rc |= run(terms, src, refresh=True, path=path, api=api)
    return rc


def run(terms: list[str], src="en", refresh=False, offline=False, note=None, aliases=(),
        reverse=False, list_all=False, path=None, api=_api) -> int:
    if not LANG.match(src):
        raise SystemExit(f"--from: код мовы (en, it, de…), а не {src!r}")
    data = load(path)
    if list_all:
        for k, e in data["entries"].items():
            be = e.get("be") or (f"{e['be_label']} (метка)" if e.get("be_label") else "—")
            print(f"{title(k, e)} → {be}" + (f"  · {e['note']}" if e.get("note") else ""))
        print(f"запісаў: {len(data['entries'])}, псеўданімаў: {len(data['aliases'])}")
        return 0
    if reverse:
        found = 0
        for t in terms:
            for k, e in data["entries"].items():
                if any(norm(t) in norm(e.get(f) or "") for f in ("be", "ru", "be_label", "tarask")):
                    show(k, e, "слоўнік")
                    found += 1
        if not found:
            print("у слоўніку няма; беларускую назву па-за слоўнікам шукайце праз англійскі артыкул")
        return 0
    if refresh and not terms:
        return refresh_all(data, path, api)
    if (note is not None or aliases) and len(terms) != 1:
        raise SystemExit("--note і --alias — толькі з адной назвай")

    keys: dict[str, str | None] = {t: (None if refresh else find(data, src, t)) for t in terms}
    ask = [t for t, k in keys.items() if k is None]
    if ask and offline:
        for t in ask:
            print(f"{t}: у слоўніку няма (--offline)")
        ask = []
    changed, rc = False, 0
    if ask:
        today = datetime.date.today().isoformat()
        titles = [t for t in ask if not is_qid(t)]
        qids = {t: t.strip().upper() for t in ask if is_qid(t)}
        found = fetch(src, titles, api) if titles else {}
        want = list(qids.values()) + [r["qid"] for r in found.values()
                                      if r.get("qid") and not r.get("missing") and not r.get("disambig")]
        wd = _safe(wikidata, want, src, api) if want else {}
        for t, r in found.items():
            if r.get("missing"):
                hints = suggest(src, t, api)
                print(f"{t}: артыкула ў {src}.wikipedia няма" + (f"; блізкія: {', '.join(hints)}" if hints else ""))
                items = _safe(wd_search, src, t, api) or []
                for q, label, desc in items:
                    print(f"    у Вікіданых: {q} {label}" + (f" — {desc}" if desc else ""))
                if items:
                    print(f'    калі гэта адзін з іх: belloc wiki Q… --from {src} --alias "{t}"')
                rc = 1
                continue
            if r.get("disambig"):
                print(f"{t}: «{r['title']}» — старонка неадназначнасці; дайце дакладны загаловак")
                rc = 1
                continue
            k = key(src, r["title"])
            old = data["entries"].get(k, {})
            entry = {f: r.get(f) for f in ("be", "ru", "en") if f != src}
            entry.update(desc=r.get("desc", ""), qid=r.get("qid"))
            if wd is not None:
                entry.update(wd_fields(wd.get(r.get("qid")) or {}, entry["be"]))
            else:                              # Вікіданыя не адказалі — пакідаем, што было
                entry.update({f: old[f] for f in WD_FIELDS if f in old})
            entry.update(note=old.get("note", ""), checked=today)
            if old and old.get("be") != entry.get("be"):
                print(f"    (было: {old.get('be')})")
            data["entries"][k] = entry
            add_alias(data, src, t, k)
            keys[t] = k
            changed = True
        for t, q in qids.items():
            if wd is None:
                rc = 1
                continue
            w = wd.get(q)
            if not w:
                print(f"{t}: элемента ў Вікіданых няма")
                rc = 1
                continue
            k = key("wd", q)
            old = data["entries"].get(k, {})
            entry = {"label": w["label"] or q, "lang": src, "be": w["be"], "ru": w["ru"],
                     "desc": w["desc"], "qid": q, **wd_fields(w, w["be"]),
                     "note": old.get("note", ""), "checked": today}
            if old and old.get("be") != entry["be"]:
                print(f"    (было: {old.get('be')})")
            data["entries"][k] = entry
            keys[t] = k
            changed = True
    for t in terms:
        k = keys.get(t)
        if not k:
            continue
        e = data["entries"][k]
        if note is not None:
            e["note"] = note
            changed = True
        for a in aliases:
            add_alias(data, src, a, k)
            changed = True
        origin = "слоўнік" if t not in ask else ("Вікіданыя" if is_qid(t) else "Вікіпедыя")
        show(k, e, origin)
    if changed:
        save(data, path)
    return rc
