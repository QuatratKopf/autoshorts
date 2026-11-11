"""HyperFrames-Grafiken: Die Grafik-Einschübe (große Zahl, Frage, Plakette, Duell, Punktestand, Vergleich, Anteil, Countdown,
Kalenderblatt, Runden-Banner) werden als HTML mit GSAP-Zeitleiste beschrieben und von HyperFrames (Chrome, Bild für Bild)
gerendert: echte Typografie mit Kantenglättung, weiche Federn und Bewegungsunschärfe statt Pixel-Zeichnung.

Gleicher Aufbau und dieselben Farben wie engine/toon/graphics.py, damit beide Wege zusammenpassen. Ist HyperFrames nicht
installiert oder schlägt ein Rendern fehl, zeichnet graphics.py die Szene wie bisher – das Video entsteht in jedem Fall.

Schalter: AS_HYPER=0 schaltet HyperFrames ab. HYPERFRAMES_BIN zeigt auf ein eigenes Programm (sonst `hyperframes` im PATH,
sonst `npx -y hyperframes@VERSION`)."""
import html
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from .state import FONTS

VERSION = "0.9.34"
GSAP = "https://cdn.jsdelivr.net/npm/gsap@3.15.0/dist/gsap.min.js"
W, H, FPS = 1080, 1920, 30
TYPES = ("number", "question", "badge", "round", "versus", "score", "compare", "share", "timer", "calendar")
THEMES = {"": ("#3a2896", "#0e0a2e"), "scary": ("#281e60", "#060616"), "panic": ("#782246", "#1a081e"),
          "tense": ("#6e3c78", "#160a28"), "sad": ("#283c82", "#0a0e28"), "happy": ("#5a46be", "#1e1050"), "calm": ("#3a2896", "#0e0a2e")}
GOLD, ORANGE, LEFT, RIGHT, GREEN, INK = "#ffc846", "#ff8a1f", "#966eff", "#ff9628", "#78e65a", "#100c22"
_state = {}


def _cmd():
    """Aufruf von HyperFrames oder None (abgeschaltet / nicht vorhanden)."""
    if os.environ.get("AS_HYPER", "1").strip() in ("0", "no", "off", "false"):
        return None
    if "cmd" not in _state:
        own = os.environ.get("HYPERFRAMES_BIN", "").strip()
        if own:
            _state["cmd"] = own.split()
        elif shutil.which("hyperframes"):
            _state["cmd"] = ["hyperframes"]
        elif shutil.which("npx"):
            _state["cmd"] = ["npx", "-y", f"hyperframes@{VERSION}"]
        else:
            _state["cmd"] = None
    return _state["cmd"]


def available():
    """HyperFrames nutzbar: vorhanden, nicht zweimal hintereinander gescheitert und das Zeitbudget des Laufs (AS_HYPER_BUDGET Sekunden,
    Standard 360) nicht aufgebraucht – der Lauf darf durch die Grafiken nie zu lang werden."""
    try:
        budget = float(os.environ.get("AS_HYPER_BUDGET") or 360)
    except ValueError:
        budget = 360.0
    return (_cmd() is not None and shutil.which("ffmpeg") is not None and not _state.get("broken")
            and _state.get("spent", 0.0) < budget)


def handles(g):
    return isinstance(g, dict) and g.get("type") in TYPES and available()


# ------------------------------------------------------------------ Text einpassen (wie graphics._fit, gemessen mit PIL)

_FONT_FILES = {"anton": "Anton-Regular.ttf", "SemiBold": "Poppins-SemiBold.ttf", "Bold": "Poppins-Bold.ttf", "ExtraBold": "Poppins-ExtraBold.ttf"}


def _fit(text, size, max_w, kind="anton", spacing=0.0):
    """Größte Schriftgröße ≤ size, bei der text in max_w Bildpunkte passt."""
    try:
        from PIL import ImageFont
        path = FONTS / _FONT_FILES[kind]
        if not path.exists():
            raise OSError
        while size > 28:
            f = ImageFont.truetype(str(path), size)
            if f.getlength(text) + spacing * size * max(0, len(text) - 1) <= max_w:
                break
            size -= 6
        return size
    except Exception:  # noqa: BLE001 – ohne Schriftdatei grob schätzen
        per = (0.46 if kind == "anton" else 0.66) + spacing
        return int(max(28, min(size, max_w / max(1, len(text)) / per)))


def _e(s):
    return html.escape(str(s or ""), quote=True)


def _num(s):
    m = re.search(r"\d[\d.]*(?:,\d+)?", str(s or ""))
    try:
        return float(m.group(0).replace(".", "").replace(",", ".")) if m else None
    except ValueError:
        return None


# ------------------------------------------------------------------ Bausteine

