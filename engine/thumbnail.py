"""Thumbnail / Cover: KI-Bild + großer, gut lesbarer Text (wie bei erfolgreichen Shorts)."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .state import FONTS

W, H = 1080, 1920
HIGHLIGHT = (255, 210, 63)   # Gelb für das wichtigste Wort


def _font(size):
    for p in (FONTS / "Poppins-ExtraBold.ttf", FONTS / "Poppins-Bold.ttf",
              Path("/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"),
              Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")):
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def _wrap(words, font, draw, max_w):
    lines, cur = [], []
    for w in words:
        test = " ".join(cur + [w])
        if cur and draw.textlength(test, font=font) > max_w:
            lines.append(cur)
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(cur)
    return lines


def make_thumbnail(src, text, out):
    img = Image.open(src).convert("RGB").resize((W, H), Image.LANCZOS)
    words = [w for w in str(text or "").upper().split() if w][:6]
    if words:
        # Verlauf oben, damit der Text immer lesbar ist
        shade = Image.new("L", (1, H))
        for y in range(H):
            shade.putpixel((0, y), int(max(0, 170 * (1 - y / (H * 0.55)))))
        img = Image.composite(Image.new("RGB", (W, H), (10, 10, 14)), img, shade.resize((W, H)))
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        hi = max(range(len(words)), key=lambda i: len(words[i].strip("!?.,")))   # längstes Wort hervorheben
        size = 190
        while size > 70:
            f = _font(size)
            lines = _wrap(words, f, d, W - 140)
            if len(lines) <= 3 and max(d.textlength(w, font=f) for w in words) <= W - 150:
                break
            size -= 10
        f = _font(size)
        lh = int(size * 1.08)
        y = int(H * 0.11)
        idx = 0
        for line in lines:
            lw = d.textlength(" ".join(line), font=f)
            x = (W - lw) / 2
            for w in line:
                col = HIGHLIGHT if idx == hi else (255, 255, 255)
                d.text((x + 6, y + 8), w, font=f, fill=(0, 0, 0, 150))                       # Schatten
                d.text((x, y), w, font=f, fill=col, stroke_width=max(8, size // 14), stroke_fill=(0, 0, 0))
                x += d.textlength(w + " ", font=f)
                idx += 1
            y += lh
        layer = layer.rotate(2.5, resample=Image.BICUBIC, center=(W / 2, H * 0.2))
        img = Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")
    img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=2))
    img.save(out, quality=90)
    # YouTube erlaubt max. 2 MB
    q = 88
    while Path(out).stat().st_size > 1_900_000 and q > 50:
        img.save(out, quality=q)
        q -= 8
    return out
