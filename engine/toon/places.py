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
        mood = getattr(self, "mood", "")
        top, bot = ((18, 22, 56), (44, 52, 110)) if self.night else ((120, 196, 250), (206, 236, 255))
        if mood == "sunset":
            top, bot = (70, 60, 130), (250, 170, 110)
        elif mood == "storm":
            top, bot = (70, 78, 96), (150, 158, 172)
        elif mood == "red":
            top, bot = (90, 30, 30), (230, 120, 70)
        elif mood == "haze":
            top, bot = (200, 190, 150), (240, 226, 190)
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
        elif mood in ("storm", "red"):
            for cx, cy, sc in ((260, 330, 1.3), (700, 420, 1.1), (980, 300, 0.9)):
                for dx, dy, r in ((0, 0, 80), (80, 20, 64), (-80, 24, 58), (20, 40, 70)):
                    col = (86, 92, 108) if mood == "storm" else (120, 60, 50)
                    self.d.ellipse((cx + dx * sc - r * sc, cy + dy * sc - r * sc, cx + dx * sc + r * sc, cy + dy * sc + r * sc), fill=col)
        else:
            self.oval((770, 240, 930, 400), (255, 150, 70) if mood == "sunset" else (255, 214, 70), glow=True)
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


def kitchen(night):
    p = P(night)
    p.room((214, 236, 222), (226, 214, 196), stripe=False)
    for y in range(0, GROUND - 80, 90):                                         # Fliesen
        p.d.line((0, y, W, y), fill=p.c((196, 222, 206)), width=3)
    for x in range(0, W, 90):
        p.d.line((x, 0, x, GROUND - 80), fill=p.c((196, 222, 206)), width=3)
    p.window((90, 430, 400, 760))
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
BASE = GROUND - 60        # Horizontlinie


