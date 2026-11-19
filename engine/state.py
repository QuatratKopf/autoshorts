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
    dict(slug="comedy", name="Comedy", emoji="🤪",
         description="Absurde Ich-Geschichten mit trockenem Humor: Was passiert, wenn man es wirklich macht?",
         script_style="Erzähle in der Ich-Form eine absurde, aber nachvollziehbare Alltags-Geschichte, die völlig eskaliert "
                      "(Beispiel: 'Ich hab mir KI-Agenten geholt, die mein Leben organisieren' – erst praktisch, dann übernehmen sie alles). "
                      "Trockener, selbstironischer Ton, kurze Sätze, schnelle Wendungen. Mindestens drei Lacher: Übertreibung, "
                      "ein Running Gag, der wiederkommt und am Ende kippt, und eine überraschende Schlusspointe. Dinge und Begriffe "
                      "werden zu Figuren mit eigenem Willen. Echte Hintergründe dürfen vorkommen, Erfundenes ist klar als Geschichte erkennbar.",
         image_mood="bright warm colors, expressive faces, cozy desk and room settings, funny reactions",
         voice="de-DE-FlorianMultilingualNeural", voice_rate="+8%", voice_pitch="+0Hz",
         voice_instructions="Trocken, leicht genervt und selbstironisch, wie jemand, der seine eigene Geschichte nicht fassen kann."),
    dict(slug="musik", name="Musik-Kugel", emoji="🎵", every_days=1, special="bounce",
         description="Eine Kugel springt durch Glasscheiben – jeder Aufprall ist ein Ton einer bekannten, gemeinfreien Melodie. "
                     "Ohne Sprecher, einmal am Tag.",
         script_style="", image_mood="", voice="", voice_rate="+0%", voice_pitch="+0Hz", voice_instructions=""),
    dict(slug="whatif", name="What If", emoji="🤯",
         description="Was wäre wenn …? Verrückte Gedankenexperimente, wissenschaftlich durchgespielt.",
         script_style="Starte mit einer verrückten Was-wäre-wenn-Frage (z. B. 'Was wäre, wenn die Erde aufhört sich zu drehen?'). "
                      "Spiele die Folgen Schritt für Schritt durch: erst Sekunden, dann Tage, dann Jahre – jede Stufe krasser als die davor. "
                      "Stütze dich auf echte Physik, Biologie und Zahlen; sag klar, wo es Schätzung ist. "
                      "Ende mit einem überraschenden Twist oder einer Frage an die Zuschauer.",
         image_mood="epic dramatic scale, glowing sci-fi colors, before/after contrast, planets, explosions in cartoon style",
         voice="de-DE-FlorianMultilingualNeural", voice_rate="+6%", voice_pitch="+0Hz",
         voice_instructions="Staunend und mitreißend, wird mit jeder Stufe aufgeregter."),
    {'slug': 'vergleich', 'name': 'Wer verdient mehr?', 'emoji': '💰', 'description': 'Zwei Menschen, zwei Jobs oder zwei Läden im Duell: Was kostet es, was bleibt hängen, wer ist am Ende erfolgreicher? Mit Beispielrechnung, Haken und Fazit.', 'script_style': "Duell zweier konkreter, alltagsnaher Menschen oder Läden mit Namen und Beruf (z. B. Barbershop gegen Friseursalon, Dönerladen gegen Burgerkette, Lkw-Fahrer gegen Paketbote, Influencer gegen Handwerker). Aufbau: 1) Hook mit beiden Namen und der Frage 'Wer ist erfolgreicher?' (versus). 2) Preis bzw. Einnahme pro Kunde/Auftrag als große Zahl, dann eine Beispielrechnung, was nach Abzügen (Material, Steuer, Miete) wirklich hängen bleibt. 3) Dasselbe für die zweite Person, mit einem witzigen Detail zum Charakter (eine Marotte, ein Spruch, ein Running Gag). 4) Zwischenstand als Balkenvergleich (compare). 5) Fixkosten, Zeit pro Auftrag (timer) und Kunden pro Tag → Einnahmen pro Monat (counter), gern mit einem Statussymbol als Beweis (Auto, Uhr). 6) 'DER HAKEN': eine überraschende Wendung, z. B. der Stundenlohn, die Arbeitszeit pro Woche oder ein versteckter Kostenpunkt. 7) Fazit mit Pointe und einem Stempel als Urteil (z. B. 'GEMOGGT', 'PLEITE', 'GEWINNER'), am Ende die Frage an die Zuschauer: 'Zu wem würdest du gehen? Schreib's in die Kommentare.' Zahlen realistisch für Deutschland und als Beispielrechnung gekennzeichnet; keine echten Personen, Marken oder Firmen. Locker, frech, Jugendsprache in Maßen. WICHTIG: In JEDER Szene ist etwas zu sehen – entweder eine Zahlen-Grafik (number, compare, counter, timer, versus, score) oder eine Figur mit Aktion und passendem Ding. Nie eine leere Szene, keine zwei Grafiken mit derselben Zahl hintereinander. Jede Zahl, die der Sprecher nennt, erscheint groß im Bild.", 'image_mood': 'dark navy background with golden sunburst rays, big bold money numbers, flat minimal characters', 'voice': 'de-DE-FlorianMultilingualNeural', 'voice_rate': '+10%', 'voice_pitch': '+0Hz', 'voice_instructions': 'Locker, schnell und frech wie ein Kumpel, der vorrechnet; bei Pointen kurz trocken.', 'topic_examples': ['Barbershop gegen Friseursalon – wer verdient mehr?', 'Dönerladen gegen Burgerkette', 'Lkw-Fahrer gegen Paketbote', 'Spätkauf gegen Supermarkt', 'Fahrlehrer gegen Pilot', 'Tattoo-Studio gegen Nagelstudio', 'Imbiss am Bahnhof gegen Foodtruck'], 'trends': False},
    {'slug': 'motivation', 'name': 'Motivation', 'emoji': '🔥', 'description': 'Kurze Motivationsrede: ein großes Wort nach dem anderen, schnelle Schnitte, Gute-Laune-Musik.', 'script_style': "Motivationsrede direkt an 'du', wie ein Coach, der dich wachrüttelt. Kurze, rhythmische Sätze (3 bis 8 Wörter), Wiederholungen als Stilmittel ('Nicht morgen. Nicht nächste Woche. Jetzt.'). Aufbau: Hook, der trifft ('Du bist nicht faul. Du bist abgelenkt.'), dann das Problem aus dem Alltag (Handy, Scrollen bis drei Uhr nachts, Ausreden, Angst vor dem ersten Schritt), dann der Wendepunkt mit einem starken Bild oder Vergleich, dann konkrete kleine Schritte, Ende mit einem Satz zum Merken und 'Speicher dir das für die harten Tage.' Keine Zitate echter Personen, keine Versprechen von Reichtum. BILDER: Jede Szene ist kurz (ein Satz, höchstens 2–3 Sekunden) und zeigt eine eigene, klare Situation zum Satz: jemand liegt nachts mit Handy im Bett, rennt los, steht am Berg, trainiert, lernt am Schreibtisch, steht vor einer Tür, feiert. Viel Bewegung, Orte wechseln ständig, keine Einblendungen und keine Grafiken – der Text erscheint als großes Wort in der Bildmitte.", 'image_mood': 'vibrant purple, violet and warm orange colors, bright cinematic flat illustration, dynamic poses', 'voice': 'de-DE-ConradNeural', 'voice_rate': '+4%', 'voice_pitch': '-2Hz', 'voice_instructions': 'Kraftvoll, warm und eindringlich wie ein Motivations-Coach; Pausen nach starken Sätzen.', 'caption_style': 'word', 'music_volume': 0.24, 'topic_examples': ['Warum du nicht faul bist, sondern abgelenkt', 'Der Tag, an dem du aufhörst, auf Motivation zu warten', 'Du vergleichst dich zu viel', 'Niemand kommt, um dich zu retten – und das ist gut so', 'Disziplin schlägt Talent', 'Fang an, bevor du bereit bist', 'Was in einem Jahr anders ist, wenn du heute anfängst'], 'trends': False, 'topic_rules': "Es geht um DICH: Einstellung, Disziplin, Angst vor dem ersten Schritt, Ausreden, Neuanfang, Durchhalten, Selbstwert. KEINE Technik-, Handy-, Algorithmus-, Daten- oder Überwachungs-Themen, KEINE 'Was wäre, wenn'-Fragen, nichts Gruseliges oder Düsteres. Das Thema klingt wie ein Satz, den ein Coach dir ins Gesicht sagt."},
    {'slug': 'liebe', 'name': 'Liebe', 'emoji': '💕', 'description': 'Liebesgeschichten, schnulzige Momente und Listen wie „3 Zeichen für echte Liebe“ – mit weicher Frauenstimme und romantischer Musik.', 'script_style': "Zwei Formen, abwechselnd: A) LIEBESGESCHICHTE – romantisch und gefühlvoll, zum Mitfühlen und Dahinschmelzen. Erfundene Geschichten klar als Geschichte erzählen ('Stell dir vor …', 'Das ist die Geschichte von Lena und Tom …'). Aufbau: Hook mit einem Moment, der sofort berührt ('Er hat ihr dreihundertfünfundsechzig Briefe geschrieben. Einen für jeden Tag.'), wie sie sich kennenlernen (ein kleiner, süßer Zufall), Herzklopfen oder Hindernis (Entfernung, Schüchternheit, ein verpasster Zug), die große Geste, gefühlvolles Ende mit Happy End. B) LISTE ÜBER DIE LIEBE – z. B. '3 Zeichen für echte Liebe' (Vertrauen, Zeit füreinander, Lachen ohne Grund), '5 kleine Gesten, die mehr sagen als Ich liebe dich', 'Woran du merkst, dass jemand in dich verliebt ist'. Aufbau: Hook ('Echte Liebe erkennst du nicht an großen Worten.'), dann jedes Zeichen mit einem eigenen Banner ('graphic': {'type': 'round', 'kicker': 'ZEICHEN 1', 'text': 'VERTRAUEN'}) und danach einer kleinen Alltagsszene mit zwei Figuren, die genau das zeigt (sie erzählt ihm ein Geheimnis; sie kochen zusammen; beide lachen grundlos auf dem Sofa); das schönste Zeichen zuletzt. Belegbares aus der Forschung darf vorkommen, nichts erfinden. Beide Formen: warm, zärtlich, ein bisschen kitschig mit einem Augenzwinkern; Ende mit einem Satz zum Seufzen und einer Frage an die Zuschauer ('Welches Zeichen kennst du? Markier die Person.'); kein Drama mit Gewalt, nichts Anzügliches, keine echten Privatpersonen. BILDER: zwei Figuren, die sich ansehen, nebeneinander gehen, tanzen, sich zuwinken; Herz-Emote ('emote': 'heart') bei Verliebtheit; romantische Orte: Park, Strand bei Sonnenuntergang, Restaurant mit Kerze, Wohnzimmer-Sofa, Küche, Bahnhof, Sternenhimmel in der Nacht. Für zärtliche Szenen 'mood': 'love'.", 'image_mood': 'soft pink, rose and warm golden sunset colors, dreamy romantic light, floating hearts and petals', 'voice': 'de-DE-SeraphinaMultilingualNeural', 'voice_rate': '-4%', 'voice_pitch': '+0Hz', 'voice_instructions': 'Sanft, warm und gefühlvoll wie eine Freundin, die eine Liebesgeschichte erzählt; leise Pausen an den schönen Stellen.', 'gemini_voice': 'Despina', 'own_voice': True, 'music_volume': 0.16, 'topic_examples': ['3 Zeichen für echte Liebe', 'Er schrieb ihr jeden Tag einen Brief – ein Jahr lang', '5 kleine Gesten, die mehr sagen als Ich liebe dich', 'Zwei Fremde, ein verpasster Zug und ein Zettel am Fenster', 'Woran du merkst, dass jemand in dich verliebt ist', 'Was beim Verliebtsein in deinem Gehirn passiert', 'Sie trafen sich nach fünfzig Jahren wieder', '3 Dinge, die glückliche Paare jeden Tag tun', 'Der Regenschirm, der zwei Leben verband', 'Warum dein Herz rast, wenn du die Person siehst'], 'trends': False, 'topic_rules': "Es geht um Liebe, Verliebtsein, Romantik, große Gesten, Wiedersehen, erste Liebe, Herzklopfen – als Liebesgeschichte ODER als Liste ('3 Zeichen für echte Liebe', 'Woran du merkst …', 'Gesten, die …'); wechsle zwischen beiden ab. Nichts Gruseliges, keine Trennungs-Dramen mit Streit oder Gewalt, nichts Anzügliches, keine Promi-Beziehungen, keine echten Privatpersonen."},
]


