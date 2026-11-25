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
  versus   {"left": "ENERGY", "right": "KAFFEE", "kicker": "5 RUNDEN"}                        Duell: zwei Seiten, großes VS
  round    {"kicker": "RUNDE 1", "text": "KOFFEIN"}                                           schräges Banner fährt durchs Bild
  score    {"left": "ENERGY", "right": "KAFFEE", "value": "0:2", "kicker": "RUNDE 3/5"}       Punktestand-Tafel
  compare  {"left": "DOSE", "right": "KAFFEE", "value": "80 mg", "sub": "180 mg"}             zwei Balken wachsen (value links, sub rechts)
  podium   {"kicker": "KÖRPERTEILE", "text": "FUSS", "left": "HAND", "right": "BEIN"}         Siegertreppchen im Scheinwerfer
  share    {"value": "1 VON 7", "label": "TRÄUMT DAVON"}                                      Reihe von Menschen, der Anteil leuchtet auf
  news     {"kicker": "TALBLATT", "text": "GONDEL 7 ABGESTÜRZT", "sub": "Unglück im Nebel"}  Zeitungsseite fliegt herein
  pulse    {"value": "1", "label": "EINE SEKUNDE", "kicker": "..."}                           Herzschlag-Linie, rotes Pochen
  radio    {"kicker": "FUNK · KANAL 4", "text": "BERGWACHT", "sub": "..."}                    Funkspruch mit Wellenform
  distance {"value": "100 m", "left": "IHR", "right": "ZIEL", "label": "..."}                 Messlinie zwischen zwei Punkten
  days     {"text": "30 TAGE ÜBERLEBEN", "value": "1", "sub": "30", "label": "NOCH 2 MIN"}    Monatskalender: Tag value von sub, vergangene abgehakt
  chart    {"kicker": "AKTIENKURS", "value": "3 BIO.", "label": "DOLLAR", "dark": false}          Kurve schießt nach oben (dark = stürzt ab)
  phone    {"mode": "alert|lock|chat", "kicker": "...", "text": "...", "value": "...", ...}   Handy in der Hand (Eilmeldung, Sperrbildschirm, Nachrichten)
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
TYPES = ("number", "timer", "calendar", "question", "houses", "badge", "map", "city", "versus", "round", "score", "compare", "podium", "share", "news", "pulse", "radio", "distance", "days", "phone", "game", "chart", "radar", "size", "message", "chapter", "echo", "voice", "primes", "zeros")
LEFT, RIGHT = (150, 110, 255), (255, 150, 40)                # Farben der beiden Seiten im Duell
GREEN = (120, 230, 90)

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


def noir(bg):
    """Look „Düster“ (Mystery-Storys): Kulisse entsättigt, dunkler und kühl – Figuren und Dinge bleiben unverändert,
    das Licht kommt nur von der Lampe über den Figuren."""
    from PIL import ImageEnhance
    t = _bg.get("_noir")
    if t is None:
        t = _bg["_noir"] = Image.new("RGB", (W, H), (150, 156, 172))
    out = ImageEnhance.Color(bg.convert("RGB")).enhance(0.35)
    return ImageChops.multiply(out, t)


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
    lab = str(g.get("label") or "").upper()
    if len(lab) > 14:                                           # am Wortende kürzen: „JAHREN UNGELÖST“ stand als „JAHREN UNGELÖS“ auf dem Blatt (Video 197)
        lab = lab[:15].rsplit(" ", 1)[0] if " " in lab[:15] else lab[:14]
    fv = _fit(d, str(g.get("value", "")), 270 if lab else 300, w - 80)
    bb = d.textbbox((0, 0), str(g.get("value", "")) or "0", font=fv)          # Unterkante der Ziffern messen: die Zahl endet über der Beschriftung
    d.text((cx - d.textlength(val, font=fv) / 2, cy + (128 if lab else 190) - bb[3]), val, font=fv, fill=(40, 30, 60))
    fl = _fit(d, lab, 84, w - 80)
    if lab:
        bl = d.textbbox((0, 0), lab, font=fl)
        d.text((cx - d.textlength(lab, font=fl) / 2, cy + 158 - bl[1]), lab, font=fl, fill=(40, 30, 60))


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
    txt = " ".join(str(g.get("text") or "").upper().split())
    if len(txt) > 34:                                           # sehr langer Text: an der Wortgrenze kürzen, nie mitten im Wort („WENIGER ALS MINDESTL“, Video 213)
        txt = txt[:35].rsplit(" ", 1)[0] if " " in txt[:35] else txt[:34]
    lines = [txt]
    if len(txt) > 14 and " " in txt:                            # ab 15 Zeichen zweizeilig, möglichst gleich lange Zeilen
        ws_b = txt.split(" ")
        cut_b = min(range(1, len(ws_b)), key=lambda j: abs(len(" ".join(ws_b[:j])) - len(" ".join(ws_b[j:]))))
        lines = [" ".join(ws_b[:cut_b]), " ".join(ws_b[cut_b:])]
    lay = Image.new("RGBA", (900, 420), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    ld.rounded_rectangle((34, 54, 884, 404), 30, fill=(0, 0, 0, 90))
    ld.rounded_rectangle((20, 40, 870, 390), 30, fill=(255, 206, 70), outline=(60, 40, 10), width=10)
    ld.rounded_rectangle((44, 64, 846, 366), 20, outline=(60, 40, 10), width=5)
    kick = str(g.get("kicker") or "").upper()[:24]
    if kick:
        fk = _fit(ld, " ".join(kick), 40, 760, "Bold")
        ld.text(((890 - ld.textlength(" ".join(kick), font=fk)) / 2, 84), " ".join(kick), font=fk, fill=(90, 60, 20))
    if len(lines) == 1:
        f = _fit(ld, txt, 190, 760)
        ld.text(((890 - ld.textlength(txt, font=f)) / 2, 150 + (190 - f.size) / 2), txt, font=f, fill=(50, 34, 10))
    else:
        f = min((_fit(ld, ln_b, 112, 760) for ln_b in lines), key=lambda f_b: f_b.size)   # beide Zeilen in derselben Schriftgröße
        y_b = 136 + (224 - 2 * f.size - 8) / 2
        for j_b, ln_b in enumerate(lines):
            ld.text(((890 - ld.textlength(ln_b, font=f)) / 2, y_b + j_b * (f.size + 8)), ln_b, font=f, fill=(50, 34, 10))
    lay = lay.rotate(-5 + math.sin(t * 1.6) * 1.5, resample=Image.BICUBIC, expand=True)
    s = min(1.06, k)
    lay = lay.resize((max(1, int(lay.width * s)), max(1, int(lay.height * s))), Image.BILINEAR)
    frame.paste(lay, (int(cx - lay.width / 2), int(cy - lay.height / 2)), lay)


# Europa, stark vereinfacht (Raster 0–100): große Flächen statt genauer Grenzen – erkennbar, nicht kartengenau
REGIONS = {"iberia": ("esp", "prt"), "france": ("fra",), "uk": ("gbr",), "ireland": ("irl",), "benelux": ("nld", "bel", "lux"), "germany": ("deu",),
           "alps": ("aut", "che"), "italy": ("ita",), "poland": ("pol",), "czech": ("cze", "svk"), "denmark": ("dnk",), "norway": ("nor",),
           "sweden": ("swe",), "finland": ("fin",), "baltics": ("est", "lva", "ltu"), "east": ("ukr", "blr", "mda"),
           "balkans": ("grc", "hrv", "srb", "bih", "alb", "mkd", "bgr", "rou", "svn", "mne", "kos", "hun")}
EUROPE = REGIONS                                             # alte Bezeichnung: Regionen, die das Drehbuch nennen darf
REGION_WORDS = {"deutsch": "germany", "frankreich": "france", "franz": "france", "spanien": "iberia", "portugal": "iberia", "italien": "italy",
                "schweden": "sweden", "norwegen": "norway", "finnland": "finland", "dänemark": "denmark", "polen": "poland", "england": "uk",
                "großbritannien": "uk", "brit": "uk", "irland": "ireland", "niederlande": "benelux", "belgien": "benelux", "österreich": "alps",
                "schweiz": "alps", "tschechien": "czech", "balkan": "balkans", "griechenland": "balkans", "baltikum": "baltics", "ukraine": "east"}
_europe = {}


def _countries():
    """Ländergrenzen Europas (Natural Earth, gemeinfrei), vereinfacht – {kürzel: [[(x, y), …], …]}."""
    if not _europe:
        import json
        from pathlib import Path
        try:
            raw = json.loads((Path(__file__).with_name("europe.json")).read_text(encoding="utf-8"))
            _europe.update({k: [[tuple(q) for q in poly] for poly in v["polys"]] for k, v in raw.items()})
        except Exception:  # noqa: BLE001 – ohne Datei bleibt die Karte leer statt abzustürzen
            _europe["_"] = []
    return _europe


def _g_map(frame, g, t, dur):
    """Europakarte mit echten Ländergrenzen: Die betroffenen Länder leuchten auf, die Karte fährt auf sie zu, Ringe pulsieren."""
    d = ImageDraw.Draw(frame, "RGBA")
    lands = _countries()
    hot_regions = [h for h in str(g.get("value") or "").lower().split(",") if h in REGIONS]
    hot = [c for r in hot_regions for c in REGIONS[r] if c in lands]
    pts_all = [q for k, polys in lands.items() for poly in polys for q in poly]
    if not pts_all:
        return
    focus = [q for c in hot for poly in lands[c] for q in poly] or pts_all
    fx0, fx1 = min(q[0] for q in focus), max(q[0] for q in focus)
    fy0, fy1 = min(q[1] for q in focus), max(q[1] for q in focus)
    cx, cy = (fx0 + fx1) / 2, (fy0 + fy1) / 2
    span = max(fx1 - fx0, (fy1 - fy0) * 0.9, 9.0) * (2.3 if hot else 1.04)       # Nachbarländer bleiben sichtbar
    ax0, ax1 = min(q[0] for q in pts_all), max(q[0] for q in pts_all)
    ay0, ay1 = min(q[1] for q in pts_all), max(q[1] for q in pts_all)
    full = max(ax1 - ax0, (ay1 - ay0) * 0.9) * 1.04
    z = min(1.0, max(0.0, (t - 0.2) / 1.2))
    z = 1 - (1 - z) ** 3                                                         # von ganz Europa auf die Länder zufahren
    span = full + (min(span, full) - full) * z
    cx = (ax0 + ax1) / 2 + (cx - (ax0 + ax1) / 2) * z
    cy = (ay0 + ay1) / 2 + (cy - (ay0 + ay1) / 2) * z
    k = 980 / span
    ox, oy = W / 2 - cx * k, 800 - cy * k

    def P(q):
        return (ox + q[0] * k, oy + q[1] * k)
    order = sorted(lands, key=lambda c: c in hot)                                # betroffene Länder zuletzt, damit ihr Rand oben liegt
    for i, c in enumerate(order):
        lit = c in hot and t > 0.5 + hot.index(c) * 0.12
        glow = 0.5 + 0.5 * math.sin(t * 4) if lit else 0
        for poly in lands[c]:
            pp = [P(q) for q in poly]
            if max(a for a, _ in pp) < -50 or min(a for a, _ in pp) > W + 50 or max(b for _, b in pp) < 150 or min(b for _, b in pp) > 1500:
                continue
            d.polygon(pp, fill=(255, int(150 + 30 * glow), 40) if lit else (66, 54, 150), outline=(255, 226, 150) if lit else (120, 106, 210), width=5 if lit else 3)
    marks = hot[:6] or [c for c in ("deu", "fra", "esp", "ita", "pol", "swe") if c in lands]
    for j, c in enumerate(marks):
        big = max(lands[c], key=len)
        mx, my = P((sum(q[0] for q in big) / len(big), sum(q[1] for q in big) / len(big)))
        st = 1.0 + j * 0.22
        if t < st or not (60 < mx < W - 60 and 260 < my < 1400):
            continue
        ph = ((t - st) * 0.7) % 1
        r = 50 + ph * 80
        d.ellipse((mx - r, my - r, mx + r, my + r), outline=(255, 240, 190, int(230 * (1 - ph))), width=7)
        pk = min(1.0, _pop(t, st, 0.3))
        if pk < 0.15:
            continue
        d.rounded_rectangle((mx - 24 * pk, my - 36 * pk, mx + 24 * pk, my + 28 * pk), 10, fill=(250, 248, 255), outline=INK, width=4)
        f = _font(int(50 * pk) or 1)
        d.text((mx - d.textlength("!", font=f) / 2, my - 38 * pk), "!", font=f, fill=(214, 60, 50))
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

def _split(frame, t, k=1.0):
    """Zweigeteiltes Bild fürs Duell: rechte Hälfte warm, schräge Kante, leuchtende Trennlinie."""
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    off = (1 - min(1.0, k)) * 700
    top, bot = 640 + off, 440 + off
    d.polygon([(top, 0), (W, 0), (W, H), (bot, H)], fill=(255, 140, 30, 165))
    d.line([(top, 0), (bot, H)], fill=(255, 236, 190, 230), width=10)
    frame.paste(lay, (0, 0), lay)


def _pill(d, cx, y, text, f, fill, ink=INK, pad=28):
    w = d.textlength(text, font=f)
    box = (cx - w / 2 - pad, y, cx + w / 2 + pad, y + f.size + 26)
    d.rounded_rectangle((box[0] + 5, box[1] + 8, box[2] + 5, box[3] + 8), 26, fill=(0, 0, 0, 100))
    d.rounded_rectangle(box, 26, fill=fill, outline=INK, width=6)
    d.text((cx - w / 2, y + 9), text, font=f, fill=ink)


def _side_names(d, g, t, y=560, start=0.15):
    for i, (key, cx, col) in enumerate((("left", 270, LEFT), ("right", 810, RIGHT))):
        txt = str(g.get(key) or "").upper()[:14]
        k = _pop(t, start + i * 0.12, 0.35)
        if txt and k > 0:
            f = _fit(d, txt, 84, 440)
            dx = (1 - min(1.0, k)) * (-300 if i == 0 else 300)
            _pill(d, cx + dx, y, txt, f, col + (255,))


def _g_versus(frame, g, t, dur):
    _split(frame, t, _pop(t, 0.0, 0.4))
    d = ImageDraw.Draw(frame, "RGBA")
    _kicker(d, 420, g.get("kicker"), t, 0.5)
    _side_names(d, g, t, 1060, 0.2)
    k = _pop(t, 0.35, 0.4)
    if k > 0:
        cx, cy = W / 2, 780
        _ring(d, cx, cy, 250, max(0.0, t - 0.3), (255, 90, 110), 12)
        f = _font(int(330 * min(1.12, k)))
        w = d.textlength("VS", font=f)
        sh = math.sin(t * 30) * 6 * max(0.0, 1 - (t - 0.35) * 2)   # kurzes Zittern beim Einschlag
        d.text((cx - w / 2 + 10 + sh, cy - f.size * 0.6 + 12), "VS", font=f, fill=(90, 10, 30))
        d.text((cx - w / 2 + sh, cy - f.size * 0.6), "VS", font=f, fill=WHITE, stroke_width=10, stroke_fill=(230, 50, 80))


def _g_round(frame, g, t, dur):
    k = _pop(t, 0.05, 0.35)
    if k <= 0:
        return
    kick, txt = str(g.get("kicker") or "").upper()[:20], str(g.get("text") or "").upper()[:20]
    lay = Image.new("RGBA", (1500, 560), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    ld.rectangle((0, 44, 1500, 544), fill=(0, 0, 0, 90))
    ld.rectangle((0, 20, 1500, 520), fill=GREEN + (255,), outline=INK, width=10)
    for x in range(-40, 1540, 90):                              # laufende Streifen am Rand
        xx = x + (t * 120) % 90
        ld.polygon([(xx, 20), (xx + 40, 20), (xx + 10, 60), (xx - 30, 60)], fill=(20, 60, 20, 90))
        ld.polygon([(xx, 480), (xx + 40, 480), (xx + 10, 520), (xx - 30, 520)], fill=(20, 60, 20, 90))
    if kick:
        fk = _fit(ld, kick, 110, 900)
        ld.text((750 - ld.textlength(kick, font=fk) / 2, 90), kick, font=fk, fill=INK)
    f = _fit(ld, txt, 230 if kick else 300, 960)
    ld.text((750 - ld.textlength(txt, font=f) / 2, (200 if kick else 120) + (230 - f.size) / 2), txt, font=f, fill=WHITE, stroke_width=8, stroke_fill=INK)
    lay = lay.rotate(7, resample=Image.BICUBIC, expand=True)
    slide = (1 - min(1.0, k)) * -1400
    frame.paste(lay, (int(W / 2 - lay.width / 2 + slide), int(780 - lay.height / 2)), lay)


def _g_score(frame, g, t, dur):
    _split(frame, t)
    d = ImageDraw.Draw(frame, "RGBA")
    k = _pop(t, 0.05, 0.4)
    if k <= 0:
        return
    m = re.match(r"^\s*(\d{1,3})\s*[:\-–]\s*(\d{1,3})\s*$", str(g.get("value") or ""))
    a, b = (m.group(1), m.group(2)) if m else ("0", "0")
    cy = 760
    w, h = 900 * min(1.04, k), 520
    d.rounded_rectangle((W / 2 - w / 2 + 10, cy - h / 2 + 16, W / 2 + w / 2 + 10, cy + h / 2 + 16), 44, fill=(0, 0, 0, 110))
    d.rounded_rectangle((W / 2 - w / 2, cy - h / 2, W / 2 + w / 2, cy + h / 2), 44, fill=(22, 16, 50), outline=GOLD, width=10)
    kick = str(g.get("kicker") or "").upper()[:24]
    if kick:
        fk = _fit(d, kick, 48, 600, "Bold")
        _pill(d, W / 2, cy - h / 2 - 44, kick, fk, GOLD + (255,))
    fn = _font(300)
    win = int(a) - int(b)
    for i, (val, cx, col) in enumerate(((a, W / 2 - 230, LEFT), (b, W / 2 + 230, RIGHT))):
        lead = (win > 0 and i == 0) or (win < 0 and i == 1)
        bump = 1 + (0.08 * abs(math.sin(t * 3)) if lead and t > 0.6 else 0)
        f = _font(int(300 * bump))
        cur = _count(val, t, 0.3, 0.6)
        d.text((cx - d.textlength(cur, font=f) / 2, cy - 140 - (f.size - 300) / 2), cur, font=f, fill=col if not lead else WHITE, stroke_width=6, stroke_fill=col)
        name = str(g.get("left" if i == 0 else "right") or "").upper()[:14]
        if name:
            fl = _fit(d, name, 50, 380, "Bold")
            d.text((cx - d.textlength(name, font=fl) / 2, cy - h / 2 + 34), name, font=fl, fill=col)
    d.text((W / 2 - d.textlength(":", font=fn) / 2, cy - 160), ":", font=fn, fill=WHITE)


def _num(s):
    m = re.search(r"\d[\d.]*(?:,\d+)?", str(s or ""))
    try:
        return float(m.group(0).replace(".", "").replace(",", ".")) if m else None
    except ValueError:
        return None


def _g_compare(frame, g, t, dur):
    _split(frame, t)
    d = ImageDraw.Draw(frame, "RGBA")
    _kicker(d, 330, g.get("kicker"), t, 0.0)
    va, vb = _num(g.get("value")), _num(g.get("sub"))
    top = max(va or 0, vb or 0) or 1
    base, full = 1040, 560
    grow = 0.0 if t < 0.25 else min(1.0, (t - 0.25) / 1.0)
    grow = 1 - (1 - grow) ** 3
    for i, (key, val, cx, col) in enumerate((("value", va, 270, LEFT), ("sub", vb, 810, RIGHT))):
        hgt = max(40, full * ((val or 0) / top)) * grow
        d.rounded_rectangle((cx - 120 + 8, base - hgt + 12, cx + 120 + 8, base + 12), 26, fill=(0, 0, 0, 100))
        d.rounded_rectangle((cx - 120, base - hgt, cx + 120, base), 26, fill=col + (255,), outline=INK, width=8)
        txt = _count(str(g.get(key) or ""), t, 0.25, 1.0).upper()[:12]
        if txt and t > 0.25:
            f = _fit(d, str(g.get(key) or "").upper()[:12], 120, 460)
            w = d.textlength(txt, font=f)
            d.text((cx - w / 2, base - hgt - f.size - 40), txt, font=f, fill=WHITE, stroke_width=6, stroke_fill=INK)
        if val is not None and val == top and va != vb and grow >= 1:      # der Größere bekommt eine Krone
            y = base - hgt - 260 + math.sin(t * 3) * 8
            d.polygon([(cx - 70, y + 70), (cx - 80, y), (cx - 36, y + 34), (cx, y - 16), (cx + 36, y + 34), (cx + 80, y), (cx + 70, y + 70)], fill=GOLD, outline=INK)
    d.rectangle((60, base, W - 60, base + 10), fill=WHITE)
    _side_names(d, g, t, base + 50, 0.1)


def _g_podium(frame, g, t, dur):
    cx = W / 2
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))               # Scheinwerferkegel von oben
    ld = ImageDraw.Draw(lay)
    sw = math.sin(t * 0.8) * 60
    ld.polygon([(cx - 60 + sw, 0), (cx + 60 + sw, 0), (cx + 330, 1160), (cx - 330, 1160)], fill=(255, 240, 200, 46))
    frame.paste(lay, (0, 0), lay)
    d = ImageDraw.Draw(frame, "RGBA")
    kick = str(g.get("kicker") or "").upper()[:24]
    if kick and t > 0.1:
        _pill(d, cx, 330, kick, _fit(d, kick, 56, 700, "Bold"), WHITE + (255,))
    base = 1240
    for i, (num, x, hgt, col, key, st) in enumerate((("2", cx - 300, 240, (200, 206, 224), "left", 0.25), ("3", cx + 300, 170, (214, 150, 96), "right", 0.4),
                                                    ("1", cx, 360, GOLD, "text", 0.6))):
        k = _pop(t, st - 0.2, 0.35)
        if k <= 0:
            continue
        hh = hgt * min(1.0, k)
        d.rectangle((x - 150, base - hh, x + 150, base), fill=col, outline=INK, width=8)
        f = _font(int(min(170, hgt * 0.7)))
        if hh > hgt * 0.8:
            d.text((x - d.textlength(num, font=f) / 2, base - hh + 14), num, font=f, fill=INK)
        name = str(g.get(key) or "").upper()[:12] or "?"
        kk = _pop(t, st, 0.35)
        if kk > 0:
            fn = _fit(d, name, int((120 if key == "text" else 84) * min(1.1, kk)), 290 if key != "text" else 420)
            w = d.textlength(name, font=fn)
            y = base - hh - fn.size - 50 + (math.sin(t * 3) * 8 if key == "text" else 0)
            d.text((x - w / 2, y), name, font=fn, fill=WHITE if key == "text" else (214, 208, 255), stroke_width=6, stroke_fill=INK)
    if t > 0.9:                                                 # Konfetti für den Sieger
        rnd = random.Random(3)
        for i in range(40):
            x = rnd.random() * W
            y = ((t - 0.9) * (260 + rnd.random() * 300) + rnd.random() * 900) % 1250
            c = (GOLD, (255, 90, 130), (120, 200, 255), GREEN)[i % 4]
            d.rectangle((x, y, x + 16, y + 10), fill=c + (230,))
    d.rectangle((0, base, W, base + 12), fill=(30, 24, 70))


