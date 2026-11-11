"""Orte im flachen Vektorstil (1080×1920). Jede Funktion zeichnet einen Hintergrund; GROUND ist die Bodenlinie,
auf der die Figuren stehen. Alle Orte gibt es bei Tag und bei Nacht."""
import math
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter

W, H = 1080, 1920
GROUND = 1270
HORIZON = 830             # Augenhöhe der Kamera: dort liegen die Köpfe aller stehenden Menschen
FAR = 900                 # Fußlinie der fernen Kulisse (Skyline, Berge, Waldrand)
PX_M = 246                # Bildpunkte pro Meter bei Maßstab 1 (eine Figur ist rund 1,75 m groß)


def depth(y):
    """Maßstab für alles, was mit den Füßen auf Bildhöhe y steht: vorn groß, hinten klein (eine Perspektive für alles)."""
    return max(0.12, 1.08 * (y - HORIZON) / (GROUND + 18 - HORIZON))


def px(meters, y):
    """Meter → Bildpunkte in der Tiefe y. Damit haben Autos, Häuser, Bäume und Menschen überall das richtige Verhältnis."""
    return meters * PX_M * depth(y)
INK = (22, 22, 26)
O = 7


def _mix(c, f, to=(14, 16, 40)):
    return tuple(int(c[i] * (1 - f) + to[i] * f) for i in range(3))


DARK = [False]


