"""Video nachbauen: Ein eingeschicktes Video (aus der App, liegt als Anhang im Release „inbox“) wird angehört und angesehen –
gesprochener Text per Spracherkennung, Ablauf der Bilder per Text-KI mit Einzelbildern – und daraus entsteht ein neues Video
in unserem Stil: eigene Worte, eigene Figuren und Orte, gleiche Idee und gleiches Tempo. Nichts wird 1:1 übernommen."""
import base64
import json
import os
import re
import subprocess
from pathlib import Path

import requests

from .state import WORK, cfg, log, secret

INBOX = "inbox"
ANALYZE = """Du siehst Einzelbilder (in zeitlicher Reihenfolge) und den gesprochenen Text eines Kurzvideos.
Beschreibe für einen Animations-Zeichner auf Deutsch, was passiert, damit ein ähnliches Video in eigenem Stil entstehen kann.
Antworte nur mit JSON: {"topic": "Thema in einem kurzen Satz, ohne Namen von Personen, Kanälen oder Marken",
"category": "eine von: comedy, fakten, storys, lustig, grusel, mysterien, tiere, whatif",
"visuals": "Ablauf der Bilder als kurze Stichpunkte: Orte, Figuren (allgemein beschrieben), wiederkehrende Figuren aus Dingen oder Begriffen, Einblendungen, Witze im Bild",
"tone": "Ton und Art des Humors in einem Satz"}"""


def _frames(path: Path, n=10):
    """n Einzelbilder gleichmäßig über das Video verteilt, klein als JPEG (für die Text-KI)."""
    out = Path(path).parent / "frames"
    out.mkdir(exist_ok=True)
    try:
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                                   capture_output=True, text=True, check=True).stdout.strip() or 0)
    except (subprocess.CalledProcessError, ValueError):
        dur = 0
    files = []
    for i in range(n):
        t = dur * (i + 0.5) / n if dur else i * 3
        f = out / f"f{i:02d}.jpg"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1",
                        "-vf", "scale=384:-2", "-q:v", "5", str(f)], capture_output=True)
        if f.exists() and f.stat().st_size > 500:
            files.append(f)
    return files, dur


def _look(frames, transcript):
    """Lässt die Text-KI (Gemini, mit Bildern) den Ablauf beschreiben. Ohne Schlüssel oder bei Fehlern: nur aus dem Text."""
    key = secret("GEMINI_API_KEY")
    if key and frames:
        parts = [{"text": f"Gesprochener Text:\n{transcript[:3000]}"}] + [
            {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(f.read_bytes()).decode()}} for f in frames]
        for model in (cfg("gemini_model") or "gemini-3.5-flash", "gemini-2.5-flash"):
            try:
                r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                                  headers={"x-goog-api-key": key}, timeout=90,
                                  json={"systemInstruction": {"parts": [{"text": ANALYZE}]}, "contents": [{"role": "user", "parts": parts}],
                                        "generationConfig": {"temperature": 0.4, "responseMimeType": "application/json"}})
                if r.status_code == 200:
                    txt = "".join(p.get("text", "") for p in r.json()["candidates"][0]["content"]["parts"] if not p.get("thought"))
                    return json.loads(txt[txt.find("{"): txt.rfind("}") + 1])
                log(f"Bild-Analyse {model}: HTTP {r.status_code}")
            except Exception as e:  # noqa: BLE001
                log(f"Bild-Analyse {model}: {str(e)[:120]}")
    from . import ai                                      # Ersatz: nur aus dem gesprochenen Text
    js, _ = ai.chat_json(ANALYZE, f"(Keine Bilder verfügbar.)\nGesprochener Text:\n{transcript[:3000]}", 0.4)
    return js


LINK_RE = re.compile(r"^https?://(?:(?:www|m|vm|vt)\.)?(?:youtube\.com/(?:shorts/|watch\?v=)|youtu\.be/|tiktok\.com/)[^\s\"'<>]{1,300}$", re.I)
MAX_SECONDS = 600


def is_link(name: str) -> bool:
    """TikTok- oder YouTube-Link statt Dateiname?"""
    return bool(LINK_RE.match(str(name or "").strip()))