def share_parts(value):
    """„1 VON 7“ → (1, 7); höchstens 12 Menschen in der Reihe."""
    m = re.match(r"^\s*(\d{1,2})\s*(?:VON|/|AUS)\s*(\d{1,2})\s*$", str(value or "").upper())
    if not m:
        return None
    a, b = int(m.group(1)), int(m.group(2))
    return (a, b) if 1 <= a <= b <= 12 and b >= 2 else None


def _person(d, x, y, s, col, face=WHITE):
    d.ellipse((x - 34 * s, y - 6 * s, x + 34 * s, y + 8 * s), fill=(0, 0, 0, 70))
    d.line([(x - 14 * s, y - 70 * s), (x - 16 * s, y)], fill=INK, width=max(3, int(9 * s)))
    d.line([(x + 14 * s, y - 70 * s), (x + 16 * s, y)], fill=INK, width=max(3, int(9 * s)))
    d.rounded_rectangle((x - 36 * s, y - 160 * s, x + 36 * s, y - 60 * s), int(26 * s), fill=col, outline=INK, width=max(3, int(7 * s)))
    d.ellipse((x - 46 * s, y - 250 * s, x + 46 * s, y - 158 * s), fill=face, outline=INK, width=max(3, int(7 * s)))
    for dx in (-16, 16):
        d.ellipse((x + (dx - 6) * s, y - 214 * s, x + (dx + 6) * s, y - 198 * s), fill=INK)


def _g_share(frame, g, t, dur):
    d = ImageDraw.Draw(frame, "RGBA")
    a, b = share_parts(g.get("value")) or (1, 2)
    _kicker(d, 400, g.get("kicker"), t, 0.0)
    k = _pop(t, 0.1, 0.4)
    if k > 0:
        txt = f"{a} VON {b}"
        f = _fit(d, txt, int(250 * min(1.06, k)), 980)
        _center(d, 460, txt, f)
    lab = str(g.get("label") or "").upper()[:30]
    if lab and t > 0.5:
        _pill(d, W / 2, 770, lab, _fit(d, lab, 60, 860, "Bold"), (255, 90, 130, 255), WHITE)
    s = min(1.0, 7.6 / b) * 1.15
    gap = min(150, 960 / b)
    base = 1260
    d.rectangle((0, base, W, base + 12), fill=(30, 24, 70))
    for i in range(b):
        x = W / 2 + (i - (b - 1) / 2) * gap
        kk = _pop(t, 0.3 + i * 0.07, 0.3)
        if kk <= 0:
            continue
        hot = i >= b - a and t > 0.9 + 0.07 * b
        hop = abs(math.sin((t - 0.9) * 5)) * 26 * s if hot else 0
        if hot:
            d.ellipse((x - 90 * s, base - 300 * s - hop, x + 90 * s, base - 110 * s - hop), fill=(255, 214, 110, 60))
        _person(d, x, base - hop - (1 - min(1.0, kk)) * 60, s, GOLD if hot else (110, 96, 190), WHITE if hot else (204, 198, 236))

def _g_news(frame, g, t, dur):
    """Zeitungsseite fliegt herein und bleibt leicht schräg liegen (Fantasie-Blatt, keine echte Zeitung)."""
    k = _pop(t, 0.0, 0.45)
    if k <= 0:
        return
    if g.get("tv"):
        return _news_tv(frame, g, t, k)
    pw, ph = 860, 1080
    paper = Image.new("RGBA", (pw, ph), (236, 224, 196, 255))
    d = ImageDraw.Draw(paper)
    rnd = random.Random(11)
    for _ in range(500):                                        # Papierkörnung
        x, y = rnd.randrange(pw), rnd.randrange(ph)
        d.point((x, y), fill=(206, 192, 160, 255))
    d.rectangle((0, 0, pw - 1, ph - 1), outline=(120, 104, 80), width=6)
    name = str(g.get("kicker") or "TAGESBLATT").upper()[:18]
    f = _fit(d, name, 120, pw - 120)
    d.text((pw / 2 - d.textlength(name, font=f) / 2, 40), name, font=f, fill=(40, 34, 30))
    d.line([(50, 190), (pw - 50, 190)], fill=(40, 34, 30), width=8)
    d.line([(50, 206), (pw - 50, 206)], fill=(40, 34, 30), width=3)
    head = str(g.get("text") or "").upper()[:40]
    words, rows, cur = head.split(), [], ""
    for w in words:                                             # Schlagzeile auf höchstens drei Zeilen
        if cur and len(cur) + len(w) + 1 > 14:
            rows.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    rows = (rows + [cur])[:3]
    y = 236
    for r in rows:
        fr = _fit(d, r, 150, pw - 110)
        d.text((pw / 2 - d.textlength(r, font=fr) / 2, y), r, font=fr, fill=(30, 26, 24))
        y += fr.size + 16
    sub = str(g.get("sub") or "")[:44]
    if sub:
        fs = _fit(d, sub, 46, pw - 120, "SemiBold")
        d.text((pw / 2 - d.textlength(sub, font=fs) / 2, y + 6), sub, font=fs, fill=(90, 78, 66))
        y += 70
    d.rectangle((60, y + 20, pw - 60, y + 300), fill=(176, 160, 130), outline=(40, 34, 30), width=5)   # „Foto“
    d.polygon([(60, y + 300), (260, y + 140), (400, y + 240), (560, y + 100), (pw - 60, y + 300)], fill=(120, 106, 86))
    d.ellipse((pw - 220, y + 50, pw - 150, y + 120), fill=(226, 212, 180))
    yy = y + 330
    while yy < ph - 40:                                         # Textspalten als Linien
        for cx in (60, pw / 2 + 15):
            d.line([(cx, yy), (cx + pw / 2 - 75 - rnd.randrange(0, 60), yy)], fill=(130, 116, 96), width=7)
        yy += 26
    ang = 60 * (1 - min(1.0, k)) - 4
    scale = 0.5 + 0.5 * min(1.0, k)
    im = paper.resize((int(pw * scale), int(ph * scale)), Image.LANCZOS).rotate(ang, resample=Image.BICUBIC, expand=True)
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    sh.paste((0, 0, 0, 120), (0, 0), im.split()[3])
    frame.paste(sh, (int(W / 2 - im.width / 2 + 14), int(800 - im.height / 2 + 20)), sh)
    frame.paste(im, (int(W / 2 - im.width / 2), int(800 - im.height / 2)), im)


