"""AutoShorts – die App.

Start (Entwicklung):  python3 quellcode/app/server.py   →  http://127.0.0.1:8791
Fertige App:          AutoShorts.cmd (eine Datei, Doppelklick)

Die App ist die Steuerzentrale: Dashboard, Kalender, Studio und Einstellungen.
Die Videos selbst baut der Motor auf GitHub Actions – auch wenn dieser PC aus ist.
"""
import base64
import hashlib
import json
import os
import re
import secrets
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "engine"))
from naclpure import derive_key, encrypt, sealed_box  # noqa: E402
from appshell import MANIFEST, SERVICE_WORKER, ensure_desktop_shortcut, icon_png, open_app_window, windowless_python  # noqa: E402,E501

APP_VERSION = "dev"   # wird beim Bauen der Ein-Datei-Version gesetzt
ROOT = os.path.dirname(os.path.abspath(__file__))
HOST = "127.0.0.1"
PORT = int(os.environ.get("AS_PORT", "8791"))
BACKGROUND = "--hintergrund" in sys.argv
LAUNCHER = os.environ.get("AS_LAUNCHER") or os.path.abspath(sys.argv[0])
DATA = os.environ.get("AS_DATA", os.path.join(ROOT, "data"))
os.makedirs(DATA, exist_ok=True)

DEFAULT_OWNER, DEFAULT_REPO = "QuatratKopf", "autoshorts"
UPDATE_URL = "https://raw.githubusercontent.com/QuatratKopf/autoshorts/main/version.json"
REDIRECT = f"http://127.0.0.1:{PORT}/oauth/"
UA = f"AutoShorts/{APP_VERSION}"
SECRET_NAMES = ["GEMINI_API_KEY", "CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN", "OPENAI_API_KEY",
                "ELEVENLABS_API_KEY", "GOOGLE_CLIENT_SECRET", "TIKTOK_CLIENT_SECRET"]
LOCAL_SECRET = {"GOOGLE_CLIENT_SECRET": "youtube", "TIKTOK_CLIENT_SECRET": "tiktok"}

INDEX_HTML = None   # beim Bauen eingebettet
ICON_SVG = None


# ───────────────────────── Einstellungen auf diesem PC ─────────────────────────
SET_FILE = os.path.join(DATA, "einstellungen.json")
SET = {"token": "", "owner": DEFAULT_OWNER, "repo": DEFAULT_REPO, "client_secrets": {}, "auto_update": True}
try:
    with open(SET_FILE, encoding="utf-8") as _f:
        SET.update(json.load(_f))
except (OSError, ValueError):
    pass
_set_lock = threading.Lock()


def save_set():
    with _set_lock:
        tmp = SET_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(SET, f, ensure_ascii=False, indent=1)
        os.replace(tmp, SET_FILE)


LOG_FILE = os.path.join(DATA, "protokoll.txt")


def log(msg, level="info"):
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + ("" if level == "info" else level.upper() + " ") + str(msg)
    print(line, flush=True)
    try:
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 2_000_000:
            os.replace(LOG_FILE, LOG_FILE + ".1")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


