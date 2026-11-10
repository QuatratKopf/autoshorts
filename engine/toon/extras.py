"""Leben in der Szene: Requisiten (Auto, Feuer, Rakete, Meteor …), Gefühls-Symbole über dem Kopf, Wetter,
Tiere/Wesen und kleine Hintergrund-Bewegungen (Wolken, funkelnde Sterne). Alles wird pro Bild gezeichnet (t = Sekunden)."""
import math
import random

from PIL import Image, ImageDraw

from .places import GROUND, W, H

INK = (22, 22, 26)
O = 7


def _o(d, box, col, w=O):
    d.ellipse(box, fill=col, outline=INK, width=w)


def _r(d, box, col, r=10, w=O):
    d.rounded_rectangle(box, r, fill=col, outline=INK, width=w)


def _pop(t, at=0.0, d=0.28):
    """Einblend-Faktor 0..1 mit kleinem Überschwingen."""
    x = (t - at) / d
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    return 1 + 0.25 * math.sin(x * math.pi) - (1 - x) ** 2


# ------------------------------------------------------------------ Requisiten
# Jede Funktion zeichnet auf d (RGBA-Ebene) an Position x (Mitte); Boden = GROUND.

def p_tree(d, x, t, s=1.0):
    sway = math.sin(t * 1.3 + x) * 6
    _r(d, (x - 24 * s, GROUND - 300 * s, x + 24 * s, GROUND), (130, 86, 54), 6)
    for dx, dy, r in ((0, -380, 130), (-90, -310, 96), (90, -310, 96), (0, -270, 104)):
        _o(d, (x + dx * s + sway - r * s, GROUND + dy * s - r * s, x + dx * s + sway + r * s, GROUND + dy * s + r * s), (70, 160, 84))


def p_rock(d, x, t, s=1.0):
    d.chord((x - 120 * s, GROUND - 110 * s, x + 120 * s, GROUND + 110 * s), 180, 360, fill=(150, 150, 158), outline=INK, width=O)
    d.line((x - 120 * s, GROUND, x + 120 * s, GROUND), fill=INK, width=O)


def p_box(d, x, t, s=1.0):
    _r(d, (x - 100, GROUND - 170, x + 100, GROUND), (214, 170, 110), 8)
    d.line((x - 100, GROUND - 120, x + 100, GROUND - 120), fill=INK, width=5)
    _r(d, (x - 24, GROUND - 170, x + 24, GROUND - 100), (236, 204, 150), 4, 5)


def p_car(d, x, t, s=1.0):
    b = math.sin(t * 9) * 3
    _r(d, (x - 210, GROUND - 150 + b, x + 210, GROUND - 40 + b), (226, 70, 60), 30)
    d.rounded_rectangle((x - 120, GROUND - 240 + b, x + 110, GROUND - 140 + b), 34, fill=(226, 70, 60), outline=INK, width=O)
    _r(d, (x - 96, GROUND - 220 + b, x - 6, GROUND - 150 + b), (170, 220, 250), 14, 5)
    _r(d, (x + 8, GROUND - 220 + b, x + 90, GROUND - 150 + b), (170, 220, 250), 14, 5)
    for wx in (-120, 120):
        _o(d, (x + wx - 48, GROUND - 90, x + wx + 48, GROUND + 6), (40, 40, 46))
        _o(d, (x + wx - 18, GROUND - 60, x + wx + 18, GROUND - 24), (190, 190, 196), 4)
    _o(d, (x + 180, GROUND - 120 + b, x + 214, GROUND - 90 + b), (255, 236, 150), 4)


def p_fire(d, x, t, s=1.0):
    for dx in (-60, 40):
        d.line((x + dx - 50, GROUND - 16, x + dx + 60, GROUND - 40), fill=(110, 70, 44), width=26)
    for i, (col, sc) in enumerate((((240, 90, 40), 1.0), ((250, 170, 50), 0.68), ((255, 236, 140), 0.38))):
        fl = 1 + 0.12 * math.sin(t * 11 + i * 2)
        hgt, wd = 230 * sc * fl * s, 110 * sc * s
        tip = x + math.sin(t * 7 + i) * 18 * sc
        d.polygon([(x - wd, GROUND - 40), (x - wd * 0.7, GROUND - 40 - hgt * 0.5), (tip, GROUND - 40 - hgt),
                   (x + wd * 0.7, GROUND - 40 - hgt * 0.5), (x + wd, GROUND - 40), (x, GROUND - 20)],
                  fill=col, outline=INK if i == 0 else None, width=O)


