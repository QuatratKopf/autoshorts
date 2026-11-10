"""Motion-Grafik: bewegte Schaubilder im Stil moderner Erklärvideos – dunkler Verlauf mit Lichtpunkten, große Zahlen und
Daten, Countdown, Kalenderblatt, Fragezeichen mit Strahlen, Häuserreihen mit aufleuchtenden Fenstern, Plakette.

Eine Grafik-Szene hat "shot": "graphic" und "graphic": {"type": ..., ...}:
  number   {"kicker": "SCHWEDEN · NOV. 2024", "value": "5 MIO.", "label": "HAUSHALTE"}      große Zahl, läuft hoch
  timer    {"value": "72:00:00", "kicker": "SO LANGE BIST DU ALLEIN"}                         Countdown läuft, Balken füllt sich
  calendar {"kicker": "VORRAT FÜR", "value": "3", "label": "TAGE"}                            Kalenderblatt
  question {"text": "WARUM?"}                                                                Fragezeichen mit Strahlen
  houses   {"value": "45.000", "label": "HAUSHALTE", "dark": true}                            Häuserreihen, Fenster gehen an (oder aus)
  badge    {"kicker": "MIND.", "text": "72 STUNDEN"}                                          Plakette im Sternenkranz
  map      {"text": "72 STUNDEN ALLEIN", "value": "sweden,germany"}                           Europakarte, Länder leuchten auf (value = betroffene)
  city     {"kicker": "BERLIN · JANUAR", "text": "45.000 OHNE STROM", "dark": true}           Stadt von oben, Fenster gehen aus
Dazu der Look "neon": dieselbe Lichtstimmung (Nachtblau/Violett, Lichtpunkte) über normalen Szenen."""
import math
import random
import re
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .. import overlays

W, H = 1080, 1920
INK = (16, 12, 34)
WHITE = (250, 248, 255)
GOLD = (255, 200, 70)
ORANGE = (255, 138, 31)
THEMES = {"": ((58, 40, 150), (14, 10, 46)), "scary": ((40, 30, 96), (6, 6, 22)), "panic": ((120, 34, 70), (26, 8, 30)),
          "tense": ((110, 60, 120), (22, 10, 40)), "sad": ((40, 60, 130), (10, 14, 40)), "happy": ((90, 70, 190), (30, 16, 80)),
          "calm": ((58, 40, 150), (14, 10, 46))}
TYPES = ("number", "timer", "calendar", "question", "houses", "badge", "map", "city")

_bg, _spr = {}, {}
_BOK = [(random.Random(i).random(), random.Random(i + 50).random(), random.Random(i + 99).random()) for i in range(14)]


@lru_cache(maxsize=64)
def _font(size, kind="anton"):
    return overlays._cfont(size) if kind == "anton" else overlays.font(size, kind)


def _pop(t, start=0.0, dur=0.35):
    if t <= start:
        return 0.0
    k = min(1.0, (t - start) / dur)
    return 1 + 0.22 * math.sin(k * math.pi) * (1 - k) if k >= 1 else (1 - (1 - k) ** 3) * (1 + 0.18 * math.sin(k * math.pi))


def _sprite(r, col, alpha=0.34):
    key = (r, col, alpha)
    if key not in _spr:
        im = Image.new("L", (r * 4, r * 4), 0)
        ImageDraw.Draw(im).ellipse((r, r, r * 3, r * 3), fill=255)
        im = im.filter(ImageFilter.GaussianBlur(r * 0.35))
        rgba = Image.new("RGBA", im.size, col + (0,))
        rgba.putalpha(im.point(lambda v: int(v * alpha)))
        _spr[key] = rgba
    return _spr[key]