def _kicker(text, y, start=0.0, ident="kick"):
    text = str(text or "").upper()[:40]
    if not text:
        return "", ""
    size = _fit(text, 36, 900, "SemiBold", 0.18)
    el = f'<div id="{ident}" class="kicker" style="top:{y}px;font-size:{size}px">{_e(text)}</div>'
    js = f'tl.fromTo("#{ident}", {{opacity: 0, y: 24, letterSpacing: "0.5em"}}, {{opacity: 1, y: 0, letterSpacing: "0.18em", duration: 0.45, ease: "power3.out"}}, {start});\n'
    return el, js


def _count_js(sel, value, start, dur=1.1):
    """Zahl läuft hoch, im selben Format wie graphics._count („5 MIO.“, „45.000“, „1,2 Mrd.“)."""
    return (f'countUp("{sel}", {json.dumps(str(value))}, tl, {start}, {dur});\n')


def _pill(ident, text, cx, y, size, bg, ink=INK, start=0.0, dx=0, kind="anton"):
    fam = "var(--display)" if kind == "anton" else "var(--body)"
    el = (f'<div id="{ident}" class="pill" style="left:{cx}px;top:{y}px;font-size:{size}px;background:{bg};color:{ink};font-family:{fam}">'
          f'{_e(text)}</div>')
    js = f'tl.fromTo("#{ident}", {{xPercent: -50, x: {dx}, opacity: 0, scale: 0.7}}, {{xPercent: -50, x: 0, opacity: 1, scale: 1, duration: 0.5, ease: "back.out(2)"}}, {start});\n'
    return el, js


def _split_kicker(text, y, start):
    """Titel über dem geteilten Bild: in einer Plakette, damit die schräge Trennlinie nicht durch die Schrift läuft."""
    text = str(text or "").upper()[:24]
    if not text:
        return "", ""
    return _pill("xkick", text, 540, y, _fit(text, 46, 640, "Bold"), "#faf8ff", INK, start, 0, "Bold")


def _split():
    el = '<div id="split"></div><div id="splitline"></div>'
    js = ('tl.fromTo("#split", {xPercent: 70}, {xPercent: 0, duration: 0.5, ease: "power4.out"}, 0);\n'
          'tl.fromTo("#splitline", {xPercent: 70, opacity: 0}, {xPercent: 0, opacity: 1, duration: 0.5, ease: "power4.out"}, 0);\n')
    return el, js


def _side_names(g, y, start):
    els, js = [], []
    for i, (key, cx, col) in enumerate((("left", 270, LEFT), ("right", 810, RIGHT))):
        txt = str(g.get(key) or "").upper()[:14]
        if txt:
            e, j = _pill(f"name{i}", txt, cx, y, _fit(txt, 84, 420), col, INK, start + i * 0.12, -300 if i == 0 else 300)
            els.append(e)
            js.append(j)
    return "".join(els), "".join(js)


# ------------------------------------------------------------------ Grafik-Arten

def _number(g, dur):
    k, kj = _kicker(g.get("kicker"), 520)
    val = str(g.get("value", "")).upper()
    size = _fit(val, 250, 980)
    els = [k, f'<div id="val" class="big" style="top:{590 + (250 - size) / 2}px;font-size:{size}px">{_e(val)}</div>',
           '<div id="bar" style="position:absolute;left:390px;top:900px;width:300px;height:12px;border-radius:6px;background:var(--orange)"></div>']
    js = [kj, 'tl.fromTo("#val", {scale: 0.4, opacity: 0}, {scale: 1, opacity: 1, duration: 0.55, ease: "back.out(2.2)"}, 0.1);\n',
          _count_js("#val", val, 0.15), 'tl.fromTo("#bar", {scaleX: 0}, {scaleX: 1, duration: 0.5, ease: "power3.out"}, 0.35);\n']
    if g.get("label"):
        e, j = _kicker(g["label"], 940, 0.45, "lab")
        els.append(e)
        js.append(j)
    if g.get("sub"):
        sub = g["sub"].upper()[:44]
        els.append(f'<div id="sub" class="body" style="top:1020px;font-size:{_fit(sub, 54, 940, "Bold")}px;color:var(--orange)">{_e(sub)}</div>')
        js.append('tl.fromTo("#sub", {opacity: 0, y: 30}, {opacity: 1, y: 0, duration: 0.4, ease: "power3.out"}, 0.9);\n')
    return els, js


