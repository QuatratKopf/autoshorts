"""Lernende Bibliothek: Gegenstände, die der Engine fehlen, werden als einfache Vektor-Zeichnung beschrieben
(Rechtecke, Ellipsen, Vielecke, Linien – keine ausführbaren Programme), geprüft, in docs/data/shapes.json gespeichert
und stehen danach wie eingebaute Requisiten zur Verfügung: in echter Größe, als Großaufnahme und für alle späteren Videos.

Format je Gegenstand (Zeichenfläche 400×400, y nach unten, Unterkante y=400 ist der Boden):
  {"name": "wasserturm", "aliases": ["water tower"], "height_m": 30, "sky": false, "anim": "none|bob|pulse",
   "shapes": [{"t": "rect", "x": 150, "y": 60, "w": 100, "h": 90, "r": 10, "c": "#9aa3b2"},
              {"t": "ellipse", "cx": 200, "cy": 60, "rx": 60, "ry": 20, "c": "#b9c2d0"},
              {"t": "poly", "p": [[150, 150], [120, 400], [140, 400]], "c": "#6b7280"},
              {"t": "line", "p": [[160, 200], [240, 260]], "c": "#16161a", "w": 6}]}"""
import json
import math
import re

from PIL import ImageDraw

from . import extras
from .places import GROUND

INK = (22, 22, 26)
LIB = {}
MAX_SHAPES = 60
BOX = 400


