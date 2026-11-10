"""Zustand von AutoShorts: alles liegt als JSON-Dateien im Repository.

docs/data/config.json   gehört der App (Einstellungen, Kategorien, Themen-Warteschlange)
docs/data/state.json    gehört dem Motor (Zeitplan, benutzte Themen, Verbindungen)
docs/data/videos.json   gehört dem Motor (alle Videos)
docs/data/stats.json    gehört dem Motor (Zahlen je Tag)
tokens/*.enc            verschlüsselte Anmeldungen bei YouTube/TikTok
"""
import base64
import json
import os
import time
from pathlib import Path

from . import naclpure

ROOT = Path(os.environ.get("AUTOSHORTS_ROOT") or Path(__file__).resolve().parent.parent)
DATA = ROOT / "docs" / "data"
THUMBS = ROOT / "docs" / "thumbs"
TOKENS = ROOT / "tokens"
WORK = ROOT / ".work"
OUT = ROOT / ".out"
MUSIC = ROOT / "music"
FONTS = Path(os.environ.get("FONTS_DIR") or ROOT / ".fonts")
TIMEZONE = "Europe/Berlin"

for d in (DATA, THUMBS, TOKENS, WORK, OUT):
    d.mkdir(parents=True, exist_ok=True)


def log(msg):
    print(time.strftime("%H:%M:%S ") + str(msg), flush=True)


# Bildstil angelehnt an flache 2D-Cartoon-Erklärvideos (dicke Konturen, ruhige Farben, niedliche Figuren)
OLD_STYLES = (
    "flat 2D vector cartoon illustration, clean thick dark outlines, soft muted warm colors, "
    "simple cute characters with big round white eyes and expressive faces, minimalist cozy background "
    "with simple shapes, explainer animation style, vertical 9:16 composition, main subject centered "
    "in the middle of the frame, no text, no letters, no words, no watermark",
)
DEFAULT_STYLE = (
    "flat 2D vector illustration like a modern animated explainer short, solid flat colors, no gradients, "
    "no 3D, no realistic rendering, clean bold dark outlines, simple geometric shapes, cute minimal characters "
    "with simple round heads and big expressive white eyes, detailed but simple flat background (room, street or landscape) "
    "with a few clear objects, cinematic lighting with flat shading, vertical 9:16 composition, main subject in the "
    "lower middle of the frame, upper third calm and uncluttered, no text, no letters, no words, no watermark"
)
DEFAULT_CHARACTER = (
    "a cheerful little character with a round yellow head, big round eyes, a small smile "
    "and a simple green bean-shaped body with thin stick arms and legs"
)