def _question(g, dur):
    txt = str(g.get("text") or "").upper()[:26]
    els = ['<div id="rays" class="rays" style="left:540px;top:740px"></div>', '<div id="ring" class="ring" style="left:540px;top:740px;width:800px;height:800px"></div>',
           '<div id="ring2" class="ring" style="left:540px;top:740px;width:800px;height:800px;border-width:6px"></div>',
           '<div id="q" class="big" style="top:330px;font-size:620px;color:var(--gold);-webkit-text-stroke:8px #784610;text-shadow:12px 16px 0 #96591a">?</div>']
    js = ['tl.fromTo("#rays", {rotation: 0, opacity: 0}, {rotation: %d, opacity: 1, duration: %.2f, ease: "none"}, 0);\n' % (int(dur * 14), dur),
          'tl.fromTo("#ring", {xPercent: -50, yPercent: -50, scale: 0}, {xPercent: -50, yPercent: -50, scale: 1, duration: 0.5, ease: "back.out(1.6)"}, 0.05);\n',
          'tl.fromTo("#ring2", {xPercent: -50, yPercent: -50, scale: 1, opacity: 0.6}, {xPercent: -50, yPercent: -50, scale: 1.3, opacity: 0, duration: 1.4, ease: "power1.out", repeat: %d}, 0.5);\n' % max(0, int(dur / 1.4)),
          'tl.fromTo("#q", {scale: 0.2, rotation: -30, opacity: 0}, {scale: 1, rotation: 0, opacity: 1, duration: 0.6, ease: "back.out(2.4)"}, 0.1);\n',
          'tl.fromTo("#q", {y: 0}, {y: 16, duration: 0.7, ease: "sine.inOut", yoyo: true, repeat: %d}, 0.7);\n' % max(0, int((dur - 0.7) / 0.7))]
    if txt:
        els.append(f'<div id="qt" class="big" style="top:1180px;font-size:{_fit(txt, 110, 940)}px">{_e(txt)}</div>')
        js.append('tl.fromTo("#qt", {opacity: 0, y: 40}, {opacity: 1, y: 0, duration: 0.45, ease: "power3.out"}, 0.5);\n')
    return els, js


def _badge(g, dur):
    txt = str(g.get("text") or "").upper()[:20]
    kick = " ".join(str(g.get("kicker") or "").upper()[:24])
    stars = "".join(f'<div class="star" style="left:{540 + 400 * math.cos(i / 12 * 6.2832):.0f}px;'
                    f'top:{760 + 400 * math.sin(i / 12 * 6.2832):.0f}px">★</div>' for i in range(12))
    els = [f'<div id="stars" style="position:absolute;inset:0">{stars}</div>',
           '<div id="plaque" class="box" style="position:absolute;left:105px;top:585px;width:870px;height:350px;border-radius:30px;background:linear-gradient(160deg,#ffe08a,#ffc846 55%,#e9a92c);'
           'border:10px solid #3c280a;box-shadow:14px 16px 0 rgba(0,0,0,.35)">'
           '<div style="position:absolute;inset:14px;border:5px solid #3c280a;border-radius:20px"></div>'
           + (f'<div class="body" style="top:34px;font-size:{_fit(kick, 40, 740, "Bold")}px;color:#5a3c14;letter-spacing:.08em">{_e(kick)}</div>' if kick else "")
           + f'<div class="big" style="top:{100 + (190 - _fit(txt, 190, 740)) / 2}px;font-size:{_fit(txt, 190, 740)}px;color:#32220a;text-shadow:none">{_e(txt)}</div></div>']
    js = ['tl.fromTo("#stars", {rotation: 0}, {rotation: %d, duration: %.2f, ease: "none", transformOrigin: "540px 760px"}, 0);\n' % (int(dur * 17), dur),
          'tl.fromTo("#stars .star", {scale: 0, opacity: 0}, {scale: 1, opacity: 1, duration: 0.3, ease: "back.out(3)", stagger: 0.04}, 0.1);\n',
          'tl.fromTo("#plaque", {scale: 0.2, rotation: 25, opacity: 0}, {scale: 1, rotation: -5, opacity: 1, duration: 0.6, ease: "back.out(1.8)"}, 0.15);\n',
          'tl.to("#plaque", {rotation: -3.5, duration: 1.2, ease: "sine.inOut", yoyo: true, repeat: %d}, 0.75);\n' % max(0, int((dur - 0.75) / 1.2))]
    return els, js


def _round(g, dur):
    kick, txt = str(g.get("kicker") or "").upper()[:20], str(g.get("text") or "").upper()[:20]
    ts = _fit(txt, 230 if kick else 300, 900)
    inner = ((f'<div class="big" style="top:70px;font-size:{_fit(kick, 110, 860)}px;color:{INK};text-shadow:none">{_e(kick)}</div>' if kick else "")
             + f'<div class="big" style="top:{(200 if kick else 110) + (230 - ts) / 2}px;font-size:{ts}px;-webkit-text-stroke:8px {INK};paint-order:stroke fill">{_e(txt)}</div>')
    els = [f'<div id="banner" class="box" style="position:absolute;left:-210px;top:530px;width:1500px;height:500px;background:{GREEN};border:10px solid {INK};'
           f'box-shadow:0 24px 0 rgba(0,0,0,.35);overflow:hidden"><div id="stripes" class="stripes"></div>{inner}</div>']
    js = ['tl.fromTo("#banner", {x: -1500, rotation: 7}, {x: 0, rotation: 7, duration: 0.45, ease: "power4.out"}, 0.05);\n',
          'tl.fromTo("#stripes", {x: 0}, {x: %d, duration: %.2f, ease: "none"}, 0);\n' % (int(dur * 120), dur),
          'tl.to("#banner", {scale: 1.04, duration: 0.18, ease: "power2.out", yoyo: true, repeat: 1}, 0.5);\n']
    return els, js


