"""Themenfindung (auch aus aktuellen Trends) und Drehbuch mit Titel, Beschreibung, Tags und Thumbnail-Idee."""
import datetime as dt

from . import ai, trends
from .state import VIDEOS, cfg


def audience():
    return str(cfg("audience") or "").strip()

SYSTEM = """Du schreibst virale deutsche Kurzvideos (YouTube Shorts / TikTok) im Stil animierter Cartoon-Erklärvideos.
Regeln für die Sprechertexte:
- Der erste Satz ist ein starker Hook (Frage, überraschende Behauptung oder Konflikt) – keine Begrüßung, kein "Heute erkläre ich".
- Gesprochene, einfache Sprache, kurze Sätze, Du-Ansprache erlaubt. Zahlen ausschreiben, wie man sie spricht.
- Keine Emojis, keine Regieanweisungen, keine Klammern im Sprechertext.
- Der letzte Satz ist eine Pointe oder Wendung, gern mit kurzer Aufforderung wie "Folg für mehr".
- Inhaltlich korrekt bleiben: nichts als Tatsache ausgeben, was erfunden ist. Bei aktuellen Themen nur das verwenden,
  was in den mitgelieferten Schlagzeilen steht oder allgemein bekanntes Hintergrundwissen ist; keine erfundenen Details,
  Zitate oder Zahlen. Lieber den zeitlosen Hintergrund erklären als Gerüchte wiedergeben.
- Ton für eine junge TikTok-Zielgruppe: locker, direkt, selbstbewusst, gern mit aktueller Umgangssprache, aber nicht cringe
  oder übertrieben jugendlich. Nie belehrend, nie wie für Kinder.
- Keine Beleidigungen, nichts Anzügliches, keine echten Privatpersonen, keine Marken- oder Filmfiguren im Bild.
Regeln für die Bild-Prompts (Englisch):
- Beschreibe exakt eine Szene: wer/was, Pose, Gesichtsausdruck, Ort, Blickwinkel. Hauptmotiv mittig.
- Keine Schrift im Bild. Keine bekannten Figuren, Marken oder realen Personen (auch nicht bei Trend-Themen: stelle sie symbolisch dar).
- Wiederkehrende Figuren in jeder Szene gleich beschreiben, damit sie konsistent aussehen.
Antworte ausschließlich mit JSON."""

FORMAT = """Gib JSON in genau diesem Format zurück:
{
  "title": "kurzer, neugierig machender Titel mit dem wichtigsten Suchbegriff vorne (max. 70 Zeichen, ohne Hashtags, ohne Clickbait-Lügen)",
  "description": "2–3 Sätze: worum es geht (mit Suchbegriffen), was man lernt, und am Ende eine Frage an die Zuschauer für die Kommentare",
  "hashtags": ["#shorts", "… 5–8 passende Hashtags: was auf TikTok gerade läuft (auch englische wie #fyp oder #viral, wenn passend) plus spezifische deutsche"],
  "tags": ["8–15 Suchbegriffe ohne #, z. B. 'spinnen im haus', 'tierfakten'"],
  "thumbnail": {"image": "English prompt for ONE eye-catching cover image: the most surprising moment of the story, close-up, exaggerated facial expression, bold simple composition, strong contrast, empty space in the upper third for text",
                "text": "2–4 Wörter Cover-Text in GROSSBUCHSTABEN, macht neugierig, verrät die Auflösung nicht"},
  "scenes": [
    {"text": "Sprechertext dieser Szene (1–2 kurze Sätze)",
     "image": "English image prompt for this scene",
     "overlay": "optional: 1–3 Wörter Infokarte in GROSSBUCHSTABEN wie 'VERBOTEN', '22 °C', '8 BEINE' – sonst leerer String"}
  ]
}"""

UNSUITABLE = ("Ungeeignet sind: Todesfälle, Unglücke, Verbrechen, Krieg, Terror, Krankheiten einzelner Personen, "
              "Parteipolitik und Wahlen, Klatsch über Privatleben, Glücksspiel, reine Sport-Ergebnisse ohne Hintergrundgeschichte "
              "und alles, was ohne Belege Spekulation wäre.")


def _past(cat):
    return [v["topic"] for v in VIDEOS if v.get("category") == cat["slug"] and v.get("topic")][-60:]


def new_topic(cat: dict) -> str:
    past = _past(cat)
    user = (f"Kategorie: {cat['name']} – {cat['description']}\n"
            f"Stilvorgabe: {cat['script_style']}\n"
            + (f"Zielgruppe: {audience()}\n" if audience() else "")
            + "Schlage EIN konkretes, neues Thema für ein 60-Sekunden-Short vor, das sehr hohe Neugier weckt "
            "und bei dieser Zielgruppe auf TikTok funktioniert (Thema, über das man in der Bubble redet, oder das man sofort teilen will).\n"
            "Diese Themen gab es schon (nicht wiederholen, auch nicht sehr ähnlich):\n- "
            + ("\n- ".join(past) if past else "(noch keine)")
            + '\nAntworte als JSON: {"topic": "…"}')
    js, _ = ai.chat_json("Du bist Redakteur für virale deutsche Kurzvideos. Antworte nur mit JSON.", user, 1.0)
    topic = str(js.get("topic", "")).strip()
    if not topic:
        raise ai.ProviderError("Kein Thema erhalten")
    return topic