def _news_tv(frame, g, t, k):
    """Eilmeldung im Fernsehen (der Satz sagt „Im Fernsehen läuft …“): Fernseher mit Sendebild, rotes Band, Schlagzeile, Laufband –
    keine Zeitungsseite (Video 192). Fantasie-Sender, kein echtes Logo."""
    tw, th = 960, 700
    tv = Image.new("RGBA", (tw, th + 90), (0, 0, 0, 0))
    d = ImageDraw.Draw(tv)
    d.polygon([(tw / 2 - 150, th - 6), (tw / 2 + 150, th - 6), (tw / 2 + 210, th + 70), (tw / 2 - 210, th + 70)], fill=(26, 28, 36, 255), outline=INK)   # Fuß
    d.rounded_rectangle((0, 0, tw - 1, th - 1), 36, fill=(20, 22, 30, 255), outline=INK, width=8)
    sx0, sy0, sx1, sy1 = 30, 30, tw - 30, th - 46
    d.rounded_rectangle((sx0, sy0, sx1, sy1), 16, fill=(22, 40, 84, 255))
    for i in range(7):                                                       # Studio-Hintergrund: schräge Lichtbahnen
        d.polygon([(sx0 + i * 150 - 60, sy1), (sx0 + i * 150 + 30, sy1), (sx0 + i * 150 + 210, sy0), (sx0 + i * 150 + 120, sy0)], fill=(30, 54, 110, 255))
    d.rectangle((sx0, sy0, sx0 + 12, sy1), fill=(22, 40, 84, 255))
    d.rectangle((sx1 - 12, sy0, sx1, sy1), fill=(22, 40, 84, 255))
    kick = str(g.get("kicker") or "EILMELDUNG").upper()[:18]
    fk = _fit(d, kick, 64, 420, "Bold")
    blink = (t * 2) % 1 < 0.6
    d.rounded_rectangle((sx0 + 30, sy0 + 34, sx0 + 30 + d.textlength(kick, font=fk) + 96, sy0 + 34 + fk.size + 30), 12, fill=(206, 36, 46, 255))
    d.ellipse((sx0 + 52, sy0 + 34 + fk.size / 2 + 2, sx0 + 78, sy0 + 34 + fk.size / 2 + 28), fill=(255, 255, 255, 255) if blink else (206, 36, 46, 255))
    d.text((sx0 + 96, sy0 + 44), kick, font=fk, fill=WHITE)
    head = str(g.get("text") or "").upper()[:40]
    rows, cur = [], ""
    for w in head.split():
        if cur and len(cur) + len(w) + 1 > 16:
            rows.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    rows = (rows + [cur])[:3]
    y = sy0 + 170
    for r in rows:
        fr = _fit(d, r, 112, sx1 - sx0 - 80)
        d.text((sx0 + 40, y), r, font=fr, fill=WHITE, stroke_width=4, stroke_fill=(10, 16, 40, 255))
        y += fr.size + 14
    d.rectangle((sx0, sy1 - 96, sx1, sy1), fill=(240, 240, 244, 255))       # Laufband unten
    sub = str(g.get("sub") or "")[:44]
    if sub:
        fs = _fit(d, sub, 48, sx1 - sx0 - 60, "SemiBold")
        d.text((sx0 + 30, sy1 - 96 + (96 - fs.size) / 2 - 6), sub, font=fs, fill=(20, 24, 40, 255))
    d.ellipse((tw - 70, th - 34, tw - 50, th - 14), fill=(220, 60, 50, 255))
    scale = 0.6 + 0.4 * min(1.0, k)
    im = tv.resize((int(tv.width * scale), int(tv.height * scale)), Image.LANCZOS)
    glow = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((W / 2 - 620, 800 - 520, W / 2 + 620, 800 + 520), fill=(70, 110, 220, 46))
    frame.paste(glow.filter(ImageFilter.GaussianBlur(90)), (0, 0), glow.filter(ImageFilter.GaussianBlur(90)))
    frame.paste(im, (int(W / 2 - im.width / 2), int(800 - im.height / 2)), im)


def _beat(u):
    """Eine Herzschlag-Zacke, u = 0…1 innerhalb eines Schlags."""
    if 0.30 < u < 0.36:
        return -0.25 * math.sin((u - 0.30) / 0.06 * math.pi)
    if 0.40 < u < 0.46:
        return (u - 0.40) / 0.06 * 1.0
    if 0.46 <= u < 0.52:
        return 1.0 - (u - 0.46) / 0.06 * 1.6
    if 0.52 <= u < 0.58:
        return -0.6 + (u - 0.52) / 0.06 * 0.6
    if 0.66 < u < 0.80:
        return 0.18 * math.sin((u - 0.66) / 0.14 * math.pi)
    return 0.0


def _g_pulse(frame, g, t, dur):
    """Herzschlag-Linie läuft durchs Bild, darüber eine große Zahl – für den Moment, in dem alles stillsteht."""
    red = (255, 70, 100)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    beat = (t * 1.5) % 1.0
    ld.rectangle((0, 0, W, H), fill=(200, 20, 50, int(46 + 40 * max(0.0, 1 - beat * 3))))
    frame.paste(lay, (0, 0), lay)
    d = ImageDraw.Draw(frame, "RGBA")
    _kicker(d, 330, g.get("kicker"), t, 0.0)
    val = str(g.get("value") or "").upper()[:8]
    k = _pop(t, 0.1, 0.35)
    if val and k > 0:
        f = _fit(d, val, int(440 * min(1.08, k) * (1 + 0.05 * max(0.0, 1 - beat * 3))), 900)
        w = d.textlength(val, font=f)
        d.text((W / 2 - w / 2, 640 - f.size / 2), val, font=f, fill=WHITE, stroke_width=10, stroke_fill=red)
    lab = str(g.get("label") or "").upper()[:26]
    if lab and t > 0.5:
        _pill(d, W / 2, 900, lab, _fit(d, lab, 60, 860, "Bold"), red + (255,), WHITE)
    cy, amp, head = 1140, 150, min(1.0, t / 0.9)
    pts = []
    for x in range(0, int(W * head) + 1, 6):
        u = (x / 360.0 - t * 1.5) % 1.0
        pts.append((x, cy - _beat(u) * amp))
    if len(pts) > 1:
        d.line(pts, fill=red + (90,), width=26, joint="curve")
        d.line(pts, fill=(255, 190, 200), width=8, joint="curve")
        d.ellipse((pts[-1][0] - 16, pts[-1][1] - 16, pts[-1][0] + 16, pts[-1][1] + 16), fill=WHITE)


def _g_radio(frame, g, t, dur):
    """Funkspruch: Gerät mit Kanal-Anzeige, die Wellenform schlägt im Sprechtakt aus."""
    d = ImageDraw.Draw(frame, "RGBA")
    k = _pop(t, 0.0, 0.4)
    if k <= 0:
        return
    cx, cy = W / 2, 760
    w, h = 880 * min(1.03, k), 560
    d.rounded_rectangle((cx - w / 2 + 10, cy - h / 2 + 16, cx + w / 2 + 10, cy + h / 2 + 16), 50, fill=(0, 0, 0, 110))
    d.rounded_rectangle((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), 50, fill=(18, 26, 40), outline=GREEN, width=10)
    kick = str(g.get("kicker") or "FUNK").upper()[:22]
    fk = _fit(d, kick, 46, 640, "Bold")
    d.text((cx - w / 2 + 110, cy - h / 2 + 44), kick, font=fk, fill=(150, 226, 150))
    for i in range(3):                                          # Sendesymbol
        r = 16 + i * 14
        if (t * 3) % 3 >= i:
            d.arc((cx - w / 2 + 56 - r, cy - h / 2 + 68 - r, cx - w / 2 + 56 + r, cy - h / 2 + 68 + r), -50, 50, fill=GREEN, width=6)
    d.ellipse((cx - w / 2 + 48, cy - h / 2 + 60, cx - w / 2 + 64, cy - h / 2 + 76), fill=GREEN)
    txt = str(g.get("text") or "").upper()[:16]
    f = _fit(d, txt, 150, 760)
    d.text((cx - d.textlength(txt, font=f) / 2, cy - 150), txt, font=f, fill=WHITE, stroke_width=4, stroke_fill=INK)
    rnd = random.Random(5)
    n = 34
    for i in range(n):
        ph = rnd.random() * 6.28
        a = abs(math.sin(t * (5 + rnd.random() * 5) + ph)) * (0.35 + 0.65 * abs(math.sin(t * 2.2 + i * 0.4)))
        bh = 14 + a * 120
        x = cx - 360 + i * (720 / (n - 1))
        d.rounded_rectangle((x - 7, cy + 130 - bh, x + 7, cy + 130 + bh), 7, fill=GREEN if i % 5 else GOLD)
    sub = str(g.get("sub") or "").upper()[:30]
    if sub and t > 0.5:
        _pill(d, cx, cy + h / 2 + 40, sub, _fit(d, sub, 54, 820, "Bold"), GOLD + (255,))


def _g_distance(frame, g, t, dur):
    """Entfernung: zwei Punkte, dazwischen wächst die Messlinie, darüber die Strecke."""
    d = ImageDraw.Draw(frame, "RGBA")
    _kicker(d, 400, g.get("kicker"), t, 0.0)
    y, x0, x1 = 980, 130, W - 130
    grow = 0.0 if t < 0.2 else min(1.0, (t - 0.2) / 0.9)
    grow = 1 - (1 - grow) ** 3
    xe = x0 + (x1 - x0) * grow
    for x in range(int(x0), int(xe), 44):
        d.line([(x, y), (min(xe, x + 26), y)], fill=WHITE, width=10)
    for x in (x0, xe):
        d.line([(x, y - 44), (x, y + 44)], fill=WHITE, width=10)
    for i, (key, x, col) in enumerate((("left", x0, LEFT), ("right", x1, RIGHT))):
        if i == 1 and grow < 1:
            continue
        _ring(d, x, y, 90, max(0.0, t - (0.0 if i == 0 else 1.1)), col, 8)
        d.ellipse((x - 30, y - 30, x + 30, y + 30), fill=col, outline=INK, width=6)
        name = str(g.get(key) or "").upper()[:10]
        if name:
            fn = _fit(d, name, 60, 300, "Bold")
            cx = min(W - 60 - d.textlength(name, font=fn) / 2 - 28, max(60 + d.textlength(name, font=fn) / 2 + 28, x))
            _pill(d, cx, y + 90, name, fn, col + (255,))
    val = str(g.get("value") or "")
    cur = _count(val, t, 0.2, 0.9).upper()
    f = _fit(d, val.upper(), 260, 940)
    w = d.textlength(cur, font=f)
    d.text((W / 2 - w / 2, 560), cur, font=f, fill=GOLD, stroke_width=8, stroke_fill=INK)
    lab = str(g.get("label") or "").upper()[:30]
    if lab and t > 1.1:
        fl = _fit(d, lab, 64, 900, "Bold")
        d.text((W / 2 - d.textlength(lab, font=fl) / 2, 560 + f.size + 30), lab, font=fl, fill=WHITE)