def p_tv(d, x, t, s=1.0):
    _r(d, (x - 30, GROUND - 120, x + 30, GROUND), (60, 60, 66), 4, 5)
    _r(d, (x - 200, GROUND - 400, x + 200, GROUND - 120), (40, 44, 54), 16)
    flick = 200 + int(40 * math.sin(t * 13))
    d.rounded_rectangle((x - 176, GROUND - 376, x + 176, GROUND - 144), 8, fill=(110, flick, 250))
    d.rectangle((x - 176, GROUND - 200, x + 176, GROUND - 160), fill=(226, 58, 52))


def p_computer(d, x, t, s=1.0):
    _r(d, (x - 220, GROUND - 230, x + 220, GROUND - 200), (176, 118, 76), 6)
    for lx in (-190, 170):
        _r(d, (x + lx, GROUND - 200, x + lx + 22, GROUND), (110, 110, 118), 4, 5)
    _r(d, (x - 130, GROUND - 420, x + 130, GROUND - 250), (40, 44, 54), 12)
    d.rounded_rectangle((x - 112, GROUND - 402, x + 112, GROUND - 268), 6, fill=(120, 200, 255))
    for i in range(3):
        wdt = 60 + (int(t * 6 + i * 2) % 5) * 26
        d.rectangle((x - 96, GROUND - 386 + i * 34, x - 96 + wdt, GROUND - 372 + i * 34), fill=(250, 250, 255))
    _r(d, (x - 16, GROUND - 250, x + 16, GROUND - 230), (60, 60, 66), 2, 4)


def p_money(d, x, t, s=1.0):
    for i in range(5):
        y = GROUND - 34 - i * 30
        _r(d, (x - 110 + (i % 2) * 12, y, x + 110 + (i % 2) * 12, y + 34), (110, 190, 110), 6, 5)
        _o(d, (x - 16 + (i % 2) * 12, y + 5, x + 16 + (i % 2) * 12, y + 29), (220, 240, 200), 3)


def p_rocket(d, x, t, s=1.0):
    lift = max(0.0, t - 0.8) ** 2 * 520
    y = GROUND - lift
    for i, col in enumerate(((240, 90, 40), (255, 200, 70))):
        fl = (140 - i * 50) * (1 + 0.2 * math.sin(t * 20 + i)) * (1.6 if lift > 0 else 0.5)
        d.polygon([(x - 44 + i * 16, y - 20), (x, y - 20 + fl), (x + 44 - i * 16, y - 20)], fill=col)
    d.polygon([(x - 70, y - 20), (x - 120, y + 20), (x - 70, y - 140)], fill=(226, 70, 60), outline=INK, width=O)
    d.polygon([(x + 70, y - 20), (x + 120, y + 20), (x + 70, y - 140)], fill=(226, 70, 60), outline=INK, width=O)
    _r(d, (x - 70, y - 380, x + 70, y - 20), (244, 244, 248), 60)
    d.chord((x - 70, y - 470, x + 70, y - 290), 180, 360, fill=(226, 70, 60), outline=INK, width=O)
    _o(d, (x - 34, y - 300, x + 34, y - 232), (130, 200, 250))


def p_ufo(d, x, t, s=1.0):
    y = 560 + math.sin(t * 2.2) * 26
    xx = x + math.sin(t * 1.1) * 40
    beam = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(beam).polygon([(xx - 60, y + 40), (xx + 60, y + 40), (xx + 200, GROUND), (xx - 200, GROUND)],
                                 fill=(190, 255, 190, 70 + int(30 * math.sin(t * 6))))
    d._image.alpha_composite(beam)
    d.chord((xx - 100, y - 130, xx + 100, y + 50), 180, 360, fill=(170, 230, 250), outline=INK, width=O)
    _o(d, (xx - 230, y - 50, xx + 230, y + 50), (170, 176, 190))
    for i in range(5):
        on = int(t * 5 + i) % 2
        _o(d, (xx - 180 + i * 80, y - 14, xx - 152 + i * 80, y + 14), (255, 236, 120) if on else (240, 110, 90), 4)


def p_meteor(d, x, t, s=1.0):
    k = min(1.0, t / 1.6)
    mx, my = x + 500 - 500 * k, 120 + (GROUND - 320) * k
    for i in range(6):
        a = 200 - i * 34
        d.ellipse((mx + i * 40 - (60 - i * 8), my - i * 46 - (60 - i * 8), mx + i * 40 + (60 - i * 8), my - i * 46 + (60 - i * 8)),
                  fill=(255, 170 - i * 14, 60, max(0, a)))
    _o(d, (mx - 80, my - 80, mx + 80, my + 80), (120, 100, 96))
    _o(d, (mx - 40, my - 30, mx - 6, my + 4), (90, 76, 74), 4)
    _o(d, (mx + 10, my + 14, mx + 44, my + 46), (90, 76, 74), 4)
    if k >= 1.0:
        p_explosion(d, x, t - 1.6)