PRESET_CATEGORIES = [
    dict(slug="fakten", name="Fakten", emoji="💡",
         description="Verblüffende Fakten, frech und witzig erklärt.",
         script_style="Erkläre einen überraschenden, wahren Fakt Schritt für Schritt wie eine kleine Geschichte. "
                      "Nutze konkrete Zahlen und Vergleiche aus dem Alltag. Nur belegbare, korrekte Fakten – nichts erfinden. "
                      "Locker, frech, mit einem kleinen Witz zwischendurch.",
         image_mood="bright friendly daylight, cheerful colors, clear infographic-like scenes",
         voice="de-DE-FlorianMultilingualNeural", voice_rate="+8%", voice_pitch="+0Hz",
         voice_instructions="Begeistert, locker und schnell, wie ein Freund, der etwas Verrücktes erzählt."),
    dict(slug="grusel", name="Grusel", emoji="👻",
         description="Gänsehaut-Geschichten und unheimliche Legenden.",
         script_style="Erzähle eine unheimliche Gruselgeschichte oder Legende mit langsam steigender Spannung. "
                      "Kurze Sätze, Pausen durch Punkte, ein Schockmoment oder eine Wendung am Ende. Kein Blut, keine Gewalt-Details. "
                      "Wenn es eine wahre Legende ist, sag das; sonst kennzeichne sie als Geschichte.",
         image_mood="dark moonlit night, eerie fog, deep blue and purple palette, spooky but still cartoonish, soft glow",
         voice="de-DE-FlorianMultilingualNeural", voice_rate="-4%", voice_pitch="-4Hz",
         voice_instructions="Leise, langsam und unheimlich, mit Spannung in der Stimme."),
    dict(slug="storys", name="Spannende Storys", emoji="🔥",
         description="Wahre Geschichten mit Wendungen: Rettungen, Rekorde, Coups.",
         script_style="Erzähle eine wahre, spannende Geschichte mit Hook, Aufbau, Höhepunkt und überraschender Auflösung. "
                      "Nur reale, belegbare Ereignisse. Jede Szene endet so, dass man weiter zuhören will.",
         image_mood="cinematic lighting, dramatic composition, warm and cool contrast",
         voice="de-DE-FlorianMultilingualNeural", voice_rate="+4%", voice_pitch="+0Hz",
         voice_instructions="Spannend und mitreißend, wie ein Erzähler in einer Doku."),
    dict(slug="lustig", name="Lustige Geschichten", emoji="😂",
         description="Absurde, lustige Alltagsgeschichten und kuriose Vorfälle.",
         script_style="Erzähle eine absurde, lustige Geschichte mit Situationskomik und einer Pointe am Ende. "
                      "Übertreibe charmant, spiele mit Erwartungen. Ohne Beleidigungen oder Anzüglichkeiten.",
         image_mood="bright saturated colors, exaggerated funny facial expressions, slapstick poses",
         voice="de-DE-FlorianMultilingualNeural", voice_rate="+10%", voice_pitch="+2Hz",
         voice_instructions="Fröhlich, verschmitzt, mit hörbarem Grinsen."),
    dict(slug="mysterien", name="Mysterien & Rätsel", emoji="🕵️",
         description="Ungelöste Rätsel, seltsame Orte, mysteriöse Funde.",
         script_style="Stelle ein echtes, ungelöstes Rätsel vor: was passiert ist, welche Erklärungen es gibt, was bis heute offen ist. "
                      "Trenne klar Belegtes von Spekulation.",
         image_mood="mysterious fog, teal and amber palette, flashlight beams, old maps and clues",
         voice="de-DE-FlorianMultilingualNeural", voice_rate="+0%", voice_pitch="-2Hz",
         voice_instructions="Ruhig, geheimnisvoll, neugierig."),
    dict(slug="tiere", name="Tierwelt", emoji="🐾",
         description="Unglaubliche Tiere und ihre Superkräfte.",
         script_style="Erkläre eine erstaunliche Fähigkeit oder Eigenschaft eines Tieres, aus Sicht des Tieres oder als Mini-Story. "
                      "Wissenschaftlich korrekt, mit Vergleichen zum Menschen.",
         image_mood="lush nature settings, friendly cute animal characters, soft sunlight",
         voice="de-DE-SeraphinaMultilingualNeural", voice_rate="+6%", voice_pitch="+0Hz",
         voice_instructions="Warm, neugierig und begeistert."),
    dict(slug="whatif", name="What If", emoji="🤯",
         description="Was wäre wenn …? Verrückte Gedankenexperimente, wissenschaftlich durchgespielt.",
         script_style="Starte mit einer verrückten Was-wäre-wenn-Frage (z. B. 'Was wäre, wenn die Erde aufhört sich zu drehen?'). "
                      "Spiele die Folgen Schritt für Schritt durch: erst Sekunden, dann Tage, dann Jahre – jede Stufe krasser als die davor. "
                      "Stütze dich auf echte Physik, Biologie und Zahlen; sag klar, wo es Schätzung ist. "
                      "Ende mit einem überraschenden Twist oder einer Frage an die Zuschauer.",
         image_mood="epic dramatic scale, glowing sci-fi colors, before/after contrast, planets, explosions in cartoon style",
         voice="de-DE-FlorianMultilingualNeural", voice_rate="+6%", voice_pitch="+0Hz",
         voice_instructions="Staunend und mitreißend, wird mit jeder Stufe aufgeregter."),
]


