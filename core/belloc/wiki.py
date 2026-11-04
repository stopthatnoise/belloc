"""Назвы з Вікіпедыі: артыкул на мове арыгінала → беларускі артыкул (інтэрвікі).

Рэальныя назвы (гістарычныя рухі, арганізацыі, культуры, месцы, людзі) правяраем па
be.wikipedia: знаходзім артыкул на мове арыгінала, бярэм назву беларускага артыкула, на
які ён спасылаецца. Што ўжо праверана, ляжыць у слоўніку dicts/wikipedia.json
рэпазіторыя — адзін на ўсе гульні; чаго ў ім няма, `wiki` пытае ў Вікіпедыі і дапісвае
(новыя запісы камітуюцца разам з перакладам, дзе іх ужылі).

    python -m belloc wiki Blackshirts "Holy See"     # са слоўніка, а чаго няма — з Вікіпедыі
    python -m belloc wiki Camicie\\ nere --from it   # артыкул італьянскай Вікіпедыі
    python -m belloc wiki "Holy See" --note "у нас — Святы Пасад (catholicnews.by)"
    python -m belloc wiki Blackshirts --alias Blackshirt --alias "Camicie Nere"
    python -m belloc wiki Пасад --reverse            # па беларускай / рускай назве ў слоўніку
    python -m belloc wiki Blackshirts --refresh      # спытаць Вікіпедыю нанова
    python -m belloc wiki --list

Запіс: `be` — назва беларускага артыкула (null — артыкула няма), `ru` — рускага (толькі
падказка), `desc` — кароткае апісанне з Вікіпедыі (пра што гаворка), `note` — наша
заўвага (рашэнне, калі мы пішам інакш), `checked` — калі пыталі. `aliases` — іншыя
напісанні (назвы з гласарыя, перанакіраванні) → загаловак артыкула.

Назва беларускага артыкула — падказка, а не загад: рашэнне і чаму — у `note` слоўніка
і ў гласарыі гульні. Калі беларускага артыкула няма, форму будуем па правапісе; рускі
артыкул — толькі падказка.

Ліцэнзія: назвы і апісанні — з Вікіпедыі (CC BY-SA 4.0, аўтары — удзельнікі Вікіпедыі),
нашы заўвагі — CC BY-SA 4.0, як пераклады. Толькі назвы і кароткія апісанні — без
тэксту артыкулаў і без тэксту гульняў.
"""
from __future__ import annotations

import datetime
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from . import config

FILE = os.path.join(config.ROOT, "dicts", "wikipedia.json")
ABOUT = ("Назвы артыкулаў Вікіпедыі: мова арыгінала → be/ru (інтэрвікі). Назвы і desc — з "
         "Вікіпедыі, CC BY-SA 4.0; note — нашы заўвагі. Папаўняецца: python -m belloc wiki <назва>")
UA = "belloc-term-check/0.1 (Belarusian game localization tools)"
BATCH = 50                     # MediaWiki: да 50 загалоўкаў у адным запыце
PAUSE = 1.0                    # секунд паміж запытамі — Вікіпедыя адказвае 429 на частыя


def norm(s: str) -> str:
    return " ".join(s.replace("_", " ").split()).casefold()


def key(src: str, title: str) -> str:
    return f"{src}:{title}"


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
    data.setdefault("_about", ABOUT)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data["entries"] = dict(sorted(data["entries"].items(), key=lambda kv: kv[0].casefold()))
    data["aliases"] = dict(sorted(data["aliases"].items()))
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, path)


def find(data: dict, src: str, term: str) -> str | None:
    """Ключ запісу для назвы: загаловак артыкула або псеўданім, без уліку рэгістра."""
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


# ---------------------------------------------------------------- Вікіпедыя

def _api(src: str, params: dict) -> dict:
    url = f"https://{src}.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
        {"action": "query", "format": "json", "formatversion": 2, **params})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 3:
                raise SystemExit(f"Вікіпедыя: {e.code} {e.reason} ({src})")
            time.sleep(int(e.headers.get("Retry-After") or 0) or 5 * (attempt + 1))
        except urllib.error.URLError as e:
            raise SystemExit(f"Вікіпедыя недаступная: {e.reason}")
    raise AssertionError


def fetch(src: str, titles: list[str], api=_api) -> dict[str, dict]:
    """{запыт: {"title", "be", "ru", "desc", "disambig"} або {"missing": True}}."""
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
                          "lllang": lang, "lllimit": "max", "ppprop": "disambiguation"})["query"]
            for step in ("normalized", "redirects"):
                for x in q.get(step, []):
                    resolve[x["from"]] = x["to"]
            for p in q.get("pages", []):
                e = pages.setdefault(p["title"], {"title": p["title"], "be": None, "ru": None})
                if p.get("missing") or p.get("invalid"):
                    e["missing"] = True
                    continue
                e["desc"] = p.get("description", "")
                e["disambig"] = "disambiguation" in p.get("pageprops", {})
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


# ---------------------------------------------------------------- вывад

def show(k: str, e: dict, origin: str):
    src, _, title = k.partition(":")
    be = e.get("be")
    head = f"{title} → {be}" if be else f"{title} → (беларускага артыкула няма)"
    extra = [f"ru: {e['ru']}"] if e.get("ru") else []
    if src != "en" and e.get("en"):
        extra.append(f"en: {e['en']}")
    print(head + (f"  ({'; '.join(extra)})" if extra else ""))
    if e.get("desc"):
        print(f"    пра што: {e['desc']}")
    if e.get("note"):
        print(f"    заўвага: {e['note']}")
    if be:
        print(f"    https://be.wikipedia.org/wiki/{be.replace(' ', '_')}")
    print(f"    [{origin}, {src}, праверана {e.get('checked', '?')}]")


def run(terms: list[str], src="en", refresh=False, offline=False, note=None, aliases=(),
        reverse=False, list_all=False, path=None, api=_api) -> int:
    data = load(path)
    if list_all:
        for k, e in data["entries"].items():
            print(f"{k.partition(':')[2]} → {e.get('be') or '—'}" + (f"  · {e['note']}" if e.get("note") else ""))
        print(f"запісаў: {len(data['entries'])}, псеўданімаў: {len(data['aliases'])}")
        return 0
    if reverse:
        found = 0
        for t in terms:
            for k, e in data["entries"].items():
                if any(norm(t) in norm(e.get(f) or "") for f in ("be", "ru")):
                    show(k, e, "слоўнік")
                    found += 1
        if not found:
            print("у слоўніку няма; беларускую назву па-за слоўнікам шукайце праз англійскі артыкул")
        return 0
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
        for t, r in fetch(src, ask, api).items():
            if r.get("missing"):
                hints = suggest(src, t, api)
                print(f"{t}: артыкула ў {src}.wikipedia няма" + (f"; блізкія: {', '.join(hints)}" if hints else ""))
                rc = 1
                continue
            if r.get("disambig"):
                print(f"{t}: «{r['title']}» — старонка неадназначнасці; дайце дакладны загаловак")
                rc = 1
                continue
            k = key(src, r["title"])
            old = data["entries"].get(k, {})
            entry = {f: r.get(f) for f in ("be", "ru", "en") if f != src}
            entry.update(desc=r.get("desc", ""), note=old.get("note", ""), checked=today)
            if old and old.get("be") != entry.get("be"):
                print(f"    (было: {old.get('be')})")
            data["entries"][k] = entry
            add_alias(data, src, t, k)
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
        show(k, e, "Вікіпедыя" if t in ask else "слоўнік")
    if changed:
        save(data, path)
    return rc