def p_explosion(d, x, t, s=1.0):
    k = min(1.0, max(0.0, t) / 0.5)
    if t < 0:
        return
    r = 60 + 300 * k
    for i, col in enumerate(((240, 90, 40), (250, 170, 50), (255, 240, 170))):
        rr = r * (1 - i * 0.28)
        pts = []
        for j in range(20):
            a = j / 20 * math.tau
            m = rr * (1.0 if j % 2 else 0.7) * (1 + 0.06 * math.sin(t * 20 + j))
            pts.append((x + math.cos(a) * m, GROUND - 220 + math.sin(a) * m))
        d.polygon(pts, fill=col, outline=INK if i == 0 else None, width=O)


def p_earth(d, x, t, s=1.0):
    cy, r = 520, 190
    _o(d, (x - r, cy - r, x + r, cy + r), (70, 150, 230))
    sh = (t * 30) % (r * 2)
    for dx, dy, rw, rh in ((-90, -60, 80, 60), (30, 40, 90, 70), (60, -100, 50, 36), (-40, 90, 60, 40)):
        cx = x + ((dx + sh + r) % (2 * r)) - r
        if abs(cx - x) < r - rw * 0.6:
            d.ellipse((cx - rw, cy + dy - rh, cx + rw, cy + dy + rh), fill=(90, 190, 110))
    d.ellipse((x - r, cy - r, x + r, cy + r), outline=INK, width=O)


def p_bigsun(d, x, t, s=1.0):
    cy, r = 520, 170 * (1 + 0.03 * math.sin(t * 3))
    for i in range(12):
        a = i / 12 * math.tau + t * 0.4
        d.line((x + math.cos(a) * (r + 30), cy + math.sin(a) * (r + 30), x + math.cos(a) * (r + 90), cy + math.sin(a) * (r + 90)),
               fill=(255, 190, 60), width=22)
    _o(d, (x - r, cy - r, x + r, cy + r), (255, 214, 70))


def p_bigmoon(d, x, t, s=1.0):
    cy, r = 520, 180
    _o(d, (x - r, cy - r, x + r, cy + r), (236, 232, 214))
    for dx, dy, rr in ((-70, -50, 40), (50, 30, 54), (-20, 90, 30), (80, -90, 26)):
        d.ellipse((x + dx - rr, cy + dy - rr, x + dx + rr, cy + dy + rr), fill=(206, 200, 180))


def p_tornado(d, x, t, s=1.0):
    for i in range(9):
        wdt = 40 + i * 34
        y = GROUND - 30 - i * 90
        ox = math.sin(t * 5 + i * 0.7) * (20 + i * 6)
        d.ellipse((x + ox - wdt, y - 40, x + ox + wdt, y + 40), fill=(150, 156, 170, 230), outline=INK, width=5)


def p_wave(d, x, t, s=1.0):
    k = min(1.0, t / 4.0)
    top = GROUND - 120 - 330 * k
    pts = [(0, H)]
    for i in range(0, W + 60, 60):
        pts.append((i, top + math.sin(i * 0.012 + t * 3) * 50 - (W - i) * 0.25 * k))
    pts.append((W, H))
    d.polygon(pts, fill=(50, 140, 220, 235), outline=INK, width=O)
    for i in range(0, W, 120):
        d.arc((i, top + 40 + math.sin(i + t * 3) * 20, i + 100, top + 100 + math.sin(i + t * 3) * 20), 180, 360, fill=(220, 240, 255), width=8)


def p_ice(d, x, t, s=1.0):
    d.polygon([(x - 200, GROUND), (x - 120, GROUND - 260), (x - 20, GROUND - 180), (x + 60, GROUND - 380), (x + 200, GROUND)],
              fill=(200, 232, 250), outline=INK, width=O)
    d.line((x - 20, GROUND - 180, x + 10, GROUND - 40), fill=(150, 200, 235), width=6)


def p_volcano(d, x, t, s=1.0):
    d.polygon([(x - 300, GROUND), (x - 80, GROUND - 480), (x + 80, GROUND - 480), (x + 300, GROUND)], fill=(110, 84, 80), outline=INK, width=O)
    d.polygon([(x - 80, GROUND - 480), (x + 80, GROUND - 480), (x + 40, GROUND - 380), (x - 10, GROUND - 300), (x - 50, GROUND - 400)], fill=(244, 110, 40))
    for i in range(7):
        ph = (t * 0.9 + i / 7) % 1
        a = -math.pi / 2 + (i - 3) * 0.28
        px, py = x + math.cos(a) * 420 * ph, GROUND - 480 + math.sin(a) * 420 * ph + 380 * ph * ph
        d.ellipse((px - 18, py - 18, px + 18, py + 18), fill=(250, 160, 50), outline=INK, width=4)


