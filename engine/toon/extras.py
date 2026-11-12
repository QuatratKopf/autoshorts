"""Leben in der Szene: Requisiten (Auto, Feuer, Rakete, Meteor …), Gefühls-Symbole über dem Kopf, Wetter,
Tiere/Wesen und kleine Hintergrund-Bewegungen (Wolken, funkelnde Sterne). Alles wird pro Bild gezeichnet (t = Sekunden)."""
import math
import random

from PIL import Image, ImageDraw

from .places import GROUND, W, H, FAR, depth, px

INK = (22, 22, 26)
O = 7


def _dk(col, a=0.24):
    """Dunklere Schattenseite einer Farbe (wie rig._dark); Deckkraft bleibt erhalten."""
    c = tuple(int(col[i] * (1 - a) + (20, 16, 40)[i] * a) for i in range(3))
    return c + tuple(col[3:4])


def _lt(col, a=0.3):
    c = tuple(int(col[i] * (1 - a) + 255 * a) for i in range(3))
    return c + tuple(col[3:4])


def _box(box):
    x0, y0, x1, y1 = box
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)


def _o(d, box, col, w=O, shade=True):
    """Ellipse im Stil der Figuren: Umriss, dunklere Schattenseite unten rechts, helle Fläche, kleiner Glanz oben links."""
    x0, y0, x1, y1 = box = _box(box)
    bw, bh = x1 - x0, y1 - y0
    if not shade or min(bw, bh) < 18 or col == INK:
        d.ellipse(box, fill=col, outline=INK, width=w)
        return
    d.ellipse(box, fill=_dk(col), outline=INK, width=w)
    d.ellipse((x0 + w * 0.6, y0 + w * 0.6, x1 - bw * 0.14, y1 - bh * 0.16), fill=col)
    if min(bw, bh) >= 50:
        d.ellipse((x0 + bw * 0.2, y0 + bh * 0.16, x0 + bw * 0.38, y0 + bh * 0.3), fill=_lt(col, 0.45))


def _r(d, box, col, r=10, w=O, shade=True):
    """Abgerundetes Rechteck im Stil der Figuren: Umriss, Schattenkante rechts und unten, helle Fläche, Glanzstreifen."""
    x0, y0, x1, y1 = box = _box(box)
    bw, bh = x1 - x0, y1 - y0
    if not shade or min(bw, bh) < 18 or col == INK:
        d.rounded_rectangle(box, r, fill=col, outline=INK, width=w)
        return
    r = max(0, min(r, bw / 2 - 1, bh / 2 - 1))
    d.rounded_rectangle(box, r, fill=_dk(col), outline=INK, width=w)
    sx, sy = min(bw * 0.12, 26), min(bh * 0.12, 26)
    d.rounded_rectangle((x0 + w * 0.6, y0 + w * 0.6, x1 - max(sx, w), y1 - max(sy, w)), max(0, r - 2), fill=col)
    if bw >= 50 and bh >= 50:
        d.rounded_rectangle((x0 + w + bw * 0.06, y0 + w + bh * 0.06, x0 + w + bw * 0.06 + max(6, bw * 0.06), y1 - max(sy, w) - bh * 0.12),
                            3, fill=_lt(col, 0.4))


def _poly(d, pts, col, w=O, shade=0.14):
    """Fläche aus Punkten mit Umriss und dunklerer Schattenseite (unten rechts)."""
    d.polygon(pts, fill=_dk(col), outline=INK, width=w)
    if shade:
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        sz = max(max(xs) - min(xs), max(ys) - min(ys))
        d.polygon([(mx + (x - mx) * (1 - shade) - sz * shade * 0.3, my + (y - my) * (1 - shade) - sz * shade * 0.3) for x, y in pts], fill=col)


def _blobs(d, circles, col, w=O):
    """Mehrere Kreise als eine Form (Baumkrone, Wolke, Busch): gemeinsamer Umriss, Schatten unten, Licht oben."""
    for cx, cy, r in circles:
        d.ellipse((cx - r - w, cy - r - w, cx + r + w, cy + r + w), fill=INK)
    for cx, cy, r in circles:
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=_dk(col, 0.26))
    for cx, cy, r in circles:
        d.ellipse((cx - r * 0.86 - r * 0.1, cy - r * 0.9 - r * 0.12, cx + r * 0.86 - r * 0.1, cy + r * 0.72 - r * 0.12), fill=col)
    for cx, cy, r in circles[:3]:
        d.ellipse((cx - r * 0.5, cy - r * 0.62, cx + r * 0.1, cy - r * 0.18), fill=_lt(col, 0.22))


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
    d.polygon([(x - 34 * s, GROUND), (x - 22 * s, GROUND - 300 * s), (x + 22 * s, GROUND - 300 * s), (x + 34 * s, GROUND)], fill=(104, 68, 44), outline=INK, width=O)
    d.polygon([(x - 28 * s, GROUND - 4), (x - 18 * s, GROUND - 300 * s), (x + 8 * s, GROUND - 300 * s), (x + 12 * s, GROUND - 4)], fill=(134, 90, 58))
    d.line((x - 4 * s, GROUND - 230 * s, x - 44 * s, GROUND - 300 * s), fill=INK, width=int(22 * s))       # Ast
    d.line((x - 4 * s, GROUND - 230 * s, x - 44 * s, GROUND - 300 * s), fill=(120, 80, 52), width=int(10 * s))
    _blobs(d, [(x + dx * s + sway, GROUND + dy * s, r * s) for dx, dy, r in
               ((0, -400, 128), (-96, -320, 100), (96, -326, 104), (-30, -282, 96), (60, -268, 92), (-110, -400, 80), (104, -420, 84))], (88, 168, 92))
    for dx, dy in ((-60, -350), (40, -300), (80, -400), (-20, -440)):                                      # Früchte/Blüten-Tupfer
        d.ellipse((x + dx * s + sway - 9, GROUND + dy * s - 9, x + dx * s + sway + 9, GROUND + dy * s + 9), fill=(120, 196, 110))


def p_rock(d, x, t, s=1.0):
    pts = [(x - 130 * s, GROUND), (x - 112 * s, GROUND - 62 * s), (x - 60 * s, GROUND - 108 * s), (x + 10 * s, GROUND - 118 * s),
           (x + 78 * s, GROUND - 90 * s), (x + 124 * s, GROUND - 40 * s), (x + 132 * s, GROUND)]
    d.polygon(pts, fill=(118, 116, 128), outline=INK, width=O)
    d.polygon([(x - 120 * s, GROUND - 6), (x - 104 * s, GROUND - 60 * s), (x - 56 * s, GROUND - 100 * s), (x + 8 * s, GROUND - 110 * s),
               (x + 60 * s, GROUND - 84 * s), (x + 30 * s, GROUND - 40 * s), (x - 20 * s, GROUND - 22 * s)], fill=(156, 154, 166))
    d.polygon([(x - 70 * s, GROUND - 86 * s), (x - 20 * s, GROUND - 104 * s), (x - 40 * s, GROUND - 76 * s)], fill=(186, 184, 196))     # Glanzkante
    d.line((x + 20 * s, GROUND - 60 * s, x + 50 * s, GROUND - 30 * s, x + 44 * s, GROUND - 6), fill=(90, 88, 100), width=5)        # Riss


def p_box(d, x, t, s=1.0):
    _r(d, (x - 100, GROUND - 170, x + 100, GROUND), (214, 170, 110), 8)
    d.line((x - 100, GROUND - 120, x + 100, GROUND - 120), fill=INK, width=5)
    _r(d, (x - 24, GROUND - 170, x + 24, GROUND - 100), (236, 204, 150), 4, 5)


def p_car(d, x, t, s=1.0):
    b = math.sin(t * 9) * 3
    col, dark = (226, 70, 60), (184, 50, 48)
    d.ellipse((x - 230, GROUND - 22, x + 230, GROUND + 18), fill=(0, 0, 0, 60))
    _r(d, (x - 210, GROUND - 150 + b, x + 210, GROUND - 40 + b), col, 30)
    d.rounded_rectangle((x - 120, GROUND - 240 + b, x + 110, GROUND - 140 + b), 34, fill=col, outline=INK, width=O)
    d.rounded_rectangle((x - 204, GROUND - 84 + b, x + 204, GROUND - 46 + b), 18, fill=dark)                 # Schattenkante unten
    d.rounded_rectangle((x - 190, GROUND - 144 + b, x + 60, GROUND - 128 + b), 8, fill=(244, 110, 96))       # Glanz
    _r(d, (x - 96, GROUND - 220 + b, x - 6, GROUND - 150 + b), (170, 220, 250), 14, 5)
    _r(d, (x + 8, GROUND - 220 + b, x + 90, GROUND - 150 + b), (170, 220, 250), 14, 5)
    for wx0 in (-90, 14):
        d.polygon([(x + wx0 + 8, GROUND - 214 + b), (x + wx0 + 30, GROUND - 214 + b), (x + wx0 + 14, GROUND - 156 + b), (x + wx0 + 2, GROUND - 156 + b)], fill=(220, 240, 255))
    d.line((x - 2, GROUND - 140 + b, x - 2, GROUND - 52 + b), fill=INK, width=4)                             # Türfuge und Griff
    d.rounded_rectangle((x + 14, GROUND - 124 + b, x + 50, GROUND - 112 + b), 5, fill=INK)
    for wx in (-120, 120):
        _o(d, (x + wx - 48, GROUND - 90, x + wx + 48, GROUND + 6), (40, 40, 46))
        _o(d, (x + wx - 20, GROUND - 62, x + wx + 20, GROUND - 22), (200, 200, 206), 4)
        d.ellipse((x + wx - 7, GROUND - 49, x + wx + 7, GROUND - 35), fill=(120, 120, 128))
    _o(d, (x + 180, GROUND - 120 + b, x + 214, GROUND - 90 + b), (255, 236, 150), 4)
    _o(d, (x - 214, GROUND - 118 + b, x - 192, GROUND - 92 + b), (230, 60, 60), 4)
    d.rounded_rectangle((x - 222, GROUND - 70 + b, x - 196, GROUND - 52 + b), 6, fill=(90, 92, 100))         # Stoßstangen
    d.rounded_rectangle((x + 196, GROUND - 70 + b, x + 222, GROUND - 52 + b), 6, fill=(90, 92, 100))


def p_fire(d, x, t, s=1.0):
    d.ellipse((x - 190 * s, GROUND - 150 * s, x + 190 * s, GROUND + 30), fill=(255, 190, 80, 46))            # Feuerschein
    for dx in (-60, 40):
        d.line((x + dx - 50, GROUND - 16, x + dx + 60, GROUND - 40), fill=INK, width=34)
        d.line((x + dx - 50, GROUND - 16, x + dx + 60, GROUND - 40), fill=(118, 76, 48), width=22)
    for i, (col, sc) in enumerate((((236, 84, 40), 1.0), ((250, 150, 44), 0.72), ((255, 214, 90), 0.46), ((255, 246, 190), 0.24))):
        for j, off in enumerate((-0.42, 0.0, 0.42)):                                                     # drei Zungen je Farbschicht
            fl = 1 + 0.16 * math.sin(t * 11 + i * 2 + j * 1.7)
            hgt, wd = 240 * sc * fl * s * (1.0 if j == 1 else 0.68), 62 * sc * s
            cx = x + off * 120 * sc * s
            tip = cx + math.sin(t * 7 + i + j * 2) * 22 * sc
            pts = [(cx - wd, GROUND - 40), (cx - wd * 0.8, GROUND - 40 - hgt * 0.45), (tip, GROUND - 40 - hgt),
                   (cx + wd * 0.8, GROUND - 40 - hgt * 0.45), (cx + wd, GROUND - 40), (cx, GROUND - 22)]
            if i == 0:
                d.polygon(pts, fill=col, outline=INK, width=O)
            else:
                d.polygon(pts, fill=col)
    for k in range(6):                                                                                   # Funken
        ph = (t * 0.9 + k / 6) % 1
        fx, fy = x + math.sin(k * 2.3 + t * 2) * 90 * s, GROUND - 120 * s - ph * 380 * s
        d.ellipse((fx - 6, fy - 6, fx + 6, fy + 6), fill=(255, 220, 110, int(255 * (1 - ph))))


def p_tv(d, x, t, s=1.0):
    _r(d, (x - 30, GROUND - 120, x + 30, GROUND), (60, 60, 66), 4, 5)
    _r(d, (x - 200, GROUND - 400, x + 200, GROUND - 120), (40, 44, 54), 16)
    flick = 200 + int(40 * math.sin(t * 13))
    d.rounded_rectangle((x - 176, GROUND - 376, x + 176, GROUND - 144), 8, fill=(110, flick, 250))
    d.rectangle((x - 176, GROUND - 200, x + 176, GROUND - 160), fill=(226, 58, 52))
    d.rectangle((x - 150, GROUND - 192, x - 20, GROUND - 168), fill=(250, 250, 250))                          # Laufschrift-Balken
    d.polygon([(x - 176, GROUND - 300), (x - 96, GROUND - 376), (x - 40, GROUND - 376), (x - 176, GROUND - 240)], fill=(255, 255, 255, 70))   # Spiegelung


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
    d.polygon([(xx - 60, y + 40), (xx + 60, y + 40), (xx + 200, GROUND), (xx - 200, GROUND)],
              fill=(190, 255, 190, 70 + int(30 * math.sin(t * 6))))
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
    """Explosion: Druckwelle, Feuerball mit hellem Kern, Rauchballen am Rand und fliegende Funken."""
    k = min(1.0, max(0.0, t) / 0.5)
    if t < 0:
        return
    cy = GROUND - 240
    r = 70 + 300 * k
    w = max(0.0, t - 0.05)                                                           # Druckwelle läuft schnell nach außen
    rw = 120 + 900 * w
    if w < 0.8:
        d.ellipse((x - rw, cy - rw * 0.9, x + rw, cy + rw * 0.9), outline=(255, 255, 255, int(210 * (1 - w / 0.8))), width=int(22 * (1 - w / 0.8)) + 4)
    for j in range(9):                                                               # dunkle Rauchballen hinter dem Feuer
        a = j / 9 * math.tau + 0.3
        m = r * (0.95 + 0.12 * math.sin(t * 3 + j))
        px_, py_ = x + math.cos(a) * m, cy + math.sin(a) * m * 0.9
        rr = r * (0.34 + 0.06 * (j % 3))
        d.ellipse((px_ - rr - 5, py_ - rr - 5, px_ + rr + 5, py_ + rr + 5), fill=INK)
        d.ellipse((px_ - rr, py_ - rr, px_ + rr, py_ + rr), fill=(86, 80, 92))
        d.ellipse((px_ - rr * 0.8, py_ - rr * 0.9, px_ + rr * 0.5, py_ + rr * 0.3), fill=(112, 106, 118))
    for i, col in enumerate(((228, 76, 38), (248, 140, 44), (255, 204, 84), (255, 246, 196))):
        rr = r * (1 - i * 0.22)
        pts = []
        n = 22
        for j in range(n):
            a = j / n * math.tau
            m = rr * (1.0 if j % 2 else 0.74) * (1 + 0.07 * math.sin(t * 22 + j * 1.3 + i))
            pts.append((x + math.cos(a) * m, cy + math.sin(a) * m * 0.94))
        d.polygon(pts, fill=col, outline=INK if i == 0 else None, width=O)
    for j in range(14):                                                              # Funken und Trümmer fliegen im Bogen
        a = j / 14 * math.tau + 0.2
        dist = (240 + 520 * min(1.0, t / 0.9)) * (0.7 + 0.3 * ((j * 7) % 5) / 4)
        fx, fy = x + math.cos(a) * dist, cy + math.sin(a) * dist * 0.8 + 260 * t * t
        al = int(255 * max(0.0, 1 - t / 1.6))
        if j % 3:
            d.ellipse((fx - 9, fy - 9, fx + 9, fy + 9), fill=(255, 214, 96, al))
        else:
            d.rectangle((fx - 12, fy - 9, fx + 12, fy + 9), fill=(70, 64, 72, al))


