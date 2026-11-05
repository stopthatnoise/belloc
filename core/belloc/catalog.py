"""Каталог перакладаў: які пераклад якой гульні ёсць і якой версіі (для лаўнчара і exe).

Каталог — адзін публічны catalog/catalog.json у main рэпазіторыя belloc (CATALOG_URL),
пакеты перакладаў — у яго Releases (тэг <game_id>-v<версія>).

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

Каталог і пакет — даныя з сеткі, ім не давяраем:
- побач з catalog.json ляжыць catalog.json.sig — подпіс Ed25519 яго байтаў (base64);
  без сапраўднага подпісу ключом PUBLIC_KEY каталог лічыцца адсутным, таму падмена
  файла на серверы ці ў дарозе нічога не дае. Сакрэтны ключ — толькі ў мейнтейнера
  (key_path(), па-за git);
- сетка — толькі https на хасты HOSTS (і пасля перанакіраванняў), памеры абмежаваныя;
  спасылкі, якія адкрывае сістэма (page), — тое ж (safe_url), steam — толькі лік;
- пакет — па sha256 з каталога да распакоўкі, у zip — толькі payload.json і assets/,
  id гульні — толькі [a-z0-9._-] (ідзе ў шляхі), шляхі payload — толькі ўнутры папкі
  гульні (install/paths.py).

    python -m belloc catalog <гульня> [--catalog ФАЙЛ] → пакет у build/release/ + запіс у каталог
    python -m belloc catalog-key                       → новы ключ подпісу (раз)
    python -m belloc catalog-sign [ФАЙЛ]               → падпісаць каталог нанова (пасля праўкі рукамі)
"""
from __future__ import annotations

import base64
import binascii
import datetime
import hashlib
import json
import os
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from . import engines, payload as payload_mod
from .config import ROOT, Loc, local_root
from .install import paths

CATALOG_URL = "https://raw.githubusercontent.com/stopthatnoise/belloc/main/catalog/catalog.json"
RELEASES = "https://github.com/stopthatnoise/belloc/releases"
CATALOG_FILE = os.path.join(ROOT, "catalog", "catalog.json")       # копія ў рэпазіторыі
PUBLIC_KEY = "1d33b5d384a5588a3d497f6f9724ee3f587d6990b261128db38b1424e647d5ac"                                        # Ed25519, сыры ключ у hex
SIG = ".sig"                                                        # catalog.json + SIG — подпіс
HOSTS = {"github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com",
         "raw.githubusercontent.com", "store.steampowered.com"}
SCHEMA = 1
MAX_CATALOG = 8 << 20               # catalog.json, байтаў
MAX_SIG = 1024
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


# ---------------------------------------------------------------- подпіс

def key_path() -> str:
    """Сакрэтны ключ подпісу: BELLOC_CATALOG_KEY або local/keys/ (па-за git)."""
    return os.environ.get("BELLOC_CATALOG_KEY") or os.path.join(local_root(), "keys", "catalog-ed25519.pem")


def keygen(path: str | None = None) -> str:
    """Новы ключ у path (існы не перазапісваецца); вяртае публічны ключ для PUBLIC_KEY."""
    from Crypto.PublicKey import ECC
    path = path or key_path()
    if os.path.exists(path):
        raise SystemExit(f"ключ ужо ёсць: {path}")
    key = ECC.generate(curve="ed25519")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="ascii", newline="\n") as f:
        f.write(key.export_key(format="PEM"))
    return key.public_key().export_key(format="raw").hex()


def sign(data: bytes, path: str | None = None) -> bytes:
    """Подпіс байтаў каталога (base64) сакрэтным ключом."""
    from Crypto.PublicKey import ECC
    from Crypto.Signature import eddsa
    with open(path or key_path(), encoding="ascii") as f:
        key = ECC.import_key(f.read())
    return base64.b64encode(eddsa.new(key, "rfc8032").sign(data)) + b"\n"


def verify(data: bytes, sig: bytes, public_key: str | None = None) -> bool:
    """Ці sig — сапраўдны подпіс data ключом PUBLIC_KEY."""
    from Crypto.Signature import eddsa
    # eddsa грузіць іх па імені — без яўнага імпарту PyInstaller іх у exe не кладзе
    from Crypto.Math import _IntegerNat  # noqa: F401
    from Crypto.PublicKey import _edwards, _ec_lib  # noqa: F401
    try:
        key = eddsa.import_public_key(bytes.fromhex(public_key or PUBLIC_KEY))
        eddsa.new(key, "rfc8032").verify(data, base64.b64decode(sig.strip(), validate=True))
        return True
    except (ValueError, binascii.Error):
        return False


def sign_file(catalog_path: str, key: str | None = None):
    """catalog.json → catalog.json.sig."""
    with open(catalog_path, "rb") as f:
        data = f.read()
    with open(catalog_path + SIG, "wb") as f:
        f.write(sign(data, key))


# ---------------------------------------------------------------- кліент