def _versus(g, dur):
    se, sj = _split()
    ne, nj = _side_names(g, 1060, 0.2)
    k, kj = _split_kicker(g.get("kicker"), 400, 0.5)
    els = [se, k, ne, '<div id="vsring" class="ring" style="left:540px;top:780px;width:500px;height:500px;border-color:#ff5a6e"></div>',
           '<div id="vs" class="big" style="top:560px;font-size:330px;-webkit-text-stroke:10px #e63250;paint-order:stroke fill;text-shadow:10px 12px 0 #5a0a1e">VS</div>']
    js = [sj, kj, nj, 'tl.fromTo("#vsring", {xPercent: -50, yPercent: -50, scale: 0}, {xPercent: -50, yPercent: -50, scale: 1, duration: 0.5, ease: "back.out(1.6)"}, 0.3);\n',
          'tl.fromTo("#vs", {scale: 2.6, opacity: 0}, {scale: 1, opacity: 1, duration: 0.3, ease: "power4.in"}, 0.35);\n',
          'tl.fromTo("#stage", {x: -14}, {x: 0, duration: 0.4, ease: "elastic.out(1, 0.25)"}, 0.65);\n']
    return els, js


def _score(g, dur):
    se, sj = _split()
    m = re.match(r"^\s*(\d{1,3})\s*[:\-–]\s*(\d{1,3})\s*$", str(g.get("value") or ""))
    a, b = (m.group(1), m.group(2)) if m else ("0", "0")
    win = int(a) - int(b)
    els = [se, f'<div id="board" style="position:absolute;left:90px;top:500px;width:900px;height:520px;border-radius:44px;background:#16103a;border:10px solid {GOLD};'
               'box-shadow:12px 18px 0 rgba(0,0,0,.4)"></div>']
    js = [sj, 'tl.fromTo("#board", {scaleX: 0.2, opacity: 0}, {scaleX: 1, opacity: 1, duration: 0.45, ease: "back.out(1.6)"}, 0.05);\n']
    kick = str(g.get("kicker") or "").upper()[:24]
    if kick:
        e, j = _pill("skick", kick, 540, 456, _fit(kick, 48, 600, "Bold"), GOLD, INK, 0.2, 0, "Bold")
        els.append(e)
        js.append(j)
    for i, (val, cx, col) in enumerate(((a, 310, LEFT), (b, 770, RIGHT))):
        lead = (win > 0 and i == 0) or (win < 0 and i == 1)
        els.append(f'<div id="sc{i}" class="big" style="left:{cx - 200}px;width:400px;top:610px;font-size:300px;color:{"#fff" if lead else col};'
                   f'-webkit-text-stroke:6px {col};paint-order:stroke fill">{_e(val)}</div>')
        js.append(_count_js(f"#sc{i}", val, 0.3, 0.6))
        if lead:
            js.append(f'tl.fromTo("#sc{i}", {{scale: 1}}, {{scale: 1.1, duration: 0.35, ease: "sine.inOut", yoyo: true, repeat: {max(0, int((dur - 0.9) / 0.35))}}}, 0.9);\n')
        name = str(g.get("left" if i == 0 else "right") or "").upper()[:14]
        if name:
            els.append(f'<div class="body" style="left:{cx - 200}px;width:400px;top:534px;font-size:{_fit(name, 50, 380, "Bold")}px;color:{col}">{_e(name)}</div>')
    els.append('<div class="big" style="top:590px;font-size:300px">:</div>')
    return els, js


def _compare(g, dur):
    se, sj = _split()
    k, kj = _split_kicker(g.get("kicker"), 180, 0.0)
    va, vb = _num(g.get("value")), _num(g.get("sub"))
    top = max(va or 0, vb or 0) or 1
    base, full = 1040, 470                                   # Platz über dem höchsten Balken für Wert, Krone und Titel
    els, js = [se, k, f'<div style="position:absolute;left:60px;top:{base}px;width:960px;height:10px;background:#faf8ff"></div>'], [sj, kj]
    for i, (key, val, cx, col) in enumerate((("value", va, 270, LEFT), ("sub", vb, 810, RIGHT))):
        hgt = max(40, full * ((val or 0) / top))
        txt = str(g.get(key) or "").upper()[:12]
        els.append(f'<div id="bar{i}" class="cbar" style="left:{cx - 120}px;top:{base - hgt}px;height:{hgt}px;background:{col}"></div>')
        els.append(f'<div id="bv{i}" class="big" style="left:{cx - 240}px;width:480px;top:{base - hgt - 160}px;font-size:{_fit(txt, 120, 460)}px;'
                   f'-webkit-text-stroke:6px {INK};paint-order:stroke fill">{_e(txt)}</div>')
        js.append(f'tl.fromTo("#bar{i}", {{scaleY: 0}}, {{scaleY: 1, transformOrigin: "50% 100%", duration: 1.0, ease: "power3.out"}}, 0.25);\n')
        js.append(f'tl.fromTo("#bv{i}", {{y: {hgt}, opacity: 0}}, {{y: 0, opacity: 1, duration: 1.0, ease: "power3.out"}}, 0.25);\n')
        js.append(_count_js(f"#bv{i}", txt, 0.25, 1.0))
        if val is not None and val == top and va != vb:
            els.append(f'<div id="crown" style="position:absolute;left:{cx - 80}px;top:{base - hgt - 300}px;width:160px;height:90px">'
                       '<svg viewBox="0 0 160 90" width="160" height="90"><polygon points="10,86 0,16 44,50 80,0 116,50 160,16 150,86" '
                       f'fill="{GOLD}" stroke="{INK}" stroke-width="6" stroke-linejoin="round"/></svg></div>')
            js.append('tl.fromTo("#crown", {y: -200, opacity: 0, rotation: -20}, {y: 0, opacity: 1, rotation: 0, duration: 0.5, ease: "bounce.out"}, 1.25);\n')
    ne, nj = _side_names(g, base + 50, 0.1)
    return els + [ne], js + [nj]


