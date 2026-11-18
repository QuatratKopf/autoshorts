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
from naclpure import decrypt, derive_key, encrypt, sealed_box  # noqa: E402
from appshell import MANIFEST, SERVICE_WORKER, ensure_desktop_shortcut, icon_png, open_app_window, windowless_python  # noqa: E402,E501

APP_VERSION = "dev"   # wird beim Bauen der Ein-Datei-Version gesetzt
EDITION = "admin"     # admin = alles einstellbar · lite = Kanal-App zum Weitergeben (nur das Nötigste); wird beim Bauen gesetzt
ROOT = os.path.dirname(os.path.abspath(__file__))
HOST = "127.0.0.1"
PORT = int(os.environ.get("AS_PORT", "8791"))
BACKGROUND = "--hintergrund" in sys.argv
LAUNCHER = os.environ.get("AS_LAUNCHER") or os.path.abspath(sys.argv[0])
DATA = os.environ.get("AS_DATA", os.path.join(ROOT, "data"))
os.makedirs(DATA, exist_ok=True)

DEFAULT_OWNER, DEFAULT_REPO = ("QuatratKopf", "autoshorts") if EDITION == "admin" else ("", "autoshorts")   # Kanal-App: eigene Kopie eintragen
UPDATE_URL = "https://raw.githubusercontent.com/QuatratKopf/autoshorts/main/" + ("version.json" if EDITION == "admin" else "version-lite.json")
REDIRECT = f"http://127.0.0.1:{PORT}/oauth/"
# Zugänge: Liste liegt im Repository des Admins (nur Prüfsummen der Codes, Ablaufdatum, Rechte) – die Kanal-App prüft dagegen
ACCESS_URL = "https://raw.githubusercontent.com/QuatratKopf/autoshorts/main/docs/admin/access.json"
UA = f"AutoShorts/{APP_VERSION}"
SECRET_NAMES = ["GEMINI_API_KEY", "CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN", "OPENAI_API_KEY",
                "ELEVENLABS_API_KEY", "GOOGLE_CLIENT_SECRET", "TIKTOK_CLIENT_SECRET", "ZERNIO_API_KEY"]
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


def _log_crash(kind, exc_type, exc, tb):
    import traceback
    log(f"{kind}: " + "".join(traceback.format_exception(exc_type, exc, tb))[-1500:], "error")


sys.excepthook = lambda t, e, tb: _log_crash("Absturz", t, e, tb)
threading.excepthook = lambda a: _log_crash(f"Absturz im Faden {a.thread.name if a.thread else ''}", a.exc_type, a.exc_value, a.exc_traceback)


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


