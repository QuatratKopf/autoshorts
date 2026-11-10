"""Themenfindung (auch aus aktuellen Trends) und Drehbuch mit Titel, Beschreibung, Tags und Thumbnail-Idee."""
import datetime as dt
import os

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
- Erfundene Geschichten (Grusel, Lustiges) klar als Geschichte erzählen ('Stell dir vor …', 'Eine Legende erzählt …'):
  keine erfundenen 'echten' Ereignisse, Trends, Apps, Studien oder Personen als Tatsache ausgeben, und keine Titel wie 'Die Wahrheit über …' dafür.
- Keine Videos über einzelne echte Personen (auch keine Promis): nimm das allgemeine Thema dahinter.
- ALLES auf Deutsch: Sprechertext, Titel, Beschreibung, Titelbild-Text, Orts-/Zeitangaben und jeder Text in Einblendungen
  (Karten, Notizen, Listen, Handy, Balken, A/B-Frage). Keine englischen Wörter oder Gaming-Begriffe wie "Inventory", "Level",
  "Boss", "Respawn", "Fact" – nimm das deutsche Wort (Liste, Stufe, Chef, Fakt). Erlaubt sind nur Eigennamen und Wörter,
  die im Deutschen ganz normal sind (Handy, Internet, App). Deutsche Einheiten und Schreibweise (Liter, Meter, Grad).
- Sprechertext zum Vorlesen schreiben: Zahlen und Einheiten ausschreiben ("dreißigtausend Grad", "zwanzig Prozent"),
  keine Abkürzungen, Klammern, Emojis oder Sonderzeichen; kurze, klare Sätze. In Einblendungen dürfen Ziffern stehen.
- Keine Beleidigungen, nichts Anzügliches, keine echten Privatpersonen, keine Marken- oder Filmfiguren im Bild.
- Baue Themen nie um urheberrechtlich geschützte Figuren, Filme, Serien, Spiele oder Marken (z. B. Godzilla, Pokémon,
  Marvel, Disney, Minecraft). Nimm stattdessen eigene, namenlose Wesen oder echte Natur/Wissenschaft (z. B. 'ein 100 Meter großes Monster').
Regeln für die Bild-Prompts (Englisch):
- Beschreibe exakt eine Szene: wer/was, Pose, Gesichtsausdruck, Ort, Blickwinkel. Hauptmotiv mittig.
- Keine Schrift im Bild. Keine bekannten Figuren, Marken oder realen Personen (auch nicht bei Trend-Themen: stelle sie symbolisch dar).
- Lege wiederkehrende Figuren in "cast" und wiederkehrende Orte in "places" EINMAL genau fest und nutze sie in vielen Szenen –
  so sieht das Video aus wie aus einem Guss (gleiche Figur, gleiches Zimmer). Wenige Orte (1–3), wenige Figuren (1–2).