def _person_svg(col, face):
    return (f'<svg viewBox="0 0 100 260" width="100%" height="100%"><g stroke="{INK}" stroke-width="7" stroke-linecap="round">'
            f'<line x1="36" y1="190" x2="34" y2="252"/><line x1="64" y1="190" x2="66" y2="252"/>'
            f'<rect x="14" y="96" width="72" height="104" rx="26" fill="{col}"/><circle cx="50" cy="50" r="46" fill="{face}"/></g>'
            f'<circle cx="34" cy="48" r="6" fill="{INK}"/><circle cx="66" cy="48" r="6" fill="{INK}"/></svg>')


def _share(g, dur):
    m = re.match(r"^\s*(\d{1,2})\s*(?:VON|/|AUS)\s*(\d{1,2})\s*$", str(g.get("value") or "").upper())
    a, b = (int(m.group(1)), int(m.group(2))) if m else (1, 2)
    k, kj = _kicker(g.get("kicker"), 400)
    txt = f"{a} VON {b}"
    els, js = [k, f'<div id="frac" class="big" style="top:460px;font-size:{_fit(txt, 250, 980)}px">{_e(txt)}</div>'], [kj,
              'tl.fromTo("#frac", {scale: 0.4, opacity: 0}, {scale: 1, opacity: 1, duration: 0.5, ease: "back.out(2.2)"}, 0.1);\n']
    lab = str(g.get("label") or "").upper()[:30]
    if lab:
        e, j = _pill("slab", lab, 540, 770, _fit(lab, 60, 860, "Bold"), "#ff5a82", "#faf8ff", 0.5, 0, "Bold")
        els.append(e)
        js.append(j)
    s = min(1.0, 7.6 / b) * 1.15
    gap, base = min(150, 960 / b), 1260
    els.append(f'<div style="position:absolute;left:0;top:{base}px;width:1080px;height:12px;background:#1e1846"></div>')
    hot_t = 0.9 + 0.07 * b
    for i in range(b):
        x = 540 + (i - (b - 1) / 2) * gap
        w, h = 100 * s, 260 * s
        hot = i >= b - a
        els.append(f'<div id="p{i}" class="person" style="left:{x - w / 2:.0f}px;top:{base - h:.0f}px;width:{w:.0f}px;height:{h:.0f}px">'
                   f'<div class="pc">{_person_svg("#6e60be", "#ccc6ec")}</div>'
                   + (f'<div class="ph">{_person_svg(GOLD, "#faf8ff")}</div>' if hot else "") + '</div>')
        js.append(f'tl.fromTo("#p{i}", {{y: 60, opacity: 0}}, {{y: 0, opacity: 1, duration: 0.3, ease: "back.out(2)"}}, {0.3 + i * 0.07:.2f});\n')
        if hot:
            js.append(f'tl.fromTo("#p{i} .ph", {{opacity: 0}}, {{opacity: 1, duration: 0.2}}, {hot_t:.2f});\n')
            js.append(f'tl.fromTo("#p{i}", {{y: 0}}, {{y: {-26 * s:.0f}, duration: 0.3, ease: "sine.out", yoyo: true, repeat: {max(0, int((dur - hot_t) / 0.3))}}}, {hot_t:.2f});\n')
    return els, js


