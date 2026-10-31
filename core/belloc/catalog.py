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
       "exe": "PonyIsland.exe", "language_name": "Беларуская", "replaces": "Русский",   — null: асобная мова
       "page": "https://…/releases/tag/pony-island-v1.0",
       "package": {"url": "…/pony-island-1.0.zip", "sha256": "…", "size": 123},
       "probe": {…}}}}                                       — payload без strings:
                                                               хопіць, каб спытаць engine.installed()

Пакет перакладу — <game_id>-<версія>.zip: payload.json (наш тэкст па ключах і
апісанне рэліза) і assets/ — тое ж, што ўсярэдзіне exe. Кода ў ім няма: рухавікі —
у лаўнчары. payload_schema большы за payload.SCHEMA лаўнчара → «абнавіце лаўнчар».

Каталог і пакет — даныя з сеткі, ім не давяраем: толькі https (і пасля
перанакіраванняў), абмежаваныя памеры, пакет — па sha256 з каталога да распакоўкі,
у zip — толькі payload.json і assets/, id гульні — толькі [a-z0-9._-] (ідзе ў шляхі),
шляхі payload — толькі ўнутры папкі гульні (install/paths.py).

    python -m belloc catalog <гульня> [--catalog ФАЙЛ] → пакет у build/release/ + запіс у каталог
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
import tempfile
import urllib.error
import urllib.request
import zipfile

from . import engines, payload as payload_mod
from .config import Loc
from .install import paths

CATALOG_URL = "https://raw.githubusercontent.com/stopthatnoise/belloc-catalog/main/catalog.json"
RELEASES = "https://github.com/stopthatnoise/belloc-catalog/releases"
SCHEMA = 1
MAX_CATALOG = 8 << 20               # catalog.json, байтаў
MAX_PACKAGE = 256 << 20             # пакет: спампаваны zip і ўсё, што ў ім, разам
MAX_FILES = 10000                   # файлаў у пакеце


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

class _HttpsOnly(urllib.request.HTTPRedirectHandler):
    """Перанакіраванні — толькі на https (GitHub Releases вядзе на свой CDN)."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.lower().startswith("https://"):
            raise urllib.error.URLError(f"перанакіраванне не на https: {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_HttpsOnly)


def _get(src: str, timeout: float, limit: int) -> bytes:
    """Змесціва па https або лакальнага файла (тэсты, свой каталог); больш за limit — памылка."""
    if "://" not in src:
        with open(src, "rb") as f:
            data = f.read(limit + 1)
    elif not src.lower().startswith("https://"):
        raise ValueError(f"толькі https: {src}")
    else:
        req = urllib.request.Request(src, headers={"User-Agent": "belloc"})
        with _opener.open(req, timeout=timeout) as r:
            data = r.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"больш за {limit} байтаў: {src}")
    return data


def fetch(src: str = CATALOG_URL, timeout: float = 5) -> dict | None:
    """Каталог або None (няма сеткі, бітая адказ): без каталога ўсё працуе далей."""
    try:
        cat = json.loads(_get(src, timeout, MAX_CATALOG))
        if not isinstance(cat.get("games"), dict):
            return None
    except Exception:
        return None
    # запіс з дзіўным id або не слоўнікам — не наш: адкідаем, астатнія працуюць
    cat["games"] = {gid: e for gid, e in cat["games"].items()
                    if isinstance(e, dict) and paths.GAME_ID.fullmatch(gid) and ".." not in gid}
    return cat


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
    want = str(pkg.get("sha256", "")).lower()
    if len(want) != 64 or any(c not in "0123456789abcdef" for c in want):
        raise SystemExit("У каталогу няма sha256 пакета — усталёўка спынена.")
    name = paths.name(pkg["url"].split("?")[0].replace("\\", "/").rsplit("/", 1)[-1])
    if not name.lower().endswith(".zip"):
        raise SystemExit(f"Пакет перакладу — не .zip: {name}")
    os.makedirs(cache, exist_ok=True)
    dst = os.path.join(cache, name)
    if os.path.exists(dst) and sha256(dst) == want:
        return dst
    try:
        data = _get(pkg["url"], timeout, MAX_PACKAGE)
    except ValueError as e:
        raise SystemExit(f"Пакет перакладу не спампаваны: {e}")
    if hashlib.sha256(data).hexdigest() != want:
        raise SystemExit("Пакет перакладу пашкоджаны (sha256 не супадае) — паспрабуйце пазней.")
    with open(dst + ".part", "wb") as f:
        f.write(data)
    os.replace(dst + ".part", dst)
    return dst


def open_package(path: str, dest: str) -> dict:
    """Распакаваць пакет у dest і вярнуць payload (assets — у dest/assets)."""
    with zipfile.ZipFile(path) as z:
        infos = z.infolist()
        if len(infos) > MAX_FILES or sum(i.file_size for i in infos) > MAX_PACKAGE:
            raise SystemExit("Пакет перакладу завялікі пасля распакоўкі.")
        for i in infos:
            n = i.filename
            if n != "payload.json" and not (n.startswith("assets/") and not n.endswith("/")):
                raise SystemExit(f"дзіўны файл у пакеце: {n}")
            paths.inside(dest, *n.split("/"))
            if (i.external_attr >> 16) & 0o170000 == 0o120000:      # сімвальная спасылка (unix)
                raise SystemExit(f"дзіўны файл у пакеце: {n}")
        shutil.rmtree(dest, ignore_errors=True)
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
            "language_name": rel["language_name"], "replaces": rel.get("replaces"),
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
    """Часовая папка пакета (open_package яе выдаляе і стварае нанова)."""
    return os.path.join(tempfile.gettempdir(), "belloc", paths.game_id(game_id))
