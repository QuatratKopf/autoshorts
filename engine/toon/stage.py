"""Bühne: setzt Figuren, Tiere und Requisiten auf einen Ort und rendert die Szene Bild für Bild (30 fps) als Video.
Figuren bewegen sich (gehen, rennen, springen …), blinzeln und bewegen den Mund passend zur Sprecherstimme;
dazu Wetter, Gefühls-Symbole und kleine Bewegungen im Hintergrund."""
import math
import subprocess
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from . import extras, graphics, places, rig
from .. import hyper

W, H, FPS = 1080, 1920, 30
SCALE = 1.08            # Figuren bewusst kleiner: die Szene steht im Mittelpunkt
POS = {"left": 250, "center": 540, "right": 830, "offleft": -260, "offright": 1340,
       "links": 250, "mitte": 540, "rechts": 830}
TALL_OV = ("phone", "checklist", "note")
NO_FURNITURE = ("restaurant", "bathroom", "hallway", "supermarket", "supermarket_empty", "station", "basement", "attic", "hospital", "serverroom")
MAIN_IDS = ("du", "ich", "held", "hero", "main", "erzähler", "narrator", "a0")


def _x(v, default):
    if isinstance(v, (int, float)):
        return float(v)
    return float(POS.get(str(v or "").lower().strip(), default))


def _mouth(t_abs, words):
    """Mund-Öffnung 0..1: während eines gesprochenen Wortes auf/zu, sonst geschlossen."""
    for _, s, e in words:
        if s <= t_abs <= e:
            return 0.25 + 0.75 * abs(math.sin((t_abs - s) * 17))
        if s > t_abs:
            break
    return 0.0


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
    if sc["shot"] not in ("event", "close", "insert", "graphic"):
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
            for k in ("action", "emotion", "emote", "kind", "hold", "facing"):
                c[k] = word(a.get(k)) if k == "emote" else word(a.get(k)).lower()
            if isinstance(a.get("look"), dict):               # Nebenfiguren der Regie bringen ihr Aussehen mit
                c["look"] = {k: v for k, v in a["look"].items() if k in ("shirt", "hair", "hat", "glasses", "skin") and isinstance(v, (str, bool))}
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


def _prepare(scene, cast):
    scene = sanitize(scene)
    cast = cast if isinstance(cast, dict) else {}
    place = places.resolve(backdrop(scene))
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
        x0 = _x(a.get("pos"), default_x[i])
        x1 = _x(a.get("to"), x0) if a.get("to") else x0
        action = str(a.get("action") or "idle").lower()
        if x1 != x0 and action not in ("walk", "run"):
            action = "walk"
        if action in ("walk", "run") and x1 == x0:       # ohne Ziel: von außen hereinkommen
            x0 = -260 if x0 <= 540 else 1340
        actors.append({"look": rig.Look.from_spec(spec, aid, list(cast).index(aid) if aid in cast else None), "kind": kind if kind in extras.CREATURES else "",
                       "hold": extras.held_key(a.get("hold")),
                       "action": action, "emotion": str(a.get("emotion") or "").lower(), "emote": a.get("emote") or "", "giant": bool(scene.get("giant")), "hero": bool(a.get("hero")), "say": str(a.get("say") or "") if isinstance(a.get("say"), str) else "",
                       "x0": x0, "x1": x1, "speaks": bool(a.get("speaks")), "seed": i * 5 + len(aid), "face": a.get("facing")})
    for i, a in enumerate(actors):     # zwei Figuren nie auf derselben Stelle
        for b in actors[:i]:
            if abs(a["x1"] - b["x1"]) < 200:
                a["x1"] = b["x1"] + (300 if b["x1"] < 600 else -300)
                if a["x0"] == b["x0"] or abs(a["x0"] - b["x1"]) < 200:
                    a["x0"] = a["x1"]
    if actors and not any(a["speaks"] for a in actors):
        actors[0]["speaks"] = len(actors) == 1
    for a in actors:   # passende Symbole automatisch, wenn das Drehbuch keine nennt
        if not a["emote"]:
            a["emote"] = {"shocked": "!", "scared": "!", "think": "?", "angry": "anger"}.get(a["action"]) or \
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
        if isinstance(p, dict) and str(scene.get("shot") or "") != "insert" and \
                extras.PROP_ALIASES.get(str(p.get("type")).lower(), str(p.get("type")).lower()) in PLACE_HAS.get(place, ()):
            continue                                              # steht an diesem Ort schon
        if isinstance(p, dict) and place not in places.OUTDOOR and place not in ("space", "plain") and \
                extras.PROP_ALIASES.get(str(p.get("type")).lower(), str(p.get("type")).lower()) in extras.SKY and str(scene.get("shot") or "") != "insert":
            if place in places.WINDOWS and len(win) < 2:          # was am Himmel passiert, sieht man drinnen durchs Fenster
                win.append(extras.PROP_ALIASES.get(str(p["type"]).lower(), str(p["type"]).lower()))
            continue                                              # Sonne, Mond, Wolken stehen nicht im Zimmer
        if isinstance(p, dict) and place not in places.OUTDOOR and place not in ("space", "plain", "cave", "underwater") and \
                extras.PROP_ALIASES.get(str(p.get("type")).lower(), str(p.get("type")).lower()) in ("fire", "volcano", "tornado", "car", "bus", "truck", "house", "tree", "meteor", "wave") \
                and str(scene.get("shot") or "") != "insert":
            continue                                              # gehört nach draußen, nicht ins Zimmer
        if isinstance(p, dict) and place not in places.OUTDOOR and str(p.get("type")).lower().startswith("lib_") \
                and extras.REAL_M.get(str(p.get("type")).lower(), extras.SIZES.get(str(p.get("type")).lower(), (0,))[0]) > 2.6 and str(scene.get("shot") or "") != "insert":
            continue                                              # Gelerntes, das höher ist als ein Zimmer (Turm, Gebäude), steht nicht im Raum
        if isinstance(p, dict) and p.get("type"):
            taken = [q["x1"] for q in actors] + [q[1] for q in props]
            free = [c for c in (830, 250, 540, 930, 150) if all(abs(c - tx) > 200 for tx in taken)] or [830]   # nie am Rand: Dinge haben eine Mindestgröße
            kind = str(p["type"]).lower().strip()
            fit = extras.prop_fit(kind)
            if fit and fit[1] < 1200 and not p.get("pos"):      # Großes (Auto, Haus, Baum) steht weiter hinten und darf mittig stehen
                free = [c for c in (760, 320, 540) if all(abs(c - q[1]) > 300 for q in props)] or [760]
            props.append((kind, _x(p.get("pos"), free[0]) if p.get("pos") else free[0]))
            p_given.append(bool(p.get("pos")))
    if event:
        props = [(k, 600 if (i == 0 and not p_given[i]) else x) for i, (k, x) in enumerate(props)]
    return place, night, scale, actors, props, str(scene.get("weather") or "").lower()


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
        look = rig.Look.from_spec({"shirt": CROWD_SHIRTS[(i * 3 + 1) % len(CROWD_SHIRTS)], "hat": ("", "", "cap", "beanie", "")[i % 5],
                                   "hat_color": CROWD_SHIRTS[(i * 7) % len(CROWD_SHIRTS)], "hair": ("", "long", "", "bun")[i % 4],
                                   "skin": ("weiß", "hell", "mittel", "dunkel")[i % 4]})
        people.append((gy, look, rnd.random(), rnd.choice((-1, 1)), i))
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
             "livingroom": ("tv",), "forest": ("tree",), "park": ("tree",), "camp": ("tent", "fire"), "street": ("streetlamp", "house"),
             "village": ("house",), "restaurant": ("table",), "hallway": (), "serverroom": ("computer", "shelf"),
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
        if nat and not (table and _on_table(key)) and nat * f < MIN_PROP_PX:
            f = MIN_PROP_PX / nat                         # Kleines (Spinne, Chip, Schuh) erkennbar groß – sonst ist das Thema nur ein Punkt
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
    if big <= 1.01 or key in ("aurora", "lightning", "crack", "flood", "wave", "eclipse", "ship"):
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