def _timer(g, dur):
    k, kj = _kicker(g.get("kicker"), 520)
    m = re.match(r"^(\d{1,3}):(\d{2})(?::(\d{2}))?$", str(g.get("value") or "72:00:00"))
    hh, mm, ss = (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)) if m else (72, 0, 0)
    total = hh * 3600 + mm * 60 + ss
    size = _fit("00:00:00", 230, 980)
    segs = "".join(f'<div class="seg" style="left:{120 + i * 30:.0f}px"></div>' for i in range(28))
    els = [k, f'<div id="clock" class="big" style="top:600px;font-size:{size}px;font-variant-numeric:tabular-nums">{hh:02d}:{mm:02d}:{ss:02d}</div>',
           "".join(f'<div class="body" style="left:{540 + (i - 1) * 300 - 100}px;width:200px;top:860px;font-size:30px;color:#beb8f0">{lab}</div>'
                   for i, lab in enumerate(("STD", "MIN", "SEK"))),
           f'<div id="segs" style="position:absolute;inset:0">{segs}</div>']
    js = [kj, 'tl.fromTo("#clock", {scale: 0.4, opacity: 0}, {scale: 1, opacity: 1, duration: 0.5, ease: "back.out(2)"}, 0.1);\n',
          f'countDown("#clock", {total}, tl, 0.7, {dur:.2f});\n',
          f'tl.fromTo("#segs .seg", {{backgroundColor: "#463c82"}}, {{backgroundColor: "{GOLD}", duration: 0.05, stagger: {max(0.02, (dur - 1.2) / 28):.3f}}}, 0.7);\n']
    return els, js


def _calendar(g, dur):
    kick = str(g.get("kicker") or "").upper()[:22]
    val = str(g.get("value", ""))
    lab = str(g.get("label") or "").upper()[:14]
    els = ['<div id="cring" class="ring" style="left:540px;top:760px;width:940px;height:940px;border-color:#d2965a;border-width:10px"></div>',
           '<div id="sheet" class="box" style="position:absolute;left:280px;top:460px;width:520px;height:600px;border-radius:30px;background:#faf0d6;'
           f'border:8px solid {INK};box-shadow:12px 18px 0 rgba(0,0,0,.35);overflow:hidden">'
           f'<div style="position:absolute;left:0;top:0;width:100%;height:110px;background:#d6463c;border-bottom:8px solid {INK}"></div>'
           + (f'<div class="body" style="top:30px;font-size:{_fit(kick, 36, 460, "Bold")}px">{_e(kick)}</div>' if kick else "")
           + f'<div id="cval" class="big" style="top:{150 + (300 - _fit(val, 300, 440)) / 2}px;font-size:{_fit(val, 300, 440)}px;color:#281e3c;text-shadow:none">{_e(val)}</div>'
           + f'<div class="big" style="top:{460 + (96 - _fit(lab, 96, 440)) / 2}px;font-size:{_fit(lab, 96, 440)}px;color:#281e3c;text-shadow:none">{_e(lab)}</div></div>',
           "".join(f'<div class="hook" style="left:{540 + dx - 14}px"></div>' for dx in (-150, 150))]
    js = ['tl.fromTo("#cring", {xPercent: -50, yPercent: -50, scale: 0}, {xPercent: -50, yPercent: -50, scale: 1, duration: 0.5, ease: "back.out(1.6)"}, 0.05);\n',
          'tl.fromTo("#sheet", {y: -900, rotation: -12}, {y: 0, rotation: 0, duration: 0.6, ease: "bounce.out"}, 0.05);\n',
          'tl.fromTo(".hook", {y: -900}, {y: 0, duration: 0.6, ease: "bounce.out"}, 0.05);\n',
          _count_js("#cval", val, 0.3, 0.8)]
    return els, js


BUILD = {"number": _number, "question": _question, "badge": _badge, "round": _round, "versus": _versus, "score": _score,
         "compare": _compare, "share": _share, "timer": _timer, "calendar": _calendar}


# ------------------------------------------------------------------ Seite