def download(url: str, work: Path) -> Path:
    """Lädt ein Video von TikTok oder YouTube (yt-dlp, eine Datei ohne Zusammenfügen, höchstens 720p und 10 Minuten)."""
    import yt_dlp
    opts = {"format": "b[ext=mp4][height<=720]/b[height<=720]/b[ext=mp4]/b", "outtmpl": str(work / "vorlage.%(ext)s"),
            "noplaylist": True, "quiet": True, "no_warnings": True, "max_filesize": 300_000_000, "socket_timeout": 30,
            "match_filter": lambda info, *a, **k: "zu lang" if (info.get("duration") or 0) > MAX_SECONDS else None}
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(url, download=True)
        path = Path(y.prepare_filename(info))
    if not path.exists():
        found = sorted(work.glob("vorlage.*"), key=lambda f: f.stat().st_mtime)
        if not found:
            raise RuntimeError("Video ließ sich nicht laden (zu lang oder gesperrt)")
        path = found[-1]
    return path


def link_text(url: str) -> str:
    """Ersatz, wenn das Video selbst nicht ladbar ist: Titel/Beschreibung über die öffentliche oEmbed-Schnittstelle."""
    api = ("https://www.tiktok.com/oembed" if "tiktok.com" in url else "https://www.youtube.com/oembed")
    r = requests.get(api, params={"url": url, "format": "json"}, timeout=25, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    js = r.json()
    return str(js.get("title") or "").strip()


def analyze_link_text(url: str) -> dict:
    """Nur Text (Titel/Bildunterschrift) – wenn die Plattform das Herunterladen gesperrt hat."""
    text = link_text(url)
    if not text.strip():
        raise RuntimeError("Video nicht ladbar und kein Titel lesbar")
    info = _look([], "(Nur Titel/Beschreibung des Videos, kein Ton:) " + text) or {}
    topic = re.sub(r"\s+", " ", str(info.get("topic") or "")).strip()[:140]
    if not topic:
        raise RuntimeError("Aus dem Link ließ sich kein Thema erkennen")
    return {"topic": topic, "category": str(info.get("category") or "").strip().lower(), "transcript": "",
            "visuals": str(info.get("visuals") or "")[:2000], "tone": str(info.get("tone") or "")[:300]}


def fetch(name: str) -> Path:
    """Lädt das eingeschickte Video: aus dem Release „inbox“ (Datei aus der App) oder direkt von TikTok/YouTube (Link)."""
    if is_link(name):
        work = WORK / "remake"
        work.mkdir(parents=True, exist_ok=True)
        return download(name.strip(), work)
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,120}", name or ""):
        raise RuntimeError("Ungültiger Dateiname für das Vorlagen-Video")
    work = WORK / "remake"
    work.mkdir(parents=True, exist_ok=True)
    subprocess.run(["gh", "release", "download", INBOX, "-p", name, "-D", str(work), "--clobber"], capture_output=True, text=True, check=True)
    path = work / name
    if not path.exists():
        raise RuntimeError(f"Vorlagen-Video {name} nicht gefunden")
    return path


def analyze(path: Path) -> dict:
    """Gibt {"topic", "category", "transcript", "visuals", "tone"} zurück."""
    from . import ai
    heard = ai.listen(path) or []
    transcript = " ".join(w for w, _, _ in heard)
    frames, dur = _frames(path)
    log(f"Vorlage: {dur:.0f} s, {len(transcript.split())} Wörter erkannt, {len(frames)} Bilder")
    info = _look(frames, transcript) or {}
    topic = re.sub(r"\s+", " ", str(info.get("topic") or "")).strip()[:140]
    if not topic:
        raise RuntimeError("Aus dem Video ließ sich kein Thema erkennen")
    return {"topic": topic, "category": str(info.get("category") or "").strip().lower(), "transcript": transcript,
            "visuals": str(info.get("visuals") or "")[:2000], "tone": str(info.get("tone") or "")[:300]}


def cleanup(name: str):
    """Vorlage nach dem Nachbauen aus dem Eingang entfernen (sie gehört nicht ins Repository)."""
    if os.environ.get("GH_TOKEN") and not is_link(name):
        subprocess.run(["gh", "release", "delete-asset", INBOX, name, "-y"], capture_output=True)
