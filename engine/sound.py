"""Klang-Bibliothek der Videos: echte Soundeffekte statt ffmpeg-Pieptönen.

Quellen (einmal mit der Aktion `sounds` gebaut und im Repository gespeichert, danach in jedem Video ohne Netz nutzbar):
- earshot (github.com/Leonxlnx/earshot, MIT): 252 im Code gebaute, gemessene Soundeffekte – Whoosh, Pop, Cut-Hit, Klick,
  Glockenspiel, Kamera-Verschluss, Tropfen, Riser … Je Rolle mehrere Takes; zu jedem Take merken wir uns, wo der Klang
  beginnt (onset) und wo er am lautesten ist (peak), damit er bildgenau sitzt.
- Openverse (api.openverse.org, ohne Schlüssel): echte Aufnahmen unter CC0/Public Domain – Regen, Wind, Gewitter, Stadt,
  Wald, Meer, Nacht … als leiser Hintergrund passend zum Ort und Wetter, dazu freie Musik je Video-Art.

Platzierung nach den Regeln von real-sfx (github.com/Clipwing/skills): jedes Geräusch hat seinen Platz zum Schnitt
(ein Whoosh ist 37 ms NACH dem Schnitt am lautesten, ein Pop setzt 30 ms danach ein, ein Tippen 60 ms davor), einen
Mindestabstand zur Wiederholung, eine Lautstärke über der Musik und unter der Stimme – und nichts wird doppelt gelegt."""
import json
import random
import re
import shutil
import subprocess
import time
from pathlib import Path

import requests

from .state import ROOT, log

LIB = ROOT / "assets" / "sfx"
MANIFEST = LIB / "manifest.json"
MUSIC_DIR = ROOT / "music"
EARSHOT_REF = "4ac3d2ac2b151e1c23376f9ce7f3047a17050013"   # geprüfter Stand von earshot (MIT)

# Rolle → earshot-Klänge (Kategorie/Mitglied). Je Klang werden zwei Takes gerendert (das Original und eine Variante).
EARSHOT = {
    "whoosh": ["whoosh_fast/crisp", "whoosh_fast/tight", "whoosh_fast/whip", "whoosh_big/thump_airy"],
    "swish": ["swish/bright", "swish/flick", "swish/soft", "fit/whoosh.short/bamboo_swish"],
    "pop": ["ui_pop/soft", "ui_pop/boop", "pro_pop_in/round", "pro_pop_in/airy", "fit/pop/lip_pop"],
    "hit": ["cut_hit/punch", "cut_hit/kick", "cut_hit/sub"],
    "boom": ["cut_hit/rumble", "pro_sub_drop/quick", "pro_impact/short"],
    "ding": ["mallet/glock", "mallet/celesta", "pro_notify/ding_1930", "notify/mid_tine"],
    "tick": ["pro_hover_tick/soft", "fit/tick/domino", "pro_click/tink"],
    "shutter": ["shutter/quick", "shutter/snap"],
    "knock": ["knock/wood", "knock/desk", "fit/hit/bamboo_tok"],
    "stamp": ["whoosh_big/thump", "knock/double"],
    "glitch": ["glitch/mid", "glitch/chirp"],
    "riser": ["riser/snatch", "riser/dark"],
    "swell": ["reverse_swell/short", "reverse_swell/cymbal"],
    "drip": ["drip/drop", "drip/plink"],
    "type": ["pro_typing_run/soft"],
    "bell": ["fit/bell/small_bell"],
}
# Lage zum Ereignis (Sekunden): Bezugspunkt im Klang ("onset" = Einsatz, "peak" = lautester Moment) und Versatz zum Bild.
# Werte aus earshot/real-sfx (Mediane aus professionellen Filmen).
ANCHOR = {"whoosh": ("peak", 0.037), "swish": ("peak", 0.030), "swell": ("peak", 0.042), "riser": ("peak", 0.0),
          "pop": ("onset", 0.030), "tick": ("onset", -0.011), "knock": ("onset", -0.040), "drip": ("onset", 0.0),
          "hit": ("onset", 0.0), "boom": ("onset", 0.0), "ding": ("onset", 0.0), "shutter": ("onset", -0.011),
          "stamp": ("onset", 0.030), "glitch": ("onset", 0.0), "type": ("onset", 0.0), "bell": ("onset", 0.0)}
GAIN = {"whoosh": 0.42, "swish": 0.26, "pop": 0.34, "hit": 0.5, "boom": 0.55, "ding": 0.26, "tick": 0.3, "shutter": 0.32,
        "knock": 0.38, "stamp": 0.5, "glitch": 0.3, "riser": 0.3, "swell": 0.32, "drip": 0.3, "type": 0.25, "bell": 0.22}