def _g_days(frame, g, t, dur):
    """Monatskalender: vergangene Tage werden abgehakt, der heutige leuchtet, der letzte ist das Ziel."""
    d = ImageDraw.Draw(frame, "RGBA")
    k = _pop(t, 0.0, 0.4)
    if k <= 0:
        return
    total = int(max(2, min(35, _num(g.get("sub")) or 30)))
    today = int(max(1, min(total, _num(g.get("value")) or 1)))
    cols = 6 if total <= 30 else 7
    rows = -(-total // cols)
    cell, gap = 132, 12
    w = cols * cell + (cols - 1) * gap + 80
    h = 150 + rows * (cell + gap) + 60
    cx, top = W / 2, 760 - h / 2 + (1 - min(1.0, k)) * 200
    x0 = cx - w / 2
    d.rounded_rectangle((x0 + 10, top + 16, x0 + w + 10, top + h + 16), 40, fill=(0, 0, 0, 110))
    d.rounded_rectangle((x0, top, x0 + w, top + h), 40, fill=(26, 34, 70), outline=INK, width=8)
    d.rounded_rectangle((x0, top, x0 + w, top + 130), 40, fill=(255, 150, 40), outline=INK, width=8)
    d.rectangle((x0 + 4, top + 90, x0 + w - 4, top + 130), fill=(255, 150, 40))
    for dx in (-w / 2 + 110, w / 2 - 110):
        d.rounded_rectangle((cx + dx - 14, top - 34, cx + dx + 14, top + 40), 10, fill=(60, 56, 80), outline=INK, width=5)
    head = str(g.get("text") or g.get("kicker") or f"{total} TAGE").upper()[:26]
    fh = _fit(d, head, 76, w - 240)
    d.text((cx - d.textlength(head, font=fh) / 2, top + 65 - fh.size / 2), head, font=fh, fill=WHITE, stroke_width=3, stroke_fill=INK)
    fn = _font(62)
    done = (today - 1) * min(1.0, max(0.0, (t - 0.5) / 1.0))            # Haken laufen der Reihe nach durch
    for i in range(total):
        r, c = divmod(i, cols)
        x = x0 + 40 + c * (cell + gap)
        y = top + 160 + r * (cell + gap)
        n = i + 1
        is_today = n == today and t > 0.5 + 1.0 * (today > 1)
        last = n == total
        fill = (255, 214, 110) if last else ((60, 76, 140) if is_today else (38, 48, 96))
        if is_today:
            p = 6 + 4 * math.sin(t * 5)
            d.rounded_rectangle((x - p, y - p, x + cell + p, y + cell + p), 26, outline=WHITE, width=7)
        d.rounded_rectangle((x, y, x + cell, y + cell), 20, fill=fill)
        s = str(n)
        d.text((x + cell / 2 - d.textlength(s, font=fn) / 2, y + 28), s, font=fn, fill=INK if last else (WHITE if n >= today else (120, 132, 180)))
        if n <= done:                                                    # abgehakt
            d.line([(x + 30, y + 70), (x + 56, y + 98), (x + 104, y + 36)], fill=GREEN, width=14, joint="curve")
    lab = str(g.get("label") or "").upper()[:30]
    if lab and t > 0.7:
        _pill(d, cx, top + h + 30, lab, _fit(d, lab, 54, 820, "Bold"), (255, 70, 100, 255), WHITE)


def _g_phone(frame, g, t, dur):
    """Handy in der Hand, groß im Bild. mode: alert (Eilmeldung mit Betrag), lock (Sperrbildschirm mit Nachricht), chat (Nachrichten)."""
    k = _pop(t, 0.0, 0.45)
    if k <= 0:
        return
    mode = str(g.get("mode") or "alert").lower()
    pw, ph = 620, 1160
    lay = Image.new("RGBA", (pw + 240, ph + 300), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    ox, oy = 120, 20
    skin = (240, 200, 160)
    d.rounded_rectangle((ox - 70, oy + 620, ox + 40, oy + 1010), 50, fill=skin, outline=INK, width=8)             # Handfläche links
    d.rounded_rectangle((ox + 60, oy + ph - 60, ox + pw - 60, oy + ph + 280), 60, fill=skin, outline=INK, width=8)   # Arm
    d.rounded_rectangle((ox + 8, oy + 14, ox + pw + 8, oy + ph + 14), 80, fill=(0, 0, 0, 110))
    d.rounded_rectangle((ox, oy, ox + pw, oy + ph), 80, fill=(16, 16, 24), outline=INK, width=8)
    sx0, sy0, sx1, sy1 = ox + 26, oy + 26, ox + pw - 26, oy + ph - 26
    scr = {"alert": (24, 12, 20), "lock": (30, 44, 96), "chat": (236, 232, 224)}.get(mode, (24, 12, 20))
    d.rounded_rectangle((sx0, sy0, sx1, sy1), 58, fill=scr)
    d.rounded_rectangle((ox + pw / 2 - 80, oy + 44, ox + pw / 2 + 80, oy + 84), 20, fill=(0, 0, 0))
    cx = ox + pw / 2
    sw = sx1 - sx0 - 60
    kick = str(g.get("kicker") or "").upper()[:24]
    if mode == "lock":
        for i in range(6):                                              # weiches Hintergrundbild
            d.ellipse((sx0 + 40 + i * 90, sy1 - 420 + (i % 2) * 60, sx0 + 300 + i * 90, sy1 - 120), fill=(60 + i * 12, 70 + i * 6, 150))
        d.rounded_rectangle((sx0, sy1 - 200, sx1, sy1), 58, fill=(24, 34, 80))
        tm = str(g.get("value") or "07:49")[:6]
        ft = _fit(d, tm, 190, sw)
        d.text((cx - d.textlength(tm, font=ft) / 2, sy0 + 130), tm, font=ft, fill=WHITE)
        kk = _pop(t, 0.6, 0.35)
        if kk > 0:                                                      # Nachricht rutscht herein
            y = sy0 + 440 + (1 - min(1.0, kk)) * 80
            d.rounded_rectangle((sx0 + 24, y, sx1 - 24, y + 230), 36, fill=(250, 248, 244), outline=INK, width=5)
            d.ellipse((sx0 + 48, y + 26, sx0 + 108, y + 86), fill=GREEN, outline=INK, width=4)
            fk = _fit(d, kick or "NACHRICHT", 44, sw - 130, "Bold")
            d.text((sx0 + 124, y + 30), kick or "NACHRICHT", font=fk, fill=INK)
            msg = _short_msg(g.get("text"), 96)
            fm = _font(44, "SemiBold")
            lines = _lines(d, msg, fm, sw - 40)
            if len(lines) > 2:                                          # längere Nachricht („Du hast die Nachricht selbst gesendet. Aus dem Jahr 2035.“): kleiner und bis zu vier Zeilen – nie mitten im Satz abgeschnitten (Video 192)
                fm = _font(38, "SemiBold")
                lines = _lines(d, msg, fm, sw - 40)[:4]
            if len(lines) > 2:
                d.rounded_rectangle((sx0 + 24, y, sx1 - 24, y + 230 + (len(lines) - 2) * 50), 36, fill=(250, 248, 244), outline=INK, width=5)
                d.ellipse((sx0 + 48, y + 26, sx0 + 108, y + 86), fill=GREEN, outline=INK, width=4)
                d.text((sx0 + 124, y + 30), kick or "NACHRICHT", font=fk, fill=INK)
            for i, ln in enumerate(lines):
                d.text((sx0 + 48, y + 104 + i * (54 if len(lines) <= 2 else 50)), ln, font=fm, fill=(50, 50, 60))
    elif mode == "chat":
        d.rounded_rectangle((sx0, sy0, sx1, sy0 + 190), 58, fill=(250, 248, 244))
        d.rectangle((sx0, sy0 + 120, sx1, sy0 + 190), fill=(250, 248, 244))
        d.ellipse((sx0 + 30, sy0 + 84, sx0 + 116, sy0 + 170), fill=(200, 170, 230), outline=INK, width=4)
        name = (kick or "CHAT").title()
        d.text((sx0 + 134, sy0 + 100), name, font=_fit(d, name, 54, sw - 130, "Bold"), fill=INK)
        y = sy0 + 240
        for i, (key, mine) in enumerate((("text", False), ("sub", True), ("label", False))):
            msg = _short_msg(g.get(key), 90)
            kk = _pop(t, 0.4 + i * 0.7, 0.3)
            if not msg or kk <= 0:
                continue
            f = _font(46, "SemiBold")
            lines = _lines(d, msg, f, sw - 150)[:5]               # ganze Nachricht: „… liegt eine halbe Pizza“ brach nach drei Zeilen mitten im Satz ab (Video 192)
            bw = max(d.textlength(ln, font=f) for ln in lines) + 56
            bh = len(lines) * 58 + 40
            bx = (sx1 - 30 - bw) if mine else sx0 + 30
            yy = y + (1 - min(1.0, kk)) * 40
            d.rounded_rectangle((bx, yy, bx + bw, yy + bh), 30, fill=(150, 226, 150) if mine else WHITE, outline=INK, width=5)
            for j, ln in enumerate(lines):
                d.text((bx + 28, yy + 18 + j * 58), ln, font=f, fill=INK)
            y += bh + 26
    else:
        red = (255, 70, 90)
        if kick:
            fk = _fit(d, kick, 34, sw, "Bold")
            d.ellipse((cx - d.textlength(kick, font=fk) / 2 - 34, sy0 + 96, cx - d.textlength(kick, font=fk) / 2 - 14, sy0 + 116), fill=red if (t * 2) % 1 < 0.6 else scr)
            d.text((cx - d.textlength(kick, font=fk) / 2, sy0 + 86), kick, font=fk, fill=WHITE)
        bx0, by0, bx1, by1 = cx - 150, sy0 + 160, cx + 150, sy0 + 500                                     # Steckbrief-Bild: Umriss im Fadenkreuz
        d.rounded_rectangle((bx0, by0, bx1, by1), 26, fill=(250, 232, 220), outline=red, width=8)
        d.ellipse((cx - 70, by0 + 60, cx + 70, by0 + 200), fill=(90, 80, 110))
        d.pieslice((cx - 120, by0 + 210, cx + 120, by0 + 470), 180, 360, fill=(90, 80, 110))
        r = 110 + 10 * math.sin(t * 4)
        d.ellipse((cx - r, by0 + 150 - r, cx + r, by0 + 150 + r), outline=red, width=6)
        d.line([(cx - r - 20, by0 + 150), (cx + r + 20, by0 + 150)], fill=red, width=4)
        d.line([(cx, by0 + 150 - r - 20), (cx, by0 + 150 + r + 20)], fill=red, width=4)
        txt = str(g.get("text") or "").upper()[:16]
        f = _fit(d, txt, 150, sw)
        d.text((cx - d.textlength(txt, font=f) / 2, sy0 + 540), txt, font=f, fill=red)
        val = str(g.get("value") or "")
        if val:
            cur = _count(val, t, 0.4, 1.0).upper()
            fv = _fit(d, val.upper(), 110, sw)
            d.text((cx - d.textlength(cur, font=fv) / 2, sy0 + 720), cur, font=fv, fill=WHITE)
        btn = str(g.get("label") or "").upper()[:22]
        if btn:
            fb = _fit(d, btn, 44, sw - 80, "Bold")
            d.rounded_rectangle((sx0 + 50, sy0 + 880, sx1 - 50, sy0 + 980), 50, fill=(255, 150, 40), outline=INK, width=5)
            d.text((cx - d.textlength(btn, font=fb) / 2, sy0 + 930 - fb.size / 2 - 4), btn, font=fb, fill=INK)
    for i in range(4):                                                  # Finger rechts greifen ums Gerät
        y = oy + 600 + i * 104
        d.rounded_rectangle((ox + pw - 34, y, ox + pw + 62, y + 84), 40, fill=skin, outline=INK, width=8)
    d.rounded_rectangle((ox - 80, oy + 520, ox + 30, oy + 640), 50, fill=skin, outline=INK, width=8)   # Daumen
    ang = math.sin(t * 1.6) * 1.5 - 2
    im = lay.rotate(ang, resample=Image.BICUBIC)
    frame.paste(im, (int(W / 2 - im.width / 2), int(330 + (1 - min(1.0, k)) * 900)), im)


def _g_chart(frame, g, t, dur):
    """Kurs-/Wachstumskurve: Gitter, Linie zeichnet sich von links nach rechts und schießt am Ende steil nach oben (dark: stürzt ab)."""
    d = ImageDraw.Draw(frame, "RGBA")
    down = bool(g.get("dark"))
    col = (255, 96, 86) if down else GREEN
    _kicker(d, 400, g.get("kicker"), t, 0.0)
    x0, x1, y0, y1 = 110, 970, 500, 950                      # endet über den Untertiteln (die stehen bei etwa 1310–1440)
    d.rounded_rectangle((x0 - 40, y0 - 40, x1 + 40, y1 + 40), 34, fill=(10, 8, 34, 150), outline=(255, 255, 255, 46), width=4)
    for i in range(5):                                        # Gitterlinien
        y = y0 + (y1 - y0) * i / 4
        d.line((x0, y, x1, y), fill=(255, 255, 255, 30), width=3)
    for i in range(1, 6):
        x = x0 + (x1 - x0) * i / 6
        d.line((x, y0, x, y1), fill=(255, 255, 255, 16), width=3)
    rnd = random.Random(11)
    n = 44
    pts = []
    for i in range(n + 1):
        u = i / n
        base = 0.06 + 0.1 * u + 0.84 * u ** 4.2            # lange flach, dann steil
        wob = (rnd.random() - 0.5) * 0.07 * (0.4 + u) + 0.03 * math.sin(u * 19)
        v = max(0.02, min(0.98, base + wob))
        if i == n:
            v = 0.97
        if down:
            v = 1.0 - v * 0.94
        pts.append((x0 + (x1 - x0) * u, y1 - (y1 - y0) * v))
    k = 0.0 if t < 0.15 else min(1.0, (t - 0.15) / min(1.9, max(1.0, dur * 0.55)))
    k = k * k * (3 - 2 * k)
    m = max(1, int(round(k * n)))
    shown = pts[:m + 1]
    if len(shown) >= 2:
        d.polygon(shown + [(shown[-1][0], y1), (x0, y1)], fill=col + (46,))
        d.line(shown, fill=col + (255,), width=14, joint="curve")
        hx, hy = shown[-1]
        pr = 20 + 5 * math.sin(t * 7)
        d.ellipse((hx - pr * 2.2, hy - pr * 2.2, hx + pr * 2.2, hy + pr * 2.2), fill=col + (50,))
        d.ellipse((hx - pr, hy - pr, hx + pr, hy + pr), fill=WHITE + (255,), outline=col + (255,), width=7)
        if k >= 1.0:                                          # Pfeil in Kursrichtung
            a = _pop(t - 0.15 - min(1.9, max(1.0, dur * 0.55)), 0.0, 0.3)
            if a > 0:
                s_ = 64 * min(1.1, a)
                dy = 1 if down else -1
                ax, ay = min(hx, x1 - 30), hy + dy * 34
                d.polygon([(ax, ay + dy * s_), (ax - s_ * 0.72, ay), (ax + s_ * 0.72, ay)], fill=col + (255,), outline=INK + (255,), width=5)
    d.line((x0, y0 - 10, x0, y1, x1 + 10, y1), fill=(255, 255, 255, 150), width=6)
    val = str(g.get("value") or "").strip()
    y = y1 + 64
    if val and t > 0.5:
        kk = _pop(t, 0.5, 0.4)
        f = _fit(d, val.upper(), int(150 * min(1.06, kk)), 940)
        _center(d, y + (150 - f.size) / 2, _count(val, t, 0.5, 1.4).upper(), f, fill=WHITE)
        y += 168
    if g.get("label") and t > 0.7:
        f = _fit(d, str(g["label"]).upper(), 60, 940, "Bold")
        _center(d, y, str(g["label"]).upper()[:40], f, fill=ORANGE if not down else (255, 150, 140))


def _g_radar(frame, g, t, dur):
    """Radarschirm: Ringe, umlaufender Suchstrahl, ein Leuchtpunkt. Mit sub="lost" blinkt der Punkt und erlischt – das Signal ist weg."""
    grn, dim = (110, 255, 170), (40, 120, 90)
    cx, cy, r = W // 2, 760, 380
    k = _pop(t, 0.0, 0.35)
    if k <= 0:
        return
    r = int(r * min(1.04, k))
    lay = frame.convert("RGB")                                                 # deckend zeichnen, halbtransparente Flächen mischen sich richtig
    d = ImageDraw.Draw(lay, "RGBA")
    d.ellipse((cx - r - 26, cy - r - 26, cx + r + 26, cy + r + 26), fill=(18, 22, 30, 255), outline=(70, 84, 100, 255), width=12)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(8, 34, 30, 255))
    ang = (t * 150) % 360
    for i in range(40):                                                        # Nachleuchten hinter dem Suchstrahl
        d.pieslice((cx - r, cy - r, cx + r, cy + r), ang - 2.2 * (i + 1), ang - 2.2 * i, fill=(60, 230, 140, int(120 * (1 - i / 40) ** 1.6)))
    for q in (0.25, 0.5, 0.75, 1.0):
        d.ellipse((cx - r * q, cy - r * q, cx + r * q, cy + r * q), outline=dim + (255,), width=5)
    d.line((cx - r, cy, cx + r, cy), fill=dim + (255,), width=4)
    d.line((cx, cy - r, cx, cy + r), fill=dim + (255,), width=4)
    d.line((cx, cy, cx + r * math.cos(math.radians(ang)), cy + r * math.sin(math.radians(ang))), fill=grn + (255,), width=8)
    lost = str(g.get("sub") or "").lower()[:4] in ("lost", "verl", "weg", "gone")
    gone = max(1.3, min(dur * 0.5, 2.4))                                       # Zeitpunkt, zu dem der Punkt erlischt
    bx, by = cx + r * 0.42 + min(t, gone) * 14, cy - r * 0.36 - min(t, gone) * 10    # der Punkt wandert langsam über den Schirm
    if not lost or t < gone:
        blink = 1.0 if not lost or t < gone - 0.8 else (1.0 if int(t * 10) % 2 else 0.25)
        pr = 20 + 4 * math.sin(t * 6)
        d.ellipse((bx - pr * 2.2, by - pr * 2.2, bx + pr * 2.2, by + pr * 2.2), fill=grn + (int(70 * blink),))
        d.ellipse((bx - pr, by - pr, bx + pr, by + pr), fill=(220, 255, 230, int(255 * blink)))
    else:                                                                      # Signal weg: rotes Kreuz an der letzten Position
        e = _pop(t, gone, 0.3)
        s2 = 44 * min(1.1, e)
        for sgn in (1, -1):
            d.line((bx - s2, by - s2 * sgn, bx + s2, by + s2 * sgn), fill=(255, 80, 90, 255), width=16)
        d.ellipse((bx - 90, by - 90, bx + 90, by + 90), outline=(255, 80, 90, int(200 * (0.5 + 0.5 * math.sin(t * 8)))), width=6)
    disc = Image.new("L", (W, H), 0)                                           # der Schirm bleibt deckend – der Hintergrund scheint nicht durch den Suchstrahl
    ImageDraw.Draw(disc).ellipse((cx - r - 26, cy - r - 26, cx + r + 26, cy + r + 26), fill=255)
    frame.paste(lay, (0, 0), disc)
    d = ImageDraw.Draw(frame, "RGBA")
    _kicker(d, 300, g.get("kicker"), t, 0.0)
    lab = str(g.get("text") or "").upper()[:26]
    if lab and (t > gone if lost else t > 0.5):
        _pill(d, W / 2, 1196, lab, _fit(d, lab, 64, 860, "Bold"), ((230, 50, 70, 255) if lost else (30, 150, 100, 255)), WHITE)


def _g_primes(frame, g, t, dur):
    """Zahlenfeld: 1 bis 30 (mit sub="100" bis 100), die Primzahlen leuchten nacheinander auf – man sieht, dass sie ohne Muster verteilt sind.
    Für Mathe-Themen (Prüfung 24.11.2026, Video 197: zu „Geheimnis der Primzahlen“ stand eine Figur vor einer leeren Tafel)."""
    d = ImageDraw.Draw(frame, "RGBA")
    big = str(g.get("sub") or "").strip() == "100"
    n, cols = (100, 10) if big else (30, 6)
    cell, gap = (80, 7) if big else (140, 16)
    rows = n // cols
    x0 = (W - cols * cell - (cols - 1) * gap) / 2
    y0 = 400 if not big else 404                              # großes Feld: endet bei 1267, das Schild steht darüber – unter dem Feld läge es auf den Untertiteln (Video 198)
    _kicker(d, 300 if not big else 250, g.get("kicker") or "Primzahlen", t, 0.0)
    primes = [q for q in range(2, n + 1) if all(q % r for r in range(2, int(q ** 0.5) + 1))]
    span = min(2.8, max(1.2, dur * 0.55))                      # so lange dauert es, bis alle Primzahlen leuchten
    fn = _font(40 if big else 70)
    for q in range(1, n + 1):
        r_, c_ = divmod(q - 1, cols)
        k = _pop(t, 0.02 * (r_ + c_), 0.3)
        if k <= 0:
            continue
        cx, cy = x0 + c_ * (cell + gap) + cell / 2, y0 + r_ * (cell + gap) + cell / 2
        lit = q in primes and t >= 0.5 + span * primes.index(q) / len(primes)
        kk = _pop(t, 0.5 + span * primes.index(q) / len(primes), 0.35) if lit else 1.0
        h_ = cell / 2 * min(1.0, k) * (max(0.86, min(1.12, kk)) if lit else 1.0)
        rad = 12 if big else 22
        if lit:
            d.rounded_rectangle((cx - h_ + 4, cy - h_ + 6, cx + h_ + 4, cy + h_ + 6), rad, fill=(0, 0, 0, 90))
            d.rounded_rectangle((cx - h_, cy - h_, cx + h_, cy + h_), rad, fill=GOLD + (255,), outline=INK + (255,), width=4 if big else 6)
        else:
            d.rounded_rectangle((cx - h_, cy - h_, cx + h_, cy + h_), rad, fill=(24, 18, 70, 190), outline=(255, 255, 255, 40), width=3)
        txt = str(q)
        bb = d.textbbox((0, 0), txt, font=fn)
        d.text((cx - (bb[0] + bb[2]) / 2, cy - (bb[1] + bb[3]) / 2), txt, font=fn, fill=INK + (255,) if lit else (200, 196, 240, 120))
    lab = str(g.get("label") or g.get("text") or "").upper()[:30]
    if lab and t > 0.5 + span * 0.6:
        _pill(d, W / 2, 304 if big else y0 + rows * (cell + gap) + 30, lab, _fit(d, lab, 52 if big else 58, 860, "Bold"), GOLD + (255,), INK)


_ZEROS = (14.13, 21.02, 25.01, 30.42, 32.94, 37.59, 40.92, 43.33, 48.01, 49.77)   # Höhen der ersten zehn Nullstellen (echte Werte, gerundet)


def _g_zeros(frame, g, t, dur):
    """Nullstellen auf einer Linie: Zahlenebene mit einer senkrechten leuchtenden Linie, die Punkte erscheinen nacheinander und sitzen alle genau darauf.
    sub="doubt": weit oben blinkt daneben ein Fragezeichen – irgendwo könnte eine Ausnahme liegen. Abstände wie bei den ersten zehn echten Nullstellen."""
    d = ImageDraw.Draw(frame, "RGBA")
    doubt = str(g.get("sub") or "").lower()[:5] in ("doubt", "zweif", "ausna")
    _kicker(d, 300, g.get("kicker") or "Nullstellen", t, 0.0)
    x0, x1, y0, y1 = 110, 970, 390, 1150
    d.rounded_rectangle((x0 - 30, y0 - 30, x1 + 30, y1 + 30), 34, fill=(10, 8, 34, 160), outline=(255, 255, 255, 46), width=4)
    for i in range(1, 8):                                       # Gitter der Zahlenebene
        y = y0 + (y1 - y0) * i / 8
        d.line((x0, y, x1, y), fill=(255, 255, 255, 20), width=3)
    for i in range(1, 6):
        x = x0 + (x1 - x0) * i / 6
        d.line((x, y0, x, y1), fill=(255, 255, 255, 20), width=3)
    ax = x0 + (x1 - x0) / 3                                     # Achsen: die Linie liegt rechts der senkrechten Achse
    d.line((x0, y1 - 60, x1, y1 - 60), fill=(255, 255, 255, 130), width=5)
    d.line((ax, y0, ax, y1), fill=(255, 255, 255, 130), width=5)
    lx = x0 + (x1 - x0) * 0.6
    grow = min(1.0, max(0.0, (t - 0.1) / 0.5))
    top = y1 - (y1 - y0) * grow
    glow = int(70 + 30 * math.sin(t * 4))
    d.line((lx, y1, lx, top), fill=GOLD + (glow,), width=26)
    for yy in range(int(y1), int(top), -34):                    # gestrichelte Linie
        d.line((lx, yy, lx, max(top, yy - 20)), fill=GOLD + (255,), width=8)
    span = min(2.6, max(1.2, dur * 0.5))
    for j, z in enumerate(_ZEROS):
        st = 0.55 + span * j / len(_ZEROS)
        k = _pop(t, st, 0.3)
        if k <= 0:
            continue
        cy = y1 - 60 - (y1 - 60 - y0 - 40) * (z - 8) / 44
        r = 19 * min(1.15, k)
        ph = min(1.0, (t - st) / 0.6)
        if ph < 1:
            d.ellipse((lx - r - 40 * ph, cy - r - 40 * ph, lx + r + 40 * ph, cy + r + 40 * ph), outline=GREEN + (int(200 * (1 - ph)),), width=5)
        d.ellipse((lx - r, cy - r, lx + r, cy + r), fill=GREEN + (255,), outline=INK + (255,), width=6)
    end = 0.55 + span
    if doubt and t > end:
        k = _pop(t, end, 0.35)
        qx, qy = lx + 190, y0 + 74
        blink = 0.55 + 0.45 * math.sin(t * 7)
        r = 46 * min(1.1, k)
        d.ellipse((qx - r - 14, qy - r - 14, qx + r + 14, qy + r + 14), outline=(255, 96, 86, int(200 * blink)), width=6)
        d.ellipse((qx - r, qy - r, qx + r, qy + r), fill=(255, 96, 86, 255), outline=INK + (255,), width=6)
        fq = _font(int(64 * min(1.1, k)))
        bb = d.textbbox((0, 0), "?", font=fq)
        d.text((qx - (bb[0] + bb[2]) / 2, qy - (bb[1] + bb[3]) / 2), "?", font=fq, fill=WHITE + (255,))
    lab = str(g.get("text") or g.get("label") or "").upper()[:30]
    if lab and t > (end if doubt else 0.55 + span * 0.5):
        _pill(d, W / 2, 1196, lab, _fit(d, lab, 58, 860, "Bold"), ((255, 96, 86, 255) if doubt else GOLD + (255,)), WHITE if doubt else INK)


def _lines(d, text, f, max_w):
    out, cur = [], ""
    for w in str(text).split():
        if cur and d.textlength(cur + " " + w, font=f) > max_w:
            out.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    return out + ([cur] if cur else [])


# ------------------------------------------------------------------ Größe veranschaulichen (winzige Tiere: Bärtierchen, Milbe, Floh …)

_NUMW = {"ein": 1, "eins": 1, "einen": 1, "eine": 1, "zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "sechs": 6, "sieben": 7, "acht": 8,
         "neun": 9, "zehn": 10, "fünfzehn": 15, "zwanzig": 20, "dreißig": 30, "fünfzig": 50, "hundert": 100, "zweihundert": 200,
         "dreihundert": 300, "fünfhundert": 500}
_FRAC = {"halben": 0.5, "halbe": 0.5, "halber": 0.5, "viertel": 0.25, "zehntel": 0.1, "hundertstel": 0.01, "drittel": 1 / 3}
_UNIT = {"mm": 1.0, "millimeter": 1.0, "mikrometer": 0.001, "µm": 0.001, "tausendstel millimeter": 0.001, "cm": 10.0, "zentimeter": 10.0}
SIZE_RE = (r"(?:(\d+(?:[.,]\d+)?)|(anderthalb|eineinhalb)|(?:(?:nur |etwa |rund |gerade mal |knapp |ungefähr |circa |ca\. )*"
           r"(?:(ein|eins|einen|eine|zwei|drei|vier|fünf|sechs|sieben|acht|neun|zehn|fünfzehn|zwanzig|dreißig|fünfzig|hundert|zweihundert|dreihundert|fünfhundert)\s+)?"
           r"(halben|halbe|halber|viertel|zehntel|hundertstel|drittel)?))\s*(tausendstel millimeter|millimeter|mikrometer|zentimeter|µm|mm|cm)\b")


def size_mm(text):
    """Größenangabe aus einem Satz in Millimetern („einen halben Millimeter“ → 0.5, „0,1 mm“ → 0.1, „50 Mikrometer“ → 0.05).
    Nur kleine Dinge (bis 2 cm) – für alles Größere braucht es kein Lineal."""
    for m in re.finditer(SIZE_RE, str(text or "").lower()):
        num, onehalf, word, frac, unit = m.groups()
        if num:
            v = float(num.replace(",", "."))
        elif onehalf:
            v = 1.5
        elif frac:
            v = (_NUMW.get(word, 1) if word else 1) * _FRAC[frac]
        elif word:
            v = _NUMW[word]
        else:
            continue
        mm = v * _UNIT[unit]
        if 0.001 <= mm <= 20:
            return mm
    return None


def fmt_size(mm):
    if mm < 0.1:
        return f"{mm * 1000:.0f} µm"
    txt = f"{mm:.2f}".rstrip("0").rstrip(".").replace(".", ",")
    return f"{txt} mm"


def _size_val(v):
    m = re.match(r"\s*(\d+(?:[.,]\d+)?)\s*(µm|mm)", str(v or ""))
    if not m:
        return None
    x = float(m.group(1).replace(",", "."))
    return x / 1000 if m.group(2) == "µm" else x


def _macro_backdrop():
    """Hintergrund der Größen-Szene: warmes Licht von oben, weit entfernte unscharfe Halme und weiche Lichtkreise (wie Makro-Fotos)."""
    if "macro" in _bg:
        return _bg["macro"]
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    for i in range(0, H, 6):
        k = i / H
        d.rectangle((0, i, W, i + 6), fill=(int(236 - 70 * k), int(238 - 40 * k), int(200 - 90 * k)))
    lay = Image.new("RGBA", (W, H), (110, 180, 90, 0))                 # Grundfarbe auch im Durchsichtigen: sonst dunkle Ränder beim Weichzeichnen
    ld = ImageDraw.Draw(lay)
    r = random.Random(5)
    for _ in range(46):                                                 # ferne Halme: helles, verschwommenes Grün
        x, h = r.uniform(-60, W + 60), r.uniform(700, 1500)
        w_, lean = r.uniform(26, 60), r.uniform(-140, 140)
        g_ = r.randint(150, 200)
        ld.polygon([(x - w_ / 2, H), (x + lean * 0.6, H - h * 0.6), (x + lean, H - h), (x + lean * 0.6 + w_ * 0.2, H - h * 0.6), (x + w_ / 2, H)],
                   fill=(int(g_ * 0.55), g_, int(g_ * 0.45), 150))
    bl = lay.filter(ImageFilter.GaussianBlur(22))
    im.paste(bl.convert("RGB"), (0, 0), bl.getchannel("A"))
    lay = Image.new("RGBA", (W, H), (255, 250, 215, 0))
    ld = ImageDraw.Draw(lay)
    for _ in range(22):                                                 # Lichtkreise (Sonne durch Blätter)
        x, y, rr = r.uniform(0, W), r.uniform(0, H * 0.6), r.uniform(30, 110)
        ld.ellipse((x - rr, y - rr, x + rr, y + rr), fill=(255, 250, 215, r.randint(40, 90)))
    bl = lay.filter(ImageFilter.GaussianBlur(14))
    im.paste(bl.convert("RGB"), (0, 0), bl.getchannel("A"))
    _bg["macro"] = im
    return im


def _blade(d, P, x, hgt, wid, lean, col, ow, dew, sc_px, L):
    """Grashalm: gebogen, spitz zulaufend, Licht- und Schattenseite, helle Mittelrippe, gelegentlich ein Tautropfen."""
    n = 12
    left, right, mid = [], [], []
    for i in range(n + 1):
        s_ = i / n
        cx_, cy_ = x + lean * s_ * s_, -hgt * s_
        ww = wid * (1 - s_) ** 0.85 / 2
        left.append(P(cx_ - ww, cy_))
        right.append(P(cx_ + ww, cy_))
        mid.append(P(cx_, cy_))
    d.polygon(left + right[::-1], fill=col + (255,), outline=INK, width=ow)
    dark = tuple(max(0, int(c * 0.72)) for c in col)
    d.polygon(mid + right[::-1], fill=dark + (255,))                    # Schattenseite
    d.line(left + right[::-1] + [left[0]], fill=INK, width=ow)
    light = tuple(min(255, int(c * 1.25)) for c in col)
    d.line(mid[:-2], fill=light + (200,), width=max(1, int(0.03 * L / 10 * sc_px)))
    if dew:                                                             # Tautropfen auf dem Halm
        s_ = 0.42
        cx_, cy_ = x + lean * s_ * s_ + wid * 0.12, -hgt * s_
        rr = 0.16 * L / 10 * sc_px
        c = P(cx_, cy_)
        if rr >= 3:
            d.ellipse((c[0] - rr, c[1] - rr, c[0] + rr, c[1] + rr), fill=(200, 235, 255, 150), outline=(40, 70, 90, 200), width=max(1, ow - 3))
            d.ellipse((c[0] - rr * 0.55, c[1] - rr * 0.6, c[0] - rr * 0.1, c[1] - rr * 0.15), fill=(255, 255, 255, 230))


def _moss(d, P, mx, mr, sc_px, ow, r):
    """Moospolster: dunkles Kissen mit vielen kleinen hellen Blättchen obendrauf."""
    a_, b_ = P(mx - mr, -mr * 1.3), P(mx + mr, 0)
    d.ellipse((a_[0], a_[1], b_[0], b_[1] + mr * sc_px * 0.25), fill=(48, 104, 52, 255), outline=INK, width=max(1, ow - 2))
    for _ in range(26):
        ang, rad_ = r.uniform(math.pi, 2 * math.pi), r.uniform(0.2, 0.95)
        lx, ly = mx + math.cos(ang) * mr * rad_, -mr * 0.65 + math.sin(ang) * mr * 0.65 * rad_
        c = P(lx, ly)
        ll = max(1.5, mr * 0.22 * sc_px)
        rot = r.uniform(0, math.pi)
        d.polygon([(c[0] + math.cos(rot) * ll, c[1] + math.sin(rot) * ll * 0.5), (c[0] - math.sin(rot) * ll * 0.3, c[1] - ll * 0.6),
                   (c[0] - math.cos(rot) * ll, c[1] - math.sin(rot) * ll * 0.5)], fill=(r.randint(90, 130), r.randint(170, 205), r.randint(70, 100), 255))


def _g_size(frame, g, t, dur):
    """Wie klein ist das wirklich? Erst ganz nah: das Tier zwischen riesigen Grashalmen, Moos und einem Sandkorn – dann zoomt die
    Kamera heraus, bis es als Pünktchen neben einem Lineal liegt; eine Klammer zeigt die echte Größe."""
    from . import extras
    mm = _size_val(g.get("value")) or 0.5
    L = 1.0 if mm < 0.1 else 10.0 if mm <= 5 else 50.0                # Lineal: 1 mm, 1 cm oder 5 cm
    ppm = 860 / L                                                       # Bildpunkte je Millimeter bei voller Ansicht
    x_c = L * 0.3                                                       # hier steht das Tier auf dem Lineal
    z0 = max(1.0, 430 / (mm * ppm))                                     # Anfang: das Tier etwa 430 Bildpunkte groß, die Halme daneben im Bild
    z_a, z_b = 0.55, max(1.3, min(dur * 0.62, 2.5))
    u = min(1.0, max(0.0, (t - z_a) / (z_b - z_a)))
    e = u * u * (3 - 2 * u)
    Z = z0 ** (1 - e)                                                   # gleichmäßig wirkender Zoom (geometrisch)
    fx, fy = x_c + (L / 2 - x_c) * e, -(mm / 2) * (1 - e)               # Blickpunkt in Millimetern (y nach unten, Boden = 0)
    ax, ay = W / 2, 960 * (1 - e) + 1130 * e                            # dort liegt der Blickpunkt im Bild

    def P(x, y):
        return (ax + (x - fx) * ppm * Z, ay + (y - fy) * ppm * Z)
    sc_px = ppm * Z
    d = ImageDraw.Draw(frame, "RGBA")
    frame.paste(_macro_backdrop(), (0, 0))                              # unscharfer Hintergrund wie bei einer Makro-Aufnahme
    gy = P(0, 0)[1]
    for i in range(int(max(0, gy)), H, 6):                              # Erdboden: nach unten dunkler
        k_ = (i - gy) / max(1, H - gy)
        d.rectangle((0, i, W, i + 6), fill=(int(128 - 34 * k_), int(98 - 28 * k_), int(68 - 20 * k_)))
    rg = random.Random(11)                                              # Körnchen und Steinchen in echter Größe: von nah wie Kiesel
    x_lo, x_hi = fx - (W / 2) / (ppm * Z), fx + (W / 2) / (ppm * Z)
    for _ in range(900):
        gx_, gy_ = rg.uniform(-0.3 * L, 2.0 * L), rg.uniform(0.0, 1.6 * L)
        r_ = rg.uniform(0.004, 0.02) * L
        if not (x_lo - r_ <= gx_ <= x_hi + r_):
            continue
        c_ = P(gx_, gy_)
        rp = r_ * ppm * Z
        if rp < 1.2 or c_[1] - rp > H or c_[1] + rp < gy:
            continue
        sh = rg.randint(-22, 22)
        d.ellipse((c_[0] - rp, c_[1] - rp * 0.7, c_[0] + rp, c_[1] + rp * 0.7), fill=(150 + sh, 118 + sh, 84 + sh // 2, 255))
    rnd = random.Random(7)
    ow = max(2, min(7, int(0.04 * sc_px)))
    macro = L >= 10                                                     # Gras, Moos, Sandkorn nur bei Millimetern (unter 0,1 mm wären sie falsch groß)
    blades = []                                                         # (x, Höhe, Breite, Neigung, Farbe, Tau) in Millimetern
    for jb in range(26 if macro else 0):
        x = -3 * L / 10 + jb * (L * 1.6 / 26) + rnd.uniform(-0.2, 0.2) * L / 10
        if abs(x - x_c) < max(0.9, mm * 2.2) * L / 10:
            continue
        blades.append((x, rnd.uniform(6, 16) * L / 10, rnd.uniform(0.45, 0.9) * L / 10, rnd.uniform(-2.2, 2.2) * L / 10,
                       (int(70 + rnd.uniform(0, 40)), int(150 + rnd.uniform(0, 50)), int(55 + rnd.uniform(0, 30))), rnd.random() < 0.3))
    w1, w2 = 0.9 * L / 10, 1.0 * L / 10
    if macro:                                                           # zwei Halme direkt neben dem Tier: von nah wie riesige Wände
        blades += [(x_c - mm * 0.95 - w1 / 2, 9 * L / 10, w1, -1.4 * L / 10, (62, 150, 66), True),
                   (x_c + mm * 1.05 + w2 / 2, 12 * L / 10, w2, 1.8 * L / 10, (84, 172, 76), False)]
    for x, hgt, wid, lean, col, dew in blades:
        _blade(d, P, x, hgt, wid, lean, col, ow, dew, sc_px, L)
    for jm in range(9 if macro else 0):                                 # Moospolster aus vielen kleinen Blättchen
        mx, mr = x_c + rnd.uniform(-2.2, 2.6) * L / 10, rnd.uniform(0.18, 0.4) * L / 10
        _moss(d, P, mx, mr, sc_px, ow, random.Random(100 + jm))
    if macro:                                                           # Sandkorn mit Facetten und Glanz
        sx0, sr = x_c + max(1.2, mm * 3) * L / 10 * (1 if mm < 3 else 0.6), 0.6 * (L / 10)
        sg = [(0, 0), (0.12, -0.42), (0.42, -0.66), (0.74, -0.52), (0.9, -0.18), (0.86, 0)]
        d.polygon([P(sx0 + px_ * sr, py_ * sr) for px_, py_ in sg], fill=(226, 196, 138, 255), outline=INK, width=ow)
        d.polygon([P(sx0 + px_ * sr, py_ * sr) for px_, py_ in ((0.42, -0.66), (0.74, -0.52), (0.9, -0.18), (0.5, -0.3))], fill=(196, 160, 104, 255))
        d.polygon([P(sx0 + px_ * sr, py_ * sr) for px_, py_ in ((0.16, -0.38), (0.36, -0.56), (0.3, -0.36))], fill=(255, 244, 214, 220))
    img, fx_, fy_, _fly = extras.creature(str(g.get("kind") or "tardigrade"), t)   # das Tier selbst, in echter Größe
    box = img.getbbox()
    if box:
        img = img.crop(box)
        h_px = mm * sc_px
        if h_px >= 3:
            f = h_px / img.height
            im2 = img.resize((max(1, int(img.width * f)), max(1, int(h_px))), Image.LANCZOS)
            px_, py_ = P(x_c, 0)
            frame.paste(im2, (int(px_ - im2.width / 2), int(py_ - im2.height)), im2)
        else:
            px_, py_ = P(x_c, 0)
            d.ellipse((px_ - 2, py_ - 4, px_ + 2, py_), fill=INK)
    # Lineal: Holz mit Kante, Schatten, Maserung und Glanz; Skala mm / 5 mm / cm; läuft wie ein echtes über den Bildrand hinaus
    D, y0 = 0.30 * L, 0.05 * L                                          # Tiefe der Oberseite, Abstand zum Tier
    x0, x1 = -0.10 * L, 3.2 * L
    edge = 0.055 * L                                                    # sichtbare Vorderkante (Dicke)
    lay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    s0, s1 = P(x0 + 0.03 * L, y0 + 0.06 * L), P(x1, y0 + D + edge + 0.07 * L)
    ld.rounded_rectangle((s0[0], s0[1], s1[0], s1[1]), int(max(4, 0.03 * L * sc_px)), fill=(40, 26, 10, 120))
    frame.paste(Image.new("RGB", frame.size, (40, 26, 10)), (0, 0), lay.filter(ImageFilter.GaussianBlur(max(3, 0.02 * L * sc_px))).getchannel("A"))
    d = ImageDraw.Draw(frame, "RGBA")
    rad = int(min(40, max(3, 0.025 * L * sc_px)))
    a_, b_ = P(x0, y0 + D - 0.02 * L), P(x1, y0 + D + edge)             # Vorderkante (dunkleres Holz)
    d.rounded_rectangle((a_[0], a_[1], b_[0], b_[1]), rad, fill=(184, 128, 62, 255), outline=INK, width=max(2, ow - 2))
    a_, b_ = P(x0, y0), P(x1, y0 + D)                                   # Oberseite
    d.rounded_rectangle((a_[0], a_[1], b_[0], b_[1]), rad, fill=(236, 194, 120, 255), outline=INK, width=max(2, ow - 2))
    rw = random.Random(3)
    for k_ in range(9):                                                 # Holzmaserung (feine, leicht wellige Linien)
        yy = y0 + D * (0.18 + 0.08 * k_) + rw.uniform(-0.01, 0.01) * L
        pts = [P(x, yy + 0.008 * L * math.sin(x / L * 9 + k_)) for x in [x0 + 0.04 * L + q * 0.05 * L for q in range(int((x1 - x0) / (0.05 * L)))]]
        pts = [q for q in pts if -50 < q[0] < W + 50]
        if len(pts) > 1:
            d.line(pts, fill=(214, 168, 96, 150), width=max(1, int(0.004 * L * sc_px)))
    a_, b_ = P(x0 + 0.02 * L, y0 + 0.012 * L), P(x1, y0 + 0.05 * L)      # Glanz an der Oberkante
    d.rounded_rectangle((a_[0], a_[1], b_[0], b_[1]), max(2, rad // 2), fill=(255, 245, 220, 110))
    minor = L / 10 if L <= 10 else 1.0                                  # kleinster Strich: 1 mm (bei Mikrometern 0,1 mm)
    if minor * sc_px >= 5:
        n0, n1 = int(math.floor((fx - (W / 2) / sc_px) / minor)) - 1, int(math.ceil((fx + (W / 2) / sc_px) / minor)) + 1
        for i_ in range(max(0, n0), min(int(x1 / minor), n1)):
            x = i_ * minor
            major, mid = i_ % 10 == 0, i_ % 5 == 0
            ln = D * (0.50 if major else 0.34 if mid else 0.20)
            p0, p1 = P(x, y0 + 0.004 * L), P(x, y0 + ln)
            d.line((p0[0], p0[1], p1[0], p1[1]), fill=(52, 34, 18, 255), width=max(2, int((0.010 if major else 0.007) * L * sc_px)))
            if major and e > 0.85:                                      # Zahlen unter den langen Strichen (0, 1, 2 … in cm bzw. mm)
                num = str(i_ // 10) + ((" mm" if L <= 1 else " cm") if i_ // 10 == max(1, round(L / 10)) else "")   # Einheit an der letzten Zahl im Bild
                f_r = _font(int(max(30, min(64, 0.1 * L * sc_px))), "Bold")
                q = P(x, y0 + ln + 0.02 * L)
                d.text((q[0] - d.textlength(num, font=f_r) / 2, q[1]), num, font=f_r, fill=(52, 34, 18))
    k = _pop(t, z_b, 0.4)                                                # Klammer und Etikett mit der echten Größe
    if k > 0:
        top, bot = P(x_c, -mm), P(x_c, 0)
        bx = bot[0] + max(22, mm * sc_px * 0.75)
        red = (226, 58, 48)
        d.line((bx, top[1], bx, bot[1]), fill=red, width=5)
        for yy in (top[1], bot[1]):
            d.line((bx - 12, yy, bx + 12, yy), fill=red, width=5)
        lab_ = str(g.get("value"))
        f_v = _font(int(84 * min(1.0, 0.6 + 0.4 * k)), "anton")
        tw = d.textlength(lab_, font=f_v)
        cx_ = min(W - 60 - tw / 2, max(60 + tw / 2, bx + 150))
        cy_ = top[1] - 230
        d.line((bx, (top[1] + bot[1]) / 2, cx_ - tw / 2 + 20, cy_ + 60), fill=red, width=4)
        d.rounded_rectangle((cx_ - tw / 2 - 34, cy_ - 16, cx_ + tw / 2 + 34, cy_ + f_v.size + 28), 26, fill=(255, 255, 255, 240), outline=red, width=5)
        d.text((cx_ - tw / 2, cy_), lab_, font=f_v, fill=red)
    kt = str(g.get("kicker") or "ECHTE GRÖSSE").upper()[:40]            # dunkle Schrift: der Hintergrund ist hier hell
    f_k = _fit(d, kt, 70, 940, "Bold")
    d.rounded_rectangle((W / 2 - d.textlength(kt, font=f_k) / 2 - 34, 268, W / 2 + d.textlength(kt, font=f_k) / 2 + 34, 268 + f_k.size + 44), 30,
                        fill=(255, 255, 255, 215))
    _center(d, 288, kt, f_k, fill=INK, shadow=False)


# ------------------------------------------------------------------ Spielwelt (Videospiel-Themen): eigenes Pixel-Bild, keine Figur und keine Welt aus einem echten Spiel
GAME_P = 40                                                    # Kantenlänge eines Bildpunkts der Spielwelt
GAME_SUBS = ("world", "room", "minus", "far")
_GAME_HERO = ("..yyy..", ".yyyyy.", ".yeyey.", ".yyyyy.", "ggggggg", "ggggggg", ".ggggg.", ".d...d.", ".d...d.")
_GAME_COL = {"y": (255, 214, 80), "e": (24, 24, 36), "g": (70, 190, 110), "d": (40, 44, 70)}


def _game_hero(d, x, by, t, px=14, walk=True):
    """Kleine Spielfigur in den Farben der Kanal-Figur (gelber Kopf, grüner Körper) – eigene Zeichnung."""
    step = int(t * 6) % 2 if walk else 0
    for r, row in enumerate(_GAME_HERO):
        for c, ch in enumerate(row):
            if ch == ".":
                continue
            if r >= 7 and walk and ((c < 3) == bool(step)) and r == 8:
                continue                                       # ein Bein hebt sich im Wechsel
            x0, y0 = x + (c - 3.5) * px, by - (len(_GAME_HERO) - r) * px
            d.rectangle((x0, y0, x0 + px - 1, y0 + px - 1), fill=_GAME_COL[ch])


def _game_cells(d, cells, col, P=GAME_P):
    for cx, cy in cells:
        d.rectangle((cx * P, cy * P, cx * P + P - 1, cy * P + P - 1), fill=col)


def _game_banner(d, text, y, t, col=WHITE):
    text = str(text or "").upper().strip()[:26]
    if not text or _pop(t, 0.15, 0.3) <= 0:
        return
    f = _fit(d, text, 84, 860)
    w = d.textlength(text, font=f)
    d.rectangle((W / 2 - w / 2 - 44, y - 18, W / 2 + w / 2 + 44, y + f.size + 34), fill=(12, 12, 20), outline=WHITE, width=8)
    d.text((W / 2 - w / 2, y), text, font=f, fill=col)


def _g_game(frame, g, t, dur):
    """Blick in eine Spielwelt. sub: "world" (Landschaft mit verborgener Tür), "room" (dunkles Labyrinth, hinter der Wand ein geheimer Raum mit
    blinkender Schrift), "minus" (endloses Unterwasser-Level, das sich wiederholt), "far" (Blocklandschaft, die am Rand der Welt zu einer
    löchrigen Riesenwand zerbricht). kicker = Schild oben, text = Schrift im Bild."""
    P = GAME_P
    sub = str(g.get("sub") or "").lower()
    sub = sub if sub in GAME_SUBS else "world"
    d = ImageDraw.Draw(frame, "RGBA")
    cols, rows = W // P, H // P
    k = max(0.0, min(1.0, t / max(dur, 1.0)))
    step = int(str(g.get("label") or "1")) if str(g.get("label") or "1").isdigit() else 1          # wievieltes Bild dieser Welt: 0 = davor, 1 = der Moment, 2 = danach
    if sub == "room" and step >= 2:                                                                  # im geheimen Raum: die Schrift groß in wechselnden Farben
        d.rectangle((0, 0, W, H), fill=(10, 10, 16))
        wall = (150, 90, 220)
        _game_cells(d, [(c, r) for c in range(cols) for r in (7, 8, 31, 32)] + [(c, r) for c in (0, 1, cols - 2, cols - 1) for r in range(7, 33)], wall)
        rb = [(255, 90, 90), (255, 170, 60), (255, 230, 90), (110, 230, 120), (90, 190, 255), (190, 130, 255)]
        txt = str(g.get("text") or "ERSCHAFFEN VON").upper()[:18]
        f = _fit(d, txt, 150, 820)
        d.text((W / 2 - d.textlength(txt, font=f) / 2, 560), txt, font=f, fill=rb[int(t * 8) % len(rb)])
        for i in range(6):
            d.rectangle((174 + i * 126, 800, 174 + i * 126 + 100, 900), fill=rb[(int(t * 8) + i) % len(rb)])
        hx = 300 + math.sin(t * 1.4) * 120
        d.rectangle((hx - 50, 1080, hx + 50, 1180), fill=(255, 214, 80))
    elif sub == "room":
        d.rectangle((0, 0, W, H), fill=(10, 10, 16))
        wall = (150, 90, 220)
        _game_cells(d, [(c, r) for c in range(cols) for r in (9, 10, 30, 31)], wall)                 # Gang oben/unten
        _game_cells(d, [(c, r) for c in (0, cols - 1) for r in range(9, 32)], wall)
        _game_cells(d, [(13, r) for r in range(11, 30) if r not in (19, 20, 21)], wall)              # Trennwand – in der Mitte nur eine hauchdünne Linie
        d.rectangle((13 * P + 16, 19 * P, 13 * P + 23, 22 * P), fill=(90, 90, 100))
        hx = 150 + min(1.0, k / 0.45) * 620 if step else 260 + math.sin(t * 1.6) * 130              # die Figur trägt den grauen Punkt durch die Wand (step 0: sie sucht noch)
        hy = 21 * P + 34
        d.rectangle((hx - 44, hy - 88, hx + 44, hy), fill=(255, 214, 80))
        d.rectangle((hx + 56, hy - 54, hx + 76, hy - 34), fill=(170, 170, 180))
        if k > 0.45 and step:                                                                        # im Raum: Schrift in wechselnden Farben
            rb = [(255, 90, 90), (255, 170, 60), (255, 230, 90), (110, 230, 120), (90, 190, 255), (190, 130, 255)]
            txt = str(g.get("text") or "ERSCHAFFEN VON").upper()[:18]
            f = _fit(d, txt, 78, 400)
            col = rb[int(t * 8) % len(rb)]
            d.text((790 - d.textlength(txt, font=f) / 2, 13 * P), txt, font=f, fill=col)
            for i in range(6):                                                                       # der Name selbst bleibt ein blinkender Balken (keine echte Person im Bild)
                d.rectangle((592 + i * 68, 16 * P - 10, 592 + i * 68 + 52, 16 * P + 44), fill=rb[(int(t * 8) + i) % len(rb)])
    elif sub == "minus" and step in (0, 3):                                                          # 3 = Vorstellung des Spiels: die Figur läuft im Level hin und her                                                               # davor: unterirdisches Level, die Figur rutscht in die Mauer
        d.rectangle((0, 0, W, H), fill=(16, 18, 40))
        brick, brick2 = (190, 110, 60), (160, 86, 46)
        hx = 330 + math.sin(t * 1.5) * 190 if step == 3 else 140 + min(1.0, k / 0.7) * 630                                                          # … und verschwindet darin
        if hx > 16 * P:
            _game_hero(d, hx, 31 * P, t, 24)
        for c in range(cols + 1):
            for r in list(range(6, 10)) + list(range(31, rows)):
                _game_cells(d, [(c, r)], brick if (c + r) % 2 else brick2)
        for c in range(17, 22):
            for r in range(10, 31):
                _game_cells(d, [(c, r)], brick if (c + r) % 2 else brick2)
        if hx <= 16 * P:
            _game_hero(d, hx, 31 * P, t, 24)
    elif sub == "minus":
        d.rectangle((0, 0, W, H), fill=(26, 60, 170))
        d.rectangle((0, 0, W, 6 * P), fill=(60, 110, 220))
        off = int(t * 5)                                                                             # die Welt zieht vorbei – und wiederholt sich alle 9 Spalten
        for c in range(-1, cols + 2):
            wc = (c + off) % 9
            _game_cells(d, [(c, r) for r in range(31, rows)], (40, 70, 120) if (c + off) % 2 else (48, 82, 136))
            if wc == 2:
                _game_cells(d, [(c, r) for r in range(25, 31)], (70, 200, 120))                      # Seegras
            if wc == 6:
                _game_cells(d, [(c, r) for r in range(27, 31)], (240, 120, 160))                     # Koralle
                _game_cells(d, [(c + 1, 28), (c - 1, 29)], (240, 120, 160))
            if wc == 4:
                _game_cells(d, [(c, r) for r in range(6, 13)], (120, 130, 150))                      # Felsblock von oben
        for i in range(9):                                                                           # Luftblasen
            bx = (i * 137 + 60) % W
            by = H - ((t * (120 + i * 17) + i * 260) % (H - 240))
            d.rectangle((bx, by, bx + 16, by + 16), outline=(200, 230, 255), width=4)
        _game_hero(d, 470, 21 * P + math.sin(t * 3) * 30, t, 26)
        hud = str(g.get("text") or "WELT  -1").upper()[:14]
        f = _font(92)
        d.text((W / 2 - d.textlength(hud, font=f) / 2, 150), hud, font=f, fill=WHITE)
    else:
        d.rectangle((0, 0, W, H), fill=(120, 190, 255))
        d.rectangle((0, 0, W, 10 * P), fill=(96, 170, 250))
        for cx, cy in ((3, 8), (17, 12), (10, 5)):                                                   # Pixel-Wolken
            cx = (cx + int(t * 0.6)) % (cols + 6) - 3
            _game_cells(d, [(cx + i, cy) for i in range(5)] + [(cx + 1 + i, cy - 1) for i in range(3)], WHITE)
        grass, dirt, stone = (96, 200, 90), (150, 100, 60), (130, 132, 142)
        far = sub == "far"
        edge = (15, 15, 8, 0)[min(step, 3)] if far and step else cols + 1                            # 2 = dicht vor der Wand, 3 = nur noch Wand und Löcher
        for c in range(cols + 1):
            top = 31 - (1 if c % 7 in (3, 4) else 0) - (2 if not far and c in (9, 10, 11) else 0)
            if c >= edge:
                continue
            _game_cells(d, [(c, top)], grass)
            _game_cells(d, [(c, r) for r in range(top + 1, top + 4)], dirt)
            _game_cells(d, [(c, r) for r in range(top + 4, rows)], stone)
        if far and not step:                                                                         # davor: die Figur läuft und läuft durch die Blocklandschaft
            _game_hero(d, 200 + k * 620, 31 * P - (P if int((200 + k * 620) // P) % 7 in (3, 4) else 0), t, 24)
        elif far:                                                                                    # Rand der Welt: die Landschaft zerbricht zu einer löchrigen Riesenwand bis in den Himmel
            grow = min(1.0, k / 0.5) if step == 1 else 1.0
            for c in range(edge, cols + 1):
                for r in range(int(rows - (rows - 4) * grow), rows):
                    if r < 31 and math.sin(r * 0.9) + math.sin(c * 1.7 + r * 0.35) + 0.5 * math.sin(c * 0.6 - r * 1.3) < -0.55:
                        continue                                                                     # Loch: der Himmel scheint durch
                    col = (grass if r == 31 else dirt if r < 35 else stone) if r >= 31 else grass if r % 6 == 0 else dirt if r % 6 in (1, 2) else stone
                    _game_cells(d, [(c, r)], col)
            hx = 120 + min(1.0, k / 0.7) * 360 if step == 1 else 150
            if step < 3:
                _game_hero(d, hx, 31 * P, t, 24, walk=k < 0.7 and step == 1)
        else:
            door_c = 20                                                                              # Felswand rechts mit verborgener Tür, die aufleuchtet
            _game_cells(d, [(c, r) for c in range(18, cols + 1) for r in range(17, 31)], stone)
            glow = 0.5 + 0.5 * math.sin(t * 5)
            _game_cells(d, [(c, r) for c in (door_c, door_c + 1, door_c + 2) for r in range(23, 31)], (int(40 + 215 * glow), int(40 + 180 * glow), 60))
            f = _font(150)
            d.text((door_c * P + 22, 18 * P), "?", font=f, fill=(255, 230, 90, int(255 * glow)))
            hx = 140 + min(1.0, k / 0.8) * 470
            _game_hero(d, hx, 30 * P if 9 * P <= hx <= 12 * P else 31 * P - (P if int(hx // P) % 7 in (3, 4) else 0), t, 24, walk=k < 0.8)
        if g.get("value"):
            val = str(g["value"]).upper()[:22]
            f = _fit(d, val, 80, 900)
            tw = d.textlength(val, font=f)
            d.rectangle((W / 2 - tw / 2 - 36, 138, W / 2 + tw / 2 + 36, 150 + f.size + 30), fill=(12, 12, 20), outline=WHITE, width=8)   # eigenes Feld: die Riesenwand dahinter macht die Zahl sonst unlesbar
            d.text((W / 2 - tw / 2, 150), val, font=f, fill=WHITE)
    _game_banner(d, g.get("kicker"), 300, t, GOLD)
    for y in range(0, H, 8):                                                                         # Zeilen eines alten Bildschirms
        d.line((0, y, W, y), fill=(0, 0, 0, 26), width=2)



# ------------------------------------------------------------------ Nachricht vom Unbekannten, Kapitelkarte (Vorbild: Mystery-Storys mit Countdown)

_dark = {}


def _dark_bg():
    """Fast schwarzer, kühler Grund mit weichem Lichtfleck in der Mitte – wie ein Handy-Bildschirm im dunklen Zimmer."""
    if "msg" not in _dark:
        g = Image.new("L", (W // 8, H // 8), 0)
        ImageDraw.Draw(g).ellipse((-20, H // 8 * 0.18, W // 8 + 20, H // 8 * 0.86), fill=255)
        g = g.filter(ImageFilter.GaussianBlur(26)).resize((W, H), Image.BILINEAR)
        _dark["msg"] = Image.composite(Image.new("RGB", (W, H), (34, 44, 70)), Image.new("RGB", (W, H), (6, 8, 14)), g)
    return _dark["msg"].copy()


def msg_lines(g):
    """Zeilen der Nachricht: "lines" (Liste) oder "text" mit „/“ getrennt. Eine Zeile mit „!“ davor ist die rote Warnung."""
    raw = g.get("lines") if isinstance(g.get("lines"), list) else str(g.get("text") or "").split("/")
    out = []
    for x in raw:
        ln = " ".join(str(x).split())
        if not ln:
            continue
        warn = ln.startswith("!")
        words, cur = ln.lstrip("! ").split(), ""
        for w in words:                                   # lange Zeile („Besonders nicht mit dem Nachbarn.“) lief rechts aus dem Bild: umbrechen statt abschneiden (Video 192)
            if cur and len(cur) + 1 + len(w) > 21:
                out.append(("!" if warn else "") + cur)
                cur = w
            else:
                cur = (cur + " " + w).strip()
        if cur:
            out.append(("!" if warn else "") + cur[:30])
    return out[:7]


def _short_msg(text, limit):
    """Nachrichtentext für ein Handy: höchstens `limit` Zeichen, am Wortende gekürzt – nie mitten im Wort."""
    msg = " ".join(str(text or "").split())
    if len(msg) <= limit:
        return msg
    cut = msg[:limit + 1].rsplit(" ", 1)[0].rstrip(" ,;:–-")
    return cut + " …"


def _g_message(frame, g, t, dur):
    """Nachricht von unbekannter Nummer: dunkles Handy schräg im Hintergrund, die Zeilen erscheinen nacheinander (getippt),
    die Warnzeile („!…“) leuchtet rot. Für Mystery- und Countdown-Geschichten."""
    frame.paste(_dark_bg())
    d = ImageDraw.Draw(frame, "RGBA")
    ph = Image.new("RGBA", (560, 1080), (0, 0, 0, 0))                    # Handy, leicht gedreht, halb im Dunkeln
    pd = ImageDraw.Draw(ph)
    pd.rounded_rectangle((0, 0, 559, 1079), 70, fill=(22, 26, 38, 255), outline=(70, 80, 104, 255), width=6)
    pd.rounded_rectangle((180, 26, 380, 58), 16, fill=(8, 10, 16, 255))
    pd.ellipse((240, 110, 320, 190), fill=(64, 72, 96, 255))
    sender = str(g.get("kicker") or "UNBEKANNT").upper()[:18]
    fs = _font(34, "Bold")
    pd.text((280 - pd.textlength(sender, font=fs) / 2, 206), sender, font=fs, fill=(150, 160, 186, 255))
    for i in range(6):                                                     # angedeutete ältere Nachrichten
        pd.rounded_rectangle((40, 300 + i * 112, 40 + (380 if i % 2 else 470), 370 + i * 112), 30, fill=(40, 46, 64, 255))
    ph = ph.rotate(-7, expand=True, resample=Image.BICUBIC)
    shake = math.sin(t * 40) * 6 if t < 0.5 else 0                         # brummt kurz beim Eintreffen
    frame.paste(ph, (int(-170 + shake), 520), ph)
    lines = msg_lines(g)
    if not lines:
        return
    x0, max_w = 390, 540                                                    # Platz für Kamerafahrt und rote Umrandung
    size = 60                                                              # eine Schriftgröße für alle Zeilen (wie im Chat)
    while size > 42 and max(d.textlength(ln.lstrip("! "), font=_font(size, "Bold")) for ln in lines) > max_w:
        size -= 2
    f = _font(size, "Bold")
    t0, t1 = 0.35, max(0.9, dur * 0.82)
    step = (t1 - t0) / max(1, len(lines))
    row = int(size * 1.85)
    y = int(1000 - row * len(lines) / 2)
    for i, ln in enumerate(lines):
        ts = t0 + i * step
        if t < ts:
            break
        warn = ln.startswith("!")
        txt = ln.lstrip("! ").strip()
        n = len(txt) if warn else max(1, min(len(txt), int((t - ts) / max(0.25, step * 0.55) * len(txt)) + 1))   # tippt sich, Warnung steht sofort
        shown = txt[:n]
        fl = f
        tw = d.textlength(txt, font=fl)
        hgt = size * 1.3
        if warn:
            k = _pop(t, ts, 0.3)
            pad = 14 * min(1.0, k)
            d.rounded_rectangle((x0 - 22 - pad, y - 12 - pad / 2, x0 + tw + 22 + pad, y + hgt + 6 + pad / 2), 18, fill=(196, 34, 46, 235))
        else:
            d.rounded_rectangle((x0 - 22, y - 12, x0 + tw + 22, y + hgt + 6), 18, fill=(24, 30, 46, 210))
        d.text((x0, y), shown, font=fl, fill=WHITE)
        if not warn and n < len(txt) and (t * 3) % 1 < 0.6:                 # Schreibmarke
            cx = x0 + d.textlength(shown, font=fl) + 6
            d.rectangle((cx, y + 6, cx + 6, y + hgt - 4), fill=WHITE)
        y += row


def _g_chapter(frame, g, t, dur):
    """Kapitelkarte auf Schwarz: große Zahl, darunter die Zeile („NOCH 7 TAGE“, „TAG 3“) – kurzer Ruck, leichtes Flackern."""
    frame.paste((4, 4, 6), (0, 0, W, H))
    d = ImageDraw.Draw(frame, "RGBA")
    k = _pop(t, 0.05, 0.4)
    if k <= 0:
        return
    val = str(g.get("value") or "").strip()[:6]
    sub = str(g.get("text") or g.get("label") or "").upper().strip()[:28]
    head = str(g.get("kicker") or "").upper().strip()[:24]
    col = (250, 214, 160) if not (t > 0.4 and (t * 7) % 1 < 0.06) else (180, 150, 112)      # ganz selten flackert sie
    fv = _font(int(420 * min(1.08, k)), "anton")
    if val:
        vw = d.textlength(val, font=fv)
        d.text((W / 2 - vw / 2, 640 - 420 * min(1.08, k) / 2 + 60), val, font=fv, fill=col)
    fsb = _fit(d, sub, 92, 900, "anton")
    if sub and t > 0.25:
        a = int(255 * min(1.0, (t - 0.25) / 0.3))
        d.text((W / 2 - d.textlength(sub, font=fsb) / 2, 1020), sub, font=fsb, fill=(232, 120, 60, a))
    if head:
        fh = _fit(d, " ".join(head), 40, 900, "SemiBold")
        d.text((W / 2 - d.textlength(" ".join(head), font=fh) / 2, 420), " ".join(head), font=fh, fill=(150, 150, 160))


DRAW = {"primes": _g_primes, "zeros": _g_zeros, "message": _g_message, "chapter": _g_chapter, "game": _g_game, "radar": _g_radar, "size": _g_size, "days": _g_days, "phone": _g_phone, "chart": _g_chart,
        "news": _g_news, "pulse": _g_pulse, "radio": _g_radio, "distance": _g_distance,
        "versus": _g_versus, "round": _g_round, "score": _g_score, "compare": _g_compare, "podium": _g_podium, "share": _g_share,
        "map": _g_map, "city": _g_city, "number": _g_number, "timer": _g_timer, "calendar": _g_calendar, "question": _g_question, "houses": _g_houses, "badge": _g_badge}


def _echo_phone(d, cx, cy, k, lit, name):
    """Handy für das Echo-Schaubild: steht aufrecht, Lautsprecher-Schlitz oben, Mikrofon-Punkt unten."""
    w, h = 96 * k, 190 * k
    d.rounded_rectangle((cx - w, cy - h, cx + w, cy + h), 30 * k, fill=(26, 28, 38, 255), outline=(8, 8, 14, 255), width=10)
    d.rounded_rectangle((cx - w + 16, cy - h + 44, cx + w - 16, cy + h - 44), 14 * k, fill=tuple(int(c * (0.55 + 0.45 * lit)) for c in (110, 190, 255)) + (255,))
    d.rounded_rectangle((cx - 26 * k, cy - h + 16, cx + 26 * k, cy - h + 28), 6, fill=(120, 130, 150, 255))
    d.ellipse((cx - 9, cy + h - 30, cx + 9, cy + h - 12), fill=(120, 130, 150, 255))
    d.ellipse((cx - 40 * k, cy - 70 * k, cx + 40 * k, cy + 10 * k), fill=(240, 246, 255, 255))                      # Kontaktbild: Kopf und Schultern
    d.pieslice((cx - 66 * k, cy + 20 * k, cx + 66 * k, cy + 150 * k), 180, 360, fill=(240, 246, 255, 255))
    f = _font(46, "Bold")
    tw = d.textlength(name, font=f)
    d.rounded_rectangle((cx - tw / 2 - 22, cy + h + 26, cx + tw / 2 + 22, cy + h + 92), 22, fill=(255, 255, 255, 255))
    d.text((cx - tw / 2, cy + h + 32), name, font=f, fill=INK)


def _g_echo(frame, g, t, dur):
    """Echo am Telefon: zwei Handys. Deine Stimme läuft als Welle oben hinüber, drüben aus dem Lautsprecher ins Mikrofon und unten – blasser,
    verspätet – wieder zurück. Mit sub="filter" hält eine Sperre die Rückwelle auf (Echo-Unterdrückung)."""
    k = _pop(t, 0.0, 0.35)
    if k <= 0:
        return
    d = ImageDraw.Draw(frame, "RGBA")
    lx, rx, cy = 215, W - 215, 860
    left = str(g.get("left") or "DU").upper()[:10]
    right = str(g.get("right") or "FREUND").upper()[:10]
    block = str(g.get("sub") or "").lower()[:6] in ("filter", "block", "stopp", "cancel")
    loop = 3.2
    u = (t % loop) / loop
    go, back = min(1.0, u / 0.42), min(1.0, max(0.0, (u - 0.5) / 0.42))
    _echo_phone(d, lx, cy, 1.2 * min(1.04, k), 0.4 + 0.6 * (1 if u < 0.2 or (back >= 1 and not block) else 0), left)
    _echo_phone(d, rx, cy, 1.2 * min(1.04, k), 0.4 + 0.6 * (1 if 0.4 < u < 0.62 else 0), right)

    def wave(p, y, col, rev, alpha):
        x0, x1 = (rx - 150, lx + 150) if rev else (lx + 150, rx - 150)
        x = x0 + (x1 - x0) * p
        sg = -1 if rev else 1
        for j in range(3):                                                    # drei Bögen hintereinander: eine Schallwelle
            xr = x - sg * j * 40
            if min(x0, x1) - 4 <= xr <= max(x0, x1) + 4:
                rr = 58 + j * 18
                a0 = (-60, 60) if not rev else (120, 240)
                d.arc((xr - rr, y - rr, xr + rr, y + rr), a0[0], a0[1], fill=col + (int(alpha * (1 - j * 0.25)),), width=16)

    d.line((lx + 150, cy - 130, rx - 150, cy - 130), fill=(255, 255, 255, 40), width=4)
    d.line((lx + 150, cy + 130, rx - 150, cy + 130), fill=(255, 255, 255, 40), width=4)
    if 0 < go < 1:
        wave(go, cy - 130, ORANGE, False, 255)
    stop = 0.45 if block else 1.0
    if 0 < back < stop:
        wave(back, cy + 130, (120, 200, 255), True, 200)
    if block:                                                                 # Sperre mitten auf dem Rückweg
        bx = W / 2 - 30
        hit = back >= stop
        col = (120, 230, 90, 255) if hit else (200, 210, 230, 255)
        d.rounded_rectangle((bx - 14, cy + 40, bx + 14, cy + 220), 10, fill=col, outline=(8, 8, 14, 255), width=5)
    d = ImageDraw.Draw(frame, "RGBA")
    _kicker(d, 300, g.get("kicker"), t, 0.0)
    f1 = _font(50, "Bold")
    for txt, y, col in ((str(g.get("value") or "DEINE STIMME").upper()[:18], cy - 290, ORANGE), (str(g.get("label") or ("GESTOPPT" if block else "ECHO")).upper()[:18], cy + 250, (150, 210, 255))):
        tw = d.textlength(txt, font=f1)
        d.text((W / 2 - tw / 2, y), txt, font=f1, fill=col + (255,), stroke_width=5, stroke_fill=(8, 8, 14, 255))
    lab = str(g.get("text") or "").upper()[:28]
    if lab and t > 0.5:
        _pill(d, W / 2, 1250, lab, _fit(d, lab, 64, 900, "Bold"), (40, 60, 130, 255), WHITE)


DRAW["echo"] = _g_echo


def _g_voice(frame, g, t, dur):
    """Warum die eigene Stimme fremd klingt: ein Kopf von vorn. Orange läuft der Schall vom Mund außen durch die Luft zum Ohr, blau wandert er
    innen durch die Schädelknochen zum anderen Ohr. Mit sub="air" bleibt nur der Luftweg – so hören dich die anderen und das Telefon."""
    k = _pop(t, 0.0, 0.35)
    if k <= 0:
        return
    d = ImageDraw.Draw(frame, "RGBA")
    cx, cy, r = W // 2, 840, int(250 * min(1.04, k))
    only_air = str(g.get("sub") or "").lower()[:3] in ("air", "luf", "tel")
    skin, ink = (255, 222, 190, 255), (8, 8, 14, 255)
    for sx in (-1, 1):                                                        # Ohren
        d.ellipse((cx + sx * r - 46, cy - 60, cx + sx * r + 46, cy + 60), fill=skin, outline=ink, width=10)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=skin, outline=ink, width=12)
    for sx in (-1, 1):                                                        # Augen
        d.ellipse((cx + sx * 96 - 44, cy - 96, cx + sx * 96 + 44, cy - 8), fill=(255, 255, 255, 255), outline=ink, width=8)
        d.ellipse((cx + sx * 96 - 16, cy - 66, cx + sx * 96 + 16, cy - 34), fill=ink)
    mo = 26 + 16 * abs(math.sin(t * 7))                                       # der Mund spricht
    d.ellipse((cx - 54, cy + 110 - mo, cx + 54, cy + 110 + mo), fill=(150, 40, 60, 255), outline=ink, width=8)
    u = (t % 1.6) / 1.6
    p0, p1, p2 = (cx + 70, cy + 124), (cx + r + 250, cy + 360), (cx + r + 52, cy + 6)   # Bogen: vom Mund außen herum zum rechten Ohr
    air = [((1 - q) ** 2 * p0[0] + 2 * q * (1 - q) * p1[0] + q * q * p2[0], (1 - q) ** 2 * p0[1] + 2 * q * (1 - q) * p1[1] + q * q * p2[1]) for q in [i / 30 for i in range(31)]]
    for i, (x, y) in enumerate(air):
        ph = (u - i / 30) % 1.0
        rr = 14 if ph < 0.16 else 7
        d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=ORANGE + (255 if ph < 0.16 else 150,))
    if not only_air:
        zig = [(cx - 64 - (r - 90) * i / 8, cy + 104 - 100 * i / 8 + (26 if i % 2 else -26) * (0 < i < 8)) for i in range(9)]   # innen: Zickzack durch den Knochen zum linken Ohr
        d.line(zig, fill=(60, 130, 255, 255), width=12, joint="curve")
        q = u * 8
        i0 = min(7, int(q))
        bx, by = zig[i0][0] + (zig[i0 + 1][0] - zig[i0][0]) * (q - i0), zig[i0][1] + (zig[i0 + 1][1] - zig[i0][1]) * (q - i0)
        d.ellipse((bx - 20, by - 20, bx + 20, by + 20), fill=(190, 220, 255, 255), outline=(8, 8, 14, 255), width=5)
    _kicker(d, 300, g.get("kicker"), t, 0.0)
    f1 = _font(50, "Bold")
    labs = [(str(g.get("right") or "LUFT").upper()[:12], cx + 330, cy + 330, ORANGE)]
    if not only_air:
        labs.append((str(g.get("left") or "KNOCHEN").upper()[:12], cx - 300, cy + 330, (120, 180, 255)))
    for txt, x, y, col in labs:
        tw = d.textlength(txt, font=f1)
        d.text((x - tw / 2, y), txt, font=f1, fill=col + (255,), stroke_width=5, stroke_fill=ink)
    lab = str(g.get("text") or "").upper()[:28]
    if lab and t > 0.5:
        _pill(d, W / 2, 1250, lab, _fit(d, lab, 64, 900, "Bold"), (40, 60, 130, 255), WHITE)


DRAW["voice"] = _g_voice


_EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF\u2300-\u23FF\u2600-\u27BF\u2B00-\u2BFF\uFE0E\uFE0F\u200D\u20E3]")


def clean(g):
    """Prüft eine Grafik-Beschreibung aus dem Drehbuch; gibt die saubere Fassung zurück oder None."""
    if not isinstance(g, dict) or str(g.get("type") or "").lower() not in TYPES:
        return None
    out = {"type": str(g["type"]).lower()}
    if out["type"] == "size":                    # welches Tier gezeigt wird (nur bekannte Wesen)
        kind = str(g.get("kind") or "").lower()
        out["kind"] = kind if re.fullmatch(r"[a-z_]{2,24}", kind) else "tardigrade"
    for k in ("kicker", "value", "label", "sub", "text", "left", "right"):
        v = g.get(k)
        if isinstance(v, (str, int, float)) and not isinstance(v, bool) and str(v).strip():
            v = " ".join(_EMOJI_RE.sub(" ", str(v)).split())
            v = re.sub(r"(?<=\d )B[Il1]{2}\b\.?", "BIO.", v)    # „10 BII.“ statt „10 BIO.“ groß im Bild (Video 197)      # Emojis kennt die Schrift nicht: „Bist du gut angekommen? ❤️“ zeigte ein leeres Kästchen (Video 190)
            if v:
                out[k] = _short_msg(v, 96) if out["type"] == "phone" and k in ("text", "sub", "label") else v[:44]   # Nachricht auf dem Handy: ganzer Satz
    if out.get("kicker") and out.get("text") and out["kicker"].strip().lower() == out["text"].strip().lower():
        out.pop("kicker")                         # „DER BLICK“ klein über „DER BLICK“ groß (Video 191): dieselbe Zeile nicht zweimal
    out["dark"] = g.get("dark") is True
    if out["type"] == "news" and g.get("tv") is True:
        out["tv"] = True                          # Eilmeldung im Fernsehen statt auf der Zeitungsseite
    need = {"number": "value", "timer": "value", "calendar": "value", "houses": "value", "badge": "text", "question": None,
            "map": None, "city": None, "versus": "left", "round": "text", "score": "value", "compare": "value", "podium": "text",
            "share": "value", "news": "text", "pulse": "value", "radio": "text", "distance": "value", "days": "value", "phone": "text", "chart": None, "game": None, "radar": None, "size": "value", "message": None, "chapter": "value", "echo": None, "voice": None, "primes": None, "zeros": None}[out["type"]]
    mode = str(g.get("mode") or "").lower()
    if out["type"] == "phone":
        out["mode"] = mode if mode in ("alert", "lock", "chat") else "alert"
    if need and need not in out:
        return None
    if out["type"] == "versus" and "right" not in out:
        return None
    if out["type"] == "compare" and (_num(out.get("value")) is None or _num(out.get("sub")) is None):
        return None
    if out["type"] == "score" and not re.match(r"^\s*\d{1,3}\s*[:\-–]\s*\d{1,3}\s*$", out["value"]):
        return None
    if out["type"] == "share" and not share_parts(out["value"]):
        return None
    if out["type"] == "size" and _size_val(out["value"]) is None:
        return None
    if out["type"] == "message":                 # Zeilen der Nachricht (sonst „text“ mit „/“ getrennt)
        lines = msg_lines(g)
        if not lines:
            return None
        out["lines"] = lines
        out.pop("text", None)
    return out


def frame(g, t, dur, mood=""):
    f = background(t, mood)
    DRAW[g["type"]](f, g, t, max(dur, 1.0))
    return f
