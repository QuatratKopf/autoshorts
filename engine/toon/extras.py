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
        if min(bw, bh) < 3:                               # winziges Teil (Glühbirnen-Sockel, während das Zeichen ins Bild springt): nichts zu zeichnen – Pillow wirft sonst „x1 must be greater than or equal to x0“ und die ganze Szene fiel auf die Ersatzfassung zurück
            return
        w = max(1, min(int(w), int(min(bw, bh) / 2) - 1)) if min(bw, bh) < 18 else w
        d.rounded_rectangle(box, max(0, min(r, bw / 2 - 1, bh / 2 - 1)), fill=col, outline=INK, width=w)
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


def p_moss(d, x, t, s=1.0):
    """Moospolster (Prüfung 17.11.2026, Bärtierchen): sattgrünes, buckliges Kissen mit Sporenkapseln auf dünnen Stielen und Tautropfen."""
    g, gd, gl = (86, 150, 70), (60, 116, 54), (124, 186, 96)
    for bx, r in ((-150, 70), (-70, 100), (30, 112), (126, 84), (190, 56)):          # Umriss der Buckel
        d.chord((x + bx - r - O, GROUND - r - O, x + bx + r + O, GROUND + r + O), 180, 360, fill=INK)
    for bx, r in ((-150, 70), (-70, 100), (30, 112), (126, 84), (190, 56)):
        d.chord((x + bx - r, GROUND - r, x + bx + r, GROUND + r), 180, 360, fill=gd)
        d.chord((x + bx - r * 0.84, GROUND - r * 0.92, x + bx + r * 0.7, GROUND + r * 0.92), 180, 360, fill=g)
    for i, (bx, by) in enumerate(((-150, 44), (-96, 78), (-40, 60), (10, 96), (62, 70), (116, 62), (168, 36), (-10, 36), (-116, 26), (86, 28))):   # Tupfen: einzelne Moos-Büschel
        d.ellipse((x + bx - 16, GROUND - by - 10, x + bx + 16, GROUND - by + 10), fill=gl if i % 2 else gd)
    for bx, h in ((-84, 150), (6, 176), (98, 140)):                                  # Sporenkapseln, wiegen sich leicht
        sway = math.sin(t * 2.2 + bx) * 8
        d.line((x + bx, GROUND - h + 60, x + bx + sway, GROUND - h), fill=(120, 90, 60), width=6)
        d.ellipse((x + bx + sway - 10, GROUND - h - 22, x + bx + sway + 10, GROUND - h + 4), fill=(196, 150, 84), outline=INK, width=4)
    for bx, by in ((-30, 104), (140, 72)):                                           # Tautropfen
        d.ellipse((x + bx - 9, GROUND - by - 9, x + bx + 9, GROUND - by + 9), fill=(190, 230, 250), outline=(90, 150, 200), width=3)


def p_shield(d, x, t, s=1.0):
    """Schutzschild mit Erbgut-Strang (Prüfung 17.11.2026: „ein Schutz-Eiweiß legt sich wie ein Schild um ihr Erbgut“): blauer Wappenschild, darauf eine
    gewundene Doppelhelix; pulsiert leicht."""
    k = 1.0 + 0.03 * math.sin(t * 5)
    w, h, top = 120 * k, 300 * k, GROUND - 330
    out = [(x - w, top), (x + w, top), (x + w, top + h * 0.5), (x, top + h), (x - w, top + h * 0.5)]
    d.polygon(out, fill=(40, 96, 190), outline=INK, width=O)
    d.polygon([(x - w + 18, top + 18), (x - 4, top + 18), (x - 4, top + h - 30), (x - w + 18, top + h * 0.5 - 6)], fill=(74, 140, 230))
    pa, pb = [], []
    for i in range(13):                                                              # Doppelhelix
        yy = top + 44 + i * (h * 0.62) / 12
        dx = math.sin(i * 0.78 + t * 2.4) * 46
        pa.append((x + dx, yy))
        pb.append((x - dx, yy))
        if i % 2 == 0:
            d.line((x + dx, yy, x - dx, yy), fill=(255, 236, 170), width=6)
    d.line(pa, fill=(255, 255, 255), width=10, joint="curve")
    d.line(pb, fill=(255, 196, 80), width=10, joint="curve")


def p_box(d, x, t, s=1.0):
    _r(d, (x - 100, GROUND - 170, x + 100, GROUND), (214, 170, 110), 8)
    d.line((x - 100, GROUND - 120, x + 100, GROUND - 120), fill=INK, width=5)
    _r(d, (x - 24, GROUND - 170, x + 24, GROUND - 100), (236, 204, 150), 4, 5)


def _p_car(d, x, t, col, dark, shine, stripe=None, light=False):
    b = math.sin(t * 9) * 3
    d.ellipse((x - 230, GROUND - 22, x + 230, GROUND + 18), fill=(0, 0, 0, 60))
    _r(d, (x - 210, GROUND - 150 + b, x + 210, GROUND - 40 + b), col, 30)
    d.rounded_rectangle((x - 120, GROUND - 240 + b, x + 110, GROUND - 140 + b), 34, fill=col, outline=INK, width=O)
    d.rounded_rectangle((x - 204, GROUND - 84 + b, x + 204, GROUND - 46 + b), 18, fill=dark)                 # Schattenkante unten
    d.rounded_rectangle((x - 190, GROUND - 144 + b, x + 60, GROUND - 128 + b), 8, fill=shine)       # Glanz
    if stripe:                                                                                               # Streifenwagen: farbiges Band über die Seite
        d.rectangle((x - 204, GROUND - 122 + b, x + 204, GROUND - 92 + b), fill=stripe)
    if light:                                                                                                # Blaulicht auf dem Dach (ruhiges Pulsieren)
        k = 0.5 + 0.5 * math.sin(t * 5)
        _r(d, (x - 34, GROUND - 268 + b, x + 30, GROUND - 236 + b), (40 + int(60 * k), 120 + int(80 * k), 255), 10, 5)
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


def p_car(d, x, t, s=1.0):
    _p_car(d, x, t, (226, 70, 60), (184, 50, 48), (244, 110, 96))


def p_police(d, x, t, s=1.0):
    """Streifenwagen: helles Auto mit blauem Band und Blaulicht (ohne Wappen oder Schriftzug)."""
    _p_car(d, x, t, (236, 238, 244), (198, 202, 214), (255, 255, 255), stripe=(52, 104, 190), light=True)


def p_ambulance(d, x, t, s=1.0):
    """Rettungswagen: weißer Kastenwagen mit rotem Band, Blaulicht und schlichtem Kreuz (kein Logo)."""
    b = math.sin(t * 9) * 3
    d.ellipse((x - 330, GROUND - 24, x + 330, GROUND + 20), fill=(0, 0, 0, 60))
    _r(d, (x - 300, GROUND - 330 + b, x + 120, GROUND - 50 + b), (244, 244, 248), 16)                        # Aufbau
    _r(d, (x + 110, GROUND - 250 + b, x + 300, GROUND - 50 + b), (244, 244, 248), 26)                        # Fahrerhaus
    d.rectangle((x - 294, GROUND - 100 + b, x + 294, GROUND - 58 + b), fill=(208, 210, 220))                 # Schattenkante unten
    d.rectangle((x - 294, GROUND - 172 + b, x + 294, GROUND - 128 + b), fill=(226, 70, 60))                  # rotes Band
    _r(d, (x + 170, GROUND - 232 + b, x + 284, GROUND - 180 + b), (170, 220, 250), 10, 5)                    # Scheibe
    d.polygon([(x + 184, GROUND - 226 + b), (x + 208, GROUND - 226 + b), (x + 194, GROUND - 186 + b), (x + 178, GROUND - 186 + b)], fill=(220, 240, 255))
    _r(d, (x - 250, GROUND - 300 + b, x - 150, GROUND - 200 + b), (170, 220, 250), 10, 5)                    # Fenster im Aufbau
    cx, cy = x - 40, GROUND - 250 + b                                                                        # schlichtes blaues Kreuz
    d.rounded_rectangle((cx - 16, cy - 46, cx + 16, cy + 46), 6, fill=(52, 104, 190))
    d.rounded_rectangle((cx - 46, cy - 16, cx + 46, cy + 16), 6, fill=(52, 104, 190))
    k = 0.5 + 0.5 * math.sin(t * 5)
    _r(d, (x - 120, GROUND - 362 + b, x - 50, GROUND - 326 + b), (40 + int(60 * k), 120 + int(80 * k), 255), 10, 5)   # Blaulicht
    d.line((x + 112, GROUND - 240 + b, x + 112, GROUND - 60 + b), fill=INK, width=4)
    for wx in (-190, 200):
        _o(d, (x + wx - 52, GROUND - 98, x + wx + 52, GROUND + 6), (40, 40, 46))
        _o(d, (x + wx - 21, GROUND - 67, x + wx + 21, GROUND - 25), (200, 200, 206), 4)
    _o(d, (x + 276, GROUND - 130 + b, x + 304, GROUND - 100 + b), (255, 236, 150), 4)


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


def p_aquarium(d, x, t, s=1.0, crab=False):
    """Aquarium auf einem Schränkchen: Wasser, Kies, Pflanze, Luftblasen und ein Goldfisch, der hin und her schwimmt
    (crab=True: Forschungsbecken mit einem bunten Krebs am Kies statt des Goldfischs)."""
    _r(d, (x - 190, GROUND - 190, x + 190, GROUND), (150, 104, 70), 10)                          # Schränkchen
    _r(d, (x - 150, GROUND - 150, x - 14, GROUND - 30), (176, 124, 84), 8, 5)
    _r(d, (x + 14, GROUND - 150, x + 150, GROUND - 30), (176, 124, 84), 8, 5)
    for kx in (-36, 36):
        d.ellipse((x + kx - 9, GROUND - 100, x + kx + 9, GROUND - 82), fill=(250, 214, 110), outline=INK, width=3)
    top, bot = GROUND - 470, GROUND - 190
    d.rounded_rectangle((x - 176, top, x + 176, bot), 14, fill=(150, 214, 240), outline=INK, width=O)   # Becken
    d.rectangle((x - 170, top + 34, x + 170, bot - 6), fill=(96, 184, 232))
    wv = [(x - 170 + i * 20, top + 34 + math.sin(t * 3 + i * 0.9) * 4) for i in range(18)]
    d.polygon(wv + [(x + 170, top + 52), (x - 170, top + 52)], fill=(190, 232, 248))               # Wasserlinie
    d.rectangle((x - 170, bot - 40, x + 170, bot - 6), fill=(226, 196, 140))                       # Kies
    for i in range(9):
        d.ellipse((x - 160 + i * 37, bot - 46 + (i % 2) * 6, x - 134 + i * 37, bot - 28 + (i % 2) * 6), fill=(204, 170, 118))
    for i, (px_, hgt) in enumerate(((-120, 130), (-96, 90), (124, 110))):                           # Wasserpflanzen
        pts = [(x + px_ + math.sin(t * 2 + j * 0.8 + i) * (4 + j * 2), bot - 30 - j * hgt / 6) for j in range(7)]
        d.line(pts, fill=(40, 150, 96), width=12, joint="curve")
    for i in range(3):                                                                             # Luftblasen
        by_ = bot - 50 - ((t * 70 + i * 60) % 170)
        d.ellipse((x + 96 + i * 12 - 7, by_ - 7, x + 96 + i * 12 + 7, by_ + 7), outline=(236, 250, 255), width=3)
    if crab:                                                                                       # Krebs im Becken: sitzt am Kies, die Keule schnellt gegen die Scheibe
        cx_, cy_ = x - 10 + math.sin(t * 1.1) * 14, bot - 86
        gr, gd = (70, 176, 124), (48, 132, 92)
        for i, (ox, oy, r_) in enumerate(((-96, 26, 20), (-70, 12, 27), (-38, 2, 33))):            # Hinterleib aus Ringen
            d.ellipse((cx_ + ox - r_, cy_ + oy - r_, cx_ + ox + r_, cy_ + oy + r_), fill=gd if i % 2 else gr, outline=INK, width=4)
        d.polygon([(cx_ - 112, cy_ + 30), (cx_ - 146, cy_ + 12), (cx_ - 140, cy_ + 52)], fill=(60, 130, 220), outline=INK, width=4)   # Schwanzfächer
        for lx in (-50, -24, 2):
            d.line([(cx_ + lx, cy_ + 28), (cx_ + lx - 6 + math.sin(t * 7 + lx) * 4, cy_ + 50)], fill=gd, width=6)
        d.ellipse((cx_ - 30, cy_ - 40, cx_ + 62, cy_ + 34), fill=gr, outline=INK, width=5)           # Panzer
        for sx in (-8, 18):
            d.ellipse((cx_ + sx - 6, cy_ - 28, cx_ + sx + 6, cy_ - 16), fill=(250, 206, 80))
        for ex in (30, 54):                                                                        # Stielaugen
            d.line([(cx_ + ex, cy_ - 30), (cx_ + ex, cy_ - 52)], fill=(150, 110, 200), width=7)
            d.ellipse((cx_ + ex - 12, cy_ - 72, cx_ + ex + 12, cy_ - 48), fill=(255, 255, 255), outline=INK, width=4)
            d.ellipse((cx_ + ex - 2, cy_ - 64, cx_ + ex + 8, cy_ - 54), fill=INK)
        ph = (t * 0.9) % 1.0
        ext = 1.0 if ph > 0.8 else 0.0
        fx_ = cx_ + 74 + 46 * ext
        d.line([(cx_ + 46, cy_ + 12), (cx_ + 66 + 10 * ext, cy_ + 26), (fx_, cy_ + 10)], fill=gd, width=9, joint="curve")
        d.ellipse((fx_ - 15, cy_ - 4, fx_ + 17, cy_ + 24), fill=(232, 84, 60), outline=INK, width=4)   # Keule
        if ext:
            for i in range(8):
                a_ = i / 8 * math.tau
                d.line([(fx_ + 30 + math.cos(a_) * 10, cy_ + 10 + math.sin(a_) * 10), (fx_ + 30 + math.cos(a_) * 26, cy_ + 10 + math.sin(a_) * 26)], fill=(255, 236, 120), width=5)
        return
    sw = math.sin(t * 1.3)
    fx, fy = x + sw * 70, top + 150 + math.sin(t * 2.4) * 12
    fd = 1 if math.cos(t * 1.3) >= 0 else -1                                                       # schwimmt in Blickrichtung
    wag = math.sin(t * 10) * 10
    gold = (250, 150, 50)
    d.polygon([(fx - fd * 44, fy), (fx - fd * 92, fy - 34 + wag), (fx - fd * 80, fy + wag * 0.3), (fx - fd * 92, fy + 34 + wag)], fill=gold, outline=INK, width=5)
    d.polygon([(fx - fd * 20, fy - 30), (fx, fy - 60), (fx + fd * 24, fy - 30)], fill=_dk(gold), outline=INK, width=5)
    d.ellipse((fx - 56, fy - 38, fx + 56, fy + 38), fill=_dk(gold), outline=INK, width=5)
    d.ellipse((fx - 50, fy - 34, fx + 44, fy + 26), fill=gold)
    ex = fx + fd * 28
    d.ellipse((ex - 15, fy - 22, ex + 15, fy + 8), fill=(255, 255, 255), outline=INK, width=4)
    d.ellipse((ex - 7 + fd * 5, fy - 13, ex + 7 + fd * 5, fy + 1), fill=INK)
    d.arc((ex - 4, fy + 6, ex + 20, fy + 24), 20, 150, fill=INK, width=4)
    d.polygon([(x - 170, top + 110), (x - 100, top + 40), (x - 56, top + 40), (x - 170, top + 170)], fill=(255, 255, 255, 60))   # Spiegelung im Glas
    d.rounded_rectangle((x - 176, top, x + 176, bot), 14, outline=INK, width=O)
    _r(d, (x - 186, top - 22, x + 186, top + 8), (60, 64, 76), 8, 5)                               # Deckel


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

def p_debris(d, x, t, s=1.0):
    """Treibgut auf dem Meer: ein abgerissenes Rumpfstück mit Fenstern, ein Sitzkissen und ein Koffer schaukeln auf den Wellen
    (nur von der Regie gesetzt – auf der Meeresoberfläche, nie an Land)."""
    def bob(i):
        return math.sin(t * 1.5 + i * 2.1) * 9
    y = FAR + 250 + bob(0)                                                      # Rumpfstück: groß, schräg im Wasser
    _poly(d, [(x - 190, y - 6), (x - 150, y - 108), (x - 96, y - 86), (x - 40, y - 128), (x + 44, y - 112), (x + 150, y - 132), (x + 196, y - 20), (x + 150, y + 8), (x - 150, y + 10)], (236, 238, 244))
    d.line((x - 168, y - 26, x + 186, y - 34), fill=(214, 70, 60), width=10)
    for i in range(3):
        _o(d, (x - 96 + i * 76, y - 84 - i * 3, x - 58 + i * 76, y - 46 - i * 3), (120, 190, 240), 4, False)
    y2 = FAR + 120 + bob(1)                                                     # Sitzkissen weiter hinten
    _r(d, (x - 330, y2 - 44, x - 236, y2 + 4), (236, 140, 50), 14, 5)
    y3 = FAR + 150 + bob(2)                                                     # Koffer
    _r(d, (x + 250, y3 - 62, x + 350, y3 + 6), (120, 84, 60), 10, 5)
    d.line((x + 284, y3 - 62, x + 284, y3 - 80, x + 316, y3 - 80, x + 316, y3 - 62), fill=INK, width=6)
    for wx, wy, ww in ((x - 20, y + 16, 250), (x - 286, y2 + 10, 80), (x + 300, y3 + 12, 84)):       # Wasserlinie: helle Wellenbögen davor
        for k in (-1, 0, 1):
            d.arc((wx + k * ww * 0.66 - ww * 0.36, wy - 14, wx + k * ww * 0.66 + ww * 0.36, wy + 22), 180, 360, fill=(226, 242, 252, 255), width=7)


def p_submersible(d, x, t, s=1.0):
    """Forschungs-Tauchboot (Sonar, Tauchroboter): schwebt im Wasser, Blick nach rechts; der Scheinwerfer leuchtet schräg nach unten,
    die Ortungs-Ringe des Sonars laufen in dieselbe Richtung zum Meeresgrund."""
    if x <= W:
        x = max(290, min(x, W - 250))                                                                         # ganz im Bild, auch am rechten Platz
    y = 640 + math.sin(t * 1.3) * 12
    d.polygon([(x + 196, y + 52), (x + 560, y + 250), (x + 430, y + 380)], fill=(255, 240, 170, 54))          # Lichtkegel
    for i in range(3):                                                                                        # Sonar: drei Ringe wandern nach außen und verblassen
        ph = (t * 0.6 + i / 3) % 1
        rr = 150 + ph * 330
        d.arc((x + 150 - rr, y + 40 - rr, x + 150 + rr, y + 40 + rr), 14, 76, fill=(120, 244, 220, int(230 * (1 - ph) ** 0.7)), width=12)
    for sx in (-120, 110):                                                                                    # Kufen
        d.line((x + sx, y + 80, x + sx - 14, y + 124), fill=INK, width=12)
    d.line((x - 190, y + 124, x + 170, y + 124), fill=INK, width=16)
    d.line((x - 186, y + 122, x + 166, y + 122), fill=(120, 126, 140), width=6)
    _r(d, (x - 262, y - 56, x - 226, y + 56), (96, 104, 122), 8)                                              # Schraube im Schutzring
    spin = math.sin(t * 14) * 40
    d.line((x - 244, y - spin, x - 244, y + spin), fill=(200, 206, 216), width=8)
    _r(d, (x - 232, y - 20, x - 196, y + 22), (96, 104, 122), 4)
    _r(d, (x - 96, y - 136, x + 44, y - 66), (232, 120, 52), 16)                                              # Turm
    d.line((x - 40, y - 136, x - 40, y - 186), fill=INK, width=8)
    d.ellipse((x - 52, y - 206, x - 28, y - 182), fill=(250, 90, 70) if int(t * 2) % 2 else (150, 60, 56), outline=INK, width=4)
    _r(d, (x - 220, y - 84, x + 190, y + 90), (246, 196, 56), 84)                                             # Rumpf
    d.line((x - 176, y + 34, x + 96, y + 34), fill=(210, 150, 40), width=10)
    _r(d, (x - 150, y - 34, x - 60, y + 6), (96, 104, 122), 12)                                               # seitliche Düse
    _o(d, (x + 70, y - 76, x + 228, y + 82), (150, 214, 240))                                                 # Sichtkuppel
    d.arc((x + 92, y - 56, x + 190, y + 42), 190, 262, fill=(240, 250, 255), width=9)
    _o(d, (x + 150, y + 48, x + 200, y + 98), (255, 244, 180), 5)                                             # Scheinwerfer
    d.line([(x + 60, y + 86), (x + 130, y + 150), (x + 196, y + 136)], fill=INK, width=14, joint="curve")     # Greifarm
    d.line([(x + 60, y + 86), (x + 130, y + 150), (x + 196, y + 136)], fill=(150, 156, 170), width=6, joint="curve")
    d.line([(x + 196, y + 136), (x + 226, y + 118)], fill=INK, width=8)
    d.line([(x + 196, y + 136), (x + 228, y + 152)], fill=INK, width=8)


def p_tank(d, x, t, s=1.0):
    """Forschungsbecken aus dickem Kunststoff mit einem Krebs darin (Tier-Videos: „Forscher halten ihn in Plastikbecken“)."""
    p_aquarium(d, x, t, s, crab=True)


CAVI_Y = 930                                                # Höhe der Keule eines Meerestiers als Hauptfigur (stage: HERO_SIZE)


def p_cavitation(d, x, t, s=1.0):
    """Kavitationsblase vor der Keule des Krebses: wächst nach dem Schlag, fällt in sich zusammen und blitzt dabei hell auf –
    mit Druckringen, die sich im Wasser ausbreiten. Läuft im Takt des Schlags (extras.creature, mantis)."""
    cy = CAVI_Y
    ph = (t * 0.9 + 0.2) % 1.0
    if ph < 0.5:                                           # Blase wächst
        g = ph / 0.5
        r_ = 26 + 96 * g ** 0.7
    elif ph < 0.62:                                        # fällt zusammen
        g = (ph - 0.5) / 0.12
        r_ = 122 * (1 - g) + 14
    else:
        r_ = 0
    if r_:
        d.ellipse((x - r_, cy - r_, x + r_, cy + r_), fill=(214, 240, 252, 150), outline=(240, 252, 255, 240), width=max(4, int(r_ * 0.09)))
        d.ellipse((x - r_ * 0.55, cy - r_ * 0.62, x - r_ * 0.1, cy - r_ * 0.2), fill=(255, 255, 255, 210))
        for i in range(5):                                 # kleine Dampfblasen steigen daneben auf
            bx = x - 90 + i * 46 + math.sin(t * 3 + i) * 8
            by_ = cy + 150 - ((t * 120 + i * 53) % 260)
            d.ellipse((bx - 11, by_ - 11, bx + 11, by_ + 11), outline=(236, 250, 255, 220), width=4)
    else:                                                  # Blitz und Druckwelle beim Zusammenfallen
        g = (ph - 0.62) / 0.38
        fl = max(0.0, 1 - g * 1.6)
        if fl > 0:
            pts = []
            for i in range(20):
                a_ = i / 20 * math.tau + 0.2
                rr = (150 if i % 2 else 62) * (0.6 + 0.6 * g)
                pts.append((x + math.cos(a_) * rr, cy + math.sin(a_) * rr))
            d.polygon(pts, fill=(255, 244, 170, int(240 * fl)), outline=(255, 190, 60, int(255 * fl)), width=6)
            d.ellipse((x - 46, cy - 46, x + 46, cy + 46), fill=(255, 255, 255, int(250 * fl)))
        for i in range(3):
            rr = 80 + (g + i * 0.22) * 300
            al = int(230 * max(0.0, 1 - g - i * 0.2))
            if al > 0:
                d.ellipse((x - rr, cy - rr, x + rr, cy + rr), outline=(255, 255, 255, al), width=12)


def p_ping(d, x, t, s=1.0):
    """Ortungs-Signal eines Senders am Boden (Blackbox): Ringe steigen vom Gerät auf, werden größer und verblassen."""
    cy = GROUND - 150
    for i in range(4):
        ph = (t * 0.55 + i / 4) % 1
        rr = 110 + ph * 400
        d.arc((x - rr, cy - rr, x + rr, cy + rr), 200, 340, fill=(120, 244, 220, int(235 * (1 - ph) ** 0.8)), width=13)


