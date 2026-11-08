"""Baut AutoShorts.cmd: eine einzige Datei (Windows-Batch + Python), die die ganze App enthält.

    python3 quellcode/build_onefile.py 1.0.0 "Was ist neu"

Legt ab:  AutoShorts.cmd (aktuelle Version), releases/AutoShorts-<version>.cmd, version.json
"""
import base64
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
APP = os.path.join(HERE, "app")

HEADER = r"""0<0# : ^
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
"""

LOCAL = re.compile(r"^(from (naclpure|appshell) import .*|sys\.path\.insert\(0, .*\))\s*$", re.M)


def module(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    return f"\n# ═════════════════ {os.path.basename(path)} ═════════════════\n" + LOCAL.sub("", src)


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else "0.0.0"
    notes = sys.argv[2] if len(sys.argv) > 2 else ""
    assert re.fullmatch(r"\d+\.\d+\.\d+", version), "Version wie 1.0.0 angeben"
    with open(os.path.join(APP, "static", "index.html"), encoding="utf-8") as f:
        html = f.read()
    with open(os.path.join(ROOT, "docs", "icon.svg"), encoding="utf-8") as f:
        svg = f.read()
    pngs = {}
    for size in (192, 256, 512):
        with open(os.path.join(ROOT, "docs", f"icon-{size}.png"), "rb") as f:
            pngs[size] = base64.b64encode(f.read()).decode()
    body = module(os.path.join(ROOT, "engine", "naclpure.py")) + module(os.path.join(APP, "appshell.py"))
    server = module(os.path.join(APP, "server.py"))
    server = server.replace('DATA = os.environ.get("AS_DATA", os.path.join(ROOT, "data"))',
                            'DATA = os.environ.get("AS_DATA", os.path.join(os.path.dirname(os.path.abspath(__file__)), "AutoShorts-Daten"))')
    assert "AutoShorts-Daten" in server
    server = server.replace('APP_VERSION = "dev"', f'APP_VERSION = "{version}"', 1)
    server = server.replace("INDEX_HTML = None", f"INDEX_HTML = {html!r}", 1).replace("ICON_SVG = None", f"ICON_SVG = {svg!r}", 1)
    assert f'APP_VERSION = "{version}"' in server and "INDEX_HTML = None" not in server and "ICON_SVG = None" not in server
    consts = f"\nICON_PNG.update({pngs!r})\n"
    out = HEADER + body + consts + server
    os.makedirs(os.path.join(ROOT, "releases"), exist_ok=True)
    files = [os.path.join(ROOT, "AutoShorts.cmd"), os.path.join(ROOT, "releases", f"AutoShorts-{version}.cmd")]
    for p in files:
        with open(p, "w", encoding="utf-8", newline="\r\n") as f:
            f.write(out)
    with open(files[0], "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    with open(os.path.join(ROOT, "version.json"), "w", encoding="utf-8") as f:
        # eigene, nie wieder geänderte Datei je Version: GitHub kann keine veraltete Fassung ausliefern
        json.dump({"version": version, "file": f"releases/AutoShorts-{version}.cmd", "sha256": sha, "notes": notes},
                  f, ensure_ascii=False, indent=2)
    print("gebaut:", files[0], os.path.getsize(files[0]), "Bytes · Version", version)


if __name__ == "__main__":
    main()
