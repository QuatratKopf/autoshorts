"""Bühne: setzt Figuren auf einen Ort und rendert die Szene Bild für Bild (30 fps) als Video.
Figuren bewegen sich (gehen, rennen, springen …), blinzeln und bewegen den Mund passend zur Sprecherstimme."""
import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from . import places, rig

W, H, FPS = 1080, 1920, 30
SCALE = 1.45
POS = {"left": 250, "center": 540, "right": 830, "offleft": -220, "offright": 1300,
       "links": 250, "mitte": 540, "rechts": 830}


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


def _shadow(frame, x, y, w):
    d = ImageDraw.Draw(frame, "RGBA")
    d.ellipse((x - w, y - w * 0.16, x + w, y + w * 0.16), fill=(0, 0, 0, 70))


def _extras(d, pose, hx, hy, t):
    if pose.extra.get("zzz"):
        for i in range(3):
            ph = (t * 0.7 + i * 0.33) % 1
            s = 30 + 30 * ph
            x, y = hx + 60 + ph * 120, hy - 80 - ph * 220
            d.line((x, y, x + s, y, x, y + s, x + s, y + s), fill=(255, 255, 255, int(255 * (1 - ph))), width=8, joint="curve")
    if "dots" in pose.extra:
        for i in range(pose.extra["dots"]):
            d.ellipse((hx + 150 + i * 46, hy - 170, hx + 180 + i * 46, hy - 140), fill=(255, 255, 255, 255), outline=rig.INK, width=4)


def render_scene(scene: dict, cast: dict, dur: float, out: Path, words=(), t0=0.0, still: Path = None):
    """scene: {"place", "time", "actors": [{"id", "action", "emotion", "pos", "to", "speaks"}]}.
    words: [(wort, start, ende)] der ganzen Sprecherspur; t0 = Startzeit der Szene darin."""
    night = str(scene.get("time") or "").lower() in ("night", "nacht", "abend", "evening")
    bg = places.background(scene.get("place"), night)
    actors = []
    in_bed = places.ALIASES.get(str(scene.get("place") or "").lower(), str(scene.get("place") or "").lower()) == "bedroom"
    raw = scene.get("actors") or [{"id": next(iter(cast), "held"), "action": "talk", "speaks": True}]
    n_frames = max(2, round(dur * FPS))
    ov = scene.get("overlay") if isinstance(scene.get("overlay"), dict) else {}
    SCALE = 1.0 if str(ov.get("type")) in ("phone", "checklist", "note") else globals()["SCALE"]   # Platz für hohe Einblendungen
    for i, a in enumerate(raw[:3]):
        aid = str(a.get("id") or f"a{i}")
        default_x = (540,) if len(raw) == 1 else ((330, 750) if len(raw) == 2 else (220, 540, 860))
        x0 = _x(a.get("pos"), default_x[min(i, len(default_x) - 1)])
        x1 = _x(a.get("to"), x0) if a.get("to") else x0
        action = str(a.get("action") or "idle").lower()
        if x1 != x0 and action not in ("walk", "run"):
            action = "walk"
        if action in ("walk", "run") and x1 == x0:       # ohne Ziel: von außen hereinkommen
            x0 = -220 if x0 <= 540 else 1300
        actors.append({"look": rig.Look.from_spec(cast.get(aid) or {}), "action": action, "emotion": a.get("emotion") or "",
                       "x0": x0, "x1": x1, "speaks": bool(a.get("speaks")), "seed": i * 5 + len(aid),
                       "face": a.get("facing")})
    if actors and not any(a["speaks"] for a in actors):
        actors[0]["speaks"] = len(actors) == 1
    ff = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
                           "-crf", "17", "-pix_fmt", "yuv420p", str(out)], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for fidx in range(n_frames):
            t = fidx / FPS
            frame = bg.copy()
            over = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            od = ImageDraw.Draw(over)
            for a in sorted(actors, key=lambda q: q["speaks"]):
                moving = a["x1"] != a["x0"]
                move_t = min(dur * 0.75, abs(a["x1"] - a["x0"]) / (330 if a["action"] == "walk" else 620)) if moving else 0
                arrived = moving and t >= move_t
                x = a["x1"] if arrived else (a["x0"] + (a["x1"] - a["x0"]) * (t / move_t) if moving else a["x0"])
                action = ("talk" if a["speaks"] else "idle") if arrived else a["action"]
                mouth = _mouth(t0 + t, words) if a["speaks"] else 0.0
                if action == "idle" and a["speaks"]:
                    action = "talk"
                pose, _ = rig.pose_at(action, t if not arrived else t - move_t, dur, a["emotion"], mouth, a["seed"])
                if moving and not arrived:
                    facing = 1 if a["x1"] > a["x0"] else -1
                elif a["face"] in ("left", "links"):
                    facing = -1
                elif a["face"] in ("right", "rechts"):
                    facing = 1
                else:
                    facing = 1 if x < 600 else -1
                    if len(actors) == 1:
                        facing = 1
                im, fx, fy = rig.draw(a["look"], pose, facing, SCALE)
                gy = places.GROUND + (18 if a["speaks"] else 0)
                if pose.lying and in_bed:      # im Schlafzimmer liegt die Figur im Bett
                    x, gy = 300, places.GROUND - 150
                _shadow(frame, int(x), gy, int(95 * SCALE * (1 - min(0.5, pose.lift / 200))))
                frame.paste(im, (int(x - fx), int(gy - fy)), im)
                _extras(od, pose, x, gy - 430 * SCALE * a["look"].size, t)
            frame.paste(over, (0, 0), over)
            if fidx == min(n_frames - 1, FPS // 2) and still is not None:
                frame.save(still, quality=92)
            ff.stdin.write(frame.tobytes())
        ff.stdin.close()
        err = ff.stderr.read().decode()[-500:]
        if ff.wait() != 0:
            raise RuntimeError("ffmpeg (Toon): " + err)
    finally:
        if ff.poll() is None:
            ff.kill()
