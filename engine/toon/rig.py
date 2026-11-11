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
         "weiß": (252, 228, 206), "gelb": (250, 214, 70), "grün": (120, 190, 90)}


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
    hair: str = ""           # long | bun | "" (kurz)
    size: float = 1.0
    hair_color: tuple = None

    @staticmethod
    def from_spec(spec: dict):
        spec = spec or {}
        return Look(shirt=color(spec.get("shirt"), COLORS["blau"]), pants=color(spec.get("pants"), (40, 40, 48)),
                    skin=SKINS.get(str(spec.get("skin") or "").lower(), SKINS["hell"]),
                    hat=str(spec.get("hat") or "").lower(), hat_color=color(spec.get("hat_color"), COLORS["rot"]),
                    glasses=bool(spec.get("glasses")), hair=str(spec.get("hair") or "").lower(),
                    hair_color=HAIRS.get(str(spec.get("hair_color") or "").lower().strip()),
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
HAIRS = {"braun": (104, 66, 44), "schwarz": (44, 40, 46), "blond": (232, 190, 96), "rot": (176, 84, 46), "grau": (150, 150, 156),
         "dunkelbraun": (72, 48, 36), "weiß": (236, 236, 232)}
_HAIR_AUTO = ("braun", "schwarz", "blond", "dunkelbraun", "rot")


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


def _mix(c, other, a):
    return tuple(int(c[i] * (1 - a) + other[i] * a) for i in range(3))


def _dark(c, a=0.22):
    return _mix(c, (20, 16, 40), a)


def _light(c, a=0.25):
    return _mix(c, (255, 255, 255), a)


def hair_color(look):
    """Haarfarbe: ausdrücklich gewählt – sonst fest aus dem Aussehen abgeleitet, damit jede Figur ihre Farbe behält."""
    if look.hair_color:
        return look.hair_color
    if look.skin == SKINS["dunkel"]:
        return HAIRS["schwarz"]
    return HAIRS[_HAIR_AUTO[(look.shirt[0] + look.shirt[1] * 3 + look.shirt[2] * 7 + look.skin[0]) % len(_HAIR_AUTO)]]


def _eye(d, cx, cy, r, kind, look, lid=0.0):
    white = (255, 255, 255)
    if kind in ("closed", "happy"):
        if kind == "happy":
            d.arc((cx - r * 1.05, cy - r * 0.6, cx + r * 1.05, cy + r * 1.3), 195, 345, fill=INK, width=max(2, int(r * 0.44)))
        else:
            d.arc((cx - r * 1.05, cy - r * 1.2, cx + r * 1.05, cy + r * 0.6), 15, 165, fill=INK, width=max(2, int(r * 0.4)))
        return
    rx, ry = (r * 1.2, r * 1.5) if kind == "wide" else (r * 1.08, r * 1.3)
    d.ellipse((cx - rx - r * 0.2, cy - ry - r * 0.2, cx + rx + r * 0.2, cy + ry + r * 0.2), fill=INK)
    d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=white)
    pr = r * (0.46 if kind == "wide" else 0.7)
    px = cx + look * (rx - pr) * 0.85
    py = cy + (ry - pr) * (0.45 if kind in ("sad", "worried") else 0.12)
    d.ellipse((px - pr, py - pr, px + pr, py + pr), fill=INK)
    hr = pr * 0.42
    d.ellipse((px + pr * 0.1, py - pr * 0.72, px + pr * 0.1 + hr * 2, py - pr * 0.72 + hr * 2), fill=white)
    d.ellipse((px - pr * 0.62, py + pr * 0.22, px - pr * 0.62 + hr, py + pr * 0.22 + hr), fill=white)
    if kind in ("angry", "tired") or lid > 0:                 # schweres Oberlid: wütend, müde
        cut = ry * (0.55 if kind == "angry" else max(lid, 0.7))
        d.chord((cx - rx - r * 0.2, cy - ry - r * 0.2, cx + rx + r * 0.2, cy + ry + r * 0.2), 180 + 12, 360 - 12, fill=INK) if cut > ry * 0.9 else \
            d.pieslice((cx - rx - r * 0.2, cy - ry - r * 0.25, cx + rx + r * 0.2, cy - ry + cut * 2), 180, 360, fill=INK)


