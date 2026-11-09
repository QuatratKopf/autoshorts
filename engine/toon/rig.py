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
# Stil: Mischung aus Strichmännchen und niedlichem Cartoon – großer runder Kopf mit großen Augen und roten Wangen,
# kleiner Bohnen-Körper in Farbe, dünne Strich-Arme und -Beine, überall kräftige dunkle Umrisse.

OUT = 7          # Umriss-Stärke (px bei Maßstab 1)
CHEEK = (255, 150, 150)


def _pt(p0, ang, ln):
    return p0[0] + math.sin(math.radians(ang)) * ln, p0[1] + math.cos(math.radians(ang)) * ln


def _stroke(d, pts, w, col):
    for a, b in zip(pts, pts[1:]):
        d.line((a[0], a[1], b[0], b[1]), fill=col, width=int(w))
    for x, y in pts:
        d.ellipse((x - w / 2, y - w / 2, x + w / 2, y + w / 2), fill=col)


def _blob(d, box, fill, o):
    x0, y0, x1, y1 = box
    d.ellipse((x0 - o, y0 - o, x1 + o, y1 + o), fill=INK)
    d.ellipse(box, fill=fill)


def _eye(d, cx, cy, r, kind, look):
    white = (255, 255, 255)
    if kind in ("closed", "happy"):
        box = (cx - r, cy - r * 0.5, cx + r, cy + r * 1.1)
        if kind == "happy":
            d.arc(box, 200, 340, fill=INK, width=int(r * 0.42))
        else:
            d.arc((cx - r, cy - r * 1.1, cx + r, cy + r * 0.5), 20, 160, fill=INK, width=int(r * 0.38))
        return
    rx, ry = (r * 1.15, r * 1.4) if kind == "wide" else (r, r * 1.2)
    d.ellipse((cx - rx - r * 0.22, cy - ry - r * 0.22, cx + rx + r * 0.22, cy + ry + r * 0.22), fill=INK)
    d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=white)
    pr = r * (0.42 if kind == "wide" else 0.66)
    px = cx + look * (rx - pr) * 0.8
    py = cy + (ry - pr) * (0.5 if kind in ("sad", "worried") else 0.15)
    d.ellipse((px - pr, py - pr, px + pr, py + pr), fill=INK)
    hr = pr * 0.38
    d.ellipse((px + pr * 0.15, py - pr * 0.7, px + pr * 0.15 + hr * 2, py - pr * 0.7 + hr * 2), fill=white)