def oauth_start(platform, client_id, mode="direct"):
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
    scopes = "user.info.basic,user.info.stats,video.list," + ("video.upload" if mode == "inbox" else "video.publish")
    q = {"client_key": client_id, "scope": scopes,
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


def access_hash(code):
    return hashlib.sha256(("autoshorts|" + str(code or "").strip().upper()).encode()).hexdigest()


ACCESS = {"at": 0, "res": None}


def check_access(code=None, force=False):
    """Kanal-App: Ist der Zugangscode (noch) gültig? Gibt {"ok", "reason", "name", "expires", "perms", "id"} zurück.
    Die Admin-App braucht keinen Code."""
    if EDITION == "admin":
        return {"ok": True, "admin": True}
    code = (code or SET.get("access_code") or "").strip()
    if not code:
        return {"ok": False, "reason": "code"}
    if not force and code == SET.get("access_code") and ACCESS["res"] and time.time() - ACCESS["at"] < 600:
        return ACCESS["res"]
    try:
        data = json.loads(_fetch(ACCESS_URL, 2_000_000).decode("utf-8"))
    except Exception:  # noqa: BLE001 – offline: ein zuletzt gültiger Zugang gilt noch 3 Tage weiter
        last = SET.get("access_last") or {}
        if code == SET.get("access_code") and last.get("ok") and time.time() - float(SET.get("access_last_at") or 0) < 3 * 86400 \
                and (not last.get("expires") or time.time() < float(last["expires"])):
            return last
        return {"ok": False, "reason": "offline"}
    h = access_hash(code)
    e = next((x for x in data.get("access", []) if isinstance(x, dict) and x.get("hash") == h), None)
    if not e:
        res = {"ok": False, "reason": "gelöscht"}
    elif e.get("expires") and time.time() > float(e["expires"]):
        res = {"ok": False, "reason": "abgelaufen", "name": e.get("name", ""), "expires": e.get("expires")}
    else:
        res = {"ok": True, "id": e.get("id"), "name": e.get("name", ""), "expires": e.get("expires"),
               "perms": {**(data.get("defaults") or {}), **(e.get("perms") or {})},
               "cats": [str(x) for x in e.get("cats") or [] if isinstance(x, str)][:60]}
    if code == SET.get("access_code"):
        ACCESS.update(at=time.time(), res=res)
        if res["ok"]:
            SET.update(access_last=res, access_last_at=time.time())
            save_set()
    return res


def _fetch(url, limit=10_000_000):
    url += ("&" if "?" in url else "?") + f"t={int(time.time())}"   # GitHub-Zwischenspeicher umgehen
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.read(limit + 1)[:limit]
    except Exception:
        import shutil
        import subprocess
        if shutil.which("curl"):   # z. B. fehlende Zertifikate bei Python auf dem Mac
            return subprocess.run(["curl", "-fsSL", "-H", "Cache-Control: no-cache", url], capture_output=True,
                                  check=True, timeout=90).stdout[:limit]
        raise


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
    ed = re.search(r'^EDITION = "(\w+)"', text, re.M)
    if ed and ed.group(1) != EDITION:
        raise ValueError("Diese Datei ist eine andere App-Ausgabe (Admin/Kanal-App) und wurde nicht installiert.")
    compile(text, "AutoShorts.cmd", "exec")
    return m.group(1)


def _probe_start(data):
    """Startet die neue App-Datei einmal mit --pruefen in einem eigenen Ordner. Nur wenn sie sauber hochfährt, wird installiert."""
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        fp = os.path.join(tmp, "probe.cmd")
        with open(fp, "wb") as f:
            f.write(data)
        env = {**os.environ, "AS_DATA": os.path.join(tmp, "daten"), "AS_PORT": "0", "AS_LAUNCHER": fp}
        try:
            r = subprocess.run([sys.executable, fp, "--pruefen"], capture_output=True, text=True, timeout=90, env=env,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except Exception as e:  # noqa: BLE001
            raise ValueError(f"Die neue Version ließ sich nicht probeweise starten ({e}). Das Update wurde nicht installiert.")
        if "AUTOSHORTS-OK" not in (r.stdout or ""):
            log(f"Update abgelehnt, Probestart fehlgeschlagen: {(r.stderr or r.stdout or '')[-500:]}", "error")
            raise ValueError("Die neue Version startet nicht – das Update wurde nicht installiert, deine App bleibt wie sie ist.")


def install_update(data, sha=None):
    if not LAUNCHER.lower().endswith(".cmd") or not os.path.exists(LAUNCHER):
        raise ValueError("Updates funktionieren nur mit der Ein-Datei-Version (AutoShorts.cmd). "
                         "Wurde die App direkt aus der ZIP gestartet? Dann bitte erst entpacken.")
    new_version = _validate_build(data, sha)
    _probe_start(data)                                # neue Version erst probeweise starten – startet sie nicht, bleibt die alte
    backup_dir = os.path.join(DATA, "backup")
    os.makedirs(backup_dir, exist_ok=True)
    with open(LAUNCHER, "rb") as f:
        old = f.read()
    with open(os.path.join(backup_dir, f"AutoShorts-{APP_VERSION}.cmd"), "wb") as f:
        f.write(old)
    tmp = LAUNCHER + ".neu"
    with open(tmp, "wb") as f:
        f.write(data)
    try:
        os.replace(tmp, LAUNCHER)
    except OSError as e:
        os.remove(tmp)
        log(f"Update: Datei konnte nicht ersetzt werden: {e}", "error")
        raise ValueError(f"Die App-Datei konnte nicht ersetzt werden ({e.strerror or e}). "
                         "Liegt sie in einem geschützten Ordner? Verschieb AutoShorts.cmd z. B. nach Dokumente und versuch es erneut.") from e
    log(f"Update installiert: Version {APP_VERSION} → {new_version}. App startet neu.")
    print(f"Update {APP_VERSION} -> {new_version}: Datei ersetzt, Neustart folgt", flush=True)
    t = threading.Timer(0.8, restart)
    t.daemon = False   # sonst beendet Python diesen Neustart-Faden, sobald der Hauptfaden endet
    t.start()
    return new_version


RESTART_FLAG = os.path.join(DATA, "neustart.txt")
RESTARTING = False


def _answers(timeout):
    """Wartet, bis auf dem App-Port wieder eine AutoShorts-Instanz antwortet."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    end = time.time() + timeout
    while time.time() < end:
        try:
            with opener.open(f"http://127.0.0.1:{PORT}/api/version", timeout=2) as r:
                if json.loads(r.read().decode()).get("app") == "AutoShorts":
                    return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(1)
    return False


def restart():
    """Startet AutoShorts neu und prüft, ob die neue Version wirklich antwortet. Klappt ein Weg nicht,
    wird der nächste versucht: 1) direkt mit demselben Python, 2) über den Windows-Explorer wie ein
    Doppelklick (unabhängig von diesem Prozess), 3) Prozess durch die neue Version ersetzen."""
    import subprocess
    global RESTARTING
    RESTARTING = True
    log("Neustart beginnt")
    try:
        if SRV:
            # erst den Webserver sauber anhalten, dann den Port freigeben (unter Windows reißt ein direktes
            # Schließen sonst den Hauptfaden mit Fehler ab und Python beendet den Neustart mittendrin)
            done = threading.Event()
            threading.Thread(target=lambda: (SRV.shutdown(), done.set()), daemon=True).start()
            done.wait(5)
            SRV.server_close()
        with open(RESTART_FLAG, "w", encoding="utf-8") as f:   # neue Instanz: kein zweites Fenster öffnen
            f.write(str(time.time()))
        exe = sys.executable
        win = sys.platform.startswith("win")
        if win and exe.lower().endswith("python.exe"):
            cand = os.path.join(os.path.dirname(exe), "pythonw.exe")
            exe = cand if os.path.exists(cand) else exe
        args = [exe, LAUNCHER, "--hintergrund"]
        cwd = os.path.dirname(LAUNCHER)
        env = dict(os.environ, AS_LAUNCHER=LAUNCHER, AS_DATA=DATA, AS_NO_BROWSER="1")

        def direct():
            if win:
                base = 0x00000008 | 0x00000200 | 0x08000000   # DETACHED_PROCESS | NEW_PROCESS_GROUP | NO_WINDOW
                try:
                    subprocess.Popen(args, cwd=cwd, env=env, close_fds=True, creationflags=base | 0x01000000)  # + BREAKAWAY_FROM_JOB
                except OSError:
                    subprocess.Popen(args, cwd=cwd, env=env, close_fds=True, creationflags=base)
            else:
                subprocess.Popen(args, cwd=cwd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

        def explorer():
            subprocess.Popen([os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "explorer.exe"), LAUNCHER], cwd=cwd)

        ways = [("direkt", direct)] + ([("Explorer", explorer)] if win else [])
        for name, start in ways:
            try:
                log(f"Neustart ({name}): {exe if name == 'direkt' else LAUNCHER}")
                start()
            except Exception as e:  # noqa: BLE001
                log(f"Neustart ({name}) nicht möglich: {e}", "warn")
                continue
            if _answers(25):
                log("Neustart erfolgreich")
                return
            log(f"Neustart ({name}): neue Version antwortet nicht, nächster Versuch", "warn")
        log("Neustart: ersetze den laufenden Prozess durch die neue Version", "warn")
        os.environ.update(env)
        os.execv(sys.executable, [sys.executable, LAUNCHER, "--hintergrund"])
    except Exception as e:  # noqa: BLE001
        log(f"Neustart fehlgeschlagen: {e}", "error")
    finally:
        os._exit(0)


def _download_install():
    """Neue Version laden und einspielen (mit Wiederholung, falls GitHub kurz eine alte Datei liefert)."""
    for attempt in range(3):
        data = _fetch(UPDATE["file"])
        try:
            return install_update(data, UPDATE.get("sha256"))
        except ValueError as e:
            if "Prüfsumme" not in str(e) or attempt == 2:
                raise
            log("Update: Prüfsumme passt noch nicht, lade erneut …", "warn")
            time.sleep(4)
            check_update()


# ───────────────────────── Backups (verschlüsselt, z. B. per Google-Apps-Script in Google Drive) ─────────────────────────
# Inhalt: die Einstellungen dieses PCs (GitHub-Schlüssel, Client-Secrets, Zugangscode …) und eine Kopie der Daten aus dem Repository.
# Verschlüsselt mit dem Backup-Passwort, BEVOR etwas die App verlässt – das Script und Google sehen nur unlesbare Bytes.
BACKUP_FIELDS = ("backup_url", "backup_secret", "backup_password", "backup_every", "backup_keep")
REPO_FILES = ("docs/data/config.json", "docs/data/videos.json", "docs/data/stats.json", "docs/data/state.json", "docs/data/shapes.json",
              "docs/data/wishes.json", "docs/data/plans.json", "docs/data/insights.json", "docs/admin/access.json")
BACKUP = {"busy": False}


def _backup_key(password):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), b"autoshorts-backup-v1", 200_000)


def make_backup(password):
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        mine = {k: v for k, v in SET.items() if k not in ("backup_password",)}   # das Passwort selbst nie mit hinein
        z.writestr("pc/einstellungen.json", json.dumps(mine, ensure_ascii=False, indent=1))
        for name in os.listdir(DATA):                     # weitere kleine Dateien dieses PCs (ohne Sicherungen alter App-Versionen)
            fp = os.path.join(DATA, name)
            if name != "einstellungen.json" and os.path.isfile(fp) and os.path.getsize(fp) < 2_000_000 and name.endswith((".json", ".txt", ".log")):
                z.write(fp, "pc/" + name)
        repo_ok = 0
        if SET.get("token"):
            for f in REPO_FILES:
                st, body = gh("GET", repo_path(f"/contents/{f}?ref=main"), raw=True)
                if st == 200 and body:
                    z.writestr("repo/" + f, body)
                    repo_ok += 1
        z.writestr("info.json", json.dumps({"app": "AutoShorts", "version": APP_VERSION, "edition": EDITION, "repo": f"{SET.get('owner')}/{SET.get('repo')}",
                                            "created": time.time(), "repo_files": repo_ok}, ensure_ascii=False))
    return encrypt(buf.getvalue(), _backup_key(password))


def backup_name():
    return time.strftime("AutoShorts-Backup-%Y-%m-%d-%H%M.asbak")


def _post_script(url, payload):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json", "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:   # Google Apps Script leitet nach dem Speichern weiter (wird automatisch gefolgt)
            code, txt = r.status, r.read(200_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        code, txt = e.code, e.read(2000).decode("utf-8", "replace")
    if code == 404:
        raise ValueError("Fehler 404 – Google findet unter diesem Link kein Script. Prüfe: 1) Es ist die Web-App-Adresse mit /exec am Ende "
                         "(nicht /dev), 2) Bereitstellen → Bereitstellungen verwalten → Web-App, Zugriff „Jeder“, 3) Nach Änderungen am Script "
                         "eine NEUE Version bereitstellen und den Link neu kopieren.")
    if code in (401, 403):
        raise ValueError(f"Fehler {code} – das Script verlangt eine Anmeldung. Bei der Bereitstellung als Web-App den Zugriff auf „Jeder“ stellen.")
    if code >= 400:
        raise ValueError(f"Der Backup-Link antwortet mit Fehler {code}.")
    try:
        js = json.loads(txt)
    except ValueError:
        js = None
    if not isinstance(js, dict):                      # z. B. Google-Anmeldeseite oder „Funktion doPost nicht gefunden“ – das ist KEIN Erfolg
        hint = "das Script verlangt eine Anmeldung (Zugriff auf „Jeder“ stellen)" if re.search(r"accounts\.google|ServiceLogin|signin", txt, re.I) \
            else "dem Script fehlt die Funktion doPost" if re.search(r"doPost", txt) else "kein {\"ok\": true} zurückgegeben"
        raise ValueError(f"Das Script hat nicht wie erwartet geantwortet: {hint}. Die Script-Vorlage macht es richtig.")
    if js.get("ok") is not True:
        raise ValueError("Das Backup-Script meldet: " + str(js.get("error") or "Fehler")[:200]
                         + (" – unter dem Link läuft nicht das AutoShorts-Script, sondern vermutlich das einer anderen App. Bitte ein eigenes "
                            "Apps-Script-Projekt mit der AutoShorts-Vorlage bereitstellen und dessen Link eintragen."
                            if re.search(r"dateiname|filename|name", str(js.get("error")), re.I) else ""))
    return js


def upload_backup(force=False):
    """Backup bauen und an den hinterlegten Link schicken. Gibt eine Meldung zurück; Fehler landen in SET["backup_error"]."""
    url, pw = (SET.get("backup_url") or "").strip(), SET.get("backup_password") or ""
    if not url or not pw:
        raise ValueError("Erst Backup-Link und Passwort eintragen.")
    if not url.lower().startswith("https://"):
        raise ValueError("Der Backup-Link muss mit https:// beginnen.")
    if BACKUP["busy"]:
        raise ValueError("Es läuft schon ein Backup.")
    BACKUP["busy"] = True
    try:
        blob = make_backup(pw)
        name = backup_name()
        _post_script(url, {"app": "AutoShorts", "action": "backup", "secret": SET.get("backup_secret") or "", "filename": name,
                           "mimeType": "application/octet-stream", "keep": int(SET.get("backup_keep") or 30),
                           "data": base64.b64encode(blob).decode()})
        SET.update(backup_last=time.time(), backup_error="", backup_last_name=name, backup_last_size=len(blob))
        save_set()
        log(f"Backup hochgeladen: {name} ({len(blob) // 1024} KB)")
        return f"Backup hochgeladen ({len(blob) // 1024} KB)"
    except Exception as e:
        SET.update(backup_error=str(e)[:300], backup_error_at=time.time())
        save_set()
        raise
    finally:
        BACKUP["busy"] = False


def _backup_loop():
    time.sleep(60)
    while True:
        try:
            every = {"daily": 86400, "weekly": 7 * 86400}.get(SET.get("backup_every") or "daily", 86400)
            failed_recently = time.time() - float(SET.get("backup_error_at") or 0) < 3600
            if SET.get("backup_url") and SET.get("backup_password") and SET.get("backup_every") != "off" and not failed_recently \
                    and time.time() - float(SET.get("backup_last") or 0) >= every:
                upload_backup()
        except Exception as e:  # noqa: BLE001
            log(f"Automatisches Backup fehlgeschlagen: {e}", "error")
        time.sleep(900)


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


def _window_open():
    """Windows: Ist noch ein AutoShorts-Fenster offen? Ein Fenster im Hintergrund (minimiert, getrennte
    Fernsitzung) wird vom Browser schlafen gelegt und meldet sich dann nicht mehr – offen ist es trotzdem."""
    if not sys.platform.startswith("win"):
        return False
    import subprocess
    ps = ("@(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(msedge|chrome)\\.exe$' -and "
          "$_.CommandLine -like '*--app=http://127.0.0.1:%d*' }).Count") % PORT
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True,
                             timeout=40, creationflags=0x08000000).stdout.strip()
        return out.isdigit() and int(out) > 0
    except Exception:  # noqa: BLE001
        return False


def _idle_loop():
    global LAST_UI
    while True:
        time.sleep(60)
        if time.time() - LAST_UI > IDLE_EXIT and not UPDATE.get("busy"):
            if _window_open():
                LAST_UI = time.time()   # Fenster ist noch da, nur eingeschlafen: weiterlaufen
                continue
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
    h._send(200, {"app": "AutoShorts", "version": APP_VERSION, "pid": os.getpid()})


@route("GET", r"/api/state")
def state(h):
    h._send(200, {
        "version": APP_VERSION, "edition": EDITION, "access": check_access(), "platform": sys.platform, "launcher": LAUNCHER, "data": DATA,
        "connected": bool(SET.get("token")), "owner": SET["owner"], "repo": SET["repo"],
        "local_secrets": {k: bool(v) for k, v in SET.get("client_secrets", {}).items()},
        "auto_update": bool(SET.get("auto_update")), "update": UPDATE, "redirect": REDIRECT})


@route("GET", r"/api/backup")
def backup_get(h):
    h._send(200, {"url": SET.get("backup_url") or "", "secret": bool(SET.get("backup_secret")), "password": bool(SET.get("backup_password")),
                  "every": SET.get("backup_every") or "daily", "keep": int(SET.get("backup_keep") or 30), "last": SET.get("backup_last"),
                  "last_name": SET.get("backup_last_name") or "", "last_size": SET.get("backup_last_size") or 0,
                  "error": SET.get("backup_error") or "", "busy": BACKUP["busy"]})


@route("POST", r"/api/backup")
def backup_set(h):
    b = h._json()
    url = str(b.get("url") or "").strip()
    if url and not re.match(r"^https://[^\s\"'<>]{8,2000}$", url):
        raise ValueError("Der Backup-Link muss eine https://-Adresse sein.")
    if re.search(r"script\.google\.com/.*/dev(\?|$)", url):
        raise ValueError("Das ist der Test-Link (/dev) – der funktioniert nur im eigenen Browser. Bitte die Web-App-Adresse mit /exec am Ende nehmen.")
    SET["backup_url"] = url
    if b.get("secret") is not None and str(b.get("secret")).strip():
        SET["backup_secret"] = str(b["secret"]).strip()[:200]
    if b.get("password") is not None and str(b.get("password")):
        if len(str(b["password"])) < 8:
            raise ValueError("Das Backup-Passwort braucht mindestens 8 Zeichen.")
        SET["backup_password"] = str(b["password"])
    if b.get("every") in ("daily", "weekly", "off"):
        SET["backup_every"] = b["every"]
    if b.get("keep") is not None:
        SET["backup_keep"] = max(3, min(365, int(b.get("keep") or 30)))
    save_set()
    h._send(200, {"ok": True})


@route("POST", r"/api/backup/test")
def backup_test(h):
    url = (SET.get("backup_url") or "").strip()
    if not url:
        raise ValueError("Erst den Backup-Link eintragen.")
    js = _post_script(url, {"app": "AutoShorts", "action": "ping", "secret": SET.get("backup_secret") or ""})
    if js.get("script") != "autoshorts-backup" and "folder" not in js:   # ein anderes Script antwortet zwar, aber nicht wie die Vorlage
        raise ValueError("Unter diesem Link antwortet ein anderes Script, nicht das AutoShorts-Backup-Script (vermutlich das einer anderen App). "
                         "Bitte ein NEUES Apps-Script-Projekt mit der AutoShorts-Vorlage anlegen, als Web-App bereitstellen und dessen /exec-Link eintragen.")
    SET.update(backup_error="")
    save_set()
    h._send(200, {"ok": True, "msg": "Verbindung klappt – das AutoShorts-Script antwortet. Jetzt „Jetzt sichern“ tippen."})


@route("POST", r"/api/backup/now")
def backup_now(h):
    h._send(200, {"ok": True, "msg": upload_backup(force=True)})


@route("POST", r"/api/backup/download")
def backup_download(h):
    pw = SET.get("backup_password") or ""
    if not pw:
        raise ValueError("Erst ein Backup-Passwort festlegen.")
    h._send(200, make_backup(pw), "application/octet-stream")


def restore_blob(data, pw, url=None, secret=None):
    """Backup entschlüsseln und die Einstellungen dieses PCs wiederherstellen. Die Repository-Daten liegen ohnehin auf GitHub;
    ihre Kopie im Backup ist für den Notfall."""
    import io
    import zipfile
    try:
        raw = decrypt(data, _backup_key(pw))
        z = zipfile.ZipFile(io.BytesIO(raw))
        mine = json.loads(z.read("pc/einstellungen.json").decode("utf-8"))
        info = json.loads(z.read("info.json").decode("utf-8"))
    except Exception:  # noqa: BLE001
        raise ValueError("Passwort falsch oder keine AutoShorts-Backup-Datei.")
    if not isinstance(mine, dict):
        raise ValueError("Backup-Datei beschädigt.")
    if info.get("edition") and info["edition"] != EDITION:
        raise ValueError("Dieses Backup stammt aus der anderen App (Admin/Kanal-App).")
    keep = {k: SET.get(k) for k in ("auto_update",)}
    SET.clear()
    SET.update(mine)
    SET.update({k: v for k, v in keep.items() if v is not None})
    SET["backup_password"] = pw
    if url:
        SET["backup_url"] = url
    if secret:
        SET["backup_secret"] = secret
    save_set()
    ACCESS.update(at=0, res=None)
    log(f"Backup wiederhergestellt ({info.get('repo')}, erstellt {time.strftime('%d.%m.%Y %H:%M', time.localtime(info.get('created') or 0))})")
    return {"ok": True, "repo": info.get("repo"), "created": info.get("created")}


@route("POST", r"/api/backup/restore")
def backup_restore(h):
    """Backup-Datei (roh im Körper) mit dem Passwort aus dem Kopf X-Backup-Password wiederherstellen."""
    n = int(h.headers.get("Content-Length") or 0)
    if n <= 0 or n > 100_000_000:
        raise ValueError("Die Backup-Datei ist leer oder zu groß.")
    pw = urllib.parse.unquote(h.headers.get("X-Backup-Password") or "")
    h._send(200, restore_blob(h.rfile.read(n), pw))


def _drive_args(b):
    url = str(b.get("url") or SET.get("backup_url") or "").strip()
    secret = str(b.get("secret") or SET.get("backup_secret") or "")
    if not re.match(r"^https://[^\s\"'<>]{8,2000}$", url):
        raise ValueError("Bitte den Backup-Link (https://…/exec) eintragen.")
    return url, secret


@route("POST", r"/api/backup/list")
def backup_list(h):
    """Backups im Google-Drive-Ordner auflisten (über das Script, mit Geheimwort)."""
    url, secret = _drive_args(h._json())
    js = _post_script(url, {"app": "AutoShorts", "action": "list", "secret": secret})
    items = [{"id": str(x.get("id") or "")[:200], "name": str(x.get("name") or "")[:120], "size": int(x.get("size") or 0),
              "date": str(x.get("date") or "")[:40]} for x in (js.get("files") or []) if isinstance(x, dict)][:200]
    h._send(200, {"ok": True, "files": items})


@route("POST", r"/api/backup/restore_drive")
def backup_restore_drive(h):
    """Ein Backup direkt aus Google Drive holen (über das Script) und wiederherstellen."""
    b = h._json()
    url, secret = _drive_args(b)
    fid, pw = str(b.get("id") or "").strip(), str(b.get("password") or "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{10,200}", fid):
        raise ValueError("Ungültige Backup-Auswahl.")
    if not pw:
        raise ValueError("Bitte das Backup-Passwort eingeben.")
    js = _post_script(url, {"app": "AutoShorts", "action": "get", "secret": secret, "id": fid})
    try:
        data = base64.b64decode(js.get("data") or "")
    except Exception:  # noqa: BLE001
        raise ValueError("Das Script hat kein lesbares Backup geliefert.")
    if not data or len(data) > 100_000_000:
        raise ValueError("Das Script hat kein Backup geliefert – ist die neueste Script-Vorlage bereitgestellt?")
    h._send(200, restore_blob(data, pw, url, secret))


@route("GET", r"/api/access")
def access_get(h):
    h._send(200, check_access(force=True))


@route("POST", r"/api/access")
def access_set(h):
    code = str(h._json().get("code") or "").strip()
    res = check_access(code, force=True)
    if res["ok"]:
        SET["access_code"] = code
        ACCESS.update(at=time.time(), res=res)
        SET.update(access_last=res, access_last_at=time.time())
        save_set()
        log(f"Zugang bestätigt: {res.get('name')}")
    h._send(200, res)


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
    # Ein falsch eingerichteter Schlüssel soll hier auffallen – nicht erst später, wenn die App schon „verbunden“ ist
    s2, _b = gh("GET", f"/repos/{owner}/{repo}/contents/docs/data/config.json?ref=main", token=tok)
    if s2 != 200:
        raise ValueError(f"In {owner}/{repo} liegt kein AutoShorts-Motor (docs/data/config.json fehlt). Ist das deine Kopie (Fork) von AutoShorts?")
    s3, _b = gh("GET", f"/repos/{owner}/{repo}/actions/workflows", token=tok)
    if s3 != 200:
        raise ValueError("Dem Schlüssel fehlt die Berechtigung „Actions: Read and write“. Bitte beim Schlüssel auf GitHub ergänzen.")
    s4, _b = gh("GET", f"/repos/{owner}/{repo}/actions/secrets/public-key", token=tok)
    if s4 != 200:
        raise ValueError("Dem Schlüssel fehlt die Berechtigung „Secrets: Read and write“. Bitte beim Schlüssel auf GitHub ergänzen.")
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
    if EDITION == "lite" and not check_access()["ok"]:
        raise ValueError("Dein Zugang ist nicht (mehr) gültig – bitte beim Admin melden.")
    s, body = gh(method, repo_path(path), b.get("body"), raw=bool(b.get("raw")))
    txt = body.decode("utf-8", "replace") if body else ""
    try:
        data = json.loads(txt) if txt else None
    except ValueError:
        data = txt
    h._send(200, {"status": s, "data": data})


_LIVE = {}
_LIVE_LOCK = threading.Lock()
WEB_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36",
          "Accept-Language": "de-DE,de;q=0.9"}


def _cached(key, ttl, fn):
    """Ergebnis höchstens alle ttl Sekunden neu holen; ein Fehler liefert den letzten guten Stand (falls vorhanden)."""
    hit = _LIVE.get(key)
    if hit and time.time() - hit["at"] < ttl:
        return hit
    bad = _LIVE.get("fail:" + key)
    if bad and not hit and time.time() - bad["at"] < max(600, ttl * 3):   # klappt gerade nicht: nicht jede Minute neu probieren
        raise ValueError(bad["msg"])
    try:
        out = {**fn(), "at": time.time()}
    except Exception as e:
        _LIVE["fail:" + key] = {"at": time.time(), "msg": str(e)[:200]}
        if hit:
            return {**hit, "stale": True}
        raise
    _LIVE[key] = out
    return out


def _clean_handle(h):
    return re.sub(r"[^A-Za-z0-9._-]", "", str(h or "").strip().lstrip("@"))[:60]


def _num_text(txt):
    """„1,23 Tsd. Abonnenten“, „12.345 Aufrufe“, „1.2M subscribers“ → Zahl."""
    m = re.search(r"([\d.,]+)\s*(tsd|mio|mrd|k|m|b)?\.?", str(txt or "").lower().replace("\xa0", " "))
    if not m:
        return 0
    raw, unit = m.group(1), m.group(2)
    if unit:
        v = float(raw.replace(",", ".")) if raw.count(",") + raw.count(".") <= 1 else float(raw.replace(".", "").replace(",", "."))
    else:
        v = float(re.sub(r"[.,]", "", raw) or 0)
    return int(v * {"tsd": 1e3, "k": 1e3, "mio": 1e6, "m": 1e6, "mrd": 1e9, "b": 1e9}.get(unit or "", 1))


def tt_profile(handle):
    st, body = http("GET", f"https://www.tiktok.com/@{handle}", headers=WEB_UA, timeout=20)
    txt = body.decode("utf-8", "replace") if body else ""
    m = re.search(r'"followerCount"\s*:\s*(\d+)', txt)
    if st != 200 or not m:
        raise ValueError("TikTok-Profil nicht lesbar" + (f" (HTTP {st})" if st != 200 else " – Name richtig?"))
    g = lambda k: int((re.search(r'"' + k + r'"\s*:\s*(\d+)', txt) or [0, 0])[1])   # noqa: E731
    return {"handle": handle, "followers": int(m.group(1)), "likes": g("heartCount"), "videos": g("videoCount")}


def tt_video(url):
    """Aufrufe/Likes eines TikTok-Videos von seiner öffentlichen Seite."""
    st, body = http("GET", url, headers=WEB_UA, timeout=20)
    txt = body.decode("utf-8", "replace") if body else ""
    m = re.search(r'"playCount"\s*:\s*(\d+)', txt)
    if st != 200 or not m:
        raise ValueError(f"TikTok-Video nicht lesbar ({st})")
    lk = re.search(r'"diggCount"\s*:\s*(\d+)', txt)
    return {"views": int(m.group(1)), "likes": int(lk.group(1)) if lk else 0}


# ── yt-dlp (für Video-Links und Zahlen-Listen): wird bei Bedarf einmal für diesen Benutzer installiert ──
_YTDLP = {"mod": None, "tried": 0.0, "busy": False}


def ytdlp(wait=False):
    """yt_dlp-Modul oder None. Fehlt es, wird es (höchstens einmal pro Stunde) per pip --user nachinstalliert."""
    if _YTDLP["mod"]:
        return _YTDLP["mod"]
    try:
        import yt_dlp
        _YTDLP["mod"] = yt_dlp
        return yt_dlp
    except ImportError:
        pass
    if _YTDLP["busy"] or time.time() - _YTDLP["tried"] < 3600:
        return None

    def install():
        import importlib
        import site
        import subprocess
        _YTDLP["busy"], _YTDLP["tried"] = True, time.time()
        try:
            exe = sys.executable
            if exe.lower().endswith("pythonw.exe") and os.path.exists(exe[:-5] + ".exe"):
                exe = exe[:-5] + ".exe"
            subprocess.run([exe, "-m", "pip", "install", "--user", "-q", "--disable-pip-version-check", "yt-dlp"], capture_output=True,
                           timeout=300, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            site.addsitedir(site.getusersitepackages())
            importlib.invalidate_caches()
            import yt_dlp
            _YTDLP["mod"] = yt_dlp
            log("yt-dlp installiert (für Video-Links und Live-Zahlen)")
        except Exception as e:  # noqa: BLE001
            log(f"yt-dlp nicht installierbar: {e}", "warn")
        finally:
            _YTDLP["busy"] = False
    if wait:
        install()
        return _YTDLP["mod"]
    threading.Thread(target=install, daemon=True).start()
    return None


def _flat_counts(url):
    """Alle Videos eines Profils/Kanals mit Aufrufen (yt-dlp-Liste ohne Herunterladen)."""
    y = ytdlp()
    if not y:
        raise ValueError("yt-dlp wird gerade eingerichtet")
    class Quiet:
        def debug(self, m): pass
        warning = info = error = debug
    with y.YoutubeDL({"quiet": True, "no_warnings": True, "logger": Quiet(), "extract_flat": "in_playlist", "playlistend": 200, "socket_timeout": 20}) as d:
        info = d.extract_info(url, download=False) or {}
    rows = [e for e in (info.get("entries") or []) if isinstance(e, dict)]
    views = [int(e.get("view_count") or 0) for e in rows]
    if not rows or not any(views):
        raise ValueError("keine Zahlen in der Liste")
    return {"views": sum(views), "likes": sum(int(e.get("like_count") or 0) for e in rows), "count": len(rows),
            "ids": {str(e.get("id")): int(e.get("view_count") or 0) for e in rows if e.get("id")}}


def live_tiktok_all(handle, urls):
    out = dict(_cached("tt:" + handle, 60, lambda: tt_profile(handle)))
    try:                                                  # Aufrufe: ganze Videoliste (yt-dlp), sonst die bekannten Video-Seiten
        fl = _cached("ttl:" + handle, 300, lambda: _flat_counts(f"https://www.tiktok.com/@{handle}"))
        out.update(views=fl["views"], views_src="profil")
    except Exception:  # noqa: BLE001
        vids = {}
        for u in urls[-15:]:
            try:
                vids[u] = _cached("ttv:" + u, 300, lambda u=u: tt_video(u))
            except Exception:  # noqa: BLE001
                pass
        if vids:
            out.update(videos_live={u: {"views": v["views"], "likes": v["likes"]} for u, v in vids.items()}, views_src="videos")
    return out


def _yt_token(cid):
    """Zugang zum eigenen YouTube-Kanal: Anmeldung aus tokens/youtube.enc (wie die Engine), Zugriffsschlüssel hier frisch geholt."""
    sec = SET.get("client_secrets", {}).get("youtube", "")
    if not sec or not cid:
        return None
    hit = _LIVE.get("ytok")
    if hit and time.time() < hit["exp"]:
        return hit["access"]
    st, body = gh("GET", repo_path("/contents/tokens/youtube.enc"), raw=True)
    if st != 200:
        return None
    tok = json.loads(decrypt(base64.b64decode(body), derive_key("autoshorts", "youtube", sec)))
    st, body = http("POST", "https://oauth2.googleapis.com/token", form={"client_id": cid, "client_secret": sec,
                                                                        "refresh_token": tok["refresh_token"], "grant_type": "refresh_token"})
    js = json.loads(body or b"{}")
    if st != 200 or "access_token" not in js:
        raise ValueError("YouTube-Anmeldung abgelaufen – bitte neu verbinden")
    _LIVE["ytok"] = {"access": js["access_token"], "exp": time.time() + int(js.get("expires_in", 3600)) - 120, "at": time.time()}
    return js["access_token"]


def yt_api_live(token, ids):
    h = {"Authorization": "Bearer " + token}
    st, body = http("GET", "https://www.googleapis.com/youtube/v3/channels?part=statistics,snippet&mine=true", headers=h, timeout=20)
    if st != 200:
        raise ValueError(f"YouTube meldet {st}")
    it = (json.loads(body).get("items") or [{}])[0]
    s_ = it.get("statistics", {})
    out = {"followers": int(s_.get("subscriberCount") or 0), "views": int(s_.get("viewCount") or 0), "videos": int(s_.get("videoCount") or 0),
           "name": it.get("snippet", {}).get("title", ""), "src": "api"}
    likes, vids = 0, {}
    for i in range(0, len(ids), 50):
        q = urllib.parse.urlencode({"part": "statistics", "id": ",".join(ids[i:i + 50])})
        st, body = http("GET", "https://www.googleapis.com/youtube/v3/videos?" + q, headers=h, timeout=20)
        if st == 200:
            for v in json.loads(body).get("items", []):
                x = v.get("statistics", {})
                vids[v["id"]] = {"views": int(x.get("viewCount") or 0), "likes": int(x.get("likeCount") or 0)}
                likes += vids[v["id"]]["likes"]
    out.update(likes=likes, videos_live=vids)
    return out


def yt_public(handle):
    """Öffentliche Kanal-Seite: Abonnenten, Aufrufe gesamt, Anzahl Videos (YouTube rundet Abonnenten selbst)."""
    st, body = http("GET", f"https://www.youtube.com/@{handle}/about?hl=de&gl=DE", headers=WEB_UA, timeout=20)
    txt = body.decode("utf-8", "replace") if body else ""
    if st != 200:
        raise ValueError(f"YouTube-Kanal nicht lesbar ({st})")
    f = lambda k: (re.search(r'"' + k + r'"\s*:\s*(?:\{"simpleText"\s*:\s*)?"([^"]{1,60})"', txt) or [0, ""])[1]   # noqa: E731
    subs = f("subscriberCountText") or (re.search(r'"content"\s*:\s*"([\d.,\s]+(?:Tsd\.|Mio\.)?\s*Abonnent(?:en|in))"', txt) or [0, ""])[1]
    if not subs:
        raise ValueError("YouTube-Kanal nicht gefunden – Name richtig?")
    return {"followers": _num_text(subs), "views": _num_text(f("viewCountText")), "videos": _num_text(f("videoCountText")),
            "name": (re.search(r'<meta property="og:title" content="([^"]{1,80})"', txt) or [0, "@" + handle])[1], "src": "public"}


def live_youtube_all(handle, cid, ids):
    try:
        token = _yt_token(cid)
    except Exception as e:  # noqa: BLE001
        log(f"Live-Zahlen YouTube: {e}", "warn")
        token = None
    if token:                                             # genau, mit Likes (3 Einheiten Kontingent pro Abruf, daher alle 2 Minuten)
        return _cached("yt:api", 120, lambda: yt_api_live(token, ids))
    if not handle:
        raise ValueError("YouTube nicht verbunden – Kanal-Namen in den Einstellungen eintragen")
    out = dict(_cached("yt:" + handle, 120, lambda: yt_public(handle)))
    try:                                                  # Likes/Aufrufe der Shorts aus der Kanal-Liste
        fl = _cached("ytl:" + handle, 300, lambda: _flat_counts(f"https://www.youtube.com/@{handle}/shorts"))
        out.setdefault("views", fl["views"])
        out["videos_live"] = {k: {"views": v} for k, v in fl["ids"].items()}
    except Exception:  # noqa: BLE001
        pass
    return out


@route("POST", r"/api/live")
def live_all(h):
    """Live-Zahlen beider Plattformen (läuft auf deinem PC; die App fragt jede Minute)."""
    b = h._json()
    tt, yt = _clean_handle(b.get("tt")), _clean_handle(b.get("yt"))
    ids = [str(x) for x in (b.get("yt_ids") or []) if re.fullmatch(r"[A-Za-z0-9_-]{6,20}", str(x))][:200]
    urls = [str(x) for x in (b.get("tt_urls") or []) if re.match(r"^https://(www\.)?tiktok\.com/@[\w.-]+/video/\d+", str(x))][:60]
    out, err = {}, {}
    with _LIVE_LOCK:
        if tt:
            try:
                out["tiktok"] = live_tiktok_all(tt, urls)
            except Exception as e:  # noqa: BLE001
                err["tiktok"] = str(e)
        try:
            out["youtube"] = live_youtube_all(yt, str(b.get("yt_cid") or ""), ids)
        except Exception as e:  # noqa: BLE001
            err["youtube"] = str(e)
    h._send(200, {**out, "errors": err, "at": time.time()})


@route("GET", r"/api/live/tiktok")
def live_tiktok(h):
    """Nur das TikTok-Profil (ältere App-Oberflächen)."""
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(h.path).query)
    handle = _clean_handle((q.get("u") or [""])[0])
    if not handle:
        raise ValueError("TikTok-Name fehlt")
    h._send(200, _cached("tt:" + handle, 60, lambda: tt_profile(handle)))


REMAKE_MAX = 300_000_000      # Vorlagen-Video höchstens 300 MB


def _inbox_release():
    """Release „inbox“ (Eingang für Vorlagen-Videos) holen oder anlegen; gibt seine ID zurück."""
    s_, b_ = gh("GET", repo_path("/releases/tags/inbox"))
    if s_ == 200:
        return json.loads(b_)["id"]
    rel = gh_json("POST", "/releases", {"tag_name": "inbox", "name": "Eingang: Videos zum Nachbauen", "prerelease": True,
                                        "body": "Hier landen Videos aus der App, die AutoShorts in eigenem Stil nachbauen soll. "
                                                "Sie werden nach dem Nachbauen gelöscht."})
    return rel["id"]


def _inbox_upload(data, ctype, ext):
    """Datei in das Release „inbox“ hochladen, gibt den Dateinamen zurück."""
    name = f"vorlage-{int(time.time())}.{ext}"
    rid = _inbox_release()
    hd = {"Accept": "application/vnd.github+json", "Authorization": "Bearer " + SET.get("token", ""), "Content-Type": ctype,
          "User-Agent": UA, "X-GitHub-Api-Version": "2022-11-28"}
    url = f"https://uploads.github.com/repos/{SET['owner']}/{SET['repo']}/releases/{rid}/assets?name={name}"
    req = urllib.request.Request(url, data=data, method="POST", headers=hd)
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            st = r.status
    except urllib.error.HTTPError as e:
        st = e.code
    if st not in (200, 201):
        raise ValueError(f"Hochladen zu GitHub fehlgeschlagen ({st}).")
    return name


LINK_RE = re.compile(r"^https?://(?:(?:www|m|vm|vt)\.)?(?:youtube\.com/(?:shorts/|watch\?v=)|youtu\.be/|tiktok\.com/)[^\s\"'<>]{1,300}$", re.I)


SONG_MAX = 30_000_000          # Lied für die Musik-Kugel höchstens 30 MB


def _songs_release():
    """Release „songs“ (eigene Lieder für die Musik-Kugel) holen oder anlegen; gibt seine ID zurück."""
    s_, b_ = gh("GET", repo_path("/releases/tags/songs"))
    if s_ == 200:
        return json.loads(b_)["id"]
    rel = gh_json("POST", "/releases", {"tag_name": "songs", "name": "Lieder für die Musik-Kugel", "prerelease": True,
                                        "body": "Eigene Lieder aus der App. Die Musik-Kugel nimmt jeweils das, das am längsten nicht dran war. "
                                                "Dateiname „Künstler - Titel.mp3“ = Auflösung am Ende des Videos."})
    return rel["id"]


@route("POST", r"/api/song")
def song_upload(h):
    """Lied für die Musik-Kugel annehmen und in das Release „songs“ legen (Datei roh im Körper, Name als ?name=)."""
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(h.path).query)
    n = int(h.headers.get("Content-Length") or 0)
    if n <= 0 or n > SONG_MAX:
        raise ValueError("Die Datei ist leer oder größer als 30 MB.")
    raw = (q.get("name") or ["lied.mp3"])[0]
    stem, _, ext = raw.rpartition(".")
    ext = ext.lower() if ext.lower() in ("mp3", "m4a", "wav", "ogg", "aac", "flac") else "mp3"
    stem = re.sub(r"[^A-Za-z0-9ÄÖÜäöüß() ._-]", "", stem or raw).strip(" ._-")[:90] or "Lied"
    name = re.sub(r"\s+", ".", stem) + "." + ext          # GitHub mag keine Leerzeichen im Dateinamen
    data = h.rfile.read(n)
    rid = _songs_release()
    hd = {"Accept": "application/vnd.github+json", "Authorization": "Bearer " + SET.get("token", ""),
          "Content-Type": h.headers.get("Content-Type") or "audio/mpeg", "User-Agent": UA, "X-GitHub-Api-Version": "2022-11-28"}
    url = f"https://uploads.github.com/repos/{SET['owner']}/{SET['repo']}/releases/{rid}/assets?name={urllib.parse.quote(name)}"
    req = urllib.request.Request(url, data=data, method="POST", headers=hd)
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            st = r.status
    except urllib.error.HTTPError as e:
        st = e.code
    if st == 422:
        raise ValueError("Ein Lied mit diesem Namen gibt es schon.")
    if st not in (200, 201):
        raise ValueError(f"Hochladen zu GitHub fehlgeschlagen ({st}).")
    log(f"Lied für die Musik-Kugel hochgeladen: {name}")
    h._send(200, {"ok": True, "name": name})


@route("POST", r"/api/remake/link")
def remake_link(h):
    """TikTok-/YouTube-Link nachbauen: hier auf dem PC herunterladen (klappt von zu Hause zuverlässiger als auf GitHub) und in den
    Eingang legen; geht das nicht, bekommt GitHub den Link und versucht es selbst."""
    b = h._json()
    url = str(b.get("url") or "").strip()
    m = re.search(r"https?://\S+", url)
    url = m.group(0).rstrip(").,;") if m else url        # aus geteiltem Text („Schau dir das an! https://vm.tiktok.com/…“)
    if not LINK_RE.match(url):
        raise ValueError("Bitte einen Link von TikTok oder YouTube einfügen.")
    cat = re.sub(r"[^a-z0-9_-]", "", str(b.get("category") or "").lower())[:40]
    upl = "1" if b.get("upload") else "0"
    name, how = url, "link"
    y = ytdlp(wait=True)
    if y:
        import tempfile
        tmp = tempfile.mkdtemp(prefix="as-vorlage-")
        try:
            opts = {"format": "b[ext=mp4][height<=720]/b[height<=720]/b[ext=mp4]/b", "outtmpl": os.path.join(tmp, "v.%(ext)s"),
                    "noplaylist": True, "quiet": True, "no_warnings": True, "max_filesize": REMAKE_MAX, "socket_timeout": 30}
            with y.YoutubeDL(opts) as d:
                info = d.extract_info(url, download=True)
                if (info.get("duration") or 0) > 600:
                    raise ValueError("Das Video ist länger als 10 Minuten.")
                path = d.prepare_filename(info)
            files = [os.path.join(tmp, f) for f in os.listdir(tmp)]
            path = path if os.path.exists(path) else (files[0] if files else "")
            if path and 0 < os.path.getsize(path) <= REMAKE_MAX:
                ext = path.rsplit(".", 1)[-1].lower()
                ext = ext if ext in ("mp4", "webm", "mov") else "mp4"
                with open(path, "rb") as f:
                    name = _inbox_upload(f.read(), {"webm": "video/webm", "mov": "video/quicktime"}.get(ext, "video/mp4"), ext)
                how = "datei"
        except ValueError:
            raise
        except Exception as e:  # noqa: BLE001
            log(f"Link nicht ladbar ({str(e)[:160]}) – GitHub versucht es selbst", "warn")
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)
    if b.get("queue"):                                   # nur einplanen: die App setzt den Eintrag in die Warteschlange
        log(f"Nachbau eingeplant ({'Video geladen' if how == 'datei' else 'nur Link'}): {url}")
        return h._send(200, {"ok": True, "how": how, "ref": name, "url": url})
    dispatch({"action": "remake", "video_id": name, "category": cat, "upload": upl})
    log(f"Nachbau gestartet ({'Video geladen' if how == 'datei' else 'nur Link'}): {url}")
    h._send(200, {"ok": True, "how": how})


@route("POST", r"/api/remake")
def remake_upload(h):
    """Video aus der App annehmen, in den Eingang hochladen und den Nachbau starten (Datei kommt roh im Körper der Anfrage)."""
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(h.path).query)
    n = int(h.headers.get("Content-Length") or 0)
    if n <= 0 or n > REMAKE_MAX:
        raise ValueError("Das Video ist leer oder größer als 300 MB.")
    ctype = (h.headers.get("Content-Type") or "video/mp4").split(";")[0].strip()
    if not ctype.startswith("video/"):
        raise ValueError("Bitte eine Videodatei wählen (MP4, MOV oder WebM).")
    data = h.rfile.read(n)
    ext = {"video/quicktime": "mov", "video/webm": "webm"}.get(ctype, "mp4")
    name = _inbox_upload(data, ctype, ext)
    cat = re.sub(r"[^a-z0-9_-]", "", (q.get("category") or [""])[0].lower())[:40]
    dispatch({"action": "remake", "video_id": name, "category": cat, "upload": "1" if (q.get("upload") or ["0"])[0] == "1" else "0"})
    log(f"Vorlage {name} hochgeladen ({n // 1_000_000} MB), Nachbau gestartet")
    h._send(200, {"ok": True, "name": name})


@route("POST", r"/api/secret")
def set_secret(h):
    b = h._json()
    name, value = str(b.get("name") or ""), str(b.get("value") or "").strip()
    if name not in SECRET_NAMES:
        raise ValueError("Unbekannter Schlüssel")
    if not value:
        raise ValueError("Bitte einen Wert eintragen.")
    try:
        pk = gh_json("GET", "/actions/secrets/public-key")
        enc = base64.b64encode(sealed_box(value.encode(), base64.b64decode(pk["key"]))).decode()
        gh_json("PUT", f"/actions/secrets/{name}", {"encrypted_value": enc, "key_id": pk["key_id"]})
    except ValueError as e:
        if "verweigert" in str(e):   # häufigster Fall: Schlüssel darf Secrets nur lesen
            raise ValueError("Der GitHub-Zugangsschlüssel darf keine Schlüssel speichern: bei „Secrets“ steht nur „Read-only“ (oder gar nichts). "
                             "Auf github.com → Settings → Developer settings → Fine-grained tokens den Schlüssel öffnen, bei „Secrets“ "
                             "„Read and write“ wählen, unten „Update“ – dann hier noch einmal speichern.") from None
        raise
    if name in LOCAL_SECRET:   # wird hier für die Anmeldung bei YouTube/TikTok gebraucht
        SET.setdefault("client_secrets", {})[LOCAL_SECRET[name]] = value
        save_set()
    log(f"Schlüssel gespeichert: {name}")
    h._send(200, {"ok": True})


@route("POST", r"/api/oauth/start")
def oauth_begin(h):
    b = h._json()
    h._send(200, {"url": oauth_start(b.get("platform"), b.get("client_id"), b.get("mode") or "direct")})


@route("GET", r"/oauth/?")
def oauth_cb(h):
    params = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(h.path).query))
    p = ""
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
<body><div class="c"><h1>{_h.escape(title)}</h1><p>{_h.escape(msg)}</p><p><a href="/#einstellungen" onclick="if(window.opener){{window.close();return false}}">Fenster schließen</a></p></div>
<script>
const res = {{as_oauth: true, ok: {'true' if ok else 'false'}, platform: {json.dumps(p if ok else "")}, title: {json.dumps(title)}, msg: {json.dumps(msg)}}};
if (window.opener && !window.opener.closed) {{
  try {{ window.opener.postMessage(res, location.origin); }} catch (e) {{}}
  setTimeout(() => window.close(), res.ok ? 1200 : 6000);
}} else if (res.ok) {{ setTimeout(() => location.href = "/#einstellungen", 2500); }}
</script></body></html>"""
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