MIN_GAP = {"pop": 0.114, "tick": 0.066, "type": 0.087}      # so dicht darf dieselbe Rolle aufeinander folgen
GAP_DEFAULT = 0.25

# Openverse: Hintergrund-Geräusche (echte Aufnahmen, CC0/Public Domain) – Rolle → Suchbegriffe
AMBIENCE = {
    "rain": ["rain ambience", "rain on window"], "storm": ["thunderstorm", "thunder rain"], "wind": ["wind howling", "wind ambience"],
    "city": ["city street ambience", "traffic ambience"], "forest": ["forest birds ambience", "birds forest morning"],
    "ocean": ["ocean waves", "sea waves beach"], "night": ["night crickets", "crickets night ambience"],
    "office": ["office ambience", "room tone office"], "crowd": ["crowd ambience", "people talking crowd"],
    "fire": ["fire crackling", "campfire"], "space": ["space ambience drone", "dark ambient drone"],
    "underwater": ["underwater ambience", "underwater bubbles"], "cave": ["cave dripping ambience", "cave ambience"],
}
# Openverse-Musik je Stimmung (CC0/Public Domain) → Ordner music/<Video-Art>/
MUSIC = {
    "spannend": (["suspense cinematic", "tension ambient"], ["whatif", "mysterien", "storys"]),
    "dunkel": (["dark ambient", "horror ambience music"], ["grusel"]),
    "hell": (["happy ukulele", "upbeat acoustic", "cheerful piano"], ["fakten", "tiere", "lustig", "comedy"]),
}
OV = "https://api.openverse.org/v1/audio/"
UA = {"User-Agent": "AutoShorts/1.0 (open source shorts generator)"}


# ------------------------------------------------------------------ Bibliothek lesen

_LIB = None


def library():
    """{"sfx": {Rolle: [{"file", "onset", "peak", "dur"}]}, "amb": {Rolle: [{"file", ...}]}, "credits": [...]} oder leer."""
    global _LIB
    if _LIB is None:
        try:
            _LIB = json.loads(MANIFEST.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _LIB = {}
        for kind in ("sfx", "amb"):
            for role, takes in list((_LIB.get(kind) or {}).items()):
                _LIB[kind][role] = [t for t in takes if (LIB / t["file"]).exists()]
    return _LIB


def take(role, rnd, kind="sfx"):
    takes = (library().get(kind) or {}).get(role) or []
    return rnd.choice(takes) if takes else None


def place(events, total, seed=0):
    """Ereignisse [(Bildzeit s, Rolle)] → Klänge [(Startzeit s, Datei, Lautstärke)]: richtiger Klang-Punkt auf dem Bild,
    Mindestabstände, nichts doppelt (zwei Klänge am selben Moment: der wichtigere bleibt)."""
    rnd = random.Random(seed)
    prio = ["boom", "hit", "stamp", "whoosh", "riser", "swell", "glitch", "shutter", "ding", "bell", "pop", "knock", "drip",
            "swish", "tick", "type"]
    evs = sorted({(round(t, 3), r) for t, r in events if r in GAIN and 0 <= t < total},
                 key=lambda x: (prio.index(x[1]) if x[1] in prio else 99, x[0]))
    kept, out = [], []
    for t, role in evs:
        if any(r == role and abs(t - q) < MIN_GAP.get(role, GAP_DEFAULT) for q, r in kept):
            continue
        if any(abs(t - q) < 0.09 and r != role for q, r in kept) and role in ("swish", "tick", "pop", "drip"):
            continue                                   # kleiner Klang, wo schon ein größerer sitzt: weglassen statt doppeln
        tk = take(role, rnd)
        if not tk:
            continue
        ref, off = ANCHOR.get(role, ("onset", 0.0))
        start = t + off - float(tk.get(ref) or 0.0)
        if start < 0 and t < 0.05:                     # ganz am Anfang: Klang darf nicht vor dem Video liegen
            start = 0.0
        if start < 0:
            continue
        kept.append((t, role))
        out.append((start, str(LIB / tk["file"]), GAIN[role]))
    return sorted(out)


AMB_GAIN = 0.07


def ambience_for(scene):
    """Passendes Hintergrund-Geräusch für eine Szene (Wetter vor Ort; drinnen leiser)."""
    from .toon import places
    w = str(scene.get("weather") or "").lower()
    if w in ("rain", "regen"):
        return "rain"
    if w in ("storm", "gewitter", "thunder"):
        return "storm"
    if w in ("wind", "snow", "schnee"):
        return "wind"
    from .toon import stage
    place = places.resolve(stage.backdrop(scene)) if scene.get("place") or scene.get("backdrop") else ""
    place = place if isinstance(place, str) else ""
    night = str(scene.get("time") or "").lower() in ("night", "nacht", "abend", "evening")
    indoor = bool(place) and place not in places.OUTDOOR
    for keys, role in (((r"street|city|stadt|market|square|station|bus"), "city"),
                       ((r"forest|wald|park|garden|garten|meadow|wiese|jungle|camp"), "forest"),
                       ((r"beach|strand|ocean|sea|meer|harbor|ship|island"), "ocean"),
                       ((r"underwater|reef|deep_sea"), "underwater"), ((r"cave|höhle|mine"), "cave"),
                       ((r"space|weltall|moon|planet"), "space"), ((r"office|büro|classroom|lab"), "office"),
                       ((r"stadium|concert|crowd|mall"), "crowd")):
        if re.search(keys, place or ""):
            if night and role in ("forest", "city") and not indoor:
                return "night"
            return role
    return "night" if night and not indoor and place else ""


# ------------------------------------------------------------------ Bibliothek bauen (Aktion „sounds“)

def _ff(args):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True, capture_output=True)