def p_earth(d, x, t, s=1.0):
    """Erdkugel mit Atmosphäre, Kontinenten, ziehenden Wolken und Schattenseite."""
    from .places import CONTINENTS
    cy, r = 520, 200
    for k in range(5):
        d.ellipse((x - r - 44 + k * 8, cy - r - 44 + k * 8, x + r + 44 - k * 8, cy + r + 44 - k * 8), fill=(110, 170, 255, 22 + k * 6))
    _o(d, (x - r, cy - r, x + r, cy + r), (44, 116, 204))
    d.ellipse((x - r * 0.9, cy - r * 0.95, x + r * 0.55, cy + r * 0.5), fill=(60, 136, 220))
    for pts in CONTINENTS:
        q = [(x + a * r * 0.985, cy + b * r * 0.985) for a, b in pts if a * a + b * b <= 1.0]
        if len(q) >= 3:
            d.polygon(q, fill=(98, 180, 112), outline=(30, 70, 60), width=4)
    sh = (t * 26) % (r * 2)
    for dx, dy, rw in ((-120, -90, 70), (40, 60, 80), (-30, 130, 56), (90, -40, 60)):                    # Wolken ziehen
        cx = x + ((dx + sh + r) % (2 * r)) - r
        if abs(cx - x) < r - rw * 0.9 and abs(dy) < r * 0.8:
            d.rounded_rectangle((cx - rw, cy + dy - 11, cx + rw, cy + dy + 11), 11, fill=(255, 255, 255, 190))
    d.pieslice((x - r, cy - r, x + r, cy + r), -62, 100, fill=(10, 14, 50, 70))                          # Schattenseite
    d.ellipse((x - r * 0.72, cy - r * 0.78, x - r * 0.2, cy - r * 0.34), fill=(255, 255, 255, 60))        # Glanz
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
    """Wirbelsturm: breiter Trichter aus der Wolke, der sich windet, mit umlaufenden Bändern und mitgerissenen Trümmern."""
    n = 12
    rows = []
    for i in range(n + 1):
        f = i / n                                            # 0 = Boden, 1 = Wolke
        y = GROUND - 20 - f * 860
        wdt = 46 + (f ** 1.5) * 330
        ox = math.sin(t * 3.2 + f * 4.5) * (70 * (1 - f) + 18)
        rows.append((x + ox, y, wdt))
    left = [(cx - w, y) for cx, y, w in rows]
    right = [(cx + w, y) for cx, y, w in reversed(rows)]
    d.polygon(left + right, fill=(132, 138, 156, 240), outline=INK, width=O)
    d.polygon([(cx - w * 0.2, y) for cx, y, w in rows] + right, fill=(104, 110, 130, 240))               # Schattenseite
    for i, (cx, y, w) in enumerate(rows[1:-1]):                                                           # umlaufende Bänder
        ph = (t * 2.2 + i * 0.37) % 1
        d.arc((cx - w, y - w * 0.16, cx + w, y + w * 0.16), int(ph * 360), int(ph * 360) + 150, fill=(226, 230, 240, 230), width=7)
        d.arc((cx - w, y - w * 0.16, cx + w, y + w * 0.16), int(ph * 360) + 190, int(ph * 360) + 260, fill=(84, 88, 106, 230), width=6)
    cx, y, w = rows[-1]
    for dx, r in ((-0.9, 150), (-0.4, 190), (0.2, 200), (0.8, 160)):                                      # Wolke oben
        d.ellipse((cx + dx * w - r - O, y - r * 0.8 - O, cx + dx * w + r + O, y + r * 0.6 + O), fill=INK)
    for dx, r in ((-0.9, 150), (-0.4, 190), (0.2, 200), (0.8, 160)):
        d.ellipse((cx + dx * w - r, y - r * 0.8, cx + dx * w + r, y + r * 0.6), fill=(96, 102, 122))
    for k in range(9):                                                                                    # Trümmer kreisen um den Fuß
        a = t * 5 + k * 0.7
        rr = 110 + k * 26
        px_, py_ = rows[0][0] + math.cos(a) * rr, GROUND - 60 - k * 46 + math.sin(a) * 22
        if math.sin(a) > -0.2:
            d.rectangle((px_ - 12, py_ - 8, px_ + 12, py_ + 8), fill=((120, 84, 54), (90, 96, 110), (190, 70, 60))[k % 3], outline=INK, width=3)
    d.ellipse((rows[0][0] - 190, GROUND - 46, rows[0][0] + 190, GROUND + 26), fill=(170, 160, 150, 150))  # Staub am Boden


def p_wave(d, x, t, s=1.0):
    """Riesenwelle: türmt sich auf, mit überschlagendem Kamm, Gischt und helleren Streifen im Wasser."""
    k = min(1.0, t / 4.0)
    top = GROUND - 120 - 330 * k
    def ridge(i, off=0.0):
        return top + off + math.sin(i * 0.012 + t * 3) * 50 - (W - i) * 0.25 * k
    pts = [(0, H)] + [(i, ridge(i)) for i in range(0, W + 60, 60)] + [(W, H)]
    d.polygon(pts, fill=(36, 112, 196, 240), outline=INK, width=O)
    d.polygon([(0, H)] + [(i, ridge(i, 90 + 40 * k)) for i in range(0, W + 60, 60)] + [(W, H)], fill=(52, 140, 220, 240))
    d.polygon([(0, H)] + [(i, ridge(i, 240 + 90 * k)) for i in range(0, W + 60, 60)] + [(W, H)], fill=(76, 164, 236, 240))
    for i in range(0, W + 60, 60):                                                                        # Gischt auf dem Kamm
        y = ridge(i)
        r = 26 + 12 * math.sin(i * 0.05 + t * 5)
        d.ellipse((i - r, y - r * 0.9, i + r, y + r * 0.7), fill=(240, 250, 255, 245))
    cx, cy = 150, ridge(150)                                                                              # Kamm kippt links nach vorn
    d.pieslice((cx - 150, cy - 60, cx + 170, cy + 200), 180, 320, fill=(240, 250, 255, 235))
    d.pieslice((cx - 110, cy - 20, cx + 130, cy + 180), 180, 320, fill=(52, 140, 220, 240))
    for i in range(0, W, 120):
        yy = ridge(i, 150) + math.sin(i + t * 3) * 20
        d.arc((i, yy, i + 100, yy + 60), 180, 360, fill=(200, 232, 252), width=8)
    for j in range(10):                                                                                   # Tropfen spritzen
        ph = (t * 1.3 + j / 10) % 1
        sx = (j * 131) % W
        sy = ridge(sx) - 30 - ph * 150 + 160 * ph * ph
        d.ellipse((sx - 8, sy - 8, sx + 8, sy + 8), fill=(226, 244, 255, int(255 * (1 - ph))))


def p_ice(d, x, t, s=1.0):
    d.polygon([(x - 200, GROUND), (x - 120, GROUND - 260), (x - 20, GROUND - 180), (x + 60, GROUND - 380), (x + 200, GROUND)],
              fill=(150, 200, 236), outline=INK, width=O)
    d.polygon([(x - 190, GROUND - 4), (x - 120, GROUND - 250), (x - 20, GROUND - 172), (x + 58, GROUND - 368), (x + 40, GROUND - 4)], fill=(206, 236, 252))
    d.polygon([(x + 60, GROUND - 368), (x + 30, GROUND - 200), (x + 10, GROUND - 230)], fill=(246, 252, 255))     # Glanzkante
    d.line((x - 20, GROUND - 180, x + 10, GROUND - 40), fill=(130, 186, 228), width=6)
    d.rounded_rectangle((x - 240, GROUND - 16, x + 240, GROUND + 10), 12, fill=(110, 170, 220, 160))          # Wasserlinie


def p_volcano(d, x, t, s=1.0):
    """Vulkan: Kegel mit Schattenseite, glühender Krater, Lavaströme, Rauchsäule und Lavabrocken."""
    top = GROUND - 480
    for k in range(7):                                                                                    # Rauchsäule
        ph = (t * 0.3 + k / 7) % 1
        r = 60 + ph * 170
        cx, cy = x + math.sin(k * 1.9 + t * 0.8) * 50 + ph * 140, top - 40 - ph * 760
        g = int(84 + ph * 50)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(g, g - 4, g + 8, int(220 * (1 - ph))))
    d.ellipse((x - 190, top - 150, x + 190, top + 110), fill=(255, 150, 60, 70))                          # Glut über dem Krater
    d.polygon([(x - 320, GROUND), (x - 84, top), (x + 84, top), (x + 320, GROUND)], fill=(116, 88, 84), outline=INK, width=O)
    d.polygon([(x + 10, top + O), (x + 84 - O, top + O), (x + 320 - O * 2, GROUND - O), (x + 120, GROUND - O)], fill=(92, 68, 70))     # Schattenseite
    d.polygon([(x - 320 + 30, GROUND - O), (x - 200, GROUND - 190), (x - 150, GROUND - 60)], fill=(134, 104, 98))                       # Felsrippe
    d.polygon([(x - 84, top), (x + 84, top), (x + 46, top + 100), (x - 6, top + 190), (x - 52, top + 90)], fill=(250, 120, 40))
    for sx, ln in ((-40, 330), (36, 250)):                                                                # Lavaströme laufen den Hang hinab
        pts = [(x + sx + math.sin(i * 0.9 + sx) * 16 + i * (sx / 9), top + 60 + i * ln / 8) for i in range(9)]
        d.line(pts, fill=INK, width=30, joint="curve")
        d.line(pts, fill=(246, 120, 40), width=20, joint="curve")
        d.line(pts, fill=(255, 196, 80), width=8, joint="curve")
    d.ellipse((x - 84, top - 22, x + 84, top + 22), fill=(255, 196, 80), outline=INK, width=5)
    for i in range(8):
        ph = (t * 0.9 + i / 8) % 1
        a = -math.pi / 2 + (i - 3.5) * 0.26
        px, py = x + math.cos(a) * 440 * ph, top + math.sin(a) * 440 * ph + 400 * ph * ph
        d.ellipse((px - 20, py - 20, px + 20, py + 20), fill=(250, 150, 50), outline=INK, width=4)
        d.ellipse((px - 10, py - 12, px + 4, py + 2), fill=(255, 226, 130))


def p_cloud(d, x, t, s=1.0, dark=False):
    cy = 430 + math.sin(t * 1.2) * 10
    xx = x + math.sin(t * 0.5) * 30
    col = (104, 110, 130) if dark else (252, 252, 255)
    blobs = ((60, -50, 100), (-60, -40, 92), (0, 0, 120), (130, 30, 96), (-130, 34, 90), (0, 50, 110))
    _blobs(d, [(xx + dx, cy + dy, r) for dx, dy, r in blobs], col)
    d.rounded_rectangle((xx - 200, cy + 96, xx + 200, cy + 136), 20, fill=_dk(col, 0.18))                       # flache, schattige Unterseite
    if dark:
        for i in range(12):                     # Regen aus der Wolke
            ph = (t * 1.8 + i / 12) % 1
            rx = xx - 190 + i * 34
            d.line((rx, cy + 130 + ph * 420, rx - 10, cy + 170 + ph * 420), fill=(170, 210, 255, int(255 * (1 - ph))), width=6)


def p_stormcloud(d, x, t, s=1.0):
    p_cloud(d, x, t, s, True)
    if (t % 1.5) < 0.35:
        cy = 430
        pts = [(x + 10, cy + 110), (x - 40, cy + 330), (x + 20, cy + 350), (x - 30, GROUND)]
        d.line(pts, fill=(255, 255, 255, 255), width=22, joint="curve")
        d.line(pts, fill=(255, 236, 120, 255), width=10, joint="curve")


def p_lightning(d, x, t, s=1.0):
    ph = t % 1.3
    if ph < 0.5:
        pts = [(x + 40, 0), (x - 30, 380), (x + 30, 400), (x - 60, 760), (x + 10, 790), (x - 40, GROUND)]
        d.line(pts, fill=(255, 255, 255, 255), width=26, joint="curve")
        d.line(pts, fill=(255, 236, 120, 255), width=12, joint="curve")
        if ph < 0.1:
            d.rectangle((0, 0, W, H), fill=(255, 255, 255, 120))
        d.ellipse((x - 150, GROUND - 40, x + 70, GROUND + 30), fill=(255, 240, 170, 200))


def p_crack(d, x, t, s=1.0):
    """Riss im Boden: eine dunkle Spalte, die sich quer durchs Bild öffnet (liegt flach auf dem Boden, hinter den Figuren)."""
    k = min(1.0, max(0.05, t / 1.3))
    rnd = random.Random(21)
    y0 = GROUND - 120
    n = 15
    half = 520 * k
    mid = [(x - half + 2 * half * i / (n - 1), y0 + (rnd.random() - 0.5) * 46 + 16 * math.sin(i * 1.3)) for i in range(n)]
    wid = [26 * k * math.sin(math.pi * i / (n - 1)) ** 0.7 * (0.6 + 0.8 * rnd.random()) + 2 for i in range(n)]
    top = [(px_, py - w * 0.55) for (px_, py), w in zip(mid, wid)]
    bot = [(px_, py + w) for (px_, py), w in zip(mid, wid)][::-1]
    d.polygon([(a, b_ + 7) for a, b_ in top] + [(a, b_ + 9) for a, b_ in bot], fill=(0, 0, 0, 70))      # Schattenkante
    d.polygon(top + bot, fill=(26, 18, 20), outline=INK, width=5)
    d.line([(a, b_ + 3) for a, b_ in top], fill=(96, 74, 62), width=5, joint="curve")                # helle Bruchkante
    for i in (3, 6, 9, 12):                                        # feine Seitenrisse
        if i / n > k + 0.1:
            continue
        px_, py = mid[i]
        up = -1 if i % 2 else 1
        ln = (50 + 40 * rnd.random()) * k
        d.line((px_, py + up * wid[i] * 0.6, px_ + 26 * up, py + up * ln * 0.55, px_ + 8 * up, py + up * ln), fill=INK, width=5, joint="curve")
    for i in range(5):                                             # Staub steigt aus der Spalte
        ph = (t * 0.7 + i / 5) % 1
        px_ = x - half * 0.8 + i * half * 0.4
        r = 14 + ph * 34
        d.ellipse((px_ - r, y0 - 10 - ph * 120 - r, px_ + r, y0 - 10 - ph * 120 + r), fill=(190, 176, 160, int(150 * (1 - ph))))


def p_flood(d, x, t, s=1.0):
    k = min(1.0, t / 5.0)
    top = GROUND + 120 - 420 * k
    pts = [(0, H)] + [(i, top + math.sin(i * 0.014 + t * 2.4) * 18) for i in range(0, W + 60, 60)] + [(W, H)]
    d.polygon(pts, fill=(60, 140, 220, 215), outline=INK, width=O)
    for i in range(0, W, 180):
        y = top + 70 + (i % 360) * 0.3
        d.arc((i + math.sin(t * 2 + i) * 20, y, i + 110 + math.sin(t * 2 + i) * 20, y + 34), 180, 360, fill=(210, 236, 255, 255), width=6)


def p_smoke(d, x, t, s=1.0):
    for i in range(9):
        ph = (t * 0.35 + i / 9) % 1
        r = 50 + ph * 150
        cx, cy = x + math.sin(i * 2.1 + t) * 40 + ph * 120, GROUND - 80 - ph * 900
        g = int(70 + ph * 60)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(g, g, g + 6, int(230 * (1 - ph))))


def p_aurora(d, x, t, s=1.0):
    for b, col in enumerate(((90, 240, 170), (110, 200, 250), (190, 130, 250))):
        pts_top = [(i, 260 + b * 70 + math.sin(i * 0.006 + t * 0.8 + b) * 70) for i in range(0, W + 60, 60)]
        pts = pts_top + [(i, y + 190) for i, y in reversed(pts_top)]
        d.polygon(pts, fill=(*col, 90))


def p_eclipse(d, x, t, s=1.0):
    cy, r = 520, 170
    k = min(1.0, t / 2.2)
    d.rectangle((0, 0, W, H), fill=(6, 8, 30, int(150 * k)))
    for i in range(14):
        a = i / 14 * math.tau + t * 0.3
        d.line((x + math.cos(a) * (r + 10), cy + math.sin(a) * (r + 10), x + math.cos(a) * (r + 70 + 20 * math.sin(t * 3 + i)),
                cy + math.sin(a) * (r + 70 + 20 * math.sin(t * 3 + i))), fill=(255, 220, 130, 255), width=12)
    _o(d, (x - r, cy - r, x + r, cy + r), (255, 214, 70))
    mx = x + 2 * r * (1 - k)
    d.ellipse((mx - r, cy - r, mx + r, cy + r), fill=(20, 20, 30, 255))


def p_sprout(d, x, t, s=1.0):
    k = min(1.0, t / 2.5)
    hgt = 30 + 330 * k
    pts = [(x + math.sin(i * 0.9) * 14 * k, GROUND - hgt * i / 8) for i in range(9)]
    d.line(pts, fill=INK, width=24, joint="curve")
    d.line(pts, fill=(80, 170, 90), width=14, joint="curve")
    for i, sgn in ((3, -1), (5, 1), (7, -1)):
        if k > i / 9:
            px, py = pts[i]
            lw = 70 * min(1.0, (k - i / 9) * 4)
            d.ellipse((px + (0 if sgn > 0 else -lw), py - 22, px + (lw if sgn > 0 else 0), py + 14), fill=(96, 190, 104), outline=INK, width=4)
    if k >= 1.0:
        px, py = pts[-1]
        for a in range(0, 360, 60):
            d.ellipse((px + math.cos(math.radians(a)) * 30 - 20, py + math.sin(math.radians(a)) * 30 - 20,
                       px + math.cos(math.radians(a)) * 30 + 20, py + math.sin(math.radians(a)) * 30 + 20), fill=(250, 190, 210), outline=INK, width=3)
        d.ellipse((px - 16, py - 16, px + 16, py + 16), fill=(250, 210, 70), outline=INK, width=3)


def p_cart(d, x, t, s=1.0):
    d.line((x - 150, GROUND - 250, x - 110, GROUND - 230, x - 80, GROUND - 60, x + 110, GROUND - 60), fill=INK, width=12, joint="curve")
    d.polygon([(x - 104, GROUND - 210), (x + 150, GROUND - 210), (x + 120, GROUND - 90), (x - 84, GROUND - 90)], fill=(200, 206, 216), outline=INK, width=O)
    for k in range(1, 5):
        d.line((x - 104 + k * 50, GROUND - 210, x - 84 + k * 42, GROUND - 90), fill=INK, width=4)
    d.line((x - 96, GROUND - 150, x + 136, GROUND - 150), fill=INK, width=4)
    for wx in (-60, 96):
        _o(d, (x + wx - 22, GROUND - 44, x + wx + 22, GROUND), (60, 60, 66), 5)


def p_candle(d, x, t, s=1.0):
    _r(d, (x - 26, GROUND - 130, x + 26, GROUND), (250, 244, 226), 6)
    d.line((x, GROUND - 130, x, GROUND - 150), fill=INK, width=5)
    fl = 1 + 0.15 * math.sin(t * 12)
    tip = x + math.sin(t * 7) * 8
    d.ellipse((x - 64, GROUND - 270, x + 64, GROUND - 120), fill=(255, 220, 120, 60))
    d.polygon([(x - 22, GROUND - 160), (tip, GROUND - 160 - 80 * fl), (x + 22, GROUND - 160), (x, GROUND - 140)], fill=(250, 170, 50), outline=INK, width=4)