CSS = """
@font-face { font-family: "AS Anton"; src: url("assets/fonts/Anton-Regular.ttf"); }
@font-face { font-family: "AS Poppins"; font-weight: 600; src: url("assets/fonts/Poppins-SemiBold.ttf"); }
@font-face { font-family: "AS Poppins"; font-weight: 700; src: url("assets/fonts/Poppins-Bold.ttf"); }
:root { --display: "AS Anton", "League Gothic", "Oswald", sans-serif; --body: "AS Poppins", "Poppins", sans-serif;
        --gold: %(gold)s; --orange: %(orange)s; --ink: %(ink)s; }
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { width: 1080px; height: 1920px; overflow: hidden; background: %(c1)s; }
#root { position: absolute; inset: 0; overflow: hidden; background: radial-gradient(ellipse 120%% 62%% at 50%% 22%%, %(c0)s 0%%, %(c1)s 100%%); }
#stage { position: absolute; inset: 0; }
.dot { position: absolute; border-radius: 50%%; background: #e6e2ff; }
.bokeh { position: absolute; border-radius: 50%%; background: radial-gradient(circle, rgba(200,180,255,.32), rgba(200,180,255,0) 70%%); }
.big { position: absolute; left: 0; width: 1080px; text-align: center; font-family: var(--display); color: #faf8ff; line-height: 1;
       white-space: nowrap; text-shadow: 6px 10px 0 rgba(0,0,0,.35); }
.body { position: absolute; left: 0; width: 100%%; text-align: center; font-family: var(--body); font-weight: 700; color: #faf8ff; white-space: nowrap; line-height: 1.1; }
.kicker { position: absolute; left: 0; width: 1080px; text-align: center; font-family: var(--body); font-weight: 600; color: #d6d0ff; letter-spacing: .18em; white-space: nowrap; }
.pill { position: absolute; padding: 12px 30px 10px; border-radius: 26px; border: 6px solid %(ink)s; box-shadow: 6px 9px 0 rgba(0,0,0,.4); white-space: nowrap; line-height: 1; }
.ring { position: absolute; border-radius: 50%%; border: 14px solid var(--gold); }
.rays { position: absolute; width: 3000px; height: 3000px; margin: -1500px 0 0 -1500px; border-radius: 50%%;
        background: repeating-conic-gradient(rgba(255,220,120,.14) 0deg 10deg, rgba(255,220,120,0) 10deg 22.5deg);
        -webkit-mask: radial-gradient(circle, #000 0%%, #000 30%%, transparent 70%%); }
.star { position: absolute; width: 60px; height: 60px; margin: -30px 0 0 -30px; font-size: 58px; line-height: 60px; text-align: center; color: var(--gold); }
.stripes { position: absolute; left: -200px; top: 0; width: 1900px; height: 100%%;
           background: repeating-linear-gradient(-55deg, rgba(20,60,20,.28) 0 40px, rgba(0,0,0,0) 40px 90px);
           -webkit-mask: linear-gradient(#000 0 40px, transparent 40px 440px, #000 440px); }
#split { position: absolute; inset: 0; background: rgba(255,140,30,.65); clip-path: polygon(640px 0, 1080px 0, 1080px 1920px, 440px 1920px); }
#splitline { position: absolute; inset: 0; background: rgba(255,236,190,.9); clip-path: polygon(635px 0, 645px 0, 445px 1920px, 435px 1920px); }
.cbar { position: absolute; width: 240px; border-radius: 26px; border: 8px solid %(ink)s; box-shadow: 8px 12px 0 rgba(0,0,0,.4); }
.box .big, .box .body { left: 0; width: 100%%; }
.person { position: absolute; }
.person > div { position: absolute; inset: 0; }
.seg { position: absolute; top: 930px; width: 22px; height: 26px; border-radius: 6px; background: #463c82; }
.hook { position: absolute; top: 426px; width: 28px; height: 74px; border-radius: 10px; background: #3c3850; border: 5px solid %(ink)s; }
"""

JS_HELPERS = r"""
function fmtDE(v, dec, grp) {
  var s = v.toFixed(dec), parts = s.split("."), w = parts[0];
  if (grp) w = w.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return w + (dec ? "," + parts[1] : "");
}
function countUp(sel, value, tl, start, dur) {
  var m = /^(\D*?)(\d[\d.]*)(,\d+)?(.*)$/.exec(value);
  if (!m) return;
  var dec = m[3] ? m[3].length - 1 : 0, grp = m[2].indexOf(".") >= 0;
  var target = parseFloat(m[2].replace(/\./g, "") + (m[3] ? m[3].replace(",", ".") : ""));
  if (!isFinite(target)) return;
  var el = document.querySelector(sel), o = {v: 0};
  var put = function () { el.textContent = m[1] + fmtDE(dec ? o.v : Math.round(o.v), dec, grp) + m[4]; };
  tl.fromTo(o, {v: 0}, {v: target, duration: dur, ease: "power2.out", onUpdate: put, onStart: put}, start);
}
function countDown(sel, total, tl, start, dur) {
  var el = document.querySelector(sel), o = {r: 0};
  var put = function () {
    var cur = Math.max(0, total - Math.floor(o.r * o.r * 2600));
    var p = function (n) { return (n < 10 ? "0" : "") + n; };
    el.textContent = p(Math.floor(cur / 3600)) + ":" + p(Math.floor(cur % 3600 / 60)) + ":" + p(cur % 60);
  };
  tl.fromTo(o, {r: 0}, {r: Math.max(0.01, dur - start), duration: Math.max(0.01, dur - start), ease: "none", onUpdate: put}, start);
}
"""


