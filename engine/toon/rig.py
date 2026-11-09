"""Figuren aus Einzelteilen (wie in Erklär-Shorts): runder Kopf mit großen Augen, Kapuzenpulli-Rumpf, Strich-Arme
und -Beine. Eine Pose ist ein Satz Gelenkwinkel; Aktionen berechnen die Pose für jeden Zeitpunkt.

Koordinaten in Pixeln bei Maßstab 1 (Videobreite 1080). Gezeichnet wird mit Faktor SS (Supersampling) für glatte Kanten.
"""
import math
from dataclasses import dataclass, field

from PIL import Image, ImageDraw

SS = 2
INK = (22, 22, 26)

COLORS = {
    "blau": (46, 110, 220), "rot": (214, 64, 56), "grün": (70, 150, 80), "gelb": (240, 196, 50),
    "orange": (236, 128, 44), "lila": (128, 82, 190), "pink": (232, 112, 160), "türkis": (40, 170, 170),
    "grau": (120, 124, 132), "weiß": (236, 236, 232), "schwarz": (30, 30, 34), "braun": (130, 86, 54),
    "beige": (214, 190, 150), "oliv": (128, 140, 70),
}
SKINS = {"schwarz": (22, 22, 26), "hell": (246, 214, 186), "mittel": (210, 160, 118), "dunkel": (124, 84, 58),
         "weiß": (244, 244, 240), "gelb": (250, 214, 70), "grün": (120, 190, 90)}


def color(name, default):
    if isinstance(name, (list, tuple)) and len(name) == 3:
        return tuple(int(v) for v in name)
    return COLORS.get(str(name or "").lower().strip(), default)


@dataclass
class Look:
    shirt: tuple = COLORS["blau"]
    pants: tuple = (40, 40, 48)
    skin: tuple = SKINS["schwarz"]
    hat: str = ""            # cap | helmet | bow | beanie | crown | ""
    hat_color: tuple = COLORS["rot"]
    glasses: bool = False
    hair: str = ""           # long | bun | ""
    size: float = 1.0

    @staticmethod
    def from_spec(spec: dict):
        spec = spec or {}
        return Look(shirt=color(spec.get("shirt"), COLORS["blau"]), pants=color(spec.get("pants"), (40, 40, 48)),
                    skin=SKINS.get(str(spec.get("skin") or "").lower(), SKINS["schwarz"]),
                    hat=str(spec.get("hat") or "").lower(), hat_color=color(spec.get("hat_color"), COLORS["rot"]),
                    glasses=bool(spec.get("glasses")), hair=str(spec.get("hair") or "").lower(),
                    size=max(0.6, min(1.3, float(spec.get("size") or 1.0))))


@dataclass
class Pose:
    # Winkel in Grad, 0 = nach unten hängend, positiv = nach vorne (in Blickrichtung)
    arm_l: float = 8          # Schulter hinten
    fore_l: float = 10
    arm_r: float = -8         # Schulter vorne
    fore_r: float = -10
    leg_l: float = 4
    knee_l: float = 0
    leg_r: float = -4
    knee_r: float = 0
    lean: float = 0           # Oberkörper-Neigung
    head: float = 0           # Kopf-Neigung
    lift: float = 0           # ganzer Körper nach oben (Sprung/Wippen), px
    squash: float = 1.0       # Atmen / Stauchen
    eyes: str = "normal"      # normal | wide | happy | sad | angry | closed | worried
    look: float = 0.0         # Blickrichtung der Pupillen -1..1
    mouth: float = 0.0        # 0 zu … 1 weit offen
    smile: float = 0.0        # -1 traurig … 1 Lächeln
    lying: bool = False
    extra: dict = field(default_factory=dict)


# ------------------------------------------------------------------ Zeichnen

def _limb(d, p0, a1, l1, a2, l2, w, col):
    """Zwei Segmente (Ober-/Unterteil) mit runden Gelenken. Winkel in Grad ab senkrecht nach unten."""
    x0, y0 = p0
    x1 = x0 + math.sin(math.radians(a1)) * l1
    y1 = y0 + math.cos(math.radians(a1)) * l1
    x2 = x1 + math.sin(math.radians(a1 + a2)) * l2
    y2 = y1 + math.cos(math.radians(a1 + a2)) * l2
    for (ax, ay), (bx, by) in (((x0, y0), (x1, y1)), ((x1, y1), (x2, y2))):
        d.line((ax, ay, bx, by), fill=col, width=int(w))
    for (cx, cy) in ((x0, y0), (x1, y1), (x2, y2)):
        r = w / 2
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col)
    return x2, y2