def p_bus(d, x, t, s=1.0):
    d.ellipse((x - 440, GROUND - 24, x + 440, GROUND + 20), fill=(0, 0, 0, 60))
    _r(d, (x - 420, GROUND - 330, x + 420, GROUND - 50), (240, 190, 60), 30)
    d.rounded_rectangle((x - 414, GROUND - 120, x + 414, GROUND - 56), 20, fill=(210, 156, 44))              # Schattenkante
    d.rectangle((x - 414, GROUND - 176, x + 414, GROUND - 164), fill=(250, 250, 246))                        # Zierstreifen
    for i in range(5):
        _r(d, (x - 390 + i * 150, GROUND - 300, x - 270 + i * 150, GROUND - 190), (170, 220, 250), 10, 5)
        d.polygon([(x - 380 + i * 150, GROUND - 294), (x - 356 + i * 150, GROUND - 294), (x - 372 + i * 150, GROUND - 196), (x - 386 + i * 150, GROUND - 196)], fill=(220, 240, 255))
    _r(d, (x + 300, GROUND - 180, x + 380, GROUND - 60), (200, 160, 50), 6, 5)
    _o(d, (x + 392, GROUND - 130, x + 420, GROUND - 100), (255, 236, 150), 4)
    for wx in (-270, 250):
        _o(d, (x + wx - 56, GROUND - 106, x + wx + 56, GROUND + 6), (40, 40, 46))
        _o(d, (x + wx - 22, GROUND - 72, x + wx + 22, GROUND - 28), (200, 200, 206), 4)


def p_truck(d, x, t, s=1.0):
    d.ellipse((x - 440, GROUND - 24, x + 420, GROUND + 20), fill=(0, 0, 0, 60))
    _r(d, (x - 420, GROUND - 380, x + 150, GROUND - 60), (236, 236, 240), 10)
    d.rectangle((x - 414, GROUND - 130, x + 144, GROUND - 66), fill=(206, 208, 216))                         # Schattenkante
    for lx in (-280, -140, 0):
        d.line((x + lx, GROUND - 372, x + lx, GROUND - 68), fill=(196, 198, 208), width=5)                    # Planken des Aufbaus
    _r(d, (x + 160, GROUND - 280, x + 400, GROUND - 60), (70, 130, 200), 24)
    d.rounded_rectangle((x + 166, GROUND - 120, x + 394, GROUND - 66), 16, fill=(52, 104, 170))
    _r(d, (x + 250, GROUND - 250, x + 380, GROUND - 160), (170, 220, 250), 10, 5)
    d.polygon([(x + 262, GROUND - 244), (x + 290, GROUND - 244), (x + 272, GROUND - 166), (x + 256, GROUND - 166)], fill=(220, 240, 255))
    _o(d, (x + 376, GROUND - 130, x + 402, GROUND - 100), (255, 236, 150), 4)
    for wx in (-300, -180, 290):
        _o(d, (x + wx - 56, GROUND - 106, x + wx + 56, GROUND + 6), (40, 40, 46))
        _o(d, (x + wx - 22, GROUND - 72, x + wx + 22, GROUND - 28), (200, 200, 206), 4)


def p_house(d, x, t, s=1.0):
    _r(d, (x + 110, GROUND - 520, x + 160, GROUND - 400), (150, 96, 80), 4)                                   # Schornstein
    _r(d, (x - 220, GROUND - 340, x + 220, GROUND), (236, 214, 180), 4)
    d.rectangle((x - 214, GROUND - 330, x + 214, GROUND - 304), fill=(196, 172, 140))                          # Schatten unter dem Dach
    d.polygon([(x - 262, GROUND - 330), (x, GROUND - 530), (x + 262, GROUND - 330)], fill=(160, 66, 58), outline=INK, width=O)
    d.polygon([(x - 240, GROUND - 338), (x - 4, GROUND - 516), (x + 60, GROUND - 466), (x - 150, GROUND - 338)], fill=(196, 88, 72))
    for i in range(1, 4):                                                                                        # Ziegelreihen
        y = GROUND - 330 - i * 48
        hw = 262 * (1 - i * 48 / 200)
        d.line((x - hw + 8, y, x + hw - 8, y), fill=(140, 56, 50), width=4)
    _r(d, (x - 44, GROUND - 180, x + 50, GROUND), (124, 82, 52), 8, 6)                                         # Tür mit Klinke und Stufe
    d.ellipse((x + 26, GROUND - 96, x + 40, GROUND - 82), fill=(240, 200, 90), outline=INK, width=3)
    d.rectangle((x - 64, GROUND - 14, x + 70, GROUND), fill=(170, 160, 150), outline=INK, width=4)
    for wx in (-180, 100):
        _r(d, (x + wx, GROUND - 270, x + wx + 84, GROUND - 170), (160, 210, 246), 4, 6, shade=False)
        d.polygon([(x + wx + 10, GROUND - 262), (x + wx + 34, GROUND - 262), (x + wx + 14, GROUND - 178), (x + wx + 6, GROUND - 178)], fill=(226, 242, 255))
        d.line((x + wx + 42, GROUND - 270, x + wx + 42, GROUND - 170), fill=INK, width=5)
        d.line((x + wx, GROUND - 220, x + wx + 84, GROUND - 220), fill=INK, width=5)
        d.rectangle((x + wx - 8, GROUND - 172, x + wx + 92, GROUND - 160), fill=(250, 246, 236), outline=INK, width=4)      # Fensterbank
    _o(d, (x - 230, GROUND - 70, x - 120, GROUND + 4), (96, 170, 96))                                           # Busch vor dem Haus
    _o(d, (x + 120, GROUND - 60, x + 236, GROUND + 4), (96, 170, 96))


def p_trafficlight(d, x, t, s=1.0):
    _r(d, (x - 10, GROUND - 330, x + 10, GROUND), (70, 70, 78), 2, 5)
    _r(d, (x - 44, GROUND - 560, x + 44, GROUND - 320), (50, 50, 58), 14)
    on = int(t / 1.6) % 3
    for i, col in enumerate(((230, 70, 60), (250, 200, 60), (90, 200, 110))):
        _o(d, (x - 26, GROUND - 540 + i * 72, x + 26, GROUND - 488 + i * 72), col if i == on else (90, 90, 96), 4)


def p_canister(d, x, t, s=1.0):
    _r(d, (x - 80, GROUND - 190, x + 80, GROUND), (214, 70, 60), 14)
    _r(d, (x + 20, GROUND - 230, x + 60, GROUND - 190), (60, 60, 66), 6, 5)
    d.line((x - 50, GROUND - 150, x + 50, GROUND - 40), fill=INK, width=6)
    d.line((x + 50, GROUND - 150, x - 50, GROUND - 40), fill=INK, width=6)


def p_cans(d, x, t, s=1.0):
    for i, (dx, dy) in enumerate(((-70, 0), (0, 0), (70, 0), (-35, -92), (35, -92), (0, -184))):
        col = ((220, 90, 70), (240, 196, 70), (90, 160, 110))[i % 3]
        _r(d, (x + dx - 32, GROUND + dy - 90, x + dx + 32, GROUND + dy), col, 8, 5)
        d.rectangle((x + dx - 28, GROUND + dy - 60, x + dx + 28, GROUND + dy - 34), fill=(250, 250, 246))


def p_generator(d, x, t, s=1.0):
    b = math.sin(t * 40) * 3
    _r(d, (x - 150, GROUND - 190 + b, x + 150, GROUND - 30 + b), (240, 170, 50), 16)
    _r(d, (x - 120, GROUND - 160 + b, x - 10, GROUND - 70 + b), (60, 60, 66), 8, 5)
    for i in range(3):
        d.line((x + 30, GROUND - 150 + i * 34 + b, x + 120, GROUND - 150 + i * 34 + b), fill=INK, width=6)
    d.line((x - 170, GROUND - 210, x + 170, GROUND - 210), fill=INK, width=12)
    for wx in (-150, 150):
        d.line((x + wx, GROUND - 210, x + wx, GROUND), fill=INK, width=12)
    for k in range(3):
        ph = (t * 0.8 + k / 3) % 1
        r = 20 + ph * 40
        d.ellipse((x + 170 + ph * 80 - r, GROUND - 140 - ph * 160 - r, x + 170 + ph * 80 + r, GROUND - 140 - ph * 160 + r), fill=(150, 150, 156, int(200 * (1 - ph))))


def p_bike(d, x, t, s=1.0):
    for wx in (-120, 120):
        d.ellipse((x + wx - 90, GROUND - 180, x + wx + 90, GROUND), outline=INK, width=14)
    d.line((x - 120, GROUND - 90, x - 20, GROUND - 230, x + 80, GROUND - 230, x + 120, GROUND - 90), fill=(214, 70, 60), width=14, joint="curve")
    d.line((x - 20, GROUND - 230, x + 20, GROUND - 90, x - 120, GROUND - 90), fill=(214, 70, 60), width=14, joint="curve")
    d.line((x - 50, GROUND - 250, x + 10, GROUND - 250), fill=INK, width=14)
    d.line((x + 80, GROUND - 230, x + 70, GROUND - 290, x + 110, GROUND - 300), fill=INK, width=12, joint="curve")


def p_shelf(d, x, t, s=1.0):
    _r(d, (x - 200, GROUND - 440, x + 200, GROUND), (226, 228, 234), 6)
    rnd = random.Random(int(x))
    for k in range(4):
        y1 = GROUND - 440 + (k + 1) * 110
        d.line((x - 200, y1, x + 200, y1), fill=INK, width=6)
        xx = x - 186
        while xx < x + 150:
            w, hgt = rnd.randint(30, 50), rnd.randint(50, 84)
            _r(d, (xx, y1 - hgt - 4, xx + w, y1 - 4), ((220, 90, 70), (240, 196, 70), (90, 160, 110), (70, 130, 200))[rnd.randint(0, 3)], 5, 4)
            xx += w + 8


def p_table(d, x, t, s=1.0):
    _r(d, (x - 200, GROUND - 190, x + 200, GROUND - 160), (176, 118, 76), 6)
    for lx in (-170, 150):
        _r(d, (x + lx, GROUND - 160, x + lx + 22, GROUND), (130, 86, 54), 4, 5)


def p_fridge(d, x, t, s=1.0):
    _r(d, (x - 110, GROUND - 440, x + 110, GROUND), (236, 240, 244), 16)
    d.line((x - 110, GROUND - 290, x + 110, GROUND - 290), fill=INK, width=O)
    _r(d, (x + 70, GROUND - 400, x + 88, GROUND - 320), (150, 156, 166), 6, 4)
    _r(d, (x + 70, GROUND - 260, x + 88, GROUND - 150), (150, 156, 166), 6, 4)


def p_tent(d, x, t, s=1.0):
    d.polygon([(x - 300, GROUND), (x, GROUND - 380), (x + 300, GROUND)], fill=(186, 112, 52), outline=INK, width=O)
    d.polygon([(x - 286, GROUND - 6), (x, GROUND - 368), (x + 40, GROUND - 6)], fill=(232, 152, 72))           # Licht auf der vorderen Bahn
    d.polygon([(x - 90, GROUND), (x, GROUND - 250), (x + 70, GROUND)], fill=(52, 40, 44), outline=INK, width=5)  # offener Eingang
    d.polygon([(x - 90, GROUND), (x, GROUND - 250), (x - 30, GROUND)], fill=(246, 178, 96), outline=INK, width=4)   # zurückgeschlagene Plane
    d.line((x, GROUND - 380, x, GROUND - 430), fill=INK, width=8)                                               # Stange mit Wimpel
    d.polygon([(x, GROUND - 430), (x + 50, GROUND - 416 + math.sin(t * 5) * 6), (x, GROUND - 400)], fill=(220, 70, 60), outline=INK, width=3)
    for sx in (-1, 1):                                                                                          # Spannleinen
        d.line((x + sx * 150, GROUND - 190, x + sx * 360, GROUND), fill=(80, 70, 60), width=3)


def p_streetlamp(d, x, t, s=1.0):
    _r(d, (x - 10, GROUND - 660, x + 10, GROUND), (60, 60, 66), 2, 5)
    _r(d, (x - 70, GROUND - 690, x + 70, GROUND - 650), (60, 60, 66), 12, 5)
    _o(d, (x - 40, GROUND - 654, x + 40, GROUND - 600), (255, 236, 150), 5)


def p_plane(d, x, t, s=1.0):
    y = 420 + math.sin(t * 1.5) * 14
    xx = x + (t * 60) % 200 - 100
    d.polygon([(xx - 40, y - 10), (xx - 150, y - 120), (xx - 100, y - 120), (xx + 60, y - 10)], fill=(176, 182, 196), outline=INK, width=O)
    _r(d, (xx - 260, y - 40, xx + 250, y + 40), (244, 246, 250), 40)
    d.polygon([(xx - 250, y - 20), (xx - 320, y - 130), (xx - 260, y - 130), (xx - 180, y - 30)], fill=(214, 70, 60), outline=INK, width=O)
    _poly(d, [(xx - 30, y + 10), (xx - 170, y + 130), (xx - 110, y + 130), (xx + 80, y + 10)], (210, 216, 228))
    for i in range(6):
        d.ellipse((xx - 150 + i * 56, y - 18, xx - 124 + i * 56, y + 8), fill=(120, 190, 240), outline=INK, width=3)


def p_satellite(d, x, t, s=1.0):
    y = 380 + math.sin(t * 1.2) * 16
    for sx in (-1, 1):
        d.rectangle((x + sx * 60 - (130 if sx < 0 else 0), y - 40, x + sx * 60 + (130 if sx > 0 else 0), y + 40), fill=(70, 110, 200), outline=INK, width=O)
        d.line((x + sx * 125, y - 40, x + sx * 125, y + 40), fill=INK, width=4)
    _r(d, (x - 60, y - 60, x + 60, y + 60), (220, 222, 230), 12)
    d.line((x, y + 60, x, y + 110), fill=INK, width=8)
    d.chord((x - 50, y + 90, x + 50, y + 170), 180, 360, fill=(240, 240, 246), outline=INK, width=O)
    if int(t * 2) % 2:
        d.ellipse((x - 10, y - 10, x + 10, y + 10), fill=(250, 80, 70))


def p_ship(d, x, t, s=1.0):
    y = FAR - 30 + math.sin(t * 1.4) * 6
    _r(d, (x - 20, y - 200, x + 20, y - 124), (214, 70, 60), 4)
    _r(d, (x - 110, y - 132, x + 60, y - 56), (240, 240, 244), 6)
    for i in range(4):
        d.ellipse((x - 94 + i * 38, y - 110, x - 74 + i * 38, y - 90), fill=(120, 190, 240), outline=INK, width=3)
    _poly(d, [(x - 200, y - 60), (x + 220, y - 60), (x + 170, y), (x - 160, y)], (60, 74, 110))
    d.line((x - 196, y - 44, x + 214, y - 44), fill=(214, 70, 60), width=8)

def p_door(d, x, t, s=1.0):
    _r(d, (x - 130, GROUND - 500, x + 130, GROUND), (96, 66, 46), 6)
    _r(d, (x - 110, GROUND - 480, x + 110, GROUND), (150, 100, 64), 4, 5)
    for y0, y1 in ((-450, -270), (-240, -40)):
        d.rounded_rectangle((x - 80, GROUND + y0, x + 80, GROUND + y1), 6, outline=(110, 72, 46), width=6)
    _o(d, (x + 64, GROUND - 250, x + 92, GROUND - 222), (240, 200, 90), 4)
    d.polygon([(x - 120, GROUND), (x + 120, GROUND), (x + 190, GROUND + 60), (x - 190, GROUND + 60)], fill=(255, 210, 120, 70))


def p_clock(d, x, t, s=1.0):
    cy = GROUND - 200
    _o(d, (x - 190, cy - 190, x + 190, cy + 190), (250, 250, 246))
    for i in range(12):
        a = i / 12 * math.tau
        d.line((x + math.cos(a) * 150, cy + math.sin(a) * 150, x + math.cos(a) * 172, cy + math.sin(a) * 172), fill=INK, width=8)
    for spd, ln, wd, col in ((0.9, 150, 8, (220, 60, 50)), (0.075, 130, 12, INK), (0.00625, 90, 16, INK)):
        a = t * spd * math.tau - math.pi / 2
        d.line((x, cy, x + math.cos(a) * ln, cy + math.sin(a) * ln), fill=col, width=wd)
    _o(d, (x - 14, cy - 14, x + 14, cy + 14), INK, 2)


def p_pile(d, x, t, s=1.0, col=(244, 244, 248)):
    g = _pop(t, 0.1, 1.6)                                    # Haufen wächst
    hgt, wd = 420 * (0.25 + 0.75 * g), 520 * (0.4 + 0.6 * g)
    d.polygon([(x - wd, GROUND), (x - wd * 0.2, GROUND - hgt * 0.9), (x, GROUND - hgt), (x + wd * 0.25, GROUND - hgt * 0.88), (x + wd, GROUND)],
              fill=_dk(col, 0.18), outline=INK, width=O)
    d.polygon([(x - wd + O * 2, GROUND - O), (x - wd * 0.2, GROUND - hgt * 0.9 + O), (x - 4, GROUND - hgt + O * 1.5), (x + wd * 0.1, GROUND - O)], fill=col)
    rnd = random.Random(4)
    for _ in range(26):
        fx, fy = rnd.uniform(-0.8, 0.8), rnd.uniform(0.05, 0.85)
        if abs(fx) < (1 - fy) * 0.9:
            d.ellipse((x + fx * wd - 5, GROUND - fy * hgt - 5, x + fx * wd + 5, GROUND - fy * hgt + 5), fill=tuple(max(0, c - 40) for c in col))
    for i in range(5):                                       # es rieselt nach
        ph = (t * 0.9 + i / 5) % 1
        d.ellipse((x + (i - 2) * 16 - 6, GROUND - hgt - 260 + ph * 260 - 6, x + (i - 2) * 16 + 6, GROUND - hgt - 260 + ph * 260 + 6), fill=col + (int(255 * (1 - ph * 0.3)),))


def p_sandpile(d, x, t, s=1.0):
    p_pile(d, x, t, s, (236, 196, 120))