def trend_topic(cat: dict):
    """Wählt aus den aktuellen Trends ein Thema, das zur Kategorie passt. Gibt (thema, trend) oder (None, None)."""
    items = trends.current()
    if not items:
        return None, None
    past = _past(cat)
    user = (f"Heute ist {dt.date.today():%d.%m.%Y}. Kategorie: {cat['name']} – {cat['description']}\n"
            f"Stilvorgabe: {cat['script_style']}\n"
            + (f"Zielgruppe: {audience()}\n" if audience() else "")
            + "\nDas ist gerade in den USA und in Deutschland im Trend (TikTok-Sounds, Reddit, "
            "Google-Suchen, Wikipedia):\n"
            f"{trends.as_prompt_list(items)}\n\n"
            "Wähle EINEN Trend, über den die Zielgruppe gerade redet, und mach daraus ein Short in dieser Kategorie, "
            "das ein deutsches Gen-Z-Publikum auf TikTok sofort anspricht. Bevorzuge in dieser Reihenfolge: "
            "TikTok-Trends, Internet-Kultur und Memes, Gaming, Musik und Artists, Serien und Filme, Creator, Tech und Apps, "
            "virale Momente aus den USA, die in Deutschland noch neu sind. "
            "Meide Lokalnachrichten (Stadtfeste, Regionales), Börse, Wetter, Randsportarten und alles, was nur ältere Leute interessiert. "
            "Ein TikTok-Sound ist nur geeignet, wenn du den Song, den Artist oder den Trend dazu sicher kennst – sonst lieber einen anderen Trend. "
            "Am besten: ein überraschender Fakt, die Geschichte dahinter oder eine Erklärung, warum alle gerade darüber reden, "
            "die auch in ein paar Tagen noch stimmt. " + UNSUITABLE + "\n"
            "Diese Themen gab es schon:\n- " + ("\n- ".join(past) if past else "(noch keine)") + "\n"
            'Antworte als JSON: {"index": Nummer des Trends, "topic": "konkretes Video-Thema auf Deutsch", "why": "kurz, warum es passt"} '
            'oder {"index": null}, wenn keiner passt.')
    js, _ = ai.chat_json("Du bist Trend-Scout für einen deutschen Gen-Z-TikTok-Kanal und kennst die Internet-Kultur in den USA "
                          "und Deutschland. Sorgfältig bei Fakten. Antworte nur mit JSON.", user, 0.7)
    idx, topic = js.get("index"), str(js.get("topic") or "").strip()
    if idx is None or not topic:
        return None, None
    try:
        tr = items[int(idx)]
    except (ValueError, IndexError, TypeError):
        return None, None
    return topic, {"title": tr["title"], "source": tr["source"], "news": tr.get("news", [])[:3], "summary": tr.get("summary", "")}


def write_script(cat: dict, topic: str, trend=None) -> tuple[dict, str]:
    secs = int(cfg("target_seconds") or 60)
    words = round(secs * 2.5)
    scenes = max(6, round(secs / 5))
    char = cfg("main_character") if cfg("use_main_character") else ""
    ctx = ""
    if trend:
        heads = "\n".join(f"- {n['title']} ({n.get('source', '')})" for n in trend.get("news", []))
        ctx = (f"Aktueller Anlass: „{trend['title']}“ ist gerade im Trend ({trend['source']}).\n"
               + (f"Schlagzeilen dazu:\n{heads}\n" if heads else "")
               + (f"Hintergrund: {trend['summary']}\n" if trend.get("summary") else "")
               + "Nutze den Anlass im Hook, erkläre dann den zeitlosen, belegbaren Hintergrund.\n")
    user = (f"Kategorie: {cat['name']}\nStil: {cat['script_style']}\nThema: {topic}\n{ctx}"
            + (f"Zielgruppe: {audience()}\n" if audience() else "")
            + f"Länge: ca. {words} Wörter gesprochen (≈ {secs} Sekunden), aufgeteilt auf {scenes} Szenen.\n"
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
    th = js.get("thumbnail") or {}
    return {"title": str(js.get("title") or topic)[:95], "description": str(js.get("description") or ""),
            "hashtags": tags[:10], "tags": [str(t).strip("# ")[:60] for t in js.get("tags", []) if str(t).strip("# ")][:15],
            "thumbnail": {"image": str(th.get("image") or sc[0]["image"]), "text": str(th.get("text") or "").strip()[:40]},
            "scenes": sc}, provider


def image_prompt(scene: dict, cat: dict) -> str:
    style = cfg("image_style")
    return f"{scene['image']}. Mood: {cat.get('image_mood') or ''}. Style: {style}"
