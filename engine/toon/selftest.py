"""Selbsttest der Engine: zeichnet jeden Ort, jeden Baustein, jede Requisite, jedes Wesen, jede Aktion, jedes Gefühl,
jedes Symbol, jede Menschenmenge, jedes Wetter und jede Einblendung einmal – und füttert die Regie mit kaputten
Drehbüchern. Bricht mit Fehlerliste ab, wenn irgendetwas nicht zeichenbar ist.   python -m engine.toon.selftest"""
import random
import sys
import traceback

from . import extras, places, rig, stage
from .. import overlays

errors = []
count = [0]


def check(name, fn):
    count[0] += 1
    try:
        return fn()
    except Exception:  # noqa: BLE001
        errors.append(name + "\n" + traceback.format_exc(limit=4))


def frame(scene, cast=None, t=1.3):
    cast = cast or {"du": {"shirt": "blau"}, "tom": {"shirt": "rot", "hat": "cap"}, "rex": {"kind": "dino"}}
    place, night, scale, actors, props, weather = stage._prepare(scene, cast)
    bd = stage.backdrop(scene)
    bg = places.background(bd, night, bool(scene.get("dark_city")))
    opt = {"crowd": scene.get("crowd"), "mood": str(scene.get("mood") or "").lower(), "spec": places.spec_of(bd),
           "sky": places.sky_mask(bd, night, bool(scene.get("dark_city"))), "no_traffic": bool(scene.get("no_traffic")),
           "win": scene.get("_win"), "count": scene.get("_count")}
    shot = str(scene.get("shot") or "")
    if shot == "insert":
        return stage._insert_frame([k for k, _ in props][:2], t, 3.0, opt["mood"])
    return stage._frame(bg, place, night, scale, actors, props, weather, t, 3.0, (), 0.0, place == "bedroom",
                        shot if shot == "close" else "", 1.5 if shot == "event" else 1.15, opt)


