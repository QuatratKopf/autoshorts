0<0# : ^
r'''
@echo off
title AutoShorts
cd /d "%~dp0"
set "AS_LAUNCHER=%~f0"
set "AS_DATA=%~dp0AutoShorts-Daten"
set "PYEXE="
set "PYARG="
for %%P in (py.exe) do if not "%%~$PATH:P"=="" set "PYEXE=%%~$PATH:P"
if defined PYEXE set "PYARG=-3"
if not defined PYEXE if exist "%LOCALAPPDATA%\Programs\Python\Launcher\py.exe" set "PYEXE=%LOCALAPPDATA%\Programs\Python\Launcher\py.exe"
if defined PYEXE if not defined PYARG set "PYARG=-3"
if not defined PYEXE for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if exist "%%D\python.exe" set "PYEXE=%%D\python.exe"
if not defined PYEXE (
  echo.
  echo   AutoShorts braucht Python. Es wird jetzt einmalig installiert, das dauert 1-2 Minuten ...
  echo.
  winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
  if exist "%LOCALAPPDATA%\Programs\Python\Launcher\py.exe" set "PYEXE=%LOCALAPPDATA%\Programs\Python\Launcher\py.exe"
  if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
)
if not defined PYEXE (
  echo.
  echo   Python konnte nicht automatisch installiert werden.
  echo   Bitte installiere Python von python.org ^(Haken bei "Add Python to PATH"^)
  echo   und oeffne danach diese Datei erneut.
  start "" "https://www.python.org/downloads/"
  pause
  exit /b 1
)
set "PYW="
if /i "%PYEXE:~-6%"=="py.exe" for %%I in ("%PYEXE%") do if exist "%%~dpIpyw.exe" set "PYW=%%~dpIpyw.exe"
if /i "%PYEXE:~-10%"=="python.exe" for %%I in ("%PYEXE%") do if exist "%%~dpIpythonw.exe" set "PYW=%%~dpIpythonw.exe"
if defined PYW (
  start "" "%PYW%" %PYARG% "%~f0" %*
  exit /b 0
)
echo.
echo   AutoShorts startet ... dieses Fenster bitte offen lassen.
echo.
"%PYEXE%" %PYARG% "%~f0" %*
if errorlevel 1 pause
exit /b 0
'''
# ─────────────────────────────────────────────────────────────────────────────
#  AutoShorts – die ganze App in einer Datei.
#  Windows: Doppelklick.   Mac/Linux: python3 AutoShorts.cmd
#  Einstellungen liegen im Ordner „AutoShorts-Daten“ neben dieser Datei.
#  Die Videos baut der Motor auf GitHub (github.com/QuatratKopf/autoshorts).
# ─────────────────────────────────────────────────────────────────────────────

# ═════════════════ naclpure.py ═════════════════
"""NaCl-kompatible Verschlüsselung in reinem Python (ohne Zusatzpakete).

- sealed_box(msg, public_key)      wie libsodium crypto_box_seal (für GitHub-Secrets)
- secretbox / secretbox_open        wie crypto_secretbox (für die gespeicherten Anmeldungen)

Langsam, aber für kurze Texte (Schlüssel, Tokens) mehr als schnell genug.
"""
import hashlib
import os
import struct

# ---------------------------------------------------------------- X25519 (RFC 7748)
_P = 2 ** 255 - 19
_A24 = 121665


def _clamp(k):
    k = bytearray(k)
    k[0] &= 248
    k[31] &= 127
    k[31] |= 64
    return int.from_bytes(k, "little")


def x25519(scalar: bytes, u: bytes) -> bytes:
    k = _clamp(scalar)
    x1 = int.from_bytes(u, "little") & ((1 << 255) - 1)
    x2, z2, x3, z3, swap = 1, 0, x1, 1, 0
    for t in reversed(range(255)):
        kt = (k >> t) & 1
        swap ^= kt
        if swap:
            x2, x3, z2, z3 = x3, x2, z3, z2
        swap = kt
        a, b = (x2 + z2) % _P, (x2 - z2) % _P
        aa, bb = a * a % _P, b * b % _P
        e = (aa - bb) % _P
        c, d = (x3 + z3) % _P, (x3 - z3) % _P
        da, cb = d * a % _P, c * b % _P
        x3 = (da + cb) ** 2 % _P
        z3 = x1 * (da - cb) ** 2 % _P
        x2 = aa * bb % _P
        z2 = e * (aa + _A24 * e) % _P
    if swap:
        x2, z2 = x3, z3
    return (x2 * pow(z2, _P - 2, _P) % _P).to_bytes(32, "little")


def x25519_base(scalar: bytes) -> bytes:
    return x25519(scalar, (9).to_bytes(32, "little"))


# ---------------------------------------------------------------- Salsa20 / HSalsa20 / XSalsa20

def _rotl(v, c):
    return ((v << c) & 0xFFFFFFFF) | (v >> (32 - c))


def _rounds(x):
    for _ in range(10):
        # Spalten
        x[4] ^= _rotl((x[0] + x[12]) & 0xFFFFFFFF, 7); x[8] ^= _rotl((x[4] + x[0]) & 0xFFFFFFFF, 9)
        x[12] ^= _rotl((x[8] + x[4]) & 0xFFFFFFFF, 13); x[0] ^= _rotl((x[12] + x[8]) & 0xFFFFFFFF, 18)
        x[9] ^= _rotl((x[5] + x[1]) & 0xFFFFFFFF, 7); x[13] ^= _rotl((x[9] + x[5]) & 0xFFFFFFFF, 9)
        x[1] ^= _rotl((x[13] + x[9]) & 0xFFFFFFFF, 13); x[5] ^= _rotl((x[1] + x[13]) & 0xFFFFFFFF, 18)
        x[14] ^= _rotl((x[10] + x[6]) & 0xFFFFFFFF, 7); x[2] ^= _rotl((x[14] + x[10]) & 0xFFFFFFFF, 9)
        x[6] ^= _rotl((x[2] + x[14]) & 0xFFFFFFFF, 13); x[10] ^= _rotl((x[6] + x[2]) & 0xFFFFFFFF, 18)
        x[3] ^= _rotl((x[15] + x[11]) & 0xFFFFFFFF, 7); x[7] ^= _rotl((x[3] + x[15]) & 0xFFFFFFFF, 9)
        x[11] ^= _rotl((x[7] + x[3]) & 0xFFFFFFFF, 13); x[15] ^= _rotl((x[11] + x[7]) & 0xFFFFFFFF, 18)
        # Zeilen
        x[1] ^= _rotl((x[0] + x[3]) & 0xFFFFFFFF, 7); x[2] ^= _rotl((x[1] + x[0]) & 0xFFFFFFFF, 9)
        x[3] ^= _rotl((x[2] + x[1]) & 0xFFFFFFFF, 13); x[0] ^= _rotl((x[3] + x[2]) & 0xFFFFFFFF, 18)
        x[6] ^= _rotl((x[5] + x[4]) & 0xFFFFFFFF, 7); x[7] ^= _rotl((x[6] + x[5]) & 0xFFFFFFFF, 9)
        x[4] ^= _rotl((x[7] + x[6]) & 0xFFFFFFFF, 13); x[5] ^= _rotl((x[4] + x[7]) & 0xFFFFFFFF, 18)
        x[11] ^= _rotl((x[10] + x[9]) & 0xFFFFFFFF, 7); x[8] ^= _rotl((x[11] + x[10]) & 0xFFFFFFFF, 9)
        x[9] ^= _rotl((x[8] + x[11]) & 0xFFFFFFFF, 13); x[10] ^= _rotl((x[9] + x[8]) & 0xFFFFFFFF, 18)
        x[12] ^= _rotl((x[15] + x[14]) & 0xFFFFFFFF, 7); x[13] ^= _rotl((x[12] + x[15]) & 0xFFFFFFFF, 9)
        x[14] ^= _rotl((x[13] + x[12]) & 0xFFFFFFFF, 13); x[15] ^= _rotl((x[14] + x[13]) & 0xFFFFFFFF, 18)
    return x


_SIGMA = struct.unpack("<4I", b"expand 32-byte k")


def _state(key, inp16):
    k = struct.unpack("<8I", key)
    n = struct.unpack("<4I", inp16)
    return [_SIGMA[0], k[0], k[1], k[2], k[3], _SIGMA[1], n[0], n[1], n[2], n[3], _SIGMA[2],
            k[4], k[5], k[6], k[7], _SIGMA[3]]


def hsalsa20(key: bytes, inp16: bytes) -> bytes:
    x = _rounds(_state(key, inp16))
    return struct.pack("<8I", x[0], x[5], x[10], x[15], x[6], x[7], x[8], x[9])


def _salsa20_block(key, nonce8, counter):
    s = _state(key, nonce8 + struct.pack("<Q", counter))
    x = _rounds(list(s))
    return struct.pack("<16I", *((x[i] + s[i]) & 0xFFFFFFFF for i in range(16)))


def xsalsa20_xor(msg: bytes, nonce24: bytes, key: bytes) -> bytes:
    subkey = hsalsa20(key, nonce24[:16])
    n8 = nonce24[16:24]
    out = bytearray(len(msg))
    for blk in range((len(msg) + 63) // 64):
        ks = _salsa20_block(subkey, n8, blk)
        off = blk * 64
        chunk = msg[off:off + 64]
        for i, b in enumerate(chunk):
            out[off + i] = b ^ ks[i]
    return bytes(out)


# ---------------------------------------------------------------- Poly1305

def poly1305(msg: bytes, key: bytes) -> bytes:
    r = int.from_bytes(key[:16], "little") & 0x0FFFFFFC0FFFFFFC0FFFFFFC0FFFFFFF
    s = int.from_bytes(key[16:32], "little")
    p = (1 << 130) - 5
    acc = 0
    for i in range(0, len(msg), 16):
        n = int.from_bytes(msg[i:i + 16] + b"\x01", "little")
        acc = (acc + n) * r % p
    return ((acc + s) & ((1 << 128) - 1)).to_bytes(16, "little")


# ---------------------------------------------------------------- secretbox (XSalsa20-Poly1305)

def secretbox(msg: bytes, nonce24: bytes, key: bytes) -> bytes:
    """Gibt MAC (16 Byte) + Geheimtext zurück, wie libsodium crypto_secretbox_easy."""
    stream = xsalsa20_xor(b"\x00" * 32 + msg, nonce24, key)
    ct = stream[32:]
    return poly1305(ct, stream[:32]) + ct


def secretbox_open(box: bytes, nonce24: bytes, key: bytes) -> bytes:
    mac, ct = box[:16], box[16:]
    otk = xsalsa20_xor(b"\x00" * 32, nonce24, key)
    if not _eq(poly1305(ct, otk), mac):
        raise ValueError("Entschlüsselung fehlgeschlagen")
    return xsalsa20_xor(b"\x00" * 32 + ct, nonce24, key)[32:]


def _eq(a, b):
    if len(a) != len(b):
        return False
    r = 0
    for x, y in zip(a, b):
        r |= x ^ y
    return r == 0


# ---------------------------------------------------------------- box / sealed box

def box_beforenm(public_key: bytes, secret_key: bytes) -> bytes:
    return hsalsa20(x25519(secret_key, public_key), b"\x00" * 16)


def sealed_box(msg: bytes, public_key: bytes) -> bytes:
    """crypto_box_seal: ephemeral_pk || box(msg) mit nonce = blake2b(epk || pk, 24)."""
    esk = os.urandom(32)
    epk = x25519_base(esk)
    nonce = hashlib.blake2b(epk + public_key, digest_size=24).digest()
    return epk + secretbox(msg, nonce, box_beforenm(public_key, esk))


# ---------------------------------------------------------------- einfache Ver-/Entschlüsselung mit Passwort-Ableitung

def derive_key(*parts: str) -> bytes:
    return hashlib.sha256(":".join(parts).encode()).digest()


def encrypt(data: bytes, key: bytes) -> bytes:
    nonce = os.urandom(24)
    return b"AS1" + nonce + secretbox(data, nonce, key)


def decrypt(blob: bytes, key: bytes) -> bytes:
    if not blob.startswith(b"AS1"):
        raise ValueError("Unbekanntes Format")
    return secretbox_open(blob[27:], blob[3:27], key)

# ═════════════════ appshell.py ═════════════════
"""Damit AutoShorts sich wie eine App anfühlt: eigenes Fenster, Icon, Desktop-Verknüpfung."""
import os
import shutil
import struct
import subprocess
import sys
import webbrowser
import zlib

ICON_PNG = {}   # wird beim Bauen mit den PNG-Daten (base64) gefüllt; in der Entwicklung aus docs/ gelesen


def icon_png(size=512):
    """App-Icon als PNG (192, 256 oder 512 Pixel)."""
    import base64
    key = 192 if size <= 192 else (256 if size <= 256 else 512)
    if key in ICON_PNG:
        return base64.b64decode(ICON_PNG[key])
    here = os.path.dirname(os.path.abspath(__file__))
    for p in (os.path.join(here, "..", "..", "docs", f"icon-{key}.png"),):
        if os.path.exists(p):
            with open(p, "rb") as f:
                return f.read()
    return b""


def write_ico(path):
    png = icon_png(256)
    header = struct.pack("<HHH", 0, 1, 1) + struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(png), 22)
    with open(path, "wb") as f:
        f.write(header + png)