PROPS = {"tree": p_tree, "rock": p_rock, "box": p_box, "car": p_car, "fire": p_fire, "tv": p_tv, "computer": p_computer,
         "money": p_money, "rocket": p_rocket, "ufo": p_ufo, "meteor": p_meteor, "explosion": p_explosion, "earth": p_earth,
         "sun": p_bigsun, "moon": p_bigmoon, "tornado": p_tornado, "wave": p_wave, "ice": p_ice, "volcano": p_volcano}
PROP_ALIASES = {"baum": "tree", "stein": "rock", "kiste": "box", "auto": "car", "feuer": "fire", "fernseher": "tv", "pc": "computer",
                "laptop": "computer", "geld": "money", "rakete": "rocket", "asteroid": "meteor", "erde": "earth", "sonne": "sun",
                "mond": "moon", "tsunami": "wave", "welle": "wave", "eisberg": "ice", "vulkan": "volcano", "bigsun": "sun"}
FRONT = ("wave",)     # werden vor den Figuren gezeichnet


def draw_prop(layer, kind, x, t):
    kind = PROP_ALIASES.get(str(kind).lower(), str(kind).lower())
    fn = PROPS.get(kind)
    if fn:
        d = ImageDraw.Draw(layer)
        fn(d, x, t)


# ------------------------------------------------------------------ Gefühls-Symbole über dem Kopf

def draw_emote(layer, kind, x, y, t):
    k = _pop(t, 0.15)
    if k <= 0:
        return
    d = ImageDraw.Draw(layer)
    kind = str(kind).lower().strip()
    bob = math.sin(t * 5) * 6
    s = k
    cx, cy = x + 120, y - 30 + bob
    if kind in ("!", "alarm", "exclaim"):
        _r(d, (cx - 16 * s, cy - 110 * s, cx + 16 * s, cy - 24 * s), (240, 70, 60), 10)
        _o(d, (cx - 18 * s, cy - 12 * s, cx + 18 * s, cy + 24 * s), (240, 70, 60))
    elif kind in ("?", "question"):
        d.arc((cx - 40 * s, cy - 110 * s, cx + 40 * s, cy - 30 * s), 180, 90, fill=INK, width=int(30 * s))
        d.arc((cx - 40 * s, cy - 110 * s, cx + 40 * s, cy - 30 * s), 180, 90, fill=(80, 150, 250), width=int(18 * s))
        _o(d, (cx - 16 * s, cy - 6 * s, cx + 16 * s, cy + 26 * s), (80, 150, 250))
    elif kind in ("heart", "love", "herz"):
        r = 34 * s * (1 + 0.1 * math.sin(t * 8))
        for dx in (-r * 0.5, r * 0.5):
            d.ellipse((cx + dx - r * 0.62, cy - 80 - r * 0.62, cx + dx + r * 0.62, cy - 80 + r * 0.62), fill=(240, 70, 100))
        d.polygon([(cx - r * 1.06, cy - 70), (cx + r * 1.06, cy - 70), (cx, cy - 80 + r * 1.3)], fill=(240, 70, 100))
    elif kind in ("idea", "idee", "bulb"):
        _o(d, (cx - 40 * s, cy - 130 * s, cx + 40 * s, cy - 50 * s), (255, 226, 90))
        _r(d, (cx - 20 * s, cy - 54 * s, cx + 20 * s, cy - 26 * s), (150, 156, 166), 4, 5)
        for a in (-150, -90, -30):
            d.line((cx + math.cos(math.radians(a)) * 56 * s, cy - 90 * s + math.sin(math.radians(a)) * 56 * s,
                    cx + math.cos(math.radians(a)) * 84 * s, cy - 90 * s + math.sin(math.radians(a)) * 84 * s), fill=(255, 226, 90), width=8)
    elif kind in ("sweat", "schweiß"):
        ph = (t * 1.2) % 1
        d.polygon([(cx - 40, cy - 40 + ph * 60), (cx - 62, cy + 6 + ph * 60), (cx - 18, cy + 6 + ph * 60)], fill=(130, 200, 250), outline=INK, width=4)
        d.chord((cx - 62, cy - 16 + ph * 60, cx - 18, cy + 28 + ph * 60), 0, 180, fill=(130, 200, 250), outline=INK, width=4)
    elif kind in ("anger", "wut"):
        for a in (0, 90):
            dx, dy = math.cos(math.radians(a + 45)) * 40 * s, math.sin(math.radians(a + 45)) * 40 * s
            d.line((cx - dx, cy - 80 - dy, cx + dx, cy - 80 + dy), fill=(230, 60, 50), width=int(16 * s))
    elif kind in ("music", "musik"):
        for i in range(2):
            ph = (t * 0.8 + i * 0.5) % 1
            nx, ny = cx + i * 50 + math.sin(t * 4 + i) * 10, cy - 30 - ph * 150
            d.ellipse((nx - 16, ny - 12, nx + 16, ny + 12), fill=INK)
            d.line((nx + 14, ny, nx + 14, ny - 60), fill=INK, width=7)