def p_trash(d, x, t, s=1.0):
    for i, (dx, dy, col) in enumerate(((-150, 0, (60, 60, 68)), (20, 0, (70, 110, 80)), (160, 0, (60, 60, 68)), (-60, -120, (80, 80, 90)), (90, -130, (60, 60, 68)))):
        _o(d, (x + dx - 100, GROUND + dy - 170, x + dx + 100, GROUND + dy), col)
        d.polygon([(x + dx - 26, GROUND + dy - 160), (x + dx, GROUND + dy - 210), (x + dx + 26, GROUND + dy - 160)], fill=col, outline=INK, width=5)
    for i in range(3):
        ph = (t * 0.5 + i / 3) % 1
        d.arc((x - 120 + i * 110, GROUND - 330 - ph * 120, x - 80 + i * 110, GROUND - 250 - ph * 120), 90, 270, fill=(120, 150, 90, int(220 * (1 - ph))), width=7)


def p_faucet(d, x, t, s=1.0):
    y = GROUND - 520
    _r(d, (x - 200, y - 40, x + 40, y + 30), (170, 176, 188), 14)
    _r(d, (x - 20, y - 40, x + 60, y + 130), (170, 176, 188), 14)
    _r(d, (x - 150, y - 110, x - 110, y - 40), (150, 156, 168), 6, 5)
    _r(d, (x - 190, y - 130, x - 70, y - 100), (214, 70, 60), 10, 5)
    wob = math.sin(t * 20) * 4
    d.rectangle((x + 4 + wob, y + 130, x + 36 + wob, GROUND - 150), fill=(110, 190, 250))
    d.polygon([(x - 120, GROUND - 190), (x + 160, GROUND - 190), (x + 120, GROUND), (x - 80, GROUND)], fill=(210, 236, 250, 150), outline=INK, width=O)
    lvl = 30 + 130 * min(1.0, t / 2.5)
    d.polygon([(x - 84 - lvl * 0.2, GROUND - lvl), (x + 124 + lvl * 0.2, GROUND - lvl), (x + 116, GROUND - 6), (x - 76, GROUND - 6)], fill=(110, 190, 250))


def p_glass(d, x, t, s=1.0):
    d.polygon([(x - 120, GROUND - 330), (x + 120, GROUND - 330), (x + 90, GROUND), (x - 90, GROUND)], fill=(214, 236, 250, 140), outline=INK, width=O)
    lvl = 60 + 220 * min(1.0, t / 2.5)
    k = lvl / 330
    d.polygon([(x - 90 - 30 * k + 6, GROUND - lvl), (x + 90 + 30 * k - 6, GROUND - lvl), (x + 84, GROUND - 6), (x - 84, GROUND - 6)], fill=(110, 190, 250))
    for i in range(4):
        ph = (t * 0.7 + i / 4) % 1
        d.ellipse((x - 50 + i * 30 - 7, GROUND - 20 - ph * (lvl - 30) - 7, x - 50 + i * 30 + 7, GROUND - 20 - ph * (lvl - 30) + 7), outline=(240, 250, 255), width=3)


def p_barrel(d, x, t, s=1.0):
    _r(d, (x - 110, GROUND - 300, x + 110, GROUND), (70, 110, 170), 30)
    for y in (-230, -150, -70):
        d.line((x - 110, GROUND + y, x + 110, GROUND + y), fill=INK, width=6)
    _o(d, (x - 30, GROUND - 216, x + 30, GROUND - 164), (250, 200, 60), 5)


def p_solarpanel(d, x, t, s=1.0):
    d.line((x, GROUND, x, GROUND - 170), fill=INK, width=18)
    d.polygon([(x - 260, GROUND - 120), (x + 200, GROUND - 330), (x + 260, GROUND - 250), (x - 200, GROUND - 40)], fill=(50, 80, 150), outline=INK, width=O)
    for k in range(1, 4):
        d.line((x - 260 + k * 115, GROUND - 120 - k * 52.5, x - 200 + k * 115, GROUND - 40 - k * 52.5), fill=(170, 200, 240), width=4)
    d.line((x - 230, GROUND - 80, x + 230, GROUND - 290), fill=(170, 200, 240), width=4)
    gl = (t * 0.5) % 1
    d.line((x - 240 + gl * 440, GROUND - 110 - gl * 200, x - 200 + gl * 440, GROUND - 60 - gl * 200), fill=(255, 255, 255, 170), width=10)


def p_drone(d, x, t, s=1.0):
    """Drohne: schwebt, Rotoren drehen sich, die Kamera blinkt und tastet mit einem Lichtkegel den Boden ab."""
    y = 600 + math.sin(t * 2.0) * 22
    xx = x + math.sin(t * 0.9) * 70
    sw = math.sin(t * 1.3) * 90
    d.polygon([(xx - 16, y + 58), (xx + 16, y + 58), (xx + sw + 150, GROUND - 30), (xx + sw - 150, GROUND - 30)], fill=(255, 90, 80, 46))
    for sx in (-1, 1):                                                     # Ausleger + Rotoren
        d.line((xx, y - 6, xx + sx * 150, y - 30), fill=INK, width=20)
        d.line((xx, y - 6, xx + sx * 150, y - 30), fill=(70, 76, 90), width=10)
        _r(d, (xx + sx * 150 - 14, y - 60, xx + sx * 150 + 14, y - 22), (50, 54, 64), 6, 5)
        w = 86 * (0.35 + 0.65 * abs(math.sin(t * 34 + sx)))
        d.ellipse((xx + sx * 150 - w, y - 74, xx + sx * 150 + w, y - 58), fill=(210, 216, 228, 190), outline=INK, width=4)
    _r(d, (xx - 74, y - 40, xx + 74, y + 26), (236, 238, 244), 24)         # Rumpf
    _r(d, (xx - 30, y + 20, xx + 30, y + 58), (50, 54, 64), 10, 5)         # Kamera
    _o(d, (xx - 17, y + 30, xx + 17, y + 64), (30, 32, 40), 5)
    d.ellipse((xx - 8, y + 39, xx + 8, y + 55), fill=(120, 190, 250))
    if int(t * 3) % 2:
        d.ellipse((xx + 40, y - 26, xx + 56, y - 10), fill=(240, 60, 50))
    for sx in (-1, 1):                                                     # Landekufen
        d.line((xx + sx * 50, y + 24, xx + sx * 70, y + 70), fill=INK, width=8)


def p_cctv(d, x, t, s=1.0):
    """Überwachungskamera am Mast, schwenkt langsam, rotes Licht blinkt."""
    _r(d, (x - 10, GROUND - 520, x + 10, GROUND), (90, 96, 110), 2, 5)
    d.line((x, GROUND - 500, x + 70, GROUND - 500), fill=INK, width=18)
    a = math.sin(t * 1.2) * 0.25 + 0.35
    cx, cy = x + 70, GROUND - 500
    ex, ey = cx + math.cos(a) * 150, cy + math.sin(a) * 150
    nx, ny = -math.sin(a) * 34, math.cos(a) * 34
    d.polygon([(ex, ey), (ex + math.cos(a) * 520 + nx * 5, ey + math.sin(a) * 520 + ny * 5), (ex + math.cos(a) * 520 - nx * 5, ey + math.sin(a) * 520 - ny * 5)], fill=(255, 90, 80, 40))
    d.polygon([(cx + nx, cy + ny), (ex + nx, ey + ny), (ex - nx, ey - ny), (cx - nx, cy - ny)], fill=(236, 238, 244), outline=INK, width=O)
    d.ellipse((ex - 26, ey - 26, ex + 26, ey + 26), fill=(30, 32, 40), outline=INK, width=5)
    d.ellipse((ex - 10, ey - 10, ex + 10, ey + 10), fill=(120, 190, 250))
    if int(t * 2.5) % 2:
        d.ellipse((cx + nx * 0.2 - 8, cy - ny - 20, cx + nx * 0.2 + 8, cy - ny - 4), fill=(240, 60, 50))



PROPS = {"cloud": p_cloud, "stormcloud": p_stormcloud, "lightning": p_lightning, "crack": p_crack, "flood": p_flood, "smoke": p_smoke, "aurora": p_aurora,
         "eclipse": p_eclipse, "sprout": p_sprout, "tree": p_tree, "rock": p_rock, "box": p_box, "car": p_car, "fire": p_fire, "tv": p_tv, "computer": p_computer,
         "money": p_money, "rocket": p_rocket, "ufo": p_ufo, "meteor": p_meteor, "explosion": p_explosion, "earth": p_earth,
         "sun": p_bigsun, "moon": p_bigmoon, "tornado": p_tornado, "wave": p_wave, "ice": p_ice, "volcano": p_volcano,
         "cart": p_cart, "candle": p_candle, "bus": p_bus, "truck": p_truck, "house": p_house, "trafficlight": p_trafficlight,
         "canister": p_canister, "cans": p_cans, "generator": p_generator, "bike": p_bike, "shelf": p_shelf, "table": p_table,
         "drone": p_drone, "cctv": p_cctv, "door": p_door, "clock": p_clock, "pile": p_pile, "sandpile": p_sandpile, "trash": p_trash, "faucet": p_faucet,
         "glass": p_glass, "barrel": p_barrel, "solarpanel": p_solarpanel,
         "fridge": p_fridge, "tent": p_tent, "streetlamp": p_streetlamp, "plane": p_plane, "satellite": p_satellite, "ship": p_ship}
PROP_ALIASES = {"baum": "tree", "stein": "rock", "kiste": "box", "auto": "car", "feuer": "fire", "fernseher": "tv", "pc": "computer",
                "laptop": "computer", "geld": "money", "rakete": "rocket", "asteroid": "meteor", "erde": "earth", "sonne": "sun",
                "mond": "moon", "wolke": "cloud", "gewitterwolke": "stormcloud", "regenwolke": "stormcloud", "tsunami": "wave", "blitz": "lightning", "erdbeben": "crack", "earthquake": "crack", "riss": "crack",
                "überschwemmung": "flood", "flut": "flood", "rauch": "smoke", "polarlicht": "aurora", "sonnenfinsternis": "eclipse",
                "einkaufswagen": "cart", "kerze": "candle", "kerzen": "candle", "lkw": "truck", "lastwagen": "truck", "haus": "house",
                "ampel": "trafficlight", "kanister": "canister", "benzin": "canister", "wasserkanister": "canister", "konserven": "cans",
                "dosen": "cans", "vorräte": "cans", "essen": "cans", "lebensmittel": "cans", "food": "cans", "notstromaggregat": "generator",
                "aggregat": "generator", "fahrrad": "bike", "regal": "shelf", "tisch": "table", "kühlschrank": "fridge", "zelt": "tent",
                "laterne": "streetlamp", "straßenlaterne": "streetlamp", "flugzeug": "plane", "satellit": "satellite", "schiff": "ship",
                "boot": "ship", "paket": "box", "karton": "box", "geldstapel": "money", "bildschirm": "tv", "lagerfeuer": "fire",
                "drohne": "drone", "drohnen": "drone", "quadcopter": "drone", "kamera": "cctv", "überwachungskamera": "cctv", "camera": "cctv",
                "tür": "door", "uhr": "clock", "wanduhr": "clock", "haufen": "pile", "zucker": "pile", "salz": "pile", "zuckerberg": "pile",
                "schneehaufen": "pile", "sandhaufen": "sandpile", "sand": "sandpile", "müll": "trash", "müllberg": "trash", "garbage": "trash",
                "wasserhahn": "faucet", "tap": "faucet", "hahn": "faucet", "gebäude": "house", "möbel": "shelf", "aktie": "money", "aktien": "money", "wasserstrom": "faucet", "wasserströme": "faucet", "wasserstrahl": "faucet", "glas": "glass", "wasserglas": "glass", "getränk": "glass",
                "fass": "barrel", "tonne": "barrel", "ölfass": "barrel", "solar": "solarpanel", "solaranlage": "solarpanel",
                "solarzelle": "solarpanel", "pflanze": "sprout", "plant": "sprout", "comet": "meteor", "komet": "meteor", "welle": "wave", "eisberg": "ice", "vulkan": "volcano", "bigsun": "sun"}
FRONT = ("wave", "flood", "eclipse")
BEHIND = ("sun", "moon", "earth", "cloud", "stormcloud", "aurora")      # stehen am Himmel hinter Häusern, Bergen und Bäumen
SKY = ("drone", "earth", "sun", "moon", "ufo", "meteor", "aurora", "eclipse", "lightning", "cloud", "stormcloud", "plane", "satellite")     # werden vor den Figuren gezeichnet


# Echte Größe (Höhe in Metern) und Tiefe (Fußlinie im Bild) – daraus ergibt sich der Maßstab passend zu den Menschen.
# Was hier fehlt (Naturereignisse, Himmelskörper), wird als Schaubild frei gezeichnet.
SIZES = {"car": (1.5, 1150), "bus": (3.0, 1100), "truck": (3.3, 1100), "house": (7.5, 1010), "tree": (7.5, 1130), "rock": (0.8, 1262),
         "box": (0.5, 1262), "fire": (1.1, 1250), "tv": (1.2, 1245), "computer": (1.3, 1245), "money": (0.45, 1262), "sprout": (0.5, 1262),
         "cart": (1.0, 1262), "candle": (0.9, 1262), "trafficlight": (3.4, 1225), "canister": (0.5, 1262), "cans": (0.5, 1262),
         "generator": (0.8, 1255), "bike": (1.05, 1255), "shelf": (1.9, 1238), "table": (0.78, 1250), "fridge": (1.85, 1238),
         "cctv": (3.6, 1228), "tent": (1.8, 1180), "door": (2.1, 1236), "clock": (0.6, 1262), "pile": (3.2, 1160), "sandpile": (3.2, 1160),
         "trash": (1.6, 1200), "faucet": (1.6, 1255), "glass": (0.36, 1262), "barrel": (0.95, 1255), "solarpanel": (1.8, 1200), "streetlamp": (4.6, 1225), "rocket": (14.0, 1010)}
HELD = {"phone": "phone", "handy": "phone", "smartphone": "phone", "flashlight": "flashlight", "taschenlampe": "flashlight",
        "bag": "bag", "tasche": "bag", "einkaufstüte": "bag", "tüte": "bag", "bottle": "bottle", "flasche": "bottle",
        "wasserflasche": "bottle", "umbrella": "umbrella", "regenschirm": "umbrella", "schild": "sign", "sign": "sign",
        "map": "map", "karte": "map", "radio": "radio"}
_nat = {}


def prop_fit(kind):
    """(Faktor, Fußlinie) für eine Requisite mit echter Größe – oder None für frei gezeichnete Schaubilder."""
    key = PROP_ALIASES.get(str(kind).lower(), str(kind).lower())
    if key not in SIZES or key not in PROPS:
        return None
    if key not in _nat:
        lay = Image.new("RGBA", (W * 2, H), (0, 0, 0, 0))
        PROPS[key](ImageDraw.Draw(lay, "RGBA"), W, 0.37)
        PROPS[key](ImageDraw.Draw(lay, "RGBA"), W, 6.0)        # auch ausgewachsen/ausgefahren messen
        box = lay.getbbox()
        _nat[key] = max(40, GROUND - box[1]) if box else 200
    meters, y = SIZES[key]
    return px(meters, y) / _nat[key], y


_held_sprites = {}
REAL_M = {}            # echte Höhe gelernter Gegenstände (die Anzeige am Boden ist nach unten begrenzt)


def held_key(name):
    """Was eine Figur in die Hand nehmen kann: feste Hand-Gegenstände oder jede kleine Requisite (auch gelernte) bis etwa 1 m."""
    n = str(name or "").lower().strip()
    if n in HELD:
        return HELD[n]
    key = PROP_ALIASES.get(n, n)
    if key in PROPS and key in SIZES and SIZES[key][0] <= 1.0 and key not in SKY:
        return "prop:" + key
    return ""


def _held_sprite(key):
    if key not in _held_sprites:
        lay = Image.new("RGBA", (900, H), (0, 0, 0, 0))
        PROPS[key](ImageDraw.Draw(lay, "RGBA"), 450, 0.0)
        box = lay.getbbox()
        _held_sprites[key] = lay.crop(box) if box else None
    return _held_sprites[key]


def draw_held_prop(layer, key, x, y, facing, t, k=1.0, shake=False):
    """Beliebige kleine Requisite in der Hand; beim Ausschütteln kopfüber, wackelnd, mit herausfallenden Krümeln."""
    spr = _held_sprite(key)
    if spr is None:
        return
    real = REAL_M.get(key) or SIZES.get(key, (0.3, 0))[0]                       # echte Höhe in Metern
    size = max(46.0, min(190.0, real * 290 * 1.5)) * k                         # Mensch ≈ 290 Bildpunkte je Meter; leicht vergrößert, damit man es erkennt
    f = size / max(spr.width, spr.height)
    im = spr.resize((max(2, int(spr.width * f)), max(2, int(spr.height * f))), Image.LANCZOS)
    if facing < 0:
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
    ang = (150 + 22 * math.sin(t * 16)) * (1 if facing > 0 else -1) if shake else 6 * math.sin(t * 2)
    im = im.rotate(ang, resample=Image.BICUBIC, expand=True)
    cx, cy = x + facing * 10 * k, y + (30 * k if shake else -size * 0.3)
    if shake:
        d = ImageDraw.Draw(layer, "RGBA")
        rnd = random.Random(7)
        for i in range(9):                                   # was herausfällt
            ph = (t * 1.6 + rnd.random()) % 1.0
            px_ = cx + (rnd.random() - 0.5) * 70 * k + facing * ph * 20 * k
            py_ = cy + size * 0.45 + ph * 330 * k
            r = (5 + rnd.random() * 6) * k
            d.ellipse((px_ - r, py_ - r, px_ + r, py_ + r), fill=(120, 90, 60, int(255 * (1 - ph))))
    layer.paste(im, (int(cx - im.width / 2), int(cy - im.height / 2)), im)