- Erzählstil wie erfolgreiche Erklär-Shorts: oft aus Sicht einer Figur oder in Du-Perspektive ('Du wachst auf …'), mit Spannung.
Antworte ausschließlich mit JSON."""

FORMAT = """Gib JSON in genau diesem Format zurück:
{
  "title": "kurzer, neugierig machender Titel mit dem wichtigsten Suchbegriff vorne (max. 70 Zeichen, ohne Hashtags, ohne Clickbait-Lügen)",
  "description": "2–3 Sätze: worum es geht (mit Suchbegriffen), was man lernt, und am Ende eine Frage an die Zuschauer für die Kommentare",
  "hashtags": ["#shorts", "… 5–8 passende Hashtags: was auf TikTok gerade läuft (auch englische wie #fyp oder #viral, wenn passend) plus spezifische deutsche"],
  "tags": ["8–15 Suchbegriffe ohne #, z. B. 'spinnen im haus', 'tierfakten'"],
  "thumbnail": {"image": "English prompt for ONE eye-catching cover image: the most surprising moment of the story, close-up, exaggerated facial expression, bold simple composition, strong contrast, empty space in the upper third for text",
                "text": "2–4 deutsche Wörter Cover-Text in GROSSBUCHSTABEN, macht neugierig, verrät die Auflösung nicht"},
  "cast": {"held": "English description of each recurring character (species/body, colors, clothes, face) – identical in every scene"},
  "places": {"zimmer": "English description of each recurring location (room/landscape, colors, key objects)"},
  "hud": "optional: kurze Orts-/Zeitangabe oben links für Geschichten, z. B. 'TAG 1 · 3:12 UHR' – sonst leerer String",
  "countdown": "optional: nur bei Wettlauf gegen die Zeit {\"label\": \"EINSCHLAG IN\", \"seconds\": 900}, sonst null",
  "scenes": [
    {"text": "Sprechertext dieser Szene (1–2 kurze Sätze)",
     "image": "English: ONLY action, pose, facial expression and camera framing of this scene (who/where comes from cast/places)",
     "who": ["held"],
     "place": "zimmer",
     "camera": "zoom_in | zoom_out | pan_left | pan_right | pan_up | shake | still",
     "sfx": "whoosh | pop | boom | ding | tick | none",
     "highlight": ["1–2 Schlüsselwörter aus dem Sprechertext, die in den Untertiteln gelb leuchten"],
     "hud": "optional: neue Orts-/Zeitangabe ab dieser Szene, sonst weglassen",
     "overlay": null}
  ]
}
Einblendungen (overlay) – nutze sie in etwa jeder zweiten Szene, passend zum Inhalt, sonst null:
- {"type": "card", "text": "1–3 WÖRTER"}  große Infokarte: Zahl, Fakt, Warnung (z. B. "VIERMAL HELLER", "-80 °C")
- {"type": "note", "title": "REGEL #2", "text": "kurzer Merksatz"}  Notizzettel für Regeln, Tipps, Merksätze
- {"type": "phone", "title": "3:12", "items": ["Mama: Wo bist du??", "Warnung: Bleib drinnen"]}  Handy mit Nachrichten/Alarmen
- {"type": "checklist", "title": "SPEISEKARTE", "items": [["Motten", true], ["Fliegen", true], ["Käfer", false]]}  Listen, Vergleiche
- {"type": "bar", "label": "WASSER", "value": 24}  Füllstand/Prozent/Energie
- {"type": "counter", "label": "ZUCKER IM SEE", "value": 4.4, "unit": "MRD. TONNEN", "sub": "= 23 JAHRE WELTPRODUKTION"}
  großer Zähler, der hochläuft – für jede beeindruckende Zahl (Menge, Jahre, Grad, Euro, Menschen); "sub" ist optional
- {"type": "choice", "a": "Im Bunker bleiben", "b": "Zu Mama rennen"}  NUR in der letzten Szene von Geschichten: Was würdest du tun?
Kamera: 'shake' bei Schreck/Aufprall (mit sfx 'boom'), sonst ruhige Fahrten; sfx sparsam (nicht in jeder Szene)."""

TOON = """
EIGENE ANIMATION: Das Video wird mit fertigen Cartoon-Figuren, Tieren, Orten und Requisiten animiert (keine KI-Bilder).
Fülle deshalb zusätzlich aus und nutze NUR die genannten Werte:
- "cast": Aussehen je Figur, z. B. {"mia": {"shirt": "blau", "hat": "", "hair": "long", "glasses": false, "skin": "weiß"},
                                   "rex": {"kind": "dino"}}
  Menschen: shirt/hat_color: blau, rot, grün, gelb, orange, lila, pink, türkis, grau, braun · hat: cap, helmet, beanie, bow, crown oder ""
            hair: long, bun oder "" · skin: weiß, hell, mittel, dunkel
  Tiere/Wesen statt Mensch: "kind": cat, dog, spider, ghost, alien, robot, bird, dino, monster, fish, shark
  Höchstens 3 Figuren, jede klar unterscheidbar. Bei Du-Geschichten ist die Hauptfigur „du“.
