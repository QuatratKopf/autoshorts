"""Themenfindung und Drehbuch (Skript + Szenen + Bild-Prompts)."""
from . import ai
from .state import VIDEOS, cfg

SYSTEM = """Du schreibst virale deutsche Kurzvideos (YouTube Shorts / TikTok) im Stil animierter Cartoon-Erklärvideos.
Regeln für die Sprechertexte:
- Der erste Satz ist ein starker Hook (Frage, überraschende Behauptung oder Konflikt) – keine Begrüßung, kein "Heute erkläre ich".
- Gesprochene, einfache Sprache, kurze Sätze, Du-Ansprache erlaubt. Zahlen ausschreiben, wie man sie spricht.
- Keine Emojis, keine Regieanweisungen, keine Klammern im Sprechertext.
- Der letzte Satz ist eine Pointe oder Wendung, gern mit kurzer Aufforderung wie "Folg für mehr".
- Inhaltlich korrekt bleiben: nichts als Tatsache ausgeben, was erfunden ist.
- Familienfreundlich, keine echten Privatpersonen, keine Marken- oder Filmfiguren.
Regeln für die Bild-Prompts (Englisch):
- Beschreibe exakt eine Szene: wer/was, Pose, Gesichtsausdruck, Ort, Blickwinkel. Hauptmotiv mittig.
- Keine Schrift im Bild. Keine bekannten Figuren, Marken oder realen Personen.
- Wiederkehrende Figuren in jeder Szene gleich beschreiben, damit sie konsistent aussehen.
Antworte ausschließlich mit JSON."""

FORMAT = """Gib JSON in genau diesem Format zurück:
{
  "title": "kurzer, neugierig machender Titel (max. 70 Zeichen, ohne Hashtags)",
  "description": "1–2 Sätze Videobeschreibung",
  "hashtags": ["#shorts", "#…", "… (5–8 passende deutsche Hashtags)"],
  "scenes": [
    {"text": "Sprechertext dieser Szene (1–2 kurze Sätze)",
     "image": "English image prompt for this scene",
     "overlay": "optional: 1–3 Wörter Infokarte in GROSSBUCHSTABEN wie 'VERBOTEN', '22 °C', '8 BEINE' – sonst leerer String"}
  ]
}"""


def new_topic(cat: dict) -> str:
    past = [v["topic"] for v in VIDEOS if v.get("category") == cat["slug"] and v.get("topic")][-60:]
    user = (f"Kategorie: {cat['name']} – {cat['description']}\n"
            f"Stilvorgabe: {cat['script_style']}\n"
            "Schlage EIN konkretes, neues Thema für ein 60-Sekunden-Short vor, das sehr hohe Neugier weckt "
            "und bei deutschsprachigem Publikum funktioniert.\n"
            "Diese Themen gab es schon (nicht wiederholen, auch nicht sehr ähnlich):\n- "
            + ("\n- ".join(past) if past else "(noch keine)")
            + '\nAntworte als JSON: {"topic": "…"}')
    js, _ = ai.chat_json("Du bist Redakteur für virale deutsche Kurzvideos. Antworte nur mit JSON.", user, 1.0)
    topic = str(js.get("topic", "")).strip()
    if not topic:
        raise ai.ProviderError("Kein Thema erhalten")
    return topic


def write_script(cat: dict, topic: str) -> tuple[dict, str]:
    secs = int(cfg("target_seconds") or 60)
    words = round(secs * 2.5)
    scenes = max(6, round(secs / 5))
    char = cfg("main_character") if cfg("use_main_character") else ""
    user = (f"Kategorie: {cat['name']}\nStil: {cat['script_style']}\nThema: {topic}\n"
            f"Länge: ca. {words} Wörter gesprochen (≈ {secs} Sekunden), aufgeteilt auf {scenes} Szenen.\n"
            + (f"Wiederkehrende Hauptfigur (nur wenn passend einbauen, in den Bild-Prompts immer gleich beschreiben): {char}\n" if char else "")
            + "Nutze Infokarten (overlay) sparsam, in etwa jeder dritten Szene.\n" + FORMAT)
    js, provider = ai.chat_json(SYSTEM, user, 0.9)
    sc = [s for s in js.get("scenes", []) if str(s.get("text", "")).strip()]
    if len(sc) < 3:
        raise ai.ProviderError("Drehbuch hat zu wenige Szenen")
    for s in sc:
        s["text"] = " ".join(str(s["text"]).split())
        s["image"] = str(s.get("image") or s["text"])
        s["overlay"] = str(s.get("overlay") or "").strip()[:24]
    tags = [t if str(t).startswith("#") else "#" + str(t) for t in js.get("hashtags", [])]
    tags = [t.replace(" ", "") for t in tags if len(t) > 1]
    if "#shorts" not in [t.lower() for t in tags]:
        tags.insert(0, "#shorts")
    return {"title": str(js.get("title") or topic)[:95], "description": str(js.get("description") or ""),
            "hashtags": tags[:10], "scenes": sc}, provider


def image_prompt(scene: dict, cat: dict) -> str:
    style = cfg("image_style")
    return f"{scene['image']}. Mood: {cat.get('image_mood') or ''}. Style: {style}"