def draw_held(layer, kind, x, y, facing, t, k=1.0, night=False):
    """Gegenstand in der Hand (x, y = Handpunkt)."""
    d = ImageDraw.Draw(layer, "RGBA")
    f = facing
    if kind == "phone":
        d.rounded_rectangle((x - 20 * k, y - 62 * k, x + 20 * k, y + 8 * k), 7 * k, fill=(30, 32, 40), outline=INK, width=4)
        d.rounded_rectangle((x - 14 * k, y - 54 * k, x + 14 * k, y, ), 4 * k, fill=(150, 210, 255))
        if night:
            d.ellipse((x - 90 * k, y - 120 * k, x + 90 * k, y + 60 * k), fill=(150, 210, 255, 40))
    elif kind == "flashlight":
        tip = (x + f * 64 * k, y - 10 * k)
        d.polygon([tip, (x + f * 620 * k, y - 190 * k), (x + f * 620 * k, y + 150 * k)], fill=(255, 240, 170, 90 if night else 50))
        d.line((x - f * 14 * k, y, tip[0], tip[1]), fill=INK, width=int(30 * k))
        d.line((x - f * 10 * k, y, tip[0] - f * 4 * k, tip[1]), fill=(90, 96, 110), width=int(18 * k))
        d.ellipse((tip[0] - 12 * k, tip[1] - 20 * k, tip[0] + 12 * k, tip[1] + 20 * k), fill=(255, 244, 190), outline=INK, width=4)
    elif kind == "bag":
        d.arc((x - 30 * k, y - 10 * k, x + 30 * k, y + 50 * k), 180, 360, fill=INK, width=max(3, int(9 * k)))
        _r(d, (x - 54 * k, y + 14 * k, x + 54 * k, y + 130 * k), (214, 170, 110), 8 * k, 5)
        d.line((x - 54 * k, y + 34 * k, x + 54 * k, y + 34 * k), fill=(176, 134, 84), width=max(2, int(5 * k)))      # Falz
        for sx in (-1, 1):                                                                                          # Gemüse schaut heraus
            d.ellipse((x + sx * 24 * k - 16 * k, y - 4 * k, x + sx * 24 * k + 16 * k, y + 26 * k), fill=(110, 186, 96) if sx < 0 else (232, 120, 60), outline=INK, width=4)
    elif kind == "bottle":
        _r(d, (x - 18 * k, y - 70 * k, x + 18 * k, y + 30 * k), (130, 200, 250), 8 * k, 4)
        d.rectangle((x - 17 * k, y - 34 * k, x + 17 * k, y - 10 * k), fill=(250, 250, 246))
        d.rectangle((x - 9 * k, y - 92 * k, x + 9 * k, y - 70 * k), fill=(60, 110, 200), outline=INK, width=3)
    elif kind == "umbrella":
        d.line((x, y + 20 * k, x, y - 270 * k), fill=INK, width=max(3, int(8 * k)))
        d.arc((x - 30 * k, y + 4 * k, x, y + 40 * k), 0, 180, fill=INK, width=max(3, int(8 * k)))                   # Griff
        cy, r = y - 270 * k, 170 * k
        pts = [(x + math.cos(math.radians(a)) * r, cy + math.sin(math.radians(a)) * r * 0.8) for a in range(180, 361, 10)]
        sc = [(x + r - i * r / 3, cy + (10 * k if i % 2 else 0)) for i in range(7)]                                  # gewellter Saum
        d.polygon(pts + sc[1:-1], fill=(170, 50, 46), outline=INK, width=O)
        d.polygon([(x + (px_ - x) * 0.94 - 8 * k, cy + (py_ - cy) * 0.94) for px_, py_ in pts[:12]] + [(x - 10 * k, cy)], fill=(222, 74, 62))
        for a in (-0.5, 0.0, 0.5):                                                                                  # Speichen
            d.line((x, cy - r * 0.8, x + a * r * 1.2, cy + 4 * k), fill=(140, 40, 40), width=max(2, int(4 * k)))
        d.ellipse((x - 8 * k, cy - r * 0.8 - 14 * k, x + 8 * k, cy - r * 0.8 + 2 * k), fill=INK)
    elif kind == "sign":
        bx, top = x + f * 50 * k, y - 470 * k                                                                    # über dem Kopf, nicht davor
        d.line((x, y + 20 * k, bx, top + 150 * k), fill=INK, width=max(3, int(20 * k)))
        d.line((x, y + 20 * k, bx, top + 150 * k), fill=(150, 100, 64), width=max(2, int(11 * k)))
        _r(d, (bx - 110 * k, top, bx + 110 * k, top + 150 * k), (250, 248, 238), 8 * k)
        d.line((bx - 70 * k, top + 50 * k, bx + 70 * k, top + 50 * k), fill=INK, width=max(2, int(8 * k)))
        d.line((bx - 70 * k, top + 95 * k, bx + 30 * k, top + 95 * k), fill=INK, width=max(2, int(8 * k)))
    elif kind == "map":
        d.polygon([(x - 70 * k, y - 60 * k), (x + 70 * k, y - 76 * k), (x + 70 * k, y + 20 * k), (x - 70 * k, y + 36 * k)], fill=(244, 232, 196), outline=INK, width=5)
        d.line((x - 40 * k, y - 20 * k, x, y - 40 * k, x + 40 * k, y - 10 * k), fill=(214, 70, 60), width=int(6 * k), joint="curve")
    elif kind == "radio":
        d.rounded_rectangle((x - 50 * k, y - 50 * k, x + 50 * k, y + 20 * k), 8 * k, fill=(90, 96, 110), outline=INK, width=5)
        d.ellipse((x - 36 * k, y - 36 * k, x + 4 * k, y + 4 * k), fill=(40, 40, 46))
        d.line((x + 30 * k, y - 50 * k, x + 60 * k, y - 130 * k), fill=INK, width=int(6 * k))
        for i in range(2):
            ph = (t * 1.2 + i / 2) % 1
            r = (30 + ph * 70) * k
            d.arc((x + 60 * k - r, y - 130 * k - r, x + 60 * k + r, y - 130 * k + r), 200, 320, fill=(255, 255, 255, int(230 * (1 - ph))), width=5)


def draw_prop(layer, kind, x, t):
    kind = PROP_ALIASES.get(str(kind).lower(), str(kind).lower())
    fn = PROPS.get(kind)
    if fn:
        fn(ImageDraw.Draw(layer, "RGBA"), x, t)


# ------------------------------------------------------------------ Gefühls-Symbole über dem Kopf

def draw_bubble(layer, text, x, y, t, sc=1.0):
    """Kleine Sprechblase über dem Kopf (x = Kopfmitte, y = Oberkante Kopf) für ein, zwei kurze Wörter."""
    from ..overlays import font
    k = _pop(t, 0.2)
    text = str(text or "").strip().upper()[:16]
    if k <= 0 or not text:
        return
    d = ImageDraw.Draw(layer, "RGBA")
    s = max(0.6, min(1.3, sc)) * min(1.0, k)
    f = font(max(18, int(58 * s)), "ExtraBold")
    w = d.textlength(text, font=f)
    bw, bh = w + 56 * s, f.size + 40 * s
    cx = min(W - 30 - bw / 2, max(30 + bw / 2, x + 70 * s))
    top = max(250, y - 70 * s - bh) + math.sin(t * 4) * 4
    d.polygon([(x + 6 * s, y - 20 * s), (cx - 26 * s, top + bh - 6), (cx + 14 * s, top + bh - 6)], fill=(250, 248, 244), outline=INK)
    d.rounded_rectangle((cx - bw / 2, top, cx + bw / 2, top + bh), int(26 * s), fill=(250, 248, 244), outline=INK, width=max(3, int(6 * s)))
    d.polygon([(x + 10 * s, y - 30 * s), (cx - 20 * s, top + bh - 8), (cx + 8 * s, top + bh - 8)], fill=(250, 248, 244))
    d.text((cx - w / 2, top + 16 * s), text, font=f, fill=INK)


def draw_emote(layer, kind, x, y, t, sc=1.0):
    """Symbol mittig über dem Kopf (x = Kopfmitte, y = Oberkante Kopf); sc = Maßstab der Figur."""
    k = _pop(t, 0.15)
    if k <= 0:
        return
    d = ImageDraw.Draw(layer, "RGBA")
    kind = str(kind).lower().strip()
    s = k * max(0.35, sc) * 0.8                             # etwas kleiner: die Zeichen sollen die Figur nicht übertönen
    bob = math.sin(t * 5) * 6 * s
    cx, cy = x, y - 84 * s + bob
    w = max(3, int(O * min(1.0, s)))
    if kind in ("!", "alarm", "exclaim"):
        _r(d, (cx - 16 * s, cy - 110 * s, cx + 16 * s, cy - 24 * s), (240, 70, 60), 10 * s, w)
        _o(d, (cx - 18 * s, cy - 12 * s, cx + 18 * s, cy + 24 * s), (240, 70, 60), w)
    elif kind in ("?", "question"):
        d.arc((cx - 40 * s, cy - 110 * s, cx + 40 * s, cy - 30 * s), 180, 90, fill=INK, width=int(30 * s))
        d.arc((cx - 40 * s, cy - 110 * s, cx + 40 * s, cy - 30 * s), 180, 90, fill=(80, 150, 250), width=int(18 * s))
        d.line((cx, cy - 34 * s, cx, cy - 18 * s), fill=INK, width=int(30 * s))
        d.line((cx, cy - 36 * s, cx, cy - 22 * s), fill=(80, 150, 250), width=int(18 * s))
        _o(d, (cx - 16 * s, cy - 6 * s, cx + 16 * s, cy + 26 * s), (80, 150, 250), w)
    elif kind in ("heart", "love", "herz"):
        r = 34 * s * (1 + 0.1 * math.sin(t * 8))
        for dx in (-r * 0.5, r * 0.5):
            d.ellipse((cx + dx - r * 0.62, cy - 50 * s - r * 0.62, cx + dx + r * 0.62, cy - 50 * s + r * 0.62), fill=(240, 70, 100))
        d.polygon([(cx - r * 1.06, cy - 40 * s), (cx + r * 1.06, cy - 40 * s), (cx, cy - 50 * s + r * 1.3)], fill=(240, 70, 100))
    elif kind in ("idea", "idee", "bulb"):
        _o(d, (cx - 40 * s, cy - 110 * s, cx + 40 * s, cy - 30 * s), (255, 226, 90), w)
        _r(d, (cx - 20 * s, cy - 34 * s, cx + 20 * s, cy - 6 * s), (150, 156, 166), 4, max(3, int(5 * s)))
        for a in (-150, -90, -30):
            d.line((cx + math.cos(math.radians(a)) * 56 * s, cy - 70 * s + math.sin(math.radians(a)) * 56 * s,
                    cx + math.cos(math.radians(a)) * 84 * s, cy - 70 * s + math.sin(math.radians(a)) * 84 * s), fill=(255, 226, 90), width=max(3, int(8 * s)))
    elif kind in ("sweat", "schweiß"):                     # Schweißtropfen läuft an der Schläfe herunter
        ph = (t * 1.2) % 1
        sx, sy = x + 86 * s, y + (40 + ph * 50) * s
        d.polygon([(sx, sy - 34 * s), (sx - 17 * s, sy), (sx + 17 * s, sy)], fill=(130, 200, 250), outline=INK, width=max(2, int(4 * s)))
        d.chord((sx - 17 * s, sy - 17 * s, sx + 17 * s, sy + 17 * s), 0, 180, fill=(130, 200, 250), outline=INK, width=max(2, int(4 * s)))
    elif kind in ("anger", "wut"):
        for a in (0, 90):
            dx, dy = math.cos(math.radians(a + 45)) * 40 * s, math.sin(math.radians(a + 45)) * 40 * s
            d.line((cx - dx, cy - 50 * s - dy, cx + dx, cy - 50 * s + dy), fill=(230, 60, 50), width=int(16 * s))
    elif kind in ("music", "musik"):
        for i in range(2):
            ph = (t * 0.8 + i * 0.5) % 1
            nx, ny = cx - 25 * s + i * 50 * s + math.sin(t * 4 + i) * 10 * s, cy - ph * 150 * s
            d.ellipse((nx - 16 * s, ny - 12 * s, nx + 16 * s, ny + 12 * s), fill=INK)
            d.line((nx + 14 * s, ny, nx + 14 * s, ny - 60 * s), fill=INK, width=max(3, int(7 * s)))


# ------------------------------------------------------------------ Wetter und Hintergrund-Leben

_rnd = random.Random(42)
_DROPS = [(_rnd.random(), _rnd.random(), _rnd.random()) for _ in range(140)]


def draw_weather(layer, kind, t):
    d = ImageDraw.Draw(layer, "RGBA")
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
    elif kind in ("ash", "asche"):
        d.rectangle((0, 0, W, H), fill=(120, 40, 20, 46))
        for a, b, c in _DROPS[:70]:
            x = (a * W + math.sin(t * 0.9 + c * 9) * 60) % W
            y = (b * H + t * (110 + c * 90)) % H
            d.ellipse((x - 5, y - 4, x + 5, y + 4), fill=(60, 56, 56, 230))
    elif kind in ("quake", "erdbeben"):
        for a, b, c in _DROPS[:24]:
            y = (b * 600 + t * (500 + c * 400)) % 700
            x = a * W
            d.rectangle((x - 6, GROUND - 700 + y, x + 6, GROUND - 688 + y), fill=(120, 104, 96, 220))
    elif kind in ("steam", "dampf"):                       # Dampfschwaden steigen auf (kochendes Wasser, Verdampfen)
        for i, (a, b, c) in enumerate(_DROPS[:26]):
            ph = (t * (0.22 + c * 0.2) + b) % 1
            x = a * W + math.sin(t * 1.3 + i) * 40
            y = GROUND + 120 - ph * 900
            r = 34 + ph * 70 + c * 20
            d.ellipse((x - r, y - r, x + r, y + r), fill=(250, 250, 252, int(170 * (1 - ph))))
    elif kind in ("heat", "hitze"):
        d.rectangle((0, 0, W, H), fill=(255, 120, 40, 34 + int(14 * math.sin(t * 2))))
    elif kind in ("dark", "dunkel", "blackout"):
        d.rectangle((0, 0, W, H), fill=(4, 6, 20, 110))


def _car(d, x, y, col, facing, t, moving=True):
    """Auto in richtiger Größe für die Tiefe y (rund 1,45 m hoch, etwas niedriger als ein Mensch)."""
    u = px(1.45, y) / 120
    b = math.sin(t * 9 + x * 0.01) * 2 * u if moving else 0
    w = max(3, int(3.2 * u))
    d.ellipse((x - 130 * u, y - 14 * u, x + 130 * u, y + 12 * u), fill=(0, 0, 0, 60))
    d.rounded_rectangle((x - 125 * u, y - 76 * u + b, x + 125 * u, y - 18 * u + b), 18 * u, fill=col, outline=INK, width=w)
    d.rounded_rectangle((x - 72 * u, y - 120 * u + b, x + 62 * u, y - 68 * u + b), 20 * u, fill=col, outline=INK, width=w)
    d.rounded_rectangle((x - 60 * u, y - 110 * u + b, x - 8 * u, y - 76 * u + b), 8 * u, fill=(170, 220, 250))
    d.rounded_rectangle((x + 2 * u, y - 110 * u + b, x + 50 * u, y - 76 * u + b), 8 * u, fill=(170, 220, 250))
    for wx in (-74, 74):
        d.ellipse((x + wx * u - 25 * u, y - 46 * u, x + wx * u + 25 * u, y + 4 * u), fill=(40, 40, 46), outline=INK, width=w)
        d.ellipse((x + wx * u - 9 * u, y - 30 * u, x + wx * u + 9 * u, y - 12 * u), fill=(190, 190, 196))
    d.ellipse((x + facing * 116 * u - 9 * u, y - 60 * u + b, x + facing * 116 * u + 9 * u, y - 40 * u + b), fill=(255, 236, 150))


LANES = ((1108, 1), (1192, -1))       # Fahrspuren: Fußlinie und Fahrtrichtung
PARK_Y = 1078                         # hier stehen Autos, wenn nichts mehr fährt


def has_road(spec, place=""):
    return isinstance(spec, dict) and spec.get("ground") == "road" and "ruins" not in (spec.get("elements") or [])


