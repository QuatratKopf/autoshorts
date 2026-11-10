"""Bühne: setzt Figuren, Tiere und Requisiten auf einen Ort und rendert die Szene Bild für Bild (30 fps) als Video.
Figuren bewegen sich (gehen, rennen, springen …), blinzeln und bewegen den Mund passend zur Sprecherstimme;
dazu Wetter, Gefühls-Symbole und kleine Bewegungen im Hintergrund."""
import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from . import extras, places, rig

W, H, FPS = 1080, 1920, 30
SCALE = 1.08            # Figuren bewusst kleiner: die Szene steht im Mittelpunkt
POS = {"left": 250, "center": 540, "right": 830, "offleft": -260, "offright": 1340,
       "links": 250, "mitte": 540, "rechts": 830}
TALL_OV = ("phone", "checklist", "note")


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


def _prepare(scene, cast):
    place = places.resolve(backdrop(scene))
    night = str(scene.get("time") or "").lower() in ("night", "nacht", "abend", "evening")
    ov = scene.get("overlay") if isinstance(scene.get("overlay"), dict) else {}
    scale = 0.9 if str(ov.get("type")) in TALL_OV else SCALE
    event = str(scene.get("shot") or "").lower() == "event"
    raw = [a for a in (scene.get("actors") or []) if isinstance(a, dict)]
    if "actors" not in scene and not event:
        raw = [{"id": next(iter(cast), "held"), "action": "talk", "speaks": True}]
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
        kind = str(a.get("kind") or spec.get("kind") or "").lower()
        x0 = _x(a.get("pos"), default_x[i])
        x1 = _x(a.get("to"), x0) if a.get("to") else x0
        action = str(a.get("action") or "idle").lower()
        if x1 != x0 and action not in ("walk", "run"):
            action = "walk"
        if action in ("walk", "run") and x1 == x0:       # ohne Ziel: von außen hereinkommen
            x0 = -260 if x0 <= 540 else 1340
        actors.append({"look": rig.Look.from_spec(spec), "kind": kind if kind in extras.CREATURES else "",
                       "action": action, "emotion": str(a.get("emotion") or "").lower(), "emote": a.get("emote") or "",
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
    for i, p in enumerate((scene.get("props") or [])[:3]):
        if isinstance(p, str):
            p = {"type": p}
        if isinstance(p, dict) and p.get("type"):
            taken = [q["x1"] for q in actors] + [q[1] for q in props]
            free = [c for c in (830, 250, 540, 990, 90) if all(abs(c - tx) > 230 for tx in taken)] or [830]
            props.append((str(p["type"]).lower(), _x(p.get("pos"), free[0]) if p.get("pos") else free[0]))
            p_given.append(bool(p.get("pos")))
    if event:
        props = [(k, 600 if (i == 0 and not p_given[i]) else x) for i, (k, x) in enumerate(props)]
    return place, night, scale, actors, props, str(scene.get("weather") or "").lower()


CROWD_SHIRTS = ("blau", "rot", "grün", "gelb", "orange", "lila", "türkis", "grau", "braun", "pink")
CROWD_KINDS = {"panic": "panic", "panik": "panic", "flee": "panic", "flucht": "panic", "run": "panic",
               "walk": "walk", "gehen": "walk", "busy": "walk", "cheer": "cheer", "jubel": "cheer", "party": "cheer",
               "sad": "sad", "traurig": "sad", "watch": "watch", "staunen": "watch", "gather": "watch"}


def _crowd(frame, kind, t, night):
    """Menschen im Hintergrund, die die Stimmung zeigen: Panik (rennen kreuz und quer), Alltag (gehen),
    Jubel (springen), Trauer (stehen gebeugt), Staunen (stehen und zeigen)."""
    kind = CROWD_KINDS.get(str(kind or "").lower())
    if not kind:
        return
    import random
    rnd = random.Random(11)
    n = {"panic": 7, "walk": 5, "cheer": 6, "sad": 5, "watch": 5}[kind]
    people = []
    for i in range(n):
        depth = rnd.random()                                   # 0 = hinten/klein, 1 = vorn/größer
        look = rig.Look.from_spec({"shirt": CROWD_SHIRTS[(i * 3 + 1) % len(CROWD_SHIRTS)], "hat": ("", "", "cap", "beanie", "")[i % 5],
                                   "hat_color": CROWD_SHIRTS[(i * 7) % len(CROWD_SHIRTS)], "hair": ("", "long", "", "bun")[i % 4],
                                   "skin": ("weiß", "hell", "mittel", "dunkel")[i % 4]})
        people.append((depth, look, rnd.random(), rnd.choice((-1, 1)), i))
    for depth, look, ph, direction, i in sorted(people):
        sc = 0.5 + depth * 0.28
        gy = places.GROUND - 46 + depth * 150
        emote = ""
        if kind == "panic":
            speed = 420 + ph * 380
            span = W + 500
            x = ((t * speed + ph * span) % span) - 250
            x = x if direction > 0 else W - x
            pose, _ = rig.pose_at("run", t + ph * 3, 9, "scared", 0.8, i)
            pose.arm_l, pose.arm_r, pose.fore_l, pose.fore_r = -150 + 20 * math.sin(t * 14 + i), 150 + 20 * math.sin(t * 14 + i + 1), 20, -20
            facing = direction
            emote = "!" if i % 3 == 0 else ("sweat" if i % 3 == 1 else "")
        elif kind == "walk":
            speed = 110 + ph * 90
            span = W + 400
            x = ((t * speed + ph * span) % span) - 200
            x = x if direction > 0 else W - x
            pose, _ = rig.pose_at("walk", t + ph * 3, 9, "", 0.0, i)
            facing = direction
        else:
            x = 110 + (i + 0.5) * (W - 220) / n + math.sin(i * 2.3) * 30
            facing = 1 if x < W / 2 else -1
            if kind == "cheer":
                pose, _ = rig.pose_at("jump", t + ph, 9, "happy", 0.6, i)
            elif kind == "sad":
                pose, _ = rig.pose_at("sad", t + ph, 9, "sad", 0.0, i)
            else:
                pose, _ = rig.pose_at("point" if i % 2 else "shocked", t + ph + 1.0, 9, "shocked", 0.5, i)
                emote = "!" if i % 2 == 0 else ""
        im, fx, fy = rig.draw(look, pose, facing, sc, ss=1)
        if night:
            im = Image.composite(Image.new("RGBA", im.size, (20, 24, 60, 255)), im, im.split()[-1].point(lambda v: v * 90 // 255)) if False else im
        _shadow(frame, int(x), int(gy), int(60 * sc))
        frame.paste(im, (int(x - fx), int(gy - fy)), im)
        if emote:
            extras.draw_emote(frame, emote, x - 60, gy - 430 * sc, t + ph)


def _prop(frame, kind, x, t, big):
    """Requisite zeichnen; big > 1 vergrößert sie um ihren Standpunkt (Boden bzw. Himmel)."""
    key = extras.PROP_ALIASES.get(kind, kind)
    if big <= 1.01 or key in ("aurora", "lightning", "crack", "flood", "wave", "eclipse"):
        extras.draw_prop(frame, kind, x, t)
        return
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    extras.draw_prop(layer, kind, x, t)
    ay = 520 if key in extras.SKY else places.GROUND
    big_l = layer.resize((int(W * big), int(H * big)), Image.BILINEAR)
    frame.paste(big_l, (int(x - x * big), int(ay - ay * big)), big_l)


def _frame(bg, place, night, scale, actors, props, weather, t, dur, words, t0, in_bed, shot="", big=1.0, fx=None):
    frame = bg.copy()
    if weather in ("quake", "erdbeben"):      # Erdbeben: das ganze Bild wackelt
        dx, dy = int(math.sin(t * 47) * 16), int(math.cos(t * 39) * 12)
        frame = frame.transform(frame.size, Image.AFFINE, (1, 0, dx, 0, 1, dy), resample=Image.NEAREST)
    opt = fx or {}
    if opt.get("mood") == "panic" and weather not in ("quake", "erdbeben"):      # Panik: die Kamera zittert leicht
        dx, dy = int(math.sin(t * 31) * 7), int(math.cos(t * 27) * 5)
        frame = frame.transform(frame.size, Image.AFFINE, (1, 0, dx, 0, 1, dy), resample=Image.NEAREST)
    extras.draw_ambient(frame, place, night, t)
    extras.draw_landscape_motion(frame, opt.get("spec"), place, night, t, not opt.get("no_traffic"))
    for kind, x in props:
        if extras.PROP_ALIASES.get(kind, kind) not in extras.FRONT:
            _prop(frame, kind, x, t, big)
    if opt.get("crowd"):
        _crowd(frame, opt["crowd"], t, night)
    over = frame
    od = ImageDraw.Draw(frame, "RGBA")
    focus = 540.0
    for a in sorted(actors, key=lambda q: q["speaks"]):
        moving = a["x1"] != a["x0"]
        speed = 360 if a["action"] == "walk" else 680
        move_t = min(dur * 0.7, abs(a["x1"] - a["x0"]) / speed) if moving else 0
        arrived = moving and t >= move_t
        x = a["x1"] if arrived else (a["x0"] + (a["x1"] - a["x0"]) * _ease(t / move_t) if moving else a["x0"])
        mouth = _mouth(t0 + t, words) if a["speaks"] else 0.0
        if moving and not arrived:
            facing = 1 if a["x1"] > a["x0"] else -1
        elif a["face"] in ("left", "links"):
            facing = -1
        elif a["face"] in ("right", "rechts"):
            facing = 1
        else:
            facing = 1 if (x < 600 or len(actors) == 1) else -1
        gy = places.GROUND + (18 if a["speaks"] else 0)
        head_y = gy - 430 * scale
        if a["kind"]:
            hop = abs(math.sin(t * 9)) * 16 if (moving and not arrived) else 0
            res = extras.creature(a["kind"], t + a["seed"], facing, mouth, a["emotion"] or
                                  ("shocked" if a["action"] in ("shocked", "scared") else ""), scale * 0.9)
            if res:
                im, fx, fy, fly = res
                if not fly:
                    _shadow(frame, int(x), gy, int(120 * scale))
                frame.paste(im, (int(x - fx), int(gy - fy - hop)), im)
                head_y = gy - 400 * scale
        else:
            action = a["action"]
            tt = t
            if arrived:
                action, tt = ("talk" if a["speaks"] else "idle"), t - move_t
            elif action == "idle" and a["speaks"]:
                action = "talk"
            pose, _ = rig.pose_at(action, tt, dur, a["emotion"], mouth, a["seed"])
            if 0 <= t - move_t < 0.18 and arrived:           # kleines Abfedern beim Ankommen
                pose.squash *= 1 - 0.08 * math.sin((t - move_t) / 0.18 * math.pi)
            im, fx, fy = rig.draw(a["look"], pose, facing, scale)
            if pose.lying and in_bed:                          # im Schlafzimmer liegt die Figur im Bett
                x, gy = 300, places.GROUND - 150
            _shadow(frame, int(x), gy, int(72 * scale * (1 - min(0.5, max(0, pose.lift) / 200))))
            frame.paste(im, (int(x - fx), int(gy - fy)), im)
            head_y = gy - (430 + max(0, pose.lift)) * scale * a["look"].size
            _zzz(od, pose, x, head_y, t)
        if a["emote"]:
            extras.draw_emote(over, a["emote"], x, head_y, t)
        if a["speaks"] or len(actors) == 1:
            focus = x
    for kind, x in props:
        if extras.PROP_ALIASES.get(kind, kind) in extras.FRONT:
            _prop(over, kind, x, t, 1.0)
    if weather and not (night and weather in ("dark", "dunkel", "blackout")):
        extras.draw_weather(over, weather, t)
    if opt.get("mood"):
        extras.draw_mood(over, opt["mood"], t)
    if shot == "close":       # Nahaufnahme: Ausschnitt um die Hauptfigur, folgt ihr weich
        cx = max(330, min(W - 330, focus))
        frame = frame.crop((int(cx - 330), places.GROUND - 780, int(cx + 330), places.GROUND + 393)).resize((W, H), Image.BICUBIC)
    return frame


def direct(scenes, times):
    """Kleine Regie über das ganze Video: sorgt für Abwechslung, wenn das Drehbuch mehrmals hintereinander dieselbe
    Einstellung vorgibt (gleicher Ort, gleiche Figur, nur Reden) – andere Position, Nahaufnahme oder Hereinkommen."""
    prev_place, same, changes, prev_bd = None, 0, 0, None
    power_out = False
    for i, (sc, (s0, e0)) in enumerate(zip(scenes, times)):
        acts = [a for a in (sc.get("actors") or []) if isinstance(a, dict)]
        place = places.resolve(sc.get("place"))
        has_bd = isinstance(sc.get("backdrop"), dict) and (sc["backdrop"].get("elements") or sc["backdrop"].get("ground"))
        hint = None if has_bd else _hint(sc.get("text"))
        if hint is not None and (place in GENERIC or str(sc.get("shot") or "") == "event"):
            if isinstance(hint, dict):               # passende Landschaft aus dem Baukasten
                if place != "custom":
                    sc["backdrop"] = hint
            elif hint != place:
                sc["place"] = place = hint
        if has_bd or isinstance(sc.get("backdrop"), dict):
            place = "custom:" + ",".join(str(e) for e in (sc["backdrop"].get("elements") or [sc["backdrop"].get("ground")]))
        if place == "plain":      # unbekannter Ort im Drehbuch → beim letzten Ort bleiben (draußen: Park), nie ein leerer Raum
            if prev_bd is not None:
                sc["backdrop"] = prev_bd
                place = prev_place
            else:
                place = prev_place if (prev_place and not str(prev_place).startswith("custom")) else "park"
                sc["place"] = place
        prev_bd = sc.get("backdrop") if isinstance(sc.get("backdrop"), dict) else None
        m_hint, c_hint = _mood_hint(sc.get("text"))
        if not sc.get("mood") and m_hint:
            sc["mood"] = m_hint
        outdoor = places.resolve(backdrop(sc)) not in INDOOR
        if not sc.get("crowd") and c_hint and outdoor and not (c_hint == "walk" and str(sc.get("mood") or "") in ("scary", "sad")):
            sc["crowd"] = c_hint
        if sc.get("crowd") and not outdoor:
            sc["crowd"] = ""
        if str(sc.get("mood") or "") == "panic" and outdoor and not sc.get("crowd"):
            sc["crowd"] = "panic"
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
        if _re.search(r"\bstill\b|stillstand|steht still|stehen still|bleiben stehen|bleibt stehen|kein benzin|verkehr bricht|lahmgelegt|menschenleer|niemand mehr", txt):
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
            sc["crowd"] = "walk"            # nie ein Bild, in dem gar nichts passiert
        has_ov = isinstance(sc.get("overlay"), dict) and sc["overlay"].get("type")
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
        prev_place = place
    return scenes


def backdrop(scene):
    """Was als Hintergrund gezeichnet wird: Baukasten-Landschaft (backdrop) oder ein fester Ort."""
    b = scene.get("backdrop")
    if isinstance(b, dict) and (b.get("elements") or b.get("ground") or b.get("sky")):
        return b
    return scene.get("place")


# Wörter im Sprechertext → passender Hintergrund (greift nur, wenn das Drehbuch einen unpassenden Allerwelts-Ort nennt)
HINTS = [
    (r"regenwald|dschungel|\bwald|wälder|bäume", {"elements": ["forest"]}),
    (r"ausgetrocknet|dürre|vertrocknet|trocknen aus|staubtrocken", {"ground": "dry", "sky": "haze", "elements": ["deadtrees", "dryriver"]}),
    (r"\bfluss|flüsse|\bbach|strom fließt", {"elements": ["hills", "river"]}),
    (r"\bsee\b|\bseen\b|teich", {"elements": ["hills", "lake"]}),
    (r"ernte|landwirt|bauern|\bfeld|felder|acker|getreide", {"elements": ["farm", "fields"]}),
    (r"gletscher|eiszeit|arktis|antarktis|polkappe|\beis\b", {"ground": "snow", "elements": ["glacier", "mountains"]}),
    (r"\bschnee|\bwinter", "snow"),
    (r"\bmeer|ozean|küste|strand|wellen", "beach"),
    (r"tiefsee|unter wasser|meeresgrund|korallen", "underwater"),
    (r"wüste|sahara|sanddüne", "desert"),
    (r"vulkan|gebirge|\bberg|gipfel", "mountain"),
    (r"weltall|weltraum|galaxie|planet|umlaufbahn|astronaut|\bmond\b|sonnensystem", "space"),
    (r"höhle", "cave"),
    (r"fabrik|industrie|kraftwerk|abgase", {"sky": "haze", "elements": ["factory", "city"]}),
    (r"\bdorf|dörfer", {"elements": ["village", "hills"]}),
    (r"ruinen|zerstört|trümmer|apokalypse", {"sky": "red", "ground": "road", "elements": ["ruins"]}),
    (r"\bstadt|städte|straße|verkehr|hochhaus|hochhäuser", "street"),
    (r"krankenhaus|\barzt|ärzte|klinik", "hospital"),
    (r"\bschule|unterricht|klasse", "classroom"),
    (r"\blabor|forscher|wissenschaftler|experiment", "lab"),
    (r"\bbüro|\barbeit\b|\bchef", "office"),
    (r"küche|kochen|kühlschrank", "kitchen"),
]
GENERIC = ("street", "park", "plain", "livingroom")
MOOD_HINTS = [
    (r"panik|chaos|flieh|flücht|rennen um|katastrophe|ausnahmezustand|alarm|schreien", ("panic", "panic")),
    (r"feiern|jubel|freude|party|gewinn|gerettet|endlich wieder", ("happy", "cheer")),
    (r"verhunger|hunger|sterben|\btod\b|trauer|verzweifel|leiden|elend|verlieren alles", ("sad", "sad")),
    (r"unheimlich|grusel|\bangst|dunkelheit|finster|schatten|lauert|monster|geist", ("scary", "")),
    (r"gefahr|bedroh|warnung|knapp|kritisch|kollabier|zusammenbr", ("tense", "")),
    (r"menschen|leute|bevölkerung|einwohner|alle rennen|millionen|milliarden|gesellschaft", ("", "walk")),
    (r"staunen|beobachten|schauen zu|zuschauer", ("", "watch")),
]
INDOOR = ("bedroom", "livingroom", "kitchen", "office", "classroom", "lab", "hospital", "basement", "cave", "underwater", "space")


def _mood_hint(text):
    import re as _re
    t = str(text or "").lower()
    mood, crowd = "", ""
    for pat, (m, c) in MOOD_HINTS:
        if _re.search(pat, t):
            mood, crowd = mood or m, crowd or c
    return mood, crowd


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


def render_scene(scene: dict, cast: dict, dur: float, out: Path, words=(), t0=0.0, still: Path = None):
    """scene: {"place", "time", "weather", "props", "actors": [{"id", "action", "emotion", "emote", "pos", "to", "speaks"}]}.
    words: [(wort, start, ende)] der ganzen Sprecherspur; t0 = Startzeit der Szene darin."""
    place, night, scale, actors, props, weather = _prepare(scene, cast)
    bg = places.background(backdrop(scene), night)
    n_frames = max(2, round(dur * FPS))
    shot = str(scene.get("shot") or "").lower()
    has_ov = isinstance(scene.get("overlay"), dict) and scene["overlay"].get("type")
    moving = any(a["x0"] != a["x1"] for a in actors)
    big = 1.5 if shot == "event" else 1.15
    shot = "close" if shot == "close" and not has_ov and not moving and not props and actors else ""
    ff = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
                           "-crf", "17", "-pix_fmt", "yuv420p", str(out)], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for fidx in range(n_frames):
            t = fidx / FPS
            frame = _frame(bg, place, night, scale, actors, props, weather, t, dur, words, t0, place == "bedroom", shot, big,
                           {"crowd": scene.get("crowd"), "mood": str(scene.get("mood") or "").lower(), "spec": backdrop(scene),
                            "no_traffic": bool(scene.get("no_traffic") or scene.get("dark_city"))})
            if still is not None and fidx == min(n_frames - 1, FPS):
                frame.save(still, quality=92)
            ff.stdin.write(frame.tobytes())
        ff.stdin.close()
        err = ff.stderr.read().decode()[-500:]
        if ff.wait() != 0:
            raise RuntimeError("ffmpeg (Toon): " + err)
    finally:
        if ff.poll() is None:
            ff.kill()


def cover(spec: dict, cast: dict, out: Path):
    """Titelbild im Stil der Engine: Ort + große Figur mit starkem Gefühl + optional Requisite. Text kommt später darüber."""
    scene = {"place": spec.get("place") or "park", "backdrop": spec.get("backdrop"), "time": spec.get("time"), "weather": spec.get("weather"),
             "props": spec.get("props") or [],
             "actors": [{"id": spec.get("actor") or next(iter(cast), "held"), "kind": spec.get("kind") or "",
                         "action": spec.get("action") or "shocked", "emotion": spec.get("emotion") or "shocked",
                         "emote": " ", "pos": "center"}]}
    place, night, _, actors, props, weather = _prepare(scene, cast)
    frame = _frame(places.background(backdrop(scene), night), place, night, 1.25, actors, props, weather, 1.4, 3.0, (), 0.0, False, "", 1.35,
                   {"crowd": spec.get("crowd"), "mood": "", "spec": backdrop(scene)})
    # so beschneiden, dass die Figur groß in der unteren Bildhälfte sitzt und das obere Drittel für den Text frei bleibt
    frame = frame.crop((135, 0, 945, 1440)).resize((W, H), Image.LANCZOS)
    frame.save(out, quality=93)