MANIFEST = {
    "name": "AutoShorts",
    "short_name": "AutoShorts",
    "start_url": "/",
    "scope": "/",
    "display": "standalone",
    "background_color": "#10131b",
    "theme_color": "#efeef2",
    "icons": [
        {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"},
    ],
}

SERVICE_WORKER = """// Macht AutoShorts installierbar. Es wird nichts zwischengespeichert.
self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', e => e.respondWith(fetch(e.request)));
"""


# ───────────────────────── App-Fenster öffnen ─────────────────────────
def _app_browser():
    if sys.platform.startswith("win"):
        for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
            for rel in (r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe"):
                if base and os.path.exists(os.path.join(base, rel)):
                    return os.path.join(base, rel)
    elif sys.platform == "darwin":
        for p in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                  "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                  "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"):
            if os.path.exists(p):
                return p
    else:
        for name in ("google-chrome", "chromium", "chromium-browser", "microsoft-edge"):
            if shutil.which(name):
                return shutil.which(name)
    return None


def open_app_window(url):
    exe = _app_browser()
    if exe:
        try:
            subprocess.Popen([exe, f"--app={url}", "--window-size=1320,900"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except OSError:
            pass
    webbrowser.open(url)


# ───────────────────────── Verknüpfungen (Windows) ─────────────────────────
def windowless_python():
    """pythonw.exe startet Python ohne Konsolenfenster."""
    exe = sys.executable
    cand = os.path.join(os.path.dirname(exe), "pythonw.exe")
    return cand if os.path.exists(cand) else exe


def make_shortcuts(paths, launcher, icon, args=""):
    ps = (
        "$w = New-Object -ComObject WScript.Shell;"
        "foreach ($p in ($env:AS_SC_PATHS -split '\\|')) {"
        "  $s = $w.CreateShortcut($p);"
        "  $s.TargetPath = $env:AS_SC_TARGET; $s.Arguments = $env:AS_SC_ARGS;"
        "  $s.WorkingDirectory = $env:AS_SC_DIR; $s.IconLocation = $env:AS_SC_ICON;"
        "  $s.Description = 'AutoShorts'; $s.Save() }"
    )
    env = dict(os.environ, AS_SC_PATHS="|".join(paths), AS_SC_TARGET=windowless_python(),
               AS_SC_ARGS=f'"{launcher}" {args}'.strip(), AS_SC_DIR=os.path.dirname(launcher), AS_SC_ICON=icon)
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                   env=env, check=True, timeout=30, creationflags=0x08000000,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _folders():
    ps = "[Environment]::GetFolderPath('Desktop'); [Environment]::GetFolderPath('Programs'); [Environment]::GetFolderPath('Startup')"
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True,
                         timeout=30, creationflags=0x08000000).stdout.split("\n")
    return [o.strip() for o in out if o.strip()]


def icon_file(data_dir):
    ico = os.path.join(data_dir, "AutoShorts.ico")
    if not os.path.exists(ico):
        write_ico(ico)
    return ico


def ensure_desktop_shortcut(launcher, data_dir, log):
    """Legt „AutoShorts“ auf Desktop und im Startmenü an und richtet es neu aus, sobald eine andere Datei läuft.
    So zeigt das Symbol nie auf eine alte Kopie (z. B. „AutoShorts (1).cmd“ in Downloads)."""
    if not sys.platform.startswith("win"):
        return
    flag = os.path.join(data_dir, "verknuepfung.txt")
    try:
        desktop, programs = _folders()[:2]
        try:
            with open(flag, encoding="utf-8") as f:
                same = f.read().strip() == launcher
        except OSError:
            same = False
        if same and os.path.exists(os.path.join(desktop, "AutoShorts.lnk")):
            return   # Symbol vorhanden und zeigt auf diese Datei
        make_shortcuts([os.path.join(desktop, "AutoShorts.lnk"), os.path.join(programs, "AutoShorts.lnk")],
                       launcher, icon_file(data_dir))
        with open(flag, "w", encoding="utf-8") as f:
            f.write(launcher)
        log(f"Desktop-Symbol zeigt auf: {launcher}")
    except Exception as e:  # noqa: BLE001
        log(f"Desktop-Symbol konnte nicht angelegt werden: {e}", "warn")


def autostart_enabled():
    return False

ICON_PNG.update({192: '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', 256: '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', 512: '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'})

# ═════════════════ server.py ═════════════════
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





APP_VERSION = "1.1.3"   # wird beim Bauen der Ein-Datei-Version gesetzt
ROOT = os.path.dirname(os.path.abspath(__file__))
HOST = "127.0.0.1"
PORT = int(os.environ.get("AS_PORT", "8791"))
BACKGROUND = "--hintergrund" in sys.argv
LAUNCHER = os.environ.get("AS_LAUNCHER") or os.path.abspath(sys.argv[0])
DATA = os.environ.get("AS_DATA", os.path.join(os.path.dirname(os.path.abspath(__file__)), "AutoShorts-Daten"))
os.makedirs(DATA, exist_ok=True)

DEFAULT_OWNER, DEFAULT_REPO = "QuatratKopf", "autoshorts"
UPDATE_URL = "https://raw.githubusercontent.com/QuatratKopf/autoshorts/main/version.json"
REDIRECT = f"http://127.0.0.1:{PORT}/oauth/"
UA = f"AutoShorts/{APP_VERSION}"
SECRET_NAMES = ["GEMINI_API_KEY", "CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN", "OPENAI_API_KEY",
                "ELEVENLABS_API_KEY", "GOOGLE_CLIENT_SECRET", "TIKTOK_CLIENT_SECRET"]
LOCAL_SECRET = {"GOOGLE_CLIENT_SECRET": "youtube", "TIKTOK_CLIENT_SECRET": "tiktok"}

INDEX_HTML = '<!doctype html>\n<html lang="de">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>AutoShorts</title>\n<link rel="manifest" href="/manifest.webmanifest">\n<meta name="theme-color" content="#efeef2">\n<script>try{var t=localStorage.getItem("as-theme");if(t==="dark")document.documentElement.dataset.theme="dark";}catch(e){}</script>\n<link rel="icon" href="/icon.svg" type="image/svg+xml">\n<link rel="apple-touch-icon" href="/icon-192.png">\n<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" media="print" onload="this.media=\'all\'">\n<style>\n/* Stil wie FVG Trader 3.0: hell & minimal, Pill-Navigation, weiche Karten, Verlauf-Akzent, Dunkelmodus */\n:root{\n  --bg:#efeef2; --surface:#ffffff; --raise:#f7f7f9; --sunk:#f2f1f5; --line:#e8e7ed; --line2:#dad9e1; --fg:#121215; --muted:#86858f;\n  --ink:#121215; --ink-fg:#ffffff;\n  --accent:#f0562b; --accent2:#ff8a4c; --accent-fg:#fff; --pos:#13a052; --neg:#e5484d; --warn:#d97a06; --fill:rgba(240,86,43,.10);\n  --pos-bg:rgba(19,160,82,.09); --neg-bg:rgba(229,72,77,.09); --warn-bg:rgba(217,122,6,.11);\n  --grad:linear-gradient(135deg,#ff8a4c 0%,#f0562b 55%,#e1401f 100%);\n  --shadow:0 1px 2px rgba(18,18,21,.04),0 10px 30px -14px rgba(18,18,21,.12);\n  --shadow-h:0 2px 4px rgba(18,18,21,.05),0 22px 44px -18px rgba(18,18,21,.22);\n  --glass:rgba(255,255,255,.86);\n  --yt:#f0562b; --tt:#121215;\n  --r:22px; --r-s:14px; --ease:cubic-bezier(.22,.8,.24,1);\n  --f-body:"Inter",system-ui,-apple-system,"Segoe UI",sans-serif;\n  --f-code:"JetBrains Mono",ui-monospace,Menlo,Consolas,monospace;\n  color-scheme:light;\n}\n:root[data-theme=dark]{\n  --bg:#0b0b0d; --surface:#161618; --raise:#1c1c1f; --sunk:#121214; --line:#242428; --line2:#323238; --fg:#f2f2f4; --muted:#8c8c95;\n  --ink:#f2f2f4; --ink-fg:#111113;\n  --accent:#ff6a3d; --accent2:#ff9a5c; --pos:#3cc97f; --neg:#ff6369; --warn:#f5a524; --fill:rgba(255,106,61,.13);\n  --pos-bg:rgba(60,201,127,.11); --neg-bg:rgba(255,99,105,.11); --warn-bg:rgba(245,165,36,.12);\n  --shadow:0 1px 2px rgba(0,0,0,.3),0 12px 30px -16px rgba(0,0,0,.6);\n  --shadow-h:0 2px 4px rgba(0,0,0,.35),0 24px 48px -18px rgba(0,0,0,.75);\n  --glass:rgba(22,22,24,.88);\n  --yt:#ff6a3d; --tt:#f2f2f4;\n  color-scheme:dark;\n}\n*{box-sizing:border-box}\n[hidden]{display:none!important}\nhtml,body{margin:0}\nhtml{background:var(--bg)}\nbody{background:var(--bg);color:var(--fg);font:14px/1.5 var(--f-body);letter-spacing:-.006em;-webkit-font-smoothing:antialiased;transition:background-color .4s var(--ease)}\n.wrap{max-width:1320px;margin:0 auto;padding:0 max(16px,env(safe-area-inset-left,0px)) 0 max(16px,env(safe-area-inset-right,0px))}\nbutton{font:inherit;cursor:pointer;color:inherit}\na{color:inherit}\n.mono,td{font-variant-numeric:tabular-nums}\ncode,.code{font-family:var(--f-code)}\n::selection{background:color-mix(in srgb,var(--accent) 25%,transparent)}\n::-webkit-scrollbar{width:10px;height:10px} ::-webkit-scrollbar-thumb{background:var(--line2);border-radius:6px;border:2px solid var(--bg)} ::-webkit-scrollbar-track{background:transparent}\n.pos{color:var(--pos)} .neg{color:var(--neg)} .muted{color:var(--muted)} .warn{color:var(--warn)}\nbutton:focus-visible,a:focus-visible,summary:focus-visible{outline:2px solid var(--accent);outline-offset:2px}\n\n/* ── Kopfzeile ── */\n.top{position:sticky;top:0;z-index:20;background:color-mix(in srgb,var(--bg) 78%,transparent);backdrop-filter:saturate(1.4) blur(16px);-webkit-backdrop-filter:saturate(1.4) blur(16px)}\n.bar{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:16px;padding-block:14px}\n.brand{display:flex;align-items:center;gap:10px;font:700 15.5px var(--f-body);letter-spacing:-.02em}\n.brand img{width:34px;height:34px;border-radius:11px;box-shadow:0 6px 16px -6px rgba(47,91,211,.6)}\n.nav{position:relative;display:flex;gap:2px;padding:5px;background:var(--surface);border-radius:999px;box-shadow:var(--shadow);border:1px solid var(--line)}\n.nav-ind{position:absolute;top:5px;bottom:5px;left:0;width:0;border-radius:999px;background:var(--ink);transition:left .45s var(--ease),width .45s var(--ease),opacity .2s;pointer-events:none;z-index:0;opacity:0}\n.nav button{position:relative;z-index:1;display:flex;align-items:center;gap:7px;padding:8px 15px;border:0;border-radius:999px;background:transparent;color:var(--muted);font:500 13.5px var(--f-body);letter-spacing:-.01em;white-space:nowrap;transition:color .3s var(--ease)}\n.nav button svg{display:none;width:18px;height:18px}\n.nav button:hover{color:var(--fg)}\n.nav button[aria-current=true]{color:var(--ink-fg);font-weight:600}\n.nav button em{display:none}\n.bar-r{display:flex;align-items:center;gap:10px;justify-content:flex-end}\n.icgrp{display:flex;align-items:center;gap:2px;padding:5px;background:var(--surface);border:1px solid var(--line);border-radius:999px;box-shadow:var(--shadow)}\n.ib{width:34px;height:34px;border-radius:50%;border:0;background:transparent;color:var(--fg);display:grid;place-items:center;padding:0;position:relative;transition:background .2s,transform .2s var(--ease)}\n.ib:hover{background:var(--sunk)} .ib:active{transform:scale(.92)}\n.ib svg{width:18px;height:18px}\n.ib .dot{position:absolute;top:7px;right:7px;width:7px;height:7px;box-shadow:0 0 0 2px var(--surface)}\n\n/* ── Seitenkopf ── */\n.phead{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap;padding:18px 0 4px}\n.phead h1{margin:0;font:600 clamp(26px,3.4vw,40px)/1.1 var(--f-body);letter-spacing:-.035em}\n.phead h1 .w{display:inline-block;white-space:pre;animation:word .8s var(--ease) both;animation-delay:calc(var(--w,0)*80ms)}\n.phead p{margin:6px 0 0;color:var(--muted);font-size:14px}\n.status{display:flex;gap:6px;flex-wrap:wrap;align-items:center;justify-content:flex-end}\n.pill{display:inline-flex;align-items:center;gap:6px;background:var(--surface);border:1px solid var(--line);border-radius:999px;font-size:12px;padding:5px 11px;color:var(--fg);box-shadow:var(--shadow);white-space:nowrap}\n.dot{width:7px;height:7px;border-radius:50%;background:var(--line2);display:inline-block}\n.dot.ok{background:var(--pos);box-shadow:0 0 0 3px var(--pos-bg)} .dot.bad{background:var(--neg);box-shadow:0 0 0 3px var(--neg-bg)} .dot.warn{background:var(--warn);box-shadow:0 0 0 3px var(--warn-bg)}\n.banner{border-radius:var(--r-s);padding:12px 16px;background:var(--warn-bg);color:var(--fg);border:1px solid color-mix(in srgb,var(--warn) 25%,transparent);margin:12px 0 0;display:flex;gap:10px;align-items:center;flex-wrap:wrap}\n.banner.run{background:var(--surface);border-color:var(--line);box-shadow:var(--shadow)}\n.banner.ok{background:var(--pos-bg);border-color:color-mix(in srgb,var(--pos) 25%,transparent)}\n.banner.bad{background:var(--neg-bg);border-color:color-mix(in srgb,var(--neg) 25%,transparent)}\n.banner a{font-weight:600}\n.spin{width:15px;height:15px;border:2px solid var(--accent);border-top-color:transparent;border-radius:50%;animation:spin 1s linear infinite;flex:none}\n@keyframes spin{to{transform:rotate(360deg)}}\nmain{display:flex;flex-direction:column;gap:20px;padding-top:20px;padding-bottom:60px}\n\n/* ── Grundbausteine ── */\nh2{font:600 16.5px/1.3 var(--f-body);letter-spacing:-.02em;margin:0}\nh3{letter-spacing:-.01em}\n.hint{color:var(--muted);font-size:12.5px;margin:0}\n.section-h{display:flex;align-items:baseline;justify-content:space-between;gap:10px;flex-wrap:wrap}\n.panel{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);box-shadow:var(--shadow);padding:20px 22px;min-width:0;display:flex;flex-direction:column;gap:12px;transition:transform .5s var(--ease),box-shadow .5s var(--ease)}\n.lift:hover{transform:translateY(-4px);box-shadow:var(--shadow-h)}\n.empty{color:var(--muted);font-size:13px;padding:18px;border:1.5px dashed var(--line2);border-radius:var(--r-s);text-align:center}\n.btn{border-radius:999px;padding:8px 16px;font:500 13px var(--f-body);background:var(--surface);color:var(--fg);border:1px solid var(--line2);transition:transform .2s var(--ease),background .2s,border-color .2s,box-shadow .2s;white-space:nowrap;text-decoration:none;display:inline-flex;align-items:center;justify-content:center;gap:7px}\n.btn:hover:not(:disabled){border-color:var(--fg)}\n.btn:active:not(:disabled){transform:scale(.96)}\n.btn:disabled{opacity:.5;cursor:default}\n.btn svg{width:16px;height:16px}\n.btn.primary{background:var(--ink);border-color:var(--ink);color:var(--ink-fg);font-weight:600}\n.btn.primary:hover:not(:disabled){box-shadow:0 8px 20px -8px color-mix(in srgb,var(--ink) 60%,transparent)}\n.btn.accent{background:var(--grad);border:0;color:#fff;font-weight:600;box-shadow:0 8px 20px -10px rgba(240,86,43,.8)}\n.btn.danger{background:var(--neg-bg);color:var(--neg);border-color:transparent}\n.btn.danger:hover{background:var(--neg)!important;color:#fff;border-color:var(--neg)!important}\n.btn.sm{padding:5px 11px;font-size:12px}\ninput,select,textarea{font:inherit;color:var(--fg);background:var(--raise);border:1px solid var(--line2);border-radius:12px;padding:8px 12px;min-width:0;transition:border-color .2s,box-shadow .2s;width:100%}\ntextarea{resize:vertical;min-height:70px;font-size:13px}\ninput:focus,select:focus,textarea:focus{outline:0;border-color:var(--fg);box-shadow:0 0 0 4px color-mix(in srgb,var(--fg) 8%,transparent)}\ninput[type=checkbox],input[type=radio]{width:auto;accent-color:var(--ink)}\n.chip{display:inline-block;border-radius:999px;padding:3px 9px;font-size:11.5px;font-weight:600;background:var(--sunk);color:var(--fg);white-space:nowrap;text-decoration:none}\n.chip.good{background:var(--pos-bg);color:var(--pos)} .chip.bad{background:var(--neg-bg);color:var(--neg)} .chip.warn{background:var(--warn-bg);color:var(--warn)} .chip.mute{background:var(--sunk);color:var(--muted)} .chip.acc{background:var(--fill);color:var(--accent)}\n.seg{display:inline-flex;background:var(--sunk);border-radius:999px;padding:3px;gap:2px}\n.seg button{border:0;border-radius:999px;padding:6px 13px;font:500 12.5px var(--f-body);color:var(--muted);background:transparent;transition:background .3s var(--ease),color .3s}\n.seg button[aria-pressed="true"]{background:var(--surface);color:var(--fg);box-shadow:0 1px 3px rgba(0,0,0,.08);font-weight:600}\n.scroll{overflow-x:auto}\ntable{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}\nth{font-size:11px;font-weight:500;color:var(--muted);text-align:right;padding:7px 8px;border-bottom:1px solid var(--line);white-space:nowrap}\ntd{font-size:13px;text-align:right;padding:8px;border-bottom:1px solid var(--line);white-space:nowrap}\nth.t,td.t{text-align:left}\ntd.w{white-space:normal}\ntr:last-child td{border-bottom:0}\ntbody tr{transition:background .2s} tbody tr:hover td{background:var(--raise)}\n.grid2{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:20px}\n.grid3{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(0,1fr);gap:20px}\n@media (max-width:900px){.grid2,.grid3{grid-template-columns:1fr}}\nsvg{display:block;width:100%;height:auto}\nsvg text{fill:var(--muted);font-family:var(--f-body);font-size:11px}\n.gl{stroke:var(--line)}\n.legend{display:flex;gap:14px;flex-wrap:wrap;align-items:center;font-size:11.5px;color:var(--muted)}\n.legend i{width:10px;height:10px;border-radius:3px;display:inline-block;margin-right:6px;vertical-align:-1px}\n\n/* ── Dashboard-Hero ── */\n.hero{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(0,1.1fr) minmax(0,1.15fr);gap:18px}\n.hero-card{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);box-shadow:var(--shadow);padding:20px 22px;display:flex;flex-direction:column;gap:14px;min-width:0;transition:transform .5s var(--ease),box-shadow .5s var(--ease)}\n.hero-card:hover{transform:translateY(-4px);box-shadow:var(--shadow-h)}\n.hc-top{display:flex;justify-content:space-between;align-items:center;gap:10px}\n.hc-top span{font-size:13.5px;font-weight:500}\n.hc-top small{font-size:12px;color:var(--muted)}\n.bal{font:600 clamp(30px,3.2vw,40px)/1.05 var(--f-body);letter-spacing:-.04em;font-variant-numeric:tabular-nums;white-space:nowrap}\n.delta{display:inline-flex;align-items:center;gap:6px;font-size:12px;color:var(--muted)}\n.delta b{font-size:11.5px;padding:2px 8px;border-radius:999px;font-weight:600}\n.delta b.pos{background:var(--pos-bg)} .delta b.neg{background:var(--neg-bg)} .delta b.zero{background:var(--sunk);color:var(--muted)}\n.hb-act{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:auto}\n.hb-act .btn{padding:12px 14px;font-weight:600}\n.wal{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;background:var(--raise);border-radius:var(--r-s);padding:8px;border:1px solid var(--line)}\n.wal>div{background:var(--surface);border-radius:11px;padding:9px 11px;display:flex;flex-direction:column;gap:2px;min-width:0;box-shadow:0 1px 2px rgba(0,0,0,.04)}\n.wal span{font-size:11.5px;color:var(--muted);display:flex;align-items:center;gap:6px}\n.wal span i{width:8px;height:8px;border-radius:50%}\n.wal b{font-size:15px;font-weight:600;letter-spacing:-.02em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-variant-numeric:tabular-nums}\n.tiles{display:grid;grid-template-columns:1fr 1fr;gap:12px}\n.tile{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);box-shadow:var(--shadow);padding:16px 18px;display:flex;flex-direction:column;gap:6px;min-width:0;transition:transform .5s var(--ease),box-shadow .5s var(--ease)}\n.tile:hover{transform:translateY(-4px);box-shadow:var(--shadow-h)}\n.tile-h{display:flex;justify-content:space-between;align-items:center;font-size:12.5px;color:var(--muted)}\n.tile-h i{width:28px;height:28px;border-radius:50%;display:grid;place-items:center;background:var(--sunk);color:var(--fg)}\n.tile-h i svg{width:14px;height:14px}\n.tile b{font:600 clamp(24px,2.4vw,30px)/1.1 var(--f-body);letter-spacing:-.035em;font-variant-numeric:tabular-nums;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:auto}\n.tile small{font-size:11.5px;color:var(--muted);display:flex;align-items:center;gap:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}\n.tile small em{font-style:normal;font-weight:600;font-size:11px;padding:1px 7px;border-radius:999px;background:var(--sunk);color:var(--fg)}\n.tile.hot{background:var(--grad);border:0;color:#fff;box-shadow:0 18px 36px -18px rgba(240,86,43,.85);position:relative;overflow:hidden}\n.tile.hot::after{content:"";position:absolute;inset:0;background:radial-gradient(120% 80% at 100% 0%,rgba(255,255,255,.28),transparent 55%);pointer-events:none}\n.tile.hot .tile-h,.tile.hot small{color:rgba(255,255,255,.85)}\n.tile.hot .tile-h i{background:rgba(255,255,255,.2);color:#fff}\n.tile.hot small em{background:rgba(255,255,255,.22);color:#fff}\n.bars-box{flex:1;display:flex;flex-direction:column;gap:8px;background:var(--raise);border:1px solid var(--line);border-radius:var(--r-s);padding:12px 12px 8px;min-height:190px}\n.bars-h{display:flex;justify-content:space-between;align-items:center;font-size:12px;color:var(--muted)}\n.bars-h b{color:var(--fg);font-weight:600;font-size:13px}\n.bars{flex:1;display:grid;grid-auto-flow:column;grid-auto-columns:minmax(0,1fr);gap:6px;align-items:stretch;min-height:130px;position:relative}\n.bars .col{position:relative;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;gap:5px;min-width:0}\n.bars .stk{position:relative;width:min(100%,26px);flex:1;display:flex;flex-direction:column;justify-content:flex-end}\n.bars .s1,.bars .s2{border-radius:7px;transform-origin:bottom;animation:growUp .9s var(--ease) both;animation-delay:calc(var(--k,0)*45ms + .15s)}\n.bars .s1{background:var(--ink)}\n.bars .s2{background:repeating-linear-gradient(-45deg,var(--accent) 0 3px,color-mix(in srgb,var(--accent) 55%,transparent) 3px 6px);margin-top:2px}\n.bars .col.ph .stk{border-radius:7px;background:repeating-linear-gradient(0deg,transparent 0 6px,var(--line) 6px 7px);opacity:.6}\n.bars .col small{font-size:10px;color:var(--muted);white-space:nowrap}\n.bars .tip{position:absolute;bottom:calc(100% + 4px);left:50%;transform:translate(-50%,4px);background:var(--ink);color:var(--ink-fg);font-size:11px;padding:4px 8px;border-radius:8px;white-space:nowrap;opacity:0;pointer-events:none;transition:opacity .2s,transform .25s var(--ease);z-index:3}\n.bars .col:hover .tip{opacity:1;transform:translate(-50%,0)}\n.bars .col:nth-last-child(-n+3) .tip{left:auto;right:0;transform:translate(0,4px)} .bars .col:nth-last-child(-n+3):hover .tip{transform:translate(0,0)}\n.bars .col:nth-child(-n+3) .tip{left:0;transform:translate(0,4px)} .bars .col:nth-child(-n+3):hover .tip{transform:translate(0,0)}\n@keyframes growUp{from{transform:scaleY(0)}}\n@media (max-width:1180px){ .hero{grid-template-columns:1fr 1fr} .hero .hero-card:last-child{grid-column:1/-1} }\n@media (max-width:720px){ .hero{grid-template-columns:1fr} .hero .hero-card:last-child{grid-column:auto} }\n.hbars{display:flex;flex-direction:column;gap:12px}\n.hbar{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr) auto;gap:12px;align-items:center}\n.hbar-l{display:flex;flex-direction:column;gap:1px;min-width:0}\n.hbar-l b{font-weight:600;font-size:13.5px} .hbar-l small{font-size:11.5px;color:var(--muted)}\n.hbar-t{height:10px;border-radius:999px;background:var(--sunk);overflow:hidden}\n.hbar-t i{display:block;height:100%;border-radius:999px;background:var(--ink);transform-origin:left;animation:growX .9s var(--ease) both}\n.hbar:first-child .hbar-t i{background:var(--grad)}\n@keyframes growX{from{transform:scaleX(0)}}\n.hbar>span{font-size:13px;font-weight:600;text-align:right;min-width:64px}\n.thumb{width:36px;height:64px;border-radius:8px;object-fit:cover;display:block;flex:none;background:var(--sunk)}\n.vrow{display:flex;gap:12px;align-items:center;min-width:0}\n.vrow .tt{display:flex;flex-direction:column;gap:4px;min-width:0}\n.vrow .tt b{font-weight:600;white-space:normal}\n.vrow .tt div{display:flex;gap:4px;flex-wrap:wrap}\n.runs{display:flex;flex-direction:column}\n.runs div{display:grid;grid-template-columns:18px minmax(0,1fr) auto;gap:10px;align-items:center;padding:8px 0;border-bottom:1px solid var(--line);font-size:13px}\n.runs div:last-child{border-bottom:0}\n\n/* ── Kalender ── */\n.cal-top{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}\n.cal-mon{display:flex;align-items:center;gap:6px}\n.cal-mon h2{font-size:22px;font-weight:600;letter-spacing:-.02em;margin:0 8px 0 2px}\n.ibtn{width:34px;height:34px;display:grid;place-items:center;border:1px solid var(--line2);border-radius:50%;background:var(--surface);color:var(--fg);padding:0;transition:border-color .2s,transform .2s var(--ease)}\n.ibtn:hover{border-color:var(--fg)} .ibtn:active{transform:scale(.92)}\n.ibtn svg{width:16px;height:16px}\n.strip{display:grid;grid-template-columns:1.4fr repeat(4,minmax(0,1fr));background:var(--surface);border:1px solid var(--line);border-radius:var(--r);box-shadow:var(--shadow);overflow:hidden}\n.strip>div{padding:14px 18px;display:flex;flex-direction:column;gap:4px;min-width:0;border-left:1px solid var(--line)}\n.strip>div:first-child{border-left:0}\n.strip .l{font-size:11px;color:var(--muted);font-weight:500}\n.strip .v{font-size:19px;font-weight:600;letter-spacing:-.02em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-variant-numeric:tabular-nums}\n.strip .big{font-size:28px;letter-spacing:-.03em}\n.strip .s{font-size:11.5px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}\n@media (max-width:820px){ .strip{grid-template-columns:repeat(2,minmax(0,1fr))} .strip>div{border-left:0;border-top:1px solid var(--line)} .strip>div:first-child{grid-column:1/-1;border-top:0} .strip>div:nth-child(odd):not(:first-child){border-left:1px solid var(--line)} }\n.calbox{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);box-shadow:var(--shadow);padding:10px;overflow:hidden}\n.cal{display:grid;grid-template-columns:repeat(7,minmax(0,1fr)) minmax(0,1.05fr);gap:6px}\n.cal .dow{font-size:11px;color:var(--muted);font-weight:500;padding:8px 10px 2px}\n.day{position:relative;min-height:100px;border:1px solid var(--line);border-radius:14px;background:var(--raise);padding:9px 11px;display:flex;flex-direction:column;gap:2px;text-align:left;font:inherit;color:inherit;min-width:0;cursor:pointer;transition:transform .35s var(--ease),box-shadow .35s var(--ease),border-color .2s}\n.day:hover{transform:translateY(-3px);box-shadow:var(--shadow-h)}\n.day.heat{background:linear-gradient(180deg,color-mix(in srgb,var(--accent) calc(var(--h,0)*28%),transparent),transparent);border-color:color-mix(in srgb,var(--accent) calc(var(--h,0)*45%),var(--line))}\n.day.out{background:transparent;border-color:transparent;opacity:.35;cursor:default;pointer-events:none}\n.day.fut{opacity:.55}\n.day.sel{border-color:var(--ink)!important;box-shadow:0 0 0 1px var(--ink),var(--shadow-h)}\n.day .dn{font-size:12px;color:var(--muted);font-weight:500;display:flex;align-items:center;gap:6px;font-variant-numeric:tabular-nums}\n.day.today .dn b{background:var(--ink);color:var(--ink-fg);border-radius:999px;padding:0 7px;font-weight:600}\n.day .dn b{font-weight:500}\n.day .pl{font-size:17px;font-weight:600;letter-spacing:-.02em;font-variant-numeric:tabular-nums;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:auto}\n.day .pl small{font-size:11px;font-weight:500;color:var(--muted);margin-left:3px}\n.day .meta{font-size:11px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:flex;gap:6px;align-items:center}\n.vdots{display:flex;gap:3px}\n.vdots i{width:7px;height:7px;border-radius:50%;background:var(--accent)}\n.wk{border-radius:14px;border:1px dashed var(--line2);padding:9px 11px;display:flex;flex-direction:column;gap:2px;min-height:100px;min-width:0}\n.wk .dn{font-size:11px;color:var(--muted);font-weight:500}\n.wk .pl{font-size:17px;font-weight:600;letter-spacing:-.02em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:auto;font-variant-numeric:tabular-nums}\n.wk .meta{font-size:11px;color:var(--muted)}\n@media (max-width:760px){\n  .calbox{padding:5px} .cal{gap:3px;grid-template-columns:repeat(7,minmax(0,1fr))} .wk,.cal .dow.wkh{display:none}\n  .day{min-height:58px;padding:5px;border-radius:9px} .day .pl{font-size:11px;letter-spacing:-.03em} .day .pl small,.day .meta{display:none}\n  .cal .dow{font-size:10px;padding:4px}\n}\n.drw-bg{position:fixed;inset:0;z-index:30;background:color-mix(in srgb,#0b0b0d 40%,transparent);backdrop-filter:blur(6px);display:flex;justify-content:flex-end;animation:fade .3s}\n.drw{width:min(470px,100%);height:100%;background:var(--surface);border-left:1px solid var(--line);border-radius:var(--r) 0 0 var(--r);display:flex;flex-direction:column;box-shadow:-20px 0 50px rgba(0,0,0,.25);animation:slide .45s var(--ease)}\n@keyframes fade{from{opacity:0}} @keyframes slide{from{transform:translateX(30px);opacity:0}}\n.drw-h{display:flex;align-items:center;gap:8px;padding:14px 16px;border-bottom:1px solid var(--line)}\n.drw-t{flex:1;min-width:0;text-align:center}\n.drw-t h2{font-size:15px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}\n.drw-b{flex:1;overflow:auto;padding:18px;display:flex;flex-direction:column;gap:18px}\n.drw-b>*{flex-shrink:0}\n.drw .l{font-size:11px;color:var(--muted);font-weight:500}\n.drw-big{display:flex;flex-direction:column;gap:2px}\n.drw-big>b{font-size:36px;font-weight:600;letter-spacing:-.04em;font-variant-numeric:tabular-nums}\n.drw-st{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));border:1px solid var(--line);border-radius:var(--r-s);overflow:hidden}\n.drw-st>div{padding:10px 12px;display:flex;flex-direction:column;gap:2px;box-shadow:1px 0 0 var(--line),0 1px 0 var(--line);min-width:0}\n.drw-st b{font-size:15px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-variant-numeric:tabular-nums}\n.tr{border:1px solid var(--line);border-radius:var(--r-s);background:var(--raise);padding:10px 12px;display:flex;gap:12px;align-items:center}\n.tr .tt{flex:1;min-width:0;display:flex;flex-direction:column;gap:3px}\n.tr .tt b{font-weight:600;font-size:13.5px}\n.tr .tt small{font-size:12px;color:var(--muted)}\n.tr .gain{font-weight:600;font-size:15px;white-space:nowrap}\n.drw-list{display:flex;flex-direction:column;gap:8px}\n@media (max-width:640px){ .drw-bg{align-items:flex-end} .drw{height:88vh;border-radius:var(--r) var(--r) 0 0;border-left:0;border-top:1px solid var(--line);animation:up .4s var(--ease)} @keyframes up{from{transform:translateY(40px);opacity:0}} }\n\n/* ── Studio ── */\n.cats{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px}\n.cat{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);box-shadow:var(--shadow);padding:18px;display:flex;flex-direction:column;gap:8px;cursor:pointer;text-align:left;transition:transform .5s var(--ease),box-shadow .5s var(--ease),border-color .2s}\n.cat:hover{transform:translateY(-4px);box-shadow:var(--shadow-h)}\n.cat.sel{border-color:var(--ink);box-shadow:0 0 0 1px var(--ink),var(--shadow-h)}\n.cat.off{opacity:.6}\n.cat-h{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}\n.cat .e{width:44px;height:44px;border-radius:14px;background:var(--sunk);display:grid;place-items:center;font-size:24px}\n.cat.sel .e{background:var(--grad)}\n.cat h3{margin:4px 0 0;font:600 16px var(--f-body);letter-spacing:-.02em}\n.cat p{margin:0;color:var(--muted);font-size:13px}\n.cat .row2{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin-top:auto;padding-top:4px}\n.make{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:12px;align-items:end}\n@media (max-width:700px){.make{grid-template-columns:1fr}}\n.make label{display:flex;flex-direction:column;gap:6px;font-size:12.5px;color:var(--muted)}\n.make label.check{flex-direction:row;align-items:center;font-size:13.5px;color:var(--fg);padding-bottom:10px}\n.check{display:flex;gap:8px;align-items:center;font-size:13.5px;white-space:nowrap}\n.qrow{display:flex;justify-content:space-between;gap:10px;align-items:center;padding:10px 0;border-bottom:1px solid var(--line)}\n.qrow:last-child{border-bottom:0}\n.trends{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:10px}\n.trend{display:flex;justify-content:space-between;gap:12px;align-items:center;border:1px solid var(--line);border-radius:var(--r-s);background:var(--raise);padding:12px 14px;min-width:0;transition:border-color .2s}\n.trend:hover{border-color:var(--line2)}\n.trend .tt{display:flex;flex-direction:column;gap:3px;min-width:0}\n.trend .tt b{font-weight:600;font-size:14px}\n.trend .tt small{font-size:12px;color:var(--muted);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}\n.trend .inline{flex:none;flex-direction:column;align-items:stretch}\n#topicTrend{color:var(--accent)}\n\n/* ── Einstellungen ── */\n.settings-wrap{max-width:860px;margin:0 auto;display:flex;flex-direction:column;gap:12px;width:100%}\ndetails.set-sec{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);box-shadow:var(--shadow);scroll-margin-top:110px}\ndetails.set-sec>summary{cursor:pointer;list-style:none;display:grid;grid-template-columns:38px minmax(0,1fr) auto 16px;gap:12px;align-items:center;padding:14px 18px;border-radius:var(--r)}\ndetails.set-sec>summary:hover{background:var(--raise)}\ndetails.set-sec>summary::-webkit-details-marker{display:none}\ndetails.set-sec>summary::after{content:"▾";color:var(--muted);transition:transform .3s var(--ease);text-align:center}\ndetails.set-sec[open]>summary::after{transform:rotate(180deg)}\ndetails.set-sec[open]>summary{border-bottom:1px solid var(--line);border-radius:var(--r) var(--r) 0 0}\n.s-ic{width:38px;height:38px;border-radius:12px;background:var(--sunk);color:var(--fg);display:grid;place-items:center}\ndetails.set-sec[open] .s-ic{background:var(--ink);color:var(--ink-fg)}\n.s-ic svg{width:19px;height:19px}\n.s-t{display:flex;flex-direction:column;gap:1px;min-width:0}\n.s-t b{font-size:15px;font-weight:600;letter-spacing:-.015em}\n.s-t .hint{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}\n.s-chip{display:flex;gap:6px}\n.set-b{padding:16px 20px 20px;display:flex;flex-direction:column;gap:12px}\ndetails>*:not(summary){animation:fadeUp .4s var(--ease)}\n@media (max-width:640px){ details.set-sec>summary{grid-template-columns:32px minmax(0,1fr) 16px;padding:12px 14px} .s-chip{display:none} .s-ic{width:32px;height:32px} }\n.row{display:grid;grid-template-columns:minmax(0,1fr) minmax(190px,44%);gap:14px;align-items:center}\n.row>label{font-size:13.5px}\n.row small{display:block;color:var(--muted);font-size:11.5px;margin-top:1px}\n.row .tgl,.row>.btn{justify-self:end}\n.inline{display:flex;gap:8px;align-items:center;justify-content:flex-end;flex-wrap:wrap}\n@media (max-width:600px){ .row{grid-template-columns:1fr} .row .tgl,.row>.btn{justify-self:start} .inline{justify-content:flex-start} }\n.sep{height:1px;background:var(--line);margin:4px 0}\n.lbl{font-size:12px;font-weight:600;color:var(--muted);margin:6px 0 0}\n.tgl{position:relative;width:42px;height:24px;border-radius:999px;border:0;background:var(--line2);transition:background .2s;flex:none}\n.tgl::after{content:"";position:absolute;top:3px;left:3px;width:18px;height:18px;border-radius:50%;background:#fff;transition:transform .35s var(--ease);box-shadow:0 1px 2px rgba(0,0,0,.25)}\n.tgl[aria-checked=true]{background:var(--pos)} .tgl[aria-checked=true]::after{transform:translateX(18px)}\n.prov{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:8px}\n.prov label{display:flex;gap:10px;align-items:flex-start;border:1px solid var(--line2);border-radius:var(--r-s);padding:10px 12px;cursor:pointer;background:var(--raise);transition:border-color .2s,background .2s}\n.prov label:has(input:checked){border-color:var(--ink);background:var(--surface);box-shadow:0 0 0 1px var(--ink)}\n.prov input{margin-top:3px}\n.prov b{display:block;font-weight:600;font-size:13.5px}\n.prov small{color:var(--muted);font-size:12px}\n.savebar{position:sticky;bottom:max(14px,env(safe-area-inset-bottom,0px));margin:6px auto 0;max-width:860px;width:100%;display:flex;gap:10px;align-items:center;justify-content:space-between;border-radius:999px;background:var(--ink);color:var(--ink-fg);padding:8px 8px 8px 20px;box-shadow:var(--shadow-h);z-index:6;animation:pop .4s var(--ease)}\n.savebar .hint{color:color-mix(in srgb,var(--ink-fg) 70%,transparent)}\n.savebar .btn{border-color:transparent}\n.savebar .btn.accent{color:#fff}\n.sec-row{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.3fr) auto;gap:10px;align-items:center;padding:10px 0;border-bottom:1px solid var(--line)}\n.sec-row:last-child{border-bottom:0}\n.sec-row b{font-weight:600;font-size:13.5px} .sec-row small{display:block;font-size:11.5px;color:var(--muted)}\n@media (max-width:640px){ .sec-row{grid-template-columns:1fr} }\n.wizard{list-style:none;margin:6px 0 0;padding:0;display:grid;gap:14px}\n.wizard li{display:grid;grid-template-columns:28px minmax(0,1fr);gap:12px;align-items:start}\n.wizard .num{width:26px;height:26px;border-radius:50%;display:grid;place-items:center;font-weight:600;font-size:13px;background:var(--ink);color:var(--ink-fg)}\n.wizard b{font-weight:600}\n.login{min-height:calc(100vh - 140px);display:grid;place-items:center;padding:20px 0}\n.login .panel{max-width:560px;width:100%;padding:30px;box-shadow:var(--shadow-h)}\n.login h1{margin:0;font:700 26px var(--f-body);letter-spacing:-.03em;display:flex;align-items:center;gap:12px}\n.login h1 img{width:42px;height:42px;border-radius:13px}\n.toast{position:fixed;left:50%;transform:translateX(-50%);bottom:max(16px,env(safe-area-inset-bottom,0px));z-index:60;border-radius:999px;background:var(--ink);color:var(--ink-fg);padding:11px 20px;font-weight:500;box-shadow:var(--shadow-h);animation:toastIn .45s var(--ease);max-width:calc(100% - 32px)}\n.toast.bad{background:var(--neg);color:#fff}\n@keyframes toastIn{from{opacity:0;transform:translate(-50%,16px) scale(.96)}}\n.modal-bg{position:fixed;inset:0;z-index:50;background:color-mix(in srgb,#0b0b0d 40%,transparent);backdrop-filter:blur(6px);display:grid;place-items:center;padding:16px;animation:fade .3s}\n.modal{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);padding:24px;max-width:440px;width:100%;display:flex;flex-direction:column;gap:12px;box-shadow:var(--shadow-h);animation:pop .4s var(--ease)}\n.modal:has(.logbox){max-width:820px}\n.logbox{max-height:min(60vh,520px);overflow:auto;white-space:pre-wrap;margin:0;font:11.5px/1.45 var(--f-code);background:var(--raise);border:1px solid var(--line);border-radius:12px;padding:12px}\n.actions{display:flex;gap:8px;flex-wrap:wrap} .actions .btn{flex:1}\n@keyframes pop{from{opacity:0;transform:translateY(12px) scale(.97)}}\n\n/* ── Einblenden ── */\n.in{animation:rise .75s var(--ease) both;animation-delay:calc(var(--i,0)*70ms)}\n@keyframes rise{from{opacity:0;transform:translateY(18px) scale(.985);filter:blur(8px)}}\n@keyframes fadeUp{from{opacity:0;transform:translateY(6px)}}\n@keyframes word{from{opacity:0;filter:blur(10px);transform:translateY(8px)}}\n::view-transition-old(root),::view-transition-new(root){animation:none;mix-blend-mode:normal}\n::view-transition-new(root){z-index:2} ::view-transition-old(root){z-index:1}\n@media (prefers-reduced-motion:reduce){ *,*::before,*::after{animation:none!important;transition:none!important} }\n\n/* ── Schmal / Handy ── */\n@media (max-width:900px){\n  .top{backdrop-filter:none;-webkit-backdrop-filter:none;background:var(--bg)}\n  .bar{grid-template-columns:1fr auto;padding-block:10px}\n  .nav{position:fixed;left:50%;transform:translateX(-50%);bottom:max(12px,env(safe-area-inset-bottom,0px));z-index:30;background:var(--glass);backdrop-filter:saturate(1.5) blur(18px);-webkit-backdrop-filter:saturate(1.5) blur(18px);box-shadow:0 12px 40px -12px rgba(0,0,0,.35);padding:6px}\n  .nav button{flex-direction:column;gap:2px;padding:7px 12px;font-size:10px}\n  .nav button svg{display:block;width:20px;height:20px}\n  .nav button span{display:none}\n  .nav button em{display:inline;font-style:normal;font-size:10px}\n  main{padding-bottom:110px}\n  .status{justify-content:flex-start}\n  .toast{bottom:calc(max(12px,env(safe-area-inset-bottom,0px)) + 76px)}\n  .savebar{bottom:calc(max(12px,env(safe-area-inset-bottom,0px)) + 76px)}\n}\n@media (max-width:480px){ .panel{padding:16px} .hero-card{padding:16px} .wal b{font-size:13.5px} .bar-r .btn span{display:none} }\n</style>\n</head>\n<body>\n<div id="app"></div>\n<script>\n"use strict";\n/* ═════════════════ Grundlagen ═════════════════ */\nconst $ = s => document.querySelector(s);\nconst esc = s => String(s ?? "").replace(/[&<>"\']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", \'"\': "&quot;", "\'": "&#39;"}[c]));\nconst icon = d => `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;\nconst I = {\n  dash: \'<path d="M4 15a8 8 0 1 1 16 0"/><path d="M12 15l4.5-4.5"/><circle cx="12" cy="15" r="1.2"/>\',\n  cal: \'<rect x="4" y="5" width="16" height="15" rx="2.5"/><path d="M4 10h16M9 3v4M15 3v4"/>\',\n  studio: \'<rect x="7" y="3" width="10" height="18" rx="2.5"/><path d="M11 9.5v5l4-2.5z"/>\',\n  gear: \'<circle cx="12" cy="12" r="3"/><path d="M12 3v2.5M12 18.5V21M3 12h2.5M18.5 12H21M5.6 5.6l1.8 1.8M16.6 16.6l1.8 1.8M5.6 18.4l1.8-1.8M16.6 7.4l1.8-1.8"/>\',\n  sun: \'<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>\',\n  moon: \'<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/>\',\n  reload: \'<path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 5v6h-6"/>\',\n  plus: \'<path d="M12 5v14M5 12h14"/>\',\n  eye: \'<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>\',\n  heart: \'<path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/>\',\n  user: \'<circle cx="12" cy="8" r="4"/><path d="M4 20c1.5-4 4.5-6 8-6s6.5 2 8 6"/>\',\n  film: \'<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8 4v16M16 4v16M4 9h4M4 15h4M16 9h4M16 15h4"/>\',\n  left: \'<path d="M15 5l-7 7 7 7"/>\', right: \'<path d="M9 5l7 7-7 7"/>\', x: \'<path d="M6 6l12 12M18 6L6 18"/>\',\n  clock: \'<circle cx="12" cy="12" r="8"/><path d="M12 8v4l3 2"/>\', plug: \'<path d="M9 7V3M15 7V3M7 7h10v4a5 5 0 0 1-10 0z"/><path d="M12 16v5"/>\',\n  spark: \'<path d="M12 3c.8 4.5 2.2 6 6.5 6.8-4.3.8-5.7 2.3-6.5 6.8-.8-4.5-2.2-6-6.5-6.8C9.8 9 11.2 7.5 12 3z"/>\',\n  key: \'<circle cx="8" cy="15" r="4"/><path d="M11 12l9-9M17 6l3 3M15 8l2 2"/>\', brush: \'<path d="M18 3l3 3-9 9-3-3z"/><path d="M9 12c-3 0-5 2-5 5 0 1-1 2-2 2 2 2 9 2 9-4"/>\',\n  app: \'<rect x="4" y="4" width="16" height="16" rx="4"/><path d="M9 12h6M12 9v6"/>\', gh: \'<path d="M9 19c-4 1.5-4-2-6-2.5M15 21v-3.5c0-1 .1-1.4-.5-2 2.8-.3 5.5-1.4 5.5-6a4.6 4.6 0 0 0-1.3-3.2 4.2 4.2 0 0 0-.1-3.2s-1-.3-3.4 1.3a11.6 11.6 0 0 0-6 0C6.8 2.8 5.8 3.1 5.8 3.1a4.2 4.2 0 0 0-.1 3.2A4.6 4.6 0 0 0 4.4 9.5c0 4.6 2.7 5.7 5.5 6-.6.6-.6 1.2-.5 2V21"/>\',\n};\nasync function api(url, body) {\n  const r = await fetch(url, {method: body === undefined ? "GET" : "POST", cache: "no-store",\n    headers: {"Content-Type": "application/json", "X-AS": "1"}, body: body === undefined ? undefined : JSON.stringify(body)});\n  const j = await r.json().catch(() => ({}));\n  if (!r.ok) throw new Error(j.error || `Fehler ${r.status}`);\n  return j;\n}\nasync function gh(method, path, body, raw) {\n  const j = await api("/api/gh", {method, path, body, raw: !!raw});\n  if (j.status >= 400) {\n    const m = (j.data && j.data.message) || "";\n    throw new Error(j.status === 401 ? "Der GitHub-Zugangsschlüssel ist ungültig oder abgelaufen." : j.status === 403 || j.status === 404 ? `GitHub verweigert den Zugriff (${m || j.status}). Prüfe die Rechte des Zugangsschlüssels.` : `GitHub meldet ${j.status}: ${m}`);\n  }\n  return j.data;\n}\nfunction toast(msg, bad) {\n  document.querySelectorAll(".toast").forEach(t => t.remove());\n  document.body.insertAdjacentHTML("beforeend", `<div class="toast${bad ? " bad" : ""}" role="status">${esc(msg)}</div>`);\n  const t = document.body.lastElementChild; setTimeout(() => t.remove(), 4200);\n}\nconst fmtN = v => { v = Math.round(v || 0); const a = Math.abs(v); return a >= 1e6 ? (v / 1e6).toFixed(1).replace(".", ",") + " Mio" : a >= 1e4 ? (v / 1e3).toFixed(1).replace(".", ",") + " Tsd" : v.toLocaleString("de-DE"); };\nconst kN = v => v >= 10000 ? (v / 1000).toFixed(v % 1000 ? 1 : 0).replace(".", ",") + "k" : String(v);\nconst pct = v => isFinite(v) ? v.toFixed(1).replace(".", ",") + " %" : "–";\nconst dkey = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;\nconst fromKey = k => { const [y, m, d] = k.split("-").map(Number); return new Date(y, m - 1, d); };\nconst fmtTs = t => t ? new Date(t * 1000).toLocaleString("de-DE", {day: "2-digit", month: "2-digit", year: "2-digit", hour: "2-digit", minute: "2-digit"}) : "–";\nconst MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"];\n\n/* ═════════════════ Zustand ═════════════════ */\nlet S = null;                                   // App (lokal)\nlet CFG = null, ST = {}, VIDS = [], STATS = {v: {}, ch: {}}, TRENDS = {items: []};   // Daten aus dem Repository\nlet SECRETS = null, RUNS = [], PENDING = null, LOADERR = "";\nlet TAB = (location.hash || "#dashboard").slice(1);\nif (!["dashboard", "kalender", "studio", "einstellungen"].includes(TAB)) TAB = "dashboard";\nconst DEF = {trend_mode: "half", make_thumbnail: true, youtube_thumbnail: true};\nconst S_ = k => { const v = (CFG && CFG.settings || {})[k]; return v === undefined ? DEF[k] : v; };\nconst cat = slug => (CFG && CFG.categories || []).find(c => c.slug === slug);\n\nasync function loadData() {\n  try {\n    const [c, s, v, st, tr] = await Promise.all(["config", "state", "videos", "stats", "trends"].map(f => gh("GET", `/contents/docs/data/${f}.json?ref=main`, null, true).catch(e => { if (f === "trends") return {items: []}; throw e; })));\n    TRENDS = tr && tr.items ? tr : {items: []};\n    CFG = typeof c === "string" ? JSON.parse(c) : c; ST = s || {}; VIDS = v || []; STATS = st || {v: {}, ch: {}};\n    CFG.settings = CFG.settings || {}; CFG.categories = CFG.categories || []; CFG.queue = CFG.queue || [];\n    LOADERR = "";\n  } catch (e) { LOADERR = e.message; }\n}\nasync function loadSecrets() {\n  try { const j = await gh("GET", "/actions/secrets?per_page=100"); SECRETS = new Set(j.secrets.map(s => s.name)); } catch (e) { SECRETS = "err"; }\n}\nfunction b64utf8(s) { const b = new TextEncoder().encode(s); let bin = ""; for (let i = 0; i < b.length; i += 8192) bin += String.fromCharCode(...b.subarray(i, i + 8192)); return btoa(bin); }\nasync function saveConfig(msg) {\n  const used = new Set(ST.used_queue || []);\n  CFG.queue = (CFG.queue || []).filter(q => !used.has(q.id));\n  const meta = await gh("GET", "/contents/docs/data/config.json?ref=main");\n  await gh("PUT", "/contents/docs/data/config.json", {message: "App: " + msg, content: b64utf8(JSON.stringify(CFG, null, 1)), sha: meta.sha, branch: "main"});\n}\nasync function persist(msg, btn) {\n  if (btn) btn.disabled = true;\n  try { await saveConfig(msg); toast("Gespeichert"); render(); }\n  catch (e) { toast(e.message, true); await loadData(); render(); }\n  finally { if (btn) btn.disabled = false; }\n}\nasync function dispatch(inputs, label) {\n  try {\n    await gh("POST", "/actions/workflows/autoshorts.yml/dispatches", {ref: "main", inputs});\n    PENDING = {label, at: Date.now()}; banner(); setTimeout(pollRuns, 4000); return true;\n  } catch (e) { toast(e.message, true); return false; }\n}\n\n/* ═════════════════ Läufe auf GitHub ═════════════════ */\nlet runTimer = null, wasActive = false;\nconst RUNLABEL = {make: "Video wird erstellt", upload: "Upload läuft", stats: "Zahlen werden geholt", trends: "Trends werden gesammelt", auto: "Autopilot läuft"};\nfunction runName(r) { if (r.event === "schedule") return "Autopilot"; const a = (r.display_title || "").trim().split(/\\s+/)[0]; return RUNLABEL[a] || r.display_title || "Auftrag"; }\nconst isLive = r => r.status !== "completed" && (r.event !== "schedule" || Date.now() - new Date(r.run_started_at || r.created_at) > 90000);\nasync function pollRuns() {\n  clearTimeout(runTimer);\n  try { const j = await gh("GET", "/actions/workflows/autoshorts.yml/runs?per_page=10"); RUNS = j.workflow_runs || []; } catch (e) {}\n  const active = RUNS.some(isLive);\n  if (PENDING && RUNS.some(r => r.event === "workflow_dispatch" && new Date(r.created_at).getTime() > PENDING.at - 60000)) PENDING = null;\n  if (wasActive && !active) { await loadData(); render(); }\n  wasActive = active;\n  banner();\n  if (TAB === "dashboard" && $("#runsBox")) $("#runsBox").innerHTML = runsList();\n  runTimer = setTimeout(pollRuns, active || PENDING ? 8000 : 45000);\n}\nconst mins = t => { const m = Math.max(0, Math.round((Date.now() - new Date(t)) / 60000)); return m < 1 ? "wenigen Sekunden" : m + " Min."; };\nfunction banner() {\n  const el = $("#banner"); if (!el) return;\n  let h = "";\n  const live = RUNS.filter(isLive), recent = RUNS.find(r => r.status === "completed" && r.event !== "schedule" && Date.now() - new Date(r.updated_at) < 15 * 60000);\n  if (PENDING && !live.length) h += `<div class="banner run"><span class="spin"></span><b>${esc(PENDING.label)}</b><span class="muted">Auftrag an GitHub gesendet, startet gleich …</span></div>`;\n  else if (live.length) { const r = live[0]; h += `<div class="banner run"><span class="spin"></span><b>${esc(runName(r))} …</b><span class="muted">${r.status === "queued" ? "wartet auf einen freien Rechner" : "läuft seit " + mins(r.run_started_at)}</span><a href="${esc(r.html_url)}" target="_blank" rel="noopener">Protokoll ↗</a></div>`; }\n  else if (recent) { const ok = recent.conclusion === "success"; h += `<div class="banner ${ok ? "ok" : "bad"}"><b class="${ok ? "pos" : "neg"}">${ok ? "Fertig" : "Fehlgeschlagen"}:</b><span>${esc(runName(recent))}</span><a href="${esc(recent.html_url)}" target="_blank" rel="noopener">Protokoll ↗</a></div>`; }\n  if (S && S.update && S.update.available) h += `<div class="banner">Update verfügbar: Version <b>${esc(S.update.version)}</b>${S.update.notes ? ` · ${esc(S.update.notes)}` : ""}<button class="btn primary sm" style="margin-left:auto" onclick="runUpdate()">Jetzt aktualisieren</button></div>`;\n  if (LOADERR) h += `<div class="banner bad">Daten konnten nicht geladen werden: ${esc(LOADERR)}</div>`;\n  el.innerHTML = h;\n}\n\n/* ═════════════════ Auswertung ═════════════════ */\nfunction latest(id) { const s = STATS.v?.[id] || {}, o = {}; for (const p in s) { const r = s[p][s[p].length - 1]; if (r) o[p] = {views: r[1], likes: r[2], comments: r[3], shares: r[4]}; } return o; }\nlet DAYS = null;\nfunction dayMap() {   // Zuwachs je Tag: {day: {yt, tt, likes, comments, shares, vids:{id:{views,likes}}}}\n  if (DAYS) return DAYS;\n  const m = {};\n  const g = d => m[d] || (m[d] = {yt: 0, tt: 0, likes: 0, comments: 0, shares: 0, vids: {}});\n  for (const id in (STATS.v || {})) for (const p in STATS.v[id]) {\n    let pv = 0, pl = 0, pc = 0, ps = 0;\n    for (const r of STATS.v[id][p]) {\n      const x = g(r[0]), dv = Math.max(0, r[1] - pv), dl = Math.max(0, r[2] - pl);\n      x[p === "youtube" ? "yt" : "tt"] += dv; x.likes += dl; x.comments += Math.max(0, r[3] - pc); x.shares += Math.max(0, r[4] - ps);\n      const vv = x.vids[id] || (x.vids[id] = {views: 0, likes: 0}); vv.views += dv; vv.likes += dl;\n      pv = r[1]; pl = r[2]; pc = r[3]; ps = r[4];\n    }\n  }\n  for (const p in (STATS.ch || {})) { let prev = null; for (const r of STATS.ch[p]) { if (prev !== null) g(r[0])["f_" + p] = r[1] - prev; prev = r[1]; } }\n  for (const v of VIDS) { const k = dkey(new Date(v.created * 1000)); (g(k).made || (g(k).made = [])).push(v.id); }\n  return DAYS = m;\n}\nfunction followers(p) { const rows = STATS.ch?.[p]; if (!rows || !rows.length) return null; const last = rows[rows.length - 1];\n  const d = new Date(); d.setDate(d.getDate() - 7); const k = dkey(d); const old = [...rows].reverse().find(r => r[0] <= k) || rows[0]; return {n: last[1], week: last[1] - old[1]}; }\nfunction lastDays(n) { const out = []; for (let i = n - 1; i >= 0; i--) { const d = new Date(); d.setDate(d.getDate() - i); out.push(dkey(d)); } return out; }\nfunction nextUp() {\n  const used = new Set(ST.used_queue || []);\n  const q = (CFG.queue || []).filter(x => !used.has(x.id) && cat(x.category)).sort((a, b) => a.created - b.created)[0];\n  if (q) return {c: cat(q.category), topic: q.text};\n  const cs = CFG.categories.filter(c => c.enabled); if (!cs.length) return null;\n  const i = cs.findIndex(c => c.slug === ST.last_category); return {c: cs[(i + 1) % cs.length], topic: null};\n}\nfunction nextRun() {\n  if (!S_("autopilot")) return null;\n  const times = String(S_("upload_times") || "18:00").split(/[,;]/).map(t => t.trim()).filter(Boolean).map(t => t.split(":").map(Number)).filter(([h]) => h >= 0 && h < 24);\n  const now = new Date(); let best = null;\n  for (let add = 0; add < 2; add++) for (const [h, m] of times) { const d = new Date(now); d.setDate(d.getDate() + add); d.setHours(h, m || 0, 0, 0); if (d > now && (!best || d < best)) best = d; }\n  return best;\n}\nconst STATUS = {rendering: ["In Arbeit", "warn"], rendered: ["Fertig, nicht hochgeladen", "mute"], published: ["Veröffentlicht", "good"], partial: ["Teilweise", "warn"], error: ["Fehler", "bad"]};\nconst thumb = v => v.thumb ? `<img class="thumb" loading="lazy" alt="" src="https://raw.githubusercontent.com/${esc(S.owner)}/${esc(S.repo)}/main/docs/thumbs/${v.id}.jpg" onerror="this.style.visibility=\'hidden\'">` : `<span class="thumb"></span>`;\nconst trendChip = v => v.trend ? `<span class="chip acc" title="${esc(v.trend.source)}: ${esc(v.trend.title)}">🔥 Trend</span>` : "";\nconst mp4 = v => `https://github.com/${S.owner}/${S.repo}/releases/download/videos/${v.id}.mp4`;\n\n/* ═════════════════ Gerüst ═════════════════ */\nconst NAV = [["dashboard", "Dashboard", I.dash, "Start"], ["kalender", "Kalender", I.cal, "Kalender"], ["studio", "Studio", I.studio, "Studio"], ["einstellungen", "Einstellungen", I.gear, "Mehr"]];\nconst PAGES = {kalender: ["Kalender", "Jeder Tag auf einen Blick. Tippe auf einen Tag für die Details."], studio: ["Studio", "Video-Art wählen, Thema vorgeben, sofort erstellen."], einstellungen: ["Einstellungen", "Zeitplan, Plattformen, KI-Anbieter und App."]};\nconst greet = () => { const h = new Date().getHours(); return h < 5 ? "Gute Nacht" : h < 11 ? "Guten Morgen" : h < 18 ? "Guten Tag" : "Guten Abend"; };\nconst theme = () => document.documentElement.dataset.theme === "dark" ? "dark" : "light";\nfunction setTheme(t, ev) {\n  try { localStorage.setItem("as-theme", t); } catch (e) {}\n  const apply = () => { if (t === "dark") document.documentElement.dataset.theme = "dark"; else delete document.documentElement.dataset.theme;\n    const m = document.querySelector(\'meta[name="theme-color"]\'); if (m) m.content = t === "dark" ? "#0b0b0d" : "#efeef2"; $("#thT").innerHTML = icon(t === "dark" ? I.sun : I.moon); };\n  if (!document.startViewTransition || matchMedia("(prefers-reduced-motion: reduce)").matches) return apply();\n  const x = ev ? ev.clientX : innerWidth - 40, y = ev ? ev.clientY : 40, r = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));\n  document.startViewTransition(apply).ready.then(() => document.documentElement.animate({clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${r}px at ${x}px ${y}px)`]},\n    {duration: 750, easing: "cubic-bezier(.65,0,.35,1)", pseudoElement: "::view-transition-new(root)"})).catch(() => {});\n}\nfunction navInd() {\n  const nav = $(".nav"), ind = $(".nav-ind"), cur = nav && nav.querySelector(\'[aria-current="true"]\');\n  if (!nav || !ind || !cur) return;\n  ind.style.left = cur.offsetLeft + "px"; ind.style.width = cur.offsetWidth + "px"; ind.style.opacity = 1;\n}\nfunction shell() {\n  $("#app").innerHTML = `\n  <header class="top"><div class="wrap bar">\n    <div class="brand"><img src="/icon.svg" alt=""><span>AutoShorts</span></div>\n    <nav class="nav" aria-label="Bereiche"><span class="nav-ind" aria-hidden="true"></span>${NAV.map(([k, l, d, short]) => `<button type="button" data-tab="${k}" aria-current="${k === TAB}">${icon(d)}<span>${l}</span><em>${short}</em></button>`).join("")}</nav>\n    <div class="bar-r">\n      <div class="icgrp"><button class="ib" id="thT" type="button" title="Hell / Dunkel">${icon(theme() === "dark" ? I.sun : I.moon)}</button><button class="ib" id="rl" type="button" title="Neu laden">${icon(I.reload)}</button></div>\n      <button class="btn accent" type="button" onclick="go(\'studio\')">${icon(I.plus)}<span>Video erstellen</span></button>\n    </div>\n  </div></header>\n  <div class="wrap">\n    <div class="phead"><div><h1 id="pTitle"></h1><p id="pSub"></p></div><div class="status" id="status"></div></div>\n    <div id="banner"></div><main id="main"></main>\n  </div>`;\n  document.querySelectorAll("[data-tab]").forEach(b => b.onclick = () => go(b.dataset.tab));\n  $("#thT").onclick = e => setTheme(theme() === "dark" ? "light" : "dark", e);\n  $("#rl").onclick = async () => { await refreshAll(); toast("Aktualisiert"); };\n  addEventListener("resize", () => { clearTimeout(navInd._t); navInd._t = setTimeout(navInd, 80); });\n  if (document.fonts && document.fonts.ready) document.fonts.ready.then(navInd);\n}\nfunction go(t) { if (t === TAB) return; closeDay(); TAB = t; history.replaceState(null, "", "#" + t); scrollTo({top: 0}); render(true); }\naddEventListener("hashchange", () => { const t = location.hash.slice(1); if (NAV.some(n => n[0] === t) && t !== TAB) { TAB = t; render(true); } });\nfunction head(animate) {\n  const [title, sub] = TAB === "dashboard" ? [greet() + ".", dashLine()] : PAGES[TAB];\n  $("#pTitle").innerHTML = title.split(/(\\s+)/).map((w, i) => /^\\s+$/.test(w) ? w : `<span class="w" style="--w:${i / 2}${animate ? "" : ";animation:none"}">${esc(w)}</span>`).join("");\n  $("#pSub").textContent = sub;\n  const con = ST.connected || {}, nr = nextRun();\n  $("#status").innerHTML = `<span class="pill"><span class="dot ${S_("autopilot") ? "ok" : "warn"}"></span>${S_("autopilot") ? "Autopilot" + (nr ? " · " + nr.toLocaleString("de-DE", {weekday: "short", hour: "2-digit", minute: "2-digit"}) : "") : "Autopilot aus"}</span>\n    <span class="pill"><span class="dot ${con.youtube ? "ok" : "bad"}"></span>YouTube</span><span class="pill"><span class="dot ${con.tiktok ? "ok" : "bad"}"></span>TikTok</span>`;\n}\nfunction dashLine() {\n  if (!CFG) return "Lade Daten …";\n  const n = nextUp(), nr = nextRun();\n  if (!S_("autopilot")) return "Der Autopilot ist aus. Videos startest du im Studio.";\n  return `Nächstes Video ${nr ? nr.toLocaleString("de-DE", {weekday: "long", hour: "2-digit", minute: "2-digit"}) + " Uhr" : "bald"}${n ? ": " + n.c.emoji + " " + n.c.name : ""}.`;\n}\nfunction render(animate) {\n  if (!S.connected) return renderSetup();\n  if (!$(".nav")) shell();\n  document.querySelectorAll("[data-tab]").forEach(b => b.setAttribute("aria-current", b.dataset.tab === TAB));\n  navInd(); head(animate); banner();\n  if (!CFG) { $("#main").innerHTML = `<div class="empty">${LOADERR ? esc(LOADERR) : "Lade Daten …"}</div>`; return; }\n  DAYS = null;\n  ({dashboard: viewDash, kalender: viewCal, studio: viewStudio, einstellungen: viewSettings})[TAB]();\n  if (!animate) document.querySelectorAll("#main .in").forEach(e => e.style.animation = "none");\n}\nasync function refreshAll() { await Promise.all([loadData(), loadSecrets(), api("/api/state").then(s => S = s)]); render(); pollRuns(); }\n\n/* ═════════════════ Einrichtung (Verbinden mit GitHub) ═════════════════ */\nfunction renderSetup() {\n  $("#app").innerHTML = `<div class="wrap login"><div class="panel in">\n    <h1><img src="/icon.svg" alt="">AutoShorts</h1>\n    <p class="hint" style="font-size:14px">Einmal einrichten: Die App braucht einen Zugangsschlüssel für dein GitHub-Repository, dort baut der Motor jeden Tag deine Videos. Der Schlüssel bleibt nur auf diesem PC.</p>\n    <ol class="wizard">\n      <li><span class="num">1</span><div><a href="https://github.com/settings/personal-access-tokens/new" target="_blank" rel="noopener"><b>Neuen Zugangsschlüssel erstellen ↗</b></a><p class="hint">Fine-grained token · Name z. B. „AutoShorts App“ · Ablauf 1 Jahr oder „No expiration“.</p></div></li>\n      <li><span class="num">2</span><div><b>Repository access:</b> Only select repositories → <code>${esc(S.owner)}/${esc(S.repo)}</code></div></li>\n      <li><span class="num">3</span><div><b>Repository permissions:</b> Actions · Contents · Secrets jeweils auf <b>Read and write</b>.</div></li>\n      <li><span class="num">4</span><div><b>Generate token</b>, kopieren und hier einfügen:</div></li>\n    </ol>\n    <input id="tok" type="password" autocomplete="off" placeholder="github_pat_…">\n    <details><summary class="hint" style="cursor:pointer">Anderes Repository</summary>\n      <div class="grid2" style="gap:10px;margin-top:8px"><input id="rown" value="${esc(S.owner)}" aria-label="Besitzer"><input id="rrep" value="${esc(S.repo)}" aria-label="Repository"></div></details>\n    <button class="btn primary" id="conn" style="padding:12px">Verbinden</button>\n  </div></div>`;\n  $("#tok").focus();\n  $("#conn").onclick = async () => {\n    const b = $("#conn"); b.disabled = true;\n    try { await api("/api/github", {token: $("#tok").value, owner: $("#rown").value, repo: $("#rrep").value});\n      S = await api("/api/state"); TAB = "einstellungen"; history.replaceState(null, "", "#einstellungen"); $("#app").innerHTML = ""; await refreshAll(); toast("Verbunden. Jetzt die KI-Schlüssel eintragen."); }\n    catch (e) { toast(e.message, true); b.disabled = false; }\n  };\n}\n\n/* ═════════════════ Dashboard ═════════════════ */\nlet RANGE = 30, PLAT = "all";\nfunction viewDash() {\n  const D = dayMap(), last14 = lastDays(14), last7 = lastDays(7), prev7 = lastDays(14).slice(0, 7);\n  const sum = (keys, f) => keys.reduce((a, k) => a + (D[k] ? f(D[k]) : 0), 0);\n  const tot = {views: 0, likes: 0, comments: 0, shares: 0, yt: 0, tt: 0};\n  const rows = [...VIDS].reverse().map(v => { const st = latest(v.id); let vw = 0, lk = 0;\n    for (const p in st) { vw += st[p].views; lk += st[p].likes; tot.views += st[p].views; tot.likes += st[p].likes; tot.comments += st[p].comments; tot.shares += st[p].shares; tot[p === "youtube" ? "yt" : "tt"] += st[p].views; }\n    return {...v, st, views: vw, likes: lk}; });\n  const w = sum(last7, x => x.yt + x.tt), pw = sum(prev7, x => x.yt + x.tt), chg = pw ? (w - pw) / pw * 100 : null;\n  const today = D[dkey(new Date())] || {yt: 0, tt: 0, likes: 0};\n  const fy = followers("youtube"), ft = followers("tiktok");\n  const published = rows.filter(v => ["published", "partial"].includes(v.status)).length;\n  const bmax = Math.max(1, ...last14.map(k => D[k] ? D[k].yt + D[k].tt : 0));\n  const byCat = {};\n  rows.filter(v => ["published", "partial"].includes(v.status)).forEach(v => { const c = cat(v.category), k = v.category;\n    const b = byCat[k] || (byCat[k] = {name: c ? c.emoji + " " + c.name : k, videos: 0, views: 0, likes: 0}); b.videos++; b.views += v.views; b.likes += v.likes; });\n  const cats = Object.values(byCat).map(c => ({...c, avg: c.views / c.videos})).sort((a, b) => b.avg - a.avg), cmax = Math.max(1, ...cats.map(c => c.avg));\n  const nx = nextUp();\n  $("#main").innerHTML = `\n  <section class="hero">\n    <div class="hero-card in" style="--i:0">\n      <div class="hc-top"><span>Aufrufe gesamt</span><small>alle Videos</small></div>\n      <div class="bal">${fmtN(tot.views)}</div>\n      <div class="delta"><b class="${chg === null ? "zero" : chg >= 0 ? "pos" : "neg"}">${chg === null ? "–" : (chg >= 0 ? "+" : "") + chg.toFixed(0) + " %"}</b> letzte 7 Tage zur Woche davor</div>\n      <div class="wal"><div><span><i style="background:var(--yt)"></i>YouTube</span><b>${fmtN(tot.yt)}</b></div><div><span><i style="background:var(--tt)"></i>TikTok</span><b>${fmtN(tot.tt)}</b></div><div><span><i style="background:var(--pos)"></i>Likes</span><b>${fmtN(tot.likes)}</b></div></div>\n      <div class="hb-act"><button class="btn primary" onclick="go(\'studio\')">Video erstellen</button><button class="btn" onclick="dispatch({action:\'stats\'},\'Zahlen werden geholt\')">Zahlen holen</button></div>\n    </div>\n    <div class="tiles in" style="--i:1">\n      <div class="tile hot"><div class="tile-h">Heute neu<i>${icon(I.eye)}</i></div><b>${fmtN(today.yt + today.tt)}</b><small><em>${fmtN(today.likes)}</em> Likes heute</small></div>\n      <div class="tile"><div class="tile-h">YouTube-Abos<i>${icon(I.user)}</i></div><b>${fmtN(fy?.n || 0)}</b><small><em class="${fy && fy.week > 0 ? "pos" : ""}">${fy ? (fy.week >= 0 ? "+" : "") + fy.week : "–"}</em> in 7 Tagen</small></div>\n      <div class="tile"><div class="tile-h">TikTok-Follower<i>${icon(I.heart)}</i></div><b>${fmtN(ft?.n || 0)}</b><small><em>${ft ? (ft.week >= 0 ? "+" : "") + ft.week : "–"}</em> in 7 Tagen</small></div>\n      <div class="tile"><div class="tile-h">Videos online<i>${icon(I.film)}</i></div><b>${published}</b><small><em>Ø ${fmtN(published ? tot.views / published : 0)}</em> Aufrufe</small></div>\n    </div>\n    <div class="hero-card in" style="--i:2">\n      <div class="hc-top"><span>Aufrufe pro Tag</span><small>letzte 14 Tage</small></div>\n      <div class="bars-box"><div class="bars-h"><span>YouTube <b style="color:var(--fg)">■</b> · TikTok <b style="color:var(--accent)">▨</b></span><b>${fmtN(sum(last14, x => x.yt + x.tt))}</b></div>\n        <div class="bars">${last14.map((k, i) => { const x = D[k]; const d = fromKey(k);\n          if (!x || !(x.yt + x.tt)) return `<div class="col ph"><div class="stk"></div><small>${d.getDate()}.</small></div>`;\n          return `<div class="col" style="--k:${i}"><span class="tip">${d.toLocaleDateString("de-DE", {weekday: "short", day: "2-digit", month: "2-digit"})}: YT ${fmtN(x.yt)} · TT ${fmtN(x.tt)}</span><div class="stk">\n            ${x.tt ? `<i class="s2" style="height:${x.tt / bmax * 100}%"></i>` : ""}${x.yt ? `<i class="s1" style="height:${x.yt / bmax * 100}%"></i>` : ""}</div><small>${d.getDate()}.</small></div>`; }).join("")}</div></div>\n    </div>\n  </section>\n  <section class="panel in" style="--i:3">\n    <div class="section-h"><div><h2>Verlauf</h2><p class="hint">Neue Aufrufe je Tag, getrennt nach Plattform.</p></div>\n      <div style="display:flex;gap:8px;flex-wrap:wrap"><div class="seg" id="pSeg">${[["all", "Beide"], ["youtube", "YouTube"], ["tiktok", "TikTok"]].map(([k, l]) => `<button type="button" data-v="${k}" aria-pressed="${PLAT === k}">${l}</button>`).join("")}</div>\n      <div class="seg" id="rSeg">${[7, 30, 90].map(d => `<button type="button" data-v="${d}" aria-pressed="${RANGE === d}">${d} Tage</button>`).join("")}</div></div></div>\n    <div id="chart"></div>\n    <div class="legend"><span><i style="background:var(--yt)"></i>YouTube</span><span><i style="background:var(--tt)"></i>TikTok</span></div>\n  </section>\n  <div class="grid3">\n    <section class="panel in" style="--i:4"><div class="section-h"><div><h2>Nach Kategorie</h2><p class="hint">Ø Aufrufe pro Video. Mehr von dem, was läuft.</p></div></div>\n      ${cats.length ? `<div class="hbars">${cats.map(c => `<div class="hbar"><div class="hbar-l"><b>${esc(c.name)}</b><small>${c.videos} Videos · ${pct(c.views ? c.likes / c.views * 100 : NaN)} Likes</small></div><div class="hbar-t"><i style="width:${c.avg / cmax * 100}%"></i></div><span>${fmtN(c.avg)}</span></div>`).join("")}</div>` : `<div class="empty">Noch keine veröffentlichten Videos.</div>`}</section>\n    <section class="panel in" style="--i:5"><div class="section-h"><div><h2>Als Nächstes</h2><p class="hint">Was der Autopilot beim nächsten Lauf erstellt.</p></div></div>\n      ${nx ? `<div style="display:flex;gap:12px;align-items:center"><span style="width:48px;height:48px;border-radius:15px;background:var(--grad);display:grid;place-items:center;font-size:26px;flex:none">${esc(nx.c.emoji)}</span><div><b style="font-size:15px">${esc(nx.c.name)}</b><p class="hint" style="font-size:13px">${esc(nx.topic || "Thema sucht die KI selbst aus, ohne Wiederholungen.")}</p></div></div>` : `<div class="empty">Keine Kategorie aktiv.</div>`}\n      <div class="sep"></div><h2 style="font-size:14px">Letzte Aufträge</h2><div class="runs" id="runsBox">${runsList()}</div></section>\n  </div>\n  <section class="panel in" style="--i:6"><div class="section-h"><div><h2>Alle Videos</h2><p class="hint">Neueste zuerst. Fehlgeschlagene Uploads kannst du hier wiederholen.</p></div></div>\n    <div class="scroll">${rows.length ? `<table><thead><tr><th class="t">Video</th><th>Erstellt</th><th class="t">Status</th><th>YT Aufrufe</th><th>TT Aufrufe</th><th>Likes</th><th></th></tr></thead><tbody>\n    ${rows.map(v => { const st = STATUS[v.status] || [v.status, "mute"], c = cat(v.category);\n      return `<tr><td class="t w" style="min-width:260px"><div class="vrow">${thumb(v)}<div class="tt"><b>${esc(v.title || v.topic || "…")}</b><div><span class="chip">${esc(c?.emoji || "")} ${esc(c?.name || v.category)}</span>${trendChip(v)}${v.yt_id ? `<a class="chip mute" href="https://youtube.com/shorts/${esc(v.yt_id)}" target="_blank" rel="noopener">YouTube ↗</a>` : ""}${v.tt_post_id ? `<span class="chip mute">TikTok ✓</span>` : ""}</div></div></div></td>\n        <td>${fmtTs(v.created)}</td>\n        <td class="t w" style="min-width:150px"><span class="chip ${st[1]}">${st[0]}</span>${v.yt_status && v.yt_status !== "public" ? `<div class="hint">YT: ${esc(v.yt_status)}</div>` : ""}${v.tt_status ? `<div class="hint">TT: ${esc(v.tt_status)}</div>` : ""}${v.error ? `<div class="hint neg">${esc(v.error.slice(0, 160))}</div>` : ""}</td>\n        <td>${v.st.youtube ? fmtN(v.st.youtube.views) : "–"}</td><td>${v.st.tiktok ? fmtN(v.st.tiktok.views) : "–"}</td><td>${fmtN(v.likes)}</td>\n        <td><div class="inline">${v.mp4 && ["rendered", "partial", "error"].includes(v.status) ? `<button class="btn sm" onclick="dispatch({action:\'upload\',video_id:\'${v.id}\'},\'Upload läuft\')">Hochladen</button>` : ""}${v.mp4 ? `<a class="btn sm" href="${esc(mp4(v))}" target="_blank" rel="noopener">MP4</a>` : ""}</div></td></tr>`; }).join("")}\n    </tbody></table>` : `<div class="empty">Noch keine Videos. Im Studio kannst du sofort das erste erstellen.</div>`}</div></section>`;\n  const segs = (id, fn) => document.querySelectorAll(`#${id} button`).forEach(b => b.onclick = () => { document.querySelectorAll(`#${id} button`).forEach(x => x.setAttribute("aria-pressed", x === b)); fn(b.dataset.v); drawChart(); });\n  segs("pSeg", v => PLAT = v); segs("rSeg", v => RANGE = +v);\n  drawChart();\n}\nfunction runsList() {\n  const rs = RUNS.filter(r => r.event !== "schedule" || r.conclusion !== "success" || isLive(r)).slice(0, 5);\n  if (!rs.length) return `<p class="hint">Noch keine Aufträge.</p>`;\n  return rs.map(r => `<div><span class="dot ${r.status !== "completed" ? "warn" : r.conclusion === "success" ? "ok" : "bad"}"></span><a href="${esc(r.html_url)}" target="_blank" rel="noopener" style="text-decoration:none">${esc(runName(r))}</a><span class="hint">${new Date(r.created_at).toLocaleString("de-DE", {day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit"})}</span></div>`).join("");\n}\nfunction nice(max) { const r = max || 1, st = Math.pow(10, Math.floor(Math.log10(r / 4))); const m = [1, 2, 2.5, 5, 10].find(x => r / (x * st) <= 5) * st; return {hi: Math.ceil(max / m) * m || m, step: m}; }\nfunction drawChart() {\n  const el = $("#chart"); if (!el) return;\n  const D = dayMap(), labels = lastDays(RANGE), ser = [];\n  if (PLAT !== "tiktok") ser.push({n: "YouTube", c: "var(--yt)", v: labels.map(k => D[k]?.yt || 0)});\n  if (PLAT !== "youtube") ser.push({n: "TikTok", c: "var(--tt)", v: labels.map(k => D[k]?.tt || 0)});\n  const W = 900, H = 250, L = 46, R = 12, T = 12, B = 26, n = labels.length, sc = nice(Math.max(1, ...ser.flatMap(s => s.v)));\n  const x = i => L + (W - L - R) * i / Math.max(1, n - 1), y = v => T + (H - T - B) * (1 - v / sc.hi);\n  let g = ""; for (let v = 0; v <= sc.hi + 1e-9; v += sc.step) g += `<line class="gl" x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/><text x="${L - 8}" y="${y(v) + 4}" text-anchor="end">${kN(v)}</text>`;\n  const every = Math.ceil(n / 8);\n  labels.forEach((k, i) => { if ((i % every === 0 && n - 1 - i >= every * .6) || i === n - 1) { const d = fromKey(k); g += `<text x="${x(i)}" y="${H - 6}" text-anchor="${i === 0 ? "start" : i === n - 1 ? "end" : "middle"}">${d.getDate()}.${d.getMonth() + 1}.</text>`; } });\n  const paths = ser.map(s => { const d = s.v.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("");\n    return `<path d="${d}L${x(n - 1)},${y(0)}L${x(0)},${y(0)}Z" fill="${s.c}" fill-opacity=".07"/><path d="${d}" fill="none" stroke="${s.c}" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/><circle cx="${x(n - 1)}" cy="${y(s.v[n - 1])}" r="4" fill="${s.c}" stroke="var(--surface)" stroke-width="2"/>`; }).join("");\n  const hits = labels.map((k, i) => `<rect x="${x(i) - (W - L - R) / n / 2}" y="${T}" width="${(W - L - R) / n}" height="${H - T - B}" fill="transparent" style="cursor:pointer" onclick="openDay(\'${k}\')"><title>${fromKey(k).toLocaleDateString("de-DE")}: ${ser.map(s => s.n + " " + s.v[i].toLocaleString("de-DE")).join(" · ")}</title></rect>`).join("");\n  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Aufrufe pro Tag">${g}${paths}${hits}</svg>`;\n}\n\n/* ═════════════════ Kalender ═════════════════ */\nlet CALM = (() => { const d = new Date(); return {y: d.getFullYear(), m: d.getMonth()}; })(), SELDAY = null;\nfunction viewCal() {\n  const D = dayMap(), {y, m} = CALM, first = new Date(y, m, 1), days = new Date(y, m + 1, 0).getDate(), todayK = dkey(new Date());\n  const keys = Array.from({length: days}, (_, i) => dkey(new Date(y, m, i + 1)));\n  const tv = keys.reduce((a, k) => a + (D[k] ? D[k].yt + D[k].tt : 0), 0), tl = keys.reduce((a, k) => a + (D[k]?.likes || 0), 0);\n  const made = keys.reduce((a, k) => a + (D[k]?.made?.length || 0), 0);\n  const best = keys.reduce((b, k) => { const v = D[k] ? D[k].yt + D[k].tt : 0; return v > b.v ? {k, v} : b; }, {k: null, v: 0});\n  const past = keys.filter(k => k <= todayK).length || 1;\n  const vmax = Math.max(1, ...keys.map(k => D[k] ? D[k].yt + D[k].tt : 0));\n  const lead = (first.getDay() + 6) % 7, cells = [];\n  for (let i = 0; i < lead; i++) cells.push(null);\n  keys.forEach(k => cells.push(k));\n  while (cells.length % 7) cells.push(null);\n  let grid = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"].map(d => `<div class="dow">${d}</div>`).join("") + `<div class="dow wkh">Woche</div>`;\n  for (let w = 0; w < cells.length / 7; w++) {\n    const wk = cells.slice(w * 7, w * 7 + 7); let wv = 0, wn = 0;\n    grid += wk.map(k => { if (!k) return `<div class="day out"></div>`;\n      const x = D[k], v = x ? x.yt + x.tt : 0, n = x?.made?.length || 0, d = fromKey(k), fut = k > todayK; wv += v; wn += n;\n      return `<button type="button" class="day ${v ? "heat" : ""} ${k === todayK ? "today" : ""} ${fut ? "fut" : ""} ${SELDAY === k ? "sel" : ""}" style="--h:${(v / vmax).toFixed(2)}" onclick="openDay(\'${k}\')" aria-label="${d.toLocaleDateString("de-DE", {weekday: "long", day: "numeric", month: "long"})}">\n        <span class="dn"><b>${d.getDate()}</b>${n ? `<span class="vdots">${"<i></i>".repeat(Math.min(n, 4))}</span>` : ""}</span>\n        ${v ? `<span class="pl">${fmtN(v)}<small>Aufrufe</small></span><span class="meta">♥ ${fmtN(x.likes)}${n ? ` · ${n} Video${n > 1 ? "s" : ""}` : ""}</span>` : n ? `<span class="meta" style="margin-top:auto">${n} Video${n > 1 ? "s" : ""} erstellt</span>` : ""}</button>`; }).join("");\n    grid += `<div class="wk"><span class="dn">KW ${kw(fromKey(wk.find(Boolean)))}</span><span class="pl">${wv ? fmtN(wv) : "–"}</span><span class="meta">${wn} Video${wn === 1 ? "" : "s"}</span></div>`;\n  }\n  $("#main").innerHTML = `\n  <div class="cal-top in"><div class="cal-mon"><button class="ibtn" id="cPrev" aria-label="Vormonat">${icon(I.left)}</button><h2>${MONTHS[m]} <span class="muted" style="font-weight:400">${y}</span></h2><button class="ibtn" id="cNext" aria-label="Nächster Monat">${icon(I.right)}</button></div>\n    <button class="btn" id="cToday">Heute</button></div>\n  <section class="strip in" style="--i:1">\n    <div><span class="l">Aufrufe im ${MONTHS[m]}</span><span class="v big">${fmtN(tv)}</span><span class="s">YouTube und TikTok zusammen</span></div>\n    <div><span class="l">Likes</span><span class="v">${fmtN(tl)}</span><span class="s">${pct(tv ? tl / tv * 100 : NaN)} der Aufrufe</span></div>\n    <div><span class="l">Videos erstellt</span><span class="v">${made}</span><span class="s">in diesem Monat</span></div>\n    <div><span class="l">Ø pro Tag</span><span class="v">${fmtN(tv / past)}</span><span class="s">Aufrufe</span></div>\n    <div><span class="l">Bester Tag</span><span class="v">${best.k ? fromKey(best.k).toLocaleDateString("de-DE", {day: "numeric", month: "short"}) : "–"}</span><span class="s">${best.k ? fmtN(best.v) + " Aufrufe" : "noch keiner"}</span></div>\n  </section>\n  <section class="calbox in" style="--i:2"><div class="cal">${grid}</div></section>\n  <p class="hint in" style="--i:3">Je kräftiger ein Tag gefärbt ist, desto mehr Aufrufe kamen dazu. Punkte zeigen, wie viele Videos an dem Tag erstellt wurden.</p>`;\n  $("#cPrev").onclick = () => { CALM = m ? {y, m: m - 1} : {y: y - 1, m: 11}; viewCal(); };\n  $("#cNext").onclick = () => { CALM = m === 11 ? {y: y + 1, m: 0} : {y, m: m + 1}; viewCal(); };\n  $("#cToday").onclick = () => { const d = new Date(); CALM = {y: d.getFullYear(), m: d.getMonth()}; viewCal(); };\n}\nfunction kw(d) { const t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate())); const n = t.getUTCDay() || 7; t.setUTCDate(t.getUTCDate() + 4 - n); const y0 = new Date(Date.UTC(t.getUTCFullYear(), 0, 1)); return Math.ceil(((t - y0) / 864e5 + 1) / 7); }\nfunction openDay(k) {\n  SELDAY = k; closeDay(true);\n  const D = dayMap(), x = D[k] || {yt: 0, tt: 0, likes: 0, comments: 0, shares: 0, vids: {}}, d = fromKey(k);\n  const made = (x.made || []).map(id => VIDS.find(v => v.id === id)).filter(Boolean);\n  const gains = Object.entries(x.vids || {}).map(([id, g]) => ({v: VIDS.find(v => String(v.id) === id), ...g})).filter(g => g.v && g.views).sort((a, b) => b.views - a.views).slice(0, 8);\n  const prevK = dkey(new Date(d.getFullYear(), d.getMonth(), d.getDate() - 1)), nextK = dkey(new Date(d.getFullYear(), d.getMonth(), d.getDate() + 1));\n  const pv = D[prevK] ? D[prevK].yt + D[prevK].tt : 0, tv = x.yt + x.tt;\n  document.body.insertAdjacentHTML("beforeend", `<div class="drw-bg" id="dayDrw" role="dialog" aria-modal="true" aria-labelledby="dT"><aside class="drw">\n    <div class="drw-h"><button class="ibtn" onclick="openDay(\'${prevK}\')" aria-label="Vortag">${icon(I.left)}</button><div class="drw-t"><span class="l">${d.toLocaleDateString("de-DE", {weekday: "long"})}</span><h2 id="dT">${d.toLocaleDateString("de-DE", {day: "numeric", month: "long", year: "numeric"})}</h2></div>\n      <button class="ibtn" onclick="openDay(\'${nextK}\')" aria-label="Nächster Tag" ${k >= dkey(new Date()) ? "disabled style=\'opacity:.4\'" : ""}>${icon(I.right)}</button><button class="ibtn" onclick="closeDay()" aria-label="Schließen">${icon(I.x)}</button></div>\n    <div class="drw-b">\n      <div class="drw-big"><span class="l">Neue Aufrufe an diesem Tag</span><b>${fmtN(tv)}</b>\n        <span class="delta"><b class="${!pv ? "zero" : tv >= pv ? "pos" : "neg"}">${pv ? (tv >= pv ? "+" : "") + Math.round((tv - pv) / pv * 100) + " %" : "–"}</b> zum Vortag</span></div>\n      <div class="drw-st">\n        <div><span class="l">YouTube</span><b>${fmtN(x.yt)}</b></div><div><span class="l">TikTok</span><b>${fmtN(x.tt)}</b></div><div><span class="l">Likes</span><b>${fmtN(x.likes)}</b></div>\n        <div><span class="l">Kommentare</span><b>${fmtN(x.comments)}</b></div><div><span class="l">Shares</span><b>${fmtN(x.shares)}</b></div><div><span class="l">Neue Follower</span><b>${x.f_youtube == null && x.f_tiktok == null ? "–" : "+" + fmtN((x.f_youtube || 0) + (x.f_tiktok || 0))}</b></div>\n      </div>\n      <div class="drw-list"><span class="l">An diesem Tag erstellt</span>${made.length ? made.map(v => { const c = cat(v.category), st = STATUS[v.status] || [v.status, "mute"];\n        return `<div class="tr">${thumb(v)}<div class="tt"><b>${esc(v.title || v.topic)}</b><small>${esc(c?.emoji || "")} ${esc(c?.name || v.category)} · ${new Date(v.created * 1000).toLocaleTimeString("de-DE", {hour: "2-digit", minute: "2-digit"})} Uhr</small><div><span class="chip ${st[1]}">${st[0]}</span> ${trendChip(v)}</div></div>${v.mp4 ? `<a class="btn sm" href="${esc(mp4(v))}" target="_blank" rel="noopener">MP4</a>` : ""}</div>`; }).join("") : `<div class="empty">Kein Video an diesem Tag erstellt.</div>`}</div>\n      <div class="drw-list"><span class="l">Woher die Aufrufe kamen</span>${gains.length ? gains.map(g => `<div class="tr">${thumb(g.v)}<div class="tt"><b>${esc(g.v.title || g.v.topic)}</b><small>♥ ${fmtN(g.likes)} neue Likes</small></div><span class="gain">+${fmtN(g.views)}</span></div>`).join("") : `<div class="empty">Für diesen Tag gibt es noch keine Zahlen.</div>`}</div>\n    </div></aside></div>`);\n  $("#dayDrw").onclick = e => { if (e.target.id === "dayDrw") closeDay(); };\n  document.querySelectorAll(".day").forEach(b => b.classList.toggle("sel", b.getAttribute("onclick") === `openDay(\'${k}\')`));\n}\nfunction closeDay(keep) { const d = $("#dayDrw"); if (d) d.remove(); if (!keep) { SELDAY = null; document.querySelectorAll(".day.sel").forEach(b => b.classList.remove("sel")); } }\naddEventListener("keydown", e => { if (e.key === "Escape") { closeDay(); document.querySelectorAll(".modal-bg").forEach(m => m.remove()); } });\n\n/* ═════════════════ Studio ═════════════════ */\nlet SEL = null;\nconst VOICES = [["de-DE-FlorianMultilingualNeural", "Florian · locker, männlich"], ["de-DE-ConradNeural", "Conrad · tief, männlich"], ["de-DE-KillianNeural", "Killian · Erzähler, männlich"], ["de-DE-SeraphinaMultilingualNeural", "Seraphina · warm, weiblich"], ["de-DE-KatjaNeural", "Katja · klar, weiblich"], ["de-DE-AmalaNeural", "Amala · jung, weiblich"]];\nfunction viewStudio() {\n  const used = new Set(ST.used_queue || []), queue = (CFG.queue || []).filter(q => !used.has(q.id)).sort((a, b) => a.created - b.created);\n  const counts = {}; VIDS.forEach(v => counts[v.category] = (counts[v.category] || 0) + 1);\n  if (!SEL || !cat(SEL)) SEL = (CFG.categories[0] || {}).slug;\n  $("#main").innerHTML = `\n  <section class="panel in"><div class="section-h"><div><h2>Neues Video</h2><p class="hint">Video-Art antippen, Thema eingeben oder leer lassen, dann erstellen. GitHub braucht dafür etwa 5–15 Minuten.</p></div></div>\n    <div class="cats" role="radiogroup" aria-label="Video-Art">${CFG.categories.map((c, i) => `\n      <div class="cat ${c.enabled ? "" : "off"} ${SEL === c.slug ? "sel" : ""}" role="radio" tabindex="0" aria-checked="${SEL === c.slug}" data-slug="${esc(c.slug)}">\n        <div class="cat-h"><span class="e" aria-hidden="true">${esc(c.emoji)}</span><span class="chip ${c.enabled ? "good" : "mute"}">${c.enabled ? "im Autopilot" : "pausiert"}</span></div>\n        <h3>${esc(c.name)}</h3><p>${esc(c.description)}</p>\n        <div class="row2"><span class="chip mute">${counts[c.slug] || 0} Videos</span><button class="btn sm" type="button" data-tog="${i}">${c.enabled ? "Pausieren" : "In Autopilot"}</button><button class="btn sm" type="button" data-edit="${i}">Bearbeiten</button></div>\n      </div>`).join("")}\n      <button class="cat" type="button" id="newCat" style="align-items:center;justify-content:center;border-style:dashed;box-shadow:none;min-height:150px"><span class="e">${icon(I.plus)}</span><b>Neue Video-Art</b><span class="hint">z. B. Weltraum oder Geschichte</span></button>\n    </div>\n    <div class="make"><label>Thema (optional)<input id="topic" maxlength="300" placeholder="Leer lassen, dann sucht die KI ein Thema aus (bei Trend-Kategorien oft ein aktuelles)"><span class="hint" id="topicTrend" hidden></span></label>\n      <label class="check"><input type="checkbox" id="upl" checked> direkt hochladen</label>\n      <button class="btn accent" id="mk" style="padding:11px 20px">${icon(I.spark)}Video erstellen</button></div>\n  </section>\n  <section class="panel in" style="--i:1" id="trendBox">\n    <div class="section-h"><div><h2>Aktuell im Trend</h2><p class="hint">Was Deutschland gerade sucht und liest${TRENDS.updated ? " · Stand " + fmtTs(TRENDS.updated) : ""}. Die KI macht daraus ein passendes, sicheres Thema.</p></div>\n      <div class="inline"><div class="seg" id="tSeg">${["Alle", "Google Trends", "Wikipedia", "YouTube"].map(k => `<button type="button" data-v="${k}" aria-pressed="${TSRC === k}">${k === "Google Trends" ? "Google" : k}</button>`).join("")}</div><button class="btn" id="tRef">${icon(I.reload)}Aktualisieren</button></div></div>\n    <div class="trends" id="tList"></div>\n  </section>\n  <div class="grid2">\n    <section class="panel in" style="--i:2"><div><h2>Themen-Warteschlange</h2><p class="hint">Der Autopilot nimmt diese Themen der Reihe nach, bevor er selbst welche sucht.</p></div>\n      <div>${queue.length ? queue.map(q => `<div class="qrow"><div><span class="chip">${esc(cat(q.category)?.emoji || "")} ${esc(cat(q.category)?.name || q.category)}</span>${q.trend ? \' <span class="chip acc">🔥 Trend</span>\' : ""} ${esc(q.text)}</div><button class="ibtn" data-delq="${esc(q.id)}" aria-label="Entfernen">${icon(I.x)}</button></div>`).join("") : `<div class="empty">Leer – die KI denkt sich passende Themen selbst aus.</div>`}</div></section>\n    <section class="panel in" style="--i:3"><div><h2>Themen einplanen</h2><p class="hint">Für die nächsten Tage vormerken, eins pro Zeile.</p></div>\n      <select id="qcat" aria-label="Kategorie">${CFG.categories.map(c => `<option value="${esc(c.slug)}">${esc(c.emoji)} ${esc(c.name)}</option>`).join("")}</select>\n      <textarea id="qtext" placeholder="Was passiert, wenn man nie schläft?&#10;Die Legende vom Klabautermann"></textarea>\n      <div><button class="btn primary" id="qadd">Zur Warteschlange</button></div></section>\n  </div>`;\n  document.querySelectorAll(".cat[data-slug]").forEach(el => { const pick = () => { SEL = el.dataset.slug; document.querySelectorAll(".cat[data-slug]").forEach(o => { o.classList.toggle("sel", o === el); o.setAttribute("aria-checked", o === el); }); };\n    el.onclick = e => { if (!e.target.closest("button")) pick(); }; el.onkeydown = e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); } }; });\n  document.querySelectorAll("[data-tog]").forEach(b => b.onclick = () => { const c = CFG.categories[+b.dataset.tog]; c.enabled = !c.enabled; persist("Kategorie " + c.name, b); });\n  document.querySelectorAll("[data-edit]").forEach(b => b.onclick = () => catModal(+b.dataset.edit));\n  document.querySelectorAll("[data-delq]").forEach(b => b.onclick = () => { CFG.queue = CFG.queue.filter(q => q.id !== b.dataset.delq); persist("Thema entfernt", b); });\n  $("#newCat").onclick = () => catModal(-1);\n  drawTrends();\n  document.querySelectorAll("#tSeg button").forEach(b => b.onclick = () => { TSRC = b.dataset.v; document.querySelectorAll("#tSeg button").forEach(x => x.setAttribute("aria-pressed", x === b)); drawTrends(); });\n  $("#tRef").onclick = () => dispatch({action: "trends"}, "Trends werden gesammelt");\n  $("#topic").addEventListener("input", () => { if (TOPIC_TREND) { TOPIC_TREND = null; $("#topicTrend").hidden = true; } });\n  $("#mk").onclick = async () => { const b = $("#mk"); b.disabled = true;\n    const ok = await dispatch({action: "make", category: SEL || "", topic: $("#topic").value.trim(), upload: $("#upl").checked ? "1" : "0", trend: TOPIC_TREND ? TOPIC_TREND.id : ""}, "Video wird erstellt");\n    b.disabled = false; if (ok) { $("#topic").value = ""; TOPIC_TREND = null; $("#topicTrend").hidden = true; toast("Auftrag gesendet. Oben siehst du den Fortschritt."); scrollTo({top: 0, behavior: "smooth"}); } };\n  $("#qadd").onclick = () => { const t = $("#qtext").value.split("\\n").map(s => s.trim()).filter(Boolean); if (!t.length) return toast("Bitte mindestens ein Thema eingeben.", true);\n    const now = Date.now() / 1000; t.forEach((x, i) => CFG.queue.push({id: "q" + Math.random().toString(36).slice(2, 10), category: $("#qcat").value, text: x.slice(0, 300), created: now + i})); persist("Themen eingeplant", $("#qadd")); };\n}\nlet TSRC = "Alle", TOPIC_TREND = null;\nfunction drawTrends() {\n  const el = $("#tList"); if (!el) return;\n  const items = (TRENDS.items || []).filter(t => TSRC === "Alle" || t.source === TSRC).slice(0, 18);\n  if (!items.length) { el.innerHTML = `<div class="empty">${TRENDS.updated ? "In dieser Quelle gerade nichts." : "Noch keine Trends geholt. Tippe auf „Aktualisieren“, das dauert etwa eine Minute."}</div>`; return; }\n  el.innerHTML = items.map(t => `<div class="trend"><div class="tt"><div><span class="chip ${t.source === "Google Trends" ? "acc" : "mute"}">${esc(t.source === "Google Trends" ? "Google" : t.source)}</span>${t.traffic ? ` <span class="hint">${esc(t.traffic)}</span>` : ""}</div>\n      <b>${esc(t.title)}</b>${(t.news || [])[0] ? `<small>${esc(t.news[0].title)}${t.news[0].source ? " · " + esc(t.news[0].source) : ""}</small>` : t.summary ? `<small>${esc(t.summary.slice(0, 140))}</small>` : ""}</div>\n    <div class="inline"><button class="btn sm primary" data-tuse="${esc(t.id)}">Als Thema</button><button class="btn sm" data-tq="${esc(t.id)}">Einplanen</button></div></div>`).join("");\n  const find = id => (TRENDS.items || []).find(t => t.id === id);\n  el.querySelectorAll("[data-tuse]").forEach(b => b.onclick = () => { const t = find(b.dataset.tuse); TOPIC_TREND = t;\n    $("#topic").value = t.title; $("#topicTrend").hidden = false; $("#topicTrend").textContent = "🔥 Aktueller Anlass – die KI macht daraus ein passendes Thema für die gewählte Video-Art.";\n    $("#topic").scrollIntoView({behavior: "smooth", block: "center"}); });\n  el.querySelectorAll("[data-tq]").forEach(b => b.onclick = () => { const t = find(b.dataset.tq);\n    CFG.queue.push({id: "q" + Math.random().toString(36).slice(2, 10), category: SEL || CFG.categories[0].slug, text: t.title, created: Date.now() / 1000,\n      trend: {title: t.title, source: t.source, news: (t.news || []).slice(0, 3), summary: t.summary || ""}});\n    persist("Trend eingeplant: " + t.title, b); });\n}\nfunction catModal(i) {\n  const c = i >= 0 ? CFG.categories[i] : {emoji: "🎬", name: "", description: "", script_style: "", image_mood: "", voice: "de-DE-FlorianMultilingualNeural", voice_rate: "+6%", voice_pitch: "+0Hz", voice_instructions: ""};\n  document.body.insertAdjacentHTML("beforeend", `<div class="modal-bg" id="cm"><div class="modal" role="dialog" aria-modal="true" aria-labelledby="cmT" style="max-width:560px">\n    <h2 id="cmT" style="font-size:19px">${i >= 0 ? "Video-Art bearbeiten" : "Neue Video-Art"}</h2>\n    <div style="display:grid;grid-template-columns:70px 1fr;gap:10px"><input id="ce" value="${esc(c.emoji)}" aria-label="Emoji"><input id="cn" value="${esc(c.name)}" placeholder="Name" aria-label="Name"></div>\n    <input id="cd" value="${esc(c.description)}" placeholder="Kurzbeschreibung" aria-label="Kurzbeschreibung">\n    <label class="hint">Wie sollen die Videos erzählt werden?<textarea id="cs" rows="4">${esc(c.script_style)}</textarea></label>\n    <label class="hint">Bild-Stimmung (Englisch)<textarea id="cmo" rows="2">${esc(c.image_mood)}</textarea></label>\n    <div style="display:grid;grid-template-columns:1fr 90px 90px;gap:10px"><select id="cv" aria-label="Stimme">${VOICES.map(([v, l]) => `<option value="${v}" ${c.voice === v ? "selected" : ""}>${l}</option>`).join("")}</select>\n      <input id="cr" value="${esc(c.voice_rate || "+0%")}" aria-label="Tempo" title="Tempo"><input id="cp" value="${esc(c.voice_pitch || "+0Hz")}" aria-label="Tonhöhe" title="Tonhöhe"></div>\n    <input id="ci" value="${esc(c.voice_instructions || "")}" placeholder="Sprechweise für die OpenAI-Stimme (Premium)" aria-label="Sprechweise">\n    <label class="check"><input type="checkbox" id="ctr" ${("trends" in c ? c.trends : ["fakten", "storys", "mysterien", "tiere"].includes(c.slug)) ? "checked" : ""}> Aktuelle Trends für diese Video-Art nutzen</label>\n    <div class="actions"><button class="btn primary" id="cmS">Speichern</button>${i >= 0 ? `<button class="btn danger" id="cmD">Löschen</button>` : ""}<button class="btn" id="cmX">Abbrechen</button></div>\n  </div></div>`);\n  $("#cn").focus();\n  $("#cmX").onclick = () => $("#cm").remove();\n  $("#cm").onclick = e => { if (e.target.id === "cm") $("#cm").remove(); };\n  if ($("#cmD")) $("#cmD").onclick = () => { const b = $("#cmD"); if (b.dataset.sure !== "1") { b.dataset.sure = "1"; b.textContent = "Wirklich löschen?"; return; }\n    CFG.categories.splice(i, 1); $("#cm").remove(); persist("Video-Art gelöscht"); };\n  $("#cmS").onclick = () => {\n    const v = id => $(id).value.trim(), n = {emoji: v("#ce") || "🎬", name: v("#cn"), description: v("#cd"), script_style: v("#cs"), image_mood: v("#cmo"), voice: v("#cv"), voice_rate: v("#cr") || "+0%", voice_pitch: v("#cp") || "+0Hz", voice_instructions: v("#ci"), trends: $("#ctr").checked};\n    if (!n.name) return toast("Bitte einen Namen eingeben.", true);\n    if (i >= 0) Object.assign(CFG.categories[i], n);\n    else { let slug = n.name.toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "").slice(0, 18) || "art"; while (cat(slug)) slug += "2"; CFG.categories.push({slug, ...n, enabled: true}); SEL = slug; }\n    $("#cm").remove(); persist("Video-Art " + n.name);\n  };\n}\n\n/* ═════════════════ Einstellungen ═════════════════ */\nconst OPEN = new Set(["zeit"]);\nlet DIRTY = false;\nconst SECRET_LIST = [\n  ["GEMINI_API_KEY", "Gemini API-Key", "Skripte · kostenlos", "https://aistudio.google.com/apikey"],\n  ["CLOUDFLARE_ACCOUNT_ID", "Cloudflare Account-ID", "Bilder · kostenlos", "https://dash.cloudflare.com/?to=/:account/ai/workers-ai"],\n  ["CLOUDFLARE_API_TOKEN", "Cloudflare API-Token", "Vorlage „Workers AI“", "https://dash.cloudflare.com/profile/api-tokens"],\n  ["GOOGLE_CLIENT_SECRET", "Google Client-Secret", "für YouTube", "https://console.cloud.google.com/apis/credentials"],\n  ["TIKTOK_CLIENT_SECRET", "TikTok Client-Secret", "für TikTok", "https://developers.tiktok.com/apps"],\n  ["OPENAI_API_KEY", "OpenAI API-Key", "nur Premium", "https://platform.openai.com/api-keys"],\n  ["ELEVENLABS_API_KEY", "ElevenLabs API-Key", "nur Premium", "https://elevenlabs.io/app/settings/api-keys"]];\nconst hasSecret = n => SECRETS instanceof Set ? SECRETS.has(n) : null;\nfunction cost() {\n  const q = {low: .016, medium: .063, high: .25}[S_("openai_image_quality")] || .016, n = Math.max(6, Math.round((S_("target_seconds") || 70) / 5));\n  return ({openai: .003}[S_("text_provider")] || 0) + ({openai: .021, elevenlabs: .16}[S_("tts_provider")] || 0) + (S_("image_provider") === "openai" ? q * n : 0);\n}\nfunction sec(id, ic, title, sub, chip, body) {\n  return `<details class="set-sec in" id="s-${id}" ${OPEN.has(id) ? "open" : ""}><summary><span class="s-ic">${icon(ic)}</span><span class="s-t"><b>${title}</b><span class="hint">${sub}</span></span><span class="s-chip">${chip || ""}</span></summary><div class="set-b">${body}</div></details>`;\n}\nconst tgl = (k, label, help) => `<div class="row"><label>${label}${help ? `<small>${help}</small>` : ""}</label><button type="button" class="tgl" role="switch" data-k="${k}" aria-checked="${!!S_(k)}" aria-label="${esc(label)}"></button></div>`;\nconst fld = (k, label, help, attrs) => `<div class="row"><label for="f_${k}">${label}${help ? `<small>${help}</small>` : ""}</label><input id="f_${k}" data-k="${k}" value="${esc(S_(k))}" ${attrs || ""}></div>`;\nconst sel = (k, label, help, opts) => `<div class="row"><label for="f_${k}">${label}${help ? `<small>${help}</small>` : ""}</label><select id="f_${k}" data-k="${k}">${opts.map(([v, l]) => `<option value="${v}" ${String(S_(k)) === v ? "selected" : ""}>${l}</option>`).join("")}</select></div>`;\nconst radio = (k, opts) => `<div class="prov">${opts.map(([v, b, s]) => `<label><input type="radio" name="${k}" data-k="${k}" value="${v}" ${S_(k) === v ? "checked" : ""}><span><b>${b}</b><small>${s}</small></span></label>`).join("")}</div>`;\nfunction viewSettings() {\n  const con = ST.connected || {}, c = cost(), U = S.update || {};\n  const updChip = U.available ? `<span class="chip warn">Version ${esc(U.version)} verfügbar</span>` : U.error && U.checked ? `<span class="chip bad">Prüfung fehlgeschlagen</span>` : `<span class="chip good">aktuell</span>`;\n  const missing = ["GEMINI_API_KEY", "CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN"].filter(n => hasSecret(n) === false).length;\n  const platBlock = (p, name, idKey, secName, idLabel, help) => {\n    const ready = S_(idKey) && S.local_secrets[p];\n    return `<div class="lbl">${name}</div>\n    <div class="row"><label>Status<small>${con[p] ? "Verbunden" + (con[p].name ? " mit „" + esc(con[p].name) + "“" : "") + ". Der Autopilot lädt hier automatisch hoch." : help}</small></label>\n      <div class="inline">${con[p] ? \'<span class="chip good">verbunden</span>\' : \'<span class="chip mute">nicht verbunden</span>\'}<button class="btn ${con[p] ? "" : "primary"}" type="button" data-oauth="${p}" ${ready ? "" : "disabled"}>${con[p] ? "Neu verbinden" : "Verbinden"}</button></div></div>\n    ${ready ? "" : `<p class="hint">Zum Verbinden: ${idLabel} hier eintragen und speichern, außerdem <b>${secName}</b> unter „Zugangsdaten“ auf diesem PC eintragen.</p>`}\n    ${fld(idKey, idLabel, "", \'placeholder="eintragen"\')}`;\n  };\n  $("#main").innerHTML = `<div class="settings-wrap">\n  ${sec("zeit", I.clock, "Zeitplan", `${S_("autopilot") ? "Autopilot an · " + esc(S_("upload_times")) + " Uhr" : "Autopilot aus"} · ${S_("target_seconds")} Sekunden`, S_("autopilot") ? \'<span class="chip good">an</span>\' : \'<span class="chip warn">aus</span>\', `\n    ${tgl("autopilot", "Autopilot", "Jeden Tag automatisch ein Video erstellen und hochladen. Läuft auf GitHub, auch wenn dieser PC aus ist.")}\n    ${fld("upload_times", "Upload-Zeiten", "Deutsche Zeit. Mehrere mit Komma, z. B. 12:00, 18:30. GitHub startet manchmal bis zu einer Stunde später.")}\n    ${fld("target_seconds", "Ziel-Länge in Sekunden", "TikTok zahlt im Creator-Programm nur für Videos über 1 Minute.", \'type="number" min="20" max="170"\')}`)}\n  ${sec("trend", I.spark, "Trends & Thumbnail", `Trend-Themen ${{off: "aus", half: "jedes 2. Video", always: "immer"}[S_("trend_mode") || "half"]} · Thumbnail ${S_("make_thumbnail") !== false ? "an" : "aus"}`, "", `\n    ${sel("trend_mode", "Aktuelle Trend-Themen", "Der Autopilot schaut bei Google Trends, Wikipedia und YouTube, was gerade gefragt ist, und macht daraus ein passendes Thema. Tragische Nachrichten, Politik und Klatsch werden ausgelassen. Welche Video-Arten Trends nutzen, stellst du im Studio unter „Bearbeiten“ ein.", [["half", "Jedes zweite Video"], ["always", "Immer, wenn ein Trend passt"], ["off", "Aus – nur zeitlose Themen"]])}\n    ${tgl("make_thumbnail", "Eigenes Thumbnail gestalten", "Ein eigenes KI-Bild mit großem Text passend zum Thema. Wird bei TikTok als Titelbild gesetzt.")}\n    ${tgl("youtube_thumbnail", "Thumbnail auf YouTube hochladen", "Geht erst, wenn dein Kanal per Telefon bestätigt ist (youtube.com/verify). Bei Shorts zeigt YouTube es vor allem in Suche und Kanalseite.")}`)}\n  ${sec("plattform", I.plug, "Plattformen", `YouTube ${con.youtube ? "verbunden" : "nicht verbunden"} · TikTok ${con.tiktok ? "verbunden" : "nicht verbunden"}`, con.youtube && con.tiktok ? \'<span class="chip good">beide</span>\' : \'<span class="chip warn">offen</span>\', `\n    ${platBlock("youtube", "YouTube Shorts", "youtube_client_id", "GOOGLE_CLIENT_SECRET", "Google Client-ID", "Google Cloud: OAuth-Client vom Typ „Desktop-App“ anlegen. Die Anleitung steht im Repository (README).")}\n    ${tgl("youtube_enabled", "Auf YouTube hochladen")}\n    ${sel("youtube_privacy", "Sichtbarkeit", "Bis Google dein Projekt geprüft hat, setzt YouTube API-Uploads auf „Privat“.", [["public", "Öffentlich"], ["unlisted", "Nicht gelistet"], ["private", "Privat"]])}\n    ${sel("youtube_category", "YouTube-Kategorie", "", [["24", "Unterhaltung"], ["27", "Bildung"], ["22", "Menschen & Blogs"], ["28", "Wissenschaft & Technik"], ["15", "Tiere"], ["23", "Comedy"]])}\n    <div class="sep"></div>\n    ${platBlock("tiktok", "TikTok", "tiktok_client_key", "TIKTOK_CLIENT_SECRET", "TikTok Client Key", "TikTok-Developer-App mit Login Kit (Plattform Desktop) und Content Posting API.")}\n    <p class="hint">Weiterleitungs-URL für die TikTok-App: <code>${esc(S.redirect)}</code></p>\n    ${tgl("tiktok_enabled", "Auf TikTok hochladen")}\n    ${sel("tiktok_mode", "Art des Uploads", "Bei „Entwurf“ bekommst du das Video in der TikTok-App und postest mit einem Tipp.", [["direct", "Direkt veröffentlichen"], ["inbox", "Als Entwurf in die TikTok-App"]])}\n    ${sel("tiktok_privacy", "Sichtbarkeit", "Ohne TikTok-Prüfung ist nur „Nur ich“ erlaubt.", [["PUBLIC_TO_EVERYONE", "Öffentlich (nach Prüfung)"], ["MUTUAL_FOLLOW_FRIENDS", "Freunde"], ["FOLLOWER_OF_CREATOR", "Follower"], ["SELF_ONLY", "Nur ich"]])}\n    <div class="sep"></div>\n    ${tgl("ai_label", "Als KI-generiert kennzeichnen", "TikTok „AI-generated“ und YouTube „Synthetische Inhalte“.")}`)}\n  ${sec("ki", I.spark, "KI-Anbieter", `Skript ${S_("text_provider")} · Stimme ${S_("tts_provider")} · Bilder ${S_("image_provider")}`, c ? `<span class="chip warn">≈ ${c.toFixed(2).replace(".", ",")} $ / Video</span>` : \'<span class="chip good">gratis</span>\', `\n    <p class="hint">Starte kostenlos. Sobald Geld reinkommt, schaltest du einzelne Schritte auf Premium. Fällt ein Anbieter aus, nimmt der Motor automatisch den kostenlosen.</p>\n    <div class="lbl">Skript</div>${radio("text_provider", [["gemini", "Google Gemini", "Kostenlos · gute Texte"], ["pollinations", "Pollinations", "Kostenlos ohne Anmeldung · einfacher"], ["openai", "OpenAI · Premium", "≈ 0,3 Cent pro Video"]])}\n    <div class="lbl">Stimme</div>${radio("tts_provider", [["edge", "Microsoft Edge-Stimmen", "Kostenlos · je Video-Art einstellbar"], ["openai", "OpenAI · Premium", "≈ 2 Cent pro Video"], ["elevenlabs", "ElevenLabs · Premium", "Beste Stimmen · Abo ab ca. 5 $"]])}\n    <div class="lbl">Bilder</div>${radio("image_provider", [["cloudflare", "Cloudflare FLUX", "Kostenlos · Tageskontingent"], ["pollinations", "Pollinations", "Kostenlos · niedrigere Auflösung"], ["openai", "OpenAI · Premium", "Beste Qualität · ab ≈ 20 Cent"]])}\n    <div class="sep"></div>\n    ${fld("gemini_model", "Gemini-Modell")}${fld("openai_text_model", "OpenAI Text-Modell")}${fld("openai_image_model", "OpenAI Bild-Modell")}\n    ${sel("openai_image_quality", "OpenAI Bildqualität", "", [["low", "low"], ["medium", "medium"], ["high", "high"]])}\n    ${fld("openai_tts_model", "OpenAI Stimm-Modell")}${fld("openai_voice", "OpenAI Stimme", "z. B. ash, coral, onyx, sage")}${fld("elevenlabs_voice_id", "ElevenLabs Voice-ID")}`)}\n  ${sec("stil", I.brush, "Video-Stil", "Cartoon-Bildstil, Hauptfigur, Untertitel, Musik", "", `\n    <label class="hint">Bildstil (Englisch)<textarea data-k="image_style" rows="3">${esc(S_("image_style"))}</textarea></label>\n    ${tgl("use_main_character", "Wiederkehrende Hauptfigur", "Gibt dem Kanal ein Gesicht und Wiedererkennung.")}\n    <label class="hint">Hauptfigur (Englisch)<textarea data-k="main_character" rows="2">${esc(S_("main_character"))}</textarea></label>\n    ${tgl("subtitles_lowercase", "Untertitel kleingeschrieben", "Wie im Beispielvideo.")}\n    ${fld("music_volume", "Musik-Lautstärke", "0 bis 0,3. Musik-Dateien legst du im Repository in den Ordner music/.")}`)}\n  ${sec("keys", I.key, "Zugangsdaten", "Schlüssel werden verschlüsselt in GitHub gespeichert", missing ? `<span class="chip warn">${missing} fehlen</span>` : SECRETS === "err" ? \'<span class="chip mute">?</span>\' : \'<span class="chip good">vollständig</span>\', `\n    <p class="hint">Eintragen und auf „Speichern“ tippen. Die App verschlüsselt den Schlüssel und legt ihn direkt in deinem Repository ab; man kann ihn danach nicht mehr auslesen.</p>\n    ${SECRET_LIST.map(([n, l, h, u]) => { const has = hasSecret(n), loc = n === "GOOGLE_CLIENT_SECRET" ? S.local_secrets.youtube : n === "TIKTOK_CLIENT_SECRET" ? S.local_secrets.tiktok : null;\n      return `<div class="sec-row"><div><b>${l}</b><small>${h} · <a href="${u}" target="_blank" rel="noopener">holen ↗</a></small></div>\n        <input type="password" autocomplete="off" id="sv_${n}" placeholder="${has ? "hinterlegt – zum Ändern neu eintragen" : "einfügen"}">\n        <div class="inline">${has === true ? `<span class="chip good">✓</span>` : has === false ? `<span class="chip mute">fehlt</span>` : ""}${loc === false && has ? `<span class="chip warn" title="Für das Verbinden auf diesem PC noch einmal eintragen">PC</span>` : ""}<button class="btn sm primary" data-secret="${n}">Speichern</button></div></div>`; }).join("")}\n    ${SECRETS === "err" ? `<p class="hint neg">Die App kann nicht sehen, welche Schlüssel hinterlegt sind: Dem GitHub-Zugangsschlüssel fehlt die Berechtigung „Secrets“.</p>` : ""}`)}\n  ${sec("github", I.gh, "GitHub", `${esc(S.owner)}/${esc(S.repo)}`, \'<span class="chip good">verbunden</span>\', `\n    <div class="row"><label>Repository<small>Hier liegen Motor, Daten und fertige Videos.</small></label><div class="inline"><a class="btn" href="https://github.com/${esc(S.owner)}/${esc(S.repo)}" target="_blank" rel="noopener">Öffnen ↗</a></div></div>\n    <div class="row"><label>Alle Läufe<small>Protokolle jedes Auftrags auf GitHub Actions.</small></label><div class="inline"><a class="btn" href="https://github.com/${esc(S.owner)}/${esc(S.repo)}/actions" target="_blank" rel="noopener">Ansehen ↗</a></div></div>\n    <div class="row"><label>Zugangsschlüssel auf diesem PC löschen<small>Danach fragt die App beim Start erneut danach.</small></label><button class="btn danger" id="ghOut">Abmelden</button></div>`)}\n  ${sec("app", I.app, "App & Updates", `Version ${esc(S.version)} · Desktop-Symbol · Protokoll`, updChip, `\n    <div class="row"><label>Installierte Version<small>${U.checked ? "Zuletzt geprüft: " + fmtTs(U.checked) : "Die App prüft bei jedem Start und alle 3 Stunden."}</small></label><div class="inline"><b>${esc(S.version)}</b>${updChip}</div></div>\n    <div class="row"><label>Nach Updates suchen und installieren<small>${U.available && U.notes ? esc(U.notes) : "Deine Einstellungen und Videos bleiben erhalten."}</small></label><button class="btn primary" id="updNow">${U.available ? "Jetzt aktualisieren" : "Nach Updates suchen"}</button></div>\n    <div class="row"><label>Updates automatisch installieren<small>Installiert neue Versionen selbst, aber nie während du die App benutzt.</small></label><button class="tgl" role="switch" id="autoUpd" aria-checked="${!!S.auto_update}" aria-label="Updates automatisch installieren"></button></div>\n    <div class="row"><label>Programmdatei<small>Auf diese Datei zeigt das Desktop-Symbol. Andere Kopien (z. B. in Downloads) kannst du löschen.</small></label><div class="inline"><code style="font-size:11px;word-break:break-all;text-align:right">${esc(S.launcher)}</code></div></div>\n    ${S.platform.startsWith("win") ? `<div class="row"><label>Desktop-Symbol<small>Legt „AutoShorts“ auf dem Desktop und im Startmenü neu an.</small></label><button class="btn" id="mkIcon">Desktop-Symbol anlegen</button></div>` : ""}\n    <div class="row"><label>Protokoll<small>Was die App auf diesem PC gemacht hat.</small></label><button class="btn" id="showLog">Anzeigen</button></div>\n    <div class="row"><label>AutoShorts beenden<small>Die App beendet sich auch von selbst, wenn kein Fenster mehr offen ist. Die Videos macht GitHub trotzdem weiter.</small></label><button class="btn danger" id="quit">App beenden</button></div>`)}\n  </div>\n  <div class="savebar" id="savebar" hidden><span class="hint">Ungespeicherte Änderungen</span><div class="inline"><button class="btn sm" id="sbX">Verwerfen</button><button class="btn accent" id="sbS">Speichern</button></div></div>`;\n  document.querySelectorAll("details.set-sec").forEach(d => d.ontoggle = () => { const id = d.id.slice(2); d.open ? OPEN.add(id) : OPEN.delete(id); });\n  const dirty = () => { DIRTY = true; $("#savebar").hidden = false; };\n  document.querySelectorAll(".tgl[data-k]").forEach(b => b.onclick = () => { b.setAttribute("aria-checked", b.getAttribute("aria-checked") !== "true"); dirty(); });\n  document.querySelectorAll("input[data-k],select[data-k],textarea[data-k]").forEach(el => el.addEventListener("input", dirty));\n  $("#sbX").onclick = () => { DIRTY = false; viewSettings(); };\n  $("#sbS").onclick = () => {\n    document.querySelectorAll(".tgl[data-k]").forEach(b => CFG.settings[b.dataset.k] = b.getAttribute("aria-checked") === "true");\n    document.querySelectorAll("input[data-k]:not([type=radio]),select[data-k],textarea[data-k]").forEach(el => CFG.settings[el.dataset.k] = el.value.trim());\n    document.querySelectorAll("input[type=radio][data-k]:checked").forEach(el => CFG.settings[el.dataset.k] = el.value);\n    CFG.settings.target_seconds = Math.min(170, Math.max(20, parseInt(CFG.settings.target_seconds) || 70));\n    CFG.settings.music_volume = Math.min(.3, Math.max(0, parseFloat(String(CFG.settings.music_volume).replace(",", ".")) || 0));\n    DIRTY = false; persist("Einstellungen", $("#sbS"));\n  };\n  document.querySelectorAll("[data-secret]").forEach(b => b.onclick = async () => {\n    const n = b.dataset.secret, inp = $("#sv_" + n); if (!inp.value.trim()) return toast("Bitte zuerst den Wert einfügen.", true);\n    b.disabled = true;\n    try { await api("/api/secret", {name: n, value: inp.value}); inp.value = ""; toast("Gespeichert: " + n); OPEN.add("keys");\n      if (SECRETS instanceof Set) SECRETS.add(n); S = await api("/api/state"); viewSettings(); }\n    catch (e) { toast(e.message, true); b.disabled = false; }\n  });\n  document.querySelectorAll("[data-oauth]").forEach(b => b.onclick = async () => {\n    if (DIRTY) return toast("Bitte zuerst die Einstellungen speichern.", true);\n    const p = b.dataset.oauth;\n    try { const r = await api("/api/oauth/start", {platform: p, client_id: S_(p === "youtube" ? "youtube_client_id" : "tiktok_client_key"), mode: S_("tiktok_mode") || "direct"}); location.href = r.url; }\n    catch (e) { toast(e.message, true); }\n  });\n  $("#ghOut").onclick = () => armed($("#ghOut"), "Sicher? Nochmal tippen", async () => { await api("/api/github/logout", {}); S = await api("/api/state"); render(); });\n  $("#updNow").onclick = async () => { const b = $("#updNow"); b.disabled = true;\n    try { const u = await api("/api/update/check", {}); S.update = u; if (u.available) return runUpdate(); toast(u.error || "Du hast die neueste Version."); viewSettings(); }\n    catch (e) { toast(e.message, true); } finally { b.disabled = false; } };\n  $("#autoUpd").onclick = async () => { const on = $("#autoUpd").getAttribute("aria-checked") !== "true"; $("#autoUpd").setAttribute("aria-checked", on); await api("/api/settings", {auto_update: on}); S.auto_update = on; toast(on ? "Updates werden automatisch installiert" : "Updates nur auf Knopfdruck"); };\n  if ($("#mkIcon")) $("#mkIcon").onclick = async () => { try { await api("/api/shortcut", {}); toast("Desktop-Symbol angelegt"); } catch (e) { toast(e.message, true); } };\n  $("#showLog").onclick = async () => { const r = await api("/api/log", {});\n    document.body.insertAdjacentHTML("beforeend", `<div class="modal-bg" id="lg"><div class="modal"><h2>Protokoll</h2><pre class="logbox">${esc(r.log || "Noch leer.")}</pre><div class="actions"><button class="btn" onclick="$(\'#lg\').remove()">Schließen</button></div></div></div>`);\n    const lb = $(".logbox"); lb.scrollTop = lb.scrollHeight; };\n  $("#quit").onclick = () => armed($("#quit"), "Wirklich beenden?", async () => { await api("/api/quit", {}); document.body.innerHTML = `<div class="login"><div class="panel" style="max-width:420px"><h2>AutoShorts ist beendet</h2><p class="hint">Du kannst dieses Fenster schließen. Die Videos macht GitHub weiter.</p></div></div>`; });\n}\nfunction armed(btn, q, fn) { if (btn.dataset.sure === "1") return fn(); btn.dataset.sure = "1"; const t = btn.textContent; btn.textContent = q; setTimeout(() => { btn.dataset.sure = ""; btn.textContent = t; }, 4000); }\n\n/* ═════════════════ Updates ═════════════════ */\nasync function runUpdate() {\n  const before = S.version;\n  document.body.insertAdjacentHTML("beforeend", `<div id="updOv" style="position:fixed;inset:0;z-index:70;background:var(--bg);display:grid;place-items:center;padding:16px">\n    <div style="text-align:center;max-width:380px;display:flex;flex-direction:column;gap:10px;align-items:center"><span class="spin" style="width:26px;height:26px;border-width:3px"></span>\n      <h2 style="font-size:20px" id="updT">Update wird geladen …</h2><p class="hint" id="updMsg">Die neue Version wird heruntergeladen und geprüft.</p><div id="updAct"></div></div></div>`);\n  const msg = (t, m, act) => { $("#updT").textContent = t; $("#updMsg").innerHTML = m; $("#updAct").innerHTML = act || ""; };\n  let res;\n  try { res = await api("/api/update/apply", {}); } catch (e) {\n    $("#updOv .spin").remove(); msg("Update fehlgeschlagen", esc(e.message), \'<button class="btn" id="updClose">Schließen</button>\'); $("#updClose").onclick = () => $("#updOv").remove(); return; }\n  msg("Neustart …", `Version <b>${esc(res.version)}</b> ist installiert. AutoShorts startet neu, das dauert ein paar Sekunden.`);\n  const t0 = Date.now();\n  const poll = async () => {\n    try { const r = await fetch("/api/version", {cache: "no-store"}); if (r.ok) { const j = await r.json(); if (j.version !== before) { location.reload(); return; } } } catch (e) {}\n    if (Date.now() - t0 > 40000) { msg("Update installiert ✓", `Version <b>${esc(res.version)}</b> ist installiert.<br>Schließ dieses Fenster und starte AutoShorts über das <b>Desktop-Symbol</b>.`, \'<button class="btn" onclick="location.reload()">Erneut verbinden</button>\'); return; }\n    setTimeout(poll, 1000);\n  };\n  setTimeout(poll, 2000);\n}\nasync function startupUpdatePrompt() {\n  let u; try { u = await api("/api/update/check", {}); } catch (e) { return; }\n  S.update = u; banner();\n  if (!u.available) return;\n  try { if (sessionStorage.getItem("as-upd") === u.version) return; sessionStorage.setItem("as-upd", u.version); } catch (e) {}\n  document.body.insertAdjacentHTML("beforeend", `<div class="modal-bg" id="updAsk"><div class="modal" role="dialog" aria-modal="true" aria-labelledby="uaT">\n    <h2 id="uaT" style="font-size:19px">Update verfügbar</h2>\n    <p style="margin:0">Version <b>${esc(u.version)}</b> ist da (installiert: ${esc(S.version)}).${u.notes ? `<br><span class="hint">${esc(u.notes)}</span>` : ""}</p>\n    <p class="hint">Jetzt aktualisieren? Deine Einstellungen und Videos bleiben erhalten.</p>\n    <div class="actions"><button class="btn primary" id="uaY">Ja, jetzt aktualisieren</button><button class="btn" id="uaN">Später</button></div></div></div>`);\n  $("#uaY").focus(); $("#uaN").onclick = () => $("#updAsk").remove(); $("#uaY").onclick = () => { $("#updAsk").remove(); runUpdate(); };\n}\n\n/* ═════════════════ Start ═════════════════ */\n(async function start() {\n  try { S = await api("/api/state"); } catch (e) { $("#app").innerHTML = `<div class="login"><div class="panel"><h2>AutoShorts antwortet nicht</h2><p class="hint">${esc(e.message)}</p></div></div>`; return; }\n  if (!S.connected) return renderSetup();\n  shell(); render(true);\n  await Promise.all([loadData(), loadSecrets()]);\n  render(true); pollRuns();\n  setTimeout(startupUpdatePrompt, 1500);\n  setInterval(async () => { if (document.hidden) return; await loadData(); if (!$("#dayDrw") && !$(".modal-bg") && !DIRTY) render(); }, 5 * 60000);\n})();\nif ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});\n</script>\n</body>\n</html>\n'   # beim Bauen eingebettet
ICON_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">\n  <defs>\n    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">\n      <stop offset="0" stop-color="#3f6cf0"/>\n      <stop offset="1" stop-color="#1c3596"/>\n    </linearGradient>\n    <linearGradient id="card" x1="0" y1="0" x2="0" y2="1">\n      <stop offset="0" stop-color="#ffffff"/>\n      <stop offset="1" stop-color="#e4e9fb"/>\n    </linearGradient>\n  </defs>\n  <rect width="512" height="512" rx="112" fill="url(#bg)"/>\n  <g transform="translate(-30 0)">\n  <!-- hinteres Hochformat-Video (gestapelt = Serie / täglich) -->\n  <rect x="196" y="98" width="190" height="300" rx="34" fill="#ffffff" opacity=".22" transform="rotate(8 291 248)"/>\n  <!-- vorderes Hochformat-Video -->\n  <rect x="146" y="112" width="196" height="304" rx="36" fill="url(#card)"/>\n  <!-- Play -->\n  <path d="M222 214 L222 314 Q222 326 233 320 L311 274 Q321 264 311 256 L233 210 Q222 204 222 214 Z" fill="#2f5bd3"/>\n  <!-- Untertitel-Balken -->\n  <rect x="190" y="352" width="108" height="16" rx="8" fill="#161a24" opacity=".85"/>\n  <!-- KI-Funke -->\n  <path d="M384 96 C389 128 396 135 428 140 C396 145 389 152 384 184 C379 152 372 145 340 140 C372 135 379 128 384 96 Z" fill="#ffcf4a"/>\n  <circle cx="420" cy="196" r="10" fill="#ffcf4a"/>\n  </g>\n</svg>\n'


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
    global LAUNCHER
    new_version = _validate_build(data, sha)
    if not LAUNCHER.lower().endswith(".cmd") or not os.path.exists(LAUNCHER):
        # z. B. direkt aus der ZIP gestartet: Windows hat die Datei schon wieder weggeräumt → in den eigenen Ordner installieren
        d = install_dir()
        if not d:
            raise ValueError("Bitte AutoShorts.cmd erst aus der ZIP entpacken und von dort starten.")
        os.makedirs(os.path.join(d, "AutoShorts-Daten"), exist_ok=True)
        import shutil
        if os.path.exists(SET_FILE) and not os.path.exists(os.path.join(d, "AutoShorts-Daten", "einstellungen.json")):
            shutil.copy2(SET_FILE, os.path.join(d, "AutoShorts-Daten", "einstellungen.json"))
        LAUNCHER = os.path.join(d, "AutoShorts.cmd")
        if not os.path.exists(LAUNCHER):
            with open(LAUNCHER, "wb") as f:
                f.write(data)
            log(f"Update als Neuinstallation nach {d}")
            threading.Timer(0.8, restart).start()
            return new_version
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
    h._send(200, {"url": oauth_start(b.get("platform"), b.get("client_id"), b.get("mode") or "direct")})


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