def draw_landscape_motion(layer, spec, place, night, t, traffic=True, parked=True):
    """Bewegung passend zur Landschaft: fließendes Wasser, Wellen, fahrende Autos, Rauch, wehendes Korn, Staub, Glut."""
    d = ImageDraw.Draw(layer, "RGBA")
    base = FAR
    els = list((spec or {}).get("elements") or []) if isinstance(spec, dict) else []
    ground = str((spec or {}).get("ground") or "") if isinstance(spec, dict) else ""
    if "river" in els:                                           # Lichtreflexe treiben den Fluss entlang
        for i in range(9):
            ph = (t * 0.16 + i / 9) % 1
            x = -100 + ph * (W + 200)
            y = 995 + (i * 37) % 86
            d.arc((x, y, x + 90 + (i % 3) * 30, y + 22), 180, 360, fill=(226, 244, 255, 230), width=5)
    if "sea" in els or ground == "water":                         # Wellen laufen
        y0, y1 = (base - 200, base - 16) if "sea" in els else (base + 40, H - 240)
        for y in range(int(y0), int(y1), 46):
            sh = (t * 60 + y * 3) % 160
            for x in range(-160, W + 160, 160):
                d.arc((x + sh, y + math.sin(t * 2 + y) * 4, x + sh + 90, y + 30 + math.sin(t * 2 + y) * 4), 180, 360, fill=(226, 244, 255, 235), width=5)
    if "lake" in els:
        for i in range(4):
            ph = (t * 0.5 + i / 4) % 1
            cx, cy = 300 + i * 150, 1030 + (i % 2) * 50
            d.ellipse((cx - 24 - ph * 60, cy - 6 - ph * 12, cx + 24 + ph * 60, cy + 6 + ph * 12), outline=(226, 244, 255, int(230 * (1 - ph))), width=4)
    if "fields" in els:                                           # Wind streicht durchs Korn
        for i in range(5):
            ph = (t * 0.28 + i / 5) % 1
            x = -200 + ph * (W + 400)
            y = base + 60 + i * 60
            d.arc((x, y, x + 240, y + 40), 190, 340, fill=(250, 236, 170, 200), width=6)
    if "factory" in els and traffic:                              # steht alles still, rauchen auch die Schlote nicht
        for cx in (820, 940):
            for k in range(5):
                ph = (t * 0.3 + k / 5) % 1
                r = 40 + ph * 110
                g = int(150 - ph * 50)
                d.ellipse((cx + ph * 220 - r, base - 660 - ph * 520 - r, cx + ph * 220 + r, base - 660 - ph * 520 + r), fill=(g, g, g + 6, int(220 * (1 - ph))))
    if "powerplant" in els and traffic:                           # Dampf aus den Kühltürmen
        for cx, top in ((260, 400), (620, 320)):
            for k in range(5):
                ph = (t * 0.22 + k / 5) % 1
                r = 60 + ph * 120
                d.ellipse((cx + ph * 160 - r, top - ph * 360 - r, cx + ph * 160 + r, top - ph * 360 + r), fill=(250, 250, 252, int(210 * (1 - ph))))
    if "windturbines" in els:                                     # Rotoren drehen sich
        for x, y in ((220, 940), (700, 925), (960, 960)):
            h = 380 + (x % 3) * 40
            for k in range(3):
                a = t * (1.6 if traffic else 0.0) + k * 2.094 + x
                ex, ey = x + math.cos(a) * 150, y - h + math.sin(a) * 150
                d.line((x, y - h, ex, ey), fill=INK, width=18)
                d.line((x, y - h, ex, ey), fill=(244, 246, 250), width=10)
            d.ellipse((x - 14, y - h - 14, x + 14, y - h + 14), fill=(200, 204, 212), outline=INK, width=4)
    if has_road(spec):
        cols = ((214, 80, 70), (70, 130, 210), (240, 196, 70), (240, 240, 244), (90, 160, 120))
        if traffic:                                               # Autos fahren durch, hinten langsamer als vorn
            for i, (y, direction) in enumerate(LANES):
                period = 5.2 + i * 1.7
                n = int((t + i * 2.3) / period)
                ph = ((t + i * 2.3) % period) / 2.6
                if ph < 1:
                    x = -400 + ph * (W + 800)
                    _car(d, x if direction > 0 else W - x, y, cols[(n + i * 2) % 5], direction, t)
        elif parked:                                              # alles steht (schwebt alles, steht auch am Straßenrand nichts mehr)
            for i, x in enumerate((210, 760)):
                _car(d, x, PARK_Y, cols[i * 2], 1 if i else -1, 0, False)
    if "ruins" in els or ground == "lava":                        # Glut und Rauch steigen auf
        for i, (a, b, c) in enumerate(_DROPS[:26]):
            ph = (t * (0.18 + c * 0.2) + b) % 1
            x = a * W + math.sin(t * 1.5 + i) * 30
            y = base + 300 - ph * 1100
            r = 4 + c * 5
            d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 150 + int(80 * c), 60, int(240 * (1 - ph))))
    if ground == "dry" or "dunes" in els:                         # Staub weht, Steppenläufer rollt
        for i, (a, b, c) in enumerate(_DROPS[:10]):
            x = (a * (W + 600) + t * (300 + c * 300)) % (W + 600) - 300
            y = base - 100 + b * 500
            d.arc((x, y, x + 300, y + 40), 190, 330, fill=(240, 220, 170, 150), width=7)
        tx = (t * 260) % (W + 300) - 150
        ty = 1150 - abs(math.sin(t * 5)) * 40
        d.ellipse((tx - 34, ty - 34, tx + 34, ty + 34), outline=(120, 90, 60, 255), width=6)
        d.arc((tx - 24, ty - 24, tx + 24, ty + 24), int(t * 300) % 360, int(t * 300) % 360 + 200, fill=(120, 90, 60, 255), width=5)
    if "forest" in els or "trees" in els:                         # Blätter fallen
        for i, (a, b, c) in enumerate(_DROPS[:9]):
            ph = (t * (0.12 + c * 0.1) + b) % 1
            x = a * W + math.sin(t * 2 + i * 1.7) * 50
            y = 300 + ph * 900
            d.ellipse((x - 10, y - 6, x + 10, y + 6), fill=(110, 180, 90, int(255 * (1 - ph * 0.6))))
    if "glacier" in els or ground in ("snow", "ice"):
        for i, (a, b, c) in enumerate(_DROPS[:40]):
            x = (a * W + math.sin(t * 1.2 + c * 9) * 30) % W
            y = (b * H + t * (90 + c * 80)) % H
            d.ellipse((x - 4, y - 4, x + 4, y + 4), fill=(255, 255, 255, 220))
    if "camp" in els:                                             # Lagerfeuer zwischen den Zelten
        p_fire(d, 560, t, 0.5)


MOODS = {"panic": (255, 60, 40), "tense": (255, 120, 40), "scary": (10, 10, 40), "sad": (40, 70, 130), "happy": (255, 220, 120),
         "calm": None}


def draw_burst(layer, x, y, k, sc=1.0):
    """Schreck-/Aufprall-Strahlen: kurze Keile, die vom Punkt nach außen schießen (k = 0..1 Fortschritt)."""
    d = ImageDraw.Draw(layer, "RGBA")
    a = int(255 * (1 - k) ** 0.7)
    for i in range(12):
        ang = i * math.pi / 6 + 0.26
        r0, r1 = (150 + 150 * k) * sc, (230 + 260 * k) * sc
        wdt = (0.10 if i % 2 else 0.06)
        pts = [(x + math.cos(ang - wdt) * r0, y + math.sin(ang - wdt) * r0 * 0.9), (x + math.cos(ang) * r1, y + math.sin(ang) * r1 * 0.9),
               (x + math.cos(ang + wdt) * r0, y + math.sin(ang + wdt) * r0 * 0.9)]
        d.polygon(pts, fill=(255, 255, 255, a) if i % 2 else (255, 214, 80, a))


def draw_mood(layer, mood, t):
    """Stimmung über das ganze Bild: farbiger Schleier/Rand, bei Panik pulsierend."""
    col = MOODS.get(str(mood or "").lower())
    if not col:
        return
    d = ImageDraw.Draw(layer, "RGBA")
    m = str(mood).lower()
    if m == "panic":
        a = 26 + int(22 * (0.5 + 0.5 * math.sin(t * 9)))
        d.rectangle((0, 0, W, H), fill=(*col, a))
        for i in range(10):                                        # Rand pulsiert rot
            d.rectangle((i * 6, i * 6, W - i * 6, H - i * 6), outline=(*col, int((10 - i) * (5 + 4 * math.sin(t * 9)))), width=6)
    elif m == "tense":
        d.rectangle((0, 0, W, H), fill=(*col, 22))
    elif m == "scary":
        d.rectangle((0, 0, W, H), fill=(*col, 90))
        for i in range(12):
            d.rectangle((i * 10, i * 10, W - i * 10, H - i * 10), outline=(0, 0, 0, (12 - i) * 6), width=10)
    elif m == "sad":
        d.rectangle((0, 0, W, H), fill=(*col, 56))
    elif m == "happy":
        d.rectangle((0, 0, W, H), fill=(*col, 26))
        for i, (a, b, c) in enumerate(_DROPS[:30]):               # Konfetti
            x = (a * W + math.sin(t * 2 + i) * 40) % W
            y = (b * H + t * (240 + c * 200)) % H
            colr = ((250, 90, 90), (90, 170, 250), (250, 210, 80), (120, 220, 140))[i % 4]
            d.rectangle((x - 7, y - 4, x + 7, y + 4), fill=(*colr, 235))


_mp = {}


def _map_pts(place):
    if place not in _mp:
        from . import places as pl
        rnd = random.Random(9)
        m = Image.new("L", (W, H), 0)
        if place == "germany":
            ImageDraw.Draw(m).polygon([(190 + a * 700, 380 + b * 900) for a, b in pl.GERMANY], fill=255)
        else:
            ImageDraw.Draw(m).ellipse((540 - 400, 820 - 400, 540 + 400, 820 + 400), fill=255)
        pts = []
        while len(pts) < 46:
            x, y = rnd.randint(150, 930), rnd.randint(400, 1280)
            if m.getpixel((x, y)) and all((x - a) ** 2 + (y - b) ** 2 > 50 ** 2 for a, b in pts):
                pts.append((x, y))
        _mp[place] = pts
    return _mp[place]


def draw_ambient(layer, place, night, t):
    """Kleine Bewegung im Hintergrund, damit kein Bild stillsteht."""
    d = ImageDraw.Draw(layer, "RGBA")
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
    if place == "kitchen":                                        # Dampf über dem Topf
        for k in range(4):
            ph = (t * 0.5 + k / 4) % 1
            r = 16 + ph * 30
            d.ellipse((630 + math.sin(t * 2 + k) * 14 - r, 870 - ph * 200 - r, 630 + math.sin(t * 2 + k) * 14 + r, 870 - ph * 200 + r), fill=(255, 255, 255, int(170 * (1 - ph))))
    if place == "office" and not night:                           # Text läuft über den Bildschirm
        for i in range(4):
            wdt = 50 + (int(t * 5 + i * 2) % 5) * 34
            d.rectangle((656, 836 + i * 30, 656 + wdt, 848 + i * 30), fill=(250, 250, 255, 255))
    if place == "serverroom":                                     # Lämpchen der Server flackern
        from .places import SERVER_RACKS, SERVER_ROWS
        for i, (x0, _x1) in enumerate(SERVER_RACKS):
            for j, y in enumerate(SERVER_ROWS):
                a, b = _DROPS[(i * 13 + j * 7) % 140][0], _DROPS[(i * 5 + j * 11) % 140][1]
                if math.sin(t * (5 + a * 9) + b * 40) > 0.2:
                    d.ellipse((x0 + 30, y + 16, x0 + 48, y + 34), fill=(24, 60, 40, 255))
                if math.sin(t * (3 + b * 7) + a * 40) > 0.55:
                    d.ellipse((x0 + 56, y + 16, x0 + 74, y + 34), fill=(250, 200, 80, 255))
    if place == "station":                                        # Anzeige blinkt
        if int(t * 1.5) % 2:
            d.rectangle((700, 478, 800, 500), fill=(30, 40, 70, 255))
    if place in ("germany", "worldmap"):                          # Punkte leuchten nach und nach auf der Karte auf
        cols = ((250, 200, 70), (240, 110, 90), (120, 200, 250), (140, 220, 140))
        for i, (x, y) in enumerate(_map_pts(place)):
            k = _pop(t, 0.2 + i * 0.05, 0.3)
            if k <= 0:
                continue
            pul = 1 + 0.25 * math.sin(t * 3 + i)
            r = 9 * k
            d.ellipse((x - r * 2.4 * pul, y - r * 2.4 * pul, x + r * 2.4 * pul, y + r * 2.4 * pul), fill=cols[i % 4] + (50,))
            d.ellipse((x - r, y - r, x + r, y + r), fill=cols[i % 4] + (255,))
        return
    if place not in OUTDOOR and place not in ("space", "underwater"):   # Staub tanzt im Licht – nichts steht ganz still
        for i, (a, b, c) in enumerate(_DROPS[40:54]):
            x = (a * W + math.sin(t * 0.7 + i) * 40 + t * 12 * (c - 0.5)) % W
            y = (b * 1100 + 200 - t * (8 + c * 14)) % 1200 + 100
            r = 3 + c * 4
            d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 250, 230, int(70 + 60 * math.sin(t * 1.3 + i) ** 2)))
    if place in ("basement", "cave"):
        fl = int(18 + 16 * math.sin(t * 9) * math.sin(t * 2.3))    # flackerndes Licht
        d.rectangle((0, 0, W, H), fill=(0, 0, 0, max(0, fl)))


# ------------------------------------------------------------------ Tiere und Wesen

def _leaf(x0, y0, x1, y1, w):
    """Schmale Blatt-/Flügelform von (x0, y0) nach (x1, y1) mit größter Breite w."""
    dx, dy = x1 - x0, y1 - y0
    ln = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / ln, dx / ln
    pts = []
    for i in range(9):
        u = i / 8
        pts.append((x0 + dx * u + nx * w * math.sin(u * math.pi), y0 + dy * u + ny * w * math.sin(u * math.pi)))
    for i in range(7, 0, -1):
        u = i / 8
        pts.append((x0 + dx * u - nx * w * 0.6 * math.sin(u * math.pi), y0 + dy * u - ny * w * 0.6 * math.sin(u * math.pi)))
    return pts


