"""Motion-Grafik: bewegte Schaubilder im Stil moderner Erklärvideos – dunkler Verlauf mit Lichtpunkten, große Zahlen und
Daten, Countdown, Kalenderblatt, Fragezeichen mit Strahlen, Häuserreihen mit aufleuchtenden Fenstern, Plakette.

Eine Grafik-Szene hat "shot": "graphic" und "graphic": {"type": ..., ...}:
  number   {"kicker": "SCHWEDEN · NOV. 2024", "value": "5 MIO.", "label": "HAUSHALTE"}      große Zahl, läuft hoch
  timer    {"value": "72:00:00", "kicker": "SO LANGE BIST DU ALLEIN"}                         Countdown läuft, Balken füllt sich
  calendar {"kicker": "VORRAT FÜR", "value": "3", "label": "TAGE"}                            Kalenderblatt
  question {"text": "WARUM?"}                                                                Fragezeichen mit Strahlen
  houses   {"value": "45.000", "label": "HAUSHALTE", "dark": true}                            Häuserreihen, Fenster gehen an (oder aus)
  badge    {"kicker": "MIND.", "text": "72 STUNDEN"}                                          Plakette im Sternenkranz
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
TYPES = ("number", "timer", "calendar", "question", "houses", "badge")

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


def _sprite(r, col):
    key = (r, col)
    if key not in _spr:
        im = Image.new("L", (r * 4, r * 4), 0)
        ImageDraw.Draw(im).ellipse((r, r, r * 3, r * 3), fill=255)
        im = im.filter(ImageFilter.GaussianBlur(r * 0.35))
        rgba = Image.new("RGBA", im.size, col + (0,))
        rgba.putalpha(im.point(lambda v: int(v * 0.34)))
        _spr[key] = rgba
    return _spr[key]


def bokeh(frame, t, strength=1.0):
    """Weiche Lichtpunkte, die langsam treiben (gibt jedem Bild Tiefe)."""
    for i, (a, b, c) in enumerate(_BOK[: int(8 + 6 * min(1.0, strength))]):
        r = int(60 + c * 130)
        x = (a * (W + 400) + t * (10 + c * 22) * (1 if i % 2 else -1)) % (W + 400) - 200
        y = (b * H + math.sin(t * 0.3 + i) * 40) % H
        col = ((255, 190, 120), (170, 140, 255), (120, 170, 255), (255, 150, 200))[i % 4]
        sp = _sprite(r, col)
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


DRAW = {"number": _g_number, "timer": _g_timer, "calendar": _g_calendar, "question": _g_question, "houses": _g_houses, "badge": _g_badge}


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
    need = {"number": "value", "timer": "value", "calendar": "value", "houses": "value", "badge": "text", "question": None}[out["type"]]
    if need and need not in out:
        return None
    return out


def frame(g, t, dur, mood=""):
    f = background(t, mood)
    DRAW[g["type"]](f, g, t, max(dur, 1.0))
    return f