def _el_mountains(p, rnd):
    for cx, hgt, w, col in ((180, 560, 520, (150, 160, 184)), (640, 720, 600, (128, 138, 164)), (1000, 500, 460, (150, 160, 184))):
        p.poly([(cx - w // 2, BASE), (cx, BASE - hgt), (cx + w // 2, BASE)], col)
        p.poly([(cx - w // 9, BASE - hgt * 0.76), (cx, BASE - hgt), (cx + w // 9, BASE - hgt * 0.76),
                (cx + w // 24, BASE - hgt * 0.7), (cx - w // 24, BASE - hgt * 0.73)], (250, 252, 255), o=5)


def _el_hills(p, rnd):
    p.d.ellipse((-320, BASE - 300, 640, BASE + 260), fill=p.c((126, 196, 112)), outline=INK, width=5)
    p.d.ellipse((380, BASE - 240, 1420, BASE + 300), fill=p.c((112, 184, 102)), outline=INK, width=5)


def _el_dunes(p, rnd):
    p.d.ellipse((-300, BASE - 260, 700, BASE + 300), fill=p.c((236, 190, 110)), outline=INK, width=5)
    p.d.ellipse((460, BASE - 200, 1500, BASE + 300), fill=p.c((226, 176, 96)), outline=INK, width=5)


def _el_forest(p, rnd):
    for layer, col, base, step in ((0, (46, 104, 70), BASE - 90, 110), (1, (58, 132, 80), BASE, 135)):
        for tx in range(-70, W + 100, step):
            h = rnd.randint(420, 640) if layer else rnd.randint(360, 520)
            p.rect((tx + 46, base - h * 0.36, tx + 74, base), (104, 70, 44), o=5)
            if (tx // step + layer) % 3 == 0:      # Laubbaum
                for dx, dy, r in ((0, -0.62, 0.2), (-0.13, -0.5, 0.16), (0.13, -0.5, 0.16), (0, -0.42, 0.17)):
                    p.oval((tx + 60 + dx * h - r * h, base + dy * h - r * h, tx + 60 + dx * h + r * h, base + dy * h + r * h), col)
            else:                                  # Tanne
                for k in range(3):
                    y = base - h * 0.26 - k * h * 0.2
                    p.poly([(tx + 60 - (128 - k * 26), y), (tx + 60, y - h * 0.3), (tx + 60 + (128 - k * 26), y)], col)


def _el_trees(p, rnd):
    for tx, sc in ((150, 1.0), (930, 1.2)):
        p.rect((tx - 24 * sc, BASE - 320 * sc, tx + 24 * sc, BASE), (130, 86, 54))
        for dx, dy, r in ((0, -400, 150), (-110, -330, 110), (110, -330, 110), (0, -290, 120)):
            p.oval((tx + dx * sc - r * sc, BASE + dy * sc - r * sc, tx + dx * sc + r * sc, BASE + dy * sc + r * sc), (70, 160, 84))


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
    while x < W:
        w, h = rnd.randint(190, 290), rnd.randint(360, 740)
        p.rect((x, BASE - h, x + w, BASE), cols[rnd.randint(0, 4)])
        for wy in range(BASE - h + 46, BASE - 150, 116):
            for wx in range(x + 32, x + w - 58, 82):
                lit = p.night and rnd.random() < 0.55
                p.rect((wx, wy, wx + 48, wy + 64), (255, 226, 120) if lit else (126, 168, 214), r=4, o=5, glow=lit)
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
    for i in range(-6, 14):                         # Ackerfurchen in Perspektive
        p.d.line((W / 2 + i * 40, BASE, W / 2 + i * 210, H), fill=p.c((110, 150, 70)), width=10)
    for y in (BASE + 70, BASE + 190, BASE + 360):
        for x in range(20, W, 70):
            p.d.line((x, y, x - 8, y - 30), fill=p.c((226, 190, 80)), width=6)
            p.d.line((x, y, x + 8, y - 30), fill=p.c((226, 190, 80)), width=6)


def _fg_river(p, rnd):
    pts = [(420, BASE), (560, BASE), (760, BASE + 220), (1000, H), (160, H), (360, BASE + 220)]
    p.d.polygon(pts, fill=p.c((70, 156, 226)), outline=INK, width=5)
    for y in range(BASE + 60, H - 200, 110):
        p.d.arc((440 + (y - BASE) * 0.1, y, 560 + (y - BASE) * 0.1, y + 30), 180, 360, fill=p.c((206, 234, 252)), width=5)


def _fg_dryriver(p, rnd):
    pts = [(420, BASE), (560, BASE), (760, BASE + 220), (1000, H), (160, H), (360, BASE + 220)]
    p.d.polygon(pts, fill=p.c((176, 140, 96)), outline=INK, width=5)
    _fg_cracks(p, rnd, (300, 800))


def _fg_lake(p, rnd):
    p.d.ellipse((120, BASE + 50, 960, BASE + 420), fill=p.c((70, 156, 226)), outline=INK, width=O)
    for x, y in ((320, BASE + 170), (600, BASE + 260), (480, BASE + 120)):
        p.d.arc((x, y, x + 110, y + 30), 180, 360, fill=p.c((206, 234, 252)), width=5)


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


BACK = {"mountains": _el_mountains, "hills": _el_hills, "dunes": _el_dunes, "forest": _el_forest, "trees": _el_trees,
        "deadtrees": _el_deadtrees, "city": _el_city, "village": _el_village, "ruins": _el_ruins, "factory": _el_factory,
        "farm": _el_farm, "sea": _el_sea, "glacier": _el_glacier}
FRONT_EL = {"fields": _fg_fields, "river": _fg_river, "dryriver": _fg_dryriver, "lake": _fg_lake, "cracks": _fg_cracks,
            "rocks": _fg_rocks, "flowers": _fg_flowers}
EL_ALIASES = {"berge": "mountains", "hügel": "hills", "dünen": "dunes", "wald": "forest", "bäume": "trees", "stadt": "city",
              "dorf": "village", "ruinen": "ruins", "fabrik": "factory", "bauernhof": "farm", "meer": "sea", "gletscher": "glacier",
              "felder": "fields", "feld": "fields", "fluss": "river", "see": "lake", "risse": "cracks", "steine": "rocks",
              "blumen": "flowers", "tote bäume": "deadtrees", "ocean": "sea", "mountain": "mountains", "tree": "trees"}


def compose(spec: dict, night=False):
    """Landschaft aus Einzelteilen: {"sky": day|night|sunset|storm|red|haze, "ground": grass|sand|snow|…,
    "elements": [mountains, forest, river, …]} – hinten nach vorn in sinnvoller Reihenfolge gezeichnet."""
    sky = str(spec.get("sky") or "").lower()
    p = P(night or sky == "night")
    p.mood = sky if sky in ("sunset", "storm", "red", "haze") else ""
    p.sky()
    els = [EL_ALIASES.get(str(e).lower().strip(), str(e).lower().strip()) for e in (spec.get("elements") or [])][:5]
    rnd = random.Random(hash(tuple(els)) % 1000 + 3)
    order = ["sea", "glacier", "mountains", "hills", "dunes", "city", "ruins", "factory", "forest", "deadtrees", "village", "farm", "trees"]
    for name in order:
        if name in els:
            BACK[name](p, rnd)
    ground = str(spec.get("ground") or "").lower()
    if ground not in GROUNDS:
        ground = ("sand" if "dunes" in els else "snow" if "glacier" in els else "road" if ("city" in els or "ruins" in els)
                  else "soil" if "fields" in els else "grass")
    col = GROUNDS[ground]
    p.d.rectangle((0, BASE, W, H), fill=p.c(col))
    p.d.line((0, BASE, W, BASE), fill=INK, width=5)
    if ground == "road":
        p.rect((-10, BASE, W + 10, BASE + 90), (196, 196, 200))
        for x in range(40, W, 240):
            p.rect((x, BASE + 310, x + 130, BASE + 336), (250, 240, 200), r=4, o=0)
    elif ground == "grass":
        for _ in range(26):
            x, y = rnd.randint(0, W), rnd.randint(BASE + 50, H - 300)
            p.line((x, y, x - 8, y - 26), p.c((60, 130, 66)), 5)
            p.line((x, y, x + 10, y - 22), p.c((60, 130, 66)), 5)
    elif ground == "dry":
        _fg_cracks(p, rnd)
    elif ground == "water":
        for y in range(BASE + 40, H - 200, 70):
            for x in range(-60 + (y % 140), W, 190):
                p.d.arc((x, y, x + 100, y + 30), 180, 360, fill=p.c((200, 232, 250)), width=5)
    elif ground == "lava":
        for _ in range(12):
            x, y = rnd.randint(0, W), rnd.randint(BASE + 40, H - 260)
            p.d.ellipse((x, y, x + rnd.randint(80, 220), y + rnd.randint(16, 40)), fill=(250, 130, 40))
    for name in ("fields", "river", "dryriver", "lake", "cracks", "rocks", "flowers"):
        if name in els:
            FRONT_EL[name](p, rnd)
    return p.vignette()


def plain(night):
    p = P(night)
    p.room((244, 226, 190), (210, 170, 120))
    return p.vignette()


PLACES = {"bedroom": bedroom, "livingroom": livingroom, "street": street, "basement": basement, "park": park,
          "space": space, "lab": lab, "classroom": classroom, "plain": plain, "kitchen": kitchen, "office": office,
          "beach": beach, "desert": desert, "snow": snow, "forest": forest, "underwater": underwater,
          "mountain": mountain, "hospital": hospital, "cave": cave}
OUTDOOR = ("street", "park", "beach", "desert", "snow", "forest", "mountain", "custom")
ALIASES = {"schlafzimmer": "bedroom", "zimmer": "bedroom", "wohnzimmer": "livingroom", "straße": "street", "stadt": "street",
           "city": "street", "keller": "basement", "bunker": "basement", "wald": "forest", "natur": "park", "garten": "park",
           "küche": "kitchen", "büro": "office", "strand": "beach", "meer": "beach", "wüste": "desert", "schnee": "snow",
           "arktis": "snow", "eis": "snow", "ozean": "underwater", "unterwasser": "underwater", "ocean": "underwater",
           "berg": "mountain", "berge": "mountain", "krankenhaus": "hospital", "höhle": "cave", "arctic": "snow",
           "weltraum": "space", "mond": "space", "labor": "lab", "schule": "classroom", "klassenzimmer": "classroom",
           "home": "livingroom", "house": "livingroom", "outside": "park", "school": "classroom"}


def resolve(place):
    if isinstance(place, dict):
        return "custom"
    key = ALIASES.get(str(place or "").lower().strip(), str(place or "").lower().strip())
    return key if key in PLACES else "plain"
_cache = {}


def background(place, night=False):
    if isinstance(place, dict):                       # Baukasten-Landschaft
        key = ("c", str(place.get("sky")), str(place.get("ground")), tuple(str(e) for e in (place.get("elements") or [])), bool(night))
        if key not in _cache:
            _cache[key] = compose(place, bool(night)).convert("RGB")
        return _cache[key]
    key = resolve(place)
    if (key, bool(night)) not in _cache:
        _cache[(key, bool(night))] = PLACES[key](bool(night)).convert("RGB")
    return _cache[(key, bool(night))]