# ------------------------------------------------------------------ Wetter und Hintergrund-Leben

_rnd = random.Random(42)
_DROPS = [(_rnd.random(), _rnd.random(), _rnd.random()) for _ in range(140)]


def draw_weather(layer, kind, t):
    d = ImageDraw.Draw(layer)
    kind = str(kind or "").lower()
    if kind in ("rain", "regen", "storm", "sturm", "gewitter"):
        for a, b, c in _DROPS:
            x = (a * (W + 300) - 150 - t * 180) % (W + 300) - 150
            y = (b * H + t * (1500 + c * 500)) % H
            d.line((x, y, x - 14, y + 46), fill=(190, 220, 255, 170), width=4)
        if kind != "rain" and kind != "regen" and (t % 2.6) < 0.12:
            d.rectangle((0, 0, W, H), fill=(255, 255, 255, 110))
    elif kind in ("snow", "schnee"):
        for a, b, c in _DROPS:
            x = (a * W + math.sin(t * 1.4 + c * 9) * 40) % W
            y = (b * H + t * (160 + c * 140)) % H
            r = 5 + c * 6
            d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, 230))
    elif kind in ("wind", "sturmwind"):
        for i, (a, b, c) in enumerate(_DROPS[:14]):
            x = (a * (W + 600) + t * (900 + c * 500)) % (W + 600) - 300
            y = 300 + b * (GROUND - 300)
            d.arc((x, y, x + 260, y + 50), 180, 320, fill=(255, 255, 255, 190), width=6)
            if i < 7:   # Blätter
                d.ellipse((x + 300, y + math.sin(t * 6 + i) * 30, x + 326, y + 14 + math.sin(t * 6 + i) * 30), fill=(220, 140, 60, 255))
    elif kind in ("heat", "hitze"):
        d.rectangle((0, 0, W, H), fill=(255, 120, 40, 34 + int(14 * math.sin(t * 2))))
    elif kind in ("dark", "dunkel", "blackout"):
        d.rectangle((0, 0, W, H), fill=(4, 6, 20, 150))


def draw_ambient(layer, place, night, t):
    """Kleine Bewegung im Hintergrund, damit kein Bild stillsteht."""
    d = ImageDraw.Draw(layer)
    from .places import OUTDOOR
    if place in OUTDOOR and not night:
        cx = (t * 22 + 300) % (W + 400) - 200                    # ziehende Wolke
        for dx, dy, r in ((0, 0, 50), (52, 12, 40), (-52, 16, 36), (10, 24, 44)):
            d.ellipse((cx + dx - r, 300 + dy - r, cx + dx + r, 300 + dy + r), fill=(255, 255, 255, 235))
        for i in range(2):                                        # Vögel
            bx = (t * 90 + i * 400) % (W + 300) - 150
            by = 470 + i * 60 + math.sin(t * 3 + i) * 14
            fl = math.sin(t * 10 + i) * 12
            d.line((bx - 22, by - fl, bx, by, bx + 22, by - fl), fill=INK, width=5, joint="curve")
    if (place in OUTDOOR and night) or place == "space":
        for i, (a, b, c) in enumerate(_DROPS[:26]):                # funkelnde Sterne
            tw = 0.5 + 0.5 * math.sin(t * (2 + c * 3) + i)
            x, y, r = a * W, b * (GROUND - 380), 3 + 5 * tw
            d.line((x - r * 2, y, x + r * 2, y), fill=(255, 255, 230, int(200 * tw)), width=3)
            d.line((x, y - r * 2, x, y + r * 2), fill=(255, 255, 230, int(200 * tw)), width=3)
        ph = (t % 5.0) / 0.7                                        # Sternschnuppe
        if ph < 1:
            sx, sy = 200 + ph * 500, 240 + ph * 160
            d.line((sx - 90, sy - 30, sx, sy), fill=(255, 255, 240, int(255 * (1 - ph))), width=6)
    if place == "underwater":
        for i, (a, b, c) in enumerate(_DROPS[:18]):                # aufsteigende Blasen
            x = a * W + math.sin(t * 2 + i) * 16
            y = (b * H - t * (90 + c * 90)) % GROUND
            r = 8 + c * 14
            d.ellipse((x - r, y - r, x + r, y + r), outline=(230, 250, 255, 220), width=4)
    if place in ("basement", "cave"):
        fl = int(18 + 16 * math.sin(t * 9) * math.sin(t * 2.3))    # flackerndes Licht
        d.rectangle((0, 0, W, H), fill=(0, 0, 0, max(0, fl)))