DEFAULT_SETTINGS = {
    "autopilot": True,
    "upload_times": "18:00",
    "target_seconds": 70,
    "text_provider": "gemini",
    "tts_provider": "gemini",        # gemini = natürliche Erzählerstimme (kostenloses Kontingent), sonst edge
    "voice_style": "Lebendig und mitreißend mit klarer Betonung – wie der Sprecher eines viralen Erklärvideos, flüssig und natürlich.",
    "voice_speed": 1.0,             # 1 = normal · kleiner = langsamer
    "gemini_voice": "",              # leer = passende Stimme je Video-Art
    "image_provider": "cloudflare",
    "gemini_model": "gemini-3.5-flash",
    "openai_text_model": "gpt-4.1-mini",
    "openai_image_model": "gpt-image-1",
    "openai_image_quality": "low",
    "openai_tts_model": "gpt-4o-mini-tts",
    "openai_voice": "ash",
    "elevenlabs_voice_id": "",
    "image_style": DEFAULT_STYLE,
    "main_character": DEFAULT_CHARACTER,
    "use_main_character": True,
    "subtitles_lowercase": True,
    "auto_learn": True,             # fehlende Gegenstände automatisch zeichnen lassen und in der Bibliothek behalten
    "caption_style": "impact",      # impact = schmale fette Großbuchstaben, orange Schlüsselwörter · classic = runde Schrift
    "music_volume": 0.10,
    "sfx_volume": 0.35,
    "visual_mode": "toon",           # ai = KI-Bilder · toon = eigene Animations-Engine (Figuren + Orte)
    "youtube_enabled": True,
    "youtube_privacy": "public",
    "youtube_category": "24",
    "youtube_client_id": "",
    "tiktok_enabled": True,
    "tiktok_mode": "direct",
    "tiktok_privacy": "SELF_ONLY",
    "tiktok_client_key": "",
    "ai_label": True,
    "audience": "Gen Z (16–25) in Deutschland, die TikTok und YouTube Shorts schauen: Internet-Kultur, Memes, virale Trends, "
                "Gaming, Musik, Serien, Filme, Creator, Tech, Lifestyle. Lockere Sprache wie unter Freunden, schnell auf den Punkt, "
                "kein Lehrer- oder Kinder-Ton.",
    "trend_regions": "US,DE",      # Länder für die Trendsuche (Reihenfolge = Gewichtung)
    "trend_mode": "half",          # off | half | always – wie oft der Autopilot ein aktuelles Trend-Thema nimmt
    "make_thumbnail": True,
    "youtube_thumbnail": True,
}

TREND_DEFAULT = ("fakten", "storys", "mysterien", "tiere", "whatif")


def cat_trends(cat):
    return bool(cat.get("trends", cat.get("slug") in TREND_DEFAULT))


def default_config():
    cats = []
    for i, p in enumerate(PRESET_CATEGORIES):
        cats.append({**p, "enabled": i < 4})
    return {"settings": dict(DEFAULT_SETTINGS), "categories": cats, "queue": []}


DEFAULT_STATE = {"last_category": "", "done_slots": [], "used_queue": [], "last_stats": 0,
                 "next_id": 1, "connected": {}}


# ---------------------------------------------------------------- Dateien

def load(name, default):
    p = DATA / name
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return json.loads(json.dumps(default))


def save(name, obj):
    p = DATA / name
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


CONFIG = load("config.json", default_config())
CONFIG.setdefault("settings", {})
for k, v in DEFAULT_SETTINGS.items():
    CONFIG["settings"].setdefault(k, v)
if CONFIG["settings"].get("voice_speed") == 0.94:            # war zu langsam: zurück auf normales Tempo
    CONFIG["settings"]["voice_speed"] = 1.0
if "langsam und entspannt" in str(CONFIG["settings"].get("voice_style") or "") or "Natürlich und entspannt in normalem" in str(CONFIG["settings"].get("voice_style") or ""):
    CONFIG["settings"]["voice_style"] = DEFAULT_SETTINGS["voice_style"]
CONFIG.setdefault("categories", default_config()["categories"])
CONFIG.setdefault("queue", [])
if CONFIG["settings"].get("tts_provider") == "edge" and not CONFIG["settings"].get("tts_checked"):
    CONFIG["settings"]["tts_provider"] = "gemini"   # einmalig auf die natürlichere Stimme umstellen (Edge bleibt Ersatz)