# ───────────────────────── Internet ─────────────────────────
def http(method, url, body=None, headers=None, form=None, timeout=40):
    """Gibt (Status, Bytes) zurück, auch bei Fehlern."""
    h = {"User-Agent": UA, **(headers or {})}
    data = None
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        h["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except urllib.error.URLError as e:
        if "CERTIFICATE" in str(e).upper():
            return _curl(method, url, data, h, timeout)
        raise ValueError("Keine Internetverbindung oder Server nicht erreichbar.") from e


def _curl(method, url, data, headers, timeout):
    """Ersatzweg, z. B. wenn Python auf dem Mac keine Zertifikate hat."""
    import shutil
    import subprocess
    if not shutil.which("curl"):
        raise ValueError("Zertifikatsfehler und kein curl vorhanden.")
    args = ["curl", "-sS", "-X", method, "-w", "\n%{http_code}", url]
    for k, v in headers.items():
        args += ["-H", f"{k}: {v}"]
    if data is not None:
        args += ["--data-binary", "@-"]
    r = subprocess.run(args, input=data, capture_output=True, timeout=timeout)
    out = r.stdout
    body, _, code = out.rpartition(b"\n")
    return int(code or 0), body


def gh(method, path, body=None, raw=False, token=None):
    token = token if token is not None else SET.get("token")
    h = {"Accept": "application/vnd.github.raw+json" if raw else "application/vnd.github+json",
         "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        h["Authorization"] = "Bearer " + token
    return http(method, "https://api.github.com" + path, body=body, headers=h)


def repo_path(p=""):
    return f"/repos/{SET['owner']}/{SET['repo']}{p}"


def gh_json(method, path, body=None, ok=(200, 201, 204)):
    s, b = gh(method, repo_path(path), body)
    if s not in ok:
        try:
            msg = json.loads(b).get("message", "")
        except ValueError:
            msg = b[:200].decode("utf-8", "replace")
        if s == 401:
            raise ValueError("Der GitHub-Zugangsschlüssel ist ungültig oder abgelaufen.")
        if s in (403, 404):
            raise ValueError(f"GitHub verweigert den Zugriff ({msg or s}). Prüfe die Rechte des Zugangsschlüssels.")
        raise ValueError(f"GitHub meldet {s}: {msg}")
    return json.loads(b) if b else {}


def put_file(path, content_bytes, message):
    s, b = gh("GET", repo_path(f"/contents/{path}?ref=main"))
    sha = json.loads(b).get("sha") if s == 200 else None
    body = {"message": message, "content": base64.b64encode(content_bytes).decode(), "branch": "main"}
    if sha:
        body["sha"] = sha
    gh_json("PUT", f"/contents/{path}", body)


def dispatch(inputs):
    gh_json("POST", "/actions/workflows/autoshorts.yml/dispatches", {"ref": "main", "inputs": inputs})


# ───────────────────────── Anmeldung bei YouTube / TikTok (läuft hier, Ergebnis verschlüsselt ins Repository) ─────────────────────────
OAUTH = {}   # state -> {platform, client_id, verifier, t}


def oauth_start(platform, client_id):
    client_id = (client_id or "").strip()
    if not client_id:
        raise ValueError("Bitte zuerst die Client-ID eintragen und speichern.")
    if not SET.get("client_secrets", {}).get(platform):
        raise ValueError("Bitte zuerst das Client-Secret unter Zugangsdaten auf diesem PC eintragen.")
    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(64)[:96]
    OAUTH[state] = {"platform": platform, "client_id": client_id, "verifier": verifier, "t": time.time()}
    for k in [k for k, v in OAUTH.items() if time.time() - v["t"] > 1800]:
        OAUTH.pop(k, None)
    if platform == "youtube":
        ch = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        q = {"client_id": client_id, "redirect_uri": REDIRECT, "response_type": "code",
             "scope": "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly",
             "access_type": "offline", "prompt": "consent", "state": state,
             "code_challenge": ch, "code_challenge_method": "S256"}
        return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(q)
    q = {"client_key": client_id, "scope": "user.info.basic,user.info.stats,video.publish,video.upload,video.list",
         "response_type": "code", "redirect_uri": REDIRECT, "state": state,
         "code_challenge": hashlib.sha256(verifier.encode()).hexdigest(), "code_challenge_method": "S256"}
    return "https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode(q)


def oauth_finish(params):
    if params.get("error"):
        raise ValueError(params.get("error_description") or params.get("error"))
    p = OAUTH.pop(params.get("state", ""), None)
    if not p:
        raise ValueError("Die Anmeldung ist abgelaufen. Bitte in der App erneut auf „Verbinden“ tippen.")
    platform, sec = p["platform"], SET["client_secrets"].get(p["platform"], "")
    code = params.get("code", "")
    if platform == "youtube":
        s, b = http("POST", "https://oauth2.googleapis.com/token", form={
            "code": code, "client_id": p["client_id"], "client_secret": sec, "redirect_uri": REDIRECT,
            "grant_type": "authorization_code", "code_verifier": p["verifier"]})
        tok = json.loads(b or b"{}")
        if s != 200 or "refresh_token" not in tok:
            raise ValueError(f"Google lehnt die Anmeldung ab: {tok.get('error_description') or tok.get('error') or s}")
        tok["expires_at"] = time.time() + tok.get("expires_in", 3600) - 60
    else:
        s, b = http("POST", "https://open.tiktokapis.com/v2/oauth/token/", form={
            "client_key": p["client_id"], "client_secret": sec, "code": code, "grant_type": "authorization_code",
            "redirect_uri": REDIRECT, "code_verifier": p["verifier"]})
        tok = json.loads(b or b"{}")
        if s != 200 or "access_token" not in tok:
            raise ValueError(f"TikTok lehnt die Anmeldung ab: {tok.get('error_description') or tok.get('error') or s}")
        tok["expires_at"] = time.time() + tok.get("expires_in", 86400) - 120
    blob = encrypt(json.dumps(tok).encode(), derive_key("autoshorts", platform, sec))
    put_file(f"tokens/{platform}.enc", base64.b64encode(blob), f"App: {platform} verbunden")
    try:
        dispatch({"action": "stats"})
    except ValueError as e:
        log(f"Statistik-Auftrag nach Anmeldung: {e}", "warn")
    log(f"{platform} verbunden")
    return platform


# ───────────────────────── Updates (wie beim FVG Trader) ─────────────────────────
UPDATE = {"available": False, "version": None, "notes": "", "checked": None, "error": "", "busy": False}
SRV = None


def _vtuple(v):
    try:
        return tuple(int(x) for x in str(v).split("."))
    except ValueError:
        return (0,)


def _fetch(url, limit=10_000_000):
    url += ("&" if "?" in url else "?") + f"t={int(time.time())}"
    s, b = http("GET", url, headers={"Cache-Control": "no-cache"}, timeout=60)
    if s != 200:
        raise ValueError(f"Download fehlgeschlagen ({s})")
    return b[:limit]


def check_update():
    try:
        info = None
        m = re.match(r"^https://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/(.+)$", UPDATE_URL)
        if m:   # GitHub-API zuerst: raw.githubusercontent.com hält Dateien einige Minuten im Zwischenspeicher
            s, b = http("GET", f"https://api.github.com/repos/{m.group(1)}/{m.group(2)}/contents/{m.group(4)}?ref={m.group(3)}",
                        headers={"Accept": "application/vnd.github.raw"})
            if s == 200:
                info = json.loads(b.decode("utf-8"))
        if info is None:
            info = json.loads(_fetch(UPDATE_URL, 100_000).decode("utf-8"))
        newer = APP_VERSION != "dev" and _vtuple(info["version"]) > _vtuple(APP_VERSION)
        UPDATE.update(available=newer, version=info["version"], notes=info.get("notes", ""), error="",
                      checked=time.time(), file=urllib.parse.urljoin(UPDATE_URL, info["file"]), sha256=info["sha256"])
    except Exception as e:  # noqa: BLE001
        log(f"Update-Prüfung: {e}", "warn")
        UPDATE.update(error="Update-Server nicht erreichbar. Besteht eine Internetverbindung?", checked=time.time())
    return UPDATE


def _validate_build(data, sha=None):
    if sha and hashlib.sha256(data).hexdigest() != sha.lower():
        raise ValueError("Prüfsumme stimmt nicht. Das Update wurde nicht installiert.")
    text = data.decode("utf-8")
    m = re.search(r'^APP_VERSION = "([0-9.]+)"', text, re.M)
    if not m or "INDEX_HTML = " not in text or not text.startswith("0<0# : ^"):
        raise ValueError("Das ist keine gültige AutoShorts-Datei.")
    compile(text, "AutoShorts.cmd", "exec")
    return m.group(1)


def install_update(data, sha=None):
    if not LAUNCHER.lower().endswith(".cmd") or not os.path.exists(LAUNCHER):
        raise ValueError("Updates funktionieren nur mit der Ein-Datei-Version (AutoShorts.cmd).")
    new_version = _validate_build(data, sha)
    backup_dir = os.path.join(DATA, "backup")
    os.makedirs(backup_dir, exist_ok=True)
    with open(LAUNCHER, "rb") as f:
        old = f.read()
    with open(os.path.join(backup_dir, f"AutoShorts-{APP_VERSION}.cmd"), "wb") as f:
        f.write(old)
    tmp = LAUNCHER + ".neu"
    with open(tmp, "wb") as f:
        f.write(data)
    err = None
    for attempt in range(6):   # Virenscanner oder OneDrive halten die Datei manchmal kurz fest
        try:
            os.replace(tmp, LAUNCHER)
            err = None
            break
        except OSError as e:
            err = e
            try:   # zweiter Weg: alte Datei beiseite schieben, neue an ihren Platz
                old_path = LAUNCHER + ".alt"
                if os.path.exists(old_path):
                    os.remove(old_path)
                os.rename(LAUNCHER, old_path)
                os.rename(tmp, LAUNCHER)
                err = None
                break
            except OSError:
                time.sleep(1)
    if err is not None:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise ValueError(f"Windows lässt die App-Datei nicht ersetzen ({err.strerror or err}). "
                         "Lade AutoShorts einmal neu herunter und starte es – danach installiert es sich in einen eigenen Ordner, "
                         "in dem Updates immer funktionieren.") from err
    log(f"Update installiert: Version {APP_VERSION} → {new_version}. App startet neu.")
    threading.Timer(0.8, restart).start()
    return new_version


def restart():
    import subprocess
    try:
        if SRV:
            SRV.server_close()
        if sys.platform.startswith("win"):
            helper = os.path.join(DATA, "neustart.cmd")
            with open(helper, "w", encoding="ascii", errors="replace") as f:
                f.write("@echo off\r\nrem Startet AutoShorts nach einem Update neu\r\nping -n 3 127.0.0.1 >nul\r\n"
                        f'call "{LAUNCHER}" --hintergrund\r\n')
            flags = 0x08000000 | 0x00000200
            try:
                subprocess.Popen(["cmd.exe", "/c", helper], creationflags=flags | 0x01000000,
                                 cwd=os.path.dirname(LAUNCHER), close_fds=True)
            except OSError:
                subprocess.Popen(["cmd.exe", "/c", helper], creationflags=flags, cwd=os.path.dirname(LAUNCHER), close_fds=True)
        else:
            subprocess.Popen([sys.executable, LAUNCHER, "--hintergrund"], cwd=os.path.dirname(LAUNCHER),
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except Exception as e:  # noqa: BLE001
        print(f"Neustart fehlgeschlagen: {e}", flush=True)
    finally:
        os._exit(0)


def _download_install():
    for attempt in range(3):
        data = _fetch(UPDATE["file"])
        try:
            return install_update(data, UPDATE.get("sha256"))
        except ValueError as e:
            if "Prüfsumme" not in str(e) or attempt == 2:
                raise
            time.sleep(4)
            check_update()


def _update_loop():
    time.sleep(15)
    last = 0
    while True:
        if time.time() - last >= 3 * 3600:
            last = time.time()
            check_update()
        if SET.get("auto_update") and UPDATE.get("available") and not UPDATE.get("busy") and time.time() - LAST_UI > 120:
            UPDATE["busy"] = True   # nur wenn gerade niemand die App benutzt
            try:
                _download_install()
            except Exception as e:  # noqa: BLE001
                log(f"Automatisches Update fehlgeschlagen: {e}", "error")
            finally:
                UPDATE["busy"] = False
        time.sleep(300)


# ───────────────────────── Ruhezustand: ohne offenes Fenster beendet sich die App selbst ─────────────────────────
LAST_UI = time.time()
IDLE_EXIT = 45 * 60


def _idle_loop():
    while True:
        time.sleep(60)
        if time.time() - LAST_UI > IDLE_EXIT and not UPDATE.get("busy"):
            log("Kein Fenster mehr offen – AutoShorts beendet sich (die Videos macht weiter GitHub).")
            os._exit(0)


# ───────────────────────── Webserver ─────────────────────────
ROUTES = []


def route(method, pattern):
    def deco(fn):
        ROUTES.append((method, re.compile("^" + pattern + "$"), fn))
        return fn
    return deco


class Handler(BaseHTTPRequestHandler):
    server_version = "AutoShorts/1.0"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(data)

    def _json(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 2_000_000:
            raise ValueError("Anfrage zu groß")
        raw = self.rfile.read(n).decode("utf-8", "replace") if n else ""
        return json.loads(raw) if raw.strip() else {}

    def _dispatch(self, method):
        global LAST_UI
        host = (self.headers.get("Host") or "").split(":")[0]
        if host not in ("127.0.0.1", "localhost"):
            return self._send(403, {"error": "Nur lokal erreichbar"})
        path = self.path.split("?")[0]
        if path.startswith("/api/"):
            LAST_UI = time.time()
        # Schutz vor fremden Webseiten: jede Änderung braucht unseren Kopf-Eintrag (löst eine CORS-Vorabprüfung aus)
        if method == "POST" and self.headers.get("X-AS") != "1":
            return self._send(403, {"error": "Nicht erlaubt"})
        for m, rx, fn in ROUTES:
            mt = rx.match(path)
            if m == method and mt:
                try:
                    return fn(self, *mt.groups())
                except ValueError as e:
                    return self._send(400, {"error": str(e)})
                except Exception as e:  # noqa: BLE001
                    log(f"Fehler bei {path}: {e!r}", "error")
                    return self._send(500, {"error": f"Interner Fehler: {e}"})
        self._send(404, {"error": "Nicht gefunden"})

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")


def _index():
    if INDEX_HTML is not None:
        return INDEX_HTML
    with open(os.path.join(ROOT, "static", "index.html"), encoding="utf-8") as f:
        return f.read()


def _icon_svg():
    if ICON_SVG is not None:
        return ICON_SVG
    with open(os.path.join(ROOT, "..", "..", "docs", "icon.svg"), encoding="utf-8") as f:
        return f.read()


@route("GET", r"/")
def index(h):
    h._send(200, _index().encode(), "text/html; charset=utf-8")


@route("GET", r"/icon\.svg")
def icon_svg(h):
    h._send(200, _icon_svg().encode(), "image/svg+xml")


@route("GET", r"/icon-(192|512)\.png")
def icon(h, size):
    h._send(200, icon_png(int(size)), "image/png")


@route("GET", r"/manifest\.webmanifest")
def manifest(h):
    h._send(200, json.dumps(MANIFEST).encode(), "application/manifest+json")


@route("GET", r"/sw\.js")
def sw(h):
    h._send(200, SERVICE_WORKER.encode(), "text/javascript")


@route("GET", r"/api/version")
def version(h):
    h._send(200, {"app": "AutoShorts", "version": APP_VERSION, "pid": os.getpid(), "launcher": LAUNCHER})


@route("GET", r"/api/state")
def state(h):
    h._send(200, {
        "version": APP_VERSION, "platform": sys.platform, "launcher": LAUNCHER, "data": DATA,
        "connected": bool(SET.get("token")), "owner": SET["owner"], "repo": SET["repo"],
        "local_secrets": {k: bool(v) for k, v in SET.get("client_secrets", {}).items()},
        "auto_update": bool(SET.get("auto_update")), "update": UPDATE, "redirect": REDIRECT})


@route("POST", r"/api/github")
def github_connect(h):
    b = h._json()
    tok, owner, repo = (b.get("token") or "").strip(), (b.get("owner") or DEFAULT_OWNER).strip(), (b.get("repo") or DEFAULT_REPO).strip()
    if not tok:
        raise ValueError("Bitte den Zugangsschlüssel einfügen.")
    s, body = gh("GET", f"/repos/{owner}/{repo}", token=tok)
    if s == 401:
        raise ValueError("Der Zugangsschlüssel ist ungültig.")
    if s != 200:
        raise ValueError(f"Repository {owner}/{repo} nicht erreichbar ({s}). Ist der Schlüssel für dieses Repository freigegeben?")
    if not json.loads(body).get("permissions", {}).get("push"):
        raise ValueError("Der Schlüssel hat keine Schreibrechte (Contents: Read and write).")
    SET.update(token=tok, owner=owner, repo=repo)
    save_set()
    log(f"Mit GitHub verbunden: {owner}/{repo}")
    h._send(200, {"ok": True})


@route("POST", r"/api/github/logout")
def github_logout(h):
    SET["token"] = ""
    save_set()
    h._send(200, {"ok": True})


@route("POST", r"/api/gh")
def gh_proxy(h):
    """Zugriff der Oberfläche auf das eigene Repository (nur dieses Repository, nur mit Pfad darunter)."""
    b = h._json()
    path = str(b.get("path") or "")
    method = str(b.get("method") or "GET").upper()
    if not path.startswith("/") or ".." in path or method not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
        raise ValueError("Ungültiger Pfad")
    if path.startswith("/actions/secrets") and method != "GET":
        raise ValueError("Secrets bitte über die App-Funktion setzen")
    s, body = gh(method, repo_path(path), b.get("body"), raw=bool(b.get("raw")))
    txt = body.decode("utf-8", "replace") if body else ""
    try:
        data = json.loads(txt) if txt else None
    except ValueError:
        data = txt
    h._send(200, {"status": s, "data": data})


@route("POST", r"/api/secret")
def set_secret(h):
    b = h._json()
    name, value = str(b.get("name") or ""), str(b.get("value") or "").strip()
    if name not in SECRET_NAMES:
        raise ValueError("Unbekannter Schlüssel")
    if not value:
        raise ValueError("Bitte einen Wert eintragen.")
    pk = gh_json("GET", "/actions/secrets/public-key")
    enc = base64.b64encode(sealed_box(value.encode(), base64.b64decode(pk["key"]))).decode()
    gh_json("PUT", f"/actions/secrets/{name}", {"encrypted_value": enc, "key_id": pk["key_id"]})
    if name in LOCAL_SECRET:   # wird hier für die Anmeldung bei YouTube/TikTok gebraucht
        SET.setdefault("client_secrets", {})[LOCAL_SECRET[name]] = value
        save_set()
    log(f"Schlüssel gespeichert: {name}")
    h._send(200, {"ok": True})


@route("POST", r"/api/oauth/start")
def oauth_begin(h):
    b = h._json()
    h._send(200, {"url": oauth_start(b.get("platform"), b.get("client_id"))})


@route("GET", r"/oauth/?")
def oauth_cb(h):
    params = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(h.path).query))
    try:
        p = oauth_finish(params)
        title, msg, ok = ("YouTube" if p == "youtube" else "TikTok") + " verbunden", "Die App holt jetzt die ersten Zahlen. Du wirst gleich zurückgeleitet.", True
    except ValueError as e:
        title, msg, ok = "Verbinden fehlgeschlagen", str(e), False
    import html as _h
    page = f"""<!doctype html><html lang="de"><head><meta charset="utf-8"><title>AutoShorts</title>
<style>body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#efeef2;color:#121215;font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}}
.c{{background:#fff;border:1px solid #e8e7ed;border-radius:22px;padding:30px;max-width:420px;box-shadow:0 10px 30px -14px rgba(18,18,21,.2);display:flex;flex-direction:column;gap:10px}}
h1{{margin:0;font-size:22px;letter-spacing:-.02em;color:{'#13a052' if ok else '#e5484d'}}}p{{margin:0;color:#86858f}}a{{color:#121215;font-weight:600}}</style></head>
<body><div class="c"><h1>{_h.escape(title)}</h1><p>{_h.escape(msg)}</p><p><a href="/#einstellungen">Zurück zur App</a></p></div>
{'<script>setTimeout(()=>location.href="/#einstellungen",2500)</script>' if ok else ''}</body></html>"""
    h._send(200, page.encode(), "text/html; charset=utf-8")


@route("POST", r"/api/settings")
def app_settings(h):
    b = h._json()
    if "auto_update" in b:
        SET["auto_update"] = bool(b["auto_update"])
    save_set()
    h._send(200, {"ok": True})


@route("POST", r"/api/update/check")
def update_check(h):
    h._send(200, check_update())


@route("POST", r"/api/update/apply")
def update_apply(h):
    if not UPDATE.get("available"):
        check_update()
    if not UPDATE.get("available"):
        raise ValueError(UPDATE.get("error") or "Du hast bereits die neueste Version.")
    UPDATE["busy"] = True
    try:
        v = _download_install()
    finally:
        UPDATE["busy"] = False
    h._send(200, {"ok": True, "version": v})


@route("POST", r"/api/shortcut")
def shortcut(h):
    if not sys.platform.startswith("win"):
        raise ValueError("Desktop-Symbole gibt es nur unter Windows.")
    try:
        os.remove(os.path.join(DATA, "verknuepfung.txt"))
    except OSError:
        pass
    ensure_desktop_shortcut(LAUNCHER, DATA, log)
    h._send(200, {"ok": True})


@route("POST", r"/api/quit")
def quit_app(h):
    h._send(200, {"ok": True})
    threading.Timer(0.5, lambda: os._exit(0)).start()


@route("POST", r"/api/log")
def show_log(h):
    try:
        with open(LOG_FILE, encoding="utf-8") as f:
            txt = f.read()[-20000:]
    except OSError:
        txt = ""
    h._send(200, {"log": txt})


# ───────────────────────── Start ─────────────────────────
def _running():
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/version", timeout=2) as r:
            j = json.loads(r.read())
    except Exception:  # noqa: BLE001
        return None
    return j if j.get("app") == "AutoShorts" else {"version": "fremd"}


def _stop_other():
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}/api/quit", data=b"{}", method="POST",
                                     headers={"X-AS": "1", "Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=3).read()
    except Exception:  # noqa: BLE001
        pass
    time.sleep(1.5)


# ───────────────────────── Selbst-Installation (Windows) ─────────────────────────
# Die App kopiert sich beim ersten Start nach %LOCALAPPDATA%\AutoShorts. Dort sperrt kein Download-Ordner,
# OneDrive oder ZIP-Fenster die Datei, deshalb klappen Updates zuverlässig.
def install_dir():
    base = os.environ.get("LOCALAPPDATA")
    return os.path.join(base, "AutoShorts") if base else None


def self_install():
    """Gibt True zurück, wenn die installierte Kopie gestartet wurde und dieser Prozess enden soll."""
    if not sys.platform.startswith("win") or not LAUNCHER.lower().endswith(".cmd") or os.environ.get("AS_NO_INSTALL"):
        return False
    target_dir = install_dir()
    if not target_dir:
        return False
    target = os.path.join(target_dir, "AutoShorts.cmd")
    if os.path.normcase(os.path.abspath(LAUNCHER)) == os.path.normcase(os.path.abspath(target)):
        return False
    import shutil
    import subprocess
    try:
        os.makedirs(target_dir, exist_ok=True)
        with open(LAUNCHER, "rb") as f:
            mine = f.read()
        inst_ver = None
        if os.path.exists(target):
            with open(target, "rb") as f:
                m = re.search(rb'^APP_VERSION = "([0-9.]+)"', f.read(), re.M)
                inst_ver = m.group(1).decode() if m else None
        if inst_ver is None or _vtuple(APP_VERSION) >= _vtuple(inst_ver):
            tmp = target + ".neu"
            with open(tmp, "wb") as f:
                f.write(mine)
            os.replace(tmp, target)
        # Einstellungen vom alten Ort mitnehmen (Zugangsschlüssel, Client-Secrets)
        new_data = os.path.join(target_dir, "AutoShorts-Daten")
        old_set = os.path.join(DATA, "einstellungen.json")
        if os.path.exists(old_set) and not os.path.exists(os.path.join(new_data, "einstellungen.json")):
            os.makedirs(new_data, exist_ok=True)
            shutil.copy2(old_set, os.path.join(new_data, "einstellungen.json"))
        try:   # Desktop-Symbol soll ab jetzt auf die installierte Kopie zeigen
            os.remove(os.path.join(new_data, "verknuepfung.txt"))
        except OSError:
            pass
        env = dict(os.environ, AS_LAUNCHER=target, AS_DATA=new_data)
        args = [windowless_python(), target] + [a for a in sys.argv[1:]]
        subprocess.Popen(args, cwd=target_dir, env=env, close_fds=True, creationflags=0x00000008 | 0x00000200)
        print(f"AutoShorts wurde nach {target_dir} installiert und dort gestartet.", flush=True)
        return True
    except Exception as e:  # noqa: BLE001
        print(f"Installation in eigenen Ordner nicht möglich ({e}) – starte von hier.", flush=True)
        return False


def main():
    global SRV
    if self_install():
        return
    url = f"http://127.0.0.1:{PORT}"
    other = _running()
    if other and other.get("version") != "fremd":
        same_file = os.path.normcase(other.get("launcher") or "") == os.path.normcase(LAUNCHER)
        if same_file and not BACKGROUND and (_vtuple(other["version"]) >= _vtuple(APP_VERSION) or APP_VERSION == "dev"):
            print(f"AutoShorts {other['version']} läuft bereits, das Fenster wird geöffnet.", flush=True)
            open_app_window(url)
            return
        print(f"Andere AutoShorts-Instanz ({other.get('version')}, {other.get('launcher')}) wird beendet.", flush=True)
        _stop_other()
    srv = None
    for attempt in range(30):   # nach einem Update ist der Port kurz noch belegt
        try:
            srv = ThreadingHTTPServer((HOST, PORT), Handler)
            break
        except OSError:
            if attempt < 29:
                time.sleep(1)
    if srv is None:
        print(f"Port {PORT} ist belegt. Läuft AutoShorts schon? Dann einfach das Fenster nutzen.", flush=True)
        open_app_window(url)
        return
    SRV = srv
    log(f"AutoShorts {APP_VERSION} gestartet ({LAUNCHER})")
    print(f"\n  AutoShorts läuft:  {url}\n  Dieses Fenster darf geschlossen oder minimiert werden.\n", flush=True)
    if os.environ.get("AS_NO_BROWSER") != "1" and not BACKGROUND:
        threading.Timer(0.8, lambda: open_app_window(url)).start()
    threading.Thread(target=ensure_desktop_shortcut, args=(LAUNCHER, DATA, log), daemon=True).start()
    threading.Thread(target=_update_loop, daemon=True).start()
    threading.Thread(target=_idle_loop, daemon=True).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  Beendet.")


if __name__ == "__main__":
    main()
