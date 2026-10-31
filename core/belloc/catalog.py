"""Каталог перакладаў: які пераклад якой гульні ёсць і якой версіі (для лаўнчара і exe).

Каталог — адзін публічны catalog.json (CATALOG_URL). Пакуль belloc закрыты, лаўнчар
тэстуецца на часовым публічным рэпазіторыі belloc-catalog: catalog.json у main, пакеты
перакладаў — у яго Releases (тэг <game_id>-v<версія>). Калі belloc адкрыецца,
CATALOG_URL і RELEASES глядзяць на яго, а belloc-catalog выдаляецца.

  {"schema": 1, "updated": "2026-10-31", "launcher": null,
   "games": {"pony-island": {
       "name": "Pony Island", "stores": {"steam": 405640},   — пакуль толькі steam
       "engine": "unity-textasset-csv", "payload_schema": 1,
       "version": "1.0", "date": "2026-10-31", "changes": "…",
       "contents": "Перакладзены ўвесь тэкст… (1232 радкі)",     — што перакладзена (release.contents)
       "steam_buildid": "25928685",                          — пад якую версію гульні
       "exe": "PonyIsland.exe", "language_name": "Беларуская", "replaces": "Русский",
       "page": "https://…/releases/tag/pony-island-v1.0",
       "package": {"url": "…/pony-island-1.0.zip", "sha256": "…", "size": 123},
       "probe": {…}}}}                                       — payload без strings:
                                                               хопіць, каб спытаць engine.installed()

Пакет перакладу — <game_id>-<версія>.zip: payload.json (наш тэкст па ключах і
апісанне рэліза) і assets/ — тое ж, што ўсярэдзіне exe. Кода ў ім няма: рухавікі —
у лаўнчары. payload_schema большы за payload.SCHEMA лаўнчара → «абнавіце лаўнчар».

    python -m belloc catalog <гульня> [--catalog ФАЙЛ] → пакет у build/release/ + запіс у каталог
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
import tempfile
import urllib.request
import zipfile

from . import engines, payload as payload_mod
from .config import Loc

CATALOG_URL = "https://raw.githubusercontent.com/stopthatnoise/belloc-catalog/main/catalog.json"
RELEASES = "https://github.com/stopthatnoise/belloc-catalog/releases"
SCHEMA = 1


# ---------------------------------------------------------------- версіі

def version_key(v: str | None) -> tuple:
    """"1.10" > "1.9"; нелічбавыя часткі — як радкі пасля лічбаў."""
    return tuple((0, int(x), "") if x.isdigit() else (1, 0, x) for x in (v or "0").split("."))


def newer(a: str | None, b: str | None) -> bool:
    """Ці версія a навейшая за b."""
    return version_key(a) > version_key(b)


def show_date(iso: str | None) -> str:
    """"2026-10-31" → "31.10.2026": так дата паказваецца гульцу; у даных — ISO."""
    try:
        y, m, d = (iso or "").split("-")
        return f"{int(d):02d}.{int(m):02d}.{int(y)}"
    except ValueError:
        return iso or ""


# ---------------------------------------------------------------- кліент

def _get(src: str, timeout: float) -> bytes:
    if "://" not in src:                     # лакальны файл (тэсты, свой каталог)
        with open(src, "rb") as f:
            return f.read()
    req = urllib.request.Request(src, headers={"User-Agent": "belloc"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch(src: str = CATALOG_URL, timeout: float = 5) -> dict | None:
    """Каталог або None (няма сеткі, бітая адказ): без каталога ўсё працуе далей."""
    try:
        cat = json.loads(_get(src, timeout))
        return cat if isinstance(cat.get("games"), dict) else None
    except Exception:
        return None


def supported(entry: dict) -> bool:
    """Ці можа гэты код паставіць пераклад: фармат payload і рухавік вядомыя."""
    return entry.get("payload_schema", 1) <= payload_mod.SCHEMA and entry.get("engine") in engines.ENGINES


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for part in iter(lambda: f.read(1 << 20), b""):
            h.update(part)
    return h.hexdigest()


def download(entry: dict, cache: str, timeout: float = 60) -> str:
    """Пакет перакладу ў cache (калі ўжо ёсць з тым жа sha256 — не спампоўваецца)."""
    pkg = entry["package"]
    os.makedirs(cache, exist_ok=True)
    dst = os.path.join(cache, os.path.basename(pkg["url"].split("?")[0]))
    if os.path.exists(dst) and sha256(dst) == pkg["sha256"]:
        return dst
    data = _get(pkg["url"], timeout)
    if hashlib.sha256(data).hexdigest() != pkg["sha256"]:
        raise SystemExit("Пакет перакладу пашкоджаны (sha256 не супадае) — паспрабуйце пазней.")
    with open(dst + ".part", "wb") as f:
        f.write(data)
    os.replace(dst + ".part", dst)
    return dst


def open_package(path: str, dest: str) -> dict:
    """Распакаваць пакет у dest і вярнуць payload (assets — у dest/assets)."""
    shutil.rmtree(dest, ignore_errors=True)
    with zipfile.ZipFile(path) as z:
        for n in z.namelist():
            if n.startswith("/") or ".." in n.split("/"):
                raise SystemExit(f"дзіўны шлях у пакеце: {n}")
        z.extractall(dest)
    return payload_mod.load(os.path.join(dest, "payload.json"))


# ---------------------------------------------------------------- зборка

def build_package(p: dict, dst: str):
    """payload (з release) + assets → zip; парадак і час файлаў сталыя — той жа
    пакет дае той жа sha256."""
    files = [("payload.json", json.dumps(payload_mod.dump(p), ensure_ascii=False).encode("utf-8"))]
    for a in p.get("assets", []):
        with open(payload_mod.asset(p, a), "rb") as f:
            files.append((f"assets/{a}", f.read()))
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files:
            z.writestr(zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0)), data, zipfile.ZIP_DEFLATED)


def entry(loc: Loc, p: dict, pkg_path: str, url: str) -> dict:
    rel = loc.section("release")
    probe = {k: v for k, v in payload_mod.dump(p).items() if k not in ("strings", "release")}
    stores = {"steam": loc.steam_appid} if loc.steam_appid else {}
    return {"name": loc.name, "stores": stores, "engine": loc.engine, "payload_schema": p["schema"],
            "version": rel["version"], "date": p["release"]["date"], "changes": rel.get("changes", ""),
            "contents": " ".join(rel.get("contents", "").format(
                strings=sum(len(v) for v in p["strings"].values())).split()),
            "steam_buildid": p.get("steam_buildid"), "exe": rel["exe"],
            "language_name": rel["language_name"], "replaces": rel["replaces"],
            "page": rel.get("url") or f"{RELEASES}/tag/{loc.id}-v{rel['version']}",
            "package": {"url": url, "sha256": sha256(pkg_path), "size": os.path.getsize(pkg_path)},
            "probe": probe}


def publish(loc: Loc, catalog_path: str | None = None) -> tuple[str, dict]:
    """Пакет перакладу ў build/release/ і запіс гульні ў каталог (файл ствараецца, калі няма)."""
    from . import release
    engine = engines.get(loc.engine)
    p = release.release_payload(loc, engine)
    version = p["release"]["version"]
    out_dir = os.path.join(loc.build, "release")
    os.makedirs(out_dir, exist_ok=True)
    name = f"{loc.id}-{version}.zip"
    pkg = os.path.join(out_dir, name)
    build_package(p, pkg)
    e = entry(loc, p, pkg, f"{RELEASES}/download/{loc.id}-v{version}/{name}")
    catalog_path = catalog_path or os.path.join(os.path.dirname(loc.local), "catalog", "catalog.json")
    cat = {"schema": SCHEMA, "launcher": None, "games": {}}
    if os.path.exists(catalog_path):
        with open(catalog_path, encoding="utf-8") as f:
            cat = json.load(f)
    cat["games"][loc.id] = e
    cat["games"] = dict(sorted(cat["games"].items()))
    cat["updated"] = datetime.date.today().isoformat()
    os.makedirs(os.path.dirname(os.path.abspath(catalog_path)), exist_ok=True)
    with open(catalog_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(cat, f, ensure_ascii=False, indent=1)
    print(f"пакет: {pkg} ({e['package']['size'] // 1024} КБ)")
    print(f"каталог: {catalog_path} — {loc.id} {version}")
    print(f"выкласці: gh release create {loc.id}-v{version} \"{pkg}\" --repo stopthatnoise/belloc-catalog"
          f" --title \"{p['release']['title']} {version}\"  і закамітаць catalog.json")
    return pkg, e


def cache_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~/.cache")
    return os.path.join(base, "belloc", "packages")


def unpack_dir(game_id: str) -> str:
    return os.path.join(tempfile.gettempdir(), "belloc", game_id)