def creature(kind, t, facing=1, mouth=0.0, mood="", scale=1.0):
    """Zeichnet ein Wesen; gibt (Bild, Fußpunkt-x, Fußpunkt-y, schwebt) zurück.
    Stil wie die Figuren (rig.py): kräftiger Umriss, jede Farbfläche mit dunklerer Schattenseite (hinten/unten),
    Augen mit Glanzpunkten, Wangenrot. Gezeichnet wird nach rechts blickend in Wesen-Koordinaten (x nach vorn,
    y nach unten, Boden bei y = 0) und bei facing = -1 gespiegelt."""
    from .rig import _eye, _stroke, _dark, _light
    S = 2
    k = S * scale
    im = Image.new("RGBA", (int(620 * k), int(620 * k)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im, "RGBA")
    cx, gy = im.width / 2, im.height - 30 * k
    f = 1 if facing >= 0 else -1
    o = max(2, int(6 * k))
    bob = math.sin(t * 4) * 8
    blink = (t % 3.1) < 0.12
    wide = mood in ("shocked", "scared")
    eyekind = "closed" if blink and not wide else "wide" if wide else "sad" if mood == "sad" else "angry" if mood == "angry" else ""

    def P(x, y):
        return cx + x * k * f, gy + y * k

    def B(x0, y0, x1, y1):
        a, b = cx + x0 * k * f, cx + x1 * k * f
        return min(a, b), gy + y0 * k, max(a, b), gy + y1 * k

    def ell(x0, y0, x1, y1, col, shade=0.14, line=True):
        bx = B(x0, y0, x1, y1)
        if line:
            d.ellipse((bx[0] - o, bx[1] - o, bx[2] + o, bx[3] + o), fill=INK)
        if shade:
            d.ellipse(bx, fill=_dark(col, 0.24))
            d.ellipse(B(x0 + (x1 - x0) * shade, y0, x1, y1 - (y1 - y0) * shade * 0.7), fill=col)
        else:
            d.ellipse(bx, fill=col)

    def rr(x0, y0, x1, y1, r, col, shade=0.14, line=True):
        bx = B(x0, y0, x1, y1)
        if line:
            d.rounded_rectangle((bx[0] - o, bx[1] - o, bx[2] + o, bx[3] + o), r * k + o, fill=INK)
        if shade:
            d.rounded_rectangle(bx, r * k, fill=_dark(col, 0.24))
            d.rounded_rectangle(B(x0 + (x1 - x0) * shade, y0, x1, y1 - (y1 - y0) * shade * 0.7), r * k, fill=col)
        else:
            d.rounded_rectangle(bx, r * k, fill=col)

    def poly(pts, col, shade=0.13, line=True):
        q = [P(x, y) for x, y in pts]
        d.polygon(q, fill=_dark(col, 0.24) if shade else col, outline=INK if line else None, width=o if line else 0)
        if shade:
            mx, my = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
            sz = max(max(p[0] for p in pts) - min(p[0] for p in pts), max(p[1] for p in pts) - min(p[1] for p in pts))
            d.polygon([P(mx + (x - mx) * (1 - shade) + sz * shade * 0.35, my + (y - my) * (1 - shade) - sz * shade * 0.3) for x, y in pts], fill=col)

    def stroke(pts, w, col):
        q = [P(x, y) for x, y in pts]
        _stroke(d, q, w * k + 2 * o, INK)
        _stroke(d, q, w * k, col)

    def eye(x, y, r, kind=None):
        px_, py_ = P(x, y)
        _eye(d, px_, py_, r * k, eyekind if kind is None else kind, 0.6 * f)

    def brow(x, y, r, inner):                       # inner = +1: das innere Ende liegt vorn
        if mood not in ("sad", "angry", "worried", "scared"):
            return
        dy = 8 if mood == "angry" else -8
        d.line((*P(x - r, y - dy * inner), *P(x + r, y + dy * inner)), fill=INK, width=max(2, int(7 * k)))

    def cheek(x, y, r):
        d.ellipse(B(x - r, y - r * 0.6, x + r, y + r * 0.6), fill=(255, 120, 130, 90))

    def mouthf(x, y, w):
        if mouth > 0.1:
            h = 8 + mouth * 16
            d.ellipse((*P(x - w * 0.7, y - h * 0.4)[:1], P(0, y - h * 0.4)[1], *P(x + w * 0.7, 0)[:1], P(0, y + h)[1]) if False else B(x - w * 0.7, y - h * 0.4, x + w * 0.7, y + h),
                      fill=(110, 36, 46), outline=INK, width=max(2, int(4 * k)))
            d.chord(B(x - w * 0.45, y + h * 0.2, x + w * 0.45, y + h * 1.1), 180, 360, fill=(240, 120, 130))
        elif mood in ("sad", "worried"):
            d.arc(B(x - w, y, x + w, y + 22), 205, 335, fill=INK, width=max(2, int(6 * k)))
        elif wide:
            d.ellipse(B(x - w * 0.35, y - 4, x + w * 0.35, y + 14), fill=(110, 36, 46), outline=INK, width=max(2, int(4 * k)))
        else:
            d.arc(B(x - w, y - 18, x + w, y + 6), 25, 155, fill=INK, width=max(2, int(6 * k)))

    def band(x0, y0, x1, y1, a, b, col):            # Querstreifen [a, b] (x) genau in der Ellipse (x0..x1, y0..y1)
        mx, my, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
        xs = [a + (b - a) * i / 8 for i in range(9)]
        hy = [ry * math.sqrt(max(0.0, 1 - ((xx - mx) / rx) ** 2)) for xx in xs]
        poly([(xx, my - h) for xx, h in zip(xs, hy)] + [(xx, my + h) for xx, h in reversed(list(zip(xs, hy)))], col, shade=0, line=False)

    kind = str(kind).lower()
    fly = False
    if kind in ("cat", "katze", "dog", "hund"):
        dog = kind in ("dog", "hund")
        col = (214, 160, 100) if dog else (240, 160, 80)
        wag = math.sin(t * (12 if dog else 3)) * (26 if dog else 14)
        belly = _light(col, 0.55)
        tail = [(-110, -120), (-150, -150), (-165, -205 - wag * 0.5), (-150 + wag, -250)] if not dog else [(-110, -125), (-150, -160), (-170 + wag, -215)]
        stroke(tail, 22, _dark(col, 0.1))
        if not dog:
            stroke(tail[-1:] + [(tail[-1][0] + 2, tail[-1][1] - 4)], 22, _dark(col, 0.35))
        for lx in (-85, 45):                                                       # Beine auf der abgewandten Seite
            rr(lx, -80, lx + 30, 0, 13, _dark(col, 0.18), shade=0)
        ell(-128, -170, 112, -45, col)
        ell(-60, -110, 70, -52, belly, shade=0, line=False)
        if not dog:                                                                # Tigerstreifen auf dem Rücken
            for sx in (-70, -30, 10):
                d.line((*P(sx, -166), *P(sx + 10, -135)), fill=_dark(col, 0.32), width=max(2, int(10 * k)))
        for lx in (-65, 65):
            rr(lx, -80, lx + 32, 0, 13, col, shade=0.25)
            ell(lx - 4, -18, lx + 40, 4, belly, shade=0)
        hx, hy = 92, -218 + bob * 0.5
        if dog:
            ell(hx - 92, hy - 52, hx - 36, hy + 50, (150, 100, 60), shade=0)       # Ohr hinten
        else:
            for ex in (-1, 1):
                ox = hx + ex * 50
                poly([(ox - 34, hy - 52), (ox + ex * 12, hy - 120), (ox + 34, hy - 52)], col if ex > 0 else _dark(col, 0.2), shade=0)
                poly([(ox - 16, hy - 62), (ox + ex * 8, hy - 100), (ox + 16, hy - 62)], (250, 160, 170), shade=0, line=False)
        ell(hx - 88, hy - 82, hx + 88, hy + 78, col)
        if dog:
            ell(hx + 18, hy - 2, hx + 128, hy + 64, belly, shade=0.1)              # Schnauze
            ell(hx + 96, hy + 2, hx + 136, hy + 30, INK, shade=0, line=False)
            d.ellipse(B(hx + 104, hy + 6, hx + 116, hy + 14), fill=(255, 255, 255, 200))
            mouthf(hx + 84, hy + 44, 18)
            ell(hx - 52, hy - 46, hx - 6, hy + 52, (150, 100, 60), shade=0.2)      # Schlappohr vorn
            rr(hx - 70, hy + 66, hx + 50, hy + 86, 9, (214, 70, 60), shade=0)      # Halsband mit Marke
            ell(hx - 4, hy + 78, hx + 20, hy + 102, (250, 206, 80), shade=0)
            eye(hx + 22, hy - 22, 15)
            eye(hx + 70, hy - 22, 15)
            brow(hx + 22, hy - 48, 14, 1)
            brow(hx + 70, hy - 48, 14, -1)
            cheek(hx + 6, hy + 22, 16)
        else:
            ell(hx + 20, hy + 6, hx + 100, hy + 54, belly, shade=0, line=False)
            poly([(hx + 54, hy + 12), (hx + 70, hy + 12), (hx + 62, hy + 24)], (240, 110, 130), shade=0)
            for sy in (-6, 8):                                                     # Schnurrhaare
                d.line((*P(hx + 86, hy + 26), *P(hx + 140, hy + 26 + sy)), fill=INK, width=max(2, int(3 * k)))
                d.line((*P(hx + 36, hy + 26), *P(hx - 18, hy + 26 + sy)), fill=INK, width=max(2, int(3 * k)))
            mouthf(hx + 62, hy + 38, 14)
            eye(hx + 30, hy - 18, 16)
            eye(hx + 86, hy - 18, 16)
            brow(hx + 30, hy - 44, 14, 1)
            brow(hx + 86, hy - 44, 14, -1)
            cheek(hx + 14, hy + 26, 14)
    elif kind in ("spider", "spinne"):
        col = (110, 74, 52)
        by = -150 + bob * 0.4
        for back in (True, False):                                                 # hintere Beine dunkler
            for s in (-1, 1):
                for i in ((3, 1) if back else (2, 0)):
                    a = math.sin(t * 8 + i * 1.5 + s) * 6
                    knee = (s * (95 + i * 26), by - (88 - i * 20) - a)
                    stroke([(s * 40, by), knee, (s * (135 + i * 36), 0)], 14, _dark(col, 0.25) if back else col)
                    ell(knee[0] - 9, knee[1] - 9, knee[0] + 9, knee[1] + 9, _light(col, 0.15), shade=0, line=False)
        ell(-112, by - 96, 112, by + 92, col)
        ell(-62, by - 82, 30, by - 30, _light(col, 0.2), shade=0, line=False)         # Glanz auf dem Rücken
        for s in (-1, 1):                                                          # Kieferklauen
            poly([(s * 14, by + 60), (s * 34, by + 60), (s * 22, by + 92)], (60, 40, 32), shade=0)
        eye(-36, by - 2, 21)
        eye(36, by - 2, 21)
        for s in (-1, 1):                                                          # zwei kleine Nebenaugen
            ell(s * 30 - 8, by - 50, s * 30 + 8, by - 34, INK, shade=0, line=False)
        brow(-36, by - 32, 18, 1)
        brow(36, by - 32, 18, -1)
        cheek(-66, by + 30, 14)
        cheek(66, by + 30, 14)
        mouthf(0, by + 46, 14)
    elif kind in ("ghost", "geist"):
        fly = True
        by = -330 + bob * 2
        d.ellipse(B(-170, by - 170, 170, by + 230), fill=(220, 230, 255, 40))     # Schimmer
        def body(sh):
            pts = [(math.cos(math.radians(a)) * 110 * sh, by + math.sin(math.radians(a)) * 110 * sh) for a in range(180, 361, 15)]
            pts.append((110 * sh, by + 150 * sh))
            for i in range(7, -1, -1):
                xx = -110 * sh + i * 220 * sh / 7
                pts.append((xx, by + (150 + (26 if i % 2 else 0) + math.sin(t * 6 + i) * 8) * sh))
            return pts
        pa = body(1.0)
        d.polygon([P(x, y) for x, y in pa], fill=(198, 204, 232), outline=INK, width=o)
        d.polygon([P(x * 0.86 + 14, by + (y - by) * 0.9 - 6) for x, y in pa], fill=(248, 248, 255))
        for s in (-1, 1):                                                          # Ärmchen
            wv = math.sin(t * 5 + s) * 10
            poly([(s * 104, by + 20), (s * 150, by + 46 + wv), (s * 104, by + 74)], (236, 238, 250), shade=0)
        eye(-34, by - 14, 19)
        eye(42, by - 14, 19)
        brow(-34, by - 44, 16, 1)
        brow(42, by - 44, 16, -1)
        cheek(-62, by + 26, 15)
        cheek(72, by + 26, 15)
        h = 22 + mouth * 22
        d.ellipse(B(-10, by + 34, 26, by + 34 + h), fill=(70, 70, 96), outline=INK, width=max(2, int(4 * k)))
    elif kind in ("alien", "außerirdischer"):
        col = (120, 206, 120)
        for lx in (-38, 18):
            stroke([(lx + 10, -100), (lx + 10, -14)], 24, _dark(col, 0.12) if lx < 0 else col)
            ell(lx - 10, -24, lx + 34, 4, _dark(col, 0.3), shade=0)
        wv = math.sin(t * 3) * 12
        stroke([(-58, -196), (-86, -146), (-80, -100)], 18, _dark(col, 0.18))      # Arm hinten
        rr(-62, -224, 62, -84, 46, col)
        ell(-26, -180, 26, -128, (190, 240, 255), shade=0.2)                       # leuchtender Knopf
        stroke([(52, -196), (92, -160 - wv), (118, -186 - wv)], 18, col)           # Arm vorn winkt
        for a in (-30, 0, 30):
            r_ = math.radians(a - 40)
            d.line((*P(118, -186 - wv), *P(118 + math.cos(r_) * 22, -186 - wv + math.sin(r_) * 22)), fill=INK, width=max(2, int(9 * k)))
        stroke([(0, -230), (0, -258)], 30, _dark(col, 0.15))
        hy = -350 + bob * 0.5
        for s in (-1, 1):
            stroke([(s * 46, hy - 80), (s * 70, hy - 130), (s * 86, hy - 150)], 8, _dark(col, 0.2))
            glow = 0.6 + 0.4 * math.sin(t * 5 + s)
            d.ellipse(B(s * 86 - 30, hy - 180, s * 86 + 30, hy - 120), fill=(255, 236, 120, int(80 * glow)))
            ell(s * 86 - 16, hy - 166, s * 86 + 16, hy - 134, (250, 220, 90), shade=0.2)
        ell(-130, hy - 100, 130, hy + 94, col)
        for s in (-1, 1):                                                          # große Mandelaugen
            ex = s * 52 + 6
            if blink and not wide:
                d.arc(B(ex - 34, hy - 30, ex + 34, hy + 20), 20, 160, fill=INK, width=max(2, int(8 * k)))
                continue
            sc_ = 1.15 if wide else 1.0
            d.ellipse(B(ex - 36 * sc_, hy - 44 * sc_, ex + 36 * sc_, hy + 28 * sc_), fill=INK)
            d.ellipse(B(ex + 6, hy - 32, ex + 22, hy - 16), fill=(255, 255, 255))
            d.ellipse(B(ex - 16, hy + 2, ex - 6, hy + 12), fill=(255, 255, 255, 200))
        brow(-46, hy - 58, 22, 1)
        brow(58, hy - 58, 22, -1)
        cheek(-82, hy + 36, 16)
        cheek(94, hy + 36, 16)
        mouthf(6, hy + 54, 14)
    elif kind in ("robot", "roboter"):
        col = (176, 186, 202)
        for lx in (-52, 22):
            rr(lx, -96, lx + 30, -16, 6, (120, 128, 142) if lx > 0 else (100, 106, 120), shade=0.2)
            rr(lx - 10, -24, lx + 44, 0, 8, (84, 90, 104), shade=0.15)
        wv = math.sin(t * 3) * 10
        stroke([(-90, -226), (-116, -170), (-110, -124)], 20, (120, 128, 142))     # Arm hinten
        rr(-92, -258, 92, -86, 18, col)
        rr(-58, -220, 58, -122, 10, (70, 78, 94), shade=0)                         # Brust-Anzeige
        lit = int(t * 4) % 3
        for i in range(3):
            ell(-42 + i * 30, -164, -22 + i * 30, -144, (110, 240, 150) if i == lit else (96, 104, 118), shade=0, line=False)
        d.line((*P(-40, -194), *P(40, -194)), fill=(110, 220, 255), width=max(2, int(6 * k)))
        for sx in (-78, 72):                                                       # Nieten
            for sy in (-244, -104):
                d.ellipse(B(sx - 5, sy - 5, sx + 5, sy + 5), fill=_dark(col, 0.35))
        stroke([(88, -226), (122, -180 - wv), (130, -130 - wv)], 20, (150, 158, 172))   # Arm vorn mit Greifer
        ell(110, -200 - wv, 134, -176 - wv, (120, 128, 142), shade=0)
        d.arc(B(108, -146 - wv, 154, -104 - wv), 300, 120, fill=INK, width=max(2, int(9 * k)))
        rr(-22, -282, 22, -254, 6, (120, 128, 142), shade=0.2)                     # Hals
        hy = -352 + bob * 0.3
        stroke([(0, hy - 72), (0, hy - 118)], 8, (90, 96, 110))
        blinkon = int(t * 2) % 2
        d.ellipse(B(-26, hy - 152, 26, hy - 100), fill=(255, 90, 70, 70 if blinkon else 0))
        ell(-15, hy - 141, 15, hy - 111, (240, 80, 70) if blinkon else (160, 70, 66), shade=0.2)
        rr(-114, hy - 74, 114, hy + 72, 26, col)
        for s in (-1, 1):                                                          # Ohren-Schrauben
            rr(s * 114 - 14, hy - 26, s * 114 + 14, hy + 26, 6, (130, 138, 152), shade=0)
        rr(-86, hy - 46, 92, hy + 14, 22, (40, 46, 58), shade=0)                   # Gesichtsfeld
        for s in (-1, 1):
            ex = s * 42 + 4
            if blink and not wide:
                d.line((*P(ex - 20, hy - 16), *P(ex + 20, hy - 16)), fill=(110, 220, 255), width=max(2, int(8 * k)))
            else:
                r_ = 22 if wide else 17
                d.ellipse(B(ex - r_ - 8, hy - 16 - r_ - 8, ex + r_ + 8, hy - 16 + r_ + 8), fill=(110, 220, 255, 60))
                ell(ex - r_, hy - 16 - r_, ex + r_, hy - 16 + r_, (130, 230, 255), shade=0, line=False)
                d.ellipse(B(ex + 2, hy - 30, ex + 10, hy - 22), fill=(255, 255, 255))
        mh = 10 + mouth * 16
        rr(-38, hy + 30, 42, hy + 30 + mh, 4, (40, 46, 58), shade=0)
        for i in range(1, 4):
            d.line((*P(-38 + i * 20, hy + 30), *P(-38 + i * 20, hy + 30 + mh)), fill=(150, 158, 172), width=max(2, int(3 * k)))
        cheek(-78, hy + 34, 14)
        cheek(86, hy + 34, 14)
    elif kind in ("bird", "vogel"):
        fly = True
        by = -380 + bob * 2.5
        col, breast = (120, 106, 96), (236, 120, 70)
        fl = math.sin(t * 14)
        poly([(-70, by - 6), (-150, by - 34), (-156, by + 2), (-150, by + 26), (-70, by + 18)], _dark(col, 0.1))   # Schwanzfedern
        poly([(-10, by - 14), (-70 - 30 * fl, by - 74 - 60 * fl), (-110, by - 40 - 20 * fl), (40, by - 4)], _dark(col, 0.22), shade=0)   # Flügel hinten
        ell(-92, by - 64, 84, by + 62, col)
        ell(-10, by - 20, 84, by + 60, breast, shade=0.12, line=False)
        poly([(76, by - 18), (130, by - 2), (78, by + 8)], (250, 186, 60))         # Schnabel
        poly([(78, by + 8), (118, by + 4), (78, by + 22)], (226, 150, 40), shade=0)
        poly([(-30, by - 10), (-20 - 40 * fl, by - 90 - 60 * fl), (-80 - 30 * fl, by - 60 - 30 * fl), (-60, by + 10)], col)   # Flügel vorn
        for lx in (-20, 6):                                                        # angelegte Beinchen
            stroke([(lx, by + 58), (lx - 8, by + 82)], 6, (226, 150, 40))
        eye(44, by - 22, 14)
        cheek(30, by + 12, 12)
    elif kind in ("bee", "biene", "wasp", "wespe"):
        fly = True
        wasp = kind in ("wasp", "wespe")
        by = -360 + bob * 2.5 + math.sin(t * 6) * 14
        fl = math.sin(t * 40) * 16
        yel = (250, 206, 40) if wasp else (250, 196, 60)
        blk = (34, 30, 34)
        for i, sx in enumerate((-40, 6)):                                          # Flügel hinten
            if wasp:
                poly(_leaf(sx, by - 34, sx - 140, by - 110 - fl, 22), (220, 236, 255, 200), shade=0)
            else:
                d.ellipse(B(sx - 50, by - 124 - fl, sx + 40, by - 34), fill=(220, 240, 255, 200), outline=INK, width=max(2, int(4 * k)))
        if wasp:
            poly([(-196, by + 6), (-174, by - 6), (-174, by + 18)], blk, shade=0)  # Stachel
            ab = (-180, by - 46, -20, by + 58)                                     # schlanker Hinterleib, Wespentaille
            ell(*ab, yel)
            for a in (-150, -110, -70):
                band(*ab, a, a + 22, blk)
            d.ellipse(B(*ab), outline=INK, width=o)
            ell(-30, by - 40, 52, by + 34, blk, shade=0.12)
            for lx in (-6, 18, 40):
                stroke([(lx, by + 26), (lx - 6, by + 54), (lx - 16, by + 68)], 4, blk)
            hx = 92
            ell(hx - 44, by - 50, hx + 46, by + 36, yel)
            d.chord(B(hx - 44, by - 50, hx + 46, by + 36), 200, 340, fill=blk)
            for s in (0, 16):
                stroke([(hx - 4 + s, by - 44), (hx + 6 + s, by - 90), (hx + 30 + s, by - 104)], 6, blk)
            eye(hx + 18, by - 10, 13, "angry" if eyekind == "" else None)
            d.line((*P(hx - 4, by - 34), *P(hx + 38, by - 22)), fill=INK, width=max(2, int(7 * k)))
            mouthf(hx + 20, by + 18, 10)
        else:
            poly([(-120, by - 10), (-150, by + 2), (-120, by + 14)], blk, shade=0)
            ab = (-122, by - 64, 70, by + 64)
            ell(*ab, yel)
            for a in (-70, -14):
                band(*ab, a, a + 30, blk)
            d.ellipse(B(*ab), outline=INK, width=o)
            for lx in (-30, 0, 30):
                stroke([(lx, by + 60), (lx - 8, by + 82)], 6, blk)
            hx = 96
            for s in (0, 18):
                stroke([(hx - 10 + s, by - 40), (hx + s, by - 92)], 6, blk)
                ell(hx + s - 9, by - 104, hx + s + 9, by - 86, blk, shade=0, line=False)
            ell(hx - 52, by - 50, hx + 52, by + 50, yel)
            eye(hx + 16, by - 12, 14)
            cheek(hx + 2, by + 22, 12)
            mouthf(hx + 22, by + 20, 12)
        for i, sx in enumerate((-20,)):                                            # Flügel vorn (durchscheinend)
            if wasp:
                poly(_leaf(sx + 26, by - 30, sx - 92, by - 132 + fl, 26), (230, 244, 255, 170), shade=0)
            else:
                d.ellipse(B(sx - 40, by - 130 + fl, sx + 50, by - 40), fill=(230, 244, 255, 170), outline=INK, width=max(2, int(4 * k)))
    elif kind in ("dino", "dinosaurier"):
        col = (110, 186, 104)
        spike = (236, 150, 70)
        sw = math.sin(t * 2.5) * 14
        poly([(-70, -210), (-310, -60 + sw), (-300, -36 + sw), (-40, -110)], col)                 # Schwanz
        for i in range(4):                                                         # Zacken auf Schwanz
            fx = -110 - i * 45
            fy = -186 + i * 32 + sw * i / 4
            poly([(fx + 14, fy + 4), (fx, fy - 32), (fx - 14, fy + 10)], spike, shade=0)
        rr(-46, -120, 4, -8, 18, _dark(col, 0.2), shade=0)                        # Bein hinten
        ell(-64, -22, 12, 4, _dark(col, 0.3), shade=0)
        for i in range(4):                                                         # Rückenzacken
            a = math.radians(205 + i * 22)
            sx, sy = -10 + math.cos(a) * 120, -180 + math.sin(a) * 110
            poly([(sx - 18, sy + 10), (sx + math.cos(a) * 36, sy + math.sin(a) * 36), (sx + 18, sy + 10)], spike, shade=0)
        ell(-130, -292, 110, -70, col)
        ell(-40, -232, 100, -86, (226, 230, 170), shade=0.08, line=False)       # heller Bauch
        stroke([(40, -210), (96, -300)], 86, col)                                  # Hals
        stroke([(82, -190), (118, -164), (132, -178)], 14, _dark(col, 0.1))        # Ärmchen
        ell(-90, -170, 14, -54, col, shade=0.2)                                    # Oberschenkel vorn
        rr(-56, -92, -8, -8, 18, col, shade=0.25)
        ell(-74, -24, 6, 4, _dark(col, 0.1), shade=0)
        for tx in (-64, -40, -16):
            d.ellipse(B(tx - 6, -10, tx + 6, 2), fill=(250, 250, 240))
        hx, hy = 140, -360 + bob
        jaw = mouth * 26
        rr(hx - 60, hy + 6 + jaw, hx + 104, hy + 52 + jaw, 22, _dark(col, 0.08))  # Unterkiefer
        rr(hx - 90, hy - 74, hx + 110, hy + 30, 50, col)
        for i in range(5):                                                         # Zähne
            tx = hx - 20 + i * 24
            poly([(tx, hy + 26), (tx + 10, hy + 44 + jaw * 0.3), (tx + 20, hy + 26)], (252, 252, 244), shade=0, line=False)
        d.line((*P(hx - 30, hy + 26), *P(hx + 104, hy + 26)), fill=INK, width=max(2, int(5 * k)))
        ell(hx + 80, hy - 40, hx + 94, hy - 26, INK, shade=0, line=False)          # Nasenloch
        for i in range(3):                                                         # Zacken am Hinterkopf
            poly([(hx - 74 + i * 26, hy - 60), (hx - 82 + i * 26, hy - 100), (hx - 50 + i * 26, hy - 66)], spike, shade=0)
        eye(hx + 14, hy - 30, 20)
        brow(hx + 14, hy - 58, 20, 1)
        cheek(hx - 10, hy + 2, 16)
    elif kind == "brain":
        # Das Gehirn als Figur („dein Gehirn schlägt Alarm“): rosa, zwei Hälften mit Windungen, großes Augenpaar, Ärmchen und Beinchen
        col = (240, 150, 172)
        hop = abs(math.sin(t * 5)) * 10 if mood in ("happy",) else 0
        by = -168 - hop
        for lx in (-46, 46):                                                     # Beinchen mit Schuhen
            stroke([(lx, by + 80), (lx + 4, -14 - hop * 0.3)], 18, _dark(col, 0.22) if lx < 0 else _dark(col, 0.1))
            ell(lx - 18, -26, lx + 30, 2, (70, 80, 120), shade=0)
        sw = math.sin(t * 3) * 10
        for s_ in (-1, 1):                                                       # Ärmchen
            stroke([(s_ * 128, by + 30), (s_ * 172, by + 56 + s_ * sw), (s_ * 184, by + 86 + s_ * sw)], 15, _dark(col, 0.1))
            ell(s_ * 184 - 15, by + 76 + s_ * sw, s_ * 184 + 15, by + 106 + s_ * sw, col, shade=0)
        bumps = [(-112, -40, 46), (-96, -86, 46), (-52, -116, 48), (0, -124, 48), (52, -116, 48), (96, -86, 46), (112, -40, 46),
                 (118, 12, 42), (96, 58, 42), (-118, 12, 42), (-96, 58, 42), (-48, 78, 42), (0, 84, 42), (48, 78, 42)]
        for bx_, by_, r_ in bumps:                                               # Umriss aus Wülsten …
            ell(bx_ - r_, by + by_ - r_, bx_ + r_, by + by_ + r_, _dark(col, 0.24), shade=0)
        for bx_, by_, r_ in bumps:                                               # … mit heller Oberseite
            ell(bx_ - r_ + 12, by + by_ - r_, bx_ + r_, by + by_ + r_ - 10, col, shade=0, line=False)
        ell(-118, by - 112, 118, by + 84, col, shade=0, line=False)
        fold = _dark(col, 0.3)
        wl = max(2, int(7 * k))
        d.line([P(4, by - 168), P(-4, by - 120), P(6, by - 84)], fill=fold, width=wl, joint="curve")                # Furche zwischen den Hälften
        for s_ in (-1, 1):                                                       # Windungen
            d.arc(B(s_ * 26, by - 140, s_ * 96, by - 84), 180, 360, fill=fold, width=wl)
            d.arc(B(s_ * 70, by - 96, s_ * 132, by - 44), 180, 360, fill=fold, width=wl)
            d.arc(B(s_ * 36, by + 36, s_ * 100, by + 84), 0, 180, fill=fold, width=wl)
        ex, ey = 8, by - 22                                                      # großes Augenpaar
        eye(ex - 40, ey, 27)
        eye(ex + 40, ey, 27)
        if mood in ("sad", "angry", "worried", "scared"):
            dy = 10 if mood == "angry" else -10
            for s_ in (-1, 1):
                d.line((*P(ex + s_ * 40 - 26, ey - 48 + dy * s_), *P(ex + s_ * 40 + 26, ey - 48 - dy * s_)), fill=INK, width=max(2, int(9 * k)))
        cheek(ex - 80, ey + 34, 15)
        cheek(ex + 84, ey + 34, 15)
        if mouth > 0.1:
            mouthf(ex, ey + 50, 18)
        elif wide:                                                               # erschrocken: kleiner offener Mund
            d.ellipse(B(ex - 12, ey + 40, ex + 12, ey + 68), fill=(110, 36, 46), outline=INK, width=max(2, int(4 * k)))
        else:
            d.arc(B(ex - 20, ey + 30, ex + 20, ey + 62), *((200, 340) if mood in ("sad", "worried", "scared", "angry") else (20, 160)), fill=INK, width=max(2, int(6 * k)))
    elif kind in ("agent", "virus", "cell"):
        # Personifizierte Begriffe (wie die KI-Agenten in den Vorbild-Shorts): ein Kästchen, eine Stachelkugel, eine Zelle –
        # mit großen Augen, Augenbrauen, Mund, Ärmchen und Beinchen; Farbe je Begriff
        col = {"agent": (240, 104, 56), "virus": (120, 196, 84), "cell": (238, 110, 130)}[kind]
        hop = abs(math.sin(t * 5)) * 10 if mood in ("happy",) else 0
        by = -150 - hop
        for lx in (-60, -20, 20, 60):                                            # Beinchen
            far = lx in (-20, 60)
            stroke([(lx, by + 70), (lx + 4, -12 - hop * 0.3)], 16, _dark(col, 0.25) if far else _dark(col, 0.1))
            ell(lx - 14, -22, lx + 18, 2, _dark(col, 0.35), shade=0)
        sw = math.sin(t * 3) * 10
        for s_ in (-1, 1):                                                       # Ärmchen
            stroke([(s_ * 110, by + 10), (s_ * 150, by + 40 + s_ * sw), (s_ * 160, by + 70 + s_ * sw)], 14, _dark(col, 0.08))
        if kind == "agent":
            rr(-125, by - 100, 125, by + 85, 34, col)
            d.rounded_rectangle(B(-110, by - 92, 60, by - 70), int(10 * k), fill=_light(col, 0.25))          # Glanzkante
        else:
            if kind == "virus":                                                  # Stacheln mit Knubbeln
                for i in range(12):
                    a_ = i / 12 * math.tau + 0.2
                    x1_, y1_ = math.cos(a_) * 118, by + math.sin(a_) * 108
                    x2_, y2_ = math.cos(a_) * 158, by + math.sin(a_) * 146
                    stroke([(x1_, y1_), (x2_, y2_)], 12, _dark(col, 0.15))
                    ell(x2_ - 16, y2_ - 16, x2_ + 16, y2_ + 16, (214, 90, 90), shade=0.2)
            ell(-125, by - 115, 125, by + 105, col)
            if kind == "cell":
                ell(-70, by - 80, 10, by - 10, _dark(col, 0.2), shade=0, line=False)            # Zellkern
            else:
                for dx, dy, r_ in ((-70, by + 40, 12), (60, by + 60, 9), (80, by - 70, 10)):
                    ell(dx - r_, dy - r_, dx + r_, dy + r_, _dark(col, 0.22), shade=0, line=False)
        ex, ey = 10, by - 25                                                     # großes Augenpaar, nah beieinander
        eye(ex - 40, ey, 26)
        eye(ex + 40, ey, 26)
        bm = mood if mood in ("sad", "angry", "worried", "scared") else ("angry" if kind == "virus" and not mood else "")
        if bm:
            dy = 10 if bm == "angry" else -10
            for s_ in (-1, 1):
                d.line((*P(ex + s_ * 40 - 26, ey - 46 - dy * s_ * -1 if False else ey - 46 + (dy if s_ < 0 else -dy) * (1 if bm == "angry" else -1)),
                        *P(ex + s_ * 40 + 26, ey - 46 - (dy if s_ < 0 else -dy) * (1 if bm == "angry" else -1))), fill=INK, width=max(2, int(9 * k)))
        cheek(ex - 78, ey + 34, 15)
        cheek(ex + 82, ey + 34, 15)
        mouthf(ex, ey + 56, 18)
    elif kind == "monster":
        col = (150, 106, 206)
        fur = _dark(col, 0.3)
        for s in (-1, 1):                                                          # große Füße mit Krallen
            ell(s * 70 - 54, -42, s * 70 + 54, 6, _dark(col, 0.15) if s < 0 else col, shade=0.15)
            for c in (-26, 0, 26):
                poly([(s * 70 + c - 8, -2), (s * 70 + c, 16), (s * 70 + c + 8, -2)], (250, 246, 230), shade=0)
        cy_ = -196 + bob * 0.5
        def furpts(r, n=40):
            return [(math.cos(i / n * math.tau) * r * (1 if i % 2 else 0.92) * 1.05, cy_ + math.sin(i / n * math.tau) * r * (1 if i % 2 else 0.92)) for i in range(n)]
        d.polygon([P(x, y) for x, y in furpts(176)], fill=fur, outline=INK, width=o)
        d.polygon([P(x + 20, y - 12) for x, y in furpts(150)], fill=col)
        ell(-60, cy_ + 20, 90, cy_ + 150, _light(col, 0.3), shade=0, line=False)  # Bauchfell
        for s in (-1, 1):                                                          # Hörner
            poly([(s * 70 - 22, cy_ - 140), (s * 120, cy_ - 230), (s * 76 + 20, cy_ - 150)], (246, 236, 200))
        wv = math.sin(t * 4) * 16
        for s in (-1, 1):                                                          # Arme mit Krallen, drohend erhoben
            stroke([(s * 160, cy_ + 10), (s * 214, cy_ - 50 - wv), (s * 220, cy_ - 110 - wv)], 34, col if s > 0 else _dark(col, 0.15))
            for c in (-18, 0, 18):
                poly([(s * 220 + c - 7, cy_ - 118 - wv), (s * 220 + c, cy_ - 146 - wv), (s * 220 + c + 7, cy_ - 118 - wv)], (250, 246, 230), shade=0)
        ex, ey = 20, cy_ - 60                                                      # ein großes Auge
        eye(ex, ey, 40)
        brow(ex, ey - 64, 40, 1)
        mh = 34 + mouth * 40 + (16 if wide else 0)
        d.chord(B(-70, cy_ - 10 - mh * 0.3, 110, cy_ + 30 + mh), 0, 180, fill=(96, 30, 50), outline=INK, width=o)
        d.line((*P(-70, cy_ + 10), *P(110, cy_ + 10)), fill=INK, width=o)
        for i in range(5):                                                         # Zähne
            tx = -56 + i * 34
            poly([(tx, cy_ + 10), (tx + 12, cy_ + 34), (tx + 24, cy_ + 10)], (252, 252, 244), shade=0, line=False)
        cheek(-90, cy_ - 10, 18)
        cheek(130, cy_ - 10, 18)
    elif kind in ("fish", "fisch", "shark", "hai"):
        fly = True
        shark = kind in ("shark", "hai")
        by = -330 + bob * 2
        wag = math.sin(t * 9) * 26
        if shark:
            col, belly = (110, 132, 158), (240, 244, 248)
            poly([(-150, by), (-250, by - 100 + wag), (-216, by + wag * 0.5), (-240, by + 74 + wag), (-140, by + 12)], _dark(col, 0.05))
            poly([(-20, by - 70), (30, by - 170), (60, by - 66)], col)                                        # Rückenflosse
            xs = [-170 + i * 22 for i in range(18)]
            top = [(x, by - 76 * math.sqrt(max(0.0, 1 - ((x - 10) / 190) ** 2)) ** 0.8) for x in xs]
            bot = [(x, by + 66 * math.sqrt(max(0.0, 1 - ((x - 10) / 190) ** 2)) ** 0.8) for x in xs]
            d.polygon([P(*p) for p in top + bot[::-1]], fill=_dark(col, 0.2), outline=INK, width=o)
            d.polygon([P(x + 10, y + 4) for x, y in top[1:]] + [P(x + 10, by + 10) for x, _ in top[:0:-1]], fill=col)
            d.polygon([P(x, by + 18 + (y - by - 18) * 0.95) for x, y in bot[2:]] + [P(xs[-1], by + 18), P(xs[2], by + 18)], fill=belly)
            for gx in (60, 78, 96):                                                                           # Kiemen
                d.arc(B(gx - 12, by - 24, gx + 12, by + 24), 290, 70, fill=_dark(col, 0.4), width=max(2, int(4 * k)))
            poly([(40, by + 30), (-20, by + 104), (90, by + 40)], _dark(col, 0.1))                           # Brustflosse
            eye(130, by - 22, 12)
            brow(130, by - 44, 14, 1)
            jaw = mouth * 22
            d.chord(B(110, by + 14, 196, by + 44 + jaw), 0, 180, fill=(110, 36, 46), outline=INK, width=max(2, int(4 * k)))
            for i in range(4):
                tx = 120 + i * 18
                poly([(tx, by + 28), (tx + 8, by + 42), (tx + 16, by + 28)], (252, 252, 244), shade=0, line=False)
        else:
            col = (250, 146, 56)
            poly([(-120, by), (-220, by - 74 + wag), (-196, by + wag * 0.3), (-220, by + 74 + wag)], col)
            for s in (-30, 30):
                d.line((*P(-150, by + s * 0.3), *P(-200, by + s * 1.6 + wag)), fill=_dark(col, 0.3), width=max(2, int(4 * k)))
            poly([(-60, by - 66), (-20, by - 140), (60, by - 120), (50, by - 70)], col)                      # Rückenflosse
            ell(-150, by - 82, 150, by + 82, col)
            ell(-80, by + 10, 120, by + 76, _light(col, 0.4), shade=0, line=False)
            band(-150, by - 82, 150, by + 82, 34, 62, (252, 250, 246))                                         # weißer Streifen
            d.ellipse(B(-150, by - 82, 150, by + 82), outline=INK, width=o)
            for sx in (-70, -30, 10):                                                                         # Schuppen
                for sy in (-30, 10):
                    d.arc(B(sx - 16, by + sy - 14, sx + 16, by + sy + 14), 270, 90, fill=_dark(col, 0.25), width=max(2, int(4 * k)))
            fl = math.sin(t * 7) * 14
            poly([(0, by + 20), (-40, by + 70 + fl), (30, by + 56)], _dark(col, 0.08))
            eye(100, by - 18, 18)
            brow(100, by - 46, 16, 1)
            cheek(96, by + 22, 14)
            mouthf(138, by + 22, 12)
    else:
        return None
    out = im.resize((im.width // S, im.height // S), Image.LANCZOS)
    return out, cx / S, gy / S, fly


CREATURES = ("cat", "dog", "spider", "ghost", "alien", "robot", "bird", "dino", "monster", "fish", "shark", "bee", "wasp", "agent", "virus", "cell", "brain")
