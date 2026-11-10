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
    items = [str(x) for x in items][:4]
    n = len(items) if n_visible is None else n_visible
    w, h = 640, 1000
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.rounded_rectangle((0, 0, w - 1, h - 1), 70, fill=(20, 20, 24))
    dr.rounded_rectangle((18, 18, w - 19, h - 19), 56, fill=(58, 64, 140))
    dr.rounded_rectangle((w // 2 - 80, 34, w // 2 + 80, 70), 18, fill=(20, 20, 24))
    fc, ft = font(150, "Bold"), font(36, "SemiBold")
    clock = (title or "3:12").strip()
    while dr.textlength(clock, font=fc) > w - 110 and fc.size > 44:      # „UNBEKANNT“ statt Uhrzeit: kleiner statt abgeschnitten
        fc = font(fc.size - 8, "Bold")
    tw = dr.textlength(clock, font=fc)
    dr.text(((w - tw) / 2, 110 + (150 - fc.size) / 2), clock, font=fc, fill=WHITE)
    fi, fs = font(34, "Bold"), font(28, "SemiBold")
    y = 340
    for i, it in enumerate(items[:n]):
        head, _, body = it.partition(":")
        lines = _wrap(body.strip() or head, fs, 470)[:2] if body else []
        bh = 76 + 36 * len(lines)
        dr.rounded_rectangle((44, y, w - 45, y + bh), 26, fill=(246, 246, 248))
        dr.ellipse((66, y + 20, 110, y + 64), fill=RED if i == 0 else (90, 90, 96))
        dr.text((128, y + 18), _short(head.strip(), 26), font=fi, fill=INK)
        for k, l in enumerate(lines):
            dr.text((128, y + 62 + k * 36), l, font=fs, fill=(80, 80, 88))
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
    lab = "  ".join(label.upper())[:60] if len(label) <= 22 else label.upper()
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
            return _pop(card(_short(ov["text"], 30))), 420
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
