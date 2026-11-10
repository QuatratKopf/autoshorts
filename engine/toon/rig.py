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
    "blau": (58, 104, 190), "rot": (196, 72, 66), "grün": (74, 138, 92), "gelb": (224, 180, 66),
    "orange": (220, 126, 60), "lila": (118, 88, 170), "pink": (206, 110, 150), "türkis": (52, 150, 152),
    "grau": (112, 118, 128), "weiß": (230, 230, 226), "schwarz": (40, 42, 50), "braun": (126, 90, 62),
    "beige": (204, 184, 150), "oliv": (122, 132, 78),
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
    arm_l: float = -10        # Schulter hinten
    fore_l: float = -6
    arm_r: float = 10         # Schulter vorne
    fore_r: float = 6
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

OUT = 5          # Umriss-Stärke (px bei Maßstab 1)
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
    d.ellipse((cx - rx - r * 0.17, cy - ry - r * 0.17, cx + rx + r * 0.17, cy + ry + r * 0.17), fill=INK)
    d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=white)
    pr = r * (0.38 if kind == "wide" else 0.6)
    px = cx + look * (rx - pr) * 0.8
    py = cy + (ry - pr) * (0.5 if kind in ("sad", "worried") else 0.15)
    d.ellipse((px - pr, py - pr, px + pr, py + pr), fill=INK)
    hr = pr * 0.38
    d.ellipse((px + pr * 0.15, py - pr * 0.7, px + pr * 0.15 + hr * 2, py - pr * 0.7 + hr * 2), fill=white)