CONFIG["settings"]["tts_checked"] = True
for _c in CONFIG["categories"]:   # ältere, künstlicher klingende Ersatzstimmen → die natürlichere mehrsprachige Stimme
    if _c.get("voice") in ("de-DE-ConradNeural", "de-DE-KillianNeural"):
        _c["voice"] = "de-DE-FlorianMultilingualNeural"
if CONFIG["settings"].get("gemini_model") in ("gemini-flash-latest", "gemini-pro-latest"):
    CONFIG["settings"]["gemini_model"] = "gemini-3.5-flash"
if not CONFIG["settings"].get("toon_checked"):          # einmalig: alles läuft über die eigene Animations-Engine
    CONFIG["settings"]["visual_mode"] = "toon"
    CONFIG["settings"]["toon_checked"] = True
if CONFIG["settings"].get("image_style") in OLD_STYLES:   # alte Standard-Vorgabe → neuer, flacherer Stil
    CONFIG["settings"]["image_style"] = DEFAULT_STYLE
_have = {c.get("slug") for c in CONFIG["categories"]}
for _p in PRESET_CATEGORIES:   # neue Video-Arten automatisch ergänzen (eingeschaltet)
    if _p["slug"] not in _have:
        CONFIG["categories"].append({**_p, "enabled": True})
for _c in CONFIG["categories"]:   # alte Vorgabe ersetzen: Zielgruppe ist Gen Z, nicht Kinder
    if _c.get("description") == "Verblüffende Fakten, kindgerecht und witzig erklärt.":
        _c["description"] = "Verblüffende Fakten, frech und witzig erklärt."

STATE = load("state.json", DEFAULT_STATE)
for k, v in DEFAULT_STATE.items():
    STATE.setdefault(k, json.loads(json.dumps(v)))
VIDEOS = load("videos.json", [])
STATS = load("stats.json", {"v": {}, "ch": {}, "updated": 0})


def cfg(key):
    return CONFIG["settings"].get(key, DEFAULT_SETTINGS.get(key))


def secret(name):
    return (os.environ.get(name) or "").strip()


def category(slug):
    return next((c for c in CONFIG["categories"] if c["slug"] == slug), None)


def video(vid):
    return next((v for v in VIDEOS if int(v["id"]) == int(vid)), None)


def save_all():
    STATE["used_queue"] = STATE["used_queue"][-500:]
    STATE["done_slots"] = STATE["done_slots"][-60:]
    save("state.json", STATE)
    save("videos.json", VIDEOS)
    save("stats.json", STATS)


# ---------------------------------------------------------------- Anmeldungen (verschlüsselt)
# Schlüssel = aus dem Client-Secret der Plattform abgeleitet, das nur in den GitHub-Secrets
# (und auf deinem PC in der App) liegt. Gleiches Verfahren wie in der App (naclpure).

def _key(platform):
    sec = secret("GOOGLE_CLIENT_SECRET" if platform == "youtube" else "TIKTOK_CLIENT_SECRET")
    if not sec:
        raise RuntimeError(f"Secret für {platform} fehlt")
    return naclpure.derive_key("autoshorts", platform, sec)


def load_token(platform):
    p = TOKENS / f"{platform}.enc"
    if not p.exists():
        return None
    try:
        return json.loads(naclpure.decrypt(base64.b64decode(p.read_bytes()), _key(platform)))
    except Exception:  # noqa: BLE001 – Secret geändert oder Datei kaputt
        return None


def save_token(platform, tok):
    blob = naclpure.encrypt(json.dumps(tok).encode(), _key(platform))
    (TOKENS / f"{platform}.enc").write_bytes(base64.b64encode(blob))


def drop_token(platform):
    """Anmeldung entfernen und die über diese Plattform abgerufenen Zahlen löschen (Datenschutz-Zusage)."""
    (TOKENS / f"{platform}.enc").unlink(missing_ok=True)
    STATE["connected"].pop(platform, None)
    STATS.get("ch", {}).pop(platform, None)
    for rows in STATS.get("v", {}).values():
        rows.pop(platform, None)