@route("POST", r"/api/shutdown")
def shutdown(h):
    log("App beendet")
    h._send(200, {"ok": True})
    threading.Timer(0.6, lambda: os._exit(0)).start()


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
class AppServer(ThreadingHTTPServer):
    """Belegt den Port exklusiv. Unter Windows erlaubt Python sonst, dass mehrere Instanzen denselben Port teilen –
    dann laufen unbemerkt alte Versionen weiter."""
    daemon_threads = True
    allow_reuse_address = not sys.platform.startswith("win")

    def server_bind(self):
        import socket
        if sys.platform.startswith("win") and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def _running_version():
    """Fragt eine eventuell laufende Instanz nach ihrer Version. None = nichts läuft, "alt" = ältere Version ohne Abfrage."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f"http://127.0.0.1:{PORT}/api/version", timeout=2) as r:
            return json.loads(r.read()).get("version") or "alt"
    except urllib.error.HTTPError:
        return "alt"
    except Exception:  # noqa: BLE001
        return None


def _port_owners():
    """Windows: Prozess-IDs, die den App-Port belegen (netstat, unabhängig von der Systemsprache)."""
    import subprocess
    try:
        out = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True, errors="replace",
                             timeout=20, creationflags=0x08000000).stdout
    except Exception:  # noqa: BLE001
        return set()
    pids = set()
    for line in out.splitlines():
        t = line.split()
        if len(t) >= 5 and t[1].endswith(f":{PORT}") and t[2] in ("0.0.0.0:0", "[::]:0") and t[-1].isdigit():
            if int(t[-1]) not in (0, os.getpid()):
                pids.add(int(t[-1]))
    return pids


def _kill_port_owners():
    import subprocess
    killed = []
    for _ in range(5):
        pids = _port_owners()
        if not pids:
            break
        for pid in pids:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, timeout=20, creationflags=0x08000000)
            killed.append(str(pid))
        time.sleep(1)
    return killed


def _kill_other_instances():
    """Windows: alle anderen AutoShorts-Prozesse beenden (alte Versionen, andere Kopien der Datei)."""
    import subprocess
    if not sys.platform.startswith("win"):
        return []
    ps = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(python|pythonw|py|pyw)\\.exe$' -and "
          "$_.CommandLine -like '*AutoShorts*' -and $_.ProcessId -ne %d -and $_.ProcessId -ne %d } | "
          "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; $_.ProcessId }") % (os.getpid(), os.getppid())
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True,
                             timeout=40, creationflags=0x08000000).stdout
        return [x for x in out.split() if x.isdigit()]
    except Exception as e:  # noqa: BLE001
        print(f"Aufräumen alter Instanzen fehlgeschlagen: {e}", flush=True)
        return []


def main():
    global SRV
    if "--pruefen" in sys.argv:                       # Probestart: alles geladen, keine Fehler – sofort wieder beenden
        print(f"AUTOSHORTS-OK {APP_VERSION} {EDITION} {len(ROUTES)}", flush=True)
        return
    srv = None
    url = f"http://127.0.0.1:{PORT}"
    if sys.platform.startswith("win"):
        rv = _running_version()
        if rv and rv != "alt" and _vtuple(rv) >= _vtuple(APP_VERSION) and not BACKGROUND:
            print(f"AutoShorts {rv} läuft bereits, das Fenster wird geöffnet.", flush=True)
            open_app_window(url)
            return
        log(f"Start {APP_VERSION}{' (Neustart)' if BACKGROUND else ''}: laufende Instanz = {rv or 'keine'}")
        t0 = time.time()
        killed = _kill_port_owners() + _kill_other_instances()   # ältere oder hängende Instanzen ablösen
        log(f"Aufräumen fertig nach {time.time() - t0:.1f} s" + (f", beendet: {', '.join(sorted(set(killed)))}" if killed else ""))
        if killed:
            print(f"Ältere AutoShorts-Prozesse beendet: {', '.join(sorted(set(killed)))}", flush=True)
            time.sleep(1.5)
    for attempt in range(60):   # nach einem Update kann der Port noch kurz von der alten Version belegt sein
        try:
            srv = AppServer((HOST, PORT), Handler)
            break
        except OSError:
            if (BACKGROUND or (sys.platform.startswith("win") and attempt < 15)) and attempt < 59:
                time.sleep(1)
                continue
            srv = None
            break
    SRV = srv
    if srv is None:
        print("\n  AutoShorts läuft bereits, das Fenster wird geöffnet.\n")
        open_app_window(url)
        return
    log(f"AutoShorts {APP_VERSION} gestartet ({LAUNCHER})")
    print(f"\n  AutoShorts läuft:  {url}\n  Dieses Fenster darf geschlossen oder minimiert werden.\n", flush=True)
    restarted = False
    try:   # nach einem Update-Neustart (auch über den Explorer) kein zweites Fenster öffnen
        restarted = time.time() - os.path.getmtime(RESTART_FLAG) < 180
        os.remove(RESTART_FLAG)
    except OSError:
        pass
    if os.environ.get("AS_NO_BROWSER") != "1" and not BACKGROUND and not restarted:
        threading.Timer(1.0, lambda: open_app_window(url)).start()
    threading.Thread(target=ensure_desktop_shortcut, args=(LAUNCHER, DATA, log), daemon=True).start()
    threading.Thread(target=_update_loop, daemon=True).start()
    threading.Thread(target=_backup_loop, daemon=True).start()
    threading.Thread(target=_idle_loop, daemon=True).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  Beendet.")
    except Exception as e:  # noqa: BLE001
        if not RESTARTING:
            log(f"Webserver beendet: {e}", "error")
    while RESTARTING:   # der Neustart läuft in einem eigenen Faden und beendet den Prozess selbst
        time.sleep(1)


if __name__ == "__main__":
    main()