def _col(v, default=(150, 156, 170)):
    if isinstance(v, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", v.strip()):
        v = v.strip()
        return tuple(int(v[i:i + 2], 16) for i in (1, 3, 5))
    if isinstance(v, (list, tuple)) and len(v) == 3 and all(isinstance(c, (int, float)) and not isinstance(c, bool) for c in v):
        return tuple(max(0, min(255, int(c))) for c in v)
    return default


def _n(v, lo=-60.0, hi=BOX + 60.0, default=0.0):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v:
        return default
    return max(lo, min(hi, float(v)))


def _pts(v):
    out = []
    for q in (v if isinstance(v, (list, tuple)) else [])[:40]:
        if isinstance(q, (list, tuple)) and len(q) == 2:
            out.append((_n(q[0]), _n(q[1])))
    return out


def clean(item):
    """Prüft und bereinigt eine Beschreibung; gibt die saubere Fassung zurück oder None, wenn sie unbrauchbar ist."""
    if not isinstance(item, dict) or not isinstance(item.get("name"), str):
        return None
    name = re.sub(r"[^a-zäöüß0-9 \-]", "", item["name"].lower()).strip()[:30]
    if len(name) < 2:
        return None
    shapes = []
    for sh in (item.get("shapes") if isinstance(item.get("shapes"), list) else [])[:MAX_SHAPES]:
        if not isinstance(sh, dict):
            continue
        t = str(sh.get("t") or "").lower()
        c = _col(sh.get("c"))
        o = sh.get("o") is not False
        if t == "rect":
            w, h = _n(sh.get("w"), 2, BOX + 100, 0), _n(sh.get("h"), 2, BOX + 100, 0)
            if w and h:
                shapes.append({"t": "rect", "x": _n(sh.get("x")), "y": _n(sh.get("y")), "w": w, "h": h, "r": _n(sh.get("r"), 0, 200, 0), "c": c, "o": o})
        elif t == "ellipse":
            rx, ry = _n(sh.get("rx"), 1, BOX, 0), _n(sh.get("ry"), 1, BOX, 0)
            if rx and ry:
                shapes.append({"t": "ellipse", "cx": _n(sh.get("cx")), "cy": _n(sh.get("cy")), "rx": rx, "ry": ry, "c": c, "o": o})
        elif t == "poly":
            p = _pts(sh.get("p"))
            if len(p) >= 3:
                shapes.append({"t": "poly", "p": p, "c": c, "o": o})
        elif t == "line":
            p = _pts(sh.get("p"))
            if len(p) >= 2:
                shapes.append({"t": "line", "p": p, "c": c, "w": _n(sh.get("w"), 2, 40, 8)})
    if len(shapes) < 2:
        return None
    ys = [y for sh in shapes for y in ([sh["y"], sh["y"] + sh["h"]] if sh["t"] == "rect" else [sh["cy"] - sh["ry"], sh["cy"] + sh["ry"]] if sh["t"] == "ellipse" else [q[1] for q in sh["p"]])]
    xs = [x for sh in shapes for x in ([sh["x"], sh["x"] + sh["w"]] if sh["t"] == "rect" else [sh["cx"] - sh["rx"], sh["cx"] + sh["rx"]] if sh["t"] == "ellipse" else [q[0] for q in sh["p"]])]
    if max(ys) - min(ys) < 40 or max(xs) - min(xs) < 20:
        return None
    aliases = [re.sub(r"[^a-zäöüß0-9 \-]", "", a.lower()).strip()[:30] for a in (item.get("aliases") if isinstance(item.get("aliases"), list) else []) if isinstance(a, str)]
    return {"name": name, "aliases": [a for a in aliases if len(a) > 1 and a != name][:6],
            "height_m": _n(item.get("height_m"), 0.1, 80, 1.0), "sky": item.get("sky") is True,
            "anim": item.get("anim") if item.get("anim") in ("bob", "pulse") else "none",
            "shapes": shapes, "shift": BOX - max(ys), "mid": (min(xs) + max(xs)) / 2}


def _drawer(item):
    def fn(d, x, t, s=1.0):
        k = 1.25                                                   # Zeichenfläche 400 → 500 Bildpunkte
        oy = GROUND - BOX * k + item["shift"] * k                  # Unterkante der Zeichnung steht auf dem Boden
        if item["sky"]:
            oy = 520 - (BOX - item["shift"]) * k / 2 + math.sin(t * 1.4) * 14
        elif item["anim"] == "bob":
            oy -= abs(math.sin(t * 3)) * 14
        ox = x - item["mid"] * k
        g = 1 + (0.04 * math.sin(t * 5) if item["anim"] == "pulse" else 0)

        def P(px_, py_):
            return (ox + (item["mid"] + (px_ - item["mid"]) * g) * k, oy + py_ * k)
        for sh in item["shapes"]:
            c, w = tuple(sh["c"]), (7 if sh.get("o", True) else 0)
            if sh["t"] == "rect":
                a, b = P(sh["x"], sh["y"]), P(sh["x"] + sh["w"], sh["y"] + sh["h"])
                d.rounded_rectangle((a[0], a[1], b[0], b[1]), min(sh["r"] * k, (b[0] - a[0]) / 2, (b[1] - a[1]) / 2), fill=c, outline=INK if w else None, width=w)
            elif sh["t"] == "ellipse":
                a, b = P(sh["cx"] - sh["rx"], sh["cy"] - sh["ry"]), P(sh["cx"] + sh["rx"], sh["cy"] + sh["ry"])
                d.ellipse((a[0], a[1], b[0], b[1]), fill=c, outline=INK if w else None, width=w)
            elif sh["t"] == "poly":
                d.polygon([P(*q) for q in sh["p"]], fill=c, outline=INK if w else None, width=w)
            else:
                d.line([P(*q) for q in sh["p"]], fill=c, width=int(sh["w"] * k), joint="curve")
    return fn


def _depth_y(h):
    return 1262 if h <= 1.2 else 1245 if h <= 2.4 else 1215 if h <= 5 else 1130 if h <= 10 else 1010


def register(item):
    """Macht einen geprüften Gegenstand als Requisite verfügbar (eingebaute Requisiten werden nie überschrieben)."""
    name = item["name"]
    key = "lib_" + re.sub(r"[^a-z0-9]", "_", name.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss"))
    extras.PROPS[key] = _drawer(item)
    for alias in [name] + item["aliases"]:
        if alias not in extras.PROPS and alias not in extras.PROP_ALIASES and alias not in extras.HELD:
            extras.PROP_ALIASES[alias] = key
    if item["sky"]:
        extras.SKY = tuple(extras.SKY) + (key,)
    else:
        from .places import PX_M, depth
        y = _depth_y(item["height_m"]) if item["height_m"] <= 10 else 935
        extras.SIZES[key] = (min(item["height_m"], 1050 / (PX_M * depth(y))), y)      # sehr Hohes bleibt im Bild
    LIB[name] = dict(item, key=key)
    return key


def load_all(data):
    """data = Inhalt von shapes.json ({name: Beschreibung})."""
    n = 0
    for raw in (data.values() if isinstance(data, dict) else []):
        item = clean(raw)
        if item:
            register(item)
            n += 1
    return n


def names():
    return sorted(LIB)


def text_props():
    """(Suchmuster, Requisite) für die Regie: Wird ein gelernter Gegenstand im Satz genannt, erscheint er im Bild."""
    out = []
    for name, item in LIB.items():
        words = [name] + item["aliases"]
        pat = "|".join(r"\b" + re.escape(w.replace("-", " ")).replace(r"\ ", r"[ -]?") for w in words if len(w) > 2)
        if pat:
            out.append((pat, item["key"]))
    return out


PROMPT = """Du zeichnest einfache, flache Vektor-Gegenstände für Cartoon-Erklärvideos. Antworte NUR mit JSON.
Zeichenfläche 400×400 (x nach rechts, y nach unten). Der Gegenstand steht auf dem Boden bei y=400 und ist mittig (x≈200).
Nutze 6 bis 25 Formen, große klare Flächen, kräftige aber nicht grelle Farben; spätere Formen liegen über früheren.
Formen: {"t":"rect","x":..,"y":..,"w":..,"h":..,"r":Eckenradius,"c":"#rrggbb"} · {"t":"ellipse","cx":..,"cy":..,"rx":..,"ry":..,"c":"#rrggbb"}
        {"t":"poly","p":[[x,y],...],"c":"#rrggbb"} · {"t":"line","p":[[x,y],...],"c":"#16161a","w":Breite}
Jede Fläche bekommt automatisch einen dunklen Umriss ("o": false schaltet ihn ab, z. B. für Glanzlichter).
Antwortformat: {"name": "<deutscher Name, klein>", "aliases": ["weitere Wörter, auch Mehrzahl"], "height_m": <echte Höhe in Metern>,
 "sky": <true nur für Dinge am Himmel>, "anim": "none" | "bob" | "pulse", "shapes": [ ... ]}
Wenn das Gewünschte kein einzelner greifbarer Gegenstand ist (ein Ort, ein Wetter, ein Gefühl, ein Vorgang) oder eine echte Person,
eine Marke oder ein Logo wäre, antworte mit {"skip": true}.
Beispiel Wasserturm: {"name":"wasserturm","aliases":["wassertürme","water tower"],"height_m":30,"sky":false,"anim":"none","shapes":[
 {"t":"poly","p":[[150,170],[120,400],[145,400],[170,170]],"c":"#6b7280"},{"t":"poly","p":[[230,170],[255,400],[280,400],[250,170]],"c":"#6b7280"},
 {"t":"rect","x":185,"y":170,"w":30,"h":230,"c":"#8b93a1"},{"t":"line","p":[[150,290],[250,290]],"c":"#4b5563","w":8},
 {"t":"rect","x":110,"y":60,"w":180,"h":115,"r":14,"c":"#5aa7e0"},{"t":"poly","p":[[105,62],[200,10],[295,62]],"c":"#c2504a"},
 {"t":"rect","x":130,"y":100,"w":140,"h":18,"c":"#e8f1fa","o":false}]}"""


def learn(wishes, chat_json, known, log=print, limit=3):
    """Lässt fehlende Gegenstände zeichnen. wishes: Wörter aus dem Drehbuch; known: bisheriger Inhalt von shapes.json.
    Gibt die neu gelernten Beschreibungen zurück ({name: Beschreibung})."""
    new = {}
    for wish in [w for w in wishes if isinstance(w, str)][:6]:
        w = wish.strip().lower()
        if len(new) >= limit or len(w) < 3 or w in LIB or w in extras.PROPS or w in extras.PROP_ALIASES or w in extras.HELD or w in known:
            continue
        try:
            js, _ = chat_json(PROMPT, f"Zeichne: {wish}", 0.6)
        except Exception as e:  # noqa: BLE001
            log(f"Bibliothek: „{wish}“ konnte nicht gezeichnet werden ({e})")
            continue
        if isinstance(js, dict) and js.get("skip"):
            continue
        if isinstance(js, dict):
            js["name"] = w                                        # unter dem gewünschten Wort ablegen
        item = clean(js)
        if not item:
            log(f"Bibliothek: Zeichnung für „{wish}“ war unbrauchbar")
            continue
        try:                                                      # Probe zeichnen, bevor etwas gespeichert wird
            from PIL import Image
            lay = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
            _drawer(item)(ImageDraw.Draw(lay, "RGBA"), 540, 1.0)
            box = lay.getbbox()
            if not box or (box[2] - box[0]) < 40 or (box[3] - box[1]) < 40:
                raise ValueError("leer")
        except Exception as e:  # noqa: BLE001
            log(f"Bibliothek: Zeichnung für „{wish}“ ließ sich nicht zeichnen ({e})")
            continue
        register(item)
        new[item["name"]] = json.loads(json.dumps({k: v for k, v in item.items() if k not in ("shift", "mid")}))
        new[item["name"]]["auto"] = True          # vorläufige KI-Zeichnung – wird beim nächsten Ausbau geprüft und ersetzt
        log(f"Bibliothek: „{item['name']}“ neu gelernt ({len(item['shapes'])} Formen, {item['height_m']:g} m)")
    return new