# ------------------------------------------------------------------ Heißluftballon (Ballonflucht, Ballonfahrt)
BALLOON_COLS = ((214, 70, 60), (246, 196, 56), (70, 130, 200), (238, 236, 226), (90, 170, 110), (236, 140, 50), (150, 100, 180), (120, 190, 220))
_HEADS = (((250, 214, 180), (92, 60, 40)), ((240, 196, 160), (40, 36, 40)), ((250, 220, 190), (190, 140, 60)), ((232, 184, 150), (120, 70, 40)))
_SHIRTS = ((120, 124, 136), (70, 110, 190), (190, 80, 70), (90, 150, 110))


def _rot(pivot, deg):
    """Punkt-Abbildung: Drehung um pivot (Grad, im Uhrzeigersinn auf dem Bildschirm)."""
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    px_, py_ = pivot
    return lambda x, y: (px_ + (x - px_) * ca - (y - py_) * sa, py_ + (x - px_) * sa + (y - py_) * ca)


def _flame(d, tr, cx, y0, hgt, wd, t):
    """Brennerflamme von (cx, y0) nach oben (drei Farbschichten, flackert)."""
    for i, (col, sc) in enumerate((((236, 84, 40), 1.0), ((250, 150, 44), 0.7), ((255, 226, 110), 0.42))):
        fl = 1 + 0.14 * math.sin(t * 12 + i * 2)
        h_, w_ = hgt * sc * fl, wd * sc
        tip = cx + math.sin(t * 8 + i) * wd * 0.3
        pts = [tr(cx - w_, y0), tr(cx - w_ * 0.9, y0 - h_ * 0.5), tr(tip, y0 - h_), tr(cx + w_ * 0.9, y0 - h_ * 0.5), tr(cx + w_, y0), tr(cx, y0 + w_ * 0.4)]
        d.polygon(pts, fill=col, outline=INK if i == 0 else None, width=max(2, int(wd * 0.12)) if i == 0 else 0)


def _basket(d, tr, cx, gy, R, t, people=8, flame=1.0, mouth_y=None):
    """Offene Plattform-Gondel wie bei selbstgebauten Ballons: Stahlplatte, vier Eckpfosten, Seil als Geländer, in der Mitte die
    Gasflaschen mit Brenner; dicht gedrängt die Fahrgäste (people: 0, 4 oder 8 – Erwachsene hinten, Kinder vorn)."""
    gw, py = 0.36 * R, gy + 0.38 * R
    lw = max(2, int(R * 0.022))

    def quad(x0, y0, x1, y1, col, o=lw):
        d.polygon([tr(x0, y0), tr(x1, y0), tr(x1, y1), tr(x0, y1)], fill=col, outline=INK, width=o)

    for bx in ((-0.09, 0.09) if people else (-0.24, -0.09, 0.09, 0.24)):              # Gasflaschen (leer sieht man alle vier) und Brennerrohr
        quad(cx + (bx - 0.065) * R, gy + 0.08 * R, cx + (bx + 0.065) * R, py, (150, 160, 176))
        quad(cx + (bx - 0.03) * R, gy + 0.03 * R, cx + (bx + 0.03) * R, gy + 0.08 * R, (96, 104, 122))
    d.line([tr(cx, gy + 0.05 * R), tr(cx, gy - 0.16 * R)], fill=INK, width=max(4, int(R * 0.05)))
    quad(cx - 0.07 * R, gy - 0.2 * R, cx + 0.07 * R, gy - 0.13 * R, (96, 104, 122))
    if flame > 0:
        top = (mouth_y if mouth_y is not None else gy - 0.5 * R)
        _flame(d, tr, cx, gy - 0.2 * R, (gy - 0.2 * R - top) * (0.75 + 0.35 * flame), 0.085 * R * (0.8 + 0.3 * flame), t)
    if people:
        ad = (-0.25, 0.25) if people <= 4 else (-0.27, -0.1, 0.1, 0.27)
        kd = (-0.12, 0.12) if people <= 4 else (-0.19, -0.02, 0.02 + 0.0, 0.19)
        hr = 0.085 * R
        for i, ox in enumerate(ad):                                                   # Erwachsene: Oberkörper und Kopf über dem Geländer
            skin, hair = _HEADS[i % 4]
            hx, hy = cx + ox * R, gy - 0.02 * R + math.sin(t * 2.2 + i * 1.7) * 0.012 * R
            quad(hx - hr * 0.95, hy + hr * 0.7, hx + hr * 0.95, py, _SHIRTS[i % 4])
            c = tr(hx, hy)
            d.ellipse((c[0] - hr, c[1] - hr, c[0] + hr, c[1] + hr), fill=skin, outline=INK, width=lw)
            d.chord((c[0] - hr, c[1] - hr, c[0] + hr, c[1] + hr), 180, 360, fill=hair, outline=INK, width=lw)
            if hr >= 12:
                for sx in (-0.36, 0.36):
                    d.ellipse((c[0] + sx * hr - hr * 0.13, c[1] + hr * 0.14, c[0] + sx * hr + hr * 0.13, c[1] + hr * 0.4), fill=INK)
        kr = hr * 0.72
        for i, ox in enumerate(kd[:max(0, people - len(ad))]):                        # Kinder: kleiner, eine Reihe tiefer
            skin, hair = _HEADS[(i + 2) % 4]
            hx, hy = cx + ox * R + (0.0 if people <= 4 else (-0.03 if i == 1 else 0.03 if i == 2 else 0)) * R, gy + 0.2 * R
            quad(hx - kr * 0.9, hy + kr * 0.7, hx + kr * 0.9, py, _SHIRTS[(i + 1) % 4])
            c = tr(hx, hy)
            d.ellipse((c[0] - kr, c[1] - kr, c[0] + kr, c[1] + kr), fill=skin, outline=INK, width=lw)
            d.chord((c[0] - kr, c[1] - kr, c[0] + kr, c[1] + kr), 180, 360, fill=hair, outline=INK, width=lw)
            if kr >= 12:
                for sx in (-0.36, 0.36):
                    d.ellipse((c[0] + sx * kr - kr * 0.14, c[1] + kr * 0.14, c[0] + sx * kr + kr * 0.14, c[1] + kr * 0.42), fill=INK)
    for ry in (0.1, 0.24):                                                            # Geländer: Wäscheleine zwischen den Pfosten
        d.line([tr(cx - gw, gy + ry * R), tr(cx + gw, gy + ry * R)], fill=INK, width=max(3, int(R * 0.03)))
        d.line([tr(cx - gw, gy + ry * R), tr(cx + gw, gy + ry * R)], fill=(226, 204, 150), width=max(1, int(R * 0.014)))
    for sx in (-1, 1):                                                                # Eckpfosten
        quad(cx + sx * gw - 0.022 * R, gy - 0.02 * R, cx + sx * gw + 0.022 * R, py, (120, 126, 140))
    quad(cx - gw - 0.05 * R, py, cx + gw + 0.05 * R, py + 0.075 * R, (150, 156, 170))  # Plattform


def _balloon(d, cx, top, k, t, flame=1.0, rot=0.0, sag=0.0, people=8):
    """Selbstgenähter Heißluftballon: Hülle aus bunten Stoffbahnen, Seile, darunter die Plattform-Gondel mit Brenner.
    cx = Mitte, top = Scheitel der Hülle, k = Maßstab (1 → Hülle 500 px breit); rot = Schräglage in Grad um die Gondel,
    sag = 0..1 (schlaffe, einfallende Hülle, wenn die heiße Luft fehlt)."""
    R = 250.0 * k
    cy = top + R
    my, mw = 1.25 * R, 0.2 * R
    gy = cy + my + 0.5 * R
    tr = _rot((cx, gy + 0.3 * R), rot)

    def half(yy):
        if yy <= 0:
            w_ = math.sqrt(max(0.0, R * R - yy * yy))
        else:
            w_ = mw + (R - mw) * (0.5 + 0.5 * math.cos(math.pi * yy / my)) ** 0.85
        if sag:
            w_ *= 1 - 0.2 * sag + 0.07 * sag * math.sin(yy / R * 7 + t * 6)
        return w_

    def yy_s(yy):                                                                     # schlaffe Hülle: der Scheitel sackt ein
        return yy * (1 - 0.28 * sag) if yy < 0 else yy

    ys = [-R + i * (R + my) / 30 for i in range(31)]
    n = 8
    us = [math.sin(-math.pi / 2 + j * math.pi / n) for j in range(n + 1)]
    out = [tr(cx - half(y), cy + yy_s(y)) for y in ys] + [tr(cx + half(y), cy + yy_s(y)) for y in reversed(ys)]
    d.polygon(out, fill=INK)
    warm = [y for y in ys if y >= my * 0.3]
    for j in range(n):                                                                # Stoffbahnen: links im Licht, rechts im Schatten
        col = BALLOON_COLS[(j * 3) % len(BALLOON_COLS)]
        col = _lt(col, 0.16) if j < 2 else _dk(col, 0.1 + 0.09 * (j - 4)) if j > 4 else col
        if flame <= 0:
            col = _dk(col, 0.34)                                                      # ohne Feuer wird die Hülle dunkel
        d.polygon([tr(cx + us[j] * half(y), cy + yy_s(y)) for y in ys] + [tr(cx + us[j + 1] * half(y), cy + yy_s(y)) for y in reversed(ys)], fill=col)
        if flame > 0:                                                                 # Feuerschein unten in der Hülle (flackert)
            f = 0.3 + 0.08 * math.sin(t * 9)
            glow = tuple(int(col[i] * (1 - f) + (255, 206, 110)[i] * f) for i in range(3))
            d.polygon([tr(cx + us[j] * half(y), cy + yy_s(y)) for y in warm] + [tr(cx + us[j + 1] * half(y), cy + yy_s(y)) for y in reversed(warm)], fill=glow)
    for j in range(1, n):                                                             # Nähte zwischen den Bahnen
        d.line([tr(cx + us[j] * half(y), cy + yy_s(y)) for y in ys], fill=(58, 50, 62), width=max(2, int(4 * k)))
    for fy in (-0.42, 0.3, 0.8):                                                      # Quernähte: zusammengestückelter Stoff
        y = fy * R
        d.line([tr(cx + (i / 12 - 1) * half(y), cy + yy_s(y) + 0.1 * R * (1 - (i / 12 - 1) ** 2)) for i in range(25)], fill=(58, 50, 62), width=max(2, int(3 * k)))
    d.line(out + out[:1], fill=INK, width=max(4, int(O * k)), joint="curve")
    m = [tr(cx - mw, cy + my), tr(cx + mw, cy + my)]
    d.line(m, fill=INK, width=max(6, int(0.07 * R)))
    d.line(m, fill=(96, 60, 44), width=max(2, int(0.035 * R)))
    gw = 0.36 * R
    for sx in (-1, 1):                                                                # Seile zur Gondel
        for ex, ey in ((mw, my), (half(my * 0.86), my * 0.86)):
            d.line([tr(cx + sx * ex, cy + ey), tr(cx + sx * gw, gy)], fill=INK, width=max(2, int(4 * k)))
    _basket(d, tr, cx, gy, R, t, people, flame, cy + my)


def _mound(d, x0, x1, gy, hgt, t, limp=1.0):
    """Schlaffe Ballonhülle am Boden: gestreifter Stoffberg von x0 bis x1 (Fußlinie gy)."""
    n, st = 6, 28

    def prof(s):
        return hgt * (math.sin(math.pi * s) ** 0.55) * (1 + 0.05 * limp * math.sin(s * 15 + t * 2.4)) * (0.7 + 0.3 * math.sin(math.pi * min(1.0, s * 1.3)) ** 2)

    xs = [x0 + (x1 - x0) * i / st for i in range(st + 1)]
    top = [(x, gy - prof(i / st)) for i, x in enumerate(xs)]
    d.polygon(top + [(x1, gy + 6), (x0, gy + 6)], fill=INK)
    for j in range(n):
        lo = [(x, gy - prof(i / st) * j / n) for i, x in enumerate(xs)]
        hi = [(x, gy - prof(i / st) * (j + 1) / n) for i, x in enumerate(xs)]
        d.polygon(lo + hi[::-1], fill=_dk(BALLOON_COLS[(j * 3 + 1) % len(BALLOON_COLS)], 0.05 * (n - j)))
        d.line(hi, fill=(58, 50, 62), width=4)
    d.line(top, fill=INK, width=O, joint="curve")
    d.line((x0 - 4, gy + 3, x1 + 4, gy + 3), fill=INK, width=O)


def p_balloon(d, x, t, s=1.0):
    """Heißluftballon in der Luft: die Hülle leuchtet vom Brenner, acht Köpfe drängen sich in der kleinen Gondel."""
    _balloon(d, x + math.sin(t * 0.6) * 8, 420 + math.sin(t * 1.1) * 12, 1.0, t, 0.8 + 0.2 * math.sin(t * 3))


def p_balloon_out(d, x, t, s=1.0):
    """Der Brenner ist aus: schlaffe Hülle, Schräglage, der Ballon sackt durch – Fahrtwind-Striche zeigen nach oben."""
    for i in range(9):
        ph = (t * 1.5 + i * 0.37) % 1
        lx = x + (-430 + i * 108) + (54 if i % 2 else 0)
        if abs(lx - x) < 250 and 0.25 < ph < 0.8:
            continue
        ly = 1400 - ph * 1150
        d.line((lx, ly, lx, ly - 150), fill=(255, 255, 255, int(150 * math.sin(math.pi * ph))), width=9)
    _balloon(d, x - 70 + math.sin(t * 5) * 10, 440 + math.sin(t * 3.1) * 16, 1.0, t, 0.0, 10 + 4 * math.sin(t * 2.3), 0.85)


def p_balloon_dark(d, x, t, s=1.0):
    """Das Gas ist aus: keine Flamme mehr, die Hülle wird dunkel und beginnt einzufallen."""
    _balloon(d, x + math.sin(t * 0.9) * 10, 425 + math.sin(t * 1.4) * 12, 1.0, t, 0.0, 3 * math.sin(t * 1.1), 0.35)


def p_balloon_fill(d, x, t, s=1.0):
    """Start auf der Wiese: Der Brenner faucht, die Hülle bläht sich auf und richtet sich auf – die Gondel steht noch am Boden."""
    k = 0.86
    R = 250 * k
    _balloon(d, x, GROUND - 3.42 * R, k, t, 1.7, -13 + 3 * math.sin(t * 1.3), 0.22, 0)


def p_balloon_ground(d, x, t, s=1.0):
    """Aufbau auf der Wiese: Die Hülle liegt als bunter Stoffberg im Gras, daneben steht die Gondel mit den Gasflaschen."""
    _mound(d, x - 470, x + 150, GROUND + 4, 250, t)
    R = 250 * 0.9
    gy = GROUND - 0.455 * R
    tr = _rot((x, gy), 0)
    for sx in (-1, 1):
        d.line([(x + 150, GROUND - 30), tr(x + 300 + sx * 0.36 * R, gy)], fill=INK, width=4)
    _basket(d, tr, x + 300, gy, R, t, 0, 0.0)


def p_balloon_down(d, x, t, s=1.0):
    """Nach der Landung: Die Hülle hängt zerknittert im Gebüsch, die Gondel steht schief im Gras."""
    _blobs(d, [(x - 330, GROUND - 90, 96), (x - 190, GROUND - 130, 120), (x - 30, GROUND - 100, 104), (x + 110, GROUND - 70, 80)], (62, 128, 78))
    _mound(d, x - 400, x + 90, GROUND - 120, 190, t * 0.3, 2.0)
    for bx, by, br in ((x - 300, GROUND - 40, 60), (x - 120, GROUND - 30, 54), (x + 40, GROUND - 34, 50)):
        _blobs(d, [(bx, by, br), (bx + br * 0.9, by + 8, br * 0.7)], (74, 146, 88), 5)
    R = 250 * 0.9
    gy = GROUND - 0.5 * R
    tr = _rot((x + 290, GROUND), 14)
    for sx in (-1, 1):
        d.line([(x + 60, GROUND - 150), tr(x + 290 + sx * 0.36 * R, gy)], fill=INK, width=4)
    _basket(d, tr, x + 290, gy, R, t, 0, 0.0)


def p_gondola(d, x, t, s=1.0):
    """Die Gondel ganz nah: acht Menschen auf einer winzigen Plattform, über ihnen die Öffnung der Hülle mit der Flamme."""
    R = 620.0
    _balloon(d, x, 760 - 2.75 * R + math.sin(t * 1.1) * 8, R / 250.0, t, 0.8 + 0.2 * math.sin(t * 3))


def p_gondola_empty(d, x, t, s=1.0):
    """Die leere Gondel groß auf der Wiese: Blechplatte, Eckpfosten, Wäscheleine als Geländer, in der Mitte die Gasflaschen mit dem Brenner."""
    R = 560.0
    gy = GROUND - 0.455 * R
    _basket(d, _rot((x, gy), 0), x, gy, R, t, 0, 0.0)


def p_searchlight(d, x, t, s=1.0):
    """Suchscheinwerfer vom Boden: zwei Lichtkegel schwenken über den Nachthimmel und kreuzen sich am Ziel."""
    for bx, ph, by in ((120, 0.0, 1790), (960, 1.9, 1830)):
        txx = x + math.sin(t * 0.9 + ph) * 150
        ty = 760.0
        dx, dy = txx - bx, ty - by
        ln = math.hypot(dx, dy)
        ux, uy = dx / ln, dy / ln
        ex, ey = bx + ux * 2200, by + uy * 2200
        nx, ny = -uy, ux
        for wd, al in ((150, 44), (86, 50)):
            d.polygon([(bx - nx * 16, by - ny * 16), (bx + nx * 16, by + ny * 16), (ex + nx * wd * 2.2, ey + ny * wd * 2.2), (ex - nx * wd * 2.2, ey - ny * wd * 2.2)], fill=(255, 246, 196, al))
        _r(d, (bx - 44, by - 20, bx + 44, by + 56), (70, 76, 92), 10)
        _o(d, (bx - 30, by - 44, bx + 30, by + 8), (255, 244, 180), 5, False)


def p_sewing(d, x, t, s=1.0):
    """Alte Nähmaschine auf einem Tisch: die Nadel rattert, bunte Stoffbahnen laufen darunter durch und türmen sich am Boden."""
    ty = GROUND - 250
    for i, col in enumerate(BALLOON_COLS[:4]):                                          # Stoffberg neben dem Tisch
        _o(d, (x + 150 - i * 26, GROUND - 70 - i * 44, x + 400 - i * 34, GROUND + 6 - i * 40), col)
    for lx in (-200, 150):
        _r(d, (x + lx, ty, x + lx + 36, GROUND), (150, 104, 70), 4)
    _r(d, (x - 250, ty - 34, x + 240, ty + 6), (176, 124, 84), 8)
    _poly(d, [(x - 250, ty - 40), (x + 250, ty - 40), (x + 330, GROUND - 150), (x + 200, GROUND - 150), (x + 170, ty - 14), (x - 250, ty - 14)], BALLOON_COLS[1], shade=0)
    _poly(d, [(x - 250, ty - 40), (x - 60, ty - 40), (x - 60, ty - 14), (x - 250, ty - 14)], BALLOON_COLS[0], shade=0)
    _r(d, (x - 190, ty - 76, x + 150, ty - 40), (44, 44, 52), 10)                         # Maschine: Sockel, Säule, Arm, Kopf
    _r(d, (x + 60, ty - 250, x + 150, ty - 66), (44, 44, 52), 16)
    _r(d, (x - 170, ty - 250, x + 150, ty - 180), (44, 44, 52), 22)
    _r(d, (x - 180, ty - 250, x - 110, ty - 130), (44, 44, 52), 12)
    d.line((x - 60, ty - 216, x + 40, ty - 216), fill=(226, 190, 90), width=6)            # Zierlinie
    ny = ty - 130 + (math.sin(t * 26) * 0.5 + 0.5) * 44
    d.line((x - 145, ty - 130, x - 145, ny + 44), fill=(210, 214, 224), width=7)          # Nadel
    _o(d, (x + 130, ty - 240, x + 210, ty - 160), (150, 156, 170), 6)                     # Handrad
    a = t * 9
    d.line((x + 170, ty - 200, x + 170 + math.cos(a) * 30, ty - 200 + math.sin(a) * 30), fill=INK, width=6)
    _o(d, (x - 30, ty - 292, x + 6, ty - 250), (236, 236, 228), 5, False)                 # Garnrolle


def p_fabric(d, x, t, s=1.0):
    """Stoffballen: bunte Rollen, gestapelt."""
    for i, (ox, oy, col) in enumerate(((-110, 0, BALLOON_COLS[2]), (110, 0, BALLOON_COLS[0]), (0, -116, BALLOON_COLS[1]))):
        cx, cy = x + ox, GROUND - 62 + oy
        _r(d, (cx - 150, cy - 58, cx + 150, cy + 58), col, 56)
        _o(d, (cx + 96, cy - 58, cx + 204, cy + 58), _lt(col, 0.25), O, False)
        d.ellipse((cx + 132, cy - 20, cx + 168, cy + 20), fill=(120, 96, 70), outline=INK, width=4)


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
         "eclipse": p_eclipse, "sprout": p_sprout, "moss": p_moss, "shield": p_shield, "tree": p_tree, "rock": p_rock, "box": p_box, "car": p_car, "police": p_police, "ambulance": p_ambulance, "fire": p_fire, "tv": p_tv, "computer": p_computer,
         "money": p_money, "rocket": p_rocket, "ufo": p_ufo, "meteor": p_meteor, "explosion": p_explosion, "earth": p_earth,
         "sun": p_bigsun, "moon": p_bigmoon, "tornado": p_tornado, "wave": p_wave, "ice": p_ice, "volcano": p_volcano,
         "cart": p_cart, "candle": p_candle, "bus": p_bus, "truck": p_truck, "house": p_house, "trafficlight": p_trafficlight,
         "canister": p_canister, "cans": p_cans, "generator": p_generator, "bike": p_bike, "shelf": p_shelf, "table": p_table,
         "drone": p_drone, "cctv": p_cctv, "door": p_door, "clock": p_clock, "pile": p_pile, "sandpile": p_sandpile, "trash": p_trash, "faucet": p_faucet,
         "glass": p_glass, "barrel": p_barrel, "solarpanel": p_solarpanel,
         "fridge": p_fridge, "tent": p_tent, "streetlamp": p_streetlamp, "plane": p_plane, "satellite": p_satellite, "ship": p_ship, "aquarium": p_aquarium}
PROP_ALIASES = {"tuer": "door", "türe": "door", "türen": "door", "haustür": "door", "zimmertür": "door", "krankenwagen": "ambulance", "rettungswagen": "ambulance", "notarzt": "ambulance", "polizeiauto": "police", "streifenwagen": "police", "polizei": "police", "police car": "police",
                "baum": "tree", "stein": "rock", "kiste": "box", "auto": "car", "feuer": "fire", "fernseher": "tv", "pc": "computer",
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
                "solarzelle": "solarpanel", "pflanze": "sprout", "plant": "sprout", "schutzschild": "shield", "moos": "moss", "moospolster": "moss", "mooskissen": "moss", "flechte": "moss", "comet": "meteor", "komet": "meteor", "welle": "wave", "eisberg": "ice", "vulkan": "volcano", "bigsun": "sun",
                "fischglas": "aquarium", "goldfischglas": "aquarium", "aquarien": "aquarium", "fischbecken": "aquarium", "fish tank": "aquarium", "fishtank": "aquarium"}
FRONT = ("wave", "flood", "eclipse")
BEHIND = ("sun", "moon", "earth", "cloud", "stormcloud", "aurora")      # stehen am Himmel hinter Häusern, Bergen und Bäumen
SKY = ("drone", "earth", "sun", "moon", "ufo", "meteor", "aurora", "eclipse", "lightning", "cloud", "stormcloud", "plane", "satellite")     # werden vor den Figuren gezeichnet
def p_ship_ice(d, x, t, s=1.0):
    """Großes Containerschiff, im Eis eingefroren (nur von der Regie gesetzt – zugefrorenes Meer): liegt leicht schief, bewegt sich nicht,
    rundum aufgeschobene Eisschollen am Rumpf."""
    y = FAR + 150
    a = math.radians(-4)

    def R(px_, py_):
        return x + px_ * math.cos(a) - py_ * math.sin(a), y + px_ * math.sin(a) + py_ * math.cos(a)

    _poly(d, [R(-400, -150), R(420, -150), R(350, 10), R(-350, 10)], (52, 66, 104))                       # Rumpf
    d.polygon([R(-392, -40), R(380, -40), R(350, 10), R(-350, 10)], fill=(170, 60, 54))                     # Unterwasseranstrich
    d.line((*R(-398, -112), *R(404, -112)), fill=(236, 238, 244), width=9)
    _poly(d, [R(-380, -330), R(-250, -330), R(-250, -150), R(-380, -150)], (240, 240, 244))                # Brücke
    for i in range(3):
        d.rectangle((*R(-366 + i * 40, -310), *R(-340 + i * 40, -288)), fill=(120, 190, 240), outline=INK, width=3)
    _poly(d, [R(-340, -400), R(-296, -400), R(-296, -330), R(-340, -330)], (214, 70, 60))                  # Schornstein
    cols = ((214, 90, 60), (70, 130, 200), (240, 190, 70), (90, 170, 120), (150, 110, 190))
    for row in range(3):                                                                                    # Containerstapel
        for i in range(6 - row):
            x0 = -220 + i * 100 + row * 50
            _poly(d, [R(x0, -150 - row * 56 - 56), R(x0 + 96, -150 - row * 56 - 56), R(x0 + 96, -150 - row * 56), R(x0, -150 - row * 56)], cols[(i + row * 2) % 5], 5)
    for fx, w, h in ((-380, 120, 90), (-210, 150, 60), (-30, 130, 104), (150, 160, 70), (330, 130, 96), (-460, 90, 50), (450, 100, 56)):   # Schollen, die sich am Rumpf auftürmen
        _poly(d, [(x + fx - w / 2, y + 40), (x + fx - w * 0.2, y + 40 - h), (x + fx + w * 0.3, y + 40 - h * 0.6), (x + fx + w / 2, y + 40)], (226, 242, 252), 5)
    for fx in (-300, -60, 220):                                                                            # Eiszapfen an der Bordwand
        d.polygon([R(fx, -112), R(fx + 22, -112), R(fx + 11, -60)], fill=(226, 242, 252), outline=INK)