def _eye(d, cx, cy, r, kind, look, flip):
    white = (250, 250, 248)
    if kind == "closed":
        d.arc((cx - r, cy - r * 0.4, cx + r, cy + r * 0.9), 200, 340, fill=white, width=int(r * 0.32))
        return
    if kind == "happy":
        d.arc((cx - r, cy - r * 0.2, cx + r, cy + r * 1.6), 200, 340, fill=white, width=int(r * 0.38))
        return
    rx, ry = r, r * 1.18
    if kind == "wide":
        rx, ry = r * 1.18, r * 1.4
    d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=white)
    pr = r * (0.34 if kind == "wide" else 0.5)
    px = cx + look * r * 0.38 * flip
    py = cy + (r * 0.15 if kind in ("sad", "worried") else r * 0.05)
    d.ellipse((px - pr, py - pr, px + pr, py + pr), fill=INK)
    d.ellipse((px - pr * 0.35 + pr * 0.3, py - pr * 0.7, px + pr * 0.1 + pr * 0.3, py - pr * 0.25), fill=white)


def draw(look: Look, pose: Pose, facing=1, scale=1.0):
    """Zeichnet die Figur und gibt (RGBA-Bild, Fußpunkt-x, Fußpunkt-y) im Maßstab 1 zurück."""
    k = SS * scale * look.size
    W, H = int(520 * k), int(760 * k)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    foot_x, foot_y = W / 2, H - 40 * k
    hip = (foot_x, foot_y - 220 * k * pose.squash - pose.lift * k)
    leg_w, arm_w = 26 * k, 24 * k
    shirt, dark = look.shirt, tuple(max(0, int(c * 0.78)) for c in look.shirt)
    f = facing

    # Beine (hinteres zuerst)
    for a, kn, col in ((pose.leg_l, pose.knee_l, tuple(int(c * 0.82) for c in look.pants)), (pose.leg_r, pose.knee_r, look.pants)):
        end = _limb(d, (hip[0] + (-10 if a > 0 else 10) * k * f * 0, hip[1]), a * f, 108 * k, -kn * f, 112 * k, leg_w, col)
        sx, sy = end
        d.rounded_rectangle((sx - 18 * k + 14 * k * f, sy - 10 * k, sx + 22 * k + 14 * k * f, sy + 16 * k), 10 * k, fill=INK)

    # Rumpf
    lean = math.radians(pose.lean * f)
    th = 190 * k * pose.squash
    neck = (hip[0] + math.sin(lean) * th, hip[1] - math.cos(lean) * th)
    shoulder = (hip[0] + math.sin(lean) * th * 0.86, hip[1] - math.cos(lean) * th * 0.86)

    # hinterer Arm (hinter dem Körper)
    _limb(d, shoulder, pose.arm_l * f + pose.lean * f, 92 * k, pose.fore_l * f, 88 * k, arm_w, dark)
    # Rumpf als Kapsel (dicke Linie mit runden Enden) plus Kapuzenkragen
    bw = 104 * k
    top = (hip[0] + math.sin(lean) * (th - bw * 0.35), hip[1] - math.cos(lean) * (th - bw * 0.35))
    bot = (hip[0] + math.sin(lean) * bw * 0.2, hip[1] - math.cos(lean) * bw * 0.2)
    d.line((bot[0], bot[1], top[0], top[1]), fill=shirt, width=int(bw))
    for cx, cy in (top, bot):
        d.ellipse((cx - bw / 2, cy - bw / 2, cx + bw / 2, cy + bw / 2), fill=shirt)
    d.ellipse((neck[0] - 50 * k, neck[1] - 6 * k, neck[0] + 50 * k, neck[1] + 34 * k), fill=dark)

    # Kopf
    hr = 74 * k
    ha = math.radians(pose.head * f) + lean
    hc = (neck[0] + math.sin(ha) * hr * 1.0, neck[1] - math.cos(ha) * hr * 1.0)
    if look.hair == "long":
        d.rounded_rectangle((hc[0] - hr * 1.05, hc[1] - hr * 0.6, hc[0] + hr * 1.05, hc[1] + hr * 1.25), hr * 0.5, fill=(60, 40, 30))
    d.ellipse((hc[0] - hr, hc[1] - hr, hc[0] + hr, hc[1] + hr), fill=look.skin)
    if look.hair == "bun":
        d.ellipse((hc[0] - hr * 0.35, hc[1] - hr * 1.45, hc[0] + hr * 0.35, hc[1] - hr * 0.8), fill=(60, 40, 30))
    # Augen
    ex = hc[0] + 14 * k * f
    ey = hc[1] - 6 * k
    er = 17 * k
    for dx in (-24 * k, 24 * k):
        _eye(d, ex + dx, ey, er, pose.eyes, pose.look if pose.look else 0.6 * f, 1)
    # Augenbrauen bei Gefühlen
    if pose.eyes in ("angry", "sad", "worried"):
        light = (250, 250, 248)
        for s in (-1, 1):
            x0 = ex + s * 24 * k
            if pose.eyes == "angry":
                d.line((x0 - 16 * k, ey - 34 * k - s * 6 * k, x0 + 16 * k, ey - 34 * k + s * 6 * k), fill=light, width=int(6 * k))
            else:
                d.line((x0 - 16 * k, ey - 32 * k + s * 6 * k, x0 + 16 * k, ey - 32 * k - s * 6 * k), fill=light, width=int(6 * k))
    # Mund
    mx, my = ex, hc[1] + 36 * k
    mcol = (250, 250, 248) if look.skin == SKINS["schwarz"] else INK
    if pose.mouth > 0.08:
        mh = 6 * k + pose.mouth * 22 * k
        d.ellipse((mx - 12 * k, my - mh / 2, mx + 12 * k, my + mh / 2), fill=mcol)
    elif pose.smile > 0.2:
        d.arc((mx - 18 * k, my - 16 * k, mx + 18 * k, my + 8 * k), 20, 160, fill=mcol, width=int(5 * k))
    elif pose.smile < -0.2:
        d.arc((mx - 16 * k, my - 2 * k, mx + 16 * k, my + 22 * k), 200, 340, fill=mcol, width=int(5 * k))
    if look.glasses:
        for dx in (-24 * k, 24 * k):
            d.ellipse((ex + dx - 24 * k, ey - 24 * k, ex + dx + 24 * k, ey + 24 * k), outline=(250, 250, 248), width=int(4 * k))
        d.line((ex - 2 * k, ey, ex + 2 * k, ey), fill=(250, 250, 248), width=int(4 * k))
    # Kopfbedeckung
    hcx, top = hc[0], hc[1] - hr
    if look.hat == "cap":
        d.chord((hcx - hr * 0.98, top - 6 * k, hcx + hr * 0.98, top + hr * 1.1), 180, 360, fill=look.hat_color)
        d.rounded_rectangle((hcx + (10 if f > 0 else -110) * k, top + hr * 0.42, hcx + (110 if f > 0 else -10) * k, top + hr * 0.58), 6 * k, fill=look.hat_color)
    elif look.hat == "helmet":
        d.chord((hcx - hr * 1.04, top - 10 * k, hcx + hr * 1.04, top + hr * 1.2), 180, 360, fill=(236, 128, 44))
        d.ellipse((hcx + 30 * k * f - 14 * k, top + 6 * k, hcx + 30 * k * f + 14 * k, top + 34 * k), fill=(255, 240, 160))
    elif look.hat == "beanie":
        d.chord((hcx - hr * 1.0, top - 16 * k, hcx + hr * 1.0, top + hr * 1.1), 180, 360, fill=look.hat_color)
        d.ellipse((hcx - 14 * k, top - 34 * k, hcx + 14 * k, top - 6 * k), fill=look.hat_color)
    elif look.hat == "bow":
        bx, by = hcx - 40 * k * f, top + 14 * k
        d.polygon([(bx, by), (bx - 30 * k, by - 22 * k), (bx - 30 * k, by + 22 * k)], fill=look.hat_color)
        d.polygon([(bx, by), (bx + 30 * k, by - 22 * k), (bx + 30 * k, by + 22 * k)], fill=look.hat_color)
    elif look.hat == "crown":
        y0 = top + 4 * k
        d.polygon([(hcx - 46 * k, y0), (hcx - 46 * k, y0 - 44 * k), (hcx - 22 * k, y0 - 20 * k), (hcx, y0 - 52 * k),
                   (hcx + 22 * k, y0 - 20 * k), (hcx + 46 * k, y0 - 44 * k), (hcx + 46 * k, y0)], fill=(246, 196, 40))

    # vorderer Arm
    _limb(d, shoulder, pose.arm_r * f + pose.lean * f, 92 * k, pose.fore_r * f, 88 * k, arm_w, shirt)

    if pose.lying:
        im = im.rotate(90 * f, expand=True, resample=Image.BICUBIC)
        foot_x, foot_y = im.width / 2, im.height - 60 * k
    out = im.resize((max(1, im.width // SS), max(1, im.height // SS)), Image.LANCZOS)
    return out, foot_x / SS, foot_y / SS


# ------------------------------------------------------------------ Aktionen

def _blink(t, seed):
    period = 2.6 + (seed % 7) * 0.31
    ph = (t + seed * 0.37) % period
    return ph < 0.12


def pose_at(action, t, dur, emotion="", mouth=0.0, seed=0):
    """Pose für Aktion zum Zeitpunkt t (Sekunden seit Szenenbeginn). Gibt (Pose, Fortschritt 0..1 der Bewegung)."""
    p = Pose()
    s = math.sin
    prog = min(1.0, t / max(0.3, dur))
    p.squash = 1 + 0.012 * s(t * 2.4 + seed)
    p.arm_l = 8 + 3 * s(t * 1.6 + seed)
    p.arm_r = -8 - 3 * s(t * 1.6 + seed + 1)
    a = (action or "idle").lower()

    if a in ("walk", "run"):
        sp = 9.0 if a == "walk" else 15.0
        amp = 26 if a == "walk" else 42
        ph = t * sp
        p.leg_l, p.leg_r = amp * s(ph), -amp * s(ph)
        p.knee_l, p.knee_r = max(0, 30 * s(ph + 1.4)), max(0, 30 * s(ph + 1.4 + math.pi))
        p.arm_l, p.arm_r = -amp * 0.8 * s(ph), amp * 0.8 * s(ph)
        p.fore_l = p.fore_r = 18 if a == "walk" else 70
        p.lift = abs(s(ph)) * (8 if a == "walk" else 18)
        p.lean = 4 if a == "walk" else 14
    elif a == "wave":
        p.arm_r, p.fore_r = 125, 35 + 30 * s(t * 9)
        p.smile = 0.8
        p.head = 4 * s(t * 3)
    elif a == "point":
        p.arm_r, p.fore_r = 95, 0
        p.lean = 4
    elif a in ("shocked", "scared"):
        j = max(0.0, 1 - t / 0.35)
        p.lift = 60 * s(min(1, t / 0.35) * math.pi) if t < 0.35 else 0
        p.arm_l, p.fore_l, p.arm_r, p.fore_r = 140, 40, 140, -40
        p.eyes = "wide"
        p.lean = -6 + 3 * s(t * 30) * (0.3 + j)
        p.leg_l, p.leg_r = 10, -10
    elif a == "sad":
        p.head, p.lean = 18, 10
        p.arm_l, p.arm_r = 2, -2
        p.eyes, p.smile = "sad", -0.8
        p.squash = 0.96
    elif a in ("jump", "happy", "cheer"):
        ph = (t * 2.2) % 1.0
        p.lift = 70 * s(ph * math.pi)
        p.arm_l, p.fore_l, p.arm_r, p.fore_r = 160, -20, 160, 20
        p.leg_l, p.knee_l, p.leg_r, p.knee_r = 20 * (1 - s(ph * math.pi)), 40 * s(ph * math.pi), -10, 30 * s(ph * math.pi)
        p.eyes, p.smile = "happy", 1
    elif a == "think":
        p.arm_r, p.fore_r = 40, 120
        p.head = -8
        p.look = 0.0
        p.eyes = "normal"
        p.extra["dots"] = int(t * 2.5) % 4
    elif a == "sit":
        p.leg_l, p.knee_l, p.leg_r, p.knee_r = 80, -80, 76, -80
        p.lift = -95
        p.arm_r, p.fore_r = 40, 30
    elif a == "sleep":
        p.lying = True
        p.eyes = "closed"
        p.squash = 1 + 0.03 * s(t * 1.5)
        p.extra["zzz"] = True
    elif a == "talk":
        p.arm_r, p.fore_r = 40 + 20 * s(t * 3.1 + seed), 50 + 20 * s(t * 4.3)
        p.head = 3 * s(t * 2.7)
    elif a == "look_around":
        p.look = s(t * 1.8)
        p.head = 6 * s(t * 1.8)
    elif a == "fall":
        p.lean = min(90, t * 260)
        p.eyes = "wide"
        p.arm_l, p.arm_r = 160, 160
    elif a == "dance":
        p.lift = 14 * abs(s(t * 6))
        p.arm_l, p.fore_l = 120 + 40 * s(t * 6), 40
        p.arm_r, p.fore_r = 120 - 40 * s(t * 6), -40
        p.leg_l, p.leg_r = 18 * s(t * 6), -18 * s(t * 6)
        p.lean = 8 * s(t * 3)
        p.eyes, p.smile = "happy", 1

    emo = (emotion or "").lower()
    if emo and a not in ("shocked", "jump", "happy", "sad", "sleep"):
        p.eyes = {"happy": "happy", "shocked": "wide", "scared": "wide", "sad": "sad", "angry": "angry",
                  "worried": "worried", "tired": "closed"}.get(emo, p.eyes)
        p.smile = {"happy": 0.8, "sad": -0.8, "angry": -0.6, "worried": -0.4}.get(emo, p.smile)
    if p.eyes not in ("closed", "happy") and _blink(t, seed):
        p.eyes = "closed"
    p.mouth = mouth
    return p, prog