def main():
    try:                                                       # gelernte Gegenstände mitprüfen
        import json
        from pathlib import Path
        from . import library
        f = Path(__file__).resolve().parents[2] / "docs" / "data" / "shapes.json"
        if f.exists():
            print("Bibliothek:", library.load_all(json.loads(f.read_text(encoding="utf-8"))), "Gegenstände")
    except Exception as e:  # noqa: BLE001
        errors.append(f"Bibliothek laden: {e}")
    all_places = sorted(set(places.PLACES) | set(places.OUTDOOR_SPECS))
    for pl in all_places:
        for night, dark in ((False, False), (True, False), (True, True)):
            check(f"Ort {pl} nacht={night} dunkel={dark}", lambda: places.background(pl, night, dark))
        check(f"Szene an Ort {pl}", lambda: frame({"place": pl, "actors": [{"id": "du", "action": "talk", "speaks": True}], "crowd": "walk"}))
        check(f"Leere Szene an Ort {pl}", lambda: frame({"place": pl, "actors": [], "crowd": "panic", "mood": "panic", "no_traffic": True}))
    for el in sorted(set(places.BACK) | set(places.MID) | set(places.FRONT_EL)):
        for sky in ("", "night", "sunset", "storm", "red", "haze"):
            check(f"Baustein {el} Himmel {sky}", lambda: frame({"backdrop": {"sky": sky, "elements": [el]}, "actors": []}))
    for g in places.GROUNDS:
        check(f"Boden {g}", lambda: frame({"backdrop": {"ground": g, "elements": ["hills"]}, "crowd": "walk", "actors": []}))
    for name in sorted(set(extras.PROPS) | set(extras.PROP_ALIASES)):
        for pl in ("street", "kitchen", "park"):
            for t in (0.05, 1.0, 4.0):
                check(f"Requisite {name} in {pl} t={t}", lambda: frame({"place": pl, "props": [name], "actors": [{"id": "du"}]}, t=t))
        check(f"Requisite {name} als Ereignis", lambda: frame({"place": "desert", "props": [name, "meteor"], "actors": [], "shot": "event"}))
        check(f"Requisite {name} als Einschub", lambda: frame({"place": "kitchen", "props": [name], "actors": [], "shot": "insert"}))
    for kind in extras.CREATURES:
        for mood in ("", "shocked", "sad"):
            check(f"Wesen {kind} {mood}", lambda: frame({"place": "park", "actors": [{"id": "x", "kind": kind, "emotion": mood, "speaks": True}]}))
    actions = ("idle", "talk", "walk", "run", "wave", "point", "shocked", "sad", "jump", "think", "sit", "sleep", "dance", "look_around", "fall", "unbekannt", "")
    emotions = ("", "happy", "sad", "angry", "scared", "worried", "shocked", "tired", "unbekannt")
    for a in actions:
        for e in emotions:
            for t in (0.0, 0.7, 2.9):
                check(f"Aktion {a} Gefühl {e} t={t}", lambda: frame({"place": "livingroom", "actors": [{"id": "du", "action": a, "emotion": e, "speaks": True}]}, t=t))
        check(f"Aktion {a} mit Weg", lambda: frame({"place": "street", "actors": [{"id": "du", "action": a, "pos": "offleft", "to": "right"}, {"id": "tom", "action": a}]}))
        check(f"Aktion {a} im Bett", lambda: frame({"place": "bedroom", "time": "night", "actors": [{"id": "du", "action": a}]}))
    for em in ("!", "?", "heart", "idea", "sweat", "anger", "music", "unbekannt", " "):
        check(f"Symbol {em}", lambda: frame({"place": "park", "actors": [{"id": "du", "emote": em}], "shot": "close"}))
    for held in sorted(set(extras.HELD)) + ["unbekannt"]:
        for a in ("talk", "walk", "run", "sleep"):
            check(f"In der Hand {held} bei {a}", lambda: frame({"place": "basement", "time": "night", "actors": [{"id": "du", "action": a, "hold": held}]}))
        check(f"In der Hand {held} als Requisite", lambda: frame({"place": "park", "props": [held], "actors": [{"id": "du"}]}))
    for c in sorted(set(stage.CROWD_KINDS)) + ["unbekannt"]:
        for pl in ("street", "park", "supermarket", "snow", {"elements": ["ruins"]}):
            for nt in (False, True):
                check(f"Menge {c} in {pl}", lambda: frame({"place": pl if isinstance(pl, str) else None, "backdrop": None if isinstance(pl, str) else pl,
                                                           "crowd": c, "actors": [{"id": "du"}], "no_traffic": nt}))
    for w in ("rain", "storm", "snow", "wind", "ash", "quake", "heat", "dark", "unbekannt"):
        for pl in ("street", "forest", "office"):
            check(f"Wetter {w} in {pl}", lambda: frame({"place": pl, "weather": w, "time": "night" if w == "dark" else "day", "actors": [{"id": "du"}]}))
    for m in ("panic", "tense", "scary", "sad", "happy", "calm", "unbekannt"):
        check(f"Stimmung {m}", lambda: frame({"place": "street", "mood": m, "crowd": "walk", "actors": []}))
        check(f"Einschub Stimmung {m}", lambda: frame({"place": "kitchen", "mood": m, "props": ["candle", "cans"], "shot": "insert", "actors": []}))
    for hat in ("", "cap", "helmet", "beanie", "bow", "crown", "unbekannt"):
        for hair in ("", "long", "bun"):
            check(f"Aussehen {hat}/{hair}", lambda: frame({"place": "park", "actors": [{"id": "z"}]},
                                                          {"z": {"shirt": "lila", "hat": hat, "hair": hair, "glasses": True, "skin": "dunkel", "size": 1.2}}))
    ovs = [{"type": "card", "text": "VIERMAL HELLER"}, {"type": "note", "title": "REGEL #1", "text": "Tür bleibt zu, egal wer klopft"},
           {"type": "phone", "title": "3:12", "items": ["Mama: Wo bist du??", "Warnung: Bleib drinnen"]},
           {"type": "checklist", "title": "LISTE", "items": [["Wasser", True], ["Essen", False], "Licht"]},
           {"type": "bar", "label": "WASSER", "value": 24}, {"type": "choice", "a": "Bleiben", "b": "Gehen"},
           {"type": "counter", "label": "ZUCKER IM SEE", "value": 4.4, "unit": "MRD. TONNEN", "sub": "= 23 Jahre"},
           {"type": "counter", "label": "JAHRE", "value": "48", "unit": ""}, {"type": "counter", "value": "abc"},
           {"type": "counter", "label": "x" * 80, "value": 1234567.5, "unit": "y" * 40}, {"type": "bar", "label": None, "value": "x"},
           {"type": "unbekannt"}, {"type": "card"}, {"type": "phone", "items": []}, {}]
    for ov in ovs:
        check(f"Einblendung {ov}", lambda: overlays.frames_for(ov))
    # Regie mit zufälligen und kaputten Drehbüchern
    rnd = random.Random(1)
    junk = [None, "", 0, 3.5, [], {}, "xyz", ["a"], {"type": None}, {"elements": None}, {"elements": ["forest", 3, None]}, True]
    texts = ["Plötzlich fällt überall der Strom aus und alle rennen in Panik weg.", "Es ist ganz ruhig im Wald.", "In ganz Deutschland jubeln die Menschen.",
             "Weltweit steigen die Preise, die Supermärkte sind leergekauft.", "", None, "Der Fluss trocknet aus, die Ernte verdorrt, niemand ist da.",
             "Am Bahnhof steht alles still.", "Die Sonne verschwindet, es wird stockdunkel."]
    keys = ("place", "backdrop", "time", "weather", "props", "actors", "crowd", "mood", "shot", "overlay", "hud", "highlight")
    for n in range(260):
        scenes = []
        for _ in range(rnd.randint(1, 6)):
            sc = {"text": rnd.choice(texts)}
            for k in keys:
                r = rnd.random()
                if r < 0.35:
                    sc[k] = rnd.choice(junk)
                elif r < 0.75:
                    sc[k] = {"place": rnd.choice(all_places + ["straße", "nirgendwo"]), "backdrop": {"sky": rnd.choice(["", "red", "x"]), "ground": rnd.choice(list(places.GROUNDS) + ["x"]),
                             "elements": rnd.sample(sorted(set(places.BACK) | set(places.MID) | set(places.FRONT_EL)) + ["x"], 3)},
                             "time": rnd.choice(["day", "night", "x"]), "weather": rnd.choice(["rain", "quake", "dark", "x"]),
                             "props": rnd.sample(sorted(extras.PROPS) + sorted(extras.HELD) + ["x", 5, None, {"type": "car", "pos": "left"}, {"pos": 3}], 3),
                             "actors": [{"id": rnd.choice(["du", "tom", "rex", None, 4]), "action": rnd.choice(actions), "emotion": rnd.choice(emotions),
                                         "emote": rnd.choice(["!", "", None, 3]), "pos": rnd.choice(["left", "x", None, 300]), "to": rnd.choice([None, "right", "x"]),
                                         "speaks": rnd.choice([True, False, None, "ja"]), "hold": rnd.choice([None, "handy", "x", 2])} for _ in range(rnd.randint(0, 4))],
                             "crowd": rnd.choice(["panic", "walk", "worried", "x"]), "mood": rnd.choice(["panic", "tense", "calm", "x"]),
                             "shot": rnd.choice(["event", "close", "insert", "wide", "x"]), "overlay": rnd.choice(ovs), "hud": "TAG 1", "highlight": ["a"]}[k]
            scenes.append(sc)
        times = [(i * 3.0, i * 3.0 + 3.0) for i in range(len(scenes))]
        if check(f"Regie Drehbuch {n}", lambda: stage.direct(scenes, times) or True):
            for i, sc in enumerate(scenes):
                check(f"Regie Drehbuch {n} Szene {i}: {str(sc)[:300]}", lambda: frame(sc, t=rnd.choice((0.0, 1.0, 2.9))))
    check("Titelbild", lambda: stage.cover({"place": "street", "props": ["meteor"], "actor": "du"}, {"du": {}}, "/tmp/_selftest_cover.jpg"))
    check("Titelbild kaputt", lambda: stage.cover({"place": None, "props": [None, 3], "actor": None, "backdrop": "x"}, {}, "/tmp/_selftest_cover.jpg"))
    print(f"{count[0]} Prüfungen, {len(errors)} Fehler")
    import collections
    for line, n in collections.Counter(e.strip().splitlines()[-1] + "  @ " + e.strip().splitlines()[-3].strip()[:90] for e in errors).most_common(30):
        print(f"{n:4d}× {line}")
    for e in errors[:6]:
        print("-" * 60 + "\n" + e)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
