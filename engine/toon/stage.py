"""Bühne: setzt Figuren, Tiere und Requisiten auf einen Ort und rendert die Szene Bild für Bild (30 fps) als Video.
Figuren bewegen sich (gehen, rennen, springen …), blinzeln und bewegen den Mund passend zur Sprecherstimme;
dazu Wetter, Gefühls-Symbole und kleine Bewegungen im Hintergrund."""
import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from . import extras, places, rig

W, H, FPS = 1080, 1920, 30
SCALE = 1.45
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
    place = places.resolve(scene.get("place"))
    night = str(scene.get("time") or "").lower() in ("night", "nacht", "abend", "evening")
    ov = scene.get("overlay") if isinstance(scene.get("overlay"), dict) else {}
    scale = 1.0 if str(ov.get("type")) in TALL_OV else SCALE
    raw = [a for a in (scene.get("actors") or []) if isinstance(a, dict)] or \
        [{"id": next(iter(cast), "held"), "action": "talk", "speaks": True}]
    actors = []
    default_x = {1: (540,), 2: (330, 750), 3: (200, 540, 880)}[min(3, len(raw))]
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
    if actors and not any(a["speaks"] for a in actors):
        actors[0]["speaks"] = len(actors) == 1
    for a in actors:   # passende Symbole automatisch, wenn das Drehbuch keine nennt
        if not a["emote"]:
            a["emote"] = {"shocked": "!", "scared": "!", "think": "?", "angry": "anger"}.get(a["action"]) or \
                         {"angry": "anger", "scared": "sweat", "worried": "sweat"}.get(a["emotion"], "")
    props = []
    for i, p in enumerate((scene.get("props") or [])[:3]):
        if isinstance(p, str):
            p = {"type": p}
        if isinstance(p, dict) and p.get("type"):
            taken = [q["x1"] for q in actors] + [q[1] for q in props]
            free = [c for c in (830, 250, 540, 990, 90) if all(abs(c - tx) > 230 for tx in taken)] or [830]
            props.append((str(p["type"]).lower(), _x(p.get("pos"), free[0]) if p.get("pos") else free[0]))
    return place, night, scale, actors, props, str(scene.get("weather") or "").lower()


def _frame(bg, place, night, scale, actors, props, weather, t, dur, words, t0, in_bed, shot=""):
    frame = bg.copy()
    extras.draw_ambient(frame, place, night, t)
    for kind, x in props:
        if extras.PROP_ALIASES.get(kind, kind) not in extras.FRONT:
            extras.draw_prop(frame, kind, x, t)
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
            _shadow(frame, int(x), gy, int(95 * scale * (1 - min(0.5, max(0, pose.lift) / 200))))
            frame.paste(im, (int(x - fx), int(gy - fy)), im)
            head_y = gy - (430 + max(0, pose.lift)) * scale * a["look"].size
            _zzz(od, pose, x, head_y, t)
        if a["emote"]:
            extras.draw_emote(over, a["emote"], x, head_y, t)
        if a["speaks"] or len(actors) == 1:
            focus = x
    for kind, x in props:
        if extras.PROP_ALIASES.get(kind, kind) in extras.FRONT:
            extras.draw_prop(over, kind, x, t)
    if weather and not (night and weather in ("dark", "dunkel", "blackout")):
        extras.draw_weather(over, weather, t)
    if shot == "close":       # Nahaufnahme: Ausschnitt um die Hauptfigur, folgt ihr weich
        cx = max(360, min(W - 360, focus))
        frame = frame.crop((int(cx - 360), places.GROUND - 900, int(cx + 360), places.GROUND + 380)).resize((W, H), Image.BICUBIC)
    return frame


def direct(scenes, times):
    """Kleine Regie über das ganze Video: sorgt für Abwechslung, wenn das Drehbuch mehrmals hintereinander dieselbe
    Einstellung vorgibt (gleicher Ort, gleiche Figur, nur Reden) – andere Position, Nahaufnahme oder Hereinkommen."""
    prev_place, same, changes = None, 0, 0
    for i, (sc, (s0, e0)) in enumerate(zip(scenes, times)):
        acts = [a for a in (sc.get("actors") or []) if isinstance(a, dict)]
        place = places.resolve(sc.get("place"))
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
                if same % 3 == 2 and not has_ov and not sc.get("shot"):
                    sc["shot"] = "close"
                elif same % 3 == 1 and str(acts[0].get("action") or "") in ("", "idle"):
                    acts[0]["action"] = "look_around"
        prev_place = place
    return scenes


def render_scene(scene: dict, cast: dict, dur: float, out: Path, words=(), t0=0.0, still: Path = None):
    """scene: {"place", "time", "weather", "props", "actors": [{"id", "action", "emotion", "emote", "pos", "to", "speaks"}]}.
    words: [(wort, start, ende)] der ganzen Sprecherspur; t0 = Startzeit der Szene darin."""
    place, night, scale, actors, props, weather = _prepare(scene, cast)
    bg = places.background(place, night)
    n_frames = max(2, round(dur * FPS))
    shot = str(scene.get("shot") or "").lower()
    has_ov = isinstance(scene.get("overlay"), dict) and scene["overlay"].get("type")
    moving = any(a["x0"] != a["x1"] for a in actors)
    shot = "close" if shot == "close" and not has_ov and not moving and not props else ""
    ff = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
                           "-crf", "17", "-pix_fmt", "yuv420p", str(out)], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for fidx in range(n_frames):
            t = fidx / FPS
            frame = _frame(bg, place, night, scale, actors, props, weather, t, dur, words, t0, place == "bedroom", shot)
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
    scene = {"place": spec.get("place") or "plain", "time": spec.get("time"), "weather": spec.get("weather"),
             "props": spec.get("props") or [],
             "actors": [{"id": spec.get("actor") or next(iter(cast), "held"), "kind": spec.get("kind") or "",
                         "action": spec.get("action") or "shocked", "emotion": spec.get("emotion") or "shocked",
                         "emote": " ", "pos": "center"}]}
    place, night, _, actors, props, weather = _prepare(scene, cast)
    frame = _frame(places.background(place, night), place, night, 1.5, actors, props, weather, 1.0, 3.0, (), 0.0, False)
    # so beschneiden, dass die Figur groß in der unteren Bildhälfte sitzt und das obere Drittel für den Text frei bleibt
    frame = frame.crop((135, 0, 945, 1440)).resize((W, H), Image.LANCZOS)
    frame.save(out, quality=93)