def _light(frame, kind, xs):
    """Legt Licht und Schatten über das fertige Bild (Maske in kleiner Auflösung, weich, zwischengespeichert)."""
    key = (kind, tuple(sorted(int(x) // 30 for x in xs)) if kind in ("spot", "night") else ())
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
    if place == "space" and any(extras.PROP_ALIASES.get(k, k) in ("sun", "moon", "earth") for k, _ in props):
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
            _prop_many(frame, kind, x, t, big, (opt.get("count") or {}).get(extras.PROP_ALIASES.get(kind, kind), 1), indoor,
                       grow=max(0.02, extras._pop(t, 0.06 + 0.12 * pi, 0.32)) if opt.get("pop_in", True) else 1.0)
    if opt.get("crowd"):
        _crowd(frame, opt["crowd"], t, night, 1090, 9999, **ckw)
    close = shot == "close" and bool(actors)
    if close:              # Großaufnahme: Kulisse vergrößert und leicht unscharf (Tiefenschärfe), die Figur scharf und groß davor
        lead = next((a for a in actors if a["speaks"]), actors[0])
        hw = CLOSE_BG / 2
        c_x = max(hw, min(W - hw, lead["x1"]))
        top = places.GROUND - 780
        frame = frame.crop((int(c_x - hw), top, int(c_x + hw), top + int(CLOSE_BG * H / W))).resize((W, H), Image.BILINEAR)
        frame = frame.filter(ImageFilter.GaussianBlur(3))
        frame = _light(frame, _light_kind(place, night, opt.get("mood"), [540]), [540])
        scale = scale * CLOSE_ZOOM
    over = frame
    od = ImageDraw.Draw(frame, "RGBA")
    focus = 540.0
    xs_now = []
    for a in sorted(actors, key=lambda q: q["speaks"]):
        moving = a["x1"] != a["x0"]
        speed = 360 if a["action"] == "walk" else 680
        move_t = min(dur * 0.7, abs(a["x1"] - a["x0"]) / speed) if moving else 0
        arrived = moving and t >= move_t
        x = a["x1"] if arrived else (a["x0"] + (a["x1"] - a["x0"]) * _ease(t / move_t) if moving else a["x0"])
        if close:                                      # die Hauptfigur steht mittig, andere im selben Abstand daneben
            x = 540 + (x - lead["x1"]) * W / CLOSE_BG
        xs_now.append(x)
        mouth = _mouth(t0 + t, words) if a["speaks"] else 0.0
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
        landed = a_hit if a_hit is not None and (landed is None or a_hit > landed) else landed
        head_y = gy - 505 * scale
        if a["kind"]:
            hop = abs(math.sin(t * 9)) * 16 if (moving and not arrived) else 0
            ksz = 1.0 if a.get("giant") else HERO_SIZE.get(a["kind"], 0.8) if a.get("hero") else CREATURE_SIZE.get(a["kind"], 1.0)   # Tiere in echter Größe – als Hauptfigur des Videos groß
            res = extras.creature(a["kind"], t + a["seed"], facing, mouth, a["emotion"] or
                                  ("shocked" if a["action"] in ("shocked", "scared") else ""), scale * 0.9 * ksz)
            if res:
                im, fx, fy, fly = res
                if not fly:
                    _shadow(frame, int(x), gy, int(120 * scale * ksz))
                frame.paste(im, (int(x - fx), int(gy - fy - hop * ksz - a_lift)), im)
                head_y = gy - 430 * scale * ksz - a_lift
        else:
            action = a["action"]
            tt = t
            if arrived:
                action, tt = ("talk" if a["speaks"] else "idle"), t - move_t
            elif action == "idle" and a["speaks"]:
                action = "talk"
            if flo:                                           # schwerelos treiben – nach dem Absturz liegt die Figur am Boden
                action, tt = ("fall", a_hit) if a_hit is not None else ("float", t)
            pose, _ = rig.pose_at(action, tt, dur, a["emotion"], mouth, a["seed"])
            if a.get("hold") and action not in ("run", "sleep", "fall", "jump", "dance", "wave", "shake") and not pose.lying:
                pose.arm_r, pose.fore_r = (62, 50) if a["hold"] in ("phone", "map", "flashlight", "radio", "bottle") else (8, 4)
                if a["hold"] in ("umbrella", "sign"):
                    pose.arm_r, pose.fore_r = 40, 100
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
            if pose.lying and in_bed and not close:                          # im Schlafzimmer liegt die Figur im Bett
                x, gy = 300, places.GROUND - 150
            elif pose.lying:                                   # sonst liegt sie auf dem Boden auf, nicht darüber
                fy -= 62 * scale
            _shadow(frame, int(x), gy, int(72 * scale * (1 - min(0.5, max(0, pose.lift + a_lift) / 400))))
            gy0, gy = gy, gy - int(a_lift)
            frame.paste(im, (int(x - fx), int(gy - fy)), im)
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
        extras.draw_mood(over, opt["mood"], t)
    if not close:
        frame = _light(frame, _light_kind(place, night, opt.get("mood"), xs_now), xs_now)
    if landed is not None and landed < 0.5:      # Aufschlag: das Bild wackelt kurz
        k = 1 - landed / 0.5
        dx, dy = int(math.sin(t * 61) * 22 * k), int(math.cos(t * 53) * 26 * k)
        frame = frame.transform(frame.size, Image.AFFINE, (1, 0, dx, 0, 1, dy), resample=Image.NEAREST)
    return frame


CLOSE_BG = 660         # Großaufnahme: Breite des Kulissen-Ausschnitts (Zoom 1,6) …
CLOSE_ZOOM = 2.6       # … die Figur selbst wird 2,6-mal so groß gezeichnet (scharf, nicht hochgerechnet) …
CLOSE_FOOT = H + 230   # … und steht unterhalb des Bildrands: Kopf und Oberkörper füllen das Bild


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
        if v is None or (w.lower().strip(".,") in ("ein", "eine", "einen", "einem", "einer") and
                         (i + 1 >= len(ws) or ws[i + 1].lower().strip(".,;:!?") not in _SCALE)):
            continue
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
    if not fig and _re.search(r"ganze stadt|stadtviertel|von oben|häuserblock|stadtweit|ganze viertel|millionenstadt|in der stadt", low):
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
    for w in str(text or "").replace("-", " ").split():
        n = _number(w)
        if n is not None:
            nums.append(n)
    if not nums:
        return False
    if "komma" in str(text or "").lower() and float(int(v)) in nums:
        return True                                       # „vier Komma vier Milliarden“
    return any(abs(n - v) < 1e-6 or abs(n * 1000 - v) < 1e-6 or abs(n * 1e6 - v) < 1e-3 or abs(n * 1e9 - v) < 1 for n in nums)


FIGURE_GFX = ("number", "badge", "houses", "share", "compare", "distance", "days", "pulse", "calendar", "timer")
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


def direct(scenes, times, topic="", style="", look=""):
    """Kleine Regie über das ganze Video: sorgt für Abwechslung, wenn das Drehbuch mehrmals hintereinander dieselbe
    Einstellung vorgibt (gleicher Ort, gleiche Figur, nur Reden) – andere Position, Nahaufnahme oder Hereinkommen."""
    prev_place, same, changes, prev_bd = None, 0, 0, None
    import re as _re0
    power_out = False
    last_id = None
    maps_used = 0
    spooky = str(style or "").lower() in ("grusel", "mysterien", "horror")
    used = {}
    fig_prev, inserts, counters = False, 0, 0
    topic_things = [k for pat, k in _lib_props() + TEXT_PROPS if _re0.search(pat, str(topic or "").lower()) and extras.prop_fit(k)][:2]
    topic_any = [k for pat, k in _lib_props() + TEXT_PROPS if _re0.search(pat, str(topic or "").lower())][:2]   # auch Himmel/Natur
    topic_place = _hint(topic)
    topic_place = topic_place if isinstance(topic_place, str) and topic_place in TOPIC_PLACES else None
    stale, topic_ins, gfx = 0, 0, 0
    charts = 0
    neon = str(look or "").lower() == "neon"
    cur_hud = ""
    for i, (sc, (s0, e0)) in enumerate(zip(scenes, times)):
        sanitize(sc)
        if spooky:                                        # Grusel und Rätsel spielen im Dunkeln; Stimmung unheimlich, keine Passanten
            if not _re0.search(r"tagsüber|am tag\b|mittags|sonnenschein|am nächsten morgen|am morgen", sc["text"].lower()):
                sc["time"] = "night"
            if sc["mood"] in ("", "calm", "happy"):
                sc["mood"] = "scary"
            if sc["crowd"] in ("walk", "cheer"):
                sc["crowd"] = ""
        sc["props"] = [q for q in sc["props"] if (lambda k: k in extras.PROPS or k in extras.PROP_ALIASES or k in extras.HELD)(q["type"].lower())]
        low0 = sc["text"].lower()
        simile = sc["_simile"] = []
        for pat, k in TEXT_PROPS:                         # „wie ein Raketenstart“, „wie ein Vulkan“: ein Vergleich, kein Ding im Bild
            m = _re0.search(r"\bwie (?:bei |in |auf |von )?(?:ein\w* |der |die |das |dem |den )?(?:\w+ )?(?:" + pat + ")", low0)
            if m and not _re0.search(pat, low0[:m.start()] + " " + low0[m.end():]):
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
        if place in MAPS:                                 # Karte höchstens zweimal pro Video
            maps_used += 1
            if maps_used > 2:
                sc["place"] = place = "street"
        ov_c = sc.get("overlay") if isinstance(sc.get("overlay"), dict) else None
        if ov_c and str(ov_c.get("type") or "").lower() in graphics.TYPES and str(ov_c.get("type") or "").lower() != "phone":
            if not sc.get("graphic") and graphics.clean(ov_c):   # Grafik stand versehentlich als Einblendung im Drehbuch: als Grafik zeigen
                sc["graphic"], sc["shot"] = graphics.clean(ov_c), "graphic"
            sc["overlay"] = ov_c = None
        g0 = sc.get("graphic") if isinstance(sc.get("graphic"), dict) else None
        if g0 and g0.get("type") == "chart" and g0.get("value") and not spoken_number(_lead_number(g0["value"]), sc["text"]):
            g0.pop("value", None)                         # Kurve ja – aber keine Zahl, die der Sprecher nicht nennt
            if _re0.search(r"dollar|euro|%|prozent|mio|mrd|bio", str(g0.get("label") or "").lower()):
                g0.pop("label", None)
        if ov_c and str(ov_c.get("type") or "") == "counter" and not spoken_number(ov_c.get("value"), sc["text"]):
            sc["overlay"] = None                          # Zahl in der Einblendung, die der Sprecher gar nicht nennt: weg damit
        said_c = sc["text"] + " " + (str(scenes[i - 1].get("text") or "") if i and isinstance(scenes[i - 1], dict) else "")
        if g0 and g0.get("type") in FIGURE_GFX and unspoken_figures(g0, said_c):
            sc["graphic"], g0 = None, None                # Grafik mit einer Zahl, die niemand sagt („1.000.000 KARTEN“, „100 % KONTROLLE“): erfunden – weg
            sc["shot"] = "" if sc.get("shot") == "graphic" else sc.get("shot")
        if ov_c and sc.get("overlay") and str(ov_c.get("type") or "") in ("card", "counter", "note", "stamp") and unspoken_figures(ov_c, said_c):
            sc["overlay"] = None
        has_bd = isinstance(sc.get("backdrop"), dict) and (sc["backdrop"].get("elements") or sc["backdrop"].get("ground"))
        hint = None if has_bd else _hint(sc.get("text"))
        said = None if has_bd or place in MAPS else _said_place(sc.get("text"))
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
        if len(sc.get("props") or []) < 2 and str(sc.get("shot") or "") != "close" and places.resolve(sc.get("place")) not in MAPS:       # was der Satz nennt, ist auch zu sehen
            have = {extras.PROP_ALIASES.get(str(q.get("type")).lower(), str(q.get("type")).lower()) for q in (sc.get("props") or [])}
            for pat, kind in _lib_props() + TEXT_PROPS:
                if kind not in have and kind not in simile and _re0.search(pat, txt0):
                    if kind in OUTDOOR_THINGS and places.resolve(backdrop(sc)) not in places.OUTDOOR and not (
                            kind in extras.SKY and places.resolve(backdrop(sc)) in places.WINDOWS):
                        continue                           # Feuer, Autos, Naturgewalten erscheinen nicht im Zimmer (Himmelsdinge: im Fenster)
                    if kind in ("computer", "tv", "fridge", "shelf", "cart") and places.resolve(backdrop(sc)) in NO_FURNITURE:
                        continue                           # „zocken“ im Diner stellt keinen Schreibtisch ins Restaurant
                    if places.resolve(backdrop(sc)) == "bedroom" and sc.get("props"):
                        break                              # im Schlafzimmer ist neben Bett und Tisch nur Platz für ein Ding
                    if kind in INDOOR_THINGS and places.resolve(backdrop(sc)) in ("space", "underwater", "cave"):
                        continue                           # kein Schreibtisch im All, kein Kühlschrank am Meeresgrund
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
                for a in acts:
                    if not a.get("kind") and not a.get("hold"):
                        a["hold"] = item
                        break
                break
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
        if places.resolve(backdrop(sc)) == "underwater":          # unter Wasser schwimmen Fische, keine Menschen
            for a in acts:
                if not a.get("kind"):
                    a["kind"] = "fish"
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
                and not sc.get("shot")):
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
            if public and not sc.get("crowd"):            # leerer öffentlicher Raum: Menschen passend zur Stimmung
                sc["crowd"] = {"panic": "panic", "tense": "worried", "sad": "sad", "happy": "cheer"}.get(mood, "walk")
            elif not public and last_id and rp not in ("space", "underwater", "cave"):
                sc["actors"] = acts = [{"id": last_id, "action": "walk", "pos": "offleft", "to": "center",
                                        "emotion": MOOD_EMOTION.get(mood, "")}]
        # Gegenstand groß zeigen statt dritter Rede-Szene im selben Zimmer
        things = [q for q in (sc.get("props") or []) if extras.prop_fit(q.get("type") if isinstance(q, dict) else q)]
        if ((not outdoor or used.get(place, 0) >= 3) and rp not in MAPS and things and not has_ov and not sc.get("shot") and (outdoor or not sc.get("crowd")) and len(acts) <= 1
                and all(str(a.get("action") or "talk").lower() in ("talk", "idle", "") for a in acts)
                and not (i and str(scenes[i - 1].get("shot") or "") == "insert")):
            sc["shot"] = "insert"
        lone = len(acts) == 1 and str(acts[0].get("action") or "talk").lower() in ("talk", "idle", "") and not acts[0].get("to")
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
        g_auto = None
        low_c = str(sc.get("text") or "").lower()
        if sc.get("shot") == "graphic" and (sc.get("graphic") or {}).get("type") == "chart":
            if charts >= 2 or (i and scenes[i - 1].get("shot") == "graphic" and (scenes[i - 1].get("graphic") or {}).get("type") == "chart"):
                sc["shot"], sc["graphic"] = "", None        # höchstens zwei Kurven, nie zwei hintereinander
            else:
                charts += 1
                sc["actors"], sc["props"], sc["crowd"], sc["weather"] = [], [], "", ""
                acts, lone = [], False
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
        if sc.get("shot") == "graphic":
            gfx += 1
        elif (lone or not acts) and (fig_prev or neon or (i and scenes[i - 1].get("shot") == "graphic")) and sc.get("shot") in ("", "close", "event") \
                and ov_t in ("", "card", "counter", "bar") and not last and i > 0 and gfx < (6 if neon else 4) and not window_scene and rp2 not in MAPS:
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
            elif rp2 in PUBLIC_INDOOR:
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
                elif step == 2:                                                # Blick nach draußen: Straße, Menschen, das Thema am Himmel
                    sc["place"], sc["backdrop"] = "street", None
                    sc["actors"], sc["shot"] = [], "event"
                    sc["props"] = [{"type": k} for k in topic_any[:1]]
                    sc["crowd"] = {"panic": "panic", "tense": "worried", "sad": "sad", "happy": "cheer", "scary": ""}.get(str(sc.get("mood") or ""), "walk")
                    place = "street"
                elif step in (1, 3) and not prev_close:
                    sc["shot"] = "close"
                else:
                    acts[0].update(action="walk", pos="offright" if stale % 8 < 4 else "offleft", to="center")
        outdoor2 = rp2 in places.OUTDOOR
        topic_out = [k for k in topic_any if (k not in INDOOR_THINGS if outdoor2 else (k not in extras.SKY and extras.prop_fit(k)))]
        named = [k for pat, k in _lib_props() + TEXT_PROPS if k in topic_out and _re0.search(pat, str(sc.get("text") or "").lower())]
        if topic_out and not sc.get("props") and sc.get("shot") not in ("close", "graphic", "insert") and rp2 not in MAPS and not last \
                and (named or i % 2 == 0):
            sc["props"] = [{"type": (named or topic_out)[0]}]        # das Thema bleibt im Bild (die Drohne über der Straße, die Spinne im Zimmer)
        fig_prev = bool([a for a in (sc.get("actors") or []) if isinstance(a, dict)]) and sc.get("shot") not in ("insert", "graphic")
        # --- beeindruckende Zahl im Satz → Zähler, wenn das Drehbuch keine Einblendung vorsieht
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
            floats_now = bool(_re0.search(FLOAT_RE, txt_f))
            if _re0.search(DROP_RE, txt_f) and (_re0.search(GRAVITY_BACK_RE, txt_f) or (float_seen and not floats_now)):
                fl = "drop"                               # „… während Möbel schwerelos durcheinanderfliegen“ ist noch kein Absturz
            elif _re0.search(FLOAT_RE, txt_f) or any(str(a.get("action") or "") in ("float", "schweben") for a in acts_f):
                fl = "float"
            elif zero_g and i < len(scenes) - 1:
                fl, kept = "float", True                  # die Schwerkraft ist noch weg: wer im Bild ist, schwebt weiter
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
        if sc.get("shot") == "insert" and keys:           # Großaufnahme nur von Dingen, von denen der Satz (oder das Thema) wirklich handelt
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
    _time_weather(scenes)
    _auto_explain(scenes)
    _topic_creature(scenes, topic)
    for i in range(1, len(scenes)):                  # nie zweimal dieselbe Großaufnahme hintereinander
        if isinstance(scenes[i], dict) and isinstance(scenes[i - 1], dict) and scenes[i].get("shot") == "close" == scenes[i - 1].get("shot"):
            scenes[i]["shot"] = ""
    _auto_tags(scenes)
    return scenes


# Tier/Wesen im Titel → es wird die Hauptfigur des Videos (wie in den Vorbild-Shorts: die Spinne ist fast in jeder Szene, mit Gefühl)
TOPIC_CREATURES = [(r"ki-agent|\bagent|\bbots?\b|chatbot|\bassistent|\bki\b|künstliche intelligenz|\bclaude\b|chatgpt|sprachmodell", "agent"),
                   (r"\bvirus|\bviren|bakterie|\bkeim|erreger|grippe|infektion", "virus"), (r"\bzelle|zellen|blutkörperchen|immunsystem", "cell"),
                   (r"spinne|tarantel|vogelspinne|weberknecht|kreuzspinne", "spider"), (r"katze|kater|kätzchen", "cat"), (r"\bhund|hunde|welpe", "dog"),
                   (r"biene", "bee"), (r"wespe|hornisse", "wasp"), (r"\bhai\b|haie|weißer hai", "shark"), (r"\bfisch|goldfisch", "fish"),
                   (r"\bvogel|vögel|spatz|taube|amsel", "bird"), (r"\bgeist|gespenst", "ghost"), (r"roboter", "robot"),
                   (r"außerirdisch|alien|\bufo", "alien"), (r"dinosaurier|\bdino|t-rex", "dino"), (r"monster|ungeheuer", "monster")]
PLURAL = {"agent": r"agenten|\bbots\b|assistenten", "virus": r"\bviren|bakterien|keime|erreger", "cell": r"zellen|blutkörperchen",
          "spider": r"spinnen|taranteln", "bee": r"bienen", "wasp": r"wespen", "cat": r"katzen", "dog": r"\bhunde\b", "bird": r"vögel",
          "fish": r"fische", "shark": r"\bhaie", "ghost": r"geister|gespenster", "robot": r"roboter\b", "alien": r"außerirdische|aliens",
          "dino": r"dinosaurier", "monster": r"monster"}
HERO_SIZE = {"agent": 0.8, "virus": 0.75, "cell": 0.75, "spider": 1.15, "cat": 0.95, "dog": 1.0, "bee": 1.0, "wasp": 1.0, "bird": 1.0, "fish": 0.8, "shark": 0.9}   # Hauptfigur: etwa halb so hoch wie ein Mensch


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


# Tageszeit und Wetter, die der Satz nennt („nachts“, „es regnet in Strömen“) – Tag/Nacht und Wetter müssen zum Satz passen
NIGHT_RE = (r"\bnachts\b|in der nacht|\bum mitternacht|mitten in der nacht|\babends\b|am abend|nachtaktiv|im dunkeln\b|bei nacht|heute nacht|"
            r"jede nacht|die ganze nacht|nächtlich|in dieser nacht|sternenhimmel|im mondlicht")
DAY_RE = r"\btagsüber\b|am morgen|\bmorgens\b|am tag\b|\bmittags\b|am nachmittag|bei tageslicht|sonnenaufgang|in der mittagssonne|bei sonnenschein"
WEATHER_RE = [(r"gewitter|blitz und donner|\bunwetter|\bsturm\b|stürme|orkan|sturmböen|hurrikan", "storm"),
              (r"\bregnet|\bregen\b|regenschauer|platzregen|wolkenbruch|in strömen|nieselregen|regentropfen", "rain"),
              (r"\bschneit|schneefall|schneesturm|schneeflocken", "snow"), (r"\bwindig|\bwind\b|böen|weht", "wind"),
              (r"hitze|brütend heiß|\bheiß\b|hitzewelle|glühend heiß|sengende", "heat"), (r"asche regnet|ascheregen|aschewolke", "ash")]


def _time_weather(scenes):
    """Nennt der Satz Nacht/Tag oder ein Wetter, stimmt das Bild: nachts wird es Nacht (drinnen mit Lichtkegel, draußen dunkelblau),
    Regen, Schnee, Sturm, Wind und Hitze sieht man – Wetter nur draußen (drinnen regnet es nicht). Verneintes zählt nicht."""
    import re as _re
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
        if outdoor and not sc.get("weather"):
            for pat, w in WEATHER_RE:
                m = _re.search(pat, low)
                if m and not _re.search(r"(?:kein\w*|nicht|ohne|nie)\s+(?:\w+\s+){0,2}" + _re.escape(m.group(0)), low) \
                        and not _re.search(_re.escape(m.group(0)) + r"\w*\s+(?:\w+\s+)?(?:nicht|mehr)\b", low):
                    sc["weather"] = w
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


def _stamp_for(low, prev=""):
    """Passender Stempel für den Satz (nicht verneint, nicht derselbe wie eben) → (Wort, Farbe) oder None."""
    import re as _re
    for pat, word, col in STAMPS:
        m = _re.search(pat, low)
        if m and not _re.search(r"(?:nicht|kein\w*|nie)\s+(?:\w+\s+)?" + _re.escape(m.group(0)), low) and word != prev:
            return word, col
    return None


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
            sc["shot"], sc["graphic"] = "", None           # Temperatur/Anteil: lieber Thermometer bzw. Füllstand über der Szene als eine nackte Zahl
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
                    and not _re.search(r"grad (?:celsius )?(?:mehr|wärmer|kälter|weniger)|grad (?:steig|sink|fäll)|um \S+ grad", low):
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
        prev = bool(has and str(sc["overlay"].get("type")) == "tag")


def backdrop(scene):
    """Was als Hintergrund gezeichnet wird: Baukasten-Landschaft (backdrop) oder ein fester Ort."""
    b = scene.get("backdrop")
    if isinstance(b, dict) and (b.get("elements") or b.get("ground") or b.get("sky")):
        return b
    return scene.get("place")


# Wörter im Sprechertext → passender Hintergrund (greift nur, wenn das Drehbuch einen unpassenden Allerwelts-Ort nennt)
HINTS = [
    (r"rechenzentr|serverfarm|serverraum|serverräume|\bserver\b|\bservern\b|rechenleistung|rechenpower|ki-modell|supercomputer|datenzentr|des (gesamten |ganzen )?internets|datenström", "serverroom"),
    (r"konzern|firmenzentrale|hauptsitz|hauptquartier|firmensitz|tech-gigant|tech-riese|techriese|wolkenkratzer|weltfirma|weltmarktführer|milliardenfirma|billionenfirma", "headquarters"),
    (r"leergekauft|leere regale|leeren regale|regale sind leer|regale leer|hamsterk|ausverkauft|geplündert", "supermarket_empty"),
    (r"vorräte.{0,30}(neige|knapp|leer|aus)|lebensmittel.{0,30}(knapp|leer|aus)|nichts mehr zu kaufen", "supermarket_empty"),
    (r"supermarkt|supermärkte|einkaufen|einkauf\b|lebensmittelladen|geschäfte|\bläden", "supermarket"),
    (r"tankstelle|zapfsäule|tanken|benzin", "gasstation"),
    (r"kraftwerk|atomkraft|reaktor|stromnetz", "powerplant"),
    (r"strommast|stromleitung|hochspannung", {"elements": ["powerlines", "hills"]}),
    (r"windrad|windräder|windkraft", {"elements": ["windturbines", "fields"]}),
    (r"bahnhof|\bzug\b|\bzüge|u-bahn|s-bahn|bahnsteig", "station"),
    (r"friedhof|\bgrab\b|gräber", "graveyard"),
    (r"restaurant|café|kellner|\bdiner\b|burgerladen|imbiss|kneipe|pizzeria|gaststätte", "restaurant"),
    (r"badezimmer|dusche|badewanne|toilette|wasserhahn|leitungswasser", "bathroom"),
    (r"brücke", {"elements": ["bridge", "river", "city"]}),
    (r"\bzelt|camping|flüchtlingslager|notunterk", "camp"),
    (r"bauernhof|\bstall\b|\bkühe|\bvieh", "farm"),
    (r"mondoberfläche|auf dem mond|mondlandung", "moon"),
    (r"wasserwerk|klärwerk|talsperre|staudamm|wasserversorgung|wasserspeicher", {"elements": ["factory", "river", "hills"]}),
    (r"feuerwehr|löschen|\bbrände", "street"),
    (r"\bflur\b|korridor|\bgang\b|treppenhaus|hotel|vor der tür|an der tür|türklinke|klopft|zimmernummer", "hallway"),
    (r"dachboden|speicher\b", "attic"),
    (r"\bbett\b|schlafzimmer|wachst auf|aufwach|einschlaf|schläfst|decke über", "bedroom"),
    (r"spiegel|waschbecken", "bathroom"),
    (r"\bkeller|kellertreppe|bunker", "basement"),
    (r"kirche|\bdom\b|kathedrale", "church"),
    (r"müllhalde|müllberg|deponie|\bmüll\b", "landfill"),
    (r"regenwald|dschungel|\bwald|wälder|bäume", {"elements": ["forest"]}),
    (r"ausgetrocknet|dürre|vertrocknet|trocknen aus|staubtrocken", {"ground": "dry", "sky": "haze", "elements": ["deadtrees", "dryriver"]}),
    (r"\bfluss|flüsse|\bbach|strom fließt", {"elements": ["hills", "river"]}),
    (r"\bsee\b|\bseen\b|teich", {"elements": ["hills", "lake"]}),
    (r"ernte|landwirt|bauern|\bfeld|felder|acker|getreide", {"elements": ["farm", "fields"]}),
    (r"\bgarten|gärten|\bwiese|\brasen\b|käfer|insekten|maulwurf|regenwurm|schnecken", "park"),
    (r"gletscher|eiszeit|arktis|antarktis|polkappe|\beis\b", {"ground": "snow", "elements": ["glacier", "mountains"]}),
    (r"\bschnee|\bwinter", "snow"),
    (r"\bmeer|ozean|küste|strand|wellen|welle\b", "beach"),
    (r"tiefsee|unter wasser|meeresgrund|korallen|\bfisch|unter der oberfläche|im wasser leb|\\btauch(?!t (plötzlich )?auf)|taucher", "underwater"),
    (r"wüste|sahara|sanddüne", "desert"),
    (r"vulkan|gebirge|\bberg|gipfel", "mountain"),
    (r"weltall|weltraum|galaxie|planet|umlaufbahn|astronaut|\bmond\b|sonnensystem", "space"),
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
    (r"\bbüro|\barbeit\b|\bchef", "office"),
    (r"küche|kochen|kühlschrank", "kitchen"),
]
GENERIC = ("street", "park", "plain", "livingroom")
SPACE_RE = (r"weltall|weltraum|\ball\b|galaxi|planet|umlaufbahn|orbit|astronaut|\bmond|sonnensystem|\bstern|satellit|rakete|raumschiff|raumstation|\biss\b|"
            r"kosmos|universum|schwarze\w* l[oö]ch|\berde\b|\bsonne\b|meteor|asteroid|komet|außerirdisch|alien|\bufo|raumfahrt|schwerelos|mars\b|jupiter|saturn|milchstraße")
GROUP_RE = (r"\b(zwei|drei|vier|fünf) (?:\w+ )?(gründer\w*|freund\w*|forscher\w*|wissenschaftler\w*|student\w*|brüder\w*|schwestern|kolleg\w*|ingenieur\w*|"
            r"entwickler\w*|tüftler\w*|erfinder\w*|männer\w*|frauen|jungs|kumpel\w*|nerds|programmierer\w*|unternehmer\w*|geschwister\w*|typen|partner\w*|"
            r"schüler\w*|mitarbeiter\w*|expert\w*|bastler\w*|teenager\w*|jugendliche\w*)\b")
GROUP_LOOKS = ({"shirt": "rot", "hair": "bun", "glasses": True}, {"shirt": "orange", "hat": "cap"}, {"shirt": "lila", "hair": "long"}, {"shirt": "türkis", "glasses": True})
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
DROP_RE = (r"kracht|krachen|aufprall|prall\w* .{0,70}(boden|erde|asphalt|straße|\bauf\b)|knall\w* .{0,70}(boden|erde|asphalt|straße|pflaster)|"
           r"\b(schlägt|schlagen) .{0,30}(boden|asphalt|\bauf\b)|(fällt|fällst|fallen|stürzt|stürzen) .{0,50}(boden|herunter|herab|hinab|zurück|\bab\b)|plumps")
GRAVITY_BACK_RE = r"(schwerkraft|gravitation|erdanziehung\w*)\w* .{0,60}(wieder|zurück|setzt .{0,12}ein|schaltet sich .{0,12}ein|kehrt)"
ZERO_G_TOPIC = r"schwerkraft|schwerelos|gravitation|erdanziehung"
FLOAT_THINGS = ("lib_stuhl", "lib_kaffeetasse", "box", "clock", "lib_schuh", "glass")       # was in einem Zimmer herumtreibt, wenn nichts Bestimmtes genannt ist
DISASTER_RE = (r"zerstör|vernicht|verwüst|reiß\w* .{0,40}\b(ab|auf|ein|mit|weg)\b|br[ie]ch\w* .{0,30}\b(auf|ein|zusammen)\b|stürz\w* ein|orkan|hurrikan|erdbeben|"
               r"tsunami|flutwelle|explodier|explosion|verglüh|tödlich|albtraum|weltuntergang|trümmer|kracht|krachen|aufprall|schleuder|druckwelle")
WEATHER_HINTS = [(r"erdbeben|\bbebt\b|erschütter", "quake"), (r"orkan|hurrikan|sturmböe|\bsturm\b|stürmt|windböe|luftmassen|druckwelle", "wind"),
                 (r"\bkocht|zu kochen|brodel|verdampf|verdunste", "steam"), (r"ascheregen|\basche\b", "ash")]
PANIC_RE = r"panik|flieh|flücht|rennen (weg|davon|los|um)|rennt (weg|davon|los)|schrei|stürmen|plünder|todesangst|rette sich"
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
INDOOR = ("bedroom", "livingroom", "kitchen", "office", "classroom", "lab", "hospital", "basement", "cave", "underwater", "space", "cinema")
MAPS = ("germany", "worldmap")
OUTDOOR_THINGS = ("drone", "cctv", "fire", "smoke", "volcano", "meteor", "tornado", "lightning", "flood", "crack", "wave", "explosion", "car", "bus", "truck",
                  "plane", "satellite", "rocket", "ufo", "aurora", "ice", "ship", "bike", "tent", "trafficlight", "house", "tree", "solarpanel",
                  "pile", "sandpile", "trash", "barrel", "generator")
DULL = ("table", "shelf", "streetlamp", "rock", "box")          # allein als Großaufnahme langweilig
INDOOR_THINGS = ("faucet", "glass", "candle", "cans", "clock", "door", "fridge", "tv", "computer", "shelf", "cart", "table", "money")
TEXT_PROPS = [(r"drohne", "drone"), (r"überwachungskamera|kameras? (erfass|film|beobacht)|überwacht|überwachung", "cctv"), (r"zucker|\bsalz\b", "pile"), (r"\bsand\b", "sandpile"), (r"\bmüll|abfall|plastik", "trash"), (r"wasserhahn|trinkwasser|leitungswasser", "faucet"),
              (r"\bglas\b|\bgläser|trinken|getränk|\bdurst", "glass"), (r"kerze", "candle"), (r"konserve|vorrät|dosen", "cans"), (r"benzin|kanister|sprit", "canister"),
              (r"\bautos?\b|\bstau\b", "car"), (r"\bbus\b|busse", "bus"), (r"lkw|lastwagen|lieferung|lieferkette", "truck"), (r"flugzeug|flieger|\bflüge", "plane"),
              (r"satellit|\bgps\b", "satellite"), (r"rakete", "rocket"), (r"\bgeld|\beuro\b|kosten|teuer|preise|milliarden euro|bezahl", "money"),
              (r"solar", "solarpanel"), (r"generator|notstrom|aggregat", "generator"), (r"\bfeuer\b|flammen|\bbrand\b|in brand|lichterloh|waldbr[aä]nd|\bbrände", "fire"), (r"\brauch\b|qualm", "smoke"),
              (r"vulkan|lava", "volcano"), (r"meteor|asteroid|komet", "meteor"), (r"tornado|wirbelsturm", "tornado"), (r"gewitter|\bblitz", "lightning"),
              (r"überschwemm|\bflut|hochwasser", "flood"), (r"erdbeben|boden reißt|erdkruste|fundament|reiß\w* .{0,40}\b(ab|auf)\b|bricht .{0,20}\bauf\b|\brisse\b|spalte", "crack"), (r"tsunami|riesenwelle|wasserwelle|wasserwand|wassermassen|flutwelle|monsterwelle|riesige\w* welle", "wave"), (r"orkan|hurrikan|\bsturm\b", "stormcloud"), (r"explo", "explosion"),
              (r"\bufo|außerirdisch", "ufo"), (r"polarlicht", "aurora"), (r"eisberg|\beis schmilzt", "ice"), (r"\bschiff|\bboot", "ship"),
              (r"fahrrad", "bike"), (r"kühlschrank", "fridge"), (r"einkaufswagen", "cart"), (r"tür\b|türen\b|klopft", "door"), (r"\buhr\b|uhrzeit", "clock"),
              (r"\bfass|fässer|\böl\b", "barrel"), (r"\bzelt", "tent"), (r"ampel", "trafficlight"), (r"fernseh|nachrichten", "tv"), (r"computer|internet|server|zock|gaming|videospiel|ballerspiel|\bgamer|\bpc\b|laptop", "computer"),
              (r"pflanze[n]? wachs|keim|\bsaat", "sprout")]
MAP_HINTS = ((r"ganz deutschland|in deutschland|deutschlandweit|bundesweit|bundesländer|jeder deutsche|alle deutschen", "germany"),
             (r"weltweit|auf der ganzen welt|alle länder|rund um den globus|weltbevölkerung|alle kontinente|die ganze erde|die ganze welt", "worldmap"))
# Tiere neben Menschen: Größe im Verhältnis zur Figur (1.0 = menschengroß). „Riesen…“-Themen heben das auf (giant).
CREATURE_SIZE = {"spider": 0.38, "cat": 0.42, "dog": 0.55, "bird": 0.45, "bee": 0.45, "wasp": 0.45}
GIANT_RE = r"riesen|riesig|gigant|monströs|so groß wie|meterhoh|haushoh|mutier"
# Nur hier laufen Passanten durchs Bild – auf dem Feld, im Wald, im Keller ist niemand unterwegs
CROWD_PLACES = ("headquarters", "street", "park", "village", "beach", "gasstation", "station", "supermarket", "supermarket_empty", "hospital", "office",
                "classroom", "restaurant", "church")
CROWD_ELEMENTS = ("city", "village", "street", "houses")


def crowd_ok(scene):
    b = backdrop(scene)
    if isinstance(b, dict):
        return any(str(e) in CROWD_ELEMENTS for e in (b.get("elements") or []))
    return places.resolve(b) in CROWD_PLACES


PUBLIC_INDOOR = ("supermarket", "supermarket_empty", "station", "hospital", "office", "classroom", "restaurant")
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


TIGHT_Z, TIGHT_AY = 1.3, 300.0            # Halbnahe: Zoom und Fixpunkt (oben) – wie in Erklär-Shorts füllen die Figuren das Bild


def _camera(frame, t, dur, cam):
    """Lebendige Kamera für jede Szene: etwas näher an den Figuren, langsame Fahrt, ein kurzer Ruck beim Schnitt und – wenn
    das Schlüsselwort fällt – ein schneller Sprung auf die Hauptfigur (wie in geschnittenen Kurzvideos)."""
    k = t / max(dur, 0.1)
    z = (1.0 if cam.get("flat") else cam.get("zt", TIGHT_Z) if cam.get("tight") else 1.06) + 0.035 * (k if cam.get("drift", 1) > 0 else 1 - k)
    ax, ay = 540.0, (TIGHT_AY if cam.get("tight") else 1010.0)
    if cam.get("tight"):                                  # nah dran: Figuren füllen das Bild, der leere Boden unten fällt weg
        ax += (float(cam.get("fx", 540)) - 540) * 0.6
    pt = cam.get("punch")
    if pt is not None and t >= pt:
        e = _ease(min(1.0, (t - pt) / 0.14))
        z += 0.14 * e
        ax += (float(cam.get("fx", 540)) - 540) * e
        ay -= 90 * e
    if t < 0.22:                                          # Schnitt: kurzer Ruck hinein und zur Seite
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


CUT_MIN = 2.6        # ab dieser Szenenlänge (s) wird mitten im Satz geschnitten – wie in den Vorbild-Shorts etwa alle 1,8 Sekunden ein neues Bild


def _cut_plan(scene, shot, special, moving, ov_tall, place, actors, props, dur, cam, index):
    """Zweites Bild innerhalb einer Szene: beim Schlüsselwort (sonst zur Mitte) harter Schnitt auf den genannten Gegenstand groß
    („insert“) oder auf die Großaufnahme der Hauptfigur bzw. des Tiers („close“). Jede dritte Szene bleibt ruhig ohne Schnitt.
    Gibt (Schnittzeit oder None, Art, Gegenstände) zurück und schaltet den Kamerasprung ab, wenn geschnitten wird."""
    if special or shot or moving or ov_tall or scene.get("float") or dur < CUT_MIN or place in MAPS or index % 3 == 2 \
            or str(scene.get("shot") or "") in ("event", "insert", "graphic", "close"):
        return None, "", []
    named = [k for k, _ in props if extras.prop_fit(k) and extras.PROP_ALIASES.get(k, k) not in DULL
             and extras.PROP_ALIASES.get(k, k) not in PLACE_HAS.get(place, ())]
    down = any(a.get("action") in ("fall", "sleep", "sit", "float") for a in actors)      # liegt, sitzt oder schwebt jemand, schneidet die Großaufnahme ihn an
    kind = "insert" if named and index % 2 == 0 else "close" if 0 < len(actors) <= 2 and not down else "insert" if named else ""   # Gruppen nicht anschneiden
    if not kind:
        return None, "", []
    pt = cam.get("punch")
    cut = min(max(pt if pt is not None else dur * 0.5, 1.1), dur - 1.0)
    cam["punch"] = None
    return cut, kind, named


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
    if gfx and hyper.handles(gfx) and hyper.render(gfx, dur, out, str(scene.get("mood") or "").lower(), still):
        return                                # Grafik von HyperFrames (HTML/GSAP) gerendert – sonst zeichnet graphics.py sie unten wie bisher
    neon_look = str(scene.get("look") or "") == "neon"
    if neon_look:                             # Neon-Nacht: nur die Kulisse wird violett getönt – Figuren und Dinge bleiben kräftig
        bg = graphics.tint(bg)
    shot = "close" if shot == "close" and not has_ov and not moving and not props and actors and not scene.get("float") else ""
    ov_tall = str((scene.get("overlay") or {}).get("type") or "") in TALL_OV if has_ov else False
    lead = next((a for a in actors if a["speaks"]), actors[0] if actors else None)
    cam = {"dir": 1 if index % 2 == 0 else -1, "drift": 1 if index % 3 != 2 else -1,
           "fx": (lead["x1"] if lead else (props[0][1] if props else 540)),
           "punch": None if (shot == "close" or moving or ov_tall or place in MAPS or not (actors or props)) else _punch_time(scene, words, t0, dur)}
    if actors and shot != "close" and not ov_tall and place not in MAPS and not scene.get("float") and str(scene.get("shot") or "") != "event":
        xs = [a["x1"] for a in actors] + [a["x0"] for a in actors if -100 < a["x0"] < W + 100]
        xs += [x for k, x in props if extras.prop_fit(k) and 0 <= x <= W]   # auch der Gegenstand, von dem der Satz spricht, bleibt ganz im Bild
        for a_l in actors:                                              # wer umfällt oder liegt, ist so breit wie sonst hoch: ganz im Bild lassen
            if a_l.get("action") in ("fall", "sleep"):
                xs += [a_l["x1"] - 200, a_l["x1"] + 60]
                cam["punch"] = None                                         # kein Sprung auf den Kopf – der läge dann am Bildrand
        span = max(xs) - min(xs) + 420                                  # Breite der Gruppe samt Armen
        cam.update(tight=True, zt=max(1.0, min(1.42, W / span)), fx=(max(xs) + min(xs)) / 2)
    cam_flat = {"flat": True, "dir": cam["dir"], "drift": cam["drift"]}
    cut_t, cut_kind, named = _cut_plan(scene, shot, gfx or ins, moving, ov_tall, place, actors, props, dur, cam, index)
    mood_s = str(scene.get("mood") or "").lower()
    fx_opt = {"crowd": scene.get("crowd") if crowd_ok(scene) else "", "mood": mood_s, "spec": places.spec_of(backdrop(scene)), "sky": sky_m,
              "win": scene.get("_win"), "count": scene.get("_count"), "neon": neon_look, "float": str(scene.get("float") or ""),
              "aloft": bool(scene.get("aloft")), "low": bool(scene.get("low")), "no_traffic": bool(scene.get("no_traffic") or scene.get("dark_city"))}
    ff = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
                           "-crf", "17", "-pix_fmt", "yuv420p", str(out)], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for fidx in range(n_frames):
            t = fidx / FPS
            if gfx or ins:
                frame = (graphics.frame(gfx, t, dur, str(scene.get("mood") or "").lower()) if gfx
                         else _insert_frame(ins, t, dur, str(scene.get("mood") or "").lower(), bool(has_ov), neon_look))
                if still is not None and fidx == min(n_frames - 1, FPS):
                    frame.save(still, quality=92)
                ff.stdin.write(_camera(frame.convert("RGB"), t, dur, cam_flat).tobytes())
                continue
            if cut_t is not None and t >= cut_t:            # Schnitt mitten im Satz: auf das genannte Ding oder die Großaufnahme der Figur
                tc = t - cut_t
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


def poster(spec: dict, cast: dict, out: Path, topic=""):
    """Eigens gestaltetes Titelbild (kein Bild aus dem Video): Strahlen-Hintergrund, das Ding des Videos riesig als Aufkleber,
    darunter die Hauptfigur groß im Anschnitt mit starkem Gefühl. Der Text kommt danach ins obere Drittel."""
    import re as _re
    from PIL import ImageFilter
    dark = str(spec.get("time") or "").lower() in ("night", "nacht") or str(spec.get("mood") or "").lower() in ("scary", "panic")
    c0, c1, glow = (((70, 40, 150), (38, 20, 96), (190, 150, 255)) if dark else ((255, 205, 60), (250, 160, 40), (255, 250, 220)))
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
    low = str(topic or "").lower()
    keys = [extras.PROP_ALIASES.get(str(p.get("type") if isinstance(p, dict) else p).lower(), str(p.get("type") if isinstance(p, dict) else p).lower())
            for p in (spec.get("props") or [])]
    keys += [k for pat, k in _lib_props() + TEXT_PROPS if _re.search(pat, low)]
    for k in keys:
        if k in extras.PROPS:
            lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            extras.draw_prop(lay, k, 540, 1.2)
            box = lay.getbbox()
            if box:
                hero = lay.crop(box)
                break
    if hero is None and (kind in extras.CREATURES or cast_kind in extras.CREATURES):
        res = extras.creature(kind if kind in extras.CREATURES else cast_kind, 0.4, 1, 0.6, "", 1.6)
        if res and res[0].getbbox():
            hero = res[0].crop(res[0].getbbox())
    # 2) die Hauptfigur, groß im Anschnitt
    aid = spec.get("actor") if isinstance((cast or {}).get(spec.get("actor")), dict) and not cast[spec.get("actor")].get("kind") else \
        next((k for k, v in (cast or {}).items() if isinstance(v, dict) and not v.get("kind")), None)
    look = rig.Look.from_spec((cast or {}).get(aid) if aid else {}, aid or "", list(cast).index(aid) if aid and aid in (cast or {}) else None)
    pose, _ = rig.pose_at("shocked", 1.0, 3.0, str(spec.get("emotion") or "shocked"), 0.8, 3)
    pose.lift = 0
    fig, fx, fy = rig.draw(look, pose, 1, 2.3)
    if hero is not None:
        sticker(hero, 700, 640, 640, 930, -6)
        frame.paste(fig, (int(250 - fx), int(2330 - fy)), fig)
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