def bokeh(frame, t, strength=1.0):
    """Weiche Lichtpunkte, die langsam treiben (gibt jedem Bild Tiefe)."""
    soft = strength < 0.6                                      # über normalen Szenen: wenige, zarte Punkte – das Bild bleibt klar
    for i, (a, b, c) in enumerate(_BOK[: (5 if soft else 14)]):
        r = int((40 + c * 70) if soft else (60 + c * 130))
        x = (a * (W + 400) + t * (10 + c * 22) * (1 if i % 2 else -1)) % (W + 400) - 200
        y = (b * H + math.sin(t * 0.3 + i) * 40) % H
        col = ((255, 190, 120), (170, 140, 255), (120, 170, 255), (255, 150, 200))[i % 4]
        sp = _sprite(r, col, 0.16 if soft else 0.34)
        frame.paste(sp, (int(x - sp.width / 2), int(y - sp.height / 2)), sp)


def background(t, mood=""):
    mood = mood if mood in THEMES else ""
    if mood not in _bg:
        c0, c1 = THEMES[mood]
        g = Image.new("L", (W // 8, H // 8), 0)
        ImageDraw.Draw(g).ellipse((-30, -10, W // 8 + 30, H // 8 * 0.62), fill=255)
        g = g.filter(ImageFilter.GaussianBlur(24)).resize((W, H), Image.BILINEAR)
        im = Image.composite(Image.new("RGB", (W, H), c0), Image.new("RGB", (W, H), c1), g)
        d = ImageDraw.Draw(im)
        rnd = random.Random(7)
        for _ in range(46):
            x, y, r = rnd.randint(0, W), rnd.randint(0, 1100), rnd.choice((2, 2, 3))
            d.ellipse((x - r, y - r, x + r, y + r), fill=(230, 226, 255))
        _bg[mood] = im
    frame = _bg[mood].copy()
    bokeh(frame, t)
    return frame


def neon(frame, t):
    """Look „Neon-Nacht“ über einer normalen Szene: violette Nachtstimmung plus Lichtpunkte."""
    tint = _bg.get("_tint")
    if tint is None:
        tint = _bg["_tint"] = Image.new("RGB", (W, H), (186, 172, 250))
    out = ImageChops.multiply(frame.convert("RGB"), tint)
    out = Image.blend(out, frame.convert("RGB"), 0.3)
    bokeh(out, t, 0.4)
    return out


def tint(bg):
    """Kulisse für den Neon-Look: dunkler und violett, Lichter bleiben erhalten."""
    t = _bg.get("_tint")
    if t is None:
        t = _bg["_tint"] = Image.new("RGB", (W, H), (150, 132, 236))
    out = ImageChops.multiply(bg.convert("RGB"), t)
    return Image.blend(out, bg.convert("RGB"), 0.16)


def _center(d, y, text, f, fill=WHITE, stroke=0, shadow=True, spacing=0):
    if spacing:
        text = (" " * spacing).join(text)
    w = d.textlength(text, font=f)
    x = (W - w) / 2
    if shadow:
        d.text((x + 5, y + 7), text, font=f, fill=(0, 0, 0, 120))
    d.text((x, y), text, font=f, fill=fill, stroke_width=stroke, stroke_fill=INK)
    return w


def _fit(d, text, size, max_w=960, kind="anton"):
    f = _font(size, kind)
    while d.textlength(text, font=f) > max_w and size > 40:
        size -= 8
        f = _font(size, kind)
    return f


def _kicker(d, y, text, t, start=0.0):
    if not text or t < start:
        return
    text = text.upper()[:40]
    f = _fit(d, " ".join(text), 34, 940, "SemiBold")
    a = int(255 * min(1.0, (t - start) / 0.3))
    _center(d, y, text, f, fill=(214, 208, 255, a), shadow=False, spacing=1)


def _count(value, t, start=0.15, dur=1.1):
    """„5 MIO.“ / „45.000“ / „1,2“ → hochlaufende Zahl im selben Format; Text ohne Zahl bleibt, wie er ist."""
    m = re.match(r"^(\D*?)(\d[\d.]*)(,\d+)?(.*)$", str(value))
    if not m:
        return str(value)
    pre, whole, frac, post = m.group(1), m.group(2), m.group(3) or "", m.group(4)
    try:
        target = float(whole.replace(".", "") + (frac.replace(",", ".") if frac else ""))
    except ValueError:
        return str(value)
    k = 0.0 if t <= start else min(1.0, (t - start) / dur)
    k = 1 - (1 - k) ** 2.4
    cur = target * k
    if frac:
        txt = f"{cur:,.{len(frac) - 1}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    else:
        txt = f"{int(round(cur)):,}".replace(",", ".") if "." in whole else str(int(round(cur)))
    return pre + txt + post


def _rays(frame, cx, cy, t, col=(255, 220, 120), n=16, alpha=34):
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for i in range(n):
        a = t * 0.25 + i * math.tau / n
        d.polygon([(cx, cy), (cx + math.cos(a - 0.09) * 1500, cy + math.sin(a - 0.09) * 1500),
                   (cx + math.cos(a + 0.09) * 1500, cy + math.sin(a + 0.09) * 1500)], fill=col + (alpha,))
    frame.paste(lay, (0, 0), lay)


def _ring(d, cx, cy, r, t, col=GOLD, width=14):
    k = _pop(t, 0.05, 0.5)
    if k <= 0:
        return
    rr = r * k * (1 + 0.02 * math.sin(t * 3))
    d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=col + (255,), width=width)
    ph = (t * 0.6) % 1                                        # zweiter Ring läuft nach außen und verblasst
    r2 = rr * (1 + 0.25 * ph)
    d.ellipse((cx - r2, cy - r2, cx + r2, cy + r2), outline=col + (int(150 * (1 - ph)),), width=6)


def _house(d, x, y, s, lit, col):
    d.rectangle((x - 46 * s, y - 60 * s, x + 46 * s, y), fill=col, outline=INK, width=max(2, int(4 * s)))
    d.polygon([(x - 58 * s, y - 60 * s), (x, y - 108 * s), (x + 58 * s, y - 60 * s)], fill=(236, 238, 250), outline=INK, width=max(2, int(4 * s)))
    wc = (255, 214, 110) if lit else (44, 40, 86)
    for dx in (-24, 12):
        d.rectangle((x + dx * s, y - 44 * s, x + (dx + 14) * s, y - 22 * s), fill=wc)
    d.rectangle((x - 6 * s, y - 28 * s, x + 6 * s, y), fill=(60, 44, 70))
    if lit:
        d.ellipse((x - 70 * s, y - 80 * s, x + 70 * s, y + 20 * s), fill=(255, 214, 110, 22))


def _g_number(frame, g, t, dur):
    d = ImageDraw.Draw(frame, "RGBA")
    _kicker(d, 520, g.get("kicker"), t, 0.0)
    k = _pop(t, 0.1, 0.4)
    if k > 0:
        txt = _count(g.get("value", ""), t).upper()
        f = _fit(d, str(g.get("value", "")).upper(), int(250 * min(1.08, k)), 980)
        _center(d, 590 + (250 - f.size) / 2, txt, f, stroke=0)
        y = 590 + 310
        d.rounded_rectangle((W / 2 - 150 * min(1, k), y, W / 2 + 150 * min(1, k), y + 10), 5, fill=ORANGE)
    if g.get("label") and t > 0.45:
        _kicker(d, 940, g["label"], t, 0.45)
    if g.get("sub") and t > 0.9:
        f = _fit(d, g["sub"].upper(), 54, 940, "Bold")
        _center(d, 1020, g["sub"].upper()[:44], f, fill=ORANGE)


def _g_timer(frame, g, t, dur):
    d = ImageDraw.Draw(frame, "RGBA")
    _kicker(d, 520, g.get("kicker"), t, 0.0)
    m = re.match(r"^(\d{1,3}):(\d{2})(?::(\d{2}))?$", str(g.get("value") or "72:00:00"))
    hh, mm, ss = (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)) if m else (72, 0, 0)
    total = hh * 3600 + mm * 60 + ss
    run = max(0.0, t - 0.7)
    cur = max(0, total - int(run * run * 2600))                 # läuft erst langsam, dann rasend schnell herunter
    txt = f"{cur // 3600:02d}:{cur % 3600 // 60:02d}:{cur % 60:02d}"
    k = _pop(t, 0.1, 0.4)
    if k > 0:
        f = _fit(d, "00:00:00", int(230 * min(1.06, k)), 980)
        _center(d, 600, txt, f)
        for i, lab in enumerate(("STD", "MIN", "SEK")):
            fl = _font(30, "SemiBold")
            x = W / 2 + (i - 1) * 300
            d.text((x - d.textlength(lab, font=fl) / 2, 860), lab, font=fl, fill=(190, 184, 240))
        n = 28
        done = int(n * min(1.0, run / max(1.0, dur - 1.2)))
        for i in range(n):                                      # Balken aus Segmenten füllt sich
            x0 = 120 + i * (840 / n)
            d.rounded_rectangle((x0, 930, x0 + 840 / n - 8, 956), 6, fill=GOLD if i < done else (70, 60, 130))


def _g_calendar(frame, g, t, dur):
    d = ImageDraw.Draw(frame, "RGBA")
    k = _pop(t, 0.05, 0.45)
    if k <= 0:
        return
    w, h = 520 * min(1.05, k), 600 * min(1.05, k)
    cx, cy = W / 2, 760
    _ring(d, cx, cy, 470, t, (210, 150, 90), 10)
    d.rounded_rectangle((cx - w / 2 + 12, cy - h / 2 + 18, cx + w / 2 + 12, cy + h / 2 + 18), 30, fill=(0, 0, 0, 90))
    d.rounded_rectangle((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), 30, fill=(250, 240, 214), outline=INK, width=8)
    d.rounded_rectangle((cx - w / 2, cy - h / 2, cx + w / 2, cy - h / 2 + 110), 30, fill=(214, 70, 60), outline=INK, width=8)
    d.rectangle((cx - w / 2 + 4, cy - h / 2 + 70, cx + w / 2 - 4, cy - h / 2 + 110), fill=(214, 70, 60))
    for dx in (-150, 150):
        d.rounded_rectangle((cx + dx - 14, cy - h / 2 - 34, cx + dx + 14, cy - h / 2 + 40), 10, fill=(60, 56, 80), outline=INK, width=5)
    kick = str(g.get("kicker") or "").upper()[:22]
    if kick:
        fk = _fit(d, kick, 36, w - 60, "Bold")
        d.text((cx - d.textlength(kick, font=fk) / 2, cy - h / 2 + 34), kick, font=fk, fill=WHITE)
    val = _count(str(g.get("value", "")), t, 0.3, 0.8)
    fv = _fit(d, str(g.get("value", "")), 300, w - 80)
    d.text((cx - d.textlength(val, font=fv) / 2, cy - 150), val, font=fv, fill=(40, 30, 60))
    lab = str(g.get("label") or "").upper()[:14]
    fl = _fit(d, lab, 96, w - 80)
    d.text((cx - d.textlength(lab, font=fl) / 2, cy + 160), lab, font=fl, fill=(40, 30, 60))


def _g_question(frame, g, t, dur):
    cx, cy = W / 2, 740
    _rays(frame, cx, cy, t)
    d = ImageDraw.Draw(frame, "RGBA")
    _ring(d, cx, cy, 400, t)
    k = _pop(t, 0.1, 0.45)
    if k > 0:
        f = _font(int(620 * min(1.08, k)))
        w = d.textlength("?", font=f)
        wob = math.sin(t * 2.2) * 10
        d.text((cx - w / 2 + 10, cy - f.size * 0.62 + 14 + wob), "?", font=f, fill=(150, 90, 20))
        d.text((cx - w / 2, cy - f.size * 0.62 + wob), "?", font=f, fill=GOLD, stroke_width=8, stroke_fill=(120, 70, 10))
    txt = str(g.get("text") or "").upper()[:26]
    if txt and t > 0.5:
        ft = _fit(d, txt, 110, 940)
        _center(d, 1180, txt, ft)


def _g_houses(frame, g, t, dur):
    d = ImageDraw.Draw(frame, "RGBA")
    _kicker(d, 400, g.get("kicker"), t, 0.0)
    k = _pop(t, 0.1, 0.4)
    if k > 0:
        txt = _count(g.get("value", ""), t).upper()
        f = _fit(d, str(g.get("value", "")).upper(), int(210 * min(1.06, k)), 980)
        _center(d, 460, txt, f)
    _kicker(d, 700, g.get("label"), t, 0.4)
    rnd = random.Random(5)
    cols = ((200, 70, 70), (70, 110, 190), (230, 170, 70), (90, 150, 120), (160, 110, 180))
    dark = bool(g.get("dark"))
    i = 0
    for row, (y, s, n) in enumerate(((880, 0.62, 12), (1010, 0.8, 9), (1170, 1.0, 7))):
        d.rectangle((0, y, W, y + 8), fill=(30, 24, 70))
        for c in range(n):
            x = (c + 0.5) * W / n + (row % 2) * 20 - 10
            order = rnd.random()
            on = t > 0.5 + order * max(0.8, dur - 1.6)
            _house(d, x, y, s, (not on) if dark else on, cols[i % 5])
            i += 1


def _g_badge(frame, g, t, dur):
    cx, cy = W / 2, 760
    d = ImageDraw.Draw(frame, "RGBA")
    for i in range(12):                                         # Sternenkranz
        a = t * 0.3 + i * math.tau / 12
        k = _pop(t, 0.1 + i * 0.04, 0.3)
        if k <= 0:
            continue
        x, y, r = cx + math.cos(a) * 400, cy + math.sin(a) * 400, 26 * min(1.1, k)
        d.polygon([(x + math.cos(-math.pi / 2 + j * math.pi / 5) * (r if j % 2 == 0 else r * 0.45),
                    y + math.sin(-math.pi / 2 + j * math.pi / 5) * (r if j % 2 == 0 else r * 0.45)) for j in range(10)], fill=GOLD)
    k = _pop(t, 0.15, 0.45)
    if k <= 0:
        return
    txt = str(g.get("text") or "").upper()[:20]
    lay = Image.new("RGBA", (900, 420), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    ld.rounded_rectangle((34, 54, 884, 404), 30, fill=(0, 0, 0, 90))
    ld.rounded_rectangle((20, 40, 870, 390), 30, fill=(255, 206, 70), outline=(60, 40, 10), width=10)
    ld.rounded_rectangle((44, 64, 846, 366), 20, outline=(60, 40, 10), width=5)
    kick = str(g.get("kicker") or "").upper()[:24]
    if kick:
        fk = _fit(ld, " ".join(kick), 40, 760, "Bold")
        ld.text(((890 - ld.textlength(" ".join(kick), font=fk)) / 2, 84), " ".join(kick), font=fk, fill=(90, 60, 20))
    f = _fit(ld, txt, 190, 760)
    ld.text(((890 - ld.textlength(txt, font=f)) / 2, 150 + (190 - f.size) / 2), txt, font=f, fill=(50, 34, 10))
    lay = lay.rotate(-5 + math.sin(t * 1.6) * 1.5, resample=Image.BICUBIC, expand=True)
    s = min(1.06, k)
    lay = lay.resize((max(1, int(lay.width * s)), max(1, int(lay.height * s))), Image.BILINEAR)
    frame.paste(lay, (int(cx - lay.width / 2), int(cy - lay.height / 2)), lay)


# Europa, stark vereinfacht (Raster 0–100): große Flächen statt genauer Grenzen – erkennbar, nicht kartengenau
EUROPE = {
    "iberia": [(8, 70), (26, 66), (30, 74), (27, 86), (14, 90), (7, 84)],
    "france": [(26, 50), (38, 46), (44, 54), (42, 66), (30, 70), (24, 62)],
    "uk": [(24, 24), (30, 22), (33, 34), (30, 44), (22, 44), (24, 34)],
    "ireland": [(14, 32), (20, 30), (21, 40), (15, 42)],
    "benelux": [(38, 40), (44, 38), (45, 46), (39, 46)],
    "germany": [(44, 36), (56, 34), (58, 44), (55, 54), (46, 54), (44, 46)],
    "alps": [(44, 54), (58, 54), (60, 60), (46, 62)],
    "italy": [(46, 62), (54, 62), (62, 76), (68, 86), (62, 88), (54, 76), (48, 70)],
    "poland": [(57, 34), (72, 33), (74, 46), (58, 46)],
    "czech": [(57, 46), (74, 46), (72, 54), (58, 54)],
    "balkans": [(60, 56), (76, 54), (80, 70), (72, 80), (64, 72)],
    "denmark": [(46, 26), (51, 24), (52, 33), (47, 34)],
    "norway": [(44, 6), (54, 0), (58, 4), (52, 14), (49, 24), (43, 20)],
    "sweden": [(54, 4), (62, 2), (64, 14), (58, 28), (53, 24), (55, 14)],
    "finland": [(66, 2), (76, 4), (76, 20), (68, 22), (65, 12)],
    "baltics": [(68, 24), (78, 23), (79, 33), (70, 33)],
    "east": [(76, 34), (96, 30), (98, 56), (78, 56), (75, 46)],
}
REGION_WORDS = {"deutsch": "germany", "frankreich": "france", "franz": "france", "spanien": "iberia", "portugal": "iberia", "italien": "italy",
                "schweden": "sweden", "norwegen": "norway", "finnland": "finland", "dänemark": "denmark", "polen": "poland", "england": "uk",
                "großbritannien": "uk", "brit": "uk", "irland": "ireland", "niederlande": "benelux", "belgien": "benelux", "österreich": "alps",
                "schweiz": "alps", "tschechien": "czech", "balkan": "balkans", "griechenland": "balkans", "baltikum": "baltics", "ukraine": "east"}


def _g_map(frame, g, t, dur):
    """Europakarte: Länder leuchten nacheinander auf, Ringe pulsieren, Ausrufezeichen markieren betroffene Länder."""
    d = ImageDraw.Draw(frame, "RGBA")
    x0, y0, k = 60, 330, 9.6
    hot = [h for h in str(g.get("value") or "").lower().split(",") if h in EUROPE]
    names = list(EUROPE)
    for i, name in enumerate(names):
        pts = [(x0 + a * k, y0 + b * k) for a, b in EUROPE[name]]
        on = _pop(t, 0.15 + i * 0.07, 0.3) > 0
        lit = on and (not hot or name in hot)
        d.polygon([(a + 8, b + 10) for a, b in pts], fill=(0, 0, 0, 70))
        d.polygon(pts, fill=(250, 150, 40) if lit else (70, 56, 150), outline=(255, 210, 120) if lit else (110, 96, 200), width=5)
    marks = hot or names[::3]
    for j, name in enumerate(marks[:6]):
        pts = EUROPE[name]
        cx = x0 + sum(a for a, _ in pts) / len(pts) * k
        cy = y0 + sum(b for _, b in pts) / len(pts) * k
        st = 0.9 + j * 0.25
        if t < st:
            continue
        ph = ((t - st) * 0.7) % 1
        r = 50 + ph * 70
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(255, 226, 150, int(230 * (1 - ph))), width=7)
        pk = min(1.0, _pop(t, st, 0.3))
        d.rounded_rectangle((cx - 22 * pk, cy - 34 * pk, cx + 22 * pk, cy + 26 * pk), 10, fill=(250, 248, 255), outline=INK, width=4)
        f = _font(int(46 * pk) or 1)
        d.text((cx - d.textlength("!", font=f) / 2, cy - 36 * pk), "!", font=f, fill=(214, 60, 50))
    txt = str(g.get("text") or "").upper()[:30]
    if txt and t > 0.4:
        lay = Image.new("RGBA", (980, 150), (0, 0, 0, 0))
        ld = ImageDraw.Draw(lay)
        f = _fit(ld, txt, 86, 900, "ExtraBold")
        w = ld.textlength(txt, font=f)
        ld.rounded_rectangle((490 - w / 2 - 34, 14, 490 + w / 2 + 34, 136), 26, fill=(250, 240, 214), outline=INK, width=7)
        ld.text((490 - w / 2, 75 - f.size * 0.62), txt, font=f, fill=(40, 30, 60))
        lay = lay.rotate(-3, resample=Image.BICUBIC, expand=True)
        frame.paste(lay, (int(W / 2 - lay.width / 2), 190), lay)


_city = {}


def _g_city(frame, g, t, dur):
    """Stadt von oben: Häuserblöcke, Straßen, Bäume; Fenster gehen aus (dark) – ein Ring markiert den wichtigen Ort."""
    if "base" not in _city:
        rnd = random.Random(12)
        im = Image.new("RGB", (W, H + 400), (20, 14, 56))
        d0 = ImageDraw.Draw(im)
        wins = []
        y = 0
        while y < H + 400:
            bh = rnd.choice((150, 190, 230))
            x = -20
            while x < W:
                bw = rnd.choice((150, 190, 240, 290))
                if rnd.random() < 0.16:                                   # Park mit Bäumen
                    d0.rounded_rectangle((x + 10, y + 10, x + bw - 10, y + bh - 10), 18, fill=(26, 60, 70))
                    for _ in range(5):
                        tx, ty = rnd.randint(x + 30, x + bw - 30), rnd.randint(y + 30, y + bh - 30)
                        d0.ellipse((tx - 22, ty - 22, tx + 22, ty + 22), fill=(40, 120, 100), outline=(16, 40, 50), width=4)
                else:
                    col = rnd.choice(((70, 52, 150), (84, 60, 170), (60, 46, 130), (96, 70, 180)))
                    d0.rounded_rectangle((x + 10, y + 10, x + bw - 10, y + bh - 10), 12, fill=col, outline=(30, 20, 76), width=5)
                    d0.rounded_rectangle((x + 26, y + 26, x + bw - 26, y + bh - 26), 8, outline=tuple(min(255, c + 26) for c in col), width=4)
                    for wy in range(y + 44, y + bh - 50, 44):
                        for wx in range(x + 44, x + bw - 56, 46):
                            wins.append((wx, wy, rnd.random()))
                x += bw
            y += bh
        _city["base"], _city["wins"] = im, wins
    off = int((t * 26) % 400)
    view = _city["base"].crop((0, off, W, off + H))
    frame.paste(Image.blend(frame, view, 0.86), (0, 0))
    d = ImageDraw.Draw(frame, "RGBA")
    dark = bool(g.get("dark"))
    for wx, wy, r in _city["wins"]:
        yy = wy - off
        if -30 < yy < H:
            on = (t < 0.5 + r * max(1.0, dur - 1.5)) if dark else (r < 0.55 or t > 0.4 + r * 2)
            d.rectangle((wx, yy, wx + 22, yy + 20), fill=(255, 214, 110) if on else (36, 28, 84))
    cx, cy = W / 2 + math.sin(t * 0.5) * 30, 820
    _ring(d, cx, cy, 190, t, (120, 200, 255) if not dark else (255, 110, 120), 10)
    _kicker(d, 380, g.get("kicker"), t, 0.0)
    txt = str(g.get("text") or g.get("value") or "").upper()[:26]
    if txt and t > 0.4:
        f = _fit(d, txt, 150, 960)
        _center(d, 430, txt, f, stroke=8)


DRAW = {"map": _g_map, "city": _g_city, "number": _g_number, "timer": _g_timer, "calendar": _g_calendar, "question": _g_question, "houses": _g_houses, "badge": _g_badge}


def clean(g):
    """Prüft eine Grafik-Beschreibung aus dem Drehbuch; gibt die saubere Fassung zurück oder None."""
    if not isinstance(g, dict) or str(g.get("type") or "").lower() not in TYPES:
        return None
    out = {"type": str(g["type"]).lower()}
    for k in ("kicker", "value", "label", "sub", "text"):
        v = g.get(k)
        if isinstance(v, (str, int, float)) and not isinstance(v, bool) and str(v).strip():
            out[k] = str(v).strip()[:44]
    out["dark"] = g.get("dark") is True
    need = {"number": "value", "timer": "value", "calendar": "value", "houses": "value", "badge": "text", "question": None,
            "map": None, "city": None}[out["type"]]
    if need and need not in out:
        return None
    return out


def frame(g, t, dur, mood=""):
    f = background(t, mood)
    DRAW[g["type"]](f, g, t, max(dur, 1.0))
    return f