# ------------------------------------------------------------------ Tiere und Wesen

def creature(kind, t, facing=1, mouth=0.0, mood="", scale=1.0):
    """Zeichnet ein Wesen; gibt (Bild, Fußpunkt-x, Fußpunkt-y, schwebt) zurück."""
    S = 2
    k = S * scale
    im = Image.new("RGBA", (int(620 * k), int(620 * k)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx, gy = im.width / 2, im.height - 30 * k
    o = int(O * k)
    bob = math.sin(t * 4) * 8 * k
    blink = (t % 3.1) < 0.12
    wide = mood in ("shocked", "scared")

    def eye(x, y, r):
        if blink and not wide:
            d.arc((x - r, y - r * 0.4, x + r, y + r), 200, 340, fill=INK, width=int(r * 0.4))
            return
        rr = r * (1.25 if wide else 1.0)
        d.ellipse((x - rr - 4 * k, y - rr - 4 * k, x + rr + 4 * k, y + rr + 4 * k), fill=INK)
        d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=(255, 255, 255))
        pr = rr * (0.4 if wide else 0.6)
        d.ellipse((x + facing * rr * 0.25 - pr, y - pr, x + facing * rr * 0.25 + pr, y + pr), fill=INK)

    def mouthf(x, y, w):
        if mouth > 0.1:
            d.ellipse((x - w * 0.6, y - 6 * k - mouth * 12 * k, x + w * 0.6, y + 6 * k + mouth * 12 * k), fill=INK)
        elif mood == "sad":
            d.arc((x - w, y, x + w, y + 24 * k), 200, 340, fill=INK, width=int(6 * k))
        else:
            d.arc((x - w, y - 20 * k, x + w, y + 6 * k), 25, 155, fill=INK, width=int(6 * k))

    kind = str(kind).lower()
    fly = False
    if kind in ("cat", "katze", "dog", "hund"):
        dog = kind in ("dog", "hund")
        col = (214, 160, 100) if dog else (240, 160, 80)
        wag = math.sin(t * (12 if dog else 3)) * 30
        tx = cx - 110 * k * facing
        d.line((tx, gy - 110 * k, tx - facing * 60 * k, gy - (200 + wag) * k), fill=INK, width=int(34 * k))
        d.line((tx, gy - 110 * k, tx - facing * 60 * k, gy - (200 + wag) * k), fill=col, width=int(20 * k))
        for lx in (-70, 60):
            d.rounded_rectangle((cx + lx * k, gy - 70 * k, cx + (lx + 34) * k, gy), int(14 * k), fill=col, outline=INK, width=o)
        d.rounded_rectangle((cx - 120 * k, gy - 170 * k, cx + 110 * k, gy - 40 * k), int(60 * k), fill=col, outline=INK, width=o)
        hx, hy = cx + 90 * k * facing, gy - 220 * k + bob * 0.5
        if dog:
            for s in (-1, 1):
                d.ellipse((hx + s * 70 * k - 30 * k, hy - 60 * k, hx + s * 70 * k + 30 * k, hy + 50 * k), fill=(150, 100, 60), outline=INK, width=o)
        else:
            for s in (-1, 1):
                d.polygon([(hx + s * 80 * k, hy - 30 * k), (hx + s * 70 * k, hy - 120 * k), (hx + s * 20 * k, hy - 70 * k)], fill=col, outline=INK, width=o)
        d.ellipse((hx - 95 * k, hy - 85 * k, hx + 95 * k, hy + 85 * k), fill=col, outline=INK, width=o)
        eye(hx - 34 * k, hy - 8 * k, 20 * k)
        eye(hx + 34 * k, hy - 8 * k, 20 * k)
        d.ellipse((hx - 12 * k, hy + 22 * k, hx + 12 * k, hy + 40 * k), fill=INK if dog else (240, 120, 130))
        mouthf(hx, hy + 54 * k, 16 * k)
    elif kind in ("spider", "spinne"):
        by = gy - 150 * k + bob * 0.4
        for s in (-1, 1):
            for i in range(4):
                a = 20 + i * 22 + math.sin(t * 8 + i * 1.5 + s) * 6
                kx, ky = cx + s * (80 + i * 26) * k, by - (70 - i * 16) * k
                d.line((cx + s * 40 * k, by, kx, ky, cx + s * (130 + i * 34) * k, gy), fill=INK, width=int(16 * k), joint="curve")
                d.line((cx + s * 40 * k, by, kx, ky, cx + s * (130 + i * 34) * k, gy), fill=(120, 78, 50), width=int(7 * k), joint="curve")
        d.ellipse((cx - 110 * k, by - 90 * k, cx + 110 * k, by + 90 * k), fill=(120, 78, 50), outline=INK, width=o)
        d.ellipse((cx - 60 * k, by - 70 * k, cx + 60 * k, by - 10 * k), fill=(150, 104, 70))
        eye(cx - 36 * k, by + 6 * k, 24 * k)
        eye(cx + 36 * k, by + 6 * k, 24 * k)
        mouthf(cx, by + 58 * k, 16 * k)
    elif kind in ("ghost", "geist"):
        fly = True
        by = gy - 330 * k + bob * 2
        pts = [(cx - 110 * k, by + 170 * k)]
        for i in range(7):
            pts.append((cx - 110 * k + i * 36.6 * k, by + (170 + (26 if i % 2 else 0) + math.sin(t * 6 + i) * 8) * k))
        pts.append((cx + 110 * k, by + 170 * k))
        d.chord((cx - 110 * k, by - 110 * k, cx + 110 * k, by + 110 * k), 180, 360, fill=(248, 248, 255), outline=INK, width=o)
        d.polygon([(cx - 110 * k, by)] + pts[1:-1] + [(cx + 110 * k, by)], fill=(248, 248, 255))
        d.line([(cx - 110 * k, by)] + pts[1:-1] + [(cx + 110 * k, by)], fill=INK, width=o, joint="curve")
        eye(cx - 38 * k, by - 10 * k, 22 * k)
        eye(cx + 38 * k, by - 10 * k, 22 * k)
        d.ellipse((cx - 16 * k, by + 40 * k, cx + 16 * k, by + (70 + mouth * 20) * k), fill=INK)
    elif kind in ("alien", "außerirdischer"):
        col = (120, 210, 120)
        for lx in (-40, 20):
            d.rounded_rectangle((cx + lx * k, gy - 90 * k, cx + (lx + 24) * k, gy), int(10 * k), fill=col, outline=INK, width=o)
        d.rounded_rectangle((cx - 70 * k, gy - 220 * k, cx + 70 * k, gy - 70 * k), int(50 * k), fill=col, outline=INK, width=o)
        hy = gy - 300 * k + bob * 0.5
        for s in (-1, 1):
            d.line((cx + s * 50 * k, hy - 80 * k, cx + s * 90 * k, hy - 160 * k), fill=INK, width=int(12 * k))
            d.ellipse((cx + s * 90 * k - 18 * k, hy - 178 * k, cx + s * 90 * k + 18 * k, hy - 142 * k), fill=(250, 220, 90), outline=INK, width=int(5 * k))
        d.ellipse((cx - 130 * k, hy - 100 * k, cx + 130 * k, hy + 90 * k), fill=col, outline=INK, width=o)
        for s in (-1, 1):
            d.ellipse((cx + s * 54 * k - 38 * k, hy - 44 * k, cx + s * 54 * k + 38 * k, hy + 30 * k), fill=INK)
            d.ellipse((cx + s * 54 * k - 4 * k, hy - 30 * k, cx + s * 54 * k + 14 * k, hy - 12 * k), fill=(255, 255, 255))
        mouthf(cx, hy + 60 * k, 14 * k)
    elif kind in ("robot", "roboter"):
        col = (170, 180, 196)
        for lx in (-50, 20):
            d.rectangle((cx + lx * k, gy - 90 * k, cx + (lx + 30) * k, gy), fill=(120, 128, 142), outline=INK, width=o)
        d.rounded_rectangle((cx - 90 * k, gy - 250 * k, cx + 90 * k, gy - 80 * k), int(16 * k), fill=col, outline=INK, width=o)
        lit = int(t * 4) % 3
        for i in range(3):
            d.ellipse((cx - 50 * k + i * 36 * k, gy - 150 * k, cx - 26 * k + i * 36 * k, gy - 126 * k),
                      fill=(110, 240, 150) if i == lit else (90, 100, 112), outline=INK, width=int(4 * k))
        hy = gy - 330 * k + bob * 0.3
        d.line((cx, hy - 70 * k, cx, hy - 120 * k), fill=INK, width=int(10 * k))
        d.ellipse((cx - 16 * k, hy - 146 * k, cx + 16 * k, hy - 114 * k), fill=(240, 80, 70), outline=INK, width=int(5 * k))
        d.rounded_rectangle((cx - 110 * k, hy - 70 * k, cx + 110 * k, hy + 70 * k), int(24 * k), fill=col, outline=INK, width=o)
        for s in (-1, 1):
            d.ellipse((cx + s * 44 * k - 26 * k, hy - 34 * k, cx + s * 44 * k + 26 * k, hy + 18 * k), fill=(40, 44, 54))
            if not blink:
                d.ellipse((cx + s * 44 * k - 14 * k, hy - 22 * k, cx + s * 44 * k + 14 * k, hy + 6 * k), fill=(110, 220, 255))
        d.rectangle((cx - 40 * k, hy + 34 * k, cx + 40 * k, hy + (42 + mouth * 14) * k), fill=INK)
    elif kind in ("bird", "vogel"):
        fly = True
        by = gy - 380 * k + bob * 2.5
        fl = math.sin(t * 14) * 50 * k
        d.polygon([(cx - 20 * k, by), (cx - 60 * k, by - 40 * k - fl), (cx + 40 * k, by - 10 * k)], fill=(60, 120, 210), outline=INK, width=o)
        d.ellipse((cx - 90 * k, by - 60 * k, cx + 90 * k, by + 60 * k), fill=(90, 160, 240), outline=INK, width=o)
        d.polygon([(cx + facing * 80 * k, by - 10 * k), (cx + facing * 140 * k, by + 6 * k), (cx + facing * 80 * k, by + 22 * k)], fill=(250, 180, 50), outline=INK, width=int(5 * k))
        eye(cx + facing * 40 * k, by - 12 * k, 20 * k)
    elif kind in ("dino", "dinosaurier", "monster"):
        col = (110, 190, 110) if kind != "monster" else (150, 110, 200)
        d.polygon([(cx - 100 * k * facing, gy - 120 * k), (cx - 300 * k * facing, gy - 20 * k), (cx - 80 * k * facing, gy - 40 * k)], fill=col, outline=INK, width=o)
        for lx in (-60, 40):
            d.rounded_rectangle((cx + lx * k, gy - 90 * k, cx + (lx + 44) * k, gy), int(16 * k), fill=col, outline=INK, width=o)
        d.ellipse((cx - 130 * k, gy - 280 * k, cx + 130 * k, gy - 50 * k), fill=col, outline=INK, width=o)
        hx, hy = cx + 110 * k * facing, gy - 350 * k + bob
        d.rounded_rectangle((hx - 110 * k, hy - 80 * k, hx + 130 * k, hy + 70 * k), int(60 * k), fill=col, outline=INK, width=o)
        eye(hx - 10 * k, hy - 20 * k, 24 * k)
        eye(hx + 60 * k, hy - 20 * k, 24 * k)
        for i in range(4):
            tx = hx - 40 * k + i * 40 * k
            d.polygon([(tx, hy + 40 * k), (tx + 14 * k, hy + (64 + mouth * 20) * k), (tx + 28 * k, hy + 40 * k)], fill=(255, 255, 255), outline=INK, width=int(3 * k))
        for i in range(4):
            sx = cx - 80 * k + i * 50 * k
            d.polygon([(sx, gy - 268 * k), (sx + 22 * k, gy - 330 * k), (sx + 44 * k, gy - 268 * k)], fill=(70, 150, 80), outline=INK, width=int(5 * k))
    elif kind in ("fish", "fisch", "shark", "hai"):
        fly = True
        shark = kind in ("shark", "hai")
        col = (120, 140, 160) if shark else (250, 150, 60)
        by = gy - 330 * k + bob * 2
        wag = math.sin(t * 9) * 26 * k
        d.polygon([(cx - 120 * k * facing, by), (cx - 220 * k * facing, by - 70 * k + wag), (cx - 220 * k * facing, by + 70 * k + wag)], fill=col, outline=INK, width=o)
        d.ellipse((cx - 150 * k, by - 80 * k, cx + 150 * k, by + 80 * k), fill=col, outline=INK, width=o)
        d.polygon([(cx - 30 * k, by - 70 * k), (cx + 10 * k, by - 150 * k), (cx + 50 * k, by - 70 * k)], fill=col, outline=INK, width=o)
        eye(cx + facing * 80 * k, by - 16 * k, 20 * k)
        if shark:
            for i in range(4):
                tx = cx + facing * (40 + i * 22) * k
                d.polygon([(tx, by + 30 * k), (tx + 10 * k * facing, by + 52 * k), (tx + 20 * k * facing, by + 30 * k)], fill=(255, 255, 255), outline=INK, width=int(3 * k))
        else:
            mouthf(cx + facing * 100 * k, by + 34 * k, 12 * k)
    else:
        return None
    out = im.resize((im.width // S, im.height // S), Image.LANCZOS)
    return out, cx / S, gy / S, fly


CREATURES = ("cat", "dog", "spider", "ghost", "alien", "robot", "bird", "dino", "monster", "fish", "shark")