def _measure(path):
    """Einsatz und lautester Moment (s) eines Klangs, gemessen in 5-ms-Schritten (ohne Zusatzpakete)."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "8000", "-f", "s16le", "-"],
                         capture_output=True).stdout
    import array
    a = array.array("h")
    a.frombytes(raw[: len(raw) // 2 * 2])
    if not a:
        return 0.0, 0.0, 0.0
    hop = 40
    env = [max(abs(x) for x in a[i:i + hop]) for i in range(0, len(a), hop)]
    mx = max(env) or 1
    onset = next(i for i, v in enumerate(env) if v >= mx * 0.0316) * hop / 8000     # −30 dB wie earshot
    peak = env.index(mx) * hop / 8000
    return round(onset, 3), round(peak, 3), round(len(a) / 8000, 3)


def build_earshot(man):
    """Rendert die Rollen aus der earshot-Bank (braucht das Paket earshot; siehe Workflow-Schritt)."""
    try:
        from earshot.forge import bank
    except ImportError as e:
        log(f"earshot nicht installiert ({e}) – Soundeffekte bleiben wie sie sind")
        return 0
    import numpy as np
    from scipy.io import wavfile
    out = LIB / "earshot"
    out.mkdir(parents=True, exist_ok=True)
    sfx, n = {}, 0
    for role, ids in EARSHOT.items():
        for sid in ids:
            for k, seed in enumerate((None, 7)):
                name = re.sub(r"[^a-z0-9]+", "_", f"{role}_{sid}_{k}").strip("_") + ".ogg"
                try:
                    y, meta = bank.render(sid, seed=seed, sr=48000)
                    y = np.asarray(y, dtype=np.float32)
                    tmp = out / "tmp.wav"
                    wavfile.write(str(tmp), 48000, y)
                    _ff(["-i", str(tmp), "-ac", "2", "-ar", "44100", "-c:a", "libvorbis", "-q:a", "5", str(out / name)])
                    tmp.unlink(missing_ok=True)
                except Exception as e:  # noqa: BLE001
                    log(f"earshot {sid}: {str(e)[:120]}")
                    continue
                onset, peak, dur = _measure(out / name)
                sfx.setdefault(role, []).append({"file": f"earshot/{name}", "id": sid, "onset": onset, "peak": peak, "dur": dur})
                n += 1
    man["sfx"] = sfx
    man.setdefault("credits", []).append({"what": "Soundeffekte", "source": "earshot (Leon Lin)", "license": "MIT",
                                          "url": "https://github.com/Leonxlnx/earshot"})
    log(f"earshot: {n} Takes in {len(sfx)} Rollen")
    return n


def ov_search(q, category, lo, hi, n=8):
    """Openverse-Suche: nur CC0 und Public Domain (keine Namensnennung nötig, kommerziell erlaubt), Länge lo..hi s.
    Erst mit Kategorie, dann ohne (viele Aufnahmen haben keine Kategorie)."""
    out, seen = [], 0
    for cat in (category, None):
        params = {"q": q, "license": "cc0,pdm", "page_size": 20}
        if cat:
            params["category"] = cat
        for attempt in range(3):
            r = requests.get(OV, headers=UA, timeout=30, params=params)
            if r.status_code == 429 and attempt < 2:
                time.sleep(30)
                continue
            break
        if r.status_code != 200:
            log(f"Openverse „{q}“: HTTP {r.status_code} {r.text[:120]}")
            continue
        res = r.json().get("results", [])
        seen += len(res)
        for it in res:
            ms = it.get("duration")
            dur = (ms or 0) / 1000
            lic = str(it.get("license") or "").lower()
            if it.get("url") and (ms is None or lo <= dur <= hi) and lic in ("cc0", "pdm") and it["id"] not in [o["id"] for o in out]:
                out.append(it)
        if len(out) >= n:
            break
    log(f"Openverse „{q}“: {seen} Treffer, {len(out)} passend")
    return out[:n]


def _fetch(it, dest, seconds, loudness):
    """Lädt eine Openverse-Aufnahme, schneidet sie auf `seconds` mit weichen Rändern und gleicht die Lautheit an."""
    tmp = dest.with_suffix(".src")
    with requests.get(it["url"], headers=UA, timeout=60, stream=True) as r:
        r.raise_for_status()
        size = 0
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(65536):
                size += len(chunk)
                if size > 40_000_000:
                    raise RuntimeError("Datei zu groß")
                f.write(chunk)
    try:
        _ff(["-i", str(tmp), "-t", str(seconds), "-af",
             f"afade=t=in:d=1.5,afade=t=out:st={max(1.0, seconds - 2.0)}:d=2,loudnorm=I={loudness}:TP=-2",
             "-ac", "2", "-ar", "44100", "-c:a", "libvorbis", "-q:a", "4", str(dest)])
    finally:
        tmp.unlink(missing_ok=True)


def _credit(it, what):
    return {"what": what, "title": it.get("title") or "", "creator": it.get("creator") or "",
            "license": (str(it.get("license") or "") + " " + str(it.get("license_version") or "")).strip().upper(),
            "url": it.get("foreign_landing_url") or it.get("url"), "source": it.get("source") or "openverse"}


def build_openverse(man):
    """Holt Hintergrund-Geräusche und Musik von Openverse (nur CC0/Public Domain)."""
    amb, credits = {}, [c for c in man.get("credits", []) if c.get("source") == "earshot (Leon Lin)"]
    out = LIB / "openverse"
    out.mkdir(parents=True, exist_ok=True)
    for role, queries in AMBIENCE.items():
        got = []
        for q in queries:
            if len(got) >= 2:
                break
            try:
                for it in ov_search(q, "sound_effect", 10, 900):
                    if len(got) >= 2 or any(g["ov"] == it["id"] for g in got):
                        continue
                    dest = out / f"{role}_{str(it['id'])[:8]}.ogg"
                    try:
                        _fetch(it, dest, 40, -24)
                    except Exception as e:  # noqa: BLE001
                        log(f"Openverse {role}: {str(e)[:100]}")
                        continue
                    got.append({"file": f"openverse/{dest.name}", "ov": it["id"], "dur": _measure(dest)[2]})
                    credits.append(_credit(it, f"Geräusch {role}"))
            except Exception as e:  # noqa: BLE001
                log(f"Openverse-Suche „{q}“: {str(e)[:120]}")
            time.sleep(2)
        if got:
            amb[role] = got
    man["amb"] = amb
    music_n = 0
    for mood, (queries, slugs) in MUSIC.items():
        got = 0
        for q in queries:
            if got >= 3:
                break
            try:
                for it in ov_search(q, "music", 45, 600):
                    if got >= 3:
                        break
                    for slug in slugs:
                        (MUSIC_DIR / slug).mkdir(parents=True, exist_ok=True)
                    dest = MUSIC_DIR / slugs[0] / f"openverse_{str(it['id'])[:8]}.ogg"
                    try:
                        _fetch(it, dest, 75, -20)
                    except Exception as e:  # noqa: BLE001
                        log(f"Openverse-Musik: {str(e)[:100]}")
                        continue
                    for slug in slugs[1:]:
                        shutil.copy(dest, MUSIC_DIR / slug / dest.name)
                    credits.append(_credit(it, f"Musik ({mood})"))
                    got += 1
                    music_n += 1
            except Exception as e:  # noqa: BLE001
                log(f"Openverse-Musiksuche „{q}“: {str(e)[:120]}")
            time.sleep(2)
    man["credits"] = credits
    log(f"Openverse: {sum(len(v) for v in amb.values())} Geräusche in {len(amb)} Rollen, {music_n} Musikstücke")


def build():
    """Aktion `sounds`: Bibliothek neu bauen und Liste schreiben (assets/sfx/manifest.json, Quellen in CREDITS.md)."""
    global _LIB
    LIB.mkdir(parents=True, exist_ok=True)
    try:
        man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        man = {}
    build_earshot(man)
    try:
        build_openverse(man)
    except Exception as e:  # noqa: BLE001
        log(f"Openverse: {e}")
    man["updated"] = time.time()
    MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = ["# Klang-Quellen", "", "Alle Klänge sind frei nutzbar (MIT bzw. CC0/Public Domain). Automatisch erstellt.", ""]
    for c in man.get("credits", []):
        lines.append(f"- {c.get('what')}: {c.get('title') or c.get('source')}"
                     + (f" von {c['creator']}" if c.get("creator") else "") + f" ({c.get('license')}) {c.get('url') or ''}")
    (LIB / "CREDITS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    _LIB = None
    return man