class P:
    """Zeichenhilfe: Formen mit dunklem Umriss; bei Nacht werden alle Farben abgedunkelt/bläulich."""

    def __init__(self, night):
        self.night = night
        self.dark = DARK[0]           # Stromausfall: keine erleuchteten Fenster, keine Lampen
        self.im = Image.new("RGB", (W, H), (0, 0, 0))
        self.d = ImageDraw.Draw(self.im)
        self.indoor = False           # setzt room(): Zimmer bekommen Fensterlicht, Deckenschatten und Bodenglanz
        self.outdoor = False          # setzt compose(): Landschaften bekommen Dunst am Horizont
        self.windows = []             # Fenster des Zimmers (für die Lichtbahnen)
        self.sun = None               # Mittelpunkt der Sonne / des Mondes (für den Lichtschein)

    # --- weiche Flächen (Verläufe, Lichtschein, Schatten) – geben dem flachen Stil Tiefe
    def grad(self, box, top, bot, raw=False):
        """Senkrechter Farbverlauf in einem Rechteck."""
        x0, y0, x1, y1 = [int(v) for v in box]
        if x1 <= x0 or y1 <= y0:
            return
        m = Image.linear_gradient("L").resize((x1 - x0, y1 - y0))
        a, b = (top, bot) if raw else (self.c(top), self.c(bot))
        self.im.paste(Image.composite(Image.new("RGB", (x1 - x0, y1 - y0), b), Image.new("RGB", (x1 - x0, y1 - y0), a), m), (x0, y0))
        self.d = ImageDraw.Draw(self.im)

    def veil(self, shape, col, alpha, blur=0, kind="ellipse"):
        """Halbtransparente Fläche (Lichtschein, Schatten, Dunst): shape = Rechteck oder Punktliste."""
        m = Image.new("L", (W, H), 0)
        md = ImageDraw.Draw(m)
        if kind == "ellipse":
            md.ellipse(shape, fill=alpha)
        elif kind == "rect":
            md.rectangle(shape, fill=alpha)
        else:
            md.polygon(shape, fill=alpha)
        if blur:
            m = m.filter(ImageFilter.GaussianBlur(blur))
        self.im.paste(Image.new("RGB", (W, H), col), (0, 0), m)
        self.d = ImageDraw.Draw(self.im)

    def fade(self, box, col, a0, a1):
        """Farbschleier über ein Rechteck, dessen Stärke von oben (a0) nach unten (a1) verläuft (0–255)."""
        x0, y0, x1, y1 = [int(v) for v in box]
        if x1 <= x0 or y1 <= y0:
            return
        m = Image.linear_gradient("L").resize((x1 - x0, y1 - y0)).point(lambda v: int(a0 + (a1 - a0) * v / 255))
        self.im.paste(Image.new("RGB", (x1 - x0, y1 - y0), col), (x0, y0), m)
        self.d = ImageDraw.Draw(self.im)

    def blobs(self, parts, col, o=O, hi=0.14, lo=0.16):
        """Mehrere Kreise als EINE Form (Baumkrone, Busch, Wolke): gemeinsamer Umriss, Schatten unten, Licht oben."""
        col = self.c(col)
        if o:
            for cx, cy, r in parts:
                self.d.ellipse((cx - r - o, cy - r - o, cx + r + o, cy + r + o), fill=INK)
        if lo:
            for cx, cy, r in parts:
                self.d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=_mix(col, lo, (10, 20, 50)))
            for cx, cy, r in parts:
                self.d.ellipse((cx - r, cy - r - r * 0.16, cx + r, cy + r - r * 0.16), fill=col) if r > 12 else None
        else:
            for cx, cy, r in parts:
                self.d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col)
        if hi:
            for cx, cy, r in parts:
                self.d.ellipse((cx - r * 0.62, cy - r * 0.78, cx + r * 0.18, cy - r * 0.1), fill=_mix(col, hi, (255, 255, 235)))

    def cloud(self, cx, cy, s=1.0, col=(255, 255, 255), shade=(214, 228, 246)):
        parts = [(cx + dx * s, cy + dy * s, r * s) for dx, dy, r in ((-96, 14, 46), (-48, -14, 62), (14, -30, 74), (76, -6, 58), (120, 18, 40))]
        for x, y, r in parts:
            self.d.ellipse((x - r, y - r + 12 * s, x + r, y + r + 12 * s), fill=shade)
        for x, y, r in parts:
            self.d.ellipse((x - r, y - r, x + r, y + r), fill=col)
        self.d.rounded_rectangle((cx - 140 * s, cy + 14 * s, cx + 158 * s, cy + 58 * s), 22 * s, fill=shade)
        self.d.rounded_rectangle((cx - 140 * s, cy + 6 * s, cx + 158 * s, cy + 46 * s), 22 * s, fill=col)

    def c(self, col, glow=False):
        return col if (glow or not self.night) else _mix(col, 0.5, (22, 26, 66))

    def rect(self, box, col, r=0, o=O, glow=False):
        if r:
            self.d.rounded_rectangle(box, r, fill=self.c(col, glow), outline=INK if o else None, width=o)
        else:
            self.d.rectangle(box, fill=self.c(col, glow), outline=INK if o else None, width=o)

    def oval(self, box, col, o=O, glow=False):
        self.d.ellipse(box, fill=self.c(col, glow), outline=INK if o else None, width=o)

    def poly(self, pts, col, o=O, glow=False):
        self.d.polygon(pts, fill=self.c(col, glow), outline=INK if o else None, width=o)

    def line(self, pts, col=INK, w=O):
        self.d.line(pts, fill=col, width=w, joint="curve")

    def stripes(self, box, col, step=90, f=0.06):
        x0, y0, x1, y1 = box
        for x in range(x0, x1, step * 2):
            self.d.rectangle((x, y0, min(x1, x + step), y1), fill=self.c(_mix(col, f, (255, 255, 255))))

    # --- Bausteine
    def sky(self, y1=GROUND):
        mood = getattr(self, "mood", "")
        top, bot = ((14, 18, 52), (58, 60, 128)) if self.night else ((84, 168, 246), (196, 232, 255))
        if mood == "sunset":
            top, bot = (64, 58, 132), (255, 176, 112)
        elif mood == "storm":
            top, bot = (62, 70, 90), (150, 158, 174)
        elif mood == "red":
            top, bot = (84, 26, 30), (234, 124, 70)
        elif mood == "haze":
            top, bot = (196, 186, 148), (242, 228, 192)
        self.grad((0, 0, W, y1), top, bot, raw=True)
        glow = {"sunset": (255, 214, 150), "red": (255, 170, 110), "storm": (190, 196, 208), "haze": (255, 244, 214)}.get(mood, (110, 96, 170) if self.night else (240, 250, 255))
        self.fade((0, y1 - 330, W, y1), glow, 0, 150)                       # heller Schein über dem Horizont
        rnd = random.Random(7)
        if self.night:
            for _ in range(110):
                x, y, r = rnd.randint(0, W), rnd.randint(0, y1 - 160), rnd.choice((1, 2, 2, 2, 3, 4))
                self.d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 230) if r > 1 else (200, 206, 240))
            self.veil((640, 130, 1040, 530), (150, 160, 230), 90, 60)        # Hof um den Mond
            self.d.ellipse((760, 250, 920, 410), fill=(250, 244, 204))
            for cx, cy, r in ((812, 306, 20), (866, 356, 15), (838, 372, 9), (880, 296, 8)):
                self.d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(228, 220, 176))
            self.sun = (840, 330)
        elif mood in ("storm", "red"):
            dark, mid = ((70, 76, 94), (104, 110, 128)) if mood == "storm" else ((104, 48, 42), (150, 78, 60))
            for cx, cy, sc in ((230, 300, 1.5), (720, 400, 1.25), (1010, 250, 1.0), (470, 560, 0.8)):
                self.cloud(cx, cy, sc, mid, dark)
        else:
            sun = (255, 150, 70) if mood == "sunset" else (255, 220, 84)
            self.veil((610, 80, 1090, 560), (255, 244, 200), 120, 70)        # Sonnenhof
            self.veil((726, 196, 974, 444), (255, 250, 220), 150, 18)
            self.d.ellipse((770, 240, 930, 400), fill=sun)
            self.d.ellipse((786, 252, 900, 366), fill=_mix(sun, 0.3, (255, 255, 255)))
            self.sun = (850, 320)
            for cx, cy, sc in ((240, 380, 1.0), (640, 560, 0.62), (1010, 640, 0.42), (90, 690, 0.36)):
                self.cloud(cx, cy, sc, (255, 255, 255) if mood != "haze" else (250, 244, 226), (214, 228, 246) if mood != "haze" else (226, 214, 186))

    def window(self, box, curtain=None):
        """Fenster mit Rahmen, Fensterbank und Blick nach draußen; curtain = Farbe der Vorhänge (None = keine)."""
        x0, y0, x1, y1 = box
        self.windows.append(box)
        if curtain:                                                           # Vorhangstange
            self.rect((x0 - 96, y0 - 64, x1 + 96, y0 - 46), (120, 84, 56), r=8, o=5)
        self.rect((x0 - 18, y0 - 18, x1 + 18, y1 + 18), (250, 250, 246), r=8)
        if self.night:
            self.grad((x0, y0, x1, y1), (20, 24, 70), (52, 56, 120), raw=True)
            self.d.ellipse((x1 - 110, y0 + 30, x1 - 40, y0 + 100), fill=(250, 244, 200))
            for i in range(9):
                x, y = x0 + 30 + (i * 67) % (x1 - x0 - 60), y0 + 30 + (i * 41) % (y1 - y0 - 120)
                self.d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(255, 255, 230))
            self.d.polygon([(x0, y1), (x0, y1 - 50), (x0 + (x1 - x0) * 0.3, y1 - 86), (x0 + (x1 - x0) * 0.62, y1 - 54), (x1, y1 - 92), (x1, y1)], fill=(24, 40, 54))
        else:
            self.grad((x0, y0, x1, y1), (120, 196, 252), (212, 238, 255), raw=True)
            for cx, cy, r in ((x0 + 86, y0 + 92, 36), (x0 + 130, y0 + 74, 46), (x0 + 180, y0 + 96, 34)):
                self.d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 255, 255))
            w, hh = x1 - x0, y1 - y0
            pane = Image.new("RGBA", (w, hh), (0, 0, 0, 0))                    # Hügel und Spiegelung: nur innerhalb der Scheibe
            pd = ImageDraw.Draw(pane)
            pd.ellipse((-w * 0.3, hh - 130, w * 0.75, hh + 150), fill=(150, 206, 122, 255))
            pd.ellipse((w * 0.3, hh - 96, w * 1.4, hh + 130), fill=(118, 190, 100, 255))
            pd.rectangle((0, hh - 24, w, hh), fill=(104, 180, 92, 255))
            pd.polygon([(w * 0.14, 0), (w * 0.30, 0), (w * 0.10, hh), (-w * 0.06, hh)], fill=(255, 255, 255, 90))
            pd.polygon([(w * 0.36, 0), (w * 0.42, 0), (w * 0.22, hh), (w * 0.16, hh)], fill=(255, 255, 255, 70))
            self.im.paste(pane, (int(x0), int(y0)), pane)
            self.d = ImageDraw.Draw(self.im)
        self.d.rectangle((x0, y0, x1, y1), outline=INK, width=O)
        self.line(((x0 + x1) // 2, y0, (x0 + x1) // 2, y1))
        self.line((x0, (y0 + y1) // 2, x1, (y0 + y1) // 2))
        self.rect((x0 - 34, y1 + 14, x1 + 34, y1 + 40), (236, 232, 222), r=6, o=5)                            # Fensterbank
        if curtain:
            dark = _mix(curtain, 0.22, (40, 20, 30))
            for sx, a, b_ in ((x0 - 78, x0 - 78, x0 + 34), (x1 - 34, x1 - 34, x1 + 78)):
                self.rect((a, y0 - 50, b_, y1 + 70), curtain, r=18, o=6)
                for k in range(1, 4):                                         # Falten
                    xx = a + (b_ - a) * k / 4
                    self.d.line((xx, y0 - 36, xx, y1 + 56), fill=self.c(dark), width=6)

    def room(self, wall, floor, stripe=True, panel=True):
        """Zimmer: Wand mit feinem Streifenmuster und Sockelzone, Fußleiste, Dielenboden in Perspektive."""
        self.indoor = True
        base = GROUND - 60
        self.grad((0, 0, W, base), _mix(wall, 0.10, (20, 20, 50)), _mix(wall, 0.05, (255, 255, 255)))
        if stripe:
            for x in range(0, W, 120):
                self.d.rectangle((x, 0, x + 60, base), fill=self.c(_mix(wall, 0.028, (255, 255, 255))))
        if panel:                                                             # Sockelzone: dunklerer Wandstreifen mit Leiste
            pc = _mix(wall, 0.16, (60, 40, 50))
            self.d.rectangle((0, base - 210, W, base), fill=self.c(pc))
            for x in range(40, W, 200):
                self.d.rounded_rectangle((x, base - 180, x + 160, base - 34), 8, outline=self.c(_mix(pc, 0.16, (20, 14, 30))), width=5)
            self.rect((-10, base - 226, W + 10, base - 204), _mix(wall, 0.3, (255, 255, 255)), o=5)
        self.rect((-10, GROUND - 78, W + 10, GROUND - 40), (250, 248, 240), o=5)
        y0 = GROUND - 40
        self.grad((0, y0, W, H), _mix(floor, 0.10, (255, 240, 210)), _mix(floor, 0.20, (40, 20, 20)))
        seam = _mix(floor, 0.30, (40, 24, 10))
        xs = [(W / 2 + i * 60, W / 2 + i * 190) for i in range(-10, 12)]
        for i, ((a0, a1), (b0, b1)) in enumerate(zip(xs, xs[1:])):            # Dielen: jede zweite leicht heller
            if i % 2:
                m = Image.new("L", (W, H), 0)
                ImageDraw.Draw(m).polygon([(a0, y0), (b0, y0), (b1, H), (a1, H)], fill=26)
                self.im.paste(Image.new("RGB", (W, H), (255, 244, 220)), (0, 0), m)
        self.d = ImageDraw.Draw(self.im)
        for a0, a1 in xs:
            self.d.line((a0, y0, a1, H), fill=self.c(seam), width=4)
        for k, y in enumerate((GROUND + 30, GROUND + 130, GROUND + 290, GROUND + 520)):   # Stöße der Dielen, versetzt
            for i, ((a0, a1), (b0, b1)) in enumerate(zip(xs, xs[1:])):
                if (i + k) % 3 == 0:
                    f = (y - y0) / (H - y0)
                    self.d.line((a0 + (a1 - a0) * f, y, b0 + (b1 - b0) * f, y), fill=self.c(seam), width=4)
        self.d.line((0, y0, W, y0), fill=INK, width=5)

    def rug(self, box, col):
        """Teppich als flaches Oval mit Rand."""
        x0, y0, x1, y1 = box
        self.d.ellipse((x0 - 5, y0 - 4, x1 + 5, y1 + 5), fill=self.c(_mix(col, 0.5, (30, 20, 30))))
        self.d.ellipse(box, fill=self.c(col))
        self.d.ellipse((x0 + (x1 - x0) * 0.07, y0 + (y1 - y0) * 0.12, x1 - (x1 - x0) * 0.07, y1 - (y1 - y0) * 0.12), outline=self.c(_mix(col, 0.25, (255, 255, 255))), width=6)

    def books(self, x0, y, x1, h=74, seed=1):
        """Wandbrett mit Büchern (y = Oberkante des Bretts)."""
        rnd = random.Random(seed)
        cols = ((206, 84, 76), (76, 128, 196), (232, 190, 84), (92, 160, 112), (150, 104, 170), (236, 232, 222), (224, 132, 70))
        x = x0 + 14
        while x < x1 - 40:
            w, hh = rnd.randint(18, 34), rnd.randint(int(h * 0.7), h)
            if rnd.random() < 0.14:                                           # Lücke mit kleiner Vase
                self.oval((x + 4, y - 40, x + 36, y - 2), (120, 190, 180), o=4)
                x += 48
                continue
            self.rect((x, y - hh, x + w, y), cols[rnd.randint(0, 6)], r=3, o=4)
            x += w + 2
        self.rect((x0, y, x1, y + 20), (150, 100, 64), r=6, o=5)
        self.d.rectangle((x0 + 8, y + 22, x1 - 8, y + 30), fill=self.c((0, 0, 0)) if False else self.c(_mix((150, 100, 64), 0.6, (20, 10, 20))))

    def floor_lamp(self, x, top=600):
        self.rect((x - 8, top + 70, x + 8, GROUND - 46), (86, 88, 98), o=5)
        self.oval((x - 60, GROUND - 62, x + 60, GROUND - 36), (86, 88, 98), o=5)
        self.poly([(x - 84, top + 96), (x + 84, top + 96), (x + 54, top), (x - 54, top)], (255, 232, 150), glow=True)
        if self.night and not self.dark:
            self.lamp_glow(x, top + 80, 360)

    def plant(self, x, y=GROUND - 20, s=1.0, pot=(220, 130, 80)):
        """Zimmerpflanze im Topf (y = Unterkante des Topfs)."""
        self.rect((x - 12 * s, y - 150 * s, x + 12 * s, y - 60 * s), (120, 84, 54), o=5)
        self.blobs([(x + dx * s, y - 150 * s + dy * s, r * s) for dx, dy, r in ((-58, -30, 50), (0, -94, 58), (58, -30, 50), (-26, 14, 44), (32, 20, 42))], (80, 170, 96), o=6)
        self.poly([(x - 70 * s, y - 84 * s), (x + 70 * s, y - 84 * s), (x + 54 * s, y), (x - 54 * s, y)], pot)
        self.rect((x - 78 * s, y - 96 * s, x + 78 * s, y - 70 * s), _mix(pot, 0.14, (255, 255, 255)), r=6, o=5)

    def lamp_glow(self, cx, cy, r=420):
        if not self.night or self.dark:
            return
        g = Image.new("L", (W, H), 0)
        ImageDraw.Draw(g).ellipse((cx - r, cy - r, cx + r, cy + r), fill=74)
        g = g.filter(ImageFilter.GaussianBlur(120))
        light = Image.composite(Image.new("RGB", (W, H), (255, 214, 130)), Image.new("RGB", (W, H), (0, 0, 0)), g)
        self.im = ImageChops.screen(self.im, light)        # Licht hellt auf, ohne die Farben zu vernebeln
        self.d = ImageDraw.Draw(self.im)

    def vignette(self):
        """Abschluss für jeden Hintergrund: Licht und Schatten, Dunst, leichte Weichzeichnung (die Figuren davor bleiben
        gestochen scharf und heben sich ab), feine Körnung und dunkle Ecken."""
        night = self.night
        if self.indoor:
            self.fade((0, 0, W, 420), (20, 16, 44), 70 if night else 60, 0)                       # Schatten unter der Decke
            self.fade((0, GROUND - 150, W, GROUND - 78), (30, 20, 40), 0, 46)                     # Wand wird zum Boden hin dunkler
            self.fade((0, GROUND - 40, W, GROUND + 26), (24, 14, 20), 70, 0)                      # Schatten der Fußleiste auf dem Boden
            if not self.dark:
                for x0, y0, x1, y1 in self.windows:                                               # Lichtbahn vom Fenster auf den Boden
                    w = x1 - x0
                    sh = 260 if (x0 + x1) / 2 < W / 2 else -260
                    col, al = ((150, 170, 255), 34) if night else ((255, 246, 214), 58)
                    self.veil([(x0, y1), (x1, y1), (x1 + sh + w * 0.5, GROUND + 300), (x0 + sh - w * 0.2, GROUND + 300)], col, al, 34, kind="poly")
                    self.veil([(x0 + sh * 0.6, GROUND - 30), (x1 + sh * 0.6 + w * 0.2, GROUND - 30), (x1 + sh * 1.25 + w * 0.7, GROUND + 420), (x0 + sh * 1.25 - w * 0.3, GROUND + 420)],
                              col, al, 44, kind="poly")
        if self.outdoor:
            self.fade((0, GROUND + 60, W, H), (16, 20, 44), 0, 84)                                # Vordergrund wird nach unten dunkler
            if self.sun and not night:
                self.veil((self.sun[0] - 520, self.sun[1] - 520, self.sun[0] + 520, self.sun[1] + 520), (255, 240, 200), 44, 150)
        soft = self.im.filter(ImageFilter.GaussianBlur(1.6))
        self.im = Image.blend(self.im, soft, 0.6)
        self.im = self.im.point(lambda v: int(v * 0.93 + 13))                                     # Schwarz leicht anheben: Umrisse der Kulisse treten zurück
        try:
            noise = Image.effect_noise((W, H), 9)
            self.im = ImageChops.soft_light(self.im, Image.merge("RGB", (noise, noise, noise)))
        except Exception:  # noqa: BLE001 – Körnung ist nur Zierde
            pass
        v = Image.new("L", (W, H), 0)
        ImageDraw.Draw(v).ellipse((-300, -160, W + 300, H + 160), fill=255)
        v = v.filter(ImageFilter.GaussianBlur(240)).point(lambda x: 255 - int((255 - x) * (0.46 if night else 0.36)))
        self.im = Image.composite(self.im, Image.new("RGB", (W, H), (10, 8, 26)), v)
        self.d = ImageDraw.Draw(self.im)
        return self.im


# ------------------------------------------------------------------ Orte

def bedroom(night):
    p = P(night)
    p.room((190, 208, 236), (196, 140, 92))
    p.window((600, 420, 960, 800), curtain=(240, 196, 110))
    p.rect((120, 440, 360, 670), (246, 214, 120), r=6)                         # Poster
    p.oval((190, 490, 290, 590), (240, 110, 90), o=5)
    p.d.arc((150, 560, 330, 700), 200, 340, fill=p.c((230, 150, 70)), width=10)
    p.books(90, 800, 430, seed=9)                                              # Wandbrett
    p.rug((420, GROUND + 10, 1000, GROUND + 180), (226, 170, 120))
    p.rect((40, 1010, 520, 1250), (150, 96, 60), r=14)                         # Bett
    p.rect((30, 880, 110, 1250), (130, 80, 48), r=14)
    p.rect((70, 1040, 520, 1190), (96, 132, 220), r=30)
    p.d.rounded_rectangle((250, 1052, 508, 1100), 20, fill=p.c((120, 156, 236)))             # Lichtkante der Decke
    p.rect((240, 1040, 300, 1190), (236, 240, 250), r=10, o=5)                 # umgeschlagene Decke
    p.rect((90, 980, 250, 1070), (250, 250, 246), r=30)
    p.rect((820, 1050, 1020, 1250), (150, 96, 60), r=10)                       # Nachttisch
    p.rect((850, 1080, 990, 1130), (176, 118, 76), r=6, o=5)
    p.rect((850, 1150, 990, 1200), (176, 118, 76), r=6, o=5)
    p.oval((910, 1096, 930, 1116), (236, 200, 110), o=3)
    p.oval((910, 1166, 930, 1186), (236, 200, 110), o=3)
    p.rect((900, 950, 940, 1050), (90, 90, 96), o=5)
    p.poly([(850, 950), (990, 950), (960, 860), (880, 860)], (255, 226, 130), glow=True)
    p.lamp_glow(920, 920)
    return p.vignette()


def livingroom(night):
    p = P(night)
    p.room((248, 226, 170), (206, 150, 96))
    p.window((120, 400, 460, 760), curtain=(120, 160, 200))
    p.rect((640, 430, 940, 620), (250, 250, 246), r=6)                         # Bild
    p.d.rectangle((660, 450, 920, 600), fill=p.c((190, 226, 250)))
    p.poly([(662, 600), (752, 490), (812, 566), (862, 524), (918, 600)], (110, 180, 120), o=5)
    p.oval((850, 462, 890, 502), (255, 220, 110), o=0)
    p.books(610, 760, 990, seed=4)                                             # Bücherbrett
    p.floor_lamp(1010, 640)
    p.rug((170, GROUND + 6, 900, GROUND + 190), (120, 150, 190))
    p.d.ellipse((500, 1236, 1080, 1280), fill=p.c((150, 100, 66)))             # Schatten unter dem Sofa
    p.rect((540, 1030, 1040, 1250), (214, 84, 76), r=40)                       # Sofa
    p.d.rounded_rectangle((552, 1042, 1028, 1090), 30, fill=p.c((228, 104, 94)))
    p.rect((520, 1090, 600, 1250), (190, 66, 60), r=30)
    p.rect((980, 1090, 1060, 1250), (190, 66, 60), r=30)
    p.rect((620, 1060, 800, 1170), (240, 120, 110), r=26, o=5)
    p.rect((810, 1060, 990, 1170), (240, 120, 110), r=26, o=5)
    p.rect((596, 1170, 984, 1236), (224, 96, 88), r=20, o=5)                   # Sitzfläche
    p.poly([(650, 1150), (720, 1090), (776, 1150), (716, 1196)], (250, 214, 110), o=5)      # Kissen
    p.rect((560, 1236, 584, 1262), (110, 70, 46), o=4)
    p.rect((996, 1236, 1020, 1262), (110, 70, 46), o=4)
    p.plant(120, 1250)
    return p.vignette()


def street(night):
    p = P(night)
    p.sky()
    rnd = random.Random(3)
    x = -40
    cols = ((236, 150, 110), (150, 180, 230), (240, 210, 130), (170, 210, 170), (220, 160, 200))
    while x < W:
        w, h = rnd.randint(200, 300), rnd.randint(380, 760)
        col = cols[rnd.randint(0, 4)]
        p.rect((x, GROUND - 60 - h, x + w, GROUND - 60), col)
        for wy in range(GROUND - 60 - h + 50, GROUND - 200, 120):
            for wx in range(x + 34, x + w - 60, 84):
                lit = night and not p.dark and rnd.random() < 0.55
                p.rect((wx, wy, wx + 50, wy + 66), (255, 226, 120) if lit else (120, 170, 220), r=4, o=5, glow=lit)
        p.rect((x + w // 2 - 36, GROUND - 180, x + w // 2 + 36, GROUND - 60), (110, 70, 44), r=6)
        x += w
    p.rect((-10, GROUND - 60, W + 10, GROUND + 30), (200, 200, 204))            # Gehweg
    p.d.rectangle((0, GROUND + 30, W, H), fill=p.c((84, 86, 96)))
    for x in range(40, W, 240):
        p.rect((x, GROUND + 250, x + 130, GROUND + 276), (250, 240, 200), r=4, o=0)
    p.rect((880, 600, 900, GROUND - 60), (60, 60, 66), o=5)                     # Laterne
    p.rect((820, 570, 960, 610), (60, 60, 66), r=12, o=5)
    p.oval((850, 606, 930, 660), (255, 236, 150), o=5, glow=True)
    p.lamp_glow(890, 640, 380)
    return p.vignette()


def basement(night):
    p = P(True)
    p.night = False
    wall, floor = (112, 104, 100), (86, 80, 84)
    p.d.rectangle((0, 0, W, GROUND - 40), fill=wall)
    for y in range(40, GROUND - 60, 90):                                        # Ziegel
        off = 0 if (y // 90) % 2 else 90
        for x in range(-90 + off, W, 180):
            p.d.rectangle((x, y, x + 172, y + 82), outline=_mix(wall, 0.3, (30, 26, 26)), width=4)
    p.d.rectangle((0, GROUND - 40, W, H), fill=floor)
    p.d.line((0, GROUND - 40, W, GROUND - 40), fill=INK, width=6)
    p.rect((60, 620, 480, 650), (150, 110, 70))                                 # Regal
    p.rect((60, 900, 480, 930), (150, 110, 70))
    p.rect((60, 600, 90, GROUND - 40), (130, 92, 56))
    p.rect((450, 600, 480, GROUND - 40), (130, 92, 56))
    for i, col in enumerate(((90, 150, 230), (90, 150, 230), (90, 150, 230))):
        p.rect((110 + i * 110, 500, 190 + i * 110, 620), col, r=12)
        p.rect((130 + i * 110, 470, 170 + i * 110, 505), (60, 110, 190), r=4, o=5)
    for i, col in enumerate(((226, 80, 70), (240, 200, 70), (110, 190, 110), (226, 80, 70))):
        p.rect((100 + i * 90, 810, 170 + i * 90, 900), col, r=8, o=5)
    p.rect((120, 1010, 300, 1150), (250, 250, 246), r=12)                       # Erste-Hilfe-Kasten
    p.rect((196, 1040, 224, 1120), (226, 58, 52), o=0)
    p.rect((170, 1066, 250, 1094), (226, 58, 52), o=0)
    p.rect((700, 700, 1000, GROUND - 40), (120, 124, 132), r=10)                # Stahltür
    p.rect((730, 740, 970, 980), (140, 144, 152), r=6, o=5)
    p.oval((930, 1000, 970, 1040), (240, 200, 70), o=5)
    p.line((540, 0, 540, 300), INK, 5)                                          # Glühbirne
    p.oval((510, 290, 570, 360), (255, 240, 170), o=5)
    p.night = True
    p.lamp_glow(540, 420, 560)
    return p.vignette()


def park(night):
    p = P(night)
    p.sky()
    p.d.ellipse((-300, GROUND - 330, 620, GROUND + 200), fill=p.c((126, 200, 110)))
    p.d.ellipse((400, GROUND - 260, 1400, GROUND + 260), fill=p.c((110, 186, 100)))
    p.d.rectangle((0, GROUND - 60, W, H), fill=p.c((96, 176, 90)))
    p.d.line((0, GROUND - 60, W, GROUND - 60), fill=INK, width=5)
    for tx, s in ((170, 1.0), (900, 1.25)):
        p.rect((tx - 26 * s, GROUND - 60 - 330 * s, tx + 26 * s, GROUND - 60), (130, 86, 54))
        for dx, dy, r in ((0, -400, 150), (-110, -330, 110), (110, -330, 110), (0, -290, 120)):
            p.oval((tx + dx * s - r * s, GROUND - 60 + dy * s - r * s, tx + dx * s + r * s, GROUND - 60 + dy * s + r * s), (70, 160, 84))
    p.rect((440, GROUND - 190, 740, GROUND - 160), (176, 118, 76), r=6)        # Bank
    p.rect((440, GROUND - 260, 740, GROUND - 230), (176, 118, 76), r=6)
    p.rect((460, GROUND - 260, 484, GROUND - 60), (90, 90, 96), o=5)
    p.rect((696, GROUND - 260, 720, GROUND - 60), (90, 90, 96), o=5)
    rnd = random.Random(5)
    for _ in range(26):
        x, y = rnd.randint(0, W), rnd.randint(GROUND, H - 300)
        p.line((x, y, x - 8, y - 26), p.c((60, 130, 66)), 5)
        p.line((x, y, x + 10, y - 22), p.c((60, 130, 66)), 5)
    return p.vignette()


def space(night):
    p = P(True)
    for y in range(0, H, 8):
        f = y / H
        p.d.rectangle((0, y, W, y + 8), fill=(int(10 + 20 * f), int(10 + 12 * f), int(34 + 40 * f)))
    rnd = random.Random(11)
    for _ in range(170):
        x, y, r = rnd.randint(0, W), rnd.randint(0, H), rnd.choice((2, 2, 3, 3, 5))
        p.d.ellipse((x - r, y - r, x + r, y + r), fill=rnd.choice(((255, 255, 240), (200, 220, 255), (255, 220, 200))))
    p.oval((640, 240, 980, 580), (236, 150, 90), glow=True)                    # Planet mit Ring
    p.d.arc((560, 350, 1060, 480), 10, 170, fill=(250, 220, 160), width=14)
    p.oval((110, 520, 250, 660), (150, 190, 240), glow=True)
    p.d.ellipse((-200, GROUND - 60, W + 200, H + 500), fill=(120, 124, 140), outline=INK, width=O)   # Mondboden
    for cx, cy, r in ((220, GROUND + 180, 70), (700, GROUND + 120, 50), (900, GROUND + 330, 90), (430, GROUND + 420, 60)):
        p.d.ellipse((cx - r, cy - r * 0.4, cx + r, cy + r * 0.4), fill=(96, 100, 116), outline=INK, width=5)
    return p.vignette()


def lab(night):
    p = P(night)
    p.room((206, 232, 232), (150, 160, 170), stripe=False)
    for x in range(0, W, 180):
        p.d.line((x, 0, x, GROUND - 78), fill=p.c((186, 214, 214)), width=4)
    p.rect((90, 420, 520, 720), (40, 60, 70), r=10)                             # Tafel/Monitor
    pts = [(120 + i * 38, 640 - int(70 * abs(math.sin(i * 0.9))) - i * 6) for i in range(10)]
    p.line(pts, (110, 230, 150), 7)
    p.rect((560, 1000, 1040, 1040), (236, 236, 240), r=6)                       # Labortisch
    p.rect((590, 1040, 620, 1250), (120, 124, 132), o=5)
    p.rect((980, 1040, 1010, 1250), (120, 124, 132), o=5)
    for i, col in enumerate(((110, 210, 140), (240, 120, 150), (120, 170, 250))):
        x = 640 + i * 130
        p.poly([(x + 20, 870), (x + 60, 870), (x + 60, 920), (x + 100, 1000), (x - 20, 1000), (x + 20, 920)], (236, 244, 250), o=5)
        p.poly([(x + 8, 950), (x + 72, 950), (x + 100, 1000), (x - 20, 1000)], col, o=0, glow=True)
        p.d.polygon([(x + 20, 870), (x + 60, 870), (x + 60, 920), (x + 100, 1000), (x - 20, 1000), (x + 20, 920)], outline=INK, width=5)
    p.window((640, 400, 980, 700))
    p.books(90, 880, 520, 66, seed=21)                                          # Regal mit Ordnern und Gläsern
    p.rect((90, 1010, 420, 1250), (226, 232, 238), r=10)                        # Laborschrank
    p.line((255, 1010, 255, 1250))
    p.oval((222, 1110, 244, 1132), (150, 156, 166), o=4)
    p.oval((266, 1110, 288, 1132), (150, 156, 166), o=4)
    p.rect((120, 930, 200, 1010), (60, 64, 76), r=8)                            # Mikroskop-Kasten
    p.rect((150, 890, 176, 936), (90, 96, 110), r=6, o=5)
    p.lamp_glow(540, 500, 600)
    return p.vignette()


def classroom(night):
    p = P(night)
    p.room((250, 236, 196), (190, 150, 110))
    p.rect((120, 420, 960, 800), (56, 96, 76), r=10, o=14)                      # Tafel
    p.d.rounded_rectangle((120, 420, 960, 800), 10, outline=(150, 96, 60), width=14)
    p.line((200, 520, 420, 520), (240, 240, 230), 6)
    p.line((200, 580, 560, 580), (240, 240, 230), 6)
    p.d.ellipse((680, 500, 860, 680), outline=(240, 240, 230), width=6)
    p.rect((120, 800, 960, 830), (150, 96, 60), r=4, o=5)
    p.rect((180, 806, 250, 822), (250, 250, 246), r=4, o=3)                     # Kreide und Schwamm
    p.rect((300, 800, 380, 824), (236, 200, 90), r=6, o=4)
    p.oval((930, 250, 1050, 370), (250, 250, 246), o=7)                         # Wanduhr
    p.line((990, 310, 990, 272), INK, 6)
    p.line((990, 310, 1020, 322), INK, 6)
    p.rect((30, 200, 330, 380), (190, 226, 250), r=6)                           # Weltkarte als Poster
    for bx, by, bw, bh in ((60, 240, 70, 60), (150, 230, 60, 90), (230, 250, 70, 50)):
        p.oval((bx, by, bx + bw, by + bh), (120, 190, 120), o=3)
    p.plant(1010, 1250, 0.8)
    for x in (80, 760):
        p.rect((x, 1090, x + 250, 1130), (200, 150, 96), r=6)
        p.rect((x + 20, 1130, x + 44, 1250), (110, 110, 118), o=5)
        p.rect((x + 206, 1130, x + 230, 1250), (110, 110, 118), o=5)
    return p.vignette()


def kitchen(night):
    p = P(night)
    p.room((214, 236, 222), (226, 214, 196), stripe=False)
    for y in range(0, GROUND - 80, 90):                                         # Fliesen
        p.d.line((0, y, W, y), fill=p.c((196, 222, 206)), width=3)
    for x in range(0, W, 90):
        p.d.line((x, 0, x, GROUND - 80), fill=p.c((196, 222, 206)), width=3)
    p.window((90, 430, 400, 760), curtain=(250, 214, 120))
    p.rect((520, 700, 1010, 980), (236, 244, 240), o=0)                         # Fliesenspiegel
    for yy in range(700, 980, 56):
        p.d.line((520, yy, 1010, yy), fill=p.c((200, 220, 214)), width=3)
    for xx in range(520, 1010, 70):
        p.d.line((xx, 700, xx, 980), fill=p.c((200, 220, 214)), width=3)
    for hx, hc in ((560, (120, 124, 132)), (610, (200, 80, 70)), (660, (120, 124, 132))):   # Kellen an der Leiste
        p.line((hx, 720, hx, 800), INK, 8)
        p.oval((hx - 16, 790, hx + 16, 830), hc, o=5)
    p.rect((540, 712, 700, 724), (150, 156, 166), r=4, o=4)
    p.rect((880, 880, 980, 980), (250, 250, 246), r=10)                         # Wasserkocher
    p.rect((900, 860, 960, 884), (90, 96, 110), r=6, o=5)
    p.rect((520, 420, 1010, 640), (236, 150, 90), r=10)                         # Hängeschränke
    p.line((765, 420, 765, 640))
    p.oval((720, 520, 746, 546), (250, 250, 246), o=5)
    p.oval((784, 520, 810, 546), (250, 250, 246), o=5)
    p.rect((470, 980, 1080, 1020), (250, 250, 246), r=6)                        # Arbeitsplatte
    p.rect((490, 1020, 1070, 1250), (236, 150, 90), r=8)
    p.rect((780, 1050, 1040, 1230), (60, 60, 66), r=10)                         # Ofen
    p.rect((810, 1090, 1010, 1200), (255, 190, 90) if night else (110, 120, 130), r=6, o=5, glow=night)
    p.rect((560, 900, 700, 980), (200, 60, 60), r=14)                           # Topf
    p.rect((540, 890, 720, 910), (170, 44, 44), r=6, o=5)
    p.rect((30, 820, 300, 1250), (236, 240, 244), r=16)                         # Kühlschrank
    p.line((30, 980, 300, 980))
    p.rect((250, 860, 270, 950), (150, 156, 166), r=6, o=4)
    p.rect((250, 1010, 270, 1130), (150, 156, 166), r=6, o=4)
    p.lamp_glow(540, 500, 560)
    return p.vignette()


def office(night):
    p = P(night)
    p.room((206, 216, 232), (120, 130, 150), stripe=False)
    for i in range(3):                                                          # Fensterfront
        p.window((70 + i * 330, 380, 350 + i * 330, 800))
    p.rect((120, 1020, 960, 1060), (176, 118, 76), r=6)                         # Schreibtisch
    p.rect((150, 1060, 180, 1250), (110, 110, 118), o=5)
    p.rect((900, 1060, 930, 1250), (110, 110, 118), o=5)
    p.rect((620, 800, 900, 980), (40, 44, 54), r=10)                            # Monitor
    p.rect((640, 820, 880, 960), (120, 200, 255), r=4, o=0, glow=True)
    p.rect((740, 980, 780, 1020), (60, 60, 66), o=5)
    p.rect((200, 950, 330, 1020), (250, 250, 246), r=4, o=5)                    # Papierstapel
    p.rect((210, 930, 340, 960), (250, 250, 246), r=4, o=5)
    p.rect((420, 960, 480, 1020), (220, 80, 70), r=8, o=5)                      # Tasse
    p.rect((560, 1060, 720, 1250), (150, 100, 66), r=6)                         # Rollcontainer
    for yy in (1090, 1150, 1210):
        p.rect((580, yy, 700, yy + 36), (176, 118, 76), r=4, o=4)
    p.oval((300, 1130, 420, 1250), (70, 74, 86), o=6)                           # Bürostuhl (Rücken)
    p.rect((330, 1040, 390, 1150), (70, 74, 86), r=18)
    p.plant(1010, 1250, 0.9)
    p.lamp_glow(760, 880, 420)
    return p.vignette()


def beach(night):
    p = P(night)
    p.sky(GROUND - 200)
    p.d.rectangle((0, GROUND - 260, W, GROUND - 40), fill=p.c((60, 150, 220)))
    for y in range(GROUND - 230, GROUND - 60, 46):
        for x in range(-60 + (y % 92), W, 160):
            p.d.arc((x, y, x + 90, y + 30), 180, 360, fill=p.c((200, 232, 250)), width=5)
    p.d.line((0, GROUND - 260, W, GROUND - 260), fill=INK, width=5)
    p.d.rectangle((0, GROUND - 60, W, H), fill=p.c((244, 220, 160)))
    p.d.line((0, GROUND - 60, W, GROUND - 60), fill=INK, width=5)
    p.rect((846, GROUND - 520, 874, GROUND - 60), (150, 100, 60))               # Palme
    for a in (-150, -110, -60, -20, 30):
        ex, ey = 860 + math.cos(math.radians(a)) * 210, GROUND - 520 + math.sin(math.radians(a)) * 120 + 60
        p.poly([(860, GROUND - 520), ((860 + ex) / 2, min(GROUND - 580, ey - 60)), (ex, ey), ((860 + ex) / 2, ey - 10)], (70, 170, 90), o=5)
    p.poly([(120, GROUND - 60), (240, GROUND - 330), (360, GROUND - 60)], (240, 90, 80))   # Sonnenschirm
    p.poly([(190, GROUND - 60), (240, GROUND - 330), (290, GROUND - 60)], (250, 250, 246), o=0)
    p.d.polygon([(120, GROUND - 60), (240, GROUND - 330), (360, GROUND - 60)], outline=INK, width=O)
    rnd = random.Random(9)
    for _ in range(30):
        x, y = rnd.randint(0, W), rnd.randint(GROUND, H - 200)
        p.d.ellipse((x, y, x + 8, y + 5), fill=p.c((220, 190, 130)))
    return p.vignette()


def desert(night):
    p = P(night)
    p.sky()
    p.d.ellipse((-300, GROUND - 300, 700, GROUND + 300), fill=p.c((236, 190, 110)))
    p.d.ellipse((500, GROUND - 220, 1500, GROUND + 300), fill=p.c((226, 176, 96)))
    p.d.rectangle((0, GROUND - 60, W, H), fill=p.c((240, 200, 124)))
    p.d.line((0, GROUND - 60, W, GROUND - 60), fill=INK, width=5)
    for cx, s in ((190, 1.0), (900, 0.8)):                                       # Kakteen
        p.rect((cx - 34 * s, GROUND - 60 - 330 * s, cx + 34 * s, GROUND - 60), (80, 160, 90), r=int(34 * s))
        p.rect((cx - 120 * s, GROUND - 60 - 230 * s, cx - 70 * s, GROUND - 60 - 110 * s), (80, 160, 90), r=int(24 * s))
        p.rect((cx - 120 * s, GROUND - 60 - 150 * s, cx, GROUND - 60 - 110 * s), (80, 160, 90), r=int(18 * s))
        p.rect((cx + 70 * s, GROUND - 60 - 280 * s, cx + 120 * s, GROUND - 60 - 160 * s), (80, 160, 90), r=int(24 * s))
        p.rect((cx, GROUND - 60 - 200 * s, cx + 120 * s, GROUND - 60 - 160 * s), (80, 160, 90), r=int(18 * s))
    p.poly([(520, GROUND - 60), (640, GROUND - 330), (760, GROUND - 60)], (214, 160, 84))   # Pyramide
    p.poly([(640, GROUND - 330), (760, GROUND - 60), (700, GROUND - 60)], (190, 136, 66), o=0)
    return p.vignette()


def snow(night):
    p = P(night)
    p.sky()
    for cx, hgt, w in ((200, 520, 420), (620, 660, 520), (980, 460, 400)):       # Berge
        p.poly([(cx - w // 2, GROUND - 60), (cx, GROUND - 60 - hgt), (cx + w // 2, GROUND - 60)], (150, 170, 200))
        p.poly([(cx - w // 8, GROUND - 60 - hgt * 3 // 4), (cx, GROUND - 60 - hgt), (cx + w // 8, GROUND - 60 - hgt * 3 // 4),
                (cx + w // 20, GROUND - 60 - hgt * 0.68), (cx - w // 20, GROUND - 60 - hgt * 0.72)], (250, 252, 255), o=5)
    p.d.rectangle((0, GROUND - 60, W, H), fill=p.c((240, 246, 252)))
    p.d.line((0, GROUND - 60, W, GROUND - 60), fill=INK, width=5)
    for tx, s in ((120, 1.0), (940, 1.2)):                                       # Tannen
        p.rect((tx - 14 * s, GROUND - 120 * s, tx + 14 * s, GROUND - 60), (120, 80, 50), o=5)
        for k in range(3):
            y = GROUND - 100 * s - k * 90 * s
            p.poly([(tx - (120 - k * 26) * s, y), (tx, y - 150 * s), (tx + (120 - k * 26) * s, y)], (50, 130, 90))
    p.oval((480, GROUND - 190, 620, GROUND - 50), (250, 252, 255))               # Schneemann
    p.oval((502, GROUND - 290, 598, GROUND - 180), (250, 252, 255))
    p.poly([(550, GROUND - 240), (600, GROUND - 228), (550, GROUND - 222)], (240, 130, 50), o=4)
    return p.vignette()


def forest(night):
    p = P(night)
    p.sky()
    p.d.rectangle((0, GROUND - 420, W, GROUND - 60), fill=p.c((60, 120, 80)))
    rnd = random.Random(21)
    for layer, col, base in ((0, (50, 110, 74), GROUND - 160), (1, (62, 140, 84), GROUND - 60)):
        for tx in range(-60, W + 100, 150 if layer else 120):
            h = rnd.randint(480, 760) if layer else rnd.randint(380, 560)
            p.rect((tx + 44, base - h * 0.4, tx + 76, base), (110, 74, 46), o=5)
            for k in range(3):
                y = base - h * 0.28 - k * h * 0.2
                p.poly([(tx + 60 - (130 - k * 26), y), (tx + 60, y - h * 0.3), (tx + 60 + (130 - k * 26), y)], col)
    p.d.rectangle((0, GROUND - 60, W, H), fill=p.c((84, 150, 80)))
    p.d.line((0, GROUND - 60, W, GROUND - 60), fill=INK, width=5)
    for mx in (300, 760):                                                        # Pilze
        p.rect((mx - 10, GROUND - 110, mx + 10, GROUND - 60), (250, 244, 230), o=4)
        p.d.chord((mx - 40, GROUND - 150, mx + 40, GROUND - 80), 180, 360, fill=p.c((220, 60, 50)), outline=INK, width=4)
    return p.vignette()


def underwater(night):
    p = P(False)
    for y in range(0, H, 8):
        f = y / H
        p.d.rectangle((0, y, W, y + 8), fill=(int(40 - 30 * f), int(150 - 90 * f), int(220 - 90 * f)))
    for x0 in (120, 420, 760):                                                   # Lichtstrahlen
        ray = Image.new("L", (W, H), 0)
        ImageDraw.Draw(ray).polygon([(x0, 0), (x0 + 120, 0), (x0 + 420, GROUND), (x0 + 120, GROUND)], fill=34)
        p.im.paste(Image.new("RGB", (W, H), (220, 250, 255)), (0, 0), ray.filter(ImageFilter.GaussianBlur(20)))
    p.d = ImageDraw.Draw(p.im)
    p.d.ellipse((-200, GROUND - 90, W + 200, H + 400), fill=(226, 204, 150), outline=INK, width=O)
    for sx, col in ((140, (240, 110, 130)), (930, (250, 160, 80))):              # Korallen
        for dx, hgt in ((-50, 180), (0, 260), (50, 150)):
            p.rect((sx + dx - 18, GROUND - 60 - hgt, sx + dx + 18, GROUND - 40), col, r=18)
    for sx in (360, 700):                                                        # Seegras
        for k in range(3):
            pts = [(sx + k * 30 + math.sin(i * 0.9) * 22, GROUND - 60 - i * 50) for i in range(7)]
            p.line(pts, (40, 140, 100), 14)
    rnd = random.Random(4)
    for _ in range(16):
        x, y, r = rnd.randint(0, W), rnd.randint(200, GROUND - 100), rnd.randint(8, 22)
        p.d.ellipse((x - r, y - r, x + r, y + r), outline=(220, 245, 255), width=4)
    return p.vignette()


def mountain(night):
    p = P(night)
    p.sky()
    p.poly([(-100, GROUND - 60), (300, GROUND - 760), (700, GROUND - 60)], (130, 140, 160))
    p.poly([(400, GROUND - 60), (800, GROUND - 620), (1200, GROUND - 60)], (112, 122, 144))
    p.poly([(220, GROUND - 620), (300, GROUND - 760), (380, GROUND - 620), (330, GROUND - 580), (280, GROUND - 610)], (250, 252, 255), o=5)
    p.poly([(730, GROUND - 520), (800, GROUND - 620), (870, GROUND - 520), (810, GROUND - 490)], (250, 252, 255), o=5)
    p.d.rectangle((0, GROUND - 60, W, H), fill=p.c((150, 170, 110)))
    p.d.line((0, GROUND - 60, W, GROUND - 60), fill=INK, width=5)
    for rx, rw in ((120, 160), (860, 220), (520, 120)):
        p.d.chord((rx, GROUND - 60 - rw * 0.5, rx + rw, GROUND - 60 + rw * 0.5), 180, 360, fill=p.c((150, 150, 158)), outline=INK, width=5)
    return p.vignette()


def hospital(night):
    p = P(night)
    p.room((226, 240, 244), (200, 214, 220), stripe=False)
    p.window((640, 420, 980, 780))
    p.rect((90, 450, 300, 660), (250, 250, 246), r=12)                           # Kreuz-Schild
    p.rect((170, 480, 220, 630), (226, 58, 52), o=0)
    p.rect((120, 530, 270, 580), (226, 58, 52), o=0)
    p.rect((60, 1050, 560, 1120), (250, 250, 246), r=14)                         # Bett
    p.rect((60, 1000, 220, 1070), (200, 226, 250), r=20)
    p.rect((80, 1120, 104, 1250), (150, 156, 166), o=5)
    p.rect((516, 1120, 540, 1250), (150, 156, 166), o=5)
    p.rect((40, 940, 70, 1250), (150, 156, 166), o=5)
    p.rect((800, 900, 990, 1060), (40, 44, 54), r=10)                            # Monitor mit Herzlinie
    p.line([(820, 990), (860, 990), (880, 940), (900, 1030), (920, 990), (970, 990)], (110, 230, 150), 6)
    p.rect((880, 1060, 910, 1250), (150, 156, 166), o=5)
    p.rect((300, 500, 560, 520), (150, 156, 166), r=6, o=4)                     # Vorhangschiene mit Vorhang
    p.rect((440, 520, 560, 1040), (170, 214, 220), r=18, o=6)
    for xx in (470, 500, 530):
        p.d.line((xx, 536, xx, 1024), fill=p.c((140, 190, 198)), width=6)
    p.rect((596, 880, 620, 1250), (150, 156, 166), o=5)                         # Infusionsständer
    p.rect((574, 860, 642, 950), (230, 244, 250), r=14, o=5)
    p.rect((60, 1110, 560, 1150), (190, 214, 236), r=10, o=5)                   # Bettdecke
    return p.vignette()


def cave(night):
    p = P(False)
    p.d.rectangle((0, 0, W, H), fill=(54, 46, 58))
    p.d.ellipse((-100, 200, W + 100, GROUND + 500), fill=(84, 72, 82))
    for x, hgt in ((80, 320), (260, 200), (520, 380), (760, 240), (960, 340)):   # Stalaktiten
        p.poly([(x - 60, 0), (x + 60, 0), (x, hgt)], (54, 46, 58), o=5)
    p.d.rectangle((0, GROUND - 40, W, H), fill=(70, 60, 66))
    p.d.line((0, GROUND - 40, W, GROUND - 40), fill=INK, width=6)
    for x, hgt in ((140, 150), (900, 210)):
        p.poly([(x - 50, GROUND - 40), (x + 50, GROUND - 40), (x, GROUND - 40 - hgt)], (96, 84, 92), o=5)
    for cx, cy, col in ((230, 760, (120, 220, 250)), (860, 640, (200, 140, 250)), (640, 900, (120, 250, 190))):  # Kristalle
        p.poly([(cx, cy - 60), (cx + 30, cy), (cx, cy + 60), (cx - 30, cy)], col, o=5, glow=True)
    p.night = True
    p.lamp_glow(540, 800, 520)
    return p.vignette()


# ------------------------------------------------------------------ Baukasten: Landschaft aus Einzelteilen
# Damit passt der Hintergrund zu jedem Thema: Himmel + Boden + beliebige Elemente dahinter.

GROUNDS = {"grass": (104, 180, 96), "sand": (240, 206, 132), "snow": (240, 246, 252), "road": (88, 90, 100),
           "rock": (140, 136, 140), "soil": (150, 104, 66), "dry": (206, 170, 110), "water": (60, 150, 220),
           "ice": (210, 234, 248), "lava": (90, 50, 44), "moon": (124, 128, 144)}
BASE = FAR               # Fußlinie der fernen Kulisse; davor liegt der Boden bis zu den Figuren


def _el_mountains(p, rnd):
    for cx, hgt, w, col in ((420, 430, 560, (176, 188, 214)), (860, 380, 520, (184, 196, 220))):          # ferne, blassere Kette
        p.poly([(cx - w // 2, BASE), (cx, BASE - hgt), (cx + w // 2, BASE)], col, o=4)
    for cx, hgt, w, col in ((180, 560, 520, (146, 158, 186)), (640, 720, 600, (124, 136, 166)), (1000, 500, 460, (146, 158, 186))):
        p.poly([(cx - w // 2, BASE), (cx, BASE - hgt), (cx + w // 2, BASE)], col)
        p.poly([(cx, BASE - hgt), (cx + w // 2, BASE), (cx + w * 0.08, BASE), (cx + w * 0.02, BASE - hgt * 0.5)], _mix(col, 0.18, (30, 30, 70)), o=0)   # Schattenseite
        p.poly([(cx - w // 9, BASE - hgt * 0.76), (cx, BASE - hgt), (cx + w // 9, BASE - hgt * 0.76),
                (cx + w // 24, BASE - hgt * 0.7), (cx - w // 24, BASE - hgt * 0.73)], (250, 252, 255), o=5)
        p.poly([(cx - w // 2, BASE), (cx, BASE - hgt), (cx + w // 2, BASE)], None, o=O) if False else None


def _el_hills(p, rnd):
    p.d.ellipse((200, BASE - 380, 1000, BASE + 300), fill=p.c((158, 212, 150)), outline=INK, width=4)           # ferner Hügel, blasser
    p.d.ellipse((-320, BASE - 300, 640, BASE + 260), fill=p.c((126, 196, 112)), outline=INK, width=5)
    p.d.ellipse((-260, BASE - 276, 520, BASE + 240), fill=p.c((138, 206, 122)))
    p.d.ellipse((380, BASE - 240, 1420, BASE + 300), fill=p.c((112, 184, 102)), outline=INK, width=5)
    p.d.ellipse((470, BASE - 216, 1300, BASE + 300), fill=p.c((124, 194, 112)))
    for bx, by, r in ((90, BASE - 150, 30), (150, BASE - 160, 38), (760, BASE - 170, 34), (820, BASE - 150, 26), (560, BASE - 60, 30)):   # Büsche auf den Kuppen
        p.blobs([(bx, by, r), (bx + r * 0.9, by + r * 0.3, r * 0.7), (bx - r * 0.9, by + r * 0.3, r * 0.7)], (84, 158, 92), o=4)


def _el_dunes(p, rnd):
    p.d.ellipse((-300, BASE - 260, 700, BASE + 300), fill=p.c((236, 190, 110)), outline=INK, width=5)
    p.d.ellipse((460, BASE - 200, 1500, BASE + 300), fill=p.c((226, 176, 96)), outline=INK, width=5)


def _el_forest(p, rnd):
    for layer, col, base, step in ((0, (46, 104, 70), BASE - 90, 110), (1, (58, 132, 80), BASE, 135)):
        for tx in range(-70, W + 100, step):
            h = rnd.randint(420, 640) if layer else rnd.randint(360, 520)
            p.rect((tx + 46, base - h * 0.36, tx + 74, base), (104, 70, 44), o=5)
            if (tx // step + layer) % 3 == 0:      # Laubbaum
                p.blobs([(tx + 60 + dx * h, base + dy * h, r * h) for dx, dy, r in ((0, -0.62, 0.2), (-0.13, -0.5, 0.16), (0.13, -0.5, 0.16), (0, -0.42, 0.17))], col, o=5)
            else:                                  # Tanne
                for k in range(3):
                    y = base - h * 0.26 - k * h * 0.2
                    p.poly([(tx + 60 - (128 - k * 26), y), (tx + 60, y - h * 0.3), (tx + 60 + (128 - k * 26), y)], col)
                    p.poly([(tx + 60, y - h * 0.3), (tx + 60 + (128 - k * 26), y), (tx + 60 + 10, y)], _mix(col, 0.18, (10, 30, 50)), o=0)


def _el_trees(p, rnd):
    for tx, sc in ((150, 1.0), (930, 1.2)):
        p.rect((tx - 24 * sc, BASE - 320 * sc, tx + 24 * sc, BASE), (130, 86, 54))
        p.d.rectangle((tx + 4 * sc, BASE - 314 * sc, tx + 18 * sc, BASE - 6), fill=p.c((104, 66, 44)))
        p.blobs([(tx + dx * sc, BASE + dy * sc, r * sc) for dx, dy, r in ((0, -400, 150), (-110, -330, 110), (110, -330, 110), (0, -290, 120))], (70, 160, 84))


def _el_deadtrees(p, rnd):
    for tx, sc in ((170, 1.0), (560, 0.8), (920, 1.15)):
        p.line((tx, BASE, tx, BASE - 330 * sc), INK, int(34 * sc))
        p.line((tx, BASE, tx, BASE - 330 * sc), p.c((110, 84, 64)), int(22 * sc))
        for dx, dy, y0 in ((-110, -90, 0.5), (120, -110, 0.65), (-70, -80, 0.85), (60, -70, 0.95)):
            y = BASE - 330 * sc * y0
            p.line((tx, y, tx + dx * sc, y + dy * sc), INK, int(20 * sc))
            p.line((tx, y, tx + dx * sc, y + dy * sc), p.c((110, 84, 64)), int(11 * sc))


def _el_city(p, rnd):
    x = -40
    cols = ((214, 150, 120), (150, 176, 214), (224, 200, 140), (170, 200, 172), (196, 160, 190))
    x2 = -90
    while x2 < W:                                                                # ganz hinten: blasse Silhouetten
        w, h = rnd.randint(150, 260), rnd.randint(520, 900)
        p.rect((x2, BASE - h, x2 + w, BASE), _mix(cols[rnd.randint(0, 4)], 0.62, (206, 222, 246)), o=0)
        x2 += w + rnd.randint(-10, 60)
    while x < W:
        w, h = rnd.randint(190, 290), rnd.randint(360, 740)
        col = _mix(cols[rnd.randint(0, 4)], 0.22, (206, 222, 246))
        p.rect((x, BASE - h, x + w, BASE), col, o=5)
        p.d.rectangle((x + w - 34, BASE - h + 5, x + w - 5, BASE), fill=p.c(_mix(col, 0.14, (30, 30, 70))))      # Schattenseite
        p.rect((x - 6, BASE - h - 12, x + w + 6, BASE - h + 8), _mix(col, 0.2, (40, 30, 50)), o=4)              # Dachkante
        for wy in range(BASE - h + 46, BASE - 150, 116):
            for wx in range(x + 32, x + w - 58, 82):
                lit = p.night and not p.dark and rnd.random() < 0.55
                p.rect((wx, wy, wx + 48, wy + 64), (255, 226, 120) if lit else (150, 188, 226), r=4, o=4, glow=lit)
                if not lit:
                    p.d.polygon([(wx + 8, wy + 6), (wx + 22, wy + 6), (wx + 10, wy + 58), (wx + 6, wy + 58)], fill=p.c((190, 216, 240)))
        x += w


def _el_village(p, rnd):
    for hx, w, h, col in ((90, 250, 190, (236, 214, 180)), (430, 220, 160, (220, 196, 170)), (760, 260, 200, (240, 222, 190))):
        p.rect((hx, BASE - h, hx + w, BASE), col)
        p.poly([(hx - 26, BASE - h), (hx + w / 2, BASE - h - 130), (hx + w + 26, BASE - h)], (190, 84, 70))
        p.rect((hx + w / 2 - 28, BASE - 96, hx + w / 2 + 28, BASE), (120, 80, 50), r=6, o=5)
        p.rect((hx + 30, BASE - h + 40, hx + 86, BASE - h + 96), (255, 226, 120) if p.night else (150, 200, 240), r=4, o=5, glow=p.night)


def _el_ruins(p, rnd):
    x = -20
    while x < W:
        w, h = rnd.randint(170, 260), rnd.randint(240, 600)
        top = [(x, BASE - h + rnd.randint(0, 120)), (x + w * 0.3, BASE - h + rnd.randint(40, 160)), (x + w * 0.55, BASE - h),
               (x + w * 0.8, BASE - h + rnd.randint(60, 200)), (x + w, BASE - h + rnd.randint(0, 100))]
        p.poly([(x, BASE)] + top + [(x + w, BASE)], (120, 116, 122))
        for wy in range(BASE - h + 210, BASE - 120, 120):
            for wx in range(int(x + 30), int(x + w - 50), 84):
                p.rect((wx, wy, wx + 44, wy + 60), (40, 40, 48), r=3, o=4)
        x += w + rnd.randint(10, 60)


def _el_factory(p, rnd):
    p.rect((120, BASE - 300, 760, BASE), (150, 150, 160))
    for i in range(4):
        p.poly([(120 + i * 160, BASE - 300), (120 + i * 160, BASE - 400), (280 + i * 160, BASE - 300)], (130, 130, 142))
    for cx in (820, 940):
        p.rect((cx - 36, BASE - 620, cx + 36, BASE), (170, 110, 96))
        p.rect((cx - 44, BASE - 640, cx + 44, BASE - 600), (140, 84, 74), r=6, o=5)
        for k in range(4):
            r = 46 + k * 22
            g = 150 - k * 14
            p.d.ellipse((cx + k * 44 - r, BASE - 700 - k * 100 - r, cx + k * 44 + r, BASE - 700 - k * 100 + r), fill=(g, g, g + 6))


def _el_farm(p, rnd):
    p.rect((90, BASE - 260, 430, BASE), (190, 70, 60))
    p.poly([(70, BASE - 260), (260, BASE - 400), (450, BASE - 260)], (150, 50, 44))
    p.rect((210, BASE - 150, 310, BASE), (250, 240, 226), r=4, o=5)
    p.line((210, BASE - 150, 310, BASE))
    p.line((310, BASE - 150, 210, BASE))
    p.rect((520, BASE - 330, 610, BASE), (220, 220, 226), r=40)          # Silo
    for fx in range(660, W + 40, 90):                                     # Zaun
        p.rect((fx, BASE - 90, fx + 16, BASE), (176, 130, 86), o=4)
    p.rect((650, BASE - 76, W + 20, BASE - 60), (176, 130, 86), o=4)


def _el_sea(p, rnd):
    p.d.rectangle((0, BASE - 220, W, BASE), fill=p.c((60, 150, 220)))
    for y in range(BASE - 190, BASE - 20, 46):
        for x in range(-60 + (y % 92), W, 160):
            p.d.arc((x, y, x + 90, y + 30), 180, 360, fill=p.c((200, 232, 250)), width=5)
    p.d.line((0, BASE - 220, W, BASE - 220), fill=INK, width=5)


def _el_glacier(p, rnd):
    p.poly([(-40, BASE), (60, BASE - 380), (300, BASE - 460), (520, BASE - 330), (760, BASE - 520), (1000, BASE - 400), (W + 40, BASE - 440), (W + 40, BASE)], (206, 232, 250))
    for x in (200, 470, 830):
        p.line((x, BASE - 300, x + 30, BASE - 60), p.c((150, 200, 235)), 6)


def _fg_fields(p, rnd):
    for i in range(-8, 16):                         # Ackerfurchen in Perspektive
        p.d.line((W / 2 + i * 70, BASE, W / 2 + i * 300, H), fill=p.c((110, 150, 70)), width=8)
    for y in (BASE + 40, BASE + 110, BASE + 210, BASE + 330):
        k = depth(y)
        for x in range(20, W, max(30, int(110 * k))):
            p.d.line((x, y, x - 8 * k, y - 60 * k), fill=p.c((226, 190, 80)), width=max(3, int(8 * k)))
            p.d.line((x, y, x + 8 * k, y - 60 * k), fill=p.c((226, 190, 80)), width=max(3, int(8 * k)))


RIVER = (975, 1105)       # Fluss quert das Bild hinter den Figuren


def _river_band(p, col):
    top = [(x, RIVER[0] + 14 * math.sin(x / 170)) for x in range(-20, W + 40, 40)]
    bot = [(x, RIVER[1] + 18 * math.sin(x / 210 + 1)) for x in range(W + 20, -40, -40)]
    p.d.polygon(top + bot, fill=p.c(col), outline=INK, width=5)


def _fg_river(p, rnd):
    _river_band(p, (70, 156, 226))


def _fg_dryriver(p, rnd):
    _river_band(p, (176, 140, 96))
    for _ in range(9):
        x, y = rnd.randint(0, W), rnd.randint(RIVER[0] + 20, RIVER[1] - 30)
        p.d.line((x, y, x + rnd.randint(-50, 50), y + 24, x + rnd.randint(-70, 70), y + 44), fill=p.c((120, 90, 60)), width=5)


def _fg_lake(p, rnd):
    p.d.ellipse((90, 950, 990, 1150), fill=p.c((70, 156, 226)), outline=INK, width=O)
    for x, y in ((320, 1010), (600, 1060), (480, 985)):
        p.d.arc((x, y, x + 110, y + 26), 180, 360, fill=p.c((206, 234, 252)), width=5)


def _fg_cracks(p, rnd, xr=(0, W)):
    for _ in range(16):
        x, y = rnd.randint(*xr), rnd.randint(BASE + 40, H - 260)
        pts = [(x, y)]
        for _k in range(3):
            x, y = x + rnd.randint(-70, 70), y + rnd.randint(20, 60)
            pts.append((x, y))
        p.d.line(pts, fill=p.c((120, 90, 60)), width=6, joint="curve")


def _fg_rocks(p, rnd):
    for _ in range(7):
        x, y, w = rnd.randint(0, W), rnd.randint(BASE + 10, H - 300), rnd.randint(70, 170)
        p.d.chord((x, y - w * 0.4, x + w, y + w * 0.4), 180, 360, fill=p.c((150, 150, 158)), outline=INK, width=5)


def _fg_flowers(p, rnd):
    for _ in range(26):
        x, y = rnd.randint(0, W), rnd.randint(BASE + 30, H - 260)
        p.d.line((x, y, x, y - 30), fill=p.c((60, 130, 66)), width=5)
        p.d.ellipse((x - 10, y - 44, x + 10, y - 24), fill=p.c(rnd.choice(((250, 120, 150), (250, 220, 90), (250, 250, 250)))))


def tree_at(p, x, y, kind=0, col=(62, 140, 84)):
    """Baum in richtiger Größe für die Tiefe y (rund 8 m hoch); vorn ragen die Stämme aus dem Bild."""
    h, tw = px(8.0, y), px(0.55, y)
    o = max(3, int(O * min(1.0, depth(y) + 0.3)))
    p.rect((x - tw / 2, y - h * 0.5, x + tw / 2, y), (112, 76, 48), o=o)
    p.d.rectangle((x + tw * 0.08, y - h * 0.5 + o, x + tw / 2 - o, y - o), fill=p.c((88, 58, 40)))             # Schattenseite des Stamms
    p.d.ellipse((x - tw * 1.6, y - tw * 0.3, x + tw * 1.6, y + tw * 0.3), fill=p.c(_mix(col, 0.45, (20, 50, 40))))   # Schatten am Fuß
    p.rect((x - tw / 2, y - h * 0.2, x + tw / 2, y), (112, 76, 48), o=0)
    p.d.rectangle((x + tw * 0.08, y - h * 0.2, x + tw / 2 - o, y), fill=p.c((88, 58, 40)))
    p.d.line((x - tw / 2, y - h * 0.2, x - tw / 2, y), fill=INK, width=o)
    p.d.line((x + tw / 2, y - h * 0.2, x + tw / 2, y), fill=INK, width=o)
    if kind % 3 == 0:
        p.blobs([(x + dx * h, y + dy * h, r * h) for dx, dy, r in ((0, -0.74, 0.24), (-0.17, -0.58, 0.19), (0.17, -0.58, 0.19), (0, -0.48, 0.2))], col, o=o)
    else:
        for k in range(4):
            yy = y - h * 0.22 - k * h * 0.19
            wd = h * (0.24 - k * 0.045)
            p.poly([(x - wd, yy), (x, yy - h * 0.3), (x + wd, yy)], col, o=o)
            p.poly([(x, yy - h * 0.3 + o), (x + wd - o * 2, yy - o), (x + wd * 0.1, yy - o)], _mix(col, 0.2, (10, 30, 50)), o=0)


def _mid_forest(p, rnd):
    for i, (x, y) in enumerate(((330, 960), (760, 950), (90, 1000), (560, 990), (990, 1010), (210, 1070), (880, 1090), (-20, 1190), (1100, 1210))):
        tree_at(p, x, y, i, ((52, 118, 74), (62, 140, 84), (74, 156, 92))[i % 3])


def _mid_trees(p, rnd):
    tree_at(p, 110, 1040, 0)
    tree_at(p, 990, 1090, 0, (74, 156, 92))


def _mid_deadtrees(p, rnd):
    for x, y in ((150, 1010), (900, 1060), (520, 960)):
        h = px(6.0, y)
        w = max(8, int(px(0.4, y)))
        p.line((x, y, x, y - h), INK, w + 10)
        p.line((x, y, x, y - h), p.c((110, 84, 64)), w)
        for dx, dy, y0 in ((-0.3, -0.25, 0.5), (0.34, -0.3, 0.65), (-0.2, -0.22, 0.85)):
            yy = y - h * y0
            p.line((x, yy, x + dx * h, yy + dy * h), INK, int(w * 0.6) + 8)
            p.line((x, yy, x + dx * h, yy + dy * h), p.c((110, 84, 64)), int(w * 0.6))


def _mid_palms(p, rnd):
    for x, y in ((120, 1060), (960, 1120)):
        h, w = px(7.0, y), max(10, int(px(0.35, y)))
        top = (x + h * 0.12, y - h)
        p.line((x, y, x + h * 0.05, y - h * 0.5, top[0], top[1]), INK, w + 10)
        p.line((x, y, x + h * 0.05, y - h * 0.5, top[0], top[1]), p.c((150, 110, 70)), w)
        for a in (-150, -110, -60, -20, 200, 240):
            ex, ey = top[0] + math.cos(math.radians(a)) * h * 0.36, top[1] + math.sin(math.radians(a)) * h * 0.2 + h * 0.08
            p.poly([top, ((top[0] + ex) / 2, top[1] - h * 0.1), (ex, ey), ((top[0] + ex) / 2, top[1] + h * 0.03)], (70, 160, 84), o=5)


def _mid_cactus(p, rnd):
    for x, y in ((170, 1050), (930, 1120)):
        h, w = px(3.0, y), px(0.5, y)
        p.rect((x - w / 2, y - h, x + w / 2, y), (84, 150, 90), r=int(w / 2), o=5)
        p.rect((x - w * 1.6, y - h * 0.62, x - w * 0.9, y - h * 0.3), (84, 150, 90), r=int(w / 3), o=5)
        p.rect((x - w * 1.6, y - h * 0.42, x, y - h * 0.3), (84, 150, 90), r=int(w / 4), o=5)
        p.rect((x + w * 0.9, y - h * 0.8, x + w * 1.6, y - h * 0.45), (84, 150, 90), r=int(w / 3), o=5)
        p.rect((x, y - h * 0.57, x + w * 1.6, y - h * 0.45), (84, 150, 90), r=int(w / 4), o=5)


def _mid_street(p, rnd):
    """Häuserzeile in echter Größe hinter der Straße: Läden im Erdgeschoss mit Markisen und Schaufenstern, Fenster mit
    Rahmen und Fensterbank, Dachgesims – Türen so hoch wie ein Mensch plus etwas."""
    y = 1000
    m = px(1.0, y)
    x = -60
    cols = ((214, 150, 120), (150, 176, 214), (224, 200, 140), (170, 200, 172), (196, 160, 190), (208, 190, 170))
    i = 0
    while x < W:
        w, floors = rnd.randint(int(m * 3.6), int(m * 5.0)), rnd.randint(2, 3)
        h = m * (3.4 + floors * 3.0)
        col = cols[(i * 2 + rnd.randint(0, 1)) % 6]
        dark = _mix(col, 0.2, (40, 30, 50))
        p.rect((x, y - h, x + w, y), col)
        p.d.rectangle((x + w - m * 0.35, y - h + O, x + w - O, y - O), fill=p.c(_mix(col, 0.1, (40, 30, 60))))      # Schattenkante
        p.rect((x - 8, y - h - 22, x + w + 8, y - h + 12), dark, r=4, o=5)                                          # Dachgesims
        p.d.rectangle((x + O, y - h + 14, x + w - O, y - h + 26), fill=p.c(_mix(col, 0.18, (30, 30, 60))))
        gf = y - m * 3.2                                        # Erdgeschoss: Sockel, Schaufenster, Tür
        p.d.rectangle((x + O, gf + m * 0.1, x + w - O, y - O), fill=p.c(_mix(col, 0.16, (60, 50, 60))))
        lit = p.night and not p.dark and i % 2 == 1
        sx0, sy0, sx1, sy1 = x + m * 0.3, gf + m * 0.6, x + w - m * 1.5, y - m * 0.5
        p.rect((sx0 - 8, sy0 - 8, sx1 + 8, sy1 + 8), (244, 240, 230), r=4, o=5)
        p.rect((sx0, sy0, sx1, sy1), (255, 232, 150) if lit else (150, 204, 236), r=2, o=4, glow=lit)
        if not lit:                                             # Spiegelung im Schaufenster
            p.d.polygon([(sx0 + 14, sy0 + 6), (sx0 + 44, sy0 + 6), (sx0 + 22, sy1 - 6), (sx0 + 8, sy1 - 6)], fill=p.c((198, 228, 246)))
            p.d.polygon([(sx0 + 58, sy0 + 6), (sx0 + 70, sy0 + 6), (sx0 + 48, sy1 - 6), (sx0 + 40, sy1 - 6)], fill=p.c((198, 228, 246)))
        p.rect((sx0 - 14, sy1 + 4, sx1 + 14, sy1 + 16), (224, 220, 212), r=3, o=4)
        dx0, dx1 = x + w - m * 1.25, x + w - m * 0.3              # Tür mit Oberlicht und Griff
        p.rect((dx0, y - m * 2.2, dx1, y), (104, 70, 48), r=4, o=5)
        p.rect((dx0 + 8, y - m * 2.1, dx1 - 8, y - m * 1.5), (150, 204, 236) if not lit else (255, 232, 150), r=3, o=3, glow=lit)
        p.oval((dx0 + 10, y - m * 1.05, dx0 + 22, y - m * 0.93), (236, 200, 110), o=2)
        aw = ((214, 80, 70), (70, 130, 190), (240, 190, 70), (90, 160, 110))[i % 4]
        a0, a1 = x + m * 0.1, x + w - m * 0.1
        p.poly([(a0, gf + m * 0.62), (a1, gf + m * 0.62), (a1 - m * 0.12, gf + m * 0.02), (a0 + m * 0.12, gf + m * 0.02)], aw, o=5)
        n = max(4, int((a1 - a0) / (m * 0.42)))
        for k in range(0, n, 2):                                # gestreifte Markise
            x0s, x1s = a0 + (a1 - a0) * k / n, a0 + (a1 - a0) * (k + 1) / n
            p.d.polygon([(x0s + 4, gf + m * 0.58), (x1s, gf + m * 0.58), (x1s - 2, gf + m * 0.08), (x0s + 6, gf + m * 0.08)], fill=p.c((250, 246, 236)))
        p.d.line((a0, gf + m * 0.62, a1, gf + m * 0.62), fill=INK, width=5)
        for fl in range(floors):
            wy = gf - m * (2.6 + fl * 3.0)
            for wx in (x + w * 0.16, x + w * 0.58):
                lit2 = p.night and not p.dark and rnd.random() < 0.5
                p.rect((wx - 7, wy - 7, wx + m * 0.9 + 7, wy + m * 1.4 + 7), (246, 242, 232), r=4, o=4)
                p.rect((wx, wy, wx + m * 0.9, wy + m * 1.4), (255, 226, 120) if lit2 else (126, 168, 214), r=2, o=4, glow=lit2)
                p.d.line((wx + m * 0.45, wy, wx + m * 0.45, wy + m * 1.4), fill=INK, width=3)
                if not lit2:
                    p.d.polygon([(wx + 5, wy + 5), (wx + 16, wy + 5), (wx + 8, wy + m * 1.4 - 5), (wx + 4, wy + m * 1.4 - 5)], fill=p.c((176, 206, 236)))
                p.rect((wx - 12, wy + m * 1.4 + 5, wx + m * 0.9 + 12, wy + m * 1.4 + 15), (226, 222, 214), r=3, o=3)
                if (i + fl) % 3 == 0:                           # Blumenkasten
                    p.rect((wx - 6, wy + m * 1.4 - 8, wx + m * 0.9 + 6, wy + m * 1.4 + 8), (150, 96, 64), r=3, o=3)
                    for k in range(4):
                        cx = wx + 6 + k * m * 0.26
                        p.d.ellipse((cx - 9, wy + m * 1.4 - 22, cx + 9, wy + m * 1.4 - 4), fill=p.c(((226, 90, 110), (250, 200, 80))[k % 2]))
        x += w
        i += 1


def _mid_powerlines(p, rnd):
    y = 1010
    h = px(9.0, y)
    pts = []
    for x in (120, 620, 1120):
        p.line((x, y, x, y - h), p.c((96, 76, 60)), 14)
        p.line((x - 60, y - h + 30, x + 60, y - h + 30), p.c((96, 76, 60)), 10)
        pts.append((x, y - h + 30))
    for dx in (-56, 56):
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            p.d.line([(x0 + dx + (x1 - x0) * k / 10, y0 + 46 * math.sin(k / 10 * math.pi)) for k in range(11)], fill=INK, width=4)
        p.d.line([(-200 + dx + (pts[0][0] + 200) * k / 10, pts[0][1] + 46 * math.sin(k / 10 * math.pi)) for k in range(11)], fill=INK, width=4)


def _mid_windturbines(p, rnd):
    for x, y in ((220, 940), (700, 925), (960, 960)):
        h = 380 + (x % 3) * 40
        p.poly([(x - 9, y), (x - 4, y - h), (x + 4, y - h), (x + 9, y)], (240, 242, 246), o=4)


def _mid_gasstation(p, rnd):
    y = 1030
    m = px(1.0, y)
    p.rect((90, y - m * 4.6, 90 + m * 8.5, y - m * 4.0), (220, 60, 56), r=8)                 # Dach
    for x in (90 + m * 0.8, 90 + m * 7.5):
        p.rect((x, y - m * 4.0, x + m * 0.3, y), (200, 200, 206), o=5)
    for x in (90 + m * 2.6, 90 + m * 5.2):                                                   # Zapfsäulen
        p.rect((x, y - m * 1.7, x + m * 0.8, y), (240, 240, 244), r=8)
        p.rect((x + m * 0.12, y - m * 1.5, x + m * 0.68, y - m * 1.0), (60, 70, 90), r=4, o=4)
        p.line((x + m * 0.8, y - m * 1.2, x + m * 1.1, y - m * 0.7, x + m * 0.9, y - m * 0.3), INK, 6)
    p.rect((780, y - m * 3.2, 1100, y), (236, 228, 214))                                     # Shop
    p.rect((810, y - m * 2.2, 960, y - m * 0.8), (255, 232, 150) if (p.night and not p.dark) else (150, 204, 236), r=4, o=5, glow=p.night and not p.dark)
    p.rect((985, y - m * 2.1, 1060, y), (104, 70, 48), r=4, o=5)


def _mid_powerplant(p, rnd):
    y = 960
    for cx, w, h in ((260, 300, 560), (620, 340, 640)):                                       # Kühltürme
        p.poly([(cx - w / 2, y), (cx - w * 0.3, y - h * 0.6), (cx - w * 0.38, y - h), (cx + w * 0.38, y - h),
                (cx + w * 0.3, y - h * 0.6), (cx + w / 2, y)], (206, 206, 212))
    p.rect((820, y - 260, 1060, y), (160, 164, 176))
    p.rect((900, y - 520, 950, y - 260), (170, 110, 96))


def _mid_bridge(p, rnd):
    y = 1010
    p.rect((-20, y - 150, W + 20, y - 110), (150, 150, 160))
    for x in (160, 540, 920):
        p.rect((x - 30, y - 110, x + 30, y + 30), (130, 130, 142))
    for x in (350, 730):
        p.rect((x - 16, y - 520, x + 16, y - 150), (176, 80, 70))
        for k in range(1, 8):
            p.d.line((x, y - 520, x - k * 46, y - 150), fill=INK, width=4)
            p.d.line((x, y - 520, x + k * 46, y - 150), fill=INK, width=4)


def _mid_camp(p, rnd):
    for x, y, col in ((230, 1080, (230, 150, 70)), (880, 1120, (90, 150, 190))):
        h, w = px(1.9, y), px(3.0, y)
        p.poly([(x - w / 2, y), (x, y - h), (x + w / 2, y)], col)
        p.poly([(x - w * 0.12, y), (x, y - h * 0.62), (x + w * 0.12, y)], (50, 44, 50), o=5)


def _mid_graves(p, rnd):
    for i, (x, y) in enumerate(((160, 1010), (420, 1050), (700, 1000), (930, 1080), (300, 1140), (820, 1170))):
        h, w = px(1.1, y), px(0.7, y)
        p.rect((x - w / 2, y - h, x + w / 2, y), (160, 160, 170), r=int(w / 2.2), o=5)
        p.rect((x - w / 2, y - h * 0.45, x + w / 2, y), (160, 160, 170), o=0)
        p.line((x - w / 2, y - h * 0.5, x - w / 2, y)); p.line((x + w / 2, y - h * 0.5, x + w / 2, y))
        p.line((x, y - h * 0.8, x, y - h * 0.45), w=5); p.line((x - w * 0.2, y - h * 0.68, x + w * 0.2, y - h * 0.68), w=5)


def _mid_church(p, rnd):
    y = 1000
    m = px(1.0, y)
    cx = 700
    col = (86, 80, 96) if not p.night else (40, 40, 60)
    p.rect((cx - m * 3.2, y - m * 5.2, cx + m * 3.2, y), col)
    p.poly([(cx - m * 3.4, y - m * 5.2), (cx, y - m * 7.4), (cx + m * 3.4, y - m * 5.2)], _mix(col, 0.2, (0, 0, 0)))
    for sx in (-1, 1):
        tx = cx + sx * m * 2.2
        p.rect((tx - m * 0.9, y - m * 9.0, tx + m * 0.9, y), col)
        p.poly([(tx - m * 1.0, y - m * 9.0), (tx, y - m * 13.0), (tx + m * 1.0, y - m * 9.0)], _mix(col, 0.2, (0, 0, 0)))
        for k in range(3):
            p.rect((tx - m * 0.3, y - m * (8.0 - k * 2.0), tx + m * 0.3, y - m * (6.9 - k * 2.0)), (255, 214, 120) if p.night and not p.dark else (150, 190, 230), r=int(m * 0.3), o=4, glow=p.night and not p.dark)
    p.oval((cx - m * 0.9, y - m * 4.4, cx + m * 0.9, y - m * 2.6), (240, 180, 90) if p.night and not p.dark else (150, 190, 230), o=5, glow=p.night and not p.dark)
    p.rect((cx - m * 0.6, y - m * 1.9, cx + m * 0.6, y), (60, 44, 40), r=int(m * 0.5), o=5)


def _mid_tower(p, rnd):
    """Firmenzentrale: gläserner Büroturm mit Vorplatz, überragt die Stadt – ohne Schriftzug und ohne Logo."""
    y = 1000
    m = px(1.0, y) * 0.6                                       # steht weit hinten am Platz: ganz im Bild, auch bei herangezoomter Kamera
    cx = 600
    lit = p.night and not p.dark
    glass, frame = (120, 196, 226), (70, 92, 124)
    p.rect((cx - m * 4.6, y - m * 3.2, cx + m * 4.6, y), frame)                                  # Sockel
    for i in range(6):
        x0 = cx - m * 4.2 + i * m * 1.42
        p.rect((x0, y - m * 2.7, x0 + m * 1.1, y - m * 0.9), (255, 226, 120) if lit else glass, r=4, o=4, glow=lit)
    p.rect((cx - m * 0.9, y - m * 1.9, cx + m * 0.9, y), (44, 52, 70), r=6, o=5)                # Eingang
    p.rect((cx - m * 3.0, y - m * 11.6, cx + m * 3.0, y - m * 3.2), frame)                      # Turm
    for r_ in range(6):
        for c_ in range(4):
            x0 = cx - m * 2.6 + c_ * m * 1.36
            y0 = y - m * 11.1 + r_ * m * 1.3
            on = lit and rnd.random() < 0.6
            p.rect((x0, y0, x0 + m * 1.12, y0 + m * 0.95), (255, 226, 120) if on else (glass if (r_ + c_) % 3 else (160, 220, 240)), r=3, o=3, glow=on)
    p.poly([(cx - m * 3.0, y - m * 11.6), (cx - m * 1.6, y - m * 12.7), (cx + m * 1.6, y - m * 12.7), (cx + m * 3.0, y - m * 11.6)], (56, 74, 104))
    p.line((cx, y - m * 12.7, cx, y - m * 14.4), w=6)                                            # Antenne
    p.oval((cx - 9, y - m * 14.4 - 9, cx + 9, y - m * 14.4 + 9), (240, 80, 70), o=4, glow=True)


MID = {"tower": _mid_tower, "church": _mid_church, "forest": _mid_forest, "trees": _mid_trees, "deadtrees": _mid_deadtrees, "palms": _mid_palms, "cactus": _mid_cactus,
       "street": _mid_street, "powerlines": _mid_powerlines, "windturbines": _mid_windturbines, "gasstation": _mid_gasstation,
       "powerplant": _mid_powerplant, "bridge": _mid_bridge, "camp": _mid_camp, "graves": _mid_graves}

BACK = {"mountains": _el_mountains, "hills": _el_hills, "dunes": _el_dunes, "forest": _el_forest, "trees": _el_trees,
        "deadtrees": _el_deadtrees, "city": _el_city, "village": _el_village, "ruins": _el_ruins, "factory": _el_factory,
        "farm": _el_farm, "sea": _el_sea, "glacier": _el_glacier}
FRONT_EL = {"fields": _fg_fields, "river": _fg_river, "dryriver": _fg_dryriver, "lake": _fg_lake, "cracks": _fg_cracks,
            "rocks": _fg_rocks, "flowers": _fg_flowers}
EL_ALIASES = {"berge": "mountains", "hügel": "hills", "dünen": "dunes", "wald": "forest", "bäume": "trees", "stadt": "city",
              "dorf": "village", "ruinen": "ruins", "fabrik": "factory", "bauernhof": "farm", "meer": "sea", "gletscher": "glacier",
              "felder": "fields", "feld": "fields", "fluss": "river", "see": "lake", "risse": "cracks", "steine": "rocks",
              "blumen": "flowers", "palmen": "palms", "kaktus": "cactus", "kakteen": "cactus", "straße": "street", "häuser": "street",
              "läden": "street", "geschäfte": "street", "shops": "street", "strommasten": "powerlines", "stromleitung": "powerlines",
              "windräder": "windturbines", "windrad": "windturbines", "tankstelle": "gasstation", "kraftwerk": "powerplant",
              "atomkraftwerk": "powerplant", "brücke": "bridge", "zelte": "camp", "lager": "camp", "friedhof": "graves", "gräber": "graves",
              "skyline": "city", "hochhaus": "tower", "wolkenkratzer": "tower", "firmenzentrale": "tower", "zentrale": "tower", "konzern": "tower",
              "büroturm": "tower", "skyscraper": "tower", "headquarters": "tower", "kirche": "church", "dom": "church", "kathedrale": "church", "hochhäuser": "city", "tote bäume": "deadtrees", "ocean": "sea", "mountain": "mountains", "tree": "trees"}


MID_ORDER = ("tower", "church", "windturbines", "powerplant", "bridge", "street", "gasstation", "powerlines", "graves", "camp", "cactus", "palms",
             "deadtrees", "trees", "forest")


def norm_spec(spec):
    els = [EL_ALIASES.get(str(e).lower().strip(), str(e).lower().strip()) for e in (spec.get("elements") or [])][:6]
    ground = str(spec.get("ground") or "").lower()
    if ground not in GROUNDS:
        ground = ("sand" if ("dunes" in els or "palms" in els or "cactus" in els) else "snow" if "glacier" in els
                  else "road" if any(e in els for e in ("city", "ruins", "street", "gasstation")) else "soil" if "fields" in els else "grass")
    return {"sky": str(spec.get("sky") or "").lower(), "ground": ground, "elements": els}


def compose(spec: dict, night=False):
    """Landschaft aus Einzelteilen: {"sky": day|night|sunset|storm|red|haze, "ground": grass|sand|snow|…,
    "elements": [mountains, forest, river, street, …]}. Hinten die ferne Kulisse (Fußlinie FAR), davor der Boden,
    auf dem Dinge je nach Tiefe in richtiger Größe stehen, ganz vorn die Figuren."""
    spec = norm_spec(spec)
    sky, ground, els = spec["sky"], spec["ground"], spec["elements"]
    p = P(night or sky == "night")
    p.outdoor = True
    p.mood = sky if sky in ("sunset", "storm", "red", "haze") else ""
    if p.mood:
        p.haze_col = {"sunset": (255, 200, 150), "storm": (150, 158, 174), "red": (214, 120, 84), "haze": (240, 228, 196)}[p.mood]
    p.sky(BASE + 10)
    sky0 = p.im.copy()
    rnd = random.Random(sum(ord(c) for c in ",".join(els)) % 1000 + 3)
    if "street" in els and "city" not in els and "ruins" not in els:
        els = els + ["city"]
    for name in ["sea", "glacier", "mountains", "hills", "dunes", "city", "ruins", "factory", "forest", "village", "farm"]:
        if name in els:
            BACK[name](p, rnd)
    if ("trees" in els or "deadtrees" in els) and not any(e in els for e in ("mountains", "hills", "dunes", "city", "forest", "sea", "glacier")):
        _el_hills(p, rnd) if ground in ("grass", "soil") else None
    col = GROUNDS[ground]
    for y in range(BASE, H, 10):                                  # Boden: hinten etwas heller (Luftperspektive)
        f = max(0.0, 0.22 * (1 - (y - BASE) / 420))
        p.d.rectangle((0, y, W, y + 10), fill=p.c(_mix(col, f, (255, 255, 255))))
    p.d.line((0, BASE, W, BASE), fill=INK, width=5)
    if ground == "road":
        p.d.rectangle((0, BASE, W, 1040), fill=p.c((188, 188, 194)))                      # ferner Gehweg / Platz
        p.d.rectangle((0, 1040, W, 1222), fill=p.c((84, 86, 96)))                         # Fahrbahn
        p.d.line((0, 1040, W, 1040), fill=INK, width=5)
        for x in range(-40, W, 300):
            p.rect((x, 1136, x + 170, 1150), (250, 240, 200), r=4, o=0)
        p.d.rectangle((0, 1222, W, H), fill=p.c((200, 200, 206)))                         # Gehweg vorn
        p.rect((-10, 1222, W + 10, 1240), (160, 160, 168), o=4)
        for i in range(-5, 12):
            p.d.line((W / 2 + (i - 3) * 190, 1240, W / 2 + (i - 3) * 330, H), fill=p.c((176, 176, 184)), width=4)
        for y in (1330, 1470, 1680):
            p.d.line((0, y, W, y), fill=p.c((176, 176, 184)), width=4)
    elif ground == "grass":
        for _ in range(40):
            x, y = rnd.randint(0, W), rnd.randint(BASE + 30, H - 300)
            k = depth(y)
            p.line((x, y, x - 8 * k, y - 30 * k), p.c((60, 130, 66)), max(3, int(6 * k)))
            p.line((x, y, x + 10 * k, y - 26 * k), p.c((60, 130, 66)), max(3, int(6 * k)))
    elif ground == "dry":
        _fg_cracks(p, rnd)
    elif ground in ("sand", "snow", "moon", "rock", "soil", "ice"):
        dark = _mix(col, 0.12, (60, 50, 40))
        for _ in range(16):
            x, y = rnd.randint(0, W), rnd.randint(BASE + 40, H - 300)
            k = depth(y)
            p.d.arc((x, y, x + 240 * k, y + 40 * k), 190, 350, fill=p.c(dark), width=max(3, int(6 * k)))
    elif ground == "water":
        for y in range(BASE + 30, H - 200, 60):
            k = depth(y)
            for x in range(-60 + (y % 140), W, int(120 + 160 * k)):
                p.d.arc((x, y, x + 110 * k + 30, y + 30 * k + 6), 180, 360, fill=p.c((200, 232, 250)), width=5)
    elif ground == "lava":
        for _ in range(14):
            x, y = rnd.randint(0, W), rnd.randint(BASE + 40, H - 260)
            p.d.ellipse((x, y, x + rnd.randint(80, 220), y + rnd.randint(16, 40)), fill=(250, 130, 40))
    for name in ("fields", "river", "dryriver", "lake", "cracks", "rocks", "flowers"):
        if name in els:
            FRONT_EL[name](p, rnd)
    hz = getattr(p, "haze_col", (60, 64, 120) if p.night else (206, 222, 250))
    p.fade((0, BASE - 260, W, BASE + 10), hz, 0, 60 if p.night else 84)                           # Dunst vor der fernen Kulisse …
    p.fade((0, BASE + 10, W, BASE + 150), hz, 50 if p.night else 70, 0)                           # … Bäume und Häuser davor bleiben klar
    for name in MID_ORDER:
        if name in els:
            MID[name](p, rnd)
    _last_p.append(p)
    r, g, bl = ImageChops.difference(p.im, sky0).split()          # wo noch Himmel zu sehen ist (für Sonne, Wolken, Sterne dahinter)
    m = ImageChops.lighter(ImageChops.lighter(r, g), bl).point(lambda v: 255 if v == 0 else 0)
    m.paste(0, (0, BASE + 10, W, H))
    p.skymask = m.filter(ImageFilter.MinFilter(5))
    return p.vignette()


# Feste Außen-Orte sind fertige Baukasten-Landschaften – so gilt überall dieselbe Perspektive und derselbe Maßstab.
OUTDOOR_SPECS = {
    "street": {"ground": "road", "elements": ["street"]},
    "park": {"ground": "grass", "elements": ["hills", "trees", "flowers"]},
    "beach": {"ground": "sand", "elements": ["sea", "palms"]},
    "desert": {"ground": "sand", "elements": ["dunes", "cactus"]},
    "snow": {"ground": "snow", "elements": ["mountains", "glacier"]},
    "forest": {"ground": "grass", "elements": ["forest"]},
    "mountain": {"ground": "rock", "elements": ["mountains", "rocks"]},
    "farm": {"ground": "soil", "elements": ["farm", "fields", "hills"]},
    "village": {"ground": "grass", "elements": ["village", "hills", "trees"]},
    "gasstation": {"ground": "road", "elements": ["gasstation", "city"]},
    "powerplant": {"ground": "grass", "elements": ["powerplant", "powerlines"]},
    "graveyard": {"ground": "grass", "sky": "haze", "elements": ["graves", "deadtrees", "hills"]},
    "ruins": {"ground": "road", "sky": "red", "elements": ["ruins"]},
    "camp": {"ground": "grass", "elements": ["forest", "camp"]},
    "moon": {"ground": "moon", "sky": "night", "elements": ["rocks"]},
    "church": {"ground": "road", "elements": ["church", "city"]},
    "lake": {"ground": "grass", "elements": ["mountains", "hills", "lake", "trees"]},
    "river": {"ground": "grass", "elements": ["hills", "river", "trees"]},
    "fields": {"ground": "soil", "elements": ["fields", "hills", "windturbines"]},
    "landfill": {"ground": "soil", "sky": "haze", "elements": ["hills", "factory"]},
    "headquarters": {"ground": "road", "elements": ["city", "tower"]},
}


def spec_of(place):
    """Baukasten-Beschreibung eines Hintergrunds (oder None bei Innenräumen und Sonder-Orten)."""
    if isinstance(place, dict):
        return norm_spec(place)
    key = resolve(place)
    return norm_spec(OUTDOOR_SPECS[key]) if key in OUTDOOR_SPECS else None


def _shelf(p, x0, x1, top, bottom, full, rnd):
    p.rect((x0, top, x1, bottom), (226, 228, 234), r=6)
    n = 4
    for k in range(n):
        y1 = top + (k + 1) * (bottom - top) / n
        p.line((x0, y1, x1, y1), w=6)
        if not full and rnd.random() < 0.8:
            if rnd.random() < 0.3:                                 # ein einsames Teil bleibt liegen
                xx = rnd.randint(int(x0 + 20), int(x1 - 60))
                p.rect((xx, y1 - 44, xx + 34, y1 - 4), (220, 90, 70), r=4, o=4)
            continue
        xx = x0 + 14
        while xx < x1 - 40:
            w = rnd.randint(30, 52)
            hgt = rnd.randint(50, int((bottom - top) / n) - 26)
            col = ((220, 90, 70), (240, 196, 70), (90, 160, 110), (70, 130, 200), (236, 150, 90), (190, 120, 190))[rnd.randint(0, 5)]
            p.rect((xx, y1 - hgt - 4, xx + w, y1 - 4), col, r=5, o=4)
            xx += w + rnd.randint(4, 10)


def _supermarket(night, full):
    p = P(night)
    p.room((236, 238, 232), (214, 216, 222), stripe=False)
    rnd = random.Random(5)
    for x in range(120, W, 300):                                                # Deckenlampen
        p.rect((x, 300, x + 180, 326), (255, 250, 220) if (full or not night) else (120, 120, 130), r=8, o=5, glow=not night)
    p.rect((300, 420, 780, 520), (214, 70, 60), r=14)                           # Schild
    p.rect((340, 452, 740, 488), (250, 250, 246), r=8, o=0)
    _shelf(p, 20, 500, 760, 1225, full, rnd)
    _shelf(p, 580, 1060, 760, 1225, full, rnd)
    if not full:
        p.rect((420, 1250, 520, 1290), (214, 170, 110), r=6, o=5)              # umgekippter Karton
    return p.vignette()


def supermarket(night):
    return _supermarket(night, True)


def supermarket_empty(night):
    return _supermarket(night, False)


def bathroom(night):
    p = P(night)
    p.room((206, 232, 238), (190, 200, 210), stripe=False)
    for y in range(0, GROUND - 80, 110):
        p.d.line((0, y, W, y), fill=p.c((180, 214, 224)), width=3)
    for x in range(0, W, 110):
        p.d.line((x, 0, x, GROUND - 80), fill=p.c((180, 214, 224)), width=3)
    p.rect((90, 560, 400, 880), (200, 230, 244), r=10)                          # Spiegel
    p.line((140, 820, 240, 620), p.c((240, 250, 255)), 8)
    p.rect((110, 1010, 380, 1070), (250, 250, 250), r=20)                       # Waschbecken
    p.rect((210, 1070, 280, 1230), (240, 240, 244), o=5)
    p.rect((232, 950, 258, 1010), (170, 176, 186), r=6, o=5)
    p.rect((560, 1040, 1040, 1235), (250, 250, 250), r=40)                      # Badewanne
    p.rect((540, 1020, 1060, 1060), (240, 240, 246), r=16)
    p.rect((960, 760, 980, 1020), (170, 176, 186), o=5)                         # Dusche
    p.rect((900, 740, 980, 770), (170, 176, 186), r=8, o=5)
    p.rect((70, 540, 420, 900), (236, 240, 244), r=14)                          # Spiegelrahmen
    p.rect((90, 560, 400, 880), (200, 230, 244), r=10, o=4)
    p.d.polygon([(140, 600), (190, 600), (130, 860), (104, 860)], fill=p.c((228, 244, 252)))
    p.rect((600, 800, 800, 820), (150, 156, 166), r=6, o=4)                     # Handtuchstange
    p.rect((630, 812, 760, 960), (250, 170, 130), r=10, o=5)
    p.rug((180, GROUND + 10, 520, GROUND + 130), (120, 190, 200))
    p.rect((470, 960, 520, 1010), (120, 190, 180), r=8, o=4)                    # Seife und Becher
    p.plant(480, 1250, 0.7, (236, 240, 244))
    p.lamp_glow(540, 500, 520)
    return p.vignette()


def station(night):
    p = P(night)
    p.room((196, 204, 214), (176, 176, 184), stripe=False)
    p.rect((-10, 240, W + 10, 300), (90, 96, 110), o=5)                         # Dachträger
    for x in (140, 540, 940):
        p.rect((x - 16, 300, x + 16, 1230), (110, 116, 130), o=5)
    p.rect((250, 420, 830, 560), (30, 40, 70), r=10)                            # Anzeigetafel
    for i in range(3):
        p.rect((280, 440 + i * 38, 620 - i * 40, 462 + i * 38), (250, 200, 80), r=4, o=0, glow=True)
        p.rect((700, 440 + i * 38, 800, 462 + i * 38), (250, 120, 90) if i == 1 else (140, 220, 140), r=4, o=0, glow=True)
    p.rect((-20, 760, W + 20, 1180), (210, 60, 56), r=30)                       # Zug
    p.rect((-20, 1120, W + 20, 1180), (60, 60, 70), o=5)
    for x in range(40, W, 260):
        p.rect((x, 820, x + 180, 980), (255, 236, 160) if night else (170, 214, 240), r=14, o=5, glow=night)
    p.rect((470, 800, 610, 1120), (230, 230, 236), r=10)
    p.line((540, 800, 540, 1120))
    p.rect((-10, 1210, W + 10, 1236), (250, 220, 70), o=4)                      # Bahnsteigkante
    return p.vignette()


def restaurant(night):
    p = P(night)
    p.room((236, 214, 190), (150, 104, 76))
    p.window((90, 420, 480, 800))
    p.rect((600, 430, 980, 700), (60, 70, 66), r=10)                            # Tafel
    for i in range(4):
        p.line((640, 480 + i * 50, 940 - (i % 2) * 90, 480 + i * 50), (240, 240, 230), 6)
    for lx in (270, 810):                                                       # Hängelampen
        p.line((lx, 0, lx, 300), INK, 6)
        p.poly([(lx - 80, 380), (lx + 80, 380), (lx + 40, 300), (lx - 40, 300)], (236, 190, 90), glow=True)
    p.plant(560, 1250, 1.0, (120, 84, 60))
    for cx in (270, 810):                                                       # Tische
        p.rect((cx - 170, 1050, cx + 170, 1080), (250, 250, 246), r=6)
        p.rect((cx - 14, 1080, cx + 14, 1235), (110, 80, 60), o=5)
        p.oval((cx - 60, 1030, cx + 60, 1056), (240, 240, 244), o=5)
        p.rect((cx + 90, 990, cx + 120, 1050), (200, 60, 60), r=6, o=5)
    p.lamp_glow(540, 520, 560)
    return p.vignette()


GERMANY = [(0.45, 0.02), (0.52, 0.06), (0.58, 0.03), (0.66, 0.07), (0.78, 0.09), (0.86, 0.14), (0.9, 0.24), (0.88, 0.33), (0.93, 0.42),
           (0.9, 0.5), (0.8, 0.56), (0.72, 0.6), (0.76, 0.7), (0.84, 0.78), (0.78, 0.86), (0.8, 0.94), (0.66, 0.96), (0.56, 0.99), (0.44, 0.95),
           (0.34, 0.98), (0.22, 0.96), (0.24, 0.86), (0.14, 0.78), (0.08, 0.68), (0.12, 0.58), (0.06, 0.48), (0.1, 0.38), (0.16, 0.3),
           (0.2, 0.2), (0.3, 0.16), (0.32, 0.08), (0.4, 0.08)]


def _map(night, pts, title_col=(120, 150, 255)):
    """Kartenbild: dunkler Grund, leuchtender Umriss – für „in ganz Deutschland“, „weltweit“ und Zahlen pro Land."""
    p = P(False)
    p.grad((0, 0, W, H), (8, 10, 30), (22, 26, 66), raw=True)
    for gx in range(0, W, 90):                                                 # feines Kartennetz
        p.d.line((gx, 0, gx, H), fill=(20, 26, 58), width=2)
    for gy in range(0, H, 90):
        p.d.line((0, gy, W, gy), fill=(20, 26, 58), width=2)
    x0, y0, w, h = 190, 380, 700, 900
    poly = [(x0 + a * w, y0 + b * h) for a, b in pts]
    p.veil([(x + 0, y + 0) for x, y in poly], (70, 100, 220), 150, 40, kind="poly")       # Leuchten um das Land
    p.d.polygon(poly, fill=(26, 36, 82))
    p.d.line(poly + [poly[0]], fill=(60, 80, 170), width=14, joint="curve")
    p.d.line(poly + [poly[0]], fill=title_col, width=5, joint="curve")
    return p.im


def germany(night):
    return _map(night, GERMANY)


CONTINENTS = (   # grobe Umrisse auf der Einheitskugel (Blick auf Europa/Afrika), x nach rechts, y nach unten
    ((-0.12, -0.72), (0.02, -0.80), (0.20, -0.78), (0.30, -0.66), (0.22, -0.56), (0.28, -0.48), (0.14, -0.44), (0.06, -0.50), (-0.02, -0.44),
     (-0.12, -0.46), (-0.22, -0.42), (-0.26, -0.52), (-0.14, -0.58), (-0.20, -0.66)),                                   # Europa
    ((-0.30, -0.36), (-0.10, -0.42), (0.10, -0.38), (0.26, -0.36), (0.34, -0.22), (0.46, -0.08), (0.36, 0.06), (0.30, 0.30), (0.20, 0.52),
     (0.10, 0.64), (0.02, 0.56), (-0.02, 0.30), (-0.06, 0.10), (-0.22, 0.06), (-0.38, -0.02), (-0.40, -0.20)),         # Afrika
    ((0.30, -0.66), (0.50, -0.74), (0.72, -0.60), (0.88, -0.38), (0.98, -0.14), (0.84, -0.02), (0.70, -0.10), (0.62, 0.08), (0.52, -0.06),
     (0.44, -0.22), (0.36, -0.34), (0.30, -0.46)),                                                                     # Asien
    ((-0.98, 0.08), (-0.78, 0.02), (-0.66, 0.14), (-0.62, 0.34), (-0.74, 0.56), (-0.84, 0.72), (-0.92, 0.52), (-1.0, 0.30)),   # Südamerika
    ((-0.52, -0.86), (-0.34, -0.92), (-0.26, -0.76), (-0.42, -0.66)),                                                  # Grönland
    ((0.38, 0.34), (0.45, 0.32), (0.46, 0.46), (0.40, 0.50)),                                                          # Madagaskar
)


def _starfield(p, seed=11, n=140):
    p.grad((0, 0, W, H), (8, 10, 30), (22, 26, 66), raw=True)
    rnd = random.Random(seed)
    for _ in range(n):
        x, y, r = rnd.randint(0, W), rnd.randint(0, H), rnd.choice((1, 1, 2, 2, 3))
        p.d.ellipse((x - r, y - r, x + r, y + r), fill=(236, 240, 255) if r > 1 else (150, 160, 210))


def worldmap(night):
    """Weltkugel mit erkennbaren Kontinenten, Tag-/Nachtseite, Glanz und Atmosphäre – vor Sternen."""
    p = P(False)
    _starfield(p)
    cx, cy, r = 540, 820, 430
    p.veil((cx - r - 70, cy - r - 70, cx + r + 70, cy + r + 70), (90, 150, 255), 150, 34)             # Atmosphäre leuchtet
    ball = Image.new("RGBA", (r * 2, r * 2), (0, 0, 0, 0))
    bd = ImageDraw.Draw(ball)
    bd.ellipse((0, 0, r * 2, r * 2), fill=(36, 104, 190, 255))
    bd.ellipse((-r * 0.2, -r * 0.3, r * 1.5, r * 1.4), fill=(48, 124, 208, 255))                      # hellere Meeresseite
    for pts in CONTINENTS:
        q = [(r + a * r, r + b * r) for a, b in pts]
        bd.polygon([(x + 5, y + 7) for x, y in q], fill=(28, 84, 150, 255))                           # Küstenschatten
        bd.polygon(q, fill=(96, 176, 110, 255), outline=(30, 70, 60, 255), width=5)
        m = (sum(x for x, _ in q) / len(q), sum(y for _, y in q) / len(q))
        bd.polygon([(m[0] + (x - m[0]) * 0.55, m[1] + (y - m[1]) * 0.55) for x, y in q], fill=(124, 196, 122, 255))
    bd.polygon([(r + a * r, r + b * r) for a, b in ((-0.36, -0.30), (0.20, -0.30), (0.30, -0.16), (0.0, -0.10), (-0.34, -0.12))], fill=(226, 200, 130, 255))   # Sahara
    for k in (-0.5, 0.0, 0.5):                                                                        # Breitenkreise
        hh = r * abs(k)
        w2 = r * math.sqrt(1 - k * k)
        bd.arc((r - w2, r + k * r - 26, r + w2, r + k * r + 26), 0, 180, fill=(150, 200, 255, 90), width=3)
    for cxx, cyy, s_ in ((-0.3, -0.56, 1.0), (0.5, 0.2, 0.8), (-0.5, 0.36, 0.9), (0.1, 0.78, 0.7)):   # Wolkenbänder
        bd.rounded_rectangle((r + cxx * r - 90 * s_, r + cyy * r - 12 * s_, r + cxx * r + 90 * s_, r + cyy * r + 12 * s_), 12, fill=(255, 255, 255, 170))
        bd.rounded_rectangle((r + cxx * r - 40 * s_, r + cyy * r - 28 * s_, r + cxx * r + 60 * s_, r + cyy * r - 6 * s_), 12, fill=(255, 255, 255, 150))
    mask = Image.new("L", (r * 2, r * 2), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, r * 2, r * 2), fill=255)
    shade = Image.new("L", (r * 2, r * 2), 0)                                                         # Nachtseite rechts unten
    ImageDraw.Draw(shade).ellipse((r * 0.5, r * 0.4, r * 2.9, r * 2.8), fill=150)
    shade = shade.filter(ImageFilter.GaussianBlur(70))
    ball.paste(Image.new("RGBA", (r * 2, r * 2), (8, 10, 40, 255)), (0, 0), shade)
    hi = Image.new("L", (r * 2, r * 2), 0)                                                            # Glanzlicht links oben
    ImageDraw.Draw(hi).ellipse((r * 0.18, r * 0.12, r * 0.95, r * 0.8), fill=80)
    hi = hi.filter(ImageFilter.GaussianBlur(60))
    ball.paste(Image.new("RGBA", (r * 2, r * 2), (255, 255, 255, 255)), (0, 0), hi)
    p.im.paste(ball, (cx - r, cy - r), mask)
    p.d = ImageDraw.Draw(p.im)
    p.d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(150, 190, 255), width=6)
    return p.im


def hallway(night):
    """Flur mit Türen (Hotel, Wohnhaus, Schule): Türen in echter Größe, Wandlampen, Läufer in Perspektive."""
    p = P(night)
    p.room((206, 190, 170), (120, 92, 76))
    p.rect((-10, GROUND - 330, W + 10, GROUND - 78), (176, 156, 136), o=0)                # Sockelzone
    p.line((0, GROUND - 330, W, GROUND - 330), w=5)
    for i, x in enumerate((70, 420, 770)):                                                    # Türen
        p.rect((x - 16, 726, x + 256, GROUND - 40), (84, 58, 44), r=6)
        p.rect((x, 742, x + 240, GROUND - 40), (132, 90, 60), r=4, o=5)
        for y0, y1 in ((770, 960), (990, 1190)):
            p.d.rounded_rectangle((x + 30, y0, x + 210, y1), 6, outline=p.c((100, 66, 44)), width=6)
        p.oval((x + 196, 990, x + 222, 1016), (240, 200, 90), o=4, glow=True)
        p.rect((x + 84, 690, x + 156, 724), (240, 232, 210), r=6, o=4)
        if night and not p.dark and i == 1:                                                   # Licht unter einer Tür
            p.rect((x + 6, GROUND - 52, x + 234, GROUND - 40), (255, 220, 130), o=0, glow=True)
    for x in (360, 710):                                                                      # Wandlampen
        p.rect((x - 8, 560, x + 8, 620), (90, 80, 70), o=4)
        p.poly([(x - 44, 560), (x + 44, 560), (x + 26, 500), (x - 26, 500)], (255, 226, 150) if not p.dark else (120, 110, 100), o=5, glow=not p.dark)
    p.poly([(330, GROUND - 40), (750, GROUND - 40), (1000, H), (80, H)], (140, 44, 50), o=5)   # Läufer
    p.line((372, GROUND - 40, 170, H), p.c((196, 150, 90)), 8)
    p.line((708, GROUND - 40, 910, H), p.c((196, 150, 90)), 8)
    p.lamp_glow(360, 560, 330)
    p.lamp_glow(710, 560, 330)
    return p.vignette()


def attic(night):
    p = P(night)
    p.room((150, 118, 92), (112, 84, 62))
    p.poly([(0, 0), (W, 0), (W, 520), (540, 180), (0, 520)], (96, 72, 54))                   # Dachschräge
    for x in (140, 340, 740, 940):
        p.line((x, 0, x + (60 if x < 540 else -60), 520 - abs(540 - x) * 0.63), p.c((70, 50, 38)), 22)
    p.oval((440, 300, 640, 500), (30, 36, 86) if night else (150, 212, 255))                  # rundes Fenster
    p.line((540, 300, 540, 500)); p.line((440, 400, 640, 400))
    p.rect((60, 1040, 330, 1232), (150, 110, 70), r=8)                                        # Truhe
    p.rect((60, 1040, 330, 1100), (120, 84, 54), r=8)
    p.rect((180, 1076, 210, 1120), (240, 200, 90), r=4, o=4)
    for bx, by, bw in ((760, 1100, 250), (800, 960, 190)):                                   # Kartons
        p.rect((bx, by, bx + bw, by + 140), (196, 156, 104), r=6)
        p.line((bx, by + 40, bx + bw, by + 40), w=5)
    p.line((540, 0, 540, 150), w=5)
    p.oval((512, 150, 568, 214), (255, 236, 150) if not p.dark else (110, 104, 90), o=5, glow=not p.dark)
    p.lamp_glow(540, 190, 420)
    return p.vignette()


SERVER_RACKS = [(30 + i * 262, 250 + i * 262) for i in range(4)]       # Schränke im Rechenzentrum (x0, x1)
SERVER_ROWS = list(range(410, 1140, 66))                               # Einschübe je Schrank (y)


def serverroom(night):
    """Rechenzentrum / Serverraum: Reihe hoher Serverschränke mit Lämpchen, kühles Licht, Kabelkanal an der Decke."""
    p = P(False)                                                # immer kunstlichtbeleuchtet – kein Fenster, keine Tageszeit
    p.room((52, 62, 92), (118, 126, 146), stripe=False)
    p.rect((-10, 250, W + 10, 300), (88, 96, 122), o=5)                         # Kabelkanal
    for x in range(40, W, 130):
        p.d.line((x, 300, x, 330), fill=(240, 196, 70), width=8)
    for x0, x1 in SERVER_RACKS:
        p.rect((x0, 350, x1, GROUND - 60), (30, 34, 48), r=10)
        p.rect((x0 + 14, 366, x1 - 14, 398), (58, 66, 92), r=6, o=0)
        for y in SERVER_ROWS:
            p.rect((x0 + 16, y, x1 - 16, y + 50), (66, 74, 100), r=6, o=4)
            for k in range(4):
                p.d.line((x0 + 96 + k * 22, y + 14, x0 + 96 + k * 22, y + 36), fill=(36, 40, 58), width=6)   # Lüftungsschlitze
            p.d.ellipse((x0 + 30, y + 16, x0 + 48, y + 34), fill=(110, 230, 140))
            p.d.ellipse((x0 + 56, y + 16, x0 + 74, y + 34), fill=(90, 170, 250))
    g = Image.new("L", (W, H), 0)                                               # kühler Lichtschein von den Schränken
    ImageDraw.Draw(g).rectangle((0, 380, W, GROUND - 60), fill=70)
    g = g.filter(ImageFilter.GaussianBlur(140))
    p.im.paste(Image.new("RGB", (W, H), (120, 190, 255)), (0, 0), g)
    p.d = ImageDraw.Draw(p.im)
    return p.vignette()


def plain(night):
    p = P(night)
    p.room((244, 226, 190), (210, 170, 120))
    p.rect((380, 430, 700, 660), (250, 250, 246), r=6)                          # Bild und Pflanze: kein kahler Raum
    p.d.rectangle((400, 450, 680, 640), fill=p.c((250, 220, 170)))
    p.oval((480, 480, 600, 600), (240, 150, 90), o=5)
    p.plant(960, 1250, 1.0)
    p.rug((250, GROUND + 10, 830, GROUND + 170), (200, 130, 100))
    return p.vignette()


PLACES = {"bedroom": bedroom, "livingroom": livingroom, "street": street, "basement": basement, "park": park,
          "space": space, "lab": lab, "classroom": classroom, "plain": plain, "kitchen": kitchen, "office": office,
          "beach": beach, "desert": desert, "snow": snow, "forest": forest, "underwater": underwater,
          "mountain": mountain, "hospital": hospital, "cave": cave, "supermarket": supermarket,
          "supermarket_empty": supermarket_empty, "bathroom": bathroom, "station": station, "restaurant": restaurant, "germany": germany, "worldmap": worldmap, "hallway": hallway, "attic": attic,
          "serverroom": serverroom}
OUTDOOR = tuple(OUTDOOR_SPECS) + ("custom",)
ALIASES = {"schlafzimmer": "bedroom", "zimmer": "bedroom", "wohnzimmer": "livingroom", "straße": "street", "stadt": "street",
           "city": "street", "keller": "basement", "bunker": "basement", "wald": "forest", "natur": "park", "garten": "park",
           "küche": "kitchen", "büro": "office", "strand": "beach", "meer": "beach", "wüste": "desert", "schnee": "snow",
           "arktis": "snow", "eis": "snow", "ozean": "underwater", "unterwasser": "underwater", "ocean": "underwater",
           "berg": "mountain", "berge": "mountain", "krankenhaus": "hospital", "höhle": "cave", "arctic": "snow",
           "weltraum": "space", "mond": "moon", "labor": "lab", "schule": "classroom", "klassenzimmer": "classroom",
           "home": "livingroom", "house": "livingroom", "outside": "park", "school": "classroom",
           "flur": "hallway", "gang": "hallway", "korridor": "hallway", "treppenhaus": "hallway", "hotel": "hallway", "hotelflur": "hallway", "corridor": "hallway", "hausflur": "hallway", "hotelzimmer": "bedroom", "hotel room": "bedroom", "dachboden": "attic", "speicher": "attic", "deutschland": "germany", "deutschlandkarte": "germany", "karte": "germany", "map": "germany", "weltkarte": "worldmap",
           "welt": "worldmap", "world": "worldmap", "globus": "worldmap", "supermarkt": "supermarket", "laden": "supermarket", "geschäft": "supermarket", "shop": "supermarket", "store": "supermarket",
           "leerer supermarkt": "supermarket_empty", "bad": "bathroom", "badezimmer": "bathroom", "bahnhof": "station",
           "u-bahn": "station", "zug": "station", "restaurant": "restaurant", "café": "restaurant", "cafe": "restaurant", "diner": "restaurant", "burgerladen": "restaurant", "imbiss": "restaurant", "kneipe": "restaurant",
           "gaststätte": "restaurant", "schnellrestaurant": "restaurant", "fast food": "restaurant", "bistro": "restaurant", "pizzeria": "restaurant",
           "bauernhof": "farm", "dorf": "village", "tankstelle": "gasstation", "kraftwerk": "powerplant", "friedhof": "graveyard", "kirche": "church", "dom": "church", "see": "lake", "fluss": "river", "müllhalde": "landfill", "deponie": "landfill",
           "rechenzentrum": "serverroom", "serverraum": "serverroom", "serverfarm": "serverroom", "datacenter": "serverroom", "data center": "serverroom",
           "server room": "serverroom", "server": "serverroom", "datenzentrum": "serverroom",
           "firmenzentrale": "headquarters", "konzernzentrale": "headquarters", "hauptsitz": "headquarters", "firmensitz": "headquarters",
           "wolkenkratzer": "headquarters", "hochhaus": "headquarters", "konzern": "headquarters", "firma": "headquarters", "hq": "headquarters",
           "ruinen": "ruins", "zeltlager": "camp", "lager": "camp", "feld": "farm", "felder": "farm", "mondoberfläche": "moon"}


def resolve(place):
    if isinstance(place, dict):
        return "custom"
    raw = str(place or "").lower().strip()
    key = ALIASES.get(raw, raw)
    if key in PLACES or key in OUTDOOR_SPECS:
        return key
    for name in sorted(list(ALIASES) + list(PLACES) + list(OUTDOOR_SPECS), key=len, reverse=True):   # „dunkler Hotelflur“ → Flur
        if len(name) >= 4 and name in raw:
            return ALIASES.get(name, name)
    return "plain"
# Fenster der Innenräume (x0, y0, x1, y1) – dort ist zu sehen, was draußen am Himmel passiert
WINDOWS = {"bedroom": [(600, 420, 960, 800)], "livingroom": [(120, 400, 460, 760)], "kitchen": [(90, 430, 400, 760)],
           "office": [(70 + i * 330, 380, 350 + i * 330, 800) for i in range(3)], "hospital": [(640, 420, 980, 780)],
           "restaurant": [(90, 420, 480, 800)]}

_cache = {}
_masks = {}
_last_p = []


def sky_mask(place, night=False, dark=False):
    """Maske des sichtbaren Himmels zum Hintergrund (None bei Innenräumen und Sonder-Orten)."""
    background(place, night, dark)
    return _masks.get("last")


def background(place, night=False, dark=False):
    """dark = Stromausfall: Fenster und Lampen bleiben aus."""
    DARK[0] = bool(dark)
    if len(_cache) > 24:                                  # Speicher begrenzen (jedes Bild ist mehrere MB groß)
        _cache.clear()
        last = _masks.get("last")
        _masks.clear()
        _masks["last"] = last
    try:
        if not isinstance(place, dict) and resolve(place) in OUTDOOR_SPECS:
            place = OUTDOOR_SPECS[resolve(place)]
        if isinstance(place, dict):                       # Baukasten-Landschaft
            key = ("c", str(place.get("sky")), str(place.get("ground")), tuple(str(e) for e in (place.get("elements") or [])), bool(night), bool(dark))
            if key not in _cache:
                _last_p.clear()
                _cache[key] = compose(place, bool(night)).convert("RGB")
                _masks[key] = _last_p[0].skymask if _last_p else None
            _masks["last"] = _masks.get(key)
            return _cache[key]
        key = resolve(place)
        if (key, bool(night), bool(dark)) not in _cache:
            _cache[(key, bool(night), bool(dark))] = PLACES[key](bool(night)).convert("RGB")
        _masks["last"] = None
        return _cache[(key, bool(night), bool(dark))]
    finally:
        DARK[0] = False
