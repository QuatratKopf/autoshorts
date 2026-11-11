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
TYPES = ("number", "timer", "calendar", "question", "houses", "badge", "map", "city", "versus", "round", "score", "compare", "podium", "share", "news", "pulse", "radio", "distance", "days", "phone", "chart")
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
            msg = str(g.get("text") or "")[:44]
            lines = _lines(d, msg, _font(44, "SemiBold"), sw - 40)[:2]
            for i, ln in enumerate(lines):
                d.text((sx0 + 48, y + 104 + i * 54), ln, font=_font(44, "SemiBold"), fill=(50, 50, 60))
    elif mode == "chat":
        d.rounded_rectangle((sx0, sy0, sx1, sy0 + 190), 58, fill=(250, 248, 244))
        d.rectangle((sx0, sy0 + 120, sx1, sy0 + 190), fill=(250, 248, 244))
        d.ellipse((sx0 + 30, sy0 + 84, sx0 + 116, sy0 + 170), fill=(200, 170, 230), outline=INK, width=4)
        name = (kick or "CHAT").title()
        d.text((sx0 + 134, sy0 + 100), name, font=_fit(d, name, 54, sw - 130, "Bold"), fill=INK)
        y = sy0 + 240
        for i, (key, mine) in enumerate((("text", False), ("sub", True), ("label", False))):
            msg = str(g.get(key) or "")[:44]
            kk = _pop(t, 0.4 + i * 0.7, 0.3)
            if not msg or kk <= 0:
                continue
            f = _font(46, "SemiBold")
            lines = _lines(d, msg, f, sw - 150)[:3]
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
    _kicker(d, 430, g.get("kicker"), t, 0.0)
    x0, x1, y0, y1 = 110, 970, 540, 1130
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
    y = y1 + 110
    if val and t > 0.5:
        kk = _pop(t, 0.5, 0.4)
        f = _fit(d, val.upper(), int(170 * min(1.06, kk)), 940)
        _center(d, y + (170 - f.size) / 2, _count(val, t, 0.5, 1.4).upper(), f, fill=WHITE)
        y += 200
    if g.get("label") and t > 0.7:
        f = _fit(d, str(g["label"]).upper(), 60, 940, "Bold")
        _center(d, y, str(g["label"]).upper()[:40], f, fill=ORANGE if not down else (255, 150, 140))


def _lines(d, text, f, max_w):
    out, cur = [], ""
    for w in str(text).split():
        if cur and d.textlength(cur + " " + w, font=f) > max_w:
            out.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    return out + ([cur] if cur else [])


DRAW = {"days": _g_days, "phone": _g_phone, "chart": _g_chart,
        "news": _g_news, "pulse": _g_pulse, "radio": _g_radio, "distance": _g_distance,
        "versus": _g_versus, "round": _g_round, "score": _g_score, "compare": _g_compare, "podium": _g_podium, "share": _g_share,
        "map": _g_map, "city": _g_city, "number": _g_number, "timer": _g_timer, "calendar": _g_calendar, "question": _g_question, "houses": _g_houses, "badge": _g_badge}


def clean(g):
    """Prüft eine Grafik-Beschreibung aus dem Drehbuch; gibt die saubere Fassung zurück oder None."""
    if not isinstance(g, dict) or str(g.get("type") or "").lower() not in TYPES:
        return None
    out = {"type": str(g["type"]).lower()}
    for k in ("kicker", "value", "label", "sub", "text", "left", "right"):
        v = g.get(k)
        if isinstance(v, (str, int, float)) and not isinstance(v, bool) and str(v).strip():
            out[k] = str(v).strip()[:44]
    out["dark"] = g.get("dark") is True
    need = {"number": "value", "timer": "value", "calendar": "value", "houses": "value", "badge": "text", "question": None,
            "map": None, "city": None, "versus": "left", "round": "text", "score": "value", "compare": "value", "podium": "text",
            "share": "value", "news": "text", "pulse": "value", "radio": "text", "distance": "value", "days": "value", "phone": "text", "chart": None}[out["type"]]
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
    return out


def frame(g, t, dur, mood=""):
    f = background(t, mood)
    DRAW[g["type"]](f, g, t, max(dur, 1.0))
    return f