def p_icehole(d, x, t, s=1.0):
    """Atemloch in der Eisdecke (nur von der Regie gesetzt): dunkles Wasser mit gezackter Eiskante, ein Delfin taucht zum Luftholen auf."""
    y = GROUND + 6
    rim = [(x + math.cos(math.radians(a_)) * (300 + (26 if i % 2 else 0)), y + math.sin(math.radians(a_)) * (86 + (10 if i % 2 else 0))) for i, a_ in enumerate(range(0, 360, 20))]
    d.polygon(rim, fill=(236, 246, 252), outline=INK, width=O)
    d.ellipse((x - 250, y - 62, x + 250, y + 62), fill=(24, 70, 110), outline=INK, width=6)
    d.ellipse((x - 236, y - 40, x + 236, y + 62), fill=(34, 96, 146))
    up = (math.sin(t * 1.6) * 0.5 + 0.5) * 60                                                               # taucht auf und ab
    col, belly = (112, 142, 172), (236, 242, 248)
    top = y - 270 - up
    d.rounded_rectangle((x + 40, top + 96, x + 214, top + 150), 27, fill=INK)                               # Schnabel
    d.rounded_rectangle((x + 46, top + 102, x + 208, top + 144), 21, fill=col)
    d.line((x + 110, top + 128, x + 204, top + 126), fill=INK, width=5)
    d.ellipse((x - 118, top - 8, x + 118, y + 58), fill=INK)                                               # Kopf und Rumpf ragen aus dem Wasser
    d.ellipse((x - 110, top, x + 110, y + 50), fill=_dk(col))
    d.ellipse((x - 100, top + 4, x + 110, y + 44), fill=col)
    d.ellipse((x - 10, top + 120, x + 104, y + 46), fill=belly)                                            # heller Bauch
    d.rounded_rectangle((x + 46, top + 102, x + 150, top + 144), 21, fill=col)                              # Schnabelansatz ohne Naht
    d.arc((x + 60, top + 96, x + 150, top + 150), 20, 110, fill=INK, width=5)                               # Lächeln
    d.ellipse((x + 30, top + 54, x + 66, top + 90), fill=(255, 255, 255), outline=INK, width=4)
    d.ellipse((x + 44, top + 64, x + 60, top + 80), fill=INK)
    d.ellipse((x + 50, top + 66, x + 56, top + 72), fill=(255, 255, 255))
    d.ellipse((x + 4, top + 104, x + 34, top + 122), fill=(255, 120, 130, 110))                             # Wangenrot
    d.ellipse((x - 22, top + 2, x + 8, top + 18), fill=(40, 60, 90))                                        # Blasloch
    d.chord((x - 236, y - 40, x + 236, y + 62), 0, 180, fill=(34, 96, 146))                                 # Wasser vor dem Tier
    for i in range(5):                                                                                      # Atemwolke
        ph = (t * 0.9 + i / 5) % 1
        r = 14 + ph * 34
        d.ellipse((x - 8 + (i - 2) * 16 * ph - r, top - 30 - ph * 150 - r, x - 8 + (i - 2) * 16 * ph + r, top - 30 - ph * 150 + r), fill=(240, 248, 255, int(190 * (1 - ph))))
    d.arc((x - 250, y - 62, x + 250, y + 62), 20, 160, fill=(200, 232, 250), width=8)                       # Wasserkante vor dem Tier
    for wx in (-150, 150):
        d.arc((x + wx - 60, y + 6, x + wx + 60, y + 36), 180, 360, fill=(200, 232, 250), width=6)


PROPS["ship_ice"] = p_ship_ice                             # eingefrorenes Containerschiff (nur von der Regie gesetzt)
PROPS["icehole"] = p_icehole                               # Atemloch im Eis mit Delfin (nur von der Regie gesetzt)
PROPS["debris"] = p_debris                                 # Treibgut auf dem Meer (nur von der Regie gesetzt)
PROPS["tank"] = p_tank                                     # Forschungsbecken mit Krebs (nur von der Regie gesetzt)
PROPS["cavitation"] = p_cavitation                         # Kavitationsblase vor der Keule (nur von der Regie gesetzt)
PROPS["ping"] = p_ping                                     # Signal-Ringe über einem Sender (nur von der Regie gesetzt)
PROPS["submersible"] = p_submersible                       # Tauchboot mit Sonar: schwebt wie die Himmels-Dinge frei im Bild (unter Wasser)
PROP_ALIASES.update({"sonar": "submersible", "tauchboot": "submersible", "tauchboote": "submersible", "u-boot": "submersible", "uboot": "submersible",
                     "unterseeboot": "submersible", "tauchroboter": "submersible", "tiefseeroboter": "submersible", "submarine": "submersible"})
SKY += ("submersible", "ping", "cavitation")
PROPS.update({"balloon": p_balloon, "balloon_out": p_balloon_out, "balloon_dark": p_balloon_dark, "balloon_fill": p_balloon_fill, "balloon_ground": p_balloon_ground, "balloon_down": p_balloon_down,
              "gondola": p_gondola, "gondola_empty": p_gondola_empty, "searchlight": p_searchlight, "sewing": p_sewing, "fabric": p_fabric})
PROP_ALIASES.update({"heißluftballon": "balloon", "heissluftballon": "balloon", "hot air balloon": "balloon", "fesselballon": "balloon", "ballonhülle": "balloon_ground",
                     "gondel": "gondola", "ballongondel": "gondola", "ballonkorb": "gondola", "suchscheinwerfer": "searchlight", "flakscheinwerfer": "searchlight",
                     "nähmaschine": "sewing", "naehmaschine": "sewing", "sewing machine": "sewing", "stoffballen": "fabric", "stoffrollen": "fabric", "stoffbahnen": "fabric"})
SKY += ("balloon", "balloon_out", "balloon_dark", "gondola", "searchlight")     # Ballon in der Luft: schwebt frei im Bild (die Regie setzt ihn vor den hohen Himmel)
BALLOON_KINDS = ("balloon", "balloon_out", "balloon_dark", "gondola_empty", "balloon_fill", "balloon_ground", "balloon_down", "gondola", "searchlight")


