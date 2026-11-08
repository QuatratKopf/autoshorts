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