def draw(look: Look, pose: Pose, facing=1, scale=1.0):
    """Zeichnet die Figur und gibt (RGBA-Bild, Fußpunkt-x, Fußpunkt-y) im Maßstab 1 zurück."""
    k = SS * scale * look.size
    W, H = int(600 * k), int(740 * k)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f, o = facing, OUT * k
    foot_x, foot_y = W / 2, H - 36 * k
    leg1, leg2, arm1, arm2 = 62 * k, 62 * k, 58 * k, 54 * k
    lw = 15 * k
    hip = (foot_x, foot_y - (leg1 + leg2) * pose.squash - pose.lift * k)
    lean = pose.lean * f
    bh, bw = 128 * k * pose.squash, 104 * k
    top = _pt(hip, 180 - lean, bh)                       # Hals
    shoulder = _pt(hip, 180 - lean, bh * 0.74)
    skin = look.skin if look.skin != SKINS["schwarz"] else (252, 250, 244)   # heller Kopf wirkt freundlicher
    dark = tuple(max(0, int(c * 0.8)) for c in look.shirt)

    def limb(p0, a1, l1, a2, l2, hand=None, shoe=False):
        p1 = _pt(p0, a1, l1)
        p2 = _pt(p1, a1 + a2, l2)
        _stroke(d, [p0, p1, p2], lw, INK)
        if hand:
            r = 15 * k
            _blob(d, (p2[0] - r, p2[1] - r, p2[0] + r, p2[1] + r), hand, o * 0.7)
        if shoe:
            d.rounded_rectangle((p2[0] - 16 * k + 12 * k * f, p2[1] - 12 * k, p2[0] + 22 * k + 12 * k * f, p2[1] + 14 * k), 12 * k, fill=INK)
        return p2

    # hinterer Arm, Beine
    limb(shoulder, pose.arm_l * f + lean, arm1, pose.fore_l * f, arm2, hand=skin)
    hl = (hip[0] - 20 * k, hip[1] - 8 * k)
    hr_ = (hip[0] + 20 * k, hip[1] - 8 * k)
    limb(hl, pose.leg_l * f, leg1, -pose.knee_l * f, leg2, shoe=True)
    limb(hr_, pose.leg_r * f, leg1, -pose.knee_r * f, leg2, shoe=True)

    # Bohnen-Körper (Kapsel mit Umriss), unten etwas breiter
    b0 = _pt(hip, 180 - lean, bw * 0.42)
    b1 = _pt(hip, 180 - lean, bh - bw * 0.40)
    _stroke(d, [b0, b1], bw + 2 * o, INK)
    _stroke(d, [b0, b1], bw, look.shirt)
    belly = _pt(hip, 180 - lean, bw * 0.40)
    d.ellipse((belly[0] - bw * 0.30 + 8 * k * f, belly[1] - bw * 0.26, belly[0] + bw * 0.30 + 8 * k * f, belly[1] + bw * 0.30),
              fill=tuple(min(255, int(c * 1.14 + 10)) for c in look.shirt))   # heller Bauchfleck

    # Kopf
    hr = 98 * k
    ha = pose.head * f + lean
    hc = _pt(top, 180 - ha, hr * 0.82)
    if look.hair == "long":
        d.rounded_rectangle((hc[0] - hr * 1.08 - o, hc[1] - hr * 0.5, hc[0] + hr * 1.08 + o, hc[1] + hr * 1.3 + o), hr * 0.5, fill=INK)
        d.rounded_rectangle((hc[0] - hr * 1.08, hc[1] - hr * 0.5, hc[0] + hr * 1.08, hc[1] + hr * 1.3), hr * 0.5, fill=(96, 62, 44))
    if look.hair == "bun":
        _blob(d, (hc[0] - hr * 0.4, hc[1] - hr * 1.5, hc[0] + hr * 0.4, hc[1] - hr * 0.8), (96, 62, 44), o)
    _blob(d, (hc[0] - hr, hc[1] - hr * 0.94, hc[0] + hr, hc[1] + hr * 0.94), skin, o)
    if look.hair in ("long", "bun"):
        d.chord((hc[0] - hr, hc[1] - hr * 0.94, hc[0] + hr, hc[1] + hr * 0.5), 185, 355, fill=(96, 62, 44))
    # Gesicht (leicht in Blickrichtung versetzt)
    ex, ey, er = hc[0] + 16 * k * f, hc[1] + 2 * k, 23 * k
    lk = pose.look if pose.look else 0.45 * f
    for sgn in (-1, 1):
        _eye(d, ex + sgn * 36 * k, ey, er, pose.eyes, lk)
        cx, cy = ex + sgn * 62 * k, ey + 40 * k
        d.ellipse((cx - 17 * k, cy - 10 * k, cx + 17 * k, cy + 10 * k), fill=CHEEK)
    if pose.eyes in ("angry", "sad", "worried"):
        for sgn in (-1, 1):
            x0, y0 = ex + sgn * 36 * k, ey - 44 * k
            dy = (8 if pose.eyes == "angry" else -8) * k * sgn
            d.line((x0 - 20 * k, y0 - dy, x0 + 20 * k, y0 + dy), fill=INK, width=int(8 * k))
    mx, my = ex, ey + 46 * k
    if pose.mouth > 0.08:
        mh = 8 * k + pose.mouth * 26 * k
        d.ellipse((mx - 15 * k, my - mh / 2, mx + 15 * k, my + mh / 2), fill=INK)
        d.ellipse((mx - 8 * k, my + mh * 0.05, mx + 8 * k, my + mh * 0.42), fill=(240, 110, 110))
    elif pose.smile < -0.2:
        d.arc((mx - 16 * k, my - 4 * k, mx + 16 * k, my + 20 * k), 200, 340, fill=INK, width=int(6 * k))
    else:
        wdt = (20 + 8 * max(0, pose.smile)) * k
        d.arc((mx - wdt, my - 22 * k, mx + wdt, my + 8 * k), 25, 155, fill=INK, width=int(6 * k))
    if look.glasses:
        for sgn in (-1, 1):
            d.ellipse((ex + sgn * 36 * k - 34 * k, ey - 36 * k, ex + sgn * 36 * k + 34 * k, ey + 36 * k), outline=INK, width=int(6 * k))
    # Kopfbedeckung
    hcx, ty = hc[0], hc[1] - hr * 0.94
    hat_box = (hcx - hr * 1.02, ty - 10 * k, hcx + hr * 1.02, ty + hr * 1.25)
    if look.hat in ("cap", "helmet", "beanie"):
        col = (242, 140, 40) if look.hat == "helmet" else look.hat_color
        d.chord((hat_box[0] - o, hat_box[1] - o, hat_box[2] + o, hat_box[3] + o), 180, 360, fill=INK)
        d.chord(hat_box, 180, 360, fill=col)
        base = ty + hr * 0.60
        if look.hat == "cap":
            x0, x1 = (hcx, hcx + 150 * k) if f > 0 else (hcx - 150 * k, hcx)
            d.rounded_rectangle((x0, base - 12 * k - o, x1, base + 12 * k), 12 * k, fill=INK)
            d.rounded_rectangle((x0 + o, base - 12 * k, x1 - o, base + 12 * k - o), 10 * k, fill=col)
        elif look.hat == "helmet":
            _blob(d, (hcx + 40 * k * f - 17 * k, ty + 8 * k, hcx + 40 * k * f + 17 * k, ty + 42 * k), (255, 242, 150), o * 0.6)
        else:
            _blob(d, (hcx - 20 * k, ty - 44 * k, hcx + 20 * k, ty - 4 * k), col, o * 0.8)
    elif look.hat == "bow":
        bx, by = hcx - 56 * k * f, ty + 18 * k
        for sgn in (-1, 1):
            d.polygon([(bx, by), (bx + sgn * 44 * k, by - 30 * k), (bx + sgn * 44 * k, by + 30 * k)], fill=INK)
            d.polygon([(bx + sgn * 6 * k, by), (bx + sgn * 38 * k, by - 20 * k), (bx + sgn * 38 * k, by + 20 * k)], fill=look.hat_color)
    elif look.hat == "crown":
        y0 = ty + 14 * k
        pts = [(hcx - 56 * k, y0), (hcx - 56 * k, y0 - 54 * k), (hcx - 28 * k, y0 - 26 * k), (hcx, y0 - 64 * k),
               (hcx + 28 * k, y0 - 26 * k), (hcx + 56 * k, y0 - 54 * k), (hcx + 56 * k, y0)]
        d.polygon(pts, fill=(250, 200, 40), outline=INK, width=int(o))

    # vorderer Arm
    limb(shoulder, pose.arm_r * f + lean, arm1, pose.fore_r * f, arm2, hand=skin)

    if pose.lying:
        im = im.rotate(90 * f, expand=True, resample=Image.BICUBIC)
        foot_x, foot_y = im.width / 2, im.height / 2 + 120 * k
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
        p.arm_r, p.fore_r = 118, 30 + 30 * s(t * 9)
        p.smile = 0.8
        p.head = 4 * s(t * 3)
    elif a == "point":
        p.arm_r, p.fore_r = 95, 0
        p.lean = 4
    elif a in ("shocked", "scared"):
        j = max(0.0, 1 - t / 0.35)
        p.lift = 60 * s(min(1, t / 0.35) * math.pi) if t < 0.35 else 0
        p.arm_l, p.fore_l, p.arm_r, p.fore_r = -130, -30, 130, 30
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
        p.arm_l, p.fore_l, p.arm_r, p.fore_r = -140, -15, 140, 15
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
        p.lift = -60
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