- In jeder Szene:
  "place": drinnen: bedroom, livingroom, kitchen, bathroom, office, classroom, lab, hospital, basement, supermarket,
           supermarket_empty (leergekaufte Regale), station (Bahnhof), restaurant, cave, underwater, space
           draußen: street (Häuserzeile mit Läden und Straße), park, forest, beach, desert, snow, mountain, farm, village,
           gasstation, powerplant, graveyard, ruins, camp (Zelte), moon
           (genau eines dieser Wörter – jede Szene braucht einen Ort aus dieser Liste, auch Ereignis-Einstellungen)
  "backdrop": für Landschaften draußen statt "place" – ein Baukasten, mit dem JEDE Umgebung passend gebaut wird:
           {"sky": "day|night|sunset|storm|red|haze", "ground": "grass|sand|snow|road|rock|soil|dry|water|ice|lava",
            "elements": [bis zu 4 aus: mountains, hills, dunes, forest, trees, deadtrees, palms, cactus, city (Skyline),
                         street (Häuserzeile), village, ruins, factory, powerplant, farm, gasstation, bridge, powerlines,
                         windturbines, camp, graves, sea, glacier, fields, river, dryriver, lake, cracks, rocks, flowers]}
           Beispiele: Wald mit Fluss = {"elements": ["forest", "river"]} · Dürre = {"sky": "haze", "ground": "dry",
           "elements": ["deadtrees", "dryriver"]} · Bauernhof = {"elements": ["farm", "fields"]} · zerstörte Stadt =
           {"sky": "red", "ground": "road", "elements": ["ruins"]} · Bergsee = {"elements": ["mountains", "lake", "flowers"]}
  DER HINTERGRUND MUSS ZUM SATZ PASSEN: Redet der Sprecher vom Wald, ist ein Wald zu sehen; bei Flüssen ein Fluss, bei Ernte
  ein Feld, beim Meer das Meer. Nimm "street" nur, wenn es wirklich um die Stadt geht – nie als Verlegenheitslösung.
  Wechsle den Hintergrund, sobald der Text den Schauplatz wechselt.
  "time": "day" oder "night"
  "weather": rain, storm, snow, wind, heat, dark, ash (Ascheregen), quake (Erdbeben: Bild wackelt) oder ""
  "props": 0–2 Requisiten. Alle Dinge erscheinen automatisch in echter Größe im Verhältnis zu den Menschen.
           Dinge: car, bus, truck, bike, house, tree, rock, box, cart (Einkaufswagen), shelf (Regal), fridge, table, tv, computer,
                  money, cans (Konserven), canister, candle, generator, tent, fire, streetlamp, trafficlight, rocket, sprout
           Himmel/Natur (Schaubilder, groß): plane, satellite, ship, ufo, meteor, explosion, earth, sun, moon, tornado, wave,
                  flood, ice, volcano, cloud, stormcloud, lightning, crack, smoke, aurora, eclipse
           (meteor fällt und schlägt ein, rocket startet, wave/flood steigen, crack reißt den Boden auf, eclipse verdunkelt
            die Sonne, sprout wächst zur Blume, volcano spuckt Lava)
           Nimm nur Requisiten, die an diesen Ort gehören (kein Karton mitten auf der Straße als Ersatz für einen Supermarkt –
           dafür gibt es den Ort "supermarket").
  "actors": 1–2 Figuren, z. B. [{"id": "mia", "action": "run", "emotion": "scared", "emote": "!", "pos": "offleft", "to": "center", "speaks": true}]
     action: idle, talk, walk, run, wave, point, shocked, sad, jump, think, sit, sleep, dance, look_around, fall
     emotion: happy, sad, angry, scared, worried, shocked oder ""
     emote (Symbol über dem Kopf, sparsam): "!", "?", heart, idea, sweat, anger, music oder ""
     pos / to: left, center, right, offleft, offright ("to" nur wenn die Figur sich bewegt)
     speaks: true bei der Figur, um die es in dieser Szene geht
     hold (optional, Gegenstand in der Hand): phone, flashlight, bag, bottle, umbrella, sign, map, radio
     Die Gefühle müssen zum Satz passen: niemand ist erschrocken oder panisch, wenn der Satz ruhig oder sachlich ist.
  "crowd": Menschen im Bild, die die Stimmung zeigen (draußen und in Supermarkt, Bahnhof, Krankenhaus, Büro, Schule):
           "walk" (Alltag, Leute gehen vorbei), "worried" (stehen unruhig, sehen sich besorgt um), "panic" (rennen in Panik
           durcheinander – NUR wenn der Satz wirklich von Panik, Flucht oder Schreien handelt), "cheer" (jubeln),
           "sad" (stehen gebeugt), "watch" (staunen, zeigen) oder ""
  "mood": Stimmung der Szene als Farbe/Wirkung: "calm", "tense", "panic", "scary", "sad" oder "happy" – genau so stark wie
          der Satz. Die meisten Szenen sind "calm" oder "tense"; "panic" höchstens in ein bis zwei Szenen am Höhepunkt.
          Sachliche Erklärungen sind "calm".
  JEDE SZENE BRAUCHT SICHTBARE BEWEGUNG: Figur, die etwas tut, eine Menschenmenge, animierte Requisite oder Wetter.
  Kein leeres Standbild.
  "shot": "event" = Ereignis-Einstellung: das Geschehen (Requisiten, Wetter, Ort) füllt das Bild, "actors" ist [] oder
          höchstens eine kleine Figur am Rand, die zuschaut · "close" = Nahaufnahme einer Figur (selten, nur bei starker
          Reaktion) · "insert" = ein einzelner Gegenstand aus "props" groß und allein im Bild, wenn der Satz genau von
          diesem Ding handelt (z. B. Kühlschrank, Kerze, Konserven) · sonst "wide"