def draw(look: Look, pose: Pose, facing=1, scale=1.0, ss=None):
    """Zeichnet die Figur und gibt (RGBA-Bild, Fußpunkt-x, Fußpunkt-y) im Maßstab 1 zurück."""
    SS = ss or globals()["SS"]
    k = SS * scale * look.size
    W, H = int(600 * k), int(740 * k)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f, o = facing, OUT * k
    foot_x, foot_y = W / 2, H - 36 * k
    leg1, leg2, arm1, arm2 = 80 * k, 78 * k, 66 * k, 60 * k
    lw = 21 * k
    hip = (foot_x, foot_y - (leg1 + leg2) * pose.squash - pose.lift * k)
    lean = pose.lean * f
    bh, bw = 150 * k * pose.squash, 90 * k
    top = _pt(hip, 180 - lean, bh)                       # Hals
    shoulder = _pt(hip, 180 - lean, bh * 0.74)
    skin = look.skin if look.skin != SKINS["schwarz"] else (250, 244, 232)
    dark = tuple(max(0, int(c * 0.8)) for c in look.shirt)

    def limb(p0, a1, l1, a2, l2, hand=None, shoe=False, col=INK):
        p1 = _pt(p0, a1, l1)
        p2 = _pt(p1, a1 + a2, l2)
        _stroke(d, [p0, p1, p2], lw + 2 * o, INK)
        _stroke(d, [p0, p1, p2], lw, col)
        if hand:
            r = 13 * k
            _blob(d, (p2[0] - r, p2[1] - r, p2[0] + r, p2[1] + r), hand, o * 0.7)
        if shoe:
            d.rounded_rectangle((p2[0] - 16 * k + 12 * k * f, p2[1] - 12 * k, p2[0] + 22 * k + 12 * k * f, p2[1] + 14 * k), 12 * k, fill=INK)
        return p2

    # hinterer Arm, Beine
    sh_b = (shoulder[0] - 34 * k * f, shoulder[1] + 6 * k)      # hintere / vordere Schulter (leicht frontal gezeichnet)
    sh_f = (shoulder[0] + 34 * k * f, shoulder[1] + 6 * k)
    limb(sh_b, pose.arm_l * f + lean, arm1, pose.fore_l * f, arm2, hand=skin, col=dark)
    hl = (hip[0] - 18 * k, hip[1] - 8 * k)
    hr_ = (hip[0] + 18 * k, hip[1] - 8 * k)
    limb(hl, pose.leg_l * f, leg1, -pose.knee_l * f, leg2, shoe=True, col=tuple(int(c * 0.85) for c in look.pants))
    limb(hr_, pose.leg_r * f, leg1, -pose.knee_r * f, leg2, shoe=True, col=look.pants)

    # Bohnen-Körper (Kapsel mit Umriss), unten etwas breiter
    b0 = _pt(hip, 180 - lean, bw * 0.42)
    b1 = _pt(hip, 180 - lean, bh - bw * 0.40)
    _stroke(d, [b0, b1], bw + 2 * o, INK)
    _stroke(d, [b0, b1], bw, look.shirt)
    hood = _pt(hip, 180 - lean, bh - 8 * k)                                   # Kapuze im Nacken + Reißverschluss + Tasche
    d.ellipse((hood[0] - 46 * k, hood[1] - 22 * k, hood[0] + 46 * k, hood[1] + 26 * k), fill=dark, outline=INK, width=int(o))
    z0, z1 = _pt(hip, 180 - lean, bh - 20 * k), _pt(hip, 180 - lean, bw * 0.2)
    d.line((z0[0] + 4 * k * f, z0[1], z1[0] + 4 * k * f, z1[1]), fill=dark, width=int(4 * k))
    pk = _pt(hip, 180 - lean, bw * 0.46)
    d.rounded_rectangle((pk[0] - 26 * k, pk[1] - 12 * k, pk[0] + 26 * k, pk[1] + 14 * k), 8 * k, fill=dark)

    # Kopf
    hr = 72 * k
    ha = pose.head * f + lean
    hc = _pt(top, 180 - ha, hr * 0.82)
    if look.hair == "long":
        d.rounded_rectangle((hc[0] - hr * 1.08 - o, hc[1] - hr * 0.5, hc[0] + hr * 1.08 + o, hc[1] + hr * 1.3 + o), hr * 0.5, fill=INK)
        d.rounded_rectangle((hc[0] - hr * 1.08, hc[1] - hr * 0.5, hc[0] + hr * 1.08, hc[1] + hr * 1.3), hr * 0.5, fill=(96, 62, 44))
    if look.hair == "bun":
        _blob(d, (hc[0] - hr * 0.4, hc[1] - hr * 1.5, hc[0] + hr * 0.4, hc[1] - hr * 0.8), (96, 62, 44), o)
    _blob(d, (hc[0] - hr, hc[1] - hr * 0.94, hc[0] + hr, hc[1] + hr * 0.94), skin, o)
    if look.hair in ("long", "bun"):
        d.chord((hc[0] - hr, hc[1] - hr * 0.94, hc[0] + hr, hc[1] - hr * 0.05), 180, 360, fill=(96, 62, 44))
    u = k * 0.76
    # Gesicht (leicht in Blickrichtung versetzt)
    ex, ey, er = hc[0] + 16 * u * f, hc[1] + 2 * u, 19 * u
    lk = pose.look if pose.look else 0.45 * f
    for sgn in (-1, 1):
        _eye(d, ex + sgn * 36 * u, ey, er, pose.eyes, lk)
    if pose.eyes in ("angry", "sad", "worried"):
        for sgn in (-1, 1):
            x0, y0 = ex + sgn * 36 * u, ey - 44 * u
            dy = (-9 if pose.eyes == "angry" else 8) * u * sgn      # wütend: innen tiefer · traurig/besorgt: innen höher
            d.line((x0 - 20 * u, y0 - dy, x0 + 20 * u, y0 + dy), fill=INK, width=int(8 * u))
    mx, my = ex, ey + 46 * u
    if pose.mouth > 0.08:
        mh = 8 * u + pose.mouth * 26 * u
        d.ellipse((mx - 15 * u, my - mh / 2, mx + 15 * u, my + mh / 2), fill=INK)
        d.ellipse((mx - 8 * u, my + mh * 0.05, mx + 8 * u, my + mh * 0.42), fill=(240, 110, 110))
    elif pose.smile < -0.2:
        d.arc((mx - 16 * u, my - 4 * u, mx + 16 * u, my + 20 * u), 200, 340, fill=INK, width=int(6 * u))
    else:
        wdt = (20 + 8 * max(0, pose.smile)) * u
        d.arc((mx - wdt, my - 22 * u, mx + wdt, my + 8 * u), 25, 155, fill=INK, width=int(6 * u))
    if look.glasses:
        for sgn in (-1, 1):
            d.ellipse((ex + sgn * 36 * u - 30 * u, ey - 31 * u, ex + sgn * 36 * u + 30 * u, ey + 31 * u), outline=INK, width=int(5 * u))
    # Kopfbedeckung
    hcx, ty = hc[0], hc[1] - hr * 0.94
    hat_box = (hcx - hr * 1.02, ty - 10 * u, hcx + hr * 1.02, ty + hr * 1.25)
    if look.hat in ("cap", "helmet", "beanie"):
        col = (242, 140, 40) if look.hat == "helmet" else look.hat_color
        d.chord((hat_box[0] - o, hat_box[1] - o, hat_box[2] + o, hat_box[3] + o), 180, 360, fill=INK)
        d.chord(hat_box, 180, 360, fill=col)
        base = ty + hr * 0.60
        if look.hat == "cap":
            x0, x1 = (hcx, hcx + 150 * u) if f > 0 else (hcx - 150 * u, hcx)
            d.rounded_rectangle((x0, base - 12 * u - o, x1, base + 12 * u), 12 * u, fill=INK)
            d.rounded_rectangle((x0 + o, base - 12 * u, x1 - o, base + 12 * u - o), 10 * u, fill=col)
        elif look.hat == "helmet":
            _blob(d, (hcx + 40 * u * f - 17 * u, ty + 8 * u, hcx + 40 * u * f + 17 * u, ty + 42 * u), (255, 242, 150), o * 0.6)
        else:
            _blob(d, (hcx - 20 * u, ty - 44 * u, hcx + 20 * u, ty - 4 * u), col, o * 0.8)
    elif look.hat == "bow":
        bx, by = hcx - 56 * u * f, ty + 18 * u
        for sgn in (-1, 1):
            d.polygon([(bx, by), (bx + sgn * 44 * u, by - 30 * u), (bx + sgn * 44 * u, by + 30 * u)], fill=INK)
            d.polygon([(bx + sgn * 6 * u, by), (bx + sgn * 38 * u, by - 20 * u), (bx + sgn * 38 * u, by + 20 * u)], fill=look.hat_color)
    elif look.hat == "crown":
        y0 = ty + 14 * u
        pts = [(hcx - 56 * u, y0), (hcx - 56 * u, y0 - 54 * u), (hcx - 28 * u, y0 - 26 * u), (hcx, y0 - 64 * u),
               (hcx + 28 * u, y0 - 26 * u), (hcx + 56 * u, y0 - 54 * u), (hcx + 56 * u, y0)]
        d.polygon(pts, fill=(250, 200, 40), outline=INK, width=int(o))

    # vorderer Arm
    hp = limb(sh_f, pose.arm_r * f + lean, arm1, pose.fore_r * f, arm2, hand=skin, col=look.shirt)
    pose.extra["hand"] = (hp[0] / SS, hp[1] / SS)          # Handpunkt im fertigen Bild (für Gegenstände in der Hand)

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
    p.arm_l = -12 - 3 * s(t * 1.6 + seed)
    p.arm_r = 12 + 3 * s(t * 1.6 + seed + 1)
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
        p.arm_r, p.fore_r = 150, 10 + 28 * s(t * 9)
        p.smile = 0.8
        p.head = 4 * s(t * 3)
    elif a == "point":
        p.arm_r, p.fore_r = 95, 0
        p.lean = 4
    elif a in ("shocked", "scared"):
        j = max(0.0, 1 - t / 0.35)
        p.lift = 60 * s(min(1, t / 0.35) * math.pi) if t < 0.35 else 0
        p.arm_l, p.fore_l, p.arm_r, p.fore_r = -150, 20, 150, -20
        p.eyes = "wide"
        p.lean = -6 + 3 * s(t * 30) * (0.3 + j)
        p.leg_l, p.leg_r = 10, -10
    elif a == "sad":
        p.head, p.lean = 18, 10
        p.arm_l, p.arm_r = -4, 4
        p.eyes, p.smile = "sad", -0.8
        p.squash = 0.96
    elif a in ("jump", "happy", "cheer"):
        ph = (t * 2.2) % 1.0
        p.lift = 70 * s(ph * math.pi)
        p.arm_l, p.fore_l, p.arm_r, p.fore_r = -155, 10, 155, -10
        p.leg_l, p.knee_l, p.leg_r, p.knee_r = 20 * (1 - s(ph * math.pi)), 40 * s(ph * math.pi), -10, 30 * s(ph * math.pi)
        p.eyes, p.smile = "happy", 1
    elif a == "think":
        p.arm_r, p.fore_r = 20, 150
        p.arm_l, p.fore_l = 30, 80
        p.head = -8
        p.look = 0.0
        p.eyes = "normal"
        p.extra["dots"] = int(t * 2.5) % 4
    elif a == "sit":
        p.leg_l, p.knee_l, p.leg_r, p.knee_r = 84, -84, 78, -78
        p.lift = -80                 # Hüfte auf Sitzhöhe, Füße stehen auf dem Boden (die Bühne stellt einen Hocker darunter)
        p.arm_r, p.fore_r = 40, 30
    elif a == "sleep":
        p.lying = True
        p.eyes = "closed"
        p.squash = 1 + 0.03 * s(t * 1.5)
        p.extra["zzz"] = True
    elif a == "talk":
        g = int((t + seed * 0.7) / 1.7) % 4                 # alle ~1,7 s eine andere Geste
        if g == 0:
            p.arm_r, p.fore_r = 46 + 16 * s(t * 3.1), 60 + 22 * s(t * 4.3)
        elif g == 1:
            p.arm_r, p.fore_r = 70 + 10 * s(t * 3.4), 30 + 18 * s(t * 5.0)
            p.arm_l, p.fore_l = -60 - 10 * s(t * 3.4), -30 - 18 * s(t * 5.0)
        elif g == 2:
            p.arm_l, p.fore_l = -50 - 16 * s(t * 3.0), -70 - 20 * s(t * 4.1)
        else:
            p.arm_r, p.fore_r = 110, 20 + 14 * s(t * 6)
        p.head = 4 * s(t * 2.7)
        p.lean = 2.5 * s(t * 1.9 + seed)
        p.lift = 5 * abs(s(t * 3.8)) + mouth * 4
        if emotion in ("", "happy"):
            p.smile = 0.6
    elif a == "look_around":
        p.look = s(t * 1.8)
        p.head = 6 * s(t * 1.8)
    elif a == "fall":
        p.lean = min(90, t * 260)
        p.eyes = "wide"
        p.arm_l, p.arm_r = -160, 160
    elif a == "dance":
        p.lift = 14 * abs(s(t * 6))
        p.arm_l, p.fore_l = -120 - 40 * s(t * 6), -40
        p.arm_r, p.fore_r = 120 - 40 * s(t * 6), 40
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
    p.mouth = max(mouth, 0.75) if a in ("shocked", "scared", "fall") or emo in ("shocked", "scared") else mouth
    return p, prog