def page(g, dur, mood=""):
    """Komplette HTML-Seite (index.html) für eine Grafik-Szene."""
    import random
    c0, c1 = THEMES.get(mood if mood in THEMES else "", THEMES[""])
    els, js = BUILD[g["type"]](g, dur)
    rnd = random.Random(7)
    dots = "".join(f'<div class="dot" style="left:{rnd.randint(0, W)}px;top:{rnd.randint(0, 1100)}px;width:{2 * r}px;height:{2 * r}px"></div>'
                   for r in [rnd.choice((2, 2, 3)) for _ in range(46)])
    rb = random.Random(3)
    bok = []
    bjs = []
    cols = ("170,120,255", "255,120,190", "110,150,255", "255,170,90", "150,110,255")
    for i in range(14):
        x, y, r = rb.random() * W, rb.random() * H, 40 + rb.random() * 90
        c = cols[i % len(cols)]
        bok.append(f'<div id="bk{i}" class="bokeh" style="left:{x - r:.0f}px;top:{y - r:.0f}px;width:{2 * r:.0f}px;height:{2 * r:.0f}px;'
                   f'background:radial-gradient(circle, rgba({c},.34) 0%, rgba({c},.22) 55%, rgba({c},0) 72%)"></div>')
        bjs.append(f'tl.fromTo("#bk{i}", {{y: 0}}, {{y: {-40 - rb.random() * 80:.0f}, duration: {dur:.2f}, ease: "none"}}, 0);\n')
    camera = (f'tl.fromTo("#stage", {{scale: 1.0}}, {{scale: 1.045, transformOrigin: "540px 760px", duration: {dur:.2f}, ease: "sine.inOut"}}, 0);\n'
              f'tl.fromTo("#flash", {{opacity: 0.55}}, {{opacity: 0, duration: 0.25, ease: "power2.out"}}, 0);\n')
    return f"""<!doctype html>
<html lang="de">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width={W}, height={H}">
<script src="{GSAP}"></script>
<style>{CSS % {"gold": GOLD, "orange": ORANGE, "ink": INK, "c0": c0, "c1": c1}}</style>
</head>
<body>
<div id="root" class="clip" data-composition-id="main" data-start="0" data-duration="{dur:.3f}" data-width="{W}" data-height="{H}" data-track-index="0">
  <div id="sky" style="position:absolute;inset:0">{dots}{"".join(bok)}</div>
  <div id="stage">{"".join(els)}</div>
  <div id="flash" style="position:absolute;inset:0;background:#fff;opacity:0"></div>
</div>
<script>
{JS_HELPERS}
const tl = gsap.timeline({{paused: true}});
{"".join(bjs)}{camera}{"".join(js)}
window.__timelines["main"] = tl;
tl.seek(0);
</script>
</body>
</html>
"""


def _fonts_into(proj: Path):
    dst = proj / "assets" / "fonts"
    dst.mkdir(parents=True, exist_ok=True)
    for name in ("Anton-Regular.ttf", "Poppins-SemiBold.ttf", "Poppins-Bold.ttf"):
        for src in (FONTS / name, Path("/usr/share/fonts/truetype/google-fonts") / name):
            if src.exists():
                shutil.copy(src, dst / name)
                break


def render(g, dur, out: Path, mood="", still: Path = None, timeout=240):
    """Rendert die Grafik-Szene nach out (1080×1920, 30 fps, genau dur Sekunden). True bei Erfolg, sonst False (dann zeichnet
    graphics.py die Szene). Ein Bild nach 1 s landet in still (für die Prüf-Übersicht)."""
    if not handles(g):
        return False
    cmd = _cmd()
    n = max(2, round(dur * FPS))
    with tempfile.TemporaryDirectory(prefix="hyper_") as tmp:
        proj = Path(tmp) / "g"
        proj.mkdir()
        (proj / "index.html").write_text(page(g, n / FPS, mood), encoding="utf-8")
        (proj / "package.json").write_text('{"name": "g", "private": true, "type": "module"}', encoding="utf-8")
        _fonts_into(proj)
        raw = Path(tmp) / "raw.mp4"
        env = dict(os.environ, HYPERFRAMES_NO_TELEMETRY="1", DO_NOT_TRACK="1", CI="1")
        t_start = time.time()
        try:
            p = subprocess.run([*cmd, "render", str(proj), "-o", str(raw), "--fps", str(FPS), "--quality", "looks", "--resolution", "portrait"],
                               capture_output=True, text=True, timeout=timeout, env=env, cwd=tmp)
        except (OSError, subprocess.TimeoutExpired) as e:
            _note(f"HyperFrames nicht ausgeführt: {e}")
            return False
        finally:
            _state["spent"] = _state.get("spent", 0.0) + time.time() - t_start
        if p.returncode != 0 or not raw.exists() or raw.stat().st_size < 1000:
            _note("HyperFrames-Rendern fehlgeschlagen: " + (p.stderr or p.stdout or "")[-600:])
            return False
        # auf exakt n Bilder bei 30 fps bringen (die Szene wird später mit anderen Clips verbunden)
        q = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(raw), "-vf",
                            f"fps={FPS},scale={W}:{H}:flags=lanczos,tpad=stop_mode=clone:stop_duration=2,setsar=1,format=yuv420p",
                            "-frames:v", str(n), "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", str(out)], capture_output=True, text=True)
        if q.returncode != 0:
            _note("HyperFrames-Clip nicht umwandelbar: " + q.stderr[-400:])
            return False
        _state["fails"] = 0
        if still is not None:
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{min(1.0, (n - 1) / FPS):.2f}", "-i", str(out),
                            "-frames:v", "1", "-q:v", "3", str(still)], capture_output=True)
    return True


def _note(msg):
    _state["fails"] = _state.get("fails", 0) + 1
    if _state["fails"] >= 2:                     # zweimal hintereinander kaputt: für diesen Lauf abschalten, nicht jede Szene warten
        _state["broken"] = True
    try:
        from .state import log
        log(msg)
    except Exception:  # noqa: BLE001
        print(msg)