- WICHTIG – das Thema zeigen, nicht die Figur: Die Figuren sind Nebensache und klein im Bild. Immer wenn der Sprecher über
  Natur, Wetter, Weltall, Katastrophen, Tiere oder ein Phänomen redet, nimm "shot": "event" mit passenden Requisiten, Wetter
  und Ort (z. B. Vulkanausbruch: place mountain, props ["volcano","smoke"], weather "ash", actors []). Bei Natur-,
  Wissens- und What-If-Themen ist mindestens jede zweite Szene eine Ereignis-Einstellung. Figuren zeigen nur kurz die
  Reaktion oder die Folgen für Menschen.
- Wechsle Orte, Aktionen und Requisiten ab: nicht zweimal hintereinander dieselbe Kombination; jede Szene zeigt sichtbar,
  wovon der Sprecher gerade redet (Bewegung statt Herumstehen: reinkommen, rennen, erschrecken, zeigen, springen).
- Erklärendes (Zahlen, Listen, Regeln) kommt in die Einblendungen (overlay).
- "thumbnail": {"text": "2–4 deutsche WÖRTER", "place": "...", "time": "day|night", "actor": "id aus cast", "action": "shocked",
                "emotion": "shocked", "props": ["meteor"], "weather": ""}  – der spannendste Moment als Titelbild,
                am besten mit dem Ereignis (Requisite) groß im Bild.