DEFAULT_SETTINGS = {
    "channel_name": "",             # Kanal-Profil: Name des Kanals (nur zur Übersicht)
    "channel_focus": "",            # Kanal-Profil: Themen-Schwerpunkt, z. B. „Sport und Fitness“ oder „Essen und Kochen“
    "channel_seed": "",             # Kanal-Merkmal: jede Kopie (Fork) mischt Themen, Figuren und Melodien anders (leer = Original)
    "autopilot": True,
    "upload_times": "18:00",
    "upload_via": "direct",         # direct = eigene Google-/TikTok-App · zernio = über den Dienst Zernio (ein API-Schlüssel)
    "target_seconds": 70,
    "min_seconds": 62,              # Videos sollen sicher über einer Minute liegen (TikTok-Creator-Programm)
    "youtube_seconds": 55,          # YouTube bekommt eine gekürzte Fassung um diese Länge (Shorts werden kurz öfter zu Ende geschaut) · 0 = aus
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
    "auto_optimize": True,          # Analyse steuert mit: starke Kategorien öfter, Themen in der Art der erfolgreichsten Videos
    "look": "cartoon",              # cartoon = hell und bunt · neon = dunkle Motion-Grafik-Stimmung (violette Nacht, Lichtpunkte)
    "stats_minutes": 30,            # wie oft die Zahlen der Videos geholt werden
    "plan_ahead": True,             # Thema und Drehbuch am Vortag festlegen, damit Fehlendes vor dem Video gebaut werden kann
    "hold_missing": True,           # nicht hochladen, solange der Engine für das Video noch etwas fehlt
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


ANGLES = ("Alltag und Schule", "Essen und Trinken", "Sport und Körper", "Geld und Jobs", "Internet und Games", "Natur und Tiere",
          "Weltall und Physik", "Geschichte und alte Kulturen", "Psychologie und Gefühle", "Städte und Reisen", "Technik und Erfindungen",
          "Musik und Filme", "Gesundheit und Schlaf", "Rekorde und Extreme", "Verbrechen und Rätsel", "Meer und Wetter")


def channel_seed():
    return str((CONFIG.get("settings") or {}).get("channel_seed") or "").strip()


def channel_rand(*salt):
    """Zufall, der für diesen Kanal fest ist (anderes Kanal-Merkmal → andere Reihenfolge); None im Original ohne Merkmal."""
    import random
    seed = channel_seed()
    return random.Random("|".join([seed] + [str(x) for x in salt])) if seed else None


def channel_hint():
    """Kanal-Profil für die Themenwahl: eigener Schwerpunkt und – je Kanal-Merkmal – eigene Blickwinkel, die wöchentlich wechseln.
    So wählen zwei Kopien der App selbst bei denselben Trends andere Themen."""
    st = CONFIG.get("settings") or {}
    parts = []
    if str(st.get("channel_focus") or "").strip():
        parts.append(f"Schwerpunkt dieses Kanals: {str(st['channel_focus']).strip()[:200]}. Wähle Themen, die dazu passen.")
    rnd = channel_rand("angles", time.strftime("%G-%V"))
    if rnd:
        a, b = rnd.sample(ANGLES, 2)
        parts.append(f"Eigener Blickwinkel dieses Kanals diese Woche: bevorzugt Themen rund um „{a}“ oder „{b}“ "
                     f"(Kanal-Merkmal {channel_seed()} – andere Kanäle mit derselben App wählen andere Themen).")
    return ("\n" + "\n".join(parts) + "\n") if parts else ""


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
for _c in CONFIG["categories"]:   # Sonder-Einstellungen einer Video-Art (Untertitel-Stil, Look, Musik) bleiben erhalten, auch wenn die App sie nicht kennt
    _p = next((p for p in PRESET_CATEGORIES if p["slug"] == _c.get("slug")), None)
    for _k in ("caption_style", "look", "music_volume", "special", "every_days", "topic_examples", "topic_rules", "trends", "gemini_voice", "own_voice"):
        if _p and _k in _p and _k not in _c:
            _c[_k] = _p[_k]
if CONFIG["settings"].get("text_provider") not in ("gemini",):   # Premium-Dienste (OpenAI, Pollinations als Wahl) sind aus der App entfernt:
    CONFIG["settings"]["text_provider"] = "gemini"                  # Gemini schreibt, der kostenlose Ersatz springt bei Ausfall von selbst ein
if CONFIG["settings"].get("tts_provider") not in ("gemini", "edge"):   # OpenAI/ElevenLabs-Stimmen entfernt → Gemini-Erzähler
    CONFIG["settings"]["tts_provider"] = "gemini"
_have = {c.get("slug") for c in CONFIG["categories"]}
for _p in PRESET_CATEGORIES:   # neue Video-Arten automatisch ergänzen (eingeschaltet)
    if _p["slug"] not in _have:
        CONFIG["categories"].append({**_p, "enabled": True})
for _c in CONFIG["categories"]:   # alte Vorgabe ersetzen: Zielgruppe ist Gen Z, nicht Kinder
    if _c.get("description") == "Verblüffende Fakten, kindgerecht und witzig erklärt.":
        _c["description"] = "Verblüffende Fakten, frech und witzig erklärt."

_allowed = CONFIG["settings"].get("allowed_cats")   # Gast-Kopie: nur die Video-Arten, die der Admin für diesen Zugang freigibt
if isinstance(_allowed, list) and _allowed:
    for _c in CONFIG["categories"]:
        if _c.get("slug") not in _allowed:
            _c["enabled"] = False

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