def safe_url(u) -> str | None:
    """Спасылка, якую можна адкрыць або спампаваць: https на хост з HOSTS, без
    карыстальніка, партоў і прабелаў; інакш None (file://, \\\\server, ms-…: — ніколі)."""
    if not isinstance(u, str) or any(c.isspace() or ord(c) < 32 or c == "\\" for c in u):
        return None
    try:
        p = urllib.parse.urlsplit(u)
        port = p.port
    except ValueError:
        return None
    if p.scheme != "https" or p.hostname not in HOSTS or p.username or p.password or port not in (None, 443):
        return None
    return u


class _HttpsOnly(urllib.request.HTTPRedirectHandler):
    """Перанакіраванні — толькі па safe_url (GitHub Releases вядзе на свой CDN)."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not safe_url(newurl):
            raise urllib.error.URLError(f"перанакіраванне не туды: {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_HttpsOnly)


def _get(src: str, timeout: float, limit: int) -> bytes:
    """Змесціва па https або лакальнага файла (тэсты, свой каталог); больш за limit — памылка."""
    if "://" not in src:
        with open(src, "rb") as f:
            data = f.read(limit + 1)
    elif not safe_url(src):
        raise ValueError(f"толькі https на {', '.join(sorted(HOSTS))}: {src}")
    else:
        req = urllib.request.Request(src, headers={"User-Agent": "belloc"})
        with _opener.open(req, timeout=timeout) as r:
            data = r.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"больш за {limit} байтаў: {src}")
    return data


def _entry_ok(e, local: bool) -> bool:
    """Запіс каталога, з якім можна працаваць: steam — лік, пакет — па safe_url
    (у лакальным каталогу — і лакальны файл), page — па safe_url або None."""
    if not isinstance(e, dict) or not isinstance(e.get("stores", {}), dict):
        return False
    steam = e.get("stores", {}).get("steam")
    if steam is not None and (type(steam) is not int or steam <= 0):
        return False
    url = e["package"].get("url") if isinstance(e.get("package"), dict) else None
    if not (safe_url(url) or (local and isinstance(url, str) and "://" not in url)):
        return False
    e["page"] = safe_url(e.get("page"))
    return True


def fetch(src: str = CATALOG_URL, timeout: float = 5) -> dict | None:
    """Каталог або None (няма сеткі, бітая адказ, няма подпісу): без каталога ўсё працуе далей."""
    try:
        data = _get(src, timeout, MAX_CATALOG)
        if not verify(data, _get(src + SIG, timeout, MAX_SIG)):
            return None
        cat = json.loads(data)
        if not isinstance(cat.get("games"), dict):
            return None
    except Exception:
        return None
    # запіс з дзіўным id або палямі — не наш: адкідаем, астатнія працуюць
    local = "://" not in src
    cat["games"] = {gid: e for gid, e in cat["games"].items()
                    if paths.GAME_ID.fullmatch(gid) and ".." not in gid and _entry_ok(e, local)}
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


def update_readmes(loc: Loc, version: str, files: list[str] | None = None) -> list[str]:
    """Спасылкі на рэліз гульні ў README → новая версія; вяртае змененыя файлы.

    На гэтыя README вядуць гайды ў Steam (адрас папкі гульні не мяняецца), таму
    версія ў іх — заўсёды апошняя: **[1.0](…/tag/<гульня>-v1.0)** і `<file>_1.0.zip`.
    """
    import re
    files = files or [loc.path("README.md"), os.path.join(ROOT, "README.md")]
    link = re.compile(r"\*\*\[[0-9.]+\]\(" + re.escape(f"{RELEASES}/tag/{loc.id}-v")
                      + r"[0-9.]+\)\*\*")
    new_link = f"**[{version}]({RELEASES}/tag/{loc.id}-v{version})**"
    file = loc.section("release").get("file")
    exe_zip = re.compile(re.escape(f"{file}_") + r"[0-9.]+\.zip") if file else None
    changed = []
    for path in files:
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8", newline="") as f:
            s = f.read()
        t = link.sub(lambda m: new_link, s)
        if exe_zip:
            t = exe_zip.sub(lambda m: f"{file}_{version}.zip", t)
        if t != s:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(t)
            changed.append(path)
    return changed


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
    catalog_path = catalog_path or CATALOG_FILE
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
    if os.path.exists(key_path()):
        sign_file(catalog_path)
        signed = "падпісаны"
    else:
        signed = f"НЕ падпісаны (няма ключа {key_path()}) — лаўнчар яго не прыме"
    print(f"пакет: {pkg} ({e['package']['size'] // 1024} КБ)")
    print(f"каталог: {catalog_path} — {loc.id} {version}, {signed}")
    if catalog_path == CATALOG_FILE:
        for path in update_readmes(loc, version):
            print(f"README: {path} → {version}")
    print(f"выкласці: gh release create {loc.id}-v{version} \"{pkg}\" --repo stopthatnoise/belloc"
          f" --title \"{loc.name} {version}\" --latest=false  і закамітаць catalog.json з .sig")
    return pkg, e


def cache_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~/.cache")
    return os.path.join(base, "belloc", "packages")


def unpack_dir(game_id: str) -> str:
    """Часовая папка пакета (open_package яе выдаляе і стварае нанова)."""
    return os.path.join(tempfile.gettempdir(), "belloc", paths.game_id(game_id))