- "image" je Szene darf leer bleiben.
- "wishes": Liste (deutsch, je 1–3 Wörter) von Dingen, die du für dieses Video gebraucht hättest, die es aber in den Listen
  oben nicht gibt (z. B. "Krebs", "Windrad", "Wasserfall"). Leere Liste, wenn alles da war."""

UNSUITABLE = ("Ungeeignet sind: Themen, die sich um einzelne echte Personen drehen (Promis, Musiker, Sportler, Politiker, Creator), Todesfälle, Unglücke, Verbrechen, Krieg, Terror, Krankheiten einzelner Personen, "
              "Parteipolitik und Wahlen, Klatsch über Privatleben, Glücksspiel, geschützte Film-/Spielfiguren und Marken als Hauptthema, reine Sport-Ergebnisse ohne Hintergrundgeschichte "
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
            "WICHTIG: Das Thema muss wirklich zur Kategorie passen (z. B. Tierwelt = ein echtes Tier steht im Mittelpunkt; "
            "Grusel = eine Gruselgeschichte). Passt kein Trend sauber, antworte mit {\"index\": null} – lieber kein Trend als ein unpassender. "
            "Marken, Spiele, Filme, Serien und Apps dürfen nur der Anlass sein, nie das Thema selbst: mach daraus das allgemeine Thema "
            "dahinter (statt eines Spiels z. B. 'Warum wir Nostalgie lieben').\n"
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
    words = round(secs * (2.05 if str(cfg("tts_provider") or "") == "gemini" else 2.2))   # Gemini-Erzähler spricht ruhiger
    scenes = max(6, round(secs / 5))
    toon = str(os.environ.get("AS_VISUAL") or cfg("visual_mode") or "ai") == "toon"
    char = cfg("main_character") if cfg("use_main_character") and not toon else ""
    ctx = ""
    if trend:
        heads = "\n".join(f"- {n['title']} ({n.get('source', '')})" for n in trend.get("news", []))
        ctx = (f"Aktueller Anlass: „{trend['title']}“ ist gerade im Trend ({trend['source']}).\n"
               + (f"Schlagzeilen dazu:\n{heads}\n" if heads else "")
               + (f"Hintergrund: {trend['summary']}\n" if trend.get("summary") else "")
               + "Nutze den Anlass im Hook, erkläre dann den zeitlosen, belegbaren Hintergrund.\n")
    user = (f"Kategorie: {cat['name']}\nStil: {cat['script_style']}\nThema: {topic}\n{ctx}"
            + (f"Zielgruppe: {audience()}\n" if audience() else "")
            + f"Länge: zwischen {round(words * 0.85)} und {words} Wörter gesprochen insgesamt (≈ {secs} Sekunden) – zähle nach; nicht kürzer, nicht länger. "
            f"Aufgeteilt auf {scenes} Szenen, also etwa {round(words / scenes)} Wörter pro Szene.\n"
            + (f"Wiederkehrende Hauptfigur (nur wenn passend einbauen, in den Bild-Prompts immer gleich beschreiben): {char}\n" if char else "")
            + FORMAT + (TOON if toon else ""))
    js, provider = ai.chat_json(SYSTEM, user, 0.9)
    n_words = sum(len(str(x.get("text", "")).split()) for x in js.get("scenes", []) if isinstance(x, dict))
    if n_words > words * 1.25:       # zu lang geraten → einmal straffen lassen
        ai.log(f"Drehbuch hat {n_words} Wörter statt {words} – lasse es kürzen")
        try:
            js2, provider = ai.chat_json(SYSTEM, user + f"\n\nACHTUNG: Dein letzter Entwurf hatte {n_words} Wörter Sprechertext. "
                                         f"Schreibe das Drehbuch neu mit {round(words * 0.9)} bis {words} Wörtern insgesamt (nicht weniger!), "
                                         f"etwa {max(6, round(words / scenes))} Wörter pro Szene, gleiche Szenenzahl.", 0.7)
            n2 = sum(len(str(x.get("text", "")).split()) for x in js2.get("scenes", []) if isinstance(x, dict))
            if words * 0.75 <= n2 < n_words:
                js = js2
        except Exception as e:  # noqa: BLE001
            ai.log(f"Kürzen nicht möglich ({e}) – nehme den ersten Entwurf")
    sc = [s for s in js.get("scenes", []) if isinstance(s, dict) and str(s.get("text", "")).strip()]
    if len(sc) < 3:
        raise ai.ProviderError("Drehbuch hat zu wenige Szenen")
    raw_cast = js.get("cast") if isinstance(js.get("cast"), dict) else {}
    cast = {str(k): (str(v) if not isinstance(v, dict) else "") for k, v in raw_cast.items() if v}
    places = {str(k): str(v) for k, v in (js.get("places") or {}).items() if v} if isinstance(js.get("places"), dict) else {}
    for s in sc:
        s["text"] = " ".join(str(s["text"]).split())
        s["image"] = str(s.get("image") or s["text"])
        ov = s.get("overlay")
        if isinstance(ov, str):   # altes Format: nur Text
            ov = {"type": "card", "text": ov} if ov.strip() else None
        s["overlay"] = ov if isinstance(ov, dict) and ov.get("type") else None
        who = s.get("who") or []
        who = [who] if isinstance(who, str) else who
        s["who_desc"] = "; ".join(cast[w] for w in who if w in cast)
        s["place_desc"] = places.get(str(s.get("place") or ""), "")
        s["highlight"] = [str(h) for h in (s.get("highlight") or []) if str(h).strip()][:3]
        s["camera"] = str(s.get("camera") or "")
        s["sfx"] = str(s.get("sfx") or "")
        s["hud"] = str(s.get("hud") or "").strip()
    tags = [t if str(t).startswith("#") else "#" + str(t) for t in js.get("hashtags", [])]
    tags = [t.replace(" ", "") for t in tags if len(t) > 1]
    if "#shorts" not in [t.lower() for t in tags]:
        tags.insert(0, "#shorts")
    th = js.get("thumbnail") if isinstance(js.get("thumbnail"), dict) else {}
    return {"title": str(js.get("title") or topic)[:95], "description": str(js.get("description") or ""),
            "hashtags": tags[:10], "tags": [str(t).strip("# ")[:60] for t in js.get("tags", []) if str(t).strip("# ")][:15],
            "thumbnail": {**th, "image": str(th.get("image") or sc[0]["image"]), "text": str(th.get("text") or "").strip()[:40]},
            "wishes": [str(w)[:40] for w in (js.get("wishes") or []) if str(w).strip()][:8] if isinstance(js.get("wishes"), list) else [],
            "toon": toon, "cast": {str(k): v for k, v in raw_cast.items() if isinstance(v, dict)},
            "scenes": sc, "hud": str(js.get("hud") or "").strip()[:28],
            "countdown": js.get("countdown") if isinstance(js.get("countdown"), dict) else None}, provider


def image_prompt(scene: dict, cat: dict) -> str:
    style = cfg("image_style")
    who = f" Characters: {scene['who_desc']}." if scene.get("who_desc") else ""
    where = f" Setting: {scene['place_desc']}." if scene.get("place_desc") else ""
    return f"{scene['image']}.{who}{where} Mood: {cat.get('image_mood') or ''}. Style: {style}"