def p_goosebumps(d, x, t, s=1.0):
    """Gänsehaut als Schaubild: Hautschnitt mit drei Haaren. Die kleinen Haarbalgmuskeln (rot) ziehen sich zusammen, die Haare richten sich
    auf und die Haut wölbt sich an jedem Haar zu einem Hügel (Wörter Gänsehaut, Haarwurzel, Haarbalg, Härchen – stage.GOOSE_RE)."""
    e = max(0.0, min(1.0, (t - 0.55) / 0.35))
    e = e * e * (3 - 2 * e)
    tremble = math.sin(t * 22) * 1.6 * e                                                           # aufgerichtet zittern die Haare leicht
    ys, bot = GROUND - 300, GROUND - 44
    for lx in (-200, 200):                                                                         # Schautafel auf zwei Beinen: liest sich als Schaubild, nicht als Möbel
        _r(d, (x + lx - 12, GROUND - 60, x + lx + 12, GROUND), (110, 118, 134), 5, 5)
    _r(d, (x - 290, ys - 216, x + 290, bot + 26), (60, 110, 190), 30)
    d.rounded_rectangle((x - 268, ys - 194, x + 268, bot + 4), 18, fill=(236, 244, 252), outline=INK, width=5)
    _r(d, (x - 236, ys + 10, x + 236, bot), (244, 214, 150), 22)                                   # Fettgewebe (unten)
    for i in range(7):
        d.ellipse((x - 214 + i * 62, bot - 58 + (i % 2) * 10, x - 166 + i * 62, bot - 16 + (i % 2) * 10), fill=(250, 228, 176))
    _r(d, (x - 236, ys + 6, x + 236, ys + 176), (240, 160, 150), 16)                                # Lederhaut
    skin, skin_d = (240, 196, 164), (214, 160, 128)
    top = [(x - 236, ys + 44), (x - 236, ys)]
    for i in range(48):                                                                            # Oberhaut mit Hügeln an den Haaren
        px_ = x - 236 + 472 * i / 47
        bump = sum(math.exp(-((px_ - (x + hx)) / 34) ** 2) for hx in (-140, 0, 140)) * 20 * e
        top.append((px_, ys - bump))
    top += [(x + 236, ys), (x + 236, ys + 44)]
    d.polygon(top, fill=skin_d, outline=INK, width=O)
    d.polygon([(a, b + 5) for a, b in top[1:-1]] + [(x + 230, ys + 30), (x - 230, ys + 30)], fill=skin)
    for hx in (-140, 0, 140):
        ex, ey = x + hx, ys - 20 * e
        a = math.radians(40 * (1 - e) + 4 * e + tremble)
        ux, uy = math.sin(a), -math.cos(a)
        tip = (ex + ux * 128, ey + uy * 128)
        bulb = (ex - ux * 132, ey - uy * 132)
        m1, m2 = (ex - ux * 100, ey - uy * 100), (ex + 74, ys + 38)                                   # Haarbalgmuskel: vom Haarbalg schräg hoch unter die Oberhaut
        mw = int(15 + 11 * e)
        mc = (226, 70 + int(20 * (1 - e)), 76)
        d.line((*m1, *m2), fill=INK, width=mw + 10)
        d.line((*m1, *m2), fill=mc, width=mw)
        d.line((m1[0] + 5, m1[1] - 4, m2[0] - 6, m2[1] - 4), fill=_lt(mc, 0.35), width=max(3, mw // 4))
        d.line((*bulb, ex, ey), fill=INK, width=30)                                                # Haarbalg (Scheide um die Wurzel)
        d.line((*bulb, ex, ey), fill=(250, 226, 206), width=18)
        d.ellipse((bulb[0] - 21, bulb[1] - 21, bulb[0] + 21, bulb[1] + 21), fill=(150, 96, 70), outline=INK, width=5)   # Haarzwiebel
        d.line((*bulb, *tip), fill=INK, width=17)                                                  # Haar
        d.line((*bulb, *tip), fill=(104, 70, 52), width=8)
        if e > 0.6:                                                                                # kurze Zuck-Striche am Muskel
            k = (e - 0.6) / 0.4
            for j, (ox, oy) in enumerate(((40, -34), (64, -10))):
                d.line((m2[0] + ox * 0.5, m2[1] + oy * 0.5 + 60, m2[0] + ox * (0.5 + 0.5 * k), m2[1] + oy * (0.5 + 0.5 * k) + 60), fill=(226, 70, 76), width=6)


PROPS["goosebumps"] = p_goosebumps                         # Schaubild Gänsehaut: Haare richten sich auf (Regie: stage.GOOSE_RE)
PROP_ALIASES.update({"gänsehaut": "goosebumps", "haarwurzel": "goosebumps", "haarwurzeln": "goosebumps", "haarbalgmuskel": "goosebumps", "haarbalg": "goosebumps",
                     "härchen": "goosebumps", "goose bumps": "goosebumps"})


def _board(d, x):
    """Schautafel auf zwei Beinen wie bei p_goosebumps; gibt (linke Kante, Oberkante, rechte Kante, Unterkante) der hellen Fläche zurück."""
    ys, bot = GROUND - 300, GROUND - 44
    for lx in (-200, 200):
        _r(d, (x + lx - 12, GROUND - 60, x + lx + 12, GROUND), (110, 118, 134), 5, 5)
    _r(d, (x - 290, ys - 216, x + 290, bot + 26), (60, 110, 190), 30)
    d.rounded_rectangle((x - 268, ys - 194, x + 268, bot + 4), 18, fill=(226, 238, 250), outline=INK, width=5)
    return x - 262, ys - 188, x + 262, bot - 2


def p_fur(d, x, t, s=1.0):
    """Fell als Schaubild (Ausbau 17.11.2026): Hautschnitt mit dichtem Fell. Erst liegen die Haare flach und die Kälte (blaue Pfeile) kommt bis
    an die Haut; dann richten sie sich auf und schließen eine warme Luftschicht ein (orange), an der die Kälte abprallt.
    Wörter Luftschicht, Luftpolster, Fell stellt sich auf – stage.FUR_RE."""
    e = max(0.0, min(1.0, (t - 0.6) / 0.45))
    e = e * e * (3 - 2 * e)
    x0, y0, x1, y1 = _board(d, x)
    skin_y = y1 - 96
    _r(d, (x0 + 14, skin_y + 30, x1 - 14, y1 - 6), (240, 160, 150), 14)                             # Lederhaut
    _r(d, (x0 + 14, skin_y, x1 - 14, skin_y + 40), (240, 196, 164), 12)                             # Oberhaut
    L = 156
    air = 150 * e                                                                                   # Höhe der eingeschlossenen Luftschicht
    if e > 0.02:
        top = [(x0 + 22, skin_y)]
        for i in range(25):
            px_ = x0 + 22 + (x1 - x0 - 44) * i / 24
            top.append((px_, skin_y - air - 8 * math.sin(i * 0.9 + t * 3)))
        top.append((x1 - 22, skin_y))
        d.polygon(top, fill=(255, 164, 56, int(235 * e)))
        d.polygon([(a, skin_y - (skin_y - b) * 0.55) for a, b in top], fill=(255, 218, 128, int(215 * e)))
        for i, wx in enumerate((-150, -10, 130)):                                                   # Wärme steigt von der Haut auf und bleibt im Fell
            ph = (t * 0.7 + i * 0.37) % 1
            wy = skin_y - 22 - ph * max(10.0, air - 60)
            pts = [(x + wx + 30 + math.sin(j * 1.3 + t * 5 + i) * 9, wy - j * 9) for j in range(6)]
            d.line(pts, fill=(226, 84, 50, int(230 * e * (1 - ph * 0.6))), width=7, joint="curve")
    n = 13
    for i in range(n):                                                                              # dichtes Fell: liegt flach, richtet sich auf (leicht gefächert, damit es die Tafel füllt)
        rx = x0 + 40 + (x1 - x0 - 214) * i / (n - 1)
        a = math.radians(60 * (1 - e) + (-8 + 40 * i / (n - 1)) * e + math.sin(t * 20 + i) * 1.2 * e)
        ln = L * (0.92 + 0.08 * math.sin(i * 1.7))
        tip = (rx + math.sin(a) * ln, skin_y + 6 - math.cos(a) * ln)
        mid = (rx + math.sin(a * 0.8) * ln * 0.5, skin_y + 6 - math.cos(a * 0.8) * ln * 0.5)
        d.line([(rx, skin_y + 14), mid, tip], fill=INK, width=17, joint="curve")
        d.line([(rx, skin_y + 14), mid, tip], fill=(120, 80, 54) if i % 2 else (98, 64, 44), width=9, joint="curve")
        d.ellipse((rx - 11, skin_y + 4, rx + 11, skin_y + 26), fill=(150, 96, 70), outline=INK, width=4)
    stop = skin_y - 60 - (air + 40) * e                                                             # so tief kommt die Kälte
    for i, ax_ in enumerate((-170, 0, 170)):                                                        # Kälte von oben: blaue Pfeile
        bobk = 10 * math.sin(t * 4 + i * 1.7)
        ay = stop - 18 + bobk
        ax = x + ax_
        top_y = max(y0 + 14, ay - 120)
        d.line((ax, top_y, ax, ay - 30), fill=INK, width=24)
        d.polygon([(ax - 34, ay - 40), (ax + 34, ay - 40), (ax, ay + 8)], fill=(70, 150, 230), outline=INK, width=5)
        d.line((ax, top_y + 4, ax, ay - 34), fill=(70, 150, 230), width=14)
        if e > 0.7:                                                                                 # prallt an der Luftschicht ab
            for sx in (-1, 1):
                d.line((ax + sx * 30, ay + 14, ax + sx * 56, ay + 2), fill=(70, 150, 230), width=6)
    for i, (a_, b_, c_) in enumerate(_DROPS[:7]):                                                   # Schneekristalle im kalten Teil
        fx_ = x0 + 30 + a_ * (x1 - x0 - 60)
        fy_ = y0 + 20 + ((b_ + t * 0.12 * (1 + c_)) % 1) * max(20.0, stop - y0 - 110)
        for k_ in range(3):
            an = math.radians(k_ * 60 + i * 20)
            d.line((fx_ - math.cos(an) * 11, fy_ - math.sin(an) * 11, fx_ + math.cos(an) * 11, fy_ + math.sin(an) * 11), fill=(255, 255, 255), width=4)


def p_adrenaline(d, x, t, s=1.0):
    """Adrenalin als Schaubild (Ausbau 17.11.2026): Oberkörper mit Herz und den beiden Nieren; die Nebennieren (gelb, sitzen wie Kappen auf den
    Nieren) pulsieren und schütten Adrenalin aus – orange Tropfen strömen durch die Adern zum Herzen, das schneller schlägt, und weiter in
    den Kopf. Wörter Adrenalin, Nebenniere, Stresshormon – stage.TEXT_PROPS."""
    x0, y0, x1, y1 = _board(d, x)
    body, body_d = (200, 214, 236), (150, 170, 204)
    hy = y0 + 56
    d.rounded_rectangle((x - 30, hy + 20, x + 30, hy + 80), 12, fill=body, outline=body_d, width=6)   # Hals
    d.ellipse((x - 58, hy - 50, x + 58, hy + 50), fill=body, outline=body_d, width=6)               # Kopf
    d.rounded_rectangle((x - 196, hy + 64, x + 196, y1), 76, fill=body, outline=body_d, width=6)    # Rumpf mit Schultern
    d.rectangle((x - 196, y1 - 90, x + 196, y1), fill=body_d)
    d.rectangle((x - 190, y1 - 92, x + 190, y1), fill=body)
    d.rectangle((x - 24, hy + 58, x + 24, hy + 76), fill=body)
    beat = abs(math.sin(t * 9.5)) ** 3
    hx, hyy = x + 10, hy + 132
    kid_y = y1 - 78
    vein = (214, 84, 84)

    def curve(p0, p1, p2, n=10):
        return [((1 - u) ** 2 * p0[0] + 2 * u * (1 - u) * p1[0] + u * u * p2[0], (1 - u) ** 2 * p0[1] + 2 * u * (1 - u) * p1[1] + u * u * p2[1]) for u in (i / n for i in range(n + 1))]
    paths = [curve((x + sx * 122, kid_y - 88), (x + sx * 128, hyy + 10), (hx + sx * 26, hyy + 14)) for sx in (-1, 1)]   # Adern: Nebenniere → Herz
    paths.append(curve((hx, hyy - 20), (x + 14, hy + 70), (x, hy + 8), 6))                          # Herz → Kopf
    for sx in (-1, 1):                                                                              # Nieren (Bohnenform, Einbuchtung zur Mitte)
        kx = x + sx * 122
        _o(d, (kx - 44, kid_y - 46, kx + 44, kid_y + 62), (176, 86, 74), 6)
        nb = (kx - sx * 46 - 20, kid_y - 14, kx - sx * 46 + 20, kid_y + 32)
        d.ellipse(nb, fill=body)
        d.arc(nb, 270 if sx > 0 else 90, 90 if sx > 0 else 270, fill=INK, width=6)
    for pth in paths:
        d.line(pth, fill=_dk(vein, 0.3), width=17, joint="curve")
        d.line(pth, fill=vein, width=9, joint="curve")
    for sx in (-1, 1):                                                                              # Nebennieren: gelbe Kappen, pulsieren und feuern
        kx = x + sx * 122
        pul = 1 + 0.16 * math.sin(t * 9.5 + (0 if sx < 0 else 1.2))
        for an_ in (200, 235, 305, 340):
            ca, sa = math.cos(math.radians(an_)), math.sin(math.radians(an_))
            r0, r1 = 60 + 8 * pul, 70 + 22 * pul
            d.line((kx + ca * r0, kid_y - 60 + sa * r0 * 0.8, kx + ca * r1, kid_y - 60 + sa * r1 * 0.8), fill=(240, 150, 30), width=7)
        d.pieslice((kx - 46 * pul, kid_y - 96 - 6 * pul, kx + 46 * pul, kid_y - 24 + 6 * pul), 180, 360, fill=(250, 190, 50), outline=INK, width=6)
        d.line((kx - 46 * pul, kid_y - 60, kx + 46 * pul, kid_y - 60), fill=INK, width=6)
        d.arc((kx - 30 * pul, kid_y - 86, kx + 8, kid_y - 50), 190, 290, fill=(255, 236, 160), width=5)
    hs = 1 + 0.2 * beat                                                                             # Herz schlägt schnell
    r_ = 27 * hs
    for k_ in range(2):                                                                             # Puls-Ringe ums Herz
        ph = (t * 1.9 + k_ / 2) % 1
        rr_ = 70 + ph * 50
        d.arc((hx - rr_, hyy - rr_ * 0.9, hx + rr_, hyy + rr_ * 0.9 + 16), 200, 340, fill=(226, 60, 76, int(230 * (1 - ph))), width=6)
    d.ellipse((hx - r_ * 2 - 4, hyy - r_ * 1.5 - 4, hx + 4, hyy + r_ * 0.5 + 4), fill=INK)
    d.ellipse((hx - 4, hyy - r_ * 1.5 - 4, hx + r_ * 2 + 4, hyy + r_ * 0.5 + 4), fill=INK)
    d.polygon([(hx - r_ * 1.9 - 6, hyy), (hx + r_ * 1.9 + 6, hyy), (hx, hyy + r_ * 2.1 + 8)], fill=INK)
    d.ellipse((hx - r_ * 2, hyy - r_ * 1.5, hx, hyy + r_ * 0.5), fill=(226, 60, 76))
    d.ellipse((hx, hyy - r_ * 1.5, hx + r_ * 2, hyy + r_ * 0.5), fill=(226, 60, 76))
    d.polygon([(hx - r_ * 1.86, hyy - 2), (hx + r_ * 1.86, hyy - 2), (hx, hyy + r_ * 2.1)], fill=(226, 60, 76))
    d.ellipse((hx - r_ * 1.5, hyy - r_ * 1.1, hx - r_ * 0.8, hyy - r_ * 0.5), fill=(255, 170, 176))
    for pi_, pth in enumerate(paths):                                                               # Adrenalin strömt: Tropfen laufen die Adern entlang
        seg = [max(0.01, math.dist(pth[i], pth[i + 1])) for i in range(len(pth) - 1)]
        tot = sum(seg)
        for j in range(3 if pi_ < 2 else 2):
            ph = (t * 1.2 + j / (3 if pi_ < 2 else 2)) % 1
            dist, i = ph * tot, 0
            while i < len(seg) - 1 and dist > seg[i]:
                dist -= seg[i]
                i += 1
            f_ = min(1.0, dist / seg[i])
            qx, qy = pth[i][0] + (pth[i + 1][0] - pth[i][0]) * f_, pth[i][1] + (pth[i + 1][1] - pth[i][1]) * f_
            d.ellipse((qx - 12, qy - 12, qx + 12, qy + 12), fill=(255, 150, 30), outline=INK, width=4)
            d.ellipse((qx - 6, qy - 7, qx - 1, qy - 2), fill=(255, 226, 150))


def draw_breath(layer, x, y, facing, t, scale=1.0):
    """Atemwolke vor dem Mund (Kälte): kleine weiße Wölkchen lösen sich und verwehen."""
    d = ImageDraw.Draw(layer, "RGBA")
    for i in range(3):
        ph = (t * 0.75 + i / 3) % 1
        r = (12 + ph * 30) * scale
        cx = x + facing * (20 + ph * 110) * scale
        cy = y - ph * 46 * scale + math.sin(t * 3 + i) * 5
        d.ellipse((cx - r, cy - r * 0.8, cx + r, cy + r * 0.8), fill=(246, 250, 255, int(215 * (1 - ph) ** 0.8)))


PROPS["fur"] = p_fur                                       # Schaubild Fell: richtet sich auf und schließt eine warme Luftschicht ein (Regie: stage.FUR_RE)
PROPS["adrenaline"] = p_adrenaline                         # Schaubild Adrenalin: Nebennieren schütten aus, das Herz rast
PROP_ALIASES.update({"fell": "fur", "pelz": "fur", "luftschicht": "fur", "luftpolster": "fur", "isolierschicht": "fur", "fur": "fur",
                     "adrenalin": "adrenaline", "nebenniere": "adrenaline", "nebennieren": "adrenaline", "stresshormon": "adrenaline", "stresshormone": "adrenaline",
                     "noradrenalin": "adrenaline", "hautschnitt": "goosebumps"})


# Echte Größe (Höhe in Metern) und Tiefe (Fußlinie im Bild) – daraus ergibt sich der Maßstab passend zu den Menschen.
# Was hier fehlt (Naturereignisse, Himmelskörper), wird als Schaubild frei gezeichnet.
SIZES = {"car": (1.5, 1150), "police": (1.6, 1150), "ambulance": (2.5, 1130), "bus": (3.0, 1100), "truck": (3.3, 1100), "house": (7.5, 1010), "tree": (7.5, 1130), "rock": (0.8, 1262),
         "box": (0.5, 1262), "fire": (1.1, 1250), "tv": (1.2, 1245), "computer": (1.3, 1245), "money": (0.45, 1262), "sprout": (0.5, 1262), "moss": (0.7, 1262), "shield": (1.7, 1262),
         "cart": (1.0, 1262), "candle": (0.9, 1262), "trafficlight": (3.4, 1225), "canister": (0.5, 1262), "cans": (0.5, 1262),
         "generator": (0.8, 1255), "bike": (1.05, 1255), "shelf": (1.9, 1238), "table": (0.78, 1250), "fridge": (1.85, 1238),
         "cctv": (3.6, 1228), "tent": (1.8, 1180), "door": (2.1, 1236), "clock": (0.6, 1262), "pile": (3.2, 1160), "sandpile": (3.2, 1160),
         "trash": (1.6, 1200), "faucet": (1.6, 1255), "glass": (0.36, 1262), "barrel": (0.95, 1255), "solarpanel": (1.8, 1200), "streetlamp": (4.6, 1225), "rocket": (14.0, 1010), "aquarium": (1.3, 1245), "tank": (1.75, 1245), "sewing": (1.5, 1250), "fabric": (0.75, 1255), "goosebumps": (1.5, 1245), "fur": (1.5, 1245), "adrenaline": (1.5, 1245)}
# ------------------------------------------------------------------ See-Schatz (versenkte Kisten, Taucher, Baumstämme am Seegrund)
def _rotp(pivot, deg):
    """Wie _rot, nimmt aber einen Punkt (x, y) als ein Argument."""
    f_ = _rot(pivot, deg)
    return lambda q: f_(q[0], q[1])


def _crate(d, cx, by, w, h, rot=0.0, lid=True):
    """Eine Holzkiste aus Brettern mit Eisenbändern; (cx, by) = Mitte der Unterkante, rot in Grad."""
    piv = (cx, by - h / 2)
    r_ = _rotp(piv, rot)
    def Q(x0, y0, x1, y1):
        return [r_((cx + x0 * w, by - y0 * h)), r_((cx + x1 * w, by - y0 * h)), r_((cx + x1 * w, by - y1 * h)), r_((cx + x0 * w, by - y1 * h))]
    wood, dark = (176, 128, 78), (120, 84, 52)
    d.polygon(Q(-0.5, 0, 0.5, 1), fill=_dk(wood, 0.2), outline=INK, width=O)
    d.polygon(Q(-0.5, 0.06, 0.44, 1), fill=wood)
    for i in range(1, 4):                                                   # Bretterfugen
        a, b = r_((cx - 0.5 * w, by - h * i / 4)), r_((cx + 0.5 * w, by - h * i / 4))
        d.line((*a, *b), fill=dark, width=max(3, int(h * 0.03)))
    for fx in (-0.34, 0.34):                                                # Eisenbänder
        d.polygon(Q(fx - 0.05, 0, fx + 0.05, 1), fill=(86, 88, 98), outline=INK, width=max(2, O // 2))
    if lid:
        d.polygon(Q(-0.55, 0.9, 0.55, 1.04), fill=_lt(wood, 0.12), outline=INK, width=O)
    d.polygon(Q(-0.5, 0, 0.5, 1), outline=INK, width=O)


def p_crate(d, x, t, s=1.0):
    """Schwere Holzkiste (Schatzkiste, Transportkiste) – kein Pappkarton."""
    _crate(d, x, GROUND, 230, 170)


def p_crates(d, x, t, s=1.0):
    """Stapel aus drei Holzkisten."""
    _crate(d, x - 122, GROUND, 230, 170)
    _crate(d, x + 122, GROUND, 230, 170)
    _crate(d, x + 10, GROUND - 176, 230, 170, rot=-4)


def _note(d, cx, cy, w, h, rot=0.0):
    r_ = _rotp((cx, cy), rot)
    box = [r_((cx - w / 2, cy - h / 2)), r_((cx + w / 2, cy - h / 2)), r_((cx + w / 2, cy + h / 2)), r_((cx - w / 2, cy + h / 2))]
    d.polygon(box, fill=(238, 234, 214), outline=INK, width=4)
    inn = [r_((cx - w * 0.42, cy - h * 0.34)), r_((cx + w * 0.42, cy - h * 0.34)), r_((cx + w * 0.42, cy + h * 0.34)), r_((cx - w * 0.42, cy + h * 0.34))]
    d.line(inn + [inn[0]], fill=(120, 140, 120), width=3)
    d.ellipse((cx - h * 0.2, cy - h * 0.2, cx + h * 0.2, cy + h * 0.2), outline=(120, 140, 120), width=3)


def p_cashcrate(d, x, t, s=1.0):
    """Offene Holzkiste voller gebündelter Geldscheine (ohne echtes Banknoten-Motiv); ein paar Scheine flattern heraus."""
    for i, (dx, rot) in enumerate(((-70, -16), (-10, 6), (56, 20))):          # Bündel ragen heraus
        _note(d, x + dx, GROUND - 204 - (i % 2) * 16, 150, 92, rot)
    _crate(d, x, GROUND, 250, 170, lid=False)
    r_ = _rotp((x - 125, GROUND - 170), -62)                                   # aufgeklappter Deckel
    d.polygon([r_((x - 125, GROUND - 170)), r_((x + 125, GROUND - 170)), r_((x + 125, GROUND - 200)), r_((x - 125, GROUND - 200))], fill=(196, 148, 96), outline=INK, width=O)
    for i in range(3):                                                        # Scheine in der Luft
        ph = (t * 0.35 + i / 3) % 1
        _note(d, x + 40 + i * 60 + math.sin(t * 2 + i) * 16, GROUND - 270 - ph * 170, 120, 72, 20 + i * 25 + math.sin(t * 3 + i) * 14)


def p_goldbars(d, x, t, s=1.0):
    """Kleine Pyramide aus Goldbarren mit Glanz."""
    gold = (244, 196, 56)
    for row, n in enumerate((3, 2, 1)):
        for i in range(n):
            bx = x + (i - (n - 1) / 2) * 112
            y1 = GROUND - row * 56
            d.polygon([(bx - 52, y1), (bx + 52, y1), (bx + 40, y1 - 52), (bx - 40, y1 - 52)], fill=_dk(gold, 0.2), outline=INK, width=O)
            d.polygon([(bx - 44, y1 - 8), (bx + 30, y1 - 8), (bx + 24, y1 - 46), (bx - 34, y1 - 46)], fill=gold)
            d.line((bx - 26, y1 - 38, bx + 4, y1 - 38), fill=(255, 240, 170), width=6)
    tw = 0.5 + 0.5 * math.sin(t * 5)
    gx, gy_ = x + 70, GROUND - 150
    d.line((gx - 22 * tw, gy_, gx + 22 * tw, gy_), fill=(255, 250, 210), width=6)
    d.line((gx, gy_ - 22 * tw, gx, gy_ + 22 * tw), fill=(255, 250, 210), width=6)


def _log(d, x0, y0, x1, y1, r, col=(112, 84, 58)):
    """Ein versunkener Baumstamm von (x0, y0) nach (x1, y1) mit Schnittfläche und Jahresringen am rechten Ende."""
    ang = math.atan2(y1 - y0, x1 - x0)
    nx, ny = -math.sin(ang) * r, math.cos(ang) * r
    d.polygon([(x0 + nx, y0 + ny), (x1 + nx, y1 + ny), (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)], fill=_dk(col, 0.22), outline=INK, width=O)
    d.polygon([(x0 + nx * 0.2, y0 + ny * 0.2), (x1 + nx * 0.2, y1 + ny * 0.2), (x1 - nx * 0.9, y1 - ny * 0.9), (x0 - nx * 0.9, y0 - ny * 0.9)], fill=col)
    for f_ in (0.25, 0.55, 0.8):                                              # Rinde
        mx, my = x0 + (x1 - x0) * f_, y0 + (y1 - y0) * f_
        d.line((mx - nx * 0.5, my - ny * 0.5, mx + math.cos(ang) * r * 1.6 - nx * 0.5, my + math.sin(ang) * r * 1.6 - ny * 0.5), fill=_dk(col, 0.4), width=5)
    mx, my = x0 + (x1 - x0) * 0.4, y0 + (y1 - y0) * 0.4                       # Aststumpf
    d.polygon([(mx - nx * 0.9, my - ny * 0.9), (mx - nx * 2.0 + math.cos(ang) * r * 0.5, my - ny * 2.0 + math.sin(ang) * r * 0.5), (mx - nx * 0.9 + math.cos(ang) * r * 1.1, my - ny * 0.9 + math.sin(ang) * r * 1.1)],
              fill=col, outline=INK, width=5)
    d.ellipse((x1 - r * 0.62, y1 - r, x1 + r * 0.62, y1 + r), fill=(206, 172, 120), outline=INK, width=O)
    d.ellipse((x1 - r * 0.36, y1 - r * 0.6, x1 + r * 0.36, y1 + r * 0.6), outline=(150, 116, 76), width=4)
    d.ellipse((x1 - r * 0.14, y1 - r * 0.24, x1 + r * 0.14, y1 + r * 0.24), fill=(150, 116, 76))


def p_logs(d, x, t, s=1.0):
    """Schicht aus versunkenen Baumstämmen: kreuz und quer, schwebt als Sperre mitten im Wasser (nur unter Wasser)."""
    y = GROUND - 330
    sway = math.sin(t * 0.9) * 6
    for i, (x0, y0, x1, y1, r) in enumerate(((-420, 40, 300, -30, 40), (-300, -80, 440, 60, 36), (-460, 150, 180, 110, 44), (-140, 190, 470, 150, 38), (-380, -150, 240, -120, 32))):
        _log(d, x + x0, y + y0 + sway * (1 if i % 2 else -1), x + x1, y + y1 + sway * (1 if i % 2 else -1), r, ((112, 84, 58), (96, 76, 56), (124, 96, 66))[i % 3])


def p_crates_sink(d, x, t, s=1.0):
    """Drei Holzkisten sinken trudelnd in die Tiefe und ziehen Blasen hinter sich her (nur unter Wasser)."""
    for i, (dx, y0, w) in enumerate(((-250, 330, 200), (40, 170, 230), (270, 420, 190))):
        y = y0 + t * 78
        _crate(d, x + dx + math.sin(t * 1.4 + i * 2) * 18, y, w, w * 0.74, rot=math.sin(t * 1.1 + i * 1.7) * 16 + (i - 1) * 8)
        for j in range(5):                                                    # Blasenspur nach oben
            ph = (t * 0.9 + j / 5 + i * 0.13) % 1
            bx, by_ = x + dx + math.sin(ph * 9 + i) * 26, y - w * 0.8 - ph * 330
            r = 8 + (1 - ph) * 14
            d.ellipse((bx - r, by_ - r, bx + r, by_ + r), outline=(226, 246, 252, int(230 * (1 - ph * 0.7))), width=4)


def p_rocketpart(d, x, t, s=1.0):
    """Verrostetes Versuchsteil am Grund: ein zylindrischer Körper mit Leitwerk, schräg im Schlick – keine startende Weltraumrakete."""
    rust, dark = (146, 104, 78), (92, 70, 62)
    r_ = _rotp((x, GROUND - 60), -14)
    def R(pts):
        return [r_(q) for q in pts]
    d.polygon(R([(x - 250, GROUND - 60), (x - 330, GROUND - 150), (x - 220, GROUND - 110)]), fill=dark, outline=INK, width=O)      # Leitwerk
    d.polygon(R([(x - 250, GROUND - 40), (x - 330, GROUND + 40), (x - 220, GROUND - 4)]), fill=dark, outline=INK, width=O)
    body = R([(x - 250, GROUND - 112), (x + 150, GROUND - 112), (x + 150, GROUND - 4), (x - 250, GROUND - 4)])
    d.polygon(body, fill=_dk(rust, 0.2), outline=INK, width=O)
    d.polygon(R([(x - 240, GROUND - 104), (x + 150, GROUND - 104), (x + 150, GROUND - 40), (x - 240, GROUND - 40)]), fill=rust)
    d.polygon(R([(x + 150, GROUND - 112), (x + 290, GROUND - 58), (x + 150, GROUND - 4)]), fill=_dk(rust, 0.1), outline=INK, width=O)   # Spitze
    for bx in (-150, -20, 100):                                                # Nietenbänder, Rostflecken
        d.line((*r_((x + bx, GROUND - 110)), *r_((x + bx, GROUND - 6))), fill=dark, width=8)
    for bx, by_, rr in ((-90, -70, 18), (40, -36, 14), (-190, -30, 12)):
        c = r_((x + bx, GROUND + by_))
        d.ellipse((c[0] - rr, c[1] - rr * 0.7, c[0] + rr, c[1] + rr * 0.7), fill=(176, 96, 60))
    d.ellipse((x - 330, GROUND - 26, x + 300, GROUND + 26), fill=(70, 80, 78), outline=INK, width=5)                               # Schlick, in dem es steckt


PROPS.update({"crate": p_crate, "crates": p_crates, "cashcrate": p_cashcrate, "goldbars": p_goldbars, "logs": p_logs, "crates_sink": p_crates_sink, "rocketpart": p_rocketpart})
PROP_ALIASES.update({"holzkiste": "crate", "holzkisten": "crates", "kisten": "crates", "schatzkiste": "crate", "schatztruhe": "crate", "truhe": "crate", "transportkiste": "crate",
                     "banknoten": "cashcrate", "geldscheine": "cashcrate", "falschgeld": "cashcrate", "geldkiste": "cashcrate",
                     "goldbarren": "goldbars", "gold": "goldbars", "goldschatz": "goldbars", "baumstämme": "logs", "baumstamm": "logs", "stämme": "logs"})
SIZES.update({"crate": (0.8, 1255), "crates": (1.5, 1250), "cashcrate": (1.25, 1255), "goldbars": (0.5, 1262), "rocketpart": (0.85, 1245)})     # leicht überzeichnet, damit man sie neben den Figuren erkennt
SKY += ("logs", "crates_sink")                              # schweben frei im Wasser (nur von der Regie unter Wasser gesetzt)
WATER_KINDS = ("submersible", "ping", "logs", "crates_sink", "cavitation")     # schweben unter Wasser frei im Bild
LAKE_KINDS = ("crate", "crates", "cashcrate", "goldbars", "logs", "crates_sink", "rocketpart")

HELD = {"phone": "phone", "handy": "phone", "smartphone": "phone", "flashlight": "flashlight", "taschenlampe": "flashlight",
        "bag": "bag", "tasche": "bag", "einkaufstüte": "bag", "tüte": "bag", "bottle": "bottle", "flasche": "bottle",
        "wasserflasche": "bottle", "umbrella": "umbrella", "regenschirm": "umbrella", "schild": "sign", "sign": "sign",
        "map": "map", "karte": "map", "radio": "radio", "letter": "letter", "brief": "letter", "umschlag": "letter"}
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
    size = max(84.0, min(190.0, real * 290 * 1.5)) * k                         # Mensch ≈ 290 Bildpunkte je Meter; leicht vergrößert, damit man es erkennt
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
    elif kind == "letter":                                 # Brief/Abmahnung: Umschlag mit rotem Siegel
        box = (x - 62 * k, y - 66 * k, x + 62 * k, y + 16 * k)
        d.rounded_rectangle(box, 6 * k, fill=(250, 246, 232), outline=INK, width=5)
        d.line((box[0], box[1], x, y - 18 * k, box[2], box[1]), fill=INK, width=max(3, int(5 * k)), joint="curve")
        d.ellipse((x - 15 * k, y - 32 * k, x + 15 * k, y - 2 * k), fill=(214, 60, 60), outline=INK, width=max(2, int(4 * k)))
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
    s = k * max(0.35, sc) * (0.5 if kind in ("!", "alarm", "exclaim", "?", "question") else 0.8)   # klein: die Zeichen sollen die Figur nicht übertönen
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


COLD = ("cold", "kälte", "kaelte", "frost")


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
    elif kind in COLD:                                     # Kälte/Frost: kaltes blaues Licht, Eiskristalle treiben langsam (Atemwolken zeichnet stage._frame)
        d.rectangle((0, 0, W, H), fill=(120, 176, 255, 58))
        for a, b, c in _DROPS[:34]:
            x = (a * W + math.sin(t * 0.8 + c * 9) * 50 + t * 22) % W
            y = (b * H + t * (46 + c * 50)) % H
            r = 9 + c * 9
            tw = 0.55 + 0.45 * math.sin(t * 3 + c * 20)
            for k_ in range(3):
                an = math.radians(k_ * 60 + c * 60 + t * 20)
                d.line((x - math.cos(an) * r, y - math.sin(an) * r, x + math.cos(an) * r, y + math.sin(an) * r), fill=(240, 250, 255, int(150 + 100 * tw)), width=3)
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
    if ("sea" in els and "harbor" not in els) or ground == "water":   # Wellen laufen (im Hafenbecken nicht: sie liefen über Pier und Frachter)
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
         "love": (255, 120, 160), "calm": None}


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


def draw_mood(layer, mood, t, confetti=False):
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
    elif m == "love":                                              # Romantik: rosiger Schimmer, warmer Rand, Herzen und Blütenblätter schweben
        d.rectangle((0, 0, W, H), fill=(*col, 30))
        for i in range(10):
            d.rectangle((i * 9, i * 9, W - i * 9, H - i * 9), outline=(255, 150, 120, (10 - i) * 5), width=9)
        for i, (a, b, c) in enumerate(_DROPS[:26]):
            ph = (b + t * (0.05 + c * 0.05)) % 1
            if i % 3 == 0:                                         # Herz steigt langsam auf und verblasst oben
                x = a * W + math.sin(t * 1.1 + i) * 46
                y = H - ph * (H + 120)
                r = 18 + c * 18
                al = int(210 * min(1.0, (1 - ph) * 2.2) * min(1.0, ph * 6))
                for dx in (-r * 0.5, r * 0.5):
                    d.ellipse((x + dx - r * 0.62, y - r * 0.62, x + dx + r * 0.62, y + r * 0.62), fill=(255, 92, 132, al))
                d.polygon([(x - r * 1.06, y + r * 0.12), (x + r * 1.06, y + r * 0.12), (x, y + r * 1.3)], fill=(255, 92, 132, al))
            else:                                                  # Blütenblatt fällt und dreht sich
                x = (a * W + math.sin(t * 1.6 + i * 2) * 70 + t * 18) % W
                y = ph * (H + 80) - 40
                rw, rh = 9 + c * 7, 5 + c * 4
                k = abs(math.sin(t * 2.2 + i))
                d.ellipse((x - rw, y - rh * k - 1, x + rw, y + rh * k + 1), fill=(255, 170, 190, 215) if i % 2 else (250, 120, 150, 215))
    elif m == "happy":
        d.rectangle((0, 0, W, H), fill=(*col, 26))
        for i, (a, b, c) in enumerate(_DROPS[:30] if confetti else ()):               # Konfetti (nur wenn gefeiert wird)
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


def creature(kind, t, facing=1, mouth=0.0, mood="", scale=1.0, action=""):
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
    ax = cx                                                                      # Fußpunkt (bleibt, auch wenn ein Wesen seine Zeichnung verschiebt)
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
        puff = action == "puff" and not dog                                        # Katze sträubt das Fell: Buschschwanz steil nach oben, Haare stehen an Rücken und Schwanz ab
        if puff:
            tail = [(-110, -120), (-146, -170), (-150, -240), (-140 + wag * 0.3, -300)]
            for i in range(9):                                                      # abstehende Haare rund um den Schwanz
                ty_ = -150 - i * 18
                tx_ = -146 + (ty_ + 170) * 0.03
                q = 1 + 0.08 * math.sin(t * 24 + i * 1.7)
                for sd in (-1, 1):
                    poly([(tx_, ty_ - 9), (tx_ + sd * 44 * q, ty_ - 8 - 10 * q), (tx_, ty_ + 9)], _dark(col, 0.1) if i % 2 else col, shade=0)
        stroke(tail, 34 if puff else 22, _dark(col, 0.1))
        if not dog:
            stroke(tail[-1:] + [(tail[-1][0] + 2, tail[-1][1] - 4)], 34 if puff else 22, _dark(col, 0.35))
        if puff:
            for i in range(11):                                                     # gesträubtes Rückenfell
                an = math.radians(200 + i * 14)
                q = 1 + 0.08 * math.sin(t * 24 + i * 1.9)
                bx_, by_ = -8 + math.cos(an) * 108, -107 + math.sin(an) * 52
                tx_, ty_ = -8 + math.cos(an) * (120 + 62 * q), -107 + math.sin(an) * (62 + 62 * q)
                nx_, ny_ = -math.sin(an) * 19, math.cos(an) * 19
                poly([(bx_ + nx_, by_ + ny_), (tx_, ty_), (bx_ - nx_, by_ - ny_)], _dark(col, 0.1) if i % 2 else col, shade=0)
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
    elif kind in ("fridge", "kühlschrank"):                                          # Haushaltsgerät als Figur: Kühlschrank mit Gesicht, Armen und kurzen Beinen
        col = (236, 240, 244)
        sway = math.sin(t * 2.2) * 4
        hop = abs(math.sin(t * 5)) * 10 if mood == "angry" or action in ("shake", "point") else 0
        y0 = -hop
        for lx in (-64, 30):                                                         # kurze Beine mit Schuhen
            rr(lx, y0 - 44, lx + 30, y0 - 12, 6, (120, 128, 142), shade=0.2)
            rr(lx - 8, y0 - 22, lx + 46, y0, 9, (70, 76, 92), shade=0.15)
        av = math.sin(t * (9 if mood == "angry" or action in ("shake", "point") else 3)) * 12
        stroke([(-100, y0 - 250), (-136, y0 - 200 + av * 0.5), (-126, y0 - 150)], 18, (176, 184, 198))   # Arm hinten
        rr(-104, y0 - 470, 104, y0 - 38, 22, col)                                    # Gehäuse
        d.line((*P(-104, y0 - 318), *P(104, y0 - 318)), fill=INK, width=max(2, int(7 * k)))             # Fuge zwischen Gefrierfach und Tür
        rr(66, y0 - 444, 82, y0 - 348, 6, (150, 158, 172), shade=0)                  # Griffe
        rr(66, y0 - 288, 82, y0 - 150, 6, (150, 158, 172), shade=0)
        fy_ = y0 - 392 + sway * 0.3                                                  # Gesicht auf dem Gefrierfach
        for s in (-1, 1):
            eye(s * 36 - 6, fy_, 21)
            brow(s * 36 - 6, fy_ - 34, 22, -s)
            cheek(s * 66 - 6, fy_ + 26, 13)
        mouthf(-6, fy_ + 34, 22)
        if mood == "angry":
            d.arc(B(-28, fy_ + 30, 16, fy_ + 54), 200, 340, fill=INK, width=max(2, int(6 * k)))
        if action in ("point", "shake") or mood == "angry":                          # Arm vorn: erhoben (schimpft / zeigt)
            stroke([(100, y0 - 250), (146, y0 - 290 - av), (176, y0 - 330 - av)], 18, (196, 204, 216))
            ell(162, y0 - 350 - av, 192, y0 - 320 - av, (236, 240, 244), shade=0)
        else:
            stroke([(100, y0 - 250), (136, y0 - 200 - av * 0.5), (128, y0 - 150)], 18, (196, 204, 216))
            ell(114, y0 - 162, 142, y0 - 134, (236, 240, 244), shade=0)
        for i_, (mx_, my_, mc_) in enumerate(((-60, -250, (240, 90, 80)), (-30, -206, (250, 200, 70)), (-66, -168, (90, 170, 240)))):   # Magnete an der Tür
            rr(mx_, y0 + my_, mx_ + 24, y0 + my_ + 18, 4, mc_, shade=0)
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
        by = -250 - hop                                                          # lange Beine: das Gesicht liegt über den Untertiteln
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
    elif kind in ("diver", "taucher"):
        fly = True                                                                 # Taucher im Neoprenanzug: schwimmt waagerecht, Lampe voraus, Blasen steigen auf
        by = -330 + bob * 1.6
        suit, trim, skin = (44, 52, 66), (246, 196, 56), (244, 204, 170)
        kick = math.sin(t * 6) * 26
        d.polygon([P(150, by + 34), P(300, by + 70), P(300, by + 210), P(214, by + 96)], fill=(255, 240, 170, 60))    # Lichtkegel der Lampe
        for sgn, off in ((1, 14), (-1, -10)):                                      # Beine mit Flossen
            ky = kick * sgn
            stroke([(-70, by + off), (-150, by + off + ky * 0.5), (-214, by + off + ky)], 34, suit)
            poly([(-204, by + off + ky - 20), (-296, by + off + ky * 1.5 - 44), (-290, by + off + ky * 1.5 + 44), (-204, by + off + ky + 20)], trim)
        rr(-96, by - 96, 30, by - 44, 22, trim)                                    # Pressluftflasche auf dem Rücken
        rr(30, by - 84, 52, by - 58, 6, (150, 156, 170))
        rr(-104, by - 46, 78, by + 44, 40, suit)                                   # Rumpf
        d.line((*P(-60, by + 22), *P(50, by + 22)), fill=trim, width=max(2, int(8 * k)))
        stroke([(40, by + 20), (96, by + 52), (150, by + 40)], 26, suit)           # Arm nach vorn mit Lampe
        rr(140, by + 24, 196, by + 56, 8, (200, 60, 50))
        ell(186, by + 22, 208, by + 58, (255, 244, 180), shade=0)
        ell(44, by - 66, 156, by + 42, suit)                                       # Kopf in der Haube
        ell(74, by - 46, 150, by + 30, skin, shade=0)                              # Gesicht
        rr(84, by - 44, 158, by + 2, 14, (150, 214, 240), shade=0)                 # Maske
        d.arc(B(92, by - 38, 126, by - 10), 190, 262, fill=(240, 250, 255), width=max(2, int(5 * k)))
        eye(126, by - 20, 11)
        d.line((*P(84, by - 22), *P(50, by - 22)), fill=INK, width=max(2, int(7 * k)))   # Maskenband
        rr(132, by + 6, 164, by + 30, 6, (96, 104, 122))                           # Atemregler
        stroke([(134, by + 18), (90, by + 50), (20, by - 50)], 8, (96, 104, 122))  # Schlauch zur Flasche
        for i in range(4):                                                         # Blasen
            ph = (t * 0.8 + i / 4) % 1
            bx, by2 = 160 + math.sin(ph * 8 + i) * 16 - ph * 40, by - 20 - ph * 230
            r = 6 + (1 - ph) * 12
            d.ellipse(B(bx - r, by2 - r, bx + r, by2 + r), outline=(230, 250, 255, int(235 * (1 - ph * 0.6))), width=max(2, int(4 * k)))
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
    elif kind in ("shrimp", "mantis"):
        # Krebstiere von der Seite: Pistolenkrebs (eine riesige Knallschere, die zuschnappt und eine Blase abschießt) und
        # Fangschreckenkrebs (bunt, Stielaugen, zwei Keulen, die blitzschnell zuschlagen). Schwimmt knapp über dem Grund.
        fly = True
        mantis = kind == "mantis"
        k = k * 0.84                                                             # der lange Körper samt Schere passt ganz auf die Zeichenfläche
        cx -= 52 * k * f
        by = -250 + bob * 1.4
        col = (70, 176, 124) if mantis else (238, 112, 70)
        belly = _light(col, 0.5)
        edge = (240, 150, 60) if mantis else _dark(col, 0.18)
        sway = math.sin(t * 3) * 14
        for i, (fx_, fy_, fc) in enumerate(((-232, 150, 1), (-214, 186, 0), (-180, 196, 1))):       # Schwanzfächer
            fcol = ((60, 130, 220) if fc else (226, 80, 70)) if mantis else (_dark(col, 0.12) if fc else col)
            poly(_leaf(-176, by + 128, fx_, by + fy_ + sway * 0.3, 26), fcol, shade=0)
        segs = [(-28, 10, 66), (-76, 26, 60), (-120, 52, 53), (-152, 88, 45), (-170, 124, 36)]
        for j, (sx, sy, r_) in reversed(list(enumerate(segs))):                   # Hinterleib aus überlappenden Ringen, von hinten nach vorn
            ell(sx - r_ * 0.72, by + sy - r_, sx + r_ * 0.72, by + sy + r_, col)
            d.arc(B(sx - r_ * 0.72, by + sy - r_, sx + r_ * 0.72, by + sy + r_), *((250, 20) if f > 0 else (160, 290)), fill=edge, width=max(2, int(9 * k)))
            if j:
                pad = math.sin(t * 9 + j) * 6                                    # Schwimmbeinchen paddeln
                stroke([(sx + 6, by + sy + r_ - 6), (sx - 4 + pad, by + sy + r_ + 22)], 7, _dark(col, 0.28))
        for lx in (-6, 26, 58):                                                  # Laufbeine
            a_ = math.sin(t * 7 + lx) * 6
            stroke([(lx, by + 52), (lx - 10 + a_, by + 96), (lx + 6 + a_, by + 122)], 8, _dark(col, 0.25))
        for an, ln in ((0, 150), (1, 118)):                                      # Fühler
            stroke([(112, by - 44), (150 + an * 34, by - 110 - sway * 0.4), (118 + an * 80, by - 110 - ln + sway)], 5, _dark(col, 0.3))
        ell(-58, by - 72, 136, by + 64, col)                                     # Panzer
        ell(-20, by + 4, 112, by + 58, belly, shade=0, line=False)
        poly([(108, by - 46), (178, by - 58), (126, by - 14)], _dark(col, 0.1), shade=0)             # Stirnspitze
        if mantis:
            for sx in (-30, 10, 50):                                             # bunte Flecken auf dem Panzer
                ell(sx - 12, by - 52, sx + 12, by - 30, (250, 206, 80), shade=0, line=False)
            poly(_leaf(96, by - 20, 170, by + 4, 20), (250, 206, 80), shade=0)   # Fühlerschuppe
        for ex, er in ((64, 23), (118, 21)):                                     # Stielaugen
            stroke([(ex + 4, by - 52), (ex, by - 92)], 13, (150, 110, 200) if mantis else col)
            eye(ex, by - 108, er + (3 if mantis else 0))
            brow(ex, by - 108 - er - 18, er, 1 if ex < 100 else -1)
        cheek(96, by + 4, 13)
        mouthf(124, by + 24, 11)
        if mantis:                                                               # Schlag: Keule holt aus und schnellt nach vorn
            ph = (t * 0.9) % 1.0
            ext = 1.0 if ph > 0.8 else max(0.0, (ph - 0.6) / 0.2) * -0.25
            for far in (True, False):
                oy = -16 if far else 12
                ccol = _dark((232, 84, 60), 0.2) if far else (232, 84, 60)
                elbow = (150 + 20 * ext, by + 78 + oy - 10 * ext)
                fist = (150 + 118 * ext + (0 if ext > 0 else 20), by + 40 + oy - 6 * max(0.0, ext))
                stroke([(92, by + 40 + oy), elbow, fist], 17, _dark(col, 0.15) if far else col)
                ell(fist[0] - 30, fist[1] - 28, fist[0] + 34, fist[1] + 28, ccol, shade=0.2)
                ell(fist[0] - 4, fist[1] - 16, fist[0] + 10, fist[1] - 4, (255, 255, 255, 190), shade=0, line=False)
            if ph > 0.8:                                                         # Einschlag: Stern und Druckwelle
                hx_, hy_ = 322, by + 46
                g = (ph - 0.8) / 0.2
                pts = []
                for i in range(16):
                    a_ = i / 16 * math.tau
                    r_ = (44 if i % 2 else 20) * (0.7 + 0.5 * g)
                    pts.append((hx_ + math.cos(a_) * r_, hy_ + math.sin(a_) * r_))
                d.polygon([P(x, y) for x, y in pts], fill=(255, 236, 120), outline=INK, width=max(2, int(4 * k)))
                d.arc(B(hx_ - 40 - 30 * g, hy_ - 70 - 30 * g, hx_ + 40 + 30 * g, hy_ + 70 + 30 * g), *((300, 60) if f > 0 else (120, 240)),
                      fill=(255, 255, 255, int(220 * (1 - g))), width=max(2, int(8 * k)))
        else:                                                                    # Knallschere: öffnet sich langsam, schnappt zu, Blase schießt heraus
            ph = (t * 0.75) % 1.0
            gap = min(1.0, ph / 0.7) if ph < 0.78 else 0.0
            stroke([(96, by + 36), (150, by + 84), (196, by + 44)], 18, col)
            stroke([(80, by + 44), (118, by + 96), (150, by + 104)], 10, _dark(col, 0.15))           # kleine zweite Schere
            poly([(150, by + 96), (182, by + 92), (156, by + 116)], _dark(col, 0.1), shade=0)
            ccol = _light(col, 0.12)
            poly([(236, by + 36), (352, by + 52), (346, by + 66), (236, by + 84)], _dark(ccol, 0.12), shade=0)   # fester Finger
            piv = (240, by - 2)
            a_ = math.radians(6 + 40 * gap)
            ca, sa = math.cos(a_), math.sin(a_)
            def rot(dx, dy):                                                     # Punkt des beweglichen Fingers um das Gelenk drehen
                return piv[0] + dx * ca + dy * sa, piv[1] + 30 - dx * sa + dy * ca
            poly([rot(-6, -34), rot(60, -30), rot(112, 0), rot(60, 6), rot(-6, 10)], ccol, shade=0)
            ell(160, by - 40, 262, by + 88, ccol)                                # dicke Scherenhand
            ell(186, by - 22, 222, by + 4, _light(ccol, 0.4), shade=0, line=False)
            if ph >= 0.78:                                                       # Knall: Blase und Druckringe vor der Schere
                g = (ph - 0.78) / 0.22
                bx_, by_ = 366 + 8 * g, by + 40
                for r_, al in ((30 + 22 * g, 150), (16 + 10 * g, 230)):
                    d.ellipse(B(bx_ - r_, by_ - r_, bx_ + r_, by_ + r_), outline=(255, 255, 255, int(al * (1 - g * 0.7))), width=max(2, int(7 * k)))
                d.ellipse(B(bx_ - 12, by_ - 12, bx_ + 12, by_ + 12), fill=(255, 244, 170, int(255 * (1 - g))))
    elif kind in ("jelly", "qualle"):
        # Qualle: durchscheinender Schirm, der pulsiert, Fransen und wehende Tentakel; freundliches Gesicht auf dem Schirm
        fly = True
        col = (236, 150, 206)
        pul = math.sin(t * 3.2)
        by = -350 + bob * 2 - pul * 8
        w, h = 128 * (1 - 0.07 * pul), 136 * (1 + 0.06 * pul)
        for i, tx in enumerate((-84, -44, 0, 44, 84)):                           # Tentakel (hinter dem Schirm)
            pts = [(tx * (1 - 0.07 * pul) + math.sin(t * 2.6 + i * 1.3 + j * 0.45) * (5 + j * 1.6), by + 30 + j * 17) for j in range(14)]
            stroke(pts, 9, _dark(col, 0.12) if i % 2 else _light(col, 0.25))
        for s_ in (-1, 1):                                                       # Mundarme: kurz und kraus
            pts = [(s_ * 22 + math.sin(t * 3 + j * 0.5 + s_) * 9, by + 36 + j * 12) for j in range(10)]
            stroke(pts, 20, _light(col, 0.45))
        dome = [(math.cos(math.radians(a)) * w, by + math.sin(math.radians(a)) * h) for a in range(180, 361, 10)]
        n = 6
        low = []
        for i in range(n * 4 + 1):                                               # gewellter Saum
            u = i / (n * 4)
            low.append((w - u * 2 * w, by + 26 + abs(math.sin(u * n * math.pi)) * 24))
        shape = dome + low
        d.polygon([P(x, y) for x, y in shape], fill=(*_dark(col, 0.2), 235), outline=INK, width=o)
        d.polygon([P(x * 0.86 + 12, by + (y - by) * 0.86 - 4) for x, y in shape], fill=(*col, 235))
        ell(-70, by - 112, -6, by - 78, _light(col, 0.55), shade=0, line=False)                   # Glanz
        ell(-4, by - 104, 40, by - 66, (226, 104, 110), shade=0, line=False)                        # roter Magen schimmert durch (typisch für die „unsterbliche Qualle“)
        ell(8, by - 96, 28, by - 78, (244, 150, 150), shade=0, line=False)
        eye(-40, by - 12, 21)
        eye(44, by - 12, 21)
        brow(-40, by - 44, 18, 1)
        brow(44, by - 44, 18, -1)
        cheek(-78, by + 12, 14)
        cheek(84, by + 12, 14)
        mouthf(2, by + 14, 13)
    elif kind == "axolotl":
        # Axolotl: rosa Schwanzlurch mit breitem Lächeln und je drei gefiederten Kiemenästen; schwimmt
        fly = True
        col = (246, 176, 190)
        gill = (226, 92, 120)
        by = -300 + bob * 1.6
        wag = math.sin(t * 5) * 22
        tail = [(-90, by - 10), (-170, by - 30 + wag * 0.4), (-250, by - 14 + wag), (-282, by + 6 + wag), (-240, by + 34 + wag * 0.8), (-160, by + 40 + wag * 0.3), (-90, by + 40)]
        poly(tail, col)                                                          # Ruderschwanz mit Flossensaum
        d.line([P(x, y) for x, y in ((-100, by + 12), (-180, by + 6 + wag * 0.4), (-262, by + 10 + wag))], fill=_dark(col, 0.3), width=max(2, int(5 * k)))
        for lx, far in ((-70, True), (40, True), (-50, False), (60, False)):     # vier kurze Beine mit Zehen
            sw_ = math.sin(t * 5 + lx) * 8
            c2 = _dark(col, 0.2) if far else col
            stroke([(lx, by + 44), (lx + 10 + sw_, by + 82), (lx + 30 + sw_, by + 96)], 16, c2)
            for tz in (-8, 4, 16):
                stroke([(lx + 30 + sw_, by + 96), (lx + 44 + sw_, by + 96 + tz)], 5, c2)
        ell(-120, by - 52, 96, by + 64, col)                                     # Rumpf
        ell(-70, by + 10, 70, by + 60, _light(col, 0.5), shade=0, line=False)
        hx = 122
        for far in (True, False):                                                # je drei gefiederte Kiemenäste, fächerförmig nach hinten oben
            for i, a_ in enumerate((158, 128, 98) if not far else (146, 116, 88)):
                r_ = math.radians(a_ + math.sin(t * 3 + i) * 5)
                ln = 84 if far else 104
                bx_, by_ = (hx - 34, by - 44) if far else (hx - 62, by - 26)
                tx_, ty_ = bx_ + math.cos(r_) * ln, by_ - math.sin(r_) * ln
                stroke([(bx_, by_), (tx_, ty_)], 12 if far else 15, _dark(gill, 0.25) if far else gill)
                if not far:
                    for q in (0.5, 0.8):                                         # Fiederchen
                        mx_, my_ = bx_ + (tx_ - bx_) * q, by_ + (ty_ - by_) * q
                        nx_, ny_ = math.sin(r_) * 16, math.cos(r_) * 16
                        d.line((*P(mx_ - nx_, my_ - ny_), *P(mx_ + nx_, my_ + ny_)), fill=_light(gill, 0.35), width=max(2, int(5 * k)))
        ell(hx - 84, by - 70, hx + 96, by + 62, col)                             # breiter Kopf
        eye(hx + 4, by - 20, 15)
        eye(hx + 62, by - 20, 15)
        brow(hx + 4, by - 44, 14, 1)
        brow(hx + 62, by - 44, 14, -1)
        cheek(hx - 22, by + 16, 15)
        cheek(hx + 84, by + 12, 12)
        if mouth > 0.1 or wide:
            mouthf(hx + 36, by + 18, 14)
        else:
            d.arc(B(hx - 14, by - 14, hx + 86, by + 34), *((20, 160) if mood not in ("sad", "worried") else (200, 340)), fill=INK, width=max(2, int(6 * k)))
    elif kind == "tardigrade":
        # Bärtierchen: pralles, gegliedertes Körperchen auf acht Stummelbeinen mit Krallen, runder Rüssel-Mund
        col = (214, 186, 150)
        if action == "tun":
            # Tönnchen (Prüfung 17.11.2026): eingerollt und ausgetrocknet – faltige, geschrumpfte Tonne, Beine eingezogen, Augen zu, regungslos
            col = (186, 156, 118)
            ell(-150, -196, 150, -8, col)
            for rx_ in (-96, -48, 0, 48, 96):                                    # Falten quer über die Tonne
                hh = 94 * math.sqrt(max(0.0, 1 - (rx_ / 150) ** 2))
                d.line((*P(rx_, -102 - hh * 0.86), *P(rx_ - 10, -102), *P(rx_, -102 + hh * 0.86)), fill=_dark(col, 0.34), width=max(2, int(7 * k)), joint="curve")
            for sx in (-92, -30, 30, 92):                                        # eingezogene Beinstummel
                ell(sx - 20, -30, sx + 20, 0, _dark(col, 0.2), shade=0)
            eye(70, -118, 13, "closed")
            eye(112, -112, 13, "closed")
            ell(128, -92, 160, -64, _light(col, 0.25), shade=0)                  # eingezogener Rüssel
            out = im.resize((im.width // S, im.height // S), Image.LANCZOS)
            return out, ax / S, gy / S, fly
        step = math.sin(t * 6)
        by = -150 + bob * 0.3
        segs = [(-150, 6, 70), (-80, -6, 88), (0, -10, 92), (78, -4, 82)]
        for i, (sx, sy, r_) in enumerate(segs):                                  # Beine hinten (abgewandte Seite)
            lift = step * 8 * (1 if i % 2 else -1)
            stroke([(sx + 18, by + 60), (sx + 26, -22 - max(0, lift))], 30, _dark(col, 0.28))
        for sx, sy, r_ in segs:                                                  # Körperringe
            ell(sx - r_ * 0.78, by + sy - r_, sx + r_ * 0.78, by + sy + r_, col)
        for sx, sy, r_ in segs[1:]:
            d.arc(B(sx - r_ * 0.78, by + sy - r_, sx + r_ * 0.78, by + sy + r_), *((120, 240) if f > 0 else (300, 60)), fill=_dark(col, 0.3), width=max(2, int(6 * k)))
        for i, (sx, sy, r_) in enumerate(segs):                                  # Beine vorn mit Krallen
            lift = step * 8 * (-1 if i % 2 else 1)
            fy_ = -18 - max(0, lift)
            stroke([(sx - 16, by + 62), (sx - 10, fy_)], 34, col)
            for cz in (-12, 0, 12):
                poly([(sx - 10 + cz - 5, fy_ + 8), (sx - 10 + cz, fy_ + 26), (sx - 10 + cz + 5, fy_ + 8)], (90, 70, 56), shade=0, line=False)
        hx = 150
        ell(hx - 70, by - 74, hx + 70, by + 62, col)                             # Kopf
        ell(hx + 40, by - 14, hx + 96, by + 36, _light(col, 0.3), shade=0.1)     # Rüssel
        mh = 8 + mouth * 10
        ell(hx + 62, by + 10 - mh, hx + 62 + 2 * mh, by + 10 + mh, (110, 60, 60), shade=0, line=False)
        eye(hx - 14, by - 22, 14)
        eye(hx + 30, by - 26, 14)
        brow(hx - 14, by - 46, 13, 1)
        brow(hx + 30, by - 50, 13, -1)
        cheek(hx - 34, by + 14, 14)
    elif kind in ("cheetah", "gepard", "chimera"):
        # Gepard: schlanke Raubkatze mit langen Beinen, Tupfen, Tränenstreifen und Ringelschwanz; action = "run": gestreckter Galopp
        # "chimera": das Misch-Wesen aus „Was wäre, wenn man ein Super-Tier baut“ (Prüfung 19.11.2026) – Gepard-Körper mit Adlerflügeln,
        # großen gelben Adleraugen und einem leuchtenden, schlagenden Herzen in der Brust; action = "down": zusammengesackt am Boden
        chim = kind == "chimera"
        down = chim and action == "down"
        col = (236, 184, 96)
        belly = _light(col, 0.6)
        spot = (64, 46, 34)
        run = action == "run"
        ext = math.sin(t * 11) if run else 0.0                                   # +1 gestreckt, -1 Beine unter dem Bauch
        oy = (-16 - 12 * ext) if run else bob * 0.25                             # im Galopp hebt der Körper ab
        if down:
            oy = 96 + bob * 0.1                                                  # der Rumpf liegt am Boden, die Beine sind eingeknickt
        wcol = (112, 78, 54)
        wfl = math.sin(t * (9 if run else 2.2)) * (0.5 if run else 0.25) + (0.2 if not down else -1.5)

        def chim_wing(front):
            wy_ = -40 * wfl
            ax_, ay_ = (-10 if front else 14), -232 + oy
            pts = [(ax_ + 30, ay_ + 4), (ax_ - 6, ay_ - 96 + wy_), (ax_ - 62, ay_ - 160 + wy_ * 1.3), (ax_ - 96, ay_ - 134 + wy_ * 1.2), (ax_ - 116, ay_ - 164 + wy_ * 1.3),
                   (ax_ - 146, ay_ - 130 + wy_ * 1.2), (ax_ - 170, ay_ - 150 + wy_ * 1.25), (ax_ - 190, ay_ - 110 + wy_ * 1.1), (ax_ - 214, ay_ - 116 + wy_ * 1.1),
                   (ax_ - 200, ay_ - 60 + wy_ * 0.7), (ax_ - 110, ay_ + 14)]
            poly(pts, wcol if front else _dark(wcol, 0.3), shade=0.08 if front else 0)
            if front:
                for q in (0.3, 0.52, 0.74):
                    d.line((*P(ax_ - 10 - 110 * q, ay_ - 20 - 100 * q + wy_ * q), *P(ax_ - 100 - 90 * q, ay_ + 6 - 76 * q + wy_ * q * 0.8)), fill=_dark(wcol, 0.35), width=max(2, int(5 * k)))
        wag = math.sin(t * 3) * 12
        tail = [(-168, -196 + oy), (-232, -176 + oy), (-272, -128 + oy + wag * 0.5), (-268 + wag * 0.4, -78 + oy + wag)] if not run else \
               [(-168, -196 + oy), (-232, -206 + oy), (-272, -214 + oy - ext * 10), (-296, -196 + oy - ext * 18)]
        stroke(tail, 20, col)
        for q in (0.45, 0.7):                                                    # Ringe am Schwanz
            a_, b_ = tail[2], tail[3]
            mx_, my_ = a_[0] + (b_[0] - a_[0]) * q, a_[1] + (b_[1] - a_[1]) * q
            stroke([(mx_ - 2, my_ - 3), (mx_ + 2, my_ + 3)], 20, spot)
        stroke(tail[-1:] + [(tail[-1][0] + 1, tail[-1][1] + 3)], 20, spot)        # dunkle Spitze

        def leg(front, e, c2):
            if front:
                top = (98, -150 + oy)
                paw = (98 + 122 * e, -10 - 34 * abs(e) if run else -10)
                knee = ((top[0] + paw[0]) / 2 + 16 - 10 * e, (top[1] + paw[1]) / 2 + 6)
                if down:
                    paw, knee = (190, -8), (150, -40)
            else:
                top = (-128, -150 + oy)
                paw = (-128 - 118 * e, -10 - 30 * abs(e) if run else -10)
                knee = ((top[0] + paw[0]) / 2 - 30 + 8 * e, (top[1] + paw[1]) / 2 + 14)
                if down:
                    paw, knee = (-60, -8), (-150, -44)
            stroke([top, knee, paw], 24, c2)
            ell(paw[0] - 14, paw[1] - 12, paw[0] + 26, paw[1] + 10, _light(c2, 0.35), shade=0)
        for fr in (True, False):                                                 # Beine der abgewandten Seite (leicht versetzt im Takt)
            leg(fr, math.sin(t * 11 - 0.7) if run else -0.22, _dark(col, 0.22))
        if chim:
            chim_wing(False)
        ell(-190, -240 + oy, 60, -128 + oy, col)                                 # schlanker Rumpf mit tiefer Brust
        ell(10, -256 + oy, 160, -112 + oy, col)
        ell(-176, -234 + oy, 100, -134 + oy, col, shade=0, line=False)           # Naht zwischen Rumpf und Brust schließen
        ell(-120, -176 + oy, 120, -124 + oy, belly, shade=0, line=False)
        for sx, sy in ((-150, -206), (-112, -222), (-118, -186), (-74, -206), (-40, -224), (-36, -190), (4, -208), (40, -228), (48, -192), (88, -214), (112, -180), (-160, -172)):
            ell(sx - 9, sy - 8 + oy, sx + 9, sy + 8 + oy, spot, shade=0, line=False)
        for fr in (True, False):
            leg(fr, ext if run else 0.0, col)
        if chim:
            chim_wing(True)
            beat = 1.0 + 0.16 * max(0.0, math.sin(t * (2.0 if down else 7.0))) ** 2          # das Wal-Herz schlägt sichtbar in der Brust
            hcx, hcy, hr = 96, -176 + oy, 30 * beat
            hcol = (150, 150, 160) if down else (232, 60, 76)
            if not down:
                d.ellipse(B(hcx - hr * 1.9, hcy - hr * 1.7, hcx + hr * 1.9, hcy + hr * 1.9), fill=(255, 90, 100, 70))
            ell(hcx - hr, hcy - hr * 0.9, hcx, hcy + hr * 0.1, hcol, shade=0)
            ell(hcx, hcy - hr * 0.9, hcx + hr, hcy + hr * 0.1, hcol, shade=0)
            poly([(hcx - hr * 0.96, hcy - hr * 0.2), (hcx + hr * 0.96, hcy - hr * 0.2), (hcx, hcy + hr * 1.05)], hcol, shade=0)
            d.ellipse(B(hcx - hr * 0.8, hcy - hr * 0.7, hcx + hr * 0.8, hcy + hr * 0.05), fill=hcol)
        hx, hy = 186, -306 + oy + (bob * 0.3 if not run else 0)
        if down:
            hx, hy = 214, -150 + oy                                              # der Kopf liegt vorn auf den Pfoten
        stroke([(118, -214 + oy), (158, hy + 26)], 58, col)                      # Hals
        for ex_ in (-34, 22):                                                    # kleine runde Ohren
            ell(hx + ex_ - 18, hy - 76, hx + ex_ + 18, hy - 36, _dark(col, 0.2) if ex_ < 0 else col, shade=0)
            ell(hx + ex_ - 8, hy - 66, hx + ex_ + 8, hy - 44, spot, shade=0, line=False)
        ell(hx - 64, hy - 60, hx + 64, hy + 52, col)                             # Kopf
        ell(hx + 6, hy + 2, hx + 78, hy + 50, belly, shade=0, line=False)        # helle Schnauze
        for sx, sy in ((-34, -40), (-14, -50), (-44, -14)):                      # Tupfen auf der Stirn
            ell(hx + sx - 5, hy + sy - 5, hx + sx + 5, hy + sy + 5, spot, shade=0, line=False)
        for ex_ in (4, 46):                                                      # Tränenstreifen vom Auge zum Maul
            d.line((*P(hx + ex_ + 6, hy - 4), *P(hx + ex_ + 12, hy + 16), *P(hx + ex_ + 8, hy + 36)), fill=spot, width=max(2, int(6 * k)), joint="curve")
        poly([(hx + 46, hy + 6), (hx + 66, hy + 6), (hx + 56, hy + 19)], (60, 40, 40), shade=0)   # Nase
        mouthf(hx + 54, hy + 32, 13)
        if chim:                                                                 # Adleraugen: groß, gelb umrandet, strenge Braue
            for ex_ in (2, 48):
                ell(hx + ex_ - 29, hy - 49, hx + ex_ + 29, hy + 9, col if down else (248, 196, 60), shade=0, line=not down)
            eye(hx + 2, hy - 20, 17, "closed" if down else None)
            eye(hx + 48, hy - 20, 17, "closed" if down else None)
            if not down and mood not in ("sad", "worried", "scared"):
                d.line((*P(hx - 22, hy - 52), *P(hx + 26, hy - 42)), fill=INK, width=max(2, int(7 * k)))
        else:
            eye(hx + 4, hy - 18, 14)
            eye(hx + 46, hy - 18, 14)
        brow(hx + 4, hy - 42, 13, 1)
        brow(hx + 46, hy - 42, 13, -1)
        cheek(hx - 24, hy + 20, 13)
        if run:                                                                  # Fahrtstriche hinter dem Tier
            for i, ly in enumerate((-250, -196, -140)):
                lx = -250 - ((t * 520 + i * 37) % 50)
                d.line((*P(lx, ly + oy), *P(lx - 46, ly + oy)), fill=(255, 255, 255, 170), width=max(2, int(7 * k)))
    elif kind in ("eagle", "adler"):
        # Adler: großer Greifvogel im Flug – dunkelbraun, weißer Kopf und Stoß, gelber Hakenschnabel, gelbe Fänge, strenger Blick
        fly = True
        col, white, yel = (112, 78, 54), (246, 242, 232), (248, 196, 60)
        by = -292 + bob * 1.5
        fl = math.sin(t * 5.5)
        poly([(-104, by - 16), (-196, by - 40), (-222, by - 6), (-214, by + 30), (-190, by + 52), (-104, by + 30)], white)        # Stoß (Schwanzfedern)
        for ty in (-14, 14):
            d.line((*P(-130, by + 6 + ty * 0.4), *P(-206, by + 6 + ty * 1.6)), fill=_dark(white, 0.2), width=max(2, int(4 * k)))
        wy = -46 * fl
        poly([(40, by - 30), (10, by - 126 + wy), (-60, by - 180 + wy * 1.3), (-150, by - 180 + wy * 1.3), (-196, by - 126 + wy), (-110, by - 36)], _dark(col, 0.3), shade=0)   # Flügel hinten
        for lx in (-34, 6):                                                      # Fänge
            stroke([(lx, by + 52), (lx - 6, by + 84)], 12, yel)
            for cz in (-16, 0, 16):
                stroke([(lx - 6, by + 84), (lx - 6 + cz, by + 106)], 6, yel)
                poly([(lx - 10 + cz, by + 104), (lx - 2 + cz, by + 104), (lx - 4 + cz * 1.2, by + 120)], (40, 34, 34), shade=0, line=False)
        ell(-136, by - 62, 96, by + 64, col)                                     # Rumpf
        for sx, sy in ((-60, 24), (-20, 34), (20, 26), (-40, 4), (0, 10)):       # Brustgefieder
            d.arc(B(sx - 16, by + sy - 12, sx + 16, by + sy + 12), 20, 160, fill=_dark(col, 0.35), width=max(2, int(5 * k)))
        hx, hy = 112, by - 44
        ell(hx - 66, hy - 56, hx + 58, hy + 56, white)                           # weißer Kopf
        ell(hx - 76, hy + 4, hx + 10, hy + 70, white, shade=0, line=False)       # weißer Nacken geht in die Brust über
        poly([(hx + 44, hy - 20), (hx + 92, hy - 16), (hx + 112, hy + 6), (hx + 108, hy + 36), (hx + 92, hy + 20), (hx + 46, hy + 22)], yel)   # Hakenschnabel
        d.line((*P(hx + 50, hy + 6), *P(hx + 92, hy + 6)), fill=_dark(yel, 0.4), width=max(2, int(4 * k)))
        w2 = -52 * fl
        wing = [(30, by - 22), (-10, by - 126 + w2), (-70, by - 195 + w2 * 1.3), (-108, by - 165 + w2 * 1.2), (-128, by - 198 + w2 * 1.3), (-160, by - 161 + w2 * 1.2),
                (-186, by - 186 + w2 * 1.25), (-208, by - 141 + w2 * 1.1), (-236, by - 151 + w2 * 1.1), (-222, by - 87 + w2 * 0.7), (-130, by - 6)]
        poly(wing, col, shade=0.08)                                              # Flügel vorn mit gefingerten Schwungfedern
        for q in (0.3, 0.52, 0.74):                                              # Federreihen
            d.line((*P(-10 - 120 * q, by - 40 - 120 * q + w2 * q), *P(-110 - 100 * q, by - 14 - 90 * q + w2 * q * 0.8)), fill=_dark(col, 0.35), width=max(2, int(5 * k)))
        eye(hx + 16, hy - 12, 14, "angry" if eyekind == "" else None)
        d.line((*P(hx - 6, hy - 38), *P(hx + 38, hy - 26)), fill=INK, width=max(2, int(7 * k)))      # strenge Braue
        cheek(hx - 4, hy + 20, 11)
    elif kind in ("flea", "floh"):
        # Floh: hochgewölbter, rotbrauner Körper mit Ringen, winziger Kopf, Stechrüssel und riesige Sprungbeine; action = "jump": springt hoch
        col = (168, 92, 56)
        jump = action == "jump"
        u = (t % 1.5) / 1.5
        air = jump and 0.16 < u < 0.86
        lift = math.sin((u - 0.16) / 0.7 * math.pi) * 240 if air else 0.0
        crouch = (14 * math.sin(min(1.0, u / 0.16) * math.pi) if u <= 0.16 else 0.0) if jump else 0.0
        by = -168 - lift + crouch + (0 if jump else bob * 0.3)
        gyl = -lift                                                              # Fußlinie (in der Luft hängen die Beine)
        def legs(far):
            c2 = _dark(col, 0.28) if far else col
            dx = -22 if far else 0
            if air:
                stroke([(-70 + dx, by + 40), (-150 + dx, by + 80), (-200 + dx, by + 190), (-224 + dx, by + 200)], 22 if not far else 18, c2)     # gestrecktes Sprungbein
                for lx in (-6, 52):
                    stroke([(lx + dx, by + 62), (lx + dx - 16, by + 112), (lx + dx - 34, by + 140)], 12, c2)
            else:
                stroke([(-70 + dx, by + 36), (-190 + dx, by - 40 + crouch), (-150 + dx, gyl - 14), (-106 + dx, gyl - 8)], 22 if not far else 18, c2)   # gefaltetes Sprungbein
                for lx in (-6, 52):
                    stroke([(lx + dx, by + 62), (lx + dx + 22, (by + 62 + gyl) / 2), (lx + dx + 12, gyl - 8), (lx + dx + 30, gyl - 6)], 12, c2)
        legs(True)
        for bx_ in (-120, -84, -46, -8):                                         # Borsten auf dem Rücken
            poly([(bx_ - 8, by - 96), (bx_ - 26, by - 136), (bx_ + 8, by - 104)], _dark(col, 0.4), shade=0)
        ell(-170, by - 118, 78, by + 84, col)                                    # Körper
        for a_ in (-120, -72, -24, 24):                                          # Körperringe
            band(-170, by - 118, 78, by + 84, a_, a_ + 9, _dark(col, 0.3))
        ell(-110, by - 96, -30, by - 44, _light(col, 0.3), shade=0, line=False)  # Glanz
        hx = 96
        stroke([(hx + 40, by + 10), (hx + 58, by + 44), (hx + 52, by + 70)], 9, _dark(col, 0.4))      # Stechrüssel
        for ax_ in (0, 22):                                                      # kurze Fühler
            stroke([(hx + ax_, by - 62), (hx + ax_ + 18, by - 96)], 7, _dark(col, 0.35))
            ell(hx + ax_ + 11, by - 106, hx + ax_ + 27, by - 90, _dark(col, 0.35), shade=0, line=False)
        ell(hx - 58, by - 72, hx + 64, by + 44, _light(col, 0.12))               # Kopf
        legs(False)
        eye(hx - 4, by - 22, 15)
        eye(hx + 36, by - 22, 15)
        brow(hx - 4, by - 48, 13, 1)
        brow(hx + 36, by - 48, 13, -1)
        cheek(hx - 30, by + 12, 12)
        mouthf(hx + 22, by + 14, 11)
        if air and lift > 60:                                                    # Sprungstriche unter dem Tier
            for lx in (-80, -30, 20):
                d.line((*P(lx, gyl + 40), *P(lx, gyl + 40 + min(90, lift * 0.4))), fill=(255, 255, 255, 170), width=max(2, int(7 * k)))
    elif kind in ("dolphin", "delfin", "schweinswal", "tümmler", "porpoise"):       # Delfin/Schweinswal: grauer Rücken, heller Bauch, Rückenfinne, Schnabel – schwimmt
        fly = True
        by = -330 + bob * 2
        wag = math.sin(t * 6) * 22
        col, belly = (112, 142, 172), (236, 242, 248)
        poly([(-150, by + 4), (-236, by - 78 + wag), (-212, by + 6 + wag * 0.6), (-244, by + 70 + wag), (-146, by + 20)], _dark(col, 0.08))   # Fluke
        poly([(-30, by - 66), (-6, by - 160), (64, by - 62)], col)                    # Rückenfinne
        xs = [-176 + i * 21 for i in range(18)]
        top = [(x, by - 80 * math.sqrt(max(0.0, 1 - ((x - 4) / 184) ** 2)) ** 0.8) for x in xs]
        bot = [(x, by + 68 * math.sqrt(max(0.0, 1 - ((x - 4) / 184) ** 2)) ** 0.8) for x in xs]
        d.polygon([P(*q) for q in top + bot[::-1]], fill=_dark(col, 0.2), outline=INK, width=o)
        d.polygon([P(x + 10, y + 4) for x, y in top[1:]] + [P(x + 10, by + 12) for x, _ in top[:0:-1]], fill=col)
        d.polygon([P(x, by + 20 + (y - by - 20) * 0.95) for x, y in bot[2:]] + [P(xs[-1], by + 20), P(xs[2], by + 20)], fill=belly)
        jaw = mouth * 16
        poly([(150, by - 6), (232, by + 12), (150, by + 30)], col, shade=0)           # Schnabel oben
        poly([(150, by + 22), (222, by + 22 + jaw), (150, by + 44 + jaw * 0.5)], belly, shade=0)   # Unterkiefer
        ell(96, by - 60, 176, by + 52, col, shade=0, line=False)                      # Stirn (Melone) deckt den Ansatz
        d.arc(B(120, by + 6, 190, by + 44), 20, 120, fill=INK, width=max(2, int(5 * k)))   # Lächeln
        poly([(30, by + 30), (-30, by + 112), (84, by + 46)], _dark(col, 0.1))        # Brustflosse
        eye(120, by - 16, 14)
        brow(120, by - 40, 13, 1)
        cheek(98, by + 14, 12)
    elif kind in ("whale", "wal", "blauwal", "buckelwal"):                          # Blauwal: langer blaugrauer Körper, helle Kehle mit Furchen, winzige Finne weit hinten, breite Fluke – gleitet
        fly = True
        by = -300 + bob * 1.5
        wag = math.sin(t * 2.2) * 16
        col, belly = (84, 128, 172), (214, 228, 238)
        x0, x1 = -214, 286
        xs = [x0 + (x1 - x0) * i / 28 for i in range(29)]

        def half(x, hm):                                                            # Umriss: dünner Schwanzstiel, größte Dicke im vorderen Drittel, stumpfes Maul
            u = (x - x0) / (x1 - x0)
            return 15 * (1 - u) + hm * math.sin(math.pi * min(1.0, u ** 1.45)) ** 0.62
        top = [(x, by - half(x, 66) + wag * max(0.0, (-60 - x) / 154) ** 2) for x in xs]
        bot = [(x, by + half(x, 84) + wag * max(0.0, (-60 - x) / 154) ** 2) for x in xs]
        fy = by + wag
        poly([(-196, fy - 8), (-232, fy - 50), (-268, fy - 92), (-304, fy - 98), (-290, fy - 56), (-262, fy - 2), (-292, fy + 54), (-306, fy + 94), (-268, fy + 90),
              (-232, fy + 50), (-196, fy + 10)], _dark(col, 0.1))                    # Fluke: zwei geschwungene Lappen mit Kerbe
        poly([(-112, by - 44), (-132, by - 78), (-74, by - 52)], col, shade=0)        # kleine Rückenfinne, weit hinten
        d.polygon([P(*q) for q in top + bot[::-1]], fill=_dark(col, 0.22), outline=INK, width=o)
        d.polygon([P(x + 4, y + 6) for x, y in top[1:-1]] + [P(x + 4, by + (y - by) * 0.12 + 8) for x, y in top[-2:0:-1]], fill=col)   # Rücken im Licht, läuft zum Schwanz spitz aus
        thr = [(x, y, min(1.0, max(0.0, (x + 44) / 90))) for x, y in bot[:-1] if x >= -44]   # Kehle und Bauch hell, setzt hinter der Brustflosse weich an
        d.polygon([P(x, y - 7) for x, y, _ in thr] + [P(x, (y - 7) - (y - by) * 0.62 * w_) for x, y, w_ in thr[::-1]], fill=belly)
        for i in range(4):                                                           # Kehlfurchen folgen dem Bauch
            fr = 0.52 + i * 0.11
            d.line([P(x, by + (y - by) * fr) for x, y, w_ in thr if w_ >= 1 and x < 250 - i * 6][i:], fill=_dark(belly, 0.2), width=max(2, int(3.5 * k)), joint="curve")
        for sx, sy, sr in ((-60, -30, 9), (-20, -44, 7), (40, -40, 10), (96, -48, 7), (-110, -14, 6), (150, -36, 8), (10, -14, 6)):   # helle Sprenkel
            d.ellipse(B(sx - sr, by + sy - sr * 0.6, sx + sr, by + sy + sr * 0.6), fill=_light(col, 0.22))
        jaw = mouth * 10
        d.line([P(278, by + 8), P(236, by + 22 + jaw), P(190, by + 28 + jaw), P(150, by + 22)], fill=INK, width=max(2, int(5 * k)), joint="curve")   # langes Maul
        d.arc(B(132, by + 4, 168, by + 34), 60, 170, fill=INK, width=max(2, int(5 * k)))                                                        # Mundwinkel lächelt
        ell(186, by - 60, 210, by - 51, _dark(col, 0.35), shade=0)                     # Blasloch
        poly([(86, by + 46), (62, by + 96), (24, by + 138), (74, by + 122), (112, by + 92), (134, by + 60)], _dark(col, 0.12))   # lange, spitze Brustflosse
        eye(162, by - 8, 11)
        brow(162, by - 28, 11, 1)
        cheek(140, by + 12, 10)
    elif kind in ("cow", "kuh", "pig", "schwein"):                                  # Hoftiere: Kuh (gefleckt, Hörner, Euter) und Schwein (rosa, Rüsselscheibe, Ringelschwanz)
        cow = kind in ("cow", "kuh")
        col = (246, 244, 238) if cow else (246, 170, 176)
        dk = (52, 46, 50) if cow else _dark(col, 0.22)
        pink = (246, 176, 180) if cow else (250, 196, 200)
        top, bot, leg = (-268, -96, 104) if cow else (-206, -52, 62)
        wag = math.sin(t * 5) * 16
        if cow:
            stroke([(-160, -220), (-196, -190), (-200 + wag, -120)], 12, _dark(col, 0.2))
            ell(-216 + wag, -128, -186 + wag, -84, dk, shade=0)                     # Schwanzquaste
        else:
            stroke([(-146, -150), (-176, -160), (-182, -186 + wag * 0.3), (-164, -192), (-160, -172)], 9, _dark(col, 0.1))   # Ringelschwanz
        for lx in (-112, 52):                                                       # Beine auf der abgewandten Seite
            rr(lx, -leg, lx + 34, 0, 12, _dark(col, 0.2), shade=0)
            rr(lx - 2, -20, lx + 36, 0, 8, dk if cow else _dark(col, 0.4), shade=0)
        if cow:
            ell(-52, -128, 16, -66, pink, shade=0.15)                               # Euter
        ell(-166, top, 132, bot, col)
        if cow:                                                                     # Flecken, genau im Körper
            for a, b in ((-120, -66), (-10, 52)):
                band(-166, top, 132, bot, a, b, dk)
            ell(-150, top + 40, -90, top + 110, col, shade=0, line=False)
            ell(14, top + 96, 70, bot - 4, col, shade=0, line=False)
            ell(-64, top + 10, -6, top + 62, col, shade=0, line=False)
            d.ellipse(B(-166, top, 132, bot), outline=INK, width=o)
        else:
            ell(-80, -120, 60, -58, _light(col, 0.4), shade=0, line=False)
        for lx in (-86, 82):
            rr(lx, -leg, lx + 36, 0, 12, col, shade=0.25)
            rr(lx - 2, -20, lx + 38, 0, 8, dk if cow else _dark(col, 0.4), shade=0)
        hx, hy = (118, top - 34 + bob * 0.5) if cow else (104, -214 + bob * 0.5)
        if cow:
            for ex in (-1, 1):                                                      # Hörner und Ohren
                poly([(hx + ex * 44, hy - 66), (hx + ex * 62, hy - 124), (hx + ex * 22, hy - 78)], (240, 226, 190), shade=0)
                ell(hx + ex * 84 - 30, hy - 56, hx + ex * 84 + 30, hy - 18, dk if ex < 0 else col, shade=0)
            ell(hx - 80, hy - 84, hx + 80, hy + 70, col)
            d.chord(B(hx - 80, hy - 84, hx + 80, hy + 70), 150, 262, fill=dk)       # dunkler Fleck über einem Auge
            d.ellipse(B(hx - 80, hy - 84, hx + 80, hy + 70), outline=INK, width=o)
            ell(hx - 50, hy + 4, hx + 96, hy + 92, pink, shade=0.1)                 # Maul
            for nx in (hx + 4, hx + 50):
                ell(nx - 9, hy + 26, nx + 9, hy + 44, _dark(pink, 0.45), shade=0, line=False)
            mouthf(hx + 26, hy + 64, 20)
            eye(hx - 22, hy - 26, 16)
            eye(hx + 44, hy - 26, 16)
            brow(hx - 22, hy - 54, 15, 1)
            brow(hx + 44, hy - 54, 15, -1)
        else:
            for ex in (-1, 1):
                ox = hx + ex * 52
                poly([(ox - 30, hy - 50), (ox + ex * 26, hy - 122), (ox + 34, hy - 56)], col if ex > 0 else _dark(col, 0.2), shade=0)
            ell(hx - 92, hy - 84, hx + 92, hy + 80, col)
            ell(hx + 2, hy - 4, hx + 96, hy + 58, pink, shade=0.1)                  # Rüsselscheibe
            for nx in (hx + 34, hx + 66):
                ell(nx - 8, hy + 14, nx + 8, hy + 40, _dark(col, 0.45), shade=0, line=False)
            mouthf(hx + 44, hy + 66, 16)
            eye(hx - 8, hy - 30, 16)
            eye(hx + 58, hy - 30, 16)
            brow(hx - 8, hy - 58, 15, 1)
            brow(hx + 58, hy - 58, 15, -1)
            cheek(hx - 40, hy + 22, 16)
    elif kind in ("chimp", "schimpanse", "affe", "monkey"):                          # Schimpanse: sitzt aufrecht, lange Arme, helles Gesicht, runde Ohren
        col, face = (92, 66, 50), (226, 184, 150)
        wv = math.sin(t * 3) * 10
        if action == "puff":                                                        # aufgestelltes Fell: Haare sträuben sich rund um Körper und Kopf – das Tier wirkt größer
            pe = 1.0
            for cx_, cy_, rx_, ry_, n_ in ((0, -165, 92, 132, 22), (8, -372 + bob * 0.5, 108, 100, 20)):
                for i in range(n_):
                    an = 2 * math.pi * i / n_ + 0.1
                    if cy_ == -165 and math.sin(an) > 0.55:
                        continue                                                    # unten sitzen die Beine
                    q = 1 + 0.05 * math.sin(t * 24 + i * 1.9)
                    bx_, by_ = cx_ + math.cos(an) * rx_ * 0.9, cy_ + math.sin(an) * ry_ * 0.9
                    tx_, ty_ = cx_ + math.cos(an) * (rx_ + 46 * pe * q), cy_ + math.sin(an) * (ry_ + 46 * pe * q)
                    nx_, ny_ = -math.sin(an) * 17, math.cos(an) * 17
                    poly([(bx_ + nx_, by_ + ny_), (tx_, ty_), (bx_ - nx_, by_ - ny_)], _dark(col, 0.1) if i % 2 else col)
        for lx in (-84, 36):                                                        # angewinkelte Beine mit Füßen
            ell(lx, -86, lx + 70, -6, _dark(col, 0.12) if lx < 0 else col)
            ell(lx + 30, -30, lx + 96, 4, face, shade=0.15)
        stroke([(-62, -250), (-112, -170), (-104, -70)], 30, _dark(col, 0.18))      # Arm hinten
        ell(-122, -80, -84, -44, face, shade=0)
        rr(-84, -290, 84, -40, 70, col)
        ell(-46, -220, 50, -70, _light(col, 0.22), shade=0, line=False)             # hellerer Bauch
        stroke([(64, -250), (112, -200 - wv), (100, -300 - wv)] if action in ("point", "talk", "shake") or mouth > 0.1 else [(64, -250), (116, -170), (108, -70)], 30, col)
        hand = (100, -300 - wv) if action in ("point", "talk", "shake") or mouth > 0.1 else (108, -70)
        ell(hand[0] - 20, hand[1] - 22, hand[0] + 20, hand[1] + 18, face, shade=0)
        hx, hy = 8, -372 + bob * 0.5
        for ex in (-1, 1):                                                          # runde Ohren
            ell(hx + ex * 104 - 30, hy - 40, hx + ex * 104 + 30, hy + 24, face, shade=0.15)
        ell(hx - 104, hy - 98, hx + 104, hy + 92, col)
        ell(hx - 66, hy - 52, hx + 20, hy + 20, face, shade=0, line=False)          # Gesicht: zwei Augenfelder und die Schnauze
        ell(hx - 6, hy - 52, hx + 80, hy + 20, face, shade=0, line=False)
        ell(hx - 62, hy - 6, hx + 78, hy + 86, face, shade=0.1)
        for nx in (hx - 2, hx + 18):
            ell(nx - 5, hy + 16, nx + 5, hy + 28, _dark(face, 0.5), shade=0, line=False)
        mouthf(hx + 8, hy + 56, 26)
        eye(hx - 24, hy - 20, 16)
        eye(hx + 40, hy - 20, 16)
        brow(hx - 24, hy - 48, 15, 1)
        brow(hx + 40, hy - 48, 15, -1)
    elif kind in ("mosquito", "mücke", "muecke", "stechmücke", "fly", "fliege"):     # Mücke: schlank, lange Beine, langer Stechrüssel; Fliege: gedrungen, rote Augen
        fly = True
        fli = kind in ("fly", "fliege")
        by = -360 + bob * 2.5 + math.sin(t * 6) * 14
        fl = math.sin(t * 40) * 16
        col = (70, 76, 92) if fli else (132, 124, 118)
        for sx in (-50, -4):                                                        # Flügel
            d.ellipse(B(sx - 96, by - 128 - fl, sx + 30, by - 30), fill=(220, 240, 255, 190), outline=INK, width=max(2, int(4 * k)))
        for i, lx in enumerate((-40, -8, 26)):                                      # lange, geknickte Beine
            sw = math.sin(t * 6 + i) * 6
            stroke([(lx, by + 26), (lx - 26 + sw, by + 80), (lx - 10 + sw, by + (104 if fli else 150))], 5, _dark(col, 0.4))
        ab = (-178, by - 34, -6, by + 38) if not fli else (-150, by - 54, 0, by + 56)
        ell(*ab, col)
        for a in ((-150, -112, -74) if not fli else (-110, -60)):
            band(*ab, a, a + 14, _dark(col, 0.45))
        d.ellipse(B(*ab), outline=INK, width=o)
        ell(-30, by - 48, 56, by + 42, _dark(col, 0.15), shade=0.12)                # Brust
        hx = 92
        ell(hx - 50, by - 56, hx + 50, by + 44, _light(col, 0.18))                  # Kopf
        if not fli:
            stroke([(hx + 38, by + 16), (hx + 110, by + 62), (hx + 150, by + 96)], 7, _dark(col, 0.5))   # Stechrüssel
        for s in (0, 18):                                                           # Fühler
            stroke([(hx - 6 + s, by - 48), (hx + 8 + s, by - 96), (hx + 30 + s, by - 108)], 5, _dark(col, 0.5))
        eye(hx - 2, by - 12, 15)
        eye(hx + 34, by - 12, 15)
        brow(hx - 2, by - 38, 13, 1)
        brow(hx + 34, by - 38, 13, -1)
        cheek(hx - 28, by + 16, 11)
        mouthf(hx + 12, by + 24, 10)
    elif kind in ("lion", "löwe", "loewe"):
        # Löwe (Prüfung 17.11.2026, „zäher als ein Löwe“): kräftige Raubkatze mit dunkler Mähne, breiter Brust, dicken Pranken und Schwanzquaste;
        # action = "roar": Maul weit offen, Kopf gehoben; action = "walk": schreitet
        col = (228, 176, 92)
        belly = _light(col, 0.55)
        mane = (150, 92, 44)
        roar = action == "roar"
        walk = action in ("walk", "run")
        oy = bob * 0.25
        wag = math.sin(t * 2.6) * 14
        sw = math.sin(t * 6) if walk else 0.0
        tail = [(-176, -214 + oy), (-236, -226 + oy), (-276, -186 + oy + wag * 0.4), (-282 + wag * 0.5, -128 + oy + wag)]
        stroke(tail, 18, col)
        ell(tail[-1][0] - 22, tail[-1][1] - 14, tail[-1][0] + 22, tail[-1][1] + 34, mane, shade=0.1)   # Quaste

        def leg(front, e, c2):
            top = (96, -150 + oy) if front else (-132, -150 + oy)
            paw = (top[0] + 6 + 46 * e, -12 - 10 * max(0.0, e))
            knee = ((top[0] + paw[0]) / 2 + (10 if front else -18), (top[1] + paw[1]) / 2 + 4)
            stroke([top, knee, paw], 36, c2)
            ell(paw[0] - 24, paw[1] - 14, paw[0] + 34, paw[1] + 12, _light(c2, 0.25), shade=0)
        leg(True, -sw * 0.9 - 0.25, _dark(col, 0.22))                             # Beine der abgewandten Seite
        leg(False, sw * 0.9 - 0.3, _dark(col, 0.22))
        ell(-200, -262 + oy, 70, -122 + oy, col)                                 # Rumpf
        ell(-10, -280 + oy, 150, -112 + oy, col)                                 # breite Brust
        ell(-184, -254 + oy, 96, -132 + oy, col, shade=0, line=False)
        ell(-130, -178 + oy, 110, -124 + oy, belly, shade=0, line=False)
        leg(True, sw * 0.9, col)
        leg(False, -sw * 0.9, col)
        hx, hy = 170, -318 + oy - (14 if roar else 0)
        for i_m in range(12):                                                    # Mähne: Kranz aus Zotteln rund um den Kopf, bis auf die Brust
            a_m = i_m * math.pi / 6 + math.sin(t * 2 + i_m) * 0.03
            mx_, my_ = hx - 14 + math.cos(a_m) * 84, hy + 6 + math.sin(a_m) * 92
            ell(mx_ - 46, my_ - 46, mx_ + 46, my_ + 46, mane, shade=0)
        ell(hx - 104, hy - 96, hx + 76, hy + 112, mane, shade=0, line=False)
        ell(hx - 60, hy - 4, hx + 30, hy + 120, _dark(mane, 0.18), shade=0, line=False)   # dunklere Brustmähne
        for ex_ in (-40, 30):                                                    # runde Ohren
            ell(hx + ex_ - 20, hy - 86, hx + ex_ + 20, hy - 44, col, shade=0)
            ell(hx + ex_ - 9, hy - 76, hx + ex_ + 9, hy - 54, _dark(col, 0.35), shade=0, line=False)
        ell(hx - 60, hy - 62, hx + 70, hy + 56, col)                             # Kopf
        ell(hx + 4, hy - 2, hx + 86, hy + 54, belly, shade=0, line=False)        # helle Schnauze
        poly([(hx + 46, hy + 2), (hx + 74, hy + 2), (hx + 60, hy + 20)], (70, 44, 40), shade=0)   # Nase
        if roar:
            mh_ = 26 + 6 * math.sin(t * 14)
            d.ellipse(B(hx + 30, hy + 24, hx + 84, hy + 24 + 2 * mh_), fill=(110, 36, 46), outline=INK, width=max(2, int(5 * k)))
            for tx_ in (40, 70):                                                 # Reißzähne
                poly([(hx + tx_ - 6, hy + 28), (hx + tx_ + 6, hy + 28), (hx + tx_, hy + 46)], (250, 250, 244), shade=0, line=False)
            d.chord(B(hx + 40, hy + 24 + mh_, hx + 76, hy + 24 + 2 * mh_ - 4), 0, 180, fill=(240, 120, 130))
        else:
            mouthf(hx + 58, hy + 34, 14)
        eye(hx + 2, hy - 18, 15, "angry" if roar else None)
        eye(hx + 46, hy - 18, 15, "angry" if roar else None)
        brow(hx + 2, hy - 44, 14, 1)
        brow(hx + 46, hy - 44, 14, -1)
        cheek(hx - 26, hy + 22, 13)
    elif kind == "frog":
        # Pfeilgiftfrosch (Prüfung 19.11.2026): winziger, knallgelber Frosch mit dunklen Zehenspitzen und großen dunklen Augen; sitzt, die Kehle pulsiert.
        # action „hop“: er hüpft auf der Stelle.
        col = (250, 208, 40)
        dk = (60, 54, 60)
        hop = abs(math.sin(t * 5)) * 60 if action in ("hop", "walk", "run") else 0
        oy = -hop
        pulse = math.sin(t * 6) * 6
        stroke([(-96, -96 + oy), (-150, -60 + oy * 0.5), (-70, -22 + oy * 0.2)], 34, _dark(col, 0.16))      # Hinterbein der abgewandten Seite
        ell(-160, -196 + oy, 30, -58 + oy, col)                                                              # Rumpf: hinten flach …
        ell(-50, -252 + oy, 160, -62 + oy, col)                                                              # … vorn hoch aufgerichtet
        ell(-140, -186 + oy, 60, -70 + oy, col, shade=0, line=False)
        ell(-20, -150 + oy, 150, -58 + oy - pulse, _light(col, 0.5), shade=0, line=False)                    # helle Kehle
        stroke([(-80, -150 + oy), (-170, -110 + oy * 0.6), (-110, -30 + oy * 0.2), (-30, -16)], 40, col)   # gefaltetes Hinterbein
        for tz in (-14, 6, 26):                                                                             # lange Zehen mit dunklen Haftscheiben
            stroke([(-34, -16), (20 + tz, -8 + abs(tz) * 0.2)], 10, col)
            ell(14 + tz, -18 + abs(tz) * 0.2, 34 + tz, 2 + abs(tz) * 0.2, dk, shade=0)
        stroke([(96, -110 + oy), (110, -50 + oy * 0.4), (140, -14)], 26, col)                               # Vorderbein
        for tz in (-16, 4, 24):
            stroke([(140, -14), (160 + tz, -8)], 9, col)
            ell(154 + tz, -18, 172 + tz, 0, dk, shade=0)
        for sx_, sy_, r_ in ((-70, -170, 16), (-20, -200, 12), (-110, -120, 11)):                           # ein paar dunkle Flecken
            ell(sx_ - r_, sy_ + oy - r_ * 0.8, sx_ + r_, sy_ + oy + r_ * 0.8, _dark(col, 0.3), shade=0, line=False)
        hx, hy = 120, -210 + oy
        ell(hx - 90, hy - 56, hx + 86, hy + 66, col)                                                         # breiter Kopf
        for ex_ in (-34, 44):                                                                               # Augenhügel obenauf
            ell(hx + ex_ - 34, hy - 92, hx + ex_ + 34, hy - 24, col, shade=0)
            eye(hx + ex_ + 2, hy - 56, 23)
        brow(hx - 32, hy - 96, 18, 1)
        brow(hx + 46, hy - 96, 18, -1)
        cheek(hx - 52, hy + 14, 14)
        cheek(hx + 66, hy + 12, 12)
        if mouth > 0.1 or wide:
            mouthf(hx + 14, hy + 16, 16)
        else:
            d.arc(B(hx - 50, hy - 30, hx + 78, hy + 36), *((20, 160) if mood not in ("sad", "worried") else (200, 340)), fill=INK, width=max(2, int(6 * k)))
    elif kind == "platypus":
        # Schnabeltier (Prüfung 19.11.2026): brauner, flacher Pelzkörper, breiter Biberschwanz, dunkler Entenschnabel, Schwimmfüße; am Hinterbein der Giftsporn.
        # action „spur“: das Hinterbein ist angehoben, der Sporn steht groß und hell hervor (mit Warn-Ring).
        col = (150, 104, 70)
        belly = _light(col, 0.4)
        bill = (74, 70, 78)
        foot = (92, 80, 84)
        spur = action == "spur"
        cx -= 24 * k * f                                                                                    # der lange Schnabel passt ganz auf die Zeichenfläche
        sw = math.sin(t * 6) * (10 if action in ("walk", "run", "swim") else 3)
        wag = math.sin(t * 3) * 8
        poly([(-120, -150), (-200, -170 + wag), (-286, -150 + wag), (-300, -110 + wag), (-280, -76 + wag), (-190, -64 + wag * 0.5), (-120, -80)], _dark(col, 0.12))   # platter Biberschwanz
        for q in (-250, -220, -190):
            d.line((*P(q, -150 + wag), *P(q + 10, -84 + wag)), fill=_dark(col, 0.4), width=max(2, int(4 * k)))
        for lx in (-70, 110):                                                                               # Füße der abgewandten Seite
            stroke([(lx, -70), (lx + 8 - sw, -24)], 30, _dark(col, 0.25))
            poly([(lx - 12 - sw, -26), (lx + 52 - sw, -4), (lx - 14 - sw, 0)], _dark(foot, 0.2), shade=0)
        ell(-170, -210, 130, -50, col)                                                                       # Rumpf
        ell(-110, -110, 110, -54, belly, shade=0, line=False)
        hx, hy = 150, -150
        ell(hx - 80, hy - 70, hx + 60, hy + 62, col)                                                         # Kopf
        poly([(hx + 30, hy - 22), (hx + 120, hy - 26), (hx + 160, hy - 6), (hx + 164, hy + 16), (hx + 120, hy + 34), (hx + 30, hy + 30)], bill)   # breiter, flacher Schnabel
        d.line((*P(hx + 44, hy + 8), *P(hx + 156, hy + 8)), fill=INK, width=max(2, int(4 * k)))
        for nx_ in (132, 146):
            ell(hx + nx_ - 4, hy - 12, hx + nx_ + 4, hy - 4, INK, shade=0, line=False)
        rr(hx + 18, hy - 34, hx + 40, hy + 40, 10, _dark(bill, 0.2), shade=0)                                # Schnabelschild
        eye(hx - 4, hy - 22, 15)
        brow(hx - 4, hy - 46, 14, -1)
        cheek(hx - 26, hy + 18, 13)
        stroke([(104, -76), (112 + sw, -24)], 32, col)                                                       # Vorderfuß mit Schwimmhaut
        poly([(92 + sw, -28), (166 + sw, -6), (90 + sw, 2)], foot, shade=0)
        hx0, hy0 = (-96, -90)
        fx_, fy_ = (-150, -96) if spur else (-84 - sw, -22)                                                  # Hinterbein: angehoben zeigt es den Sporn
        stroke([(hx0, hy0), (fx_, fy_)], 36, col)
        if spur:
            poly([(fx_ - 6, fy_ - 22), (fx_ - 74, fy_ + 6), (fx_ - 8, fy_ + 26)], foot, shade=0)
            gl = 0.5 + 0.5 * math.sin(t * 7)
            rx_ = 62 + 12 * gl
            d.ellipse(B(fx_ + 8 - rx_, fy_ + 58 - rx_, fx_ + 8 + rx_, fy_ + 58 + rx_), outline=(236, 64, 60, 230), width=max(3, int(8 * k)))   # Warn-Ring um den Sporn
            poly([(fx_ - 16, fy_ + 16), (fx_ + 28, fy_ + 22), (fx_ + 12, fy_ + 98)], (250, 240, 214), shade=0)   # Giftsporn, gut sichtbar
            ell(fx_ + 2, fy_ + 102, fx_ + 22, fy_ + 126, (150, 220, 90), shade=0)                            # Gifttropfen
        else:
            poly([(fx_ - 14, -28), (fx_ + 60, -6), (fx_ - 16, 2)], foot, shade=0)
            poly([(fx_ - 10, -44), (fx_ - 34, -40), (fx_ - 14, -30)], (250, 240, 214), shade=0)             # kleiner Sporn an der Ferse
    elif kind == "puffer":
        # Kugelfisch (Prüfung 19.11.2026): rundlicher, sandgelber Fisch mit dunklen Tupfen, hellem Bauch und kleinem Schnabelmund; schwimmt.
        # action „puff“: Er bläst sich zur stacheligen Kugel auf.
        fly = True
        col = (232, 190, 96)
        belly = (250, 244, 226)
        puff = action == "puff"
        g = min(1.0, max(0.0, t / 0.7)) if puff else 0.0
        g = g + (math.sin(t * 5) * 0.03 if puff else 0)
        by = -300 + bob * (0.8 if puff else 1.8)
        rx_, ry_ = 130 + 60 * g, 92 + 96 * g
        wag = math.sin(t * 8) * 18
        poly([(-rx_ + 14, by - 12), (-rx_ - 66, by - 50 + wag), (-rx_ - 50, by + wag * 0.4), (-rx_ - 66, by + 50 + wag), (-rx_ + 14, by + 12)], _dark(col, 0.08))   # Schwanzflosse
        if puff:
            for i in range(22):                                                                             # Stacheln rundum
                a_ = i * math.tau / 22
                if abs(math.cos(a_) - 1) < 0.08:
                    continue
                x0, y0 = math.cos(a_) * (rx_ - 6), by + math.sin(a_) * (ry_ - 6)
                x1, y1 = math.cos(a_) * (rx_ + 34), by + math.sin(a_) * (ry_ + 34)
                nx_, ny_ = -math.sin(a_) * 13, math.cos(a_) * 13
                poly([(x0 - nx_, y0 - ny_), (x1, y1), (x0 + nx_, y0 + ny_)], (252, 246, 232) if math.sin(a_) > 0.2 else _light(col, 0.3), shade=0)
        fl = math.sin(t * 10) * 12
        poly([(-10, by - ry_ + 8), (-50, by - ry_ - 44 + fl * 0.4), (40, by - ry_ - 30), (50, by - ry_ + 10)], _dark(col, 0.06))   # Rückenflosse
        ell(-rx_, by - ry_, rx_, by + ry_, col)
        d.chord(B(-rx_ + 6, by - ry_ * 0.5, rx_ - 6, by + ry_ - 4), 10, 170, fill=belly)                    # heller Bauch
        d.ellipse(B(-rx_, by - ry_, rx_, by + ry_), outline=INK, width=o)
        for sx_, sy_, r_ in ((-70, -0.55, 13), (-20, -0.7, 15), (30, -0.5, 11), (-100, -0.2, 11), (-44, -0.3, 10), (70, -0.72, 9)):   # dunkle Tupfen auf dem Rücken
            xx, yy = sx_ * rx_ / 130, by + sy_ * ry_
            ell(xx - r_, yy - r_ * 0.8, xx + r_, yy + r_ * 0.8, _dark(col, 0.32), shade=0, line=False)
        poly([(-6, by + 16), (-52, by + 58 + fl), (22, by + 50)], _dark(col, 0.1))                           # Brustflosse
        ex_ = rx_ * 0.52
        eye(ex_, by - ry_ * 0.22, 22 if not puff else 26, "wide" if puff else None)
        brow(ex_, by - ry_ * 0.22 - 34, 18, 1)
        cheek(ex_ - 8, by + ry_ * 0.2, 15)
        mx_ = rx_ - 12
        ell(mx_ - 16, by + 4, mx_ + 20, by + 34, (240, 150, 140), shade=0)                                   # kleiner Schnabelmund
        d.line((*P(mx_ - 10, by + 19), *P(mx_ + 16, by + 19)), fill=INK, width=max(2, int(4 * k)))
    else:
        return None
    out = im.resize((im.width // S, im.height // S), Image.LANCZOS)
    return out, ax / S, gy / S, fly


CREATURES = ("cat", "dog", "spider", "ghost", "alien", "robot", "bird", "dino", "monster", "fish", "shark", "bee", "wasp", "agent", "virus", "cell", "brain", "shrimp", "mantis", "jelly", "axolotl", "tardigrade", "cheetah", "eagle", "flea", "diver", "fridge", "cow", "pig", "chimp", "mosquito", "fly", "dolphin", "lion", "whale", "chimera", "frog", "platypus", "puffer")


# ------------------------------------------------------------------ Werkstatt & Technik (Motor, Kran, Reifen, Getriebe …)

STEEL, STEEL_D, RED, BLUE_T, BLACK_R = (176, 182, 192), (120, 126, 138), (222, 70, 58), (60, 110, 200), (46, 46, 52)
ENG_BLOCK, ENG_BANK = (104, 110, 124), (124, 130, 144)


def _engine(d, cx, base, s=1.0, swing=0.0):
    """V-Motor (V8): Motorblock mit zwei schrägen Zylinderbänken, rote Ventildeckel, Riemen vorn, Ölwanne unten."""
    k = s
    r_ = _rotp((cx, base - 160 * k), swing)

    def R(pts):
        return [r_(p) for p in pts]
    _poly(d, R([(cx - 120 * k, base - 30 * k), (cx + 120 * k, base - 30 * k), (cx + 100 * k, base), (cx - 100 * k, base)]), (70, 74, 84))      # Ölwanne
    _poly(d, R([(cx - 130 * k, base - 170 * k), (cx + 130 * k, base - 170 * k), (cx + 120 * k, base - 30 * k), (cx - 120 * k, base - 30 * k)]), ENG_BLOCK)  # Block (dunkler Guss: hebt sich von grauen Wänden ab)
    for sg in (-1, 1):                                                       # Zylinderbänke (V-Form) mit roten Ventildeckeln
        bank = [(cx + sg * 20 * k, base - 170 * k), (cx + sg * 150 * k, base - 250 * k), (cx + sg * 200 * k, base - 215 * k), (cx + sg * 110 * k, base - 140 * k)]
        _poly(d, R(bank), ENG_BANK)
        cover = [(cx + sg * 60 * k, base - 225 * k), (cx + sg * 155 * k, base - 282 * k), (cx + sg * 190 * k, base - 258 * k), (cx + sg * 95 * k, base - 202 * k)]
        _poly(d, R(cover), RED)
        for j in range(4):                                                   # Zündkabel (blau)
            p0 = (cx + sg * (78 + j * 26) * k, base - (232 + j * 14) * k)
            d.line((*r_(p0), *r_((p0[0] + sg * 6 * k, p0[1] - 30 * k))), fill=BLUE_T, width=max(3, int(7 * k)))
    im = [(cx - 60 * k, base - 170 * k), (cx + 60 * k, base - 170 * k), (cx + 46 * k, base - 230 * k), (cx - 46 * k, base - 230 * k)]
    _poly(d, R(im), (186, 190, 198))                                         # Ansaugbrücke zwischen den Bänken
    for px_, py_, pr in ((0, -70, 40), (78, -120, 22), (-80, -122, 20)):     # Riemenscheiben (hell, Nabe dunkel)
        c = r_((cx + px_ * k, base + py_ * k))
        d.ellipse((c[0] - pr * k, c[1] - pr * k, c[0] + pr * k, c[1] + pr * k), fill=(200, 204, 212), outline=INK, width=max(3, int(6 * k)))
        q = pr * 0.35
        d.ellipse((c[0] - q * k, c[1] - q * k, c[0] + q * k, c[1] + q * k), fill=(90, 94, 104))
    pts = [r_((cx + px_ * k, base + py_ * k)) for px_, py_ in ((-40, -70), (-80, -142), (78, -142), (40, -70))]
    d.line(pts, fill=(40, 40, 46), width=max(3, int(6 * k)))                 # Keilriemen


def p_engine(d, x, t, s=1.0):
    """V8-Motor am Boden (auf einer kleinen Palette)."""
    _r(d, (x - 150, GROUND - 26, x + 150, GROUND), (178, 132, 86), 6)
    _engine(d, x, GROUND - 26)


def p_enginestand(d, x, t, s=1.0):
    """Motor auf dem roten Montageständer (wie in der Werkstatt)."""
    _r(d, (x - 16, GROUND - 330, x + 16, GROUND - 20), RED, 6)
    _r(d, (x - 170, GROUND - 26, x + 170, GROUND), RED, 8)
    _r(d, (x - 60, GROUND - 52, x + 60, GROUND - 22), RED, 6)
    _engine(d, x, GROUND - 330, 0.9)


def _crane(d, x, top_y=None):
    """Roter Motorkran: Fuß mit Rollen, Säule, Ausleger nach rechts; gibt den Hakenpunkt zurück."""
    base = GROUND
    _r(d, (x - 240, base - 34, x + 120, base - 10), RED, 8)                  # Fußgestell
    for wx in (x - 220, x + 100):
        _o(d, (wx - 20, base - 24, wx + 20, base + 6), BLACK_R)
    _r(d, (x - 180, base - 560, x - 150, base - 30), RED, 6)                 # Säule
    arm = [(x - 200, base - 560), (x + 300, base - 610), (x + 300, base - 580), (x - 200, base - 528)]
    _poly(d, arm, RED)                                                       # Ausleger
    _poly(d, [(x - 165, base - 330), (x + 60, base - 560), (x + 80, base - 548), (x - 150, base - 300)], (190, 60, 52), shade=0)   # Hydraulik
    hook = (x + 285, base - 590)
    return hook


def p_crane(d, x, t, s=1.0):
    """Motorkran (Werkstattkran) mit Kette – ohne Last."""
    hx, hy = _crane(d, x)
    d.line((hx, hy, hx, hy + 120), fill=(70, 70, 76), width=6)
    d.arc((hx - 18, hy + 110, hx + 18, hy + 146), 0, 220, fill=INK, width=8)


def p_enginehoist(d, x, t, s=1.0):
    """Motorkran hebt einen V8 – der Motor schwingt leicht und senkt sich langsam (zum Einbauen)."""
    hx, hy = _crane(d, x - 285)                                              # Haken (und Motor) in der Bildmitte des Dings
    drop = min(120, 40 * t)                                                  # senkt sich langsam ab
    swing = 4 * math.sin(t * 2.2)
    eng_top = hy + 170 + drop
    for sg in (-1, 1):                                                       # zwei Ketten zum Motor
        d.line((hx, hy, hx + sg * 90 + swing * 2, eng_top - 30), fill=(70, 70, 76), width=6)
    _engine(d, hx + swing * 2, eng_top + 262, 0.95, swing)


def p_tire(d, x, t, s=1.0):
    """Autoreifen mit Felge."""
    cy = GROUND - 150
    _o(d, (x - 150, cy - 150, x + 150, cy + 150), BLACK_R)
    for a in range(0, 360, 30):                                              # Profil
        c, s_ = math.cos(math.radians(a)), math.sin(math.radians(a))
        d.line((x + c * 132, cy + s_ * 132, x + c * 148, cy + s_ * 148), fill=(20, 20, 24), width=8)
    _o(d, (x - 86, cy - 86, x + 86, cy + 86), STEEL)                         # Felge
    for a in range(0, 360, 72):
        c, s_ = math.cos(math.radians(a)), math.sin(math.radians(a))
        d.line((x + c * 22, cy + s_ * 22, x + c * 78, cy + s_ * 78), fill=STEEL_D, width=14)
    _o(d, (x - 22, cy - 22, x + 22, cy + 22), STEEL_D)


def p_tires(d, x, t, s=1.0):
    """Reifenstapel (vier liegende Reifen)."""
    for i in range(4):
        y = GROUND - 70 - i * 74
        _r(d, (x - 150, y - 36, x + 150, y + 36), BLACK_R, 30)
        d.line((x - 120, y, x + 120, y), fill=(30, 30, 34), width=6)


def p_radiator(d, x, t, s=1.0):
    """Kühler: Rahmen mit Lamellen und Einfüllstutzen."""
    _r(d, (x - 200, GROUND - 320, x + 200, GROUND - 20), (90, 96, 108), 8)
    for xx in range(int(x - 180), int(x + 180), 16):
        d.line((xx, GROUND - 300, xx, GROUND - 40), fill=(150, 156, 168), width=6)
    _r(d, (x + 120, GROUND - 360, x + 170, GROUND - 316), STEEL, 6)
    _r(d, (x - 70, GROUND - 20, x - 40, GROUND), (70, 72, 80), 4)
    _r(d, (x + 40, GROUND - 20, x + 70, GROUND), (70, 72, 80), 4)


def p_gearbox(d, x, t, s=1.0):
    """Getriebe: blaues Gehäuse, Glocke zum Motor, Schaltstange oben."""
    _poly(d, [(x - 220, GROUND - 240), (x - 80, GROUND - 260), (x - 80, GROUND - 20), (x - 220, GROUND - 40)], (60, 100, 190))   # Kupplungsglocke
    _r(d, (x - 90, GROUND - 220, x + 200, GROUND - 30), (70, 120, 210), 40)
    for xx in (x - 20, x + 50, x + 120):                                     # Rippen
        d.line((xx, GROUND - 200, xx, GROUND - 50), fill=(50, 90, 170), width=8)
    _r(d, (x + 60, GROUND - 330, x + 80, GROUND - 210), STEEL, 4)           # Schaltstange
    _o(d, (x + 44, GROUND - 370, x + 96, GROUND - 318), BLACK_R)


def p_toolbox(d, x, t, s=1.0):
    """Roter Werkzeugwagen mit Schubladen."""
    _r(d, (x - 170, GROUND - 400, x + 170, GROUND - 30), RED, 12)
    for i in range(5):
        y = GROUND - 380 + i * 68
        _r(d, (x - 150, y, x + 150, y + 54), (236, 92, 78), 6)
        _r(d, (x - 50, y + 20, x + 50, y + 32), STEEL, 4, shade=False)
    for wx in (x - 140, x + 140):
        _o(d, (wx - 22, GROUND - 40, wx + 22, GROUND + 4), BLACK_R)


def p_wrench(d, x, t, s=1.0):
    """Großer Schraubenschlüssel (liegt schräg am Boden)."""
    r_ = _rotp((x, GROUND - 60), -20)
    _poly(d, [r_(p) for p in ((x - 170, GROUND - 76), (x + 140, GROUND - 76), (x + 140, GROUND - 46), (x - 170, GROUND - 46))], STEEL)
    for ex, sg in ((x + 170, 1), (x - 200, -1)):                             # Maulschlüssel-Köpfe (offen nach außen)
        c = r_((ex, GROUND - 61))
        a0 = (-20 if sg > 0 else 160) + 40
        for col, w in ((INK, 40), (STEEL, 26)):
            d.arc((c[0] - 44, c[1] - 44, c[0] + 44, c[1] + 44), a0, a0 + 280, fill=col, width=w)


def p_speedometer(d, x, t, s=1.0):
    """Tacho auf einem Ständer: Zeiger steigt mit der Zeit (Beschleunigung)."""
    cy = GROUND - 330
    _r(d, (x - 12, cy + 120, x + 12, GROUND - 10), (70, 72, 80), 4)
    _r(d, (x - 90, GROUND - 24, x + 90, GROUND), (70, 72, 80), 6)
    _o(d, (x - 170, cy - 170, x + 170, cy + 170), (40, 44, 52), shade=False)
    d.ellipse((x - 150, cy - 150, x + 150, cy + 150), fill=(250, 250, 246), outline=INK, width=5)
    for i in range(11):                                                      # Skala 0–300
        a = math.radians(150 + i * 24)
        d.line((x + math.cos(a) * 118, cy + math.sin(a) * 118, x + math.cos(a) * 140, cy + math.sin(a) * 140), fill=INK, width=6 if i % 2 == 0 else 3)
    for i in range(8, 11):                                                   # roter Bereich
        a0 = 150 + i * 24
        d.arc((x - 140, cy - 140, x + 140, cy + 140), a0 - 12, a0 + 12, fill=RED, width=10)
    val = min(1.0, 0.1 + t * 0.22)
    a = math.radians(150 + val * 240)
    d.line((x, cy, x + math.cos(a) * 120, cy + math.sin(a) * 120), fill=RED, width=10)
    _o(d, (x - 18, cy - 18, x + 18, cy + 18), INK, shade=False)


def p_scale(d, x, t, s=1.0):
    """Balkenwaage: neigt sich langsam zur schwereren Seite (rechts)."""
    tilt = 10 * min(1.0, t / 1.2)
    _r(d, (x - 120, GROUND - 26, x + 120, GROUND), (130, 96, 70), 6)
    _poly(d, [(x - 40, GROUND - 26), (x + 40, GROUND - 26), (x, GROUND - 120)], (160, 118, 82))
    r_ = _rotp((x, GROUND - 130), tilt)
    _poly(d, [r_(p) for p in ((x - 240, GROUND - 140), (x + 240, GROUND - 140), (x + 240, GROUND - 120), (x - 240, GROUND - 120))], (190, 140, 96))
    for sg in (-1, 1):
        px_, py_ = r_((x + sg * 210, GROUND - 140))
        _r(d, (px_ - 80, py_ - 22, px_ + 80, py_), (200, 200, 206), 6)
        if sg < 0:                                                           # links ein kleines Gewicht …
            _r(d, (px_ - 34, py_ - 70, px_ + 34, py_ - 20), (110, 112, 120), 6)
        else:                                                                # … rechts ein großes, schweres
            _poly(d, [(px_ - 70, py_ - 22), (px_ + 70, py_ - 22), (px_ + 50, py_ - 140), (px_ - 50, py_ - 140)], (70, 72, 80))
            _r(d, (px_ - 20, py_ - 170, px_ + 20, py_ - 136), (70, 72, 80), 8)


def p_piston(d, x, t, s=1.0):
    """Kolben mit Pleuelstange – bewegt sich auf und ab."""
    lift = 30 * math.sin(t * 6)
    top = GROUND - 330 - lift
    _r(d, (x - 30, top + 110, x + 30, GROUND - 60), STEEL_D, 10)             # Pleuel
    _o(d, (x - 60, GROUND - 120, x + 60, GROUND - 10), STEEL_D)
    _r(d, (x - 110, top, x + 110, top + 140), STEEL, 18)                     # Kolben
    for yy in (top + 22, top + 42, top + 62):
        d.line((x - 106, yy, x + 106, yy), fill=(90, 94, 104), width=5)


def p_carlift(d, x, t, s=1.0):
    """Hebebühne: zwei rote Säulen mit Tragarmen (ohne Auto)."""
    for sx in (x - 330, x + 330):
        _r(d, (sx - 34, GROUND - 620, sx + 34, GROUND), RED, 8)
        _r(d, (sx - 60, GROUND - 24, sx + 60, GROUND), (90, 94, 104), 6)
    lift = min(180, 70 * t)
    for sx, sg in ((x - 330, 1), (x + 330, -1)):
        _r(d, (min(sx, sx + sg * 200), GROUND - 140 - lift, max(sx, sx + sg * 200), GROUND - 116 - lift), (240, 200, 60), 6)


def p_oilcan(d, x, t, s=1.0):
    """Ölkanne mit Ausgießer."""
    _r(d, (x - 90, GROUND - 230, x + 90, GROUND), (240, 190, 50), 16)
    _r(d, (x - 50, GROUND - 270, x + 20, GROUND - 228), (200, 150, 40), 8)
    _poly(d, [(x + 70, GROUND - 200), (x + 190, GROUND - 300), (x + 204, GROUND - 286), (x + 90, GROUND - 170)], (200, 150, 40))
    _r(d, (x - 66, GROUND - 160, x + 66, GROUND - 80), (40, 40, 44), 8, shade=False)


def p_drill(d, x, t, s=1.0):
    """Akku-Bohrmaschine, steht auf ihrem Akku, der Bohrer zeigt nach rechts und rattert (der Heimwerker-Nachbar; Prüfung 18.11.2026)."""
    j = int(math.sin(t * 43) * 4)                                             # sie läuft: das ganze Gerät zittert leicht
    yel, dark = (244, 190, 48), (58, 60, 70)
    _poly(d, [(x - 78 + j, GROUND - 222), (x - 8 + j, GROUND - 222), (x - 30 + j, GROUND - 84), (x - 100 + j, GROUND - 84)], dark)    # Griff
    _r(d, (x - 126 + j, GROUND - 92, x + 22 + j, GROUND - 6), dark, 12)                                                         # Akku
    _r(d, (x - 110 + j, GROUND - 60, x + 6 + j, GROUND - 40), yel, 6, shade=False)
    _r(d, (x - 130 + j, GROUND - 318, x + 78 + j, GROUND - 212), yel, 26)                                                       # Gehäuse
    for i in range(3):                                                                                                          # Lüftungsschlitze
        _r(d, (x - 104 + i * 26 + j, GROUND - 292, x - 92 + i * 26 + j, GROUND - 240), dark, 4, shade=False)
    _poly(d, [(x + 76 + j, GROUND - 306), (x + 132 + j, GROUND - 286), (x + 132 + j, GROUND - 244), (x + 76 + j, GROUND - 224)], STEEL)   # Bohrfutter
    by = GROUND - 265 + int(math.sin(t * 61) * 3)
    _r(d, (x + 130 + j, by - 9, x + 232 + j, by + 9), (170, 176, 186), 6)                                                       # Bohrer
    _poly(d, [(x + 230 + j, by - 9), (x + 256 + j, by), (x + 230 + j, by + 9)], (170, 176, 186), shade=0)
    _r(d, (x - 22 + j, GROUND - 214, x + 6 + j, GROUND - 176), RED, 6, shade=False)                                             # Schalter
    for k in range(3):                                                                                                          # Lärm-Striche an der Spitze
        a = math.radians(-40 + k * 40)
        r0, r1 = 34 + (int(t * 12) % 3) * 6, 62 + (int(t * 12) % 3) * 6
        d.line((x + 262 + j + math.cos(a) * r0, by + math.sin(a) * r0, x + 262 + j + math.cos(a) * r1, by + math.sin(a) * r1), fill=INK, width=7)


def p_tattoomachine(d, x, t, s=1.0):
    """Tätowiermaschine (Prüfung 20.11.2026, Plan „Tattoo-Studio gegen Nagelstudio“): Stift-Maschine schräg, dunkler Griff, Motor oben,
    Nadel unten links mit Tintentropfen; sie surrt (zittert, Striche an der Spitze)."""
    j = int(math.sin(t * 47) * 3)
    dark = (40, 40, 48)
    tip = (x - 96 + j, GROUND - 14)
    d.line([(x + 96 + j, GROUND - 300), (x + 150 + j, GROUND - 330), (x + 190 + j, GROUND - 300)], fill=INK, width=12, joint="curve")   # Kabel
    d.line([(x - 40 + j, GROUND - 96), (x + 84 + j, GROUND - 288)], fill=INK, width=84)                                         # Körper mit Umriss
    d.line([(x - 40 + j, GROUND - 96), (x + 84 + j, GROUND - 288)], fill=dark, width=68)
    d.line([(x + 30 + j, GROUND - 204), (x + 84 + j, GROUND - 288)], fill=RED, width=68)                                        # Motor
    d.line([(x - 40 + j, GROUND - 96), (x - 4 + j, GROUND - 152)], fill=(96, 100, 112), width=68)                               # Griffstück
    d.line([(x - 70 + j, GROUND - 50), (x - 40 + j, GROUND - 96)], fill=INK, width=44)                                          # Spitze
    d.line([(x - 70 + j, GROUND - 50), (x - 40 + j, GROUND - 96)], fill=STEEL, width=30)
    d.line([tip, (x - 70 + j, GROUND - 50)], fill=INK, width=9)                                                                 # Nadel
    d.ellipse((tip[0] - 16, tip[1] - 6, tip[0] + 16, tip[1] + 14), fill=(30, 30, 36))                                           # Tintentropfen
    for k in range(3):                                                                                                          # Surr-Striche
        a = math.radians(150 + k * 35)
        r0, r1 = 34 + (int(t * 12) % 3) * 5, 60 + (int(t * 12) % 3) * 5
        d.line((tip[0] + math.cos(a) * r0, tip[1] - 20 + math.sin(a) * r0, tip[0] + math.cos(a) * r1, tip[1] - 20 + math.sin(a) * r1), fill=INK, width=7)


def p_nailfile(d, x, t, s=1.0):
    """Nagelfeile: lange rosa Feile mit rauer Fläche, lehnt schräg (Prüfung 20.11.2026)."""
    a, b = (x - 90, GROUND - 10), (x + 90, GROUND - 300)
    d.line([a, b], fill=INK, width=64)
    d.line([a, b], fill=(244, 150, 180), width=50)
    d.line([(x - 66, GROUND - 48), (x + 66, GROUND - 262)], fill=(226, 226, 232), width=30)
    for k in range(9):                                                                                                          # raue Körnung
        f = 0.08 + k * 0.1
        cx, cy = a[0] + (b[0] - a[0]) * f + 24, a[1] + (b[1] - a[1]) * f - 2
        d.line((cx - 9, cy - 6, cx + 9, cy + 6), fill=(170, 170, 180), width=5)
    if int(t * 3) % 2 == 0:                                                                                                     # Glitzer
        d.line((x + 120, GROUND - 330, x + 120, GROUND - 290), fill=(250, 206, 60), width=7)
        d.line((x + 100, GROUND - 310, x + 140, GROUND - 310), fill=(250, 206, 60), width=7)


def p_nailpolish(d, x, t, s=1.0):
    """Nagellack-Fläschchen: pinkes Glas mit schwarzem Deckel und Lichtreflex (Prüfung 20.11.2026)."""
    _r(d, (x - 34, GROUND - 300, x + 34, GROUND - 170), (40, 40, 48), 14)                                                       # Deckel mit Pinsel
    _r(d, (x - 84, GROUND - 180, x + 84, GROUND - 6), (236, 70, 120), 34)                                                       # Flasche
    _r(d, (x - 58, GROUND - 150, x - 34, GROUND - 60), (255, 190, 210), 10, 0, shade=False)
    _r(d, (x - 44, GROUND - 196, x + 44, GROUND - 168), (226, 190, 96), 8)


PROPS["tattoomachine"] = p_tattoomachine
PROPS["nailfile"] = p_nailfile
PROPS["nailpolish"] = p_nailpolish
PROP_ALIASES.update({"tattoomaschine": "tattoomachine", "tätowiermaschine": "tattoomachine", "tattoo machine": "tattoomachine", "tattoo gun": "tattoomachine", "tattoo_gun": "tattoomachine",
                     "tattoonadel": "tattoomachine", "tätowiernadel": "tattoomachine", "tattoo tool": "tattoomachine", "tattoo needle": "tattoomachine", "tattoo pen": "tattoomachine",
                     "nagelfeile": "nailfile", "feile": "nailfile", "nail file": "nailfile", "nail_file": "nailfile",
                     "nagellack": "nailpolish", "nail polish": "nailpolish", "nail_polish": "nailpolish", "gel-lack": "nailpolish", "nagelgel": "nailpolish", "uv-gel": "nailpolish", "aufbaugel": "nailpolish", "gellack": "nailpolish", "nagellackfläschchen": "nailpolish"})
SIZES["tattoomachine"] = (0.24, 1262)
SIZES["nailfile"] = (0.2, 1262)
SIZES["nailpolish"] = (0.14, 1262)


PROPS["drill"] = p_drill
PROP_ALIASES.update({"bohrmaschine": "drill", "bohrer": "drill", "akkuschrauber": "drill", "schlagbohrer": "drill", "bohrhammer": "drill"})
SIZES["drill"] = (0.45, 1262)


def _vacuum(d, x, t, broken):
    """Bodenstaubsauger (Prüfung 20.11.2026, Plan „Unpassend lachen“: „mein Staubsauger explodierte“ – kein Staubsauger im Bild):
    rotes Gehäuse auf Rädern, Schlauch im Bogen zum Saugrohr mit Bodendüse. Kaputt: Deckel aufgesprungen, Staubwolke, Knall-Zacken."""
    j = int(math.sin(t * 37) * 3) if not broken else 0                        # er läuft: zittert leicht
    body, dark = (214, 64, 58), (58, 60, 70)
    bx = x - 40 + j
    pts = [(bx - 30, GROUND - 250), (bx - 62, GROUND - 190), (bx - 70, GROUND - 120), (bx - 84, GROUND - 60), (bx - 112, GROUND - 22), (bx - 176, GROUND - 14)]   # Schlauch → Rohr → Düse
    d.line(pts[:3], fill=INK, width=30, joint="curve")
    d.line(pts[:3], fill=(96, 100, 112), width=18, joint="curve")
    d.line(pts[2:5], fill=INK, width=24, joint="curve")
    d.line(pts[2:5], fill=STEEL, width=12, joint="curve")
    _r(d, (bx - 236, GROUND - 34, bx - 96, GROUND - 4), dark, 10)                                                               # Bodendüse
    _o(d, (bx + 96, GROUND - 92, bx + 184, GROUND - 4), dark)                                                                 # Rad hinten
    _o(d, (bx + 124, GROUND - 64, bx + 156, GROUND - 32), STEEL, 5, shade=False)
    _r(d, (bx - 40, GROUND - 210, bx + 190, GROUND - 46), body, 62)                                                             # Gehäuse
    _r(d, (bx - 6, GROUND - 100, bx + 150, GROUND - 76), dark, 8, shade=False)                                                  # Lüftungsgitter
    _o(d, (bx + 96, GROUND - 180, bx + 150, GROUND - 126), (250, 206, 60), 6)                                                 # Schalter
    _o(d, (bx - 30, GROUND - 60, bx + 26, GROUND - 4), dark)                                                                  # Rad vorn
    if not broken:
        _r(d, (bx + 10, GROUND - 244, bx + 130, GROUND - 204), dark, 16)                                                        # Tragegriff
        return
    _poly(d, [(bx + 10, GROUND - 214), (bx + 150, GROUND - 300), (bx + 176, GROUND - 264), (bx + 40, GROUND - 190)], (178, 52, 50))   # Deckel steht offen
    k = min(1.0, max(0.0, t / 0.35))
    cx, cy = bx + 70, GROUND - 300
    if t < 1.1:                                                                                                                 # Knall-Zacken
        star = []
        for i in range(16):
            a = math.radians(i * 22.5)
            r = (150 if i % 2 == 0 else 84) * (0.4 + 0.6 * k)
            star.append((cx + math.cos(a) * r, cy - 40 + math.sin(a) * r))
        d.polygon(star, fill=(252, 214, 80), outline=INK, width=O)
    for i in range(7):                                                                                                          # Staubwolke quillt heraus
        ph = (t * 0.4 + i / 7) % 1
        r = 34 + ph * 70
        px = cx - 120 + i * 44 + math.sin(t * 1.3 + i * 2.1) * 16
        py = cy - 30 - ph * 230
        g = int(150 + ph * 60)
        d.ellipse((px - r, py - r, px + r, py + r), fill=(g, g - 8, g - 20), outline=INK if ph < 0.55 else None, width=5)
    for i in range(5):                                                                                                          # Staubflusen am Boden
        fx = bx - 260 + i * 118 + (i % 2) * 30
        d.ellipse((fx - 30, GROUND - 22, fx + 30, GROUND + 4), fill=(170, 160, 146), outline=INK, width=4)


def p_vacuum(d, x, t, s=1.0):
    _vacuum(d, x, t, False)


def p_vacuum_broken(d, x, t, s=1.0):
    _vacuum(d, x, t, True)


PROPS["vacuum"] = p_vacuum
PROPS["vacuum_broken"] = p_vacuum_broken
PROP_ALIASES.update({"staubsauger": "vacuum", "sauger": "vacuum", "vacuum cleaner": "vacuum", "bodenstaubsauger": "vacuum", "kaputter staubsauger": "vacuum_broken", "broken vacuum": "vacuum_broken"})
SIZES["vacuum"] = (0.8, 1262)
SIZES["vacuum_broken"] = (1.7, 1262)


PROPS.update({"engine": p_engine, "enginestand": p_enginestand, "crane": p_crane, "enginehoist": p_enginehoist, "tire": p_tire, "tires": p_tires,
              "radiator": p_radiator, "gearbox": p_gearbox, "toolbox": p_toolbox, "wrench": p_wrench, "speedometer": p_speedometer,
              "scale": p_scale, "piston": p_piston, "carlift": p_carlift, "oilcan": p_oilcan})
PROP_ALIASES.update({"motor": "engine", "motoren": "engine", "v8": "engine", "v8-motor": "engine", "v12": "engine", "w12": "engine", "w16": "engine",
                     "verbrenner": "engine", "automotor": "engine", "motorblock": "engine", "triebwerk": "engine",
                     "motorständer": "enginestand", "montageständer": "enginestand",
                     "kran": "crane", "motorkran": "crane", "werkstattkran": "crane", "flaschenzug": "crane",
                     "einbauen": "enginehoist", "motoreinbau": "enginehoist", "motortausch": "enginehoist",
                     "reifen": "tire", "rad": "tire", "räder": "tire", "felge": "tire", "felgen": "tire", "reifenstapel": "tires", "winterreifen": "tires",
                     "kühler": "radiator", "wasserkühler": "radiator", "getriebe": "gearbox", "schaltgetriebe": "gearbox", "sechsgang-getriebe": "gearbox",
                     "werkzeug": "toolbox", "werkzeugkasten": "toolbox", "werkzeugwagen": "toolbox", "schraubenschlüssel": "wrench", "schraubenschluessel": "wrench",
                     "tacho": "speedometer", "tachometer": "speedometer", "geschwindigkeit": "speedometer", "höchstgeschwindigkeit": "speedometer",
                     "waage": "scale", "gewicht": "scale", "kolben": "piston", "zylinder": "piston", "hebebühne": "carlift", "öl": "oilcan", "motoröl": "oilcan",
                     "ölkanne": "oilcan"})
SIZES.update({"engine": (0.9, 1255), "enginestand": (1.6, 1255), "crane": (2.3, 1255), "enginehoist": (2.3, 1255), "tire": (0.7, 1260), "tires": (1.2, 1255),
              "radiator": (0.75, 1255), "gearbox": (0.7, 1258), "toolbox": (1.1, 1255), "wrench": (0.3, 1262), "speedometer": (1.1, 1255),
              "scale": (0.9, 1255), "piston": (0.6, 1260), "carlift": (2.2, 1250), "oilcan": (0.5, 1262)})
