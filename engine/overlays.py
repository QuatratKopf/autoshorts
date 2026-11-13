"""Animierte Einblendungen im Stil erfolgreicher Erklär-Shorts: Infokarte, Notizzettel, Handy mit Nachrichten,
Checkliste, Füllbalken und A/B-Auswahl. Jede Einblendung wird als kurze PNG-Folge gezeichnet (Pop-in-Animation),
ffmpeg legt sie über die Szene und hält danach das letzte Bild."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .state import FONTS

FPS = 30
INK = (24, 24, 28)
WHITE = (250, 248, 244)
YELLOW = (255, 210, 63)
RED = (226, 58, 52)
GREEN = (52, 168, 83)
NOTE = (255, 224, 102)
BLUE = (37, 99, 235)
TALL = ("phone", "checklist", "note")   # hohe Einblendungen: Figuren werden dafür kleiner gezeichnet


def font(size, weight="ExtraBold"):
    for w in (weight, "ExtraBold", "Bold", "SemiBold"):
        for p in (FONTS / f"Poppins-{w}.ttf", Path(f"/usr/share/fonts/truetype/google-fonts/Poppins-{w}.ttf")):
            if p.exists():
                return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def _wrap(text, f, max_w):
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    lines, cur = [], ""
    for w in str(text).split():
        t = (cur + " " + w).strip()
        if cur and d.textlength(t, font=f) > max_w:
            lines.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


def _shadow(img, off=10, blur=14, alpha=110):
    a = img.split()[-1]
    sh = Image.new("RGBA", (img.width + 60, img.height + 60), (0, 0, 0, 0))
    m = Image.new("L", sh.size, 0)
    m.paste(a, (30 + off // 2, 30 + off))
    m = m.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: v * alpha // 255)
    sh.putalpha(m)
    sh.alpha_composite(img, (30, 30))
    return sh


# ------------------------------------------------------------------ Elemente (Endzustand)

def card(text, color=RED):
    f = font(92)
    lines = _wrap(text.upper(), f, 820)[:2]
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    w = int(max(d.textlength(l, font=f) for l in lines)) + 90
    h = 112 * len(lines) + 60
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.rounded_rectangle((0, 0, w - 1, h - 1), 26, fill=WHITE, outline=INK, width=8)
    for i, l in enumerate(lines):
        tw = dr.textlength(l, font=f)
        dr.text(((w - tw) / 2, 22 + i * 112), l, font=f, fill=color)
    return _shadow(im.rotate(-3, expand=True, resample=Image.BICUBIC))


def tag(text):
    """Kleines Beschriftungs-Schild (Ort, Zeit, Ding): farbiges Etikett, leicht schräg – wie in Erklär-Shorts."""
    text = text.upper()
    col = (RED, (238, 150, 30), GREEN, BLUE, (150, 80, 210))[sum(map(ord, text)) % 5]
    f = font(58)
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    w = int(d.textlength(text, font=f)) + 64
    h = 92
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.rounded_rectangle((0, 0, w - 1, h - 1), 22, fill=col, outline=INK, width=7)
    dr.rounded_rectangle((10, 8, w - 11, 22), 7, fill=tuple(min(255, c + 50) for c in col))         # Glanzkante
    dr.text((32, 12), text, font=f, fill=WHITE)
    return _shadow(im.rotate(4, expand=True, resample=Image.BICUBIC), 8, 10, 120)


def quote(head, text):
    """Zitat-Karte („FORSCHER WARNEN“ + Aussage): weiße Karte, Rolle als Kopfzeile, großes rotes Anführungszeichen – ohne Namen."""
    fh, ft, fq = font(40, "Bold"), font(52), _cfont(190)
    lines = _wrap(text, ft, 640)[:3]
    if len(_wrap(text, ft, 640)) > 3:
        lines[-1] = lines[-1].rstrip(".,;: ") + " …"
    w, h = 860, 150 + 66 * len(lines)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.rounded_rectangle((0, 0, w - 1, h - 1), 26, fill=WHITE, outline=INK, width=7)
    hw = dr.textlength(head, font=fh)
    dr.text(((w - hw) / 2, 26), head, font=fh, fill=RED)
    dr.line(((w - hw) / 2, 78, (w + hw) / 2, 78), fill=RED, width=4)
    dr.text((34, -30), "„", font=fq, fill=RED)                 # das deutsche Anführungszeichen sitzt tief: hochrücken zur ersten Zeile
    for i, l in enumerate(lines):
        dr.text((150, 104 + i * 66), l, font=ft, fill=INK)
    return _shadow(im.rotate(-2, expand=True, resample=Image.BICUBIC))


def thermo(value, shown=None):
    """Thermometer mit steigender Säule und großer Gradzahl: rot bei Hitze, blau bei Kälte."""
    v = float(value)
    s = v if shown is None else float(shown)
    col = (226, 58, 52) if v >= 25 else (37, 99, 235) if v <= 5 else (238, 150, 30)
    w, h = 470, 420
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    tx, top, bot = 90, 20, 330                                    # Röhre
    dr.rounded_rectangle((tx - 34, top, tx + 34, bot), 34, fill=WHITE, outline=INK, width=8)
    dr.ellipse((tx - 66, bot - 30, tx + 66, bot + 92), fill=col, outline=INK, width=8)
    lo, hi = min(-30.0, v - 10), max(45.0, v + 10)              # Skala reicht immer über den Wert hinaus
    k = max(0.0, min(1.0, (s - lo) / (hi - lo)))
    y = bot - 10 - (bot - top - 40) * k
    dr.rounded_rectangle((tx - 18, y, tx + 18, bot + 20), 18, fill=col)
    for i in range(1, 6):                                         # Skalenstriche
        yy = top + 30 + i * (bot - top - 60) / 6
        dr.line((tx + 36, yy, tx + 58, yy), fill=INK, width=5)
    dr.ellipse((tx - 40, bot - 6, tx - 10, bot + 24), fill=(255, 255, 255, 110))          # Glanz
    f = _cfont(150)
    txt = (f"{s:.0f}" if abs(v) >= 10 or v == int(v) else f"{s:.1f}".replace(".", ",")) + "°C"
    while dr.textlength(txt, font=f) > w - 180 and f.size > 60:
        f = _cfont(f.size - 8)
    dr.text((180, 150 - f.size / 2), txt, font=f, fill=col, stroke_width=8, stroke_fill=INK)
    return _shadow(im)


def stamp(text, color=RED):
    """Stempel („VERBOTEN“, „GIFTIG“, „GRATIS“): doppelter Rahmen, schräg, in kräftiger Farbe."""
    text = text.upper()
    f = font(84)
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    w = int(d.textlength(text, font=f)) + 110
    h = 170
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.rounded_rectangle((4, 4, w - 5, h - 5), 22, fill=(255, 255, 255, 215), outline=color, width=12)
    dr.rounded_rectangle((22, 22, w - 23, h - 23), 14, outline=color, width=5)
    dr.text((55, (h - f.size) / 2 - 12), text, font=f, fill=color)
    return _shadow(im.rotate(-7, expand=True, resample=Image.BICUBIC), 6, 8, 90)


def _slam(final, n=7):
    """Stempel-Auftritt: kommt groß herein und knallt auf seine Größe (umgekehrt zum Pop-in)."""
    frames = []
    for k, sc in enumerate((1.9, 1.55, 1.25, 0.94, 1.03, 1.0, 1.0)[:n]):
        im = final.resize((max(2, int(final.width * sc)), max(2, int(final.height * sc))), Image.BICUBIC)
        if k < 2:
            im.putalpha(im.split()[-1].point(lambda v, f=(k + 1) / 3: int(v * f)))
        frames.append(im)
    return frames


def note(title, text):
    ft, fb = font(44, "Bold"), font(64)
    lines = _wrap(text.upper(), fb, 600)[:4]
    w, h = 720, 150 + 82 * len(lines) + 40
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.rectangle((0, 0, w - 1, h - 1), fill=NOTE)
    dr.rectangle((0, 0, w - 1, 22), fill=(240, 205, 80))
    dr.rectangle((w // 2 - 80, -6, w // 2 + 80, 40), fill=(255, 255, 255, 150))   # Klebestreifen
    if title:
        tw = dr.textlength(title.upper(), font=ft)
        dr.text(((w - tw) / 2, 62), title.upper(), font=ft, fill=RED)
    for i, l in enumerate(lines):
        tw = dr.textlength(l, font=fb)
        dr.text(((w - tw) / 2, 130 + i * 82), l, font=fb, fill=INK)
    return _shadow(im.rotate(4, expand=True, resample=Image.BICUBIC))


def phone(title, items, n_visible=None):
    """Handy mit Nachrichten. Die Einblendung wird im Video auf rund 60 % verkleinert – deshalb große Schrift, höchstens drei Nachrichten."""
    import re
    items = [re.sub(r"[^\w\s.,;:!?…'\"„“()/%€+–-]", "", str(x)).strip() for x in items]      # Emojis kann die Schrift nicht (leeres Kästchen)
    items = [x for x in items if x][:3]
    n = len(items) if n_visible is None else n_visible
    w, h = 640, 1000
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.rounded_rectangle((0, 0, w - 1, h - 1), 70, fill=(20, 20, 24))
    dr.rounded_rectangle((18, 18, w - 19, h - 19), 56, fill=(58, 64, 140))
    dr.rounded_rectangle((w // 2 - 80, 34, w // 2 + 80, 70), 18, fill=(20, 20, 24))
    fc = font(104, "Bold")
    clock = (title or "3:12").strip()
    while dr.textlength(clock, font=fc) > w - 110 and fc.size > 44:      # „UNBEKANNT“ statt Uhrzeit: kleiner statt abgeschnitten
        fc = font(fc.size - 8, "Bold")
    tw = dr.textlength(clock, font=fc)
    dr.text(((w - tw) / 2, 92 + (104 - fc.size) / 2), clock, font=fc, fill=WHITE)
    fi, fs = font(40, "Bold"), font(44, "SemiBold")
    y = 250
    for i, it in enumerate(items[:n]):
        head, _, body = it.partition(":")
        lines = _wrap(body.strip(), fs, 500)[:3] if body.strip() else []
        bh = 74 + 54 * len(lines) + (10 if lines else 0)
        if y + bh > h - 46:
            break
        dr.rounded_rectangle((40, y, w - 41, y + bh), 28, fill=(246, 246, 248))
        dr.ellipse((60, y + 18, 100, y + 58), fill=RED if i == 0 else (90, 90, 96))
        dr.text((116, y + 12), _short(head.strip(), 20), font=fi, fill=INK if lines else (60, 60, 68))
        for k, l in enumerate(lines):
            dr.text((62, y + 68 + k * 54), l, font=fs, fill=(52, 52, 60))
        y += bh + 18
    return _shadow(im, off=14, blur=20)


def checklist(title, items, n_checked=None):
    rows = []
    for it in items[:5]:
        if isinstance(it, (list, tuple)):
            rows.append((str(it[0]), bool(it[1]) if len(it) > 1 else True))
        else:
            rows.append((str(it), True))
    n = sum(1 for _, c in rows if c) if n_checked is None else n_checked
    ft, fi = font(66), font(54, "Bold")
    w, h = 820, 170 + 96 * len(rows) + 30
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.rounded_rectangle((0, 0, w - 1, h - 1), 28, fill=WHITE, outline=INK, width=6)
    tw = dr.textlength(title.upper(), font=ft)
    dr.text(((w - tw) / 2, 36), title.upper(), font=ft, fill=RED)
    done = 0
    for i, (t, c) in enumerate(rows):
        y = 160 + i * 96
        dr.text((60, y), _short(t, 22), font=fi, fill=INK)
        bx = w - 140
        dr.rounded_rectangle((bx, y + 6, bx + 64, y + 70), 10, outline=INK, width=6, fill=WHITE)
        if c and done < n:
            dr.line((bx + 12, y + 38, bx + 28, y + 56, bx + 56, y + 18), fill=GREEN, width=12, joint="curve")
            done += 1
    return _shadow(im)


def _short(text, n):
    """Kürzt an einer Wortgrenze statt mitten im Wort."""
    text = " ".join(str(text or "").split())
    if len(text) <= n:
        return text
    cut = text[:n + 1].rsplit(" ", 1)[0]
    return cut if len(cut) >= n * 0.4 else text[:n]


def bar(label, value, shown=None):
    v = max(0, min(100, int(value)))
    s = v if shown is None else shown
    label = _short(label, 28).upper()
    fl, fv = font(46), font(44)
    w, h = 900, 120
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    while dr.textlength(label, font=fl) > w * 0.55 and fl.size > 24:      # lange Beschriftung: kleiner statt abgeschnitten
        fl = font(fl.size - 3)
    dr.rounded_rectangle((0, 0, w - 1, h - 1), 26, fill=WHITE, outline=INK, width=6)
    lw = dr.textlength(label, font=fl) + 50
    dr.text((26, (h - fl.size) / 2 - 6), label, font=fl, fill=INK)
    x0, x1 = lw + 10, w - 30
    dr.rounded_rectangle((x0, 32, x1, h - 32), 26, fill=(230, 230, 232), outline=INK, width=4)
    fx = x0 + (x1 - x0) * s / 100
    if s > 0:
        dr.rounded_rectangle((x0, 32, max(x0 + 40, fx), h - 32), 26, fill=RED if v < 35 else GREEN, outline=INK, width=4)
    t = f"{int(s)}%"
    tw = dr.textlength(t, font=fv)
    dr.text(((x0 + x1 - tw) / 2, 30), t, font=fv, fill=INK)
    return _shadow(im)


def choice(a, b):
    fa, fl = font(54, "Bold"), font(62)
    w = 900
    im = Image.new("RGBA", (w, 360), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    for i, (letter, txt, col) in enumerate((("A", a, RED), ("B", b, YELLOW))):
        y = i * 180
        dr.rounded_rectangle((0, y, w - 1, y + 150), 24, fill=(28, 28, 34), outline=col, width=8)
        dr.rounded_rectangle((22, y + 25, 122, y + 125), 18, fill=col)
        lw = dr.textlength(letter, font=fl)
        dr.text((72 - lw / 2, y + 30), letter, font=fl, fill=WHITE if col == RED else INK)
        lines = _wrap(str(txt).upper(), fa, 700)[:2]
        for k, l in enumerate(lines):
            dr.text((150, y + (46 if len(lines) == 1 else 18) + k * 62), l, font=fa, fill=WHITE)
    return _shadow(im)


# ------------------------------------------------------------------ Animation

def _cfont(size):
    """Schmale fette Schrift (Anton) für große Zahlen – sonst Poppins."""
    for pth in (FONTS / "Anton-Regular.ttf", Path("/usr/share/fonts/truetype/google-fonts/Anton-Regular.ttf")):
        if pth.exists():
            return ImageFont.truetype(str(pth), size)
    return font(int(size * 0.8))


def _num(v, decimals):
    txt = f"{v:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return txt


def counter(label, value, unit, shown=None, sub=""):
    """Großer Zähler wie in Erklärvideos: kleine Zeile, darunter die hochlaufende Zahl mit Einheit."""
    try:
        v = float(str(value).replace(",", "."))
    except ValueError:
        v = 0.0
    decimals = 0 if abs(v - round(v)) < 1e-9 else (1 if abs(v * 10 - round(v * 10)) < 1e-9 else 2)
    cur = v if shown is None else shown
    fl, fn, fs = font(34, "Bold"), _cfont(150), font(40, "Bold")
    txt = (_num(cur, decimals) + (" " + unit.upper() if unit else "")).strip()
    w, h = 980, 330
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    while dr.textlength(_num(v, decimals) + (" " + unit.upper() if unit else ""), font=fn) > w - 60 and fn.size > 70:
        fn = _cfont(fn.size - 10)
    lab = "  ".join(label.upper()) if len(label) <= 22 else label.upper()
    if dr.textlength(lab, font=fl) > w - 40:              # lange Zeile: ohne Sperrung und notfalls kleiner – nie abgeschnitten
        lab = label.upper()
        while dr.textlength(lab, font=fl) > w - 40 and fl.size > 20:
            fl = font(fl.size - 2, "Bold")
    dr.text(((w - dr.textlength(lab, font=fl)) / 2, 6), lab, font=fl, fill=(235, 235, 235), stroke_width=5, stroke_fill=INK)
    tw = dr.textlength(txt, font=fn)
    dr.text(((w - tw) / 2 + 6, 62 + 8), txt, font=fn, fill=(0, 0, 0, 150))
    dr.text(((w - tw) / 2, 62), txt, font=fn, fill=WHITE, stroke_width=7, stroke_fill=INK)
    if sub:
        dr.text(((w - dr.textlength(sub.upper(), font=fs)) / 2, 62 + fn.size + 34), sub.upper(), font=fs, fill=(255, 138, 31), stroke_width=5, stroke_fill=INK)
    return im


def _pop(final, n=9):
    """Pop-in: klein → etwas zu groß → normal, mit Einblenden."""
    curve = [0.55, 0.75, 0.92, 1.06, 1.1, 1.06, 1.02, 1.0, 1.0][:n]
    frames = []
    for k, s in enumerate(curve):
        im = final.resize((max(2, int(final.width * s)), max(2, int(final.height * s))), Image.BICUBIC)
        if k < 3:
            a = im.split()[-1].point(lambda v, f=(k + 1) / 4: int(v * f))
            im.putalpha(a)
        frames.append(im)
    return frames


def frames_for(ov: dict):
    """Gibt (Bilder, Mittelpunkt-y) für eine Einblendung zurück, oder None."""
    if not isinstance(ov, dict):
        return None
    t = str(ov.get("type") or "").lower()
    try:
        if t == "card" and ov.get("text"):
            import re
            txt = re.sub(r"(?i)\bkm\s+h\b", "KM/H", str(ov["text"]))        # „300 KM H“ → „300 KM/H“
            return _pop(card(_short(txt, 30))), 420
        if t == "quote" and ov.get("text"):
            return _pop(quote(_short(str(ov.get("title") or "EXPERTEN").upper(), 26), _short(str(ov["text"]), 120))), 520
        if t == "thermo" and ov.get("value") is not None:
            v = float(str(ov["value"]).replace(",", "."))
            fr = _pop(thermo(v, min(v, -30.0 if v > -30 else v)), 5)
            n = 22
            for k in range(1, n + 1):                              # Säule steigt (oder fällt) auf den Wert
                f = 1 - (1 - k / n) ** 2.2
                start = min(0.0, v)
                fr.append(thermo(v, start + (v - start) * f))
            return fr, 330
        if t == "stamp" and ov.get("text"):
            col = {"red": RED, "green": GREEN, "orange": (238, 130, 20), "purple": (130, 60, 190)}.get(str(ov.get("color") or "red"), RED)
            return _slam(stamp(_short(str(ov["text"]), 16), col)), 360
        if t == "tag" and ov.get("text"):
            return _pop(tag(_short(str(ov["text"]), 22))), 300
        if t == "note" and ov.get("text"):
            return _pop(note(_short(ov.get("title") or "", 20), _short(ov["text"], 80))), 560
        if t == "phone" and ov.get("items"):
            items = ov["items"]
            fr = _pop(phone(_short(ov.get("title") or "", 16), items, 0))
            for k in range(1, min(4, len(items)) + 1):   # Nachrichten erscheinen nacheinander
                fr += [phone(_short(ov.get("title") or "", 16), items, k)] * 10
            return fr, 760
        if t == "checklist" and ov.get("items"):
            items = ov["items"]
            fr = _pop(checklist(_short(ov.get("title") or "", 18), items, 0))
            n = sum(1 for it in items[:5] if not isinstance(it, (list, tuple)) or len(it) < 2 or it[1])
            for k in range(1, n + 1):   # Haken nacheinander setzen
                fr += [checklist(_short(ov.get("title") or "", 18), items, k)] * 9
            return fr, 640
        if t == "bar" and ov.get("label") is not None:
            v = int(float(ov.get("value") or 0))
            fr = _pop(bar(str(ov["label"]), v, 0), 6)
            fr += [bar(str(ov["label"]), v, v * k / 24) for k in range(1, 25)]   # Balken füllt sich
            return fr, 300
        if t == "counter" and ov.get("value") is not None:
            lab, unit, sub = str(ov.get("label") or "")[:26], str(ov.get("unit") or "")[:16], str(ov.get("sub") or "")[:30]
            try:
                v = float(str(ov["value"]).replace(",", "."))
                v0 = float(str(ov.get("from") or 0).replace(",", "."))
            except ValueError:
                return None
            fr = _pop(counter(lab, v, unit, v0, ""), 5)
            n = 34
            for k in range(1, n + 1):                              # Zahl läuft hoch, am Ende langsamer
                f = 1 - (1 - k / n) ** 2.4
                fr.append(counter(lab, v, unit, v0 + (v - v0) * f, ""))
            fr += [counter(lab, v, unit, None, sub)] * 2
            return fr, 330
        if t == "choice" and ov.get("a") and ov.get("b"):
            return _pop(choice(_short(ov["a"], 40), _short(ov["b"], 40))), 640
    except Exception:  # noqa: BLE001
        return None
    return None


def write_frames(ov, folder: Path):
    """Schreibt die PNG-Folge; gibt (Muster, Mittelpunkt-y) oder None zurück."""
    res = frames_for(ov)
    if not res:
        return None
    frames, cy = res
    folder.mkdir(parents=True, exist_ok=True)
    cw, ch = max(f.width for f in frames), max(f.height for f in frames)
    for i, im in enumerate(frames):   # alle Bilder gleich groß, Inhalt mittig (ffmpeg mag keine wechselnden Größen)
        canvas = Image.new("RGBA", (cw + cw % 2, ch + ch % 2), (0, 0, 0, 0))
        canvas.alpha_composite(im, ((cw - im.width) // 2, (ch - im.height) // 2))
        canvas.save(folder / f"f{i:03d}.png")
    return str(folder / "f%03d.png"), cy, cw + cw % 2, ch + ch % 2
