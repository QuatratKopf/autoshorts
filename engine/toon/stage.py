"""Bühne: setzt Figuren, Tiere und Requisiten auf einen Ort und rendert die Szene Bild für Bild (30 fps) als Video.
Figuren bewegen sich (gehen, rennen, springen …), blinzeln und bewegen den Mund passend zur Sprecherstimme;
dazu Wetter, Gefühls-Symbole und kleine Bewegungen im Hintergrund."""
import math
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from . import extras, graphics, places, rig
from .. import hyper

W, H, FPS = 1080, 1920, 30
SCALE = 1.08            # Figuren bewusst kleiner: die Szene steht im Mittelpunkt
POS = {"left": 250, "center": 540, "right": 830, "offleft": -260, "offright": 1340,
       "links": 250, "mitte": 540, "rechts": 830}
CALL_ARM = (106, 70)    # Oberarm/Unterarm für „Handy am Ohr“
TALL_OV = ("phone", "checklist", "note")
NO_FURNITURE = ("restaurant", "diningroom", "bathroom", "hallway", "supermarket", "supermarket_empty", "station", "transit", "basement", "attic", "hospital", "serverroom", "chapel", "tattoostudio", "nailstudio", "barbershop", "hairsalon", "controlroom", "throneroom", "royalmuseum")
MAIN_IDS = ("du", "ich", "held", "hero", "main", "erzähler", "narrator", "a0")


def _x(v, default):
    if isinstance(v, (int, float)):
        return float(v)
    return float(POS.get(str(v or "").lower().strip(), default))


_VOWEL = re.compile(r"ie|ei|ai|au|eu|äu|[aeiouäöüy]")
_SYL = {}


def _syllables(word, dur):
    """Mundformen eines Wortes: je Silbe (Vokalgruppe) a = offen, o = rund, e = breit."""
    key = (word, round(dur, 2))
    if key not in _SYL:
        groups = _VOWEL.findall(str(word).lower())
        if not groups:                                     # Zahlen, Abkürzungen: Silben aus der Sprechdauer schätzen
            groups = ["a", "e", "o"] * 8
            groups = groups[:max(1, round(dur / 0.17))]
        _SYL[key] = ["o" if g in ("eu", "äu") or g[0] in "ouöü" else "e" if g in ("ie",) or g[0] in "eiy" else "a" for g in groups]
    return _SYL[key]


OPEN = {"a": 0.95, "o": 0.62, "e": 0.5}


def _mouth(t_abs, words):
    """(Öffnung 0..1, Mundform) passend zum gesprochenen Wort: jede Silbe öffnet den Mund in der Form ihres Vokals und schließt
    ihn wieder; zwischen Wörtern und in Pausen ist er zu – kein gleichmäßiges Auf und Zu."""
    for w, s, e in words:
        if s <= t_abs <= e:
            syl = _syllables(w, e - s)
            n = len(syl)
            seg = (e - s) / n
            i = min(n - 1, int((t_abs - s) / max(1e-3, seg)))
            x = (t_abs - s - i * seg) / max(1e-3, seg)
            amp = OPEN[syl[i]] * (0.6 if seg < 0.07 else 1.0) * (1.0 if i == 0 else 0.85)
            return amp * math.sin(math.pi * min(1.0, max(0.0, x))) ** 0.6, syl[i]
        if s > t_abs:
            break
    return 0.0, "a"


_LIPS = re.compile(r"\b(ich|mir|mich|mein\w*|wir|uns|unser\w*)\b|[„“\"»«]", re.I)


def lips(text):
    """Bewegt die Figur die Lippen zum Text? Nur wenn sie selbst spricht (Ich-/Wir-Erzählung, wörtliche Rede).
    Erzählt die Stimme über sie („Du wachst auf …“, Fakten), hört sie zu und spielt mit Mimik und Gesten."""
    return bool(_LIPS.search(str(text or "")))


# Gesten zum Inhalt: (Name, Wörter) – höhere Zeile hat Vorrang
CUES = [
    ("shock", r"plötzlich|explo\w*|tot|tödlich\w*|gefährlich\w*|katastroph\w*|panik|schrei\w*|unglaublich\w*|krass\w*|wahnsinn\w*|achtung|vorsicht|horror"),
    ("shrug", r""),                                       # Frage: Wort mit „?“
    ("no", r"nicht|nie|niemals|kein|keine[nmrs]?|nein|nichts|falsch|verboten|niemand"),
    ("wide", r"riesig\w*|gigantisch\w*|enorm\w*|millionen?|milliarden?|tausende?|unendlich\w*|überall|größte[nmrs]?|komplett|gewaltig\w*"),
    ("sad", r"leider|traurig\w*|verloren|verliert|stirbt|starb|einsam\w*|vermiss\w*|weint|weinen"),
    ("happy", r"toll\w*|genial\w*|super|endlich|glück\w*|gewinn\w*|lustig\w*|freu\w*|perfekt\w*|cool\w*|lieblings\w*"),
    ("think", r"vielleicht|eigentlich|warum|wieso|weshalb|überleg\w*|nachdenk\w*|rätsel\w*|theorie|angeblich|geheimnis\w*"),
    ("count", r"erstens|zweitens|drittens|zuerst|nummer|schritt"),
    ("nod", r"ja|genau|richtig|stimmt|tatsächlich|wirklich"),
    ("self", r"ich|mir|mich|mein\w*"),
    ("you", r"du|dich|dein\w*"),
]
_CUE_RE = [(n, re.compile(r"^(?:" + rx + r")$")) for n, rx in CUES if rx]
GAP = 1.1                       # Sekunden Ruhe zwischen zwei Gesten (so lang wie eine Geste: nichts springt mitten hinein)


def gesture_plan(scene_words, t0, talking):
    """Wann die Figur welche Geste macht: passend zum Wort, das gerade fällt (Frage → Schultern hoch, „nie“ → Kopfschütteln,
    „riesig“ → Arme weit, „plötzlich“ → Hände an den Kopf …). Zwischen zwei Gesten mindestens GAP Sekunden Ruhe.
    talking: Figur spricht selbst (dann auch ich/du-Gesten und Betonungen); sonst nur Reaktionen auf den Inhalt."""
    prio = {n: i for i, (n, _) in enumerate(CUES)}
    cand = []
    for w, s, e in scene_words:
        raw = str(w)
        low = raw.lower().strip(".,;:!?…\"'„“»«()–-")
        if raw.rstrip("\"'“»)").endswith("?"):
            cand.append((prio["shrug"], s - t0, "shrug"))
            continue
        for n, rx in _CUE_RE:
            if n in ("self", "you") and not talking:
                continue
            if rx.match(low):
                cand.append((prio[n], s - t0 - 0.12, n))
                break
    plan = []
    for _, st, n in sorted(cand):
        if all(abs(st - q) >= GAP for q, _ in plan):
            plan.append((max(0.0, st), n))
    if talking:                                            # wer spricht, betont lange Wörter mit der Hand – aber nicht ununterbrochen
        for w, s, e in sorted(scene_words, key=lambda x: -len(str(x[0]))):
            st = s - t0 - 0.1
            if len(str(w).strip(".,!?")) >= 7 and all(abs(st - q) >= GAP * 1.6 for q, _ in plan):
                plan.append((max(0.0, st), "beat"))
    return sorted(plan)


def _gest_at(plan, t):
    cur = None
    for st, n in plan or ():
        if st <= t:
            cur = (n, t - st)
        else:
            break
    return cur


def _ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 2.2


def _shadow(frame, x, y, w):
    ImageDraw.Draw(frame, "RGBA").ellipse((x - w, y - w * 0.16, x + w, y + w * 0.16), fill=(0, 0, 0, 70))


def _zzz(d, pose, hx, hy, t):
    if pose.extra.get("zzz"):
        for i in range(3):
            ph = (t * 0.7 + i * 0.33) % 1
            s = 30 + 30 * ph
            x, y = hx + 60 + ph * 120, hy - 80 - ph * 220
            d.line((x, y, x + s, y, x, y + s, x + s, y + s), fill=(255, 255, 255, int(255 * (1 - ph))), width=8, joint="curve")
    if "dots" in pose.extra:
        for i in range(pose.extra["dots"]):
            d.ellipse((hx + 150 + i * 46, hy - 170, hx + 180 + i * 46, hy - 140), fill=(255, 255, 255, 255), outline=rig.INK, width=4)


def sanitize(sc):
    """Bringt eine Szene aus dem Drehbuch in saubere Form – egal, was die Text-KI geliefert hat (falsche Typen, Unsinn)."""
    if not isinstance(sc, dict):
        return {}
    def word(v):
        return v.strip() if isinstance(v, str) else ""
    sc["text"] = sc.get("text") if isinstance(sc.get("text"), str) else ""
    for k in ("time", "weather", "crowd", "mood", "shot"):
        sc[k] = word(sc.get(k)).lower()
    sc["float"] = sc.get("float") if sc.get("float") in ("float", "drop") else ""      # Schwerelosigkeit (setzt die Regie)
    sc["graphic"] = graphics.clean(sc.get("graphic"))
    if sc["shot"] == "graphic" and not sc["graphic"]:
        sc["shot"] = ""
    if sc["shot"] == "mirror" and str(sc.get("mirror") or "") not in MIRROR_STATES:
        sc["shot"] = ""
    if sc["shot"] not in ("event", "close", "insert", "graphic", "mirror"):
        sc["shot"] = ""                                   # "wide" und Unbekanntes = normale Einstellung
    if not isinstance(sc.get("place"), str):
        sc["place"] = ""
    b = sc.get("backdrop")
    if isinstance(b, dict):
        els = b.get("elements") if isinstance(b.get("elements"), (list, tuple)) else []
        b = {"sky": word(b.get("sky")), "ground": word(b.get("ground")), "elements": [e for e in els if isinstance(e, str) and e.strip()]}
        sc["backdrop"] = b if (b["elements"] or b["ground"] or b["sky"]) else None
    else:
        sc["backdrop"] = None
    props = []
    for q in (sc.get("props") if isinstance(sc.get("props"), (list, tuple)) else []):
        if isinstance(q, str) and q.strip():
            props.append({"type": q.strip()})
        elif isinstance(q, dict) and isinstance(q.get("type"), str) and q["type"].strip():
            props.append({"type": q["type"].strip(), **({"pos": q["pos"]} if isinstance(q.get("pos"), (str, int, float)) and not isinstance(q.get("pos"), bool) else {}),
                          **({"count": max(1, min(7, int(q["count"])))} if isinstance(q.get("count"), (int, float)) and not isinstance(q.get("count"), bool) else {})})
    sc["props"] = props
    if "actors" in sc:
        acts = []
        for a in (sc.get("actors") if isinstance(sc.get("actors"), (list, tuple)) else []):
            if not isinstance(a, dict):
                continue
            c = {"id": str(a.get("id")) if isinstance(a.get("id"), (str, int)) and not isinstance(a.get("id"), bool) else "held",
                 "speaks": a.get("speaks") is True, **({"hero": True} if a.get("hero") is True else {})}
            if isinstance(a.get("_ksz"), (int, float)) and not isinstance(a.get("_ksz"), bool):
                c["_ksz"] = float(a["_ksz"])               # Größe je Figur, von der Regie gesetzt (stage._tiny_story)
            if a.get("_awake") is True:
                c["_awake"] = True                         # liegt wach im Bett am Handy, von der Regie gesetzt (stage._speech)
            if a.get("_jog") is True:
                c["_jog"] = True                           # Dauerlauf, von der Regie gesetzt (stage._jogging)
            if a.get("_outfit") in ("modern", "period", "king", "guard", "exo", "exo_off"):
                c["_outfit"] = a["_outfit"]                # Kleidung der Zeit, von der Regie gesetzt (stage._past_story); exo = Exoskelett (stage._exo_story)
            if a.get("_lift") == "barbell":
                c["_lift"] = "barbell"                     # stemmt eine Langhantel über den Kopf, von der Regie gesetzt (stage._exo_story)
            for k in ("action", "emotion", "emote", "kind", "hold", "facing"):
                c[k] = word(a.get(k)) if k == "emote" else word(a.get(k)).lower()
            if isinstance(a.get("look"), dict):               # Nebenfiguren der Regie bringen ihr Aussehen mit
                c["look"] = {k: v for k, v in a["look"].items() if k in ("shirt", "hair", "hat", "glasses", "skin", "hair_color", "gender", "size", "outfit", "hat_color") and isinstance(v, (str, bool, int, float))}
            if isinstance(a.get("teeth"), str) and a["teeth"].lower() in TEETH_COLORS:
                c["teeth"] = a["teeth"].lower()
            if str(a.get("wear") or "").lower() == "headphones":   # Kopfhörer auf dem Kopf (setzt die Regie: _music)
                c["wear"] = "headphones"
            say = a.get("say")
            c["say"] = "".join(ch for ch in say if ch not in "{}<>\\").strip()[:16] if isinstance(say, str) else ""
            for k in ("pos", "to"):
                v = a.get(k)
                if (isinstance(v, str) and v.strip()) or (isinstance(v, (int, float)) and not isinstance(v, bool)):
                    c[k] = v
            acts.append(c)
        sc["actors"] = acts
    sc["overlay"] = sc.get("overlay") if isinstance(sc.get("overlay"), dict) else None
    return sc


def clock_time(text):
    """Uhrzeit, die der Satz nennt („Drei Uhr zwölf“, „um 3:12 Uhr“, „kurz nach vier Uhr“) als (Stunde, Minute) – sonst None."""
    import re as _re
    low = str(text or "").lower()
    m = _re.search(r"\b(\d{1,2})[:.](\d{2})\s*uhr\b", low)
    if m and int(m.group(1)) < 24 and int(m.group(2)) < 60:
        return int(m.group(1)), int(m.group(2))
    if _re.search(r"mitternacht", low):
        return 0, 0
    m = _re.search(r"\b([a-zäöüß]+|\d{1,2})\s+uhr\b(?:\s+([a-zäöüß]+|\d{1,2})\b)?", low)
    if not m:
        return None
    hh = _number(m.group(1))
    if hh is None or hh != int(hh) or not 0 <= hh < 24:
        return None
    mm = _number(m.group(2)) if m.group(2) and m.group(2) not in ("ein", "eine", "einen", "nachts", "morgens", "früh") else None
    return int(hh), int(mm) if mm is not None and mm == int(mm) and 0 <= mm < 60 else 0


def _prepare(scene, cast):
    scene = sanitize(scene)
    cast = cast if isinstance(cast, dict) else {}
    place = places.resolve(backdrop(scene))
    _PROP_MIN[0] = 300 if scene.get("_near") else MIN_PROP_PX
    extras.CLOCK_AT[0] = clock_time(scene.get("text"))
    extras.DOOR_OPEN[0] = bool(scene.get("_door_open"))
    MOURN[0] = bool(scene.get("_mourn"))                  # Beerdigung: Trauergäste und Verwandte tragen Schwarz (stage._funeral_story)
    ERA[0] = bool(scene.get("_era"))                      # Geschichte spielt um 1800 oder früher: Passanten tragen die Kleidung der Zeit (stage._past_story)
    places.XMAS[0] = bool(scene.get("_xmas"))             # Weihnachts-Video: Wohn- und Esszimmer sind geschmückt (stage._feast_story)
    places.ICE[0] = bool(scene.get("_ice"))               # zugefrorenes Meer: „unter Wasser“ liegt unter der Eisdecke
    places.LAKE[0] = bool(scene.get("_lake"))             # Schatzsuche im See: „unter Wasser“ ist der Seegrund, nicht das Meer
    night = str(scene.get("time") or "").lower() in ("night", "nacht", "abend", "evening")
    ov = scene.get("overlay") if isinstance(scene.get("overlay"), dict) else {}
    scale = 0.9 if str(ov.get("type")) in TALL_OV else SCALE
    event = str(scene.get("shot") or "").lower() == "event"
    raw = [a for a in (scene.get("actors") or []) if isinstance(a, dict)]
    if "actors" not in scene and not event:
        raw = [{"id": next(iter(cast), "held"), "action": "talk", "speaks": True}]
    if place in ("germany", "worldmap"):       # auf der Karte stehen keine Figuren
        raw = []
    if event:            # Ereignis-Einstellung: das Geschehen groß, höchstens eine kleine Figur am Rand als Zuschauer
        raw = raw[:1]
        for a in raw:
            a.setdefault("pos", "left")
            a["pos"] = "left" if a["pos"] in ("center", "mitte") else a["pos"]
        scale = 0.8
    actors = []
    default_x = {0: (540,), 1: (540,), 2: (330, 750), 3: (200, 540, 880)}[min(3, len(raw))]
    for i, a in enumerate(raw[:3]):
        aid = str(a.get("id") or f"a{i}")
        spec = cast.get(aid) if isinstance(cast.get(aid), dict) else {}
        if not spec and isinstance(a.get("look"), dict):
            spec = a["look"]
        elif not spec and not a.get("kind") and aid.lower() not in MAIN_IDS and i > 0:
            spec = GROUP_LOOKS[(i + len(aid)) % len(GROUP_LOOKS)]   # Nebenfigur ohne Besetzung: kein Zwilling der Hauptfigur
        elif not spec and not a.get("kind") and aid.lower() in MAIN_IDS:
            humans = [v for v in cast.values() if isinstance(v, dict) and not v.get("kind")]
            if len(humans) == 1:                          # Bildplan sagt „du“, Besetzung nennt die Hauptfigur beim Namen: dieselbe Figur
                spec = humans[0]
        kind = str(a.get("kind") or spec.get("kind") or "").lower()
        if MOURN[0] and not kind:                         # auf der Beerdigung: schwarz gekleidet, keine bunte Mütze (Plan 20.11.2026: Oma mit roter Mütze in der Kirche)
            spec = dict(spec, shirt="schwarz", hat="" if str(spec.get("hat") or "") in ("cap", "beanie", "party", "chef") else spec.get("hat") or "")
        fit_a = str(a.get("_outfit") or "")
        if fit_a in ("period", "king", "guard") and not kind:   # Kleidung der Zeit (stage._past_story): König mit Krone und Hermelin, Wache im Uniformrock mit Dreispitz, Bürger im Rock bzw. Kleid
            fem_a = str(spec.get("gender") or "").lower() in ("w", "f", "female", "frau", "weiblich") or (str(spec.get("hair") or "").lower() in rig.FEM_HAIR and fit_a != "king")
            if fit_a == "king":
                spec = dict(spec, outfit="king", hat="crown", shirt=spec.get("shirt") or "rot", hair=spec.get("hair") if fem_a else "", hair_color=spec.get("hair_color") or "grau")
            elif fit_a == "guard":
                spec = dict(spec, outfit="guard", hat="tricorn", shirt="blau", hair="", gender="m")
            else:
                hat_a = str(spec.get("hat") or "").lower()
                spec = dict(spec, outfit="period", hat=("bonnet" if fem_a else "tricorn") if hat_a in ("cap", "beanie", "helmet", "headphones", "army", "chef") else hat_a)
        if fit_a in ("exo", "exo_off") and not kind:         # Exoskelett über der Alltagskleidung (stage._exo_story)
            spec = dict(spec, outfit=fit_a)
        if not kind and not spec and aid.lower() not in MAIN_IDS:   # „vogel“ im Bildplan, in der Besetzung heißt er „truthahn“ (kind bird): das Tier, kein Mensch im Pulli (Video 148)
            kind = next((k for pat, k in TOPIC_CREATURES if k not in ("agent", "virus", "cell") and re.search(pat, aid.lower())), "")
            if not kind:
                near = [v for k_, v in cast.items() if isinstance(v, dict) and v.get("kind") and (k_.lower()[:5] == aid.lower()[:5])]
                kind = str(near[0].get("kind")).lower() if near else ""
        if re.search(r"gehirn|hirn|brain", aid.lower()) and kind in ("", "agent", "robot", "cell"):
            kind = "brain"                                # „gehirn_bot“, „dein_gehirn“: das Gehirn selbst als Figur, kein oranges KI-Kästchen
        if re.search(r"wecker", aid.lower()) and kind in ("", "agent", "robot"):
            kind = "wecker"                               # „wecker“ als Figur: der Wecker selbst mit Gesicht, kein Roboter (Video 225)
        if re.search(FRIDGE_ID_RE, aid.lower()) and kind in ("", "agent", "robot"):
            kind = "fridge"                               # „kuehlschrank“ als Figur: der Kühlschrank selbst mit Gesicht – kein Roboter neben einem Kühlschrank
        x0 = _x(a.get("pos"), default_x[i])
        x1 = _x(a.get("to"), x0) if a.get("to") else x0
        action = str(a.get("action") or "idle").lower()
        if x1 != x0 and action not in ("walk", "run"):
            action = "walk"
        if action in ("walk", "run") and x1 == x0:       # ohne Ziel: von außen hereinkommen
            x0 = -260 if x0 <= 540 else 1340
        look_a = rig.Look.from_spec(spec, aid, list(cast).index(aid) if aid in cast else None)
        if (scene.get("_no_headphones") or action in ("sleep", "schlafen")) and look_a.hat == "headphones":   # im Bett liegt niemand mit Kopfhörern auf den Ohren (Prüfung 27.11.2026, Video 231)
            import dataclasses
            look_a = dataclasses.replace(look_a, hat="")   # Telefonat: der Freund hat das Handy auf laut – trüge er laut Besetzung schon Kopfhörer, widerspräche das Bild dem Satz (Video 184)
        if a.get("wear") == "headphones" and not look_a.hat and kind not in extras.CREATURES:
            import dataclasses
            look_a = dataclasses.replace(look_a, hat="headphones")
        actors.append({"look": look_a, "kind": kind if kind in extras.CREATURES else "",
                       "hold": extras.held_key(a.get("hold")),
                       "action": action, "emotion": str(a.get("emotion") or "").lower(), "emote": a.get("emote") or "", "giant": bool(scene.get("giant")), "small": bool(scene.get("_beside_bed") or a.get("small")), "hero": bool(a.get("hero")), "ksz": float(a["_ksz"]) if isinstance(a.get("_ksz"), (int, float)) and not isinstance(a.get("_ksz"), bool) and 0.2 <= a["_ksz"] <= 2.0 else 0.0, "say": str(a.get("say") or "") if isinstance(a.get("say"), str) else "",
                       "x0": x0, "x1": x1, "speaks": bool(a.get("speaks")), "awake": bool(a.get("_awake")), "seed": i * 5 + len(aid), "face": a.get("facing"), "jog": bool(a.get("_jog")) and action == "run", "lift": a.get("_lift") == "barbell" and not kind,
                       "teeth": TEETH_COLORS.get(str(a.get("teeth") or "").lower())})
    for i, a in enumerate(actors):     # zwei Figuren nie auf derselben Stelle
        for b in actors[:i]:
            if abs(a["x1"] - b["x1"]) < 200:
                a["x1"] = b["x1"] + (300 if b["x1"] < 600 else -300)
                if a["x0"] == b["x0"] or abs(a["x0"] - b["x1"]) < 200:
                    a["x0"] = a["x1"]
    if actors and not any(a["speaks"] for a in actors):
        actors[0]["speaks"] = len(actors) == 1
    talk = lips(scene.get("text"))
    for a in actors:                  # Lippen nur, wenn die Figur selbst spricht – sonst hört sie zu und reagiert
        a["lips"] = a["speaks"] and talk
    for a in actors:   # passende Symbole automatisch, wenn das Drehbuch keine nennt
        if not a["emote"] and a["kind"] not in SEA_KINDS + ("wecker",):
            a["emote"] = {"shocked": "!", "scared": "!", "think": "" if a["emotion"] == "happy" else "?", "angry": "anger"}.get(a["action"]) or \
                         {"angry": "anger", "scared": "sweat", "worried": "sweat"}.get(a["emotion"], "")
    props, p_given = [], []
    win, counts = [], {}
    scene["_win"], scene["_count"] = win, counts
    for i, p in enumerate((scene.get("props") or [])[:3]):
        if isinstance(p, dict) and isinstance(p.get("count"), int) and p["count"] > 1:
            counts[extras.PROP_ALIASES.get(str(p.get("type")).lower(), str(p.get("type")).lower())] = p["count"]
        if isinstance(p, str):
            p = {"type": p}
        if isinstance(p, dict) and str(p.get("type")).lower().strip() in extras.HELD:      # Handy, Taschenlampe …: gehört in die Hand
            for a in actors:
                if not a["kind"] and not a["hold"]:
                    a["hold"] = extras.HELD[str(p["type"]).lower().strip()]
                    break
            continue
        if isinstance(p, dict) and any(a["hold"] == "prop:" + extras.PROP_ALIASES.get(str(p.get("type")).lower(), str(p.get("type")).lower()) for a in actors):
            continue                                              # hält die Figur schon in der Hand: nicht noch einmal auf den Boden stellen
        if isinstance(p, dict) and str(scene.get("shot") or "") != "insert" and \
                extras.PROP_ALIASES.get(str(p.get("type")).lower(), str(p.get("type")).lower()) in PLACE_HAS.get(place, ()):
            continue                                              # steht an diesem Ort schon
        if isinstance(p, dict) and extras.PROP_ALIASES.get(str(p.get("type")).lower(), str(p.get("type")).lower()) == "fridge" and any(q["kind"] == "fridge" for q in actors):
            continue                                              # der Kühlschrank ist selbst die Figur: kein zweiter daneben
        if isinstance(p, dict) and place != "underwater" and str(scene.get("shot") or "") != "insert" and \
                extras.PROP_ALIASES.get(str(p.get("type")).lower(), str(p.get("type")).lower()) == "submersible":
            continue                                              # ein Tauchboot schwebt nur unter Wasser frei im Bild – nicht am Himmel, nicht im Zimmer
        if isinstance(p, dict) and place not in places.OUTDOOR and place not in ("space", "plain", "highsky") and not (place == "underwater" and
                extras.PROP_ALIASES.get(str(p.get("type")).lower(), str(p.get("type")).lower()) in extras.WATER_KINDS) and \
                extras.PROP_ALIASES.get(str(p.get("type")).lower(), str(p.get("type")).lower()) in extras.SKY and str(scene.get("shot") or "") != "insert":
            if place in places.WINDOWS and len(win) < 2:          # was am Himmel passiert, sieht man drinnen durchs Fenster
                win.append(extras.PROP_ALIASES.get(str(p["type"]).lower(), str(p["type"]).lower()))
            continue                                              # Sonne, Mond, Wolken stehen nicht im Zimmer
        if isinstance(p, dict) and place not in places.OUTDOOR and place not in ("space", "plain", "cave", "underwater", "highsky") and not (
                place in GARAGES and extras.PROP_ALIASES.get(str(p.get("type")).lower(), str(p.get("type")).lower()) in GARAGE_VEHICLES) and \
                extras.PROP_ALIASES.get(str(p.get("type")).lower(), str(p.get("type")).lower()) in ("fire", "volcano", "tornado", "car", "police", "ambulance", "bus", "truck", "house", "tree", "meteor", "wave") \
                and str(scene.get("shot") or "") != "insert":
            continue                                              # gehört nach draußen, nicht ins Zimmer
        if isinstance(p, dict) and place not in places.OUTDOOR and place != "underwater" and str(p.get("type")).lower().startswith("lib_") \
                and extras.REAL_M.get(str(p.get("type")).lower(), extras.SIZES.get(str(p.get("type")).lower(), (0,))[0]) > 2.6 and str(scene.get("shot") or "") != "insert":
            continue                                              # Gelerntes, das höher ist als ein Zimmer (Turm, Gebäude), steht nicht im Raum
        if isinstance(p, dict) and place not in places.OUTDOOR and place != "underwater" and str(scene.get("shot") or "") != "insert" \
                and extras.PROP_ALIASES.get(str(p.get("type")).lower(), str(p.get("type")).lower()) == "lib_wrack":
            continue                                              # ein Flugzeugwrack passt in kein Labor (das „Wrackteil“ im Satz ist das Treibgut unterm Mikroskop)
        if isinstance(p, dict) and p.get("type"):
            taken = [q["x1"] for q in actors] + [q[1] for q in props]
            free = [c for c in (830, 250, 540, 930, 150) if all(abs(c - tx) > 200 for tx in taken)] or [830]   # nie am Rand: Dinge haben eine Mindestgröße
            kind = str(p["type"]).lower().strip()
            fit = extras.prop_fit(kind)
            if fit and fit[1] < 1200 and not p.get("pos"):      # Großes (Auto, Haus, Baum) steht weiter hinten und darf mittig stehen
                free = [c for c in (760, 320, 540) if all(abs(c - q[1]) > 300 for q in props)] or [760]
            props.append((kind, _x(p.get("pos"), free[0]) if p.get("pos") else free[0]))
            p_given.append(bool(p.get("pos")))
    if len(props) == 1 and not actors and not p_given[0] and extras.PROP_ALIASES.get(props[0][0], props[0][0]) in ("plane", "ufo", "satellite", "rocket"):
        props = [(props[0][0], 540)]                          # allein im Bild: mittig, nicht am rechten Rand vor einem Deko-Planeten
    if event:
        props = [(k, 600 if (i == 0 and not p_given[i]) else 540 if (not p_given[i] and extras.PROP_ALIASES.get(k, k) in ("plane", "ufo", "satellite", "drone")) else x)
                 for i, (k, x) in enumerate(props)]           # das Flugzeug über dem Schiff fliegt mittig – am Rand wäre es vergrößert angeschnitten
    for a in actors:                  # wer schläft, hält nichts in der ausgestreckten Hand
        if a["action"] == "sleep":
            a["hold"] = ""
        elif a["action"] in ("shake", "schütteln") and not a["hold"] and not a["kind"]:
            a["action"] = "idle"      # „shake“ heißt ausschütteln, was man hält – mit leerer Hand (gemeint war Kopfschütteln) bliebe nur ein ausgestreckter Arm
    return place, night, scale, actors, props, str(scene.get("weather") or "").lower()


ERA = [False]          # Geschichte um 1800 (setzt _prepare je Szene): Passanten tragen Rock, Kleid, Dreispitz und Haube statt Kapuzenpulli und Mütze
ERA_SHIRTS = ("braun", "grün", "grau", "blau", "beige", "oliv", "türkis", "rot")
MOURN = [False]        # Trauerfeier (setzt _prepare je Szene): alle im Bild tragen Schwarz
MOURN_SHIRTS = ("schwarz", "grau", "schwarz", "schwarz", "grau")
CROWD_SHIRTS = ("blau", "rot", "grün", "gelb", "orange", "lila", "türkis", "grau", "braun", "pink")
CROWD_KINDS = {"worried": "worried", "besorgt": "worried", "nervous": "worried", "tense": "worried", "unruhig": "worried",
               "wait": "worried", "queue": "worried", "panic": "panic", "panik": "panic", "flee": "panic", "flucht": "panic", "run": "panic",
               "walk": "walk", "gehen": "walk", "busy": "walk", "cheer": "cheer", "jubel": "cheer", "party": "cheer",
               "sad": "sad", "traurig": "sad", "watch": "watch", "staunen": "watch", "gather": "watch"}


def _crowd(frame, kind, t, night, lo=0, hi=9999, road=False, traffic=True, indoor=False, avoid=()):
    """Menschen im Bild, die die Stimmung zeigen: Panik (rennen kreuz und quer), Alltag (gehen), Sorge (stehen unruhig,
    sehen sich um), Jubel (springen), Trauer (stehen gebeugt), Staunen (stehen und zeigen). Jeder Mensch ist so groß,
    wie es zu seiner Tiefe im Bild passt; gezeichnet werden nur die mit Fußlinie zwischen lo und hi."""
    kind = CROWD_KINDS.get(str(kind or "").lower())
    if not kind:
        return
    import random
    rnd = random.Random(11)
    n = {"panic": 8, "walk": 5, "cheer": 6, "sad": 5, "watch": 5, "worried": 5}[kind]
    if indoor:
        n = min(n, 3 if kind != "panic" else 5)
    people = []
    for i in range(n):
        if indoor:
            gy = 1240 + rnd.random() * 36
        elif road and traffic:                                   # Gehwege: hinten oder vorn, nie auf der Fahrbahn
            gy = (1004 + rnd.random() * 30) if i % 2 else (1236 + rnd.random() * 40)
        elif road:
            gy = (1004 + rnd.random() * 30) if i % 3 == 0 else (1110 + rnd.random() * 160)
        else:
            gy = 1000 + (rnd.random() ** 0.8) * 270
        look = rig.Look.from_spec({"shirt": MOURN_SHIRTS[i % len(MOURN_SHIRTS)] if MOURN[0] else CROWD_SHIRTS[(i * 3 + 1) % len(CROWD_SHIRTS)], "hat": "" if MOURN[0] else ("", "", "cap", "beanie", "")[i % 5],
                                   "hat_color": CROWD_SHIRTS[(i * 7) % len(CROWD_SHIRTS)], "hair": ("", "long", "", "bun")[i % 4],
                                   "skin": ("weiß", "hell", "mittel", "dunkel")[i % 4]})
        if ERA[0] and not MOURN[0]:
            hair_e = ("", "long", "", "bun")[i % 4]
            look = rig.Look.from_spec({"shirt": ERA_SHIRTS[(i * 3 + 1) % len(ERA_SHIRTS)], "outfit": "period", "hair": hair_e, "hat_color": ERA_SHIRTS[(i * 5) % len(ERA_SHIRTS)],
                                       "hat": ("bonnet" if i % 4 == 3 else "") if hair_e else ("tricorn" if i % 4 == 0 else ""), "skin": ("weiß", "hell", "weiß", "hell")[i % 4]})
        people.append((gy, look, rnd.random(), rnd.choice((-1, 1)), i))
    stood = []
    for gy, look, ph, direction, i in sorted(people, key=lambda q: q[0]):
        if not (lo <= gy < hi):
            continue
        sc = places.depth(gy) * (0.97 + 0.06 * ((i * 7) % 3) / 2)
        emote = ""
        if kind == "panic":
            speed = (420 + ph * 380) * sc
            span = W + 500
            x = ((t * speed + ph * span) % span) - 250
            x = x if direction > 0 else W - x
            pose, _ = rig.pose_at("run", t + ph * 3, 9, "scared", 0.8, i)
            pose.arm_l, pose.arm_r, pose.fore_l, pose.fore_r = -150 + 20 * math.sin(t * 14 + i), 150 + 20 * math.sin(t * 14 + i + 1), 20, -20
            facing = direction
            emote = "!" if i % 3 == 0 else ("sweat" if i % 3 == 1 else "")
        elif kind == "walk":
            speed = (150 + ph * 110) * sc
            span = W + 400
            x = ((t * speed + ph * span) % span) - 200
            x = x if direction > 0 else W - x
            pose, _ = rig.pose_at("walk", t + ph * 3, 9, "", 0.0, i)
            facing = direction
        else:
            x = 110 + (i + 0.5) * (W - 220) / n + math.sin(i * 2.3) * 30
            for ax in avoid:                                   # nicht hinter einer Hauptfigur verstecken
                if abs(x - ax) < 150:
                    x = ax + (170 if x >= ax else -170)
            if any(abs(x - ax) < 150 for ax in avoid) or any(abs(x - px_) < 150 for px_ in stood) or (indoor and len(avoid) >= 2 and min(avoid) < x < max(avoid)):
                continue                                       # zwischen zwei Hauptfiguren ist kein Platz: lieber einer weniger als ein Knäuel aus fünf Leuten (Video 214)
            stood.append(x)
            facing = 1 if x < W / 2 else -1
            if kind == "cheer":
                pose, _ = rig.pose_at("jump", t + ph, 9, "happy", 0.6, i)
            elif kind == "sad":
                pose, _ = rig.pose_at("sad", t + ph, 9, "sad", 0.0, i)
            elif kind == "worried":
                pose, _ = rig.pose_at("look_around" if i % 2 else "think", t + ph * 2, 9, "worried", 0.0, i)
                x += math.sin(t * 0.8 + i * 1.9) * 26                      # unruhig von einem Fuß auf den anderen
                emote = "?" if i % 3 == 0 else ("sweat" if i % 3 == 1 else "")
            else:
                pose, _ = rig.pose_at("point" if i % 2 else "shocked", t + ph + 1.0, 9, "shocked", 0.5, i)
                emote = "!" if i % 2 == 0 else ""
        im, fx, fy = rig.draw(look, pose, facing, sc, ss=1 if sc < 0.7 else 2)
        _shadow(frame, int(x), int(gy), int(60 * sc))
        frame.paste(im, (int(x - fx), int(gy - fy)), im)
        if emote and sc > 0.3:
            extras.draw_emote(frame, emote, x, gy - (505 + max(0, pose.lift)) * sc, t + ph, sc)


ON_TABLE = ("cans", "candle", "money", "canister", "glass")           # Kleines steht drinnen auf einem Tisch, damit man es sieht


def _on_table(key):
    """Auch kleine gelernte Gegenstände (Tasse, Router, Mikroskop …) stehen drinnen auf dem Tisch statt auf dem Boden."""
    return key in ON_TABLE or (key.startswith("lib_") and extras.SIZES.get(key, (9,))[0] <= 0.5)
PLACE_HAS = {"kitchen": ("fridge", "table"), "office": ("computer", "table"), "supermarket": ("shelf",), "supermarket_empty": ("shelf",),
             "livingroom": ("lib_sofa", "sofa", "couch"), "forest": ("tree",), "park": ("tree",), "camp": ("tent", "fire"), "street": ("streetlamp", "house"),
             "village": ("house",), "restaurant": ("table",), "diningroom": ("table", "chair", "candle", "lib_stuhl"), "hallway": (), "serverroom": ("computer", "shelf"), "controlroom": ("computer", "table", "tv"),
             "headquarters": ("house", "streetlamp"), "cinema": ("tv",)}


def _float_lift(mode, t, seed=0.0, top=300.0, aloft=False):
    """Höhe über dem Boden (px) für alles, was schwerelos ist: hebt sanft ab und treibt wippend in der Luft. Bei "drop"
    hängt es noch kurz oben und kracht dann ungebremst herunter. Gibt (Höhe, Sekunden seit dem Aufschlag oder None) zurück."""
    bob = math.sin(t * 1.7 + seed * 1.3) * 20
    if mode == "drop":
        hold = 0.5 + (seed % 3) * 0.07
        if t < hold:
            return top + bob, None
        h = top + bob - 2400 * (t - hold) ** 2
        if h > 0:
            return h, None
        return 0.0, t - hold - math.sqrt(max(0.0, top) / 2400)
    k = 1.0 if aloft else _ease(t / 1.8)
    return (top + bob) * k, None


MIN_PROP_PX = 120      # Mindesthöhe (Bildpunkte) eines Gegenstands am Boden; ein Mensch ist etwa 590 hoch
MIN_TABLE_PX = 95      # … und auf dem Tisch


_PROP_MIN = [MIN_PROP_PX]                                 # je Szene: neben einem groß gezeichneten Tier (Krebs mit Sprungfeder, Muschel) ist auch das Ding groß


def _prop(frame, kind, x, t, big, table=False, lift=0.0, rot=0.0, grow=1.0):
    """Requisite zeichnen. Dinge mit echter Größe (Auto, Regal, Haus …) stehen in ihrer Tiefe im richtigen Verhältnis
    zu den Menschen; Naturereignisse und Himmelskörper sind Schaubilder und dürfen groß sein (big).
    lift/rot: das Ding schwebt so viele Pixel über dem Boden und ist dabei gekippt (Schwerelosigkeit)."""
    key = extras.PROP_ALIASES.get(kind, kind)
    fit = extras.prop_fit(key)
    if fit and (lift or rot):
        f, gy = fit
        if key.startswith("lib_") or extras.SIZES.get(key, (9,))[0] <= 0.6:      # Kleines leicht überzeichnen, sonst erkennt man es in der Luft nicht
            f *= max(1.0, 0.5 / max(0.05, extras.SIZES[key][0]))
        elif key in FLOAT_SHRINK:                         # als Standbild groß gezeichnete Kleinigkeiten (Glas, Kerze) neben einem schwebenden Menschen nicht riesig
            f *= FLOAT_SHRINK[key] / extras.SIZES[key][0]
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        extras.draw_prop(layer, kind, 540, t)
        box = layer.getbbox()
        if not box:
            return
        cut = layer.crop(box)
        cut = cut.resize((max(1, int(cut.width * f)), max(1, int(cut.height * f))), Image.BILINEAR)
        if rot:
            cut = cut.rotate(rot, expand=True, resample=Image.BICUBIC)
        _shadow(frame, int(x), int(gy), int(cut.width * 0.42 * max(0.35, 1 - lift / 900)))
        frame.paste(cut, (int(x - cut.width / 2), int(gy - lift - cut.height)), cut)
        return
    if fit:
        f, gy = fit
        nat = extras._nat.get(key)
        if nat and not (table and _on_table(key)) and nat * f < _PROP_MIN[0]:
            f = _PROP_MIN[0] / nat                         # Kleines (Spinne, Chip, Schuh) erkennbar groß – sonst ist das Thema nur ein Punkt
        f *= grow                                         # Auftritt: das Ding springt mit kleinem Überschwingen ins Bild
        if table and _on_table(key):
            _prop(frame, "table", x, t, big)
            tf, ty = extras.prop_fit("table")
            gy = ty - int(places.px(0.78, ty)) + 6
            if key.startswith("lib_"):                    # sehr Kleines (Tasse, Router) leicht überzeichnen, sonst erkennt man es nicht
                f *= max(1.0, 0.32 / max(0.05, extras.SIZES[key][0]))
            if nat and nat * f < MIN_TABLE_PX:            # auch auf dem Tisch nie nur ein Punkt
                f = MIN_TABLE_PX / nat
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        nx = max(260, min(W - 260, x))                    # in der Mitte zeichnen, damit beim Vergrößern nichts abgeschnitten wird
        extras.draw_prop(layer, kind, nx, t)
        box = layer.getbbox()
        if not box:
            return
        cut = layer.crop(box)
        cut = cut.resize((max(1, int(cut.width * f)), max(1, int(cut.height * f))), Image.BILINEAR)
        px0 = x + (box[0] - nx) * f
        py0 = gy + (box[1] - places.GROUND) * f
        if not (table and _on_table(key)):
            _shadow(frame, int(x), int(gy), int(cut.width * 0.42))
        frame.paste(cut, (int(px0), int(py0)), cut)
        return
    if big <= 1.01 or key in ("aurora", "lightning", "crack", "flood", "wave", "eclipse", "ship", "debris", "logs", "crates_sink", "ship_ice", "icehole"):
        extras.draw_prop(frame, kind, x, t)
        return
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    extras.draw_prop(layer, kind, x, t)
    ay = 520 if key in extras.SKY else places.GROUND
    big_l = layer.resize((int(W * big), int(H * big)), Image.BILINEAR)
    frame.paste(big_l, (int(x - x * big), int(ay - ay * big)), big_l)


INK = (22, 22, 26)
_lights = {}


def _light_kind(place, night, mood, xs):
    """Lichtführung der Szene: "spot" (Dunkelheit, Lichtkegel auf den Figuren) bei unheimlicher, angespannter oder trauriger
    Stimmung und nachts in Innenräumen – sonst "floor" (der Boden unten läuft weich ins Dunkle, der Blick bleibt bei den Figuren)."""
    if xs and (str(mood or "") in ("scary", "tense", "sad") or (night and place not in places.OUTDOOR)):
        return "spot"
    if night and place in places.OUTDOOR:
        return "night"
    return "floor"


GLOWS = {"markers": (0, 430, 430), "minimap": (0, 500, 330), "display": (0, places.GROUND - 150, 300), "cavitation": (0, 930, 330), "lib_glasscheibe": (0, places.GROUND - 280, 340), "lib_sprungfeder": (0, places.GROUND - 150, 260), "gondola_empty": (0, places.GROUND - 300, 460), "balloon": (0, 780, 400), "balloon_dark": (0, 780, 400), "balloon_out": (0, 800, 400), "balloon_fill": (-70, places.GROUND - 470, 430),
         "balloon_ground": (-80, places.GROUND - 130, 420), "balloon_down": (-60, places.GROUND - 150, 420)}   # leuchtet nachts selbst (Brenner) bzw. steht im Blick


def _light(frame, kind, xs, glows=()):
    """Legt Licht und Schatten über das fertige Bild (Maske in kleiner Auflösung, weich, zwischengespeichert)."""
    glows = tuple((int(gx) // 30 * 30, int(gy), int(gr)) for gx, gy, gr in glows) if kind in ("night", "spot") else ()
    key = (kind, tuple(sorted(int(x) // 30 for x in xs)) if kind in ("spot", "night") else (), glows)
    if key not in _lights:
        if len(_lights) > 60:
            _lights.clear()
        f = 6
        m = Image.new("L", (W // f, H // f), 255 if kind == "floor" else 104)
        d = ImageDraw.Draw(m)
        g = places.GROUND // f
        for y in range(g, H // f):                                   # Boden läuft zum unteren Rand ins Dunkle
            k = (y - g) / max(1, H // f - g)
            d.line((0, y, W // f, y), fill=int((255 if kind == "floor" else 104) * (1 - 0.34 * k ** 1.3)))
        if kind == "night":                                          # Nacht draußen: alles dunkelblau, die Figuren im warmen Lichtfleck
            m = Image.new("L", (W // f, H // f), 0)
            d = ImageDraw.Draw(m)
            for y in range(H // f):
                d.line((0, y, W // f, y), fill=int(150 - 40 * min(1.0, max(0.0, (y - 100) / (H // f - 100)))))
            for x in xs:
                xx = x / f
                d.ellipse((xx - 52, g - 120, xx + 52, g + 10), fill=255)
                d.ellipse((xx - 70, g - 8, xx + 70, g + 18), fill=225)
            for gx, gy, gr in glows:                                 # der Ballon im Schein seines Brenners: nachts nicht nur ein dunkler Fleck
                d.ellipse(((gx - gr) / f, (gy - gr) / f, (gx + gr) / f, (gy + gr) / f), fill=240)
            m = m.filter(ImageFilter.GaussianBlur(10))
            tint = Image.new("RGB", m.size, (150, 165, 235))                                   # Mondlicht-Blau, im Lichtfleck warm
            warm = Image.new("RGB", m.size, (255, 236, 200))
            mm = Image.composite(warm, tint, m.point(lambda v: max(0, (v - 150) * 2.4)))
            lum = Image.merge("RGB", [m] * 3)
            _lights[key] = ImageChops.multiply(lum, mm).resize((W, H), Image.BILINEAR)
            return _night_windows(frame.convert("RGB"), _lights[key])
        if kind == "spot":
            for x in xs:
                xx = x / f
                d.polygon([(xx - 8, 0), (xx + 8, 0), (xx + 50, g + 6), (xx - 50, g + 6)], fill=170)     # Lichtkegel von oben
                d.ellipse((xx - 44, g - 105, xx + 44, g + 14), fill=255)                                 # die Figur steht im Licht
                d.ellipse((xx - 60, g - 4, xx + 60, g + 16), fill=215)                                   # Lichtfleck am Boden
            for gx, gy, gr in glows:                                 # was selbst leuchtet (Blitz der Dampfblase), steht nicht im Dunkeln
                d.ellipse(((gx - gr) / f, (gy - gr) / f, (gx + gr) / f, (gy + gr) / f), fill=250)
            m = m.filter(ImageFilter.GaussianBlur(9))
        else:
            m = m.filter(ImageFilter.GaussianBlur(3))
        _lights[key] = Image.merge("RGB", [m.resize((W, H), Image.BILINEAR)] * 3)
    if kind == "night":
        return _night_windows(frame.convert("RGB"), _lights[key])
    return ImageChops.multiply(frame.convert("RGB"), _lights[key])


def _night_windows(frame, light):
    """Nacht: Bild abdunkeln, aber erleuchtete Fenster (warmes Gelb) bleiben hell und strahlen weich in die Umgebung."""
    r, g, b = frame.split()
    win = ImageChops.multiply(ImageChops.multiply(r.point(lambda v: 255 if v > 205 else 0), g.point(lambda v: 255 if v > 165 else 0)),
                              b.point(lambda v: 255 if v < 150 else 0))
    out = Image.composite(frame, ImageChops.multiply(frame, light), win)
    small = win.resize((W // 6, H // 6), Image.BILINEAR).filter(ImageFilter.GaussianBlur(5)).resize((W, H), Image.BILINEAR)
    return Image.composite(Image.new("RGB", (W, H), (255, 206, 120)), out, small.point(lambda v: int(v * 0.55)))


FLOAT_TOPS = (300.0, 170.0, 390.0)                 # Schwebehöhen (px über der Fußlinie) für mehrere Dinge im Zimmer …
FLOAT_TOPS_OUT = (310.0, 250.0, 70.0)
FLOAT_SHRINK = {"candle": 0.5, "faucet": 0.6}
FLOAT_LOW = (110.0, 70.0, 90.0)                    # unter hohen Einblendungen und für Busse: nur knapp über dem Boden             # … und draußen (Autos): nebeneinander oben, eines tiefer in der Mitte
_wv = {}


def _window_view(frame, box, kind, t):
    """Zeichnet ein Himmels-Ding (Drohne, Mond, Flugzeug, Blitz …) hinter die Fensterscheibe – begrenzt auf das Fenster."""
    x0, y0, x1, y1 = box
    key = extras.PROP_ALIASES.get(kind, kind)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    extras.draw_prop(lay, key, 540, t)
    if key not in _wv:                                       # fester Ausschnitt (aus einer ruhigen Messung), damit nichts zittert
        m = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        extras.draw_prop(m, key, 540, 1.0)
        bb = m.getbbox() or (340, 400, 740, 800)
        side = max(bb[2] - bb[0], 200) + 120
        cx = (bb[0] + bb[2]) // 2
        _wv[key] = (cx - side // 2, bb[1] - 50, cx + side // 2, bb[1] - 50 + int(side * (y1 - y0) / (x1 - x0)))
    cut = lay.crop(_wv[key]).resize((x1 - x0 - 8, y1 - y0 - 8), Image.BILINEAR)
    frame.paste(cut, (x0 + 4, y0 + 4), cut)
    d = ImageDraw.Draw(frame)
    d.line(((x0 + x1) // 2, y0, (x0 + x1) // 2, y1), fill=INK, width=7)       # Fensterkreuz wieder darüber
    d.line((x0, (y0 + y1) // 2, x1, (y0 + y1) // 2), fill=INK, width=7)
    d.rectangle((x0, y0, x1, y1), outline=INK, width=7)


SWARM = ((0, 0, 1.0), (-330, -150, 0.6), (310, -200, 0.5), (-190, 150, 0.72), (250, 110, 0.8), (-420, 40, 0.45), (420, -40, 0.55))


def _prop_many(frame, kind, x, t, big, n, table=False, grow=1.0):
    """Mehrere gleiche Himmels-Dinge (Schwarm): versetzt, verschieden groß, leicht zeitversetzt."""
    if n <= 1 or extras.prop_fit(kind):
        return _prop(frame, kind, x, t, big, table, grow=grow)
    for i, (dx, dy, sc) in enumerate(SWARM[:n]):
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        extras.draw_prop(lay, kind, 540, t + i * 0.9)
        bb = lay.getbbox()
        if not bb:
            continue
        cut = lay.crop(bb)
        f = sc * min(big, 1.2)
        cut = cut.resize((max(1, int(cut.width * f)), max(1, int(cut.height * f))), Image.BILINEAR)
        frame.paste(cut, (int(x + dx + (bb[0] - 540) * f), int(bb[1] + dy + (1 - f) * 120)), cut)


_osx = {}


def _open_sky_x(sky, x, cy, max_up=0, half=170):
    """Lage für ein Himmels-Ding (Sonne, Mond, Wolke …), an der es auch zu sehen ist: bleibt, wo es ist, wenn dort genug Himmel
    frei ist – sonst rückt es zur nächsten offenen Stelle zwischen Bäumen und Häusern (Wolken auch bis max_up px höher).
    Gibt (x, Anhebung) zurück."""
    from PIL import ImageStat
    key = (id(sky), sky.size, int(x), cy, max_up)
    if key in _osx:
        return _osx[key]

    def free(cx, up=0):
        y = cy - up
        box = (int(max(0, cx - half)), max(0, y - half), int(min(W, cx + half)), min(H, y + half))
        return ImageStat.Stat(sky.crop(box)).mean[0] / 255.0 if box[2] > box[0] and box[3] > box[1] else 0.0
    best = (x, 0)
    if free(x) < 0.6:
        cands = [(cx, up) for cx in range(220, W - 219, 30) for up in range(0, max_up + 1, 50)]
        best = max(cands, key=lambda c: free(*c) - abs(c[0] - x) / 2400.0 - c[1] / 4000.0)
        if free(*best) <= free(x):
            best = (x, 0)
    if len(_osx) > 400:
        _osx.clear()
    _osx[key] = best
    return best


def _frame(bg, place, night, scale, actors, props, weather, t, dur, words, t0, in_bed, shot="", big=1.0, fx=None):
    if place == "space" and any(extras.PROP_ALIASES.get(k, k) in extras.PROBE_KINDS for k, _ in props):
        bg = places.space_deep(night)                 # Raumsonde: tiefer Weltraum ohne Mondboden – sie fliegt weit hinter den Planeten
    elif place == "space" and any(extras.PROP_ALIASES.get(k, k) in ("sun", "moon", "earth", "satellite", "rocket", "ufo") for k, _ in props):
        bg = places.space_bare(night)                 # großer Himmelskörper im Bild: die Deko-Planeten treten zurück, nichts steckt ineinander
    frame = bg.copy()
    if (fx or {}).get("neon"):                # Lichtpunkte liegen hinter den Figuren
        graphics.bokeh(frame, t, 0.4)
    if weather in ("quake", "erdbeben"):      # Erdbeben: das ganze Bild wackelt
        dx, dy = int(math.sin(t * 47) * 16), int(math.cos(t * 39) * 12)
        frame = frame.transform(frame.size, Image.AFFINE, (1, 0, dx, 0, 1, dy), resample=Image.NEAREST)
    opt = fx or {}
    if opt.get("mood") == "panic" and weather not in ("quake", "erdbeben"):      # Panik: die Kamera zittert leicht
        dx, dy = int(math.sin(t * 31) * 7), int(math.cos(t * 27) * 5)
        frame = frame.transform(frame.size, Image.AFFINE, (1, 0, dx, 0, 1, dy), resample=Image.NEAREST)
    for wi, box in enumerate(places.WINDOWS.get(place, []) if opt.get("win") else []):     # Blick aus dem Fenster
        _window_view(frame, box, opt["win"][wi % len(opt["win"])], t + wi * 0.7)
    sky = opt.get("sky")
    behind = [(k, x) for k, x in props if extras.PROP_ALIASES.get(k, k) in extras.BEHIND]
    if sky is not None:                                # Wolken, Vögel, Sterne, Sonne, Mond: nur dort, wo Himmel zu sehen ist
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        extras.draw_ambient(lay, place, night, t)
        for kind, x in behind:
            high = extras.PROP_ALIASES.get(kind, kind) in ("sun", "moon", "earth")
            x, up = _open_sky_x(sky, x, 290 if high else 430, 0 if high else 200)    # nicht hinter Baumkronen oder Fassaden verstecken
            if up:                                           # Wolke rückt höher in den freien Himmel
                tmp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                _prop(tmp, kind, x, t, min(big, 1.2))
                lay.alpha_composite(tmp, (0, 0), (0, up))
            elif high:                                       # hoch am Himmel, über den Dächern
                tmp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                _prop(tmp, kind, x, t, 1.0)
                lay.alpha_composite(tmp, (0, 0), (0, 230))
            else:
                _prop(lay, kind, x, t, min(big, 1.2))
        frame.paste(lay, (0, 0), ImageChops.multiply(lay.getchannel("A"), sky))
        props = [q for q in props if q not in behind]
    else:
        extras.draw_ambient(frame, place, night, t)
    spec = opt.get("spec")
    road, traffic = extras.has_road(spec), not opt.get("no_traffic")
    indoor = place not in places.OUTDOOR
    ckw = dict(road=road, traffic=traffic, indoor=indoor, avoid=[a["x1"] for a in actors])
    if opt.get("crowd"):
        _crowd(frame, opt["crowd"], t, night, 0, 1090, **ckw)           # Menschen hinter der Fahrbahn zuerst
    flo, aloft = str(opt.get("float") or ""), bool(opt.get("aloft"))
    landed = None
    extras.draw_landscape_motion(frame, spec, place, night, t, traffic, not flo)
    for pi, (kind, x) in enumerate(sorted(props, key=lambda q: (extras.prop_fit(q[0]) or (0, 0))[1])):
        if extras.PROP_ALIASES.get(kind, kind) not in extras.FRONT:
            if flo and extras.prop_fit(kind):                # schwerelos: Tasse, Stuhl, Auto treiben gekippt in der Luft
                top = (FLOAT_TOPS if indoor else (FLOAT_LOW if opt.get("low") else FLOAT_TOPS_OUT))[pi % 3]
                lift, hit = _float_lift(flo, t, pi * 2.1 + 1, top, aloft)
                landed = hit if hit is not None and (landed is None or hit > landed) else landed
                rot = (16 + 5 * pi) * math.sin(t * (0.9 + 0.2 * pi) + pi * 1.9) * (1 if pi % 2 else -1) * (0.35 if kind in ("bus", "truck") else 1)
                rot = rot * min(1.0, lift / 120) if hit is None else (9 if pi % 2 else -7) * (0 if kind in ("car", "bus", "truck") else 1)
                _prop(frame, kind, x, t, big, False, max(lift, 0.01), rot)
                continue
            _prop_many(frame, kind, x, t, big, (opt.get("count") or {}).get(extras.PROP_ALIASES.get(kind, kind), 1), indoor and place != "underwater",
                       grow=max(0.02, extras._pop(t, 0.06 + 0.12 * pi, 0.32)) if opt.get("pop_in", True) else 1.0)
    if opt.get("crowd"):
        _crowd(frame, opt["crowd"], t, night, 1090, 9999, **ckw)
    if opt.get("blocks"):                     # Tetris-Effekt: gedachte Bausteine fallen durchs Bild, hinter den Figuren (Video 231)
        extras.fallblocks(frame, t)
    close = shot == "close" and bool(actors)
    if close:              # Großaufnahme: Kulisse vergrößert und leicht unscharf (Tiefenschärfe), die Figur scharf und groß davor
        lead = next((a for a in actors if a["speaks"]), actors[0])
        hw = CLOSE_BG / 2
        c_off = ((110 if lead["x1"] < 600 else -110) if lead["kind"] and lead["kind"] != "brain" else 0)   # das Gehirn ist rund und steht mittig – verschoben war es links angeschnitten (Video 204)   # Tier: der Kopf (vorn) kommt in die Bildmitte, nicht der Bauch
        c_x = max(hw, min(W - hw, lead["x1"] + c_off))
        top = places.GROUND - 780
        frame = frame.crop((int(c_x - hw), top, int(c_x + hw), top + int(CLOSE_BG * H / W))).resize((W, H), Image.BILINEAR)
        frame = frame.filter(ImageFilter.GaussianBlur(3))
        frame = _light(frame, _light_kind(place, night, opt.get("mood"), [540]), [540])
        scale = scale * CLOSE_ZOOM
    over = frame
    od = ImageDraw.Draw(frame, "RGBA")
    focus = 540.0
    xs_now = []
    lures = []                                         # Anglerfisch: wo sein Köder leuchtet (x, y, Radius des Scheins, an/aus)
    for a in sorted(actors, key=lambda q: q["speaks"]):
        moving = a["x1"] != a["x0"]
        speed = 360 if a["action"] == "walk" else 680
        move_t = min(dur * 0.7, abs(a["x1"] - a["x0"]) / speed) if moving else 0
        if moving and a.get("jog"):                    # Dauerlauf: quer durchs Bild, die ganze Szene lang
            move_t = dur + 0.8
        arrived = moving and t >= move_t
        x = a["x1"] if arrived else (a["x0"] + (a["x1"] - a["x0"]) * (t / move_t if a.get("jog") else _ease(t / move_t)) if moving else a["x0"])
        if close:                                      # die Hauptfigur steht mittig, andere im selben Abstand daneben
            x = 540 + (x - lead["x1"] - c_off) * W / CLOSE_BG
        xs_now.append(x)
        mouth, shape = _mouth(t0 + t, words) if a["speaks"] and a.get("lips", True) else (0.0, "a")
        if moving and not arrived:
            facing = 1 if a["x1"] > a["x0"] else -1
        elif a["face"] in ("left", "links"):
            facing = -1
        elif a["face"] in ("right", "rechts"):
            facing = 1
        else:
            facing = 1 if (x < 600 or len(actors) == 1) else -1
        if flo and not (moving and not arrived):          # wer schwebt oder abstürzt, kippt zur Bildmitte – der Kopf landet nie außerhalb des Bildes
            facing = 1 if x < 600 else -1
        gy = ((H - 70 if a["kind"] else CLOSE_FOOT) if close else places.GROUND) + (18 if a["speaks"] and not close else 0)   # Tiere sind niedrig: ganz im Bild
        a_lift, a_hit = _float_lift(flo, t, a["seed"], 190.0, aloft) if flo else (0.0, None)
        if a["kind"] in SEA_KINDS + ("angler",) and a.get("hero") and not close and not props:
            a_lift += (70 if a["kind"] == "jelly" else 150) * scale                          # Schwimmer treiben über dem Grund – frei von der Untertitel-Zeile
        if a["kind"] == "diver" and not close:
            a_lift += 150 * scale                                                             # der Taucher schwebt über Kisten und Stämmen, nicht darin
        landed = a_hit if a_hit is not None and (landed is None or a_hit > landed) else landed
        head_y = gy - 505 * scale
        if a["kind"] and not (moving and not arrived) and not close:   # Wesen steht nie ganz still: treibt/tappt sanft hin und her
            x += 34 * math.sin(t * 0.9 + a["seed"])
        if a["kind"]:
            hop = abs(math.sin(t * 9)) * 16 if (moving and not arrived) else 0
            ksz = a["ksz"] if a.get("ksz") else 1.0 if a.get("giant") else HERO_SIZE.get(a["kind"], 0.8) if a.get("hero") else CREATURE_SIZE.get(a["kind"], 1.0)   # Tiere in echter Größe – als Hauptfigur des Videos groß
            if a.get("small") and a["kind"] == "brain":
                ksz *= 0.72                                # neben dem Bett: kleiner, damit die Schlafende sichtbar bleibt
            if close and a["kind"] == "brain":
                ksz = 1.15                                 # Großaufnahme: das Gehirn füllt das Bild, wird aber nicht angeschnitten
            res = extras.creature(a["kind"], t + a["seed"], facing, mouth, a["emotion"] or
                                  ("shocked" if a["action"] in ("shocked", "scared") else ""), scale * 0.9 * ksz, a["action"])
            if res:
                im, fx, fy, fly = res
                if not (moving and not arrived) and not close:   # nie über den Bildrand hinaus (große Tiere als Hauptfigur sind breit)
                    lo, hi = 30 + fx, W - 30 - (im.width - fx)
                    if a["kind"] == "brain" and im.getbbox():           # das Gehirn nach seinem sichtbaren Umriss begrenzen (die Zeichenfläche ist viel breiter): so kann es rechts neben dem Bett stehen
                        bb_ = im.getbbox()
                        lo, hi = 30 + fx - bb_[0], W - 30 - (bb_[2] - fx)
                    x = (lo + hi) / 2 if lo > hi else min(max(x, lo), hi)
                if not fly:
                    _shadow(frame, int(x), gy, int(120 * scale * ksz))
                frame.paste(im, (int(x - fx), int(gy - fy - hop * ksz - a_lift)), im)
                head_y = gy - 430 * scale * ksz - a_lift
                if a["kind"] == "angler":                  # der Köder ist die einzige Lichtquelle: Er beleuchtet das Maul; in der Finsternis bleibt nur der Lichtpunkt
                    sc_a = scale * 0.9 * ksz
                    far_a = a["action"] in ("far", "dark")
                    lures.append((x + facing * 172 * sc_a, gy - hop * ksz - a_lift - 347 * sc_a, (150 if far_a else 330) * sc_a, a["action"] != "dark"))
                    if x in xs_now:
                        xs_now.remove(x)
        else:
            action = a["action"]
            tt = t
            if arrived:
                action, tt = ("talk" if a["speaks"] else "idle"), t - move_t
            elif action == "idle" and a["speaks"]:
                action = "talk"
            if flo:                                           # schwerelos treiben – nach dem Absturz liegt die Figur am Boden
                action, tt = ("fall", a_hit) if a_hit is not None else ("float", t)
            pose, _ = rig.pose_at(action, tt, dur, a["emotion"], mouth, a["seed"],
                                  _gest_at(a.get("gplan"), t) if action in ("talk", "idle") and not a.get("hold") else None, shape)
            if a.get("lift"):                                 # stemmt die Langhantel: beide Arme gestreckt nach oben, federt leicht in den Knien
                bob_l = math.sin(t * 2.4)
                pose.arm_l, pose.fore_l, pose.arm_r, pose.fore_r = -162, -6, 162, 6
                pose.lift, pose.lean, pose.head, pose.squash = 0, 0, 0, 1.0 - 0.02 * (bob_l + 1)
                pose.leg_l, pose.leg_r, pose.knee_l, pose.knee_r = -14, 14, 0, 0
                pose.extra["reach"] = 1.7
                pose.extra.pop("dots", None)
            bed_phone = bool(a.get("awake")) and action == "sleep" and in_bed and not close
            if a.get("awake") and action == "sleep":          # liegt wach im Bett am Handy (Prüfung 26.11.2026, Video 216): Augen offen, kein „zzz“
                pose.eyes, pose.squash = "normal", 1.0
                pose.extra.pop("zzz", None)
            if a.get("teeth"):                                # verfärbte Zähne zeigen: Mund bleibt offen
                pose.teeth = a["teeth"]
                pose.mouth = max(pose.mouth, 0.75)
                pose.shape = "e"
            if a.get("hold") and action not in ("run", "sleep", "fall", "jump", "dance", "wave", "shake") and not pose.lying:
                small_h = a["hold"].startswith("prop:") and (extras.REAL_M.get(a["hold"][5:]) or extras.SIZES.get(a["hold"][5:], (9,))[0]) <= 0.3
                pose.arm_r, pose.fore_r = (62, 50) if a["hold"] in ("phone", "map", "flashlight", "radio", "bottle", "letter", "phonelight", "phonedead", "phonemusic") or small_h else (104, 34) if a["hold"] == "phoneflash" else (8, 4)   # Kleines (Apfel, Kuchen) hält man vor sich, nicht an der Hüfte
                if a["hold"] in ("umbrella", "sign"):
                    pose.arm_r, pose.fore_r = 40, 100
                if a["hold"] == "call":                         # Telefonat: Hand mit dem Handy am Ohr
                    pose.arm_r, pose.fore_r = CALL_ARM
            if 0 <= t - move_t < 0.18 and arrived:           # kleines Abfedern beim Ankommen
                pose.squash *= 1 - 0.08 * math.sin((t - move_t) / 0.18 * math.pi)
            elif not moving and t < 0.3 and not pose.lying:  # Szenenbeginn: die Figur federt kurz – nichts steht steif da
                pose.squash *= 1 + 0.07 * math.sin(t / 0.3 * math.pi) * (1 - t / 0.3)
            if action in ("shocked", "scared") and t < 0.45:  # Schreck: Strahlen um den Kopf
                extras.draw_burst(frame, x, gy - 420 * scale, t / 0.45, scale)
            if action == "sit" and not pose.lying:               # niemand sitzt in der Luft: Hocker unter die Figur
                sw, sh = 62 * scale, 74 * scale
                d0 = ImageDraw.Draw(frame, "RGBA")
                sx = x - facing * 6 * scale
                d0.rounded_rectangle((sx - sw, gy - sh, sx + sw, gy + 4), 14 * scale, fill=(150, 104, 70) if not night else (86, 70, 80), outline=INK, width=6)
                d0.rounded_rectangle((sx - sw - 8, gy - sh - 16 * scale, sx + sw + 8, gy - sh + 8 * scale), 12 * scale,
                                     fill=(214, 90, 80) if not night else (120, 70, 86), outline=INK, width=6)
            im, fx, fy = rig.draw(a["look"], pose, facing, scale, ss=1 if close else None)
            if pose.lying and in_bed and not close and action == "sleep":    # im Schlafzimmer liegt die schlafende Figur im Bett – wer umfällt, liegt am Boden
                x, gy = 300, places.GROUND - 108             # Kopf auf dem Kissen, Körper auf der Matratze (nicht darüber)
            elif pose.lying:                                   # sonst liegt sie auf dem Boden auf, nicht darüber
                fy -= 62 * scale
            if not (pose.lying and in_bed and not close and action == "sleep"):   # im Bett kein Bodenschatten (er lag als Fleck auf der Decke)
                _shadow(frame, int(x), gy, int(72 * scale * (1 - min(0.5, max(0, pose.lift + a_lift) / 400))))
            gy0, gy = gy, gy - int(a_lift)
            frame.paste(im, (int(x - fx), int(gy - fy)), im)
            if pose.lying and in_bed and not close and action == "sleep":    # zugedeckt: die Decke liegt über Bauch und Beinen – niemand liegt steif obenauf, keine Füße ragen übers Bettende
                d_b = ImageDraw.Draw(frame)
                col_b = places.BLANKET if not night else places._mix(places.BLANKET, 0.5, (22, 26, 66))
                lit_b = (120, 156, 236) if not night else places._mix((120, 156, 236), 0.5, (22, 26, 66))
                fold_b = (236, 240, 250) if not night else places._mix((236, 240, 250), 0.5, (22, 26, 66))
                br_b = 6 * math.sin(t * 1.6)                             # die Decke hebt und senkt sich mit dem Atem
                d_b.rounded_rectangle((360, 968 - br_b, places.BED_END, 1190), 34, fill=col_b, outline=INK, width=6)
                d_b.rounded_rectangle((420, 982 - br_b, places.BED_END - 14, 1026 - br_b), 20, fill=lit_b)
                d_b.rounded_rectangle((340, 964 - br_b, 400, 1190), 12, fill=fold_b, outline=INK, width=5)
            if bed_phone:                                     # das Handy steht auf der Decke vor dem Gesicht, die Hand hält es, das Display leuchtet ins Gesicht
                d_p = ImageDraw.Draw(frame, "RGBA")
                px, py = 412, 962 + 3 * math.sin(t * 5.0)     # der Daumen wischt: das Handy wippt leicht
                if night:
                    d_p.ellipse((px - 250, py - 190, px + 70, py + 90), fill=(150, 210, 255, 46))
                d_p.polygon([(px - 6, py + 8), (px + 26, py - 62), (px + 44, py - 54), (px + 14, py + 16)], fill=(30, 32, 40), outline=INK)
                d_p.line((px - 6, py + 8, px + 26, py - 62), fill=(150, 210, 255), width=7)     # Displaykante leuchtet zum Gesicht hin
                sk_p = rig._dark(a["look"].skin if a["look"].skin != rig.SKINS["schwarz"] else (250, 244, 232), 0.16)
                d_p.ellipse((px + 2, py - 22, px + 40, py + 14), fill=sk_p, outline=INK, width=5)
            if a.get("lift") and not pose.lying and "hand" in pose.extra:
                _barbell(frame, x, gy - fy + pose.extra["hand"][1] - 6 * scale, scale * a["look"].size)
            if a.get("hold") and not pose.lying and "hand" in pose.extra:
                hx, hy = pose.extra["hand"]
                if a["hold"].startswith("prop:"):
                    extras.draw_held_prop(frame, a["hold"][5:], x - fx + hx, gy - fy + hy, facing, t, scale, action == "shake")
                else:
                    extras.draw_held(frame, a["hold"], x - fx + hx, gy - fy + hy, facing, t, scale, night)
            head_y = gy - (505 + max(0, pose.lift)) * scale * a["look"].size
            gy = gy0
            if pose.lean > 60 or pose.lying:                 # liegt am Boden: Zeichen knapp über statt weit über der Figur
                head_y = gy - 300 * scale
            _zzz(od, pose, x, head_y + 75 * scale, t)
        if weather in extras.COLD and not close and not (not a["kind"] and (pose.lying or action in ("sleep", "fall"))):
            ksz_c = (a["ksz"] if a.get("ksz") else 1.0 if a.get("giant") else HERO_SIZE.get(a["kind"], 0.8) if a.get("hero") else CREATURE_SIZE.get(a["kind"], 1.0)) if a["kind"] else a["look"].size
            extras.draw_breath(over, x + facing * 86 * scale * ksz_c, head_y + 215 * scale * ksz_c, facing, t + a["seed"], scale * ksz_c)   # Kälte: Atemwolke vor dem Mund
        if a.get("say"):
            extras.draw_bubble(over, a["say"], x, head_y, t, min(scale, 1.4))
        elif a["emote"]:
            extras.draw_emote(over, a["emote"], x, head_y, t, min(scale, 1.6))
        if a["speaks"] or len(actors) == 1:
            focus = x
    for kind, x in props:
        if extras.PROP_ALIASES.get(kind, kind) in extras.FRONT:
            _prop(over, kind, x, t, 1.0)
    if weather and not (night and weather in ("dark", "dunkel", "blackout")):
        extras.draw_weather(over, weather, t)
    if opt.get("mood"):
        extras.draw_mood(over, opt["mood"], t, opt.get("confetti", False))
    if not close:
        glows = [(x + GLOWS[extras.PROP_ALIASES.get(k_, k_)][0],) + GLOWS[extras.PROP_ALIASES.get(k_, k_)][1:] for k_, x in props if extras.PROP_ALIASES.get(k_, k_) in GLOWS]
        glows += [(lx_, ly_, lr_ if on_ else lr_ * 0.5) for lx_, ly_, lr_, on_ in lures]
        frame = _light(frame, "spot" if lures else "night" if glows and night and place in places.OUTDOOR else
                       ("spot" if opt.get("noir") and xs_now else _light_kind(place, night, opt.get("mood"), xs_now)), xs_now, glows)
        if any(on_ for _, _, _, on_ in lures):                # der Schein des Köders liegt hell über dem dunklen Bild
            gl = Image.new("RGB", (W // 4, H // 4), (0, 0, 0))
            gd = ImageDraw.Draw(gl)
            pul_ = 1 + 0.07 * math.sin(t * 6)
            for lx_, ly_, lr_, on_ in lures:
                if on_:
                    for r_, c_ in ((lr_ * 0.5 * pul_, (40, 96, 84)), (lr_ * 0.24 * pul_, (96, 190, 160)), (lr_ * 0.1, (200, 255, 236))):
                        gd.ellipse(((lx_ - r_) / 4, (ly_ - r_) / 4, (lx_ + r_) / 4, (ly_ + r_) / 4), fill=c_)
            frame = ImageChops.screen(frame.convert("RGB"), gl.filter(ImageFilter.GaussianBlur(7)).resize((W, H), Image.BILINEAR))
    if landed is not None and landed < 0.5:      # Aufschlag: das Bild wackelt kurz
        k = 1 - landed / 0.5
        dx, dy = int(math.sin(t * 61) * 22 * k), int(math.cos(t * 53) * 26 * k)
        frame = frame.transform(frame.size, Image.AFFINE, (1, 0, dx, 0, 1, dy), resample=Image.NEAREST)
    return frame


CLOSE_BG = 660         # Großaufnahme: Breite des Kulissen-Ausschnitts (Zoom 1,6) …
CLOSE_ZOOM = 2.6       # … die Figur selbst wird 2,6-mal so groß gezeichnet (scharf, nicht hochgerechnet) …
CLOSE_FOOT = H + 110   # … und steht unterhalb des Bildrands: Kopf und Oberkörper füllen das Bild


_ONES = {"null": 0, "ein": 1, "eine": 1, "einen": 1, "einem": 1, "einer": 1, "eins": 1, "zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "sechs": 6,
         "sieben": 7, "acht": 8, "neun": 9, "zehn": 10, "elf": 11, "zwölf": 12, "dreizehn": 13, "vierzehn": 14, "fünfzehn": 15,
         "sechzehn": 16, "siebzehn": 17, "achtzehn": 18, "neunzehn": 19}
_TENS = {"zwanzig": 20, "dreißig": 30, "vierzig": 40, "fünfzig": 50, "sechzig": 60, "siebzig": 70, "achtzig": 80, "neunzig": 90}
_SCALE = {"tausend": "TSD.", "million": "MIO.", "millionen": "MIO.", "milliarde": "MRD.", "milliarden": "MRD.", "billion": "BIO.", "billionen": "BIO."}
_UNITS = {"prozent": "%", "grad": "GRAD", "liter": "LITER", "tonnen": "TONNEN", "kilo": "KILO", "kilogramm": "KILO", "jahre": "JAHRE", "jahren": "JAHRE",
          "tage": "TAGE", "tagen": "TAGE", "stunden": "STUNDEN", "minuten": "MINUTEN", "sekunden": "SEKUNDEN", "wochen": "WOCHEN", "monate": "MONATE",
          "monaten": "MONATE", "kilometer": "KM", "meter": "METER", "euro": "EURO", "dollar": "DOLLAR", "menschen": "MENSCHEN", "liter pro": "LITER",
          "haushalte": "HAUSHALTE", "tiere": "TIERE", "autos": "AUTOS", "bäume": "BÄUME", "kalorien": "KALORIEN", "stundenkilometer": "KM/H",
          "watt": "WATT", "kilowattstunden": "KWH", "mal": "MAL"}


def _number(word):
    """Deutsches Zahlwort (bis 999) → Zahl, sonst None."""
    w = word.lower().strip(".,;:!?")
    if w.replace(",", "").replace(".", "").isdigit():
        return float(w.replace(".", "").replace(",", "."))
    if w in ("halbe", "halb"):
        return 0.5
    if w.endswith("tausend") and w != "tausend":             # „fünfundvierzigtausend“
        base = _number(w[:-7])
        return base * 1000 if base else None
    if w == "tausend":
        return 1000
    if "tausend" in w:                                       # „dreitausendsechshundert“ in einem Wort (Video 214: die Einblendung „3.600 EURO“ fiel weg, weil die Zahl als nicht gesprochen galt)
        head_n, tail_n = w.split("tausend", 1)
        base_n = 1 if head_n in ("", "ein") else _number(head_n)
        rest_n = _number(tail_n[3:] if tail_n.startswith("und") and len(tail_n) > 3 else tail_n)
        return base_n * 1000 + rest_n if base_n and rest_n is not None and base_n < 1000 and 0 < rest_n < 1000 else None
    total = 0
    if "hundert" in w:
        h, w = w.split("hundert", 1)
        if h and h not in _ONES:
            return None
        total += (_ONES.get(h, 1) or 1) * 100
        if not w:
            return total
    if w in _ONES:
        return total + _ONES[w]
    if w in _TENS:
        return total + _TENS[w]
    if "und" in w:
        a, b = w.split("und", 1)
        if a in _ONES and b in _TENS:
            return total + _ONES[a] + _TENS[b]
    return None


def find_figure(text):
    """Sucht im Satz eine beeindruckende Zahl mit Einheit („achtzig Millionen Menschen“) → Zähler-Einblendung oder None."""
    ws = str(text or "").replace("-", " ").split()
    best = None
    for i, w in enumerate(ws):
        v = _number(w)
        if v is not None and i and ws[i - 1].lower() in ("mehrere", "mehreren", "einige", "einigen", "viele", "vielen", "paar", "etliche", "zig", "unzählige", "hunderte", "tausende", "wenige", "wenigen", "manche"):   # „nur wenige hundert Meter“ → kein Zähler „100 METER“ (Video 155)
            continue                                      # „mehrere tausend Grad“ ist keine Zahl für einen Zähler („1.000 GRAD“ wäre falsch)
        if v is None or (w.lower().strip(".,") in ("ein", "eine", "einen", "einem", "einer") and
                         (i + 1 >= len(ws) or ws[i + 1].lower().strip(".,;:!?") not in _SCALE)):
            continue
        if i >= 2 and ws[i - 1].lower().strip(".,") == "komma" and _number(ws[i - 2]) is not None and 0 <= v < 10 and v == int(v):
            v = _number(ws[i - 2]) + v / 10               # „zweiundzwanzig Komma fünf Stunden“ sind 22,5 – nicht „5 STUNDEN“ (Video 178)
        j, unit = i + 1, []
        if j < len(ws) and ws[j].lower().strip(".,;:!?") in _SCALE:
            unit.append(_SCALE[ws[j].lower().strip(".,;:!?")])
            j += 1
        if j < len(ws) and ws[j].lower().strip(".,;:!?") in _UNITS:
            unit.append(_UNITS[ws[j].lower().strip(".,;:!?")])
        if not unit:
            continue
        score = (2 if len(unit) == 2 else 1) + (1 if unit[0] in _SCALE.values() else 0)
        if best is None or score > best[0]:
            best = (score, v, " ".join(unit))
    if not best:
        return None
    return {"type": "counter", "label": "", "value": best[1], "unit": best[2]}


def _fmt_num(v):
    if abs(v - round(v)) < 1e-9:
        v = int(round(v))
        return f"{v:,}".replace(",", ".") if v >= 10000 else str(v)
    return f"{v:.1f}".replace(".", ",")


def auto_graphic(text, hud=""):
    """Erkennt im Satz, was sich als bewegte Grafik zeigen lässt: Warum-Frage, Zahl mit Einheit, Frist, Haushalte."""
    import re as _re
    raw = str(text or "").strip()
    low = raw.lower()
    kick = str(hud or "")[:36]
    if not _re.search(r"\d|\bTAG\b|\bJAHR", kick.upper()):
        kick = ""                                         # ein bloßer Ort („WALD“) ist keine Überschrift für eine Zahl
    if "?" in raw and _re.search(r"\b(warum|wieso|weshalb)\b", low):
        return {"type": "question", "text": _re.search(r"\b(warum|wieso|weshalb)\b", low).group(1).upper() + "?"}
    if _re.search(r"ganz europa|in europa|europaweit|europäisch|\beu\b|eu-staaten|quer durch europa", low):
        hot = sorted({v for k, v in graphics.REGION_WORDS.items() if k in low})
        return {"type": "map", "value": ",".join(hot), "text": kick}
    m = _re.search(r"\b(\w+) von (\w+)\b", low) if _re.search(r"\b(jede[rs]?|menschen|deutschen?|leuten?|personen|kinder|erwachsenen?|von ihnen|von uns)\b", low) else None
    if m:
        a, b = _number(m.group(1)), _number(m.group(2))
        if m.group(1) in ("einer", "eine", "eines", "jeder", "jede"):
            a = 1.0
        if a and b and a == int(a) and b == int(b) and 1 <= a < b <= 12:
            return {"type": "share", "value": f"{int(a)} VON {int(b)}", "kicker": kick}
    m = _re.search(r"\bjede[rs]? (zweite|dritte|vierte|fünfte|sechste|siebte|achte|neunte|zehnte)\b", low)
    if m:
        n = ("zweite", "dritte", "vierte", "fünfte", "sechste", "siebte", "achte", "neunte", "zehnte").index(m.group(1)) + 2
        return {"type": "share", "value": f"1 VON {n}", "kicker": kick}
    m = _re.search(r"\brunde (\w+)\b[:,.]?\s*(?:der |die |das |den )?([a-zäöüß\-]{3,18})?", low)
    if m and _number(m.group(1)) and len(raw.split()) <= 6:
        return {"type": "round", "kicker": f"RUNDE {int(_number(m.group(1)))}", "text": (m.group(2) or "LOS").upper()}
    fig = find_figure(raw)
    if not fig and _re.search(r"ganze stadt|stadtviertel|(?:blick|sicht|aufnahme|stadt|häuser|straßen) (?:\w+ ){0,2}von oben|von oben (?:gesehen|betrachtet|aus gesehen)|häuserblock|stadtweit|ganze viertel|millionenstadt|in der stadt", low):
        return {"type": "city", "kicker": kick, "dark": bool(_re.search(r"ohne strom|stromausfall|dunkel|ohne licht|lichter gehen aus", low))}
    if not fig:
        if raw.endswith("?") and len(raw.split()) <= 5 and len(raw) <= 26:
            return {"type": "question", "text": raw.upper()}
        return None
    v, unit = float(fig["value"]), str(fig["unit"])
    parts = unit.split()
    scale = parts[0] if parts and parts[0] in _SCALE.values() else ""
    noun = " ".join(parts[1:] if scale else parts)
    whole = abs(v - round(v)) < 1e-9
    if not scale and noun == "STUNDEN" and whole and 1 <= v <= 999 and _re.search(r"countdown|zeit läuft|bleiben dir|nur noch|auf dich allein|allein|ohne hilfe|frist|eigenständ|durchhalten|überstehen|autark|auf sich gestellt|selbst versorgen", low):
        return {"type": "timer", "value": f"{int(v):02d}:00:00", "kicker": kick}
    if not scale and noun in ("TAGE", "WOCHEN", "MONATE", "JAHRE") and whole and 1 <= v <= 999:
        return {"type": "calendar", "value": str(int(v)), "label": noun, "kicker": kick}
    val = (_fmt_num(v) + (" " + scale if scale else "")).strip()
    if _re.search(r"haushalt|häuser|wohnung|gebäude|familien", low):
        return {"type": "houses", "value": val, "label": noun or "HAUSHALTE", "kicker": kick,
                "dark": bool(_re.search(r"ohne strom|stromausfall|dunkel|ohne licht|abgeschnitten", low))}
    if noun == "%":
        val, noun = val + " %", ""
    return {"type": "number", "value": val, "label": noun, "kicker": kick}


def spoken_number(value, text):
    """Kommt die Zahl einer Einblendung im gesprochenen Satz vor (als Ziffer oder Zahlwort)?"""
    try:
        v = float(str(value).replace(".", "").replace(",", ".")) if isinstance(value, str) else float(value)
    except (TypeError, ValueError):
        return True                                       # keine Zahl (Text-Zähler): nicht zu prüfen
    nums = []
    prev_k = False
    for w in str(text or "").replace("-", " ").split():
        n = _number(w)
        if n is not None:
            if prev_k and n < 1000 and nums:               # „viertausend siebenhundert“ ist eine Zahl (4700) – nicht 4000 und 700
                nums[-1] += n
            else:
                nums.append(n)
        prev_k = n is not None and w.lower().strip(".,;:!?").endswith("tausend")
    if not nums:
        return False
    if "komma" in str(text or "").lower() and float(int(v)) in nums:
        return True                                       # „vier Komma vier Milliarden“
    return any(abs(n - v) < 1e-6 or abs(n * 1000 - v) < 1e-6 or abs(n * 1e6 - v) < 1e-3 or abs(n * 1e9 - v) < 1 for n in nums)


STORY_STYLES = ("nachricht", "storys", "grusel", "mysterien", "horror", "liebe")   # erzählte Geschichten: Nachrichten im Bild gehören zur Handlung
FIGURE_GFX = ("number", "badge", "houses", "share", "compare", "distance", "days", "pulse", "calendar", "timer", "phone")
_FIG_WORDS = set(_SCALE) | {"prozent", "hundert", "tausend"}


def unspoken_figures(box, text):
    """Steht in einer Grafik oder Einblendung eine Zahl (Ziffern oder Zahlwort wie „NULL PROZENT“), die der Sprecher im Satz
    (oder im Satz davor) nicht nennt? Solche Zahlen hat die Text-KI erfunden – der Zuschauer hört sie nie."""
    import re as _re
    said = str(text or "")
    low = said.lower()
    for k in ("value", "text", "label", "sub", "kicker", "unit"):
        v = box.get(k)
        if isinstance(v, bool) or not isinstance(v, (str, int, float)):
            continue
        v = str(v)
        for m in _re.finditer(r"\d[\d.]*(?:,\d+)?", v):
            if not spoken_number(m.group(0), said) and not _re.search(r"(?<![\d.,])" + _re.escape(m.group(0)) + r"(?![\d])", said):
                return True
        ws = [w.lower().strip(".,;:!?%") for w in v.replace("-", " ").split()]
        for j, w in enumerate(ws):
            n = _number(w) if w not in ("ein", "eine", "einen", "einem", "einer", "eins", "acht", "halb", "halbe") else None
            if n is not None and not w.replace(".", "").replace(",", "").isdigit() and (w == "null" or (j + 1 < len(ws) and (ws[j + 1] in _FIG_WORDS or ws[j + 1] in _UNITS))):
                if w not in low and not spoken_number(n, said):
                    return True
    return False


def _lead_number(value):
    import re as _re
    m = _re.search(r"\d[\d.]*(?:,\d+)?", str(value))
    return m.group(0) if m else str(value)


def has_ov0(sc):
    return isinstance(sc.get("overlay"), dict) and str(sc["overlay"].get("type") or "") in TALL_OV + ("choice",)


def _lib_props():
    try:
        from . import library
        return library.text_props()
    except Exception:  # noqa: BLE001
        return []


DENY_RE = r"\b(?:ohne|kein|keine|keinen|keinem|keiner|keines|keinerlei)\s+(?:(?!und\b|oder\b|aber\b)[a-zäöüß-]+\s+){0,2}?"


def denied(pat, low):
    """Nennt der Satz das Ding nur, um zu sagen, dass es fehlt („nur ohne Burgen“, „keinen Chip“, „ohne einen einzigen Fernseher“)?
    Dann gehört es nicht ins Bild. Steht es daneben auch unverneint im Satz, bleibt es."""
    low = str(low or "")
    hits = [m for m in re.finditer(pat, low)]
    if not hits:
        return False
    return all(re.search(DENY_RE + r"$", low[:m.start()]) for m in hits)


def topic_head(topic):
    """Kern eines langen Themas (bis zum ersten Doppelpunkt, Gedankenstrich oder der ersten Klammer). Ein Thema mit ausführlichen
    Vorgaben nennt viele Dinge – keines davon ist „das Ding des Themas“, das in jeder zweiten Szene im Bild steht."""
    import re as _re
    t = " ".join(str(topic or "").split())
    return _re.split(r"\s[–—-]\s|:\s|\s\(", t)[0] if len(t) > 90 else t


HEAP_RE = r"zucker|\bsalz|mehl|pulver|haufen|\bberg\b|berge\b|schnee|\bsand|kies|schutt|geröll|asche|staub|müll|abfall|schrott|plastik"
NUM_LABEL_RE = r"(?i)\b(nummer|nr\.?|regel|fakt|punkt|platz|runde|tipp|grund|stufe|teil)\s*#?\s*(eins|zwei|drei|vier|fünf|sechs|sieben|acht|neun|zehn|\d{1,2})\b"
_ORDINALS = {1: r"eins|erste|erstens", 2: r"zwei|zweite|zweitens", 3: r"drei|dritte|drittens", 4: r"vier|vierte|viertens", 5: r"fünf|fünfte|fünftens",
             6: r"sechs|sechste", 7: r"sieben|siebte", 8: r"acht|achte", 9: r"neun|neunte", 10: r"zehn|zehnte"}


def numbered_label_wrong(box, text):
    """Schild „REGEL NUMMER EINS“ / „FAKT 2“ an einem Satz, der diese Nummer gar nicht nennt (z. B. beim Cliffhanger über die letzte Regel)."""
    import re as _re
    lab = " ".join(str(box.get(k) or "") for k in ("text", "title", "label", "kicker"))
    m = _re.search(NUM_LABEL_RE, lab.replace("NUMMER", "").replace("Nummer", "").replace("  ", " ")) or _re.search(NUM_LABEL_RE, lab)
    if not m:
        return False
    n = int(m.group(2)) if m.group(2).isdigit() else {"eins": 1, "zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "sechs": 6, "sieben": 7, "acht": 8, "neun": 9, "zehn": 10}[m.group(2).lower()]
    pat = _ORDINALS.get(n)
    return bool(pat) and not _re.search(r"\b(?:" + pat + r")[rsnm]?\b", str(text or "").lower())


MATH_RE = r"\bmathe|primzahl|nullstelle|\bformel|gleichung|\bbeweis\w*|vermutung|geometrie|algebra|\brechenweg|zahlentheorie"


def _stay(scenes):
    """Schlussdurchgang: Dieselbe Figur stand im Bild davor schon am selben Ort – dann kommt sie nicht noch einmal von der Seite herein (Video 197: viermal
    hintereinander lief der Professor ins Klassenzimmer), sondern bleibt, zeigt, überlegt oder redet, jedes Mal anders als im Bild davor."""
    for i in range(1, len(scenes)):
        sc, prev = scenes[i], scenes[i - 1]
        if not isinstance(sc, dict) or not isinstance(prev, dict) or sc.get("shot") in ("graphic", "insert", "event") or prev.get("shot") in ("graphic", "insert", "event"):
            continue
        acts = [a for a in sc.get("actors") or [] if isinstance(a, dict)]
        if len(acts) != 1 or acts[0].get("kind") or str(acts[0].get("action") or "") != "walk" or not str(acts[0].get("pos") or "").startswith("off") or not acts[0].get("to"):
            continue
        if isinstance(backdrop(sc), dict) or isinstance(backdrop(prev), dict) or places.resolve(backdrop(sc)) != places.resolve(backdrop(prev)):
            continue
        was = next((a for a in prev.get("actors") or [] if isinstance(a, dict) and a.get("id") == acts[0].get("id")), None)
        if was is None or len([a for a in prev.get("actors") or [] if isinstance(a, dict)]) != 1:
            continue
        acts[0]["action"] = next(x for x in (("point", "think", "talk") * 2)[i % 3:] if x != str(was.get("action") or ""))
        acts[0]["pos"] = next(x for x in ((330, "center", 750) * 2)[i % 3:] if x != (was.get("to") or was.get("pos")))
        acts[0].pop("to", None)


def direct(scenes, times, topic="", style="", look=""):
    """Kleine Regie über das ganze Video: sorgt für Abwechslung, wenn das Drehbuch mehrmals hintereinander dieselbe
    Einstellung vorgibt (gleicher Ort, gleiche Figur, nur Reden) – andere Position, Nahaufnahme oder Hereinkommen."""
    prev_place, same, changes, prev_bd = None, 0, 0, None
    import re as _re0
    _clock = r"\d{1,2}[:.]\d{2}(?:\s*UHR)?|\d{1,2}\s*UHR"
    for sc in scenes:                                     # Bildplan sagt „Du rennst im Park“ und Ort park, die Baukasten-Landschaft daneben ist aber eine Straße: der genannte Ort gilt (Video 173)
        if isinstance(sc, dict) and isinstance(sc.get("backdrop"), dict) and isinstance(sc.get("place"), str) and sc["place"].strip():
            said_pl = _said_place(sc.get("see")) or _said_place(sc.get("text"))
            if said_pl and places.resolve(said_pl) == places.resolve(sc["place"]) and places.resolve(sc["place"]) in places.PLACES \
                    and places.resolve(sc["place"]) not in [places.EL_ALIASES.get(str(e_).lower(), str(e_).lower()) for e_ in sc["backdrop"].get("elements") or []]:
                sc["backdrop"] = None                     # enthält die Landschaft den Ort selbst (Wald mit Schneeboden), ist sie kein Widerspruch: der Winterwald bleibt verschneit (Video 199)
    for sc in scenes:                                     # erfundene Uhrzeit („02:00 UHR · WALD“) in der Ecke oder über einer Zahl: sagt der Satz keine Uhrzeit, entfällt sie
        if not isinstance(sc, dict) or _re0.search(r"\buhr\b", str(sc.get("text") or "").lower()):
            continue
        for box, key in ((sc, "hud"), (sc.get("graphic") if isinstance(sc.get("graphic"), dict) else {}, "kicker")):
            if isinstance(box.get(key), str) and _re0.search(_clock, box[key].upper()):
                parts = [x.strip() for x in _re0.split(r"\s*[·|•]\s*|\s+[–-]\s+", box[key]) if x.strip() and not _re0.fullmatch(_clock, x.strip().upper())]
                box[key] = " · ".join(parts) if key == "hud" else ""
        g_y = sc.get("graphic") if isinstance(sc.get("graphic"), dict) else None
        if g_y and isinstance(g_y.get("kicker"), str):    # Jahreszahl als kleine Überschrift über einer Zahl, die der Satz gar nicht nennt („1859“ über „10 BIO.“, Video 198)
            yrs_y = _re0.findall(r"(?<![\d.,])(1[0-9]{3}|20[0-9]{2})(?![\d.,])", g_y["kicker"])
            if yrs_y and not any(spoken_number(int(y_), str(sc.get("text") or "")) for y_ in yrs_y):
                g_y["kicker"] = ""
        low_c0 = str(sc.get("text") or "").lower()
        for pre_c in ("quadrat", "kubik"):                # „über tausend Quadratmeter Stoff“ → Schild „1000 METER STOFF“: die Einheit stimmt nicht
            if pre_c + "meter" in low_c0 and not _re0.search(r"(?<![a-zäöü])(?:kilo)?meter", low_c0):
                for box in (sc.get("overlay"), sc.get("graphic")):
                    for key in ("text", "label", "unit", "sub") if isinstance(box, dict) else ():
                        if isinstance(box.get(key), str):
                            box[key] = _re0.sub(r"(?<![A-Za-zÄÖÜäöü])METERN?\b", pre_c.upper() + "METER", box[key])
        for box in (sc.get("overlay"), sc.get("graphic")):  # „Milliarden“ gesagt, „BILLIONEN“ gezeigt (falscher Freund aus dem Englischen) – und Währungen, die niemand nennt
            if not isinstance(box, dict):
                continue
            for key in ("value", "text", "label", "sub", "unit", "kicker"):
                v_c = box.get(key)
                if not isinstance(v_c, str):
                    continue
                if "milliard" in low_c0 and "billion" not in low_c0 and _re0.search(r"BILLION|\bBIO\b", v_c.upper()):
                    v_c = _re0.sub(r"(?i)billionen", "MILLIARDEN", v_c)
                    v_c = _re0.sub(r"(?i)billion", "MILLIARDE", v_c)
                    v_c = _re0.sub(r"(?i)\bbio\b\.?", "MRD.", v_c)
                    box[key] = v_c
                if key in ("label", "sub", "unit", "kicker"):
                    for cur_c in ("reichsmark", "euro", "dollar", "pfund", "franken", "rubel", "yen", "d-mark", "goldmark"):
                        if cur_c in v_c.lower() and cur_c not in low_c0:
                            box[key] = ""
        for box in (sc.get("overlay"), sc.get("graphic")):  # ausgeschriebene Jahreszahl auf Schild oder Grafik → Ziffern (sonst wird das Schild abgeschnitten)
            for key in ("text", "kicker", "sub", "label", "title") if isinstance(box, dict) else ():
                if isinstance(box.get(key), str) and "hundert" in box[key].lower():
                    box[key] = year_digits(box[key])
        if isinstance(ov_m := sc.get("overlay"), dict) and str(ov_m.get("type") or "") == "tag" and isinstance(ov_m.get("text"), str):
            for mon_c in _MONTHS.split("|"):               # Schild „MAI 1945“, der Satz sagt aber nur „im Frühjahr“: den erfundenen Monat streichen
                if _re0.search(r"(?i)\b" + mon_c + r"\b", ov_m["text"]) and mon_c not in low_c0 and _re0.search(r"\d{4}", ov_m["text"]):
                    ov_m["text"] = " ".join(_re0.sub(r"(?i)\b\d{0,2}\.?\s*" + mon_c + r"\b", "", ov_m["text"]).split())
        g_c = sc.get("graphic")
        if isinstance(g_c, dict) and str(g_c.get("type") or "").lower() == "question" and "?" not in str(sc.get("text") or "") and str(g_c.get("text") or "").strip():
            g_c["type"] = "badge"                         # großes Fragezeichen über einem Satz, der nichts fragt („Tauchen ist streng verboten“): als Plakette zeigen
        if isinstance(g_c, dict) and str(g_c.get("type") or "").lower() == "badge" and str(sc.get("shot") or "") == "graphic":
            stems_c = [w_[:5] for w_ in _re0.findall(r"[a-zäöüß]{4,}", (str(g_c.get("text") or "") + " " + str(g_c.get("kicker") or "")).lower())]
            if stems_c and not any(st_ in low_c0 for st_ in stems_c):
                sc["graphic"], sc["shot"] = None, ""      # Plakette ohne ein einziges Wort aus dem Satz („KÜHLSCHRANK STREIKT“ zum Nachbarn mit der Polizei): der Satz bekommt ein echtes Bild
        if isinstance(g_c, dict) and sc.get("graphic") and str(g_c.get("type") or "").lower() == "badge" and "?" not in str(sc.get("text") or ""):
            for key_q in ("text", "kicker"):              # Plakette „ÜBERLEBENSREFLEX?“ über einem Satz, der es feststellt: ohne Fragezeichen
                if isinstance(g_c.get(key_q), str) and g_c[key_q].rstrip().endswith("?"):
                    g_c[key_q] = g_c[key_q].rstrip().rstrip("?").rstrip()
        i_q = next(j_q for j_q, x_q in enumerate(scenes) if x_q is sc)
        pv_q = scenes[i_q - 1] if i_q and isinstance(scenes[i_q - 1], dict) else {}
        if isinstance(g_c, dict) and sc.get("graphic") and str(g_c.get("type") or "").lower() == "badge" and str(sc.get("shot") or "") == "graphic" \
                and str(pv_q.get("shot") or "") == "graphic" and isinstance(pv_q.get("graphic"), dict) and [a_q for a_q in (sc.get("actors") or []) if isinstance(a_q, dict)]:
            sc["graphic"], sc["shot"] = None, ""          # zwei Vollbild-Grafiken hintereinander (Fragezeichen, dann Plakette – neun Sekunden ohne Bild): die Plakette weicht dem Bild der Szene
        if isinstance(g_c, dict) and sc.get("graphic") and str(g_c.get("type") or "").lower() == "podium":
            near_q = " ".join(str(scenes[j_q].get("text") or "") for j_q in (i_q - 1, i_q, i_q + 1) if 0 <= j_q < len(scenes) and isinstance(scenes[j_q], dict)).lower()
            hit_q = sum(1 for key_q in ("text", "left", "right")
                        if any(w_[:5] in near_q for w_ in _re0.findall(r"[a-zäöüß]{3,}", str(g_c.get(key_q) or "").lower())))
            if hit_q < 2:                                 # Siegertreppchen mit Plätzen, die niemand nennt („ARME, NACKEN, RÜCKEN“ zur Frage, warum es nicht jeder spürt): erfunden – der Satz bekommt ein echtes Bild
                sc["graphic"] = None
                sc["shot"] = "" if sc.get("shot") == "graphic" else sc.get("shot")
        if isinstance(sc.get("backdrop"), dict) and str(sc.get("place") or "").strip() and places.resolve(sc.get("place")) in ROOMS \
                and not _re0.search(OUTSIDE_RE, low_c0):
            sc["backdrop"] = None                         # Ort „Zimmer“, dazu ein Landschafts-Baukasten (Bauernhof mit Feldern), von dem kein Satz spricht: der Raum gilt (Video 123 begann auf einem Bauernhof bei Nacht)
        for key_m in ("hud", "status"):                   # Regie-Wort als Ecken-Zeile („REHOOK“, „FINTE“ im Bildplan von Video 179): entfällt
            if isinstance(sc.get(key_m), str) and _re0.search(META_LABEL_RE, sc[key_m].upper()) and not _re0.search(META_LABEL_RE, low_c0.upper()):
                sc[key_m] = ""
        for key_m in ("overlay", "graphic"):              # Regie-Wort der Drehbuch-Anleitung als Einblendung („CLIFFHANGER“, „REHOOK“): hat im Bild nichts zu suchen
            box_m = sc.get(key_m)
            if isinstance(box_m, dict):
                shown_m = " ".join(str(box_m.get(k_m) or "") for k_m in ("text", "title", "kicker", "label")).upper()
                if _re0.search(META_LABEL_RE, shown_m) and not _re0.search(META_LABEL_RE, low_c0.upper()):
                    if str(box_m.get("type") or "") in ("card", "tag", "stamp", "badge", "note") or key_m == "graphic":
                        sc[key_m] = None
                        if key_m == "graphic" and sc.get("shot") == "graphic":
                            sc["shot"] = ""
                    else:
                        for k_m in ("title", "kicker", "label"):
                            if isinstance(box_m.get(k_m), str) and _re0.search(META_LABEL_RE, box_m[k_m].upper()):
                                box_m[k_m] = ""
        if isinstance(sc.get("overlay"), dict) and str(sc["overlay"].get("type") or "") in ("checklist", "note") \
                and isinstance(sc["overlay"].get("title"), str) and _re0.search(ENGLISH_TITLE_RE, sc["overlay"]["title"].upper()):
            sc["overlay"]["title"] = "CHECKLISTE" if sc["overlay"]["type"] == "checklist" else ""   # englischer Titel („NIGHT SHIFT“) in einem deutschen Video
        ov_c = sc.get("overlay")
        if isinstance(ov_c, dict) and str(ov_c.get("type") or "") == "choice" and "?" not in str(sc.get("text") or "") and not _re0.search(r"\boder\b", str(sc.get("text") or "").lower()):
            sc["overlay"] = None                          # Auswahl „A/B“ an einem Satz, der gar keine Frage stellt
    power_out = False
    last_id = None
    math_zero, math_n = None, {"zeros": 0, "primes": 0}     # Mathe-Schaubilder: letzter Satz mit „Nullstellen“, Anzahl je Art
    maps_used = 0
    spooky = str(style or "").lower() in ("grusel", "mysterien", "horror")
    used = {}
    fig_prev, inserts, counters = False, 0, 0
    topic_things = [k for pat, k in _lib_props() + TEXT_PROPS if _re0.search(pat, str(topic or "").lower()) and extras.prop_fit(k)][:2]
    topic_any = [k for pat, k in _lib_props() + TEXT_PROPS if _re0.search(pat, str(topic or "").lower())][:2]   # auch Himmel/Natur
    _CTX["mem"] = bool(_re0.search(MEM_TOPIC_RE, (str(topic or "") + " " + " ".join(str(x.get("text") or "") for x in scenes if isinstance(x, dict))).lower()))
    topic_place = _hint(topic)
    topic_place = topic_place if isinstance(topic_place, str) and topic_place in TOPIC_PLACES else None
    stale, topic_ins, gfx = 0, 0, 0
    size_done = False                                     # „nur einen halben Millimeter groß“: einmal je Video die Größe mit Lineal zeigen
    charts = 0
    neon = str(look or "").lower() == "neon"
    noir = str(look or "").lower() == "noir"
    cur_hud = ""
    sea_last = any_last = None
    sea_age = any_age = 0
    _SEA_DEF[0] = None
    _SEA_DEF[0] = _sea_default(scenes, topic)
    any_video = _one_tiny(scenes)
    sea_topic = bool(_re0.search(SEA_TOPIC_RE, str(topic or "").lower() + " " + " ".join(str(x.get("text") or "") for x in scenes if isinstance(x, dict)).lower()))
    for i, (sc, (s0, e0)) in enumerate(zip(scenes, times)):
        sanitize(sc)
        low_d = str(sc.get("text") or "").lower()
        deep_f = bool(_re0.search(DEEP_RE, low_d) or (sea_topic and _re0.search(SUB_RE, low_d)) or str(sc.get("place") or "").lower() in ("underwater", "unterwasser"))
        if deep_f:
            # Meeresboden, Tiefsee, Tauchboot: spielt unter Wasser – auch wenn das Drehbuch dazu eine Landschaft mit Meeresoberfläche und Himmel angibt
            sc["place"], sc["backdrop"] = "underwater", None
            sc["_deep"] = bool(_re0.search(DEEP_THING_RE, low_d))
            if sc["_deep"] or _re0.search(DEEP_DARK_RE, low_d):
                sc["time"], sc["weather"] = "night", ""           # „Nacht“ unter Wasser zeichnet die Tiefsee: dunkel, Schlick, kein Sonnenlicht
        under0 = places.resolve(backdrop(sc)) == "underwater"
        if spooky:                                        # Grusel und Rätsel spielen im Dunkeln; Stimmung unheimlich, keine Passanten
            if not _re0.search(r"tagsüber|am tag\b|mittags|sonnenschein|am nächsten morgen|am morgen", sc["text"].lower()):
                sc["time"] = "night"
            if sc["mood"] in ("", "calm", "happy"):
                sc["mood"] = "scary"
            if sc["crowd"] in ("walk", "cheer"):
                sc["crowd"] = ""
        if style == "liebe" and sc["mood"] in ("", "calm", "happy"):   # Liebesgeschichten: rosiges Licht, schwebende Herzen (Trauriges bleibt traurig)
            sc["mood"] = "love"
        sc["props"] = [q for q in sc["props"] if (lambda k: k in extras.PROPS or k in extras.PROP_ALIASES or k in extras.HELD)(q["type"].lower())]
        low0 = sc["text"].lower()
        if not _re0.search(HEAP_RE, low0):                # weißer Haufen (Zucker/Salz), Sand- oder Müllberg nur, wenn der Satz davon spricht
            sc["props"] = [q for q in sc["props"] if extras.PROP_ALIASES.get(q["type"].lower(), q["type"].lower()) not in ("pile", "sandpile", "trash")]
        ov_n = sc.get("overlay") if isinstance(sc.get("overlay"), dict) else None
        if ov_n and str(ov_n.get("type") or "").lower() in ("tag", "card", "note", "stamp") and numbered_label_wrong(ov_n, sc["text"]):
            sc["overlay"] = None                          # „REGEL NUMMER EINS“ über einem Satz, der die Nummer nicht nennt
        elif ov_n and str(ov_n.get("type") or "").lower() == "stamp" and len(str(ov_n.get("text") or "").strip()) > 16:
            ov_n["type"] = "card"                         # ein Stempel fasst 16 Zeichen: „GESCHONTER RÜCKEN“ wurde zu „GESCHONTER“ gekürzt (Video 228) – längere Urteile stehen als Karte da
        elif ov_n and str(ov_n.get("type") or "").lower() == "stamp":
            st_w = [w for w in _re0.findall(r"[a-zäöüß]{4,}", str(ov_n.get("text") or "").lower())]
            if st_w and not any(w[:5] in low0 for w in st_w) and not any(_re0.search(p_, low0) and lab_ == str(ov_n.get("text") or "").upper() for p_, lab_, _c in STAMPS):
                sc["overlay"] = None                      # Stempel („GRATIS“, „PLEITE“) mit einem Wort, das im Satz gar nicht fällt
            elif any(refuted(w[:5], low0) for w in st_w):
                sc["overlay"] = None                      # Stempel „VERBOTEN“ zu „Du denkst, das war verboten? Falsch, …“
        simile = sc["_simile"] = []
        for pat, k in TEXT_PROPS:                         # „wie ein Raketenstart“, „wie ein Vulkan“: ein Vergleich, kein Ding im Bild
            m = _re0.search(r"\bwie (?:bei |in |auf |von )?(?:ein\w* |der |die |das |dem |den )?(?:\w+ )?(?:" + pat + ")", low0)
            if m and not _re0.search(pat, low0[:m.start()] + " " + low0[m.end():]):
                simile.append(k)
                sc["props"] = [q for q in sc["props"] if extras.PROP_ALIASES.get(q["type"].lower(), q["type"].lower()) != k]
        for pat, k in _lib_props() + TEXT_PROPS:          # „nur ohne Burgen“, „weil er keinen Chip besitzt“: wovon der Satz sagt, dass es fehlt, steht nicht im Bild (Video 156)
            if k not in simile and denied(pat, low0):
                simile.append(k)
                sc["props"] = [q for q in sc["props"] if extras.PROP_ALIASES.get(q["type"].lower(), q["type"].lower()) != k]
        if sc["weather"] in ("dark", "dunkel", "blackout") and not _re0.search(r"dunkel|finster|nacht|schwarz|\bstrom|licht|blackout|sonne", low0):
            sc["weather"] = ""                            # Dunkelheit nur, wenn der Satz davon spricht – sonst erkennt man das Bild nicht
        acts = [a for a in (sc.get("actors") or []) if isinstance(a, dict)]
        place = places.resolve(sc.get("place"))
        if place in ("space", "moon") and not isinstance(sc.get("backdrop"), dict) and not _re0.search(SPACE_RE, low0) \
                and not _re0.search(SPACE_RE, str(topic or "").lower()):
            sc["place"] = place = "street"                # der Satz spielt nicht im All (z. B. „das Internet“): Ort aus dem Satz, sonst die Stadt
            sc["time"] = "" if sc.get("time") == "night" and not _re0.search(r"nacht|dunkel|abend", low0) else sc.get("time")
            sc["props"] = [q for q in sc["props"] if extras.PROP_ALIASES.get(q["type"].lower(), q["type"].lower()) not in extras.SKY]
        if place in MAPS and not isinstance(sc.get("backdrop"), dict) and _hint(sc.get("text")) is not None \
                and not any(_re0.search(pat, sc["text"].lower()) for pat, _ in MAP_HINTS):
            sc["place"] = place = "park"                  # der Satz nennt einen Schauplatz (Ozean, Wald, Stadt …), nicht die ganze Welt: dort spielt die Szene
        if place in MAPS:                                 # Karte höchstens zweimal pro Video – und nie zweimal hintereinander (zehn Sekunden dieselbe Weltkugel)
            maps_used += 1
            if maps_used > 2:
                sc["place"] = place = "street"
            elif i and isinstance(scenes[i - 1], dict) and places.resolve(scenes[i - 1].get("place")) in MAPS and not isinstance(sc.get("backdrop"), dict):
                maps_used -= 1
                sc["place"] = place = "livingroom"        # die Hauptfigur erlebt den Satz (leere Szene wird unten gefüllt)
        ov_c = sc.get("overlay") if isinstance(sc.get("overlay"), dict) else None
        if ov_c and str(ov_c.get("type") or "").lower() in graphics.TYPES and str(ov_c.get("type") or "").lower() != "phone":
            if not sc.get("graphic") and graphics.clean(ov_c) and not (i == 0 and str(ov_c.get("type") or "").lower() == "round"
                                                                        and any(isinstance(a_, dict) for a_ in sc.get("actors") or [])):
                sc["graphic"], sc["shot"] = graphics.clean(ov_c), "graphic"   # Grafik stand versehentlich als Einblendung im Drehbuch: als Grafik zeigen – außer im
                # ersten Bild mit Figuren: dort bleibt die Szene (das Paar im Café), der Hook-Titel steht ohnehin oben; eine Titelkarte „LIEBE / SITUATIONSHIP“ statt des Bildes
                # ergab mit Handy-Grafik und „ZEICHEN 1“ drei Tafeln am Stück zum Einstieg (Video 190)
            sc["overlay"] = ov_c = None
        g0 = sc.get("graphic") if isinstance(sc.get("graphic"), dict) else None
        was_gfx = bool(g0) and str(sc.get("shot") or "") == "graphic"
        if g0 and g0.get("type") == "map" and not _re0.search(GEO_RE, low0):
            sc["graphic"], g0 = None, None                # Europakarte mit leuchtenden Ländern zu einem Satz, der kein Land und keine Karte nennt (Satelliten-Pings)
            sc["shot"] = "" if sc.get("shot") == "graphic" else sc.get("shot")
        if g0 and g0.get("type") == "radar" and not deep_f:   # Radarschirm aus dem Drehbuch: ob der Punkt erlischt, bestimmt der Satz
            none_r = bool(_re0.search(r"\b(?:kein|keine|keinen|ohne) (?:\w+ )?radar", low0))
            lost_r = none_r or bool(_re0.search(RADAR_LOST_RE, low0)) or str(g0.get("sub") or "").lower()[:4] in ("lost", "verl", "weg", "gone")
            g0["sub"] = "lost" if lost_r else ""
            if none_r:
                g0["text"] = "KEIN RADAR"
            elif not str(g0.get("text") or "").strip() or len(str(g0.get("text"))) > 22:
                g0["text"] = "SIGNAL VERLOREN" if lost_r else "RADAR"
        elif not deep_f and _re0.search(RADAR_RE, low0) and not (g0 and g0.get("type") in FIGURE_GFX and graphics.clean(g0)):
            none_r = bool(_re0.search(r"\b(?:kein|keine|keinen|ohne) (?:\w+ )?radar", low0))
            lost_r = none_r or bool(_re0.search(RADAR_LOST_RE, low0))   # „verschwindet vom Radar“: Radarschirm, der Leuchtpunkt erlischt
            sc["graphic"] = g0 = {"type": "radar", "text": "KEIN RADAR" if none_r else "SIGNAL VERLOREN" if lost_r else "RADAR", "sub": "lost" if lost_r else ""}
            sc["shot"], sc["overlay"] = "graphic", None
            ov_c = None
        # Mathe-Themen (Prüfung 24.11.2026, Video 197 „Riemann-Vermutung“): zu „Nullstellen … liegen auf einer Linie“ und „Geheimnis der Primzahlen“ lief eine Figur
        # vor einer leeren Tafel auf und ab – das Schaubild zeigt, wovon der Satz spricht
        if _re0.search(ZEROS_RE, low0):
            math_zero = i
        cnt_m = bool(ov_c and str(ov_c.get("type") or "") == "counter")
        g_m = bool(g0 and graphics.clean(g0))
        prev_m = scenes[i - 1] if i and isinstance(scenes[i - 1], dict) else {}
        prev_gm = str((prev_m.get("graphic") or {}).get("type") or "") if prev_m.get("shot") == "graphic" and isinstance(prev_m.get("graphic"), dict) else ""
        if i and not g_m and not cnt_m and not deep_f:
            line_m = bool(_re0.search(ZLINE_RE, low0))
            near_m = math_zero is not None and i - math_zero <= 6
            new_m = None
            after_g = prev_m.get("shot") == "graphic"         # nicht Tafel auf Tafel: nach einem Schaubild nur die Kernaussage „alle auf einer Linie“ – sonst steht die Figur vor der Mathe-Tafel
            if (math_zero == i or (line_m and near_m)) and math_n["zeros"] < 3 and prev_gm != "zeros" and (line_m or not after_g):
                new_m = {"type": "zeros", "text": "ALLE AUF EINER LINIE" if line_m else ""}
            elif near_m and math_n["zeros"] and math_n["zeros"] < 3 and prev_gm != "zeros" and not after_g and _re0.search(r"\bausnahme|gegenbeispiel|\babweich|aus der reihe", low0):
                new_m = {"type": "zeros", "sub": "doubt", "text": "GIBT ES EINE AUSNAHME?"}
            elif _re0.search(PRIMES_RE, low0) and math_n["primes"] < 2 and not after_g and not _re0.search(r"verschlüssel|passw|sicherheit|\bbank|konto", low0):
                new_m = {"type": "primes", "sub": "100" if math_n["primes"] else "", "kicker": "PRIMZAHLEN BIS 100" if math_n["primes"] else "PRIMZAHLEN"}
            if new_m:
                math_n[new_m["type"]] += 1
                sc["graphic"] = g0 = new_m
                sc["shot"], sc["overlay"] = "graphic", None
                ov_c = None
        if ov_c and str(ov_c.get("type") or "") == "tag":      # Schild mit dem Namen einer echten Person über einer Figur („BERNHARD RIEMANN“, Video 197): die Figur ist nicht diese Person
            m_p = _re0.search(PERSON_JOB_RE + r"(?:in)? ((?:[A-ZÄÖÜ][\w-]+ ){0,2}[A-ZÄÖÜ][\w-]+)", str(sc.get("text") or ""))
            if m_p and any(w_.lower() in str(ov_c.get("text") or "").lower() for w_ in m_p.group(1).split() if len(w_) > 3):
                sc["overlay"] = ov_c = None
        if g0 and g0.get("type") == "chart" and g0.get("value") and not spoken_number(_lead_number(g0["value"]), sc["text"]):
            g0.pop("value", None)                         # Kurve ja – aber keine Zahl, die der Sprecher nicht nennt
            if _re0.search(r"dollar|euro|%|prozent|mio|mrd|bio", str(g0.get("label") or "").lower()):
                g0.pop("label", None)
        if ov_c and str(ov_c.get("type") or "") == "counter" and not spoken_number(ov_c.get("value"), sc["text"]):
            sc["overlay"] = None                          # Zahl in der Einblendung, die der Sprecher gar nicht nennt: weg damit
        if ov_c and sc.get("overlay") and str(ov_c.get("type") or "") == "counter" and str(ov_c.get("value")).replace(".0", "") in ("100", "1000", "1000000", "1000000000") \
                and _re0.search(r"\b(?:wenige|mehrere|einige|viele|etliche|manche)n?\s+(?:hundert|tausend|millionen|milliarden)|\bpaar\s+(?:hundert|tausend|millionen|milliarden)", str(sc.get("text") or "").lower()):
            sc["overlay"] = None                          # „nur wenige hundert Meter“ ist keine Zahl für einen Zähler („100 METER“ stand quer über dem Gepard, Video 155)
        if ov_c and str(ov_c.get("type") or "") == "bar" and not spoken_number(ov_c.get("value"), sc["text"]):
            sc["overlay"] = ov_c = None                   # Füllstand „SAUERSTOFF 15 %“ zu einem Satz ohne Zahl: die Prozentzahl ist erfunden
        if ov_c and str(ov_c.get("type") or "") == "thermo" and (not spoken_number(ov_c.get("value"), sc["text"])
                                                                  or not -90 <= (graphics._num(str(ov_c.get("value"))) or 0) <= 120):
            sc["overlay"] = ov_c = None                   # Thermometer mit einer Zahl, die niemand sagt (44000 statt 4500), oder jenseits der Skala
        if ov_c and str(ov_c.get("type") or "") == "thermo":
            low_th = str(sc.get("text") or "").lower()
            down_th = bool(_re0.search(r"\bs[ia]nk|gesunken|\bf[aä]ll|gefallen|stürz|kälter|kühler|kühlt|weniger grad", low_th))
            v_th = graphics._num(str(ov_c.get("value"))) or 0
            if _re0.search(r"\bum (?:über |fast |rund |etwa |mehr als |bis zu |ganze )?\S+ grad|grad (?:mehr|wärmer|kälter|weniger|kühler)", low_th):
                sc["overlay"] = ov_c = {"type": "card", "text": f"{abs(v_th):g}".replace(".", ",") + (" GRAD KÄLTER" if down_th else " GRAD WÄRMER")}   # „sinken um fünfzehn Grad“ ist ein Unterschied, kein Stand: kein Thermometer, das auf plus 15 °C steigt
            elif v_th > 0 and _re0.search(r"minus\s+\S+\s+grad|unter null|unter den gefrierpunkt", low_th):
                ov_c["value"] = -abs(v_th)                # „minus zwanzig Grad“: die Säule fällt unter null
        if g0 and g0.get("type") == "compare" and graphics._num(g0.get("value")) is not None \
                and graphics._num(g0.get("value")) == graphics._num(g0.get("sub")):
            sc["graphic"] = g0 = {"type": "number", "kicker": str(g0.get("left") or ""), "value": str(g0.get("value")),   # „Vergleich“ mit zweimal derselben
                                  "label": ""}                                                                             # Zahl: als eine große Zahl zeigen
        said_c = sc["text"] + " " + (str(scenes[i - 1].get("text") or "") if i and isinstance(scenes[i - 1], dict) else "")
        if g0 and g0.get("type") == "news" and _re0.search(r"fernseh|\btv\b|nachrichtensend|sondersendung|im radio und|bildschirm", sc["text"].lower()) \
                and not _re0.search(r"zeitung|schlagzeile|titelseite|\bblatt\b", sc["text"].lower()):
            g0["tv"] = True                               # „Im Fernsehen läuft eine Eilmeldung“: Fernsehbild, keine Zeitungsseite (Video 192)
        g_chk = g0
        if g0 and g0.get("type") == "phone" and str(style or "").lower() in STORY_STYLES:
            # Nachricht auf dem Handy in einer Geschichte: ihr Wortlaut ist Teil der Handlung („Du hast die Nachricht selbst gesendet. Aus dem
            # Jahr 2035.“), keine erfundene Zahl – und die Uhr des Sperrbildschirms ist keine Behauptung (Video 192: die Auflösung fehlte im Bild)
            g_chk = {k_: v_ for k_, v_ in g0.items() if k_ not in ("text", "sub", "label")
                     and not (k_ == "value" and _re0.fullmatch(r"\s*\d{1,2}[:.]\d{2}\s*(?:uhr)?\s*", str(v_).lower()))}
        if g0 and g0.get("type") in FIGURE_GFX and unspoken_figures(g_chk, said_c):
            sc["graphic"], g0 = None, None                # Grafik mit einer Zahl, die niemand sagt („1.000.000 KARTEN“, „100 % KONTROLLE“): erfunden – weg
            sc["shot"] = "" if sc.get("shot") == "graphic" else sc.get("shot")
        if g0 and g0.get("type") == "pulse" and not _re0.search(r"puls|herz|schläge pro|\bbpm\b|adrenalin|blutdruck", sc["text"].lower()) \
                and graphics._num(g0.get("value")) is not None and (_stems(g0.get("label")) & _stems(sc["text"])):
            # „Der Countdown erreicht null“ mit Herzschlag-Kurve „0 · COUNTDOWN ABGELAUFEN“: Zahl und Wort stimmen, nur die Kurve nicht – als große Zahl zeigen (Video 192)
            sc["graphic"] = g0 = {"type": "chapter" if str(style or "").lower() == "nachricht" else "number", "value": str(g0.get("value")),
                                  "label": str(g0.get("label") or ""), "text": str(g0.get("label") or ""), "kicker": str(g0.get("kicker") or "")}
        if g0 and g0.get("type") == "pulse" and not _re0.search(r"puls|herz|schläge pro|\bbpm\b|adrenalin|blutdruck", sc["text"].lower()):
            sc["graphic"], g0 = None, None                # Herzschlag-Kurve mit „1 · MOMENT DER STILLE“ zu einem Satz, der von keinem Herzschlag spricht (Video 168)
            sc["shot"] = "" if sc.get("shot") == "graphic" else sc.get("shot")
        if ov_c and sc.get("overlay") and str(ov_c.get("type") or "") in ("card", "counter", "note", "stamp") and unspoken_figures(ov_c, said_c):
            sc["overlay"] = None
        if ov_c and sc.get("overlay") and str(ov_c.get("type") or "") == "tag" and not _re0.search(r"\b(1[0-9]|20)\d{2}\b", str(ov_c.get("text") or "")) \
                and unspoken_figures(ov_c, sc["text"]):
            sc["overlay"] = None                          # Schild „SEKUNDE 10“ an einem Satz, der die Zahl nicht nennt (sie fällt erst im nächsten); Jahreszahlen bleiben
        if was_gfx and not isinstance(sc.get("graphic"), dict) and not acts and not sc.get("props") and not sc.get("crowd") and i:
            # Grafik mit erfundener Zahl ist entfallen („300 KG“, „10 HP“): Der Satz spielt dort weiter, wo die Geschichte gerade ist – mit der Figur von eben.
            # Bisher blieb der Platzhalter-Ort der Grafik („zimmer“) stehen, und die Figur lief dreimal durchs leere Wohnzimmer (Video 206)
            for back_g in scenes[max(0, i - 3):i][::-1]:
                hum_g = [a_ for a_ in (back_g.get("actors") or []) if isinstance(a_, dict) and not a_.get("kind") and a_.get("id")] if isinstance(back_g, dict) else []
                if hum_g and str(back_g.get("shot") or "") not in ("graphic", "insert", "mirror") and places.resolve(backdrop(back_g)) not in MAPS:
                    sc["place"], sc["time"] = back_g.get("place"), back_g.get("time") or sc.get("time")
                    sc["backdrop"] = dict(back_g["backdrop"]) if isinstance(back_g.get("backdrop"), dict) else None
                    ask_g = bool(_re0.search(r"\?\s*$|\bdu denkst\b|\bdu glaubst\b|\bfrag", sc["text"].lower()))
                    sc["actors"] = acts = [{"id": hum_g[0]["id"], "action": "think" if ask_g else "idle", "pos": "center",
                                            "emotion": MOOD_EMOTION.get(str(sc.get("mood") or "").lower(), ""), "emote": "?" if ask_g else ""}]
                    place = places.resolve(sc.get("place"))
                    break
        has_bd = isinstance(sc.get("backdrop"), dict) and (sc["backdrop"].get("elements") or sc["backdrop"].get("ground"))
        if not has_bd and not deep_f and not (sc.get("shot") == "graphic" and graphics.clean(sc.get("graphic"))) and not _re0.search(r"unter wasser|taucht|tauchen|versink|versunk|\bsinkt|gesunken", low0) \
                and (_re0.search(SURFACE_RE, low0) or (_re0.search(DEBRIS_RE, low0) and _re0.search(r"treib(?!gut)|schwimm|strömung|\bmeer|ozean", low0)
                                                      and not _re0.search(r"forscher|wissenschaftler|ermittler|expert|untersuch|\blabor|analys|biolog|muschel|seepocke", low0))):
            # „auf dem Ozean“, „über dem Meer“, treibende Trümmer: die Meeresoberfläche mit Himmel – nicht der Meeresgrund mit Goldfisch, nicht der Palmenstrand
            sc["backdrop"] = {"sky": "night" if str(sc.get("time") or "").lower() == "night" else "day", "ground": "water", "elements": ["sea"]}
            sc["place"] = place = "beach"
            has_bd = True
        hint = None if has_bd or deep_f else _hint(sc.get("text"))
        said = None if has_bd or place in MAPS or deep_f else _said_place(sc.get("text"))
        if isinstance(hint, str) and not said and not has_bd:
            # „… schickt dir einen Countdown zu deiner Dachbodentür“: der Ort steckt nur in einem zusammengesetzten Ding-Wort – nennt die
            # Bildbeschreibung ausdrücklich einen anderen Ort („schläft im dunklen Schlafzimmer“), gilt der (Video 192: schlief auf dem Dachboden)
            see_pl = _said_place(sc.get("see"))
            if see_pl and places.resolve(see_pl) != places.resolve(hint) \
                    and _hint(_re0.sub(COMPOUND_THING_RE, " ", str(sc.get("text") or "").lower())) != hint:
                hint = None
                if places.resolve(see_pl) != places.resolve(place) and place in GENERIC:
                    sc["place"] = place = see_pl
        if not said and hint is None and topic_place and place == "livingroom" and not sc.get("props") and topic_place != place \
                and not (i and isinstance(scenes[i - 1], dict) and places.resolve(scenes[i - 1].get("place")) == topic_place):
            said = topic_place                            # ortlose Szene im Allerwelts-Wohnzimmer: dort spielen, wovon das Video handelt (Hollywood → Kino)
        if said:                                          # der Satz nennt den Ort selbst („in deinen Garten“, „im Keller“): das gilt
            if isinstance(hint, str) and (hint.startswith(said) or said.startswith(hint)):
                said = hint                               # genauere Fassung aus den Hinweisen (leerer statt voller Supermarkt)
            if places.resolve(said) != places.resolve(place):
                sc["place"], sc["backdrop"] = said, None
                place = said
            hint = None
        used[place] = used.get(place, 0) + 1
        if hint is not None and (place in GENERIC or str(sc.get("shot") or "") == "event" or used[place] >= 3):   # ab dem dritten Mal am selben Ort darf der Text den Schauplatz wechseln
            if isinstance(hint, dict):               # passende Landschaft aus dem Baukasten
                if place != "custom":
                    sc["backdrop"] = hint
            elif hint != place:
                sc["place"] = place = hint
        if places.resolve(sc.get("place")) == "bedroom" and not acts and str(sc.get("shot") or "") in ("", "event") \
                and _re0.search(r"schlaf|weck|\bwach|\bbett\b|träum", str(sc.get("text") or "").lower()):
            woke = bool(_re0.search(r"weck|\bwach|schreck|zuck|reißt", str(sc.get("text") or "").lower()))
            who = next((str(a.get("id")) for s2 in scenes if isinstance(s2, dict) for a in (s2.get("actors") or [])
                        if isinstance(a, dict) and str(a.get("id") or "").lower() in MAIN_IDS), "du")       # der Mensch – nicht das Gehirn oder ein Tier
            sc["actors"] = acts = [{"id": who, "action": "shocked" if woke else "sleep", "emotion": "shocked" if woke else "",
                                    "emote": "!" if woke else "", "pos": "center", "speaks": False, "keep": True}]
            sc["crowd"], sc["shot"] = "", ""              # Schlafen und Aufwachen passiert im Bett – nicht auf der Straße zwischen Passanten
        lone0 = len(acts) <= 1 and all(str(a.get("action") or "talk").lower() in ("talk", "idle", "", "point", "think") for a in acts)
        if not has_bd and not spooky and maps_used < 2 and lone0 and str(sc.get("shot") or "") != "insert" and (hint is None or place not in MAPS):
            for pat, target in MAP_HINTS:                       # „in ganz Deutschland“, „weltweit“ → Kartenbild (höchstens zweimal)
                if _re0.search(pat, str(sc.get("text") or "").lower()):
                    sc["place"] = place = target
                    maps_used += 1
                    break
        if places.resolve(sc.get("place")) in MAPS and not has_bd:   # auf der Karte stehen keine Figuren und Dinge
            sc["actors"], sc["props"], sc["crowd"], sc["weather"] = [], [], "", ""
            sc["shot"] = "" if str(sc.get("shot") or "") in ("close", "insert", "event") else sc.get("shot")
            acts = []
        txt0 = str(sc.get("text") or "").lower()
        if any(_re0.search(pat, txt0) for pat, _k in _lib_props()):   # der Satz nennt das Ding selbst (Tresor, Glasscheibe): der Notbehelf des Drehbuchs
            sc["props"] = [p for p in (sc.get("props") or [])     # (Karton, Trinkglas) fliegt raus, wenn der Satz nicht auch davon spricht
                           if not (isinstance(p, dict) and extras.PROP_ALIASES.get(str(p.get("type")).lower(), str(p.get("type")).lower()) in ("box", "glass")
                                   and not any(k2 == extras.PROP_ALIASES.get(str(p.get("type")).lower(), str(p.get("type")).lower()) and _re0.search(pat, txt0) for pat, k2 in TEXT_PROPS))]
        if _re0.search(r"haferbrei|porridge|haferschleim|frühstücksbrei", txt0) and not _re0.search(r"suppe|eintopf|brühe", txt0) and "lib_haferbrei" in extras.PROPS:
            sc["props"] = [p for p in (sc.get("props") or []) if _pkey(p) != "lib_suppe"]   # die Suppenschüssel war der Notbehelf des Drehbuchs für den Haferbrei (Ausbau 27.11.2026)
        if len(sc.get("props") or []) < 2 and str(sc.get("shot") or "") != "close" and places.resolve(sc.get("place")) not in MAPS:       # was der Satz nennt, ist auch zu sehen
            have = {extras.PROP_ALIASES.get(str(q.get("type")).lower(), str(q.get("type")).lower()) for q in (sc.get("props") or [])}
            for pat, kind in _lib_props() + TEXT_PROPS:
                if kind not in have and kind not in simile and _re0.search(pat, txt0):
                    if kind == "engine" and have & {"enginehoist", "enginestand"}:
                        continue                           # der Motor hängt schon am Kran / steht auf dem Ständer
                    if str(kind).lower().replace("lib_", "") in WORN_THINGS and any(not a_.get("kind") for a_ in acts) \
                            and _re0.search(r"\b(?:dein|sein|ihr|mein|unser|eur)\w* (?:[a-zäöüß]+ )?(?:" + "|".join(WORN_THINGS) + r")\w*", txt0):
                        continue                           # „das Reiben deiner Hose“: Kleidung, die die Figur anhat, liegt nicht zusätzlich als Ding im Bild (Video 209)
                    if kind == "display" and _re0.search(BLANK_DISPLAY_RE, txt0):
                        continue                           # „auf dem Display steht rein gar nichts“: kein Großbild eines Handys, auf dem gerade ein Anruf eingeht (Video 209)
                    if kind in OUTDOOR_THINGS and places.resolve(backdrop(sc)) not in places.OUTDOOR and not (
                            places.resolve(backdrop(sc)) in GARAGES and kind in GARAGE_VEHICLES) and not (
                            kind in extras.SKY and places.resolve(backdrop(sc)) in places.WINDOWS) and not (
                            kind in ("satellite", "rocket", "ufo", "meteor") and places.resolve(backdrop(sc)) == "space"):
                        continue                           # Feuer, Autos, Naturgewalten erscheinen nicht im Zimmer (Himmelsdinge: im Fenster)
                    if kind in ("computer", "tv", "fridge", "shelf", "cart") and places.resolve(backdrop(sc)) in NO_FURNITURE:
                        continue                           # „zocken“ im Diner stellt keinen Schreibtisch ins Restaurant
                    if places.resolve(backdrop(sc)) == "bedroom" and have & set(extras.PROPS) and not (kind == "lib_sirene" and have == {"lib_wecker"}):
                        break                              # im Schlafzimmer ist neben Bett und Tisch nur Platz für ein Ding (ein „phone“ aus dem Drehbuch zählt nicht: das gibt es nur in der Hand)
                    if kind in INDOOR_THINGS and places.resolve(backdrop(sc)) in ("space", "underwater", "cave"):
                        continue                           # kein Schreibtisch im All, kein Kühlschrank am Meeresgrund
                    if kind == "submersible" and places.resolve(backdrop(sc)) != "underwater":
                        continue                           # Tauchboot und Sonar gibt es nur unter Wasser
                    if kind in INDOOR_THINGS and (places.resolve(backdrop(sc)) in places.OUTDOOR):
                        if used.get(place, 0) < 3 or sc.get("overlay") or sc.get("shot"):
                            continue                       # Zimmer-Dinge stehen nicht in der Landschaft …
                        sc["shot"] = "insert"              # … aber als Großaufnahme lockern sie einen oft gezeigten Ort auf
                        sc["props"] = []
                    sc["props"] = (sc.get("props") or []) + [{"type": kind}]
                    have.add(kind)
                    if len(sc["props"]) >= 2:
                        break
        if _re0.search(r"jede[mnrs]? |überall|millionen|tausende|hunderte|schwarm|schwärme|unzählige|der ganze himmel|am himmel wimmel", txt0):
            for q in sc.get("props") or []:              # „vor jedem Fenster“, „Millionen Drohnen“ → mehrere davon im Bild
                if extras.PROP_ALIASES.get(q["type"].lower(), q["type"].lower()) in ("drone", "plane", "ufo", "satellite", "meteor") and not q.get("count"):
                    q["count"] = 5
        for pat, item in ((r"handy|smartphone|display|bildschirm leuchtet|nachricht", "phone"), (r"taschenlampe", "flashlight"), (r"regenschirm", "umbrella"),
                          (r"landkarte|stadtplan", "map"), (r"\bradio\b|funkgerät", "radio"), (r"einkaufstüte|\btasche\b|rucksack", "bag")):
            if _re0.search(pat, txt0):                   # was die Figur laut Satz in der Hand hat
                if _re0.search(r"\b(?:lieg\w*|steh\w*|steck\w*|häng\w*|lehnt|lag|stand)\b", txt0) and _re0.search(r"\b(?:im|in|auf|unter|neben|hinter|an) ", txt0) \
                        or _re0.search(r"nachttisch|vibriert|klingelt|brummt", txt0) and item == "phone":
                    sc["props"] = [q for q in (sc.get("props") or []) if not (isinstance(q, dict) and extras.HELD.get(str(q.get("type") or "").lower().strip()) == item)]
                    break                                 # „In deinem Kühlschrank liegen … und ein kaputter Regenschirm“, „Dein Handy vibriert auf dem Nachttisch“: liegt dort, niemand hält es (Video 192: aufgespannter Schirm in der Küche)
                for a in acts:
                    if not a.get("kind") and not a.get("hold"):
                        a["hold"] = item
                        break
                break
        if _re0.search(r"(?<!ohne )(?<!kein )(?<!keinen )(?<!keine )\b(?:rucksack|rucksäcke|schulranzen|ranzen)\b", txt0) and extras.held_key("lib_rucksack"):
            for a in acts:                                # „Dein Rucksack darf höchstens …“: die Figur hält den Rucksack – nicht die Einkaufstüte mit Obst, während der Rucksack klein am Bildrand steht (Video 207)
                if not a.get("kind") and str(a.get("hold") or "").lower() in ("bag", "tasche", "rucksack", "backpack"):
                    a["hold"] = "lib_rucksack"
                    sc["props"] = [q for q in (sc.get("props") or []) if not (isinstance(q, dict) and extras.PROP_ALIASES.get(str(q.get("type") or "").lower(), str(q.get("type") or "").lower())
                                                                              in ("lib_rucksack", "rucksack", "bag"))]
                    break
        kinds_now = [extras.PROP_ALIASES.get(str(p.get("type")).lower(), str(p.get("type")).lower()) for p in (sc.get("props") or []) if isinstance(p, dict)]
        if ("ambulance" in kinds_now or "police" in kinds_now) and "car" in kinds_now and not _re0.search(r"\bautos?\b|autofahrer|\bstau", txt0):
            sc["props"] = [p for p in sc["props"] if not (isinstance(p, dict) and extras.PROP_ALIASES.get(str(p.get("type")).lower(), str(p.get("type")).lower()) == "car")]
        surprise_g = bool(_re0.search(SURPRISE_RE, txt0)) and len([a for a in acts if not a.get("kind")]) >= 2 and bool(extras.held_key("lib_geschenk"))
        if (_re0.search(GIVE_RE + "|" + TAKE_RE, txt0) or surprise_g) and str(sc.get("shot") or "") not in ("insert", "event", "graphic"):   # „teilt sein Stück Kuchen“: jemand hält es in der Hand
            things_g = [k for pat, k in _lib_props() + TEXT_PROPS if _re0.search(pat, txt0)]
            thing_g = next((str(x) for x in things_g if extras.held_key(x).startswith("prop:")), "")
            humans_g = [a for a in acts if not a.get("kind")]
            if surprise_g and not thing_g:                # „Er überrascht dich mit etwas, das du vor Wochen erwähnt hast“: er hält ein Päckchen hin, statt nur zu zeigen (Video 191)
                thing_g = "lib_geschenk"
                if not any(a.get("hold") for a in humans_g):
                    humans_g = [a for a in humans_g if str(a.get("action") or "") != "shocked"] or humans_g   # der Überraschte hält es nicht
                    humans_g = humans_g + humans_g[:1] if len(humans_g) == 1 else humans_g
            if thing_g and humans_g and not any(a.get("hold") for a in humans_g):
                giver = humans_g[-1] if len(humans_g) > 1 and _re0.search(GIVE_RE, txt0) else humans_g[0]   # geben: der andere („der Kollege“); essen/nehmen: die Hauptfigur
                giver["hold"] = thing_g
                if str(giver.get("action") or "").lower() in ("", "idle", "think", "wave", "look_around", "walk"):
                    giver["action"] = "talk"
                sc["props"] = [p for p in (sc.get("props") or []) if (p.get("type") if isinstance(p, dict) else p) != thing_g]
        # Der Satz beschreibt eine Handlung mit einem Ding (ausschütteln, ausklopfen …): eine Figur tut es – nicht bloß das Ding zeigen
        if _re0.search(r"schüttel|ausschütt|ausklopf|ausleer", txt0):
            things = [p.get("type") if isinstance(p, dict) else p for p in (sc.get("props") or [])]
            things += [k for pat, k in _lib_props() + TEXT_PROPS if _re0.search(pat, txt0)]
            thing = next((str(x) for x in things if extras.held_key(x).startswith("prop:")), "")
            if thing:
                who = next((a for a in acts if not a.get("kind")), None)
                if who is None:
                    who = {"id": last_id or "du", "pos": "center"}
                    sc["actors"] = acts = [who]
                who.update({"action": "shake", "hold": thing, "to": None})
                sc["props"] = [p for p in (sc.get("props") or []) if (p.get("type") if isinstance(p, dict) else p) != thing]
                if sc.get("shot") in ("insert", "event"):
                    sc["shot"] = ""
        if _re0.search(r"wespe|biene|insekten", txt0) and len(acts) < 2 and not any(a.get("kind") for a in acts) and "actors" in sc:
            sc["actors"] = acts = acts + [{"id": "_biene", "kind": "bee", "action": "idle", "pos": "right", "speaks": False}]
        any_now = next((k for pat, k in ANY_CREATURES if _re0.search(pat, txt0)), None)
        gfx_s = bool(str(sc.get("shot") or "") == "graphic" and graphics.clean(sc.get("graphic")))
        shot_s = str(sc.get("shot") or "")
        sea_now = _sea_kind(txt0, sea_topic or places.resolve(backdrop(sc)) == "underwater")
        other_s = bool(_re0.search(HUMAN_RE, txt0)) or any(_re0.search(pat, txt0) for pat, _k in TOPIC_CREATURES)   # der Satz handelt von Menschen/anderem
        if any_now:
            any_last, any_age, sea_last = any_now, 0, None
        elif any_last and not gfx_s:
            any_age += 1
            if other_s or sea_now or any_age > 3 or (any_last in LAND_KINDS and (any_age > 1 or not _re0.search(LAND_NEXT_RE, txt0))):
                any_last = None
            else:
                any_now = any_last                         # „Sie trocknen jahrelang aus“: der Satz handelt weiter vom selben Tier
        if not any_now and any_video and not gfx_s and not other_s and not sea_now and not any(_re0.search(pat, txt0) for pat, _k, _pl in NAMED_ANIMALS):
            any_now = any_video                            # Ein-Tier-Video („Es rollt sich ein …“, „Dieser Winzling …“): jeder Satz ohne Menschen zeigt das Tier – auch viele Sätze nach seinem Namen
        if any_now and not gfx_s and places.resolve(sc.get("place")) not in MAPS:
            sc["actors"] = acts = [{"id": "_tier", "kind": any_now, "hero": True, "action": "idle", "speaks": False, "pos": "center", "emote": "", "say": "",
                                    "hold": "", "facing": "right", "emotion": MOOD_EMOTION.get(str(sc.get("mood") or ""), "")}]
            sc["crowd"] = ""
            sc["props"] = [q for q in (sc.get("props") or []) if extras.PROP_ALIASES.get(str(q.get("type")).lower(), str(q.get("type")).lower()) in extras.SKY][:1]
            if shot_s in ("event", "insert", "close"):
                sc["shot"] = shot_s = ""
            if any_now == "cheetah" and _re0.search(r"\bjag|\brenn|sprint|\bläuf|\blauf|geschwindigkeit|km/h|kilometer\w* pro stunde|stundenkilometer|\bschnell", txt0):
                acts[0].update(action="run", emotion="")   # der Gepard jagt im Galopp ins Bild – entschlossen, nicht besorgt
            elif any_now == "flea" and _re0.search(r"spring|sprung|sprüng|hüpf", txt0):
                acts[0]["action"] = "jump"                 # der Floh springt
            if any_now in LAND_KINDS and not said and places.resolve(backdrop(sc)) == "underwater":
                sc["place"], sc["backdrop"] = "fields", None
            sc["_sea"] = True
            sc["_keep"] = dict(acts[0])
        # Meerestiere: Nennt der Satz Pistolenkrebs, Fangschreckenkrebs, Qualle oder Axolotl, ist das Tier die Figur der Szene – groß, unter Wasser,
        # mit seiner Bewegung (Schere knallt, Keule schlägt, Schirm pulsiert). Folgesätze („Sie verwandelt …“, „Sein Schlag …“) bleiben bei ihm.
        sea_carry = None
        if sea_now is None and not gfx_s and _re0.search(SEA_NEXT_RE, txt0):
            nxt_s = scenes[i + 1] if i + 1 < len(scenes) and isinstance(scenes[i + 1], dict) else None
            sea_tease = _sea_kind(str(nxt_s.get("text") or "").lower(), True) if nxt_s else None      # „Kraft Nummer drei“: schon das nächste Tier zeigen
            if sea_tease:
                sea_last, sea_age = sea_tease, 0
        elif sea_now:
            sea_last, sea_age, any_last = sea_now, 0, None
        elif sea_last and not gfx_s:
            sea_age += 1
            if not under0 and (other_s or sea_age > 3 or any_now):
                sea_last = None                            # der Satz handelt wieder von Menschen: zurück ins Zimmer
            elif not under0 and not any_now:
                sea_carry = sea_last                       # Folgesatz über dasselbe Tier, vom Drehbuch ins Labor/Zimmer gelegt: bleibt beim Tier
        if (sea_now or sea_carry) and not gfx_s and not any_now:
            if not has_bd and places.resolve(backdrop(sc)) != "underwater" and not (said and places.resolve(said) != "underwater") \
                    and not _re0.search(r"aquarium|\bbecken\b|\bzoo\b|teller|restaurant|\bküche", txt0):
                sc["place"], sc["backdrop"] = "underwater", None          # das Tier lebt im Meer – nicht im Wohnzimmer
                place = "underwater"
                sc["crowd"], sc["weather"], sc["time"] = "", "", "day"
                sc["props"] = [q for q in (sc.get("props") or []) if extras.PROP_ALIASES.get(str(q.get("type")).lower(), str(q.get("type")).lower()) not in INDOOR_THINGS]
                sc["actors"] = acts = []
                if shot_s == "close":
                    sc["shot"] = shot_s = ""
        if under0 and (sea_now or sea_last) and places.resolve(backdrop(sc)) != "underwater":
            sc["place"], sc["backdrop"] = "underwater", None      # das Tier schlägt unter Wasser zu – „zertrümmert“ macht daraus keine Ruinenstadt
            place = "underwater"
        # Tier-Video, das Drehbuch stellt bei einem Satz über Menschen („ein menschlicher Wimpernschlag“, „Menschen haben drei Farbrezeptoren“,
        # „Forscher halten ihn …“) einen Menschen unter Wasser: Der Satz spielt mit dem Menschen an Land – das Tier wäre zum x-ten Mal dasselbe Bild.
        hum_s = [a for a in acts if not a.get("kind") and not _re0.search(SEA_ID_RE, str(a.get("id") or "").lower())]
        if under0 and not hum_s and not sea_now and not any_now and not gfx_s and not sc.get("_deep") and _SEA_DEF[0] and shot_s != "insert" \
                and _re0.search(SEA_PEOPLE_RE, txt0) and not _re0.search(DIVER_TEXT_RE, txt0):
            hum_s = [{"id": "du", "action": "talk", "speaks": False, "emotion": "", "emote": "", "say": "", "hold": "", "kind": ""}]
            sc["actors"] = acts = hum_s                    # „Menschen haben drei Farbrezeptoren“: ein Mensch im Bild, nicht zum x-ten Mal der Krebs
        if under0 and not sea_now and not any_now and not gfx_s and not sc.get("_deep") and (sea_last or _SEA_DEF[0]) and hum_s and len(hum_s) == len(acts) \
                and _re0.search(SEA_HUMAN_RE, txt0) and not _re0.search(DIVER_TEXT_RE, txt0) and shot_s != "insert":
            lab_s = bool(_re0.search(r"forsch|wissenschaft|labor|\bbecken|aquari|zoo", txt0))
            sc["place"], sc["backdrop"] = ("lab" if lab_s else "livingroom"), None
            place = sc["place"]
            sc["crowd"], sc["weather"], sc["time"] = "", "", "day"
            who_s = hum_s[0]
            who_s.update(pos="center", hold="")
            who_s.pop("to", None)
            if str(who_s.get("action") or "") in ("walk", "run", "sit", "sleep", "fall", "float", "jump"):
                who_s["action"] = "talk"
            sc["actors"] = acts = [who_s]
            sc["props"] = [{"type": "tank", "pos": 760}] if _re0.search(TANK_RE, txt0) else []
            if sc["props"]:
                who_s.update(pos=300, facing="right", action="point", emotion="")
                sc["shot"] = shot_s = ""
            else:
                sc["shot"] = shot_s = "close"            # Großaufnahme: das Gesicht (Auge, Wimpernschlag) ist das Bild
            sc["_land"] = True
        elif not under0 and _SEA_DEF[0] in ("mantis", "shrimp") and not sea_now and not gfx_s and hum_s and len(hum_s) == len(acts) and _re0.search(TANK_RE, txt0) \
                and places.resolve(backdrop(sc)) not in places.OUTDOOR and shot_s != "insert":
            who_s = hum_s[0]                              # „Forscher halten ihn in Plastikbecken“: Das Becken mit dem Krebs steht im Labor neben der Figur
            who_s.update(pos=300, facing="right", action="point", emotion="", hold="")
            who_s.pop("to", None)
            sc["actors"] = acts = [who_s]
            sc["props"] = [{"type": "tank", "pos": 760}]
            sc["crowd"] = ""
            sc["shot"] = shot_s = ""
            sc["_land"] = True
        if any(extras.PROP_ALIASES.get(str(q.get("type")).lower(), str(q.get("type")).lower()) == "aquarium" for q in (sc.get("props") or [])):
            sc["props"] = [q for q in sc["props"] if extras.PROP_ALIASES.get(str(q.get("type")).lower(), str(q.get("type")).lower()) != "glass"]   # Aquarium statt Trinkglas
        if places.resolve(backdrop(sc)) == "underwater":          # unter Wasser schwimmen Meerestiere, keine Menschen
            sea_k = None if any_now else sea_now or (sea_last if not _re0.search(r"\bfisch|\bhai", txt0) else None)
            div_s = [a for a in acts if _re0.search(DIVER_ID_RE, str(a.get("id") or "").lower()) or str(a.get("kind") or "").lower() == "diver"]
            if div_s and not sea_now and _re0.search(DIVER_TEXT_RE, txt0):
                for a in div_s:                           # „Taucher nennen ihn Daumenspalter“: Die Figur „taucher“ bleibt ein Taucher und wird nicht zum Krebs
                    a["kind"] = "diver"
                sc["actors"] = acts = div_s[:1]
                sea_k = None
            for a in acts:
                aid_s = str(a.get("id") or "").lower()
                own_s = _sea_named(aid_s.replace("_", " ")) or (None if sea_last else _sea_kind(aid_s.replace("_", " "), True))   # die Kennung nennt das Tier („qualle“, „fangschrecke“): das gilt vor dem Folgesatz-Tier; ein bloßes „krebs“ meint das Tier von eben
                own_s = "mantis" if _re0.search(r"fangschreck|mantis", aid_s) else "jelly" if "jelly" in aid_s else "axolotl" if "lurch" in aid_s else own_s
                if own_s and not sea_now:
                    a["kind"] = sea_k = sea_last = own_s
                    sea_age = 0
                elif sea_k and (not a.get("kind") or _re0.search(r"krebs|garnele|qualle|shrimp|jelly|axolotl|lurch", aid_s) or str(a.get("kind")).lower() in ("monster", "fish")):
                    a["kind"] = sea_k
                elif not a.get("kind"):
                    a["kind"] = "fish"
            if sea_k and shot_s in ("", "event", "insert", "close", "wide"):      # auch statt der Großaufnahme eines Dings: das Tier trifft es
                mine_s = [a for a in acts if str(a.get("kind") or "").lower() == sea_k]
                if not mine_s:
                    mine_s = [{"id": "_meer", "kind": sea_k, "action": "idle", "speaks": False, "emote": "", "say": "", "hold": "", "facing": "",
                               "emotion": "angry" if _re0.search(SEA_HIT_RE, txt0) else MOOD_EMOTION.get(str(sc.get("mood") or ""), "")}]
                has_thing = bool(sc.get("props"))
                for a in mine_s[:1]:
                    a.update(hero=True, pos=400 if has_thing else "center", facing="right")
                    a.pop("to", None)
                    if str(a.get("action") or "") in ("walk", "run", "jump", "sit", "sleep", "fall"):
                        a["action"] = "idle"
                sc["actors"] = acts = mine_s[:1]
                sc["_sea"] = True
                sc["_keep"] = dict(mine_s[0])
                for q in (sc.get("props") or [])[:1]:               # das Ding, auf das es zielt, steht vor ihm
                    if isinstance(q, dict) and not q.get("pos"):
                        q["pos"] = 860
                sc["shot"] = "" if shot_s in ("event", "insert", "close") else sc.get("shot")
                sc["crowd"] = ""
        if not has_bd and places.resolve(backdrop(sc)) == "livingroom" and str(sc.get("shot") or "") != "graphic" \
                and (_re0.search(r"nachttisch|schlafzimmer|\bim bett\b|\bins bett\b|bettdecke|kopfkissen", (str(sc.get("text") or "") + " " + str(sc.get("see") or "")).lower())
                     or (len(acts) == 1 and str(acts[0].get("action") or "").lower() == "sleep" and not _re0.search(r"sofa|couch|sessel", (str(sc.get("text") or "") + " " + str(sc.get("see") or "")).lower()))):
            sc["place"] = place = "bedroom"               # „Dein Handy vibriert auf dem Nachttisch“, Ort „Zimmer“: das ist das Schlafzimmer, nicht das Wohnzimmer (Video 192)
            sc["backdrop"] = None
        for a in acts:                                    # geschlafen wird im Bett oder auf dem Sofa, nicht auf der Straße
            if str(a.get("action") or "").lower() == "sleep" and places.resolve(backdrop(sc)) not in ("bedroom", "livingroom", "hospital", "camp", "attic"):
                if len(acts) == 1 and not has_bd and (place in GENERIC or places.resolve(backdrop(sc)) in places.OUTDOOR):
                    sc["place"] = place = "bedroom"
                    sc["backdrop"] = None
                    sc["crowd"], sc["props"] = "", []
                else:
                    a["action"] = "sit"
        if places.resolve(backdrop(sc)) in ("space", "underwater", "cave"):
            sc["props"] = [q for q in (sc.get("props") or []) if extras.PROP_ALIASES.get(str(q.get("type")).lower(), str(q.get("type")).lower()) not in INDOOR_THINGS]
        # „Drei Gründer“, „zwei Freunde“: so viele Menschen stehen auch im Bild – nicht einer allein
        mg = _re0.search(GROUP_RE, txt0)
        humans = [a for a in acts if not a.get("kind")]
        dead_gfx = str(sc.get("shot") or "") == "graphic" and not graphics.clean(sc.get("graphic"))   # Grafik-Szene ohne Grafik
        if mg and ("actors" in sc or "who" in sc or not acts) and len(humans) <= 1 and len(acts) <= 1 and places.resolve(sc.get("place")) not in MAPS \
                and places.resolve(backdrop(sc)) not in ("underwater",) and (str(sc.get("shot") or "") in ("", "event") or dead_gfx) \
                and str((sc.get("overlay") or {}).get("type") or "") not in TALL_OV:
            n = max(2, min(3, int(_number(mg.group(1)) or 3)))
            first = humans[0] if humans else {"id": last_id or "du", "action": "talk", "speaks": True, "emotion": MOOD_EMOTION.get(str(sc.get("mood") or ""), "")}
            first.pop("to", None)
            if str(first.get("action") or "") in ("walk", "run", "sit", "sleep", ""):
                first["action"] = "talk"
            xs = (300, 760) if n == 2 else (210, 540, 870)
            first["pos"] = xs[n // 2] if n == 3 else xs[0]
            team = [first]
            for k in range(n - 1):
                team.append({"id": f"_team{k + 1}", "action": ("point", "think")[k % 2] if first.get("action") != "point" else ("talk", "think")[k % 2],
                             "emotion": first.get("emotion") or "", "emote": "", "speaks": False, "look": GROUP_LOOKS[(i + k) % len(GROUP_LOOKS)],
                             "pos": [x for x in xs if x != first["pos"]][k], "facing": "", "kind": "", "hold": "", "say": ""})
            sc["actors"] = acts = team
            sc["crowd"] = ""
            if dead_gfx:
                sc["shot"] = ""
            if sc.get("shot") == "event":
                sc["shot"] = ""
        home = {"shelf": "supermarket", "cart": "supermarket", "fridge": "kitchen", "tv": "livingroom", "computer": "office"}
        for q in (sc.get("props") or []):
            k = str(q.get("type") if isinstance(q, dict) else q).lower().strip()
            k = extras.PROP_ALIASES.get(k, k)
            if k in home and not has_bd and places.resolve(sc.get("place")) in ("headquarters", "gasstation", "powerplant", "church", "graveyard", "farm", "camp"):
                sc["props"] = [q2 for q2 in sc["props"] if q2 is not q]   # der Ort ist bewusst gewählt: das Zimmer-Ding entfällt, der Ort bleibt
                break
            if k in home and (places.resolve(backdrop(sc)) in places.OUTDOOR or place == "plain"):
                sc["place"] = place = home[k]            # Regal, Kühlschrank, Fernseher stehen nicht auf der Straße
                sc.pop("backdrop", None)
                has_bd = False
                break
        celestial = any(extras.PROP_ALIASES.get(str(q.get("type") if isinstance(q, dict) else q).lower(), str(q.get("type") if isinstance(q, dict) else q).lower())
                        in extras.SKY for q in (sc.get("props") or []))
        if celestial and not has_bd and places.resolve(sc.get("place")) == "street":
            sc["backdrop"] = {"ground": "road", "elements": ["city"]}      # Skyline mit freiem Himmel statt Häuserwand
        if has_bd or isinstance(sc.get("backdrop"), dict):
            place = "custom:" + ",".join(str(e) for e in (sc["backdrop"].get("elements") or [sc["backdrop"].get("ground")]))
        if place == "plain":      # unbekannter Ort im Drehbuch → beim letzten Ort bleiben (draußen: Park), nie ein leerer Raum
            if prev_bd is not None:
                sc["backdrop"] = prev_bd
                place = prev_place
            else:
                place = prev_place if (prev_place and not str(prev_place).startswith("custom")) else ("bedroom" if spooky else "park")
                sc["place"] = place
        prev_bd = sc.get("backdrop") if isinstance(sc.get("backdrop"), dict) else None
        import re as _re
        txt = _re.sub(r"\b(keine|ohne|kein grund zur|statt) (panik|angst|sorge|gefahr)\b", " ", str(sc.get("text") or "").lower())   # „Keine Panik“ ist keine Panik
        m_hint, c_hint = _mood_hint(txt)
        mood = str(sc.get("mood") or "").lower()
        crowd_in = CROWD_KINDS.get(str(sc.get("crowd") or "").lower(), "")
        # Stimmung muss zum Satz passen: Panik nur, wenn der Text wirklich von Panik/Flucht redet – sonst Sorge statt Rennen
        if (mood == "panic" or crowd_in == "panic") and not _re.search(PANIC_RE, txt):
            sc["_unpanic"] = mood == "panic"              # Panik im Drehbuch, die der Satz nicht hergibt: erzählte Videos nehmen unten auch den Schreck aus dem Gesicht
            mood = m_hint if m_hint and m_hint != "panic" else ("tense" if mood == "panic" else mood)
            crowd_in = "worried" if crowd_in == "panic" else crowd_in
        if _re.search(CALM_RE, txt) and not m_hint:
            mood = "" if mood in ("panic", "tense", "scary") else mood
            crowd_in = "" if crowd_in in ("panic", "worried") else crowd_in
        if m_hint and mood in ("", "calm"):
            mood = m_hint
        sc["mood"], sc["crowd"] = mood, crowd_in
        rp = places.resolve(backdrop(sc))
        outdoor = rp in places.OUTDOOR
        public = rp in PUBLIC_INDOOR
        if outdoor and not sc.get("weather") and rp not in MAPS:
            for pat, wth in WEATHER_HINTS:                # Orkan, Erdbeben, kochendes Meer: das Wetter zeigt, wovon der Satz spricht
                if _re.search(pat, txt):
                    sc["weather"] = wth
                    break
        if not sc.get("crowd") and c_hint and (outdoor or public) and not (c_hint == "walk" and mood in ("scary", "sad")):
            sc["crowd"] = c_hint
        if sc.get("crowd") and not (outdoor or public):
            sc["crowd"] = ""
        if mood == "panic" and (outdoor or public) and not sc.get("crowd"):
            sc["crowd"] = "panic"
        if sc.get("crowd") == "walk" and mood in ("tense", "panic"):
            sc["crowd"] = "worried" if mood == "tense" else "panic"
        for a in acts:                                    # Gefühle der Figuren passen zur Stimmung der Szene
            emo = str(a.get("emotion") or "").lower()
            if emo not in EMOTION_OK.get(mood, EMOTION_OK[""]):
                a["emotion"] = MOOD_EMOTION.get(mood, "")
                if str(a.get("emote") or "") in ("!", "sweat", "anger") and mood in ("", "calm", "happy"):
                    a["emote"] = ""
            if str(a.get("action") or "").lower() in ("shocked", "fall") and mood in ("", "calm", "happy") and not _re.search(r"plötzlich|schock|erschr|auf einmal|unglaublich|krass|wow", txt):
                a["action"] = "talk" if a.get("speaks") else "idle"
            if str(a.get("action") or "").lower() in ("dance", "jump") and mood in ("panic", "tense", "scary", "sad"):
                a["action"] = "look_around"
        if len(acts) == 1 and not acts[0].get("kind") and _re.search(LYING_RE, txt) and not _re.search(r"\bbett|sofa|couch|strand|wiese|liege\b|schläf|schlaf", txt):
            acts[0]["action"] = "fall"                    # „… und du liegst platt auf dem Boden“: die Figur liegt – sie steht nicht lächelnd in Großaufnahme da
            sc["shot"] = "" if sc.get("shot") == "close" else sc.get("shot")
        import re as _re
        txt = str(sc.get("text") or "").lower()
        if _re.search(r"stromausfall|\bstrom\b.{0,40}\b(aus|weg|zusammen)\b|ohne strom|kein strom|blackout|lichter gehen aus|stockdunkel|finsternis|dunkelheit", txt):
            sc["time"] = "night"                      # ohne Strom / Dunkelheit → Nacht
            sc["dark_city"] = True
            sc["mood"] = sc.get("mood") or "scary"
            power_out = True
        elif power_out and not _re.search(r"strom (ist|kommt) (wieder|zurück)|wieder strom|lichter gehen (wieder )?an", txt):
            sc["dark_city"] = True                    # der Strom bleibt weg: kein Verkehr, keine rauchenden Schlote
        else:
            power_out = False
        if _re.search(r"\bstill\b|stillstand|steht still|stehen still|bleiben stehen|bleibt stehen|kein benzin|verkehr bricht|lahmgelegt|menschenleer|\bniemand\b|keine menschenseele", txt):
            sc["no_traffic"] = True
            if sc.get("crowd") == "walk":
                sc["crowd"] = ""
        acts_now = [a for a in (sc.get("actors") or []) if isinstance(a, dict)]
        # Erzählt das Drehbuch alles mit einer redenden Figur in der Mitte, zeigt jede zweite passende Szene stattdessen das Geschehen
        if (len(acts_now) == 1 and str(acts_now[0].get("action") or "talk").lower() in ("talk", "idle", "") and outdoor
                and (sc.get("crowd") or sc.get("props") or isinstance(sc.get("backdrop"), dict)) and i % 2 == 1
                and not sc.get("shot") and not _re.search(r"\bdu\b|\bdich\b|\bdir\b", txt) and str(style or "") != "motivation"):   # „Du stehst auf dem Gipfel“ zeigte nur einen Felsbrocken (Video 174)
            sc["actors"] = []
            sc["shot"] = "event"
            acts_now = []
        if outdoor and not acts_now and not sc.get("props") and not sc.get("crowd") and not sc.get("weather") \
                and str(sc.get("mood") or "") != "scary":
            sc["crowd"] = {"panic": "panic", "tense": "worried", "sad": "sad"}.get(str(sc.get("mood") or ""), "walk")   # nie ein Bild, in dem gar nichts passiert
        has_ov = isinstance(sc.get("overlay"), dict) and sc["overlay"].get("type")
        if acts:
            last_id = acts[0].get("id") or last_id
        if not outdoor and "actors" in sc and not acts_now and str(sc.get("shot") or "") != "insert":
            solo = bool(last_id) and not sc.get("crowd") and (str(style or "") == "motivation" or bool(_re.search(SELF_RE, txt))) \
                and not _re.search(r"\balle\b|\bleute|menschen|\bmenge\b|publikum|kolleg|\bteam\b|zuschauer", txt)
            prev_p = scenes[i - 1] if i and isinstance(scenes[i - 1], dict) else {}
            same_fig = rp == "classroom" and bool(last_id) and not sc.get("crowd") and bool(prev_p) and places.resolve(backdrop(prev_p)) == rp and prev_p.get("shot") != "graphic" \
                and any(isinstance(a_, dict) and a_.get("id") == last_id for a_ in prev_p.get("actors") or []) \
                and not _re.search(r"\balle\b|\bleute|menschen|\bmenge\b|publikum|kolleg|\bteam\b|zuschauer|schüler|\bklasse\b|kinder|studenten|gäste|patienten|kunden", txt)
            if public and same_fig and not solo:          # eben stand der Lehrer an der Tafel, der nächste Satz nennt niemanden: er bleibt – keine fremden Leute, die durchs Klassenzimmer laufen (Video 197)
                sc["actors"] = acts = [{"id": last_id, "action": ("point", "think")[i % 2], "pos": (330, 750)[i % 2], "emotion": MOOD_EMOTION.get(mood, ""), "stay": True}]
            elif public and not sc.get("crowd") and not solo:   # leerer öffentlicher Raum: Menschen passend zur Stimmung
                sc["crowd"] = {"panic": "panic", "tense": "worried", "sad": "sad", "happy": "cheer"}.get(mood, "walk")
            elif public and solo:                         # „Fang genau jetzt an.“ spricht zu dir: die Hauptfigur steht da – keine drei jubelnden Fremden im Konfetti (Video 173)
                sc["actors"] = acts = [{"id": last_id, "action": "cheer" if mood == "happy" else "talk", "pos": "center",
                                        "emotion": MOOD_EMOTION.get(mood, "") or ("happy" if mood == "happy" else "")}]
            elif not public and last_id and rp not in ("space", "underwater", "cave"):
                sc["actors"] = acts = [{"id": last_id, "action": "walk", "pos": "offleft", "to": "center",
                                        "emotion": MOOD_EMOTION.get(mood, "")}]
        # Gegenstand groß zeigen statt dritter Rede-Szene im selben Zimmer
        things = [q for q in (sc.get("props") or []) if extras.prop_fit(q.get("type") if isinstance(q, dict) else q)]
        if ((not outdoor or used.get(place, 0) >= 3) and rp not in MAPS and things and not has_ov and not sc.get("shot") and (outdoor or not sc.get("crowd")) and len(acts) <= 1
                and all(str(a.get("action") or "talk").lower() in ("talk", "idle", "") for a in acts)
                and not (i and str(scenes[i - 1].get("shot") or "") == "insert")):
            sc["shot"] = "insert"
        lone = len(acts) == 1 and str(acts[0].get("action") or "talk").lower() in ("talk", "idle", "") and not acts[0].get("to") and not acts[0].get("keep")
        if place != prev_place:
            same = 0
            changes += 1
            if i > 0 and lone and changes % 2 == 0 and (e0 - s0) > 2.6:     # bei jedem zweiten Ortswechsel hereinkommen
                acts[0].update(action="walk", pos="offleft" if changes % 4 else "offright", to=acts[0].get("pos") or "center")
        else:
            same += 1
            if lone:
                if not acts[0].get("pos"):
                    acts[0]["pos"] = ("center", "left", "right", "center")[same % 4]
                if same % 4 == 3 and not has_ov and not sc.get("shot"):
                    sc["shot"] = "close"
                elif same % 3 == 1 and str(acts[0].get("action") or "") in ("", "idle"):
                    acts[0]["action"] = "look_around"
        if lone and acts and not acts[0].get("to") and not has_ov and not sc.get("shot") and not things and i < len(scenes) - 1 \
                and str(acts[0].get("emotion") or "").lower() in STRONG_FEELINGS and not (i and str(scenes[i - 1].get("shot") or "") == "close"):
            sc["shot"] = "close"                      # starkes Gefühl: Großaufnahme des Gesichts (wie in den Vorbild-Shorts)
        # --- Großaufnahme nur von Dingen, die etwas erzählen: kein leerer Tisch, nichts unter hohen Einblendungen
        if sc.get("shot") == "insert":
            ov_t0 = str((sc.get("overlay") or {}).get("type") or "")
            keep = [q for q in (sc.get("props") or []) if extras.PROP_ALIASES.get(q["type"].lower(), q["type"].lower()) not in DULL]
            if not keep or ov_t0 in TALL_OV or ov_t0 == "choice":
                sc["shot"] = ""
                if not [a for a in (sc.get("actors") or []) if isinstance(a, dict)] and last_id and places.resolve(backdrop(sc)) not in MAPS:
                    sc["actors"] = [{"id": last_id, "action": "talk", "speaks": True}]
            else:
                sc["props"] = keep
        # --- mindestens jede zweite Szene zeigt das Geschehen statt der redenden Figur
        acts = [a for a in (sc.get("actors") or []) if isinstance(a, dict)]
        ov_t = str((sc.get("overlay") or {}).get("type") or "")
        lone = len(acts) == 1 and str(acts[0].get("action") or "talk").lower() in ("talk", "idle", "", "look_around") and not acts[0].get("to") and not acts[0].get("kind")
        last = i == len(scenes) - 1
        rp2 = places.resolve(backdrop(sc))
        window_scene = rp2 in places.WINDOWS and any(extras.PROP_ALIASES.get(q["type"].lower(), q["type"].lower()) in extras.SKY for q in (sc.get("props") or []))
        cur_hud = sc.get("hud") if isinstance(sc.get("hud"), str) and sc.get("hud").strip() else cur_hud
        if neon:
            sc["look"], sc["time"] = "neon", "night"
        elif noir:
            sc["look"] = "noir"
        g_auto = None
        low_c = str(sc.get("text") or "").lower()
        g_t = (sc.get("graphic") or {}).get("type") if sc.get("shot") == "graphic" and isinstance(sc.get("graphic"), dict) else None
        if g_t and g_t != "chart" and i and isinstance(scenes[i - 1], dict) and scenes[i - 1].get("shot") == "graphic" \
                and isinstance(scenes[i - 1].get("graphic"), dict) and scenes[i - 1]["graphic"].get("type") == g_t:
            sc["shot"], sc["graphic"] = "", None            # nie zweimal dieselbe Grafik-Art hintereinander (zwei Zahlen-Tafeln = zehn Sekunden Standbild)
        if g_t == "number" and isinstance(sc.get("graphic"), dict):
            m_v = _re0.match(r"^\s*(\d[\d.,]*)\s+(\S+\s+\S+.*)$", str(sc["graphic"].get("value") or ""))
            if m_v and not any(w.lower() in _UNITS or w.lower() in _SCALE for w in m_v.group(2).split()):
                sc["graphic"]["value"] = m_v.group(1)       # „3 PRO KETTE“ als große Zahl: nur die Zahl bleibt, der Rest war erfunden
        if sc.get("shot") == "graphic" and (sc.get("graphic") or {}).get("type") == "chart":
            if charts >= 2 or (i and scenes[i - 1].get("shot") == "graphic" and (scenes[i - 1].get("graphic") or {}).get("type") == "chart"):
                sc["shot"], sc["graphic"] = "", None        # höchstens zwei Kurven, nie zwei hintereinander
            else:
                charts += 1
                sc["actors"], sc["props"], sc["crowd"], sc["weather"] = [], [], "", ""
                acts, lone = [], False
                sc["graphic"]["dark"] = bool(_re0.search(CHART_DOWN_RE, low_c))   # „Die Börsenkurse stürzen ab“ mit steigender grüner Kurve (Video 156): die Richtung bestimmt der Satz
                kick_c = str(sc["graphic"].get("kicker") or "").strip().lower()
                if kick_c and not all(w[:5] in low_c for w in _re0.findall(r"[a-zäöüß0-9]{3,}", kick_c)):
                    sc["graphic"]["kicker"] = next((k for pat, k in CHART_KICKERS if _re0.search(pat, low_c)), "KURS")   # „DAX“, wenn niemand vom DAX spricht
                lab_c = str(sc["graphic"].get("label") or "").strip().lower()
                if lab_c and not any(w[:5] in low_c for w in _re0.findall(r"[a-zäöüß]{3,}", lab_c)):
                    sc["graphic"]["label"] = ""
        elif _re0.search(CHART_RE, low_c) and sc.get("shot") != "graphic" and charts < 2 and i > 0 and not last and ov_t not in TALL_OV and ov_t != "choice" \
                and not sc.get("float") and not (scenes[i - 1].get("shot") == "graphic" and (scenes[i - 1].get("graphic") or {}).get("type") == "chart"):
            fig_c = find_figure(sc.get("text"))             # nur Zahlen, die der Sprecher auch sagt
            g_c = {"type": "chart", "dark": bool(_re0.search(CHART_DOWN_RE, low_c)),
                   "kicker": next((k for pat, k in CHART_KICKERS if _re0.search(pat, low_c)), "KURS")}
            if fig_c:
                parts_c = str(fig_c["unit"]).split()
                sc_c = parts_c[0] if parts_c and parts_c[0] in _SCALE.values() else ""
                g_c["value"] = (_fmt_num(float(fig_c["value"])) + (" " + sc_c if sc_c else "")).strip()
                g_c["label"] = " ".join(parts_c[1:] if sc_c else parts_c)
            sc["shot"], sc["graphic"] = "graphic", graphics.clean(g_c)
            sc["actors"], sc["props"], sc["crowd"], sc["overlay"], sc["weather"] = [], [], "", None, ""
            acts, lone = [], False
            charts += 1
        if not size_done and sc.get("shot") != "graphic":   # winziges Tier mit Größenangabe: Zoom heraus bis zum Lineal statt Tier so groß wie ein Bär
            mm_s = graphics.size_mm(str(sc.get("text") or ""))
            kinds_s = [str(a.get("kind") or "").lower() for a in (sc.get("actors") or []) if isinstance(a, dict)
                       and str(a.get("kind") or "").lower() in extras.CREATURES and str(a.get("kind") or "").lower() not in ("ghost", "robot", "agent", "monster", "alien", "fridge", "diver")]
            if mm_s and kinds_s:
                g_s = graphics.clean({"type": "size", "value": graphics.fmt_size(mm_s), "kind": kinds_s[0], "kicker": "ECHTE GRÖSSE"})
                if g_s:
                    sc["shot"], sc["graphic"] = "graphic", g_s
                    sc["actors"], sc["props"], sc["crowd"], sc["overlay"], sc["weather"] = [], [], "", None, ""
                    acts, lone, size_done = [], False, True
        if sc.get("shot") == "graphic":
            gfx += 1
        elif (lone or not acts) and (fig_prev or neon or (i and scenes[i - 1].get("shot") == "graphic")) and sc.get("shot") in ("", "close", "event") \
                and ov_t in ("", "card", "counter", "bar") and not last and i > 0 and gfx < (6 if neon else 4) and not window_scene and rp2 not in MAPS \
                and not sc.get("_deep"):                  # Blackbox, Wrack, Tauchboot am Meeresgrund: das Ding zeigen, keine Zahlen-Tafel
            ov0 = sc.get("overlay") or {}                 # Zahl aus der Einblendung („72 STUNDEN“) oder aus dem Satz
            ov_txt = " ".join(str(ov0.get(k) or "") for k in ("text", "value", "unit", "label")) if ov_t in ("card", "counter") else ""
            g_auto = graphics.clean(auto_graphic((ov_txt + ". " if ov_txt.strip() else "") + str(sc.get("text") or ""), cur_hud)) if ov_t != "bar" else None
            if g_auto is None and ov_t:
                pass                                      # Einblendung bleibt, wie sie ist
            prev_g = scenes[i - 1].get("graphic") if scenes[i - 1].get("shot") == "graphic" else None
            if g_auto and prev_g and (prev_g.get("type") == g_auto["type"] or (i > 1 and scenes[i - 2].get("shot") == "graphic")):
                g_auto = None                            # nie dieselbe Grafik-Art zweimal hintereinander, nie drei Grafiken am Stück
        if g_auto:                                       # Zahl, Frist oder Warum-Frage als bewegte Grafik statt redender Figur
            sc["shot"], sc["graphic"], gfx = "graphic", g_auto, gfx + 1
            sc["overlay"] = None
        elif lone and fig_prev and not window_scene and not sc.get("shot") and not last and ov_t not in TALL_OV and ov_t != "choice" and rp2 not in MAPS:
            things = [q for q in (sc.get("props") or []) if extras.prop_fit(q.get("type"))
                      and extras.PROP_ALIASES.get(q["type"].lower(), q["type"].lower()) not in DULL]
            if things and inserts < 4:
                sc["shot"], inserts = "insert", inserts + 1
            elif rp2 in places.OUTDOOR:
                sc["actors"], sc["shot"] = [], "event"
                if not sc.get("crowd") and not sc.get("props") and not sc.get("weather"):
                    sc["crowd"] = {"panic": "panic", "tense": "worried", "sad": "sad", "happy": "cheer", "scary": ""}.get(str(sc.get("mood") or ""), "walk")
            elif rp2 in PUBLIC_INDOOR and not any(isinstance(a_, dict) and a_.get("stay") for a_ in sc.get("actors") or []):   # der Lehrer, der an der Tafel bleibt, wird nicht gegen Fremde getauscht
                sc["actors"] = []
                sc["crowd"] = sc.get("crowd") or {"panic": "panic", "tense": "worried", "sad": "sad", "happy": "cheer"}.get(str(sc.get("mood") or ""), "walk")
            elif spooky and not (i and scenes[i - 1].get("shot") == "close"):
                sc["shot"] = "close"                    # Grusel: Nahaufnahme des erschrockenen Gesichts statt Totale
            elif not has_ov0(sc):                       # Wohnraum ohne eigenen Gegenstand: reihum Abwechslung
                stale += 1
                step = stale % 4
                prev_close = bool(i and scenes[i - 1].get("shot") == "close")
                if step == 1 and topic_any and topic_ins < 2:                 # das Ding, um das sich das Video dreht, groß im Bild
                    sc["props"] = [{"type": topic_any[topic_ins % len(topic_any)]}]
                    sc["shot"], topic_ins = "insert", topic_ins + 1
                elif step == 2 and str(style or "").lower() not in STORY_STYLES and not _re0.search(r"\b(?:du|dich|dir|dein\w*|ich|mich|mir|mein\w*)\b|" + BODY_BRAIN_RE + "|" + BODY_PARTS_RE, str(sc.get("text") or "").lower()):   # Blick nach draußen: Straße, Menschen, das Thema am Himmel – nicht, wenn der Satz von „dir“, deinem Körper oder dem Gehirn spricht („Dann ziehst du den Kopf ein“ zeigte Passanten)
                    sc["place"], sc["backdrop"] = "street", None
                    sc["actors"], sc["shot"] = [], "event"
                    sc["props"] = [{"type": k} for k in topic_any[:1]]
                    sc["crowd"] = {"panic": "panic", "tense": "worried", "sad": "sad", "happy": "cheer", "scary": ""}.get(str(sc.get("mood") or ""), "walk")
                    place = "street"
                elif step in (1, 3) and not prev_close:
                    sc["shot"] = "close"
                elif not acts[0].get("keep"):
                    acts[0].update(action="walk", pos="offright" if stale % 8 < 4 else "offleft", to="center")
        outdoor2 = rp2 in places.OUTDOOR
        topic_out = [k for k in topic_any if (k not in INDOOR_THINGS if outdoor2 else (k not in extras.SKY and extras.prop_fit(k)))]
        named = [k for pat, k in _lib_props() + TEXT_PROPS if k in topic_out and _re0.search(pat, str(sc.get("text") or "").lower())]
        if topic_out and not sc.get("props") and sc.get("shot") not in ("close", "graphic", "insert") and rp2 not in MAPS and not last \
                and (named or i % 2 == 0):
            sc["props"] = [{"type": (named or topic_out)[0]}]        # das Thema bleibt im Bild (die Drohne über der Straße, die Spinne im Zimmer)
        fig_prev = bool([a for a in (sc.get("actors") or []) if isinstance(a, dict)]) and sc.get("shot") not in ("insert", "graphic")
        # --- beeindruckende Zahl im Satz → Zähler, wenn das Drehbuch keine Einblendung vorsieht
        hand_p = [str(q.get("type") if isinstance(q, dict) else q).lower() for q in (sc.get("props") or [])]
        if last_id and not [a for a in (sc.get("actors") or []) if isinstance(a, dict)] and not sc.get("crowd") and hand_p and sc.get("shot") not in ("graphic", "insert") \
                and places.resolve(backdrop(sc)) not in MAPS + ("space", "underwater", "moon", "highsky") and all(extras.held_key(k_) for k_ in hand_p) \
                and _re0.search(r"\b(?:du|dich|dir|dein\w*|man|wir|ich)\b", str(sc.get("text") or "").lower()):
            # „Ohne Mini-Karte musst du auf Papier schauen“ mit Landkarte als einzigem Ding und ohne Figur: dreieinhalb Sekunden leerer Wald, die Karte war nicht zu sehen
            # (Video 207). Ein Ding, das man in die Hand nimmt, und ein Satz über „du“: die Hauptfigur hält es und sieht darauf
            sc["actors"] = [{"id": last_id, "action": "think", "pos": "center", "hold": hand_p[0], "emotion": MOOD_EMOTION.get(str(sc.get("mood") or ""), "")}]
            sc["shot"] = "" if sc.get("shot") == "event" else sc.get("shot")
        if not [a for a in (sc.get("actors") or []) if isinstance(a, dict)] and not sc.get("crowd") and not sc.get("props") and not sc.get("weather") \
                and sc.get("shot") not in ("graphic", "insert") and places.resolve(backdrop(sc)) not in MAPS:
            if last_id:                                   # nie ein leeres Bild: die Figur kommt herein und sieht sich um
                sc["actors"] = [{"id": last_id, "action": "walk", "pos": "offleft", "to": "center", "emotion": MOOD_EMOTION.get(str(sc.get("mood") or ""), "")}]
                sc["shot"] = ""
            elif not spooky:
                sc["crowd"] = "walk"
        if sc.get("shot") == "graphic":
            sc["overlay"] = None if str((sc.get("overlay") or {}).get("type") or "") in ("counter", "bar", "card", "tag") else sc.get("overlay")
        elif not sc.get("overlay") and counters < 3 and not last:
            fig = find_figure(sc.get("text"))
            if fig:
                sc["overlay"] = fig
                counters += 1
        prev_place = place
    giant = bool(_re0.search(GIANT_RE, str(topic or "").lower()))
    main_id = next((a.get("id") for sc in scenes if isinstance(sc, dict) for a in (sc.get("actors") or [])
                    if isinstance(a, dict) and a.get("id") and not a.get("kind")), None) or "du"
    pats = _lib_props() + TEXT_PROPS
    filled = 0
    zero_topic = bool(_re0.search(ZERO_G_TOPIC, str(topic or "").lower()))
    zero_g, float_seen, floats = False, False, 0
    inserts_seen = set()
    for i, sc in enumerate(scenes):
        if not isinstance(sc, dict):
            continue
        if giant:
            sc["giant"] = True
        if sc.get("crowd") == "walk" and (str(sc.get("mood") or "") in ("tense", "panic") or _re0.search(DISASTER_RE, str(sc.get("text") or "").lower())):
            sc["crowd"] = "worried"                       # niemand schlendert gemütlich durch eine Katastrophe
        # --- Schwerelosigkeit: was der Satz schweben lässt, schwebt auch im Bild (Figur, Dinge, Autos) – und kracht wieder herunter
        txt_f = str(sc.get("text") or "").lower()
        rp_f = places.resolve(backdrop(sc))
        acts_f = [a for a in (sc.get("actors") or []) if isinstance(a, dict)]
        fl, kept = "", False
        if rp_f not in MAPS and rp_f not in ("space", "underwater") and sc.get("shot") != "graphic":
            m_fl = _re0.search(FLOAT_RE, txt_f)
            if m_fl and m_fl.group(0) in ("durch die luft", "in der luft") and _re0.search(NOT_BODIES_RE, txt_f) \
                    and not _re0.search(FLOAT_RE, txt_f.replace("durch die luft", " ").replace("in der luft", " ")):
                m_fl = None                               # Laser, Licht, Rauch, Schall „durch die Luft“: da schwebt kein Mensch und kein Möbel
            if m_fl and _re0.search(HUD_AIR_RE, txt_f) and not _re0.search(r"schwerelos|schwerkraft|hebs?t .{0,40}\bab\b", txt_f):
                m_fl = None                               # „Symbole schweben in der Luft“: Einblendungen wie im Spiel – Figur und Autos bleiben am Boden (Prüfung 27.11.2026, Video 231)
            floats_now = bool(m_fl)
            if _re0.search(DROP_RE, _re0.sub(SOFT_CRASH_RE, " ", txt_f)) and (_re0.search(GRAVITY_BACK_RE, txt_f) or (float_seen and not floats_now)):
                fl = "drop"                               # „… während Möbel schwerelos durcheinanderfliegen“ ist noch kein Absturz
            elif floats_now or ((zero_topic or zero_g) and any(str(a.get("action") or "") in ("float", "schweben") for a in acts_f)):
                fl = "float"
            elif zero_g and i < len(scenes) - 1:
                fl, kept = "float", True                  # die Schwerkraft ist noch weg: wer im Bild ist, schwebt weiter
        if not fl:                                        # das Drehbuch lässt die Figur schweben, der Satz handelt aber gar nicht davon: sie bleibt am Boden
            for a_f in acts_f:
                if str(a_f.get("action") or "") in ("float", "schweben"):
                    a_f["action"] = "shocked" if str(a_f.get("emotion") or "") in ("scared", "shocked") else "talk"
        seen_before = float_seen
        if fl == "drop":
            zero_g = False
        elif fl == "float" and not kept:
            float_seen, zero_g = True, zero_topic
        if fl:
            sc["float"] = fl
            sc["aloft"] = fl == "drop" or kept or (zero_topic and seen_before) or bool(i and isinstance(scenes[i - 1], dict) and scenes[i - 1].get("float") == "float")
            sc["crowd"], sc["no_traffic"] = "", True
            if sc.get("shot") in ("insert", "close"):
                sc["shot"] = ""
            if sc.get("weather") in ("rain", "snow"):
                sc["weather"] = ""
            for a in acts_f:
                a["action"] = "float"
                a.pop("to", None)
                if str(a.get("pos") or "") in ("offleft", "offright"):
                    a["pos"] = "center"
                a["emotion"] = "scared" if fl == "drop" else (a.get("emotion") or "shocked")
                a["emote"] = a.get("emote") if a.get("emote") in ("!", "?", "sweat") else "!"
            if not kept:
                outdoor_f = rp_f in places.OUTDOOR
                road_f = extras.has_road(places.spec_of(backdrop(sc)))
                tall = str((sc.get("overlay") or {}).get("type") or "") in TALL_OV if isinstance(sc.get("overlay"), dict) else False
                have = [p for p in (sc.get("props") or []) if isinstance(p, dict) and extras.prop_fit(p.get("type"))]
                rest = [p for p in (sc.get("props") or []) if isinstance(p, dict) and p not in have]
                named = [k for pat, k in pats if extras.prop_fit(k) and k not in (sc.get("_simile") or []) and _re0.search(pat, txt_f)]
                pool = [k for k in FLOAT_THINGS if k in extras.PROPS]
                pool = (["car", "car", "car"] if road_f else []) if outdoor_f else ((pool[i % len(pool):] + pool[:i % len(pool)]) if pool else [])
                if not acts_f and not (outdoor_f and road_f):
                    acts_f = [{"id": main_id, "action": "float", "emotion": "scared" if fl == "drop" else "shocked", "emote": "!", "speaks": False}]
                room = (2 if outdoor_f and not acts_f else 1) if tall else (2 if acts_f else 3)
                if outdoor_f:                             # ein schwebender Bus füllt das ganze Bild: neben Autos weglassen, allein nur einer
                    cars = [p for p in have if str(p.get("type")).lower() == "car"]
                    have = cars + [p for p in have if p not in cars and str(p.get("type")).lower() not in ("bus", "truck")] if (cars or tall) else have[:1]
                    named = [k for k in named if k not in ("bus", "truck")] if (cars or tall or "car" in named) else named
                    if have and str(have[0].get("type")).lower() in ("bus", "truck"):
                        room = 1
                for k in named + pool:
                    if len(have) >= room:
                        break
                    if (k in ("car", "bus", "truck") and not outdoor_f) or (k != "car" and any(str(p.get("type")).lower() == k for p in have)):
                        continue
                    have.append({"type": k})
                have = have[:room]
                flip = floats % 2 == 1                    # von Szene zu Szene die Seiten tauschen, damit nicht viermal dasselbe Bild kommt
                if len(acts_f) == 1 and have:             # Figur an der Seite, die treibenden Dinge daneben – nichts verdeckt sich
                    acts_f[0]["pos"] = (910 if flip else 170) if tall else (840 if flip else 240)
                    xs = ((150,) if flip else (930,)) if tall else ((500, 250) if flip else (650, 930))
                elif acts_f:
                    xs = (540, 120, 960)
                else:
                    xs = (270, 810, 540) if len(have) > 1 else (540,)
                for n, p in enumerate(have):
                    p["pos"] = xs[n % len(xs)]
                sc["actors"] = acts_f
                sc["low"] = bool(tall and outdoor_f) or bool(have and str(have[0].get("type")).lower() in ("bus", "truck"))
                sc["props"] = have + [p for p in rest if not extras.prop_fit(p.get("type"))][:max(0, 3 - len(have))][:2]   # Welle, Riss, Wolke bleiben im Bild
                floats += 1
                continue
        if sc.get("crowd") and not crowd_ok(sc):          # Feld, Wald, Keller: dort läuft niemand herum
            sc["crowd"] = ""
        if fl and not acts_f and sc.get("shot") != "insert" and not [
                p for p in (sc.get("props") or []) if isinstance(p, dict) and extras.PROP_ALIASES.get(str(p.get("type")).lower(), str(p.get("type")).lower())
                not in PLACE_HAS.get(rp_f, ())]:
            sc["actors"] = [{"id": main_id, "action": "float", "emotion": "scared", "emote": "!", "pos": "center", "speaks": False}]   # die Schwerkraft ist weg: kein leeres Bild
            if sc.get("shot") == "event":
                sc["shot"] = ""
            continue
        txt = str(sc.get("text") or "").lower()
        rp = places.resolve(backdrop(sc))
        if rp in MAPS and sc.get("shot") != "graphic":
            continue
        keys = [extras.PROP_ALIASES.get(str(p.get("type") if isinstance(p, dict) else p).lower(), str(p.get("type") if isinstance(p, dict) else p).lower())
                for p in (sc.get("props") or [])]
        if sc.get("shot") == "insert" and keys and not sc.get("_sea"):           # Großaufnahme nur von Dingen, von denen der Satz (oder das Thema) wirklich handelt
            in_txt = [k for k in keys if k in txt or any(k2 == k and _re0.search(pat, txt) for pat, k2 in pats)]
            in_topic = [k for k in keys if any(k2 == k and _re0.search(pat, str(topic or "").lower()) for pat, k2 in pats)]
            good = in_txt or [k for k in keys[:1] if k in in_topic]
            if good and tuple(good[:2]) not in inserts_seen:
                inserts_seen.add(tuple(good[:2]))
                if good != keys:                          # das genannte Ding nach vorn (Grafikkarte statt Schreibtisch)
                    sc["props"] = [p for k in good for p in (sc.get("props") or []) if isinstance(p, dict)
                                   and extras.PROP_ALIASES.get(str(p.get("type")).lower(), str(p.get("type")).lower()) == k][:2]
                    keys = good[:2]
            else:                                         # nichts Genanntes oder dieselbe Großaufnahme gab es schon: normale Szene mit Figur
                sc["shot"] = ""
                sc["props"] = [p for p in (sc.get("props") or []) if isinstance(p, dict)
                               and extras.PROP_ALIASES.get(str(p.get("type")).lower(), str(p.get("type")).lower()) in good]
                keys = [k for k in keys if k in good]
                if not [a for a in (sc.get("actors") or []) if isinstance(a, dict)] and rp not in ("space", "underwater", "cave"):
                    sc["actors"] = [{"id": main_id, "action": "point" if keys else "talk", "emotion": MOOD_EMOTION.get(str(sc.get("mood") or ""), ""),
                                     "pos": "left" if keys else "center", "speaks": True}]
        ov_t = str((sc.get("overlay") or {}).get("type") or "") if isinstance(sc.get("overlay"), dict) else ""
        if isinstance(sc.get("graphic"), dict) and ov_t in ("checklist", "phone", "note", "choice"):
            sc.pop("graphic", None)                       # Liste und Grafik zugleich überdecken sich: die Liste bleibt, die Grafik geht
            sc["shot"] = ""
        if sc.get("shot") == "graphic":
            continue
        people = [a for a in (sc.get("actors") or []) if isinstance(a, dict) and (giant or str(a.get("kind") or "").lower() not in CREATURE_SIZE)]
        acts = people if sc.get("shot") != "insert" else [a for a in (sc.get("actors") or []) if isinstance(a, dict)]
        small = [a for a in (sc.get("actors") or []) if isinstance(a, dict) and a not in people]
        big = [k for k in keys if (k in extras.SKY or (extras.SIZES.get(k) or (9, 0))[0] >= 0.6) and k not in PLACE_HAS.get(rp, ())]   # was der Ort schon hat, füllt kein Bild
        if sc.get("shot") != "insert" and not acts and not sc.get("crowd") and not big and not sc.get("weather"):
            # leerer Raum, leere Wiese: Die Hauptfigur erlebt, wovon der Satz spricht – nie ein Bild, in dem niemand ist und nichts passiert
            mood = str(sc.get("mood") or "")
            action, emotion = {"scary": ("shocked", "scared"), "panic": ("run", "scared"), "tense": ("look_around", "worried"), "sad": ("sad", "sad"),
                               "happy": ("wave", "happy")}.get(mood, ("look_around" if filled % 2 == 0 else "think", ""))
            if _re0.search(r"albtr|erschr|schreck|\bangst", txt):
                action, emotion = "shocked", "scared"
            elif _re0.search(r"aufpassen|vorsicht|abstand|ausweich", txt):
                action, emotion = "look_around", "worried"
            elif _re0.search(r"\bweh\b|schmerz|\bbiss\b|stich|verletz", txt):
                action, emotion = "sad", "sad"
            sc["actors"] = [{"id": main_id, "action": action, "emotion": emotion, "pos": "left" if (keys or small) else "center",
                             "emote": {"shocked": "!", "look_around": "?"}.get(action, "")}] + [dict(a, pos="right") for a in small[:1]]
            if sc.get("shot") == "event":
                sc["shot"] = ""
            filled += 1
    _time_weather(scenes, topic, style)
    _carry_thing(scenes, main_id)
    _opening(scenes)
    _auto_explain(scenes)
    _topic_creature(scenes, topic)
    for i in range(1, len(scenes)):                  # nie zweimal dieselbe Großaufnahme hintereinander
        if isinstance(scenes[i], dict) and isinstance(scenes[i - 1], dict) and scenes[i].get("shot") == "close" == scenes[i - 1].get("shot"):
            scenes[i]["shot"] = ""
    _auto_tags(scenes)
    for sc in scenes:                                     # Zustands-Zeile oben rechts mit einer Zahl, die niemand sagt („FALL: 15 M/S“): erfunden, entfällt
        if isinstance(sc, dict) and isinstance(sc.get("status"), str) and unspoken_figures({"text": sc["status"]}, str(sc.get("text") or "")):
            sc["status"] = ""
    for sc in scenes:                                     # Ecken-Zeile mit einer Jahreszahl, die der Satz nicht nennt („1977 · START INS ALL“ über dem Fehler von 2023): entfällt
        if isinstance(sc, dict) and isinstance(sc.get("hud"), str):
            yrs_h = _re0.findall(r"\b(?:1[5-9]\d\d|20\d\d)\b", sc["hud"])
            if yrs_h:
                from ..writer import year_words
                low_h = str(sc.get("text") or "").lower().replace("-", "").replace(" ", "")
                if not any(y_h in low_h or year_words(int(y_h)).replace(" ", "") in low_h for y_h in yrs_h):
                    sc["hud"] = ""
    _balloon_story(scenes, topic)
    _probe_story(scenes, topic, main_id)
    _family(scenes, main_id)
    for sc in scenes:                                     # Nähmaschine: steht frei zwischen den Figuren, nicht dahinter; der Stoffberg gehört schon dazu
        if isinstance(sc, dict) and sc.get("shot") not in ("graphic", "insert"):
            ks_n = [extras.PROP_ALIASES.get(str(q.get("type")).lower(), str(q.get("type")).lower()) for q in (sc.get("props") or []) if isinstance(q, dict)]
            if "sewing" in ks_n:
                sc["props"] = [dict(q, pos=600) for q in sc["props"] if isinstance(q, dict) and extras.PROP_ALIASES.get(str(q.get("type")).lower(), str(q.get("type")).lower()) == "sewing"]
                hs_n = [a for a in (sc.get("actors") or []) if isinstance(a, dict) and not a.get("kind")]
                if 1 <= len(hs_n) <= 2 and not any(a.get("to") for a in hs_n):
                    hs_n[0].update(pos=330, facing="right", action="talk" if str(hs_n[0].get("action") or "") in ("sit", "sleep", "fall", "float", "walk", "run") else hs_n[0].get("action") or "idle")
                    for a in hs_n[1:]:
                        a.update(pos=960, facing="left")
                sc["props"] = [dict(q, pos=650) for q in sc["props"]]
                sc["_no_cut"] = True                       # kein harter Schnitt auf die Maschine allein vor leerem Grund: die Figur näht
                if sc.get("shot") in ("close", "event"):
                    sc["shot"] = ""
    if str(style or "").lower() != "motivation":           # Motivationsrede: das erste Bild zeigt den ersten Satz – „Du bist nicht faul, du wartest …“ lief als fröhlicher Dauerlauf im Park (Video 217)
        _cold_open(scenes)
    for sc in scenes:                                     # Tier als Figur der Szene: bleibt allein im Bild – spätere Regeln (Ereignis-Bild ohne
        if isinstance(sc, dict) and sc.get("_sea") and isinstance(sc.get("_keep"), dict):   # Figur, Hauptfigur dazustellen) gelten hier nicht
            kept = [a for a in (sc.get("actors") or []) if isinstance(a, dict) and a.get("kind") == sc["_keep"].get("kind")][:1] or [dict(sc["_keep"])]
            kept[0].update(hero=True)
            if kept[0].get("kind") in LAND_KINDS:          # Galopp und Sprung gehören zum Tier und bleiben
                kept[0].update(action=sc["_keep"].get("action") or "idle", pos=sc["_keep"].get("pos") or "center")
                kept[0].pop("to", None)
            elif str(kept[0].get("action") or "") in ("walk", "run", "sit", "sleep", "fall", "jump"):
                kept[0].update(action="idle", pos=sc["_keep"].get("pos") or "center")
                kept[0].pop("to", None)
            sc["actors"], sc["crowd"] = kept, ""
            if sc.get("shot") in ("event", "insert", "close"):
                sc["shot"] = ""
    sea_run = (None, 0)
    sea_prev = sea_thing = None
    for sc in scenes:                                     # Meerestier-Szenen: Das Tier bleibt allein im Bild – kein Mensch auf dem Meeresgrund,
        if not isinstance(sc, dict) or places.resolve(backdrop(sc)) != "underwater":      # keine Feuer-Explosion und keine Flutwelle unter Wasser
            continue
        acts_s = [a for a in (sc.get("actors") or []) if isinstance(a, dict)]
        seas = [a for a in acts_s if str(a.get("kind") or "").lower() in SEA_KINDS]
        low_s = str(sc.get("text") or "").lower()
        _key_s = lambda q: extras.PROP_ALIASES.get(str(q.get("type")).lower(), str(q.get("type")).lower())      # noqa: E731
        sc["props"] = [q for q in (sc.get("props") or []) if isinstance(q, dict) and (_key_s(q) not in extras.SKY or _key_s(q) in extras.WATER_KINDS)]   # unter Wasser fliegt kein Flugzeug, scheint keine Sonne
        if sc.get("_deep") and not seas and sc.get("shot") not in ("graphic", "insert"):                           # Tiefsee-Technik: Blackbox, Wrack, Tauchboot mit Sonar
            for pat_s, k_s in ((DEEP_WRECK_RE, "lib_wrack"), (DEEP_BOX_RE, "lib_blackbox"), (SUB_RE, "submersible")):
                if _re0.search(pat_s, low_s) and k_s in extras.PROPS and k_s not in [_key_s(q) for q in sc["props"]]:
                    sc["props"].append({"type": k_s})
            keys_s = [_key_s(q) for q in sc["props"]]
            if "lib_wrack" in keys_s and "submersible" not in keys_s:
                sc["props"].append({"type": "submersible"})          # das Wrack liegt im Dunkeln: ein Tauchboot leuchtet es an
            keys_s = [_key_s(q) for q in sc["props"]]
            box_x = 660 if "submersible" in keys_s else 540
            lay_s = {"submersible": 270, "lib_wrack": 750, "lib_blackbox": box_x}
            if any(k in lay_s for k in keys_s):                      # nur die Technik, fest verteilt: Boot links oben, Wrack/Blackbox rechts am Grund
                sc["props"] = [dict({k: v for k, v in q.items() if k != "count"}, pos=lay_s[_key_s(q)]) for q in sc["props"] if _key_s(q) in lay_s][:2]
                if "lib_blackbox" in keys_s and "lib_wrack" not in keys_s and _re0.search(DEEP_PING_RE, low_s):
                    sc["props"].append({"type": "ping", "pos": box_x})   # der Sender der Blackbox: Ringe breiten sich im Wasser aus
                sc["actors"] = acts_s = []                           # kein Goldfisch und kein Mensch neben dem Flugschreiber in viertausend Metern Tiefe
            sc["crowd"] = ""
            if sc.get("shot") in ("event", "close"):
                sc["shot"] = ""                                      # das Lichtkegel-Bild steht für sich, ohne Vergrößerung über den Bildrand hinaus
        if not seas and sea_prev and sc.get("shot") in ("", None, "close", "event", "wide") and len(acts_s) <= 1 \
                and all(str(a.get("kind") or "fish").lower() == "fish" for a in acts_s) and not _re0.search(r"fisch|\bhai|beute|opfer", low_s):
            keep_s = acts_s[0] if acts_s else {"id": "_meer", "action": "idle", "speaks": False, "say": "", "hold": "", "facing": ""}
            keep_s.update(kind=sea_prev, hold="", pos="center")       # namenloser Fisch in einem Satz über das Tier von eben: das Tier selbst zeigen
            sc["actors"] = seas = [keep_s]
        if not seas:
            for a in acts_s:                              # spätere Regeln stellen gern die Hauptfigur dazu: am Meeresgrund steht kein Mensch im Pulli
                if not a.get("kind"):
                    a.update(kind="fish", hold="", emote="")
                    if str(a.get("action") or "") in ("walk", "run", "sit", "sleep", "fall", "point", "wave", "think"):
                        a["action"] = "idle"
            continue
        seas[0].update(hero=True, emote="")
        sea_prev = seas[0]["kind"]
        sc["actors"] = seas[:1]
        if str(sc.get("weather") or "") == "steam":
            sc["weather"] = ""                            # „lässt das Wasser kochen“: unter Wasser steigt kein Küchendampf auf – die Blase zeigt es
        if seas[0]["kind"] in ("mantis", "shrimp") and sc.get("shot") not in ("graphic", "insert"):
            keys_t = [_key_s(q) for q in (sc.get("props") or []) if isinstance(q, dict)]
            if not any(k in SEA_TARGETS for k in keys_t):   # der Satz nennt, was vor der Keule passiert: Dampfblase, Sprungfeder, Beute
                add_t = next((k for pat, k in ((CAVI_RE, "cavitation"), (r"sprungfeder|spiralfeder|\bfeder\b|gespannte\w* feder", "lib_sprungfeder"))
                              if _re0.search(pat, low_s) and k in extras.PROPS), None)
                if add_t:
                    flip_t = sea_thing == add_t           # zweimal hintereinander dasselbe Ding: das Bild steht gespiegelt
                    sc["props"] = [{"type": add_t, "pos": (330 if flip_t else 670) if add_t == "cavitation" else (220 if flip_t else 860)}]
                    seas[0].update(pos=(700 if flip_t else 380) if add_t == "cavitation" else (680 if flip_t else 400), facing="left" if flip_t else "right")
                    seas[0].pop("to", None)
                    if str(seas[0].get("action") or "") in ("walk", "run"):
                        seas[0]["action"] = "idle"
                    if str((sc.get("overlay") or {}).get("type") or "") in TALL_OV:
                        sc["overlay"] = None              # Notizzettel/Liste schöbe das Tier an den Rand, weg von dem Ding – das Bild zeigt es selbst
                    sea_thing = None if flip_t else add_t
                    sc["_near"] = add_t != "cavitation"
                else:
                    sea_thing = None
            else:
                sea_thing = None
        else:
            sea_thing = None
        sc["props"] = [q for q in (sc.get("props") or []) if isinstance(q, dict) and extras.PROP_ALIASES.get(       # nur, worauf das Tier zielt (Stein, Scheibe) –
            str(q.get("type")).lower(), str(q.get("type")).lower()) in SEA_TARGETS][:1]                                # keine Explosion, Flutwelle, gelernten Notbehelfe
        tg_s = [q for q in (sc.get("props") or []) if isinstance(q, dict) and _key_s(q) in SEA_TARGETS]
        if tg_s and sc.get("shot") not in ("graphic", "insert"):          # das Tier und sein Ziel stehen sich gegenüber, beide ganz im Bild
            if str((sc.get("overlay") or {}).get("type") or "") in TALL_OV:
                sc["overlay"] = None                      # Notizzettel/Liste schöbe das Tier an den Rand, weg von dem Ding – das Bild zeigt es selbst
            if not isinstance(seas[0].get("pos"), (int, float)):
                seas[0].update(pos=400, facing="right")
                tg_s[0]["pos"] = 860
            seas[0].pop("to", None)
            if str(seas[0].get("action") or "") in ("walk", "run"):
                seas[0]["action"] = "idle"
            if _key_s(tg_s[0]) == "lib_sprungfeder":
                sc["_near"] = True
        same_s = sea_run[1] + 1 if sea_run[0] == seas[0]["kind"] else 0
        sea_run = (seas[0]["kind"], same_s)
        if not sc["props"]:                               # mehrere Sätze über dasselbe Tier: jedes Mal anders im Bild (Mitte, links, rechts mit Blick zurück)
            seas[0]["pos"] = ("center", 400, 680)[same_s % 3]
            seas[0]["facing"] = "left" if same_s % 3 == 2 else "right"
        if sc.get("shot") in ("event", "insert", "close"):
            sc["shot"] = ""
    for sc in scenes:                                     # Meeresoberfläche: Niemand steht im Pulli auf dem Wasser, kein Karton auf den Wellen –
        if not isinstance(sc, dict):                      # es treibt, was der Satz nennt (Trümmer), sonst fährt ein Schiff
            continue
        _key_w = lambda q: extras.PROP_ALIASES.get(str(q.get("type")).lower(), str(q.get("type")).lower())      # noqa: E731
        shot_w = str(sc.get("shot") or "")
        gfx_w = shot_w == "graphic" and graphics.clean(sc.get("graphic"))
        bd_w = backdrop(sc)
        if isinstance(bd_w, dict) and str(bd_w.get("ground") or "").lower() in ("water", "wasser") and not gfx_w:
            low_w = str(sc.get("text") or "").lower()
            if shot_w == "insert":
                sc["shot"] = shot_w = "event"              # Schiff und Flugzeug fahren auf dem Meer – nicht als Einzelteile vor braunem Grund
            sc["actors"] = [a for a in (sc.get("actors") or []) if isinstance(a, dict) and a.get("kind")]
            sc["crowd"] = ""
            if shot_w == "close":
                sc["shot"] = shot_w = ""
            props_w = [q for q in (sc.get("props") or []) if isinstance(q, dict) and (_key_w(q) in extras.SKY or _key_w(q) in SEA_TOP)]
            if _re0.search(DEBRIS_RE, low_w) and "debris" not in [_key_w(q) for q in props_w]:
                props_w = [q for q in props_w if _key_w(q) != "ship"][:1]
                props_w.insert(0, {"type": "debris", "pos": 540})
            elif not props_w and not sc["actors"]:
                props_w.append({"type": "ship"})
            if not _re0.search(r"riesenwelle|monsterwelle|flutwelle|tsunami|meterhohe? wellen?|welle (?:bricht|rollt|türmt)", low_w):
                props_w = [q for q in props_w if _key_w(q) != "wave"] or props_w      # die Flutwelle verschluckt sonst das Suchschiff
            if _re0.search(r"flugzeug|flieger|suchflüge", low_w) and "plane" not in [_key_w(q) for q in props_w] and "debris" not in [_key_w(q) for q in props_w] and len(props_w) < 2:
                props_w.append({"type": "plane"})         # „Schiffe und Flugzeuge suchen“: beides ist zu sehen
            props_w = [dict(q, pos=560) if _key_w(q) == "ship" and not q.get("pos") and shot_w != "event" else q for q in props_w]   # das Schiff fährt mittig, nicht halb aus dem Bild
            sc["props"] = props_w
        if places.resolve(bd_w) == "underwater" and not gfx_w and shot_w != "insert":
            sc["props"] = [dict(q, pos=270) if isinstance(q, dict) and _key_w(q) == "submersible" and not q.get("pos") else q for q in (sc.get("props") or [])]   # Tauchboot links, Lichtkegel nach rechts – ganz im Bild
        keys_w = [_key_w(q) for q in (sc.get("props") or []) if isinstance(q, dict)]
        rp_w = places.resolve(bd_w)
        if rp_w == "space" and "satellite" in keys_w and len(keys_w) <= 2 and all(k in ("satellite", "earth") for k in keys_w) and not sc.get("actors") \
                and shot_w in ("", "event", "wide"):          # der Satellit kreist um die Erde – nicht über einer Mondlandschaft; beide ganz im Bild,
            sc["props"] = [{"type": "satellite", "pos": 730}, {"type": "earth", "pos": 370}]
            keys_w = ["satellite", "earth"]
            sc["shot"] = shot_w = ""                       # ohne Ereignis-Vergrößerung: sonst ragt die Erde aus dem Bild
        sky_w = [k for k in keys_w if k in extras.SKY and k not in ("submersible", "ping")]
        sc["_ov_low"] = 3 if (rp_w == "underwater" and keys_w == ["submersible"] and not sc.get("actors")) or (rp_w == "highsky" and sc.get("_balloon")) or sc.get("_balloon") in ("fill", "fly") or sc.get("_probe") else 0   # 3 = ganz oben, über dem Tauchboot
        if sky_w and not sc.get("_probe") and all(k in sky_w or k == "ship" for k in keys_w) and not sc.get("actors") and not sc.get("crowd") \
                and shot_w in ("", "event", "wide") and (rp_w in places.OUTDOOR or rp_w == "space"):
            sc["_ov_low"] = 2 if "ship" in keys_w else 1  # nur Flugzeug/Satellit am Himmel (und ein Schiff darunter): das Schild steht tiefer im freien Bild, nicht quer über dem Flugzeug
    _divers(scenes)
    _lake_story(scenes, topic, next((str(a.get("id")) for sc in scenes if isinstance(sc, dict) for a in (sc.get("actors") or [])
                                     if isinstance(a, dict) and not a.get("kind") and not str(a.get("id") or "").startswith("_")), "du"))
    for sc in scenes:                                     # Menschen-Satz im Tier-Video: bleibt die Großaufnahme des Gesichts – die Figur läuft nicht durchs Zimmer
        if isinstance(sc, dict) and sc.get("_land") and sc.get("shot") == "close":
            for a in [a for a in (sc.get("actors") or []) if isinstance(a, dict)][:1]:
                a.pop("to", None)
                a.update(pos="center", emote="")
                if str(a.get("action") or "") in ("walk", "run", "sit", "sleep", "fall", "float", "jump", "idle", ""):
                    a["action"] = "shocked" if _re0.search(r"schneller|unglaublich|unfassbar|\bkaum\b", str(sc.get("text") or "").lower()) else "talk"
            sc["actors"] = [a for a in (sc.get("actors") or []) if isinstance(a, dict)][:1]
            sc["props"], sc["crowd"] = [], ""
        g_n = sc.get("graphic") if isinstance(sc, dict) and isinstance(sc.get("graphic"), dict) else None
        if g_n and str(g_n.get("label") or "").strip().lower() and str(g_n.get("label") or "").strip().lower() == str(g_n.get("value") or "").strip().lower():
            g_n["label"] = ""                             # Unterzeile wiederholt nur die Zahl („80 KM/H“ unter „80 KM/H“)
    _map_sense(scenes)
    _ice_story(scenes, topic)
    _named_animals(scenes, topic)
    _tiny_story(scenes)
    _household(scenes)
    _feast_story(scenes, topic)
    _relatives(scenes)
    _funeral_story(scenes, topic)
    _studio_story(scenes, topic)
    _unpaid(scenes)
    _score_labels(scenes)
    _music(scenes, topic)
    _fur_ancestor(scenes)
    _fur_story(scenes)
    _indoor_sense(scenes)
    _pair_sense(scenes, style)
    _sleep_story(scenes, topic)
    _body_story(scenes)
    _game_story(scenes, topic, next((str(a.get("id")) for sc in scenes if isinstance(sc, dict) for a in (sc.get("actors") or [])
                                     if isinstance(a, dict) and a.get("id") and not a.get("kind")), "du"))
    for i_n in range(1, len(scenes)):                     # eben stand das Ding schon groß allein im Bild: der nächste Satz schneidet nicht noch einmal darauf (neun Sekunden derselbe Lautsprecher)
        sc_n, pv_n = scenes[i_n], scenes[i_n - 1]
        if isinstance(sc_n, dict) and isinstance(pv_n, dict) and str(pv_n.get("shot") or "") == "insert":
            keys_n = {str(q.get("type") if isinstance(q, dict) else q) for q in pv_n.get("props") or []}
            if keys_n & {str(q.get("type") if isinstance(q, dict) else q) for q in sc_n.get("props") or []}:
                sc_n["_no_insert"] = True
    for sc in scenes:                                     # Kälte-Wetter (Eiskristalle, Atemwolke) gibt es nur draußen – wechselt die Regie den Ort nachträglich ins Zimmer, entfällt es (Prüfung 17.11.2026)
        if isinstance(sc, dict) and str(sc.get("weather") or "") == "cold" and not isinstance(backdrop(sc), dict) and places.resolve(backdrop(sc)) in INDOOR:
            sc["weather"] = ""
            for a in sc.get("actors") or []:
                if isinstance(a, dict) and a.get("action") == "shiver" and not re.search(COLD_RE + "|" + SHIVER_RE, str(sc.get("text") or "").lower()):
                    a["action"] = "idle"
    _hybrid_story(scenes, topic, next((str(a.get("id")) for sc in scenes if isinstance(sc, dict) for a in (sc.get("actors") or [])
                                       if isinstance(a, dict) and a.get("id") and not a.get("kind") and not str(a.get("id")).startswith("_")), "du"))
    _cooks(scenes)
    _cute_animals(scenes, next((str(a.get("id")) for sc in scenes if isinstance(sc, dict) for a in (sc.get("actors") or [])
                                if isinstance(a, dict) and a.get("id") and not a.get("kind") and not str(a.get("id")).startswith("_")), "du"))
    for sc in scenes:                                     # von der Regie eingesetzte Figur („_tier“, „_meer“) ohne Art: wäre ein fremder Mensch im Bild (ein Junge neben dem Eisberg in der Küche, Video 152)
        if isinstance(sc, dict) and sc.get("actors"):
            sc["actors"] = [a for a in sc["actors"] if not (isinstance(a, dict) and str(a.get("id") or "") in ("_tier", "_meer") and not a.get("kind"))]   # andere „_…“-Figuren (Gründer, Soldaten, Familie) sind Menschen und bleiben
        g_k = sc.get("graphic") if isinstance(sc, dict) and isinstance(sc.get("graphic"), dict) else None
        if g_k and str(g_k.get("label") or "").strip().upper() == "KM" and re.search(r"kilometer\w* pro stunde|km/h|stundenkilometer", str(sc.get("text") or "").lower()):
            g_k["label"] = "KM/H"                         # „93 Kilometer pro Stunde“ stand als „93 KM“ im Bild (Video 152)
        o_k = sc.get("overlay") if isinstance(sc, dict) and isinstance(sc.get("overlay"), dict) else None
        if o_k and str(o_k.get("type") or "") == "counter" and str(o_k.get("unit") or "").strip().upper() == "KM" \
                and re.search(r"kilometer\w* pro stunde|km/h|stundenkilometer", str(sc.get("text") or "").lower()):
            o_k["unit"] = "KM/H"
    _devices(scenes)
    _last_look(scenes, topic)
    _map_hud(scenes)
    _door_story(scenes)
    _jogging(scenes)
    _speech(scenes, style)
    _call_story(scenes, topic, main_id)
    _past_story(scenes, topic, main_id)
    for sc in scenes:                                     # Zähler mit einer Jahreszahl („ERSTER SATELLIT 1.957“ zählte hoch, mit Tausenderpunkt, mitten im Bild – Video 186): ein Jahr ist keine Menge, es wird ein Schild
        ov_y = sc.get("overlay") if isinstance(sc, dict) and isinstance(sc.get("overlay"), dict) else None
        if ov_y and str(ov_y.get("type") or "") == "counter" and not str(ov_y.get("unit") or "").strip():
            try:
                v_y = float(str(ov_y.get("value")).replace(".", "").replace(",", "."))
            except (TypeError, ValueError):
                v_y = None
            if v_y is not None and 1000 <= v_y <= 2100 and v_y == int(v_y):
                lab_y = str(ov_y.get("label") or "").strip().upper()
                sc["overlay"] = {"type": "tag", "text": ((lab_y + " " if lab_y else "JAHR ") + str(int(v_y)))[:30]}
    for sc in scenes:                                     # ein einzelnes Auge neben Menschen („mustern dich mit großen Augen“ in der Bahn, Video 160) – überall, nicht nur im Zimmer
        if isinstance(sc, dict) and isinstance(sc.get("props"), list) and str(sc.get("shot") or "") not in ("insert", "graphic") and (
                sc.get("crowd") or any(isinstance(a, dict) and not a.get("kind") for a in sc.get("actors") or [])):
            sc["props"] = [q for q in sc["props"] if str((q.get("type") if isinstance(q, dict) else q) or "").lower().replace("lib_", "") not in ("auge", "augen")]
    for sc in scenes:                                     # was der Satz verneint („ohne Burgen“), bringt auch kein späterer Durchgang zurück
        if isinstance(sc, dict) and sc.get("_simile") and isinstance(sc.get("props"), list) and str(sc.get("shot") or "") != "graphic":
            deny_k = [k for pat, k in _lib_props() + TEXT_PROPS if k in sc["_simile"] and denied(pat, str(sc.get("text") or "").lower())]
            if deny_k:
                sc["props"] = [q for q in sc["props"] if extras.PROP_ALIASES.get(str((q.get("type") if isinstance(q, dict) else q) or "").lower(),
                                                                             str((q.get("type") if isinstance(q, dict) else q) or "").lower()) not in deny_k]
                if str(sc.get("shot") or "") == "insert" and not sc["props"]:
                    sc["shot"] = ""
    _stay(scenes)
    for sc in scenes:                                     # Mathe-Thema im Klassenzimmer: an der Tafel stehen Zahlenstrahl mit eingekreisten Primzahlen und eine Kurve statt zweier Striche (Video 197)
        if isinstance(sc, dict) and not isinstance(sc.get("backdrop"), dict) and places.resolve(sc.get("place")) == "classroom" \
                and _re0.search(MATH_RE, (str(topic or "") + " " + str(sc.get("text") or "")).lower()):
            sc["place"] = "mathroom"
        elif isinstance(sc, dict) and not isinstance(sc.get("backdrop"), dict) and places.resolve(sc.get("place")) == "lab" and _re0.search(MATH_RE, str(topic or "").lower()) \
                and not _re0.search(r"\blabor|experiment|chemi|reagenz|mikroskop|versuch", str(sc.get("text") or "").lower()):
            sc["place"] = "mathroom"                      # Mathe-Thema: der Forscher steht vor der Tafel, nicht zwischen Kolben und Reagenzgläsern (Video 198)
    _frost_frog(scenes, topic, main_id)
    _angler_story(scenes, topic)
    _door_people(scenes, main_id)
    _wecker_story(scenes, topic, main_id)
    _exo_story(scenes, topic, main_id)
    _tetris_story(scenes, topic)
    _plates_apart(scenes, main_id)
    _mirror_story(scenes, topic, main_id)
    _mirror_msg(scenes, topic, style, main_id)
    _fridge_open(scenes)
    _studio_money(scenes)
    return scenes


# Spiegel-Video (Video 204): Sätze über das eigene Spiegelbild zeigen den Blick in den Spiegel (Einstellung „mirror“, `_mirror_frame`) im Zustand,
# den der Satz beschreibt; die Regie führt Buch (normal → Rand versinkt → schwarze Augen → Fratze → wieder normal). Höchstens zwei Spiegel-Bilder
# hintereinander, dazwischen die Figur im Bad oder das Gehirn als Erklärer – das erklärt ruhig, nicht ängstlich. Erleichterte Sätze sind hell und froh.
MIRROR_TOPIC_RE = r"spiegel"
MIRROR_GAZE_RE = r"starr|troxler|spiegelbild|im dunkeln|in den spiegel (?:schau|blick|seh|guck)|gesicht"
MIRROR_BACK_RE = r"verschwindet|verschwunden|echtes gesicht|wieder normal|bricht\b.{0,30}zusammen|alles wie vorher|ist der spuk vorbei"
MIRROR_MON_RE = r"fratze|monster|fremde[sn]? gesicht|grimasse|dämon|ungeheuer|fremde person|jemand anderes"
MIRROR_VOID_RE = r"augen\b.{0,60}(?:riesig|schwarz|höhle|löcher)|pechschwarz|schwarze augen|augenhöhlen"
MIRROR_FADE_RE = r"löscht|blendet\b.{0,40}aus|verblass|verschwimm|versink|rand de[sr]|sichtfeld|verändert sich|verzerr|kontur|verformt|zerfließ|schmilz|unscharf"
MIRROR_SELF_RE = r"spiegel|starr|gesicht|deine (?:nase|augen|haare|stirn|wangen)|dein(?:en)? (?:mund|kopf)\b"
MIRROR_CALM_RE = r"erleichtert|beruhigt|atmest (?:tief )?(?:durch|auf)|aufatmen|licht an|entspann|keine angst"
BRAIN_IDS = ("gehirn", "hirn", "brain", "_hirn")


def _plates_apart(scenes, main_id="du"):
    """Das Gehirn als Figur ist hoch – unter einem Notizzettel (und anderen hohen Einblendungen) wird es kleiner gezeichnet, damit der Zettel nicht
    auf seinem Kopf klebt (Prüfung 27.11.2026, Video 232: „GEHIRN-UPDATE“ verdeckte die obere Hälfte des Gehirns)."""
    for sc in scenes:
        if isinstance(sc, dict) and isinstance(sc.get("overlay"), dict) and str(sc["overlay"].get("type") or "") in TALL_OV:
            for a in (sc.get("actors") or []):
                if isinstance(a, dict) and (a.get("kind") == "brain" or str(a.get("id")) == "gehirn"):
                    a["small"] = True


# ------------------------------------------------------------------ Tetris-Effekt: die Bausteine fallen wirklich durchs Bild
# Prüfung 27.11.2026 (Video 231, „Tetris-Effekt“): „Überall fallen plötzlich Blöcke“ und „vor deinem inneren Auge fallen weiter Steine“ – zu sehen war
# kein einziger Baustein, nur die erschrockene Figur im Zimmer und im Bett. Jetzt fallen in solchen Sätzen halb durchsichtige Bausteine durchs Bild
# (extras.fallblocks, frei erfundene Formen – kein Spielfeld, kein Zeichen des echten Spiels).
TETRIS_RE = r"tetris|blockspiel|klötzchenspiel"
TETRIS_PLAY_RE = r"tetris (?:\w+ ){0,4}(?:spiel|zock|gespielt|gezockt)|(?:spiel|zock)\w* (?:\w+ ){0,8}tetris|\bzocks?t\b|\bzocken\b|\bgezockt\b"
TETRIS_BLOCK_RE = (r"bl[oö]cke?n?\b|\bsteine?n?\b|bausteine?n?\b|klötz|\bformen\b|puzzleteil|tetris-?effekt|\bstapel|einsortier|\blücken?\b|\braster\b|"
                   r"inner\w* auge|geschlossen\w* augen|beim einschlafen|schläfst du ein|im traum|träum")


def tetris_story(scenes, topic=""):
    import re as _re
    return bool(_re.search(TETRIS_RE, topic_head(topic).lower())) or \
        sum(1 for sc in scenes if isinstance(sc, dict) and _re.search(TETRIS_RE, str(sc.get("text") or "").lower())) >= 2


def _tetris_story(scenes, topic=""):
    import re as _re
    if not tetris_story(scenes, topic):
        return
    for sc in scenes:
        if not isinstance(sc, dict) or (str(sc.get("shot") or "") == "graphic" and sc.get("graphic")):
            continue
        if _re.search(TETRIS_BLOCK_RE, str(sc.get("text") or "").lower()):
            sc["_blocks"] = True
            if str(sc.get("shot") or "") == "insert":
                sc["shot"] = ""                       # die Bausteine fallen im Raum um die Figur – keine Großaufnahme eines einzelnen Gegenstands
        low_t = str(sc.get("text") or "").lower()
        humans = [a_ for a_ in (sc.get("actors") or []) if isinstance(a_, dict) and not a_.get("kind") and str(a_.get("id")) != "gehirn"]
        if isinstance(sc.get("props"), list):             # der einzelne lila „Tetris-Block“ am Boden (von der Text-KI gelernt) stand in fünf Szenen herum und füllte vier Sekunden lang allein das Bild (Video 232)
            sc["props"] = [q for q in sc["props"] if "tetris" not in str(q.get("type") if isinstance(q, dict) else q).lower()]
        if sc.get("_blocks"):
            for a_ in humans:
                if str(a_.get("action") or "") in ("sleep", "schlafen"):
                    sc["time"] = "night"                  # „sah beim Einschlafen fallende Steine“: geschlafen wird nachts, ohne Handy in der Hand und ohne Musiknoten
                    a_["hold"] = ""
                    if str(a_.get("emote") or "") == "music":
                        a_["emote"] = ""
        if _re.search(TETRIS_PLAY_RE, low_t):
            sc["_no_insert"] = True                       # kein harter Schnitt auf einen Gegenstand, während erzählt wird, wer spielt
        if humans and _re.search(TETRIS_PLAY_RE, low_t):
            if str(sc.get("shot") or "") == "insert":
                sc["shot"] = ""                       # „… ließen Testpersonen Tetris spielen“: die Figur spielt – kein leerer Bildschirm auf einem Tisch als Großaufnahme
            if not any(isinstance(q, dict) and str(q.get("type")).lower() in ("computer", "tv", "konsole", "console") for q in (sc.get("props") or [])) and not humans[0].get("hold") \
                    and str(humans[0].get("action") or "") not in ("sleep", "schlafen"):
                humans[0]["hold"] = "phone"           # ohne Rechner im Bild (Notaufnahme, Bahn): gespielt wird auf dem Handy in der Hand

def mirror_story(scenes, topic=""):
    head = str(topic or "").lower()
    return bool(re.search(MIRROR_TOPIC_RE, head) and re.search(MIRROR_GAZE_RE, head))


def _mirror_story(scenes, topic="", main_id="du"):
    if not mirror_story(scenes, topic):
        return scenes
    cur, run, lit = "normal", 0, False
    for i, sc in enumerate(scenes):
        if not isinstance(sc, dict):
            continue
        low = str(sc.get("text") or "").lower()
        acts = [a for a in (sc.get("actors") or []) if isinstance(a, dict)]
        if re.search(r"licht\b.{0,12}\ban\b|licht ein|lichtschalter", low):
            lit = True                                    # „Du machst das Licht an“: ab hier ist das Bad hell
        elif re.search(r"licht\b.{0,12}\baus\b|heute (?:abend|nacht)|im dunkeln|halbdunkel", low):
            lit = False
        if lit and places.resolve(backdrop(sc)) == "bathroom":
            sc["time"], sc["weather"] = "day", ""
            if str(sc.get("mood") or "") in ("scary", "tense", "panic", "sad"):
                sc["mood"] = "calm"
        brain = [a for a in acts if str(a.get("kind") or "").lower() == "brain" or str(a.get("id") or "").lower() in BRAIN_IDS]
        for a in brain:                                   # das Gehirn erklärt: sachlich, kein Angstgesicht mit Schweißtropfen
            a["emotion"], a["emote"] = "", ""
            if str(a.get("action") or "") in ("shocked", "scared"):
                a["action"] = "talk"
        shot = str(sc.get("shot") or "")
        if shot == "graphic" and graphics.clean(sc.get("graphic")):
            run = 0
            continue
        if re.search(MIRROR_CALM_RE, low) and not re.search(MIRROR_SELF_RE, low):     # „Du machst das Licht an und gehst erleichtert ins Bett“: hell und froh
            sc["mood"] = "happy"
            for a in acts:
                if a not in brain:
                    a["emotion"], a["emote"] = "happy", ""
            run = 0
            continue
        state = None
        if re.search(MIRROR_BACK_RE, low):
            state = "snap" if cur in ("fade", "void", "monster") else "clear" if lit else "normal"
            cur = "normal"
        elif re.search(MIRROR_MON_RE, low):
            state = cur = "monster"
        elif re.search(MIRROR_VOID_RE, low):
            state = cur = "void"
        elif re.search(MIRROR_FADE_RE, low) and (re.search(MIRROR_SELF_RE, low) or cur != "normal" or not brain):
            state = cur = "fade"
        elif re.search(MIRROR_SELF_RE, low) and (not (brain and len(brain) == len(acts)) or re.search(r"\bstarr|\bfixier", low)):
            state = cur if cur != "normal" else "clear" if lit else "stare"
        if i == 0 and state:                              # erstes Bild: gleich das, worum es geht – die schwarzen Augen im Spiegel
            state, cur = "void", "normal"                 # nur der Vorgriff – danach beginnt die Geschichte beim unveränderten Spiegelbild
        if not state or (run >= 2 and state not in ("snap", "monster")):
            run = 0
            continue
        sc["shot"], sc["mirror"] = "mirror", state
        sc["actors"] = [{"id": main_id, "action": "idle", "emotion": "", "emote": "", "pos": "center", "speaks": False, "say": "", "hold": "", "facing": "", "kind": ""}]
        sc["props"], sc["crowd"], sc["graphic"] = [], "", None
        sc["place"], sc["backdrop"] = "bathroom", None
        sc["_no_cut"] = True
        if isinstance(sc.get("overlay"), dict) and str(sc["overlay"].get("type") or "") not in ("card", "tag", "stamp"):
            sc["overlay"] = None                          # Liste, Zähler, Handy lägen über dem Spiegelbild
        run += 1
    return scenes


# Erzählte Geschichte mit Spiegeln (Prüfung 26.11.2026, Video 219 „Unbekannte Nummer: Verhäng alle Spiegel“): Die Geschichte handelte davon, alle
# Spiegel zu verhängen, bis sich das Spiegelbild von allein bewegt – im Bild war kein einziger Spiegel, die Figur zeigte ins Leere. Jetzt: Spricht
# der Satz vom Spiegelbild, sieht man den Blick in den Spiegel (Einstellung „mirror“: reglos → „stare“, bewegt sich von allein → „void“, lächelt
# fremd → „monster“). Spricht er vom Verhängen oder von Tüchern, steht der verhängte Spiegel neben der Figur; nennt er sonst einen Spiegel, der
# offene. Im Bad hängt der Spiegel schon an der Wand.
MSG_MIRROR_RE = r"spiegelbild|aus dem spiegel|im spiegel\b.{0,60}(?:beweg|lächel|grins|wink|starr|blinzel|steht)|(?:beweg|lächel|grins|wink|starr|blinzel)\w*\b.{0,40}im spiegel"
MSG_MIRROR_MON_RE = r"lächel|grins|fratze|fremde[sn]? gesicht|lacht"
MSG_MIRROR_MOVE_RE = r"beweg|wink|blinzel|hebt\b|dreht sich|von allein|von selbst"
MSG_COVER_RE = r"verh[äa]ng|verhüll|zugehängt|abgehängt|bedeck|hinter (?:\w+ ){0,2}(?:stoff|tuch|tüchern|decken|laken)|(?:tuch|decke|laken) über"
MSG_CLOTH_RE = r"\btuch\b|\btücher|\bdecken\b|\blaken\b|\bstoff\b"
MSG_COVER_NOT_RE = r"(?:nicht|kein\w*)\s+(?:\w+\s+){0,2}(?:verh[äa]ng|verhüll|bedeck|zugehängt)"


FRIDGE_OPEN_RE = r"kühlschrank\w*\b.{0,25}\b(?:auf|offen)\b|(?:öffne|reißt|reisst|machst)\w*\b.{0,30}kühlschrank\w*\b(?:.{0,12}\bauf\b)?|kühlschranktür"


def _fridge_open(scenes):
    """„Du reißt den Kühlschrank auf“: ein Mensch steht davor, der Kühlschrank steht offen und leuchtet (Video 220: die Figur stand vor der geschlossenen Küchenzeile)."""
    for sc in scenes:
        if not isinstance(sc, dict) or sc.get("shot") in ("graphic", "mirror"):
            continue
        acts = [a for a in (sc.get("actors") or []) if isinstance(a, dict)]
        if len(acts) != 1 or acts[0].get("kind") or not re.search(FRIDGE_OPEN_RE, str(sc.get("text") or "").lower()):
            continue
        if isinstance(backdrop(sc), dict) or places.resolve(backdrop(sc)) != "kitchen":
            sc["place"], sc["backdrop"] = "kitchen", None
        sc["props"] = [{"type": "fridge_open", "pos": "right"}]
        sc["shot"] = ""
        acts[0]["pos"], acts[0]["to"], acts[0]["facing"] = "left", "", "right"
        sc["_no_cut"] = True


def _mirror_msg(scenes, topic="", style="", main_id="du"):
    if str(style or "").lower() not in STORY_STYLES or mirror_story(scenes, topic):
        return scenes
    if "spiegel" not in " ".join(str(sc.get("text") or "") for sc in scenes if isinstance(sc, dict)).lower():
        return scenes
    ordered, run, rooms, n_cov = False, 0, ("hallway", "livingroom", "bedroom"), 0
    for sc in scenes:
        if not isinstance(sc, dict):
            continue
        low = str(sc.get("text") or "").lower()
        cover = bool(re.search(MSG_COVER_RE, low)) and not re.search(MSG_COVER_NOT_RE, low)
        if cover:
            ordered = True
        card = sc.get("shot") == "graphic" and bool(graphics.clean(sc.get("graphic")))
        if card and str(sc["graphic"].get("type")) != "chapter":
            run = 0
            continue                                      # Kapitel-Tafel: nach CHAPTER_MAX Sekunden sieht man die Figur am Ort – auch dort steht der Spiegel
        acts = [a for a in (sc.get("actors") or []) if isinstance(a, dict)]
        if re.search(MSG_MIRROR_RE, low) and run < 2 and not card:
            sc["shot"] = "mirror"
            sc["mirror"] = "monster" if re.search(MSG_MIRROR_MON_RE, low) else "void" if re.search(MSG_MIRROR_MOVE_RE, low) else "stare"
            sc["actors"] = [{"id": main_id, "action": "idle", "emotion": "", "emote": "", "pos": "center", "speaks": False, "say": "", "hold": "", "facing": "", "kind": ""}]
            sc["props"], sc["crowd"], sc["graphic"], sc["overlay"] = [], "", None, None
            sc["place"], sc["backdrop"], sc["time"], sc["weather"] = "bathroom", None, "night", ""
            sc["_no_cut"] = True
            run += 1
            continue
        run = 0
        in_bath = bool(re.search(r"\bbad\b|badezimmer", low)) or (not cover and "spiegel" not in low and not isinstance(backdrop(sc), dict)
                                                                  and places.resolve(backdrop(sc)) == "bathroom")   # „Du greifst nach dem Tuch“ im Bad: dort hängt der Spiegel offen an der Wand
        kind = "mirror_covered" if (cover or (ordered and re.search(MSG_CLOTH_RE, low))) and not in_bath else \
            "mirror" if "spiegel" in low and not in_bath and not re.search(MSG_COVER_NOT_RE, low) else ""
        if in_bath and "spiegel" in low:                    # der Spiegel hängt im Bad an der Wand: die Figur steht ganz davor, keine Großaufnahme ohne Spiegel
            sc["place"], sc["backdrop"] = "bathroom", None
            sc["shot"] = "" if str(sc.get("shot") or "") in ("close", "insert", "event") else sc.get("shot")
        if not kind or not acts:
            continue
        if isinstance(backdrop(sc), dict) or places.resolve(backdrop(sc)) not in ("hallway", "livingroom", "bedroom"):
            sc["place"], sc["backdrop"] = rooms[n_cov % len(rooms)], None
        n_cov += 1
        sc["props"] = [{"type": kind, "pos": "right"}]
        sc["shot"], sc["weather"], sc["crowd"] = "graphic" if card else "", "", ""
        for a in acts[:1]:
            a["pos"], a["to"], a["facing"] = "left", "", "right"
            if str(a.get("action") or "") in ("walk", "run", "idle", ""):
                a["action"] = "point" if kind == "mirror_covered" and cover else "look_around" if str(a.get("emotion") or "") == "scared" else "idle"
        sc["actors"] = acts[:1]
        sc["_no_cut"] = True
    return scenes


# Reise in die Vergangenheit (Prüfung 22.11.2026, Video 185 „Smartphone im Jahr 1800: Was passiert wirklich?“): Das Jahr 1800 spielte vor Läden
# mit Markisen an einer Asphaltstraße, die Passanten trugen Kapuzenpullis und Mützen, die Stadtwache einen Bauhelm, der König stand im Pulli auf
# dem Gehweg; zur Musik stand eine Bassbox im Bild, zu „Stück Glas und Metall“ ein Trinkglas, zum Museum Kühltürme, zu „Display wird schwarz“
# leuchtete ein Anrufbild, und bei „kein einziger Mobilfunkmast“ funkelte eine Weltkugel voller Stadtlichter. Jetzt: Nennt der Kern des Themas
# ein Jahr bis 1849 oder das Mittelalter, spielt alles in der Zeit – Altstadt mit Fachwerk und Pflaster (`oldtown`), Thronsaal (`throneroom`),
# Kabinett mit Vitrine (`royalmuseum`), Dorf ohne Masten; alle außer der Hauptfigur tragen die Kleidung der Zeit; nichts Modernes steht im Bild.
# Bringt die Hauptfigur ein Handy mit, hält sie es in jeder Szene – mit Blitz beim Foto, als Taschenlampe, mit Noten bei Musik, schwarz, sobald
# der Akku leer ist.
PAST_TOPIC_RE = r"\b(?:im|ins|das|dem) jahre? (?:1[0-7]\d\d|18[0-4]\d|[1-9]\d\d)\b|\bmittelalter"
P_THRONE_RE = r"könig|kaiser|herrscher|\bthron|stadtrat|palast|\bfürst|vorgeführt|\bhof\b|majestät"
P_MUSEUM_RE = r"museum|vitrine|ausgestellt|schatzkammer|kunstkammer|kabinett|artefakt"
P_TOWN_RE = r"straße|passant|\bstadt\b|marktplatz|\bmarkt\b|gasse|landest|ankunft|kommst (?:\w+ ){0,3}an\b"
P_FIELD_RE = r"mobilfunkmast|funkmast|sendemast|\bmast\b|\bmasten\b|weit und breit|funkturm|satellit"
P_GUARD_RE = r"\bwache|wachen\b|stadtwache|soldat|in ketten|festgenommen|verhaftet|abgeführt|gefesselt|nehmen dich|packen dich|kerker"
P_PHOTO_RE = r"\bfoto|\bblitz\b|fotografier|kamera|selfie"
P_WITCH_RE = r"hexe|teufel|zauberei|dämon|schreien|flieh|weichen (?:\w+ ){0,3}zurück|\bangst\b|panik"
P_LIGHT_RE = r"taschenlampe|\blicht\b|leuchte"
P_MUSIC_RE = r"musik|\blied|\bsong|melodie|lautsprecher"
P_CALC_RE = r"\brechn|taschenrechner|zahlen|mathe"
P_MAGE_RE = r"zauberer|magier|hexer|hexenmeister|spion|verbeugt|staunt"
P_BATT_RE = r"\bakku|prozent|batterie"
P_DEAD_RE = r"(?:display|bildschirm|schirm) (?:\w+ ){0,3}schwarz|geht (?:\w+ ){0,4}aus\b|akku (?:ist |war )?(?:leer|tot)|erlischt|schaltet sich (?:\w+ ){0,2}ab|ist tot\b"
P_PLUG_RE = r"steckdose|aufladen|ladekabel|ladegerät|\bstrom\b|stromnetz|kraftwerk"
P_JUNK_RE = r"glas und metall|nutzlos|wertlos|briefbeschwerer|\bschrott"
P_KING_ID = r"k(?:ö|oe|o)nig|kaiser|herrscher|fuerst|fürst|king"
P_GUARD_ID = r"wache|waechter|wächter|soldat|guard"
P_SCHOLAR_RE = r"gelehrte|berater|minister|hofstaat|höfling|professor|mathematiker|rechenmeister"
P_STEP_RE = r"\bnach (?:\w+ ){1,2}(?:sekunde|minute|stunde|tag|woche)"


def past_story(scenes, topic=""):
    """Für den Selbsttest."""
    _past_story(scenes, topic, "du")
    return scenes


def _past_story(scenes, topic="", main_id=""):
    """Geschichte in der Vergangenheit: siehe Kommentar oben. Greift nur, wenn der Kern des Themas ein Jahr bis 1849 oder das Mittelalter nennt."""
    import re as _re
    if not _re.search(PAST_TOPIC_RE, topic_head(topic).lower()):
        return
    dicts = [sc for sc in scenes if isinstance(sc, dict)]
    main_id = str(main_id or "du")
    ids = [str(a.get("id")) for sc in dicts for a in (sc.get("actors") or []) if isinstance(a, dict) and a.get("id") and not a.get("kind")]
    king_id = next((i for i in ids if _re.search(P_KING_ID, i.lower())), "_koenig")
    guard_id = next((i for i in ids if _re.search(P_GUARD_ID, i.lower())), "_wache")
    has_phone = bool(_re.search(r"smartphone|handy|telefon", str(topic or "").lower()))
    king_look = {"shirt": "rot", "hat": "crown", "hair_color": "grau", "gender": "m", "outfit": "king"}
    guard_look = {"shirt": "blau", "hat": "tricorn", "gender": "m", "outfit": "guard"}
    folk = ({"shirt": "braun", "hat": "tricorn", "gender": "m", "outfit": "period", "hair_color": "braun"},
            {"shirt": "grün", "hat": "bonnet", "hair": "bun", "gender": "w", "outfit": "period", "hair_color": "rot", "hat_color": "blau"},
            {"shirt": "oliv", "hat": "", "gender": "m", "outfit": "period", "hair_color": "schwarz"},
            {"shirt": "türkis", "hat": "", "hair": "long", "gender": "w", "outfit": "period", "hair_color": "dunkelbraun"})

    def citizen(i, pos, action, emotion="", emote=""):
        return {"id": "_buerger%d" % (i % 4 + 1), "look": dict(folk[i % 4]), "_outfit": "period", "action": action, "emotion": emotion, "emote": emote,
                "pos": pos, "speaks": False, "hold": "", "kind": "", "facing": "", "say": ""}

    def king(action, emotion="", emote="", pos=800):          # nicht am Rand: die Kamerafahrt schnitt Figuren bei 170/900 an (Video 187)
        return {"id": king_id, "look": dict(king_look), "_outfit": "king", "action": action, "emotion": emotion, "emote": emote, "pos": pos,
                "speaks": False, "hold": "", "kind": "", "facing": "", "say": ""}

    def guard(i, pos):
        return {"id": guard_id if i == 0 else "_wache2", "look": dict(guard_look), "_outfit": "guard", "action": "point", "emotion": "angry", "emote": "",
                "pos": pos, "speaks": False, "hold": "", "kind": "", "facing": "", "say": ""}

    loc, dead, last_n, n_town, said_dead, last_sig = "town", False, len(scenes) - 1, 0, False, None
    seen_museum = False
    head_years = set(_re.findall(r"\b\d{3,4}\b", topic_head(topic)))
    for n, sc in enumerate(scenes):
        if not isinstance(sc, dict):
            continue
        text = str(sc.get("text") or "")
        low = text.lower()
        sc["_era"] = True
        if any(isinstance(a, dict) and a.get("kind") for a in sc.get("actors") or []):
            continue                                      # Tier oder Wesen als Figur: gehört einer anderen Regie
        museum = bool(_re.search(P_MUSEUM_RE, low))
        if _re.search(P_THRONE_RE, low):
            loc = "throne"
        elif _re.search(P_TOWN_RE, low) and not museum:
            loc = "town"
        here = "museum" if museum else loc
        if seen_museum and dead and here == "throne" and not _re.search(P_PLUG_RE + "|" + P_BATT_RE, low):
            here = "museum"                               # das Handy liegt schon in der Vitrine: „Der König staunt täglich über das schwarze Wunderwerk“ spielt dort – die Hauptfigur hielt es sonst wieder in der Hand (Video 188)
        seen_museum = seen_museum or museum
        if n == last_n and "?" in text and n > 2:
            here = "town"                                 # die Schlussfrage an die Zuschauer: zurück auf den Platz
        dying = bool(_re.search(P_DEAD_RE, low)) and has_phone
        if sc.get("shot") == "graphic" and graphics.clean(sc.get("graphic")):
            g_p = sc["graphic"]
            step = _re.search(P_STEP_RE, low) and str(g_p.get("type") or "").lower() in ("number", "timer", "calendar", "days") and _re.search(r"\bdu\b|\bdich\b|\bdein", low)
            if not step:
                dead = dead or dying
                if _re.search(r"ankunft|gelandet|landung", str(g_p.get("kicker") or "").lower()):
                    g_p["kicker"] = "ERST SPÄTER" if _re.search(r"später|danach", low) else ""   # „JAHR 1800 · ANKUNFT“ über „100 JAHRE“ (später): die Ecken-Zeile ist keine Überschrift für diese Zahl
                continue                                  # echtes Schaubild (Jahre, Vergleich) bleibt
            sc["graphic"], sc["shot"] = None, ""          # „Doch schon nach zwei Sekunden bemerkst du …“: die Zahl „2 SEKUNDEN“ allein erzählt nichts – die Szene zeigt, was passiert
            if not isinstance(sc.get("overlay"), dict):
                val, lab = str(g_p.get("value") or "").strip(), str(g_p.get("label") or "").strip()
                if val and lab and spoken_number(val, text):
                    sc["overlay"] = {"type": "tag", "text": ("NACH %s %s" % (val, lab)).upper()[:24]}
        sc["backdrop"], sc["weather"], sc["crowd"], sc["props"], sc["shot"] = None, "", "", [], ""
        sc["mood"] = ""                                   # kein Halbdunkel mit Lichtkegel am helllichten Tag auf dem Marktplatz, im Thronsaal und vor der Vitrine
        sc["time"] = "night" if str(sc.get("time") or "") == "night" and _re.search(r"nacht|mitternacht|dunkel", low) else "day"
        sc["place"] = {"town": "oldtown", "throne": "throneroom", "museum": "royalmuseum"}[here]
        phone = ("phonedead" if dead else "phone") if has_phone else ""
        me = {"id": main_id, "_outfit": "modern", "action": "idle", "emotion": "", "emote": "", "pos": "left", "hold": phone, "speaks": True,
              "kind": "", "facing": "", "say": ""}
        yrs_p = [int(y) for y in _re.findall(r"\b(1[0-9]\d\d|20\d\d)\b", year_digits(text) + " " + text) if y not in head_years]   # ein anderes Jahr als das der Geschichte („erst 1826“, „erst 1882“)
        prev_p = scenes[n - 1] if n and isinstance(scenes[n - 1], dict) else {}
        next_p = scenes[n + 1] if n + 1 < len(scenes) and isinstance(scenes[n + 1], dict) else {}
        next_g = next_p.get("shot") == "graphic" and bool(graphics.clean(next_p.get("graphic"))) and bool(yrs_p) and str(yrs_p[0]) in " ".join(str(v) for v in (next_p.get("graphic") or {}).values())   # der Folgesatz zeigt das Jahr schon als Schaubild: nicht zweimal hintereinander „1882“ (Video 188: 13 Sekunden nur Plaketten)
        if yrs_p and n and prev_p.get("shot") != "graphic" and not next_g and not _re.search(P_GUARD_RE + "|" + P_MUSEUM_RE, low) and not dying:
            sc["graphic"] = {"type": "badge", "kicker": "ERST SPÄTER", "text": "JAHR %d" % yrs_p[0]}   # „Die ersten Kraftwerke gehen erst 1882 ans Netz“: das Jahr groß als Plakette statt noch einmal dieselbe ratlose Figur (Video 187)
            sc["shot"], sc["overlay"], sc["actors"] = "graphic", None, []
            continue
        if here == "museum":                              # Vitrine in der Mitte, zwei staunende Besucher in der Kleidung der Zeit – die Hauptfigur ist nicht dabei
            sc["actors"] = [citizen(n, 230, "think", "", "?"), king("point", "shocked", "!", 850) if (_re.search(P_THRONE_RE, low) and not museum) else citizen(n + 1, 850, "point", "shocked", "!")]
            sc["_no_cut"], sc["mood"] = True, ""          # hell: im Halbdunkel verschwand die Vitrine (Video 186)
        elif dying and not said_dead:                     # das Handy geht aus: groß und allein im Bild, der Schirm schwarz
            sc["actors"], sc["props"], sc["shot"], sc["mood"] = [], [{"type": "phone_dead"}], "insert", "sad"
            said_dead = True
        elif _re.search(P_GUARD_RE, low):                 # Wachen links und rechts, die Hauptfigur duckt sich dazwischen
            me.update(action="cower", emotion="scared", pos="center", hold="")
            sc["actors"] = [guard(0, 250), me, guard(1, 830)]
            sc["_no_cut"] = True
        elif here == "town" and _re.search(P_PHOTO_RE, low) and has_phone and not dead:
            me.update(hold="phoneflash", pos=260, emotion="happy")
            sc["actors"] = [me, citizen(n, 610, "shocked", "scared", "!"), citizen(n + 1, 840, "cower", "scared", "")]
            sc["_no_cut"] = True
        elif here == "town" and _re.search(P_WITCH_RE, low):
            me.update(pos=260, emotion="worried", action="idle")
            sc["actors"] = [me, citizen(n, 600, "point", "angry", "anger"), citizen(n + 1, 840, "shocked", "scared", "!")]
            sc["_no_cut"] = True
        elif here == "throne":
            solo = False
            if _re.search(P_PLUG_RE, low):
                me.update(action="look_around", emotion="sad", emote="?", pos="center")
                solo = True
            elif _re.search(P_BATT_RE, low):
                me.update(action="shocked", emotion="worried", pos="center")
                solo = True
            elif _re.search(P_JUNK_RE, low):
                me.update(action="sad", emotion="sad", pos=290)
                kg = king("think", "", "?")
            elif _re.search(P_LIGHT_RE, low) and has_phone and not dead:
                me.update(hold="phonelight", pos=290, emotion="happy")
                kg = king("shocked", "shocked", "!", 800)
            elif _re.search(P_MUSIC_RE, low) and has_phone and not dead:
                me.update(hold="phonemusic", pos=290, emotion="happy")
                kg = king("freeze", "shocked", "!")
            elif _re.search(P_CALC_RE, low):
                me.update(pos=290, emotion="happy")
                kg = king("think", "worried", "?")
            elif _re.search(P_MAGE_RE, low):
                me.update(pos=290, emotion="happy", action="idle")
                kg = king("point", "shocked", "!")
            else:
                me.update(pos=290, emotion="worried")
                kg = king("talk", "angry", "")
                kg["speaks"], me["speaks"] = True, False
            sc["actors"] = [me] if solo else [me, kg]
            if not solo:
                sc["_no_cut"] = bool(me["hold"] in ("phonelight", "phonemusic"))
                sig = (me["hold"], kg["action"])
                if _re.search(P_SCHOLAR_RE, low):           # „Die Gelehrten des Königs brauchen dafür Stunden“: zwei ratlose Gelehrte neben dem König statt noch einmal dasselbe Bild
                    me.update(pos=250)
                    sc["actors"] = [me, dict(citizen(0, 540, "think", "worried", "?"), id="_gelehrter1"), dict(citizen(2, 820, "shocked", "shocked", "!"), id="_gelehrter2")]
                    sc["_no_cut"] = True
                elif sig == last_sig:                     # zweiter Satz zum selben Moment (Musik … „hat hier noch nie ein Mensch gehört“): eine Wache staunt mit, der König reißt die Arme hoch
                    me.update(pos=250)
                    kg.update(pos=830, action="shocked", emotion="shocked", emote="!")
                    sc["actors"] = [me, dict(guard(0, 540), action="shocked", emotion="shocked", emote="?"), kg]
                    sc["_no_cut"] = True
                last_sig = sig
        else:                                             # auf dem Platz der alten Stadt (oder im Dorf, wenn der Satz von Masten spricht)
            if _re.search(P_FIELD_RE, low) and not _re.search(P_PLUG_RE, low):
                sc["place"] = "village"
                me.update(action="look_around", emotion="worried", emote="?", pos="center")
            elif n == last_n:
                me.update(action="talk", emotion="happy", pos="center", hold="phone" if has_phone and not dead else "")
            elif _re.search(P_PLUG_RE, low):
                me.update(action="look_around", emotion="sad", emote="?", pos="center")
            elif _re.search(P_BATT_RE, low):
                me.update(action="shocked", emotion="worried", pos="center")
            elif n == 0:
                me.update(action="look_around", emotion="worried", pos="center")
                sc["crowd"] = "walk"
            else:
                me.update(action="think" if n_town % 2 else "idle", emotion="worried", pos="center" if n_town % 2 else 330)
                sc["crowd"] = "walk" if n_town % 2 == 0 else ""
            sc["actors"] = [me]
            n_town += 1
        dead = dead or dying
        ov_p = sc.get("overlay")
        if isinstance(ov_p, dict) and str(ov_p.get("type") or "") == "counter" and str(ov_p.get("unit") or "").strip() and ov_p.get("value") is not None:
            sc["overlay"] = {"type": "tag", "text": ("NACH %s %s" % (_fmt_num(ov_p["value"]) if isinstance(ov_p["value"], (int, float)) else ov_p["value"], str(ov_p["unit"]).strip())).upper()[:24]} \
                if _re.search(P_STEP_RE, low) else ov_p   # „Nach fünf Minuten …“: kleines Schild oben statt einer großen Zahl, die mitten über der Handlung hochzählt
        ov_p = sc.get("overlay")
        if isinstance(ov_p, dict) and str(ov_p.get("type") or "") in ("phone", "note", "checklist"):
            sc["overlay"] = None                          # Handy-Chat oder Zettel als Einblendung: im Jahr 1800 schreibt niemand zurück
    for n in range(1, len(scenes)):                       # dieselbe Einstellung zweimal hintereinander: die zweite rückt als Großaufnahme an die Hauptfigur
        a_, b_ = scenes[n - 1], scenes[n]
        if not (isinstance(a_, dict) and isinstance(b_, dict) and b_.get("_era")):
            continue
        acts_b = [x for x in (b_.get("actors") or []) if isinstance(x, dict)]
        acts_a = [x for x in (a_.get("actors") or []) if isinstance(x, dict)]
        if len(acts_b) == 1 and len(acts_a) == 1 and a_.get("place") == b_.get("place") and not a_.get("shot") and not b_.get("shot") \
                and acts_b[0].get("hold") not in ("phonelight", "phonemusic", "phoneflash") and str(acts_b[0].get("action")) not in ("cower",):
            b_["shot"], b_["crowd"] = "close", ""
            acts_b[0]["pos"] = "center"


# Telefonat (Prüfung 22.11.2026, Video 181 „Doppelgänger am Telefon“): Die Geschichte spielt während eines Anrufs – im Bild saß der Angerufene
# aber im selben Wohnzimmer daneben, die Hauptfigur hatte in den meisten Szenen gar kein Handy, lief zwischendurch auf eine Stadtstraße und
# in ein Rechenzentrum, und die Erklärung („Echo in der Leitung“) hatte kein Bild. Jetzt: Wer telefoniert, hält das Handy ans Ohr (hold „call“)
# und bleibt zu Hause; der Angerufene ist allein in seinem eigenen Zimmer; Technik-Sätze über Echo, Leitung, Lautsprecher und Mikrofon zeigen
# das Schaubild „echo“ (zwei Handys, Stimme hin, Echo zurück) im Wechsel mit dem Handy des Freundes auf laut.
CALL_RE = r"telefon|\banruf|\bruf\w* (?:\w+ ){0,5}an\b|angerufen|auflegen|\blegst (?:\w+ ){0,3}auf\b|aufgelegt|freizeichen|\bhörer\b|am handy|in der leitung|geht ran|gehst ran|nimmt ab|hebt ab|klingelt"
CALL_END_RE = r"\blegst (?:\w+ ){0,4}auf\b|aufgelegt|\bleg\w* (?:\w+ ){0,3}auf\b|verbindung (?:\w+ ){0,6}(?:bricht|abbricht|abgebrochen|weg|tot)|leitung (?:ist |bleibt )?(?:tot|stumm)|freizeichen|anruf (?:ist )?(?:beendet|vorbei)|drückst (?:\w+ ){0,3}weg"
CALL_TRY_END_RE = r"willst (?:\w+ ){0,3}auflegen|auflegen, aber|nicht (?:mehr )?(?:auflegen|beenden)|lässt sich nicht"
CALL_TECH_RE = r"\becho|\bfilter|herausgerechnet|rechnet \w+ (?:\w+ )?heraus|leitung|verzögerung|verzögert|mikrofon|lautsprecher|echo-?unterdrück|schallwelle|signal|zurückgeschickt|zurück zu dir|wieder zurück|laut gestellt|freisprech"
CALL_FILTER_RE = r"echo (?:\w+ ){0,3}stopp|stoppt das echo|verschwind|kein echo|echo (?:ist )?weg|unterdrück|\bfilter|herausgerechnet|rechnet \w+ (?:\w+ )?heraus|löscht|gelöscht|entfern|normalerweise|eigentlich"
CALL_OTHER_RE = (r"\b(?:er|sie) (?:antwortet|geht ran|nimmt ab|hebt ab|meldet sich|sagt|lacht|schwört|schweigt|hört)\b|am anderen ende|bei (?:ihm|ihr)\b|"
                 r"(?:kumpel|freund|freundin|bruder|schwester|mama|mutter|papa|vater)s? (?:\w+ ){0,2}(?:antwortet|geht ran|nimmt ab|hebt ab|meldet sich|sagt|schwört|schläft|hat|hatte|stellt|nimmt|setzt|dreht)|"
                 r"(?:kumpel|freund|freundin)[^.!?]{0,40}kopfhörer|\bsein(?:em|en|e)? (?:handy|lautsprecher|mikrofon|zimmer)|\bihr(?:em|en|e)? (?:handy|lautsprecher|mikrofon|zimmer)")
CALL_START_RE = r"\bruf\w* (?:\w+ ){0,5}an\b|klingelt|geht ran|gehst ran|nimmt ab|hebt ab|\bwählst|nächste[rn]? anruf (?:\w+ ){0,3}(?:kommt|klingelt)"
CALL_FAIL_RE = r"versag|scheiter|schafft (?:\w+ ){0,3}nicht|fällt aus|klappt (?:\w+ ){0,2}nicht|funktioniert (?:\w+ ){0,2}nicht|überfordert"
CALL_OUT_RE = r"straße|draußen|\bstadt\b|\bpark\b|\bbus\b|\bbahn|unterwegs|\bbüro|schule|supermarkt"


def _call_story(scenes, topic="", main_id=""):
    """Geschichte eines Telefonats: siehe Kommentar oben. Greift nur, wenn Thema oder mindestens drei Sätze vom Telefonieren handeln."""
    import re as _re
    dicts = [sc for sc in scenes if isinstance(sc, dict)]
    hits = sum(1 for sc in dicts if _re.search(CALL_RE, str(sc.get("text") or "").lower()))
    if not ((_re.search(r"telefon|\banruf|am handy", str(topic or "").lower()) and hits >= 2) or hits >= 3):
        return
    main_id = str(main_id or "du")
    home = next((places.resolve(sc.get("place")) for sc in dicts if places.resolve(sc.get("place")) in ("bedroom", "livingroom", "kitchen", "hallway")
                 and any(isinstance(a, dict) and str(a.get("id")) == main_id for a in sc.get("actors") or [])), "livingroom")
    other_home = "bedroom" if home != "bedroom" else "livingroom"
    other_id = next((str(a.get("id")) for sc in dicts for a in (sc.get("actors") or []) if isinstance(a, dict) and a.get("id") and not a.get("kind")
                     and str(a.get("id")) != main_id and not str(a.get("id")).startswith("_")), "_freund")
    on, tech_n, last_kind, n_main, ended, last_sub = False, 0, "", 0, False, "-"
    for n, sc in enumerate(scenes):
        if not isinstance(sc, dict):
            continue
        low = str(sc.get("text") or "").lower()
        if _re.search(CALL_START_RE if ended else CALL_RE, low) and not _re.search(CALL_END_RE, low):
            on = True                                     # nach dem Auflegen beginnt ein Anruf nur neu, wenn wirklich wieder gewählt wird („aus dem Telefon kommt …“ ist keiner)
        ending = bool(_re.search(CALL_END_RE, low)) and not _re.search(CALL_TRY_END_RE, low)
        ended = ended or ending
        g_run = 0                                         # wie viele Schaubilder stehen unmittelbar davor – nie drei hintereinander
        while n - g_run - 1 >= 0 and isinstance(scenes[n - g_run - 1], dict) and scenes[n - g_run - 1].get("shot") == "graphic":
            g_run += 1
        if isinstance(sc.get("status"), str) and _re.search(r"läuft|aktiv|verbunden|bereit|live", sc["status"].lower()):
            sc["status"] = ""                             # „TELEFONAT: LÄUFT“ stand bis zum Schluss über der ganzen Erklärung (Video 182)
        g_c = sc.get("graphic") if sc.get("shot") == "graphic" and isinstance(sc.get("graphic"), dict) else None
        if g_c and str(g_c.get("type") or "").lower() == "echo":   # Echo-Schaubild aus dem Drehbuch: Fassung und Überschrift richten sich nach dem Satz („FILTER BOCKT“ über „filtert es heraus“)
            sub_c = "filter" if _re.search(CALL_FILTER_RE, low) and not _re.search(CALL_FAIL_RE, low) else ""
            story_c = bool(_re.search(r"plötzlich|antwortet dir|\bdu hörst\b|\bhörst du\b|erschr|panik|gänsehaut|" + HEADPHONE_RE, low))
            if story_c or g_run >= 2 or (last_kind == "graphic" and last_sub == sub_c):
                sc["graphic"], sc["shot"], g_c = None, "", None   # zweimal dasselbe Schaubild hintereinander oder mitten in der Geschichte: die Szene bekommt ihr Bild
            else:
                sc["graphic"] = {"type": "echo", "sub": sub_c, "kicker": "ECHO-UNTERDRÜCKUNG" if sub_c else "SO ENTSTEHT DAS ECHO"}
                sc["overlay"] = None
                last_sub = sub_c
        if sc.get("shot") == "graphic" and graphics.clean(sc.get("graphic")):
            ov_c, gg_c = sc.get("overlay"), sc.get("graphic")
            if isinstance(ov_c, dict) and str(ov_c.get("text") or "").strip().upper() and str(ov_c.get("text") or "").strip().upper() in " ".join(str(v) for v in gg_c.values()).upper():
                sc["overlay"] = None                      # Stempel „KEIN GEIST“ auf der Plakette „KEIN GEIST“
            if str(gg_c.get("type") or "").lower() != "echo":
                last_sub = "-"
            last_kind = "graphic"
            on = on and not ending
            continue
        if any(isinstance(a, dict) and a.get("kind") for a in sc.get("actors") or []):
            last_kind = ""                                # Gehirn, Tier, Gerät als Figur: gehört einer anderen Regie
            on = on and not ending
            continue
        rp = places.resolve(backdrop(sc)) if not isinstance(backdrop(sc), dict) else "custom"
        tech = bool(_re.search(CALL_TECH_RE, low))
        other = bool(_re.search(CALL_OTHER_RE, low))
        if _re.search(r"plötzlich|antwortet dir|\bdu hörst\b|\bhörst du\b|erschr|panik|gänsehaut", low) and not other:
            tech = False                                  # „Doch plötzlich antwortet dir mit kleiner Verzögerung deine eigene Stimme“ ist die Geschichte, nicht die Erklärung (Video 182)
        if _re.search(r"tonhöhe|frequenz|blechern|dumpf|\bklingt\b", low) and not _re.search(r"\becho|mikrofon|lautsprecher", low):
            tech = False                                  # „Telefone übertragen nur einen Teil der Tonhöhen“, „klingt über die Leitung blechern“: Klang, kein Echo (Video 183 zeigte das Echo-Schaubild)
        phones_tip = bool(_re.search(HEADPHONE_RE, low))
        ov_k = sc.get("overlay")
        if isinstance(ov_k, dict) and _re.search(HEADPHONE_RE, " ".join(str(v) for v in ov_k.values()).lower()) and not phones_tip:
            sc["overlay"] = None                          # Zettel „TIPP: Kopfhörer benutzen!“ einen Satz zu früh
        if phones_tip:
            tech, other = False, True                     # „Bitte deinen Kumpel, Kopfhörer zu nutzen, um das Echo zu stoppen“: der Freund mit Kopfhörern, nicht noch einmal das Echo-Schaubild
        bone = bool(_re.search(r"schädel|knochen", low))
        air = bool(_re.search(r"durch die luft|luftschall|so hören dich|hören dich (?:alle |die )?ander|wie (?:alle )?andere dich hören", low))
        if (bone or air) and n and last_kind != "graphic" and _re.search(r"stimme|\bhör|kling|schall", low):
            sc["graphic"] = {"type": "voice", "sub": "" if bone else "air", "kicker": "SO HÖRST DU DICH SELBST" if bone else "SO HÖREN DICH ANDERE"}
            sc["shot"], sc["overlay"] = "graphic", None    # warum die eigene Stimme fremd klingt: Kopf mit Luft- und Knochenweg statt noch einmal das Wohnzimmer
            last_kind, last_sub = "graphic", "-"
            on = on and not ending
            continue
        sub = "filter" if _re.search(CALL_FILTER_RE, low) and not _re.search(CALL_FAIL_RE, low) else ""   # „versagt die Echo-Unterdrückung“: das Echo kommt durch
        if tech and not (n == 0) and g_run < 2 and (last_kind != "graphic" or (last_sub not in ("-", sub))) and (tech_n % 2 == 0 or not other):
            sc["graphic"] = {"type": "echo", "sub": sub, "kicker": "ECHO-UNTERDRÜCKUNG" if sub else "SO ENTSTEHT DAS ECHO"}
            sc["shot"], sc["overlay"] = "graphic", None
            tech_n, last_kind, last_sub = tech_n + 1, "graphic", sub
            on = on and not ending
            continue
        if tech or other:                                 # beim Angerufenen: allein in seinem Zimmer, Handy in der Hand (auf laut) bzw. am Ohr
            tech_n += 1 if tech else 0
            off = bool(_re.search(r"ausgeschaltet|\bhandy (?:\w+ ){0,4}(?:aus\b|lag\b|liegt\b)|kein(?:en)? (?:anruf|empfang)|gar nicht (?:angerufen|telefoniert)|schlief|schläft|geschlafen", low))
            sc["place"], sc["time"] = other_home, sc.get("time") or "night"
            sc.pop("backdrop", None)
            sc["actors"] = [{"id": other_id, "action": "think" if off else "talk", "speaks": not off, "emotion": "" if not off else "worried", "emote": "?" if off else "",
                             "hold": "" if off else ("phone" if tech or not on or _re.search(HEADPHONE_RE, low) else "call"), "pos": "center", "facing": "", "say": "", "kind": "", "keep": True}]
            if _re.search(HEADPHONE_RE, low):             # „Bitte deinen Freund, Kopfhörer zu nehmen“: er trägt sie, nicht die Anruferin
                sc["actors"][0]["wear"] = "headphones"
            else:
                sc["_no_headphones"] = True
            sc["props"] = [{"type": "phone", "pos": 800}] if off else []
            sc["crowd"], sc["weather"] = "", ""
            sc["shot"] = "" if last_kind in ("other", "close") or off else "close"
            last_kind = "other" if sc["shot"] == "" else "close"
            on = on and not ending
            continue
        humans = [a for a in (sc.get("actors") or []) if isinstance(a, dict) and not a.get("kind")]
        if sc.get("shot") == "insert" and not humans:      # Großaufnahme des Handys bleibt
            last_kind = "insert"
            on = on and not ending
            continue
        elsewhere = rp not in ("bedroom", "livingroom", "kitchen", "hallway", "bathroom") and not _re.search(CALL_OUT_RE, low)
        if elsewhere or not any(str(a.get("id")) == main_id for a in humans) or len(humans) != 1 or sc.get("crowd"):
            if elsewhere or not _re.search(CALL_OUT_RE, low):   # Stadtstraße, Rechenzentrum, Passanten, der Freund im selben Zimmer: wer telefoniert, ist allein zu Hause
                sc["place"] = home
                sc.pop("backdrop", None)
                sc["crowd"], sc["weather"] = "", ""
                me = next((a for a in humans if str(a.get("id")) == main_id), None) or {"id": main_id, "action": "talk", "speaks": True, "emotion": MOOD_EMOTION.get(str(sc.get("mood") or ""), ""),
                                                                                        "emote": "", "say": "", "kind": "", "facing": ""}
                sc["actors"] = humans = [me]
                sc["props"] = [q for q in (sc.get("props") or []) if isinstance(q, dict) and str(q.get("type") or "").lower() not in ("phone", "handy", "smartphone", "display")]
                if sc.get("shot") in ("event", "insert"):
                    sc["shot"] = ""
        me = next((a for a in humans if str(a.get("id")) == main_id), None)
        if me is not None and len(humans) == 1 and not str(me.get("hold") or "").startswith("prop:") and str(me.get("action") or "") not in ("sleep", "fall", "run", "sit"):
            after = not on or ending
            me["hold"] = "phone" if after else "call"      # nach dem Auflegen starrt sie aufs Handy in der Hand
            if ended and not ending:                      # die Erklärung danach: kein Dauer-Schreck mehr (Video 182: bis zum „beruhigt“ am Schluss erschrocken)
                calm = bool(_re.search(r"beruhig|keine sorge|entspann|jetzt weißt du|weißt du jetzt|ganz normal|harmlos|kein grund", low))
                scary = bool(_re.search(r"erschr|schreck|panik|gänsehaut|unheimlich|grusel|\bangst", low))
                if not scary:
                    me["emotion"] = "happy" if calm else ("worried" if "?" in str(sc.get("text") or "") else "")
                    me["emote"] = "?" if "?" in str(sc.get("text") or "") else ""
                    if str(me.get("action") or "") in ("shocked", "scared", "freeze"):
                        me["action"] = "talk"
                    if str(sc.get("mood") or "") in ("scary", "panic", "tense"):
                        sc["mood"] = "calm"
            if str(me.get("action") or "") == "walk" or me.get("to"):
                me["action"] = "shocked" if _re.search(r"erschr|schreck|erstarr|panisch|gänsehaut|zuck", low) else "talk"
                me.pop("to", None)
            if _re.search(r"erschr|schreck|erstarr|panisch|gänsehaut|zuck|deine eigene stimme|dich selbst", low) and on:
                me["emotion"] = "scared"
            me["pos"] = (540, 410, 670, 540)[n_main % 4]   # nicht ganz an den Rand: mit Kamerafahrt war die Figur links halb abgeschnitten (Video 183)
            me["facing"] = {410: "right", 670: "left"}.get(me["pos"], "")
            if str(me.get("action") or "") in ("cower", "fall", "freeze", "look_around", "sit", "sleep") and me["hold"] == "call":
                me["action"] = "shocked"                  # geduckt rutscht das Handy vors Auge; wer das Handy am Ohr hat, steht
            n_main += 1
            sc["props"] = [q for q in (sc.get("props") or []) if isinstance(q, dict) and str(q.get("type") or "").lower() not in ("phone", "handy", "smartphone")]
            if sc.get("shot") == "close" and last_kind == "close":
                sc["shot"] = ""
            elif sc.get("shot") in ("", None) and last_kind == "wide":
                sc["shot"] = "close"
            last_kind = "close" if sc.get("shot") == "close" else "wide"
        else:
            last_kind = ""
        on = on and not ending


# Misch-Wesen (Prüfung 19.11.2026, Video 152 „Super-Tier aus vier Arten“): Das Video handelt von einem Wesen, das aus mehreren Tieren gebaut wird.
# Vorher war dieses Wesen nie zu sehen – stattdessen ein Blauwal unter Wasser (auch im ersten Bild „im Labor“), Passanten zum „Haufen Zellen“,
# drei Waagen auf der Straße. Jetzt: Sätze über das Wesen zeigen das gezeichnete Misch-Wesen (extras.creature „chimera“) im Labor neben der
# Hauptfigur bzw. rennend in der Savanne; Sätze, die ein Tier beim Namen nennen, behalten dieses Tier in seinem Lebensraum (höchstens ein Folgesatz).
HYBRID_RE = (r"super-?tier|mischwesen|misch-wesen|hybrid-?(?:tier|wesen)|chimäre|tier-?mix|wesen aus \w+ (?:verschiedenen )?(?:tier)?arten|tier aus \w+ (?:verschiedenen )?(?:tier)?arten|"
             r"(?:tiere|tierarten) (?:zu einem|in einem) (?:\w+ )?(?:wesen|tier)|aus (?:mehreren|verschiedenen|vier|drei|fünf) tieren")
HYBRID_BEING_RE = r"super-?tier|\bwesen\b|\bmonster|\bbiest|\bkreatur|mischwesen|chimäre|geschöpf|unser tier\b|dein tier\b|\bbauplan|\bbaukasten"
HYBRID_FAIL_RE = r"bricht\b.*zusammen|zusammenbr|kollabier|überhitz|\bversagt|\bstirbt|\bkippt um|\bfällt um|klappt zusammen|macht schlapp|\bschlapp\b|geht k\.?o|am ende seiner kräfte|kann es nicht|schafft es nicht"
HYBRID_HOME = {"cheetah": "savannah", "lion": "savannah", "eagle": "mountain", "tardigrade": "forest", "flea": "park", "cow": "fields", "pig": "farm", "chimp": "forest"}
HYBRID_RUN_RE = r"\brenn|\bsprint|\brast\b|\bjagt\b|km/h|kilometer\w* pro stunde|stundenkilometer|\bbeschleunig"


# „Lauf diese Runde“, „du rennst durch den Park“: die Figur läuft die ganze Szene – sie kommt nicht ins Bild und steht dann vier Sekunden da (Video 173)
JOG_RE = r"(?:^|[.!?,:;] |\bund )\s*(?:lauf|laufe|renn|renne|jogg|jogge|sprinte)\b|\bdu (?:läufst|rennst|joggst|sprintest)\b|\b(?:läufst|rennst|joggst|sprintest) du\b"


SPEECH_PANIC_RE = r"panik|\bangst|fürcht|erschr|schock|zitter|albtraum|gefahr|bedroh"


def _speech(scenes, style=""):
    """Motivationsrede (Prüfung 21.11.2026, Videos 173/174): Die Rede geht an „du“ – in jedem Bild steht die Hauptfigur, keine Menschenmenge
    rennt durchs Büro, wenn der Satz vom konzentrierten Lernen spricht, kein leeres Bild mit einem Felsbrocken. Das große Wort steht über dem
    Kopf, deshalb gibt es dort keine Zeichen (!, ?). Für alle Videos: Wer im Bett am Handy scrollt, schläft nicht; eine Wanduhr steht nur im
    Bild, wenn der Satz von Uhr oder Zeit spricht."""
    speech = str(style or "").lower() == "motivation"
    main = next((str(a.get("id")) for sc in scenes if isinstance(sc, dict) for a in (sc.get("actors") or [])
                 if isinstance(a, dict) and str(a.get("id") or "").lower() in MAIN_IDS), "du")
    for sc in scenes:
        if not isinstance(sc, dict) or str(sc.get("shot") or "") == "graphic":
            continue
        low = str(sc.get("text") or "").lower()
        acts = [a for a in (sc.get("actors") or []) if isinstance(a, dict)]
        for a in acts:                                    # „weicht erschrocken zurück“ kam als „fall“: die Figur lag reglos am Boden, obwohl niemand stürzt (Video 192)
            if not a.get("kind") and str(a.get("action") or "") == "fall" and not re.search(FALL_SAID_RE, low + " " + str(sc.get("see") or "").lower()):
                a["action"] = "shocked"
        for a in acts:
            see_low = str(sc.get("see") or "").lower()
            awake_re = r"scroll|handy|smartphone|bildschirm|\bfeed\b|wach\b|nicht schlafen|tippst|chattest"
            if not a.get("kind") and len(acts) == 1 and str(a.get("action") or "idle").lower() in ("", "idle", "talk", "walk", "sit", "think", "look_around") \
                    and re.search(r"\blieg\w*\b.{0,40}\bim bett\b|\bim bett\b.{0,30}\blieg", low) and re.search(awake_re + r"|starrst", low) \
                    and not re.search(r"schläfst|eingeschlafen|schlummer|\bnicht\b.{0,12}\bim bett\b|aufsteh|stehst auf", low) \
                    and not isinstance(backdrop(sc), dict) and places.resolve(backdrop(sc)) == "bedroom" and str(sc.get("shot") or "") in ("", "wide"):
                a.update(action="sleep", pos="center")    # „Nachts liegst du wach im Bett und starrst auf das Handy“: die Figur lief mit dem Handy durchs Schlafzimmer (Video 217)
                a.pop("to", None)
            if not a.get("kind") and str(a.get("action") or "") == "sleep" \
                    and (re.search(awake_re, low) or (re.search(awake_re + r"|starrst", see_low) and not re.search(r"schläf|schlaf(?!zimmer)|träum", low + " " + see_low))) \
                    and not re.search(r"schläfst|eingeschlafen|schlummer|nachttisch|vibriert|klingelt|brummt|summt|leuchtet auf", low):   # „Dein Handy vibriert auf dem Nachttisch“: es liegt dort, die Figur schläft (Video 192)
                if not isinstance(backdrop(sc), dict) and places.resolve(backdrop(sc)) == "bedroom":
                    a.update(_awake=True, emote="", emotion="")       # liegt wach im Bett am Handy: Augen offen, Handy vor dem Gesicht, kein „zzz“ (Video 216: auch wenn nur der Bildplan das Handy nennt)
                else:
                    a.update(action="idle", hold="phone", emote="")   # nicht im Schlafzimmer: steht wach mit dem Handy da
        if isinstance(sc.get("props"), list) and not re.search(r"\buhr|wecker|\bzeit|spät|stunde|minute|sekunde|tick|pünktlich|countdown|frist", low):
            sc["props"] = [q for q in sc["props"] if str((q.get("type") if isinstance(q, dict) else q) or "").lower() not in ("clock", "uhr", "wanduhr")]
        if re.search(r"handy|smartphone|telefon", low) and re.search(r"bleibt\b.{0,40}\b(zimmer|draußen|liegen|weg|aus)\b|\bim (?:anderen|nächsten) zimmer|nebenzimmer|\bleg\w*\b.{0,30}\bweg\b|ohne (?:dein |das )?(?:handy|smartphone)|aus der hand", low):
            for a in acts:                                # „Das Handy bleibt im anderen Zimmer liegen“: dann hält es niemand in der Hand (Video 175)
                if str(a.get("hold") or "").lower() in ("phone", "handy", "smartphone"):
                    a["hold"] = ""
            if isinstance(sc.get("props"), list):
                sc["props"] = [q for q in sc["props"] if str((q.get("type") if isinstance(q, dict) else q) or "").lower() not in ("phone", "handy", "smartphone")]
        if re.search(r"\bspeicher\w*\s+(?:dir|es|das|dies\w*|ab)\b|abspeicher|gespeichert|\bspeichern\b", low) and not re.search(r"dachboden|auf dem speicher|im speicher|auf den speicher", low) \
                and not isinstance(backdrop(sc), dict) and places.resolve(backdrop(sc)) == "attic":
            prev_sc = next((q for q in reversed(scenes[:scenes.index(sc)]) if isinstance(q, dict) and str(q.get("shot") or "") != "graphic"), None)
            if prev_sc is not None:                       # „Speicher dir das“ meint Merken, nicht den Dachboden (Video 175)
                sc["place"], sc["backdrop"], sc["time"] = prev_sc.get("place"), prev_sc.get("backdrop"), prev_sc.get("time") or sc.get("time")
        if "speicher" in low and "dachboden" not in low and (_CTX["mem"] or re.search(COMPUTER_MEM_RE, low)) \
                and not isinstance(backdrop(sc), dict) and places.resolve(backdrop(sc)) == "attic":
            prev_sc = next((q for q in reversed(scenes[:scenes.index(sc)]) if isinstance(q, dict) and str(q.get("shot") or "") != "graphic"
                            and not isinstance(backdrop(q), dict) and places.resolve(backdrop(q)) in ROOMS and places.resolve(backdrop(q)) != "attic"), None)
            # „freie Stellen im Speicher“ in einem Video über Computerspeicher: der Raum von eben, nicht der Dachboden (Video 178)
            sc["place"], sc["backdrop"] = (prev_sc.get("place"), prev_sc.get("backdrop")) if prev_sc is not None else ("office", None)
            sc["time"] = (prev_sc.get("time") if prev_sc is not None else "") or sc.get("time")
        if not speech:
            continue
        if sc.get("crowd") and not re.search(PEOPLE_RE + r"|publikum|zuschauer|\bmenge\b", low):
            sc["crowd"] = ""
        if (str(sc.get("mood") or "") == "panic" or sc.get("_unpanic")) and not re.search(SPEECH_PANIC_RE, low):
            sc["mood"] = "" if str(sc.get("mood") or "") == "panic" else sc.get("mood")
            for a in acts:
                if str(a.get("emotion") or "") in ("scared", "shocked") or str(a.get("action") or "") in ("shocked", "scared", "shiver", "cower"):
                    a["emotion"] = ""
                    a["action"] = "idle" if str(a.get("action") or "") in ("shocked", "scared", "shiver", "cower") else a.get("action")
        if not acts and str(sc.get("shot") or "") in ("", "event") and not sc.get("float"):
            sc["actors"] = acts = [{"id": main, "action": "idle", "pos": "left" if sc.get("props") else "center", "emotion": MOOD_EMOTION.get(str(sc.get("mood") or ""), "")}]
            sc["shot"] = ""
        if acts:
            sc["_no_insert"] = True                       # „Du stehst vor der Tür“: drei Sekunden nur die Tür vor braunem Grund (Video 217) – der Schnitt geht auf die Figur, nicht auf ein Ding allein
        for a in acts:
            a["emote"] = "none"                           # das große Wort steht über dem Kopf – dort kein Zeichen
            if str(a.get("hold") or "").lower() in ("rock", "table", "shelf", "streetlamp", "box", "door", "sofa", "bed", "tree") \
                    and not re.search(r"fels|stein|brocken|geröll|tisch|regal|laterne|karton|kiste|\btür|sofa|couch|bett|baum|heb|trag|stemm|schlepp", low):
                held_s = str(a["hold"]).lower()           # „Der perfekte Moment kommt niemals“: die Figur hielt am Berg einen Felsbrocken in der Hand (Video 217)
                a["hold"] = ""
                if isinstance(sc.get("props"), list):
                    sc["props"] = [q for q in sc["props"] if str((q.get("type") if isinstance(q, dict) else q) or "").lower() != held_s]
            if not a.get("kind") and str(a.get("hold") or "") and str(a.get("action") or "").lower() in ("jump", "happy", "cheer", "dance", "wave"):
                a["action"] = "idle"                      # beide Arme oben: die Hantel in der Hand lag quer über dem großen Wort (Video 216) – gehalten wird vor dem Körper
                a["emotion"] = a.get("emotion") or "happy"


def _jogging(scenes):
    for sc in scenes:
        if not isinstance(sc, dict) or str(sc.get("shot") or "") in ("graphic", "insert", "close") or sc.get("float"):
            continue
        low = str(sc.get("text") or "").lower()
        acts = [a for a in (sc.get("actors") or []) if isinstance(a, dict)]
        see_jog = str(acts[0].get("action") or "").lower() == "run" and re.search(r"\bdu (?:läufst|rennst|joggst|sprintest)\b", str(sc.get("see") or "").lower()) if len(acts) == 1 else None
        # „Zieh die Laufschuhe an und lauf zwei Minuten“ / Bildplan „Du rennst durch den Park“: die Figur kam hereingerannt und stand dann da (Video 217)
        if len(acts) != 1 or acts[0].get("kind") or not (re.search(JOG_RE, low) or see_jog) or re.search(r"\bnicht\b.{0,12}\b(lauf|renn)|davon|\bweg\b|läuft (?:gut|schlecht|schief|ab)", low):
            continue
        bd = backdrop(sc)
        if not isinstance(bd, dict) and places.resolve(bd) not in places.OUTDOOR:
            continue
        acts[0].update(action="run", pos=190, to=890, _jog=True, hold="", facing="")
        if str(acts[0].get("emote") or "") in ("x", "?", "anger"):
            acts[0]["emote"] = ""
        if str(acts[0].get("emotion") or "") in ("angry", "sad", "worried", "scared"):
            acts[0]["emotion"] = ""                       # entschlossen, nicht wütend
        sc["props"] = [q for q in (sc.get("props") or []) if isinstance(q, dict) and q.get("pos") in (None, "")][:1]
        if str(sc.get("mood") or "") in ("tense", "panic", "sad") and str(sc.get("time") or "") != "night":
            sc["mood"] = ""                               # Lauf am Tag: helles Bild, kein Halbdunkel mit Lichtkegel


def hybrid_story(scenes, topic=""):
    return bool(re.search(HYBRID_RE, str(topic or "").lower()))


def _hybrid_named(low):
    """Welches zeichenbare Tier nennt der Satz beim Namen?"""
    for pat, k in ANY_CREATURES + SEA_CREATURES:
        if re.search(pat, low):
            return k
    for pat, k, _pl in NAMED_ANIMALS:
        if re.search(pat, low):
            return k
    for pat, k in TOPIC_CREATURES:
        if k in ("lion", "cat", "dog", "spider", "bee", "wasp", "shark", "fish", "dino") and re.search(pat, low):
            return k
    return None


def _hybrid_story(scenes, topic="", main_id="du"):
    if not hybrid_story(scenes, topic):
        return scenes
    last_named, flip, n_lab, fallen = None, False, 0, False
    wild = ("space", "snow", "desert", "underwater", "mountain", "savannah", "forest", "fields", "highsky", "beach", "cave", "icesea", "lake", "river", "moon")

    def animal(sc, kind, low, keep_place=True):
        """Das genannte Tier allein in seinem Lebensraum – nicht im Labor (der Adler flog zwischen den Kolben, Video 153)."""
        rp = places.resolve(backdrop(sc)) if not isinstance(backdrop(sc), dict) else "custom"
        hint = _hint(low)
        home = HYBRID_HOME.get(kind) or ("underwater" if kind in SEA_KINDS + ("fish", "shark", "dolphin") else "")
        if kind in SEA_KINDS + ("fish", "shark", "dolphin"):
            place = "underwater"
        elif hint in wild and hint != "underwater":
            place = hint
        elif keep_place and (rp == "custom" or (rp in wild and rp != "underwater")):
            place = rp                                    # Schnee, Wüste, eigene Landschaft aus dem Drehbuch bleiben
        else:
            place = home or rp
        act = next((a for a in (sc.get("actors") or []) if isinstance(a, dict) and str(a.get("kind") or "").lower() == kind), None)
        act = dict(act or {"id": "_tier", "speaks": False, "emote": "", "say": "", "hold": "", "action": "idle",
                           "emotion": MOOD_EMOTION.get(str(sc.get("mood") or ""), "")}, kind=kind, hero=True, pos="center", facing="right")
        act.pop("to", None)
        if kind == "cheetah" and re.search(HYBRID_RUN_RE + r"|\bschnell", low):
            act.update(action="run", emotion="")
        if place != rp:
            sc.update(place=place, backdrop=None, weather="", time="night" if place == "space" else "day")
        sc.update(actors=[act], crowd="", float="", props=[q for q in (sc.get("props") or []) if place == rp and isinstance(q, dict)
                                                           and extras.PROP_ALIASES.get(str(q.get("type")).lower(), str(q.get("type")).lower()) in extras.SKY][:1])
        if sc.get("shot") in ("event", "insert", "close"):
            sc["shot"] = ""
        if kind == "tardigrade" and place in ("forest", "park"):   # der Winzling stand baumhoch im Wald (Videos 152–155): klein am Moospolster
            act.update(hero=False, pos=430)
            sc["props"] = [{"type": "moss", "pos": 650}]

    for i, sc in enumerate(scenes):
        if not isinstance(sc, dict):
            continue
        low = str(sc.get("text") or "").lower()
        sc["crowd"] = ""
        named = _hybrid_named(low)
        being = bool(re.search(HYBRID_BEING_RE, low))
        fail = bool(re.search(HYBRID_FAIL_RE, low))
        acts = [a for a in (sc.get("actors") or []) if isinstance(a, dict)]
        ov_h = sc.get("overlay") if isinstance(sc.get("overlay"), dict) else None
        if ov_h and str(ov_h.get("type") or "") == "counter" and not str(ov_h.get("label") or "").strip() and re.search(r"\bminus\b", low) \
                and re.search(r"grad", str(ov_h.get("unit") or "").lower()):
            ov_h["label"] = "MINUS"                       # „minus zweihundert Grad“ stand als „200 GRAD“ im Bild
        if sc.get("shot") == "graphic" and graphics.clean(sc.get("graphic")):
            if last_named:
                last_named = (last_named[0], i)           # die Zahl gehört noch zum Tier von eben: der Satz danach („Seine eigentliche Stärke …“) meint es weiter
            continue
        if named and not fail and not (being and i == 0):
            animal(sc, named, low)                        # „… die Augen vom Adler“: der Adler in seinem Lebensraum
            last_named, n_lab = (named, i), 0
            continue
        near = bool(last_named and i - last_named[1] == 1 and not re.search(HUMAN_RE, low)
                    and not re.search(r"^(?:aber|doch|jetzt|dann|nun|und am ende|am ende)\b|superkr|\bpreis|\bhaken|\bzutat|evolution|\bnatur\b", low))   # „In freier Wildbahn wurden 93 km/h gemessen“ direkt nach dem Gepard-Satz meint den Gepard (Video 154: das Wesen rannte)
        follow = bool(last_named and i - last_named[1] <= 2 and not being and not fail
                      and (near or re.search(r"^(?:es|er|sie|seine?|ihre?|dieses tier|dieser|im jahr|sogar|dabei|damit|und (?:es|er|sie))\b", low))
                      and not (re.search(r"\bherz", low) and last_named[0] != "whale"))
        if follow:
            animal(sc, last_named[0], low, keep_place=False if _hint(low) is None and i - last_named[1] == 0 else True)   # Folgesätze bleiben beim Tier von eben
            if scenes[last_named[1]] is not sc and isinstance(scenes[last_named[1]], dict) and scenes[last_named[1]].get("shot") != "graphic" \
                    and places.resolve(backdrop(sc)) == places.resolve(backdrop(scenes[last_named[1]])) and i - last_named[1] == 1:
                sc["actors"][0]["facing"] = "left"        # derselbe Ort wie eben: wenigstens gespiegelt
            n_lab = 0
            continue
        last_named = None
        fallen = fallen or fail
        run = bool(re.search(HYBRID_RUN_RE, low)) and not fail
        human = next((a for a in acts if not a.get("kind") and not str(a.get("id") or "").startswith("_")), None)
        cells = bool(re.search(r"\bzellen\b|zellhaufen|\bhaufen\b", low))
        lying = fail or cells or (fallen and "?" not in str(sc.get("text") or ""))   # einmal zusammengebrochen, bleibt es liegen – bis zur Schlussfrage
        beast = {"id": "_tier", "kind": "chimera", "speaks": False, "emote": "", "say": "", "hold": "",
                 "action": "down" if lying else "run" if run else "idle",
                 "emotion": "sad" if lying else MOOD_EMOTION.get(str(sc.get("mood") or ""), "")}
        if sc.get("shot") == "close" and human and not being and i > 0 and n_lab >= 1:
            sc.update(place="lab", time="day", backdrop=None, weather="", props=[], float="", actors=[human])
            n_lab += 1
            continue                                      # „Falsch, denn …“: die Großaufnahme der Hauptfigur bleibt als Abwechslung
        if run:
            sc.update(place="savannah", time="day", backdrop=None, weather="", props=[], float="", shot="",
                      actors=[dict(beast, pos="center", facing="right", hero=True)])
            n_lab = 0
            continue
        me = dict(human or {"id": main_id, "speaks": False, "emote": ""})
        me.pop("to", None)
        me["hold"] = ""
        if str(me.get("action") or "") in ("", "idle", "walk", "run", "sit", "sleep", "fall", "float", "jump", "cower", "swim", "lie"):
            me["action"] = "shocked" if fail or cells else "point" if being else "think"
        if lying:
            me.update(emotion="sad", emote="")
        flip = not flip                                   # abwechselnd links/rechts; das breite Wesen steht mit Abstand neben der Figur, Kopf nach außen
        me["pos"], me["facing"] = (230, "right") if flip else (850, "left")   # nicht am Rand: die Kamera schnitt die Figur sonst an (Video 153)
        beast.update(pos=730 if flip else 350, facing="right" if flip else "left")
        sc.update(place="lab", time="day", backdrop=None, weather="", props=[], float="", shot="", actors=[me, beast], _no_cut=True, cam_move="push" if n_lab % 2 else "pull")   # Figur und breites Wesen füllen das Bild: kein Schwenk, kein näherer Gegenschnitt (schnitt die Figur an)
        if str(sc.get("mood") or "") in ("scary", "panic"):
            sc["mood"] = "tense"
        n_lab += 1
    return scenes


FALL_SAID_RE = (r"\b(?:hin|um|herunter|hinunter|runter|ab|herab)?f[aä]ll(?:t|st|en)\b|\b(?:hin|um|herunter|runter|ab)gefallen|stürz|sturz|stolper|kipp|ohnmächt|ohnmacht|bewusstlos|\bboden\b|rutsch|zusammenbr|zusammensack|sackst|taumel|schleuder|umgeworfen|umgehauen|"
                r"wirft|geworfen|purzel|plumps|landest|landet|auf die knie|k\.o\.|umgekippt|hinunter|herunter|in die tiefe|abgrund|schwerelos|erdbeben|explo|druckwelle")
DOOR_OPEN_RE = (r"tür\w*\b[^.!?]{0,60}\b(?:springt|geht|gehen|schwingt|fliegt|kracht|bricht|reißt|steht|stand|öffnet|öffnen)\b[^.!?]{0,40}\b(?:auf|offen|sich)\b|"
                r"(?:springt|schwingt|fliegt|bricht)\b[^.!?]{0,60}tür\w*\b[^.!?]{0,40}\bauf\b|öffne\w*\b[^.!?]{0,30}\btür|\boffene\w* \w*tür|tür\w* (?:ist|steht|bleibt) (?:weit )?offen|"
                r"tür\w* öffnet sich|hinter der \w*tür\w* (?:ist|liegt|wartet|steht|leuchtet|strahlt)")
DOOR_SHUT_RE = r"schließ|zugeschlagen|schlägt zu|fällt (?:\w+ )?zu\b|fällt ins schloss|verriegel|verschließ|wieder zu\b"


def _door_story(scenes):
    """Springt eine Tür auf, steht sie offen – auch in den folgenden Sätzen am selben Ort, bis sie jemand schließt (Video 192: „Das Schloss der
    Dachbodentür springt von alleine auf“ zeigte eine geschlossene Tür). Verneint („öffne niemals die Tür“) zählt nicht."""
    import re as _re
    open_at = None
    for sc in scenes:
        if not isinstance(sc, dict):
            continue
        low = str(sc.get("text") or "").lower()
        pl = places.resolve(backdrop(sc))
        if _re.search(DOOR_SHUT_RE, low) or (open_at is not None and pl != open_at):
            open_at = None
        if _re.search(DOOR_OPEN_RE, low) and not _re.search(r"\bnie\b|niemals|\bnicht\b|\bkein|\bob\b|würdest|\?|verschlossen|lässt sich nicht", low):
            open_at = pl
        if open_at is not None and any(extras.PROP_ALIASES.get(str(q.get("type")).lower(), str(q.get("type")).lower()) == "door" for q in (sc.get("props") or []) if isinstance(q, dict)):
            sc["_door_open"] = True


def _stems(text):
    import re as _re
    return {w[:5] for w in _re.findall(r"[a-zäöüß]{4,}", str(text or "").lower())}


MINIMAP_RE = r"\bmini-?maps?\b|\bmini-?karten?\b|\bmini-?radar\b"


def _map_hud(scenes):
    """Mini-Karte und Karten-Markierungen (Ausbau 25.11.2026) schweben beide mitten im Bild – zusammen verdecken sie einander, und die Karte
    rutscht an den Rand. Stehen beide in einer Szene, bleibt nur eines: die Mini-Karte, wenn der Satz sie nennt, sonst die Markierungen."""
    import re as _re
    for sc in scenes:
        if not isinstance(sc, dict):
            continue
        keys = [extras.PROP_ALIASES.get(str(q.get("type")).lower(), str(q.get("type")).lower()) for q in (sc.get("props") or []) if isinstance(q, dict)]
        if "minimap" in keys and "markers" in keys:
            drop = "markers" if _re.search(MINIMAP_RE, str(sc.get("text") or "").lower()) else "minimap"
            sc["props"] = [q for q in sc["props"] if not (isinstance(q, dict) and extras.PROP_ALIASES.get(str(q.get("type")).lower(), str(q.get("type")).lower()) == drop)]


def _last_look(scenes, topic=""):
    """Letzter Blick auf die Einblendungen und Großaufnahmen (Prüfung 18.11.2026, Video 144 „Nachbarn“):
    – dieselbe Zahl als Zähler in zwei Sätzen hintereinander („44 STUNDEN“ zählt zweimal von null hoch): der zweite entfällt;
    – Abhak-Liste, von deren Punkten der Sprecher keinen nennt („Geld / Gurken“ zu „drohen mit Mietminderung“): entfällt;
    – Schild, dessen Wörter weder im Satz noch in den Nachbarsätzen noch im Thema vorkommen („NACHTSCHICHT“): entfällt;
    – eine Tür allein vor leerem Farbgrund ist keine Großaufnahme: sie fällt aus dem Einschub heraus."""
    sc_l = [sc for sc in scenes if isinstance(sc, dict)]
    main = next((str(a.get("id")) for sc in sc_l for a in (sc.get("actors") or []) if isinstance(a, dict) and a.get("id") and not a.get("kind")), "du")
    prev_val = None
    for i, sc in enumerate(sc_l):
        ov = sc.get("overlay") if isinstance(sc.get("overlay"), dict) else None
        ov_t = str((ov or {}).get("type") or "")
        g = sc.get("graphic") if isinstance(sc.get("graphic"), dict) and sc.get("shot") == "graphic" else None
        val = None
        if ov_t == "counter":
            val = ("n", str(ov.get("value")), str(ov.get("unit") or "").upper())
        elif g and str(g.get("type") or "") in ("number", "counter"):
            val = ("n", str(g.get("value")), str(g.get("unit") or "").upper())
        if val and prev_val and val[1] == prev_val[1] and ov_t == "counter":
            sc["overlay"], ov, ov_t = None, None, ""
        prev_val = val
        near = _stems(" ".join(str(x.get("text") or "") for x in sc_l[max(0, i - 1):i + 2]))
        if ov_t == "checklist":
            items = [str(it[0] if isinstance(it, (list, tuple)) and it else it) for it in (ov.get("items") or [])]
            if items and not any(_stems(it) & near for it in items):
                sc["overlay"], ov, ov_t = None, None, ""
        if ov_t == "choice":                              # Auswahl nur an einer einzelnen Frage oder einem „oder“ – nicht zehn Sekunden „NACHSCHLAG KOMMT / VIERTER TYP“ über drei Schlusssätzen (Video 150)
            txt_c = str(sc.get("text") or "").strip()
            if not re.search(r"\boder\b", txt_c.lower()) and len([x for x in re.split(r"(?<=[.!?])\s+", txt_c) if x.strip()]) > 1:
                sc["overlay"], ov, ov_t = None, None, ""
        if ov_t == "tag":
            words = _stems(ov.get("text"))
            if words and not (words & (near | _stems(topic))):
                sc["overlay"], ov, ov_t = None, None, ""
        if str(sc.get("shot") or "") == "insert":
            props = [q for q in (sc.get("props") or []) if isinstance(q, dict)]
            rest = [q for q in props if extras.PROP_ALIASES.get(str(q.get("type")).lower(), str(q.get("type")).lower()) != "door"]
            if len(rest) != len(props):
                if rest:
                    sc["props"] = rest
                else:
                    sc["shot"] = ""
                    if not [a for a in (sc.get("actors") or []) if isinstance(a, dict)]:
                        sc["actors"] = [{"id": main, "action": "point", "pos": "left", "speaks": True}]


ROOMS = ("bedroom", "livingroom", "diningroom", "kitchen", "office", "classroom", "mathroom", "lab", "bathroom", "hallway", "basement", "attic")
OUTSIDE_RE = r"bauernhof|\bhof\b|\bfeld|wiese|draußen|\bgarten|\bwald|strand|straße|\bstadt|\bdorf|\bpark\b|\bberg|\bmeer|\bsee\b|himmel|wüste|\bland\b"
BODY_PROPS = ("auge", "augen", "ohr", "ohren", "nase", "zahn", "zähne", "finger", "muskel", "muskeln")
BIG_M = 4.0                                               # Bibliotheks-Dinge ab dieser echten Höhe (Schloss, Wasserturm, Gebäude, Achterbahn) stehen in keinem Zimmer


def _indoor_sense(scenes):
    """Schlussdurchgang: In einem Zimmer steht nichts Haushohes aus der Bibliothek. Die Text-KI stellt zu „schaltet die Muskeln ab“ ein „Schloss“
    (gemeint: Vorhängeschloss) ins Schlafzimmer – gezeichnet wird das Märchenschloss neben dem Bett."""
    for sc in scenes:
        if not isinstance(sc, dict) or isinstance(backdrop(sc), dict) or places.resolve(backdrop(sc)) not in ROOMS:
            continue
        keep = []
        has_human = any(isinstance(a, dict) and not a.get("kind") and not re.search(r"gehirn|hirn|brain", str(a.get("id") or "").lower()) for a in sc.get("actors") or [])
        for q in sc.get("props") or []:
            k = str((q.get("type") if isinstance(q, dict) else q) or "").lower()
            if has_human and k.replace("lib_", "") in BODY_PROPS:
                continue                                  # ein einzelnes Auge auf dem Nachttisch neben der Figur („nur Augen und Atmung arbeiten weiter“): die Figur hat selbst Augen
            k = extras.PROP_ALIASES.get(k, k)
            if max(float(extras.REAL_M.get(k, 0) or 0), float(extras.REAL_M.get("lib_" + k, 0) or 0)) >= BIG_M:
                continue
            keep.append(q)
        if len(keep) != len(sc.get("props") or []):
            sc["props"] = keep
            if str(sc.get("shot") or "") == "insert" and not keep:
                sc["shot"] = ""


# Paar-Videos (Prüfung 23.11.2026, 13-Uhr-Termin, „3 Zeichen, dass deine Situationship in dich verliebt ist“ – Video 190): zur Redensart „über alle Ohren
# verliebt“ lag ein einzelnes Ohr auf der Wiese zwischen den beiden; zum Satz über Eifersucht drängten sich drei erschrockene Fremde mit Ausrufezeichen zwischen
# das Paar im Restaurant; Sätze ohne Figuren im Drehbuch zeigten eine einzelne Figur, die ins leere Wohnzimmer läuft, obwohl es um die beiden geht.
BODY_IDIOM_RE = (r"über (?:beide|alle) ohren|ganz ohr\b|ohren spitz|übers ohr|aufs ohr|hinter die ohren|ins auge (?:fass|stech|spring|fall)|auge zudrück|unter vier augen|"
                 r"aus den augen|im auge behalt|ein auge auf|augen auf\b|auf den zahn|zahn der zeit|nase voll|an der nase|nase vorn|der nase nach|finger weg|um den finger|"
                 r"keinen finger|finger im spiel|muskeln spielen")
PAIR_CROWD_RE = r"\balle\b|\bleute|menschen|\bmenge\b|publikum|zuschauer|gäste|passanten|\bvoll\b|überfüllt|gedränge|fremde|kellner|\bjeder\b|andere[nr]?\b"
PAIR_FULL_RE = r"\bvoll(?:e[nrs]?)?\b|überfüllt|gedränge|\bgäste|kellner|publikum|zuschauer|\bmenge\b|alle (?:schauen|starren|gucken|sehen|drehen)|leute (?:schauen|starren|gucken|drehen)"
PAIR_QUIET = ("restaurant", "office", "classroom", "hospital", "chapel")


def _pair_sense(scenes, style=""):
    """Schlussdurchgang für Szenen mit Menschen: (1) Ein loses Körperteil aus der Bibliothek (Ohr, Auge, Nase, Zahn, Finger) liegt nie neben einer Figur –
    sie hat selbst Ohren; bei einer Redensart („über alle Ohren verliebt“) auch nicht allein im Bild. (2) Stehen zwei benannte Figuren im Bild, drängt sich
    keine erschrockene oder gaffende Menge dazu, wenn der Satz weder von Leuten noch von Panik spricht; im Restaurant, Büro, Klassenzimmer laufen auch keine
    Fremden zwischen den beiden durch. (3) Liebes-Videos handeln vom Paar: Läuft in einem Satz ohne Figuren nur eine Figur ins Zimmer, stehen beide da und
    reden miteinander."""
    pair = []
    if str(style or "") == "liebe":
        seen = {}
        for sc in scenes:
            if isinstance(sc, dict) and str(sc.get("shot") or "") not in ("graphic", "insert"):
                ids = [str(a.get("id")) for a in sc.get("actors") or [] if isinstance(a, dict) and a.get("id") and not a.get("kind")]
                if len(ids) == 2 and ids[0] != ids[1]:
                    seen[tuple(ids)] = seen.get(tuple(ids), 0) + 1
        if seen:
            pair = list(max(seen, key=lambda k_: seen[k_]))
            pair = pair if seen[tuple(pair)] + seen.get((pair[1], pair[0]), 0) >= 2 else []
    n_fill = 0
    for sc in scenes:
        if not isinstance(sc, dict):
            continue
        shot = str(sc.get("shot") or "")
        low = str(sc.get("text") or "").lower()
        humans = [a for a in sc.get("actors") or [] if isinstance(a, dict) and not a.get("kind") and not re.search(r"gehirn|hirn|brain", str(a.get("id") or "").lower())]
        idiom = bool(re.search(BODY_IDIOM_RE, low))
        if (humans and shot not in ("insert", "graphic")) or idiom:
            keep = [q for q in sc.get("props") or [] if str((q.get("type") if isinstance(q, dict) else q) or "").lower().replace("lib_", "") not in BODY_PROPS]
            if len(keep) != len(sc.get("props") or []):
                sc["props"] = keep
                if shot == "insert" and not keep:
                    sc["shot"] = shot = ""
        if shot in ("graphic", "insert") or isinstance(backdrop(sc), dict):
            continue
        rp = places.resolve(backdrop(sc))
        crowd = str(sc.get("crowd") or "")
        if len(humans) >= 2 and crowd and not re.search(PAIR_CROWD_RE, low):
            if crowd in ("worried", "panic", "watch", "sad") and not re.search(PANIC_RE, low):
                sc["crowd"] = ""
            elif rp in PAIR_QUIET:
                sc["crowd"] = ""
        elif len(humans) >= 2 and crowd and rp in PAIR_QUIET and not re.search(PAIR_FULL_RE, low) and not re.search(PANIC_RE, low):
            sc["crowd"] = ""                              # „… schenkt man nur Menschen, die einem wichtig sind“: allgemeines „Menschen“ stellt keine Fremden an den Tisch des Paars (Video 191)
        if pair and len(humans) == 1 and len(sc.get("actors") or []) == 1 and rp in ROOMS and shot == "" and not sc.get("crowd") \
                and str(humans[0].get("action") or "") == "walk" and str(humans[0].get("pos") or "") in ("offleft", "offright") and not humans[0].get("hold") \
                and not humans[0].get("say"):
            emo = MOOD_EMOTION.get(str(sc.get("mood") or ""), "") or "happy"
            a_id, b_id = (pair if n_fill % 2 == 0 else pair[::-1])
            sc["actors"] = [{"id": a_id, "action": "talk", "pos": "left", "facing": "right", "emotion": emo, "emote": "", "speaks": False},
                            {"id": b_id, "action": "think" if emo != "happy" else "idle", "pos": "right", "facing": "left", "emotion": emo,
                             "emote": "heart" if str(sc.get("mood") or "") == "love" and n_fill % 2 == 0 else "", "speaks": False}]
            n_fill += 1


# Körper-Sätze (Prüfung 16.11.2026, 21-Uhr-Termin, „Was in deinem Körper passiert, wenn du dich erschrickst“ – Video 126: vierzehn von neunzehn
# Szenen zeigten dieselbe Schreck-Pose, zum Gehirn-Satz standen Passanten auf der Straße): Beschreibt der Satz, was der Körper tut, tut die Figur genau das.
BODY_ACTS = ((r"zuck\w* (?:\w+ ){0,3}zusammen|zusammenzuck|zusammengezuckt|kopf (?:\w+ ){0,2}ein\b|kopf einzieh|ziehst (?:\w+ ){0,3}kopf|nacken und schultern|"
              r"schultern (?:\w+ ){0,3}(?:hoch|spann)|duck(?:s?t)? dich", "cower", ""),
             (r"erstarr|schreckstarre|wie gelähmt|wie angewurzelt|salzsäule|stocksteif", "freeze", "wide"),
             (r"(?:hände|finger|knie|beine) (?:\w+ ){0,3}zitter|zitter\w* (?:\w+ ){0,4}(?:hände|finger|knie|beine)|\bzitterst\b", "tremble", ""),
             (r"pupillen (?:\w+ ){0,5}(?:weit|groß|größer|riesig|öffn|licht)|(?:weit|groß|riesig|geweitet)\w* (?:\w+ ){0,2}pupillen", "pupils", "close"),
             (r"blinzel|lidschl|lider (?:\w+ ){0,3}(?:zu\b|schließ)|augen (?:\w+ ){0,4}(?:zu\b|schließ|kneif)|kneifst (?:\w+ ){0,3}augen", "blink", "close"),
             (r"\bprust\w*|\bloslach|\blosgelacht|lachkrampf|lachanfall|\blach\w* (?:\w+ ){0,2}(?:laut|los)\b|laut (?:\w+ ){0,2}lach|vor lachen", "laugh", ""),
             (r"atmest (?:\w+ ){0,3}(?:schneller|flach|hektisch)|atmung (?:\w+ ){0,3}(?:schneller|beschleunig|flach|rast)|schnappst nach luft|außer atem|keuch", "pant", ""),
             (r"herz (?:\w+ ){0,3}(?:schlägt|rast|klopft|pocht|hämmert|pumpt)|herzschlag (?:\w+ ){0,3}(?:schneller|beschleunig|rast)|puls (?:\w+ ){0,3}(?:steigt|rast|schnellt|jagt)", "pant", "wide"))
BODY_BRAIN_RE = r"\bgehirn|\bhirn\b|hirnstamm|mandelkern|amygdala|großhirn|kleinhirn|denkzentrale"
BRAIN_IDIOM_RE = (r"(?:dein|euer|mein|das) (?:ge)?hirn (?:\w+ ){0,3}(?:zerstör|spreng|explodier|schmelz|platz|wegblas|umhau|durchbrenn|überforder|brechen|kaputt)"   # „wird dein Gehirn komplett
                  r"|(?:zerstör|spreng|schmilz|überforder)\w* (?:\w+ ){0,2}(?:dein|euer|mein) (?:ge)?hirn")    # zerstören“ ist eine Redewendung des Einstiegs – kein Gehirn, das neben der Figur auf der Straße steht (Video 206)
BODY_PARTS_RE = (r"\bkörper|\bbeine?n?\b|\bfüßen?\b|\bknien?\b|\bhänden?\b|\bhand\b|\barmen?\b|\baugen?\b|pupille|\bohr(?:en)?\b|\bherz|\bpuls\b|muskel|\bnacken|schulter|"
                 r"\bkopf\b|\bhaut\b|\batem|atmung|\bblut\b|\bmagen|verdauung|\bnerven?\b|reflex|adrenalin|hormon")   # Sätze über den Körper zeigen die Figur, nie Passanten auf der Straße (Video 128: „Die Beine reagieren zuletzt“)
BODY_LEGS_RE = r"\bbeine?n?\b|\bfüßen?\b|\bknien?\b"


def _body_story(scenes):
    """Schlussdurchgang: (1) Zusammenzucken, Erstarren, Zittern, Blinzeln, weite Pupillen, schnelles Atmen – die Figur macht es vor
    (rig: cower, freeze, tremble, blink, pupils, pant) statt in jeder Szene dieselbe Schreck-Pose zu zeigen. (2) Spricht der Satz vom
    Gehirn (Hirnstamm, Mandelkern) und steht nur ein Mensch im Bild, steht das Gehirn als Figur daneben – ohne Passanten. (3) Ein Satz
    über Beine/Füße ist keine Großaufnahme des Gesichts."""
    prev_room = None
    ids_b = [str(a.get("id") or "") for sc in scenes if isinstance(sc, dict) for a in sc.get("actors") or []
             if isinstance(a, dict) and a.get("id") and not a.get("kind") and not re.search(r"gehirn|hirn|brain|" + FRIDGE_ID_RE, str(a.get("id") or "").lower())]
    lead_b = max(set(ids_b), key=ids_b.count) if ids_b else ""
    for sc in scenes:
        if not isinstance(sc, dict):
            continue
        shot = str(sc.get("shot") or "")
        bd = backdrop(sc)
        rp = places.resolve(bd) if not isinstance(bd, dict) else "custom"
        low = str(sc.get("text") or "").lower()
        if lead_b and shot == "event" and rp in ("street", "park", "plain") and not [a for a in (sc.get("actors") or []) if isinstance(a, dict)] \
                and re.search(BODY_BRAIN_RE, low) and not re.search(OUTSIDE_RE + "|" + PEOPLE_RE, low):
            sc["shot"] = shot = ""                        # „prüft das Gehirn die Lage“ als Straßenbild mit besorgten Passanten: zurück zur Figur
            sc["actors"] = [{"id": lead_b, "action": "freeze" if re.search(r"erstarr|schreckstarre", low) else "idle", "emotion": "worried", "emote": "", "pos": "center",
                             "speaks": False, "say": "", "hold": "", "facing": ""}]
            sc["props"] = []
        acts = [a for a in (sc.get("actors") or []) if isinstance(a, dict)]
        humans = [a for a in acts if not a.get("kind") and not re.search(r"gehirn|hirn|brain|" + FRIDGE_ID_RE, str(a.get("id") or "").lower())]
        if shot in ("graphic", "insert") or not humans or rp in MAPS + ("underwater", "space", "highsky"):
            prev_room = rp if rp in ROOMS else prev_room
            continue
        h = humans[0]
        hit = next(((act, want) for pat, act, want in BODY_ACTS if re.search(pat, low)), None)
        free = str(h.get("action") or "").lower() in ("", "idle", "talk", "shocked", "scared", "look_around", "think", "walk", "run", "point", "shake", "wave", "jump")
        if hit and free and len(acts) == 1 and not h.get("hold"):
            act, want = hit
            h.update(action=act, emote="", pos="center")
            h.pop("to", None)
            if act == "laugh":
                h["emotion"] = "happy"
            if act in ("tremble", "pant", "cower") and not str(h.get("emotion") or ""):
                h["emotion"] = "worried"
            if want == "close":
                sc["shot"], sc["props"], sc["crowd"] = "close", [], ""
            elif want == "wide" and shot in ("close", "event"):
                sc["shot"] = ""
            sc["_no_cut"] = True                          # kein Gegenschnitt mitten in der Geste
        elif shot == "close" and re.search(BODY_LEGS_RE, low):
            sc["shot"] = ""                               # „die Beine reagieren zuletzt“: die ganze Figur, nicht nur das Gesicht
        if re.search(BODY_BRAIN_RE, low) and not re.search(BRAIN_IDIOM_RE, low) and len(acts) == 1 and not (hit and hit[1] == "close") and str(sc.get("shot") or "") != "close" and not h.get("hold") \
                and str(h.get("action") or "").lower() not in ("dance", "sit", "sleep", "fall", "float", "jump") and not sc.get("_beside_bed") \
                and not re.search(r"im kopf\b.{0,12}$", low):
            if rp in ("street", "park", "plain") and not re.search(OUTSIDE_RE, low):
                sc["place"], sc["backdrop"] = prev_room or "livingroom", None    # ein Gedanken-Satz spielt nicht plötzlich auf der Straße
            sc["crowd"] = ""
            h["pos"] = 250                                # weit genug auseinander: das Gehirn stand halb vor der Figur (Video 204)
            h.pop("to", None)
            if str(h.get("action") or "").lower() in ("walk", "run"):
                h["action"] = "idle"
            busy = bool(re.search(r"prüf|bewert|entscheid|überleg|rechne|sortier|vergleich", low))
            sc["actors"] = [h, {"id": "_hirn", "kind": "brain", "hero": False, "small": True, "pos": 800, "action": "think" if busy else "talk", "emotion": "", "emote": "?" if busy else "",
                                "say": "", "hold": "", "facing": "left", "speaks": False}]
            sc["props"] = [q for q in (sc.get("props") or []) if not isinstance(q, dict) or q.get("pos") in (None, "")][:1]
            if str(sc.get("shot") or "") == "event":
                sc["shot"] = ""
        bd = backdrop(sc)
        rp = places.resolve(bd) if not isinstance(bd, dict) else "custom"
        prev_room = rp if rp in ROOMS else prev_room
    return scenes


# Regie-Wörter aus der Drehbuch-Anleitung, die die Text-KI manchmal als Einblendung ausgibt (Prüfung 16.11.2026, Video 121: Schild „CLIFFHANGER“, Karte „REHOOK“)
META_LABEL_RE = r"\b(?:CLIFFHANGER|RE-?HOOK|HOOK|FINTE|LOOP|PAYOFF|PUNCHLINE|CALL TO ACTION|CTA|OUTRO|INTRO|TWIST|TEASER|ÜBERLEITUNG|SCHLEIFE)\b"
ENGLISH_TITLE_RE = r"\b(?:NIGHT|SHIFT|BRAIN|SLEEP|FACTS?|TO-?DO|TODAY|DAY|LIST|RULES?|TIPS|LEVEL UP|MODE)\b"
# Schlaf-Videos (Prüfung 16.11.2026, „5 Dinge, die dein Gehirn nachts tut“)
SLEEP_TOPIC_RE = r"schlaf|schläf|\btraum|träum|\bnachts\b|in der nacht|einschl[aä]f"
WAKE_RE = r"aufwach|wachst (?:\w+ ){0,3}auf|wecker|am nächsten morgen|am morgen\b|\bmorgens\b|nächsten tag|tagsüber|ausgeschlafen|sonnenaufgang"
PEOPLE_RE = r"\bleute|\bmenschen\b|kolleg|mitarbeiter|angestellte|kunden|passant|\balle\b|\bjeder\b|millionen|team\b"


def _sleep_story(scenes, topic):
    """Schlussdurchgang für Videos über Schlaf und Nacht: (1) Ein Satz, der nebenbei eine Tageszeit nennt („was du mittags gegessen hast“),
    bleibt Nacht – Tag wird es nur, wenn jemand aufwacht oder der Morgen kommt. (2) Nachts laufen keine Passanten durch Büro, Labor oder
    Klassenzimmer, wenn der Satz nicht von Leuten spricht; steht dann niemand im Bild, kommt die Figur des Videos dazu und zeigt auf das Ding."""
    if not re.search(SLEEP_TOPIC_RE, topic_head(topic).lower()):
        return
    ids = [str(a.get("id") or "") for sc in scenes if isinstance(sc, dict) for a in sc.get("actors") or [] if isinstance(a, dict) and a.get("id")]
    lead = max(set(ids), key=ids.count) if ids else "du"
    human = next((i_ for i_ in ("du", "ich") if i_ in ids), "")
    for sc in scenes:
        if not isinstance(sc, dict):
            continue
        low = str(sc.get("text") or "").lower()
        if str(sc.get("time") or "") == "day" and re.search(DAY_RE, low) and not re.search(WAKE_RE, low):
            sc["time"] = "night"
        elif str(sc.get("time") or "") == "night" and re.search(r"wachst (?:\w+ ){0,3}auf|aufwachst|wecker klingelt", low) and not re.search(NIGHT_RE, low):
            sc["time"] = "day"                            # Aufwachen am Morgen: hell
        rp = places.resolve(backdrop(sc)) if not isinstance(backdrop(sc), dict) else "custom"
        shot_s = str(sc.get("shot") or "")
        acts_s = [a for a in sc.get("actors") or [] if isinstance(a, dict)]
        if rp == "livingroom" and shot_s not in ("graphic", "insert") and not re.search(r"sofa|couch|wohnzimmer|fernseh", low):
            sc["place"], sc["backdrop"], rp = "bedroom", None, "bedroom"   # ein Schlaf-Video spielt im Schlafzimmer, nicht im Wohnzimmer (dort lag die Schlafende vor dem Sofa auf dem Boden)
        brainy = lambda a: bool(re.search(r"gehirn|hirn|brain", (str(a.get("id") or "") + " " + str(a.get("kind") or "")).lower()))   # noqa: E731
        if rp == "bedroom" and str(sc.get("time") or "") == "night" and all(brainy(a) for a in acts_s) and human \
                and shot_s not in ("close", "insert", "graphic") and not re.search(WAKE_RE, low):
            for a in acts_s:                              # das Gehirn arbeitet, während der Mensch schläft: die Schlafende liegt im Bett, das Gehirn steht rechts daneben
                moving_s = str(a.get("action") or "") in ("walk", "run") or (a.get("to") and a.get("to") != a.get("pos"))
                a["pos"], a["to"] = ("offright" if moving_s else 830), 830   # rechts neben dem Bett (das Bett endet bei places.BED_END), die Schlafende bleibt sichtbar
            if shot_s == "event":
                sc["shot"] = ""
            sc["_beside_bed"] = True
            sc["actors"] = [{"id": human, "action": "sleep", "emotion": "", "emote": "", "pos": "left", "to": "left", "speaks": False}] + acts_s   # die Schlafende zuerst: Bett und Decke liegen hinter dem Gehirn
        if str(sc.get("time") or "") == "night" and rp in PUBLIC_INDOOR and str(sc.get("crowd") or "") in ("walk", "cheer") and not re.search(PEOPLE_RE, low):
            sc["crowd"] = ""
            if not [a for a in sc.get("actors") or [] if isinstance(a, dict)] and str(sc.get("shot") or "") not in ("insert", "graphic"):
                sc["actors"] = [{"id": lead, "action": "point", "emotion": "", "emote": "", "pos": "left", "to": "left", "speaks": False}]


# Musik-Videos (Ausbau 16.11.2026, „Warum du bei Musik Gänsehaut bekommst“): Kopfhörer auf dem Kopf, Gänsehaut als Schaubild
MUSIC_TOPIC_RE = r"\bmusik|\bsongs?\b|lieblingssong|lieblingslied|\blied(?:er|ern|es)?\b|playlist|kopfhörer|bassdrop|\bbeats?\b|ohrwurm|podcast|hörbuch"
HEADPHONE_RE = r"kopfhörer|headset|ohrstöpsel|earbuds"
FUR_RE = r"luftschicht|luftpolster|isolierschicht|\bfell (?:\w+ ){0,3}(?:auf\b|aufstell|aufricht|stell\w* sich|richt\w* sich)|(?:stell|richt)\w* sich (?:\w+ ){0,3}fell (?:\w+ ){0,2}auf"
GOOSE_RE = r"gänsehaut|haarwurzel|haarbalg|härchen|haare (?:\w+ ){0,3}(?:stell|richt)\w* sich"


def _music(scenes, topic):
    """Schlussdurchgang: (1) Handelt das Thema von Musik/Songs/Kopfhörern, trägt die Hauptfigur im ganzen Video Kopfhörer (`wear`, rig: hat
    „headphones“) – sonst nur in Sätzen, die Kopfhörer nennen. Die Kopfhörer aus der Bibliothek liegen dann nicht zusätzlich am Boden.
    (2) Steht das Gänsehaut-Schaubild im Bild (Haarwurzel, Haarbalg), entfällt der Oberarm-Muskel aus der Bibliothek daneben –
    „winzige Muskeln an den Haarwurzeln“ meint die Haarbalgmuskeln im Schaubild."""
    low_t = topic_head(topic).lower()
    music = bool(re.search(MUSIC_TOPIC_RE, low_t))
    goose_seen = False
    _key = lambda q: extras.PROP_ALIASES.get(str((q.get("type") if isinstance(q, dict) else q) or "").lower(), str((q.get("type") if isinstance(q, dict) else q) or "").lower())   # noqa: E731
    for sc in scenes:
        if not isinstance(sc, dict):
            continue
        low = str(sc.get("text") or "").lower()
        said = bool(re.search(HEADPHONE_RE, low))
        if (music or said) and places.resolve(backdrop(sc)) not in ("underwater", "space"):
            human = next((a for a in (sc.get("actors") or []) if isinstance(a, dict) and not a.get("kind")
                          and not re.search(r"gehirn|hirn|brain|" + FRIDGE_ID_RE, str(a.get("id") or "").lower())), None)
            if human is not None:
                human["wear"] = "headphones"
                sc["props"] = [q for q in (sc.get("props") or []) if _key(q) != "lib_kopfhoerer"]
        kinds = [_key(q) for q in (sc.get("props") or [])]
        if re.search(GOOSE_RE, low) and "goosebumps" not in kinds and len(kinds) < 2 and str(sc.get("shot") or "") not in ("graphic", "close", "insert") \
                and places.resolve(backdrop(sc)) not in places.OUTDOOR + ("underwater", "space") + tuple(MAPS):
            sc["props"] = (sc.get("props") or []) + [{"type": "goosebumps"}]     # „Gänsehaut“: das Schaubild steht neben der Figur
            kinds.append("goosebumps")
        if "lib_muskel" in kinds and (music or goose_seen or re.search(GOOSE_RE, low)) and not re.search(r"bizeps|oberarm|training|kraftsport|\bsport", low) \
                and re.search(r"(?:winzig|klein|fein|mini)\w* muskel|muskel\w* (?:\w+ ){0,4}(?:haar|haut)|zieh\w* sich (?:\w+ ){0,3}muskel", low):
            sc["props"] = [({"type": "goosebumps"} if _key(q) == "lib_muskel" else q) for q in sc["props"]]   # „winzige Muskeln ziehen sich zusammen“: die Haarbalgmuskeln im Schaubild, kein Oberarm mit Schild „HAARWURZELN“
            kinds = [_key(q) for q in sc["props"]]
            if kinds.count("goosebumps") > 1:
                seen_g, keep_g = False, []
                for q in sc["props"]:
                    if _key(q) == "goosebumps":
                        if seen_g:
                            continue
                        seen_g = True
                    keep_g.append(q)
                sc["props"], kinds = keep_g, [_key(q) for q in keep_g]
        goose_seen = goose_seen or "goosebumps" in kinds
        hum_g = [a for a in (sc.get("actors") or []) if isinstance(a, dict) and not a.get("kind") and not re.search(r"gehirn|hirn|brain", str(a.get("id") or "").lower())]
        if "goosebumps" in kinds and hum_g and str(sc.get("shot") or "") not in ("graphic", "insert"):
            for a in hum_g:                               # die Figur steht links neben dem Schaubild und zeigt darauf – sie läuft nicht mitten durch die Tafel
                a["pos"], a["facing"] = "left", "right"
                a.pop("to", None)
                if str(a.get("action") or "") in ("walk", "run", "jump", "dance", "idle", ""):
                    a["action"] = "point"
            sc["actors"] = [a for a in sc["actors"] if not isinstance(a, dict) or a in hum_g[:1] or a.get("kind") or a not in hum_g]
            for q in sc["props"]:
                if isinstance(q, dict) and _key(q) == "goosebumps":
                    q["pos"] = 770
            sc["shot"] = "" if str(sc.get("shot") or "") in ("event", "close") else sc.get("shot")
            sc["_no_cut"] = True
        if "lib_muskel" in kinds and goose_seen and not re.search(r"\bmuskel|bizeps|oberarm", low):
            sc["props"] = [q for q in sc["props"] if _key(q) != "lib_muskel"]     # aus dem Haarbalg-Satz mitgenommener Oberarm (_carry_thing)
        if "goosebumps" in kinds and "lib_muskel" in kinds:
            sc["props"] = [q for q in sc["props"] if _key(q) != "lib_muskel"]
    return scenes


FUR_LIKE_RE = r"\bwie (?:\w+ ){0,3}(?:jacke|mantel|decke|daunen\w*|pullover|schlafsack|isolierung)\b"
ANCESTOR_ID_RE = r"^_?(?:vorfahr\w*|urahn\w*|ahne|ahnin|ahnen|urzeit\w*vorfahr\w*)$"


def _fur_ancestor(scenes):
    """Prüfung 17.11.2026: Erzählt das Video vom Fell der Vorfahren (ANCESTOR_RE oder FUR_RE in einem Satz), ist eine Figur mit der Kennung
    „vorfahre“/„urahn“ der Affe mit Fell – kein heutiger Mensch im Kapuzenpulli, der neben der Fell-Tafel friert oder am Schluss winkt."""
    if not any(isinstance(sc, dict) and re.search(ANCESTOR_RE + "|" + FUR_RE, str(sc.get("text") or "").lower()) for sc in scenes):
        return
    for sc in scenes:
        if not isinstance(sc, dict):
            continue
        acts_f = [a for a in (sc.get("actors") or []) if isinstance(a, dict)]
        if len(acts_f) == 2 and sum(1 for a in acts_f if not a.get("kind") and re.search(ANCESTOR_ID_RE, str(a.get("id") or "").lower())) == 1:
            for a in acts_f:                              # Mensch links, Vorfahre rechts – der große Affe stünde sonst vor der Figur
                a["pos"] = 760 if re.search(ANCESTOR_ID_RE, str(a.get("id") or "").lower()) else 300
        for a in sc.get("actors") or []:
            if isinstance(a, dict) and not a.get("kind") and re.search(ANCESTOR_ID_RE, str(a.get("id") or "").lower()):
                a.update(kind="chimp", hero=True, action="puff" if a.get("action") == "puff" else "idle", hold="", wear="", speaks=False,
                         emotion="scared" if a.get("action") in ("shiver", "cower", "shocked") else "happy" if a.get("action") in ("wave", "cheer", "dance") else str(a.get("emotion") or ""))


def _fur_story(scenes):
    """Schlussdurchgang (Ausbau 17.11.2026): Spricht der Satz davon, dass sich das Fell aufstellt und eine Luftschicht einschließt (`FUR_RE`),
    steht das Schaubild `fur` im Bild – statt der Gänsehaut-Tafel, die das Drehbuch dort mangels Besserem hinstellt. Der Folgesatz ohne eigenes
    Stichwort („Das schützte vor eisiger Kälte“) behält die Fell-Tafel. Ein Affe mit gesträubtem Fell (ANCESTOR_RE) bleibt allein im Bild."""
    _key = lambda q: extras.PROP_ALIASES.get(str((q.get("type") if isinstance(q, dict) else q) or "").lower(), str((q.get("type") if isinstance(q, dict) else q) or "").lower())   # noqa: E731
    prev_fur = False
    for sc in scenes:
        if not isinstance(sc, dict):
            continue
        low = str(sc.get("text") or "").lower()
        shot = str(sc.get("shot") or "")
        kinds = [_key(q) for q in (sc.get("props") or [])]
        beast = any(isinstance(a, dict) and a.get("kind") for a in (sc.get("actors") or []))
        said = bool(re.search(FUR_RE, low)) and not beast and shot not in ("graphic", "close") and places.resolve(backdrop(sc)) not in ("underwater", "space") + tuple(MAPS)
        carry = prev_fur and "goosebumps" in kinds and not re.search(GOOSE_RE, low) and re.search(COLD_RE + r"|\bwärm|\bwarm|\bschütz|\bwinter", low)
        like = prev_fur and not beast and shot not in ("graphic", "close") and re.search(FUR_LIKE_RE, low)   # „Das wirkte wie eine dickere Jacke“: Vergleich – die Fell-Tafel bleibt, keine einzelne Jacke im Schnee
        if re.search(FUR_RE, low) and re.search(FUR_LIKE_RE, low):          # „… schloss eine Luftschicht ein, wie eine dickere Jacke“: die Jacke ist nur der Vergleich
            sc["props"] = [q for q in (sc.get("props") or []) if not re.search(r"jacke|mantel|coat|decke|pullover|schlafsack", _key(q))]
            kinds = [_key(q) for q in sc["props"]]
        if re.search(r"haarwachstum|haarwurzel|haarbalg|härchen", low) and not re.search(r"bizeps|oberarm|armmuskel", low):   # der Muskel an der Haarwurzel ist kein Oberarm
            sc["props"] = [q for q in (sc.get("props") or []) if _key(q) not in ("muskel", "lib_muskel")]
            kinds = [_key(q) for q in sc["props"]]
        if like:
            sc["props"] = [q for q in (sc.get("props") or []) if _key(q) in ("fur", "goosebumps")]
            sc["shot"] = "" if shot in ("event", "insert") else sc.get("shot")
            kinds = [_key(q) for q in sc["props"]]
        if said or carry or like:
            if "goosebumps" in kinds:
                sc["props"] = [({"type": "fur", **({"pos": q["pos"]} if isinstance(q, dict) and q.get("pos") else {})} if _key(q) == "goosebumps" else q) for q in sc["props"]]
            elif "fur" not in kinds and len(kinds) < 2:
                sc["props"] = (sc.get("props") or []) + [{"type": "fur"}]
            seen_f, keep_f = False, []
            for q in sc["props"]:                         # nie zwei Fell-Tafeln (Drehbuch + Text-Hinweis)
                if _key(q) == "fur":
                    if seen_f:
                        continue
                    seen_f = True
                keep_f.append(q)
            sc["props"] = keep_f
        kinds = [_key(q) for q in (sc.get("props") or [])]
        if "fur" in kinds and "goosebumps" in kinds:      # nie beide Tafeln nebeneinander (Vorgriff im ersten Bild): es bleibt die, von der der Satz spricht
            drop_f = "fur" if re.search(GOOSE_RE, low) and not re.search(FUR_RE, low) else "goosebumps"
            sc["props"] = [q for q in sc["props"] if _key(q) != drop_f]
            kinds = [_key(q) for q in sc["props"]]
        if "adrenaline" in kinds:                         # das Schaubild zeigt das Herz schon: kein zweites Herz daneben
            sc["props"] = [q for q in sc["props"] if _key(q) not in ("lib_herz", "heart")]
        board = next((k for k in ("fur", "adrenaline") if k in kinds), None)
        hum_f = [a for a in (sc.get("actors") or []) if isinstance(a, dict) and not a.get("kind") and not re.search(r"gehirn|hirn|brain", str(a.get("id") or "").lower())]
        if board and hum_f and shot not in ("graphic", "insert") and len(sc.get("actors") or []) == 1:
            h = hum_f[0]                                  # wie bei der Gänsehaut-Tafel: die Figur steht links daneben und zeigt darauf, statt hindurchzulaufen
            h["pos"], h["facing"] = "left", "right"
            h.pop("to", None)
            if str(h.get("action") or "") in ("walk", "run", "jump", "dance", "idle", "talk", ""):
                h["action"] = "point"
            for q in sc["props"]:
                if isinstance(q, dict) and _key(q) == board:
                    q["pos"] = 770
            sc["props"] = [q if isinstance(q, dict) or _key(q) != board else {"type": board, "pos": 770} for q in sc["props"]]
            sc["shot"] = "" if shot in ("event", "close") else sc.get("shot")
            sc["_no_cut"] = True
        if "adrenaline" in kinds and ("goosebumps" in kinds or "fur" in kinds):   # zwei Schautafeln an derselben Stelle verdecken sich: nennt der Satz Adrenalin, bleibt die Adrenalin-Tafel
            drop_a = ("goosebumps", "fur") if re.search(r"adrenalin|nebenniere|stresshormon", low) else ("adrenaline",)
            sc["props"] = [q for q in sc["props"] if _key(q) not in drop_a]
            kinds = [_key(q) for q in sc["props"]]
        prev_fur = "fur" in kinds
    return scenes


# Tiere, die der Satz nennt, stehen im Bild (Kühe protestieren, das Schwein fragt, Schimpansen im Labor, die Mücke am Ohr) – wie PET_RE für Katze und Hund.
NAMED_ANIMALS = ((r"\bkuh\b|\bkühen?\b|\brind(?:er|ern|es)?\b|\bkalb\b|\bkälber", "cow", r"kühe|rinder|kälber"),
                 (r"\bschwein(?:e|en|s)?\b|\bferkel", "pig", r"\bschweinen?\b|ferkel\b"),
                 (r"schimpanse|\baffen?\b|menschenaffe|gorilla", "chimp", r"schimpansen|\baffen\b|gorillas"),
                 (r"\bmücken?\b|stechmücke|moskito", "mosquito", r"mücken|moskitos"),
                 (r"\b(?:eine|die|jede|der|einer) fliege\b|stubenfliege", "fly", r"$^"),
                 (r"\blöwen?\b|\blöwin", "lion", r"(?:\b(?:die|viele|alle|zwei|drei|mehrere|ganze[ns]?) |-)löwen\b|\blöwen (?:sind|haben|jagen|leben|töten|brüllen)|löwenrudel"),
                 (r"spinne|tarantel", "spider", r"spinnen|taranteln"), (r"katze|kater\b|kätzchen", "cat", r"katzen"), (r"\bhund(?:e|es|en|chen)?\b|welpe", "dog", r"\bhunde[n]?\b|welpen"))
ANIMAL_IDIOM_RE = (r"schwein gehabt|armes schwein|kein schwein|schweinehund|sparschwein|glücksschwein|schweineteuer|affenhitze|affenzahn|laust der affe|heilige kuh|"
                   r"melkkuh|kuhhandel|hundemüde|hundeelend|katzensprung|katzenwäsche|\bkater\b.{0,20}(?:alkohol|party|getrunken)|spinnst|spinnen die")
TALKING_RE = r"tiere?n?\b.{0,50}\b(?:sprechen|reden|sprache|sprächen)|sprechende[nrs]? tiere?"


ANCESTOR_RE = r"behaart\w* (?:vorfahr|urahn|ahnen)|(?:vorfahr\w*|urahn\w*|ahnen) (?:\w+ ){0,8}fell\b|aufgestellt\w* (?:\w+ ){0,3}(?:vorfahr|urahn)|(?:vorfahr\w*|urahn\w*) (?:\w+ ){0,5}(?:größer|bedrohlicher)|aufgestellt\w* fell|fell (?:\w+ ){0,4}(?:aufstell|aufgestellt|sträub|aufplust)|(?:sträub|plustert)\w* (?:\w+ ){0,4}fell"


CAT_PUFF_RE = r"(?:katze|kater\b|kätzchen)\w* (?:\w+ ){0,6}(?:sträub|plustert|buckel|fell (?:\w+ ){0,3}auf)|(?:sträub|plustert|aufgestellt)\w* (?:\w+ ){0,6}(?:katze|kater\b|kätzchen)|katzenbuckel"


TINY_KINDS = ("tardigrade",)
TINY_REF_RE = r"\b(es|ihm|ihn|sie|ihnen|ihre[nmrs]?|seine[nmrs]?|tier(?:e|en|es|chen)?|winzling\w*|überlebenskünstler\w*|bärtierchen|wasserbär\w*)\b"
TUN_RE = (r"tönnchen|tonnen(?:zustand|stadium|form)|\btonne\b|trocknet\w*|ausgetrocknet|getrocknet|eingetrocknet|vertrocknet|rollt sich|eingerollt|zieht (?:\w+ ){0,3}beine ein|"
          r"scheintot|kryptobiose|stoffwechsel|regungslos|starre\b|wie tot")
WAKE_RE = (r"erwach|wacht (?:\w+ ){0,4}auf|aufgewacht|aufwach|krabbel|wieder (?:los|munter|lebendig|wach|aktiv)|zum leben|\blebt\b|\bleben sie\b|findest|\bwach und\b|\baktiv\b|"
           r"\bfrisst|\bläuft|tapst|spaziert|moos")
LION_SCENE_RE = r"\blöwen?\b|\blöwin"


def _one_tiny(scenes):
    """Nennt das ganze Drehbuch genau einen Winzling (Bärtierchen), ist er das Tier des Videos (Prüfung 17.11.2026: Im vorbereiteten Plan
    „Dieses winzige Tier …“ stand das Bärtierchen nur im Satz mit seinem Namen im Bild, danach 15 Sätze lang ein Mensch im Park oder gar nichts)."""
    kinds = {k for sc in scenes if isinstance(sc, dict) for pat, k in ANY_CREATURES if re.search(pat, str(sc.get("text") or "").lower())}
    if any(_sea_named(str(sc.get("text") or "").lower()) for sc in scenes if isinstance(sc, dict)):
        return None                                       # „3 Tiere mit Superkräften“ (Axolotl, Qualle, Bärtierchen): jedes Tier hat nur seine eigenen Sätze
    return next(iter(kinds)) if len(kinds) == 1 and next(iter(kinds)) in TINY_KINDS else None


def _tiny_story(scenes):
    """Ein-Tier-Video über einen Winzling: Der Vergleich mit dem Löwen zeigt beide (Löwe groß in der Savanne, der Winzling klein davor); spricht ein
    Menschen-Satz vom Tier („Forscher gaben ihm Wasser“, „Du findest sie im Moos“), steht es neben dem Menschen – im All und unter Wasser allein;
    ausgetrocknet ist es ein Tönnchen (extras.creature „tun“), bis ein Satz vom Aufwachen spricht."""
    kind = _one_tiny(scenes)
    if not kind:
        return scenes
    tun, n_tun = False, 0

    def beast(**kw):
        return dict({"id": "_tier", "kind": kind, "hero": True, "action": "idle", "speaks": False, "pos": "center", "emote": "", "say": "", "hold": "",
                     "facing": "right", "emotion": ""}, **kw)
    for sc in scenes:
        if not isinstance(sc, dict):
            continue
        low = str(sc.get("text") or "").lower()
        if re.search(WAKE_RE, low):
            tun = False
        elif re.search(TUN_RE, low):
            tun = True
        if str(sc.get("shot") or "") == "insert" and re.search(TINY_REF_RE + r"|\bmoos", low):
            # „Du findest sie in jedem Moospolster vor deiner Haustür“ war ein Einschub: Tür und Moos frei vor leerem Grund (Video 137) – daraus wird eine Szene mit Figur, Moos und Tier
            sc["shot"] = ""
            sc["props"] = []
            sc.setdefault("actors", [])
            if places.resolve(backdrop(sc)) in INDOOR + GENERIC + ("plain",) and re.search(r"\bmoos", low):
                sc["place"], sc["backdrop"] = "forest", None
        if "actors" not in sc or str(sc.get("shot") or "") in ("graphic", "insert"):
            continue
        rp = places.resolve(backdrop(sc))
        if rp in MAPS:
            continue
        acts = [a for a in (sc.get("actors") or []) if isinstance(a, dict)]
        if places.resolve(sc.get("place")) == "space" and rp == "custom" and str((sc.get("backdrop") or {}).get("sky") or "") == "night":
            rp = "space"                                   # Weltall mit eigener Kulisse (Sternenhimmel über Fels) bleibt Weltall
        alone = rp in ("space", "underwater", "highsky")
        if re.search(LION_SCENE_RE, low) and rp == "space":   # „Ein Löwe hätte im Weltall keine Chance“: der Löwe treibt erschrocken und allein im All
            sc["actors"] = [{"id": "_loewe", "kind": "lion", "hero": True, "action": "idle", "speaks": False, "pos": "center", "emote": "!", "say": "", "hold": "",
                             "facing": "right", "emotion": "scared"}]
            sc["props"], sc["crowd"], sc["shot"], sc["float"], sc["_no_cut"] = [], "", "", "float", True
            continue
        if re.search(LION_SCENE_RE, low) and not alone:    # „zäher als ein Löwe“: der Löwe groß, der Winzling klein und unbeeindruckt vor ihm
            if not _said_place(low) or rp in INDOOR or rp in GENERIC:
                sc["place"], sc["backdrop"], sc["time"], sc["weather"] = "savannah", None, "day", ""
            sc["actors"] = [{"id": "_loewe", "kind": "lion", "hero": True, "action": "roar" if re.search(r"stark|stärk|gefährlich|brüll|mächtig|könig|raubtier|zäh|hart", low) else "idle",
                             "speaks": False, "pos": 340, "emote": "", "say": "", "hold": "", "facing": "right",
                             "emotion": "scared" if re.search(r"keine chance|wäre (?:\w+ ){0,2}tot|überleb\w* (?:\w+ ){0,3}nicht|hätte", low) else ""},
                            beast(hero=False, pos=930, facing="left", emotion="happy")]
            sc["props"], sc["crowd"], sc["shot"], sc["overlay"] = [], "", "", (sc.get("overlay") if str((sc.get("overlay") or {}).get("type") or "") in ("tag", "") else None)
            sc["_no_cut"], sc["float"], sc["aloft"] = True, "", False
            continue
        mine = [a for a in acts if str(a.get("kind") or "").lower() == kind]
        humans = [a for a in acts if not a.get("kind")]
        if not mine and not any(a.get("kind") for a in acts) and re.search(TINY_REF_RE, low):
            if alone or not humans:
                sc["actors"] = acts = [beast()]
                sc["crowd"] = ""
            else:
                h = humans[0]
                h["pos"] = 170
                h.pop("to", None)
                h["facing"] = "right"
                if str(h.get("action") or "") in ("walk", "run", "float", "sit", "sleep", "look_around"):
                    h["action"] = "point" if re.search(r"gaben|gab |gibt|tropf|gießt|schick|setzt|legt|zeig|fand|find|entdeck|untersuch|beobacht", low) else "think"
                sc["actors"] = acts = [h, beast(pos=760, facing="left", hero=False, _ksz=0.85)]
                sc["_no_cut"] = True                       # kein Gegenschnitt: gespiegelt und näher schnitt er Mensch und Tier an den Rändern ab (Video 139)   # neben dem Menschen: deutlich kleiner als er, aber gut zu erkennen
                sc["crowd"] = ""
                if str(sc.get("shot") or "") in ("close", "event"):
                    sc["shot"] = ""
            mine = [a for a in acts if str(a.get("kind") or "").lower() == kind]
        if mine and re.search(r"\bmoos", low) and rp not in ("space", "underwater", "highsky") and rp not in INDOOR:   # „in fast jedem Moospolster“: das Moos liegt im Bild
            sc["props"] = [{"type": "moss", "pos": 480 if len(acts) > 1 else 170}]
            if len(acts) == 1:
                mine[0].update(pos=790, facing="left")     # das Tier steht neben dem Moos – in der Mitte verdeckte es das Polster (Video 138)
            sc["_no_cut"] = True
        if mine and len(acts) == 1 and re.search(r"\bdruck\b|tiefsee|meeresgrund|meeresboden", low) and rp not in ("space", "underwater"):
            sc.update(place="underwater", backdrop=None, time="night", weather="")   # „enormer Druck“: am Grund der Tiefsee – nicht in einer Höhle
            rp = "underwater"
        if mine and len(acts) == 1 and re.search(r"\bdach|dächer|mauer|gehweg|pflaster|regenrinne|hauswand|balkon", low) and rp not in ("space", "underwater"):
            # „auf Hausdächern und Mauern … unsichtbar für das bloße Auge“: kein haushohes Tier auf der Straße – klein neben einem Moospolster
            mine[0].update(hero=False, _ksz=0.8, pos=700, facing="left")
            sc["props"] = [{"type": "moss", "pos": 330}]
            sc["crowd"], sc["_no_cut"], sc["no_traffic"] = "", True, True
        if mine and len(acts) == 1 and tun:                # mehrere Tönnchen-Sätze hintereinander: abwechselnd links und rechts, mal von der anderen Seite
            n_tun += 1
            mine[0].update(pos=(400, 680)[n_tun % 2], facing=("right", "left")[n_tun % 2])
        if mine and len(acts) == 1 and re.search(r"\bschild\b|schutzschild|schutz-?eiweiß|schutz-?protein|erbgut|\bdna\b", low) and rp not in ("space", "underwater"):
            mine[0].update(pos=770, facing="left", hero=False, _ksz=0.9)   # „wie ein Schild um ihr Erbgut“: der Schild mit dem Erbgut-Strang steht neben dem Tier
            sc["props"] = [{"type": "shield", "pos": 300}]
            sc["_no_cut"] = True
        if mine and tun and not sc.get("overlay") and re.search(r"hitze|heiß|grad", low):
            fig_t = find_figure(str(sc.get("text") or ""))
            if fig_t and str(fig_t.get("unit") or "").upper().startswith("GRAD"):
                sc["overlay"] = fig_t                      # „Hitze von rund 150 Grad“: die Zahl steht groß über dem Tönnchen
        if mine and rp == "space" and not sc.get("float"):
            sc["float"] = "float"                          # im All steht nichts auf dem Boden: das Tier treibt schwerelos
        for a in mine:
            if tun:
                a.update(action="tun", emotion="", emote="")
            elif str(a.get("action") or "") == "tun":
                a["action"] = "idle"
            if re.search(r"erwach|wacht (?:\w+ ){0,4}auf|krabbel|wieder (?:los|munter|lebendig)|zum leben", low):
                a["emotion"] = "happy"
    return scenes


def _named_animals(scenes, topic):
    talking = bool(re.search(TALKING_RE, str(topic or "").lower()))
    for sc in scenes:
        if not isinstance(sc, dict) or "actors" not in sc:
            continue
        shot = str(sc.get("shot") or "")
        rp = places.resolve(backdrop(sc))
        low = str(sc.get("text") or "").lower()
        if shot in ("graphic", "insert") or rp in MAPS + ("underwater", "space", "highsky") or re.search(ANIMAL_IDIOM_RE, low):
            continue
        if re.search(CAT_PUFF_RE, low):                    # „Eine Katze sträubt ihr Fell“: die Katze mit Buschschwanz – nicht der Affen-Vorfahre (Prüfung 17.11.2026)
            sc["actors"] = [{"id": "_katze", "kind": "cat", "hero": True, "pos": "center", "action": "puff", "emote": "", "say": "", "hold": "", "facing": "", "emotion": "angry"}]
            sc["crowd"], sc["props"] = "", []
            sc["shot"] = "" if shot in ("close", "event") else sc.get("shot")
            continue
        if re.search(ANCESTOR_RE, low) and not any(a.get("kind") for a in (sc.get("actors") or []) if isinstance(a, dict)):
            sc["actors"] = [{"id": "_ahne", "kind": "chimp", "hero": True, "pos": "center", "action": "idle", "emote": "", "say": "", "hold": "", "facing": "",
                             "emotion": "scared" if re.search(r"gegner|feind|gefahr|bedroh|kälte|kalt|frier", low) else ""}]
            if re.search(r"aufgestellt|aufstell|stell\w* sich (?:\w+ ){0,3}auf|sträub|plustert|größer", low):
                sc["actors"][0].update(action="puff", emotion="angry" if re.search(r"größer|bedroh|gegner|feind|angreif", low) else sc["actors"][0]["emotion"])   # gesträubtes Fell: das Tier wirkt größer (extras.creature, chimp „puff“)   # „behaarte Vorfahren“, „aufgestelltes Fell“: ein Affe im Wald – nicht der Mensch von heute mit Kopfhörern
            sc["crowd"], sc["props"] = "", []
            if rp in INDOOR or rp in GENERIC:
                sc["place"], sc["backdrop"] = "forest", None
            sc["shot"] = "" if shot in ("close", "event") else sc.get("shot")
            continue
        hit = next(((k, pl) for pat, k, pl in NAMED_ANIMALS if re.search(pat, low)), None)
        acts = [a for a in (sc.get("actors") or []) if isinstance(a, dict)]
        if talking:                                       # die Tiere reden: Wer als Tier im Bild steht, bewegt den Mund – der Mensch hört zu
            beasts = [a for a in acts if a.get("kind")]
            for a in beasts[:1]:
                a["speaks"] = True
            if beasts:
                for a in acts:
                    if not a.get("kind"):
                        a["speaks"] = False
        if not hit or any(str(a.get("kind") or "").lower() == hit[0] for a in acts) or any(a.get("kind") for a in acts):
            continue
        kind, plural = hit
        humans = [a for a in acts if not a.get("kind")][:1]
        emo = MOOD_EMOTION.get(str(sc.get("mood") or ""), "")
        base = {"kind": kind, "action": "talk" if talking else "idle", "emotion": emo, "emote": "", "say": "", "hold": "", "facing": ""}
        if re.search(plural, low) and (not humans or not re.search(HUMAN_RE, low)):   # Mehrzahl, und der Satz handelt nicht von Menschen: eine kleine Gruppe
            sc["actors"] = [dict(base, id=f"_tier{j}", pos=x, hero=False, speaks=bool(talking and j == 1)) for j, x in enumerate((200, 540, 880))]   # in normaler Größe: drei große Kühe stünden ineinander
            sc["crowd"] = ""
        else:
            for h in humans:
                h["pos"], h["speaks"] = 300, False if talking else h.get("speaks")
                h.pop("to", None)
                if str(h.get("action") or "") in ("walk", "run"):
                    h["action"] = "idle"
            sc["actors"] = humans + [dict(base, id="_tier", pos=760 if humans else "center", hero=True, speaks=bool(talking))]
        if shot in ("close", "event"):
            sc["shot"] = ""
    return scenes


# Niedliche Gifttiere (Prüfung 19.11.2026, Plan „Tödlich niedlich“): Pfeilgiftfrosch, Schnabeltier und Kugelfisch sind gezeichnete Wesen. Nennt der Satz
# eines, steht es groß in seinem Lebensraum; bis zu zwei Folgesätze, die sichtbar weiter von ihm handeln, bleiben bei ihm (gespiegelt, mit Handlung:
# der Kugelfisch bläst sich auf, das Schnabeltier zeigt den Sporn). Geht es ums Anfassen, steht der Mensch erschrocken daneben und das Tier klein.
CUTE_ANIMALS = ((r"pfeilgiftfr[oö]sch|giftfr[oö]sch|baumsteigerfr[oö]sch|\bfr[oö]sch(?:e|en|es|s|lein)?\b", "frog", "forest"),
                (r"schnabeltier", "platypus", "river"),
                (r"kugelfisch|\bfugu", "puffer", "underwater"))
CUTE_SKIP_RE = r"frosch im hals|sei kein frosch|\bkoch\b|\bköch|restaurant|\bteller|servier|delikatesse|luxus|\bgericht\b|\bessen\b|\bgegessen|speisekarte|\bmesser"
CUTE_NEXT_RE = (r"^(?:er|sie|es|sein\w*|ihr\w*|dieses? (?:tier\w*|gift|fisch|frosch)|das (?:gift|tier\w*)|der (?:fisch|frosch|winzling)|dabei|damit|sogar|schon|denn|falsch|und (?:er|sie|es|das))\b|"
                r"\bgift(?:ig|es|sporn\w*|drüse\w*)?\b|\bsporn|\bstachel|\bhaut\b|bläst|aufgeblasen|aufblas|\bfarbe\b|fressfeind|\bnahrung\b|\bbeute\b")
CUTE_YOU_RE = r"\b(du|dein\w*|dir|dich|ich|mein\w*|mir|mich|wir|unser\w*|uns|euch|ärzt\w*|arzt|forscher\w*|opfer|patient\w*)\b"   # „zehn Menschen“ als Maß bleibt beim Tier
CUTE_PALM_RE = r"handfläche|passt (?:\w+ ){0,3}(?:auf|in) (?:deine|eine|die|jede) hand\b|daumennagel|fingerkuppe|kleiner als (?:dein|ein) daumen"
CUTE_TOUCH_RE = r"berühr|anfass|anfäss|streichel|\bhand\b|\bfinger|hochheb|\bhebst|\bnimmst"
CUTE_PUFF_RE = r"bläst|aufblas|aufgeblasen|aufpump|pumpt|stachel|stachelkugel|ballon|doppelt so groß|dreimal so groß"
CUTE_SPUR_RE = r"\bsporn|\bsporen?\b|giftsporn|\bstachel|hinterbein|\bsticht|\bstich\b"


# Köche (Prüfung 19.11.2026): „Nur ausgebildete Köche dürfen ihn zubereiten“ zeigte die Hauptfigur, die durch die Küche läuft. Nennt der Satz einen Koch,
# steht eine Figur mit Kochmütze und weißer Jacke in der Küche (im Restaurant bleibt das Restaurant).
COOK_RE = r"\bkoch\b|\bkochs\b|\bköch(?:e|en|in|innen)\b|küchenchef|sternekoch|sterneköch|spitzenkoch|spitzenköch|fugu-koch|fugu-köch"
COOK_LOOK = {"shirt": "weiß", "hat": "chef", "hair": "kurz", "hair_color": "schwarz"}


def _cooks(scenes):
    for sc in scenes:
        ov_3 = sc.get("overlay") if isinstance(sc, dict) and isinstance(sc.get("overlay"), dict) else None
        if ov_3 and str(ov_3.get("type") or "") == "choice" and re.search(r"\b(?:der|die|den|diesen?) drei\b|\bdrei (?:tiere|dinge)", str(sc.get("text") or "").lower()):
            sc["overlay"] = None                          # „Welches der drei …?“ mit nur zwei Antworten (A FROSCH / B SCHNABELTIER, Video 162)
        if not isinstance(sc, dict) or "actors" not in sc or (sc.get("shot") == "graphic" and graphics.clean(sc.get("graphic"))):
            continue
        low = str(sc.get("text") or "").lower()
        if not re.search(COOK_RE, low):
            continue
        rp = places.resolve(backdrop(sc)) if not isinstance(backdrop(sc), dict) else "custom"
        if rp != "kitchen":                               # auch „im Restaurant“: der Koch steht in der Küche, nicht zwischen den Gästen
            sc.update(place="kitchen", backdrop=None, time="day")
        hard = bool(re.search(r"falsch|fehler|vorsicht|gefähr|tödlich|\bgift|jahrelang|prüfung|lizenz|training|ausbildung", low))
        sc.update(actors=[{"id": "_koch", "action": "talk", "emotion": "worried" if hard else "", "emote": "sweat" if re.search(r"falsch|fehler", low) else "",
                           "pos": "center", "facing": "right", "speaks": False, "say": "", "hold": "", "look": dict(COOK_LOOK)}],
                  crowd="", props=[], float="")
        if sc.get("shot") in ("event", "insert"):
            sc["shot"] = ""
    return scenes


def _cute_named(low):
    return next(((k, home) for pat, k, home in CUTE_ANIMALS if re.search(pat, low)), None)


def _cute_animals(scenes, main_id="du"):
    wild = ("forest", "river", "lake", "park", "fields", "mountain", "beach", "savannah", "desert", "custom")
    last = None                                           # (Art, Zuhause, Nummer des Satzes)
    if any(isinstance(s2, dict) and (_cute_named(str(s2.get("text") or "").lower()) or ("",))[0] == "puffer" for s2 in scenes):
        for s2 in scenes:                                 # Kugelfisch-Video: der Ersatz-Goldfisch der Text-KI („das Gift der Nummer drei“, Video 164) ist der Kugelfisch
            for a2 in (s2.get("actors") or []) if isinstance(s2, dict) else []:
                if isinstance(a2, dict) and str(a2.get("kind") or "").lower() == "fish":
                    a2.update(kind="puffer", hero=True)
    for i, sc in enumerate(scenes):
        if not isinstance(sc, dict):
            continue
        low = str(sc.get("text") or "").lower()
        if sc.get("shot") == "graphic" and graphics.clean(sc.get("graphic")):
            if last:
                last = (last[0], last[1], i)              # die Zahl gehört noch zum Tier von eben
            continue
        if "actors" not in sc:
            sc["actors"] = []
        hit = _cute_named(low)
        if re.search(CUTE_SKIP_RE, low):                  # der Fisch auf dem Teller, der Koch: Sätze über Menschen und Essen bleiben, wie das Drehbuch sie setzt
            last = None
            continue
        follow = False
        palm = bool(re.search(CUTE_PALM_RE, low))        # „Er passt auf deine Handfläche“: ein Größenvergleich – das Tier bleibt im Bild, niemand weicht zurück
        if not hit and last and i - last[2] <= 2 and (re.search(CUTE_NEXT_RE, low) or palm) \
                and (palm or not re.search(CUTE_YOU_RE, low) or (re.search(CUTE_TOUCH_RE, low) and last[0] != "puffer")):
            hit, follow = (last[0], last[1]), True
        if not hit and i == 0 and not (sc.get("shot") == "graphic"):   # erstes Bild eines Videos über diese Tiere: die Tiere selbst (Frosch und Schnabeltier am Ufer) – nicht bloß ein Mensch am Fluss
            land = list(dict.fromkeys(k for s2 in scenes if isinstance(s2, dict) for k in [(_cute_named(str(s2.get("text") or "").lower()) or ("",))[0]] if k in ("frog", "platypus")))
            if len(land) == 2 and not re.search(CUTE_SKIP_RE, low):
                sc.update(place="river", backdrop={"sky": "day", "ground": "sand", "elements": ["river"]}, time="day", crowd="", float="", props=[], weather="",
                          actors=[{"id": "_tier1", "kind": "frog", "hero": True, "_ksz": 0.8, "pos": 200, "action": "hop", "emotion": "", "emote": "", "say": "", "hold": "", "facing": "right", "speaks": False},
                                  {"id": "_tier2", "kind": "platypus", "hero": True, "_ksz": 0.95, "pos": 820, "action": "idle", "emotion": "", "emote": "", "say": "", "hold": "", "facing": "left", "speaks": False}])
                if sc.get("shot") in ("event", "insert", "close"):
                    sc["shot"] = ""
                sc["_cute"] = "duo"
                continue
        if not hit:
            last = None
            continue
        kind, home = hit
        rp = places.resolve(backdrop(sc)) if not isinstance(backdrop(sc), dict) else "custom"
        keep = kind != "puffer" and (rp in wild) and not (kind == "platypus" and rp not in ("river", "lake", "custom"))
        touch = kind != "puffer" and bool(re.search(CUTE_TOUCH_RE, low)) and not palm
        emo = ""
        ov_c = sc.get("overlay") if isinstance(sc.get("overlay"), dict) else None
        act = {"id": "_tier", "kind": kind, "hero": not touch, "pos": 760 if touch else "center", "action": "idle", "emotion": emo, "emote": "", "say": "",
               "hold": "", "facing": "left" if (touch or (follow and (i - last[2]) % 2 == 1)) else "right", "speaks": False}
        if palm:
            act["_ksz"] = 0.75                            # der Größenvergleich: das Tier kleiner im Bild als eben
        if kind == "puffer" and (re.search(CUTE_PUFF_RE, low) or (follow and re.search(r"gift|tödlich|gefährlich|falsch", low))):
            act["action"] = "puff"
        elif kind == "platypus" and re.search(CUTE_SPUR_RE, low):
            act["action"] = "spur"
        elif kind == "frog" and follow and not touch and not palm:
            act["action"] = "hop"
        acts = [act]
        if touch:                                         # „Schon eine Berührung …“: der Mensch weicht erschrocken zurück
            human = next((a for a in (sc.get("actors") or []) if isinstance(a, dict) and not a.get("kind") and not str(a.get("id") or "").startswith("_")), None)
            human = dict(human or {"id": main_id, "speaks": False, "say": "", "hold": ""})
            human.pop("to", None)
            human.update(pos=300, action="cower", emotion="scared", emote="!", facing="right")
            acts = [human, act]
        if kind == "platypus":                            # am sandigen Flussufer – nicht mitten auf dem Wasser stehend
            sc.update(place="river", backdrop={"sky": "day", "ground": "sand", "elements": ["river"]}, time="day")
        elif not keep:
            sc.update(place=home, backdrop=None, time="day")
        sc.update(actors=acts, crowd="", float="", props=[], weather="")
        if sc.get("shot") in ("event", "insert", "close"):
            sc["shot"] = ""
        sc["_cute"] = kind
        if not follow:
            last = (kind, home, i)
    return scenes


# Karten nur, wo der Satz von Ländern spricht: Die Deutschlandkarte mit Leuchtpunkten erklärt weder „von Deutschland nach Dänemark und Schweden“
# (dafür leuchten die Länder auf der Europakarte auf) noch „Du denkst, das ist Science-Fiction?“ (dort steht die Figur am Ort der Szene davor).
MAP_WORLD_RE = r"\berde\b|planet|weltweit|\bwelt\b|global|kontinent|länder|international|überall|menschheit|ozean|\bmeere?\b"


def _map_sense(scenes):
    last, main_id = None, "du"
    for sc in scenes:
        if not isinstance(sc, dict):
            continue
        for a in (sc.get("actors") or []):
            if isinstance(a, dict) and not a.get("kind") and not str(a.get("id") or "").startswith("_"):
                main_id = str(a.get("id") or main_id)
                break
        rp = places.resolve(backdrop(sc))
        gfx = str(sc.get("shot") or "") == "graphic" and graphics.clean(sc.get("graphic"))
        if gfx:
            continue
        if rp not in MAPS:
            if rp not in ("underwater", "space", "highsky", "plain"):
                last = (sc.get("place"), sc.get("backdrop"))
            continue
        low = str(sc.get("text") or "").lower()
        regions = list(dict.fromkeys(v for k, v in graphics.REGION_WORDS.items() if k in low))
        if rp == "germany" and len(regions) >= 2:         # mehrere Länder im Satz: sie leuchten auf der Europakarte auf
            g = graphics.clean({"type": "map", "value": ",".join(regions[:4]), "text": "ZU FUSS" if re.search(r"zu fuß|laufen|wandern|spazier", low) else ""})
            if g:
                sc.update(graphic=g, shot="graphic", overlay=None)
                continue
        if re.search(GEO_RE, low) or (rp == "worldmap" and re.search(MAP_WORLD_RE, low)):
            continue
        place, bd = last or ("livingroom", None)          # kein Land, keine Welt im Satz: die Figur steht dort, wo die Geschichte gerade spielt
        humans = [a for a in (sc.get("actors") or []) if isinstance(a, dict) and not a.get("kind")][:1] or \
            [{"id": main_id, "action": "think", "emotion": "", "emote": "?" if "?" in str(sc.get("text") or "") else "", "pos": "center", "speaks": False}]
        for h in humans:
            h.pop("to", None)
            h["pos"] = "center"
            if str(h.get("action") or "") in ("walk", "run", "idle", ""):
                h["action"] = "think" if "?" in str(sc.get("text") or "") or re.search(r"\bdenkst\b|\bglaubst\b", low) else "talk"
        sc.update(place=place, backdrop=dict(bd) if isinstance(bd, dict) else None, actors=humans, props=[], shot="close")
    return scenes


# Zugefrorenes Meer („Was wäre, wenn die Ostsee zufriert?“): Die Geschichte spielt auf einer Eisfläche bis zum Horizont – kein offenes Wasser mit
# Wellen, kein Hochgebirge, kein einzelner Eisberg als „Eis“. Schiffe stecken im Eis fest, unter Wasser liegt die Eisdecke oben, Delfine/Schweinswale
# atmen an einem Loch im Eis.
FROZEN_RE = (r"zufrier|zugefror|zufror|zufrör|einfrier|eingefror|vereis|eisdecke|eisfläche|eisschicht|eispanzer|meereis|packeis|treibeis|"
             r"\b(?:auf|über|unter) (?:dem|das|der|einer|dickem|dünnem) (?:\w+ )?eis\b|\b(?:aufs|übers) eis\b")
FROZEN_SEA_RE = r"ostsee|nordsee|\bmeer(?:es|e)?\b|\bozean|\bbodden|\bförde|\bhaff\b|bodensee|polarmeer|eismeer|atlantik|pazifik|\bhafen|schiffsverkehr|schifffahrt"
ICE_SHIP_RE = r"schiff|frachter|\bfähre|tanker|container|kutter|eisbrecher|schifffahrt"
ICE_WHALE_RE = r"delfin|delphin|schweinswal|tümmler|\bwale?n?\b|meeressäuger|säugetier"
ICE_HOLE_RE = r"atemloch|atemlöcher|eisloch|eislöcher|loch im eis|löcher im eis|luft holen|luft schnappen|\batme[nt]\b|zum atmen|auftauch|taucht .{0,30}auf|sauerstoff"
ICE_UNDER_RE = (r"unter (?:dem|der|einer|das) (?:\w+ )?(?:eis|eisdecke|eisschicht|eisfläche)\b|unter wasser|\bfische?n?\b|meeresbewohner|gasaustausch|"
                r"wassersäule|meeresgrund|meeresboden|\balgen\b|plankton")
ICE_ON_RE = r"\b(?:auf|über) (?:dem|das|der) (?:\w+ )?(?:eis|eisfläche|eisdecke)\b|\b(?:aufs|übers) eis\b"
ICE_LAND_RE = r"küste|\bdorf|dörfer|\bstadt\b|städte|\bhäuser|\bstrand|\bufer\b|an land\b|festland"
ICE_PEOPLE_RE = r"reisende|menschen|leute|händler|soldaten|armee|truppen|\bheer\b|marschier|schlittschuh|wirtsh|gasth|\bmarkt|\bbuden|spaziergänger|familien"
ICE_COAST = {"sky": "", "ground": "snow", "elements": ["village", "packice"]}
ICE_HARBOR = {"sky": "", "ground": "quay", "elements": ["packice", "harbor"]}
ICE_ARMY_RE = r"armee|soldaten|truppen|\bheer\b|marschier|regiment"


# Waldfrosch (Prüfung 24.11.2026, Plan „Der Waldfrosch: Der Zombie der Tierwelt friert einfach ein“): Das Video handelt von einem Frosch, der einfriert und
# wieder auftaut – gezeigt wurde ein knallgelber, lächelnder Pfeilgiftfrosch im Schnee, ein Gehirn auf Beinen neben ihm („keine Gehirnaktivität“), leerer Wald
# mit Sonne und ein Eisbrocken ohne Tier. Die Regie führt Buch über seinen Zustand und zeigt ihn in jedem Bild so, wie der Satz ihn beschreibt:
# gefroren im Eisblock im Schneewald (`woodfrog`, action `frozen`), beim Auftauen mit Rest-Eis und Pfütze im Frühlingswald (`thaw`), danach lebendig.
FROSTFROG_RE = r"waldfr[oö]sch"
FF_FREEZE_RE = r"fr[oö]sch\w* (?:\w+ ){0,4}(?:friert|gefriert|erstarrt)|friert (?:\w+ ){0,5}ein\b|einfrier|eingefror|gefrier|gefror|eis(?:block|klotz|klumpen|würfel)"
FF_COLD_RE = (r"friert|frier|gefror|gefrier|eingefror|erstarr|\bstarr\b|\bsteif|\beis\b|eiskristall|\bminus\b|\bfrost\b|winter|\btot\b|atemzug|atmet nicht|"
              r"hört auf zu schlagen|steht (?:\w+ )?still|bleibt (?:\w+ )?stehen|\bwartet\b|kälte|\bkalt")
FF_THAW_RE = r"\btaut\b|auftau|aufgetaut|schmilz|schmelz|wärmer|\bwarm\b"
FF_LIVE_RE = r"hüpf|\bspring|wacht (?:\w+ ){0,5}auf\b|aufwach|aufgewacht|lebendig|quak|schlägt wieder|wieder (?:\w+ ){0,4}schlagen|\bmeister\b|als wäre nichts"
FF_YOU_RE = r"\b(du|dein\w*|dir|dich|ich|mein\w*|mir|mich|forscher\w*|wissenschaftler\w*|ärzt\w*|arzt|mensch\w*)\b"
FF_LAB_RE = r"forscher|wissenschaftler|\blabor|spenderorgan|transplant|\bmedizin|\bärzt|\barzt|\bklinik|krankenhaus"
FF_INSERTS = ("zucker", "sugar", "traubenzucker", "zuckerwürfel", "glukose", "glucose")   # nur der Zucker bleibt groß im Bild – kein loses Herz, kein Eisbrocken
FF_WINTER = {"sky": "day", "ground": "snow", "elements": ["forest"]}
FF_SPRING = {"sky": "day", "ground": "grass", "elements": ["forest"]}


def frost_frog(scenes, topic=""):
    low_t = str(topic or "").lower()
    texts = " ".join(str(sc.get("text") or "").lower() for sc in scenes if isinstance(sc, dict))
    return bool(re.search(FROSTFROG_RE, low_t + " " + texts) and re.search(FF_FREEZE_RE, low_t + " " + texts)) or \
        bool(re.search(r"fr[oö]sch", low_t) and re.search(FF_FREEZE_RE, low_t))


def _frost_frog(scenes, topic="", main_id="du"):
    if not frost_frog(scenes, topic):
        return scenes
    state, run, last_i = "frozen", 0, len(scenes) - 1
    for i, sc in enumerate(scenes):
        if not isinstance(sc, dict):
            continue
        low = str(sc.get("text") or "").lower()
        if re.search(FF_THAW_RE, low):
            state = "thaw"
        elif re.search(FF_LIVE_RE, low):
            state = "live"
        elif re.search(FF_COLD_RE, low) or i == last_i:   # der Schlusssatz führt als Schleife zurück zum ersten Bild
            state = "frozen"
        elif state == "thaw":
            state = "live"
        shot = str(sc.get("shot") or "")
        if shot == "graphic" and graphics.clean(sc.get("graphic")):
            run = 0
            continue
        if shot == "insert" and any(isinstance(q, dict) and str(q.get("type") or "").lower().replace("lib_", "") in FF_INSERTS for q in sc.get("props") or []):
            run = 0
            continue                                      # der Zuckerhaufen groß im Bild bleibt
        acts_in = [a for a in (sc.get("actors") or []) if isinstance(a, dict)]
        frog_in = any(str(a.get("kind") or "").lower() in ("frog", "woodfrog") or re.search(r"fr[oö]sch|frog|^_tier", str(a.get("id") or "").lower()) for a in acts_in)
        human = next((a for a in acts_in if not a.get("kind") and not str(a.get("id") or "").startswith("_")
                      and not re.search(r"fr[oö]sch|frog|tier", str(a.get("id") or "").lower())), None)
        if human is not None and not re.search(FF_YOU_RE, low):
            human = None                                  # „Medizinisch gesehen ist dieser Frosch tot“: der Frosch, kein Mensch, der sich am Kopf kratzt
        if re.search(FF_LAB_RE, low) and not re.search(r"fr[oö]sch|hüpf|\bspring|\btaut\b|auftau|friert|gefrier|gefror", low):
            humans = [a for a in acts_in if not a.get("kind") and not str(a.get("id") or "").startswith("_") and not re.search(r"fr[oö]sch|frog|tier", str(a.get("id") or "").lower())]
            humans = humans or [{"id": "_forscher", "action": "think", "emotion": "", "emote": "", "pos": "center", "facing": "right", "speaks": False, "say": "", "hold": "",
                                 "look": {"shirt": "weiß", "hair": "kurz", "hair_color": "braun"}}]
            rp_f = places.resolve(backdrop(sc)) if not isinstance(backdrop(sc), dict) else "custom"
            if rp_f not in places.PLACES or rp_f in places.OUTDOOR or rp_f == "custom":
                sc.update(place="lab", backdrop=None, time="day", weather="")
            sc.update(actors=humans, crowd="", float="", props=[])   # „Forscher untersuchen den Trick für Spenderorgane“: im Labor, ohne Frosch – nicht im Wald
            run = 0
            continue
        frog = {"id": "_tier", "kind": "woodfrog", "hero": True, "pos": "center", "emotion": "happy" if state == "live" else "", "emote": "", "say": "", "hold": "",
                "action": "frozen" if state == "frozen" else "thaw" if state == "thaw" else "hop" if re.search(r"hüpf|\bspring", low) else "idle",
                "facing": "left" if run % 2 else "right", "speaks": False}
        if human is not None:
            human = dict(human)
            human.pop("to", None)
            human.update(pos=300, facing="right")
            if str(human.get("action") or "").lower() in ("walk", "run", ""):
                human["action"] = "idle"
            acts = [human]
            if frog_in or re.search(r"fr[oö]sch|\b(?:er|ihn|ihm)\b", low):
                frog.update(pos=770, facing="left", _ksz=0.62)
                acts.append(frog)
            run = 0
        else:
            if run % 3 == 1:
                frog.update(pos=420, _ksz=0.82)           # nie dreimal dasselbe Bild: mal seitlich und etwas kleiner
            elif run % 3 == 2:
                frog.update(pos=640, _ksz=0.92)
            acts = [frog]
            run += 1
        winter = state == "frozen"
        sun = bool(re.search(r"sonne|sonnenstrahl", low)) or state == "thaw"
        sc.update(actors=acts, crowd="", float="", place="forest", backdrop=dict(FF_WINTER if winter else FF_SPRING), time="day", weather="cold" if winter else "",
                  props=[{"type": "sun"}] if sun else [], mood="")
        if shot in ("event", "insert", "close"):
            sc["shot"] = ""
        if not isinstance(sc.get("overlay"), dict) and human is None and re.search(r"\bherz", low):   # das Herz: am Frosch gezeigt, nicht als loses Herz vor leerem Grund
            if state == "frozen" and re.search(r"hört (?:\w+ ){0,3}auf|steht (?:\w+ ){0,2}still|bleibt (?:\w+ ){0,2}stehen|stoppt|schlägt nicht|kein herzschlag|setzt aus", low):
                sc["overlay"] = {"type": "tag", "text": "KEIN HERZSCHLAG"}
            elif state != "frozen" and re.search(r"wieder|von selbst|von allein|springt (?:\w+ ){0,2}an", low):
                sc["overlay"] = {"type": "tag", "text": "HERZ SCHLÄGT WIEDER"}
        sc["_cute"] = "woodfrog"
    return scenes



# Tiefsee-Anglerfisch (Prüfung 26.11.2026, Video 222 „Tiefsee-Anglerfisch: Die gefährlichste Falle der Welt“): 80 Sekunden lang schwamm ein lächelnder
# orangefarbener Clownfisch mit Sprechblase „HI!“ durchs Bild, die „nach innen gebogenen Zähne“ waren ein rosa Menschengebiss, bei „Kleine Fische schwimmen
# ins Licht“ war der Meeresgrund leer. Die Regie zeigt in jedem Satz den Anglerfisch (`extras.creature("angler")`) so, wie der Satz ihn beschreibt.
ANGLER_RE = r"anglerfisch|tiefsee-?angler|seeteufel|laternenfisch mit angel"
ANG_MALE_RE = r"männchen|weibchen|verwächs|verwachs|verschmilz|verschmelz|blutkreislauf|\borgan\b|nährstoff|parasit|paarung|partner"
ANG_FUSED_RE = r"schrumpf|\borgan\b|anhängsel|anhang|übrig bleibt|nur noch"
ANG_FUSE_RE = r"verwächs|verwachs|verschmilz|verschmelz|blutkreislauf|nährstoff|teilen sich|versorgt"
ANG_BITE_RE = r"beißt|beisst|festbeiß|verbeiß|klammert|heftet|dockt"
ANG_FULL_RE = r"\bmagen|dehnbar|verdau|verschluckt|verschlingt (?:\w+ ){0,4}(?:doppelt|größer)|doppelt so groß"
ANG_GAPE_RE = r"\bmaul|riesenmaul|gebiss|\bzähne|\bzahn|schnapp|verschling|saugt|sog\b|reißt (?:\w+ ){0,6}auf"
ANG_WIGGLE_RE = r"beweg|wackel|zappel|\bwurm|schwenk|leuchtkörper|köder"
ANG_LURE_RE = r"beweg|wackel|zappel|\bwurm|schwenk|\bangel\b|leuchtkörper|laterne|bakterien|scheinwerfer|köder|leuchtorgan"
ANG_PREY_RE = r"\bbeute|kleine fische|\bopfer|ins licht|zum licht|angelockt|lockt|neugierig"
ANG_FAR_RE = r"finsternis|dunkelheit|stockdunkel|pechschwarz|kein (?:\w+ )?licht|lichtpunkt|lauert|zu spät|metern tiefe|kilometer tiefe"
ANG_OFF_RE = r"licht aus|knipst (?:\w+ ){0,4}aus|erlischt|schaltet (?:\w+ ){0,4}(?:ab|aus)"
ANG_YOU_RE = r"als würdest du|als ob du|als müsstest du|stell dir vor,? du|\bdu (?:isst|müsstest|würdest|könntest)\b|so groß (?:ist )?wie du\b"
ANG_SEA = {"lure": (540, 1.0), "": (500, 0.95), "prey": (430, 0.95), "gape": (520, 1.12), "full": (560, 1.0), "far": (600, 0.8), "dark": (540, 0.95),
           "pair": (480, 0.95), "male": (560, 1.05), "fuse": (540, 1.1), "fused": (560, 1.05)}


def angler_story(scenes, topic=""):
    texts = " ".join(str(sc.get("text") or "").lower() for sc in scenes if isinstance(sc, dict))
    return bool(re.search(ANGLER_RE, str(topic or "").lower() + " " + texts))


# Sprechender Wecker (Prüfung 27.11.2026, Video 225 „Mein Wecker terrorisiert mich“): Handelt das Video von einem Wecker, der selbst etwas tut
# (lobt, schreit, droht, lacht, hackt das WLAN), steht er in jedem Satz, der von ihm spricht, als Figur mit Gesicht neben dem Menschen – im Zustand
# des Satzes (freundlich, klingelnd/brüllend, lachend, unheimlich sanft). Vorher: ein winziger stummer Wecker auf dem Nachttisch, die Figur allein.
WECKER_ACT_RE = (r"lob|schrie|schrei|brüll|droh|terror|befahl|befiehl|zwing|bestraf|bestimm|hack|blockier|sperr|verriegel|klingel|schrill|antwort|lach|sagt|"
                 r"flüster|spielt|motivier|weck|verlang|forder|kommandier|verbiet|verbot|übern[ia]mm|zählt|meldet|ruft|rief|kichert|summt|piept|heult|meint|stornier|bestell|nett\b")
WECKER_ANGRY_RE = (r"schrie|schrei|brüll|droh|terror|befahl|befiehl|zwing|bestraf|bestimm|hack|blockier|sperr|verriegel|klingel|schrill|sirene|alarm|"
                   r"kommandier|verbiet|verbot|verlang|forder|snooze|schlummer|heult|piept|gnade")
WECKER_HAPPY_RE = r"\blob|motivier|lieblings|kompliment|freundlich|fröhlich|gratulier|nett\b|charmant|lächel|summt"
WECKER_SOFT_RE = r"sanft|leise|flüster|säusel|zuckersüß|ganz ruhig|ruhiger stimme"
WECKER_REF_RE = r"wecker|\b(?:er|ihm|ihn)\b|\bgerät|\bkiste\b|\bding\b|snooze|schlummer"


# Exoskelett-Video (Prüfung 27.11.2026, Video 227): Im ganzen Video trug die Figur ihren Pulli – das Exoskelett stand als blauer Roboter daneben,
# „Motoren an den Gelenken“ zeigte einen Automotor neben einem Bizeps, „drückt dich zu Boden“ eine Wippe. Jetzt TRÄGT die Hauptfigur das Exoskelett
# (rig: outfit exo) in jeder Szene; Akku leer → nichts leuchtet, die Figur hängt gebeugt im Anzug; „hebst/stemmst“ → Langhantel über dem Kopf;
# kein loser Roboter, kein Automotor, keine Waage daneben.
EXO_RE = r"exoskelett|exo-?anzug|roboteranzug|kraftanzug|exosuit"
EXO_OFF_RE = (r"akku\w*\b[^.!?]{0,40}\b(?:leer|am ende|schlapp|aufgebraucht)|leere\w* akku|ohne strom|kein\w* strom|strom (?:ist )?(?:weg|aus|alle)\b|"
              r"(?:anzug|exoskelett|motor\w*)\b[^.!?]{0,30}\b(?:geht aus|schaltet\w* (?:sich )?ab|fällt aus|streikt|bleibt stehen)|saft aus")
EXO_HEAVY_RE = r"zu boden|in die knie|drückt dich|zieht dich (?:nach unten|runter)|lastet|schleppst du|wiegt (?:er|der anzug|das exoskelett|es)\b[^.!?]{0,30}kilo"
EXO_LIFT_RE = r"\b(?:heb|stemm|wuchte|hochheb|hebst|hebt)\w*|\bhoch\b[^.!?]{0,20}\bkilo|kilo\w*\b[^.!?]{0,30}\bfühl\w* sich"
EXO_SLOW_RE = r"schritttempo|schrittgeschwindigkeit|\bgehst|\bläufst|\bstapfst|\bmarschierst|\bgehen\b|\bspazier"
EXO_WORK_RE = r"\bfabrik|werkhalle|montage|fließband|\bwerk\b|über dem kopf|überkopf|autowerk"
EXO_REHA_RE = r"\breha\b|reha-|rehaklinik|\bklinik|gelähmt|querschnitt|therapie"
EXO_JUNK = ("lib_exoskelett", "engine", "lib_muskel", "robot", "scale", "lib_motor", "lib_roboter", "lib_roboteranzug")


def exo_story(scenes, topic=""):
    if re.search(EXO_RE, topic_head(str(topic or "").lower())):
        return True
    return sum(1 for sc in scenes if isinstance(sc, dict) and re.search(EXO_RE, str(sc.get("text") or "").lower())) >= 3


def _exo_story(scenes, topic="", main_id="du"):
    if not exo_story(scenes, topic):
        return scenes
    mains = MAIN_IDS + (str(main_id).lower(),)
    prev_sig = None
    for i, sc in enumerate(scenes):
        if not isinstance(sc, dict):
            continue
        low = str(sc.get("text") or "").lower()
        shot = str(sc.get("shot") or "")
        if shot in ("graphic", "mirror") and (shot == "mirror" or graphics.clean(sc.get("graphic")) or isinstance(sc.get("overlay"), dict)):
            prev_sig = None
            continue
        junk = [q for q in (sc.get("props") or []) if _pkey(q) in EXO_JUNK] if isinstance(sc.get("props"), list) else []
        if junk:
            sc["props"] = [q for q in sc["props"] if _pkey(q) not in EXO_JUNK]
        acts = [a for a in (sc.get("actors") or []) if isinstance(a, dict)]
        acts = [a for a in acts if str(a.get("kind") or "").lower() not in ("robot", "agent")
                and not (str(a.get("kind") or "").lower() == "brain" and not re.search(r"gehirn|\bhirn", low))]
        me = next((a for a in acts if not a.get("kind") and str(a.get("id") or "").lower() in mains), None) or next((a for a in acts if not a.get("kind")), None)
        if me is None:
            if places.resolve(backdrop(sc)) in ("germany", "worldmap"):
                prev_sig = None
                continue
            me = {"id": main_id, "action": "idle", "emotion": "", "emote": "", "say": "", "hold": "", "pos": "center", "speaks": False}
            acts.insert(0, me)
        sc["actors"] = acts
        if shot in ("insert", "graphic", "event"):
            sc["shot"] = shot = ""                        # der Schnitt auf ein loses Ding (Motor, Roboter) entfällt, ebenso die Totale mit winziger Figur: gezeigt wird die Figur im Anzug
        if "?" in str(me.get("emote") or "") and "?" not in str(sc.get("text") or ""):
            me["emote"] = ""                              # Fragezeichen über dem Kopf nur an einer Frage
        if True:                                          # Fabrik = Werkhalle (drinnen, ohne Passanten und Autos), Reha = Klinik
            to_pl = "garage" if re.search(EXO_WORK_RE, low) else "hospital" if re.search(EXO_REHA_RE, low) else ""
            if to_pl and (isinstance(sc.get("backdrop"), dict) or places.resolve(sc.get("place")) != to_pl):
                sc["place"], sc["crowd"] = to_pl, ""
                sc.pop("backdrop", None)
                sc["props"] = [q for q in (sc.get("props") or []) if _pkey(q) not in ("car", "police", "ambulance", "bike")]
                if shot == "event":
                    sc["shot"] = shot = ""
        off = bool(re.search(EXO_OFF_RE, low))
        heavy = bool(re.search(EXO_HEAVY_RE, low))
        lift = bool(re.search(EXO_LIFT_RE, low)) and not denied(EXO_LIFT_RE, low) and not off and not heavy
        slow = bool(re.search(EXO_SLOW_RE, low)) or (bool(re.search(HYBRID_RUN_RE, low)) and denied(r"\brenn\w*|\bsprint\w*", low))
        me["_outfit"] = "exo_off" if off else "exo"
        act = str(me.get("action") or "").lower()
        if off or heavy:                                  # Akku leer / der Anzug drückt: gebeugt, erschöpft – nicht fröhlich, nicht im Lauf
            me.update(action="sad", emotion="sad", emote="")
            me.pop("to", None)
            me.pop("_jog", None)
            if not isinstance(me.get("pos"), (int, float)) and str(me.get("pos") or "") in ("offleft", "offright", ""):
                me["pos"] = "center"
            sc["_no_cut"] = True
        elif lift:                                        # „hebst neunzig Kilo“: Langhantel über dem Kopf
            me.update(action="idle", emotion="happy", emote="", hold="", pos="center", _lift="barbell")
            me.pop("to", None)
            me.pop("_jog", None)
            sc["_no_cut"] = True
            if shot == "close":
                sc["shot"] = ""
            if isinstance(sc.get("props"), list):
                sc["props"] = []                          # die Hantel ist über dem Kopf – keine zweite (gelernte) auf dem Tisch, nichts, was die Scheiben verdeckt
        elif slow and act in ("run", "jump", "dance", "float", "fall"):
            me["action"] = "walk"                         # ein Exoskelett geht – es sprintet nicht
            me.pop("_jog", None)
        elif act in ("float", "fall", "sleep") and not re.search(r"schweb|flieg|stürz|fäll|fall|schl[aä]f|lieg", low):
            me["action"] = "idle"
        sig = (me.get("action"), me.get("_outfit"), bool(me.get("_lift")), places.resolve(backdrop(sc)))
        if sig == prev_sig and not me.get("_lift") and me.get("action") in ("idle", "talk", "sad", "think"):
            me["facing"] = "left" if str(me.get("facing") or "right") != "left" else "right"   # zweimal derselbe Aufbau hintereinander: gespiegelt
        prev_sig = sig
    return scenes


def _barbell(frame, cx, y, k):
    """Langhantel quer über den Händen (stage._exo_story: „hebst neunzig Kilo“): Stange, je zwei Scheiben, Verschlüsse."""
    d = ImageDraw.Draw(frame, "RGBA")
    half = 300 * k
    d.rounded_rectangle((cx - half, y - 11 * k, cx + half, y + 11 * k), 8 * k, fill=INK)
    d.rounded_rectangle((cx - half + 4 * k, y - 7 * k, cx + half - 4 * k, y + 5 * k), 6 * k, fill=(196, 204, 216))
    for sgn in (-1, 1):
        for j, (off_, h_, col) in enumerate(((226, 112, (58, 62, 78)), (268, 88, (214, 70, 60)))):
            px = cx + sgn * off_ * k
            d.rounded_rectangle((px - 22 * k, y - h_ * k - 5 * k, px + 22 * k, y + h_ * k + 5 * k), 14 * k, fill=INK)
            d.rounded_rectangle((px - 17 * k, y - h_ * k, px + 17 * k, y + h_ * k), 11 * k, fill=rig._dark(col, 0.25))
            d.rounded_rectangle((px - 17 * k, y - h_ * k, px + 9 * k, y + h_ * k - 10 * k), 11 * k, fill=col)
            d.rounded_rectangle((px - 11 * k, y - h_ * k + 12 * k, px - 5 * k, y - h_ * k * 0.2), 3 * k, fill=rig._light(col, 0.35))
        px = cx + sgn * 190 * k
        d.rounded_rectangle((px - 12 * k, y - 24 * k, px + 12 * k, y + 24 * k), 6 * k, fill=INK)
        d.rounded_rectangle((px - 8 * k, y - 20 * k, px + 8 * k, y + 20 * k), 5 * k, fill=(150, 158, 174))


def wecker_story(scenes, topic=""):
    texts = [str(sc.get("text") or "").lower() for sc in scenes if isinstance(sc, dict)]
    if "wecker" not in str(topic or "").lower() and sum("wecker" in x for x in texts) < 3:
        return False
    return sum(1 for x in texts if re.search(WECKER_REF_RE, x) and re.search(WECKER_ACT_RE, x)) >= 2


def _wecker_story(scenes, topic="", main_id="du"):
    if not wecker_story(scenes, topic):
        return scenes
    n_side, prev_solo = 0, False
    for i, sc in enumerate(scenes):
        if not isinstance(sc, dict):
            continue
        low = str(sc.get("text") or "").lower()
        shot = str(sc.get("shot") or "")
        if shot in ("graphic", "mirror") or not re.search(WECKER_REF_RE, low):
            prev_solo = False
            continue
        acts = [a for a in (sc.get("actors") or []) if isinstance(a, dict)]
        if any(not a.get("kind") and str(a.get("id") or "").lower() not in MAIN_IDS + (str(main_id).lower(),) and not str(a.get("id") or "").startswith("_")
               for a in acts) and "wecker" not in low:
            prev_solo = False
            continue                                      # ein anderer Mensch im Bild: „er“ kann auch er sein
        acts = [a for a in acts if str(a.get("kind") or "").lower() not in ("robot", "agent", "wecker")]
        human = next((a for a in acts if not a.get("kind")), None)
        lol = bool(re.search(r"lach|kicher|stornier|schadenfroh|grinst", low))
        soft = bool(re.search(WECKER_SOFT_RE, low))
        angry = bool(re.search(WECKER_ANGRY_RE, low)) and not soft and not lol
        happy = bool(re.search(WECKER_HAPPY_RE, low)) and not angry and not soft and not lol
        press = bool(re.search(r"drück\w* (?:\w+ ){0,3}(?:snooze|schlummer|den wecker|die taste|den knopf)|(?:snooze|schlummer)\w*[- ]?(?:taste|knopf)?\w* (?:\w+ ){0,2}(?:gedrückt|drück)", low))
        w = {"id": "_wecker", "kind": "wecker", "action": "laugh" if lol else "soft" if soft else "ring" if angry else "idle",
             "emotion": "angry" if angry else "happy" if (happy or lol) else "", "emote": "", "say": "", "hold": "", "speaks": False}
        solo = lol and not prev_solo and bool(re.search(r"lach|kicher", low)) and not isinstance(sc.get("overlay"), dict)   # „antwortete mit einem eiskalten Roboterlachen“: der Wecker allein, groß, lacht
        if isinstance(sc.get("props"), list):
            sc["props"] = [q for q in sc["props"] if _pkey(q) not in ("lib_wecker", "clock", "lib_stoppuhr")]
        if shot in ("insert", "close", "event"):
            sc["shot"] = ""
        sc["_no_cut"] = True
        if solo or human is None:
            w.update(pos="center", facing="right", _ksz=1.25 if solo else 1.0)
            sc["actors"] = [w]
            prev_solo = True
            continue
        prev_solo = False
        flip = n_side % 3 == 2                            # meist steht der Wecker rechts; jedes dritte Mal gespiegelt, damit nicht jedes Bild gleich aufgebaut ist
        n_side += 1
        hx, wx = (330, 770) if not flip else (750, 310)
        if any(_pkey(q) == "door_locked" for q in (sc.get("props") or [])):               # vor der verriegelten Tür: Mensch, Wecker, Tür nebeneinander – das Schloss bleibt sichtbar
            flip, (hx, wx) = False, (230, 520)
        if press:                                         # „Ich drückte auf Snooze“: die Hand liegt auf dem Wecker
            hx, wx = (410, 690) if not flip else (670, 390)
            human.update(action="point", emotion=str(human.get("emotion") or "angry"), emote="")
        elif str(human.get("action") or "").lower() in ("walk", "run") and human.get("to"):
            human.update(pos=("offleft" if not flip else "offright"), to=hx)          # läuft herein und bleibt vor dem Wecker stehen – nicht durch ihn hindurch
        if not (str(human.get("action") or "").lower() in ("walk", "run") and human.get("to")):
            human["pos"] = hx
            human.pop("to", None)
        human["facing"] = "right" if not flip else "left"
        if str(human.get("emote") or "") == "?" and (angry or lol or soft):
            human["emote"] = ""
        if soft and str(human.get("action") or "").lower() in ("", "idle", "talk", "shocked"):
            human["action"] = "shiver"
        if re.search(r"\bkoch", low) and isinstance(sc.get("props"), list):               # „koche ich ihm Haferbrei“: die Schüssel in der Hand, dem Wecker hingehalten
            dish = next((q for q in sc["props"] if extras.held_key(_pkey(q)).startswith("prop:")), None)
            if dish is not None and not human.get("hold"):
                human["hold"] = _pkey(dish)
                sc["props"] = [q for q in sc["props"] if q is not dish]
                human["action"] = "talk"
        w.update(pos=wx, facing="left" if not flip else "right")
        sc["actors"] = [human, w]
    return scenes


# Leute an der Tür (Prüfung 27.11.2026, Video 225): „Die Nachbarn klopften genervt an meine Tür“ zeigte die Hauptfigur allein im Flur – kein Nachbar.
# Jetzt stehen zwei verärgerte Nachbarn im Hausflur vor der Tür. „… verriegelte die Tür“ zeigt eine Tür mit Riegel und Schloss, kein loses Schloss
# auf dem Tisch. „… hat meine Mutter blockiert“: die Blockierte steht nicht fröhlich im selben Zimmer.
KNOCK_RE = r"(nachbar\w*|vermieter\w*|hausmeister\w*)\b[^.!?]{0,60}\b(?:klopf|hämmer|poch|klingel|trommel)\w*[^.!?]{0,40}\btür|\b(?:klopf|hämmer|poch|klingel|trommel)\w*[^.!?]{0,40}\b(nachbar\w*|vermieter\w*|hausmeister\w*)"
LOCKED_RE = r"(?:verriegel|verschl[oö]ss|versperr|abgesperr|abgeschlossen|sperrt\w* (?:\w+ ){0,3}die)\w*[^.!?]{0,40}\btür|\btür\w*\b[^.!?]{0,40}(?:verriegel|verschlossen|versperr|abgesperr|abgeschlossen|lässt sich nicht (?:mehr )?öffnen)"
BLOCKED_RE = r"\b(mutter|mama|mutti|vater|papa|oma|opa|freundin|freund|schwester|bruder|chef|chefin|partner|partnerin)\b[^.!?]{0,20}\b(?:blockiert|geblockt|gesperrt|gelöscht)"


def _door_people(scenes, main_id="du"):
    for sc in scenes:
        if not isinstance(sc, dict) or str(sc.get("shot") or "") in ("graphic", "mirror"):
            continue
        low = str(sc.get("text") or "").lower()
        acts = [a for a in (sc.get("actors") or []) if isinstance(a, dict)]
        m = re.search(KNOCK_RE, low)
        if m and not denied(r"klopf|hämmer|poch|klingel|trommel", low):
            many = (m.group(1) or m.group(2) or "").endswith(("n", "s"))
            angry = "angry" if re.search(r"genervt|wütend|sauer|verärgert|zornig|empört|beschwer|ruhestörung|hämmer|trommel", low) else "worried"
            people = [{"id": "_nachbar1", "look": {"hair": "short", "hair_color": "grau", "shirt": "grün", "gender": "m"}, "action": "point", "emotion": angry,
                       "emote": "!", "say": "", "hold": "", "pos": 470, "facing": "right", "speaks": False}]
            if many:
                people.insert(0, {"id": "_nachbar2", "look": {"hair": "bun", "hair_color": "rot", "shirt": "lila", "gender": "w"}, "action": "talk", "emotion": angry,
                                  "emote": "", "say": "", "hold": "", "pos": 230, "facing": "right", "speaks": False})
            sc["actors"] = people                         # gezeigt wird die Seite der Nachbarn: sie stehen im Hausflur vor der Tür
            sc["place"], sc["crowd"], sc["_no_cut"] = "hallway", "", True
            sc.pop("backdrop", None)
            sc["props"] = [{"type": "door", "x": 800}]
            if str(sc.get("shot") or "") in ("insert", "close", "event"):
                sc["shot"] = ""
            continue
        if re.search(LOCKED_RE, low) and not denied(r"verriegel|verschl[oö]ss|versperr|abgesperr|abgeschlossen", low) and isinstance(sc.get("props"), list):
            sc["props"] = [q for q in sc["props"] if _pkey(q) not in ("door", "lib_vorhaengeschloss", "lib_schloss", "lib_tuerrahmen")] + [{"type": "door_locked", "x": 906}]
            sc["_no_cut"] = True
            if str(sc.get("shot") or "") in ("insert", "close", "event"):
                sc["shot"] = ""
            me = next((a for a in acts if not a.get("kind")), None)
            if me is not None:
                me.update(pos=330, facing="right")
                me.pop("to", None)
                if str(me.get("action") or "").lower() in ("walk", "run", "shake", "dance", ""):
                    me["action"] = "shocked"
        m_b = re.search(BLOCKED_RE, low)
        if m_b and len([a for a in acts if not a.get("kind")]) > 1:
            keep = [a for a in acts if a.get("kind") or str(a.get("id") or "").lower() in MAIN_IDS + (str(main_id).lower(),)]
            if keep:
                sc["actors"] = keep
                for a in keep:
                    if not a.get("kind") and isinstance(a.get("pos"), (int, float)):
                        a["pos"] = "center"


def _angler_story(scenes, topic=""):
    if not angler_story(scenes, topic):
        return scenes
    prev, run, last_i = None, 0, len(scenes) - 1
    for i, sc in enumerate(scenes):
        if not isinstance(sc, dict):
            continue
        low = str(sc.get("text") or "").lower()
        shot = str(sc.get("shot") or "")
        if shot == "graphic" and graphics.clean(sc.get("graphic")):
            prev = None
            continue
        if re.search(ANG_YOU_RE, low):                    # der Vergleich mit dir („als würdest du ein Schnitzel essen …“) spielt bei dir, nicht in der Tiefsee
            humans = [a for a in (sc.get("actors") or []) if isinstance(a, dict) and not a.get("kind") and not str(a.get("id") or "").startswith("_")]
            if humans and places.resolve(backdrop(sc)) != "underwater":
                for a in humans:
                    if str(a.get("action") or "").lower() in ("walk", "run", ""):
                        a.update(action="shocked", emotion="shocked")
                    a.pop("to", None)
                humans[0].update(pos="center", facing="")
                if str(humans[0].get("emote") or "") == "?":
                    humans[0]["emote"] = ""               # kein Fragezeichen über dem Kopf: der Satz ist ein Vergleich, keine Frage
                sc["actors"] = humans[:1]
                prev = None
                continue
        if re.search(ANG_MALE_RE, low):
            act = "fused" if re.search(ANG_FUSED_RE, low) else "male" if re.search(ANG_BITE_RE, low) else "fuse" if re.search(ANG_FUSE_RE, low) else "pair"
        elif re.search(ANG_OFF_RE, low):
            act = "dark"
        elif re.search(ANG_FULL_RE, low):
            act = "full"
        elif re.search(ANG_WIGGLE_RE, low) and not re.search(r"reißt|schnapp|\bzähne|gebiss", low):
            act = "lure"                                  # „bewegt den Leuchtkörper vor seinem Maul wie einen Wurm“: die Angel zappelt, das Maul bleibt zu
        elif re.search(ANG_GAPE_RE, low):
            act = "gape"
        elif re.search(ANG_LURE_RE, low):
            act = "lure"
        elif re.search(ANG_PREY_RE, low):
            act = "prey"
        elif re.search(ANG_FAR_RE, low):
            act = "far"
        else:
            act = "lure" if prev != "lure" else ""
        if i == 0 and act in ("far", "dark", "", "pair", "male", "fuse", "fused"):
            act = "lure"                                  # das erste Bild zeigt den Fisch mit seinem Licht
        big = False
        if act == prev:                                   # nie zweimal hintereinander dasselbe Bild
            if act == "gape":
                big = True
            elif act in ("prey", "far"):
                act = "lure"
            elif act == "lure":
                act = "prey" if re.search(ANG_PREY_RE, low) else ""
            else:
                run += 1
        x, ksz = ANG_SEA.get(act, (540, 1.0))
        flip = run % 2 == 1
        fish = {"id": "_tier", "kind": "angler", "hero": True, "pos": (1080 - x) if flip else x, "_ksz": round(1.5 * ksz * (1.16 if big else 1.0), 2), "emotion": "", "emote": "", "say": "",
                "hold": "", "action": act, "facing": "left" if flip else "right", "speaks": False}
        run += 1
        prev = act
        ov = sc.get("overlay")
        if isinstance(ov, dict) and str(ov.get("type") or "") in ("phone", "note", "chat", "list"):
            sc["overlay"] = None                          # kein Handy, kein Zettel in der Tiefsee
        elif isinstance(ov, dict) and re.search(ANG_OFF_RE, str(ov.get("text") or "").lower()) and act != "dark":
            sc["overlay"] = None                          # „LICHT AUS“ über einem leuchtenden Köder widerspricht dem Bild
        sc.update(actors=[fish], crowd="", float="", place="underwater", backdrop=None, time="night", weather="", props=[], mood="", _no_cut=True, _cute="angler", _ov_low=3)   # Einblendungen ganz oben: die Karte „PERFEKTER KÖDER“ lag sonst genau auf Angel und Köder
        if shot in ("event", "insert", "close", "mirror"):
            sc["shot"] = ""
    return scenes


def _ice_story(scenes, topic):
    low_t = str(topic or "").lower()
    texts = [str(sc.get("text") or "").lower() for sc in scenes if isinstance(sc, dict)]
    n_ice = sum(1 for t_ in texts if re.search(FROZEN_RE, t_))
    sea = bool(re.search(FROZEN_SEA_RE, low_t)) or any(re.search(FROZEN_SEA_RE, t_) for t_ in texts)
    if not sea or not ((re.search(FROZEN_RE, low_t) and n_ice >= 1) or n_ice >= 3):
        return scenes
    _key = lambda q: extras.PROP_ALIASES.get(str((q.get("type") if isinstance(q, dict) else q) or "").lower(), str((q.get("type") if isinstance(q, dict) else q) or "").lower())   # noqa: E731
    main_i = next((str(a.get("id")) for sc in scenes if isinstance(sc, dict) for a in (sc.get("actors") or [])
                   if isinstance(a, dict) and not a.get("kind") and not str(a.get("id") or "").startswith("_")), "du")
    for sc in scenes:
        if not isinstance(sc, dict):
            continue
        shot = str(sc.get("shot") or "")
        if shot == "graphic" and graphics.clean(sc.get("graphic")):
            continue
        rp = places.resolve(backdrop(sc))
        if rp in MAPS or rp in ("space", "highsky") or (rp not in places.OUTDOOR and rp != "underwater"):
            continue                                      # Karten und Innenräume bleiben, wie sie sind
        low = str(sc.get("text") or "").lower()
        spec = places.spec_of(backdrop(sc)) or {}
        if not (rp in ("underwater", "beach", "snow", "lake", "icesea") or str(spec.get("ground") or "") in ("water", "ice", "snow")
                or set(spec.get("elements") or []) & {"sea", "glacier", "packice"} or re.search(FROZEN_RE, low) or re.search(FROZEN_SEA_RE, low)
                or any(str(a.get("kind") or "").lower() == "tardigrade" for a in (sc.get("actors") or []) if isinstance(a, dict))):
            continue                                      # Dürre auf dem Acker, Stadt, Wald: nicht jede Außenszene liegt auf dem Eis
        acts = [a for a in (sc.get("actors") or []) if isinstance(a, dict)]
        props = [q for q in (sc.get("props") or []) if isinstance(q, dict)]
        whale = bool(re.search(ICE_WHALE_RE, low))
        if whale and (re.search(ICE_HOLE_RE, low) or (rp != "underwater" and not re.search(ICE_UNDER_RE, low))):   # das Atemloch: ein Delfin/Schweinswal taucht in einem Loch in der Eisdecke auf
            sc.update(place="icesea", backdrop=None, props=[{"type": "icehole", "pos": 540}], actors=[], crowd="", shot="")
            continue
        if rp == "underwater" or (re.search(ICE_UNDER_RE, low) and not re.search(ICE_ON_RE, low)):
            keep = [a for a in acts if str(a.get("kind") or "").lower() in ("fish", "shark", "dolphin", "whale", "jelly", "shrimp", "mantis", "axolotl", "tardigrade", "diver", "puffer")]
            emo = MOOD_EMOTION.get(str(sc.get("mood") or ""), "") or "worried"
            if whale:
                keep = [{"id": "_delfin", "kind": "dolphin", "hero": True, "action": "idle", "emotion": emo, "pos": "center", "speaks": False, "emote": "", "say": "", "hold": "", "facing": "right"}]
            elif not keep:                                # kein leeres Wasser: ein Fisch unter dem Eis
                keep = [{"id": "_fisch", "kind": "fish", "action": "idle", "emotion": emo, "pos": "center", "speaks": False, "emote": "", "say": "", "hold": "", "facing": "right"}]
            sc.update(place="underwater", backdrop=None, time="day", weather="", _ice=True, actors=keep, crowd="",
                      props=[q for q in props if _key(q) in extras.WATER_KINDS])   # das Eis liegt als Decke oben – kein Eisberg am Meeresgrund, kein Schiff im Wasser
            if shot in ("insert", "close"):
                sc["shot"] = ""
            if str(sc.get("mood") or "") in ("scary", "tense", "sad", "panic"):
                sc["mood"] = "calm"                       # das Halbdunkel verschluckte die Eisdecke – die Not zeigt das Gesicht des Tiers
            continue
        coast = bool(re.search(ICE_LAND_RE, low)) and not re.search(ICE_ON_RE, low) and not re.search(ICE_SHIP_RE, low)
        harbor = bool(re.search(HARBOR_RE, low)) and not re.search(ICE_ON_RE, low)
        if harbor:                                        # „die Häfen frieren zu“: Kai mit Kränen und Frachter, das Hafenbecken ist Eis
            sc.update(place="harbor", backdrop=dict(ICE_HARBOR))
            props = [q for q in props if _key(q) not in ("ship", "ship_ice")]   # der Frachter liegt schon an der Kaimauer
            coast = True
        elif coast:
            if rp not in ("village", "street", "church"):
                sc.update(place="village", backdrop=dict(ICE_COAST))   # verschneites Küstendorf, dahinter das zugefrorene Meer
        else:
            sc.update(place="icesea", backdrop=None)
        props = [q for q in props if _key(q) not in ("wave", "debris", "flood") and (_key(q) != "ice" or re.search(r"eisberg", low))]
        if any(_key(q) == "ship" for q in props) or (re.search(ICE_SHIP_RE, low) and not coast):
            props = [q for q in props if _key(q) in extras.SKY][:1] + [{"type": "ship_ice", "pos": 540}]   # das Schiff steckt fest – es fährt nicht auf offenen Wellen
            sc["actors"], sc["crowd"] = [], ""
            if shot in ("insert", "close", "event"):
                sc["shot"] = ""                           # ganz im Bild, nicht vergrößert angeschnitten
        elif not coast and re.search(ICE_ARMY_RE, low):   # „eine ganze Armee marschiert über das Eis“: viele Leute ziehen übers Eis – nicht eine einzelne Figur
            sc["actors"], sc["crowd"] = [], "walk"
            if shot in ("close", "insert"):
                sc["shot"] = ""
        elif not coast and not [a for a in acts if not a.get("kind")] and re.search(ICE_PEOPLE_RE, low) and re.search(ICE_ON_RE, low):
            sc["crowd"] = "cheer" if str(sc.get("crowd") or "") == "cheer" else "walk"   # „auf dem Eis wurden Wirtshäuser aufgebaut“: Leute sind auf dem Eis unterwegs
        if not coast and str(sc.get("mood") or "") in ("tense", "sad") and str(sc.get("time") or "day").lower() not in ("night", "nacht"):
            sc["mood"] = "calm"                           # Halbdunkel mit Lichtkegel macht die weiße Eisfläche am hellen Tag zu grauem Matsch
        sc["props"] = props
        if not coast and sc.get("crowd") and not re.search(ICE_PEOPLE_RE + r"|" + ICE_ARMY_RE + r"|zu fuß|\blaufen\b|spazier|wander", low):
            sc["crowd"] = ""                              # Passanten schlendern nicht durch jede Eis-Szene – nur, wenn der Satz von Leuten auf dem Eis spricht
        if not props and not sc.get("actors") and not sc.get("crowd") and shot != "insert":
            sc["actors"] = [{"id": main_i, "action": "look_around", "emotion": "", "emote": "", "pos": "center", "speaks": False, "say": "", "hold": "", "facing": ""}]   # keine leere Eisfläche: die Hauptfigur steht staunend auf dem Eis
            if shot == "event":
                sc["shot"] = ""
    return scenes


# Alltags-Geschichten (Prüfung 15.11.2026, „Ich lebte wie 1348“): Haushaltsgerät als Figur, Haustier aus dem Satz, Brief in der Hand
FRIDGE_ID_RE = r"k(?:ü|ue|u)hlschrank|fridge|gefrierschrank"
PET_RE = ((r"katze|kater\b|kätzchen", "cat"), (r"\bhund(?:e|es|en|chen)?\b|welpe", "dog"))
PET_FLEE_RE = r"das weite|wegrenn|davon|reißaus|gerannt|rennt|rannte|flücht|flieh|floh\b|haut ab|abgehauen|weggelaufen|läuft weg|lief weg|versteckt"
LETTER_RE = r"abmahnung|\bbrief\b|\bbriefe\b|einschreiben|\bmahnung|umschlag|kündigungsschreiben|\bpost vom\b|\bvorladung|\bbescheid\b|strafzettel"
RADIO_RE = r"radio|funk|durchsage|sender|empfang|lautsprecher"
TEETH_RE = r"(?:zähne\w*|zahn|gebiss|lächeln)\b[^.!?]{0,60}\b(grün|gelb|schwarz|braun|blau)|\b(grün|gelb|schwarz|braun|blau)e[nrs]? (?:zähne|gebiss|lächeln)"
TEETH_COLORS = {"grün": (96, 190, 90), "gelb": (236, 208, 80), "schwarz": (58, 56, 62), "braun": (150, 104, 66), "blau": (90, 150, 230)}
BLANK_DISPLAY_RE = r"display\w* (?:steht|ist|zeigt|bleibt|erscheint)\b.{0,25}\b(?:nichts|leer|dunkel|schwarz|stumm|keine)|(?:nichts|keine \w+) (?:auf|in) (?:dem|deinem|ihrem|seinem) display|(?:leere[sn]?|dunkle[sn]?|schwarze[sn]?) display"
WORN_THINGS = ("hose", "jeans", "jacke", "hemd", "pullover", "pulli", "t-shirt", "shirt", "kleid", "rock", "mantel", "socke", "socken", "schuh", "schuhe", "kleidung", "stoff")
SCRUB_RE = r"schrubb|\bputz(?:t|e|en|st|te)\b|\breib(?:t|e|en|st)\b|\bkau(?:t|e|en|st)\b"


DEVICE_TALK_RE = r"sagt|meldet|fragt|verkündet|ruft|flüstert|petzt|verrät|beschwert|lacht|streikt|übernimmt|wirft|verriegelt|weigert|verweigert|schimpft|droht|antwortet|erklärt|behauptet|gesteht|plaudert|packt aus|zählt|liest|brüllt|motzt|meckert|protestiert|fordert|kündigt"


def _fridge_in(sc, acts, low, human_idle=True):
    """Stellt den Kühlschrank als Figur mit Gesicht neben den Menschen (kein gesichtsloses Gerät als Großaufnahme)."""
    human = [a for a in acts if not a.get("kind")][:1]
    for a in human:
        a["pos"] = "left"
        if a.get("action") == "walk":
            a["action"], a["to"] = "idle", ""
    sc["actors"] = human + [{"id": "kuehlschrank", "kind": "fridge", "action": "point" if human else "idle", "emotion": "angry" if re.search(
        r"kontrolle|verriegel|wirft|droht|schimpf|streik|weiger|fordert", low) else "happy", "pos": "right" if human else "center",
        "speaks": True, "emote": "!", "say": "", "hold": "", "facing": ""}]
    sc["props"] = [p for p in (sc.get("props") or []) if _pkey(p) not in ("fridge", "cans")]
    if str(sc.get("shot") or "") in ("insert", "event", "close"):
        sc["shot"] = ""
    if isinstance(backdrop(sc), dict) or places.resolve(backdrop(sc)) not in INDOOR:
        sc["place"] = "kitchen"
        sc.pop("backdrop", None)


def _pkey(p):
    k = str((p.get("type") if isinstance(p, dict) else p) or "").lower()
    return extras.PROP_ALIASES.get(k, k)


DEVICES = ((r"kühlschrank", "fridge"), (r"fernseh|\btv\b", "tv"), (r"router", "lib_router"), (r"wecker", "lib_wecker"), (r"\bnavis?\b|navigationsgerät", "car"))
CLOCK_TIME_RE = r"\bum (?:\w+ )?(?:\w+ )?uhr\b|\d\s*uhr\b|\buhr (?:nachts|morgens|abends|früh|mittags)|\buhrzeit"


def _devices(scenes):
    """Schlussdurchgang für sprechende Geräte (Prüfung 19.11.2026, Videos 156/157): Tut der Kühlschrank im Satz selbst etwas („meldet“, „fragt“,
    „übernimmt die Kontrolle“), steht er als Figur mit Gesicht neben dem Menschen – nicht als Möbel am Bildrand oder allein vor blauem Grund.
    Folgesätze mit „Er sagt …“, „Und er fragt …“ bleiben beim Gerät von eben (Kühlschrank-Figur, Fernseher, Router, Wecker). Ein Wecker ist keine
    Wanduhr am Boden; „um drei Uhr nachts“ ist eine Uhrzeit und kein Ding; der heimische Router steht nicht im Rechenzentrum; im Bus und in der Bahn
    läuft niemand durchs Bild; ein Zähler zeigt keine Wörter, die niemand sagt („7 HEUTE“)."""
    last = None
    for i, sc in enumerate(scenes):
        if not isinstance(sc, dict):
            continue
        low = str(sc.get("text") or "").lower()
        ov = sc.get("overlay") if isinstance(sc.get("overlay"), dict) else None
        if ov and str(ov.get("type") or "") == "counter" and isinstance(ov.get("unit"), str):
            ov["unit"] = " ".join(w for w in ov["unit"].split() if not (w.isalpha() and len(w) >= 4 and w.lower()[:5] not in low))
        if str(sc.get("shot") or "") == "graphic":
            continue
        acts = [a for a in (sc.get("actors") or []) if isinstance(a, dict)]
        if not isinstance(backdrop(sc), dict) and places.resolve(backdrop(sc)) == "transit":   # im Bus/in der Bahn läuft niemand durchs Bild: Fahrgäste stehen und schauen her
            if str(sc.get("crowd") or "") in ("walk", "cheer") or (not sc.get("crowd") and re.search(r"fahrg[aä]st|mitfahrer|\balle\b|leute|menschen|jeder", low)):
                sc["crowd"] = "watch"
            for a in acts:
                if a.get("action") in ("walk", "run") and not re.search(r"steig|rennt|läuft|geht|flücht|flieh", low):
                    a["action"], a["to"] = "idle", ""
                    if str(a.get("pos") or "").startswith("off"):
                        a["pos"] = "center"
        prev_d = scenes[i - 1] if i and isinstance(scenes[i - 1], dict) else {}
        if not isinstance(backdrop(sc), dict) and places.resolve(backdrop(sc)) == "station" and not re.search(r"bahnsteig|bahnhof|\bgleis|steig\w* (?:aus|ein)", low) \
                and (re.search(r"fahrg[aä]st|mitfahrer|\bim (?:\w+ )?(?:bus|abteil|waggon)\b|in der (?:\w+ )?(?:bahn|tram|straßenbahn)\b", low)
                     or (not isinstance(backdrop(prev_d), dict) and places.resolve(backdrop(prev_d)) == "transit" and str(prev_d.get("shot") or "") != "graphic")):
            sc["place"] = "transit"                                                  # Fahrgäste sitzen im Fahrzeug, nicht am Bahnsteig; der Folgesatz bleibt drin
            if str(sc.get("crowd") or "") in ("walk", "cheer", ""):
                sc["crowd"] = "watch"
            for a in acts:
                if a.get("action") in ("walk", "run"):
                    a["action"], a["to"] = "idle", ""
        if re.search(r"\bnavis?\b|navigationsgerät|\bim auto\b", low) and not isinstance(backdrop(sc), dict) and places.resolve(backdrop(sc)) in GARAGES \
                and not re.search(r"werkstatt|garage|hebebühne|schraub|reparier", low):
            sc["place"] = "street"                                                   # „Im Auto behauptet das Navi …“ spielt unterwegs, nicht in der Werkstatt
        if re.search(r"\bnavis?\b|navigationsgerät|\bim auto\b", low) and (isinstance(backdrop(sc), dict) or places.resolve(backdrop(sc)) in places.OUTDOOR):
            for a in acts:                                                           # „sitzt im Auto“: draußen säße die Figur auf einer Kiste am Gehweg vor dem Auto (Video 160)
                if not a.get("kind") and a.get("action") == "sit":
                    a["action"] = "idle"
        if isinstance(sc.get("props"), list):
            if re.search(CLOCK_TIME_RE, low) and not re.search(r"wanduhr|armbanduhr|die uhr\b|der uhr\b|eine uhr\b|wecker|zeiger|tickt", low):
                sc["props"] = [p for p in sc["props"] if _pkey(p) != "clock"]        # „um drei Uhr nachts“: eine Uhrzeit, keine Wanduhr auf dem Flurboden
            if re.search(r"wecker", low) and not denied(r"wecker", low) and "lib_wecker" in extras.SIZES:
                sc["props"] = [p for p in sc["props"] if _pkey(p) != "clock"]        # Wecker statt Wanduhr
                for a in acts:                                                       # … und keine Wanduhr in der Hand, größer als der Kopf (Video 173)
                    if isinstance(a, dict) and str(a.get("hold") or "") == "clock":
                        a["hold"] = ""
                if not any(_pkey(p) == "lib_wecker" for p in sc["props"]):
                    sc["props"].append({"type": "lib_wecker"})
        if re.search(r"router", low) and not isinstance(backdrop(sc), dict) and places.resolve(backdrop(sc)) == "serverroom" \
                and re.search(r"\bdein|\bmein|\bunser|zuhause|zu hause|daheim|wlan|wohnung", low):
            sc["place"] = "livingroom"                                               # der Router zu Hause steht nicht im Rechenzentrum
        named = next((k for pat, k in DEVICES if re.search(pat, low) and not denied(pat, low)), None)
        talks = bool(re.search(r"\b(?:" + DEVICE_TALK_RE + r")", low))
        pron = bool(re.match(r"(?:und |aber |dann |doch |denn )?(?:er|es|sie) ", low)) and talks
        dev = None
        if named:
            last = (named, i)
            dev = named if (talks or named == "fridge") else None
        elif pron and last and i - last[1] <= 2:
            dev = last[0]
            last = (dev, last[1])
            src = scenes[i - 1] if isinstance(scenes[i - 1], dict) else {}
            if str(src.get("shot") or "") != "graphic" and src.get("place") and backdrop(src) != backdrop(sc) and dev != "car":
                sc["place"], sc["time"] = src.get("place"), src.get("time", sc.get("time"))   # „Er sagt …“ spielt dort, wo das Gerät eben stand
                sc.pop("backdrop", None)
        elif not pron:
            last = last if (last and i - last[1] < 1) else None
        if dev == "fridge":
            m = re.search(r"kühlschrank\w*\b(.{0,90})", low)
            does = pron or (m and re.search(r"\b(?:" + DEVICE_TALK_RE + r")", m.group(1) + " " + low[:m.start()][-40:]))
            if does and not any(str(a.get("kind") or "") == "fridge" or re.search(FRIDGE_ID_RE, str(a.get("id") or "").lower()) for a in acts):
                _fridge_in(sc, acts, low)
        elif dev and pron and isinstance(sc.get("props"), list) and dev in extras.SIZES and not any(_pkey(p) == dev for p in sc["props"]) \
                and str(sc.get("shot") or "") not in ("close",) and (dev != "car" or isinstance(backdrop(sc), dict) or places.resolve(backdrop(sc)) in places.OUTDOOR):
            sc["props"] = sc["props"][:1] + [{"type": dev}]                          # das Gerät von eben bleibt im Bild


def _household(scenes):
    """Schlussdurchgang: (1) Heißt eine Figur „kuehlschrank“, ist sie der Kühlschrank mit Gesicht – ohne zweiten Kühlschrank daneben und nicht als
    gesichtslose Großaufnahme. (2) Nennt der Satz Katze oder Hund und steht kein Tier im Bild, kommt es dazu (läuft weg, wenn der Satz das sagt).
    (3) Abmahnung, Brief, Einschreiben: die Figur hält einen Umschlag – kein Radio, von dem niemand spricht."""
    fridge_char = any(re.search(FRIDGE_ID_RE, str(a.get("id") or "").lower()) for sc in scenes if isinstance(sc, dict)
                      for a in (sc.get("actors") or []) if isinstance(a, dict))
    vac_broken = False                                    # „mein Staubsauger explodierte“: ab da steht er kaputt da (Deckel auf, Staubwolke) – Prüfung 20.11.2026
    for sc in scenes:
        if not isinstance(sc, dict):
            continue
        low_v = str(sc.get("text") or "").lower()
        if "staubsauger" in low_v and re.search(r"explodier|knall|kaputt|qualm|raucht|rauch\b|geht .{0,20}in die luft|den geist auf|platzt", low_v):
            vac_broken = True
        if vac_broken:
            for q in (sc.get("props") or []):
                if isinstance(q, dict) and extras.PROP_ALIASES.get(str(q.get("type") or "").lower(), str(q.get("type") or "").lower()) == "vacuum":
                    q["type"] = "vacuum_broken"
            seen_v = False                                # Drehbuch nennt ihn und die Text-Regel stellt ihn dazu: nur einer steht da (Video 168: zwei ineinander)
            for q in list(sc.get("props") or []):
                if isinstance(q, dict) and q.get("type") == "vacuum_broken":
                    if seen_v:
                        sc["props"].remove(q)
                    seen_v = True
            if any(isinstance(q, dict) and q.get("type") == "vacuum_broken" for q in (sc.get("props") or [])):
                sc["props"] = [q for q in sc["props"] if not (isinstance(q, dict) and str(q.get("type") or "").lower() in ("smoke", "explosion", "fire"))]   # die Staubwolke gehört zum Gerät: kein Qualm quer durchs Zimmer, keine Feuer-Explosion
    for sc in scenes:
        if not isinstance(sc, dict):
            continue
        low = str(sc.get("text") or "").lower()
        acts = [a for a in (sc.get("actors") or []) if isinstance(a, dict)]
        shot = str(sc.get("shot") or "")
        _pk = [extras.PROP_ALIASES.get(str((p.get("type") if isinstance(p, dict) else p) or "").lower(), str((p.get("type") if isinstance(p, dict) else p) or "").lower())
               for p in (sc.get("props") or [])]
        if fridge_char and shot == "insert" and _pk and all(k_ == "fridge" for k_ in _pk):   # Großaufnahme des Geräts ohne Gesicht: stattdessen die Figur selbst
            sc["shot"] = shot = ""
            if re.search(r"kühlschrank", low) and not any(re.search(FRIDGE_ID_RE, str(a.get("id") or "").lower()) for a in acts):
                sc["actors"] = acts = [a for a in acts if not a.get("kind")][:1] + [{"id": "kuehlschrank", "kind": "fridge", "action": "idle", "emotion": "angry", "pos": "right",
                                                                                 "speaks": False, "emote": "", "say": "", "hold": "", "facing": ""}]
        if fridge_char and shot != "insert" and isinstance(sc.get("props"), list):   # der Kühlschrank ist eine Figur der Geschichte: kein gesichtsloser Kühlschrank als „Ding des Themas“ im Bad oder Flur
            sc["props"] = [p for p in sc["props"] if extras.PROP_ALIASES.get(str((p.get("type") if isinstance(p, dict) else p) or "").lower(),
                                                                             str((p.get("type") if isinstance(p, dict) else p) or "").lower()) != "fridge"]
        fridge = [a for a in acts if re.search(FRIDGE_ID_RE, str(a.get("id") or "").lower()) and str(a.get("kind") or "").lower() in ("", "agent", "robot", "fridge")]
        for a in fridge:
            a["kind"] = "fridge"
            if a.get("hold"):
                a["hold"] = ""
        if fridge:
            sc["props"] = [p for p in (sc.get("props") or []) if extras.PROP_ALIASES.get(str((p.get("type") if isinstance(p, dict) else p) or "").lower(),
                                                                                         str((p.get("type") if isinstance(p, dict) else p) or "").lower()) != "fridge"]
            if shot in ("insert", "close"):
                sc["shot"] = shot = ""
        if fridge_char and (fridge or re.search(r"kühlschrank", low)) and isinstance(sc.get("props"), list):   # „schließt seine Tür“ meint die Kühlschranktür – keine Zimmertür mitten in der Küche
            sc["props"] = [p for p in sc["props"] if extras.PROP_ALIASES.get(str((p.get("type") if isinstance(p, dict) else p) or "").lower(),
                                                                             str((p.get("type") if isinstance(p, dict) else p) or "").lower()) != "door"]
        ov_h = sc.get("overlay")
        if isinstance(ov_h, dict) and str(ov_h.get("type") or "") == "note" and not re.search(r"[#\d]|hack|trick|tipp|nummer|regel|schritt|punkt", str(ov_h.get("title") or "").lower()):
            stems_h = [w_[:5] for w_ in re.findall(r"[a-zäöüß]{5,}", str(ov_h.get("text") or "").lower())]
            if stems_h and not any(st_ in low for st_ in stems_h):
                sc["overlay"] = None                      # Notizzettel mit einer Aussage, die der Satz gar nicht macht („FAZIT: Lieber moderne Seife nutzen!“)
        for a in acts:                                    # Radio in der Hand, obwohl niemand von Funk oder Radio spricht
            if str(a.get("hold") or "").lower() == "radio" and not re.search(RADIO_RE, low):
                a["hold"] = ""
        if re.search(LETTER_RE, low) and shot not in ("graphic", "insert"):
            who = next((a for a in acts if not a.get("kind") and not a.get("hold")), None)
            if who is not None and not any(str(a.get("hold") or "") == "letter" for a in acts):
                who["hold"] = "letter"
                if str(who.get("action") or "").lower() in ("shocked", "scared", "run", "jump", "wave", "dance"):
                    who["action"] = "talk"                # der Umschlag bleibt vor der Brust sichtbar (das Gefühl zeigt das Gesicht)
        m_t = re.search(TEETH_RE, low)
        if m_t and shot not in ("graphic", "insert"):     # „meine Zähne waren komplett grün“: die Figur zeigt die verfärbten Zähne
            who_t = next((a for a in acts if not a.get("kind")), None)
            if who_t is not None:
                who_t["teeth"] = m_t.group(1) or m_t.group(2)
                if len(acts) == 1 and not sc.get("props") and not isinstance(sc.get("overlay"), dict):
                    sc["shot"] = shot = "close"
        if re.search(SCRUB_RE, low) and shot not in ("graphic", "insert", "event"):   # „Zähne schrubben mit Salbeiblättern“: das genannte kleine Ding in der Hand
            thing_s = next((str(x) for x in [k for pat, k in _lib_props() + TEXT_PROPS if re.search(pat, low)] if extras.held_key(x).startswith("prop:")
                            and str(x).lower().replace("lib_", "") not in WORN_THINGS + BODY_PROPS), "")   # „das Reiben deiner Hose“, „ein Muskel zuckt“: Hose und Muskel hat man am Leib – niemand trägt sie in der Hand durchs Bild (Video 209)
            who_s = next((a for a in acts if not a.get("kind") and not a.get("hold")), None)
            if thing_s and who_s is not None:
                who_s["hold"] = thing_s
            for a in acts:                                # schrubben heißt nicht ausschütteln: das Ding bleibt in der Hand, nichts rieselt heraus
                if thing_s and str(a.get("action") or "").lower() in ("shake", "schütteln") and extras.held_key(a.get("hold")).startswith("prop:"):
                    a["action"] = "talk"
                sc["props"] = [p for p in (sc.get("props") or []) if (p.get("type") if isinstance(p, dict) else p) != thing_s]
        pet = next((k for pat, k in PET_RE if re.search(pat, low)), None)
        if pet and shot not in ("graphic", "insert") and len(acts) < 2 and not any(a.get("kind") for a in acts) and "actors" in sc \
                and places.resolve(backdrop(sc)) not in MAPS + ("underwater", "space", "highsky"):
            left = any(_x(a.get("to") or a.get("pos"), 540) > 600 for a in acts)
            flee = bool(re.search(PET_FLEE_RE, low))
            sc["actors"] = acts + [{"id": "_haustier", "kind": pet, "action": "walk" if flee else "idle", "emotion": "scared" if flee else "",
                                    "pos": 300 if left else 780, "to": ("offleft" if left else "offright") if flee else None,
                                    "speaks": False, "emote": "", "say": "", "hold": "", "facing": ""}]
            if shot in ("close", "event"):
                sc["shot"] = ""
            for a in acts:                                # die Hauptfigur macht dem Tier Platz
                if not left and _x(a.get("to") or a.get("pos"), 540) > 450:
                    a["pos"], a["to"] = "left", "left"
    return scenes


# Schatzsuche im See (versenkte Kisten, Taucher, Baumstämme am Grund): Unter Wasser ist der dunkle Seegrund zu sehen – kein Meeresboden
# mit Röhrenwürmern –, es taucht ein Mensch im Neoprenanzug, kein Goldfisch, und am Ufer stehen Holzkisten statt Pappkartons.
LAKE_RE = (r"toplitzsee|bergsee|alpensee|stausee|baggersee|gebirgssee|kratersee|waldsee|\bseegrund|\bseeboden|\bseeufer|loch ness|"
           r"\b(?:im|am|den|der|dem|des|einem|einen|diesem|diesen|tiefen|kalten|dunklen|gesamten|ganzen) see(?:s|n)?\b")
LAKE_DIVE_RE = (r"taucher|tauch(?:t|en|te|ten|gang|gänge|gängen)\b|schatzsucher|froschm[aä]nn|expedition|forscherteam|bergungsteam|suchtrupp|"
                r"\bbarg(?:en)?\b|\bbergen\b|geborgen|\bholt\w*\b.{0,50}(?:oberfläche|herauf|nach oben|aus dem (?:see|wasser))|ertrank|ertrink|ertrunken")
LAKE_UNDER_RE = (r"versenk|versank|versunken|\bsinken|\bsank|auf (?:dem|den) (?:\w+ )?grund|am (?:\w+ )?(?:grund|seegrund|seeboden)\b|in der tiefe|in die tiefe|unter wasser|"
                 r"metern? tief|tiefen wasser|sauerstoff|dort unten|da unten|in (?:\w+ )?metern? tiefe|taucher|\btauch|schlick|schlamm")
LAKE_SINK_RE = r"versenk|versank|\bsinken\b|\bsank(?:en)?\b|ins wasser (?:geworfen|gekippt)|warfen .{0,30}(?:in den see|ins wasser)|kippten"
LAKE_CRATE_RE = r"kiste|truhe|behälter|\bschatz\b|\bfracht|ladung"
LAKE_LOG_RE = r"baumst[aä]mm|\bbäume[n]?\b|\bstämme[n]?\b|holzverhau|treibholz|holzschicht|\bstamm\b|schicht aus (?:\w+ )?holz"
LAKE_CASH_RE = r"banknote|geldschein|\bscheine[n]?\b|falschgeld|\bblüten\b|gefälschte[sn]? (?:geld|pfund)|pfundnote|pfund-|falsche[sn]? (?:geld|pfund)|geldfälsch"
LAKE_GOLD_RE = r"\bgold|goldbarren|goldschatz"
LAKE_NOGOLD_RE = r"kein(?:e|en)? (?:\w+ )?gold|gold (?:\w+ ){0,7}(?:nie|niemals|nicht)\b|(?:nie|niemals) (?:\w+ ){0,3}gold|nie (?:\w+ )?gold|statt gold|kein einziger barren|gold fehlt|vom gold fehlt"
LAKE_ROCKET_RE = r"rakete|torpedo|sprengk|versuchsstation|prüfst[aä]nd|unterwasserwaffe|marine\w* test"
LAKE_SOLDIER_RE = r"soldaten|truppen|offizier|wehrmacht|\bss-|lastwagen|\blkws?\b"
LAKE_SHORE_RE = r"\bufer\b|an den see|an land|verboten|\bverbot\b|tauchverbot|gesperrt|aus dem wasser (?:gezogen|geholt)|an die oberfläche|ans licht"
LAKE_SCARE_RE = r"ertrank|ertrink|ertrunken|starb|stirbt|\btod\b|\btot\b|tödlich|gefahr|gefährlich|riskier|verunglück|lebensgefahr|verfangen|kein sauerstoff"
LAKE_INDOOR_OK_RE = r"büro|labor|museum|archiv|\bbank\b|keller|zimmer|werkstatt|druckerei|baracke|fabrik|\blager\b|zeitung|redaktion|gericht"
LAKE_PLAIN = ("office", "livingroom", "bedroom", "kitchen", "lab", "plain", "basement", "classroom", "mathroom", "serverroom", "street", "park", "headquarters", "hospital",
              "supermarket", "cinema", "restaurant", "beach", "desert", "space", "hallway", "attic", "station")
LAKE_SHORE = {"sky": "", "ground": "grass", "elements": ["mountains", "lake"]}
SOLDIER_LOOKS = ({"shirt": "grau", "hat": "army", "hair": "kurz", "hair_color": "braun"}, {"shirt": "grau", "hat": "army", "hair": "kurz", "hair_color": "blond", "size": 0.95})
DIVER_ID_RE = r"tauch|diver|schatzsuch|froschmann"
DIVER_TEXT_RE = r"\btaucher|tauchgang|tauchgänge|schatzsucher|froschm[aä]nn|taucht (?:\w+ )?(?:hinab|ab|hinunter)"


def _diver(a=None, pos="center", facing="right", scared=False):
    d_ = {"id": str((a or {}).get("id") or "_taucher"), "kind": "diver", "action": "idle", "speaks": False, "emote": "", "say": "", "hold": "",
          "facing": facing, "emotion": "scared" if scared else "", "hero": True, "pos": pos}
    return d_


def _divers(scenes):
    """Unter Wasser taucht ein Mensch im Neoprenanzug: Heißt die Figur „taucher“ oder spricht der Satz von Tauchern, wird aus dem Ersatz-Fisch
    (oder der Figur im Pulli) ein Taucher – in jedem Video, nicht nur am See."""
    import re as _re
    for sc in scenes:
        if not isinstance(sc, dict) or places.resolve(backdrop(sc)) != "underwater" or sc.get("shot") in ("graphic", "insert"):
            continue
        acts = [a for a in (sc.get("actors") or []) if isinstance(a, dict)]
        low = str(sc.get("text") or "").lower()
        hit = [a for a in acts if _re.search(DIVER_ID_RE, str(a.get("id") or "").lower()) and str(a.get("kind") or "fish").lower() in ("fish", "monster", "diver", "")]
        if not hit and _re.search(DIVER_TEXT_RE, low) and not _re.search(r"\bfisch|\bhai", low):
            hit = [a for a in acts if str(a.get("kind") or "fish").lower() in ("fish", "")][:1]
            if not hit and not acts and not any(extras.PROP_ALIASES.get(str(q.get("type")).lower(), str(q.get("type")).lower()) == "submersible" for q in (sc.get("props") or []) if isinstance(q, dict)):
                hit = [{}]
        if not hit:
            continue
        has_thing = bool(sc.get("props"))
        sc["actors"] = [_diver(hit[0], 400 if has_thing else "center", "right", bool(_re.search(LAKE_SCARE_RE, low)))]
        if sc.get("shot") in ("close", "event"):
            sc["shot"] = ""                               # der Taucher ist breit: keine Vergrößerung über den Bildrand


def lake_story(scenes, topic=""):
    import re as _re
    texts = [str(sc.get("text") or "").lower() for sc in scenes if isinstance(sc, dict)]
    n_lake = sum(1 for t_ in texts if _re.search(LAKE_RE, t_))
    if not (_re.search(LAKE_RE, topic_head(topic).lower()) or n_lake >= 2):
        return False
    return any(_re.search(LAKE_UNDER_RE, t_) for t_ in texts) or bool(_re.search(LAKE_UNDER_RE + "|schatz", str(topic or "").lower()))


# ------------------------------------------------------------------ Videospiel-Themen: Blick in die Spielwelt statt Straße, Höhle und Goldfisch
# Prüfung 18.11.2026 (Video 140, „geheime Orte in Videospielen“): Die Engine kannte keine Spielwelt – zu sehen waren eine Straße voller Passanten,
# ein rotes Auto in der Höhle, ein Goldfisch und ein leerer Tisch im Gebirge. Jetzt zeigt die Grafik „game“ (graphics._g_game) die Spielwelt als
# eigenes Pixel-Bild; Sätze über Menschen (Programmierer, Firma, der Junge, der es fand) spielen am Rechner bzw. vor dem Fernseher.
GAME_TOPIC_RE = r"videospiel|computerspiel|konsolenspiel|\bgames?\b|gaming|spielwelt|easter ?eggs?"
GAME_WORLD_RE = r"\borte?\b|\borten\b|\bwelt|level|\bräume|\braum\b|geheim|versteck|easter ?egg|rand der|spielwelt|\bkarte"
GAME_ROOM_RE = r"\b1980\b|geheim\w* (?:raum|zimmer|kammer)|versteckt\w* (?:raum|zimmer|kammer)|grau\w* punkt|abenteuerspiel"
GAME_MINUS_RE = r"\b1985\b|\bminus|hüpfspiel|unterwasser|wasser-?level|unter wasser"
GAME_FAR_RE = r"blockspiel|klötzchen|blöcke\b|blöcken\b|rand der welt|ende der welt|bauspiel|riesenwand|riesige\w* w[aä]nd"
GAME_IN_RE = (r"\braum\b|zimmer|kammer|\bwand\b|wände|mauer|level|\bwelt\b|spielwelt|wasser|schwimm|landschaft|blöcke|blöcken|spielfigur|\bfigur\b|\bpunkt\b|pixel|"
              r"löcher|zerreißt|zerbricht|zerfällt|endlos|schleife|läufst|schwimmst|trägst|\brand\b|labyrinth|\bkarte\b|\bort\w*\b|bereich|\btür")
GAME_REAL_RE = (r"programmierer|entwickler|\bfirma|hersteller|erfinder|schöpfer|\bchefs?\b|jährig|\bjunge\b|schüler|\bbrief|streamer|\bfans?\b|absicht|geplant|gewollt|"
                r"\bcode\b|rechenfehler|ostereier|osterei\b|kommentar|gelöscht|entfernt|update|jahrelang|jahre lang")
GAME_DEV_RE = r"programmierer|entwickler|\bfirma|hersteller|erfinder|schöpfer|\bchefs?\b|\bcode\b|rechenfehler|update|gelöscht|entfernt"


def _game_step(sub, low, seen):
    """Welches Bild der Spielwelt zum Satz gehört (graphics._g_game, label): Der Satz bestimmt es, nicht die Reihenfolge – in Video 142 lief zum Satz
    über den grauen Punkt schon der Raum mit dem Namen, und der Satz über die Mauer spielte bereits unter Wasser."""
    import re as _re
    if sub == "room":
        st = "1" if _re.search(r"\bpunkt|durch (?:die|eine) (?:wand|mauer)|\btr[aä]g", low) else "2" if _re.search(r"\bname|blinkt|farben|leuchtet|schriftzug", low) else "0"
    elif sub == "minus":
        st = "0" if _re.search(r"mauer|\bwand\b|rutsch|gleite", low) else "2" if _re.search(r"wasser|endlos|wiederhol|schwimm|zeit (?:abl|aus)|schaffen|ausweg", low) else "3"
    elif sub == "far":
        st = "2" if _re.search(r"zerbricht|zerreißt|zerfällt|w[aä]nde?n?\b|löcher|himmel", low) else "1" if _re.search(r"millionen|verrechnet|rand der welt|ende der welt", low) else "0"
        if st == "2" and seen.get("far") == "2":
            st = "3"                                      # zweiter Satz über die Riesenwand: ganz nah, nur noch Wand und Löcher
    else:
        st = "0"
    seen[sub] = st
    return st


def game_story(scenes, topic=""):
    import re as _re
    head = topic_head(topic).lower()                      # nur Videos über Orte und Welten IN Spielen – nicht „Videospiel-Regeln im Alltag“ oder die Firmengeschichte einer „Gaming-Bude“
    return bool(_re.search(GAME_TOPIC_RE, head) and _re.search(GAME_WORLD_RE, head) and not _re.search(r"im alltag|in echt|im echten|wirklichkeit|\bbude|firma|konzern", head))


def _game_story(scenes, topic="", main_id="du"):
    """Regie für Videos über Videospiele (siehe oben). Läuft am Schluss von direct."""
    import re as _re
    if not game_story(scenes, topic):
        return
    seg, run, n, seen = "", 0, len([x for x in scenes if isinstance(x, dict)]), {}
    for i, sc in enumerate(scenes):
        if not isinstance(sc, dict):
            continue
        low = str(sc.get("text") or "").lower()
        g_old = graphics.clean(sc.get("graphic")) if sc.get("shot") == "graphic" else None
        if g_old and g_old.get("type") in FIGURE_GFX + ("question", "round", "versus", "score", "podium", "chart") and g_old.get("type") != "badge":
            if g_old.get("type") == "number" and _re.search(GAME_FAR_RE, low) and _re.search(r"blöcke", low):
                sc.update(graphic={"type": "game", "sub": "far", "label": _game_step("far", low, seen), "value": (str(g_old.get("value") or "") + " BLÖCKE").strip()}, overlay=None)
                seg, run = "far", run + 1                 # „nach zwölf Millionen Blöcken zerbricht die Landschaft“: die Zahl steht über der zerbrechenden Welt
                continue
            run = 0
            continue                                      # Zahl, Frage, Duell aus dem Drehbuch bleiben
        new = "room" if _re.search(GAME_ROOM_RE, low) else "minus" if _re.search(GAME_MINUS_RE, low) else "far" if _re.search(GAME_FAR_RE, low) else ""
        seg = new or seg
        real = bool(_re.search(GAME_REAL_RE, low)) and not new
        last = i == len(scenes) - 1 and n > 4
        ingame = bool(new) or (not real and not last and bool(seg or i == 0 or _re.search(GAME_IN_RE + "|" + GAME_TOPIC_RE, low)))
        if ingame and run >= 2 and not new:
            ingame = False                                # höchstens zwei Spielbilder hintereinander, dann schaut man der Spielerin zu
        ov = sc.get("overlay") if isinstance(sc.get("overlay"), dict) else {}
        if ingame:
            kick = str(ov.get("text") or "").strip() if str(ov.get("type") or "") in ("card", "tag") and not numbered_label_wrong(ov, sc.get("text")) else ""
            g = {"type": "game", "sub": seg or "world", "label": _game_step(seg or "world", low, seen)}
            if kick and len(kick) <= 22:
                g["kicker"] = kick
            sc.update(shot="graphic", graphic=g, overlay=None, crowd="", float="")
            run += 1
            continue
        run = 0
        dev = bool(_re.search(GAME_DEV_RE, low))
        acts = [a for a in (sc.get("actors") or []) if isinstance(a, dict) and not a.get("kind")][:1]
        if not acts:
            acts = [{"id": main_id, "action": "think" if dev else "shocked", "emotion": "calm" if dev else "surprised", "emote": "", "pos": "left", "speaks": False}]
        acts[0] = dict(acts[0], pos="left" if dev else "right")
        if acts[0].get("action") in ("fall", "float", "walk", "run", "swim", "sit", "lie"):
            acts[0]["action"] = "think" if dev else "point"
        if ov and str(ov.get("type") or "") in ("card", "tag") and numbered_label_wrong(ov, sc.get("text")):
            sc["overlay"] = None
        sc.update(place="office" if dev else "livingroom", time="day", mood="calm", backdrop=None, weather="", crowd="", float="", graphic=None, actors=acts,
                  props=[] if dev else [{"type": "computer", "pos": 300}])   # Büro: Rechner steht schon da; im Wohnzimmer-Bild steht kein Fernseher (PLACE_HAS behauptet es nur) – der Bildschirm kommt als Requisite
        if sc.get("shot") in ("graphic", "insert", "event"):
            sc["shot"] = ""


def _lake_story(scenes, topic="", main_id="du"):
    """Regie für Geschichten vom Seegrund (siehe oben). Läuft ganz am Schluss, damit keine spätere Regel wieder einen Fisch, einen Karton
    oder Passanten ins Bild stellt."""
    import re as _re
    if not lake_story(scenes, topic):
        return
    _key = lambda q: extras.PROP_ALIASES.get(str(q.get("type")).lower(), str(q.get("type")).lower())      # noqa: E731
    n_under = 0
    last_shore = last_under = prev_thing = None
    prev_under = False
    for i, sc in enumerate(scenes):
        if not isinstance(sc, dict):
            continue
        low = str(sc.get("text") or "").lower()
        shot = str(sc.get("shot") or "")
        sc["crowd"] = ""                                  # an einem einsamen Bergsee laufen keine Passanten
        props = []
        for q in (sc.get("props") or []):                 # Holzkiste statt Pappkarton, Versuchsteil am Grund statt startender Rakete, Scheine in der Kiste
            if not isinstance(q, dict):
                continue
            k = _key(q)
            if k == "box":
                q = dict(q, type="crates" if _re.search(r"kisten", low) else "crate")
            elif k == "rocket":
                q = dict(q, type="rocketpart")
            elif k == "money":
                q = dict(q, type="cashcrate")
            props.append(q)
        sc["props"] = props
        if shot == "graphic" and sc.get("graphic"):
            continue
        acts = [a for a in (sc.get("actors") or []) if isinstance(a, dict)]
        under = places.resolve(backdrop(sc)) == "underwater"
        shore_said = bool(_re.search(LAKE_SHORE_RE, low))
        soldiers = bool(_re.search(LAKE_SOLDIER_RE, low)) and not _re.search(LAKE_SINK_RE, low)
        if soldiers or (shore_said and not _re.search(LAKE_SINK_RE, low)):
            under = False
        elif _re.search(LAKE_UNDER_RE + "|" + LAKE_LOG_RE + "|" + LAKE_DIVE_RE, low) and shot != "insert":
            under = True
        elif prev_under and shot != "insert" and _re.search(r"\bdarin\b|\bdort\b|\bdarunter\b|\bdaraus\b|\bhinab\b|verf[aä]ng|\bunten\b", low) and not _re.search(LAKE_CASH_RE, low):
            under = True                                  # Folgesatz über die Tiefe („Wer sich darin verfängt …“): bleibt unter Wasser beim Ding von eben
        scared = bool(_re.search(LAKE_SCARE_RE, low))
        cash = bool(_re.search(LAKE_CASH_RE, low))
        gold = bool(_re.search(LAKE_GOLD_RE, low)) and not _re.search(LAKE_NOGOLD_RE, low)
        if under:
            sc.update(place="underwater", backdrop=None, time="night", weather="", float="", _lake=True, _no_cut=True)
            if shot in ("event", "close", "insert"):
                sc["shot"] = ""
            keys = [_key(q) for q in props]
            dive_txt = bool(_re.search(LAKE_DIVE_RE, low))
            sub = bool(_re.search(SUB_RE, low)) or ("submersible" in keys and not dive_txt)   # „Schatzsucher riskierten ihr Leben“: Menschen tauchen, kein Tauchboot
            if _re.search(LAKE_SINK_RE, low) and not sub:
                sc["props"], sc["actors"] = [{"type": "crates_sink", "pos": 540}], []      # die Kisten sinken trudelnd in die Tiefe
                prev_under, prev_thing, last_under, last_shore = True, "crates", None, None
                n_under += 1
                continue
            follow = prev_under and not _re.search(LAKE_UNDER_RE + "|" + LAKE_LOG_RE + "|" + LAKE_DIVE_RE + "|" + LAKE_CRATE_RE, low)
            thing = "cashcrate" if cash else (prev_thing or "") if follow else "logs" if _re.search(LAKE_LOG_RE, low) else "rocketpart" if (_re.search(LAKE_ROCKET_RE, low) or "rocketpart" in keys) else \
                "crates" if (_re.search(LAKE_CRATE_RE, low) or gold or "crates" in keys or "crate" in keys) else ""
            dive = bool(_re.search(LAKE_DIVE_RE, low)) or any(_re.search(DIVER_ID_RE, str(a.get("id") or "").lower()) or str(a.get("kind") or "") == "diver" for a in acts)
            if follow and _re.search(r"\bwer\b|verf[aä]ng|niemand|\bman\b", low):
                dive = True
            if not thing and not dive and not sub:
                dive, thing = (n_under % 2 == 0), ("" if n_under % 2 == 0 else "crates")   # nie ein leerer Grund: abwechselnd Taucher und Kisten
            if sub:
                sc["props"] = [{"type": "submersible", "pos": 270}] + ([{"type": thing, "pos": 540 if thing == "logs" else 640 if thing == "rocketpart" else 720}] if thing else [])
                sc["actors"] = []
                sc["_ov_low"] = 3
            elif thing == "logs":
                sc["props"] = [{"type": "logs", "pos": 540}]
                sc["actors"] = [_diver(acts[0] if acts else None, "center", "left" if n_under % 2 else "right", True)] if dive else []
            elif thing:
                sc["props"] = [{"type": thing, "pos": 640 if thing == "rocketpart" else 800 if dive else 540}]
                sc["actors"] = [_diver(acts[0] if acts else None, 410, "right", scared)] if dive else []
            else:
                sc["props"] = []
                sc["actors"] = [_diver(acts[0] if acts else None, "center", "left" if n_under % 2 else "right", scared)]
            sig = (tuple((q.get("type"), q.get("pos")) for q in sc["props"]), tuple((a.get("kind"), a.get("pos"), a.get("facing")) for a in sc["actors"]))
            if sig == last_under and not sub:             # zweimal hintereinander genau dasselbe Bild: Taucher kommt dazu bzw. wechselt die Seite
                if sc["actors"]:
                    sc["actors"][0].update(facing="left" if sc["actors"][0].get("facing") == "right" else "right", pos=650 if not sc["props"] else sc["actors"][0].get("pos"))
                else:
                    sc["actors"] = [_diver(None, 400, "right", scared)]
                    sc["props"] = [dict(q, pos=800) if q.get("type") != "logs" else q for q in sc["props"]]
                sig = (tuple((q.get("type"), q.get("pos")) for q in sc["props"]), tuple((a.get("kind"), a.get("pos"), a.get("facing")) for a in sc["actors"]))
            if sc["actors"] and isinstance(sc.get("overlay"), dict) and not sub:
                sc["_ov_low"] = 3                         # Karte/Schild ganz nach oben: der Taucher schwimmt sonst dahinter
            last_under = sig
            prev_under, prev_thing = True, thing
            last_shore = None
            n_under += 1
            continue
        # ---- am Ufer / an Land
        last_under, prev_under = None, False
        sc["_lake"] = False
        rp = places.resolve(backdrop(sc))
        bd_l = backdrop(sc)
        at_lake = isinstance(bd_l, dict) and any("lake" in str(e).lower() or "see" == str(e).lower() for e in (bd_l.get("elements") or []))
        if isinstance(bd_l, dict) and str(bd_l.get("ground") or "").lower() in ("water", "wasser"):
            at_lake = False                               # offene Wasserfläche mit Dampfer: am Bergsee steht man am Ufer
            if not _re.search(r"\bboot|schiff|\bfloß|\bkahn|ruder", low):
                sc["props"] = [q for q in sc["props"] if _key(q) not in ("ship", "wave", "debris")]
        if rp == "underwater" or rp in MAPS or (not at_lake and not _re.search(LAKE_INDOOR_OK_RE, low)):      # auch keine Deutschlandkarte für „die Wirtschaft Großbritanniens“
            sc["place"], sc["backdrop"] = "lake", dict(LAKE_SHORE)      # die Geschichte spielt am See – nicht im Büro mit Bildschirmen
            rp = "custom"
            sc["props"] = [q for q in sc["props"] if _key(q) not in INDOOR_THINGS and _key(q) not in ("table", "shelf", "tv", "computer", "fridge", "door", "clock")]
        people = [a for a in acts if not a.get("kind")]
        if shot == "insert":
            continue
        thing = "cashcrate" if cash else "goldbars" if gold else "crates" if _re.search(LAKE_CRATE_RE, low) else ""
        if soldiers:
            sc["actors"] = [{"id": "_soldat1", "action": "idle", "emotion": "worried", "pos": 190, "facing": "right", "speaks": False, "hold": "prop:crate", "look": dict(SOLDIER_LOOKS[0])},
                            {"id": "_soldat2", "action": "point", "emotion": "worried", "pos": 430, "facing": "right", "speaks": False, "hold": "", "look": dict(SOLDIER_LOOKS[1])}]
            sc["props"] = [{"type": "crates", "pos": 800}]
            sc["shot"] = ""
            last_shore = "crates"
            continue
        if not thing and not sc["props"] and last_shore and _re.search(r"\bdamit\b|\bdarin\b|\bdavon\b|\bdiese[nr]? (?:scheine|kisten|fund)|\bsie\b", low):
            thing = last_shore                            # Folgesatz über den Fund von eben: er bleibt im Bild
        if thing:
            lead = dict(people[0]) if people else {"id": main_id, "action": "shocked", "emotion": "shocked", "speaks": False}
            lead.update(pos=290, facing="right", hold="")
            lead.pop("to", None)
            if str(lead.get("action") or "") in ("sit", "sleep", "fall", "float", "run", "walk", ""):
                lead["action"] = "point"
            sc["actors"] = [lead]
            sc["props"] = [{"type": thing, "pos": 760}] + ([{"type": "crate", "pos": 930}] if thing == "goldbars" else [])
            if sc.get("shot") in ("close", "event"):
                sc["shot"] = ""
            last_shore = thing
        else:
            sc["actors"] = people[:2]                     # kein Fisch an Land
            if not sc["actors"] and not sc["props"]:      # leeres Ufer: die Hauptfigur blickt auf den See
                sc["actors"] = [{"id": main_id, "action": "look_around", "emotion": "worried", "pos": "center", "speaks": False, "emote": "?", "hold": "", "say": "", "facing": ""}]


# Tier/Wesen im Titel → es wird die Hauptfigur des Videos (wie in den Vorbild-Shorts: die Spinne ist fast in jeder Szene, mit Gefühl)
TOPIC_CREATURES = [(r"ki-agent|\bagent|\bbots?\b|chatbot|\bassistent|\bki\b|künstliche intelligenz|\bclaude\b|chatgpt|sprachmodell", "agent"),
                   (r"\bvirus|\bviren|bakterie|\bkeim|erreger|grippe|infektion", "virus"), (r"\bzelle|zellen|blutkörperchen|immunsystem", "cell"),
                   (r"spinne|tarantel|vogelspinne|weberknecht|kreuzspinne", "spider"), (r"katze|kater|kätzchen", "cat"), (r"\bhund(e|es|en|chen)?\b|\bhunde(?!rt)\w|welpe", "dog"),
                   (r"biene", "bee"), (r"wespe|hornisse", "wasp"), (r"\bhai\b|haie|weißer hai", "shark"), (r"\bfisch|goldfisch", "fish"),
                   (r"\bvogel|vögel|spatz|taube|amsel", "bird"), (r"\bgeist|gespenst", "ghost"), (r"roboter", "robot"),
                   (r"außerirdisch|(?<![a-zäöüß])aliens?\b|\bufo", "alien"), (r"dinosaurier|\bdino|t-rex", "dino"), (r"monster|ungeheuer", "monster")]
PLURAL = {"agent": r"agenten|\bbots\b|assistenten", "virus": r"\bviren|bakterien|keime|erreger", "cell": r"zellen|blutkörperchen",
          "spider": r"spinnen|taranteln", "bee": r"bienen", "wasp": r"wespen", "cat": r"katzen", "dog": r"\bhunde\b", "bird": r"vögel",
          "fish": r"fische", "shark": r"\bhaie", "ghost": r"geister|gespenster", "robot": r"roboter\b", "alien": r"außerirdische|aliens",
          "dino": r"dinosaurier", "monster": r"monster"}
# Meerestiere als Figur der Szene (Reihenfolge zählt: „Fangschreckenkrebs“ enthält „krebs“)
SEA_CREATURES = [(r"fangschreckenkreb|heuschreckenkreb|mantis-?shrimp", "mantis"), (r"pistolenkreb|knallkreb|knallgarnele|\bgarnele|krabben?\b|\bhummer|flusskreb|krebstier|\bshrimp", "shrimp"),
                 (r"qualle", "jelly"), (r"axolotl", "axolotl"),
                 # Blauwal und andere Großwale (Ausbau 19.11.2026) – nicht der Schweinswal/Delfin (eigenes Wesen `dolphin`), nicht „Wahl“, nicht „Walnuss“
                 (r"^(?!.*(?:schweinswal|delfin|delphin|tümmler)).*(?:blauwal|buckelwal|pottwal|finnwal|grauwal|bartenwal|\bwal(?:e|es|en|s)?\b)", "whale")]
SEA_KINDS = ("shrimp", "mantis", "jelly", "axolotl", "whale")
# Tiefsee-Technik (Flugzeug-Suche, Wracks): Der Satz spielt unter Wasser; nennt er Blackbox, Wrack oder Tauchboot/Sonar, wird es die dunkle Tiefsee
SURFACE_RE = (r"\b(?:auf|über) (?:dem|den|der|hoher|offener|offenem) (?:\w+ )?(?:ozean|meer|atlantik|pazifik|wasseroberfläche|meeresoberfläche|see\b)|übers (?:offene )?meer|"
              r"auf hoher see|meeresoberfläche|wasseroberfläche")
DEBRIS_RE = r"trümmerteil|treibgut|wrackteile? (?:treib|schwimm)|trümmer (?:treib|schwimm)"
SEA_TOP = ("ship", "debris", "wave", "ice", "lightning")       # was auf der Meeresoberfläche zu sehen sein darf (dazu alles am Himmel)
GEO_RE = (r"europ|deutsch|länder|\bland\b|\blandes\b|staat|kontinent|\bkarte|grenz|weltweit|\bwelt\b|international|global|ausland|nachbar|region|england|britann|"
          r"frankreich|spanien|italien|polen|österreich|schweiz|skandinav|schweden|norwegen|finnland|dänemark|russland|ukraine|türkei|niederlande|holland|belgien|"
          r"griechenland|portugal|irland|\beu\b|bundesl")
RADAR_RE = r"\bradar(?!falle|kontroll)|radarschirm|funkkontakt|transponder"
ZEROS_RE = r"nullstelle"                                 # Mathe: Nullstellen einer Funktion → Schaubild „zeros“
ZLINE_RE = r"auf (?:einer|derselben|der gleichen|dieser|genau einer|exakt einer|ein und derselben) (?:\w+ )?(?:linie|geraden)\b"
PRIMES_RE = r"primzahl"
PERSON_JOB_RE = r"\b(?:[Mm]athematiker|[Pp]hysiker|[Cc]hemiker|[Ff]orscher|[Ww]issenschaftler|[Ee]rfinder|[Ii]ngenieur|[Aa]stronom|[Pp]hilosoph|[Gg]ründer|[Pp]rofessor|[Aa]rzt|[Bb]iologe)"
RADAR_LOST_RE = r"verschwind|verschwund|verlier|verlor|bricht ab|abbrich|abgebrochen|reißt ab|abreiß|erlisch|erlosch|kein signal|spurlos|\bweg\b"
DEEP_RE = r"meeresboden|meeresgrund|\btiefsee|\b(?:meter|metern|kilometer|kilometern) tiefe\b|am grund des (?:meeres|ozeans)|auf dem grund des (?:meeres|ozeans)"
DEEP_DARK_RE = r"\btiefsee|\b(?:meter|metern|kilometer|kilometern) tiefe\b|tiefseegraben|abgrund"
SUB_RE = r"\bsonar|tauchboot|tauchroboter|tiefseeroboter|tauchdrohne|\bu-boot|unterseeboot"
DEEP_WRECK_RE = r"\bwracks?\b|flugzeugwrack|schiffswrack|wrackteil"
DEEP_BOX_RE = r"blackbox|black box|flugschreiber|flugdatenschreiber|flugrekorder"
DEEP_PING_RE = r"send|signal|\bping|ortung|ultraschall|funk|piep|batterie"
DEEP_THING_RE = SUB_RE + "|" + DEEP_WRECK_RE + "|" + DEEP_BOX_RE
SEA_TARGETS = ("rock", "lib_glasscheibe", "lib_tresor", "ship", "box", "barrel", "ice", "lib_sprungfeder", "cavitation")
SEA_ID_RE = r"krebs|garnele|qualle|shrimp|jelly|axolotl|lurch|fisch|tier|meer|tauch|diver|mantis|fangschreck"
SEA_HUMAN_RE = r"\bmensch\w*|\bforscher\w*|wissenschaftler\w*|\bdein\w*|\bdu\b|\bdir\b|\bdich\b|wimpernschlag|blinzel|augenzwinkern"
SEA_PEOPLE_RE = r"^(?:wir )?menschen (?:haben|besitzen|sehen|können|brauchen|schaffen)\b|ein(?:es)? menschliche[rsn]? (?:wimpernschlag|auge|hand)|\bals ein wimpernschlag"   # der Satz handelt von Menschen – auch wenn das Drehbuch dort das Tier hinstellt
TANK_RE = r"\bbecken\b|plastikbecken|kunststoffbecken|acrylbecken|acrylglas|aquarium\b|aquarien\b"
CAVI_RE = r"dampfblase|gasblase|kavitation|blasen? (?:kollabier|implodier|platz|fall\w* zusammen)|(?:kollabier|implodier|platz)\w* (?:die|diese) blase|druckwelle"
LONG_KINDS = ("shrimp", "mantis", "axolotl", "tardigrade", "jelly", "cheetah", "eagle", "flea", "dolphin", "cow", "pig", "lion", "whale", "chimera", "frog", "woodfrog", "platypus", "puffer", "angler")          # breiter als hoch: keine Großaufnahme, Kamera lässt sie ganz im Bild
# Winzlinge, die überall vorkommen (Moos, Eis, Weltall): als Figur an dem Ort, von dem der Satz spricht
ANY_CREATURES = [(r"bärtierchen|wasserbär|tardigrad", "tardigrade"), (r"\bgepard", "cheetah"), (r"\badler|greifvogel|greifvögel", "eagle"), (r"\bfloh|\bflöhe", "flea")]
# Landtiere und Vögel als Figur der Szene: bleiben nur einen Folgesatz, und nur, wenn er sichtbar weiter vom Tier handelt
LAND_KINDS = ("cheetah", "eagle", "flea")
LAND_NEXT_RE = r"^(er|sie|es|sein\w*|ihr\w*|damit|dabei)\b|\b(dieses|das) tier\b|\bdie raubkatze|\bder (vogel|springer)\b"
HUMAN_RE = (r"\b(du|dein\w*|dir|dich|ich|mein\w*|mir|mich|wir|unser\w*|uns|euch|mensch\w*|forscher\w*|wissenschaftler\w*|mediziner\w*|ärzt\w*|arzt|"
            r"schreib\w*|folg\w*|kommentar\w*|abonnier\w*|stell dir|zuschauer)\b")
SEA_TOPIC_RE = r"axolotl|pistolenkreb|knallkreb|fangschreckenkreb|\bgarnele|krebstier|qualle|unter wasser|meerest|tiefsee|\bozean|\bmeer\b|\briff"
SEA_NEXT_RE = r"nummer (zwei|drei|vier|fünf|\d)|(zweite|dritte|vierte|nächste|letzte)[nrs]? (fähigkeit|kraft|superkraft|tier|platz|kandidat)|platz (eins|zwei|drei|\d)"
SEA_HIT_RE = r"schlag|schläg|boxt|zertrümmer|knall|zuschnapp|zerstör|\bangriff|greift an|tötet|betäub"


def _sea_kind(low, sea):
    """Welches Meerestier nennt der Satz? Ein bloßes „Krebs“ zählt nur, wenn es ums Meer geht (sonst ist die Krankheit gemeint)."""
    import re as _re
    for pat, k in SEA_CREATURES:
        if _re.search(pat, low):
            return k
    if sea and _re.search(r"\bkrebs(e|es|en)?\b", low) and not _re.search(r"krank|tumor|diagnos|chemo|besieg|geheilt|heilung|\barzt|ärzt|patient|vorsorge|krebs (bekomm|hab|hat|hatte)", low):
        return _SEA_DEF[0] or "shrimp"
    return None


_SEA_DEF = [None]                                         # das Meerestier des Videos: ein bloßes „Krebs“ meint im Fangschreckenkrebs-Video den Fangschreckenkrebs


def _sea_named(low):
    """Nur ausdrücklich genannte Meerestiere (ohne das bloße „Krebs“)."""
    import re as _re
    return next((k for pat, k in SEA_CREATURES if _re.search(pat, low)), None)


def _sea_default(scenes, topic):
    """Nennt das Thema genau ein Meerestier – oder nennen alle Sätze zusammen nur eines –, ist es das Tier des ganzen Videos."""
    import re as _re
    head = _sea_named(topic_head(topic).lower())
    if head:
        return head
    kinds = {k for sc in scenes if isinstance(sc, dict) for pat, k in SEA_CREATURES if _re.search(pat, str(sc.get("text") or "").lower())}
    return next(iter(kinds)) if len(kinds) == 1 else None


HERO_SIZE = {"cheetah": 1.45, "eagle": 1.5, "flea": 1.35, "shrimp": 1.6, "mantis": 1.6, "jelly": 1.4, "axolotl": 1.6, "tardigrade": 1.5, "agent": 0.8, "brain": 1.6, "virus": 0.75, "cell": 0.75, "spider": 1.15, "cat": 0.95, "dog": 1.0, "bee": 1.0, "wasp": 1.0, "bird": 1.0, "fish": 0.8, "shark": 0.9, "diver": 1.3, "dolphin": 1.5, "cow": 1.25, "pig": 1.1, "chimp": 1.2, "mosquito": 1.0, "fly": 1.0, "lion": 1.3, "whale": 1.75, "chimera": 1.35, "frog": 1.25, "woodfrog": 1.25, "platypus": 1.45, "puffer": 1.35, "angler": 1.5}   # Hauptfigur: etwa halb so hoch wie ein Mensch


def _topic_creature(scenes, topic):
    """Handelt das Video von einem Tier oder Wesen, das die Engine als Figur kennt, ist es die Hauptfigur: groß, mit Gefühl passend zur
    Stimmung, neben dem Menschen – statt als kleiner Gegenstand am Boden. Nicht in Grafiken, Einschüben, Karten und Großaufnahmen."""
    import re as _re
    low = str(topic or "").lower()
    hit = next(((pat, k) for pat, k in TOPIC_CREATURES if _re.search(pat, low)), None)
    if not hit:
        return
    pat, kind = hit
    for sc in scenes:
        if not isinstance(sc, dict) or sc.get("shot") in ("graphic", "insert", "close") or places.resolve(backdrop(sc)) in MAPS:
            continue
        acts = [a for a in (sc.get("actors") or []) if isinstance(a, dict)]
        mine = [a for a in acts if str(a.get("kind") or "").lower() == kind]
        for a in mine:
            a["hero"] = True
        humans = [a for a in acts if not a.get("kind")]
        drop = [q for q in (sc.get("props") or []) if not (isinstance(q, dict) and _re.search(pat, str(q.get("type") or "").lower()))]
        if mine:
            sc["props"] = drop                            # das Tier steht als Figur im Bild – nicht zusätzlich als Gegenstand
            continue
        if len(humans) >= 2 or len(acts) >= 2 or (acts and not humans):   # kein Gedränge: neben höchstens einem Menschen, nie neben einem anderen Tier
            continue
        sc["props"] = drop
        mood0 = str(sc.get("mood") or "")
        if not humans and _re.search(PLURAL.get(kind, r"$^"), str(sc.get("text") or "").lower()):     # Mehrzahl ohne Menschen: eine Gruppe
            emo = MOOD_EMOTION.get(mood0, "happy" if mood0 == "happy" else "")
            sc["actors"] = [{"id": f"_thema{j}", "kind": kind, "hero": True, "speaks": False, "action": "idle", "emotion": emo,
                             "pos": x, "emote": "", "say": "", "hold": "", "facing": ""} for j, x in enumerate((230, 540, 850))]
            sc["crowd"] = ""                               # die Gruppe ist das Bild – keine Passanten dazwischen
            continue
        mood = str(sc.get("mood") or "")
        if humans:
            for h in humans[:1]:
                if str(h.get("pos") or "center") in ("center", "", "None", "right"):
                    h["pos"] = 300
                if h.get("to") and str(h.get("to")) in ("center", "mitte", "right", "rechts"):
                    h["to"] = 300                          # wer hereinläuft, bleibt links neben dem Tier stehen
        sc["actors"] = acts + [{"id": "_thema", "kind": kind, "hero": True, "speaks": False, "action": "idle",
                                "emotion": MOOD_EMOTION.get(mood, "happy" if mood == "happy" else ""),
                                "pos": 760 if humans else "center", "emote": "", "say": "", "hold": "", "facing": ""}]


PARTY_RE = r"feier|\bparty|jubel|hurra|gewinn|gewonnen|\bsieg|glückwunsch|gratul|geburtstag|silvester|konfetti|geschafft|rekord|weltmeister|applaus"
SURPRISE_RE = r"überrasch\w* (?:dich|mich|dir|sie|ihn|euch) (?:\w+ ){0,2}mit (?:etwas|was\b|einer kleinigkeit|einem kleinen)|mitbringsel|(?:bringt|schenkt) (?:dir|mir|ihr|ihm) (?:\w+ ){0,2}(?:etwas|eine kleinigkeit) mit"
GIVE_RE = r"\bteil\w*\b|schenk|überreich|\breicht\b|\bgibt\b.{0,40}\b(ab|weiter|her)\b|bringt .{0,40}\bmit\b|bietet .{0,40}\ban\b|spendier"
TAKE_RE = r"\bschnapp\w* dir\b|\bnimm dir\b|\bgreif (?:dir|zu|nach)\b|\bhol dir\b|\bisst\b|\bisse?t\b|\besse\b|bei(ß|ss)t|\bnasch|\bhältst\b|\bhält\b|\bnimmst\b|\bnimmt\b|\bgreifst\b|\bgreift\b|\bhebst\b|in der hand|\bträgst\b"
LYING_RE = r"\b(liegst|liegt|liegen)\b.{0,40}\b(platt|flach|am boden|auf dem boden|auf der straße|auf dem asphalt|auf dem gehweg)\b"
CARRY_RE = r"\b(diese[rnms]?|davon|damit|zusammen|sie alle|alle zusammen)\b"
# „diese positive Energie“, „diese Wirkung“ meinen kein Ding – sonst läge der Kuchen aus dem Büro im nächsten Satz auf der Straße
CARRY_ABSTRACT_RE = (r"\bdiese[rnms]?\s+(?:[a-zäöüß]+\s+)?(energie|wirkung\w*|gefühl\w*|stimmung|reaktion\w*|minute\w*|sekunde\w*|moment\w*|zeit|idee\w*|regel\w*|"
                     r"kraft|kräfte|art|weise|erfahrung\w*|freundlichkeit|geste\w*|effekt\w*|verhalten|welle|veränderung\w*|tatsache\w*|frage\w*|fähigkeit\w*|"
                     r"entdeckung\w*|theorie\w*|zahl\w*|menschen|leute|person\w*)\b")


# „diese Früchte“, „diese Dinger“ meinen das Ding von eben; „diese Meile“, „diese Formel“ nennen etwas Neues
CARRY_GENERIC_RE = (r"frucht|früchte|ding|dinger|teil|teile|stück|stücke|sache|sachen|menge|masse|last|ladung|gegenst[aä]nd\w*|objekt\w*|tier|tiere|ger[aä]t\w*|"
                    r"maschine\w*|exemplar\w*|brocken|kolosse?|riesen?|winzling\w*|kleinen|großen|beiden|drei|vier|alle|hier|da|gewicht|haufen|berg|stapel")


def _carry_other(text, thing):
    """Nennt „diese/dieser/dieses …“ ein eigenes Hauptwort, das nicht das zuletzt gezeigte Ding ist? Dann meint der Satz etwas Neues."""
    import re as _re
    hit = False
    for m in _re.finditer(r"\b[Dd]iese[rnms]?\s+(?:[a-zäöüß]+\s+){0,2}([A-ZÄÖÜ][a-zäöüß]{2,})", str(text or "")):
        noun = m.group(1).lower()
        if _re.fullmatch(CARRY_GENERIC_RE, noun) or _re.search(CARRY_ABSTRACT_RE, "diese " + noun):
            return False
        if any(_re.search(pat, noun) for pat, k in _lib_props() + TEXT_PROPS if k == thing):
            return False
        hit = True
    return hit


def _carry_thing(scenes, main_id=None):
    """„Du steckst neunundneunzig Wassermelonen ein.“ – „Aber in echt wiegen diese Früchte zusammen fast eine Tonne.“: Der Folgesatz
    meint dasselbe Ding, nennt es aber nicht. Statt eines leeren Bildes bleibt es stehen – bei einer großen Zahl gleich mehrfach."""
    import re as _re
    last = None
    for i, sc in enumerate(scenes):
        if not isinstance(sc, dict):
            continue
        low = str(sc.get("text") or "").lower()
        named = [k for pat, k in _lib_props() + TEXT_PROPS if _re.search(pat, low) and extras.prop_fit(k) and k not in extras.SKY and k not in ("pile", "sandpile", "trash")]
        many = any((_number(w) or 0) > 3 for w in _re.findall(r"[a-zäöüß]{4,}|\d+", _re.sub(r"\b[a-zäöüß0-9:.]+\s+uhr\b", " ", low)) if w != "acht")   # „um sechs Uhr“ ist eine Uhrzeit, keine Menge (drei Wecker im Park, Video 173)
        if named:
            last = (named[0], i, many)
            continue
        acts = [a for a in (sc.get("actors") or []) if isinstance(a, dict)]
        rp = places.resolve(backdrop(sc)) if not isinstance(backdrop(sc), dict) else "custom"
        if last and _carry_other(str(sc.get("text") or ""), last[0]):
            continue                                      # „Lauf diese eine Meile“, „Lern diese Formel“: „diese“ benennt selbst etwas anderes – der Wecker von eben bleibt nicht stehen
        if not last or i - last[1] > 2 or not _re.search(CARRY_RE, _re.sub(CARRY_ABSTRACT_RE, " ", low)) or sc.get("props") or sc.get("float") or len(acts) > 1 \
                or sc.get("shot") in ("graphic", "insert", "close") or rp in MAPS or rp in ("space", "underwater") or any(a.get("kind") for a in acts):
            continue
        sc["props"] = [{"type": last[0], "pos": p} for p in ((600, 770, 940) if last[2] else (800,))]
        if sc.get("shot") == "event":
            sc["shot"] = ""
        if acts:
            acts[0]["pos"] = "left"
        elif main_id:
            sc["actors"] = [{"id": main_id, "action": "shocked", "emotion": "shocked", "emote": "!", "pos": "left", "speaks": False}]


# Familienfest / Weihnachten (Prüfung 18.11.2026, Video 148): geschmücktes Wohn- und Esszimmer, Sätze vom Essen spielen an der Festtafel,
# einheitliche Tageszeit. Verwandte, die der Satz nennt, stehen im Bild (in jedem Video).
XMAS_RE = r"weihnacht|heiligabend|heilig abend|heiligen abend|\badvent|bescherung|christbaum|tannenbaum|christkind|nikolaus"
FEAST_RE = XMAS_RE + r"|familienfeier|familienfest|festessen|familienessen|familientisch|ostern|silvester|feiertage?n?\b"
FEAST_TABLE_RE = (r"\btisch\b|esstisch|festessen|weihnachtsessen|\bessen\b|\bisst\b|\bteller|nachschlag|\bbraten|\bgans\b|kloß|klöße|knödel|kartoffelsalat|würstchen|"
                  r"raclette|fondue|hauptgang|ersten gang|dessert|nachtisch|plätzchen|servier|\bsatt\b|appetit|\bgabel|besteck|festtafel|\bsoße|rotkohl|blaukraut|\bportion")
FEAST_TREE_RE = r"weihnachtsbaum|tannenbaum|christbaum|\bbaum\b|geschenk|bescherung|\bsofa\b|wohnzimmer|auspack"
RELATIVES = [(r"\b(?:oma|omas|omi|omis|großmutter)\b", "oma", {"hair": "bun", "hair_color": "grau", "glasses": True, "shirt": "lila", "gender": "w", "size": 0.9}),
             (r"\b(?:opa|opas|opi|großvater)\b", "opa", {"hair": "short", "hair_color": "grau", "glasses": True, "shirt": "braun", "size": 0.95}),
             (r"\b(?:onkel|onkels)\b", "onkel", {"hair": "short", "hair_color": "schwarz", "shirt": "rot", "size": 1.08}),
             (r"\b(?:tante|tantchen)\b", "tante", {"hair": "bob", "hair_color": "blond", "shirt": "türkis", "gender": "w"}),
             (r"\b(?:mama|mamas|mutter|mutti)\b", "mama", {"hair": "long", "hair_color": "braun", "shirt": "gelb", "gender": "w"}),
             (r"\b(?:papa|papas|vater|vati)\b", "papa", {"hair": "short", "hair_color": "dunkelbraun", "glasses": True, "shirt": "blau", "size": 1.05}),
             (r"\b(?:cousin|cousins|vetter)\b", "cousin", {"hair": "short", "hair_color": "blond", "hat": "cap", "shirt": "orange", "size": 0.85}),
             (r"\b(?:cousine|kusine)\b", "cousine", {"hair": "ponytail", "hair_color": "rot", "shirt": "pink", "gender": "w", "size": 0.85}),
             (r"\b(?:schwester|schwesterchen)\b", "schwester", {"hair": "ponytail", "hair_color": "braun", "shirt": "pink", "gender": "w", "size": 0.9}),
             (r"\b(?:bruder|brüderchen)\b", "bruder", {"hair": "short", "hair_color": "braun", "hat": "cap", "shirt": "orange", "size": 0.9})]
SELF_RE = r"\b(?:du|dich|dir|dein\w*|ich|mich|mir|mein\w*|wir|uns|unser\w*)\b"
RELATIVE_IDIOM_RE = r"vater staat|mutter natur|mutter erde|vater unser|großer bruder sieht|big brother|mutter aller|vater aller|mutter(?:sprache|land|mal|schiff|boden|kuchen|leib)|vater(?:land|schaft)"


def _feast_story(scenes, topic=""):
    """Weihnachten / Familienfest: Spricht Thema oder Text von Weihnachten, sind Wohn- und Esszimmer geschmückt (Baum, Girlande –
    `places.XMAS`); Sätze vom Essen spielen an der gedeckten Tafel im Esszimmer, nicht im Flur („nach dem ersten Gang“) oder vor dem Sofa;
    die Tageszeit springt nicht ohne Grund mitten im Fest von Tag auf Nacht."""
    import re as _re
    sc_l = [sc for sc in scenes if isinstance(sc, dict)]
    all_t = (str(topic or "") + " " + " ".join(str(sc.get("text") or "") for sc in sc_l)).lower()
    if not _re.search(FEAST_RE, all_t):
        return
    xmas = bool(_re.search(XMAS_RE, all_t))
    main = next((str(a.get("id")) for sc in sc_l for a in (sc.get("actors") or []) if isinstance(a, dict) and str(a.get("id") or "").lower() in MAIN_IDS), "du")
    for sc in sc_l:
        low = str(sc.get("text") or "").lower()
        if sc.get("shot") == "graphic" or isinstance(backdrop(sc), dict):
            continue
        rp = places.resolve(backdrop(sc))
        home = rp in ("livingroom", "diningroom", "plain", "restaurant", "kitchen") or (rp == "hallway" and not _re.search(r"\bflur\b|\btür|treppenhaus|klingel|klopf", low))
        if (rp in MAPS or rp in ("street", "park", "supermarket")) and _re.search(FEAST_TABLE_RE, low) and not _re.search(r"straße|supermarkt|einkauf|\bladen\b|draußen", low):
            home = True                                    # „In Deutschland liegt Kartoffelsalat ganz vorn“ / „noch vor der Gans“: am Esstisch, nicht auf der Landkarte oder mit einer Gans auf der Straße (Video 149)
            sc["shot"], sc["graphic"], sc["crowd"], sc["weather"] = "", None, "", ""
            if not [a for a in (sc.get("actors") or []) if isinstance(a, dict) and not a.get("to")]:
                sc["actors"] = [{"id": main, "action": "point", "emotion": "happy", "pos": "left", "speaks": True}]
            for a in sc["actors"]:
                if isinstance(a, dict) and str(a.get("action") or "") in ("walk", "run"):
                    a["action"] = "point"
        if home and _re.search(FEAST_TABLE_RE, low) and not _re.search(r"restaurant|\bküche\b|\bherd\b|\bofen\b", low):
            sc["place"], rp = "diningroom", "diningroom"
            sc.pop("backdrop", None)
        elif home and rp in ("plain", "hallway", "restaurant") or (rp == "diningroom" and _re.search(FEAST_TREE_RE, low) and not _re.search(FEAST_TABLE_RE, low)):
            sc["place"], rp = "livingroom", "livingroom"
            sc.pop("backdrop", None)
        if xmas and rp in ("livingroom", "diningroom"):
            sc["_xmas"] = True
            sc["props"] = [q for q in (sc.get("props") or []) if extras.PROP_ALIASES.get(str(q.get("type") if isinstance(q, dict) else q).lower(),
                           str(q.get("type") if isinstance(q, dict) else q).lower()) not in ("tree", "plant")]      # der geschmückte Baum steht schon im Zimmer
        if rp == "diningroom":                             # Tisch, Stühle, Kerzen stehen dort schon
            sc["props"] = [q for q in (sc.get("props") or []) if extras.PROP_ALIASES.get(str(q.get("type") if isinstance(q, dict) else q).lower(),
                           str(q.get("type") if isinstance(q, dict) else q).lower()) not in ("table", "chair", "candle", "lib_stuhl", "stuhl", "lib_gans", "gans")]
            sc["_no_insert"] = True                        # das Essen steht auf dem Tisch: kein Schnitt auf einen einzelnen Kloß vor leerem Grund
    inside = [sc for sc in sc_l if sc.get("shot") != "graphic" and not isinstance(backdrop(sc), dict) and places.resolve(backdrop(sc)) in ("livingroom", "diningroom", "kitchen", "hallway")]
    if inside and not _re.search(r"stromausfall|kerzenschein|im dunkeln|\bdunkel\b|finster|licht (?:geht |ist )?aus|mitten in der nacht|mitternacht", all_t):
        for sc in inside:                                  # ein Fest, ein Licht: das Festzimmer ist hell erleuchtet – „Heiligabend“ als Nacht legte das ganze Video ins düstere Halbdunkel (Video 150), in Video 148 wurde es nach der Hälfte grundlos Nacht
            sc["time"] = "day"


FUNERAL_RE = r"beerdigung|beisetzung|begräbnis|trauerfeier|trauergottesdienst|trauergäste|trauergemeinde|\bsarg\b|\bam grab\b"
CHURCH_IN_RE = r"\bin (?:der|einer|dieser|unserer) (?:\w+ )?(?:kirche|kapelle|trauerhalle)\b|kirchenbank|kirchenbänke|trauerfeier|gottesdienst|trauergäste|trauergemeinde|\bpfarrer|\bpastor|\borgel"
CHURCH_OUT_RE = r"vor der (?:kirche|kapelle)|kirchturm|kirchenglocke|kirchplatz|kirchentür|\bdraußen\b|\bfriedhof|\bam grab\b"


def _funeral_story(scenes, topic=""):
    """Beerdigung / Trauerfeier (Prüfung 20.11.2026, Plan „Unpassend lachen“): „In der Kirche war es so leise …“ spielte auf der Straße vor
    einer Kirche, die „Trauergäste“ waren bunte Passanten mit Mützen, Oma trug eine rote Mütze. Spricht Thema oder Text von einer
    Beerdigung, spielen Kirchen-Szenen im Kirchenraum (`chapel`), alle Menschen in Kirche und am Grab tragen Schwarz (`_mourn`),
    es läuft, jubelt und rennt dort niemand, kein Auto und kein Wetter im Kirchenraum, und es bleibt bei einer Tageszeit."""
    import re as _re
    sc_l = [sc for sc in scenes if isinstance(sc, dict)]
    all_t = (str(topic or "") + " " + " ".join(str(sc.get("text") or "") for sc in sc_l)).lower()
    if not _re.search(FUNERAL_RE, all_t):
        return
    inside = False
    lead_f = next((str(a.get("id")) for sc in sc_l for a in (sc.get("actors") or []) if isinstance(a, dict) and a.get("id") and not a.get("kind")
                   and not _re.search(r"gehirn|hirn|brain", str(a.get("id")).lower())), "du")
    for sc in sc_l:
        low = str(sc.get("text") or "").lower()
        if sc.get("shot") == "graphic" or isinstance(backdrop(sc), dict):
            continue
        rp = places.resolve(backdrop(sc))
        if _re.search(CHURCH_OUT_RE, low):
            inside = False
        elif rp == "church" or (_re.search(CHURCH_IN_RE, low) and rp in GENERIC + ("plain", "street", "park", "village", "graveyard", "church", "hallway")):
            sc["place"], rp, inside = "chapel", "chapel", True
        elif rp == "chapel":
            inside = True
        if rp not in ("chapel", "graveyard"):
            continue
        sc["_mourn"] = True
        cr = str(sc.get("crowd") or "").lower()
        if cr and CROWD_KINDS.get(cr) not in ("sad", "watch", "worried"):
            sc["crowd"] = "sad"                            # niemand schlendert, jubelt oder rennt durch die Trauerfeier
        elif not cr and str(sc.get("shot") or "") not in ("close", "insert") and len([a for a in (sc.get("actors") or []) if isinstance(a, dict)]) < 2 and _re.search(r"beerdigung|trauergäste|trauergemeinde|\balle\b|\bjeder\b|\bleute\b|\bstill|\bleise\b", low):
            sc["crowd"] = "sad"                            # „alle blickten betroffen auf den Boden“: die Trauergäste stehen da
        sc["props"] = [q for q in (sc.get("props") or []) if (extras.PROP_ALIASES.get(str(q.get("type") if isinstance(q, dict) else q).lower(), str(q.get("type") if isinstance(q, dict) else q).lower())
                                                           not in ("vacuum", "vacuum_broken", "smoke", "explosion", "fire"))]   # „ich dachte nur an den Staubsauger“: ein Gedanke – das Gerät steht nicht im Mittelgang
        if rp == "chapel":
            sc["weather"] = ""
            sc["time"] = "day"
            sc["props"] = [q for q in (sc.get("props") or []) if (extras.PROP_ALIASES.get(str(q.get("type") if isinstance(q, dict) else q).lower(), str(q.get("type") if isinstance(q, dict) else q).lower())
                                                               not in ("car", "bus", "truck", "police", "ambulance", "tree", "house", "tv", "computer", "fridge", "sofa"))]
        if not [a for a in (sc.get("actors") or []) if isinstance(a, dict)] and str(sc.get("shot") or "") != "insert" and _re.search(SELF_RE + r"|\bwarum\b|\bwieso\b", low):
            sc["actors"] = [{"id": lead_f, "action": "think", "emotion": "worried", "emote": "?" if "?" in low else "", "pos": "center", "speaks": True, "say": "", "hold": "", "facing": ""}]
            sc["shot"] = ""                                # „Aber warum passiert so etwas …?“ ohne Figur: die Hauptfigur grübelt in der Bank, kein leerer Kirchenraum
        for a in (sc.get("actors") or []):
            if isinstance(a, dict) and not a.get("kind") and str(a.get("action") or "") in ("dance", "cheer", "run") and not _re.search(r"renn|rann|lauf|lief|tanz|flücht|stürm", low):
                a["action"] = "freeze"                     # in der Kirche tanzt und rennt niemand ohne Grund
                a["to"] = ""


TATTOO_RE = r"tattoo|tätowier|tatowier"
NAILS_RE = r"nagelstudio|nageldesign|nagelsalon|manik[üu]re|neumodellage|gel-?nägel|kunstnägel|fingernägel|nagellack|\bnägel\b|nagelfeile|\bfeilt\b|\bfeile\b"
TATTOO_DO_RE = r"\bsticht\b|\bstechen\b|\bgestochen|tätowiert|tätowieren|\bnadel|tattoo"
NAILS_DO_RE = r"\bfeilt\b|\bfeilen\b|\bfeile\b|lackier|\bnägel\b|gel-?nägel|kunstnägel|modellage|manik[üu]re|auffüllen|aufgefüllt"
# Ausbau 28.11.2026 (Plan „Barbershop gegen Friseursalon“): zwei weitere Läden nach demselben Muster. „Haarschnitt“ allein entscheidet
# nicht, in welchem der beiden Läden der Satz spielt – das tun nur die Wörter unten.
BARBER_RE = r"barber|barbier|herrenfriseur|herrensalon|bartpflege|bartschnitt|bartrasur|nassrasur|\brasur\b|\bbart\b|\bbärte\b"
HAIRSALON_RE = r"(?<!herren)fris[eö]ur|coiffeur|haarsalon|haarstudio|damensalon|dauerwelle|strähnchen|waschen[ ,]+(?:und )?schneiden|\bföhn"
BARBER_DO_RE = r"\bschneide[tn]?\b|\bschnitt\b|haarschnitt|\brasier|\brasur|\btrimm|\bstutz|\bbart|bartpflege|\bfade\b|maschinenschnitt"
HAIR_DO_RE = r"\bschneide[tn]?\b|\bschnitt\b|haarschnitt|\bföhn|\bfärb|\bwäscht\b|waschen|\bstyl|strähnchen|dauerwelle|\bfrisier|\bfrisur"
# Ort → (Wörter für den Ort, Wörter für die Arbeit, Werkzeug in der Hand bei der Arbeit, lose Werkzeuge, die in die Hand wandern)
STUDIOS = {"tattoostudio": (TATTOO_RE, TATTOO_DO_RE, ("tattoomachine",), ()),
           "nailstudio": (NAILS_RE, NAILS_DO_RE, ("nailfile", "nailpolish"), ("nailpolish",)),
           "barbershop": (BARBER_RE, BARBER_DO_RE, ("clippers", "razor", "scissors"), ("clippers", "razor", "scissors")),
           "hairsalon": (HAIRSALON_RE, HAIR_DO_RE, ("scissors", "hairdryer"), ("scissors", "hairdryer"))}
STUDIO_TOOLS = ("tattoomachine", "nailfile", "nailpolish", "clippers", "razor", "scissors", "hairdryer")
UNPAID_RE = r"unbezahlt|bezahlt \w+ (?:leider |aber |natürlich )?(?:niemand|keiner)|(?:niemand|keiner) bezahlt|bezahlt (?:leider |aber )?(?:niemand|keiner)|ohne bezahlung|\bkostenlos\b|\bumsonst\b|\bgratis\b|kein(?:en)? cent|kein geld"


def _score_labels(scenes):
    """Punktestand trägt dieselben zwei Namen wie das Duell-Bild (Video 172: „TATTOO“ gegen „PUNKT NÄGEL“)."""
    vs = next((sc["graphic"] for sc in scenes if isinstance(sc, dict) and isinstance(sc.get("graphic"), dict) and sc["graphic"].get("type") == "versus"
               and sc["graphic"].get("left") and sc["graphic"].get("right")), None)
    if not vs:
        return
    for sc in scenes:
        g = sc.get("graphic") if isinstance(sc, dict) else None
        if isinstance(g, dict) and g.get("type") == "score":
            g["left"], g["right"] = vs["left"], vs["right"]


def _unpaid(scenes):
    """„Beratung und Zeichnen bezahlt Tobi leider niemand“ (Video 171, Prüfung 20.11.2026): die Figur hielt dabei einen Stapel Geldscheine.
    Sagt der Satz, dass etwas unbezahlt oder kostenlos ist, liegt und hält niemand Geld."""
    import re as _re
    for sc in scenes:
        if not isinstance(sc, dict) or not _re.search(UNPAID_RE, str(sc.get("text") or "").lower()):
            continue
        key = lambda q: extras.PROP_ALIASES.get(str(q.get("type") if isinstance(q, dict) else q).lower(), str(q.get("type") if isinstance(q, dict) else q).lower())
        sc["props"] = [q for q in (sc.get("props") or []) if key(q) != "money"]
        for a in (sc.get("actors") or []):
            if isinstance(a, dict) and extras.PROP_ALIASES.get(str(a.get("hold") or "").lower(), str(a.get("hold") or "").lower()) in ("money", "prop:money"):
                a["hold"] = ""
        if sc.get("shot") == "insert" and not sc.get("props"):
            sc["shot"] = "wide"


def _studio_story(scenes, topic=""):
    """Tattoo-Studio und Nagelstudio (Prüfung 20.11.2026, Plan „Tattoo-Studio gegen Nagelstudio“): Die Orte gab es nicht – „tattoo_shop“ und
    „nail_salon“ wurden zur leeren Wand. Spricht ein Satz vom Tätowieren oder von Nägeln, spielt er im passenden Studio und die Figur hält
    die Tätowiermaschine bzw. die Nagelfeile. Wer einmal in seinem Studio stand, steht in Folgesätzen ohne eigenen Ort wieder dort
    (Tobi im Tattoo-Studio, Nina im Nagelstudio). Drinnen kein Wetter, kein Auto, keine Passanten."""
    import re as _re
    sc_l = [sc for sc in scenes if isinstance(sc, dict)]
    all_t = (str(topic or "") + " " + " ".join(str(sc.get("text") or "") for sc in sc_l)).lower()
    if not any(_re.search(v_[0], all_t) for v_ in STUDIOS.values()):
        return
    home = {}
    for sc in sc_l:
        if sc.get("shot") == "graphic" or isinstance(backdrop(sc), dict):
            continue
        low = str(sc.get("text") or "").lower()
        rp = places.resolve(backdrop(sc))
        humans = [a for a in (sc.get("actors") or []) if isinstance(a, dict) and a.get("id") and not a.get("kind")]
        hit = [k_ for k_, v_ in STUDIOS.items() if _re.search(v_[0], low)]
        said = _said_place(low)
        if said in STUDIOS and said in hit:
            hit = [said]                                  # „Im Barbershop kostet der Haarschnitt …“: der genannte Laden gilt
        one = hit[0] if len(hit) == 1 else ""
        if rp in GENERIC + ("plain", "office", "hospital", "lab", "supermarket") or (rp in STUDIOS and one in ("barbershop", "hairsalon") and one != rp):
            want = ""                                     # … auch gegen ein Drehbuch, das mangels Ort aufs Tattoo- oder Nagelstudio auswich
            if one:
                want = one
            elif not hit and len(humans) == 1 and str(humans[0]["id"]) in home and rp in ("plain", "livingroom", "street", "park") and not _said_place(low):
                want = home[str(humans[0]["id"])]         # „Sie schafft acht Termine am Tag“: Nina steht in ihrem Nagelstudio
            if want:
                sc["place"], rp = want, want
        if len(humans) == 1 and home:
            # Der Satz handelt vom anderen (Video 172: „Tätowierer verdienen …“ – im Tattoo-Studio stand Nina; „nimmt Tobi dreimal so viel ein“ –
            # zu sehen war Nina): die genannte Person bzw. die Besitzerin des Studios steht im Bild, in ihrem Studio
            me = str(humans[0]["id"])
            named = [k for k in home if k != me and _re.search(r"\b" + _re.escape(k.lower()) + r"s?\b", low)]
            owner = {v_: k_ for k_, v_ in home.items()}
            target = ""
            if len(named) == 1 and not _re.search(r"\b" + _re.escape(me.lower()) + r"s?\b", low):
                target = named[0]
            elif one and owner.get(one) not in (None, me) and home.get(me) not in (None, one):
                target = owner[one]
            if target:
                humans[0]["id"] = target
                humans[0]["hold"] = ""
                if rp in STUDIOS or rp == "plain" or rp in GENERIC:
                    sc["place"] = rp = home[target]
        if rp in STUDIOS and not hit and humans:
            hs = {home.get(str(a["id"])) for a in humans}
            if len(humans) == 1 and hs - {None, rp}:
                sc["place"] = rp = hs.pop()               # der Ort blieb vom Satz davor stehen: Tobi steht nicht im Nagelstudio
            elif len(humans) > 1 and len(hs - {None}) > 1:
                sc["place"] = rp = "plain"                # beide zusammen im Vergleich: neutraler Ort
        if rp not in STUDIOS:
            continue
        sc["weather"] = ""
        if str(sc.get("time") or "") == "night" and not _re.search(r"nacht|abend|mitternacht", low):
            sc["time"] = "day"
        sc["crowd"] = ""
        tools, keep = STUDIOS[rp][2], STUDIOS[rp][3]
        sc["props"] = [q for q in (sc.get("props") or []) if (extras.PROP_ALIASES.get(str(q.get("type") if isinstance(q, dict) else q).lower(), str(q.get("type") if isinstance(q, dict) else q).lower())
                                                           not in ("car", "bus", "truck", "police", "ambulance", "tree", "house", "tv", "computer", "fridge", "sofa", "table", "shelf") + tuple(k_ for k_ in STUDIO_TOOLS if k_ not in keep))]
        loose = [q for q in (sc.get("props") or []) if (extras.PROP_ALIASES.get(str(q.get("type") if isinstance(q, dict) else q).lower(), str(q.get("type") if isinstance(q, dict) else q).lower())) in STUDIO_TOOLS]
        if loose:                                         # Fläschchen und Feile liegen nicht auf dem Fußboden: in die Hand oder weg
            sc["props"] = [q for q in sc["props"] if q not in loose]
            if humans and not str(humans[0].get("hold") or "") and str(humans[0].get("action") or "") not in ("run", "sleep", "fall", "jump", "dance", "wave", "shake", "lie"):
                humans[0]["hold"] = str(loose[0].get("type") if isinstance(loose[0], dict) else loose[0])
        if len(humans) == 1:
            home.setdefault(str(humans[0]["id"]), rp)
        do = _re.search(STUDIOS[rp][1], low)
        for a in humans[:1]:
            if home.get(str(a["id"]), rp) != rp:
                continue                                  # der Tätowierer hält im Nagelstudio keine Feile
            if do:
                sc["_no_insert"] = True                   # der Satz beschreibt die Arbeit: kein Schnitt auf Geld oder Werkzeug allein
                if sc.get("shot") == "insert":
                    sc["shot"] = "wide"
            if do and not str(a.get("hold") or "") and str(a.get("action") or "") not in ("run", "sleep", "fall", "jump", "dance", "wave", "shake", "lie"):
                tool = tools[0]
                if rp == "barbershop" and _re.search(r"\bbart|\brasier|\brasur", low) and not _re.search(r"haarschnitt|\bhaare\b", low):
                    tool = "razor"                        # nur Bart: Rasiermesser statt Haarschneider
                elif rp == "hairsalon" and _re.search(r"\bföhn|\bstyl", low) and not _re.search(r"\bschneide|\bschnitt\b|haarschnitt", low):
                    tool = "hairdryer"
                a["hold"] = tool                          # das Werkzeug in der Hand statt am Boden


def _studio_money(scenes):
    """Barbershop und Friseursalon (Prüfung 28.11.2026, Plan „Barbershop gegen Friseursalon“): Der Tisch mit dem Geldstapel stand mitten im
    Barbierstuhl bzw. im Waschplatz, bei „Davon gehen Miete, Material … ab“ gleich dreimal nebeneinander. Die festen Möbel stehen dort rechts –
    das Geld liegt deshalb links vor der Ablage, die Figur steht rechts daneben. Hält die Figur ihr Werkzeug (Schere, Föhn, Rasiermesser),
    ist die Arbeit das Bild: kein Geldtisch daneben, der Preis steht auf der Karte."""
    for sc in scenes:
        if not isinstance(sc, dict) or sc.get("shot") in ("graphic", "insert") or isinstance(backdrop(sc), dict):
            continue
        if places.resolve(backdrop(sc)) not in ("barbershop", "hairsalon"):
            continue
        key = lambda q: extras.PROP_ALIASES.get(str(q.get("type") if isinstance(q, dict) else q).lower(), str(q.get("type") if isinstance(q, dict) else q).lower())   # noqa: E731
        props = [q for q in (sc.get("props") or [])]
        if not any(key(q) == "money" for q in props):
            continue
        humans = [a for a in (sc.get("actors") or []) if isinstance(a, dict) and a.get("id") and not a.get("kind")]
        rest = [q for q in props if key(q) != "money"]
        if any(extras.PROP_ALIASES.get(str(a.get("hold") or "").lower(), str(a.get("hold") or "").lower()) in STUDIO_TOOLS for a in humans):
            sc["props"] = rest
            continue
        sc["props"] = rest + [{"type": "money", "pos": 230}]
        for a in humans[:1]:
            if a.get("to"):
                if str(a.get("to")) in ("left", "center"):
                    a["to"] = "right"
            elif str(a.get("pos") or "center") in ("left", "center"):
                a["pos"] = "right"


def _relatives(scenes):
    """Nennt der Satz Oma, Opa, Onkel, Tante, Mama, Papa, Cousin …, steht die Person im Bild – mit eigenem Aussehen (graue Haare, Dutt, Brille …).
    Handelt der Satz nur von ihr (kein du/ich), steht sie anstelle der Hauptfigur da; sonst rechts neben ihr. In Video 148 „zog Oma eine
    Trillerpfeife“ – zu sehen war die Hauptfigur; im Nachbarn-Video 147 war kein einziger Nachbar zu sehen."""
    import re as _re
    for sc in scenes:
        if not isinstance(sc, dict) or sc.get("shot") == "graphic" or sc.get("_sea") or sc.get("_balloon") or sc.get("float"):
            continue
        low = str(sc.get("text") or "").lower()
        if _re.search(RELATIVE_IDIOM_RE, low):
            continue
        if not isinstance(backdrop(sc), dict) and places.resolve(backdrop(sc)) in MAPS + ("space", "underwater", "cave", "highsky"):
            continue
        acts = [a for a in (sc.get("actors") or []) if isinstance(a, dict)]
        if any(_re.search(pat, low) for pat, _k, _l in RELATIVES):
            sc["_no_insert"] = True                        # der Satz handelt von der Person: kein Schnitt auf ein Ding allein
            if sc.get("shot") == "insert" and any(not a.get("kind") for a in acts):
                sc["shot"] = ""                            # „Der Onkel sitzt auf dem Sofa und erzählt“: sechs Sekunden ein Sofa vor leerem Grund (Video 150)
                sc["props"] = [q for q in (sc.get("props") or []) if not _re.search(r"sofa|couch|sessel", str(q.get("type") if isinstance(q, dict) else q).lower())]
        found = sorted(((m.start(), key, look) for pat, key, look in RELATIVES for m in [_re.search(pat, low)] if m), key=lambda x: x[0])[:2]
        found = [(pos, key, look) for pos, key, look in found if not any(key in str(a.get("id") or "").lower() for a in acts)]
        if not found or any(a.get("kind") for a in acts):  # Tier-Szenen bleiben, wie sie sind („die Mutter säugt ihre Jungen“)
            continue
        creature = [a for a in acts if a.get("kind")][:1]
        humans = [a for a in acts if not a.get("kind")]
        lead = humans[0] if humans else {}
        only_them = not _re.search(SELF_RE, low)
        new = []
        for n, (pos, key, look) in enumerate(found):
            new.append({"id": key, "look": dict(look), "speaks": n == 0 and pos < 25,
                        "action": (str(lead.get("action") or "talk") if only_them and n == 0 and str(lead.get("action") or "") not in ("walk", "run", "freeze", "pant", "cower", "sleep", "fall") else "talk" if n == 0 else "idle"),
                        "emotion": str(lead.get("emotion") or "") if only_them and n == 0 else "happy" if n == 0 else "",
                        "say": str(lead.get("say") or "") if only_them and n == 0 else "", "hold": str(lead.get("hold") or "") if only_them and n == 0 else ""})
        if only_them or not humans:
            cast_n = (new + creature)[:2]
        else:
            lead.update(pos=300, to="", speaks=False)
            if str(lead.get("action") or "") in ("walk", "run"):
                lead["action"] = "idle"
            cast_n = [lead] + new[:1]
        if len(cast_n) == 1:
            cast_n[0]["pos"] = "center"
        else:
            for a, x in zip(cast_n, (300, 780)):
                a["pos"], a["to"] = x, ""
        sc["actors"] = cast_n
        sc["crowd"] = ""
        sc["_no_insert"] = True                            # es geht um die Person und was sie tut, nicht um das Ding allein
        if sc.get("shot") in ("insert", "event") or (sc.get("shot") == "close" and len(cast_n) > 1):
            sc["shot"] = ""
    keys_r = [key for _p, key, _l in RELATIVES]
    seen = {}                                             # Verwandte, die im Video schon auftreten (aus Drehbuch oder von oben), in der Reihenfolge ihres Auftritts
    for sc in scenes:
        for a in (sc.get("actors") or []) if isinstance(sc, dict) else []:
            if isinstance(a, dict) and str(a.get("id") or "").lower() in keys_r:
                seen.setdefault(str(a["id"]).lower(), a)
    if len(seen) >= 2:                                    # „Diese vier Typen sitzen an jedem Tisch“: die Gruppe sind die Verwandten des Videos, keine drei Fremden (Video 149)
        for sc in scenes:
            acts = [a for a in (sc.get("actors") or []) if isinstance(a, dict)] if isinstance(sc, dict) else []
            fill = [a for a in acts if str(a.get("id") or "").startswith("_team")]
            if not fill:
                continue
            pool = [v for k, v in seen.items() if not any(str(a.get("id") or "").lower() == k for a in acts)]
            for a, rel in zip(fill, pool):
                a["id"] = rel["id"]
                if isinstance(rel.get("look"), dict):
                    a["look"] = dict(rel["look"])
                else:
                    a.pop("look", None)


FAMILY_RE = (r"\bfamilien?\b|frauen und (?:\w+ ){0,2}kinder|erwachsene und (?:\w+ ){0,2}kinder|(?:ehe)?frau(?:en)? und (?:\w+ ){0,2}kind|mit (?:ihren|seinen|den|ihrer|seiner|deinen|deiner) (?:\w+ ){0,3}kindern|eltern und (?:\w+ ){0,2}kinder|"
             r"\bmutter\b.{0,40}\bkind|\bkinder\b.{0,40}\b(?:mutter|eltern|ehefrau)")
FAMILY_LOOKS = ({"shirt": "lila", "hair": "long", "hair_color": "braun", "gender": "w"}, {"shirt": "gelb", "hair": "bob", "hair_color": "blond", "size": 0.62, "gender": "w"},
                {"shirt": "grün", "hat": "cap", "size": 0.6})


def _family(scenes, main_id="du"):
    """Spricht der Satz von Familien, Frauen und Kindern, stehen sie auch im Bild: neben der Hauptfigur eine Frau und ein Kind –
    nicht wieder nur die zwei Männer aus dem Keller."""
    import re as _re
    for sc in scenes:
        if not isinstance(sc, dict) or sc.get("shot") in ("graphic", "insert", "event") or sc.get("_balloon") or sc.get("_sea") or sc.get("float"):
            continue
        acts = [a for a in (sc.get("actors") or []) if isinstance(a, dict)]
        if not acts or len(acts) > 2 or any(a.get("kind") for a in acts) or not _re.search(FAMILY_RE, str(sc.get("text") or "").lower()):
            continue
        if places.resolve(backdrop(sc)) in MAPS + ("space", "underwater", "cave", "highsky"):
            continue
        if places.resolve(backdrop(sc)) in ("supermarket", "supermarket_empty", "office", "serverroom", "lab") and not _re.search(r"kauf|laden|geschäft|supermarkt|büro|labor", str(sc.get("text") or "").lower()):
            sc["place"] = "livingroom"                                    # die Familie ist zu Hause, nicht zwischen Regalen
            sc.pop("backdrop", None)
            sc["props"] = []
        lead = acts[0]
        emo = lead.get("emotion") or ""
        lead.update(pos=230, to="", hold="" if str(lead.get("hold") or "").startswith("prop:") else lead.get("hold") or "")
        if str(lead.get("action") or "") in ("sit", "sleep", "fall", "float", "run", "walk"):
            lead["action"] = "talk"
        sc["actors"] = [lead, {"id": "_frau", "action": "idle", "emotion": emo, "pos": 560, "speaks": False, "look": dict(FAMILY_LOOKS[0])},
                        {"id": "_kind", "action": "idle", "emotion": emo, "pos": 850, "speaks": False, "look": dict(FAMILY_LOOKS[1 + (len(str(sc.get("text") or "")) % 2)])}]
        sc["crowd"] = ""
        if sc.get("shot") == "close":
            sc["shot"] = ""


# Ballonfahrt / Ballonflucht: Der Heißluftballon ist das Bild der Geschichte – am Boden als Stoffberg mit Gondel, beim Start mit Flamme,
# in der Luft vor dem hohen Himmel (acht Köpfe in der Gondel statt Figuren, die auf einer Wiese stehen), nach der Landung im Gebüsch.
HOTAIR_RE = r"heißluftballon|heissluftballon|ballonfahr|ballonflucht|ballonflug|ballonhülle|fesselballon|\bgondel|flucht (?:\w+ ){0,3}ballon|ballon (?:\w+ ){0,6}(?:brenner|gasflasche|flucht|fliehen)"
B_WORD_RE = r"ballon|\bhülle\b|stoffbeutel|stoffsack|stoffhülle"
B_UP_RE = (r"\bheb\w* (?:\w+ ){0,6}ab\b|abheb|abgehoben|steig\w* (?:\w+ ){0,6}(?:auf\b|höher|empor|in die höhe|in den himmel|nach oben|in die nacht|in die dunkelheit)|aufsteig|aufgestiegen|"
           r"schieß\w* (?:\w+ ){0,4}(?:nach oben|in die höhe|in den himmel|empor)|kapp\w* (?:\w+ ){0,3}(?:seil|leine)|start(?:et|en) (?:\w+ ){0,5}(?:nacht|himmel|flug|luft)|"
           r"in der luft|am himmel|dort oben|hoch oben|meter(?:n)? höhe|über den wolken|schweb|treib\w* (?:\w+ ){0,4}(?:über|richtung|durch)|flieg\w* (?:\w+ ){0,4}(?:über|richtung|durch)")
B_DOWN_RE = (r"\bland(?:en|et|ete|eten|ung)\b|gelandet|krach\w*|aufschlag|schl[aä]g\w* (?:\w+ ){0,5}auf\b|aufprall|prall\w* |setz\w* (?:\w+ ){0,5}auf\b|aufgesetzt|bruchland|"
             r"im gebüsch|in ein gebüsch|in (?:den|die|einen) (?:bäume|baumkronen|wald|busch)|am boden angekommen|wieder (?:am|auf dem) boden|festen boden")
B_FALL_RE = r"abstürz|absturz|abzustürzen|stürz\w* (?:\w+ ){0,3}(?:ab\b|in die tiefe|zu boden|richtung)|freien fall|sink\w*|sackt|verlier\w* (?:\w+ ){0,3}höhe|rast\w* (?:\w+ ){0,4}(?:boden|erde|tiefe)"
B_GAS_RE = r"gas (?:\w+ ){0,4}(?:aus\b|leer|alle\b|zu ende)|kein gas|flamme (?:\w+ ){0,3}(?:erlisch|aus\b)|brenner (?:\w+ ){0,3}(?:aus\b|versagt|erlisch)|erlischt|geht (?:\w+ ){0,4}aus\b"
B_FILL_RE = r"gasflasche|brenner|flamme|\bfeuer|auftrieb|heiße[rn]? luft|füll\w*|bläh\w*|richtet sich auf|propan"
B_SETUP_RE = r"wiese|\bfeld|lichtung|waldrand|draußen|startplatz|aufbau|bauen (?:\w+ ){0,8}auf\b|baut (?:\w+ ){0,8}auf\b|ausbreit|entfalt|ausroll|auslegen|schleppen|tragen"
B_INDOOR_RE = r"keller|dachboden|garage|wohnzimmer|zimmer|\bnäh|genäht|\bkauf|gekauft|\bstoff\b|stoffe\b|\bplan\b|planen|\bidee|versteck|maschine|zeitschrift|\bbuch\b|heimlich|stasi|verrat|erste[nr]? versuch"
B_PEOPLE_RE = r"frier|zitter|eiskalt|kälte|\bminus\b|personen|familien|kinder|menschen|passagier|insassen|an bord|klammer|drängen|kauern|\bangst"
B_LIGHT_RE = r"scheinwerfer|lichtkegel|leuchtrakete|lichtstrahl|grelles licht|strahler"


def _balloon_story(scenes, topic=""):
    import copy
    import re as _re
    if not _re.search(HOTAIR_RE, (str(topic or "") + " " + " ".join(str(sc.get("text") or "") for sc in scenes if isinstance(sc, dict))).lower()):
        return
    night = any(isinstance(sc, dict) and str(sc.get("time") or "").lower() == "night" for sc in scenes)
    air = dark = fell = prev_ground = landed = False
    lead_id = next((a.get("id") for sc in scenes if isinstance(sc, dict) for a in (sc.get("actors") or []) if isinstance(a, dict) and not a.get("kind") and a.get("id")
                    and not str(a.get("id")).startswith("_")), None)
    n_air, last_kind = 0, ""

    def stage_it(sc, kind, place, props, actors=()):
        if sc.get("shot") != "graphic" or not graphics.clean(sc.get("graphic")):
            if place == "highsky":
                sc["place"] = "highsky"
                sc.pop("backdrop", None)
            elif isinstance(sc.get("backdrop"), dict) and str(sc["backdrop"].get("ground") or "") in ("grass", "soil", "snow", "sand"):
                sc["backdrop"]["elements"] = [e for e in sc["backdrop"].get("elements") or [] if e in ("hills", "mountains", "village")] or ["hills"]   # freier Blick: keine Baumstämme, keine Windräder
            else:
                sc["place"], sc["backdrop"] = "fields", {"sky": "night" if night else "day", "ground": "grass", "elements": ["hills"]}
            if night:
                sc["time"] = "night"
            sc["props"] = [dict(q) for q in props]
            sc["actors"] = list(actors)
            sc["crowd"] = ""
            sc["shot"] = ""
            sc["weather"] = "" if place == "highsky" else sc.get("weather") or ""
            for k in ("float", "aloft", "low", "dark_city"):
                sc.pop(k, None)
            if isinstance(sc.get("overlay"), dict) and str(sc["overlay"].get("type") or "") in ("phone", "note", "list", "bubble"):
                sc["overlay"] = None
        sc["_balloon"] = kind

    for sc in scenes:
        if not isinstance(sc, dict):
            continue
        low = str(sc.get("text") or "").lower()
        word = bool(_re.search(B_WORD_RE, low))
        up, down = _re.search(B_UP_RE, low), _re.search(B_DOWN_RE, low)
        humans = [a for a in (sc.get("actors") or []) if isinstance(a, dict) and not a.get("kind")][:2]
        if air and down:                                                  # Landung: Hülle im Gebüsch, Gondel schief im Gras, die Menschen stehen daneben
            air = dark = fell = prev_ground = False
            g_d = graphics.clean(sc.get("graphic")) if sc.get("shot") == "graphic" else None
            if g_d and g_d.get("type") in ("number", "counter"):          # die Landung will man sehen – die Zahl („28 MINUTEN“) wird zum Schild
                sc["overlay"] = {"type": "card", "text": f"{g_d.get('value')} {g_d.get('label') or g_d.get('unit') or ''}".strip().upper()}
                sc["shot"], sc["graphic"] = "", None
            for a in humans[:1]:
                a.update(action="shocked", emotion="scared", pos=170, to="", hold="", emote="!", facing="right")
            stage_it(sc, "down", "ground", [{"type": "balloon_down", "pos": 650}], humans[:1])
            last_kind, landed = "down", True
            continue
        if air or (up and (word or prev_ground)):                         # in der Luft
            first = not air
            air, prev_ground = True, False
            if _re.search(B_FALL_RE, low):
                fell = True
            elif _re.search(B_GAS_RE, low):
                dark = True
            g_b = graphics.clean(sc.get("graphic")) if sc.get("shot") == "graphic" else None
            if first and g_b and g_b.get("type") in ("number", "counter"):   # der Ballon hebt ab: das will man sehen – die Zahl wird zum Schild
                sc["overlay"] = {"type": "card", "text": f"{g_b.get('value')} {g_b.get('label') or g_b.get('unit') or ''}".strip().upper()}
                sc["shot"], sc["graphic"] = "", None
            pos = (540, 470, 610)[n_air % 3]
            n_air += 1
            if fell:
                kind, props = "fall", [{"type": "balloon_out", "pos": pos}]
            elif dark:
                kind, props = "dark", [{"type": "balloon_dark", "pos": pos}]
            elif _re.search(B_PEOPLE_RE, low) and last_kind != "gondola" and not first and \
                    str((sc.get("overlay") or {}).get("type") or "") not in ("thermo", "bar", "counter"):   # das Thermometer stünde quer über der Hülle
                kind, props = "gondola", [{"type": "gondola", "pos": 540}]
            else:
                kind, props = "fly", [{"type": "balloon", "pos": pos}]
            if _re.search(B_LIGHT_RE, low):
                kind, props = "light", [{"type": "searchlight", "pos": props[0]["pos"]}] + props
            stage_it(sc, kind, "ground" if first and not _re.search(B_LIGHT_RE, low) else "highsky", props)
            last_kind = kind
            continue
        indoor = bool(_re.search(B_INDOOR_RE, low))
        if not indoor and (_re.search(B_GAS_RE, low) and _re.search(r"\bgas\b|flamme|brenner", low) or (word and _re.search(B_FALL_RE, low))):
            fall_t = bool(_re.search(B_FALL_RE, low))                     # Vorgriff („kurz vor dem Ziel geht das Gas aus“): das Bild dazu, die Geschichte läuft am Boden weiter
            stage_it(sc, "fall" if fall_t else "dark", "highsky", [{"type": "balloon_out" if fall_t else "balloon_dark", "pos": 540}])
            prev_ground, last_kind = False, sc["_balloon"]
            continue
        if _re.search(r"\bgondel|ballonkorb|\bplattform|wäscheleine|geländer", low) or (
                last_kind in ("gondola", "basket") and prev_ground and _re.search(r"gasflasche|\bmitte\b|mittig", low) and not _re.search(r"brenner|flamme|\bfeuer|füll|bläh|richtet|faucht", low)):   # die winzige Gondel ganz nah – mit allen, die hineinmüssen;
            if last_kind == "gondola":                                    # im Folgesatz steht sie leer auf der Wiese: Geländer und Gasflaschen sind zu sehen
                stage_it(sc, "basket", "ground", [{"type": "gondola_empty", "pos": 540}])
            else:
                stage_it(sc, "gondola", "highsky", [{"type": "gondola", "pos": 540}])
            prev_ground, last_kind = True, sc["_balloon"]
            continue
        if word and down and not _re.search(B_INDOOR_RE, low):          # ein Versuch endet am Boden, ohne dass der Flug erzählt wurde
            for a in humans[:1]:
                a.update(action="shocked", emotion="scared", pos=170, to="", hold="", emote="!", facing="right")
            stage_it(sc, "down", "ground", [{"type": "balloon_down", "pos": 650}], humans[:1])
            prev_ground, last_kind = False, "down"
            continue
        fill = _re.search(B_FILL_RE, low) or (word and _re.search(r"meter (?:hoch|breit|groß)|riesig|gigantisch|gewaltig|so (?:hoch|groß) wie|kubikmeter|fertig|steht", low))
        setup = not indoor and _re.search(r"bau\w* (?:\w+ ){0,8}auf\b|aufbau|aufgebaut|startplatz|breiten (?:\w+ ){0,6}aus\b|ausgebreitet", low)
        if (word and (fill or _re.search(B_SETUP_RE, low) or not indoor)) or (prev_ground and fill and not indoor) or setup:
            for j, a in enumerate(humans[:1]):
                a.update(action="point" if fill else "look_around", emotion=a.get("emotion") or "worried", pos=170, to="", hold="", facing="right")
            stage_it(sc, "fill" if fill else "ground", "ground", [{"type": "balloon_fill", "pos": 660}] if fill else [{"type": "balloon_ground", "pos": 560}], humans[:1])
            prev_ground, last_kind = True, sc["_balloon"]
            continue
        prev_ground = False
        bd_l = sc.get("backdrop") if isinstance(sc.get("backdrop"), dict) else {}
        city_l = places.resolve(backdrop(sc)) in ("street", "plain", "livingroom", "basement", "supermarket", "highsky", "office") or \
            str(bd_l.get("ground") or "") == "road" or any(e in ("street", "city", "ruins", "factory") for e in bd_l.get("elements") or [])
        if landed and sc.get("shot") not in ("graphic", "insert") and not _said_place(low) and city_l:
            sc["place"], sc["backdrop"] = "fields", {"sky": "night" if night else "day", "ground": "grass", "elements": ["village"]}   # gelandet wird auf dem Land: Wiese am Dorfrand, keine Großstadtstraße
            sc["crowd"] = ""
            if night:
                sc["time"] = "night"
            if sc.get("shot") == "event":
                sc["shot"] = ""
            if not humans and lead_id:                                    # die Geretteten sind im Bild – nicht nur ein Streifenwagen vor leeren Häusern
                glad = bool(_re.search(r"überleb|geschafft|gerettet|\bfrei\b|freiheit|sicherheit|bayern|westen|jubel", low))
                sc["actors"] = [{"id": lead_id, "action": "jump" if glad else "look_around", "emotion": "happy" if glad else "worried", "emote": "" if glad else "?",
                                 "pos": 250, "speaks": False, "say": "", "hold": "", "facing": "right"}]
                sc["props"] = [dict(q, pos=760) if isinstance(q, dict) and not q.get("pos") else q for q in (sc.get("props") or [])]
        if landed and sc.get("shot") != "graphic" and not _re.search(r"\bauto|\bpkw|\bwagen\b|\bbus\b|laster|lkw", low):   # kein beliebiges rotes Auto neben den Geretteten
            sc["props"] = [q for q in (sc.get("props") or []) if not (isinstance(q, dict) and extras.PROP_ALIASES.get(str(q.get("type")).lower(), str(q.get("type")).lower()) in ("car", "bus", "truck", "trafficlight", "streetlamp"))]
        if sc.get("shot") != "graphic":                                   # ein Ballon aus dem Drehbuch in einem Satz, der nicht vom Ballon handelt (im Wohnzimmer, im Laden): raus
            kept = [q for q in (sc.get("props") or []) if not (isinstance(q, dict) and extras.PROP_ALIASES.get(str(q.get("type")).lower(), str(q.get("type")).lower()) in extras.BALLOON_KINDS)]
            if len(kept) != len(sc.get("props") or []):
                sc["props"] = kept
    for sc in scenes:                                                     # Zähler liefe groß quer über den Ballon: als Schild darüber
        ov_b = sc.get("overlay") if isinstance(sc, dict) and sc.get("_balloon") else None
        if isinstance(ov_b, dict) and str(ov_b.get("type") or "") == "counter" and sc.get("shot") != "graphic":
            val_b = ov_b.get("value")
            val_b = int(val_b) if isinstance(val_b, float) and val_b == int(val_b) else val_b
            sc["overlay"] = {"type": "card", "text": f"{val_b} {str(ov_b.get('unit') or ov_b.get('label') or '').strip()}".strip().upper()}
    first_sc = scenes[0] if scenes and isinstance(scenes[0], dict) else None
    if first_sc is not None and len(scenes) >= 4 and first_sc.get("_balloon") not in ("fly", "light", "dark", "fall") and first_sc.get("shot") != "graphic":
        src = next((sc for sc in scenes if isinstance(sc, dict) and sc.get("_balloon") == "light"), None) or \
            next((sc for sc in scenes if isinstance(sc, dict) and sc.get("_balloon") == "fly" and sc.get("place") == "highsky"), None) or \
            next((sc for sc in scenes[1:] if isinstance(sc, dict) and sc.get("_balloon") in ("fly", "dark", "fall")), None)
        if src is not None:                                               # erstes Bild: der Ballon am Nachthimmel im Scheinwerferlicht – nicht zwei Leute im Keller
            for k in ("time", "props"):
                first_sc[k] = copy.deepcopy(src.get(k))
            first_sc["place"] = "highsky"
            first_sc.pop("backdrop", None)
            first_sc.update(actors=[], crowd="", shot="", weather="", _balloon="open", _cold_open=True)
            for k in ("float", "aloft", "low", "dark_city"):
                first_sc.pop(k, None)


def _probe_story(scenes, topic="", main_id=""):
    """Geschichte einer Raumsonde (Voyager): Spielt ein Satz im All, sieht man die gezeichnete Sonde vor dem tiefen Weltraum – groß, klein in der
    Ferne, funkend, mit dem Befehl von der Erde oder mit zerhacktem Datenmüll, je nach Satz und nie zweimal hintereinander gleich. Keine Stadtstraße,
    keine Passanten, kein Mondboden, kein gelernter Notbehelf. Im Kontrollraum kommt die Ingenieurin nicht in jeder Szene neu zur Tür herein,
    sondern arbeitet am Rechner (Video 177)."""
    import re as _re
    if not _re.search(PROBE_RE, (str(topic or "") + " " + " ".join(str(sc.get("text") or "") for sc in scenes if isinstance(sc, dict))).lower()):
        return
    last, walkins, last_act = "", 0, ""
    for n, sc in enumerate(scenes):
        if not isinstance(sc, dict):
            continue
        low = str(sc.get("text") or "").lower()
        keys = [extras.PROP_ALIASES.get(str(q.get("type") if isinstance(q, dict) else q).lower(), str(q.get("type") if isinstance(q, dict) else q).lower()) for q in sc.get("props") or []]
        sc["props"] = [q for q, k in zip(sc.get("props") or [], keys) if k not in ("lib_raumsonde", "lib_sonde", "lib_voyager")]   # gelernter Notbehelf: sah aus wie eine Drohne
        if sc.get("shot") == "graphic" and graphics.clean(sc.get("graphic")):
            last = ""
            continue
        rp = places.resolve(backdrop(sc)) if not isinstance(backdrop(sc), dict) else "custom"
        humans = [a for a in (sc.get("actors") or []) if isinstance(a, dict) and not a.get("kind")]
        plan_space = places.resolve(sc.get("place")) in ("space", "moon")     # auch mit eigenem Hintergrund der Text-KI (Wiese mit Mond unter der Sonde, Video 179)
        out_there = not humans and rp not in ROOMS and bool(_re.search(PROBE_RE + r"|\bsonde\b|interstellar|\balls?\b|weltall|weltraum", low))
        if (rp in ("space", "moon") or plan_space or out_there) and (not humans or not _re.search(r"astronaut|raumfahrer|kosmonaut", low)):   # dort draußen ist kein Mensch – auch keiner, der „hereinkommt“
            if _re.search(JUNK_TALK_RE + r"|datensalat|kauderwelsch|verstumm|nur noch (?:unsinn|rauschen|nullen)", low):
                kind = "probe_glitch"
            elif _re.search(r"befehl|kommando|hochgeschick|schick\w* (?:\w+ ){0,5}(?:ins all|ins weltall|zur sonde|hinauf|hoch)|von der erde aus", low):
                kind = "probe_uplink"
            elif _re.search(r"signal|funk|\bsend|\bdaten\b|antwort|lebenszeichen|empf[aä]ng|nachricht|meldet", low):
                kind = "probe_signal"
            elif _re.search(r"\bweit|entfern|reist|fliegt|unendlich|dunkelheit|einsam|interstellar|kilometer|leere", low):
                kind = "probe_far"
            else:
                kind = "probe"
            if n == 0:
                kind = "probe" if kind == "probe_far" else kind       # erstes Bild: die Sonde groß, man soll sie erkennen
            if kind == last:
                kind = {"probe": "probe_far", "probe_far": "probe", "probe_signal": "probe", "probe_uplink": "probe_signal", "probe_glitch": "probe_far"}[kind]
            sc["place"], sc["time"] = "space", "night"
            sc.pop("backdrop", None)
            sc.update(props=[{"type": kind, "pos": 540}], actors=[], crowd="", shot="", weather="", _probe=kind, _ov_low=3, _no_cut=True)
            for k in ("float", "aloft", "low", "dark_city"):
                sc.pop(k, None)
            ov = sc.get("overlay")
            if isinstance(ov, dict) and str(ov.get("type") or "") == "counter":   # Zähler liefe groß quer über die Sonde: als Schild darüber
                val = ov.get("value")
                val = int(val) if isinstance(val, float) and val == int(val) else val
                sc["overlay"] = {"type": "card", "text": f"{val} {str(ov.get('unit') or ov.get('label') or '').strip()}".strip().upper()}
            elif isinstance(ov, dict) and str(ov.get("type") or "") in ("choice", "checklist", "phone", "note", "bar", "thermo"):
                sc["overlay"] = None                                  # Liste/Auswahl deckt die Sonde zu
            elif isinstance(ov, dict) and str(ov.get("type") or "") == "tag" and str(ov.get("text") or "").strip():
                sc["overlay"] = {"type": "card", "text": str(ov["text"]).strip()}   # ein Schild klebte quer auf der Schüssel: als Karte ganz oben (Video 179)
            last = kind
            continue
        last = ""
        if rp in ROOMS and len(humans) == 1 and len(sc.get("actors") or []) == 1 and str(humans[0].get("action") or "") == "walk" \
                and str(humans[0].get("pos") or "") in ("offleft", "offright") and not humans[0].get("say"):
            walkins += 1
            if walkins > 1:                                           # schon einmal hereingekommen: jetzt arbeitet sie am Rechner
                a = humans[0]
                if _re.search(r"du denkst|vielleicht|\bwarum|\bwie\b|rätsel|problem|\bwarten|musste", low):
                    act, emo, emote = "think", a.get("emotion") or "", "?"
                elif _re.search(r"endlich|geschafft|erfolg|klare daten|plötzlich wieder|funktioniert|gerettet", low):
                    act, emo, emote = "cheer", "happy", ""
                elif _re.search(r"kaputt|defekt|ausfall|fehler|nicht mehr", low):
                    act, emo, emote = "shocked", "worried", "!"
                else:
                    act, emo, emote = ("point", a.get("emotion") or "", "") if walkins % 2 else ("talk", a.get("emotion") or "", "")
                if act == last_act:                                   # nie zweimal hintereinander dieselbe Geste am Rechner
                    act = next(x for x in ("point", "talk", "look_around", "think") if x != last_act)
                    emote = "?" if act == "think" else ""
                last_act = act
                a.update(action=act, emotion=emo, emote=emote, pos="left", facing="right")
                a.pop("to", None)
                if "computer" not in keys:
                    sc["props"] = list(sc.get("props") or []) + [{"type": "computer"}]


def _look_sig(sc):
    """Was man in einer Szene sieht (Ort, Figuren/Wesen, Dinge, Einstellung) – gleich = für den Zuschauer dasselbe Bild."""
    if not isinstance(sc, dict):
        return None
    acts = tuple(sorted(str(a.get("kind") or a.get("id") or "") + ":" + str(a.get("action") or "") for a in (sc.get("actors") or []) if isinstance(a, dict)))
    props = tuple(sorted(str(p.get("type") if isinstance(p, dict) else p) for p in (sc.get("props") or [])))
    return (str(places.resolve(backdrop(sc))), acts, props, str(sc.get("shot") or ""), str((sc.get("graphic") or {}).get("type") if isinstance(sc.get("graphic"), dict) else ""))


def _vary_repeats(scenes):
    """Nie zweimal dasselbe Bild hintereinander: Gleicht eine Szene der vorigen, bekommt sie eine andere Einstellung – das Wesen
    schwimmt/läuft durchs Bild, die Seite wird gespiegelt, oder die Figur kommt groß. Dazu eine andere Kamerafahrt."""
    turn = 0
    for i in range(1, len(scenes)):
        sc, prev = scenes[i], scenes[i - 1]
        if not isinstance(sc, dict) or sc.get("shot") in ("graphic", "insert") or sc.get("float") or _look_sig(sc) != _look_sig(prev):
            continue
        if sc.get("_sea") and sc.get("props"):
            continue                                      # das Tier zielt auf ein Ding (Glas, Dampfblase, Feder): es schwimmt nicht davon weg
        acts = [a for a in (sc.get("actors") or []) if isinstance(a, dict)]
        crit = [a for a in acts if a.get("kind")]
        humans = [a for a in acts if not a.get("kind")]
        turn += 1
        if crit and not any(a.get("to") for a in crit) and turn % 2:          # Wesen bewegt sich durchs Bild
            a = crit[0]
            side = "left" if str(a.get("pos") or "center") in ("right", "rechts") or i % 2 else "right"
            a["pos"], a["to"] = side, ("right" if side == "left" else "left")
            a["action"] = "walk"
        elif len(humans) == 1 and not sc.get("props") and turn % 3 == 2 and not humans[0].get("to"):
            sc["shot"] = "close"                                               # Großaufnahme der Figur
        else:                                                                  # gespiegelt: Figuren und Dinge wechseln die Seite
            for a in acts:
                p = str(a.get("pos") or "")
                a["pos"] = {"left": "right", "right": "left", "links": "rechts", "rechts": "links"}.get(p, "left" if i % 2 else "right")
                a["facing"] = "left" if a["pos"] in ("right", "rechts") else "right"
            for p in sc.get("props") or []:
                if isinstance(p, dict) and isinstance(p.get("pos"), (int, float)):
                    p["pos"] = W - p["pos"]
        sc["cam_move"] = ("pan_l", "push", "pan_r", "pull")[turn % 4]


def _scene_punch(sc):
    """Wie viel passiert im Bild einer Szene? (Dinge, Tiere, Schwerelosigkeit, Ereignis-Einstellung, Wetter, starke Handlung)"""
    if not isinstance(sc, dict) or sc.get("shot") in ("graphic", "insert") or places.resolve(backdrop(sc)) in MAPS:
        return 0
    acts = [a for a in (sc.get("actors") or []) if isinstance(a, dict)]
    return (2 * min(3, len(sc.get("props") or [])) + 3 * any(a.get("kind") for a in acts) + 4 * bool(sc.get("float"))
            + 2 * (sc.get("shot") == "event") + bool(sc.get("weather"))
            + 2 * any(str(a.get("action") or "") in ("shocked", "scared", "run", "fall", "jump", "dance", "shake") for a in acts))


def _cold_open(scenes):
    """Vorgriff im ersten Bild: Zeigt der erste Satz nur Menschen, die dastehen, kommt dort schon das stärkste Bild der ersten zwei
    Drittel des Videos (die verrückteste Folge) – wer das sieht, will wissen, wie es dazu kommt. Der Satz bleibt, Schild und Ton auch."""
    import copy
    if len(scenes) < 4 or not isinstance(scenes[0], dict) or _scene_punch(scenes[0]) >= 3:
        return
    rp0 = places.resolve(backdrop(scenes[0])) if not isinstance(backdrop(scenes[0]), dict) else ""
    words0 = re.findall(r"[a-zäöüß]{4,}", str(scenes[0].get("text") or "").lower())
    if rp0 and rp0 not in GENERIC and any(places.ALIASES.get(f_) == rp0 or f_ == rp0 for w_ in words0 for f_ in (w_, w_[:-1], w_[:-2]) if f_ not in SAID_SKIP):
        return                                            # „Ich stand auf einer Beerdigung …“: der Satz nennt seinen Ort und spielt dort – kein Vorgriff aufs Wohnzimmer (Video 167)
    low0 = str(scenes[0].get("text") or "").lower()
    if clock_time(low0) or (re.search(r"nachttisch|\bbett\b|schlafzimmer|schläfst|schlafe\b|wach\w*\b", low0)
                             and any(isinstance(a, dict) and str(a.get("action") or "") == "sleep" for a in scenes[0].get("actors") or [])):
        return                                            # „Drei Uhr zwölf. Dein Handy vibriert auf dem Nachttisch.“: der Satz beschreibt genau diesen Augenblick – kein Vorgriff auf die Küche (Prüfung Video 192)
    g_first = graphics.clean(scenes[0].get("graphic")) if scenes[0].get("shot") == "graphic" else None
    if g_first and g_first.get("type") in ("radar", "news", "radio", "phone", "chart", "pulse"):
        return                                            # das erste Bild ist schon ein bewegtes Schaubild zum Satz (Radarschirm, Eilmeldung): kein fremdes Bild davor
    pool = [(i, _scene_punch(sc)) for i, sc in enumerate(scenes[2:max(3, len(scenes) * 2 // 3)], start=2)]
    pool = [x for x in pool if x[1] >= 4 and (x[1] >= 5 or scenes[x[0]].get("float") or scenes[x[0]].get("shot") == "event" or scenes[x[0]].get("weather")
                                              or any(isinstance(a, dict) and (a.get("kind") or str(a.get("action") or "") in ("fall", "run", "jump", "dance", "scared"))
                                                     for a in scenes[x[0]].get("actors") or []))]   # ein Alltagsding plus Kopfschütteln (Auto auf der Straße) ist kein „stärkstes Bild“ (Video 157)
    if not pool:
        return
    best = scenes[max(pool, key=lambda x: (x[1], -x[0]))[0]]
    sc0 = scenes[0]
    for k in ("place", "backdrop", "time", "weather", "float", "aloft", "low", "props", "crowd", "_sea", "_keep", "dark_city", "no_traffic"):
        if k in best:
            sc0[k] = copy.deepcopy(best[k])
        else:
            sc0.pop(k, None)
    sc0["actors"] = copy.deepcopy(best.get("actors") or [])
    sc0["shot"] = "" if best.get("shot") == "close" else best.get("shot", "")
    sc0["_cold_open"] = True


def _opening(scenes):
    """Das erste Bild packt: keine Grafik, keine Karte und kein leerer Ort – die Hauptfigur reagiert sichtbar (Gefühl passend zur
    Stimmung, Ausrufezeichen) und steht mittig. Der Schnitt mitten im Satz und der Kamera-Ruck zum Start erledigen den Rest."""
    sc = scenes[0] if scenes and isinstance(scenes[0], dict) else None
    if not sc or sc.get("shot") == "graphic" or places.resolve(backdrop(sc)) in MAPS or sc.get("float"):
        return
    acts = [a for a in (sc.get("actors") or []) if isinstance(a, dict)]
    humans = [a for a in acts if not a.get("kind")]
    if len(humans) == 1 and not humans[0].get("to") and str(humans[0].get("action") or "") in ("", "idle", "talk", "look_around"):
        h = humans[0]
        mood = str(sc.get("mood") or "")
        h["emotion"] = h.get("emotion") or {"scary": "scared", "panic": "scared", "tense": "worried", "sad": "sad"}.get(mood, "shocked")
        h["action"] = "shocked" if h["emotion"] in ("shocked", "scared") else "talk"
        h["emote"] = h.get("emote") or ("!" if h["emotion"] in ("shocked", "scared") else "")
        h["speaks"] = True


# Tageszeit und Wetter, die der Satz nennt („nachts“, „es regnet in Strömen“) – Tag/Nacht und Wetter müssen zum Satz passen
NIGHT_RE = (r"\bnachts\b|in der nacht|\bum mitternacht|mitten in der nacht|\babends\b|am abend|nachtaktiv|im dunkeln\b|bei nacht|heute nacht|"
            r"jede nacht|die ganze nacht|nächtlich|in dieser nacht|sternenhimmel|im mondlicht")
DAY_RE = r"\btagsüber\b|am morgen|\bmorgens\b|am tag\b|\bmittags\b|am nachmittag|bei tageslicht|sonnenaufgang|in der mittagssonne|bei sonnenschein"
COLD_RE = r"\bkälte\b|\b(?:dir|mir|ihm|ihr|uns|euch|ihnen) (?:ist|wird|war|wurde) (?:(?!nicht\b|kaum\b|nie\b|gar\b)\w+ ){0,2}kalt\b|\bes (?:ist|wird|war|wurde) (?:(?!nicht\b|kaum\b|nie\b|gar\b)\w+ ){0,2}kalt\b|eiskalt|eisig\w*|bitterkalt|klirrend\w* k[aä]lt|\bfrost\b|\bfrostig|minusgrade|\bfrierst\b|\bfrieren\b|\bfröstel"
WEATHER_RE = [(r"gewitter|blitz und donner|\bunwetter|\bsturm\b|stürme|orkan|sturmböen|hurrikan", "storm"),
              (r"\bregnet|\bregen\b|regenschauer|platzregen|wolkenbruch|in strömen|nieselregen|regentropfen", "rain"),
              (r"\bschneit|schneefall|schneesturm|schneeflocken", "snow"), (r"\bwindig|\bwind\b|böen|weht", "wind"),
              (COLD_RE, "cold"), (r"hitze|brütend heiß|\bheiß\b|hitzewelle|glühend heiß|sengende", "heat"), (r"asche regnet|ascheregen|aschewolke", "ash")]


SHIVER_RE = r"\bfrierst\b|\bfriert\b|\bfrieren\b|\bfröstel|bibber|zitter\w* vor kälte|vor kälte (?:\w+ ){0,2}zitter|\bkälte\b|eiskalt|eisig|bitterkalt|\bfrost\b|minusgrade"


NIGHT_WHY_RE = r"\bnacht|\babend|dunkel|finster|schlaf|schläf|\bbett\b|\btraum|träum|müde|mitternacht|\bmond|\bstern|gruse|unheimlich|spuk|\bgeist|einbrech|einbruch|stromausfall|kerze|lagerfeuer|\bwach\b|aufwach|wecker"


def _shiver(sc):
    """Die Menschen der Szene frieren (Arme um den Körper, bibbern) – nur wer gerade nichts anderes Bestimmtes tut."""
    for a in (sc.get("actors") or []):
        if isinstance(a, dict) and not a.get("kind") and not a.get("hold") and not a.get("to") \
                and str(a.get("action") or "").lower() in ("", "idle", "talk", "look_around", "think", "shocked", "scared", "shake", "walk"):
            a.update(action="shiver", emote="")
            if str(a.get("emotion") or "").lower() in ("", "happy", "calm"):
                a["emotion"] = "worried"


def _time_weather(scenes, topic="", style=""):
    """Nennt der Satz Nacht/Tag oder ein Wetter, stimmt das Bild: nachts wird es Nacht (drinnen mit Lichtkegel, draußen dunkelblau),
    Regen, Schnee, Sturm, Wind und Hitze sieht man – Wetter nur draußen (drinnen regnet es nicht). Verneintes zählt nicht."""
    import re as _re
    dark_n = [sc for sc in scenes if isinstance(sc, dict) and str(sc.get("time") or "") == "night"]
    all_n = " ".join(str(sc.get("text") or "") for sc in scenes if isinstance(sc, dict)).lower() + " " + str(topic or "").lower()
    if len(dark_n) * 2 > len(scenes) and str(style or "").lower() not in ("grusel", "mysterien", "horror", "nachricht") and not _re.search(NIGHT_RE + "|" + NIGHT_WHY_RE, all_n):
        for sc in dark_n:                                 # die Text-KI legt das ganze Video in die Nacht, obwohl kein Satz von Nacht, Schlaf oder Dunkelheit spricht: bei Tag (ein fröhliches Thema im Halbdunkel wirkt düster)
            sc["time"] = "day"
    for sc in scenes:
        if not isinstance(sc, dict) or sc.get("shot") == "graphic":
            continue
        low = str(sc.get("text") or "").lower()
        rp = places.resolve(backdrop(sc)) if not isinstance(backdrop(sc), dict) else "custom"
        if rp in MAPS or rp in ("space", "underwater", "cave"):
            continue
        if _re.search(NIGHT_RE, low) and not _re.search(DAY_RE, low):
            sc["time"] = "night"
        elif _re.search(DAY_RE, low) and sc.get("time") == "night" and not _re.search(NIGHT_RE, low):
            sc["time"] = "day"
        outdoor = rp in places.OUTDOOR or rp == "custom"
        if outdoor and str(sc.get("weather") or "") in ("snow", "cold") and _re.search(SHIVER_RE, low) and not _re.search(r"(?:kein\w*|nicht|ohne|nie)\s+(?:\w+\s+){0,2}(?:kälte|frost|frier)", low):
            _shiver(sc)                                   # es schneit und der Satz spricht von Kälte: die Figur friert
        if outdoor and not sc.get("weather"):
            for pat, w in WEATHER_RE:
                m = _re.search(pat, low)
                if m and not _re.search(r"(?:kein\w*|nicht|ohne|nie)\s+(?:\w+\s+){0,2}" + _re.escape(m.group(0)), low) \
                        and not _re.search(_re.escape(m.group(0)) + r"\w*\s+(?:\w+\s+)?(?:nicht|mehr)\b", low):
                    sc["weather"] = w
                    if w == "cold":                        # Kälte: wer draußen steht, friert sichtbar (rig „shiver“) – das Tier schaut ängstlich
                        _shiver(sc)
                    if w in ("rain", "storm"):             # bei Regen und Sturm ist der Himmel grau, nicht strahlend blau
                        spec = places.spec_of(backdrop(sc)) or {}
                        if spec and not spec.get("sky"):
                            sc["backdrop"] = dict(spec, sky="storm")
                    break


# Erklär-Einblendungen aus dem Satz (wie in den Vorbild-Shorts: Thermometer, Füllstand, Speisekarte, Stempel)
STAMPS = [(r"\bverboten|nicht erlaubt|\billegal|strafbar|untersagt", "VERBOTEN", "red"), (r"lebensgefährlich|\btödlich", "TÖDLICH", "red"),
          (r"(?<!un)giftig", "GIFTIG", "purple"), (r"(?<!un)gefährlich|\bgefahr\b", "GEFAHR", "orange"), (r"\bgratis|kostenlos|umsonst\b", "GRATIS", "green"),
          (r"\berlaubt\b|\blegal\b", "ERLAUBT", "green"), (r"ausverkauft|leergekauft", "AUSVERKAUFT", "red"), (r"\bpleite|bankrott|insolvent", "PLEITE", "red"),
          (r"streng geheim|\bgeheim\b", "GEHEIM", "red"), (r"\bfake\b|\bgefälscht", "FAKE", "red"), (r"\brekord", "REKORD", "green")]
LIST_TITLES = [(r"\bfr[ie]?ss|\bfraß|\bfressen|\bisst\b|\bessen\b|\baß\b|\bernähr", "SPEISEKARTE"), (r"einpack|mitnehm|\bpack|vorrat|kaufen|besorg", "CHECKLISTE")]
_NOUN = r"(?:[a-zäöüß]+\s+)?[A-ZÄÖÜ][a-zäöüß-]{2,}"
LIST_RE = r"(" + _NOUN + r"(?:,\s+" + _NOUN + r")+,?\s+(?:und|oder|sowie)\s+" + _NOUN + r")"
BAR_STOP = {"Prozent", "Jahr", "Jahre", "Jahren", "Tag", "Tage", "Woche", "Monat", "Stunde", "Stunden", "Minute", "Minuten", "Mal", "Ende", "Anfang"}


def _list_items(text):
    """„… fressen Käfer, Maulwurfsgrillen und schädliche Insekten“ → ["Käfer", "Maulwurfsgrillen", "Insekten"] (ab drei Dingen)."""
    import re as _re
    m = _re.search(LIST_RE, str(text or ""))
    if not m:
        return []
    items = _re.findall(r"[A-ZÄÖÜ][a-zäöüß-]{2,}", m.group(1))
    items = [w[:-1] if _re.search(r"[^aeiouäöü]ern$", w) else w for w in items]       # Dativ-Plural: „Käfern“ → „Käfer“ („Kugeln“ bleibt)
    return items if 3 <= len(items) <= 5 and all(len(w) <= 18 for w in items) else []


def _bar_label(text, number_word):
    """Wovon der Prozentwert handelt: das Hauptwort vor der Zahl („Der Akku hat noch elf Prozent“ → AKKU), sonst None."""
    import re as _re
    words = str(text or "").split()
    pos = next((k for k, w in enumerate(words) if w.lower().strip(".,;:!?") == number_word.lower()), None)
    if pos is None:
        return None
    clean = [w.strip(".,;:!?„“\"") for w in words[1:pos]]
    nouns = [w for w in clean if _re.match(r"^[A-ZÄÖÜ][a-zäöüß-]{2,}$", w) and w not in BAR_STOP]
    return nouns[-1].upper()[:16] if nouns else None


QUOTE_RE = (r"\b(experten|expertinnen|forscher\w*|wissenschaftler\w*|ärzte|ärztinnen|mediziner\w*|biologen|biologinnen|ingenieure|"
            r"studien|eine studie|die studie|psychologen|polizei|feuerwehr|behörden|meteorologen|astronomen|ökonomen|fachleute)\s+"
            r"(sagen|sagt|warnen|warnt|meinen|meint|erklären|erklärt|betonen|raten|rät|empfehlen|empfiehlt|zeigen|zeigt|schätzen|vermuten|glauben)"
            r"\b[:,]?\s*(.{8,})$")


def _quote_for(text):
    """„Forscher warnen, dass es schlimmer wird.“ → Zitat-Karte {title: FORSCHER WARNEN, text: …} (nur Rolle, nie ein Name) oder None."""
    import re as _re
    m = _re.search(QUOTE_RE, str(text or "").strip(), _re.I)
    if not m:
        return None
    who = m.group(1).upper().replace("EINE ", "").replace("DIE ", "")
    body = m.group(3).strip().rstrip(".!") + "."
    body = body if body[0].isupper() else "…" + body            # Nebensatz („dass es …“) bleibt vollständig, mit Auslassung davor
    return {"type": "quote", "title": f"{who} {m.group(2).upper()}"[:26], "text": body}


REFUTED_RE = r"[^.!?]*\?\s*(?:falsch|nein\b|irrtum|von wegen|stimmt nicht|im gegenteil|weit gefehlt|keineswegs)"


def refuted(stem, low):
    """„Du denkst, das war verboten? Falsch, …“: Das Wort fällt nur in einer Frage, die der Satz gleich verneint – ein Stempel „VERBOTEN“
    behauptet dann das Gegenteil dessen, was erzählt wird (Prüfung 18.11.2026, Video 143)."""
    import re as _re
    return bool(stem) and bool(_re.search(_re.escape(stem) + REFUTED_RE, low))


def _stamp_for(low, prev=""):
    """Passender Stempel für den Satz (nicht verneint, nicht derselbe wie eben) → (Wort, Farbe) oder None."""
    import re as _re
    for pat, word, col in STAMPS:
        m = _re.search(pat, low)
        if m and not _re.search(r"(?:nicht|kein\w*|nie)\s+(?:\w+\s+)?" + _re.escape(m.group(0)), low) and word != prev and not refuted(m.group(0), low):
            return word, col
    return None


def _gauge_for(sc):
    """Würde `_auto_explain` für diesen Satz ein Thermometer oder einen Füllstand über die Szene legen? Probelauf an einer Kopie."""
    probe = {k: v for k, v in sc.items() if k not in ("graphic",)}
    probe["shot"] = ""
    if isinstance(probe.get("overlay"), dict) and probe["overlay"].get("type") != "counter":
        return False
    _auto_explain([probe])
    return isinstance(probe.get("overlay"), dict) and probe["overlay"].get("type") in ("thermo", "bar")


def _auto_explain(scenes):
    """Ohne Einblendung im Drehbuch erklärt ein einfaches Bild den Satz: Aufzählung → Liste mit Haken (bei Fressen „Speisekarte“),
    Temperatur → Thermometer, Prozent mit Bezug → Füllstand, Signalwort → Stempel. Aus einem nackten Grad- oder Prozent-Zähler wird
    ebenfalls Thermometer bzw. Füllstand. Nicht in Grafik-Szenen und Einschüben, derselbe Stempel nie zweimal hintereinander."""
    import re as _re
    prev_stamp = ""
    for sc in scenes:
        if not isinstance(sc, dict):
            prev_stamp = ""
            continue
        g = sc.get("graphic") if isinstance(sc.get("graphic"), dict) else {}
        if sc.get("shot") == "graphic" and g.get("type") == "number" and (str(g.get("label") or "").upper() == "GRAD" or "%" in str(g.get("value") or "")) \
                and (sc.get("actors") or sc.get("props") or sc.get("place")):
            g_keep, ov_keep = sc.get("graphic"), sc.get("overlay")
            sc["shot"], sc["graphic"] = "", None           # Temperatur/Anteil: lieber Thermometer bzw. Füllstand über der Szene als eine nackte Zahl
            if not _gauge_for(sc):                         # „Über neunzig Prozent aller Smartphone-Nutzer“: daraus wird kein Füllstand – dann bleibt die große Zahl, statt dass die Figur bloß redet (Video 209)
                sc["shot"], sc["graphic"] = "graphic", g_keep
            sc["overlay"] = ov_keep
        if sc.get("shot") == "graphic" or (sc.get("shot") == "insert" and not _stamp_for(str(sc.get("text") or "").lower(), prev_stamp)):
            prev_stamp = ""
            continue
        txt = str(sc.get("text") or "")
        low = txt.lower()
        ov = sc.get("overlay") if isinstance(sc.get("overlay"), dict) else None
        if sc.get("shot") == "insert":                     # Großaufnahme eines Dings: höchstens ein Stempel darüber („AUSVERKAUFT“)
            if not ov:
                word, col = _stamp_for(low, prev_stamp)
                sc["overlay"] = {"type": "stamp", "text": word, "color": col}
                prev_stamp = word
            continue
        fig = ov if ov and ov.get("type") == "counter" else (None if ov else find_figure(txt))
        if fig and fig.get("unit") in ("GRAD", "%"):
            try:
                v = float(fig.get("value") or 0)
            except (TypeError, ValueError):
                v = None
            if v is not None and fig["unit"] == "GRAD" and -90 <= v <= 120 \
                    and not _re.search(r"grad (?:celsius )?(?:mehr|wärmer|kälter|weniger)|grad (?:steig|sink|fäll)|\bum (?:\w+ ){1,3}grad", low):
                if _re.search(r"minus\s+\S+\s+grad|-\s?\d+\s*grad|unter null", low):
                    v = -abs(v)
                sc["overlay"] = {"type": "thermo", "value": v}
                prev_stamp = ""
                continue
            if v is not None and fig["unit"] == "%" and 0 <= v <= 100:
                word = next((w for w in txt.split() if _number(w) == v), "")
                label = _bar_label(txt, word.strip(".,;:!?")) if word else None
                if label:
                    sc["overlay"] = {"type": "bar", "label": label, "value": v}
                    prev_stamp = ""
                    continue
        if ov:
            prev_stamp = ""
            continue
        q = _quote_for(txt)
        if q:
            sc["overlay"] = q
            prev_stamp = ""
            continue
        items = _list_items(txt)
        _cnt = r"(?:zwei|drei|vier|fünf|sechs|sieben|acht|neun|zehn|elf|zwölf|\d+)"
        if items and not any(_re.search(pat, low) for pat, _tt in LIST_TITLES) and (_re.search(_cnt + r" \w+ und " + _cnt + r" \w+", low) or _re.search(FAMILY_RE, low)):
            items = None                                  # „vier Erwachsene und vier Kinder“ nennt Mengen, keine Punkte zum Abhaken
        if items:
            title = next((tt for pat, tt in LIST_TITLES if _re.search(pat, low)), "LISTE")
            sc["overlay"] = {"type": "checklist", "title": title, "items": [[w, True] for w in items]}
            prev_stamp = ""
            continue
        st = _stamp_for(low, prev_stamp)
        if st:
            sc["overlay"] = {"type": "stamp", "text": st[0], "color": st[1]}
            prev_stamp = st[0]
        else:
            prev_stamp = ""


_MONTHS = "januar|februar|märz|april|mai|juni|juli|august|september|oktober|november|dezember"
TAG_RE = (r"(\b\d{1,2}\.\s?(?:" + _MONTHS + r")(?:\s(?:1[5-9]|20)\d{2})?\b"            # „24. Dezember 1914“
          r"|\b(?:" + _MONTHS + r")\s(?:1[5-9]|20)\d{2}\b"                                # „August 1914“
          r"|\b(?:heiligabend|silvester|neujahr|mitternacht|weihnachten|ostern)\b"
          r"|\b(?:1[5-9]|20)\d{2}\b(?=\s*(?:$|[.,!?;:]|\s[a-zäöüß])))")                   # Jahreszahl, nicht „1500 Menschen“


TERM_RE = (r"(?:nennt (?:sich|man)(?: das| dies| es)?|sogenannten?|sogenannte[rs]?|fachbegriff (?:dafür )?(?:ist|lautet)|phänomen heißt|effekt heißt)\s+"
           r"(?:(?:der|die|das|den|dem|einen|eine|ein)\s+)?(?:sogenannte[nrs]?\s+)?"
           r"((?:[a-zäöüß]{4,}(?:e|er|es|en|em)\s)?[A-ZÄÖÜ][a-zäöüß]{2,}(?:-[A-ZÄÖÜa-zäöü][a-zäöüß]+)*)")


def _term(text):
    """Fachbegriff, den der Satz einführt („Das nennt sich Türrahmen-Effekt“, „der sogenannte Mandela-Effekt“) – oder None."""
    import re as _re
    m = _re.search(TERM_RE, str(text or ""))
    term = m.group(1).strip() if m else ""
    return term.upper() if 6 <= len(term) <= 30 and ("-" in term or " " in term or len(term) >= 10) else None


_CENTURY = {"fünfzehn": 15, "sechzehn": 16, "siebzehn": 17, "achtzehn": 18, "neunzehn": 19}


def year_digits(text):
    """„FRÜHJAHR NEUNZEHNHUNDERTFÜNFUNDVIERZIG“ → „FRÜHJAHR 1945“: ausgeschriebene Jahreszahlen passen auf kein Schild."""
    import re as _re
    def rep(m):
        rest = m.group(2).lower()
        n = 0 if not rest else _number(rest)
        if n is None or not 0 <= n < 100:
            return m.group(0)
        return str(_CENTURY[m.group(1).lower()] * 100 + int(n))
    out = _re.sub(r"(?i)\b(" + "|".join(_CENTURY) + r")hundert([a-zäöüß]*)\b", rep, str(text))
    def rep2(m):
        rest = m.group(1).lower()
        n = 0 if not rest else _number(rest)
        return m.group(0) if n is None or not 0 <= n < 100 else str(2000 + int(n))
    return _re.sub(r"(?i)\bzweitausend(?:und)?([a-zäöüß]*)\b(?=\s*(?:$|[.,!?;:·]))", rep2, out)


def _auto_tags(scenes):
    """Beschriftungs-Schild wie in den Vorbild-Shorts: nennt der Satz ein Datum, eine Jahreszahl oder einen Anlass, steht es als kleines
    Etikett oben im Bild – nur ohne andere Einblendung, nie in zwei Szenen hintereinander und nicht in Grafik-Szenen."""
    import re as _re
    prev = False
    for sc in scenes:
        if not isinstance(sc, dict):
            prev = False
            continue
        has = isinstance(sc.get("overlay"), dict) and sc["overlay"].get("type")
        if not has and not prev and sc.get("shot") not in ("graphic", "insert") and isinstance(sc.get("text"), str):
            m = _re.search(TAG_RE, sc["text"], _re.I)
            if m:
                sc["overlay"] = {"type": "tag", "text": m.group(1).upper()}
                prev = True
                continue
            term = _term(sc["text"])                       # der Fachbegriff, den der Satz einführt, steht zum Mitlesen im Bild
            if term and not any(isinstance(o, dict) and isinstance(o.get("overlay"), dict)
                                and term in str(o["overlay"].get("text") or "").upper() for o in scenes):
                sc["overlay"] = {"type": "tag", "text": term}
                prev = True
                continue
        prev = bool(has and str(sc["overlay"].get("type")) == "tag")


def backdrop(scene):
    """Was als Hintergrund gezeichnet wird: Baukasten-Landschaft (backdrop) oder ein fester Ort."""
    b = scene.get("backdrop")
    if isinstance(b, dict) and (b.get("elements") or b.get("ground") or b.get("sky")):
        return b
    return scene.get("place")


# Wörter im Sprechertext → passender Hintergrund (greift nur, wenn das Drehbuch einen unpassenden Allerwelts-Ort nennt)
HARBOR_RE = r"\bhafen(?!t)|\bhäfen|hafenbecken|hafenstadt|containerterminal|containerhafen|\bkai\b|kaimauer|\bwerft"    # „Hafen“, nicht „haften“
HINTS = [
    (r"kontrollraum|kontrollräum|kontrollzentr|leitwarte|leitstand|leitstelle|bodenstation|flugleitung|missionskontrolle|mission control|bodenkontrolle", "controlroom"),
    (r"rechenzentr|serverfarm|serverraum|serverräume|\bserver\b|\bservern\b|rechenleistung|rechenpower|ki-modell|supercomputer|datenzentr|des (gesamten |ganzen )?internets|datenström", "serverroom"),
    (r"konzern|firmenzentrale|hauptsitz|hauptquartier|firmensitz|tech-gigant|tech-riese|techriese|wolkenkratzer|weltfirma|weltmarktführer|milliardenfirma|billionenfirma", "headquarters"),
    (r"leergekauft|leere regale|leeren regale|regale sind leer|regale leer|hamsterk|ausverkauft|geplündert", "supermarket_empty"),
    (r"vorräte.{0,30}(neige|knapp|leer|aus)|lebensmittel.{0,30}(knapp|leer|aus)|nichts mehr zu kaufen", "supermarket_empty"),
    (r"supermarkt|supermärkte|einkaufen|einkauf\b|lebensmittelladen|geschäfte|\bläden", "supermarket"),
    (r"tankstelle|zapfsäule|tanken|benzin", "gasstation"),
    (r"kraftwerk|atomkraft|reaktor|stromnetz", "powerplant"),
    (r"strommast|stromleitung|hochspannung", {"elements": ["powerlines", "hills"]}),
    (r"windrad|windräder|windkraft", {"elements": ["windturbines", "fields"]}),
    (r"\bim (?:\w+ )?(?:bus|linienbus|abteil|waggon)\b|in (?:der|einer|deiner) (?:\w+ )?(?:bahn|straßenbahn|tram|u-bahn|s-bahn)\b|fahrgäste|fahrgast|mitfahrer", "transit"),   # im Fahrzeug, nicht am Bahnsteig
    (r"bahnhof|\bzug\b|\bzüge|u-bahn|s-bahn|bahnsteig", "station"),
    (HARBOR_RE, "harbor"),
    (r"friedhof|\bgrab\b|gräber", "graveyard"),
    (r"restaurant|café|kellner|\bdiner\b|burgerladen|imbiss|kneipe|pizzeria|gaststätte", "restaurant"),
    (r"badezimmer|dusche|badewanne|toilette|wasserhahn|leitungswasser", "bathroom"),
    (r"brücke", {"elements": ["bridge", "river", "city"]}),
    (r"\bzelt|camping|flüchtlingslager|notunterk", "camp"),
    (r"bauernhof|\bstall\b|\bkühe|\bvieh", "farm"),
    (r"mondoberfläche|auf dem mond|mondlandung", "moon"),
    (r"wasserwerk|klärwerk|talsperre|staudamm|wasserversorgung|wasserspeicher", {"elements": ["factory", "river", "hills"]}),
    (r"feuerwehr|löschen|\bbrände", "street"),
    (r"esszimmer|esstisch|festtafel|familientisch|weihnachtsessen|festessen|festtagsessen|am (?:gedeckten |festlich gedeckten |langen )?(?:ess|fest|familien)?tisch\b", "diningroom"),
    (r"\bflur\b|korridor|(?:im|durch den|auf dem|über den|den) gang\b|treppenhaus|hotel|vor der tür|an der tür|türklinke|klopft|zimmernummer", "hallway"),
    (r"dachboden|(?<![a-zäöüß])speicher\b", "attic"),
    (r"\bbett\b|schlafzimmer|wachst auf|aufwach|einschlaf|schläfst|decke über|schlafen (zu )?(lassen|gehen|legen)|weckt (er |es |sie |das )?(dich|mich)|(dich|mich) (auf)?weck", "bedroom"),
    (r"(?<![a-zäöüß])spiegel(?!bild| (?:im|in|des|der|an|steigt|sinkt|fällt))|badezimmerspiegel|waschbecken", "bathroom"),
    (r"\bkeller|kellertreppe|bunker", "basement"),
    (r"kirche|\bdom\b|kathedrale", "church"),
    (r"müllhalde|müllberg|deponie|\bmüll\b", "landfill"),
    (r"regenwald|dschungel|\bwald|wälder|bäume", {"elements": ["forest"]}),
    (r"ausgetrocknet|dürre|vertrocknet|trocknen aus|staubtrocken", {"ground": "dry", "sky": "haze", "elements": ["deadtrees", "dryriver"]}),
    (r"\bfluss|flüsse|\bbach|strom fließt", {"elements": ["hills", "river"]}),
    (r"\bsee\b|\bseen\b|teich", {"elements": ["hills", "lake"]}),
    (r"\bernte|missernte|weinernte|landwirt|bauern|\bfeld|felder|\backer|getreide", {"elements": ["farm", "fields"]}),   # „ernte“ nur am Wortanfang: „Gelernte Vokabeln“ spielte auf dem Bauernhof
    (r"\bgarten|gärten|\bwiese|\brasen\b|käfer|insekten|maulwurf|regenwurm|schnecken", "park"),
    (r"gletscher|eiszeit|arktis|antarktis|polkappe|\beis\b", {"ground": "snow", "elements": ["glacier", "mountains"]}),
    (r"\bschnee|\bwinter", "snow"),
    (r"\bmeer|ozean|küste|strand|meereswelle|brandung|\bwellen? (?:schlagen|schlägt|rauschen|rauscht|brechen|bricht|rollen|rollt)", "beach"),   # ein bloßes „die Welle läuft von oben nach unten“ (Schreckreflex) ist kein Strand
    (r"tiefsee|unter wasser|meeresgrund|meeresboden|korallen|\bfisch|unter der oberfläche|im wasser leb|\btauch(?!\w* (?:[\wäöüß-]+ ){0,12}auf\b(?! (?:de[nmr]|die|das|eine[nmr]?|ihre[nm]?|seine[nm]?)\b))|taucher", "underwater"),   # „Plötzlich tauchen Dinge auf, von denen du erzählt hast“ (Video 190: zwei Goldfische im Liebes-Video) – auftauchen ist kein Tauchgang
    (r"wüste|sahara|sanddüne", "desert"),
    (r"vulkan|gebirge|\bberg|gipfel", "mountain"),
    (r"weltall|weltraum|galaxie|planet|umlaufbahn|astronaut|\bmond\b|sonnensystem|satellit", "space"),
    (r"(?<![a-zäöüß])höhle|tropfstein", "cave"),
    (r"\bkino|kinosaal|leinwand|hollywood|blockbuster|\bfilme?\b|\bfilmen\b|filmszene|regisseur|kinofilm", "cinema"),
    (r"fabrik|industrie|abgase|produktion", {"sky": "haze", "elements": ["factory", "city"]}),
    (r"\bdorf|dörfer", "village"),
    (r"asphalt|fahrbahn|straßenbelag|straßendecke|\bteer\b|straßen? (reiß|brech|bricht|platz)|reißen .{0,40}straßen", {"ground": "road", "elements": ["street", "asphalt"]}),
    (r"ruinen|zerstört|trümmer|apokalypse", "ruins"),
    (r"\bstadt|städte|straße|verkehr|hochhaus|hochhäuser", "street"),
    (r"krankenh[aä]us|\barzt|ärzte|klinik|notaufnahme", "hospital"),
    (r"\bschule|unterricht|klasse", "classroom"),
    (r"\blabor|forscher|wissenschaftler|experiment", "lab"),
    (r"\bbüro|(?<!vor der )(?<!nach der )(?<!während der )\barbeit\b|\bchef", "office"),   # „Motivation kommt nie vor der Arbeit“ ist eine Zeitangabe, kein Büro (Plan 26.11.2026)
    (r"küche|kochen|kühlschrank", "kitchen"),
]
GENERIC = ("street", "park", "plain", "livingroom")
_CTX = {"mem": False}     # setzt direct(): Das ganze Video handelt von Computerspeicher – „freie Stellen im Speicher“ ist dann nie der Dachboden (Video 178)
MEM_TOPIC_RE = r"speicherchip|hauptspeicher|arbeitsspeicher|bordspeicher|datenspeicher|bordcomputer|programmcode|kilobyte|megabyte|gigabyte|raumsonde"
COMPUTER_MEM_RE = (r"hauptspeicher|bordspeicher|bordcomputer|arbeitsspeicher|datenspeicher|speicherchip|speicherplatz|speicherkarte|\bchips?\b|computer|\bcode\b|programm|software|\bdaten\b|"
                   r"\bsonde\b|raumsonde|rechner|megabyte|gigabyte|kilobyte|\bbytes?\b|festplatte|handy|smartphone|\bbits?\b|prozessor|\bserver")
JUNK_TALK_RE = (r"datenmüll|müll (?:send|funk|red|erzähl|laber|schreib|von sich)|(?:send\w*|funk\w*|red\w*|erzähl\w*|laber\w*|schreib\w*) (?:\w+ ){0,4}müll|"
                r"(?:unverständlich\w*|wirr\w*|digital\w*|sinnlos\w*) müll|müll (?:aus dem (?:all|weltall|weltraum))")
PROBE_RE = r"raumsonde|weltraumsonde|voyager"
SPACE_RE = (r"weltall|weltraum|\balls?\b|raumsonde|weltraumsonde|voyager|interstellar|galaxi|planet|umlaufbahn|orbit|astronaut|\bmond|sonnensystem|\bstern|satellit|rakete|raumschiff|raumstation|\biss\b|"
            r"kosmos|universum|schwarze\w* l[oö]ch|\berde\b|\bsonne\b|meteor|asteroid|komet|außerirdisch|(?<![a-zäöüß])aliens?\b|\bufo|raumfahrt|schwerelos|mars\b|jupiter|saturn|milchstraße")
GROUP_RE = (r"\b(zwei|drei|vier|fünf) (?:\w+ )?(gründer\w*|freund\w*|forscher\w*|wissenschaftler\w*|student\w*|brüder\w*|schwestern|kolleg\w*|ingenieur\w*|"
            r"entwickler\w*|tüftler\w*|erfinder\w*|männer\w*|frauen|jungs|kumpel\w*|nerds|programmierer\w*|unternehmer\w*|geschwister\w*|typen|partner\w*|"
            r"schüler\w*|mitarbeiter\w*|expert\w*|bastler\w*|teenager\w*|jugendliche\w*)\b")
GROUP_LOOKS = ({"shirt": "rot", "hair": "ponytail", "hair_color": "blond"}, {"shirt": "orange", "hat": "cap"}, {"shirt": "lila", "hair": "long"},
               {"shirt": "türkis", "glasses": True}, {"shirt": "gelb", "hair": "curly", "hair_color": "schwarz", "skin": "dunkel"}, {"shirt": "grün", "hair": "bob", "hair_color": "rot"})
FEM_LOOKS = ({"shirt": "lila", "hair": "ponytail", "hair_color": "blond", "gender": "w"}, {"shirt": "pink", "hair": "long", "hair_color": "braun", "gender": "w"},
             {"shirt": "grün", "hair": "bob", "hair_color": "rot", "gender": "w"}, {"shirt": "türkis", "hair": "curly", "skin": "dunkel", "gender": "w"},
             {"shirt": "gelb", "hair": "long", "hair_color": "schwarz", "skin": "mittel", "gender": "w"})


def balance_cast(cast, seed=0, scenes=None):
    """Mehr Frauen im Bild: Ist die Hauptfigur „du“ (der Zuschauer selbst) ohne Frauen in der Besetzung, wird sie bei jedem zweiten
    Video eine Frau. Benannte Figuren („Tom“) und „ich“ (die Stimme erzählt selbst) bleiben, wie das Drehbuch sie meint;
    Nebenfiguren ohne Besetzung sind über GROUP_LOOKS ohnehin gemischt."""
    if not isinstance(cast, dict) or seed % 2:
        return cast
    me = sum(1 for sc in (scenes or []) if isinstance(sc, dict) and re.search(r"\b(ich|mein\w*|mir|mich)\b", str(sc.get("text") or "").lower()))
    if scenes and me >= max(3, len(scenes) // 3):         # Ich-Geschichte: die Figur IST die erzählende Stimme – sie bleibt, wie das Drehbuch sie besetzt hat
        return cast
    humans = [k for k, v in cast.items() if isinstance(v, dict) and not v.get("kind")]
    if any(rig.Look.from_spec(cast[k]).fem for k in humans) or "du" not in humans:
        return cast
    look = FEM_LOOKS[(seed // 2) % len(FEM_LOOKS)]
    cast["du"] = {**{k: v for k, v in cast["du"].items() if k in ("glasses", "size")}, **look}
    return cast


# Figuren, die das Drehbuch beim Vornamen nennt, aber nicht besetzt („murat“, „sandra“ ohne Eintrag in "cast" – Video 213: beide im selben
# blauen Pulli mit braunem Kurzhaar, die Filialleiterin Sandra als Mann): jede bekommt ihr eigenes Aussehen, Frauen sehen aus wie Frauen.
FEM_NAMES = set("""anna lena lea mia emma sophie sofia sophia marie maria laura julia lisa sarah sara hannah hanna leonie lina emily emilia clara klara
nina paula johanna charlotte lotte luisa louisa amelie mila ella ida frieda greta marta martha helga inge ingrid ursula uschi renate monika petra sabine
susanne sandra andrea claudia nicole stefanie steffi katrin kathrin karin birgit heike silke anja tanja katja nadine melanie jessica jenny jana
franziska vanessa michelle kim eva ute gisela erika christa elke gabi gabriele brigitte angelika martina kerstin simone daniela christina christine tina
bettina yvonne ines iris doris antje maren svenja carina karina miriam mirjam judith ruth esther elif ayse aylin fatma zeynep leyla emine selin olga
natascha elena irina svetlana oma mama tante schwester mutter chefin""".split())
MALE_NAMES = set("""max paul ben jonas leon finn felix lukas luca noah elias tim tom jan lars sven nils ole moritz david daniel michael thomas andreas stefan
stephan peter klaus hans karl otto fritz heinz kurt uwe jürgen dieter wolfgang bernd frank ralf rolf markus marcus martin matthias christian tobias
sebastian florian alexander alex philipp patrick dennis kevin marcel marco mario murat ali mehmet mustafa emre can cem deniz yusuf ahmet hasan ibrahim
omar jonathan julian niklas nico simon fabian robin erik eric oskar oscar emil anton theo jakob jacob henry henri karim sergej igor dimitri piotr
opa papa onkel bruder vater chef joshua jona mika elia""".split())
MALE_LOOKS = ({"shirt": "grün", "hair_color": "schwarz", "gender": "m"}, {"shirt": "rot", "hair_color": "dunkelbraun", "gender": "m"},
              {"shirt": "orange", "hair_color": "blond", "gender": "m"}, {"shirt": "türkis", "hair_color": "braun", "glasses": True, "gender": "m"},
              {"shirt": "grau", "hair_color": "rot", "gender": "m"}, {"shirt": "gelb", "hair_color": "schwarz", "skin": "mittel", "gender": "m"})


def name_cast(cast, scenes):
    """Vornamen im Bildplan ohne Besetzung bekommen ein eigenes Aussehen: Frauennamen (Liste, „Filialleiterin Sandra“, „Frau …“) eine
    Frauenfigur, Männernamen eine Männerfigur – keine zwei im selben Pulli, keiner im Pulli der Hauptfigur. Tiere, Rollen und Wesen
    („vogel“, „gehirn“, „forscher“) bleiben, wie die Regie sie ohnehin behandelt."""
    if not isinstance(cast, dict):
        return cast
    text_n = " ".join(str(sc.get("text") or "") for sc in (scenes or []) if isinstance(sc, dict))
    ids_n = []
    for sc in (scenes or []):
        for a in ((sc.get("actors") or []) if isinstance(sc, dict) else []):
            aid = str(a.get("id") or "").strip() if isinstance(a, dict) else ""
            if aid and aid not in ids_n and not a.get("kind") and not isinstance(a.get("look"), dict):
                ids_n.append(aid)
    used_n = {str(v.get("shirt") or "blau").lower() for v in cast.values() if isinstance(v, dict) and not v.get("kind")}
    for aid in ids_n:
        low_n = aid.lower()
        if isinstance(cast.get(aid), dict) and cast[aid] and not cast[aid].get("kind") and low_n in FEM_NAMES and low_n not in MAIN_IDS \
                and not str(cast[aid].get("gender") or "").strip() and str(cast[aid].get("hair") or "").lower() not in rig.FEM_HAIR:
            cast[aid] = dict(cast[aid], gender="w", hair="bob")   # besetzt, aber ohne Frisur und Geschlecht: „Sandra“ ist trotzdem eine Frau
        if low_n in MAIN_IDS or (isinstance(cast.get(aid), dict) and cast[aid]) or not re.fullmatch(r"[a-zäöüß]{2,14}", low_n):
            continue
        fem_n = low_n in FEM_NAMES or bool(re.search(r"(?i)\b(?:frau|\w{4,}in)\s+" + re.escape(aid) + r"\b", text_n))
        if not fem_n and low_n not in MALE_NAMES:
            continue                                      # kein bekannter Vorname: Rolle, Tier oder Wesen – nichts erfinden
        pool_n = FEM_LOOKS if fem_n else MALE_LOOKS
        start_n = sum(map(ord, low_n)) % len(pool_n)
        look_n = next((pool_n[(start_n + j) % len(pool_n)] for j in range(len(pool_n)) if pool_n[(start_n + j) % len(pool_n)]["shirt"] not in used_n), pool_n[start_n])
        cast[aid] = dict(look_n)
        used_n.add(look_n["shirt"])
    return cast


# Sätze über Kurse, Umsatz, Marktwert → Kurve als bewegte Grafik (steigt oder stürzt ab)
CHART_RE = (r"aktienkurs|börsenkurs|börsenwert|marktwert|börsengang|aktie\w*\b.{0,50}(steig|stieg|explod|schieß|schoss|kletter|verdoppel|verzehnfach|fiel|fällt|stürz|brach|bricht|crash|rakete|durch die decke)|"
            r"\bkurs\w*\b.{0,30}(steig|stieg|explod|schieß|schoss|fällt|fiel|stürz|brach|bricht|durch die decke)|"
            r"(umsatz|umsätze|gewinn|gewinne|verkaufszahlen|nutzerzahlen|nachfrage|bedarf)\b.{0,40}(steig|stieg|explod|wächst|wuchs|verdoppel|verzehnfach|schieß|schoss|bricht|brach|stürz|durch die decke)|"
            r"(explodier|steig|stieg|schieß|schoss|wächst|wuchs)\w*\b.{0,30}(aktienkurs|\bkurs\b|aktie|umsatz|umsätze|gewinn|verkaufszahlen|nutzerzahlen|nachfrage|bedarf|marktwert)")
CHART_DOWN_RE = r"fällt|fiel|stürz|brach\b|bricht|crash|einbr|\bsinkt|\bsank|halbier|verlier|verlor|in den keller|abwärts"
CHART_KICKERS = ((r"aktie|börsenkurs|\bkurs", "AKTIENKURS"), (r"marktwert|börsenwert", "MARKTWERT"), (r"umsatz|umsätze", "UMSATZ"), (r"gewinn", "GEWINN"),
                 (r"verkaufszahlen", "VERKÄUFE"), (r"nutzerzahlen", "NUTZER"), (r"nachfrage", "NACHFRAGE"), (r"bedarf", "BEDARF"), (r"börsengang", "BÖRSE"))
# Wörter, die die Engine als Grafik zeigt (für die Gegenprobe „kann die Engine das?“)
GRAPHIC_WORDS = [(r"aktien|börse|kurve|chart|diagramm|kursverlauf|wachstumskurve", "chart")]
# Schwerelosigkeit: Sätze, in denen etwas schwebt / abhebt / durch die Luft treibt – und Sätze, in denen alles wieder herunterkracht
FLOAT_RE = (r"schwerelos|(ohne|keine|null) (schwerkraft|gravitation|erdanziehung)|(schwerkraft|gravitation|erdanziehung\w*)\w* .{0,60}(\bweg\b|null|verschw|\baus\b|\bab\b|fehlt|abgeschaltet|nicht mehr|pause|verlier|verlor)|verlier\w* .{0,40}(schwerkraft|gravitation|erdanziehung)|"
            r"schweb(?!\w* in (lebens|großer )?gefahr)|hebs?t [^,.;:!?]{0,60}\bab\b|heben [^,.;:!?]{0,60}\bab\b|durch die luft|in der luft (treib|häng|schweb|steh)|"
            r"treib\w* .{0,24}(durch den raum|im raum|zur decke|nach oben)|flieg\w* (\w+ )?(los|davon|nach oben)\b|steig\w* .{0,30}(in den himmel|in die luft|nach oben)|\bdrifte|verlier\w* (\w+ )?den halt|verlier\w* (\w+ )?die bodenhaftung")
HUD_AIR_RE = r"symbole?n?\b|markierung|\bicons?\b|lebensbalken|\banzeigen?\b|\bpfeile?n?\b|bausteine?n?\b|bl[oö]cke?n?\b|hologramm|schriftz|\bmenüs?\b|wegpunkt"
NOT_BODIES_RE = r"laser|\blicht|strahl|leucht|schall|geräusch|\bton\b|töne|geruch|\bduft|rauch|qualm|staub|funk|signal|viren|virus|keime|pollen|wellen\b"
DROP_RE = (r"kracht|krachen|aufprall|prall\w* .{0,70}(boden|erde|asphalt|straße|\bauf\b)|knall\w* .{0,70}(boden|erde|asphalt|straße|pflaster)|"
           r"\b(schlägt|schlagen) .{0,30}(boden|asphalt|\bauf\b)|(fällt|fällst|fallen|stürzt|stürzen) .{0,50}(boden|herunter|herab|hinab|zurück|\bab\b)|plumps")
# „Das Spiel stürzt ab“, „der Server stürzt ab“: ein Programm-Absturz – da fällt niemand zu Boden
SOFT_CRASH_RE = r"(spiel|programm|app|computer|system|server|rechner|handy|browser|konsole|\bpc|software|internet|simulation|welt|matrix)\w* (stürzt|stürzen) .{0,20}\bab\b|(stürzt|stürzen) (das|dein|unser|mein) (spiel|system|programm|handy)\w* .{0,20}\bab\b"
GRAVITY_BACK_RE = r"(schwerkraft|gravitation|erdanziehung\w*)\w* .{0,60}(wieder|zurück|setzt .{0,12}ein|schaltet sich .{0,12}ein|kehrt)"
ZERO_G_TOPIC = r"schwerkraft|schwerelos|gravitation|erdanziehung"
FLOAT_THINGS = ("lib_stuhl", "lib_kaffeetasse", "box", "clock", "lib_schuh", "glass")       # was in einem Zimmer herumtreibt, wenn nichts Bestimmtes genannt ist
DISASTER_RE = (r"zerstör|vernicht|verwüst|reiß\w* .{0,40}\b(ab|auf|ein|mit|weg)\b|br[ie]ch\w* .{0,30}\b(auf|ein|zusammen)\b|stürz\w* ein|orkan|hurrikan|erdbeben|"
               r"tsunami|flutwelle|explodier|explosion|verglüh|tödlich|albtraum|weltuntergang|trümmer|kracht|krachen|aufprall|schleuder|druckwelle")
WEATHER_HINTS = [(r"erdbeben|\bbebt\b|erschütter", "quake"), (r"orkan|hurrikan|sturmböe|\bsturm\b|stürmt|windböe|luftmassen|druckwelle", "wind"),
                 (r"\bkocht|zu kochen|brodel|verdampf|verdunste", "steam"), (r"ascheregen|\basche\b", "ash")]
PANIC_RE = r"panik|flieh|flücht|rennen (weg|davon|los|um)|rennt (weg|davon|los)|schrei(?!b)|stürmen|plünder|todesangst|rette sich"
CALM_RE = r"\bruhig|friedlich|entspannt|gemütlich|ganz normal|wie immer|alltag|idyll|\bstille\b"
MOOD_HINTS = [
    (PANIC_RE, ("panic", "panic")),
    (r"feiern|jubel|freude|party|gewinn|gerettet|endlich wieder|erleichter|glücklich", ("happy", "cheer")),
    (r"verhunger|sterben|\btod\b|trauer|verzweifel|leiden|elend|verlieren alles|einsam|vermiss", ("sad", "sad")),
    (r"unheimlich|grusel|\bangst|dunkelheit|finster|schatten|lauert|monster|geist", ("scary", "")),
    (DISASTER_RE, ("tense", "worried")),
    (r"chaos|katastrophe|ausnahmezustand|alarm|gefahr|bedroh|warnung|knapp|kritisch|kollabier|zusammenbr|sorge|nervös|unsicher|"
     r"leergekauft|schlange stehen|warteschlange|hunger|engpass|notfall|notstand", ("tense", "worried")),
    (r"menschen|leute|bevölkerung|einwohner|millionen|milliarden|gesellschaft", ("", "walk")),
    (r"staunen|beobachten|schauen zu|zuschauer", ("", "watch")),
]
INDOOR = ("bedroom", "livingroom", "diningroom", "kitchen", "transit", "office", "classroom", "mathroom", "lab", "hospital", "basement", "cave", "underwater", "space", "cinema", "chapel", "tattoostudio", "nailstudio", "barbershop", "hairsalon", "controlroom", "throneroom", "royalmuseum")
MAPS = ("germany", "worldmap")
GARAGES = ("garage",)                                           # in der Werkstatt stehen Autos (drinnen sonst nie)
GARAGE_VEHICLES = ("car", "police", "ambulance", "truck", "bike")
OUTDOOR_THINGS = ("drone", "cctv", "fire", "smoke", "volcano", "meteor", "tornado", "lightning", "flood", "crack", "wave", "explosion", "car", "police", "ambulance", "bus", "truck",
                  "plane", "satellite", "rocket", "ufo", "aurora", "ice", "ship", "bike", "tent", "trafficlight", "house", "tree", "solarpanel",
                  "pile", "sandpile", "trash", "barrel", "generator")
DULL = ("table", "shelf", "streetlamp", "rock", "box")          # allein als Großaufnahme langweilig
INDOOR_THINGS = ("faucet", "glass", "candle", "cans", "clock", "door", "fridge", "tv", "computer", "shelf", "cart", "table", "money", "aquarium")
TEXT_PROPS = [(r"friseurschere|haarschere|\bscheren?\b(?! (?:zwischen|geht|öffnet|klafft|von))|haarschnitt|haare (?:\w+ ){0,3}schneiden", "scissors"), (r"haarschneider|haarschneidemaschine|barttrimmer|bartschneider|maschinenschnitt", "clippers"),   # Ausbau 28.11.2026: Friseur-Werkzeug
              (r"rasiermesser|rasierpinsel|bartpflege|nassrasur|bartrasur", "razor"), (r"\bföhn|\bfön\b|haartrockner", "hairdryer"),
              (r"\bmini-?maps?\b|\bmini-?karten?\b|\bmini-?radar\b", "minimap"),       # Ausbau 25.11.2026: Mini-Karte und Karten-Markierungen schweben frei im Bild
              (r"kartensymbol|kartenmarkierung|quest-?marker|\bwegpunkt|symbole? .{0,40}(?:sichtfeld|in der luft|schweb|auf der karte)|zu (?:den|denselben|diesen|all den) symbolen", "markers"),
              (r"staubsauger", "vacuum"), (r"\bdisplays?\b|handydisplay|handy-display|handybildschirm|handy-bildschirm|touchscreen|sperrbildschirm", "display"), (r"motorkran|werkstattkran|bau\w* .{0,40}motor.{0,40}\bein\b|motor\w* (?:\w+ )?(?:ein|aus)ge?bau|(?:ein|aus)bau\w* .{0,30}motor|motortausch|motor\w* .{0,25}(?:hoch|heb|hängt)", "enginehoist"),
              (r"motorständer|montageständer", "enginestand"), (r"\bv8\b|\bv12\b|\bw12\b|\bw16\b|\bmotor(?!rad|roller|säge|boot)\w*|motorblock|verbrenner|\bzylinder|\bps\b", "engine"),
              (r"kolben|pleuel|kurbelwelle", "piston"), (r"getriebe|kupplung|\bgänge?\b|schaltknauf", "gearbox"), (r"kühler\b|kühlwasser|überhitz", "radiator"),
              (r"(?<![a-zäöüß])(?:\w*?(?:auto|winter|sommer|ersatz|hinter|vorder|renn|gummi))?reifen\b|felge|\bräder\b", "tire"), (r"hebebühne", "carlift"), (r"werkzeug|schrauber|schraubt", "toolbox"), (r"schraubenschlüssel", "wrench"), (r"bohrmaschine|schlagbohrer|akkuschrauber|\bbohrt\b|\bbohren\b|\bbohrer\b", "drill"),
              (r"\btacho|km/h|stundenkilometer|höchstgeschwindigkeit|beschleunig|von 0 auf 100|0 auf 100", "speedometer"),
              (r"\bwaage\b|wiegt|gewicht|\bkilo\b|schwerer als", "scale"), (r"motoröl|ölwechsel|ölkanne", "oilcan"),
              (SUB_RE, "submersible"), (r"nähmaschine|\bnäh(?:en|t|ten|te)\b|zusammennäh|zusammengenäh|vernäh", "sewing"), (r"stoffbahn|stoffballen|stoffrolle|(?:quadrat)?meter (?:\w+ )?stoff\b|\bstoff\b.{0,60}(?:kauf|geschäft|läden)|kauf\w*\b.{0,60}\bstoff\b", "fabric"), (r"aquarium|aquarien(?!scheib|glas)|goldfisch|fischglas|fischbecken", "aquarium"), (r"drohne", "drone"), (r"überwachungskamera|kameras? (erfass|film|beobacht)|überwacht|überwachung", "cctv"), (r"zucker|\bsalz\b", "pile"), (r"\bsand\b", "sandpile"), (r"\bmüll|abfall|plastik", "trash"), (r"wasserhahn|trinkwasser|leitungswasser", "faucet"),
              (r"\bglas\b|\bgläser|trinken|getränk|\bdurst", "glass"), (r"kerze", "candle"), (r"konserve|vorrät|dosen", "cans"), (r"benzin|kanister|sprit", "canister"),
              (r"krankenwagen|rettungswagen|notarzt|sanitäter|rettungsdienst|rettungskräfte|einsatzkräfte|\bnotruf", "ambulance"), (r"polizeiauto|polizeiwagen|streifenwagen|\bpolizei\b|polizist", "police"),
              (r"\bautos?\b|\bstau\b|kleinwagen|sportwagen|\bpkw\b|karosserie|\bnavis?\b|navigationsgerät|navigationssystem", "car"), (r"\bbus\b|busse", "bus"), (r"lkw|lastwagen|lieferung|lieferkette", "truck"), (r"flugzeug|flieger|\bflüge", "plane"),
              (r"satellit|\bgps\b", "satellite"), (r"rakete", "rocket"), (r"\bgeld|\beuro\b|kosten|(?<![a-zäöüß])teuer|preise|milliarden euro|bezahl", "money"),
              (r"solar", "solarpanel"), (r"generator|notstrom|aggregat", "generator"), (r"\bfeuer\b|flammen|\bbrand\b|in brand|lichterloh|waldbr[aä]nd|\bbrände", "fire"), (r"\brauch\b|qualm", "smoke"),
              (r"vulkan|lava", "volcano"), (r"meteor|asteroid|komet", "meteor"), (r"tornado|wirbelsturm", "tornado"), (r"gewitter|\bblitz(?!schnell|artig|blank|sauber|gescheit)", "lightning"),
              (r"überschwemm|\bflut|hochwasser", "flood"), (r"erdbeben|boden reißt|erdkruste|fundament|reiß\w* .{0,40}\b(ab|auf)\b|bricht .{0,20}\bauf\b|\brisse\b|spalte", "crack"), (r"tsunami|riesenwelle|wasserwelle|wasserwand|wassermassen|flutwelle|monsterwelle|riesige\w* welle", "wave"), (r"orkan|hurrikan|\bsturm\b", "stormcloud"), (r"explo", "explosion"),
              (r"\bufo|außerirdisch", "ufo"), (r"polarlicht", "aurora"), (r"eisberg|\beis schmilzt", "ice"), (r"\bschiff|\bboot", "ship"),
              (r"fahrrad", "bike"), (r"kühlschrank", "fridge"), (r"einkaufswagen", "cart"), (r"tür\b|türen\b|klopft", "door"), (r"\buhr\b|uhrzeit", "clock"),
              (r"\bfass\b|\bfässer|\bölfass|\bfässern|\böl\b", "barrel"), (r"\bzelt", "tent"), (r"ampel", "trafficlight"), (r"fernseh|nachrichten", "tv"), (r"computer|internet|server|zock|gaming|videospiel|ballerspiel|\bgamer|\bpc\b|laptop", "computer"),
              (r"pflanze[n]? wachs|keim|\bsaat", "sprout"), (r"\bmoos(?!gummi)|moospolster|mooskissen", "moss"), (r"haarwurzel|haarbalg|härchen", "goosebumps"),
              (r"adrenalin|nebenniere|stresshormon", "adrenaline"), (FUR_RE, "fur")]   # „Gänsehaut“ selbst setzt stage._music (nicht als Ding des Themas in jeder zweiten Szene)
MAP_HINTS = ((r"ganz deutschland|in deutschland|deutschlandweit|bundesweit|bundesländer|jeder deutsche|alle deutschen", "germany"),
             (r"weltweit|auf der ganzen welt|alle länder|rund um den globus|weltbevölkerung|alle kontinente|die ganze erde|die ganze welt", "worldmap"))
# Tiere neben Menschen: Größe im Verhältnis zur Figur (1.0 = menschengroß). „Riesen…“-Themen heben das auf (giant).
CREATURE_SIZE = {"cheetah": 1.0, "eagle": 0.8, "flea": 0.4, "shrimp": 0.5, "mantis": 0.5, "jelly": 0.6, "axolotl": 0.5, "tardigrade": 0.5, "brain": 1.6, "spider": 0.38, "cat": 0.42, "dog": 0.55, "bird": 0.45, "bee": 0.45, "wasp": 0.45, "diver": 1.1, "dolphin": 1.0, "cow": 0.9, "pig": 0.6, "chimp": 0.75, "mosquito": 0.45, "fly": 0.45, "lion": 1.15, "whale": 1.4, "chimera": 1.05, "frog": 0.34, "woodfrog": 0.34, "platypus": 0.55, "puffer": 0.6, "angler": 0.9, "wecker": 0.72}
GIANT_RE = r"riesen|riesig|gigant|monströs|so groß wie|meterhoh|haushoh|mutier"
# Nur hier laufen Passanten durchs Bild – auf dem Feld, im Wald, im Keller ist niemand unterwegs
CROWD_PLACES = ("headquarters", "street", "park", "village", "beach", "icesea", "harbor", "gasstation", "station", "transit", "supermarket", "supermarket_empty", "hospital", "office",
                "classroom", "restaurant", "church", "chapel")
CROWD_ELEMENTS = ("city", "village", "street", "houses")


def crowd_ok(scene):
    if scene.get("_mourn") and str(scene.get("crowd") or "") in ("sad", "watch", "worried"):
        return True                                       # Trauergäste stehen auch am Grab (stage._funeral_story)
    b = backdrop(scene)
    if isinstance(b, dict):
        return any(str(e) in CROWD_ELEMENTS for e in (b.get("elements") or []))
    return places.resolve(b) in CROWD_PLACES


PUBLIC_INDOOR = ("supermarket", "supermarket_empty", "station", "transit", "hospital", "office", "classroom", "restaurant", "chapel")
STRONG_FEELINGS = ("shocked", "scared", "sad", "angry", "worried")
MOOD_EMOTION = {"panic": "scared", "tense": "worried", "scary": "scared", "sad": "sad", "happy": "happy"}
EMOTION_OK = {"panic": ("scared", "shocked", "worried"), "tense": ("worried", "scared", "shocked", "angry", ""),
              "scary": ("scared", "worried", "shocked"), "sad": ("sad", "worried", ""), "happy": ("happy", ""),
              "": ("", "happy", "worried", "shocked", "sad", "angry"), "calm": ("", "happy")}


def _mood_hint(text):
    import re as _re
    t = str(text or "").lower()
    mood, crowd = "", ""
    for pat, (m, c) in MOOD_HINTS:
        if _re.search(pat, t):
            mood, crowd = mood or m, crowd or c
    return mood, crowd


TOPIC_PLACES = ("cinema", "restaurant", "hospital", "supermarket", "station", "serverroom", "lab", "classroom", "office", "beach", "forest",
                "snow", "desert", "mountain", "underwater", "space", "farm", "village")   # Orte, die ein ganzes Video tragen können
SAID_SKIP = {"gang", "welt", "world", "karte", "map", "deutschland", "deutschlandkarte", "eis", "home", "house", "outside", "server", "zug",
             "natur", "laden", "geschäft", "firma", "konzern", "stadt", "city"}
SAID_RE = (r"\b(?:im|ins|am|zum|zur|beim|vom|aus dem|aus der|auf dem|auf der|in (?:der|die|den|dem|das|einem|einer|einen|deinen|deinem|deiner|"
           r"deine|eurem|eurer|unserem|unserer|seinem|seiner|ihrem|ihrer))\s+(?:[a-zäöüß]+(?:e|en|er|es|em)\s+)?([a-zäöüß-]+)")


COMPOUND_THING_RE = r"[a-zäöüß]{4,}(?:tür|türe|türen|luke|treppe|fenster|schlüssel|schloss|klappe|leiter)\b"   # „Dachbodentür“, „Kellerfenster“: ein Ding, kein Ort


def _said_place(text):
    """Ort, den der Satz ausdrücklich nennt („in deinen Garten“, „im dunklen Keller“, „am Strand“) – oder None."""
    import re as _re
    t = str(text or "").lower()
    for m in _re.finditer(SAID_RE, t):
        w = m.group(1)
        for form in (w, w[:-1], w[:-2], w[:-3], w.replace("ä", "a").replace("ö", "o").replace("ü", "u")):
            if len(form) >= 3 and form in places.ALIASES and form not in SAID_SKIP:
                return places.ALIASES[form]
            if form in places.PLACES and form not in SAID_SKIP:
                return form
    return None


def _hint(text):
    """Erster passender fester Ort – oder eine Landschaft, in der alle im Satz genannten Teile zusammenkommen."""
    import re as _re
    t = str(text or "").lower()
    merged, first = None, None
    for pat, target in HINTS:
        if _re.search(pat, t):
            if target == "attic" and not _re.search(r"dachboden", t) and (_CTX["mem"] or _re.search(COMPUTER_MEM_RE, t)):
                continue                                  # „im Speicher der Sonde“, „Hauptspeicher“: Computerspeicher, kein Dachboden (Video 177)
            if target == "landfill" and not _re.search(r"müllhalde|müllberg|deponie", t) and _re.search(JUNK_TALK_RE, t):
                continue                                  # „sendet nur noch Müll“, „Datenmüll“: Redensart, keine Müllkippe (Video 177)
            if isinstance(target, dict):
                if merged is None:
                    merged = {k: (list(v) if isinstance(v, list) else v) for k, v in target.items()}
                else:
                    merged["elements"] = (merged.get("elements", []) + [e for e in target.get("elements", [])
                                                                        if e not in merged.get("elements", [])])[:4]
                first = first or merged
            else:
                first = first or target
    return first


INSERT_BG = {"panic": ((96, 26, 30), (30, 10, 16)), "tense": ((104, 62, 30), (30, 18, 14)), "scary": ((30, 34, 70), (8, 8, 20)),
             "sad": ((44, 64, 104), (14, 18, 36)), "happy": ((250, 200, 110), (214, 130, 70)), "": ((52, 70, 120), (16, 20, 44))}
_ins_bg = {}


def _insert_frame(kinds, t, dur, mood, low=False, neon=False):
    """Einschub: ein Gegenstand groß und allein im Bild (wie eine Nahaufnahme), ruhiger Verlauf als Hintergrund."""
    mood = mood if mood in INSERT_BG else ""
    if mood not in _ins_bg:
        c0, c1 = INSERT_BG[mood]
        g = Image.new("L", (W // 8, H // 8), 0)
        ImageDraw.Draw(g).ellipse((-20, 10, W // 8 + 20, H // 8 - 60), fill=255)
        from PIL import ImageFilter
        g = g.filter(ImageFilter.GaussianBlur(26)).resize((W, H), Image.BILINEAR)
        _ins_bg[mood] = Image.composite(Image.new("RGB", (W, H), c0), Image.new("RGB", (W, H), c1), g)
    frame = graphics.background(t, mood) if neon else _ins_bg[mood].copy()
    d = ImageDraw.Draw(frame, "RGBA")
    n = len(kinds)
    for i, kind in enumerate(kinds):
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        extras.draw_prop(layer, kind, 540, t)
        box = layer.getbbox()
        if not box:
            continue
        cut = layer.crop(box)
        tw, th = ((760, 820) if n == 1 else (460, 560)) if not low else ((620, 600) if n == 1 else (420, 460))
        f = min(tw / cut.width, th / cut.height) * (0.9 + 0.1 * extras._pop(t, 0.05 + i * 0.25, 0.4)) * (1 + 0.04 * t / max(dur, 1))
        if t < 0.05 + i * 0.25:
            continue
        cut = cut.resize((max(1, int(cut.width * f)), max(1, int(cut.height * f))), Image.BILINEAR)
        cx = 540 if n == 1 else (290 + i * 500)
        cy = (780 if not low else 960) + math.sin(t * 1.6 + i) * 12
        d.ellipse((cx - cut.width * 0.45, cy + cut.height * 0.5 + 10, cx + cut.width * 0.45, cy + cut.height * 0.5 + 50), fill=(0, 0, 0, 80))
        frame.paste(cut, (int(cx - cut.width / 2), int(cy - cut.height / 2)), cut)
    return frame


# Blick in den Spiegel (Prüfung 24.11.2026, Video 204 „Starre nie im Dunkeln in den Spiegel“): Das ganze Video handelte davon, wie sich das eigene
# Spiegelbild im Halbdunkel verändert – zu sehen war 74 Sekunden lang nur die erschrockene Figur von vorn im dunklen Bad, kein Spiegelbild, kein
# verzerrtes Gesicht. Einstellung „mirror“: Blick über die Schulter in den Badezimmerspiegel; im Glas das Spiegelbild der Figur im Zustand, den der
# Satz beschreibt (`scene["mirror"]`): normal | stare (starrt reglos) | fade (der Rand versinkt im Dunkeln) | void (Augen riesig und schwarz) |
# monster (Fratze mit starrem Grinsen) | snap (Fratze, dann schlagartig wieder das echte Gesicht) | clear (erleichtert, hell).
MIRROR_STATES = ("normal", "stare", "fade", "void", "monster", "snap", "clear")
MIRROR_BOX = (118, 250, 962, 1300)       # Glas im Bild; darunter Ablage und Waschbecken, unten angeschnitten der Hinterkopf der Figur
_mir_cache = {}


def _mirror_params(state, t, dur):
    """(Dunkel-Anteil 0..1, schwarze Augen 0..1, Fratze, heller Blitz 0..1, Ausdruck) für den Zustand zum Zeitpunkt t."""
    x = _ease(min(1.0, t / max(0.6, dur * 0.8)))
    if state == "snap":
        ts = min(1.1, dur * 0.35)
        if t < ts:
            return 0.7, 1.0, True, 0.0, "monster"
        return 0.08, 0.0, False, max(0.0, 1 - (t - ts) / 0.3), "clear"
    if state == "monster":
        return 0.7, 1.0, True, 0.0, "monster"
    if state == "void":
        return 0.82, _ease(min(1.0, t / max(0.5, dur * 0.55))), False, 0.0, "wide"
    if state == "fade":
        return 0.3 + 0.58 * x, 0.0, False, 0.0, "worried"
    if state == "stare":
        return 0.12 + 0.22 * x, 0.0, False, 0.0, "normal"
    if state == "clear":
        return 0.0, 0.0, False, 0.0, "clear"
    return 0.12, 0.0, False, 0.0, "normal"


def mirror_glass(look, state, t, dur, size=(844, 1050), seed=3):
    """Das Spiegelbild: gespiegelte Badezimmerwand, davor die Figur groß von vorn. Je nach Zustand versinkt der Rand des Bildes im Dunkeln
    (Troxler-Effekt), die Augen werden zu schwarzen Höhlen, das Gesicht zur Fratze."""
    gw, gh = size
    state = state if state in MIRROR_STATES else "normal"
    dark, void, grin, flash, face = _mirror_params(state, t, dur)
    lit = state == "clear"                                 # nur wenn das Licht an ist – nach dem Verschwinden der Fratze bleibt es Kerzenlicht
    key = ("glassbg", size, lit)
    if key not in _mir_cache:
        c0, c1 = ((120, 150, 170), (86, 112, 134)) if lit else ((44, 60, 82), (24, 32, 48))
        g = Image.new("RGB", size, c1)
        d = ImageDraw.Draw(g)
        for y in range(gh):
            f = y / gh
            d.line((0, y, gw, y), fill=tuple(int(c0[i] + (c1[i] - c0[i]) * f) for i in range(3)))
        ln = tuple(int(c * 0.82) for c in c1)
        for y in range(40, gh, 130):
            d.line((0, y, gw, y), fill=ln, width=4)
        for x in range(30, gw, 130):
            d.line((x, 0, x, gh), fill=ln, width=4)
        d.rounded_rectangle((gw * 0.66, gh * 0.1, gw * 1.1, gh * 1.2), 14, fill=tuple(int(c * 0.78) for c in c1), outline=tuple(int(c * 0.55) for c in c1), width=10)   # Tür im Rücken der Figur
        d.ellipse((gw * 0.7, gh * 0.56, gw * 0.7 + 26, gh * 0.56 + 26), fill=tuple(int(c * 1.5) for c in c1))
        _mir_cache[key] = g.filter(ImageFilter.GaussianBlur(6))
    g = _mir_cache[key].copy()
    emo = {"monster": "angry", "wide": "scared", "worried": "worried", "clear": "happy"}.get(face, "")
    pose, _ = rig.pose_at("idle", t, dur, emo, 0.0, seed)
    pose.look = 0.02                                       # blickt sich selbst in die Augen
    pose.lift = 0
    pose.arm_l, pose.fore_l, pose.arm_r, pose.fore_r = -10, -6, 10, 6
    pose.eyes = {"monster": "angry", "wide": "wide", "worried": "worried", "clear": "happy"}.get(face, "normal")
    pose.smile = 0.8 if face == "clear" else -0.3 if face == "worried" else 0.0
    pose.mouth = 0.0
    if state == "stare":
        pose.extra["pupil"] = 0.8                          # im Halbdunkel geweitete Pupillen
    if void > 0.02:
        pose.extra["void"] = void
    if grin:
        pose.extra["grin"] = True
        pose.head = 5 * math.sin(t * 1.3)
    im, fx, fy = rig.draw(look, pose, 1, 2.55 / max(0.6, look.size), ss=1)
    hc = pose.extra.get("hc") or (im.width / 2, im.height * 0.3, 200)
    if grin:                                               # Fratze: das Gesicht zieht sich langsam in die Breite und Länge, fahle Farbe
        wob = 1 + 0.05 * math.sin(t * 2.1)
        im2 = im.resize((int(im.width * wob), int(im.height * (2 - wob))), Image.BILINEAR)
        hc = (hc[0] * wob, hc[1] * (2 - wob), hc[2])
        r_, g_, b_, a_ = im2.split()
        im = Image.merge("RGBA", (r_.point(lambda v: int(v * 0.8)), g_.point(lambda v: int(v * 0.9)), b_.point(lambda v: int(v * 0.86)), a_))
    cx, cy = gw / 2, gh * 0.52                             # Kopf unter der Zone für Titel, Karte und Schild (in Video 205 lag „EINE MINUTE“ auf dem Haaransatz)
    g.paste(im, (int(cx - hc[0]), int(cy - hc[1])), im)
    if not lit:                                            # schwaches Licht: alles etwas blau und dunkel
        g = Image.blend(g, Image.new("RGB", size, (16, 22, 40)), 0.26)
    if dark > 0.01:                                        # der Rand des Sichtfeldes versinkt: nur die Mitte des Gesichts bleibt
        m = Image.new("L", (gw // 8, gh // 8), int(250 * min(1.0, dark * 1.25)))
        r0 = (620 - 470 * dark) / 8
        ImageDraw.Draw(m).ellipse((cx / 8 - r0, (cy + 18) / 8 - r0 * 1.08, cx / 8 + r0, (cy + 18) / 8 + r0 * 1.08), fill=0)
        m = m.filter(ImageFilter.GaussianBlur(5 + 7 * (1 - dark))).resize(size, Image.BILINEAR)
        g = Image.composite(Image.new("RGB", size, (5, 7, 13)), g, m)
    if flash > 0.01:
        g = Image.blend(g, Image.new("RGB", size, (255, 255, 255)), min(0.85, flash))
    sh = Image.new("RGBA", size, (0, 0, 0, 0))             # Glanz auf dem Glas
    ds = ImageDraw.Draw(sh)
    a_s = 34 if lit else 16
    ds.polygon([(gw * 0.06, gh * 0.02), (gw * 0.2, gh * 0.02), (gw * 0.04, gh * 0.3), (gw * 0.0, gh * 0.22)], fill=(255, 255, 255, a_s))
    ds.polygon([(gw * 0.25, gh * 0.02), (gw * 0.3, gh * 0.02), (gw * 0.02, gh * 0.48), (gw * 0.02, gh * 0.4)], fill=(255, 255, 255, a_s))
    g.paste(sh, (0, 0), sh)
    return g


def mirror_sticker(look, state="monster", w=620):
    """Gerahmter Spiegel mit Spiegelbild als freigestelltes Motiv (Titelbild)."""
    gl = mirror_glass(look, state, 1.2, 3.0)
    gl = gl.resize((w, int(w * gl.height / gl.width)), Image.LANCZOS)
    b = 26
    out = Image.new("RGBA", (gl.width + 2 * b, gl.height + 2 * b), (0, 0, 0, 0))
    d = ImageDraw.Draw(out)
    d.rounded_rectangle((0, 0, out.width - 1, out.height - 1), 56, fill=INK)
    d.rounded_rectangle((7, 7, out.width - 8, out.height - 8), 50, fill=(202, 164, 110))
    d.rounded_rectangle((b - 5, b - 5, out.width - b + 4, out.height - b + 4), 36, fill=INK)
    mk = Image.new("L", gl.size, 0)
    ImageDraw.Draw(mk).rounded_rectangle((0, 0, gl.width - 1, gl.height - 1), 32, fill=255)
    out.paste(gl, (b, b), mk)
    return out


def _mirror_frame(scene, cast, t, dur):
    """Blick über die Schulter in den Badezimmerspiegel."""
    state = str(scene.get("mirror") or "normal")
    acts = [a for a in (scene.get("actors") or []) if isinstance(a, dict) and not a.get("kind")]
    aid = next((str(a.get("id")) for a in acts if isinstance((cast or {}).get(str(a.get("id"))), dict) and not cast[str(a.get("id"))].get("kind")), None) \
        or next((k for k, v in (cast or {}).items() if isinstance(v, dict) and not v.get("kind")), None)
    look = rig.Look.from_spec((cast or {}).get(aid) if aid else {}, aid or "", list(cast).index(aid) if aid and aid in (cast or {}) else None)
    lit = state == "clear"
    x0, y0, x1, y1 = MIRROR_BOX
    key = ("wall", lit)
    if key not in _mir_cache:
        c0, c1 = ((150, 176, 190), (104, 128, 148)) if lit else ((30, 40, 60), (12, 16, 28))
        fr = Image.new("RGB", (W, H), c1)
        d = ImageDraw.Draw(fr)
        for y in range(H):
            f = y / H
            d.line((0, y, W, y), fill=tuple(int(c0[i] + (c1[i] - c0[i]) * f) for i in range(3)))
        ln = tuple(int(c * 0.8) for c in c1)
        for y in range(90, 1340, 150):
            d.line((0, y, W, y), fill=ln, width=5)
        for x in range(60, W, 150):
            d.line((x, 0, x, 1340), fill=ln, width=5)
        wood = (202, 164, 110) if lit else (112, 92, 78)
        d.rounded_rectangle((x0 - 34, y0 - 34, x1 + 34, y1 + 34), 62, fill=INK)                       # Rahmen
        d.rounded_rectangle((x0 - 26, y0 - 26, x1 + 26, y1 + 26), 56, fill=wood)
        d.rounded_rectangle((x0 - 26, y1 - 4, x1 + 26, y1 + 26), 20, fill=tuple(int(c * 0.78) for c in wood))
        d.rounded_rectangle((x0 - 7, y0 - 7, x1 + 7, y1 + 7), 40, fill=INK)
        shelf = (226, 230, 236) if lit else (92, 100, 122)
        d.rounded_rectangle((40, 1372, W - 40, 1420), 18, fill=shelf, outline=INK, width=7)           # Ablage
        basin = (240, 244, 248) if lit else (104, 114, 138)
        d.rounded_rectangle((170, 1470, W - 170, 2050), 120, fill=basin, outline=INK, width=8)        # Waschbecken (angeschnitten)
        d.rounded_rectangle((500, 1400, 580, 1500), 22, fill=(190, 196, 206) if lit else (120, 128, 148), outline=INK, width=7)   # Wasserhahn
        d.rounded_rectangle((150, 1290, 226, 1376), 14, fill=(120, 190, 220) if lit else (60, 96, 124), outline=INK, width=6)     # Zahnputzbecher
        d.line((176, 1296, 160, 1210), fill=INK, width=18)
        d.line((176, 1296, 160, 1210), fill=(240, 110, 110) if lit else (130, 70, 84), width=9)
        d.line((204, 1296, 222, 1220), fill=INK, width=18)
        d.line((204, 1296, 222, 1220), fill=(250, 220, 90) if lit else (132, 120, 70), width=9)
        _mir_cache[key] = fr
    frame = _mir_cache[key].copy()
    gl = mirror_glass(look, state, t, dur, (x1 - x0, y1 - y0))
    mk = _mir_cache.setdefault("mask", Image.new("L", (x1 - x0, y1 - y0), 0))
    if not mk.getbbox():
        ImageDraw.Draw(mk).rounded_rectangle((0, 0, x1 - x0 - 1, y1 - y0 - 1), 34, fill=255)
    frame.paste(gl, (x0, y0), mk)
    if not lit:                                            # Kerze auf der Ablage: das einzige, schwache Licht
        fl = 0.86 + 0.14 * math.sin(t * 13) * math.sin(t * 7.3 + 1)
        glow = _mir_cache.get("glow")
        if glow is None:
            gm = Image.new("L", (W // 8, H // 8), 0)
            ImageDraw.Draw(gm).ellipse((880 / 8 - 22, 1270 / 8 - 22, 880 / 8 + 22, 1270 / 8 + 22), fill=255)
            glow = _mir_cache["glow"] = gm.filter(ImageFilter.GaussianBlur(11)).resize((W, H), Image.BILINEAR)
        frame = Image.composite(Image.blend(frame, Image.new("RGB", (W, H), (255, 190, 110)), 0.3 * fl), frame, glow)
        d = ImageDraw.Draw(frame, "RGBA")
        d.rounded_rectangle((852, 1280, 908, 1378), 10, fill=(236, 226, 204), outline=INK, width=6)
        d.line((880, 1280, 880, 1262), fill=INK, width=5)
        fh = 52 * fl
        d.polygon([(880, 1262 - fh - 8), (862, 1250), (880, 1272), (898, 1250)], fill=INK)
        d.polygon([(880, 1262 - fh), (868, 1250), (880, 1266), (892, 1250)], fill=(255, 190, 70))
        d.polygon([(880, 1262 - fh * 0.5), (874, 1252), (880, 1262), (886, 1252)], fill=(255, 244, 190))
    hk = ("back", look.hair, look.hair_color, look.shirt, lit)
    if hk not in _mir_cache:                               # Hinterkopf und Schultern der Figur, unscharf im Vordergrund
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        dim = 0.9 if lit else 0.42
        hair = tuple(int(c * dim) for c in rig.hair_color(look))
        shirt = tuple(int(c * dim) for c in look.shirt)
        d.rounded_rectangle((60, 1790, W - 60, 2100), 150, fill=INK)
        d.rounded_rectangle((72, 1802, W - 72, 2100), 140, fill=shirt)
        d.ellipse((540 - 300, 1470, 540 + 300, 1990), fill=INK)
        d.ellipse((540 - 288, 1482, 540 + 288, 1978), fill=hair)
        if look.hair == "curly":
            for i in range(11):
                a = math.radians(-190 + i * 20)
                bx, by = 540 + math.cos(a) * 280, 1730 + math.sin(a) * 250
                d.ellipse((bx - 92, by - 92, bx + 92, by + 92), fill=INK)
            for i in range(11):
                a = math.radians(-190 + i * 20)
                bx, by = 540 + math.cos(a) * 280, 1730 + math.sin(a) * 250
                d.ellipse((bx - 80, by - 80, bx + 80, by + 80), fill=hair)
        elif look.hair in ("long", "bob", "ponytail", "bun"):
            d.rounded_rectangle((540 - 300, 1720, 540 + 300, 2100), 120, fill=INK)
            d.rounded_rectangle((540 - 288, 1720, 540 + 288, 2100), 110, fill=hair)
        _mir_cache[hk] = lay.filter(ImageFilter.GaussianBlur(7))
    bob = int(4 * math.sin(t * 1.4))
    frame.paste(_mir_cache[hk], (0, bob), _mir_cache[hk])
    return frame


TIGHT_Z, TIGHT_AY = 1.3, 300.0            # Halbnahe: Zoom und Fixpunkt (oben) – wie in Erklär-Shorts füllen die Figuren das Bild


def _camera(frame, t, dur, cam):
    """Lebendige Kamera für jede Szene: etwas näher an den Figuren, langsame Fahrt, ein kurzer Ruck beim Schnitt und – wenn
    das Schlüsselwort fällt – ein schneller Sprung auf die Hauptfigur (wie in geschnittenen Kurzvideos)."""
    k = t / max(dur, 0.1)
    e_m = k * k * (3 - 2 * k)                             # weiche Kamerafahrt über die ganze Szene (langsam an, langsam aus)
    move = cam.get("move") or ("push" if cam.get("drift", 1) > 0 else "pull")
    z = (1.0 if cam.get("flat") else cam.get("zt", TIGHT_Z) if cam.get("tight") else 1.06)
    if move == "push":
        z += (0.06 if cam.get("flat") else 0.1) * e_m
    elif move == "pull":
        z += (0.06 if cam.get("flat") else 0.1) * (1 - e_m)
    else:                                                 # Schwenk: braucht etwas Zoom, damit seitlich Platz ist
        z += 0.07
    ax, ay = 540.0, (cam.get("ay") or (TIGHT_AY if cam.get("tight") else 1010.0))
    if move in ("pan_r", "pan_l"):
        ax += (1 if move == "pan_r" else -1) * 260 * (e_m - 0.5)
    if cam.get("tight"):                                  # nah dran: Figuren füllen das Bild, der leere Boden unten fällt weg
        ax += (float(cam.get("fx", 540)) - 540) * 0.6
    pt = cam.get("punch")
    if pt is not None and t >= pt:
        e = _ease(min(1.0, (t - pt) / 0.14))
        z += 0.14 * e
        ax += (float(cam.get("fx", 540)) - 540) * e
        ay -= 90 * e
    if cam.get("opener") and t < 0.5:                     # allererstes Bild: kräftiger Ruck ins Bild – sofort Bewegung
        e = (1 - t / 0.5) ** 3
        z += 0.2 * e
    elif t < 0.22:                                        # Schnitt: kurzer Ruck hinein und zur Seite
        e = (1 - t / 0.22) ** 2
        z += 0.08 * e
        ax += cam.get("dir", 1) * 70 * e
    ax = max(0.0, min(float(W), ax))
    w, h = W / z, H / z
    x0, y0 = ax - (ax / W) * w, ay - (ay / H) * h
    return frame.transform((W, H), Image.EXTENT, (x0, y0, x0 + w, y0 + h), Image.BILINEAR)


def _punch_time(scene, words, t0, dur):
    """Zeitpunkt (s ab Szenenbeginn) für den Kamerasprung: wenn das erste Schlüsselwort gesprochen wird, sonst zur Szenenmitte."""
    keys = [str(h).lower().strip(" .,!?") for h in (scene.get("highlight") or []) if str(h).strip()]
    first = {k.split()[0] for k in keys if k.split()}
    for w, s0, _e in words or ():
        if t0 + 0.5 <= s0 <= t0 + dur - 0.9 and str(w).lower().strip(" .,!?„“\"") in first:
            return s0 - t0
    return dur * 0.5 if dur >= 3.2 else None


CALM_MAX = 3.6       # eine ruhige Szene ohne Schnitt höchstens so lang (s); länger steht sonst dasselbe Bild zu lange
CUT_MIN = 2.3        # ab dieser Szenenlänge (s) wird mitten im Satz geschnitten – wie in den Vorbild-Shorts etwa alle 1,8 Sekunden ein neues Bild


def _said_prop(kind, low):
    """Spricht der Satz von diesem Ding? Nur dann lohnt der harte Schnitt darauf – ein Schreibtisch allein vor leerem Grund, während
    der Satz vom Gehirn handelt, ist ein Verlegenheitsbild."""
    key = extras.PROP_ALIASES.get(str(kind).lower(), str(kind).lower())
    if any(k2 == key and re.search(pat, low) for pat, k2 in _lib_props() + TEXT_PROPS):
        return True
    words = {key, str(kind).lower()} | {a for a, k2 in extras.PROP_ALIASES.items() if k2 == key}
    return any(re.search(r"(?<![a-zäöüß])" + re.escape(w), low) for w in words if len(w) >= 3)


BED_SPAN = (60, 700)                                      # Kamera-Stützpunkte für die Schlafende im Bett (weit genug für Kopf am Kissen bis Fußende, die Kamera bleibt halbnah)


def _cut_plan(scene, shot, special, moving, ov_tall, place, actors, props, dur, cam, index):
    """Zweites Bild innerhalb einer Szene: beim Schlüsselwort (sonst zur Mitte) harter Schnitt auf den genannten Gegenstand groß
    („insert“) oder auf die Großaufnahme der Hauptfigur bzw. des Tiers („close“). Jede dritte Szene bleibt ruhig ohne Schnitt.
    Gibt (Schnittzeit oder None, Art, Gegenstände) zurück und schaltet den Kamerasprung ab, wenn geschnitten wird."""
    calm = index % 3 == 2 and dur < CALM_MAX                # ruhige Szene ohne Schnitt – aber nie länger als CALM_MAX Sekunden dasselbe Bild
    if special or shot or moving or ov_tall or scene.get("float") or dur < CUT_MIN or place in MAPS or calm \
            or str(scene.get("shot") or "") in ("event", "insert", "graphic", "close") or scene.get("_balloon") or scene.get("_no_cut"):
        return None, "", []
    low = str(scene.get("text") or "").lower()
    named = [k for k, _ in props if extras.prop_fit(k) and extras.PROP_ALIASES.get(k, k) not in DULL
             and extras.PROP_ALIASES.get(k, k) not in PLACE_HAS.get(place, ()) and _said_prop(k, low)]
    if scene.get("_no_insert"):
        named = []
    down = any(a.get("action") in ("fall", "sleep", "sit", "float") or a.get("kind") in LONG_KINDS for a in actors)      # liegt, sitzt oder schwebt jemand, schneidet die Großaufnahme ihn an
    kind = "insert" if named and index % 2 == 0 else "close" if len(actors) == 1 and not down else "insert" if named else ""   # zwei und mehr nicht anschneiden
    if not kind and not any(a.get("say") or a.get("hold") in ("sign",) for a in actors):
        kind = "flip"                                     # Gegenschnitt: dieselbe Szene von der anderen Seite, andere Kamerafahrt
    if not kind:
        return None, "", []
    pt = cam.get("punch")
    cut = min(max(pt if pt is not None else dur * 0.5, 1.1), dur - 1.0)
    cam["punch"] = None
    return cut, kind, named


CHAPTER_MAX = 2.2                                            # so lange steht eine Kapitel-Tafel höchstens allein im Bild


def render_scene(scene: dict, cast: dict, dur: float, out: Path, words=(), t0=0.0, still: Path = None, index=0):
    """scene: {"place", "time", "weather", "props", "actors": [{"id", "action", "emotion", "emote", "pos", "to", "speaks"}]}.
    words: [(wort, start, ende)] der ganzen Sprecherspur; t0 = Startzeit der Szene darin."""
    place, night, scale, actors, props, weather = _prepare(scene, cast)
    bg = places.background(backdrop(scene), night, bool(scene.get("dark_city")))
    sky_m = places.sky_mask(backdrop(scene), night, bool(scene.get("dark_city")))
    n_frames = max(2, round(dur * FPS))
    shot = str(scene.get("shot") or "").lower()
    has_ov = isinstance(scene.get("overlay"), dict) and scene["overlay"].get("type")
    moving = any(a["x0"] != a["x1"] for a in actors)
    big = 1.5 if shot == "event" else 1.15
    ins = [k for k, _ in props if extras.PROP_ALIASES.get(k, k) in extras.PROPS][:2] if shot == "insert" else []
    gfx = graphics.clean(scene.get("graphic")) if shot == "graphic" else None
    mir = str(scene.get("mirror") or "") if shot == "mirror" and str(scene.get("mirror") or "") in MIRROR_STATES else ""   # Blick in den Spiegel: eigenes Bild (_mirror_frame)
    if gfx and hyper.handles(gfx) and hyper.render(gfx, dur, out, str(scene.get("mood") or "").lower(), still):
        return                                # Grafik von HyperFrames (HTML/GSAP) gerendert – sonst zeichnet graphics.py sie unten wie bisher
    neon_look = str(scene.get("look") or "") == "neon"
    if neon_look:                             # Neon-Nacht: nur die Kulisse wird violett getönt – Figuren und Dinge bleiben kräftig
        bg = graphics.tint(bg)
    elif str(scene.get("look") or "") == "noir":
        bg = graphics.noir(bg)                # Düster: graue, kühle Kulisse, Licht nur über den Figuren
    shot = "close" if shot == "close" and not has_ov and not moving and not props and actors and not scene.get("float") else ""
    ov_tall = str((scene.get("overlay") or {}).get("type") or "") in TALL_OV if has_ov else False
    ov_kind = str((scene.get("overlay") or {}).get("type") or "") if has_ov else ""
    if ov_tall:                               # Liste/Notiz/Handy füllt das obere Bild: eine Sprechblase stünde halb dahinter
        for a_o in actors:
            a_o["say"] = ""
    lead = next((a for a in actors if a["speaks"]), actors[0] if actors else None)
    if lead and not lead["kind"]:     # Gesten der Hauptfigur passend zu den Wörtern dieser Szene
        lead["gplan"] = gesture_plan([w for w in words if t0 - 0.05 <= w[1] < t0 + dur], t0, lead.get("lips"))
    cam = {"dir": 1 if index % 2 == 0 else -1, "drift": 1 if index % 3 != 2 else -1,
           "fx": (lead["x1"] if lead else (props[0][1] if props else 540)),
           "punch": None if (shot == "close" or moving or ov_tall or ov_kind in ("counter", "bar", "thermo") or place in MAPS or not (actors or props)) else _punch_time(scene, words, t0, dur)}
    if actors and shot != "close" and not ov_tall and place not in MAPS and not scene.get("float") and str(scene.get("shot") or "") != "event":
        for a_w in actors:                                              # Tiere: echte Breite ins Bild nehmen und nicht an den Rand stellen
            if a_w["kind"] and a_w["x0"] == a_w["x1"]:
                ksz_w = a_w["ksz"] if a_w.get("ksz") else 1.0 if a_w.get("giant") else HERO_SIZE.get(a_w["kind"], 0.8) if a_w.get("hero") else CREATURE_SIZE.get(a_w["kind"], 1.0)
                r_w = extras.creature(a_w["kind"], 0.0, 1, 0.0, "", scale * 0.9 * ksz_w)
                if r_w:
                    a_w["_hw"] = r_w[0].width / 2 + 40
                    a_w["x0"] = a_w["x1"] = min(max(a_w["x1"], a_w["_hw"]), W - a_w["_hw"]) if a_w["_hw"] * 2 < W else 540.0
        xs = [a["x1"] for a in actors] + [a["x0"] for a in actors if -100 < a["x0"] < W + 100]
        xs += [a["x1"] + sg * a["_hw"] for a in actors if a.get("_hw") for sg in (-1, 1)]
        xs += [x for k, x in props if extras.prop_fit(k) and 0 <= x <= W]   # auch der Gegenstand, von dem der Satz spricht, bleibt ganz im Bild
        for a_l in actors:                                              # lange Tiere (Krebs samt Schere/Keule) ganz im Bild lassen
            if a_l.get("kind") in LONG_KINDS:
                xs += [a_l["x1"] - 190, a_l["x1"] + 190]
                cam["punch"] = None
            if a_l.get("kind") == "lion" and a_l.get("hero"):          # der Löwe samt Mähne und Schwanzquaste ist breiter als jedes andere Tier
                xs += [max(40, a_l["x1"] - 330), min(W - 40, a_l["x1"] + 300)]
        for a_l in actors:                                              # Taucher samt Flossen und Lampe ganz im Bild lassen
            if a_l.get("kind") == "diver":
                xs += [max(210, a_l["x1"] - 330), min(W - 210, a_l["x1"] + 330)]
                cam["punch"] = None
        for k_b, x_b in props:                                          # Kistenstapel, Baumstämme: breiter als eine Figur – nicht am Rand anschneiden
            if extras.PROP_ALIASES.get(k_b, k_b) in ("crates", "cashcrate", "rocketpart", "logs", "crates_sink"):
                xs += [max(210, x_b - 250), min(W - 210, x_b + 250)]
                cam["punch"] = None
        for a_l in actors:                                              # wer umfällt oder liegt, ist so breit wie sonst hoch: ganz im Bild lassen
            if a_l.get("action") in ("fall", "sleep"):
                xs += [a_l["x1"] - 200, a_l["x1"] + 60]
                cam["punch"] = None                                         # kein Sprung auf den Kopf – der läge dann am Bildrand
                if a_l.get("action") == "sleep" and place == "bedroom":    # im Bett liegt die Figur fest bei x=300 (Kopf links am Kissen), egal wo sie laut Drehbuch steht: Bett samt Kopf im Bild
                    xs = [x_s for x_s in xs if x_s not in (a_l["x1"], a_l["x0"], a_l["x1"] - 200, a_l["x1"] + 60)] + [BED_SPAN[0], BED_SPAN[1]]
                    scene["_no_cut"] = True                                 # kein Gegenschnitt: gespiegelt und näher schnitt er die Liegende am Rand ab
        for a_l in actors:                                              # Langhantel über dem Kopf (stage._exo_story): samt Scheiben im Bild, kein Sprung auf den Kopf
            if a_l.get("lift"):
                xs += [a_l["x1"] - 170, a_l["x1"] + 170]
                cam["punch"] = None
        for k_b, x_b in props:                                          # Ballon am Boden (Stoffberg, Gondel): ganz im Bild lassen, kein Sprung auf den Kopf
            if extras.PROP_ALIASES.get(k_b, k_b) in extras.BALLOON_KINDS:
                xs += [max(210, x_b - 260), min(W - 210, x_b + 190)]
                cam["punch"] = None
        span = max(xs) - min(xs) + 420                                  # Breite der Gruppe samt Armen
        cam.update(tight=True, zt=max(1.0, min(1.42, W / span)), fx=(max(xs) + min(xs)) / 2)
    if actors and all(a_g["kind"] in LONG_KINDS for a_g in actors) and not scene.get("float") and place != "highsky" and \
            (place != "underwater" or all(a_g["kind"] in TINY_KINDS for a_g in actors)):
        cam["ay"] = 1450.0                                                  # nur Tiere am Boden: Die Kamera zoomt um einen Punkt unter der Bodenlinie, die Füße rücken dabei nach oben – der Fixpunkt oben schob Bärtierchen und Löwe sonst in die Untertitel (Video 137)
    if (scene.get("_balloon") and isinstance(scene.get("overlay"), dict)) or scene.get("_probe"):
        cam["punch"] = None                                                 # kein Sprung ins Bild: der Ballon wüchse sonst unter das Schild
    cam["opener"] = index == 0
    cam["move"] = scene.get("cam_move") or ("push", "pan_r", "pull", "pan_l", "push", "pull")[index % 6]
    if moving or str(scene.get("shot") or "") == "close":
        cam["move"] = "push" if index % 2 else "pull"     # wer durchs Bild läuft oder groß im Bild ist: kein zusätzlicher Schwenk
    cam_flat = {"flat": True, "dir": cam["dir"], "drift": cam["drift"], "opener": index == 0, "move": "push" if index % 2 else "pull"}
    cut_t, cut_kind, named = _cut_plan(scene, shot, gfx or ins or mir, moving, ov_tall or ov_kind == "counter", place, actors, props, dur, cam, index)   # großer Zähler mitten im Bild: kein Schnitt auf die Großaufnahme – die Zahl läge auf dem Gesicht (Video 186)
    sfx = []                                  # Ton-Ereignisse dieser Szene (Sekunden ab Szenenbeginn) für render.py / sound.py
    if mir:
        if mir in ("monster", "void"):
            sfx.append((0.1, "hit"))
        elif mir == "snap":
            sfx.append((min(1.1, dur * 0.35), "swish"))
    elif not (gfx or ins):
        for pi, (k_p, _) in enumerate([p for p in props if extras.PROP_ALIASES.get(p[0], p[0]) not in extras.FRONT][:3]):
            sfx.append((0.06 + 0.12 * pi, "pop"))           # Dinge springen ins Bild
        for a_s in actors:
            if a_s["action"] in ("shocked", "scared"):
                sfx.append((0.04, "hit"))
            elif a_s["action"] in ("jump", "happy", "cheer"):
                sfx.append((0.1, "pop"))
            elif a_s["action"] == "fall":
                sfx.append((0.3, "boom"))
        for st, gname in (lead.get("gplan") or []) if lead else []:
            if gname == "shock":
                sfx.append((st + 0.12, "hit"))
            elif gname == "count":
                sfx.append((st + 0.15, "tick"))
            elif gname == "happy":
                sfx.append((st + 0.1, "ding"))
        if cut_t is not None:
            sfx.append((cut_t, "shutter" if cut_kind == "insert" else "swish"))
    elif gfx:
        sfx.append((0.35, "ding" if str(gfx.get("type")) in ("number", "score", "round", "badge") else "pop"))
    scene["_sfx"] = [(round(t_s, 3), r_s) for t_s, r_s in sfx if 0 <= t_s < dur]
    mood_s = str(scene.get("mood") or "").lower()
    party = bool(re.search(PARTY_RE, str(scene.get("text") or "").lower())) or (str(scene.get("crowd") or "") == "cheer" and crowd_ok(scene))
    fx_opt = {"crowd": scene.get("crowd") if crowd_ok(scene) else "", "mood": mood_s, "confetti": party,   # Konfetti nur, wenn gefeiert wird – nicht in jeder fröhlichen Szene (Klinik, Büro) "spec": places.spec_of(backdrop(scene)), "sky": sky_m,
              "win": scene.get("_win"), "count": scene.get("_count"), "neon": neon_look, "float": str(scene.get("float") or ""), "blocks": bool(scene.get("_blocks")),
              "noir": str(scene.get("look") or "") == "noir",
              "aloft": bool(scene.get("aloft")), "low": bool(scene.get("low")), "no_traffic": bool(scene.get("no_traffic") or scene.get("dark_city"))}
    gfx_cut = CHAPTER_MAX if gfx and str(gfx.get("type")) == "chapter" and dur > CHAPTER_MAX + 1.2 and actors and not hyper.handles(gfx) else 0.0   # Kapitel-Tafel („3 · TAG DREI“) über einem langen Satz: nach gut zwei Sekunden weiter mit der Figur am Ort – vorher stand die Zahl fünf Sekunden vor Schwarz (Video 219)
    if gfx_cut:
        scene["_sfx"] = scene["_sfx"] + [(round(gfx_cut, 3), "swish")]
    ff = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
                           "-crf", "17", "-pix_fmt", "yuv420p", str(out)], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for fidx in range(n_frames):
            t = fidx / FPS
            if mir:
                frame = _mirror_frame(scene, cast, t, dur)
                if still is not None and fidx == min(n_frames - 1, FPS):
                    frame.save(still, quality=92)
                ff.stdin.write(_camera(frame.convert("RGB"), t, dur, cam_flat).tobytes())
                continue
            if (gfx and not (gfx_cut and t >= gfx_cut)) or ins:
                frame = (graphics.frame(gfx, t, min(dur, gfx_cut) if gfx_cut else dur, str(scene.get("mood") or "").lower()) if gfx
                         else _insert_frame(ins, t, dur, str(scene.get("mood") or "").lower(), bool(has_ov), neon_look))
                if still is not None and fidx == min(n_frames - 1, FPS):
                    frame.save(still, quality=92)
                ff.stdin.write(_camera(frame.convert("RGB"), t, dur, cam_flat).tobytes())
                continue
            if cut_t is not None and t >= cut_t:            # Schnitt mitten im Satz: auf das genannte Ding oder die Großaufnahme der Figur
                tc = t - cut_t
                if cut_kind == "flip":                      # Gegenschnitt: gespiegelt, näher dran, andere Fahrt
                    frame = _frame(bg, place, night, scale, actors, props, weather, t, dur, words, t0, place == "bedroom", "", big, fx_opt)
                    frame = frame.transpose(Image.FLIP_LEFT_RIGHT)
                    cam2 = dict(cam, fx=W - float(cam.get("fx", 540)), punch=None, opener=False, zt=min(1.55, float(cam.get("zt", TIGHT_Z)) + 0.15),
                                tight=True, move="pan_l" if cam.get("dir", 1) > 0 else "pan_r")
                    if still is not None and fidx == min(n_frames - 1, FPS):
                        frame.save(still, quality=92)
                    ff.stdin.write(_camera(frame.convert("RGB"), tc, dur - cut_t, cam2).tobytes())
                    continue
                frame = (_insert_frame(named[:1], tc, dur - cut_t, mood_s, bool(has_ov), neon_look) if cut_kind == "insert"
                         else _frame(bg, place, night, scale, actors, props, weather, t, dur, words, t0, place == "bedroom", "close", big, fx_opt))
                if still is not None and fidx == min(n_frames - 1, FPS):
                    frame.save(still, quality=92)
                ff.stdin.write(_camera(frame.convert("RGB"), tc, dur - cut_t, cam_flat).tobytes())
                continue
            frame = _frame(bg, place, night, scale, actors, props, weather, t, dur, words, t0, place == "bedroom", shot, big, fx_opt)
            if still is not None and fidx == min(n_frames - 1, FPS):
                frame.save(still, quality=92)
            ff.stdin.write(_camera(frame.convert("RGB"), t, dur, cam_flat if shot == "close" else cam).tobytes())
        ff.stdin.close()
        err = ff.stderr.read().decode()[-500:]
        if ff.wait() != 0:
            raise RuntimeError("ffmpeg (Toon): " + err)
    finally:
        if ff.poll() is None:
            ff.kill()


def poster_hero(topic, scenes, cast=None, avoid=()):
    """Welches Tier/Wesen gehört aufs Titelbild? Erst das, was der Titel/das Thema nennt, dann das Wesen, das in den Szenen am
    häufigsten auftritt – die Besetzungsliste der Text-KI nur, wenn ihr Wesen auch wirklich in einer Szene vorkommt. Was schon
    auf dem letzten Titelbild war (avoid), kommt nur, wenn es keine andere Wahl gibt."""
    import re as _re
    low = str(topic or "").lower()
    if _re.search(HYBRID_RE, topic_head(low)):
        return "chimera"                                  # Misch-Wesen-Video: das gebaute Wesen ist das Gesicht des Videos
    if _re.search(FROSTFROG_RE, low):
        return "woodfrog"
    if _re.search(ANGLER_RE, low) or sum(1 for sc in scenes or [] if isinstance(sc, dict) and any(isinstance(a, dict) and a.get("kind") == "angler" for a in sc.get("actors") or [])) >= 3:
        return "angler"                                   # Anglerfisch-Video: der Fisch mit der Leuchtangel aufs Titelbild – kein Goldfisch (Video 222)
    named = [k for pat, k in TOPIC_CREATURES if _re.search(pat, low)]
    sk = _sea_kind(low, bool(_re.search(SEA_TOPIC_RE, low)))
    named += [sk] if sk else []
    counts = {}
    for sc in scenes or []:
        for a in (sc.get("actors") or []) if isinstance(sc, dict) else []:
            k = str((a or {}).get("kind") or "").lower() if isinstance(a, dict) else ""
            if k in extras.CREATURES:
                counts[k] = counts.get(k, 0) + 1
    counts = {k: n for k, n in counts.items() if n >= 3 or n * 4 >= len(scenes or [])}  # ein Wesen, das nur in ein, zwei Szenen vorkommt (der Affe für „behaarte Vorfahren“ im Musik-Video), ist nicht das Gesicht des Videos
    if _re.search(r"gehirn|\bhirn", topic_head(low)):     # Thema „dein Gehirn“ und das Gehirn spielt als Figur mit (Art steht nur in der Besetzung): es gehört aufs Titelbild, nicht die Zuschauer-Figur
        brain_ids = {str(i_) for i_, c_ in (cast or {}).items() if isinstance(c_, dict) and str(c_.get("kind") or "").lower() == "brain"}
        n_brain = sum(1 for sc in scenes or [] if isinstance(sc, dict)
                      and any(isinstance(a, dict) and (str(a.get("id") or "") in brain_ids or str(a.get("kind") or "").lower() == "brain") for a in sc.get("actors") or []))
        if n_brain >= 3:
            return "brain"
    ranked = [k for k in named if k in extras.CREATURES] + sorted(counts, key=lambda k: -counts[k])
    ranked = list(dict.fromkeys(ranked))
    named = [k for k in named if k in extras.CREATURES]
    if named:
        return named[0]                                   # das Tier, das Titel/Thema nennen, gehört immer aufs Titelbild – auch wenn es beim letzten Video (einer verworfenen Fassung) schon dort war
    fresh = [k for k in ranked if k not in avoid]
    return (fresh or ranked or [""])[0]


POSTER_PALETTES = [((255, 205, 60), (250, 160, 40), (255, 250, 220)),     # Gelb-Orange
                   ((70, 200, 255), (30, 120, 220), (220, 245, 255)),     # Himmelblau
                   ((255, 110, 170), (200, 50, 140), (255, 225, 240)),    # Pink
                   ((120, 230, 140), (30, 160, 110), (225, 255, 230)),    # Grün
                   ((255, 140, 90), (220, 60, 60), (255, 230, 210))]      # Rot-Orange
POSTER_DARK = [((70, 40, 150), (38, 20, 96), (190, 150, 255)), ((20, 70, 110), (10, 30, 60), (130, 220, 255))]


def poster(spec: dict, cast: dict, out: Path, topic=""):
    """Eigens gestaltetes Titelbild (kein Bild aus dem Video): Strahlen-Hintergrund, das Ding des Videos riesig als Aufkleber,
    darunter die Hauptfigur groß im Anschnitt mit starkem Gefühl. Der Text kommt danach ins obere Drittel."""
    import re as _re
    from PIL import ImageFilter
    dark = str(spec.get("time") or "").lower() in ("night", "nacht") or str(spec.get("mood") or "").lower() in ("scary", "panic")
    pal = int(spec.get("palette") or 0)                  # Farbwelt wechselt von Video zu Video (gleiches Bild zweimal fällt sonst auf)
    c0, c1, glow = (POSTER_DARK[pal % len(POSTER_DARK)] if dark else POSTER_PALETTES[pal % len(POSTER_PALETTES)])
    frame = Image.new("RGB", (W, H), c1)
    d = ImageDraw.Draw(frame, "RGBA")
    cx, cy = 600, 960
    for i in range(18):                                   # Strahlen
        a0, a1 = math.radians(i * 20 - 4), math.radians(i * 20 + 6)
        d.polygon([(cx, cy), (cx + math.cos(a0) * 2600, cy + math.sin(a0) * 2600), (cx + math.cos(a1) * 2600, cy + math.sin(a1) * 2600)], fill=c0)
    halo = Image.new("L", (W // 6, H // 6), 0)
    ImageDraw.Draw(halo).ellipse((cx / 6 - 90, cy / 6 - 90, cx / 6 + 90, cy / 6 + 90), fill=200)
    halo = halo.filter(ImageFilter.GaussianBlur(26)).resize((W, H), Image.BILINEAR)
    frame = Image.composite(Image.new("RGB", (W, H), glow), frame, halo)
    vig = Image.new("L", (W // 6, H // 6), 150)
    ImageDraw.Draw(vig).ellipse((-40, -10, W // 6 + 40, H // 6 + 10), fill=0)
    frame = Image.composite(Image.new("RGB", (W, H), (20, 10, 40)), frame, vig.filter(ImageFilter.GaussianBlur(40)).resize((W, H), Image.BILINEAR))

    def sticker(im, max_w, max_h, x, y, tilt=0):
        f = min(max_w / im.width, max_h / im.height)
        im = im.resize((max(2, int(im.width * f)), max(2, int(im.height * f))), Image.LANCZOS)
        pad = 60
        big = Image.new("RGBA", (im.width + pad * 2, im.height + pad * 2), (0, 0, 0, 0))
        big.paste(im, (pad, pad), im)
        edge = big.split()[3].filter(ImageFilter.MaxFilter(31))
        st = Image.new("RGBA", big.size, (0, 0, 0, 0))
        st.paste((255, 255, 255, 255), (0, 0), edge)
        st.paste(big, (0, 0), big)
        st = st.rotate(tilt, resample=Image.BICUBIC, expand=True)
        sh = Image.new("RGBA", st.size, (0, 0, 0, 0))
        sh.paste((0, 0, 0, 120), (0, 0), st.split()[3])
        frame.paste(sh, (int(x - st.width / 2 + 18), int(y - st.height / 2 + 26)), sh)
        frame.paste(st, (int(x - st.width / 2), int(y - st.height / 2)), st)

    # 1) das Ding, um das es geht
    hero = None
    kind = str(spec.get("kind") or "").lower()
    cast_kind = next((str(v.get("kind")).lower() for v in (cast or {}).values() if isinstance(v, dict) and v.get("kind")), "")
    low = topic_head(topic).lower()                      # nur der Kern des Themas – in den Vorgaben dahinter steht auch, was NICHT vorkommen soll („kein Panzerglas“)
    keys = [extras.PROP_ALIASES.get(str(p.get("type") if isinstance(p, dict) else p).lower(), str(p.get("type") if isinstance(p, dict) else p).lower())
            for p in (spec.get("props") or [])]
    keys += [k for pat, k in _lib_props() + TEXT_PROPS if _re.search(pat, low)]
    hk = str(spec.get("hero_kind") or "").lower()
    if _re.search(FROZEN_RE, low) and _re.search(FROZEN_SEA_RE, low):
        keys, hk = ["ship_ice"], ""                       # zugefrorenes Meer: das eingefrorene Schiff aufs Titelbild – nicht der Fisch aus einer Nebenszene
    if hk in extras.CREATURES and (_sea_named(low) == hk or any(k_ == hk and _re.search(pat, low) for pat, k_ in TOPIC_CREATURES + ANY_CREATURES)):
        keys = []                                         # das Thema nennt das Tier: Es gehört aufs Titelbild, kein Gegenstand aus dem Text
    if hk in TINY_KINDS:
        keys = []                                         # Video über einen Winzling: das Tier aufs Titelbild – nicht ein Gegenstand aus dem Vorschlag der Text-KI (Videos 138/139: ein Holzfass für „Tönnchen“)
    if hk == "fridge":
        keys = []                                         # der Kühlschrank ist eine Figur der Geschichte: mit Gesicht aufs Titelbild, nicht als Gerät
    if _re.search(HYBRID_RE, low):
        keys, hk = [], "chimera"                          # Misch-Wesen-Video: das gebaute Wesen aufs Titelbild – nicht ein Herz aus den Requisiten (Video 153)
        spec["hero_kind"] = "chimera"
    frost_f = bool(_re.search(FROSTFROG_RE, str(topic or "").lower()) or (_re.search(r"fr[oö]sch", low) and _re.search(FF_FREEZE_RE, low)))
    if frost_f:
        keys, hk = [], "woodfrog"                         # Waldfrosch-Video: der Frosch im Eisblock aufs Titelbild – nicht ein Eisbrocken ohne Tier (Video 199)
        spec["hero_kind"] = "woodfrog"
    for k in keys:
        if k in extras.PROPS:
            lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            extras.draw_prop(lay, k, 540, 1.2)
            box = lay.getbbox()
            if box:
                hero = lay.crop(box)
                break
    if spec.get("hero_kind") is not None:                # von poster_hero gewählt (Titel/Szenen) – nicht blind die Besetzungsliste
        cast_kind = str(spec.get("hero_kind") or "")
    if hero is None and (kind in extras.CREATURES or cast_kind in extras.CREATURES):
        res = extras.creature(kind if kind in extras.CREATURES else cast_kind, 0.4, 1, 0.0 if frost_f else 0.6, "", 1.6, "frozen" if frost_f else "")
        if res and res[0].getbbox():
            hero = res[0].crop(res[0].getbbox())
            if frost_f:                                   # halb durchsichtiges Eis wird auf dem weißen Aufkleber-Grund grau: deckend auf Eisblau legen
                base_f = Image.new("RGBA", hero.size, (0, 0, 0, 0))
                base_f.paste((204, 232, 250, 255), (0, 0), hero.split()[3].point(lambda a_: 255 if a_ > 20 else 0))
                base_f.alpha_composite(hero)
                hero = base_f
    if mirror_story([], str(topic or "")):                # Spiegel-Video: der Spiegel mit der Fratze aufs Titelbild – nicht eine Kerze aus den Requisiten (Video 204)
        aid_m = next((k for k, v in (cast or {}).items() if isinstance(v, dict) and not v.get("kind")), None)
        hero = mirror_sticker(rig.Look.from_spec((cast or {}).get(aid_m) if aid_m else {}, aid_m or "", list(cast).index(aid_m) if aid_m else None))
    if hero is None and _re.search(r"smartphone|\bhandy", low):   # Handy-Thema ohne Motiv (Video 185: nur die Figur vor Strahlen): das leuchtende Handy als Aufkleber
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        extras.draw_prop(lay, "display", 540, 1.2)
        if lay.getbbox():
            hero = lay.crop(lay.getbbox())
    # 2) die Hauptfigur, groß im Anschnitt
    aid = spec.get("actor") if isinstance((cast or {}).get(spec.get("actor")), dict) and not cast[spec.get("actor")].get("kind") else \
        next((k for k, v in (cast or {}).items() if isinstance(v, dict) and not v.get("kind")), None)
    look = rig.Look.from_spec((cast or {}).get(aid) if aid else {}, aid or "", list(cast).index(aid) if aid and aid in (cast or {}) else None)
    if re.search(EXO_RE, topic_head(low)):                # Exoskelett-Video: die Figur trägt es auch auf dem Titelbild
        import dataclasses
        look = dataclasses.replace(look, outfit="exo")
    pose, _ = rig.pose_at("shocked", 1.0, 3.0, str(spec.get("emotion") or "shocked"), 0.8, 3)
    pose.lift = 0
    side = -1 if pal % 2 else 1                           # jedes zweite Titelbild gespiegelt: Figur rechts, Motiv links
    fig, fx, fy = rig.draw(look, pose, side, 2.3)
    if hero is not None:
        if side < 0:
            hero = hero.transpose(Image.FLIP_LEFT_RIGHT)
        n_txt = len(str(spec.get("text") or "").split())  # zwei Wörter stehen in zwei, drei und mehr in drei Zeilen: das Motiv rückt tiefer und wird etwas kleiner (der Text lag sonst über dem Kopf des Gehirns)
        sticker(hero, 700, 560 if n_txt >= 3 else 600 if n_txt == 2 else 640, 540 + 100 * side, 1170 if n_txt >= 3 else 1050 if n_txt == 2 else 930, -6 * side)
        frame.paste(fig, (int(540 - 290 * side - fx), int(2330 - fy)), fig)
    else:
        frame.paste(fig, (int(540 - fx), int(2200 - fy)), fig)
    frame.save(out, quality=93)


def cover(spec: dict, cast: dict, out: Path):
    """Titelbild im Stil der Engine: Ort + große Figur mit starkem Gefühl + optional Requisite. Text kommt später darüber."""
    scene = {"place": spec.get("place") or "park", "backdrop": spec.get("backdrop"), "time": spec.get("time"), "weather": spec.get("weather"),
             "props": spec.get("props") or [],
             "actors": [{"id": spec.get("actor") or next(iter(cast), "held"), "kind": spec.get("kind") or "",
                         "action": spec.get("action") or "shocked", "emotion": spec.get("emotion") or "shocked",
                         "emote": " ", "pos": "center"}]}
    place, night, _, actors, props, weather = _prepare(scene, cast)
    frame = _frame(places.background(backdrop(scene), night), place, night, 1.25, actors, props, weather, 1.4, 3.0, (), 0.0, False, "", 1.35,
                   {"crowd": spec.get("crowd"), "mood": "", "spec": places.spec_of(backdrop(scene)),
                    "sky": places.sky_mask(backdrop(scene), night)})
    # so beschneiden, dass die Figur groß in der unteren Bildhälfte sitzt und das obere Drittel für den Text frei bleibt
    frame = frame.crop((135, 0, 945, 1440)).resize((W, H), Image.LANCZOS)
    frame.save(out, quality=93)