def draw(look: Look, pose: Pose, facing=1, scale=1.0, ss=None):
    """Zeichnet die Figur und gibt (RGBA-Bild, Fußpunkt-x, Fußpunkt-y) im Maßstab 1 zurück.
    Stil: großer Kopf mit Frisur, Augenbrauen und ausdrucksstarkem Gesicht, Kapuzenpulli mit Schattenkante, Jeans und Turnschuhe –
    alles mit kräftigem Umriss und einer zweiten, dunkleren Farbfläche auf der lichtabgewandten Seite (Cel-Shading)."""
    SS = ss or globals()["SS"]
    k = SS * scale * look.size
    W, H = int(600 * k), int(740 * k)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f, o = facing, OUT * k
    foot_x, foot_y = W / 2, H - 36 * k
    leg1, leg2, arm1, arm2 = 80 * k, 78 * k, 66 * k, 60 * k
    lw, aw = 27 * k, 23 * k
    hip = (foot_x, foot_y - (leg1 + leg2) * pose.squash - pose.lift * k)
    lean = pose.lean * f
    bh, bw = 150 * k * pose.squash, 98 * k
    top = _pt(hip, 180 - lean, bh)                       # Hals
    shoulder = _pt(hip, 180 - lean, bh * 0.74)
    mask = look.skin == SKINS["schwarz"]                 # Strichmännchen-Kopf (weiß, ohne Frisur) – wie bisher für namenlose Figuren
    skin = look.skin if not mask else (250, 244, 232)
    skin_d = _dark(skin, 0.16)
    shirt, shirt_d, shirt_l = look.shirt, _dark(look.shirt, 0.26), _light(look.shirt, 0.16)
    pants = look.pants if look.pants != (40, 40, 48) else (62, 76, 118)
    pants_d = _dark(pants, 0.3)
    hair = hair_color(look)
    hair_d, hair_l = _dark(hair, 0.3), _light(hair, 0.22)
    sole = (244, 242, 236)

    def limb(p0, a1, l1, a2, l2, w, col, hand=None, shoe=None, cuff=None):
        p1 = _pt(p0, a1, l1)
        p2 = _pt(p1, a1 + a2, l2)
        _stroke(d, [p0, p1, p2], w + 2 * o, INK)
        _stroke(d, [p0, p1, p2], w, col)
        if cuff:                                          # Bündchen am Handgelenk / Hosensaum
            c0 = _pt(p1, a1 + a2, l2 * 0.74)
            _stroke(d, [c0, p2], w, cuff)
        if hand:
            r = 15 * k
            _blob(d, (p2[0] - r, p2[1] - r, p2[0] + r, p2[1] + r), hand, o * 0.75)
            t0 = _pt(p2, a1 + a2 + 70 * f, r * 0.95)      # Daumen
            _blob(d, (t0[0] - r * 0.42, t0[1] - r * 0.42, t0[0] + r * 0.42, t0[1] + r * 0.42), hand, o * 0.6)
            d.ellipse((p2[0] - r * 0.8, p2[1] - r * 0.8, p2[0] + r * 0.8, p2[1] + r * 0.8), fill=hand)
        if shoe:                                          # Turnschuh: farbiger Schaft, helle Sohle, Spitze in Blickrichtung
            x0, x1 = p2[0] - 20 * k + 13 * k * f, p2[0] + 26 * k + 13 * k * f
            d.rounded_rectangle((x0 - o, p2[1] - 16 * k - o, x1 + o, p2[1] + 15 * k + o), 14 * k, fill=INK)
            d.rounded_rectangle((x0, p2[1] - 16 * k, x1, p2[1] + 15 * k), 12 * k, fill=shoe)
            d.rounded_rectangle((x0, p2[1] + 5 * k, x1, p2[1] + 15 * k), 6 * k, fill=sole)
            tx = x1 - 15 * k if f > 0 else x0
            d.rounded_rectangle((tx, p2[1] - 8 * k, tx + 15 * k, p2[1] + 6 * k), 6 * k, fill=sole)
        return p2

    shoe_col = _mix(shirt, (250, 250, 250), 0.12) if not mask else (60, 60, 70)
    # hinterer Arm, Beine
    sh_b = (shoulder[0] - 36 * k * f, shoulder[1] + 6 * k)      # hintere / vordere Schulter (leicht frontal gezeichnet)
    sh_f = (shoulder[0] + 36 * k * f, shoulder[1] + 6 * k)
    limb(sh_b, pose.arm_l * f + lean, arm1, pose.fore_l * f, arm2, aw, shirt_d, hand=skin_d, cuff=_dark(shirt_d, 0.2))
    hl = (hip[0] - 20 * k * f, hip[1] - 8 * k)
    hr_ = (hip[0] + 20 * k * f, hip[1] - 8 * k)
    limb(hl, pose.leg_l * f, leg1, -pose.knee_l * f, leg2, lw, pants_d, shoe=_dark(shoe_col, 0.25))
    limb(hr_, pose.leg_r * f, leg1, -pose.knee_r * f, leg2, lw, pants, shoe=shoe_col)

    # Rumpf: Kapuzenpulli mit Schattenkante auf der Rückseite, Saum, Tasche und Kordeln
    b0 = _pt(hip, 180 - lean, bw * 0.40)
    b1 = _pt(hip, 180 - lean, bh - bw * 0.42)
    _stroke(d, [b0, b1], bw + 2 * o, INK)
    _stroke(d, [b0, b1], bw, shirt_d)
    _stroke(d, [(b0[0] + 9 * k * f, b0[1] - 2 * k), (b1[0] + 9 * k * f, b1[1] + 2 * k)], bw - 18 * k, shirt)
    hood = _pt(hip, 180 - lean, bh - 6 * k)                                   # Kapuze im Nacken
    d.ellipse((hood[0] - 52 * k - o, hood[1] - 24 * k - o, hood[0] + 52 * k + o, hood[1] + 30 * k + o), fill=INK)
    d.ellipse((hood[0] - 52 * k, hood[1] - 24 * k, hood[0] + 52 * k, hood[1] + 30 * k), fill=shirt_d)
    d.ellipse((hood[0] - 40 * k + 6 * k * f, hood[1] - 16 * k, hood[0] + 40 * k + 6 * k * f, hood[1] + 20 * k), fill=shirt)
    pk = _pt(hip, 180 - lean, bw * 0.50)                                      # Bauchtasche
    d.rounded_rectangle((pk[0] - 30 * k + 6 * k * f, pk[1] - 13 * k, pk[0] + 30 * k + 6 * k * f, pk[1] + 16 * k), 9 * k, fill=shirt_d)
    for sgn in (-1, 1):                                                       # Kordeln
        c0 = _pt(hip, 180 - lean, bh - 34 * k)
        c1 = _pt(hip, 180 - lean, bh - 70 * k)
        ox = (sgn * 11 + 6 * f) * k
        d.line((c0[0] + ox, c0[1], c1[0] + ox + sgn * 2 * k, c1[1]), fill=shirt_l, width=max(2, int(5 * k)))
        d.ellipse((c1[0] + ox + sgn * 2 * k - 5 * k, c1[1] - 2 * k, c1[0] + ox + sgn * 2 * k + 5 * k, c1[1] + 8 * k), fill=shirt_l)

    # Hals
    nk0, nk1 = _pt(top, 180 - lean, -16 * k), _pt(top, 180 - lean, 14 * k)
    _stroke(d, [nk0, nk1], 30 * k + 2 * o, INK)
    _stroke(d, [nk0, nk1], 30 * k, skin_d)

    # Kopf
    hr = 80 * k
    ha = pose.head * f + lean
    hc = _pt(top, 180 - ha, hr * 0.86)
    rx, ry = hr * 1.04, hr * 0.96
    hairy = not mask and look.hat not in ("helmet",)
    if hairy and look.hair == "long":                    # langes Haar fällt hinter dem Kopf bis auf die Schultern
        d.rounded_rectangle((hc[0] - rx * 1.07 - o, hc[1] - ry * 0.6 - o, hc[0] + rx * 1.07 + o, hc[1] + ry * 1.42 + o), hr * 0.55, fill=INK)
        d.rounded_rectangle((hc[0] - rx * 1.07, hc[1] - ry * 0.6, hc[0] + rx * 1.07, hc[1] + ry * 1.42), hr * 0.5, fill=hair_d)
        d.rounded_rectangle((hc[0] - rx * 1.07 + (16 * k if f > 0 else 0), hc[1] - ry * 0.6, hc[0] + rx * 1.07 - (16 * k if f < 0 else 0), hc[1] + ry * 1.42),
                            hr * 0.5, fill=hair)
    if hairy and look.hair == "bun":
        _blob(d, (hc[0] - hr * 0.44 - 10 * k * f, hc[1] - ry * 1.62, hc[0] + hr * 0.44 - 10 * k * f, hc[1] - ry * 0.82), hair, o)
        d.arc((hc[0] - hr * 0.3 - 10 * k * f, hc[1] - ry * 1.5, hc[0] + hr * 0.3 - 10 * k * f, hc[1] - ry * 0.95), 200, 300, fill=hair_l, width=max(2, int(6 * k)))
    if not mask:                                          # Ohr auf der abgewandten Seite
        e0 = (hc[0] - rx * 0.93 * f, hc[1] + ry * 0.12)
        _blob(d, (e0[0] - 15 * k, e0[1] - 20 * k, e0[0] + 15 * k, e0[1] + 20 * k), skin_d, o * 0.8)
    d.ellipse((hc[0] - rx - o, hc[1] - ry - o, hc[0] + rx + o, hc[1] + ry + o), fill=INK)
    d.ellipse((hc[0] - rx, hc[1] - ry, hc[0] + rx, hc[1] + ry), fill=skin_d)
    d.ellipse((hc[0] - rx + (12 * k if f > 0 else 0), hc[1] - ry, hc[0] + rx - (12 * k if f < 0 else 0), hc[1] + ry - 5 * k), fill=skin)
    if hairy:                                             # Deckhaar mit Pony und Glanz
        hb = (hc[0] - rx - 4 * k, hc[1] - ry - 10 * k, hc[0] + rx + 4 * k, hc[1] + 10 * k)
        d.chord((hb[0] - o * 0.7, hb[1] - o * 0.7, hb[2] + o * 0.7, hb[3] + o * 0.7), 180, 360, fill=INK)
        top_y = (hb[1] + hb[3]) / 2 - 2 * k
        pts = [(hc[0] - rx - 4 * k, top_y), (hc[0] - rx * 0.99, hc[1] - ry * 0.12), (hc[0] - rx * 0.74, hc[1] - ry * 0.40),
               (hc[0] - rx * 0.30 * f, hc[1] - ry * 0.27), (hc[0] + rx * 0.22 * f, hc[1] - ry * 0.44), (hc[0] + rx * 0.72, hc[1] - ry * 0.31),
               (hc[0] + rx * 0.99, hc[1] - ry * 0.12), (hc[0] + rx + 4 * k, top_y)]
        d.polygon(pts, fill=INK)                           # Pony: schräg gekämmte Strähnen mit Umriss
        d.polygon([(x, y - (o * 0.9 if 0 < i < len(pts) - 1 else 0)) for i, (x, y) in enumerate(pts)], fill=hair)
        d.chord(hb, 180, 360, fill=hair)
        d.arc((hc[0] - rx * 0.6 + 18 * k * f, hc[1] - ry * 0.96, hc[0] + rx * 0.6 + 18 * k * f, hc[1] - ry * 0.2), 208, 300, fill=hair_l, width=max(2, int(9 * k)))
    u = k * 0.84
    # Gesicht (leicht in Blickrichtung versetzt)
    ex, ey, er = hc[0] + 16 * u * f, hc[1] + 16 * u, 19 * u
    lk = pose.look if pose.look else 0.45 * f
    if not mask:                                          # Wangenrot
        for sgn in (-1, 1):
            cxk = ex + sgn * 58 * u
            d.ellipse((cxk - 17 * u, ey + 24 * u, cxk + 17 * u, ey + 44 * u), fill=_mix(skin, CHEEK, 0.55))
    for sgn in (-1, 1):
        _eye(d, ex + sgn * 37 * u, ey, er, pose.eyes, lk)
    # Augenbrauen: tragen den Ausdruck (hoch = erstaunt, innen tief = wütend, innen hoch = traurig/besorgt)
    brow = _mix(hair_d, INK, 0.55) if not mask else INK
    lift_b = {"wide": 20, "happy": 12, "closed": 4, "angry": -4, "sad": 4, "worried": 6}.get(pose.eyes, 8) * u
    tilt = {"angry": -11, "sad": 10, "worried": 9, "wide": -2}.get(pose.eyes, -3) * u
    for sgn in (-1, 1):
        x0, y0 = ex + sgn * 37 * u, ey - 36 * u - lift_b * 0.8
        dy = tilt * sgn
        _stroke(d, [(x0 - 19 * u, y0 - dy), (x0 + 19 * u, y0 + dy)], 9 * u, brow)
    if not mask:                                          # Nase: kleiner Haken in Blickrichtung
        d.arc((ex + 2 * u * f - 9 * u, ey + 12 * u, ex + 2 * u * f + 9 * u, ey + 30 * u), 300 if f > 0 else 150, 90 if f > 0 else 240, fill=_dark(skin, 0.35), width=max(2, int(5 * u)))
    mx, my = ex, ey + 50 * u
    if pose.mouth > 0.08:                                 # offener Mund mit Zähnen und Zunge
        mh = 10 * u + pose.mouth * 30 * u
        mw = (19 - 4 * pose.mouth) * u if pose.eyes == "wide" else 19 * u
        d.rounded_rectangle((mx - mw - 3 * u, my - mh / 2 - 3 * u, mx + mw + 3 * u, my + mh / 2 + 3 * u), min(mw, mh / 2 + 3 * u), fill=INK)
        d.rounded_rectangle((mx - mw, my - mh / 2, mx + mw, my + mh / 2), min(mw, mh / 2), fill=(96, 30, 44))
        if mh > 16 * u:
            d.rounded_rectangle((mx - mw * 0.72, my - mh / 2, mx + mw * 0.72, my - mh / 2 + 7 * u), 3 * u, fill=(255, 255, 255))
            d.ellipse((mx - mw * 0.6, my + mh * 0.08, mx + mw * 0.6, my + mh * 0.62), fill=(238, 112, 118))
    elif pose.smile < -0.2:
        d.arc((mx - 18 * u, my - 2 * u, mx + 18 * u, my + 24 * u), 200, 340, fill=INK, width=max(2, int(7 * u)))
    else:
        wdt = (20 + 10 * max(0, pose.smile)) * u
        d.arc((mx - wdt, my - 26 * u, mx + wdt, my + 8 * u), 22, 158, fill=INK, width=max(2, int(7 * u)))
        if pose.smile > 0.5:                              # Grübchen
            for sgn in (-1, 1):
                d.arc((mx + sgn * wdt - 6 * u, my - 12 * u, mx + sgn * wdt + 6 * u, my + 2 * u), 250 if sgn > 0 else 200, 340 if sgn > 0 else 290, fill=INK, width=max(2, int(5 * u)))
    if look.glasses:
        for sgn in (-1, 1):
            d.ellipse((ex + sgn * 37 * u - 31 * u, ey - 32 * u, ex + sgn * 37 * u + 31 * u, ey + 32 * u), outline=INK, width=max(2, int(6 * u)))
        d.line((ex - 7 * u, ey - 4 * u, ex + 7 * u, ey - 4 * u), fill=INK, width=max(2, int(6 * u)))
    # Kopfbedeckung
    hcx, ty = hc[0], hc[1] - ry
    hat_box = (hcx - rx * 1.04, ty - 12 * u, hcx + rx * 1.04, ty + hr * 1.2)
    if look.hat in ("cap", "helmet", "beanie"):
        col = (242, 140, 40) if look.hat == "helmet" else look.hat_color
        d.chord((hat_box[0] - o, hat_box[1] - o, hat_box[2] + o, hat_box[3] + o), 180, 360, fill=INK)
        d.chord(hat_box, 180, 360, fill=_dark(col, 0.22))
        d.chord((hat_box[0] + (12 * k if f > 0 else 0), hat_box[1], hat_box[2] - (12 * k if f < 0 else 0), hat_box[3]), 180, 360, fill=col)
        base = ty + hr * 0.56
        if look.hat == "cap":
            x0, x1 = (hcx, hcx + 150 * u) if f > 0 else (hcx - 150 * u, hcx)
            d.rounded_rectangle((x0, base - 12 * u - o, x1, base + 12 * u), 12 * u, fill=INK)
            d.rounded_rectangle((x0 + o, base - 12 * u, x1 - o, base + 12 * u - o), 10 * u, fill=_dark(col, 0.12))
        elif look.hat == "helmet":
            d.rounded_rectangle((hcx - rx * 1.1 - o, base - 4 * u - o, hcx + rx * 1.1 + o, base + 14 * u + o), 9 * u, fill=INK)
            d.rounded_rectangle((hcx - rx * 1.1, base - 4 * u, hcx + rx * 1.1, base + 14 * u), 8 * u, fill=col)
            _blob(d, (hcx + 40 * u * f - 17 * u, ty + 6 * u, hcx + 40 * u * f + 17 * u, ty + 40 * u), (255, 242, 150), o * 0.6)
        else:
            d.rounded_rectangle((hcx - rx * 1.04 - o, base - 8 * u - o, hcx + rx * 1.04 + o, base + 16 * u + o), 10 * u, fill=INK)
            d.rounded_rectangle((hcx - rx * 1.04, base - 8 * u, hcx + rx * 1.04, base + 16 * u), 9 * u, fill=_light(col, 0.2))
            _blob(d, (hcx - 22 * u, ty - 50 * u, hcx + 22 * u, ty - 6 * u), _light(col, 0.2), o * 0.8)
    elif look.hat == "bow":
        bx, by = hcx - 56 * u * f, ty + 22 * u
        for sgn in (-1, 1):
            d.polygon([(bx, by), (bx + sgn * 46 * u, by - 32 * u), (bx + sgn * 46 * u, by + 32 * u)], fill=INK)
            d.polygon([(bx + sgn * 6 * u, by), (bx + sgn * 40 * u, by - 22 * u), (bx + sgn * 40 * u, by + 22 * u)], fill=look.hat_color)
        _blob(d, (bx - 9 * u, by - 9 * u, bx + 9 * u, by + 9 * u), _dark(look.hat_color, 0.2), o * 0.5)
    elif look.hat == "crown":
        y0 = ty + 16 * u
        pts = [(hcx - 58 * u, y0), (hcx - 58 * u, y0 - 56 * u), (hcx - 28 * u, y0 - 26 * u), (hcx, y0 - 68 * u),
               (hcx + 28 * u, y0 - 26 * u), (hcx + 58 * u, y0 - 56 * u), (hcx + 58 * u, y0)]
        d.polygon(pts, fill=(250, 200, 40), outline=INK, width=int(o))
        for gx, gc in ((-30, (226, 70, 70)), (0, (70, 150, 230)), (30, (226, 70, 70))):
            d.ellipse((hcx + gx * u - 7 * u, y0 - 18 * u, hcx + gx * u + 7 * u, y0 - 4 * u), fill=gc)

    # vorderer Arm
    hp = limb(sh_f, pose.arm_r * f + lean, arm1, pose.fore_r * f, arm2, aw, shirt, hand=skin, cuff=shirt_d)
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
    elif a in ("shake", "schütteln"):                      # hält etwas am ausgestreckten Arm und schüttelt es kräftig aus
        p.arm_r, p.fore_r = 78 + 10 * s(t * 16), 18 + 16 * s(t * 16 + 1)
        p.lean = 6
        p.head = 5
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
        p.leg_l, p.knee_l, p.leg_r, p.knee_r = 84, 84, 76, 76      # Oberschenkel nach vorn, Unterschenkel senkrecht nach unten (Knie positiv = nach hinten beugen)
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
    elif a in ("float", "schweben"):                       # schwerelos: treibt mit ausgebreiteten Armen, Beine angewinkelt, kippt langsam hin und her
        p.arm_l, p.fore_l = -118 + 14 * s(t * 1.7 + seed), -26 + 10 * s(t * 2.3)
        p.arm_r, p.fore_r = 118 + 14 * s(t * 1.9 + seed + 1), 26 + 10 * s(t * 2.1)
        p.leg_l, p.knee_l = 26 + 10 * s(t * 1.5 + seed), 34 + 12 * s(t * 1.8)
        p.leg_r, p.knee_r = -22 + 10 * s(t * 1.3 + seed + 2), 24 + 12 * s(t * 1.6 + 1)
        p.lean = 16 * s(t * 1.1 + seed)
        p.head = 6 * s(t * 1.4)
        p.eyes = "wide"
    elif a == "fall":                                       # kippt um und bleibt ausgestreckt am Boden liegen
        p.lean = min(70, t * 260)
        p.eyes = "wide"
        p.arm_l, p.arm_r = -160, 160
        if t * 260 >= 70:
            p.lying, p.lean = True, 0
            p.arm_l, p.fore_l, p.arm_r, p.fore_r = -150, -20, 150, 20
            p.leg_l, p.leg_r = 12, -12
            p.eyes = "closed" if t > 1.6 else "wide"
            p.extra["stars"] = True
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
    p.mouth = max(mouth, 0.75) if a in ("shocked", "scared", "fall", "float", "schweben") or emo in ("shocked", "scared") else mouth
    return p, prog
