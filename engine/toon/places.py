"""Orte im flachen Vektorstil (1080×1920). Jede Funktion zeichnet einen Hintergrund; GROUND ist die Bodenlinie,
auf der die Figuren stehen. Alle Orte gibt es bei Tag und bei Nacht."""
import math
import random

from PIL import Image, ImageDraw, ImageFilter

W, H = 1080, 1920
GROUND = 1270
INK = (22, 22, 26)
O = 7


def _mix(c, f, to=(14, 16, 40)):
    return tuple(int(c[i] * (1 - f) + to[i] * f) for i in range(3))


class P:
    """Zeichenhilfe: Formen mit dunklem Umriss; bei Nacht werden alle Farben abgedunkelt/bläulich."""

    def __init__(self, night):
        self.night = night
        self.im = Image.new("RGB", (W, H), (0, 0, 0))
        self.d = ImageDraw.Draw(self.im)

    def c(self, col, glow=False):
        return col if (glow or not self.night) else _mix(col, 0.55)

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
        top, bot = ((18, 22, 56), (44, 52, 110)) if self.night else ((120, 196, 250), (206, 236, 255))
        for y in range(0, y1, 8):
            f = y / y1
            self.d.rectangle((0, y, W, y + 8), fill=tuple(int(top[i] * (1 - f) + bot[i] * f) for i in range(3)))
        rnd = random.Random(7)
        if self.night:
            for _ in range(70):
                x, y, r = rnd.randint(0, W), rnd.randint(0, y1 - 200), rnd.choice((2, 2, 3, 4))
                self.d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 230))
            self.oval((760, 250, 920, 410), (250, 244, 200), glow=True)
            self.d.ellipse((800, 290, 835, 325), fill=(226, 218, 170))
            self.d.ellipse((850, 340, 885, 372), fill=(226, 218, 170))
        else:
            self.oval((770, 240, 930, 400), (255, 214, 70), glow=True)
            for cx, cy, s in ((240, 380, 1.0), (640, 560, 0.7)):
                for dx, dy, r in ((0, 0, 70), (70, 20, 56), (-70, 24, 50), (20, 36, 60)):
                    self.d.ellipse((cx + dx * s - r * s, cy + dy * s - r * s, cx + dx * s + r * s, cy + dy * s + r * s), fill=(255, 255, 255))

    def window(self, box):
        x0, y0, x1, y1 = box
        self.rect((x0 - 18, y0 - 18, x1 + 18, y1 + 18), (250, 250, 246), r=8)
        sky = (30, 36, 86) if self.night else (150, 212, 255)
        self.d.rectangle((x0, y0, x1, y1), fill=sky)
        if self.night:
            self.d.ellipse((x1 - 110, y0 + 30, x1 - 40, y0 + 100), fill=(250, 244, 200))
            for i in range(9):
                x, y = x0 + 30 + (i * 67) % (x1 - x0 - 60), y0 + 30 + (i * 41) % (y1 - y0 - 120)
                self.d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(255, 255, 230))
        else:
            self.d.ellipse((x0 + 30, y0 + 50, x0 + 150, y0 + 120), fill=(255, 255, 255))
            self.d.ellipse((x0 + 90, y0 + 30, x0 + 210, y0 + 110), fill=(255, 255, 255))
            self.d.rectangle((x0, y1 - 70, x1, y1), fill=(110, 190, 90))
        self.d.rectangle((x0, y0, x1, y1), outline=INK, width=O)
        self.line(((x0 + x1) // 2, y0, (x0 + x1) // 2, y1))
        self.line((x0, (y0 + y1) // 2, x1, (y0 + y1) // 2))

    def room(self, wall, floor, stripe=True):
        self.d.rectangle((0, 0, W, GROUND - 60), fill=self.c(wall))
        if stripe:
            self.stripes((0, 0, W, GROUND - 60), wall)
        self.rect((-10, GROUND - 78, W + 10, GROUND - 40), (250, 248, 240), o=5)
        self.d.rectangle((0, GROUND - 40, W, H), fill=self.c(floor))
        for i in range(-4, 12):   # Dielen in Perspektive
            self.d.line((W / 2 + i * 60, GROUND - 40, W / 2 + i * 190, H), fill=self.c(_mix(floor, 0.22, (40, 24, 10))), width=4)
        for y in (GROUND + 80, GROUND + 230, GROUND + 430):
            self.d.line((0, y, W, y), fill=self.c(_mix(floor, 0.22, (40, 24, 10))), width=4)
        self.d.line((0, GROUND - 40, W, GROUND - 40), fill=INK, width=5)

    def lamp_glow(self, cx, cy, r=420):
        if not self.night:
            return
        g = Image.new("L", (W, H), 0)
        ImageDraw.Draw(g).ellipse((cx - r, cy - r, cx + r, cy + r), fill=120)
        g = g.filter(ImageFilter.GaussianBlur(120))
        self.im.paste(Image.new("RGB", (W, H), (255, 220, 140)), (0, 0), g)
        self.d = ImageDraw.Draw(self.im)

    def vignette(self):
        v = Image.new("L", (W, H), 0)
        ImageDraw.Draw(v).ellipse((-260, -100, W + 260, H + 100), fill=255)
        v = v.filter(ImageFilter.GaussianBlur(220)).point(lambda x: 255 - int((255 - x) * (0.55 if self.night else 0.22)))
        self.im = Image.composite(self.im, Image.new("RGB", (W, H), (8, 8, 20)), v)
        return self.im


# ------------------------------------------------------------------ Orte

def bedroom(night):
    p = P(night)
    p.room((190, 208, 236), (196, 140, 92))
    p.window((600, 420, 960, 800))
    p.rect((120, 470, 360, 700), (246, 214, 120), r=6)                         # Poster
    p.oval((190, 520, 290, 620), (240, 110, 90), o=5)
    p.rect((40, 1010, 520, 1250), (150, 96, 60), r=14)                         # Bett
    p.rect((30, 880, 110, 1250), (130, 80, 48), r=14)
    p.rect((70, 1040, 520, 1190), (96, 132, 220), r=30)
    p.rect((90, 980, 250, 1070), (250, 250, 246), r=30)
    p.rect((820, 1050, 1020, 1250), (150, 96, 60), r=10)                       # Nachttisch
    p.rect((850, 1100, 990, 1150), (176, 118, 76), r=6, o=5)
    p.rect((900, 950, 940, 1050), (90, 90, 96), o=5)
    p.poly([(850, 950), (990, 950), (960, 860), (880, 860)], (255, 226, 130), glow=True)
    p.lamp_glow(920, 920)
    return p.vignette()


def livingroom(night):
    p = P(night)
    p.room((248, 226, 170), (206, 150, 96))
    p.window((120, 400, 460, 760))
    p.rect((640, 470, 940, 660), (250, 250, 246), r=6)                         # Bild
    p.poly([(670, 640), (760, 520), (820, 600), (870, 560), (910, 640)], (110, 180, 120), o=5)
    p.rect((540, 1030, 1040, 1250), (214, 84, 76), r=40)                       # Sofa
    p.rect((520, 1090, 600, 1250), (190, 66, 60), r=30)
    p.rect((980, 1090, 1060, 1250), (190, 66, 60), r=30)
    p.rect((620, 1060, 800, 1170), (240, 120, 110), r=26, o=5)
    p.rect((810, 1060, 990, 1170), (240, 120, 110), r=26, o=5)
    p.rect((90, 1120, 150, 1250), (150, 96, 60), o=6)                          # Pflanze
    p.rect((50, 1170, 190, 1250), (220, 130, 80), r=14)
    for dx, dy in ((-60, -90), (0, -150), (60, -90), (-30, -40), (40, -30)):
        p.oval((120 + dx - 50, 1100 + dy - 60, 120 + dx + 50, 1100 + dy + 60), (80, 170, 96))
    p.lamp_glow(540, 700, 520)
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
                lit = night and rnd.random() < 0.55
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
    for x in (80, 760):
        p.rect((x, 1090, x + 250, 1130), (200, 150, 96), r=6)
        p.rect((x + 20, 1130, x + 44, 1250), (110, 110, 118), o=5)
        p.rect((x + 206, 1130, x + 230, 1250), (110, 110, 118), o=5)
    return p.vignette()


def plain(night):
    p = P(night)
    p.room((244, 226, 190), (210, 170, 120))
    return p.vignette()


PLACES = {"bedroom": bedroom, "livingroom": livingroom, "street": street, "basement": basement, "park": park,
          "space": space, "lab": lab, "classroom": classroom, "plain": plain}
ALIASES = {"schlafzimmer": "bedroom", "zimmer": "bedroom", "wohnzimmer": "livingroom", "straße": "street", "stadt": "street",
           "city": "street", "keller": "basement", "bunker": "basement", "wald": "park", "natur": "park", "garten": "park",
           "weltraum": "space", "mond": "space", "labor": "lab", "schule": "classroom", "klassenzimmer": "classroom",
           "home": "livingroom", "house": "livingroom", "outside": "park", "forest": "park", "school": "classroom"}
_cache = {}


def background(place, night=False):
    key = ALIASES.get(str(place or "").lower().strip(), str(place or "").lower().strip())
    key = key if key in PLACES else "plain"
    if (key, bool(night)) not in _cache:
        _cache[(key, bool(night))] = PLACES[key](bool(night)).convert("RGB")
    return _cache[(key, bool(night))]
