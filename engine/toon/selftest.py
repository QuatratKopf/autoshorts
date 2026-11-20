"""Selbsttest der Engine: zeichnet jeden Ort, jeden Baustein, jede Requisite, jedes Wesen, jede Aktion, jedes Gefühl,
jedes Symbol, jede Menschenmenge, jedes Wetter und jede Einblendung einmal – und füttert die Regie mit kaputten
Drehbüchern. Bricht mit Fehlerliste ab, wenn irgendetwas nicht zeichenbar ist.   python -m engine.toon.selftest"""
import random
import sys
import traceback

from . import extras, graphics, places, rig, stage
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
           "win": scene.get("_win"), "count": scene.get("_count"), "neon": scene.get("look") == "neon",
           "float": str(scene.get("float") or ""), "aloft": bool(scene.get("aloft")), "low": bool(scene.get("low"))}
    shot = str(scene.get("shot") or "")
    if shot == "graphic" and graphics.clean(scene.get("graphic")):
        return graphics.frame(graphics.clean(scene["graphic"]), t, 3.0, opt["mood"])
    if shot == "insert":
        return stage._insert_frame([k for k, _ in props][:2], t, 3.0, opt["mood"])
    return stage._frame(bg, place, night, scale, actors, props, weather, t, 3.0, (), 0.0, place == "bedroom",
                        shot if shot == "close" else "", 1.5 if shot == "event" else 1.15, opt)


texts_gfx = ["Warum ist das so?", "Fünf Millionen Haushalte bekommen Post.", "Du bist zweiundsiebzig Stunden auf dich allein gestellt.",
             "Vorrat für drei Tage.", "Fünfundvierzigtausend Haushalte ohne Strom.", "Neunzig Prozent fallen aus.", "Und jetzt?", "", None, 5,
             "Ein Hund läuft.", "Achtzig Milliarden Liter Wasser.", "Ganz Europa warnt, auch Schweden.", "Die ganze Stadt ist ohne Strom.",
             "Einer von sieben Menschen träumt davon.", "Jeder dritte Deutsche kennt das.", "Runde eins: Koffein.", "Drei von zehn Leuten.", "Runde x"]


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
    for w in ("rain", "storm", "snow", "cold", "wind", "ash", "quake", "heat", "dark", "steam", "unbekannt"):
        for pl in ("street", "forest", "office"):
            check(f"Wetter {w} in {pl}", lambda: frame({"place": pl, "weather": w, "time": "night" if w == "dark" else "day", "actors": [{"id": "du"}]}))
    for m in ("panic", "tense", "scary", "sad", "happy", "love", "calm", "unbekannt"):
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
           {"type": "tag", "text": "AUGUST 1914"}, {"type": "tag", "text": "x" * 60}, {"type": "tag"},
           {"type": "quote", "title": "FORSCHER WARNEN", "text": "…dass es noch schlimmer wird."}, {"type": "quote", "text": "x" * 300}, {"type": "quote"},
           {"type": "thermo", "value": 22}, {"type": "thermo", "value": -80}, {"type": "thermo", "value": "x"}, {"type": "thermo", "value": 999},
           {"type": "stamp", "text": "VERBOTEN"}, {"type": "stamp", "text": "GRATIS", "color": "green"}, {"type": "stamp", "text": "x" * 50, "color": 3},
           {"type": "unbekannt"}, {"type": "card"}, {"type": "phone", "items": []}, {}]
    for ov in ovs:
        check(f"Einblendung {ov}", lambda: overlays.frames_for(ov))
    gs = [{"type": "number", "kicker": "Schweden · Nov. 2024", "value": "5 MIO.", "label": "Haushalte", "sub": "x" * 80}, {"type": "number", "value": 45000},
          {"type": "number", "value": "1,2 Mrd."}, {"type": "number", "value": "abc"}, {"type": "timer", "value": "72:00:00"}, {"type": "timer", "value": "quatsch"},
          {"type": "calendar", "value": "3", "label": "Tage", "kicker": "Vorrat für"}, {"type": "calendar", "value": "x" * 60}, {"type": "question"},
          {"type": "question", "text": "Warum eigentlich so lange?"}, {"type": "houses", "value": "45.000", "label": "Haushalte", "dark": True},
          {"type": "houses", "value": "5"}, {"type": "badge", "text": "72 Stunden", "kicker": "mind."}, {"type": "badge"}, {"type": "x"}, {}, None, "x",
          {"type": "map", "text": "72 Stunden allein", "value": "sweden,germany,quatsch"}, {"type": "map"}, {"type": "map", "value": 5},
          {"type": "city", "kicker": "Berlin", "text": "45.000 ohne Strom", "dark": True}, {"type": "city"},
          {"type": "versus", "left": "Energy", "right": "Kaffee", "kicker": "5 Runden"}, {"type": "versus", "left": "x"}, {"type": "round", "kicker": "Runde 1", "text": "Koffein"},
          {"type": "round", "text": "x" * 60}, {"type": "score", "left": "Energy", "right": "Kaffee", "value": "0:2", "kicker": "Runde 3/5"}, {"type": "score", "value": "abc"},
          {"type": "score", "value": "3-3"}, {"type": "compare", "left": "Dose", "right": "Kaffee", "value": "80 mg", "sub": "180 mg"}, {"type": "compare", "value": "0", "sub": "0"},
          {"type": "compare", "value": "viel", "sub": "3"}, {"type": "podium", "kicker": "Körperteile", "text": "Fuß", "left": "Hand", "right": "Bein"}, {"type": "podium", "text": "x"},
          {"type": "share", "value": "1 von 7", "label": "träumt davon"}, {"type": "share", "value": "12 von 12"}, {"type": "share", "value": "9 von 3"}, {"type": "share", "value": "x"},
          {"type": "news", "kicker": "Talblatt", "text": "Gondel 7 abgestürzt", "sub": "Unglück im Nebel"}, {"type": "news", "text": "Donaudampfschifffahrtsgesellschaft " * 3},
          {"type": "news"}, {"type": "pulse", "value": "1", "label": "Eine Sekunde"}, {"type": "pulse", "value": "x" * 30}, {"type": "radar"}, {"type": "radar", "kicker": "Flugsicherung", "text": "Signal verloren", "sub": "lost"}, {"type": "radio", "kicker": "Funk · Kanal 4", "text": "Bergwacht"},
          {"type": "radio", "text": "x", "sub": "y" * 80}, {"type": "distance", "value": "100 m", "left": "Ihr", "right": "Ziel"}, {"type": "distance", "value": "weit"},
          {"type": "days", "text": "30 Tage überleben", "value": "1", "sub": "30", "label": "Noch 2 Min"}, {"type": "days", "value": "99", "sub": "999"}, {"type": "days", "value": "x"},
          {"type": "days", "value": "7", "sub": "7"}, {"type": "phone", "mode": "alert", "kicker": "Live", "text": "Fang ihn", "value": "10.000.000 €", "label": "Ich hab ihn gesehen"},
          {"type": "phone", "mode": "lock", "value": "07:49", "kicker": "Unbekannt", "text": "Wir wissen, wo du bist und kommen jetzt."}, {"type": "phone", "mode": "quatsch", "text": "x"},
          {"type": "chart", "kicker": "Aktienkurs", "value": "3 BIO.", "label": "Dollar"}, {"type": "chart", "dark": True}, {"type": "chart", "value": "x" * 60},
          {"type": "phone", "mode": "chat", "kicker": "Oma", "text": "Junge, stimmt das mit den 10 Millionen?", "sub": "Oma, bitte nicht.", "label": "Doch."}, {"type": "phone"}]
    for g in gs:
        for m in ("", "panic", "scary", "x"):
            for t in (0.0, 0.2, 1.0, 3.5):
                check(f"Grafik {g} {m} t={t}", lambda: frame({"shot": "graphic", "graphic": g, "mood": m, "place": "park"}, t=t))
    from .. import hyper                                        # HyperFrames-Seiten (HTML/GSAP) für jede Grafik bauen – ohne Chrome
    for g in gs:
        cg = graphics.clean(g)
        if cg and cg["type"] in hyper.TYPES:
            for m in ("", "panic", "x"):
                check(f"HyperFrames-Seite {g} {m}", lambda: hyper.page(cg, 3.0, m) or True)
    for txt in texts_gfx:
        check(f"Grafik aus Text: {txt}", lambda: graphics.clean(stage.auto_graphic(txt, "TAG 1")))
    for fl in ("float", "drop", "unbekannt"):                   # Schwerelosigkeit: Figuren, Tiere und Dinge schweben und krachen herunter
        for pl in ("livingroom", "street", "park", "kitchen"):
            for t in (0.0, 0.4, 0.9, 1.6, 2.9):
                check(f"Schweben {fl} in {pl} t={t}", lambda: frame({"place": pl, "float": fl, "aloft": t > 1, "props": ["car", "lib_kaffeetasse", "bus"], "low": t > 1.5,
                                                                     "actors": [{"id": "du", "action": "float", "hold": "phone"}, {"id": "rex"}], "overlay": {"type": "card", "text": "X"}}, t=t))
    for txt in ("Alles schwebt plötzlich durch die Luft.", "Auch du hebst ab.", "Dann kracht alles auf den Boden.", "Die Schwerkraft ist wieder da und alles kracht herunter."):
        for pl in ("livingroom", "street", "forest", "worldmap"):
            def _flo(txt=txt, pl=pl):
                scs = stage.direct([{"text": txt, "place": pl, "actors": [{"id": "du"}], "crowd": "walk", "props": ["bus", "car", "wave"], "overlay": {"type": "note", "text": "x"}},
                                    {"text": txt, "place": pl, "props": ["bus", "truck"]}, {"text": "Es geht weiter.", "place": pl, "weather": "wind"},
                                    {"text": "Schluss.", "place": pl}], [(0, 3), (3, 6), (6, 9), (9, 12)], "Was wäre ohne Schwerkraft?")
                for sc_ in scs:
                    frame(sc_, t=1.2)
            check(f"Regie Schweben: {txt} in {pl}", _flo)
    def _firm():                                                 # Firmengeschichte: Gründer-Gruppe, Firmensitz, Rechenzentrum, Kurve – kein Schreibtisch im All
        scs = stage.direct([{"text": "Stell dir vor, du zockst den ganzen Tag.", "place": "bedroom", "actors": [{"id": "du", "action": "sit"}]},
                            {"text": "Drei Gründer bauten Grafikchips in einer Garage.", "place": "office", "actors": [{"id": "du", "action": "point", "pos": "center"}]},
                            {"text": "Heute ist die Bude der wertvollste Konzern der Welt.", "place": "street", "props": ["house"], "shot": "event", "crowd": "walk"},
                            {"text": "Jeder brauchte plötzlich diese Rechenleistung.", "place": "powerplant", "props": ["computer"], "shot": "event", "crowd": "worried"},
                            {"text": "Dann explodierte der Aktienkurs völlig.", "place": "office", "props": ["money"], "actors": [{"id": "du", "action": "shocked"}],
                             "overlay": {"type": "counter", "label": "MARKTWERT", "value": 3.0, "unit": "BILLIONEN DOLLAR"}},
                            {"text": "Das ist das Fundament des gesamten Internets.", "place": "space", "time": "night", "props": ["satellite", "computer"], "shot": "event"},
                            {"text": "Folg für mehr.", "place": "office", "actors": [{"id": "du"}]}],
                           [(k * 4.0, k * 4.0 + 4.0) for k in range(7)], "Wie eine Gaming-Bude zum Tech-Giganten wurde", "fakten")
        assert len([a for a in scs[1]["actors"] if not a.get("kind")]) == 3, "Drei Gründer: es stehen nicht drei Figuren im Bild"
        assert stage.places.resolve(stage.backdrop(scs[2])) == "headquarters", f"Konzern: Ort ist {scs[2].get('place')}"
        assert stage.places.resolve(stage.backdrop(scs[3])) == "serverroom" and not scs[3].get("crowd"), f"Rechenleistung: Ort ist {scs[3].get('place')}"
        assert scs[4].get("shot") == "graphic" and scs[4]["graphic"]["type"] == "chart" and "value" not in scs[4]["graphic"], "Aktienkurs: keine Kurve"
        assert stage.places.resolve(stage.backdrop(scs[5])) != "space", "Internet-Satz spielt im Weltall"
        assert scs[3].get("actors") and scs[5].get("actors"), "Rechenzentrum ohne Menschen: leeres Bild"
        for sc_ in scs:
            for t in (0.3, 2.0):
                frame(sc_, {"leo": {"shirt": "grün", "hair": "long"}}, t=t)
    check("Regie Firmengeschichte", _firm)
    def _sit():                                                  # Sitzen: Unterschenkel zeigen nach unten, die Füße stehen unter den Knien – nicht über dem Kopf
        for t in (0.0, 1.0, 2.5):
            p, _ = rig.pose_at("sit", t, 3.0)
            for leg, knee in ((p.leg_l, p.knee_l), (p.leg_r, p.knee_r)):
                assert abs(leg - knee) < 30, f"Sitzhaltung verdreht: Bein {leg}, Knie {knee}"
    check("Sitzhaltung", _sit)
    def _cam():                                                  # Halbnahe: Kamera mit Zoom auf die Gruppe, Lichtkegel bei Anspannung
        fr = frame({"place": "livingroom", "mood": "tense", "actors": [{"id": "du", "pos": "left"}, {"id": "tom", "pos": "right"}], "props": ["tv"]})
        for t in (0.0, 0.1, 1.5, 2.9):
            for cam in ({"tight": True, "zt": 1.42, "fx": 900, "punch": 1.0}, {"tight": True, "zt": 1.0, "fx": 0}, {"flat": True}, {}):
                im = stage._camera(fr, t, 3.0, cam)
                assert im.size == (1080, 1920)
    check("Kamera Halbnahe", _cam)
    def _unspoken():                                             # erfundene Zahlen in Grafik/Einblendung fliegen raus, gesprochene bleiben; liegende Figur ohne Großaufnahme
        scs = [{"text": "Dazu kommt der berühmte digitale Kartenregen.", "place": "office", "shot": "graphic",
                "graphic": {"type": "number", "value": "1.000.000", "label": "DIGITALE KARTEN"}},
               {"text": "Aber im echten Leben scheitert fast jeder davon.", "place": "livingroom", "mood": "tense", "overlay": {"type": "card", "text": "NULL PROZENT"},
                "actors": [{"id": "du", "action": "fall", "emotion": "scared", "speaks": True}]},
               {"text": "Du bist zweiundsiebzig Stunden auf dich allein gestellt.", "place": "livingroom", "shot": "graphic",
                "graphic": {"type": "badge", "kicker": "MIND.", "text": "72 STUNDEN"}},
               {"text": "Am Ende lernst du das im Lehrbuch.", "place": "classroom", "actors": [{"id": "du", "speaks": True}]}]
        stage.direct(scs, [(i * 3.5, i * 3.5 + 3.5) for i in range(4)], "Test", "fakten", "")
        assert not scs[0].get("graphic") and scs[0].get("shot") != "graphic", "ungesprochene Zahl blieb als Grafik stehen"
        assert not scs[1].get("overlay"), "ungesprochene Zahl blieb als Einblendung stehen"
        assert (scs[2].get("graphic") or {}).get("type") == "badge", "gesprochene Zahl wurde entfernt"
        _pl, _n, _s, acts, props, _w = stage._prepare(scs[1], {"du": {}})
        assert stage._cut_plan(scs[1], "", None, False, False, "livingroom", acts, props, 3.6, {"punch": 1.5}, 0)[1] != "close", "Großaufnahme schneidet die liegende Figur an"
        fs = [{"text": "Jetzt kriecht der Held durch einen Schacht.", "place": "attic", "actors": [{"id": "du", "action": "float", "speaks": True}]},
              {"text": "Die Gauner rollen schwere Stahltresore weg.", "place": "livingroom", "props": ["box"], "actors": [{"id": "du", "speaks": True}]}]
        stage.direct(fs, [(0, 3.5), (3.5, 7.0)], "Filme", "fakten", "")
        assert not fs[0].get("float") and fs[0]["actors"][0]["action"] != "float", "Figur schwebt, obwohl der Satz nicht davon spricht"
        if any(k == "lib_tresor" for _p, k in stage._lib_props()):
            assert [q["type"] for q in fs[1]["props"]] == ["lib_tresor"], f"Tresor im Satz, aber im Bild: {fs[1]['props']}"
        ls = [{"text": "Im Film leuchten die Laser rot und wabern wild durch die Luft.", "place": "hallway", "actors": [{"id": "du", "action": "float", "speaks": True}]}]
        stage.direct(ls, [(0, 3.5)], "Filme", "fakten", "")
        assert not ls[0].get("float"), "Laser in der Luft lässt die Figur schweben"
        from .. import writer
        assert writer.fix_label_typos("TAGEELANG", "Das dauert oft tagelang.") == "TAGELANG"
        assert writer.polish({"scenes": [{"text": "Das ist reine reine Fantasie."}]})["scenes"][0]["text"] == "Das ist reine Fantasie."
        assert writer.fix_eszett("Ausser der Masse auf der Strasse") == "Außer der Masse auf der Straße"
        assert writer.named_person("Warum König Charles ausgerechnet den berühmten Spudbros-Pommes-Kiosk besucht hat"), "Trend über eine echte Person"
        assert writer.named_person("Warum der britische Monarch Charles Pommes isst", [], "King Charles visits the Spudbros kiosk"), "Name aus dem Trend im Thema"
        assert writer.named_person("Wie Taylor Swift Stadien füllt", ["Taylor Swift"]), "gemeldeter Name im Thema"
        assert not writer.named_person("Warum der König der Tiere brüllt") and not writer.named_person("Warum der König Angst hat")
        assert not writer.named_person("Warum ein Pommes-Kiosk Millionen Zuschauer hat", ["Spudbros"], "King Charles visits the Spudbros kiosk")
        js = writer.polish({"scenes": [{"text": "x", "graphic": {"type": "badge", "kicker": "GEHIRN-EFFECT", "text": "KONTROLLE"}}]})
        assert js["scenes"][0]["graphic"]["kicker"] == "GEHIRN-EFFEKT"
    check("Erfundene Zahlen, liegende Figur, ß", _unspoken)
    for pl in ("street", "park", "village", "livingroom"):           # Nachtlicht, Großaufnahme bei Nacht, Tier in Großaufnahme
        for kind in ("", "dog", "ghost"):
            check(f"Nacht {pl} {kind}", lambda: frame({"place": pl, "time": "night", "actors": [{"id": "x", "kind": kind, "speaks": True}], "crowd": "walk"}))
            check(f"Großaufnahme Nacht {pl} {kind}", lambda: frame({"place": pl, "time": "night", "shot": "close", "mood": "scary",
                                                                     "actors": [{"id": "x", "kind": kind, "emotion": "scared", "emote": "!", "say": "HILFE"}]}))
    def _tags():
        scs = stage.direct([{"text": "Am 24. Dezember 1914 passiert es.", "place": "street"}, {"text": "Im August 1914 auch.", "place": "street"},
                            {"text": "1500 Menschen.", "place": "park"}, {"text": "Das war 2024.", "place": "park"}], [(i * 3, i * 3 + 3) for i in range(4)], "Test")
        assert scs[0]["overlay"] == {"type": "tag", "text": "24. DEZEMBER 1914"}, scs[0].get("overlay")
        assert (scs[1].get("overlay") or {}).get("type") != "tag", "zwei Schilder hintereinander"
    check("Beschriftungs-Schilder", _tags)
    def _places_said():                                          # der Satz bestimmt den Ort; Teilwörter lösen keinen falschen Ort aus
        assert stage._said_place("Sie graben Wohnhöhlen in deinen Garten.") == "park"
        assert stage._hint("Sie graben Wohnhöhlen in deinen Garten.") != "cave"
        assert stage._said_place("Du gehst in den dunklen Keller.") == "basement"
        assert stage._said_place("Das ist gerade im Gang.") is None
        assert stage._said_place("Schließlich wollen wir im Kino kein Lehrbuch sehen.") == "cinema"
        scs = stage.direct([{"text": "Nach einer Woche graben sie Wohnhöhlen in deinen Garten.", "place": "cave", "actors": [{"id": "du"}]},
                            {"text": "Jeder Coup fühlt sich an wie ein Sieg.", "place": "livingroom", "actors": [{"id": "du"}]},
                            {"text": "Im Jahr 1993 saßen drei Gründer zusammen.", "place": "lab", "who": [], "shot": "graphic"},
                            {"text": "Schluss.", "place": "livingroom"}], [(i * 3, i * 3 + 3) for i in range(4)], "Hollywood Heist Filme")
        assert stage.places.resolve(stage.backdrop(scs[0])) == "park", scs[0].get("place")
        assert scs[1].get("place") == "cinema", scs[1].get("place")
        assert len([a for a in scs[2].get("actors") or [] if not a.get("kind")]) == 3, "drei Gründer"
    check("Ort aus dem Satz", _places_said)
    def _one_animal():                                           # Video über ein einziges Meerestier: „Krebs“ meint dieses Tier, Menschen-Sätze spielen an Land
        T = [("Drei Fakten über den Fangschreckenkrebs.", "underwater", [{"id": "krebs"}], "", ""),
             ("Und der letzte Fakt zerbricht sogar Glas.", "underwater", [{"id": "krebs", "action": "point"}], "", ""),
             ("Das ist fünfzigmal schneller als ein menschlicher Wimpernschlag.", "underwater", [{"id": "du", "action": "shocked"}], "", ""),
             ("Dafür nutzt er eine Art Sprungfeder.", "underwater", [{"id": "krebs"}], "", ""),
             ("Er lässt das Wasser wortwörtlich kochen.", "underwater", [{"id": "krebs"}], "steam", ""),
             ("Durch den Unterdruck entstehen kleine Dampfblasen.", "underwater", [], "", "insert"),
             ("Wenn diese Blasen kollabieren, entstehen mehrere tausend Grad.", "underwater", [], "", ""),
             ("Forscher halten ihn deshalb in dickwandigen Plastikbecken.", "lab", [{"id": "du", "action": "look_around"}], "", ""),
             ("Dieser Krebs sieht ultraviolettes Licht.", "underwater", [{"id": "krebs"}], "", "close")]
        scs = stage.direct([{"text": t_, "place": pl_, "actors": a_, "weather": w_, "shot": sh_} for t_, pl_, a_, w_, sh_ in T],
                           [(n_ * 3, n_ * 3 + 3) for n_ in range(len(T))], "Der Fangschreckenkrebs: Das Tier mit dem stärksten Schlag")
        kinds = [[a.get("kind") or "" for a in sc.get("actors") or []] for sc in scs]
        keys = [[q.get("type") for q in sc.get("props") or []] for sc in scs]
        for n_ in (0, 1, 3, 4, 5, 6, 8):
            assert kinds[n_] == ["mantis"], f"Ein-Tier-Video Szene {n_}: {kinds[n_]} statt Fangschreckenkrebs"
        assert kinds[2] == [""] and places.resolve(stage.backdrop(scs[2])) == "livingroom" and scs[2].get("shot") == "close", f"Wimpernschlag ohne Mensch: {kinds[2]}"
        assert keys[3] == ["lib_sprungfeder"] or "lib_sprungfeder" not in extras.PROPS, f"Sprungfeder fehlt: {keys[3]}"
        assert not scs[4].get("weather"), "Küchendampf unter Wasser"
        assert keys[5] == ["cavitation"] and keys[6] == ["cavitation"], f"Dampfblase fehlt: {keys[5]} {keys[6]}"
        assert scs[5]["actors"][0].get("facing") != scs[6]["actors"][0].get("facing"), "zweimal dasselbe Blasen-Bild"
        assert not scs[6].get("overlay"), f"Zähler aus „mehrere tausend“: {scs[6].get('overlay')}"
        assert keys[7] == ["tank"] and kinds[7] == [""], f"Forschungsbecken fehlt: {keys[7]} {kinds[7]}"
        for sc in scs:
            frame(sc, {"du": {"shirt": "blau"}})
            frame(sc, {"du": {"shirt": "blau"}}, 2.7)
        js = {"scenes": [{"text": "Drei Fakten über den Fangschreckenkrebs, die unmöglich klingen."}] + [{"text": f"Satz Nummer {n_} erzählt etwas Neues."} for n_ in range(8)]
                        + [{"text": "Und hier kommen drei Fakten über den Fangschreckenkrebs, die unmöglich klingen."}]}
        from .. import writer
        writer.polish(js)
        assert len(js["scenes"]) == 9, "Schlusssatz wiederholt den ersten (mit Vorspann)"
        js["scenes"].append({"text": "Und genau deshalb –"})
        writer.polish(js)
        assert len(js["scenes"]) == 9, "abgebrochener Schlusssatz bleibt stehen"
        assert scs[2]["actors"][0].get("action") not in ("walk", "run") and not scs[2]["actors"][0].get("to"), "Großaufnahme läuft durchs Zimmer"
        assert stage.poster_hero("Der Schlag des Fangschreckenkrebses", scs, None, ["mantis"]) == "mantis", "Titelbild ohne das Tier des Themas"
        sh = stage.direct([{"text": "Drei Fakten über den Fangschreckenkrebs.", "place": "underwater", "actors": [{"id": "krebs"}]},
                           {"text": "Das ist etwa fünfzigmal schneller als ein Wimpernschlag.", "place": "underwater", "actors": [{"id": "du"}]},
                           {"text": "Menschen haben drei Arten von Farbrezeptoren im Auge.", "place": "underwater", "actors": []},
                           {"text": "Der Fangschreckenkrebs besitzt dagegen bis zu sechzehn.", "place": "underwater", "actors": [{"id": "krebs"}]}],
                          [(n_ * 3, n_ * 3 + 3) for n_ in range(4)], "Der Fangschreckenkrebs und sein Schlag")
        for n_ in (1, 2):
            assert [a.get("kind") or "" for a in sh[n_].get("actors") or []] == [""] and places.resolve(stage.backdrop(sh[n_])) != "underwater", f"Menschen-Satz {n_} zeigt das Tier"
            frame(sh[n_], {"du": {"shirt": "blau"}})
        assert [a.get("kind") for a in sh[3].get("actors") or []] == ["mantis"], "Tier-Satz nach Menschen-Satz"
        sp = stage.direct([{"text": "Drei Fakten über den Fangschreckenkrebs.", "place": "underwater", "actors": [{"id": "krebs"}]},
                           {"text": "Eine Art Sprungfeder im Arm liefert die Kraft.", "place": "underwater", "actors": [{"id": "krebs"}],
                            "overlay": {"type": "note", "title": "MECHANISMUS", "text": "Sprungfeder"}}], [(0, 3), (3, 6)], "Der Fangschreckenkrebs")
        assert not sp[1].get("overlay") or "lib_sprungfeder" not in extras.PROPS, "Notizzettel schiebt den Krebs von der Feder weg"

    check("Ein-Tier-Video (Fangschreckenkrebs)", _one_animal)

    def _music():                                                # Musik-Video: Kopfhörer auf dem Kopf, Gänsehaut-Schaubild, Lautsprecher beim Bassdrop; Hafen
        cast_m = {"du": {"shirt": "lila", "hair": "ponytail"}, "gehirn": {"kind": "brain"}}
        T = [("Dein Gehirn löst deine Musik-Gänsehaut in nur einer halben Sekunde aus.", "livingroom", [{"id": "du", "action": "dance", "hold": "phone"}]),
             ("Schon eine halbe Sekunde vor dem Bassdrop passiert etwas völlig Verrücktes im Kopf.", "livingroom", [{"id": "du", "action": "shocked"}]),
             ("Winzige Muskeln an deinen Haarwurzeln spannen sich schlagartig an.", "livingroom", [{"id": "du", "action": "look_around"}]),
             ("Doch direkt danach erkennt dein Denkorgan, dass gar keine reale Gefahr droht.", "lab", [{"id": "gehirn", "action": "talk"}]),
             ("Ein echter Lieblingssong aktiviert dein Gehirn genau wie gutes Essen oder Achterbahnfahren.", "livingroom", [{"id": "du", "action": "dance"}])]
        sm = stage.direct([{"text": t_, "place": pl_, "actors": a_} for t_, pl_, a_ in T], [(n_ * 4, n_ * 4 + 4) for n_ in range(len(T))],
                          "Warum du Gänsehaut bekommst, wenn dein Lieblingssong droppt", "wissen", "")
        km = [[extras.PROP_ALIASES.get(str(q.get("type")).lower(), str(q.get("type")).lower()) for q in sc_.get("props") or [] if isinstance(q, dict)] for sc_ in sm]
        for n_ in (0, 1, 2, 4):
            assert any(a.get("wear") == "headphones" for a in sm[n_].get("actors") or []), f"Musik-Video: Figur ohne Kopfhörer in Szene {n_}"
        assert not any(a.get("wear") for a in sm[3].get("actors") or []), "Gehirn-Figur trägt Kopfhörer"
        assert "lib_bassbox" in km[1], f"Bassdrop ohne Lautsprecher: {km[1]}"
        assert "goosebumps" in km[2] and "lib_muskel" not in km[2], f"Haarwurzeln: {km[2]}"
        assert "lib_achterbahn" not in km[4], "Achterbahn steht im Wohnzimmer"
        for sc_ in sm:
            assert frame(sc_, cast_m) is not None
        plain = stage.direct([{"text": "Ich wollte nur kurz Strom sparen.", "place": "livingroom", "actors": [{"id": "du"}]},
                              {"text": "Dann setzte ich meine Kopfhörer auf.", "place": "livingroom", "actors": [{"id": "du"}]}], [(0, 4), (4, 8)], "Ich spare Strom", "comedy", "")
        assert not any(a.get("wear") for a in plain[0]["actors"]) and plain[1]["actors"][0].get("wear") == "headphones", "Kopfhörer nur im Satz, der sie nennt"
        for t_ in (0.2, 0.7, 1.5):
            for sh_ in ("", "insert"):
                frame({"place": "lab", "actors": [], "props": [{"type": "goosebumps"}], "shot": sh_}, cast_m, t=t_)
        for hat_ in ("headphones",):
            for hair_ in ("", "long", "curly", "bun"):
                frame({"place": "livingroom", "shot": "close", "actors": [{"id": "du", "action": "talk"}]}, {"du": {"hat": hat_, "hair": hair_}})
        assert stage._hint("Im Hamburger Hafen stapeln sich die Container.") == "harbor" and stage._hint("Dafür haftet niemand.") != "harbor", "Hafen-Hinweis"
        from .. import main as _mn
        assert places.resolve("Hafen") == "harbor" and all(_mn.known_thing(w_) for w_ in ("hafen", "kopfhörer", "bassbox", "muskel", "achterbahn")), "Hafen/Musik-Dinge unbekannt"
        hi = stage.direct([{"text": "Die Ostsee ist komplett zugefroren.", "place": "beach", "actors": [{"id": "du"}]},
                           {"text": "In den Häfen stecken die Frachter fest.", "place": "beach", "actors": [], "props": ["ship"]}],
                          [(0, 4), (4, 8)], "Was wäre, wenn die Ostsee zufriert?", "whatif", "")
        assert places.resolve(stage.backdrop(hi[1])) == "custom" and "harbor" in (hi[1].get("backdrop") or {}).get("elements", []) and \
            not any(str(q.get("type")) in ("ship", "ship_ice") for q in hi[1].get("props") or []), f"zugefrorener Hafen: {hi[1].get('backdrop')} {hi[1].get('props')}"
        assert frame(hi[1], cast_m) is not None

    def _household():                                            # Alltags-Geschichte: Kühlschrank als Figur, Haustier aus dem Satz, Brief in der Hand
        cast_h = {"du": {"shirt": "grau", "gender": "m"}, "kuehlschrank": {"kind": "robot"}}
        T = [("Mein Kühlschrank fand das gar nicht komisch.", "kitchen", [{"id": "kuehlschrank", "say": "NEIN."}], ["fridge"], "insert"),
             ("Sogar die Nachbarskatze ist rückwärts gerannt.", "hallway", [{"id": "du", "action": "point"}], [], ""),
             ("Er hat mir eine Abmahnung geschickt.", "hallway", [{"id": "du", "action": "shocked", "hold": "radio"}], [], ""),
             ("Ich musste mich bei ihm entschuldigen.", "kitchen", [{"id": "du", "action": "sad"}, {"id": "kuehlschrank"}], ["fridge"], ""),
             ("Meine Zähne waren danach komplett grün.", "livingroom", [{"id": "du", "action": "shocked"}], [], "")]
        scs = stage.direct([{"text": t_, "place": pl_, "actors": a_, "props": pr_, "shot": sh_} for t_, pl_, a_, pr_, sh_ in T],
                           [(n_ * 3, n_ * 3 + 3) for n_ in range(len(T))], "Mein Haushalt hat mich verklagt", "comedy", "")
        assert scs[0].get("shot") != "insert" and scs[0]["actors"][0].get("kind") == "fridge", "Kühlschrank-Figur wird nicht zum Kühlschrank mit Gesicht"
        assert not any((q.get("type") if isinstance(q, dict) else q) == "fridge" for sc in (scs[0], scs[3]) for q in sc.get("props") or []), "zweiter Kühlschrank neben der Figur"
        assert any(a.get("kind") == "cat" for a in scs[1]["actors"]), "Katze aus dem Satz fehlt"
        assert scs[2]["actors"][0].get("hold") == "letter", "Abmahnung: kein Brief in der Hand"
        assert scs[4]["actors"][0].get("teeth") == "grün", "grüne Zähne fehlen"
        sc2 = stage.direct([{"text": "Mein Kühlschrank klagt mich an.", "place": "kitchen", "actors": [{"id": "du"}, {"id": "kuehlschrank"}]},
                            {"text": "Nummer eins: Zähneputzen ohne Zahnpasta.", "place": "bathroom", "actors": [{"id": "du"}], "props": ["fridge"]},
                            {"text": "Mein Gebiss ist danach komplett leuchtend grün.", "place": "bathroom", "actors": [{"id": "du", "action": "shocked"}]}],
                           [(0, 3), (3, 6), (6, 9)], "Mein Kühlschrank hat mich verklagt", "comedy", "")
        assert not any((q.get("type") if isinstance(q, dict) else q) == "fridge" for q in sc2[1].get("props") or []), "gesichtsloser Kühlschrank im Bad, obwohl er eine Figur ist"
        assert sc2[2]["actors"][0].get("teeth") == "grün", "grünes Gebiss fehlt"
        sc3 = stage.direct([{"text": "Mein Kühlschrank brummt laut und schließt seine Tür ganz fest.", "place": "kitchen", "actors": [{"id": "kuehlschrank"}], "props": ["door"]},
                            {"text": "Der Gestank ist so extrem, dass die Nachbarskatze sofort das Weite sucht.", "place": "hallway", "shot": "event", "actors": [{"id": "du", "action": "walk"}]},
                            {"text": "Du denkst, alte Hausmittel sparen Geld?", "place": "kitchen", "actors": [{"id": "du"}], "overlay": {"type": "note", "title": "FAZIT", "text": "Lieber moderne Seife nutzen!"}},
                            {"text": "Zuerst habe ich meine Zähne mit Salbeiblättern geschrubbt.", "place": "bathroom", "actors": [{"id": "du", "action": "shake", "hold": "salbeiblatt"}]}],
                           [(0, 3), (3, 6), (6, 9), (9, 12)], "Mein Kühlschrank hat mich verklagt", "comedy", "")
        assert not any((q.get("type") if isinstance(q, dict) else q) == "door" for q in sc3[0].get("props") or []), "Zimmertür neben der Kühlschrank-Figur"
        assert any(a.get("kind") == "cat" for a in sc3[1]["actors"]), "Katze fehlt in der Ereignis-Einstellung"
        assert not sc3[2].get("overlay"), "Notizzettel ohne Bezug zum Satz bleibt stehen"
        assert sc3[3]["actors"][0].get("action") != "shake", "Salbeiblatt wird ausgeschüttelt statt benutzt"
        for sc in sc3:
            frame(sc, cast_h)
        from .. import writer as _w
        assert _w.polish({"title": "Ich lebte wie 1348", "scenes": [{"text": "Ich lebte wie im Mittelalter."}], "thumbnail": {"text": "LEBEN WIE 1348"}})["thumbnail"]["text"] == "LEBEN WIE 1348", "Titelbild-Text verliert die Zahl aus dem Titel"
        for sc in scs:
            frame(sc, cast_h)
        assert stage.balance_cast({"du": {"gender": "m"}}, 2, [{"text": "Ich wollte Strom sparen."}, {"text": "Mein Hund hat mich enterbt."}, {"text": "Ich hatte Blasen."}])["du"].get("gender") == "m", \
            "Ich-Geschichte: Figur wechselt das Geschlecht"
        for em_ in ("", "angry", "sad", "scared"):
            for ac_ in ("idle", "point", "shake", "walk"):
                extras.creature("fridge", 0.7, 1, 0.5, em_, 1.0, ac_)
    check("Alltags-Geschichte (Kühlschrank als Figur, Haustier, Brief)", _household)
    check("Musik-Video (Kopfhörer, Gänsehaut-Schaubild, Lautsprecher) und Hafen", _music)

    def _sleep():                                                # Schlaf-Video (Prüfung 16.11.2026, Video 121): keine Regie-Wörter im Bild, Nacht bleibt Nacht, keine Passanten im Büro, Schlafende zugedeckt im Bett
        cast_s = {"du": {"shirt": "blau", "hair": "curly", "gender": "w"}, "gehirn": {"kind": "brain"}}
        T = [("Fünf verrückte Dinge, die dein Gehirn nachts heimlich tut.", "bedroom", [{"id": "du", "action": "sleep"}], {"type": "card", "text": "5 GEHIRN-FAKTEN"}),
             ("Und Nummer fünf rettet dich jeden Tag vor dem absoluten Chaos.", "bedroom", [{"id": "gehirn", "action": "dance"}], {"type": "tag", "text": "CLIFFHANGER"}),
             ("Zweitens: Es löscht unnötige Erinnerungen wie eine volle Festplatte.", "office", [], None),
             ("Was du mittags gegessen hast, fliegt raus, aber Vokabeln werden fest gespeichert.", "bedroom", [{"id": "gehirn", "action": "point"}],
              {"type": "checklist", "title": "NIGHT SHIFT", "items": [["Mittagessen", False], ["Vokabeln", True]]}),
             ("Aber was passiert mit deinen Gefühlen nach einem richtig schlechten Tag?", "bedroom", [{"id": "du", "action": "think"}], {"type": "card", "text": "REHOOK"}),
             ("Am nächsten Morgen wachst du erholt auf.", "bedroom", [{"id": "du", "action": "idle"}], None)]
        ss = stage.direct([{"text": t_, "place": pl_, "time": "night", "actors": a_, "overlay": o_} for t_, pl_, a_, o_ in T],
                          [(n_ * 4, n_ * 4 + 4) for n_ in range(len(T))], "5 faszinierende Dinge, die dein Gehirn tut, während du schläfst", "fakten", "")
        shown = " ".join(str((sc_.get(k_) or {}).get(f_) or "") for sc_ in ss for k_ in ("overlay", "graphic") if isinstance(sc_.get(k_), dict) for f_ in ("text", "title", "kicker"))
        import re as _re_s
        assert not _re_s.search(r"CLIFFHANGER|REHOOK|NIGHT SHIFT", shown.upper()), f"Regie-Wort oder englischer Titel im Bild: {shown}"
        assert not ss[2].get("crowd"), f"Passanten nachts im Büro: {ss[2].get('crowd')}"
        assert ss[3].get("time") == "night", "„mittags gegessen“ macht aus der Nacht einen Tag"
        assert ss[5].get("time") == "day", "Aufwachen am Morgen spielt nicht am Tag"
        keep = stage.direct([{"text": "Das ist der Cliffhanger der Serie.", "place": "livingroom", "actors": [{"id": "du", "action": "talk"}], "overlay": {"type": "tag", "text": "CLIFFHANGER"}}],
                            [(0, 4)], "Serien", "fakten", "")
        assert (keep[0].get("overlay") or {}).get("text") == "CLIFFHANGER", "gesprochenes Wort darf als Schild bleiben"
        s2 = stage.direct([{"text": "Erstens: Putzen.", "place": "zimmer", "time": "night", "actors": [{"id": "gehirn", "action": "point", "emote": "idea"}]},
                           {"text": "Damit du deine Träume nicht nachspielst, schaltet das Gehirn fast alle Muskeln stumm.", "place": "zimmer", "time": "night", "actors": [{"id": "du", "action": "sleep"}]}],
                          [(0, 4), (4, 8)], "5 Dinge, die dein Gehirn tut, während du schläfst", "fakten", "")
        assert all(places.resolve(stage.backdrop(sc_)) == "bedroom" for sc_ in s2), "Schlaf-Video spielt im Wohnzimmer (Schlafende läge vor dem Sofa am Boden)"
        ids2 = [(a_.get("id"), a_.get("action")) for a_ in s2[0].get("actors") or []]
        assert ids2 and ids2[0] == ("du", "sleep") and ids2[-1][0] == "gehirn", f"Gehirn arbeitet, aber niemand schläft im Bett: {ids2}"
        for t_ in (0.02, 0.1, 0.3, 1.5):                         # Glühbirne springt ins Bild: der winzige Sockel darf die Szene nicht abbrechen
            frame(dict(s2[0], actors=[dict(a_) for a_ in s2[0]["actors"]]), cast_s, t_)
        assert stage._hint("Gelernte Vokabeln wandern ins Langzeitgedächtnis.") is None or "farm" not in str(stage._hint("Gelernte Vokabeln wandern ins Langzeitgedächtnis.")), "„Gelernte“ spielt auf dem Bauernhof"
        assert "farm" in str(stage._hint("Die Ernte fällt dieses Jahr aus.")), "Ernte ohne Bauernhof"
        s3 = stage.direct([{"text": "Fünf geheime Dinge, die dein Gehirn nachts heimlich tut.", "place": "zimmer", "backdrop": {"elements": ["farm", "fields"]}, "time": "night",
                            "props": [{"type": "schloss"}], "actors": [{"id": "du", "action": "sleep"}]},
                           {"text": "Das Gehirn räumt auf.", "place": "bedroom", "time": "night", "actors": [{"id": "gehirn", "action": "point"}]}],
                          [(0, 4), (4, 8)], "5 Dinge, die dein Gehirn tut, während du schläfst", "fakten", "")
        assert places.resolve(stage.backdrop(s3[0])) == "bedroom", f"Zimmer mit Bauernhof-Kulisse: {stage.backdrop(s3[0])}"
        assert not any("schloss" in str(q_).lower() for q_ in s3[0].get("props") or []), "Märchenschloss im Schlafzimmer"
        from .. import writer as _w_s
        gm = _w_s.given_meta({"title": "5 Dinge, die dein Gehirn schläft", "thumbnail": {"text": "X"}},
                             "Schlaf – Vorgaben: kurz. Titel: 5 Dinge, die dein Gehirn nachts für dich erledigt. Titelbild-Text: DEIN GEHIRN NACHTS")
        assert gm["title"] == "5 Dinge, die dein Gehirn nachts für dich erledigt" and gm["thumbnail"]["text"] == "DEIN GEHIRN NACHTS", f"vorgegebener Titel nicht übernommen: {gm}"
        assert _w_s.given_meta({"title": "A"}, "Thema ohne Vorgabe. Titelbild-Text fehlt")["title"] == "A"
        pl = _w_s.polish({"title": "T", "description": "D", "scenes": [{"text": f"Satz Nummer {n_} steht hier ganz."} for n_ in range(9)] + [{"text": "Und das sind genau die"}]})
        assert len(pl["scenes"]) == 9, "Schlusssatz, der auf einem Artikel endet, bleibt stehen"
        pl = _w_s.polish({"title": "T", "description": "D", "scenes": [{"text": f"Satz Nummer {n_} steht hier ganz."} for n_ in range(9)] + [{"text": "Und genau deshalb liebt dein Kopf das."}]})
        assert len(pl["scenes"]) == 10, "vollständiger Schlusssatz gestrichen"
        assert stage.poster_hero("5 verrückte Dinge, die dein Gehirn nachts tut", ss + ss, cast_s) == "brain", "Gehirn-Thema ohne Gehirn auf dem Titelbild"
        assert stage.poster_hero("Warum du bei Musik Gänsehaut bekommst", ss + ss, cast_s) != "brain", "Gehirn auf dem Titelbild eines anderen Themas"
        for tm_ in ("night", "day"):                             # Schlafende liegt zugedeckt im Bett: über dem Bettende ragen keine Füße in die Luft
            fr = frame({"text": "Du schläfst tief.", "place": "bedroom", "time": tm_, "actors": [{"id": "du", "action": "sleep", "pos": "center"}]}, cast_s, 1.3).convert("RGB")
            bare = frame({"text": "Leer.", "place": "bedroom", "time": tm_, "actors": [], "shot": "event"}, cast_s, 1.3).convert("RGB")
            from PIL import ImageChops as _IC
            box_ = _IC.difference(fr.crop((places.BED_END + 6, 880, 1080, 1260)), bare.crop((places.BED_END + 6, 880, 1080, 1260))).getbbox()
            assert tm_ == "night" or box_ is None, f"Schlafende ragt übers Bettende hinaus ({tm_}): {box_}"   # nachts unterscheidet sich das Licht (Lichtkegel), deshalb nur am Tag vergleichen
            px = fr.getpixel((560, 1100))
            assert px[2] > px[0], f"keine Decke über der Schlafenden ({tm_}): {px}"
    check("Schlaf-Video (keine Regie-Wörter, Nacht bleibt, Schlafende zugedeckt)", _sleep)

    def _fur():                                                  # Ausbau 17.11.2026 („Warum bekommen wir Gänsehaut?“): Fell-Tafel mit Luftschicht, Adrenalin-Tafel, Kälte, gesträubter Vorfahre
        from .. import main as _mn_f
        cast_f = {"du": {"shirt": "blau"}}
        T = [("Unsere Vorfahren hatten noch ein sehr viel dichteres Fell am gesamten Körper.", "forest", "", [], [{"id": "du", "action": "think"}], ""),
             ("Dadurch stellte sich das Fell auf und schloss eine wärmende Luftschicht ein.", "forest", "snow", ["goosebumps"], [], "event"),
             ("Das schützte effektiv vor eisiger Kälte und Frost im Winter.", "snow", "snow", ["goosebumps"], [], "event"),
             ("Aufgestellt wirkten unsere Vorfahren dadurch plötzlich deutlich größer.", "forest", "", ["goosebumps"], [], "event"),
             ("Adrenalin durchströmt in Sekundenschnelle unseren gesamten Organismus.", "livingroom", "", ["herz"], [{"id": "du", "action": "walk"}], ""),
             ("Du stehst im Wald und frierst in der eisigen Kälte.", "forest", "", [], [{"id": "du", "action": "talk"}], ""),
             ("Hier gibt es keine Kälte mehr.", "park", "", [], [{"id": "du", "action": "talk"}], ""),
             ("Er schloss die Augen und dachte nach.", "park", "", [], [{"id": "du", "action": "think"}], ""),
             ("Das Vorhängeschloss an der Tür war aufgebrochen.", "hallway", "", [], [{"id": "du", "action": "talk"}], "")]
        scs = stage.direct([{"text": t_, "place": pl, "time": "day", "weather": w_, "props": list(pr), "actors": [dict(a) for a in ac], "shot": sh} for t_, pl, w_, pr, ac, sh in T],
                           [(i * 4.0, i * 4.0 + 4.0) for i in range(len(T))], "Warum bekommen wir Gänsehaut?", "fakten", "")
        kn = lambda i: [extras.PROP_ALIASES.get(str(q.get("type") if isinstance(q, dict) else q).lower(), str(q.get("type") if isinstance(q, dict) else q).lower()) for q in scs[i].get("props") or []]   # noqa: E731
        ac = lambda i: [(a.get("kind") or "", a.get("action")) for a in scs[i].get("actors") or []]   # noqa: E731
        assert ac(0) and ac(0)[0][0] == "chimp", f"dichtes Fell der Vorfahren ohne Affen: {ac(0)}"
        assert kn(1) == ["fur"], f"Luftschicht ohne Fell-Tafel (oder mit Schloss/Gänsehaut): {kn(1)}"
        assert "fur" in kn(2) and "goosebumps" not in kn(2), f"Folgesatz Kälte: {kn(2)}"
        assert ac(3) == [("chimp", "puff")], f"aufgestellt/größer ohne gesträubten Affen: {ac(3)}"
        assert kn(4) == ["adrenaline"] and ac(4)[0][1] == "point", f"Adrenalin: {kn(4)} {ac(4)}"
        assert scs[5].get("weather") == "cold" and ac(5)[0][1] == "shiver", f"Kälte draußen: {scs[5].get('weather')} {ac(5)}"
        assert scs[6].get("weather") != "cold", "verneinte Kälte"
        assert not any("schloss" in k or k == "lib_burg" for i in (1, 7) for k in kn(i)), "„schloss“ als Verb zeigt ein Schloss"
        assert "lib_vorhaengeschloss" in kn(8) or "lib_vorhaengeschloss" not in extras.PROPS, f"Vorhängeschloss fehlt: {kn(8)}"
        for w_f in ("fell", "luftschicht", "kälte", "adrenalin", "nebenniere", "hautschnitt"):
            assert _mn_f.known_thing(w_f), "nicht als bekannt erkannt: " + w_f
        for sc_f in scs:
            for t_f in (0.1, 0.8, 2.6):
                frame(sc_f, cast_f, t_f)
        for k_f in ("fur", "adrenaline"):
            for t_f in (0.0, 0.7, 1.4, 3.3):
                frame({"place": "lab", "actors": [], "props": [{"type": k_f}], "shot": "insert"}, cast_f, t_f)
                frame({"place": "snow", "weather": "cold", "actors": [{"id": "du", "action": "shiver"}], "props": [{"type": k_f}]}, cast_f, t_f)
        for t_f in (0.0, 0.2, 1.0, 2.9):
            rig.pose_at("shiver", t_f, 3.0, "worried", 0.3, 1)
            assert extras.creature("chimp", t_f, -1, 0.0, "angry", 1.0, "puff") is not None
    check("Fell-Tafel, Adrenalin-Tafel, Kälte, gesträubter Vorfahre (Ausbau 17.11.)", _fur)

    def _tiny():                                                 # Prüfung 17.11.2026 („Dieses winzige Tier ist zäher als ein Löwe“): Löwe, Savanne, Bärtierchen bleibt das Tier des Videos, Tönnchen
        from .. import main as main_
        for act_l in ("idle", "roar", "walk"):
            for f_l in (1, -1):
                assert extras.creature("lion", 0.7, f_l, 0.0, "scared" if act_l == "walk" else "", 1.0, act_l) is not None
        assert extras.creature("tardigrade", 0.7, 1, 0.0, "", 1.0, "tun") is not None
        assert places.resolve("savanne") == "savannah" and places.background("savannah", False).size == (places.W, places.H)
        tx = ["Dieses winzige Tier ist zäher als ein Löwe.", "Das Bärtierchen ist nur einen halben Millimeter groß.", "Wenn es trocken wird, trocknet es fast komplett aus.",
              "So übersteht es enorme Hitze.", "Forscher schickten es sogar ins Weltall.", "Zurück auf der Erde gaben Forscher ihm ein paar Tropfen Wasser.",
              "Kurz darauf erwachte es und krabbelte davon.", "Du findest sie in fast jedem Moospolster."]
        pl = ["park", "lab", "forest", "kitchen", "space", "lab", "lab", "forest"]
        scs = stage.direct([{"text": t_, "place": p_, "time": "day", "props": [], "actors": [{"id": "du", "action": "talk", "pos": "center", "speaks": True}]} for t_, p_ in zip(tx, pl)],
                           [(i * 4.0, i * 4.0 + 4.0) for i in range(len(tx))], "Dieses winzige Tier ist zäher als ein Löwe", "tiere")
        ks = [[(a.get("kind") or "mensch", a.get("action")) for a in sc["actors"]] for sc in scs]
        assert [k for k, _ in ks[0]] == ["lion", "tardigrade"] and places.resolve(scs[0].get("place")) == "savannah" and not scs[0].get("float"), f"Löwe: {ks[0]} {scs[0].get('place')}"
        assert [k for k, _ in ks[1]] == ["tardigrade"] and ks[1][0][1] != "tun", f"Name: {ks[1]}"
        assert ks[2] == [("tardigrade", "tun")] and ks[3] == [("tardigrade", "tun")], f"Tönnchen: {ks[2:4]}"
        assert ks[4] == [("tardigrade", "tun")] and scs[4].get("float") == "float", f"All: {ks[4]} {scs[4].get('float')}"
        assert [k for k, _ in ks[5]] == ["mensch", "tardigrade"] and ks[5][1][1] == "tun", f"Wasser: {ks[5]}"
        assert [k for k, _ in ks[6]] == ["tardigrade"] and ks[6][0][1] != "tun", f"erwacht: {ks[6]}"
        assert ks[7][-1][0] == "tardigrade" and ks[7][-1][1] != "tun" and any(q.get("type") == "moss" for q in scs[7].get("props") or []), f"Moos: {ks[7]} {scs[7].get('props')}"
        for sc in scs:
            frame(sc, {"du": {"shirt": "grün"}})
        # Video 137: Einschub „Moospolster vor deiner Haustür“ wird zur Szene mit Moos und Tier; „enormer Druck“ spielt in der Tiefsee; Dächer/Mauern: kleines Tier am Moos; Hitze-Zahl als Zähler
        s3 = stage.direct([{"text": "Das Bärtierchen trocknet fast völlig aus.", "place": "park", "actors": [], "props": []},
                           {"text": "Als Tönnchen übersteht es Hitze von rund einhundertfünfzig Grad.", "place": "desert", "actors": [], "props": []},
                           {"text": "Es überlebt Kälte und enormen Druck.", "place": "cave", "actors": [], "props": []},
                           {"text": "Viele erwachten und krabbelten wieder los.", "place": "park", "actors": [], "props": []},
                           {"text": "Du findest diese Überlebenskünstler in fast jedem Moospolster vor deiner Haustür.", "place": "park", "shot": "insert", "props": [{"type": "door"}, {"type": "moss"}],
                            "actors": [{"id": "du", "action": "point"}]},
                           {"text": "Sogar auf Hausdächern und alten Mauern krabbeln sie herum.", "place": "street", "actors": [], "props": []}],
                          [(i * 4.0, i * 4.0 + 4.0) for i in range(6)], "Dieses winzige Tier ist zäher als ein Löwe", "tiere")
        assert (s3[1].get("overlay") or {}).get("value") == 150, f"Hitze-Zähler: {s3[1].get('overlay')}"
        assert places.resolve(stage.backdrop(s3[2])) == "underwater", "Druck nicht in der Tiefsee"
        assert s3[4].get("shot") != "insert" and [q.get("type") for q in s3[4].get("props") or []] == ["moss"] and any(a.get("kind") == "tardigrade" for a in s3[4]["actors"]), f"Moos-Einschub: {s3[4]}"
        assert [q.get("type") for q in s3[5].get("props") or []] == ["moss"] and not s3[5]["actors"][0].get("hero"), f"Dächer: {s3[5]}"
        s4 = stage.direct([{"text": "Das Bärtierchen ist winzig.", "place": "lab", "actors": [], "props": []},
                           {"text": "Ein Schutz-Eiweiß legt sich wie ein Schild um ihr Erbgut.", "place": "lab", "actors": [], "props": []}], [(0, 4), (4, 8)], "Tiere", "tiere")
        assert [q.get("type") for q in s4[1].get("props") or []] == ["shield"] and s4[1]["actors"][0].get("_ksz"), f"Schild: {s4[1]}"
        assert stage._prepare(dict(s4[1]), {})[3][0].get("ksz"), "Größe je Figur geht in _prepare verloren"
        for sc in s3 + s4:
            frame(sc, {"du": {"shirt": "grün"}})
        # ein Löwe ohne Winzling-Video: steht als Tier neben dem Menschen; Redewendungen meinen keinen Löwen
        s2 = stage.direct([{"text": "Ein Löwe schläft bis zu zwanzig Stunden am Tag.", "place": "park", "time": "day", "props": [], "actors": [{"id": "du", "action": "talk", "pos": "center"}]},
                           {"text": "Du bekommst den Löwenanteil vom Kuchen.", "place": "kitchen", "time": "day", "props": [], "actors": [{"id": "du", "action": "talk", "pos": "center"}]}],
                          [(0, 4), (4, 8)], "Fakten", "fakten")
        assert any(a.get("kind") == "lion" for a in s2[0]["actors"]) and not any(a.get("kind") == "lion" for a in s2[1]["actors"]), "Löwe/Löwenanteil"
        # Ähnlichkeits-Sperre: Frage- und Fürwörter tragen kein Thema, Vorgaben hinter dem Gedankenstrich zählen nicht
        assert not (main_._stems("Warum dieses winzige Tier gefährlicher ist als ein Löwe") & main_._stems("Warum du bei Musik Gänsehaut bekommst"))
        assert main_._topic_core("Warum bekommen wir Gänsehaut? – Vorgaben: winzige Muskeln") == "Warum bekommen wir Gänsehaut?"
    check("Winzling/Löwe", _tiny)

    def _goose():                                                # Prüfung 17.11.2026: Katze sträubt ihr Fell, „dir ist kalt“, gerupfte Gans, Mäuse
        T = [("Eine Katze sträubt ihr Fell heute noch genauso.", "forest"), ("Dir ist kalt.", "snow"),
             ("Der Name kommt daher, dass deine Haut dann aussieht wie die einer gerupften Gans.", "livingroom"),
             ("Forscher fanden bei Mäusen heraus, dass derselbe Muskel das Haarwachstum anregt.", "lab"), ("Dir ist nicht kalt.", "park")]
        scs = stage.direct([{"text": t_, "place": pl, "time": "day", "actors": [{"id": "du", "action": "talk", "emotion": "neutral", "speaks": True}]} for t_, pl in T],
                           [(i * 3.5, i * 3.5 + 3.5) for i in range(len(T))], "Warum bekommen wir Gänsehaut?", "fakten", "")
        kn = lambda i: [str(q.get("type") if isinstance(q, dict) else q).lower() for q in scs[i].get("props") or []]   # noqa: E731
        ac = lambda i: [(a.get("kind") or "", a.get("action")) for a in scs[i].get("actors") or []]   # noqa: E731
        assert ac(0) == [("cat", "puff")], f"Katze sträubt ihr Fell: {ac(0)}"
        assert scs[1].get("weather") == "cold", f"„dir ist kalt“ draußen: {scs[1].get('weather')} {ac(1)}"
        assert scs[4].get("weather") != "cold", "verneintes „kalt“"
        if "lib_gerupfte_gans" in extras.PROPS:
            assert "lib_gerupfte_gans" in kn(2), f"gerupfte Gans fehlt: {kn(2)}"
        if "lib_maus" in extras.PROPS:
            assert "lib_maus" in kn(3), f"Mäuse fehlen: {kn(3)}"
        from .. import writer as _wg
        assert _wg.given_meta({}, "x – y. Titel: Warum bekommen wir Gänsehaut? Titelbild-Text: WARUM GÄNSEHAUT?") == {"title": "Warum bekommen wir Gänsehaut?", "thumbnail": {"text": "WARUM GÄNSEHAUT?"}}
        assert _wg.given_meta({}, "x. Titel: 5 Dinge, die dein Gehirn tut, während du schläfst. Titelbild-Text: DEIN GEHIRN NACHTS")["title"] == "5 Dinge, die dein Gehirn tut, während du schläfst"
        sc_h = [{"text": "Dir ist kalt, und die Härchen stellen sich auf."}, {"text": "An jeder Haarwurzel sitzt ein winziger Muskel, er richtet das Haar auf."},
                {"text": "Deine Haut wölbt sich dabei zu kleinen Hügeln."}, {"text": "Steuern kannst du das nicht."}]
        assert _wg.hook_drops(sc_h, "Warum du Gänsehaut bekommst.", "Und der wahre Grund wird dich überraschen."), "Einstieg löscht die Erklärung"
        assert not _wg.hook_drops([{"text": "a"}, {"text": "Und das Ende wird dich überraschen."}] + sc_h, "Warum du Gänsehaut bekommst.", "Und der Grund ist uralt.")
        T2 = [("Bei Kälte stellte sich das Fell auf und schloss eine wärmende Luftschicht ein.", "snow", [{"id": "vorfahre", "action": "shiver"}], []),
              ("Das wirkte wie eine dickere Jacke.", "snow", [], ["coat"]),
              ("Ausgelöst wird er auch von Adrenalin, deshalb bekommst du Gänsehaut bei Angst.", "livingroom", [{"id": "du", "action": "cower"}], ["adrenaline", "goosebumps"]),
              ("Gänsehaut ist ein Gruß deiner Vorfahren.", "forest", [{"id": "du", "action": "wave"}, {"id": "vorfahre", "action": "wave"}], [])]
        s2 = stage.direct([{"text": t_, "place": pl, "time": "day", "actors": a_, "props": pr} for t_, pl, a_, pr in T2],
                          [(i * 3.5, i * 3.5 + 3.5) for i in range(len(T2))], "Warum bekommen wir Gänsehaut?", "fakten", "")
        k2 = lambda i: [extras.PROP_ALIASES.get(str(q.get("type") if isinstance(q, dict) else q).lower(), str(q.get("type") if isinstance(q, dict) else q).lower()) for q in s2[i].get("props") or []]   # noqa: E731
        assert all(a.get("kind") == "chimp" for i in (0, 3) for a in s2[i]["actors"] if a.get("id") == "vorfahre"), "Figur „vorfahre“ ist ein Mensch im Pulli"
        assert k2(1) == ["fur"], f"Jacken-Vergleich: {k2(1)}"
        s3 = stage.direct([{"text": "Bei Kälte stellte sich das Fell auf und schloss eine wärmende Luftschicht ein, wie eine dickere Jacke.", "place": "forest", "time": "day",
                            "actors": [{"id": "vorfahre", "action": "idle"}], "props": ["fur", "coat"]},
                           {"text": "Forscher fanden bei Mäusen heraus, dass derselbe Muskel bei Kälte das Haarwachstum anregt.", "place": "forest", "time": "day", "actors": [], "props": ["muskel"]}],
                          [(0, 3.5), (3.5, 7)], "Warum bekommen wir Gänsehaut?", "fakten", "")
        k3 = lambda i: [extras.PROP_ALIASES.get(str(q.get("type") if isinstance(q, dict) else q).lower(), str(q.get("type") if isinstance(q, dict) else q).lower()) for q in s3[i].get("props") or []]   # noqa: E731
        assert not any("jacke" in k or k == "coat" for k in k3(0)), f"Jacke neben der Fell-Tafel: {k3(0)}"
        assert not any("muskel" in k for k in k3(1)), f"Oberarm beim Haar-Muskel: {k3(1)}"
        s4 = stage.direct([{"text": "Dir ist kalt oder du erschrickst, und plötzlich stellen sich die Härchen auf.", "place": "livingroom", "time": "day", "weather": "cold",
                            "actors": [{"id": "du", "action": "shiver"}], "props": []}], [(0, 3.5)], "Warum bekommen wir Gänsehaut?", "fakten", "")
        assert not s4[0].get("weather"), "Eiskristalle im Wohnzimmer"
        assert k2(2) == ["adrenaline"], f"zwei Tafeln übereinander: {k2(2)}"
        p3 = sorted(a.get("pos") for a in s2[3]["actors"])
        assert len(p3) == 2 and isinstance(p3[0], int) and p3[1] - p3[0] >= 300, f"Mensch und Vorfahre stehen ineinander: {p3}"
        for sc_g in s2:
            frame(sc_g, {"du": {"shirt": "blau"}, "vorfahre": {"shirt": "braun"}}, 1.2)
        for t_g in (0.1, 0.8, 2.6):
            assert extras.creature("cat", t_g, 1, 0.0, "angry", 1.0, "puff") is not None
            assert extras.creature("cat", t_g, -1, 0.0, "angry", 0.5, "puff") is not None
        for sc_g in scs:
            frame(sc_g, {"du": {"shirt": "blau"}}, 1.2)
    check("Katze sträubt das Fell, „dir ist kalt“, gerupfte Gans, Mäuse (Prüfung 17.11.)", _goose)

    def _feast():                                                # Prüfung 18.11.2026 (Video 148): Weihnachten am Esstisch, Verwandte im Bild, „greifen“ ist kein Reifen
        T = [("Weihnachten mit der Familie eskaliert nach dem ersten Gang.", "diningroom", "day", [{"id": "du", "action": "shocked"}], ["table"]),
             ("Oma zieht seelenruhig eine Trillerpfeife aus der Handtasche.", "livingroom", "day", [{"id": "du", "action": "talk", "emotion": "angry"}], []),
             ("Dein Onkel erzählt dir zum zehnten Mal dieselbe Geschichte.", "livingroom", "night", [{"id": "du", "action": "idle"}], []),
             ("Alle greifen endlich nach dem Kartoffelsalat.", "livingroom", "night", [{"id": "du", "action": "idle"}], []),
             ("Unter dem Weihnachtsbaum liegen die Geschenke.", "diningroom", "night", [{"id": "du", "action": "idle"}], ["tree"])]
        scs = stage.direct([{"text": t_, "place": pl, "time": tm, "actors": a_, "props": pr} for t_, pl, tm, a_, pr in T],
                           [(i * 3.5, i * 3.5 + 3.5) for i in range(len(T))], "Weihnachten mit der Familie", "comedy", "")
        ids = lambda i: [str(a.get("id")) for a in scs[i].get("actors") or []]   # noqa: E731
        kn = lambda i: [str(q.get("type") if isinstance(q, dict) else q).lower() for q in scs[i].get("props") or []]   # noqa: E731
        assert scs[0]["place"] == "diningroom" and scs[0].get("_xmas"), f"erster Gang spielt am Esstisch: {scs[0]['place']}"
        assert ids(1) == ["oma"], f"Oma steht im Bild: {ids(1)}"
        assert ids(2) == ["du", "onkel"], f"Onkel neben der Hauptfigur: {ids(2)}"
        assert scs[3]["place"] == "diningroom" and "tire" not in kn(3), f"Kartoffelsalat am Tisch, kein Reifen: {scs[3]['place']} {kn(3)}"
        assert scs[4]["place"] == "livingroom" and "tree" not in kn(4), f"Baum im Wohnzimmer: {scs[4]['place']} {kn(4)}"
        assert {sc.get("time") for sc in scs} == {"day"}, "eine Tageszeit für das ganze Fest"
        s5 = stage.direct([{"text": "Nummer zwei, der Onkel.", "place": "livingroom", "time": "night", "actors": [{"id": "onkel", "action": "sit"}]},
                           {"text": "Der Onkel sitzt auf dem Sofa am Weihnachtsbaum und erzählt dieselbe Geschichte.", "place": "livingroom", "time": "night", "shot": "insert",
                            "props": ["lib_sofa"], "actors": [{"id": "onkel", "action": "talk"}]},
                           {"text": "Schaust du das am Familientisch? Dann bist du Nummer vier. Wer sitzt bei euch am Tisch?", "place": "diningroom", "time": "night",
                            "actors": [{"id": "du", "action": "shocked"}], "overlay": {"type": "choice", "a": "NACHSCHLAG KOMMT", "b": "VIERTER TYP"}}],
                          [(0, 3.5), (3.5, 7), (7, 12)], "Vier Typen an Weihnachten am Familientisch", "comedy", "")
        assert s5[1]["shot"] == "" and not s5[1]["props"], f"Onkel auf dem Sofa ist kein Sofa allein: {s5[1]['shot']} {s5[1]['props']}"
        assert s5[2].get("overlay") is None, "Auswahl über drei Schlusssätzen entfällt"
        assert {sc.get("time") for sc in s5} == {"day"}, "Festzimmer hell erleuchtet"
        for sc in scs:
            frame(sc, {"du": {"shirt": "grün"}})
        assert places.resolve("esszimmer") == "diningroom"
        assert stage._hint("Im Gang brennt noch Licht.") == "hallway" and stage._hint("Nach dem zweiten Gang wird es still.") != "hallway"
        pl_, _n, _s, ac_, _p, _w = stage._prepare({"text": "Der Vogel springt auf.", "place": "livingroom", "actors": [{"id": "vogel", "action": "jump"}]}, {"du": {}, "truthahn": {"kind": "bird"}})
        assert ac_[0]["kind"] == "bird", f"Kennung „vogel“ ist ein Vogel: {ac_[0]['kind']}"
        T4 = [("Nummer eins, die Oma, füllt meinen Teller.", "diningroom", [{"id": "oma", "action": "talk"}, {"id": "du", "action": "sit"}], []),
              ("Der Onkel erzählt dieselbe Geschichte.", "diningroom", [{"id": "onkel", "action": "talk"}], []),
              ("In Umfragen liegt an Heiligabend in Deutschland Kartoffelsalat mit Würstchen ganz vorn.", "germany", [{"id": "du", "action": "walk"}], []),
              ("Sogar noch vor der festlichen Gans landet dieser Klassiker auf den Tellern.", "street", [], ["table", "lib_gans"]),
              ("Diese vier Typen sitzen an jedem Familientisch.", "diningroom", [{"id": "du", "action": "talk"}], [])]
        s4 = stage.direct([{"text": t_, "place": pl, "time": "day", "actors": a_, "props": pr} for t_, pl, a_, pr in T4],
                          [(i * 3.5, i * 3.5 + 3.5) for i in range(len(T4))], "Vier Typen, die an Weihnachten an jedem Familientisch sitzen", "comedy", "")
        assert s4[2]["place"] == "diningroom" and s4[3]["place"] == "diningroom", f"Essens-Sätze am Tisch statt Karte/Straße: {s4[2]['place']} {s4[3]['place']}"
        assert s4[3]["actors"] and not [q for q in s4[3]["props"] if "gans" in str(q.get("type"))], f"keine lebende Gans am Esstisch: {s4[3]['props']}"
        assert not any(str(a.get("id")).startswith("_team") for a in s4[4]["actors"]), f"Gruppe aus Verwandten: {[a.get('id') for a in s4[4]['actors']]}"
        for sc in s4:
            frame(sc, {"du": {"shirt": "grün"}})
        from .. import writer as _wf
        assert _wf.hook_drops([{"text": "a"}, {"text": "Nummer eins, die Oma, füllt Teller."}, {"text": "Wer satt sagt, bekommt Nachschlag."}], "Vier Typen an Weihnachten.", "Und der letzte bist du.")
        s3 = stage.direct([{"text": "Die Mutter säugt ihre Jungen.", "place": "forest", "time": "day", "actors": [{"id": "katze", "kind": "cat", "action": "idle"}]}], [(0, 3.5)], "Katzen", "tiere", "")
        assert "mama" not in [str(a.get("id")) for a in s3[0]["actors"]] and any(a.get("kind") == "cat" for a in s3[0]["actors"]), "Tier-Szene bleibt ohne Verwandte"

    check("Weihnachten am Esstisch, Verwandte im Bild (Prüfung 18.11., Video 148)", _feast)

    def _body():                                                 # Körper-Sätze (Prüfung 16.11.2026, Video 126): die Figur macht vor, was der Satz beschreibt; Gehirn als Figur statt Passanten; „Welle“ ist kein Strand
        cast_b = {"du": {"shirt": "blau", "hair": "curly", "gender": "w"}}
        T = [("Ein lauter Knall, und du zuckst zusammen.", "livingroom", "shocked", ""), ("Zuerst blinzeln die Augen, um sich zu schützen.", "livingroom", "shocked", ""),
             ("Dann ziehst du den Kopf ein, Nacken und Schultern spannen sich an.", "livingroom", "shocked", ""),
             ("Das schützt den Nacken, die Welle läuft von oben nach unten.", "livingroom", "shocked", ""),
             ("Die Beine reagieren zuletzt.", "livingroom", "look_around", "close"), ("Du atmest schneller, mehr Blut fließt in die Muskeln.", "livingroom", "run", ""),
             ("Die Pupillen weiten sich und lassen mehr Licht herein.", "livingroom", "shocked", ""), ("Oft erstarrst du erst einen Moment.", "hallway", "shocked", "close"),
             ("In dieser Schreckstarre prüft das Gehirn die Lage.", "street", "shocked", ""), ("Herz und Pupillen beruhigen sich rasch.", "livingroom", "walk", ""),
             ("Deshalb zittern die Hände noch Minuten später.", "livingroom", "shake", "close")]
        scs = stage.direct([{"text": t_, "place": pl, "time": "day", "crowd": "worried" if pl == "street" else "", "shot": sh,
                             "actors": [{"id": "du", "action": ac, "emotion": "scared"}]} for t_, pl, ac, sh in T],
                           [(i * 3.5, i * 3.5 + 3.5) for i in range(len(T))], "Was in deinem Körper passiert, wenn du dich erschrickst", "fakten", "")
        act = lambda i: str(scs[i]["actors"][0].get("action"))   # noqa: E731
        assert act(0) == "cower" and act(2) == "cower", "Zusammenzucken/Kopf einziehen wird nicht gespielt"
        assert act(1) == "blink" and scs[1].get("shot") == "close", "Blinzeln ohne Großaufnahme"
        assert stage.places.resolve(stage.backdrop(scs[3])) != "beach", "„die Welle läuft von oben nach unten“ spielt am Strand"
        assert scs[4].get("shot") != "close", "Satz über die Beine als Großaufnahme des Gesichts"
        assert act(5) == "pant" and act(6) == "pupils" and act(7) == "freeze" and scs[7].get("shot") != "close", "Atmen/Pupillen/Erstarren fehlen"
        assert any(a.get("kind") == "brain" for a in scs[8]["actors"]) and not scs[8].get("crowd"), "Gehirn-Satz ohne Gehirn-Figur oder mit Passanten"
        assert stage.places.resolve(stage.backdrop(scs[8])) != "street", "Gehirn-Satz spielt auf der Straße"
        assert act(9) != "pupils", "„Pupillen beruhigen sich“ zeigt sich weitende Pupillen"
        assert act(10) == "tremble", "zitternde Hände fehlen"
        T2 = ["Ein lauter Knall lässt alle zusammenfahren.", "Das geht schneller als jeder Gedanke.", "Die Beine reagieren zuletzt und machen sich bereit zum Start.", "Das Herz pumpt mehr Blut in die Muskeln.",
              "Die Verdauung macht Pause.", "Die Nebennieren schütten Adrenalin aus.", "Der Reflex ist uralt.", "Die Haut wird blass."]
        scs2 = stage.direct([{"text": t_, "place": "livingroom", "time": "day", "mood": "tense", "actors": [{"id": "du", "action": "talk"}]} for t_ in T2],
                            [(i * 3.5, i * 3.5 + 3.5) for i in range(len(T2))], "Was in deinem Körper passiert, wenn du dich erschrickst", "fakten", "")
        for sc_b in scs2[2:]:
            assert stage.places.resolve(stage.backdrop(sc_b)) != "street" and not sc_b.get("crowd"), "Körper-Satz als Straßenbild mit Passanten: " + sc_b["text"]
        for sc_b in scs:
            for t_b in (0.1, 1.2, 2.4):
                frame(sc_b, cast_b, t_b)
        for ac_b in ("cower", "freeze", "tremble", "blink", "pant", "pupils"):
            for t_b in (0.0, 0.2, 1.0, 2.9):
                rig.pose_at(ac_b, t_b, 3.0, "scared", 0.3, 1)
        from .. import writer as _wr_b
        js_b = _wr_b.polish({"title": "t", "description": "d", "hashtags": ["#koerper"], "tags": ["koerperreaktion"],
                              "scenes": [{"text": "Dann die Finte: Du denkst, du rennst sofort los."}, {"text": "Die Finte des Gegners ist klug."}]})
        assert js_b["hashtags"] == ["#körper"] and js_b["scenes"][0]["text"].startswith("Du denkst") and js_b["scenes"][1]["text"].startswith("Die Finte"), "Regie-Wort gesprochen oder Umlaute fehlen"

    check("Körper-Sätze (Zusammenzucken, Blinzeln, Erstarren, Gehirn-Figur)", _body)

    def _stretched_word():                                       # Sprach-Abgleich (Video 128): ein gedehntes Wort vor einer überhörten Stelle darf dem überhörten Satz nicht die Zeit nehmen
        from .. import ai as _ai_s
        txt_s = "Die Verdauung bremst. Deine Pupillen weiten sich und lassen mehr Licht herein. Du denkst nach."
        heard_s = [("Die", 0.0, 0.2), ("Verdauung", 0.2, 0.9), ("bremst", 0.9, 5.4), ("Du", 5.5, 5.7), ("denkst", 5.7, 6.1), ("nach", 6.1, 6.5)]
        out_s, _ = _ai_s.match_words(txt_s, heard_s, 6.6)
        assert out_s[3][1] < 2.2 and out_s[10][2] > 4.5, f"überhörter Satz zusammengequetscht: {out_s[3]} … {out_s[10]}"
        assert all(b_[1] >= a_[1] for a_, b_ in zip(out_s, out_s[1:])), "Wort-Zeiten nicht aufsteigend"

    check("Sprach-Abgleich: gedehntes Wort vor überhörter Stelle", _stretched_word)

    def _sea():                                                  # Meerestiere: das genannte Tier ist die Figur, allein und unter Wasser
        T = [("Ein winziger Krebs erzeugt unter Wasser rund viertausendfünfhundert Grad.", "livingroom", [{"id": "du", "action": "shocked", "hold": "phone"}], ["computer"], "close"),
             ("Der Pistolenkrebs knallt seine Schere zu.", "underwater", [], ["explosion"], "event"),
             ("Die unsterbliche Qualle altert rückwärts.", "underwater", [], ["wave"], "event"),
             ("Sie verwandelt ihre Zellen zurück.", "underwater", [{"id": "qualle", "kind": "fish", "action": "jump"}], [], "insert"),
             ("Und jetzt Kraft Nummer drei.", "underwater", [], ["rock"], "event"),
             ("Der Fangschreckenkrebs boxt wie eine Gewehrkugel.", "underwater", [{"id": "krebs", "kind": "monster"}], ["rock"], "event"),
             ("Damit zertrümmert er dicke Aquarienscheiben aus Glas.", "underwater", [], [], "event"),
             ("Mein Goldfisch schaut mich seitdem verdächtig an.", "livingroom", [{"id": "du"}], ["glass"], ""),
             ("Mein Onkel hat Krebs besiegt.", "livingroom", [{"id": "du"}], [], "")]
        scs = stage.direct([{"text": t_, "place": pl_, "actors": a_, "props": pr_, "shot": sh_, "overlay": {"type": "thermo", "value": 44000} if not n_ else None}
                            for n_, (t_, pl_, a_, pr_, sh_) in enumerate(T)], [(n_ * 3, n_ * 3 + 3) for n_ in range(len(T))], "3 Tier-Superkräfte")
        want = ["shrimp", "shrimp", "jelly", "jelly", "mantis", "mantis", "mantis"]
        for n_, k_ in enumerate(want):
            ks = [a.get("kind") for a in scs[n_].get("actors") or []]
            assert ks == [k_], f"Meerestier Szene {n_}: {ks} statt {k_}"
            assert places.resolve(stage.backdrop(scs[n_])) == "underwater", f"Meerestier Szene {n_} nicht unter Wasser"
            assert not any(q.get("type") in ("explosion", "wave") for q in scs[n_].get("props") or []), "Explosion/Welle unter Wasser"
            frame(scs[n_], {"du": {"shirt": "blau"}})
        assert scs[0].get("overlay") is None, "Thermometer mit nicht gesprochener Zahl"
        assert [q.get("type") for q in scs[7].get("props") or []] == ["aquarium"], "Goldfisch ohne Aquarium"
        assert not any(a.get("kind") for a in scs[8].get("actors") or []) and places.resolve(stage.backdrop(scs[8])) != "underwater", "Krankheit Krebs als Tier"
        g = stage.direct([{"text": "Sein Schlag erreicht achtzig Kilometer pro Stunde.", "place": "underwater", "shot": "graphic",
                           "graphic": {"type": "compare", "left": "SCHLAG", "right": "SCHNEIDEN", "value": "80 km/h", "sub": "80 km/h"}}], [(0, 3)], "Tiere")
        assert (g[0].get("graphic") or {}).get("type") != "compare", "Vergleich mit zweimal derselben Zahl"
        TW = [("Als vierte Zutat pflanzen wir das Herz eines Blauwals in die Brust.", "lab", [{"id": "du"}], ""),      # Ausbau 19.11.2026: Blauwal als Wesen
              ("Wir gehen heute zur Wahl und essen eine Walnuss.", "livingroom", [{"id": "du"}], ""),
              ("Der Schweinswal ist der einzige Wal der Ostsee.", "underwater", [], "")]
        for n_, (t_, pl_, a_, sh_) in enumerate(TW):
            w_ = stage.direct([{"text": t_, "place": pl_, "actors": a_, "shot": sh_}], [(0, 4)], "Tiere im Vergleich")[0]
            ks = [x.get("kind") for x in w_.get("actors") or []]
            if n_ == 0:
                assert ks == ["whale"] and places.resolve(stage.backdrop(w_)) == "underwater", f"Blauwal: {ks} am Ort {stage.backdrop(w_)}"
                assert frame(w_, {"du": {"shirt": "blau"}}).getbbox(), "Blauwal-Bild leer"
            else:
                assert "whale" not in ks, f"Wal, wo keiner gemeint ist ({t_}): {ks}"
        from .. import main as _main_w
        assert _main_w.known_thing("blauwal") and _main_w.known_thing("wal"), "Blauwal gilt als unbekannt"
        T2 = [("Kandidat Nummer zwei ist der Axolotl.", "lab", [{"id": "du"}], "graphic"), ("Sogar Rückenmark wächst lückenlos nach.", "lab", [{"id": "du", "action": "shocked"}], ""),
              ("Mediziner erforschen das, um Menschen zu helfen.", "lab", [{"id": "du"}], ""), ("Bärtierchen überleben extreme Kälte.", "kitchen", [{"id": "du", "action": "walk"}], ""),
              ("Sie trocknen jahrelang ohne Wasser einfach aus.", "desert", [], ""), ("Dann wachen sie auf und krabbeln einfach weiter.", "lab", [{"id": "du"}], ""),
              ("Schreib deine Wahl in die Kommentare.", "bedroom", [{"id": "du"}], "")]
        s2 = stage.direct([{"text": t_, "place": pl_, "actors": a_, "shot": sh_, "graphic": {"type": "round", "kicker": "KRAFT 2", "text": "REGENERATION"} if sh_ else None}
                           for t_, pl_, a_, sh_ in T2], [(n_ * 3, n_ * 3 + 3) for n_ in range(len(T2))], "3 Tiere mit Superkräften")
        kinds = [[a.get("kind") or "" for a in sc_.get("actors") or []] for sc_ in s2]
        assert kinds[1] == ["axolotl"], f"Axolotl-Folgesatz: {kinds[1]}"
        assert kinds[2] == [""] and kinds[6] == [""], f"Menschen-Sätze: {kinds[2]} {kinds[6]}"
        assert kinds[3] == ["tardigrade"] and kinds[4] == ["tardigrade"] and kinds[5] == ["tardigrade"], f"Bärtierchen: {kinds[3:6]}"
        for sc_ in s2:
            frame(sc_, {"du": {"shirt": "blau"}})
        T3 = [("Ein Gepard jagt mit hundertzwanzig Kilometern pro Stunde.", "fields", []), ("Er erreicht hundertzwanzig Kilometer pro Stunde.", "fields", []),
              ("Das Problem ist die Landung.", "lab", [{"id": "du"}]), ("Der Adler sieht eine Maus aus drei Kilometern.", "mountain", []),
              ("Ein Floh springt das Zweihundertfache seiner Länge.", "lab", [{"id": "du"}]), ("Naturgesetze gelten immer.", "lab", [{"id": "du"}])]
        s3 = stage.direct([{"text": t_, "place": pl_, "actors": a_} for t_, pl_, a_ in T3], [(n_ * 3, n_ * 3 + 3) for n_ in range(len(T3))], "Was passiert, wenn wir Tiere kreuzen?")
        k3 = [[(a.get("kind") or "", a.get("action") or "") for a in sc_.get("actors") or []] for sc_ in s3]
        assert k3[0] == [("cheetah", "run")] and k3[1] == [("cheetah", "run")], f"Gepard: {k3[:2]}"
        assert not any(k_ for k_, _a in k3[2]) and not any(k_ for k_, _a in k3[5]), f"Landtier bleibt zu lange: {k3[2]} {k3[5]}"
        assert [k_ for k_, _a in k3[3]] == ["eagle"] and k3[4] == [("flea", "jump")], f"Adler/Floh: {k3[3:5]}"
        for sc_ in s3:
            for t_ in (0.2, 1.3):
                frame(sc_, {"du": {"shirt": "blau"}}, t=t_)
        assert not stage.spoken_number(700, "rund viertausend siebenhundert Grad") and stage.spoken_number(4700, "rund viertausend siebenhundert Grad"), "geteiltes Zahlwort"
        assert stage.spoken_number(700, "siebenhundert Grad") and stage.spoken_number(3000, "dreitausend Menschen"), "Zahlwort"
    check("Meerestiere", _sea)
    def _hero():                                                 # Tier im Titel wird Hauptfigur: groß, mit Gefühl, nicht doppelt als Gegenstand
        scs = stage.direct([{"text": "Die Spinne sitzt in deinem Zimmer.", "place": "bedroom", "props": ["lib_tarantel"], "actors": [{"id": "du", "action": "shocked"}]},
                            {"text": "Sie frisst Käfer.", "place": "park", "props": ["lib_tarantel"], "actors": [{"id": "du"}, {"id": "b", "kind": "bee"}]},
                            {"text": "Schluss.", "place": "bedroom"}], [(i * 3, i * 3 + 3) for i in range(3)], "Was wäre, wenn Taranteln Deutschland erobern?")
        heroes = [sc_ for sc_ in scs if any(a.get("kind") == "spider" and a.get("hero") for a in (sc_.get("actors") or []))]
        assert heroes, "Spinne nie als Hauptfigur"
        assert not any(q.get("type") == "lib_tarantel" for sc_ in heroes for q in sc_.get("props") or []), "Spinne doppelt"
        assert scs[1]["props"], "Spinne fehlt neben der Biene"
        for sc_ in scs:
            frame(sc_, t=1.0)
        frame({"place": "park", "actors": [{"id": "x", "kind": "spider", "hero": True}], "shot": "close"})
    check("Tier als Hauptfigur", _hero)
    def _explain():                                              # Erklär-Einblendungen aus dem Satz
        T = ["Taranteln fressen Unmengen an Käfern, Maulwurfsgrillen und schädlichen Insekten.", "Bei zweiundzwanzig Grad fühlt sie sich wohl.",
             "In der Antarktis hat es minus achtzig Grad.", "Der Akku hat nur noch elf Prozent.", "Das ist nicht giftig.", "Das ist streng verboten.",
             "Mit Würfeln, Kugeln und Steinen."]
        scs = stage.direct([{"text": t, "place": "park", "actors": [{"id": "du"}]} for t in T], [(i * 3, i * 3 + 3) for i in range(len(T))], "Test")
        ov = [sc_.get("overlay") or {} for sc_ in scs]
        assert ov[0] == {"type": "checklist", "title": "SPEISEKARTE", "items": [["Käfer", True], ["Maulwurfsgrillen", True], ["Insekten", True]]}, ov[0]
        assert ov[1] == {"type": "thermo", "value": 22.0}, ov[1]
        assert ov[2] == {"type": "thermo", "value": -80.0}, ov[2]
        assert ov[3] == {"type": "bar", "label": "AKKU", "value": 11.0}, ov[3]
        assert ov[4].get("type") != "stamp", "verneinter Stempel"
        assert ov[5] == {"type": "stamp", "text": "VERBOTEN", "color": "red"}, ov[5]
        assert ov[6]["items"][1][0] == "Kugeln", ov[6]
        for o in ov:
            if o:
                assert overlays.frames_for(o), o
    check("Erklär-Einblendungen", _explain)
    def _tw():                                                   # Tageszeit, Wetter und Zitat aus dem Satz
        T = ["Nachts wird es im Garten richtig kalt.", "Draußen regnet es in Strömen.", "Es regnet nicht mehr.", "Im Wohnzimmer hört man den Regen.",
             "Forscher warnen, dass es noch schlimmer wird.", "Max sagt, dass er kommt."]
        scs = stage.direct([{"text": t, "place": "livingroom" if "Wohnzimmer" in t else "park", "time": "day", "actors": [{"id": "du"}]} for t in T],
                           [(i * 3, i * 3 + 3) for i in range(len(T))], "Test")
        assert scs[0]["time"] == "night", scs[0]
        assert scs[1].get("weather") == "rain", scs[1]
        assert not scs[2].get("weather"), "verneinter Regen"
        assert not scs[3].get("weather"), "Regen im Zimmer"
        assert scs[4]["overlay"] == {"type": "quote", "title": "FORSCHER WARNEN", "text": "…dass es noch schlimmer wird."}, scs[4]["overlay"]
        assert (scs[5].get("overlay") or {}).get("type") != "quote", "Zitat mit Namen"
        for sc_ in scs:
            frame(sc_, t=1.0)
    check("Tageszeit, Wetter, Zitat", _tw)
    def _cuts():                                                 # neue Wesen, Gruppen und Schnitt mitten im Satz
        import tempfile
        from pathlib import Path
        scs = stage.direct([{"text": "Ich hab mir einen KI-Agenten geholt.", "place": "office", "actors": [{"id": "du"}]},
                            {"text": "Die Agenten arbeiten Tag und Nacht.", "place": "office", "actors": []},
                            {"text": "Einer hat meinen Computer übernommen.", "place": "office", "props": ["computer"], "actors": [{"id": "du"}]}],
                           [(i * 3.6, i * 3.6 + 3.6) for i in range(3)], "Ich hab mir KI-Agenten geholt")
        assert any(a.get("kind") == "agent" for a in scs[0]["actors"]), scs[0]["actors"]
        assert [a.get("kind") for a in scs[1]["actors"]] == ["agent"] * 3, scs[1]["actors"]
        with tempfile.TemporaryDirectory() as tmp:
            for i, sc_ in enumerate(scs):
                stage.render_scene(sc_, {}, 2.8, Path(tmp) / f"c{i}.mp4", index=i)
    check("Schnitt im Satz und Gruppen", _cuts)
    def _brain():                                                # Gehirn als Figur, Fachbegriff als Schild, Schnitt nur auf genannte Dinge
        scs = stage.direct([{"text": "Dein Gehirn schlägt Alarm.", "place": "zimmer", "props": [{"type": "computer"}],
                             "actors": [{"id": "gehirn_bot", "action": "shocked", "emotion": "shocked"}]},
                            {"text": "Das nennt sich hypnagoger Zuckungsimpuls.", "place": "schlafzimmer", "time": "night", "actors": [{"id": "du"}]},
                            {"text": "Das ist der sogenannte Türrahmen-Effekt.", "place": "flur", "actors": [{"id": "du"}]}],
                           [(i * 3.6, i * 3.6 + 3.6) for i in range(3)], "Drei Macken deines Gehirns")
        _pl, _n, _s, acts, props, _w = stage._prepare(scs[0], {"gehirn_bot": {"kind": "agent"}})
        assert [a["kind"] for a in acts] == ["brain"], acts
        assert not stage._said_prop("computer", scs[0]["text"].lower()) and stage._said_prop("computer", "am pc zocken")
        assert (scs[1].get("overlay") or {}).get("text") == "HYPNAGOGER ZUCKUNGSIMPULS", scs[1].get("overlay")
        assert stage._term("Das nennt sich Liebe.") is None and stage._term("Er nennt sich selbst König.") is None
        for m in ("", "angry", "shocked", "sad", "happy"):
            assert extras.creature("brain", 1.0, -1, 0.5, m, 1.0)
        for sc_ in scs:
            frame(sc_)
    check("Gehirn-Figur, Fachbegriff, genannte Dinge", _brain)
    def _bed():                                                  # Schlafen/Wecken spielt im Schlafzimmer mit der Hauptfigur – nicht auf der Straße
        scs = stage.direct([{"text": "Dein Gehirn schlägt Alarm.", "place": "zimmer", "actors": [{"id": "du"}]},
                            {"text": "Statt dich friedlich schlafen zu lassen, weckt er dich auf.", "place": "street", "time": "night", "shot": "event", "crowd": "walk"}],
                           [(0, 3.6), (3.6, 7.2)], "Drei Macken deines Gehirns")
        assert places.resolve(scs[1]["place"]) == "bedroom" and not scs[1].get("crowd"), scs[1]
        assert [a.get("id") for a in scs[1]["actors"]] == ["du"] and scs[1]["actors"][0].get("action") != "walk", scs[1]["actors"]
        frame(scs[1])
    check("Schlafen und Wecken im Schlafzimmer", _bed)
    def _hook():                                                 # Einstieg: schwache Anfänge erkannt, erstes Bild mit Reaktion und Ruck
        from .. import writer
        assert writer.hook_weak({"title": "Was passiert ohne Schwerkraft?", "scenes": [{"text": "Was wäre, wenn die Schwerkraft verschwindet?"}]})
        assert not writer.hook_weak({"title": "KI-Agenten", "scenes": [{"text": "Mein KI-Agent hat gerade gekündigt."}]})
        assert writer.hook_weak({"title": "KI-Agenten", "scenes": [{"text": "Mein Laptop hat gerade gekündigt."}]})          # Thema fehlt
        assert not writer.hook_weak({"title": "3 Tier-Superkräfte, die unmöglich wirken", "scenes": [{"text": "Drei Tier-Superkräfte, die eigentlich unmöglich sind."}]})
        scs = stage.direct([{"text": "Dein Auto fliegt gleich davon.", "place": "street", "actors": [{"id": "du"}]},
                            {"text": "Weiter.", "place": "street"}, {"text": "Schluss.", "place": "street"}], [(0, 3), (3, 6), (6, 9)], "Test")
        assert scs[0]["actors"][0]["emotion"], scs[0]["actors"]
        fr = frame(scs[0], t=0.1)
        for t in (0.0, 0.2, 0.49, 0.6):
            assert stage._camera(fr.convert("RGB"), t, 3.0, {"opener": True}).size == (1080, 1920)
    check("Einstieg", _hook)
    def _mimik():                                                # Lippen nur beim Selbst-Sprechen, Mundform je Silbe, Gesten zum Inhalt
        assert stage.lips("Ich habe mir gedacht …") and stage.lips('Er ruft: „Lauf!“') and not stage.lips("Du wachst auf und alles ist weg.")
        w = [("Warum", 0.0, 0.4), ("nie?", 0.4, 0.8), ("Plötzlich", 2.0, 2.6), ("explodiert", 2.6, 3.2)]
        assert stage._mouth(1.4, w)[0] == 0.0                     # Pause: Mund zu
        assert stage._mouth(0.0, w)[0] == 0.0 and stage._mouth(0.1, w)[1] == "a" and stage._mouth(0.6, w)[1] == "e"
        assert max(stage._mouth(x / 100, w)[0] for x in range(0, 80)) > 0.6
        plan = stage.gesture_plan(w, 0.0, False)
        assert ("shock" in [n for _, n in plan]) and all(b - a >= stage.GAP - 1e-6 for (a, _), (b, _) in zip(plan, plan[1:])), plan
        assert "shrug" in [n for _, n in stage.gesture_plan([("Wer", 0, 0.3), ("war", 0.3, 0.6), ("das?", 0.6, 1.0)], 0.0, False)]
        assert not [n for _, n in stage.gesture_plan([("du", 0, 0.3)], 0.0, False)]          # Erzähler sagt „du“: kein Zeigen
        sc_ = {"text": "Du wachst auf.", "place": "bedroom", "actors": [{"id": "du", "action": "talk", "speaks": True}]}
        assert not stage._prepare(dict(sc_), {})[3][0]["lips"]
        for name in rig.GESTURES:
            p, _ = rig.pose_at("talk", 0.6, 3.0, "", 0.0, 1, (name, 0.5))
            assert rig.draw(rig.Look.from_spec({}, "du", 0), p, 1, 1.0)[0].size[0] > 10, name
        for shp in ("a", "o", "e"):
            p, _ = rig.pose_at("talk", 0.6, 3.0, "", 0.8, 1, None, shp)
            assert p.shape == shp and p.mouth == 0.8
            rig.draw(rig.Look.from_spec({}, "du", 0), p, 1, 1.0)
    check("Mimik und Gesten", _mimik)
    def _sound():                                                # Klänge bildgenau: Whoosh-Spitze nach dem Schnitt, nichts doppelt
        import tempfile
        from pathlib import Path
        from .. import sound
        old = sound._LIB
        try:
            sound._LIB = {"sfx": {r: [{"file": f"{r}.ogg", "onset": 0.01, "peak": 0.2, "dur": 0.5}] for r in sound.GAIN}}
            out = sound.place([(2.0, "whoosh"), (2.03, "tick"), (3.0, "pop"), (3.05, "pop"), (3.3, "pop"), (0.0, "whoosh")], 10)
            starts = [round(t, 3) for t, _, _ in out]
            assert abs(starts[1] - (2.0 + 0.037 - 0.2)) < 1e-6, out           # Whoosh am lautesten 37 ms nach dem Schnitt
            assert len(out) == 4 and starts[0] == 0.0, out                     # Tick neben Whoosh weg, Pop-Abstand 114 ms
            assert sound.ambience_for({"place": "street"}) == "city" and sound.ambience_for({"place": "kitchen"}) == ""
            assert sound.ambience_for({"place": "forest", "time": "night"}) == "night"
        finally:
            sound._LIB = old
        sc = {"text": "Plötzlich!", "place": "livingroom", "props": ["lamp"], "actors": [{"id": "du", "action": "shocked", "speaks": True}]}
        with tempfile.TemporaryDirectory() as tmp:
            stage.render_scene(sc, {}, 1.2, Path(tmp) / "s.mp4", [("Plötzlich!", 0.1, 0.6)], 0.0)
        assert ("hit" in [r for _, r in sc["_sfx"]]) and ("pop" in [r for _, r in sc["_sfx"]]), sc["_sfx"]
    check("Klang-Platzierung", _sound)
    def _poster():                                               # Titelbild: Motiv aus Titel/Szenen, nicht dasselbe wie beim letzten Video
        import tempfile
        from pathlib import Path
        scs = [{"actors": [{"kind": "tardigrade"}]}, {"actors": [{"kind": "tardigrade"}, {"kind": "jelly"}]}, {"actors": [{"kind": "cheetah"}]}]
        assert stage.poster_hero("Was wenn wir Tier-Gene kreuzen?", scs, {"x": {"kind": "shrimp"}}) == "tardigrade"
        assert stage.poster_hero("Was wenn wir Tier-Gene kreuzen?", scs, {}, ["tardigrade"]) == "jelly"
        assert stage.poster_hero("Die Spinne in deinem Bett", scs) == "spider"
        assert stage.poster_hero("Warum wir schlafen", []) == ""
        with tempfile.TemporaryDirectory() as tmp:
            for pal in (0, 1):
                stage.poster({"hero_kind": "jelly", "palette": pal}, {}, Path(tmp) / f"p{pal}.jpg", "Qualle")
    check("Titelbild-Motiv", _poster)
    def _cold():                                                 # Vorgriff: erstes Bild zeigt das stärkste Bild statt herumstehender Leute
        scs = [{"text": "Drei Regeln, die eskalieren.", "place": "street", "actors": [{"id": "du", "action": "talk"}]},
               {"text": "Und die letzte rettet dich.", "place": "school", "actors": [{"id": "du", "action": "talk"}]},
               {"text": "Du packst Melonen ein.", "place": "street", "actors": [{"id": "du", "action": "talk"}]},
               {"text": "Deine Beine brechen.", "place": "street", "props": [{"type": "ball"}], "actors": [{"id": "du", "action": "fall"}]},
               {"text": "Ende.", "place": "park", "actors": [{"id": "du"}]}, {"text": "Ende.", "place": "park", "actors": [{"id": "du"}]}]
        stage._cold_open(scs)
        assert scs[0].get("_cold_open") and scs[0]["actors"][0]["action"] == "fall" and scs[0]["text"].startswith("Drei"), scs[0]
        busy = [{"text": "x", "place": "street", "props": [{"type": "ball"}, {"type": "lamp"}], "actors": [{"id": "du", "action": "run"}]}] + scs[1:]
        stage._cold_open(busy)
        assert not busy[0].get("_cold_open")                     # schon starkes erstes Bild: bleibt
        frame(scs[0])
    check("Vorgriff im ersten Bild", _cold)
    def _women():                                                # Frauenfiguren: alle Frisuren, beide Blickrichtungen, viele Posen
        for hair in ("long", "bun", "ponytail", "bob", "curly", ""):
            lk = rig.Look.from_spec({"hair": hair, "gender": "w", "glasses": hair == "bun"}, "x", 0)
            assert lk.fem
            for f in (1, -1):
                for act in ("talk", "shocked", "walk", "sad", "jump", "sleep", "fall"):
                    p, _ = rig.pose_at(act, 0.7, 3.0, "", 0.4, 2)
                    im = rig.draw(lk, p, f, 1.0)[0]
                    assert im.getbbox(), (hair, f, act)
        assert not rig.Look.from_spec({"shirt": "blau"}).fem
        assert stage.balance_cast({"du": {"shirt": "blau"}}, 4)["du"].get("gender") == "w"
        assert stage.balance_cast({"du": {"shirt": "blau"}}, 5)["du"] == {"shirt": "blau"}
        assert stage.balance_cast({"ich": {}}, 4) == {"ich": {}}
    check("Frauenfiguren", _women)
    def _motion():                                               # Kamera fährt sichtbar, lange Szenen schneiden, gleiche Bilder werden variiert
        import tempfile
        from pathlib import Path
        fr = frame({"place": "park", "actors": [{"id": "du"}]})
        for mv in ("push", "pull", "pan_l", "pan_r"):
            a = stage._camera(fr.convert("RGB"), 0.0, 4.0, {"move": mv, "tight": True})
            b = stage._camera(fr.convert("RGB"), 3.9, 4.0, {"move": mv, "tight": True})
            assert a.size == (1080, 1920) and a.tobytes() != b.tobytes(), mv
        cam = {"punch": None}
        cut, kind, _ = stage._cut_plan({"text": "Mutige Taucher tauchen hinab."}, "", None, False, False, "underwater",
                                       [{"action": "idle", "kind": "diver", "say": "", "hold": ""}], [], 7.0, cam, 2)
        assert cut is not None, "lange ruhige Szene muss schneiden"
        cut2, kind2, _ = stage._cut_plan({"text": "Zwei warten."}, "", None, False, False, "park",
                                         [{"action": "idle", "kind": "", "say": "", "hold": ""}, {"action": "idle", "kind": "", "say": "", "hold": ""}],
                                         [], 4.0, {"punch": None}, 0)
        assert kind2 == "flip", kind2                              # zwei Personen: Gegenschnitt statt angeschnittener Großaufnahme
        scs = [{"place": "park", "actors": [{"id": "rex", "kind": "dog", "action": "idle"}]}, {"place": "park", "actors": [{"id": "rex", "kind": "dog", "action": "idle"}]},
               {"place": "park", "actors": [{"id": "rex", "kind": "dog", "action": "idle"}]}]
        stage._vary_repeats(scs)
        sig = [stage._look_sig(x) for x in scs]
        assert sig[0] != sig[1] and sig[1] != sig[2], sig
        with tempfile.TemporaryDirectory() as tmp:
            stage.render_scene({"text": "Zwei warten lange.", "place": "park", "actors": [{"id": "a"}, {"id": "b"}]}, {}, 4.0, Path(tmp) / "f.mp4", index=0)
        from .. import render as rnd
        assert "hblur" not in rnd.TOON_TRANSITIONS and "cut" in rnd.TOON_TRANSITIONS
    check("Bewegung und Schnitt", _motion)
    def _loop():                                                 # Rehook/Finte: nur Umformulierungen, die den Inhalt behalten
        from .. import writer
        js = {"title": "Schatz", "scenes": [{"text": t} for t in ["Eins.", "Zwei.", "Soldaten versenken Kisten im See.", "Das Gerücht vom Gold entsteht.",
              "Taucher holen die Kisten hoch.", "Darin liegt kein Gold, sondern Falschgeld.", "Es sollte die Wirtschaft der Feinde zerstören.", "Ende."]]}
        old_chat = writer.ai.chat_json
        writer.ai.chat_json = lambda *a, **k: ({"edits": [{"i": 6, "text": "Gold? Falsch – darin liegt Falschgeld.", "why": "finte"},
                                                          {"i": 7, "text": "Nur wozu?", "why": "rehook"}, {"i": 5, "text": "Taucher holen 500 Kisten hoch.", "why": "x"},
                                                          {"i": 1, "text": "Anders.", "why": "x"}]}, "t")
        try:
            out = writer.loop_pass(js, "Schatz")
        finally:
            writer.ai.chat_json = old_chat
        t = [x["text"] for x in out["scenes"]]
        assert t[5].startswith("Gold? Falsch") and t[6].startswith("Es sollte") and "500" not in t[4] and t[0] == "Eins.", t
        js2 = {"title": "Vier Typen", "scenes": [{"text": t_} for t_ in ["Eins.", "Zwei.", "Wer satt sagt, bekommt bei Oma Nachschlag.",
               "Nach dem dritten Kloß gebe ich auf, aber Oma legt den vierten drauf.", "Mein Teller wird bei Oma nie leer.", "Nummer zwei, der Onkel.", "Er erzählt.", "Ende."]]}
        writer.ai.chat_json = lambda *a, **k: ({"edits": [{"i": 4, "text": "Nach dem dritten Kloß gebe ich auf, aber weißt du, was Oma danach macht?", "why": "rehook"},
                                                          {"i": 5, "text": "Mein Teller wird bei Oma nie leer, aber warum eigentlich?", "why": "rehook"}]}, "t")
        try:
            t2 = [x["text"] for x in writer.loop_pass(js2, "Vier Typen")["scenes"]]
        finally:
            writer.ai.chat_json = old_chat
        assert t2[3].endswith("vierten drauf.") and t2[4].endswith("nie leer."), t2   # Pointe bleibt; keine offene Frage direkt vor „Nummer zwei“
    check("Spannungsbogen (Rehook/Finte)", _loop)
    def _bounce():                                               # Musik-Kugel: jeder Ton trifft genau eine Scheibe, alle Melodien, Ton und Bild
        import math
        import tempfile
        from pathlib import Path
        from .. import bounce
        for song in bounce.SONGS:
            hits, total = bounce.notes(song)
            assert 40 <= len(hits) <= 220 and 15 < total < 70, (song, len(hits), total)
            segs, start = bounce.path(hits, 3)
            for sg in segs:
                bx, by = bounce.ball_at(sg["t"], segs, start)
                assert math.hypot(bx - sg["p"][0], by - sg["p"][1]) < 0.5, song
                assert bounce.BOX[0] - 1 <= sg["p"][0] <= bounce.BOX[2] + 1 and bounce.BOX[1] - 1 <= sg["p"][1] <= bounce.BOX[3] + 1, song
        bounce.SONGS["_test"] = ("Test", "Test", 240, bounce._seq("C5:1 E5:1 G5:1 C6:2"))
        try:
            with tempfile.TemporaryDirectory() as tmp:
                dur, thumb = bounce.render("_test", Path(tmp) / "b.mp4", seed=1, work=Path(tmp))
                assert (Path(tmp) / "b.mp4").stat().st_size > 10000 and thumb.exists()
        finally:
            bounce.SONGS.pop("_test", None)
        hits, _t = bounce.notes("fuer_elise")               # echter Abprall: Bewegung entlang der Scheibe bleibt erhalten
        segs, start = bounce.path(bounce.with_ghosts(hits), 4)
        for sg in segs[:-1]:
            nx, ny = sg["n"]
            vi, vo = sg["v_in"], sg["v_out"]
            ti = (vi[0] - (vi[0] * nx + vi[1] * ny) * nx, vi[1] - (vi[0] * nx + vi[1] * ny) * ny)
            to = (vo[0] - (vo[0] * nx + vo[1] * ny) * nx, vo[1] - (vo[0] * nx + vo[1] * ny) * ny)
            assert math.hypot(ti[0] - to[0], ti[1] - to[1]) < 1.0 and vi[0] * nx + vi[1] * ny < 0
        ap = bounce.appear_times(segs, start)
        assert all(a < sg["t"] for a, sg in zip(ap, segs))
        tt_ = [sg["t"] for sg in segs]                    # Scheiben stehen schon lange vorher da (nicht kurz vor dem Aufprall)
        assert sum(1 for j, a in enumerate(ap) if a <= bounce.appear_at(tt_, j) + 0.001) >= 0.95 * len(segs)
        assert all(a <= 0.001 for a in ap[:3]), ap[:3]      # die ersten Scheiben sind ab Bild 1 da
        assert bounce.ball_at(0.0, segs, start) == start and bounce.ball_at(0.2, segs, start) == start   # Kugel liegt erst auf der Startklappe
        with tempfile.TemporaryDirectory() as tmp:            # Lied-Modus: Einsätze in einer Aufnahme finden
            src = Path(tmp) / "src.wav"
            h2, tot2 = bounce.notes("bergkoenig", start=0.0)
            bounce.audio(h2, tot2, src, 1)
            st, ln, found = bounce.song_hits(src, length=20)
            real = [t for t, _ in h2 if st <= t <= st + ln]
            good = sum(1 for t, _ in found if min(abs(st + t - r) for r in real) < 0.04)
            assert good >= 0.9 * len(found) and len(found) >= 0.8 * len(real), (good, len(found), len(real))
        from .. import remix                              # Remix: jeder Stil ergibt einen Track, Töne liegen in der Melodie-Reihenfolge
        with tempfile.TemporaryDirectory() as tmp:            # Melodie statt Schlagzeug: in einem Remix mit Beat trifft die Kugel die Melodietöne
            for stl in ("trap", "edm"):
                wav_m = Path(tmp) / f"m_{stl}.wav"
                h4, _t4 = remix.build(bounce.SONGS["korobeiniki"], remix.KEYS["korobeiniki"], stl, wav_m, seed=1)
                f4 = bounce.melody_onsets(bounce._decode(wav_m, 11025), 11025, max_rate=6)
                true4 = [t for t, _ in h4]
                prec = sum(1 for t, _ in f4 if min(abs(t - u) for u in true4) < 0.05) / max(1, len(f4))
                rec = sum(1 for u in true4 if any(abs(t - u) < 0.05 for t, _ in f4)) / len(true4)
                assert prec >= 0.6 and rec >= 0.8, (stl, round(prec, 2), round(rec, 2))
        assert not bounce.instrumental({"title": "I Insist (Remix)", "tags": [{"name": "rap"}, {"name": "instrumental"}]})
        assert bounce.instrumental({"title": "Night Drive", "tags": [{"name": "instrumental"}]}) and not bounce.instrumental({"title": "x", "tags": []})
        assert set(bounce.SONGS) <= set(remix.KEYS)
        with tempfile.TemporaryDirectory() as tmp:            # Schluss: kein leeres Bild nach dem letzten Ton (Video 134 lief vier Sekunden leer weiter)
            for mel_, stl in (("saints", "pop"), ("funkel", "phonk")):
                h5, t5 = remix.build(bounce.SONGS[mel_], remix.KEYS[mel_], stl, Path(tmp) / "e.wav", seed=2)
                sg5, st5 = bounce.path(bounce.with_ghosts(h5), 2)
                end5 = bounce.end_time(sg5, st5)
                assert h5[-1][0] + 0.8 <= end5 <= h5[-1][0] + 3.9 and end5 <= t5, (mel_, end5, t5, h5[-1])
                by5 = bounce.ball_at(end5 - bounce.END_HOLD - 2 / bounce.FPS, sg5, st5)[1]
                assert by5 <= bounce.H + bounce.BALL_R, (mel_, by5)      # bis kurz vor Schluss ist die Kugel noch im Bild
            import subprocess
            import wave as _wave
            import numpy as _np
            with _wave.open(str(Path(tmp) / "e.wav")) as w5:           # Aussteuerung: Abstand zum Vollausschlag (AAC übersteuerte)
                x5 = _np.frombuffer(w5.readframes(w5.getnframes()), "<i2")
            assert 0.5 < abs(x5).max() / 32768 <= remix.TRUE_PEAK + 0.01, abs(x5).max()
            for mel_, stl, sd in (("bella_ciao", "glas", 165), ("saints", "pop", 135)):   # Video 165: Glas-Klirren lag auf +4,4 dBTP, zwei Scheiben über Eck
                h6, _t6 = remix.build(bounce.SONGS[mel_], remix.KEYS[mel_], stl, Path(tmp) / "g.wav", seed=sd)
                with _wave.open(str(Path(tmp) / "g.wav")) as w6:
                    x6 = _np.frombuffer(w6.readframes(w6.getnframes()), "<i2").reshape(-1, 2)[:, 0] / 32767
                assert remix.true_peak(x6) <= remix.TRUE_PEAK + 0.01, (stl, remix.true_peak(x6))   # Spitze zwischen den Abtastwerten
                f6 = _np.abs(_np.fft.rfft(x6)) ** 2
                assert f6[int(19000 * len(x6) / remix.SR):].sum() < 0.001 * f6.sum(), stl          # kein Rauschen an der halben Abtastrate
                hg6 = bounce.with_ghosts(h6)
                sg6, _st6 = bounce.path(hg6, sd)
                tm6 = [g["t"] for g in sg6]
                rc6 = [bounce._pane_rect(g["p"], g["n"]) for g in sg6]
                for a6 in range(len(sg6)):                  # gleichzeitig sichtbare Scheiben berühren sich nicht
                    for b6 in range(a6 + 1, len(sg6)):
                        if tm6[a6] > bounce.appear_at(tm6, b6):
                            assert not bounce._rects_touch(rc6[a6], rc6[b6]), (mel_, a6, b6)
            dur5, _th = bounce.render({"remix": "saints", "style": "pop"}, Path(tmp) / "s.mp4", seed=134, work=Path(tmp))
            assert 23.5 < dur5 < 25.5, dur5                          # vorher 27,9 s
            out5 = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(Path(tmp) / "s.mp4")],
                                  capture_output=True, text=True).stdout.strip()
            assert abs(float(out5) - dur5) < 0.15, (out5, dur5)
        with tempfile.TemporaryDirectory() as tmp:
            for stl in remix.STYLES:
                h3, tot3 = remix.build(bounce.SONGS["ode_freude"], remix.KEYS["ode_freude"], stl, Path(tmp) / f"{stl}.wav", seed=1)
                assert len(h3) >= 60 and all(a[0] < b[0] for a, b in zip(h3, h3[1:])) and (Path(tmp) / f"{stl}.wav").stat().st_size > 100000, stl
        t_c, d_c, tags_c, n_c = bounce.meta({"credit": "Musik: „X“ von Y – CC BY 4.0 – https://ccmixter.org/x", "name": "X", "who": "Y"})
        assert "CC BY 4.0" in d_c and "ccmixter" in d_c                 # Namensnennung steht in der Beschreibung
        t_r, d_r, tags_r, n_r = bounce.meta({"remix": "bergkoenig", "style": "phonk"})
        assert "Phonk" in n_r and "Bergkönig" not in d_r and "#remix" in tags_r   # Lösung wird in den Kommentaren geraten, nicht verraten
        title, desc, tags, name = bounce.meta("ode_freude")
        assert name not in desc and "Kommentare" in desc and title and "#musik" in tags
    check("Musik-Kugel", _bounce)
    check("Neon-Look", lambda: graphics.neon(frame({"place": "street", "crowd": "walk"}), 1.0))
    check("Neon-Kulisse", lambda: graphics.tint(places.background("street", True)))
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
                             "shot": rnd.choice(["event", "close", "insert", "wide", "graphic", "x"]), "overlay": rnd.choice(ovs), "hud": "TAG 1", "highlight": ["a"]}[k]
            scenes.append(sc)
        times = [(i * 3.0, i * 3.0 + 3.0) for i in range(len(scenes))]
        if check(f"Regie Drehbuch {n}", lambda: stage.direct(scenes, times, "Drohnen überwachen", rnd.choice(["", "grusel"]), rnd.choice(["", "neon"])) or True):
            for i, sc in enumerate(scenes):
                check(f"Regie Drehbuch {n} Szene {i}: {str(sc)[:300]}", lambda: frame(sc, t=rnd.choice((0.0, 1.0, 2.9))))
    def _bugs():                                                 # „Videospiel-Bugs“: kein Käfer im Bild, keine Strichliste, Programm-Absturz ist kein Sturz
        from .. import writer
        from . import library
        it = library.clean({"name": "insekt", "aliases": ["käfer", "bug", "gift"], "height_m": 0.1,
                            "shapes": [{"t": "ellipse", "cx": 200, "cy": 300, "rx": 80, "ry": 100, "c": "#cc3333"}, {"t": "rect", "x": 150, "y": 200, "w": 100, "h": 60, "c": "#222222"}]})
        assert it and it["aliases"] == ["käfer"], it
        T = ["Drei Videospiel-Bugs, die unser Leben ruinieren würden.", "Einer davon macht deinen Einkaufsbeutel überflüssig."] \
            + [f"{o} Bug: Etwas passiert." for o in ("Zweiter", "Dritter", "Vierter", "Fünfter", "Sechster", "Siebter")]
        assert writer.list_trouble({"scenes": [{"text": t} for t in T]}), "Strichliste nicht erkannt"
        assert not writer.list_trouble({"scenes": [{"text": t} for t in ["Drei Tier-Superkräfte, die unmöglich sind.", "Die letzte rettet Leben.", "Nummer eins: der Krebs.",
                                                                         "Er knallt beim vierten Versuch.", "Zweitens die Qualle.", "Die dritte Kraft ist die stärkste."]]})
        js = writer.polish({"scenes": [{"text": "x", "overlay": {"type": "counter", "value": 99, "unit": "99 STÜCK"}}]})
        assert js["scenes"][0]["overlay"]["unit"] == "STÜCK", js
        sc = [{"text": "Die Schwerkraft setzt kurz aus und du schwebst.", "place": "street", "actors": [{"id": "du", "action": "float"}]},
              {"text": "Das Spiel stürzt ab und du wachst in deinem Bett auf.", "place": "bedroom", "actors": [{"id": "du", "action": "sit"}]},
              {"text": "Folg für mehr.", "place": "livingroom", "actors": [{"id": "du", "action": "talk"}]}]
        stage.direct(sc, [(0, 3), (3, 6), (6, 9)], "Videospiel-Bugs im Alltag", "whatif")
        assert not sc[1].get("float"), sc[1]
        assert not any("insekt" in str(p_) for s_ in sc for p_ in (s_.get("props") or [])), sc
    check("Bugs: kein Käfer, keine Strichliste, Absturz", _bugs)
    def _neighbours():                                           # Video 144 „Nachbarn“: Aufzählung ohne Aufzählung, Keule bei „Club“, doppelter Zähler, fremde Liste, fremdes Schild, Tür als Großaufnahme
        from .. import writer
        from . import library
        T = ["Vier Nachbarn, die dein Leben zur Hölle machen.", "Der letzte Vorfall treibt mich in den Wahnsinn.", "Die Wand vibriert seit Stunden.",
             "Also bin ich rübergegangen.", "Aber Uwe hat nicht geöffnet.", "Jetzt habe ich Ohrstöpsel."]
        assert str(writer.list_trouble({"scenes": [{"text": t} for t in T]})).startswith("Der Einstieg"), "angekündigte Aufzählung fehlt, nicht erkannt"
        assert not writer.list_trouble({"scenes": [{"text": t} for t in ["Fünf Sekunden, die alles verändern.", "Die Schwerkraft fällt aus.", "Alles schwebt.", "Dann kracht es."]]})
        it = library.clean({"name": "keule", "aliases": ["keulen", "club"], "height_m": 0.8,
                            "shapes": [{"t": "ellipse", "cx": 200, "cy": 300, "rx": 80, "ry": 100, "c": "#cc3333"}, {"t": "rect", "x": 150, "y": 200, "w": 100, "h": 60, "c": "#222222"}]})
        assert it and it["aliases"] == ["keulen"], it
        sc = [{"text": "Nachbarn, die dein Leben zur Hölle machen.", "place": "hallway", "actors": [{"id": "du", "action": "talk"}], "overlay": {"type": "tag", "text": "NACHTSCHICHT"}},
              {"text": "Der Lärm treibt mich seit vierundvierzig Stunden in den Wahnsinn.", "place": "bedroom", "actors": [{"id": "du", "action": "walk"}],
               "overlay": {"type": "counter", "label": "", "value": 44, "unit": "STUNDEN"}},
              {"text": "Die Wand vibriert seit vierundvierzig Stunden ohne Pause.", "place": "bedroom", "actors": [{"id": "du", "action": "cower"}],
               "overlay": {"type": "counter", "label": "STUNDEN LÄRM", "value": 44, "unit": "STUNDEN"}},
              {"text": "Viele drohen jetzt mit Mietminderung.", "place": "office", "actors": [{"id": "du", "action": "talk"}],
               "overlay": {"type": "checklist", "title": "MIETMINDERUNG", "items": [["Geld", False], ["Gurken", True]]}},
              {"text": "Er hat mir eine Melone vor die Tür gelegt.", "place": "hallway", "shot": "insert", "props": [{"type": "door"}], "actors": []},
              {"text": "Folg für mehr.", "place": "livingroom", "actors": [{"id": "du", "action": "talk"}]}]
        stage._last_look(sc, "Nervige Nachbarn")
        assert not sc[0].get("overlay"), sc[0]
        assert sc[1].get("overlay") and not sc[2].get("overlay"), (sc[1], sc[2])
        assert not sc[3].get("overlay"), sc[3]
        assert sc[4].get("shot") != "insert" and sc[4].get("actors"), sc[4]
        keep = [{"text": "Im August 1914 beginnt der Krieg.", "overlay": {"type": "tag", "text": "AUGUST 1914"}},
                {"text": "Du packst Wasser, Brot und Kerzen ein.", "overlay": {"type": "checklist", "title": "CHECKLISTE", "items": [["Wasser", True], ["Brot", True]]}}]
        stage._last_look(keep, "")
        assert keep[0].get("overlay") and keep[1].get("overlay"), keep
    check("Nachbarn: Aufzählung, Club, doppelter Zähler, fremde Liste", _neighbours)
    def _labels():                                               # Nummern-Schild nur beim Satz mit der Nummer, Stempel nur mit Wort aus dem Satz, kein Zuckerhaufen ohne Anlass
        from .. import writer
        sc = [{"text": "Drei verrückte Regeln, die im Alltag eskalieren würden.", "place": "street", "actors": [{"id": "du", "action": "talk"}]},
              {"text": "Und die letzte Regel macht jede Prüfung unbesiegbar.", "place": "classroom", "actors": [{"id": "du", "action": "think"}],
               "overlay": {"type": "tag", "text": "REGEL NUMMER EINS"}},
              {"text": "Der normale Einkaufsbeutel wird dadurch völlig überflüssig.", "place": "supermarket", "actors": [{"id": "du", "action": "shake"}],
               "overlay": {"type": "stamp", "text": "GRATIS", "color": "green"}},
              {"text": "Aber in echt wiegen diese Früchte zusammen fast eine Tonne.", "place": "street", "actors": [{"id": "du", "action": "shocked"}], "props": ["pile"]},
              {"text": "Zweitens: Das ist streng verboten.", "place": "street", "actors": [{"id": "du", "action": "talk"}], "overlay": {"type": "stamp", "text": "VERBOTEN", "color": "red"}},
              {"text": "Folg für mehr.", "place": "livingroom", "actors": [{"id": "du", "action": "talk"}]}]
        stage.direct(sc, [(i * 3, i * 3 + 3) for i in range(len(sc))], stage.topic_head("Regeln im Alltag – mit Einkaufsbeutel, Zucker und Apfel erklärt, jede Regel drei Sätze, bitte genau so und nicht anders"), "whatif")
        assert "REGEL NUMMER EINS" not in str(sc[1].get("overlay")), sc[1].get("overlay")
        assert "GRATIS" not in str(sc[2].get("overlay")), sc[2].get("overlay")
        assert not any("pile" in str(q) for q in sc[3].get("props") or []), sc[3].get("props")
        assert "VERBOTEN" in str(sc[4].get("overlay")), sc[4].get("overlay")
        sc2 = [{"text": "Drei verrückte Regeln.", "place": "street", "actors": [{"id": "du", "action": "talk"}]},
               {"text": "Du steckst einfach neunundneunzig schwere Wassermelonen in deine Hosentasche.", "place": "supermarket", "actors": [{"id": "du", "action": "talk"}]},
               {"text": "Aber in echt wiegen diese Früchte zusammen fast eine ganze Tonne.", "place": "street", "actors": [], "props": ["pile"]},
               {"text": "Ein kleiner Apfel lässt den blauen Fleck am Knie verschwinden.", "place": "livingroom", "actors": [{"id": "du", "action": "jump"}]},
               {"text": "Folg für mehr.", "place": "livingroom", "actors": [{"id": "du", "action": "talk"}]}]
        stage.direct(sc2, [(i * 4, i * 4 + 4) for i in range(len(sc2))], "Videospiel-Regeln im Alltag", "whatif")
        if "lib_wassermelone" in extras.PROPS:                   # Folgesatz ohne das Wort: die Melonen bleiben im Bild, mit Figur
            assert len([q for q in sc2[2]["props"] if q.get("type") == "lib_wassermelone"]) == 3 and sc2[2]["actors"], sc2[2]
            frame(sc2[2])
        if "lib_apfel" in extras.PROPS:
            assert any(q.get("type") == "lib_apfel" for q in sc2[3]["props"]), sc2[3]["props"]
            frame(sc2[3])
        sc3 = [{"text": "Drei Regeln.", "place": "street", "actors": [{"id": "du", "action": "talk"}]},
               {"text": "Das Spiel zeigt Mitleid und du liegst einfach platt auf dem Boden.", "place": "street", "shot": "close", "actors": [{"id": "du", "action": "talk"}]},
               {"text": "Folg für mehr.", "place": "livingroom", "actors": [{"id": "du", "action": "talk"}]}]
        stage.direct(sc3, [(0, 3), (3, 7), (7, 9)], "Regeln im Alltag", "whatif")
        assert sc3[1]["actors"][0]["action"] == "fall" and sc3[1].get("shot") != "close", sc3[1]
        frame(sc3[1])
        th = writer.polish({"thumbnail": {"text": "NEUNZIG MELONEN IN DER TASCHE"}, "scenes": [{"text": "Du steckst neunundneunzig Wassermelonen ein."}]})["thumbnail"]["text"]
        assert th == "MELONEN IN DER TASCHE", th
    check("Schilder, Stempel, Haufen, Titelbild-Zahl", _labels)

    def _deeds():                                                 # Geben/Essen: Figur hält das Ding; Einsatzwagen; Schild mit fremder Zahl; Handy-Einblendung
        sc = [{"text": "Alle sind eine Minute lang nett.", "place": "livingroom", "actors": [{"id": "du", "action": "talk"}]},
              {"text": "Im Büro teilt der Kollege plötzlich sein letztes Stück Kuchen.", "place": "office", "props": ["table"],
               "actors": [{"id": "du", "action": "talk", "pos": "left"}, {"id": "tom", "action": "talk", "pos": "right"}]},
              {"text": "Einsatzkräfte haben plötzlich nichts mehr zu tun.", "place": "street", "shot": "event", "props": ["car"], "actors": []},
              {"text": "Autofahrer lassen sich lächelnd den Vortritt.", "place": "street", "overlay": {"type": "tag", "text": "SEKUNDE 10"},
               "actors": [{"id": "du", "action": "wave"}]},
              {"text": "Du denkst zufrieden nach.", "place": "hospital", "mood": "happy", "actors": [{"id": "du", "action": "think", "emotion": "happy"}]},
              {"text": "Folg für mehr.", "place": "livingroom", "actors": [{"id": "du", "action": "talk"}]}]
        stage.direct(sc, [(i * 4, i * 4 + 4) for i in range(len(sc))], "Wenn alle nett wären", "whatif")
        if "lib_kuchen" in extras.PROPS:
            assert sc[1]["actors"][-1].get("hold") == "lib_kuchen", sc[1]["actors"]
            frame(sc[1])
        kinds = [q.get("type") for q in sc[2]["props"]]
        assert "ambulance" in kinds and "car" not in kinds, kinds
        frame(sc[2])
        assert not sc[3].get("overlay"), sc[3].get("overlay")
        _pl, _n, _s, acts, _p, _w = stage._prepare(sc[4], {"du": {}})
        assert acts[0]["emote"] != "?", acts[0]["emote"]
        frame({"place": "street", "props": ["police"], "actors": []})
        from .. import overlays
        fr = overlays.frames_for({"type": "phone", "title": "12:00", "items": ["Ex: Danke für alles!", "Du: Dir auch nur das Beste ❤️", "Mama", "Vier: zu viel"]})
        assert fr and fr[0]
        sc2 = [{"text": "Acht Milliarden Menschen sind eine Minute lang nett.", "place": "worldmap", "actors": []},
               {"text": "Und das verändert sofort alles.", "place": "worldmap", "actors": []},
               {"text": "Drittens entsteht in sechzig Sekunden eine Welle.", "place": "beach", "shot": "graphic", "graphic": {"type": "number", "value": "60", "label": "SEKUNDEN"}, "actors": []},
               {"text": "Wer Freundlichkeit erfährt, gibt sie an bis zu drei Personen weiter.", "place": "lab", "shot": "graphic",
                "graphic": {"type": "number", "value": "3 PRO KETTE", "label": "WEITERGABE"}, "actors": [{"id": "du", "action": "walk"}]},
               {"text": "Folg für mehr.", "place": "livingroom", "actors": [{"id": "du", "action": "talk"}]}]
        stage.direct(sc2, [(i * 4, i * 4 + 4) for i in range(len(sc2))], "Wenn alle nett wären", "whatif")
        assert places.resolve(sc2[1].get("place")) not in stage.MAPS and sc2[1]["actors"], sc2[1]      # nie zweimal hintereinander die Weltkugel
        assert sc2[3].get("shot") != "graphic", sc2[3]                                              # nie zwei Zahlen-Tafeln hintereinander
        frame(sc2[1])
        sc3 = [{"text": "Im Büro teilt der Kollege sein Stück Kuchen.", "place": "office", "actors": [{"id": "du", "action": "talk"}, {"id": "tom", "action": "talk"}]},
               {"text": "Wer Freundlichkeit erlebt, gibt diese positive Energie sofort weiter.", "place": "street", "actors": [{"id": "du", "action": "wave"}]},
               {"text": "Folg für mehr.", "place": "livingroom", "actors": [{"id": "du", "action": "talk"}]}]
        stage.direct(sc3, [(0, 4), (4, 8), (8, 10)], "Wenn alle nett wären", "whatif")
        assert not any("kuchen" in str(q.get("type")) for q in sc3[1].get("props") or []), sc3[1].get("props")   # „diese Energie“ ist kein Ding
        assert overlays._short("SCHREIB ES IN DIE KOMMENTARE", 22) == "SCHREIB ES", overlays._short("SCHREIB ES IN DIE KOMMENTARE", 22)
        assert overlays.frames_for({"type": "tag", "text": "SCHREIB ES IN DIE KOMMENTARE"})
    check("Geben/Essen, Einsatzwagen, Schild-Zahl, Handy", _deeds)
    def _deep():                                                 # Tiefsee-Technik: Blackbox, Tauchboot mit Sonar und Wrack am dunklen Meeresgrund – kein Flugzeug, kein Mensch, keine Zahlen-Tafel
        T = [("Ein Flugzeug verschwindet über dem Atlantik vom Radar.", "street", [{"id": "du"}], ["plane"], ""),
             ("Am Meeresboden sendet die Blackbox dreißig Tage lang Signale aus.", "underwater", [], ["box"], "event"),
             ("Jetzt helfen nur noch Spezial-Tauchboote mit Hochfrequenz-Sonar in viertausend Metern Tiefe.", "underwater", [], ["sonar"], "event"),
             ("Erst wenn das Wrack gefunden ist, beginnt die eigentliche Arbeit.", "underwater", [], ["plane"], "event"),
             ("Der Flugdatenschreiber verrät den Ermittlern das Tempo.", "lab", [{"id": "du"}], ["computer"], ""),
             ("Folg für mehr.", "lab", [{"id": "du"}], [], "")]
        sd = stage.direct([{"text": t_, "place": pl_, "actors": a_, "props": pr_, "shot": sh_, "time": "day",
                            "backdrop": {"sky": "dark", "ground": "water", "elements": ["sea"]} if pl_ == "underwater" else None} for t_, pl_, a_, pr_, sh_ in T],
                          [(n_ * 4, n_ * 4 + 4) for n_ in range(len(T))], "Was passiert, wenn ein Flugzeug spurlos verschwindet?", "whatif")
        keys = [[extras.PROP_ALIASES.get(str(q.get("type")).lower(), str(q.get("type")).lower()) for q in sc_.get("props") or []] for sc_ in sd]
        for n_ in (1, 2, 3):
            assert places.resolve(stage.backdrop(sd[n_])) == "underwater" and sd[n_].get("time") == "night", f"Tiefsee {n_}: {sd[n_].get('place')} {sd[n_].get('backdrop')} {sd[n_].get('time')}"
            assert not sd[n_].get("actors") and sd[n_].get("shot") != "graphic", f"Tiefsee {n_}: {sd[n_].get('actors')} {sd[n_].get('shot')}"
        assert "lib_blackbox" in keys[1] and "ping" in keys[1] and "box" not in keys[1], f"Blackbox: {keys[1]}"
        assert keys[2] == ["submersible"], f"Sonar: {keys[2]}"
        assert "lib_wrack" in keys[3] and "submersible" in keys[3] and "plane" not in keys[3], f"Wrack: {keys[3]}"
        assert places.resolve(stage.backdrop(sd[4])) == "lab" and "lib_blackbox" in keys[4] and "submersible" not in keys[4], f"Labor: {sd[4].get('place')} {keys[4]}"
        for sc_ in sd:
            for t_ in (0.2, 1.3):
                frame(sc_, {"du": {"shirt": "blau"}}, t=t_)
        bat = stage.direct([{"text": "Fledermäuse nutzen eine Art Sonar.", "place": "forest", "actors": [{"id": "du"}]}, {"text": "Folg für mehr.", "place": "forest", "actors": [{"id": "du"}]}],
                           [(0, 4), (4, 8)], "Fledermäuse", "fakten")
        assert places.resolve(stage.backdrop(bat[0])) != "underwater" and not any("submersible" == extras.PROP_ALIASES.get(str(q.get("type")), str(q.get("type"))) for q in bat[0].get("props") or []), bat[0]
        assert not [k for k, _x in stage._prepare({"place": "street", "props": ["sonar"], "actors": [{"id": "du"}]}, {"du": {}})[4] if extras.PROP_ALIASES.get(k, k) == "submersible"], "Tauchboot auf der Straße"
        for sc_ in ({"shot": "insert", "props": ["sonar"]}, {"place": "underwater", "time": "night", "props": ["sonar", "wrack"]}, {"place": "underwater", "time": "night", "props": ["blackbox"]},
                    {"shot": "insert", "props": ["blackbox"]}, {"shot": "insert", "props": ["wrack"]}, {"place": "classroom", "props": ["prüfung"], "actors": [{"id": "du"}]}):
            frame(sc_)
        assert not stage._lib_props() or all(any(k_ == key_ for _p, k_ in stage._lib_props()) for key_ in ("lib_blackbox", "lib_wrack")), "Blackbox/Wrack fehlen in der Bibliothek"
    check("Tiefsee: Blackbox, Sonar, Wrack", _deep)

    def _balloon():                                              # Ballonflucht: Stoffberg und Gondel am Boden, Ballon mit acht Köpfen am Himmel, Suchscheinwerfer, Landung im Gebüsch – keine Figur „schwebt“ auf der Wiese
        from PIL import Image
        T = ["Zwei Familien fliehen mit einem selbst genähten Heißluftballon.", "Im Keller nähen sie heimlich über tausend Quadratmeter Stoff zusammen.",
             "Heimlich kaufen sie den Stoff in vielen Geschäften.", "Acht Personen müssen in eine winzige Gondel passen.",
             "Mitten in der Nacht bauen sie den Ballon auf einer Wiese auf.", "Mit vier Gasflaschen erzeugen sie das Feuer für den Auftrieb.",
             "Der gigantische Stoffbeutel füllt sich langsam und hebt in die Dunkelheit ab.", "Dort oben herrscht eiskalte Temperatur von minus acht Grad.",
             "Plötzlich erfassen Suchscheinwerfer der Grenze den Ballon am Himmel.", "Genau jetzt geht ihnen das Gas aus.",
             "Der Ballon beginnt abzustürzen.", "Nach achtundzwanzig Minuten krachen sie hart in ein Gebüsch.", "Sie sind endlich frei."]
        sb = stage.direct([{"text": t_, "place": "basement" if n_ < 4 else "fields", "time": "night", "status": "FALL: 15 M/S" if n_ == 10 else "", "overlay": {"type": "thermo", "value": -8} if n_ == 7 else None,
                            "actors": [{"id": "du", "action": "float" if n_ in (6, 11) else "talk"}], "props": ["fire"] if n_ == 5 else []}
                           for n_, t_ in enumerate(T)], [(n_ * 4, n_ * 4 + 4) for n_ in range(len(T))], "Flucht mit dem Heißluftballon", "storys", "")
        kinds = [sc.get("_balloon") for sc in sb]
        assert kinds == ["open", None, None, "gondola", "ground", "fill", "fly", "fly", "light", "dark", "fall", "down", None], kinds   # Thermometer: Ballon von fern, nicht die Gondel nah
        keys = [[extras.PROP_ALIASES.get(str(q.get("type")), str(q.get("type"))) for q in sc.get("props") or [] if isinstance(q, dict)] for sc in sb]
        assert keys[0] == ["searchlight", "balloon"] and keys[8] == ["searchlight", "balloon"] and keys[9] == ["balloon_dark"] and keys[10] == ["balloon_out"], keys
        assert "sewing" in keys[1] and "fabric" in keys[2] and keys[11] == ["balloon_down"], keys
        assert all(places.resolve(stage.backdrop(sb[n_])) == "highsky" and not sb[n_].get("actors") for n_ in (0, 3, 7, 8, 9, 10)), "Flug vor hohem Himmel, ohne Figuren"
        assert all(sb[n_].get("_ov_low") == 3 for n_ in (5, 7, 8)), "Einblendung über dem Ballon"
        assert not any(str(a.get("action")) == "float" for sc in sb for a in sc.get("actors") or []), "niemand schwebt"
        assert not sb[10].get("status"), "Zustands-Zeile mit nicht gesprochener Zahl"
        for sc in sb:
            assert frame(sc, {"du": {}}) is not None
        T2 = ["Acht Menschen fliehen im selbst genähten Heißluftballon.", "Und kurz vor dem Ziel geht plötzlich das Gas aus.", "Vier Erwachsene und vier Kinder wollen in den Westen.",
              "Die Gondel besteht nur aus einer kleinen Plattform aus Blech.", "Als Geländer dient eine Wäscheleine, mittig stehen vier Gasflaschen.",
              "Mitten in der Nacht bauen sie alles im Wald auf.", "Acht Menschen drängen sich zusammen und heben ab.", "Sie landen in einem Gebüsch.", "Sie sind endlich in Sicherheit."]
        s2 = stage.direct([{"text": t_, "place": "supermarket" if n_ == 2 else "forest", "time": "night", "hud": "02:00 UHR · WALD" if n_ == 5 else "",
                            "props": ["heißluftballon", "fire"] if n_ in (2, 5) else [], "actors": [{"id": "du", "action": "walk", "to": "right"}],
                            "overlay": {"type": "counter", "value": 8, "unit": "MENSCHEN"} if n_ == 6 else {"type": "choice", "a": "Freiheit", "b": "Sicherheit"} if n_ == 8 else None}
                           for n_, t_ in enumerate(T2)], [(n_ * 4, n_ * 4 + 4) for n_ in range(len(T2))], "Flucht mit dem Heißluftballon", "storys", "")
        k2 = [sc.get("_balloon") for sc in s2]
        assert k2 == ["open", "dark", None, "gondola", "basket", "ground", "fly", "down", None], k2
        assert [a.get("id") for a in s2[2].get("actors") or []] == ["du", "_frau", "_kind"] and places.resolve(stage.backdrop(s2[2])) == "livingroom" and not s2[2].get("props"), s2[2]
        assert s2[5].get("hud") == "WALD" and s2[6]["overlay"] == {"type": "card", "text": "8 MENSCHEN"} and not s2[8].get("overlay"), (s2[5].get("hud"), s2[6].get("overlay"), s2[8].get("overlay"))
        for sc in s2:
            assert frame(sc, {"du": {}}) is not None
        s3 = stage.direct([{"text": t_, "place": "street", "time": "night", "props": ["car"] if n_ == 4 else [], "actors": [{"id": "du"}],
                            "shot": "graphic" if n_ in (1, 3) else "", "graphic": {"type": "number", "value": "8", "label": "MENSCHEN"} if n_ in (1, 3) else None,
                            "overlay": {"type": "card", "text": "1000 METER STOFF"} if n_ == 0 else None}
                           for n_, t_ in enumerate(["Sie kaufen über tausend Quadratmeter Stoff für den Heißluftballon.", "Acht Menschen steigen ein, der Ballon hebt ab.", "Er fliegt über die Grenze.",
                                                    "Nach achtundzwanzig Minuten landen sie in einem Gebüsch.", "Sie sind in Bayern, alle haben überlebt."])],
                          [(n_ * 4, n_ * 4 + 4) for n_ in range(5)], "Flucht mit dem Heißluftballon", "storys", "")
        assert [sc.get("_balloon") for sc in s3][1:4] == ["fly", "fly", "down"] and s3[1].get("shot") != "graphic" and s3[3].get("shot") != "graphic", [(sc.get("_balloon"), sc.get("shot")) for sc in s3]
        assert places.resolve(stage.backdrop(s3[4])) != "street" and not s3[4].get("props"), s3[4]
        s4 = stage.direct([{"text": t_, "place": "street", "backdrop": {"sky": "night", "ground": "road", "elements": ["street"]} if n_ >= 3 else None, "time": "night",
                            "shot": "event" if n_ == 3 else "", "props": ["police"] if n_ >= 3 else [], "actors": [{"id": "du"}] if n_ < 3 else []}
                           for n_, t_ in enumerate(["Sie fliehen im Heißluftballon.", "Der Ballon hebt ab.", "Sie landen in einem Gebüsch.", "Dann taucht ein Streifenwagen auf.", "Alle acht haben überlebt."])],
                          [(n_ * 4, n_ * 4 + 4) for n_ in range(5)], "Flucht mit dem Heißluftballon", "storys", "")
        for n_ in (3, 4):                                         # Schluss: Wiese am Dorfrand mit den Geretteten – nicht nur ein Streifenwagen vor leeren Häusern
            assert isinstance(s4[n_].get("backdrop"), dict) and s4[n_]["backdrop"].get("ground") == "grass" and [a.get("id") for a in s4[n_].get("actors") or []] == ["du"], s4[n_]
            assert frame(s4[n_], {"du": {}}) is not None

        assert s3[0]["overlay"]["text"] == "1000 QUADRATMETER STOFF", s3[0]["overlay"]
        from .. import writer as _wr
        echo = _wr.polish({"title": "x", "scenes": [{"text": "Acht Menschen fliehen im Ballon aus der DDR."}] + [{"text": f"Satz Nummer {n_} erzählt etwas anderes."} for n_ in range(8)] + [{"text": "Acht Menschen fliehen im Ballon aus der DDR."}]})
        assert len(echo["scenes"]) == 9, len(echo["scenes"])
        party = stage.direct([{"text": "Zum Geburtstag gibt es einen Luftballon.", "place": "livingroom", "actors": [{"id": "du"}]}] * 4, [(n_ * 3, n_ * 3 + 3) for n_ in range(4)], "Geburtstag")
        assert not any(sc.get("_balloon") for sc in party), "Luftballon ist kein Heißluftballon"
        for k_ in extras.BALLOON_KINDS + ("sewing", "fabric"):
            for t_ in (0.2, 1.7, 3.3):
                lay = Image.new("RGBA", (places.W, places.H), (0, 0, 0, 0))
                extras.draw_prop(lay, k_, 540, t_)
                assert lay.getbbox(), k_
        assert places.background("highsky", True).size == (places.W, places.H) and places.background("highsky", False) is not None

    def _lake():                                                 # Schatz im See: Taucher statt Goldfisch, Seegrund, Holzkisten, sinkende Kisten, Baumstämme, Scheine am Ufer
        T = [("Im Toplitzsee liegen bis heute geheimnisvolle Kisten.", "underwater", [{"id": "taucher", "kind": "fish", "action": "talk"}], ["box"], "event"),
             ("Soldaten bringen schwere Holzkisten an den See.", "lake", [{"id": "du", "action": "point"}], [], ""),
             ("Sie versenken alles im über hundert Meter tiefen Wasser.", "underwater", [{"id": "taucher", "kind": "fish"}], ["box"], "event"),
             ("Schatzsucher riskieren im kalten See ihr Leben.", "underwater", [{"id": "taucher", "kind": "fish"}], ["submersible"], ""),
             ("Doch darin liegt kein Gold, sondern gefälschte Banknoten.", "office", [{"id": "du", "action": "shocked"}], [], ""),
             ("Am Grund liegt eine dicke Schicht aus Baumstämmen.", "underwater", [], [], "event"),
             ("Ein Tauchboot entdeckt dort unten alte Raketenteile.", "underwater", [], ["rocket", "submersible"], "event"),
             ("Dort unten gibt es keinen Sauerstoff.", "underwater", [{"id": "du", "kind": "fish"}], [], ""),
             ("Dort unten verrottet nichts.", "underwater", [{"id": "du", "kind": "fish"}], [], "")]
        sd = stage.direct([{"text": t_, "place": pl_, "time": "night", "actors": a_, "props": pr_, "shot": sh_, "crowd": "walk"} for t_, pl_, a_, pr_, sh_ in T],
                          [(i_ * 4.0, i_ * 4.0 + 4.0) for i_ in range(len(T))], "Der Schatz im Toplitzsee: Was liegt am Grund?", "mysterien")
        ks = [[extras.PROP_ALIASES.get(str(q.get("type")), str(q.get("type"))) for q in sc_.get("props") or []] for sc_ in sd]
        kinds = [[str(a.get("kind") or "") for a in sc_.get("actors") or []] for sc_ in sd]
        assert not any("fish" in k_ for k_ in kinds), f"Fisch im See: {kinds}"
        assert not any(k_ in ("box", "rocket") for ks_ in ks for k_ in ks_), f"Karton/Rakete im See: {ks}"
        assert kinds[0] == ["diver"] and "crates" in ks[0] and sd[0].get("_lake"), (kinds[0], ks[0])
        assert len(sd[1]["actors"]) == 2 and all((a.get("look") or {}).get("hat") == "army" for a in sd[1]["actors"]) and "crates" in ks[1] and places.resolve(stage.backdrop(sd[1])) != "underwater", sd[1]
        assert ks[2] == ["crates_sink"] and not sd[2]["actors"], sd[2]
        assert kinds[3] == ["diver"] and "submersible" not in ks[3], sd[3]
        assert "cashcrate" in ks[4] and places.resolve(stage.backdrop(sd[4])) not in ("office", "underwater") and not sd[4].get("crowd"), sd[4]
        assert ks[5] == ["logs"], sd[5]
        assert ks[6] == ["submersible", "rocketpart"] and not sd[6]["actors"], sd[6]
        assert (ks[7], kinds[7]) != (ks[8], kinds[8]) or sd[7]["actors"][0].get("facing") != sd[8]["actors"][0].get("facing"), "zweimal dasselbe Bild am Seegrund"
        for sc_ in sd:
            im_ = frame(sc_, {"du": {"shirt": "orange"}})
            assert im_.size == (places.W, places.H)
        sea = stage.direct([{"text": "Ein Taucher schwimmt durch das Korallenriff im Ozean.", "place": "underwater", "actors": [{"id": "taucher", "kind": "fish"}], "props": []},
                            {"text": "Der Goldfisch schwimmt im Riff.", "place": "underwater", "actors": [{"id": "fisch", "kind": "fish"}], "props": []}], [(0, 4), (4, 8)], "Leben im Ozean", "fakten")
        assert sea[0]["actors"][0]["kind"] == "diver" and not sea[0].get("_lake") and sea[1]["actors"][0]["kind"] == "fish", sea
        g_ = stage.direct([{"text": "Es gab Gerüchte über Milliarden an Gold.", "shot": "graphic", "graphic": {"type": "number", "value": "BILLIONEN", "label": "REICHSMARK IN GOLD"}},
                           {"text": "Tauchen ist dort streng verboten.", "shot": "graphic", "graphic": {"type": "question", "text": "STRENG VERBOTEN"}}], [(0, 4), (4, 8)], "Gold", "fakten")
        assert g_[0]["graphic"]["value"] == "MILLIARDEN" and not g_[0]["graphic"].get("label"), g_[0]["graphic"]
        assert g_[1]["graphic"]["type"] == "badge", g_[1]["graphic"]
        from PIL import Image as Image_
        assert stage.year_digits("FRÜHJAHR NEUNZEHNHUNDERTFÜNFUNDVIERZIG") == "FRÜHJAHR 1945" and stage.year_digits("EXPEDITION neunzehnhundertneunundfünfzig") == "EXPEDITION 1959" \
            and stage.year_digits("NEUNZEHNHUNDERT") == "1900" and stage.year_digits("HUNDERT METER") == "HUNDERT METER" and stage.year_digits("ZWEITAUSENDACHT") == "2008"
        end_ = stage.direct([{"text": "Im Toplitzsee liegt ein Schatz am Grund.", "place": "underwater"}, {"text": "Im Jahr neunzehnhundertneunundfünfzig holte eine Expedition Kisten aus dem See.", "place": "underwater", "overlay": {"type": "tag", "text": "EXPEDITION NEUNZEHNHUNDERTNEUNUNDFÜNFZIG"}},
                             {"text": "Am dunklen Alpenufer beginnt das Rätsel von vorn.", "backdrop": {"sky": "night", "ground": "water", "elements": ["mountains", "lake"]}, "props": ["ship"], "actors": []}],
                            [(0, 4), (4, 8), (8, 12)], "Der Schatz im Toplitzsee", "mysterien")
        assert end_[1]["overlay"]["text"] == "EXPEDITION 1959", end_[1]["overlay"]
        ng_ = stage.direct([{"text": "Im Toplitzsee liegt ein Schatz am Grund.", "place": "underwater"}, {"text": "Echtes Gold wurde im dunklen Toplitzsee nämlich niemals gefunden.", "place": "lake"},
                            {"text": "Mit dem Falschgeld sollte die Wirtschaft Großbritanniens geschwächt werden.", "place": "germany", "actors": [{"id": "du"}]},
                            {"text": "Unterhalb von zwanzig Metern gibt es keinen Sauerstoff.", "place": "underwater", "actors": [{"id": "taucher", "kind": "diver"}], "overlay": {"type": "card", "text": "KEIN SAUERSTOFF"}}],
                           [(0, 4), (4, 8), (8, 12), (12, 16)], "Der Schatz im Toplitzsee", "mysterien")
        assert not any(extras.PROP_ALIASES.get(str(q.get("type")), str(q.get("type"))) == "goldbars" for q in ng_[1].get("props") or []), ng_[1]
        assert places.resolve(stage.backdrop(ng_[2])) not in stage.MAPS and ng_[2]["actors"], ng_[2]
        assert ng_[3].get("_ov_low") == 3, ng_[3]
        mo_ = stage.direct([{"text": "Im Toplitzsee liegt ein Schatz am Grund.", "place": "underwater"}, {"text": "Im Frühjahr neunzehnhundertfünfundvierzig kamen Lastwagen.", "place": "lake", "overlay": {"type": "tag", "text": "MAI 1945"}},
                            {"text": "Im August 1914 begann es.", "place": "street", "overlay": {"type": "tag", "text": "AUGUST 1914"}},
                            {"text": "Taucher holen eine Kiste vom Grund.", "place": "underwater"}, {"text": "Darin liegen gefälschte Banknoten.", "place": "underwater"}],
                           [(0, 4), (4, 8), (8, 12), (12, 16), (16, 20)], "Der Schatz im Toplitzsee", "mysterien")
        assert mo_[1]["overlay"]["text"] == "1945" and mo_[2]["overlay"]["text"] == "AUGUST 1914", (mo_[1]["overlay"], mo_[2]["overlay"])
        assert any(extras.PROP_ALIASES.get(str(q.get("type")), str(q.get("type"))) == "cashcrate" for q in mo_[4].get("props") or []), mo_[4]
        assert not end_[2]["props"] and len(end_[2]["actors"]) == 1 and not end_[2]["actors"][0].get("kind"), end_[2]
        for k_ in extras.LAKE_KINDS:
            lay_ = Image_.new("RGBA", (places.W, places.H), (0, 0, 0, 0))
            extras.draw_prop(lay_, k_, 540, 1.2)
            assert lay_.getbbox(), k_
        assert extras.creature("diver", 1.0) is not None and places.lakebed().size == (places.W, places.H)

    check("See-Schatz", _lake)

    def _game():                                                 # Videospiel-Thema: Spielwelt als Pixel-Bild, Menschen-Sätze am Rechner – keine Straße, kein Goldfisch (Video 140)
        T = ["Drei geheime Orte in Videospielen, die fast niemand je betreten hat.",
             "Nummer eins: 1980 versteckt ein Programmierer einen geheimen Raum in einem Abenteuerspiel.",
             "Seine Firma nennt ihre Entwickler damals nirgends.",
             "Du trägst einen winzigen grauen Punkt durch eine Wand.",
             "Nummer zwei steckt in einem berühmten Hüpfspiel von 1985.",
             "Das Level liegt unter Wasser und wiederholt sich endlos.",
             "Nach über zwölf Millionen Blöcken zerbricht die Landschaft am Rand der Welt.",
             "Welchen Ort würdest du zuerst suchen?"]
        sd = stage.direct([{"text": t_, "place": "underwater" if i_ % 2 else "street", "time": "night", "actors": [{"id": "du", "kind": "fish", "action": "fall"}] if i_ % 2 else [],
                            "props": ["car"], "shot": "event" if i_ % 3 == 0 else "", "crowd": "walk"} for i_, t_ in enumerate(T)],
                          [(i_ * 4.0, i_ * 4.0 + 4.0) for i_ in range(len(T))], "Drei geheime Orte in Videospielen, die es wirklich gibt", "mysterien")
        subs = [(sc_.get("graphic") or {}).get("sub") if sc_.get("shot") == "graphic" and (sc_.get("graphic") or {}).get("type") == "game" else None for sc_ in sd]
        assert subs[0] == "world" and subs[1] == "room" and subs[3] == "room" and subs[4] == "minus" and subs[5] == "minus" and subs[6] == "far", subs
        labs = [(sc_.get("graphic") or {}).get("label") for sc_ in sd]
        assert labs[3] == "1" and labs[4] == "3" and labs[5] == "2" and labs[6] in ("1", "2"), labs
        assert stage._game_step("room", "im geheimen raum blinkt sein name", {}) == "2" and stage._game_step("minus", "wer durch eine mauer rutscht, landet in welt minus eins", {}) == "0"
        assert stage._game_step("far", "riesige wände voller löcher", {"far": "2"}) == "3"
        for i_ in (2, 7):
            assert subs[i_] is None and sd[i_]["place"] in ("office", "livingroom") and not sd[i_].get("crowd") and sd[i_]["actors"] and not sd[i_]["actors"][0].get("kind"), sd[i_]
        for sc_ in sd:
            frame(sc_)
        for sub_ in graphics.GAME_SUBS + ("x",):
            for st_ in ("0", "1", "2", "3", "9", ""):
                for t_ in (0.0, 0.4, 2.0, 3.9):
                    graphics.frame(graphics.clean({"type": "game", "sub": sub_, "label": st_, "kicker": "Nummer 1", "value": "12 Mio. Blöcke", "text": "x" * 40}), t_, 4.0)
        other = stage.direct([{"text": "Ein geheimer Raum liegt hinter der Wand im Keller.", "place": "basement", "actors": [{"id": "du", "action": "point"}]}], [(0.0, 4.0)], "Das Geheimnis im Keller", "mysterien")
        assert other[0].get("shot") != "graphic", other[0]
        assert not stage.game_story([], "Videospiel-Regeln im Alltag") and not stage.game_story([], "Wie eine Gaming-Bude zum Tech-Giganten wurde") \
            and stage.game_story([], "3 versteckte Orte in Videospielen, die fast kein Spieler je betreten hat"), "Videospiel-Thema falsch erkannt"
        assert overlays.frames_for({"type": "counter", "label": "Jahre", "value": 10, "unit": "bis zur Entdeckung"}), "Zähler mit langer Einheit"
    check("Videospiel-Welt", _game)

    def _refuted():                                              # Stempel zu einem Wort, das der Satz gleich verneint
        sd = stage.direct([{"text": "Du denkst, das war verboten? Falsch, die Firma ließ das Versteck im Spiel.", "place": "office", "actors": [{"id": "du", "action": "talk"}],
                            "overlay": {"type": "stamp", "text": "VERBOTEN", "color": "red"}},
                           {"text": "Das Betreten ist streng verboten.", "place": "office", "actors": [{"id": "du", "action": "talk"}], "overlay": {"type": "stamp", "text": "VERBOTEN", "color": "red"}}],
                          [(0.0, 4.0), (4.0, 8.0)], "Der Wald", "fakten")
        assert "VERBOTEN" not in str(sd[0].get("overlay")), sd[0].get("overlay")
        assert "VERBOTEN" in str(sd[1].get("overlay")), sd[1].get("overlay")
        assert stage.refuted("verbo", "du denkst, das war verboten? falsch, es war erlaubt.") and not stage.refuted("verbo", "das ist verboten. warum?")
    check("Stempel verneint", _refuted)

    def _surface():                                              # Meeresoberfläche: kein Mensch auf dem Wasser, Treibgut statt Karton, Radarschirm, Satellit im All statt Länderkarte
        T = [("Ein Passagierflugzeug verschwindet mitten über dem Ozean.", "space", [], ["plane"], "event", None, {"type": "card", "text": "SIGNAL VERLOREN"}),
             ("Aber moderne Satelliten empfangen noch stumme Pings.", "worldmap", [{"id": "du"}], [], "graphic", {"type": "map", "value": "germany,uk", "text": "PING"}, None),
             ("Also berechnen Physiker kreisförmige Streifen auf dem Ozean.", "worldmap", [{"id": "du"}], [], "", None, None),
             ("Meeresströmungen treiben Trümmerteile über Hunderte Kilometer auseinander.", "ocean", [{"id": "du"}], ["box"], "", None, None),
             ("Dann verschwindet der Punkt plötzlich vom Radar.", "lab", [{"id": "du"}], ["computer"], "", None, None),
             ("Schiffe und Flugzeuge starten eine Suchaktion auf dem Meer.", "ocean", [], ["ship", "plane"], "event", None, {"type": "tag", "text": "STUNDEN SPÄTER"}),
             ("Folg für mehr.", "lab", [{"id": "du"}], [], "", None, None)]
        sd = stage.direct([{"text": t_, "place": pl_, "actors": a_, "props": pr_, "shot": sh_, "time": "day", "graphic": g_, "overlay": o_,
                            "backdrop": {"sky": "day", "ground": "water", "elements": ["sea"]} if pl_ in ("ocean", "space") else None} for t_, pl_, a_, pr_, sh_, g_, o_ in T],
                          [(n_ * 4, n_ * 4 + 4) for n_ in range(len(T))], "Was passiert, wenn ein Flugzeug spurlos verschwindet?", "whatif")
        keys = [[extras.PROP_ALIASES.get(str(q.get("type")).lower(), str(q.get("type")).lower()) for q in sc_.get("props") or []] for sc_ in sd]
        assert sd[0].get("_ov_low") == 1 and not sd[0].get("actors"), f"Schild über dem Flugzeug: {sd[0].get('_ov_low')} {sd[0].get('actors')}"
        assert sd[1].get("shot") != "graphic" and places.resolve(stage.backdrop(sd[1])) == "space" and "satellite" in keys[1], f"Satellit: {sd[1].get('shot')} {sd[1].get('place')} {keys[1]}"
        for n_ in (2, 3):
            bd_ = stage.backdrop(sd[n_])
            assert isinstance(bd_, dict) and bd_.get("ground") == "water", f"Meeresoberfläche {n_}: {bd_}"
            assert not [a_ for a_ in sd[n_].get("actors") or [] if not a_.get("kind")] and keys[n_], f"Mensch auf dem Wasser / leeres Meer {n_}: {sd[n_].get('actors')} {keys[n_]}"
        assert keys[3][:1] == ["debris"] and "box" not in keys[3], f"Treibgut: {keys[3]}"
        assert sd[4].get("shot") == "graphic" and (sd[4].get("graphic") or {}).get("type") == "radar" and sd[4]["graphic"].get("sub") == "lost", f"Radar: {sd[4].get('shot')} {sd[4].get('graphic')}"
        assert sd[5].get("_ov_low") == 2, f"Schild unter dem Schiff: {sd[5].get('_ov_low')}"
        assert [x_ for k_, x_ in stage._prepare(sd[5], {"du": {}})[4] if k_ == "plane"] == [540], "Flugzeug über dem Schiff nicht mittig"
        for sc_ in sd:
            for t_ in (0.2, 1.3, 3.0):
                frame(sc_, {"du": {"shirt": "blau"}}, t=t_)
        land = stage.direct([{"text": "Die Trümmerteile liegen im Labor auf dem Tisch.", "place": "lab", "actors": [{"id": "du"}]}, {"text": "Folg für mehr.", "place": "lab", "actors": [{"id": "du"}]}],
                            [(0, 4), (4, 8)], "Flugzeug", "whatif")
        assert places.resolve(stage.backdrop(land[0])) == "lab" and land[0].get("actors"), f"Trümmer im Labor: {land[0].get('place')} {land[0].get('backdrop')}"
    check("Meeresoberfläche: Treibgut, Radar, Satellit", _surface)
    check("Ballonflucht: Ballon am Boden, am Himmel, im Gebüsch", _balloon)
    check("Titelbild", lambda: stage.cover({"place": "street", "props": ["meteor"], "actor": "du"}, {"du": {}}, "/tmp/_selftest_cover.jpg"))
    check("Titelbild kaputt", lambda: stage.cover({"place": None, "props": [None, 3], "actor": None, "backdrop": "x"}, {}, "/tmp/_selftest_cover.jpg"))
    def _garage():                                               # Werkstatt-Video: Ort, Motor am Kran, Auto drinnen, Teile aus dem Satz
        from PIL import Image
        assert places.resolve("Werkstatt") == "garage" and places.resolve("workshop") == "garage", "Werkstatt landet nicht in der Garage"
        scs = stage.direct([{"text": "Was passiert, wenn man einen V8-Motor in einen Kleinwagen baut?", "place": "garage", "actors": [{"id": "du"}], "props": ["car"]},
                            {"text": "Zuerst hebt der Motorkran den alten Motor aus dem Auto.", "place": "werkstatt", "actors": [{"id": "du", "action": "point"}], "props": ["enginehoist"]},
                            {"text": "Das alte Getriebe hält die Kraft niemals aus.", "place": "garage", "actors": [{"id": "du"}]},
                            {"text": "Von 0 auf 100 in unter vier Sekunden.", "place": "garage", "actors": [{"id": "du"}]}],
                           [(k * 3.0, k * 3.0 + 3.0) for k in range(4)], "V8 im Kleinwagen", "technik")
        kinds = [[extras.PROP_ALIASES.get(str(q.get("type")).lower(), str(q.get("type")).lower()) for q in (sc_.get("props") or []) if isinstance(q, dict)] for sc_ in scs]
        assert "car" in kinds[0], f"Auto fehlt in der Werkstatt: {kinds[0]}"
        assert "enginehoist" in kinds[1] and "engine" not in kinds[1], f"Motor doppelt am Kran: {kinds[1]}"
        for sc_ in scs:
            assert frame(sc_) is not None
        for k in ("engine", "enginestand", "crane", "enginehoist", "tire", "tires", "radiator", "gearbox", "toolbox", "wrench", "speedometer",
                  "scale", "piston", "carlift", "oilcan"):
            for t_ in (0.0, 1.0, 5.0):
                lay = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
                extras.draw_prop(lay, k, 540, t_)
                assert lay.getbbox(), f"{k} zeichnet nichts"
    check("Werkstatt: Motor, Kran, Auto, Getriebe, Tacho", _garage)
    def _word_caps():                                            # Motivation: ein großes Wort nach dem anderen in der Bildmitte
        import tempfile
        from pathlib import Path
        from .. import render
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "w.ass"
            render.build_ass([("Du", 0.0, 0.3), ("bist", 0.3, 0.6), ("unaufhaltsam!", 0.6, 1.4)], [{"highlight": ["unaufhaltsam"]}], [(0, 1.6)], f, style="word")
            big = [ln for ln in f.read_text(encoding="utf-8").splitlines() if ln.startswith("Dialogue") and ",Big," in ln]
            assert len(big) == 3 and big[2].endswith("UNAUFHALTSAM") and "\\fs" in big[2], big
            assert not [ln for ln in f.read_text(encoding="utf-8").splitlines() if ",Cap," in ln and ln.startswith("Dialogue")]
        import json
        cats = {c["slug"]: c for c in json.loads((Path(__file__).resolve().parents[2] / "docs" / "data" / "config.json").read_text(encoding="utf-8"))["categories"]}
        assert cats["motivation"]["enabled"] and cats["motivation"]["caption_style"] == "word" and cats["vergleich"]["enabled"]
        assert cats["liebe"]["enabled"] and cats["liebe"]["own_voice"] and cats["liebe"]["gemini_voice"] == "Despina"
        from .. import sound
        assert sound.MOOD_OF["liebe"] == "romantisch" and sound.MUSIC["romantisch"]
        sc_ = stage.direct([{"text": "Sie sahen sich an.", "place": "beach", "actors": [{"id": "lena"}], "mood": "calm"},
                      {"text": "Dann ging er für immer.", "place": "station", "actors": [{"id": "lena"}], "mood": "sad"}], [(0, 2), (2, 4)], "Liebe", "liebe")
        assert sc_[0]["mood"] == "love" and sc_[1]["mood"] == "sad", [s["mood"] for s in sc_]
        from .. import fresh, state as st_
        keep, sv = json.loads(json.dumps(st_.CONFIG)), fresh.save
        fresh.save = lambda *a, **k: None
        try:
            fresh.sync_admin_settings(json.loads(json.dumps(keep)), {"rubriken": True}, ["liebe", "tiere"])
            assert sorted(c["slug"] for c in st_.CONFIG["categories"] if c.get("enabled")) == ["liebe", "tiere"]
        finally:
            st_.CONFIG.clear(); st_.CONFIG.update(keep); fresh.save = sv
    check("Motivation: Wort für Wort, Rubriken da (auch Liebe), freigegebene Rubriken je Zugang", _word_caps)

    def _hook_count():                                           # Hook-Titel im ersten Bild, Listen-Zähler „2/4“
        import tempfile
        from pathlib import Path
        from .. import render as rd
        sc_l = [{"text": "Vier Typen sitzen an Weihnachten an jedem Tisch."}, {"text": "Und den letzten kennst du."}, {"text": "Nummer eins, die Oma."},
                {"text": "Sie kocht zu viel."}, {"text": "Nummer zwei: der Onkel."}, {"text": "Typ Nummer drei ist der Handy-Neffe."}, {"text": "Und Nummer vier bist du."}]
        m_, n_ = rd.list_counter(sc_l, "Vier Typen am Tisch")
        assert n_ == 4 and m_ == {2: 1, 4: 2, 5: 3, 6: 4}, (m_, n_)
        assert rd.list_counter([{"text": "Was wäre, wenn die Sonne ausgeht?"}, {"text": "Es wird kalt."}, {"text": "Nummer eins der Gefahren."}])[1] == 0
        with tempfile.TemporaryDirectory() as td:
            f_ = Path(td) / "a.ass"
            tm = [(i * 2.0, i * 2.0 + 2.0) for i in range(len(sc_l))]
            rd.build_ass([("Vier", 0.1, 0.4)], sc_l, tm, f_, hook="VIER TYPEN AM WEIHNACHTSTISCH", title="Vier Typen am Tisch")
            ev = [ln for ln in f_.read_text(encoding="utf-8").splitlines() if ln.startswith("Dialogue")]
            hk = [ln for ln in ev if ",Hook," in ln]
            assert len(hk) == 1 and hk[0].startswith("Dialogue: 4,0:00:00.00") and "\\N" in hk[0], hk
            assert len([ln for ln in ev if ",Num," in ln]) == 4
            rd.build_ass([("Mut", 0.1, 0.4)], sc_l, tm, f_, style="word", hook="NIE AUFGEBEN")
            assert not [ln for ln in f_.read_text(encoding="utf-8").splitlines() if ",Hook," in ln or ",Num," in ln]
    check("Hook-Titel im ersten Bild, Listen-Zähler", _hook_count)

    def _ytcut():                                                # kürzere YouTube-Fassung: was darf raus, wer bekommt welche Datei
        from .. import ytcut, main as mn, uploaders as up
        sc_y = [{"text": f"Satz {i}."} for i in range(14)]
        sc_y[5]["text"] = "Nummer zwei ist der Onkel."
        tm = [(i * 5.0, i * 5.0 + 5.0) for i in range(14)]       # 70 s
        keep = ytcut.plan(sc_y, tm, 55, lambda *a: ({"drop": [0, 1, 4, 5, 7, 12, 13, "x"]}, ""))
        assert keep == [0, 1, 2, 3, 5, 6, 8, 9, 10, 11, 12, 13], keep        # nie Anfang/Ende/Listen-Nummer, nur gültige Nummern
        assert ytcut.plan(sc_y, tm, 0, lambda *a: ({"drop": [4]}, "")) is None
        assert ytcut.plan(sc_y[:8], tm[:8], 55, lambda *a: ({"drop": [4]}, "")) is None          # 40 s: schon kurz genug
        k2 = ytcut.plan(sc_y, tm, 55, lambda *a: ({"drop": [2, 3, 4, 6, 7, 8, 9, 10]}, ""))
        assert k2 and 70 - 5 * (14 - len(k2)) >= 47, k2                      # nicht zu viel wegschneiden
        calls, saved = [], (up.upload_video, up.zernio_ready, up.connected, mn.cfg)
        def fake(v, path):
            calls.append((path, bool(v.get("yt_id")), bool(v.get("tt_publish_id"))))
            if not v.get("yt_id"):
                v["yt_id"] = "Y1"
            if not v.get("tt_publish_id"):
                v["tt_publish_id"] = "T1"
            v["error"] = None
        try:
            up.upload_video, up.zernio_ready, up.connected = fake, (lambda: False), (lambda p: True)
            mn.cfg = lambda k: True if k == "youtube_enabled" else saved[3](k)
            import tempfile
            from pathlib import Path
            with tempfile.TemporaryDirectory() as td:
                short = Path(td) / "k.mp4"
                short.write_bytes(b"x")
                v_ = {"id": 1}
                mn.upload_split(v_, "voll.mp4", short)
                assert calls == [(short, False, True), ("voll.mp4", True, False)], calls
                assert v_["yt_id"] == "Y1" and v_["tt_publish_id"] == "T1" and v_["status"] == "published", v_
                calls.clear()
                mn.upload_split({"id": 2}, "voll.mp4", None)
                assert calls == [("voll.mp4", False, False)], calls
        finally:
            up.upload_video, up.zernio_ready, up.connected, mn.cfg = saved
    check("YouTube-Kurzfassung: Auswahl und getrennte Uploads", _ytcut)

    def _shape():                                                # KI schreibt eine Liste, wo ein Objekt stehen muss
        from .. import ai
        js_ = ai._shape({"scenes": [{"text": "a", "overlay": [{"type": "card", "text": "X"}], "graphic": [], "actors": ["du", {"id": "er"}, 3]}, "kaputt"],
                         "thumbnail": [{"text": "T"}], "cast": [{"id": "du", "shirt": "rot"}], "fixes": [{"i": 1}]})
        assert js_ == {"scenes": [{"text": "a", "overlay": {"type": "card", "text": "X"}, "graphic": None, "actors": [{"id": "du"}, {"id": "er"}]}],
                       "thumbnail": {"text": "T"}, "cast": {"du": {"shirt": "rot"}}, "fixes": [{"i": 1}]}, js_
    check("KI-Antwort: Liste statt Objekt wird bereinigt", _shape)

    for g_m in ({"type": "message", "kicker": "UNBEKANNT", "lines": ["In sieben Tagen", "beginnt es.", "!Öffne niemals die Tür."]},
                {"type": "message", "text": "Geh zur Bank. / Heb alles ab. / !Alles."}, {"type": "message", "lines": ["x" * 80] * 9},
                {"type": "chapter", "value": "7", "text": "TAGE ÜBRIG"}, {"type": "chapter", "value": "1", "kicker": "LETZTER TAG", "text": "NOCH 24 STUNDEN"}):
        for t_m in (0.0, 0.5, 2.0, 4.9):
            check(f"Grafik {g_m['type']} t={t_m}", lambda: graphics.frame(graphics.clean(g_m), t_m, 5.0))
    assert graphics.clean({"type": "message"}) is None and graphics.clean({"type": "chapter", "text": "x"}) is None
    assert len(graphics.clean({"type": "message", "lines": ["a"] * 9})["lines"]) == 6

    def _noir():                                                 # Rubrik „Unbekannte Nachricht“: düsterer Look, Nachricht, Kapitelkarte
        import json
        from pathlib import Path
        cats = {c["slug"]: c for c in json.loads((Path(__file__).resolve().parents[2] / "docs" / "data" / "config.json").read_text(encoding="utf-8"))["categories"]}
        assert cats["nachricht"]["enabled"] and cats["nachricht"]["look"] == "noir" and cats["nachricht"]["own_voice"]
        sc_n = [{"text": "Drei Uhr zwölf. Dein Handy vibriert.", "place": "bedroom", "time": "night", "actors": [{"id": "du", "action": "sleep"}]},
                {"text": "Vertrau niemandem.", "shot": "graphic", "graphic": {"type": "message", "lines": ["Vertrau niemandem.", "!Öffne nicht die Tür."]}},
                {"text": "Noch sieben Tage.", "shot": "graphic", "graphic": {"type": "chapter", "value": "7", "text": "TAGE ÜBRIG"}}]
        stage.direct(sc_n, [(0, 3), (3, 6), (6, 8)], "Unbekannte Nachricht", "nachricht", "noir")
        assert [s.get("look") for s in sc_n] == ["noir"] * 3
        assert [(s.get("graphic") or {}).get("type") for s in sc_n[1:]] == ["message", "chapter"], [s.get("graphic") for s in sc_n]
        from PIL import Image
        bg = graphics.noir(Image.new("RGB", (graphics.W, graphics.H), (240, 200, 120)))
        r_, g_, b_ = bg.getpixel((10, 10))
        assert max(r_, g_, b_) < 200 and abs(r_ - b_) < 60, (r_, g_, b_)
    check("Unbekannte Nachricht: düsterer Look, Nachricht, Kapitelkarte", _noir)

    def _adopt():                                                # Gelerntes aus Kopien: nur Neues, keine fremden Wörter, nur nach Bild-Prüfung
        import tempfile
        from pathlib import Path
        from .. import adopt, state as st_
        good = [{"t": "rect", "x": 150, "y": 200, "w": 100, "h": 200, "c": "#88aa44"}, {"t": "ellipse", "cx": 200, "cy": 180, "rx": 60, "ry": 40, "c": "#cc4444"}]
        theirs = {"sextant": {"name": "sextant", "aliases": ["sextanten", "haus", "geld"], "shapes": good}, "auto": {"name": "auto", "shapes": good},
                  "kaputt": {"name": "kaputt", "shapes": [{"t": "rect"}]}, "boese": {"name": "boese", "shapes": good}, "x": "<script>"}
        saved = {}
        old = (adopt._repo_ok, adopt._fetch_shapes, adopt._looks_ok, adopt.load, adopt.save)
        try:
            adopt._repo_ok = lambda f: "main" if f == "freund/autoshorts" else None
            adopt._fetch_shapes = lambda f, b: theirs
            adopt._looks_ok = lambda n, png: (n != "boese", "test")
            adopt.load = lambda name, default: {}
            adopt.save = lambda name, obj: saved.update(obj)
            assert adopt.adopt("freund/autoshorts,fremd/repo") == 1
        finally:
            adopt._repo_ok, adopt._fetch_shapes, adopt._looks_ok, adopt.load, adopt.save = old
        assert set(saved) == {"sextant"} and saved["sextant"]["aliases"] == ["sextanten"], saved.keys()
    check("Kanäle: Übernahme aus Kopien nur geprüft", _adopt)

    def _size():                                                 # winzige Tiere: Größe mit Zoom und Lineal statt Tier so groß wie ein Bär
        assert graphics.size_mm("nur etwa einen halben Millimeter groß") == 0.5 and graphics.size_mm("50 Mikrometer") == 0.05
        assert graphics.size_mm("0,3 mm") == 0.3 and graphics.size_mm("Der Hai ist 4 Meter lang") is None
        assert graphics.fmt_size(0.5) == "0,5 mm" and graphics.fmt_size(0.05) == "50 µm"
        scs = [{"text": "Ein Löwe ist stark.", "place": "savannah", "actors": [{"id": "du"}]},
               {"text": "Das Bärtierchen ist nur etwa einen halben Millimeter groß.", "place": "forest", "actors": [{"id": "_t", "kind": "tardigrade"}]},
               {"text": "Es wird einen halben Millimeter groß.", "place": "forest", "actors": [{"id": "_t", "kind": "tardigrade"}]}]
        stage.direct(scs, [(k * 3.5, k * 3.5 + 3.5) for k in range(3)], "Bärtierchen", "tiere", "")
        assert scs[1].get("shot") == "graphic" and scs[1]["graphic"]["type"] == "size" and scs[1]["graphic"]["value"] == "0,5 mm", scs[1]
        assert scs[2].get("graphic", {}) is None or (scs[2].get("graphic") or {}).get("type") != "size"   # nur einmal je Video
        for v, k_ in (("0,5 mm", "tardigrade"), ("2 mm", "flea"), ("50 µm", "cell"), ("12 mm", "bee")):
            g_ = graphics.clean({"type": "size", "value": v, "kind": k_})
            for t_ in (0.0, 1.0, 3.0):
                assert graphics.frame(g_, t_, 3.4) is not None
        assert graphics.clean({"type": "size", "value": "groß"}) is None
    check("Größe: winzige Tiere mit Zoom und Lineal", _size)

    from ..writer import repeat_trouble as _w_rep
    def _ice():                                                  # zugefrorenes Meer: Eisfläche statt Wellen/Gebirge, Schiff im Eis, Eisdecke über dem Wasser, Atemloch
        from PIL import Image
        sea_bd = {"sky": "day", "ground": "snow", "elements": ["sea"]}
        T = [("Wenn die Ostsee schlagartig komplett zufriert.", "beach", [], ["ship"], "event", sea_bd, None),
             ("Riesige Containerschiffe stecken sofort bombenfest.", "snow", [], ["ship", "ice"], "event", sea_bd, None),
             ("Fische geraten unter dem Eis in Atemnot.", "underwater", [{"id": "ecky"}], ["ice"], "event", None, None),
             ("Nur Delfine finden an Atemlöchern noch Sauerstoff.", "snow", [], ["ice"], "event", sea_bd, None),
             ("Nach drei Tagen wächst die Eisschicht auf mehrere Meter an.", "snow", [{"id": "du"}], [], "", None, None),
             ("An den Küsten sinken die Temperaturen um über fünfzehn Grad.", "snow", [], ["house"], "", sea_bd, {"type": "thermo", "value": 15}),
             ("Es fällt weniger Regen und die Dürregefahr steigt.", "fields", [], ["crack"], "event", {"sky": "day", "ground": "dry", "elements": ["fields"]}, None),
             ("Du denkst, das sei unmöglich.", "livingroom", [{"id": "du"}], [], "", None, None),
             ("Damals wurden auf dem Eis sogar Wirtshäuser für Reisende aufgebaut.", "snow", [], ["house"], "event", sea_bd, None)]
        sd = stage.direct([{"text": t_, "place": pl_, "actors": a_, "props": pr_, "shot": sh_, "time": "day", "backdrop": bd_, "overlay": o_} for t_, pl_, a_, pr_, sh_, bd_, o_ in T],
                          [(n_ * 4, n_ * 4 + 4) for n_ in range(len(T))], "Was wäre, wenn die Ostsee plötzlich komplett zufriert?", "whatif")
        keys = [[extras.PROP_ALIASES.get(str(q.get("type")).lower(), str(q.get("type")).lower()) for q in sc_.get("props") or [] if isinstance(q, dict)] for sc_ in sd]
        rp = [places.resolve(stage.backdrop(sc_)) for sc_ in sd]
        assert rp[0] == rp[1] == rp[4] == rp[8] == "icesea", f"Eisfläche: {rp}"
        assert "ship_ice" in keys[0] and "ship_ice" in keys[1] and "ship" not in keys[1] and "ice" not in keys[1], f"Schiff im Eis: {keys[:2]}"
        assert rp[2] == "underwater" and sd[2].get("_ice") and "ice" not in keys[2] and sd[2].get("actors"), f"unter dem Eis: {rp[2]} {keys[2]} {sd[2].get('actors')}"
        assert keys[3] == ["icehole"] and not sd[3].get("actors"), f"Atemloch: {keys[3]}"
        assert not (isinstance(sd[5].get("overlay"), dict) and sd[5]["overlay"].get("type") == "thermo"), f"Thermometer bei „um fünfzehn Grad“: {sd[5].get('overlay')}"
        assert rp[6] != "icesea" and rp[7] == "livingroom", f"Acker/Zimmer auf dem Eis: {rp[6]} {rp[7]}"
        for sc_ in sd:
            assert frame(sc_, {"du": {}, "ecky": {"kind": "fish"}}) is not None
        plain = stage.direct([{"text": "Im Winter liegt Schnee auf dem Berg.", "place": "snow", "actors": [{"id": "du"}]},
                              {"text": "Ein Schiff fährt über das Meer.", "place": "beach", "props": ["ship"], "backdrop": {"ground": "water", "elements": ["sea"]}}],
                             [(0, 4), (4, 8)], "Winter in den Bergen", "fakten")
        assert all(places.resolve(stage.backdrop(sc_)) != "icesea" for sc_ in plain), "Eisfläche ohne zugefrorenes Meer"
        for k_ in ("ship_ice", "icehole"):
            for t_ in (0.0, 1.0, 5.0):
                lay = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
                extras.draw_prop(lay, k_, 540, t_)
                assert lay.getbbox(), f"{k_} zeichnet nichts"
        places.ICE[0] = True
        try:
            assert places.background("underwater") is not None
        finally:
            places.ICE[0] = False
        T2 = [("Wenn die Ostsee zufriert, stecken Schiffe im Eis fest.", "icesea", [], ["ship"]),
              ("Und am Ende marschiert eine ganze Armee zu Fuß über das Eis.", "icesea", [{"id": "du", "action": "walk"}], []),
              ("Du könntest zu Fuß von Deutschland direkt nach Dänemark und Schweden laufen.", "germany", [{"id": "du", "action": "walk"}], []),
              ("Du denkst, das ist nur Science-Fiction? Falsch, das ist schon so passiert.", "germany", [{"id": "du", "action": "walk"}], [])]
        s2 = stage.direct([{"text": t_, "place": pl_, "actors": a_, "props": pr_, "mood": "tense"} for t_, pl_, a_, pr_ in T2], [(n_ * 4, n_ * 4 + 4) for n_ in range(len(T2))],
                          "Was wäre, wenn die Ostsee plötzlich komplett zufriert?", "whatif")
        assert not s2[1].get("actors") and s2[1].get("crowd") == "walk", f"Armee auf dem Eis: {s2[1].get('actors')} {s2[1].get('crowd')}"
        assert s2[2].get("shot") == "graphic" and "denmark" in str((s2[2].get("graphic") or {}).get("value")), f"Länderkarte: {s2[2].get('shot')} {s2[2].get('graphic')}"
        assert places.resolve(stage.backdrop(s2[3])) not in stage.MAPS and s2[3].get("actors"), f"Karte ohne Land im Satz: {s2[3].get('place')}"
        for sc_ in s2:
            assert frame(sc_, {"du": {}}) is not None
        s3 = stage.direct([{"text": "Wenn die Ostsee zufriert, stecken Schiffe im Eis fest.", "place": "icesea", "props": ["ship"]},
                           {"text": "Unter dem Eis wird für die Fische der Sauerstoff knapp.", "place": "underwater", "overlay": {"type": "bar", "label": "SAUERSTOFF", "value": 15}},
                           {"text": "Nur noch fünfzehn Prozent Sauerstoff bleiben den Fischen.", "place": "underwater", "overlay": {"type": "bar", "label": "SAUERSTOFF", "value": 15}},
                           {"text": "Und auch in der moderneren Geschichte gab es einen solchen Rekordwinter.", "place": "icesea", "shot": "event"},
                           {"text": "Schweinswale sind die einzigen Wale hier und müssen regelmäßig atmen.", "place": "icesea", "shot": "event"}],
                          [(n_ * 4, n_ * 4 + 4) for n_ in range(5)], "Was wäre, wenn die Ostsee plötzlich komplett zufriert?", "whatif")
        assert not (isinstance(s3[1].get("overlay"), dict) and s3[1]["overlay"].get("type") == "bar"), f"Füllstand mit erfundener Zahl: {s3[1].get('overlay')}"
        assert isinstance(s3[2].get("overlay"), dict) and s3[2]["overlay"].get("type") == "bar", f"gesprochener Füllstand fehlt: {s3[2].get('overlay')}"
        assert s3[3].get("actors") and not s3[3].get("crowd"), f"leere Eisfläche: {s3[3].get('actors')} {s3[3].get('crowd')}"
        assert [str(q.get("type")) for q in s3[4].get("props") or []] == ["icehole"], f"Schweinswal ohne Atemloch: {s3[4].get('props')}"
        assert _w_rep({"scenes": [{"text": t_} for t_ in ("Die Ostsee friert leichter zu als die Nordsee, weil ihr Wasser weniger Salz enthält.", "Unter dem Eis wird der Sauerstoff knapp.",
                                                          "Die Ostsee friert viel leichter zu als die Nordsee.", "Ganz im Norden friert die Ostsee jeden Winter zu.",
                                                          "Ganz im Norden friert die Ostsee bis heute jeden Winter zu.")]}), "doppeltes Drehbuch nicht erkannt"
        from .. import writer as _w
        fy = _w.fix_years({"scenes": [{"text": "Im Winter neunzehnhunderteinundachtzig war die Ostsee fast zu.", "overlay": {"type": "tag", "text": "WINTER 1981"}}]},
                          "Ostsee – Vorgaben: 1658 Armee, 1987 fast zugefroren. Keine anderen Jahreszahlen.")
        assert "neunzehnhundertsiebenundachtzig" in fy["scenes"][0]["text"] and fy["scenes"][0]["overlay"]["text"] == "WINTER 1987", fy
    check("Zugefrorenes Meer: Eisfläche, Schiff im Eis, Eisdecke, Atemloch", _ice)

    def _animals():                                              # Tiere aus dem Satz stehen im Bild; im „Tiere sprechen“-Video bewegen sie den Mund
        T = [("Kühe fordern freie Weidezeiten und protestieren auf den Wiesen.", "farm", []),
             ("Niemand isst ein Schnitzel, wenn das Schwein fragt.", "kitchen", [{"id": "du", "action": "shocked", "speaks": True}]),
             ("Nach einem Monat kooperieren Forscher mit Schimpansen.", "lab", [{"id": "du", "action": "walk"}]),
             ("Bis auf eine winzige Mücke, die dir sagt, dass sie dich liebt.", "bedroom", [{"id": "du", "action": "shocked"}]),
             ("Da hast du noch einmal Schwein gehabt.", "livingroom", [{"id": "du"}])]
        sd = stage.direct([{"text": t_, "place": pl_, "actors": a_} for t_, pl_, a_ in T], [(n_ * 4, n_ * 4 + 4) for n_ in range(len(T))],
                          "Was wäre, wenn alle Tiere plötzlich sprechen könnten?", "whatif")
        kinds = [[str(a_.get("kind") or "") for a_ in sc_.get("actors") or []] for sc_ in sd]
        assert kinds[0] == ["cow"] * 3, f"Kühe: {kinds[0]}"
        assert kinds[1] == ["", "pig"] and kinds[2] == ["", "chimp"] and kinds[3] == ["", "mosquito"], f"Tier neben dem Menschen: {kinds[1:4]}"
        assert "pig" not in kinds[4], f"Redewendung: {kinds[4]}"
        assert [a_ for a_ in sd[1]["actors"] if a_.get("kind")][0].get("speaks"), "sprechendes Tier bewegt den Mund nicht"
        for sc_ in sd:
            assert frame(sc_, {"du": {}}) is not None
    check("Tiere aus dem Satz im Bild (Kuh, Schwein, Schimpanse, Mücke)", _animals)
    def _pruef_1116():                                           # Prüfung 16.11.: halber Schlusssatz, erfundenes Siegertreppchen, Plakette mit Fragezeichen, zweimal derselbe Einschub
        from .. import writer as _w
        js = _w.polish({"title": "x", "scenes": [{"text": f"Satz Nummer {n_} erzählt etwas ganz anderes."} for n_ in range(8)]
                        + [{"text": "Und genau aus diesem Grund passiert das jedes Mal wieder, sobald..."}]})
        assert js["scenes"][-1]["text"] == "Und genau aus diesem Grund passiert das jedes Mal wieder.", js["scenes"][-1]["text"]
        js = _w.polish({"title": "x", "scenes": [{"text": f"Satz Nummer {n_} erzählt etwas ganz anderes."} for n_ in range(8)] + [{"text": "Und das passiert, weil."}]})
        assert len(js["scenes"]) == 8, js["scenes"][-1]
        js = _w.polish({"title": "x", "scenes": [{"text": f"Satz Nummer {n_} erzählt etwas ganz anderes."} for n_ in range(8)] + [{"text": "Genau so fühlt sich das an, und zwar jedes Mal."}]})
        assert js["scenes"][-1]["text"] == "Genau so fühlt sich das an, und zwar jedes Mal.", js["scenes"][-1]["text"]
        sd = stage.direct([{"text": "Nicht jeder Mensch spürt dieses Gefühl gleich stark, doch woran liegt dieser Unterschied?", "place": "lab", "shot": "graphic",
                            "graphic": {"type": "podium", "kicker": "KÖRPER", "text": "ARME", "left": "NACKEN", "right": "RÜCKEN"}, "actors": [{"id": "du"}]},
                           {"text": "Es ist ein uralter Überlebensreflex aus der Steinzeit.", "place": "lab", "shot": "graphic", "graphic": {"type": "badge", "text": "ÜBERLEBENSREFLEX?"}},
                           {"text": "Platz eins geht an die Arme, dann kommen Nacken und Rücken.", "place": "lab", "shot": "graphic",
                            "graphic": {"type": "podium", "kicker": "KÖRPER", "text": "ARME", "left": "NACKEN", "right": "RÜCKEN"}}],
                          [(0, 5), (5, 10), (10, 15)], "Warum du bei Musik Gänsehaut bekommst", "fakten")
        assert not sd[0].get("graphic") and sd[0].get("shot") != "graphic", f"erfundenes Siegertreppchen bleibt: {sd[0].get('graphic')}"
        assert not sd[1].get("graphic") or not str(sd[1]["graphic"].get("text")).endswith("?"), sd[1].get("graphic")
        assert isinstance(sd[2].get("graphic"), dict) and sd[2]["graphic"].get("type") == "podium", f"genanntes Siegertreppchen fehlt: {sd[2].get('graphic')}"
        sd = stage.direct([{"text": "Das passiert kurz vor dem Fernseher.", "place": "livingroom", "shot": "insert", "props": [{"type": "tv"}]},
                           {"text": "Schon vor dem Fernseher passiert etwas Verrücktes im Kopf.", "place": "livingroom", "props": [{"type": "tv"}], "actors": [{"id": "du"}]}],
                          [(0, 4), (4, 9)], "Fernsehen", "fakten")
        if sd[0].get("shot") == "insert" and all(any((q_.get("type") if isinstance(q_, dict) else q_) == "tv" for q_ in sx_.get("props") or []) for sx_ in sd):
            assert sd[1].get("_no_insert"), "zweimal hintereinander Einschub auf dasselbe Ding"
        for sc_ in sd:
            assert frame(sc_, {"du": {}}) is not None
    check("Prüfung 16.11.: halber Schlusssatz, erfundenes Siegertreppchen, Plakette mit Fragezeichen", _pruef_1116)

    def _pruef_1116b():                                          # Prüfung 16.11., 1. Neubau: Nacht ohne Grund, Oberarm statt Haarbalgmuskeln, Mensch statt Vorfahre, Blitz bei „blitzschnell“
        T = [{"text": "Manche Songs treffen dich so hart, dass dir plötzlich Gänsehaut kommt.", "place": "livingroom", "time": "night", "actors": [{"id": "du"}]},
             {"text": "In diesem Moment ziehen sich winzige Muskeln zusammen, aber warum reagiert dein Körper so?", "place": "livingroom", "time": "night",
              "props": [{"type": "lib_muskel"}], "shot": "insert"},
             {"text": "Das ist ein alter Reflex von deinen behaarten Vorfahren.", "place": "forest", "time": "day", "actors": [{"id": "du", "action": "think"}]},
             {"text": "Die blitzschnelle Erleichterung danach fühlt sich extrem gut an.", "place": "livingroom", "time": "night", "actors": [{"id": "du"}]},
             {"text": "Das funktioniert bei traurigen Songs genauso wie bei wilden Party-Hits.", "place": "livingroom", "time": "night", "actors": [{"id": "du"}]}]
        sd = stage.direct([dict(x_) for x_ in T], [(n_ * 4, n_ * 4 + 4) for n_ in range(len(T))], "Warum du bei Musik Gänsehaut bekommst – Vorgaben: keine Zahlen", "fakten")
        assert all(sc_.get("time") != "night" for sc_ in sd), f"Nacht ohne Grund: {[sc_.get('time') for sc_ in sd]}"
        k1 = [str(q_.get("type") if isinstance(q_, dict) else q_) for q_ in sd[1].get("props") or []]
        assert "lib_muskel" not in k1, f"Oberarm statt Haarbalgmuskeln: {k1}"
        assert [str(a_.get("kind") or "") for a_ in sd[2].get("actors") or []] == ["chimp"], f"Vorfahren: {sd[2].get('actors')}"
        assert "lightning" not in [str(q_.get("type") if isinstance(q_, dict) else q_) for q_ in sd[3].get("props") or []], "Blitz bei blitzschnell"
        sn = stage.direct([dict(x_, text=x_["text"] + (" Mitten in der Nacht." if n_ == 0 else "")) for n_, x_ in enumerate(T)],
                          [(n_ * 4, n_ * 4 + 4) for n_ in range(len(T))], "Musik in der Nacht", "fakten")
        assert sn[0].get("time") == "night", "genannte Nacht wird Tag"
        for sc_ in sd:
            assert frame(sc_, {"du": {}}) is not None
        sg = stage.direct([{"text": "Winzige Muskeln an jeder einzelnen Haarwurzel ziehen sich in diesem Moment zusammen.", "place": "lab", "props": [{"type": "goosebumps"}],
                            "shot": "event", "actors": [{"id": "du", "action": "walk"}]}], [(0, 4)], "Warum du bei Musik Gänsehaut bekommst", "fakten")
        a_g = [a_ for a_ in sg[0].get("actors") or [] if not a_.get("kind")][0]
        assert a_g.get("pos") == "left" and a_g.get("action") == "point" and sg[0].get("shot") != "event", f"Figur läuft durch das Schaubild: {a_g} {sg[0].get('shot')}"
        assert frame(sg[0], {"du": {}}) is not None
        assert stage.poster_hero("Warum du bei Musik Gänsehaut bekommst", [{"actors": [{"kind": "chimp"}]}] * 2 + [{"actors": [{"kind": "brain"}]}] * 5 + [{}] * 13, None, ["brain"]) == "brain", "Nebenfigur auf dem Titelbild"
        assert not any(k_ == "money" for pat_, k_ in stage.TEXT_PROPS if __import__("re").search(pat_, "gesteuert wird das ganze vom unwillkürlichen nervensystem")), "gesteuert → Geld"
        assert stage._hint("Schon in den Sekunden vor deiner Lieblingsstelle steigt der Spiegel im Kopf an.") != "bathroom", "Dopaminspiegel → Badezimmer"
        assert stage._hint("Du schaust morgens in den Spiegel.") == "bathroom"
        from .. import overlays as _ov
        assert _ov.quote("FORSCHER VERMUTEN", "…dass die plötzliche Wende der Musik im Gehirn kurz wie ein Alarm wirkt.") is not None
    check("Prüfung 16.11.: Nacht ohne Grund, Haarbalgmuskeln, Vorfahren, blitzschnell", _pruef_1116b)
    def _hybrid():                                               # Prüfung 19.11.2026 (Video 152): Super-Tier aus vier Arten – das Misch-Wesen ist zu sehen, kein Wal im Labor
        T = ["Du baust im Labor das perfekte Super-Tier aus vier Tieren.", "Zutat eins: die Beine vom Gepard.", "In freier Wildbahn wurden 93 Kilometer pro Stunde gemessen.",
             "Dein Super-Tier sprintet jetzt los.", "Zutat drei: die Zähigkeit vom Bärtierchen.", "Es übersteht fast minus 272 Grad.", "Zutat vier: das Herz vom Blauwal.",
             "Du denkst, dieses Monster ist unbesiegbar?", "Dein Super-Tier bricht unter seinem eigenen Herzen zusammen.", "Übrig bleibt nur ein Haufen verwirrter Zellen auf dem Tisch.",
             "Welche Tier-Superkraft hättest du gern?"]
        sc = [{"text": t_, "place": "street", "time": "day", "crowd": "walk", "actors": [{"id": "du", "action": "walk", "speaks": True}]} for t_ in T]
        sc[2].update(shot="graphic", graphic={"type": "number", "value": "93", "label": "KM"})
        sc[5]["overlay"] = {"type": "counter", "label": "", "value": 272, "unit": "GRAD"}
        sc[7]["props"] = [{"type": "scale", "pos": 600}]
        sd = stage.direct(sc, [(i_ * 4, i_ * 4 + 4) for i_ in range(len(sc))], "Was wäre, wenn du ein Super-Tier aus vier Tierarten baust?", "whatif")
        kinds = [[str(a_.get("kind") or "") for a_ in s_.get("actors") or []] for s_ in sd]
        assert not sd[4]["actors"][0].get("hero") and [q_.get("type") for q_ in sd[4].get("props") or []] == ["moss"], "Bärtierchen klein am Moos"
        assert sd[4].get("place") == "forest" and sd[1].get("place") == "savannah" and sd[6].get("place") == "underwater", "genanntes Tier in seinem Lebensraum, nicht auf der Straße"
        sf = stage.direct([{"text": t_, "place": "lab", "actors": [{"id": "du"}]} for t_ in ("Du baust ein Super-Tier.", "Zutat drei ist das Bärtierchen.", "Es übersteht extreme Kälte.",
                                                                                              "Im Jahr 2007 überlebte es sogar den offenen Weltraum.", "Das Herz wiegt 180 Kilogramm.")],
                          [(i_ * 4, i_ * 4 + 4) for i_ in range(5)], "Was wäre, wenn du ein Super-Tier aus vier Tierarten baust?", "whatif")
        kf = [[str(a_.get("kind") or "") for a_ in s_.get("actors") or []] for s_ in sf]
        assert kf[2] == ["tardigrade"] and kf[3] == ["tardigrade"] and sf[3].get("place") == "space", f"Folgesätze bleiben beim Tier: {kf} {sf[3].get('place')}"
        assert "chimera" in kf[4] and "tardigrade" not in kf[4], f"Herz-Satz zeigt das Wesen, nicht das Tier von eben: {kf[4]}"
        for i_ in (0, 7, 8, 9, 10):
            assert "chimera" in kinds[i_] and "" in kinds[i_] and sd[i_].get("place") == "lab", f"Satz {i_}: Misch-Wesen und Hauptfigur im Labor erwartet: {kinds[i_]} {sd[i_].get('place')}"
            assert not sd[i_].get("crowd") and not sd[i_].get("props"), f"Satz {i_}: Passanten/Waage im Labor"
        assert kinds[3] == ["chimera"] and sd[3]["actors"][0].get("action") == "run" and sd[3].get("place") == "savannah", f"Sprint: {kinds[3]} {sd[3].get('place')}"
        assert kinds[1] == ["cheetah"] and kinds[4] == ["tardigrade"] and kinds[6] == ["whale"], f"genannte Tiere: {kinds[1]} {kinds[4]} {kinds[6]}"
        assert [a_ for a_ in sd[8]["actors"] if a_.get("kind")][0].get("action") == "down", "bricht zusammen: Wesen liegt"
        assert sd[2]["graphic"].get("label") == "KM/H", sd[2]["graphic"]
        assert sd[5]["overlay"].get("label") == "MINUS", sd[5]["overlay"]
        assert all(not (str(a_.get("id") or "") in ("_tier", "_meer") and not a_.get("kind")) for s_ in sd for a_ in s_.get("actors") or [])
        for s_ in sd:
            assert frame(s_, {"du": {}}) is not None
        assert stage.poster_hero("Was wäre, wenn du ein Super-Tier aus vier Tierarten baust? – Herz vom Blauwal", sd, None, []) == "chimera", "Titelbild: das Misch-Wesen"
        for act_ in ("idle", "run", "down"):
            for mood_ in ("", "sad", "scared"):
                assert extras.creature("chimera", 0.7, 1, 0.0, mood_, 1.0, act_)[0].getbbox()
        other = stage.direct([{"text": "Dieses Monster wohnt unter deinem Bett.", "place": "bedroom", "actors": [{"id": "du"}]}], [(0, 4)], "Warum Kinder Angst vor Monstern haben", "fakten")
        assert "chimera" not in [str(a_.get("kind") or "") for a_ in other[0].get("actors") or []], "Misch-Wesen in fremdem Video"
        from .. import writer as _w
        js_ = {"title": "x", "description": "y", "hashtags": ["#fakte"], "tags": [], "scenes": [{"text": "Es sieht eine Maus aus mehrerenhundert Metern Höhe."}]}
        js_ = _w.polish(js_) or js_
        assert js_["hashtags"] == ["#fakten"] and "mehreren hundert" in js_["scenes"][0]["text"], js_
        js_ = {"title": "x", "description": "y", "hashtags": [], "tags": [], "scenes": [{"text": "In freier Wildbahn wurden neunzig und drei Kilometer pro Stunde gemessen."}]}
        js_ = _w.polish(js_) or js_
        assert "dreiundneunzig Kilometer" in js_["scenes"][0]["text"], js_
        sn = stage.direct([{"text": t_, "place": "lab", "actors": [{"id": "du"}]} for t_ in ("Du baust ein Super-Tier.", "Zutat eins sind die Beine vom Gepard.",
                                                                                              "In freier Wildbahn wurden dreiundneunzig Kilometer pro Stunde gemessen.", "Aber jede Superkraft hat ihren Preis.")],
                          [(i_ * 4, i_ * 4 + 4) for i_ in range(4)], "Was wäre, wenn du ein Super-Tier aus vier Tierarten baust?", "whatif")
        kn = [[str(a_.get("kind") or "") for a_ in s_.get("actors") or []] for s_ in sn]
        assert sn[2].get("shot") == "graphic" or kn[2] == ["cheetah"], f"Messwert gehört zum Gepard: {kn[2]}"
        assert "cheetah" not in kn[3], f"neuer Gedanke: nicht mehr der Gepard: {kn[3]}"
        sw = stage.direct([{"text": "Du baust ein Super-Tier.", "place": "lab", "actors": [{"id": "du"}]},
                           {"text": "Der Gepard hält seinen Sprint nur wenige hundert Meter durch.", "place": "savannah", "actors": [{"id": "du"}],
                            "overlay": {"type": "counter", "label": "", "value": 100, "unit": "METER"}}], [(0, 4), (4, 8)], "Was wäre, wenn du ein Super-Tier aus vier Tierarten baust?", "whatif")
        assert not sw[1].get("overlay"), f"Zähler aus „wenige hundert“: {sw[1].get('overlay')}"
        js_ = _w.polish({"title": "x", "description": "y", "hashtags": ["#baertierchen"], "tags": ["baertierchen"], "scenes": [{"text": "a."}]})
        assert js_["hashtags"] == ["#bärtierchen"] and js_["tags"] == ["bärtierchen"], js_
    check("Super-Tier aus vier Arten: Misch-Wesen im Bild (Prüfung 19.11., Video 152)", _hybrid)

    def _devices():                                              # Prüfung 19.11.2026 (Videos 156/157): sprechende Geräte, Bus-Innenraum, Verneinung, Kurve stürzt ab
        T = ["Deine Geräte packen heute aus.", "Morgens verkündet der Wecker laut, dass du neunmal auf Schlummern gedrückt hast.",
             "In der vollen Bahn liest dein Handy laut deine Bildschirmzeit vor.", "Es sind sieben Stunden, und alle Fahrgäste drehen sich um.",
             "Mittags in der Küche meldet der Kühlschrank den Zustand deiner Vorräte.", "Er sagt, dass der Joghurt seit drei Wochen abgelaufen ist.",
             "Abends schaltet sich im Wohnzimmer der Fernseher von alleine ein.", "Die Passanten starren fassungslos auf den Bildschirm.",
             "Er zählt laut auf, wer um drei Uhr nachts noch online war.", "Die Börsenkurse stürzen ab.",
             "Nach einer Woche leben wir wie im Mittelalter, nur ohne Burgen.", "Nur das alte Radio läuft noch, weil es keinen Chip besitzt.",
             "Und dein Router führt eine Liste aller verbundenen Geräte."]
        sc = [{"text": t_, "place": "livingroom", "time": "day", "props": [], "actors": [{"id": "du", "action": "walk", "pos": "offleft", "to": "center"}]} for t_ in T]
        sc[1].update(place="bedroom", props=[{"type": "clock"}])
        sc[2].update(place="station", crowd="walk")
        sc[3].update(place="station", crowd="walk", overlay={"type": "counter", "label": "STUNDEN", "value": 7, "unit": "HEUTE"})
        sc[4].update(place="kitchen", shot="insert", props=[{"type": "fridge"}, {"type": "cans"}])
        sc[5].update(place="kitchen")
        sc[6].update(props=[{"type": "tv"}])
        sc[8].update(place="hallway", props=[{"type": "clock"}])
        sc[9].update(shot="graphic", graphic={"type": "chart", "kicker": "DAX", "label": "PUNKTE", "dark": False}, actors=[])
        sc[10].update(place="village", props=[{"type": "lib_burg"}])
        sc[11].update(props=[{"type": "lib_mikrochip"}])
        sc[12].update(place="serverroom")
        sd = stage.direct(sc, [(i_ * 4, i_ * 4 + 4) for i_ in range(len(sc))], "Was wäre, wenn deine Geräte die Wahrheit sagen?", "whatif")
        keys = [[stage._pkey(q_) for q_ in s_.get("props") or []] for s_ in sd]
        kinds = [[str(a_.get("kind") or "") for a_ in s_.get("actors") or []] for s_ in sd]
        assert "clock" not in keys[1] and "lib_wecker" in keys[1], ("Wecker statt Wanduhr", keys[1])
        assert sd[2]["place"] == "transit" and sd[3]["place"] == "transit", ("Bahn-Innenraum statt Bahnsteig", sd[2]["place"], sd[3]["place"])
        assert sd[3].get("crowd") == "watch" and all(a_.get("action") != "walk" for s_ in sd[2:4] for a_ in s_.get("actors") or []), "in der Bahn läuft niemand"
        assert "HEUTE" not in str((sd[3].get("overlay") or {}).get("unit") or ""), "Zähler ohne Wort, das niemand sagt"
        assert "fridge" in kinds[4] and sd[4].get("shot") != "insert" and "fridge" not in keys[4], ("Kühlschrank als Figur", kinds[4], sd[4].get("shot"))
        assert "fridge" in kinds[5], ("„Er sagt …“ bleibt beim Kühlschrank", kinds[5])
        assert "tv" in keys[6], ("Fernseher im Wohnzimmer ist zu sehen", keys[6])
        assert "barrel" not in keys[7], "fassungslos ist kein Fass"
        assert "clock" not in keys[8], ("Uhrzeit ist keine Wanduhr", keys[8])
        assert sd[9].get("shot") != "graphic" or (sd[9]["graphic"].get("dark") and sd[9]["graphic"].get("kicker") != "DAX"), "Kurve stürzt ab, kein DAX"
        assert "lib_burg" not in keys[10], ("ohne Burgen: keine Burg", keys[10])
        assert "lib_mikrochip" not in keys[11], ("keinen Chip: kein Chip", keys[11])
        assert places.resolve(sd[12]["place"]) != "serverroom", "Router zu Hause steht nicht im Rechenzentrum"
        assert stage.denied(r"burg", "nur ohne burgen") and stage.denied(r"chip", "weil er keinen chip besitzt") and not stage.denied(r"chip", "ein chip, aber kein chip aus gold")
        assert "tv" in stage._prepare({"place": "livingroom", "props": [{"type": "tv"}], "actors": [{"id": "du"}]}, {"du": {}})[4][0][0], "Fernseher wird gezeichnet"
        frame({"place": "transit", "crowd": "watch", "actors": [{"id": "du", "hold": "phone"}]})
        frame({"place": "transit", "time": "night", "actors": [{"id": "du"}]})
        assert stage._hint("Nach zwei Sekunden liest es deinen Suchverlauf laut im Bus vor.") == "transit" and stage._hint("Der Bus fährt los.") != "transit"
        from .. import writer as wr_
        js_ = wr_.polish({"title": "T", "hashtags": ["#fy", "#geraete"], "tags": ["kuehlschrank"], "scenes": [{"text": "Warum du jeden Abend hineinschaußt."}, {"text": "Es war nämlich nur du."}]})
        assert "hineinschaust" in js_["scenes"][0]["text"], js_["scenes"][0]["text"]
        assert js_["scenes"][1]["text"] == "Es warst nämlich nur du." and js_["hashtags"] == ["#fyp", "#geräte"] and js_["tags"] == ["kühlschrank"], (js_["scenes"][1], js_["hashtags"], js_["tags"])
        sd2 = stage.direct([{"text": "Das ist der Anfang.", "place": "livingroom", "actors": [{"id": "du"}]},
                            {"text": "Plötzlich drehen sich alle Fahrgäste um und mustern dich mit großen Augen.", "place": "transit", "crowd": "worried", "props": [{"type": "lib_auge"}], "actors": [{"id": "du", "action": "cower"}]},
                            {"text": "Auf dem Weg zum Bäcker sagt das Navi im Auto, dass du auch zu Fuß gehen kannst.", "place": "street", "props": [{"type": "car"}], "actors": [{"id": "du", "action": "sit"}]},
                            {"text": "Ende.", "place": "livingroom", "actors": [{"id": "du"}]}], [(i_ * 4, i_ * 4 + 4) for i_ in range(4)], "Geräte sagen die Wahrheit", "whatif")
        assert "lib_auge" not in [stage._pkey(q_) for q_ in sd2[1].get("props") or []], "kein einzelnes Auge in der Bahn"
        assert all(a_.get("action") != "sit" for a_ in sd2[2].get("actors") or []), "niemand sitzt auf dem Gehweg vor dem Auto"
    check("Sprechende Geräte, Bus-Innenraum, Verneinung, fallende Kurve (Prüfung 19.11., Videos 156/157)", _devices)
    def _cute():                                                 # Prüfung 19.11.2026 (Plan „Tödlich niedlich“): Pfeilgiftfrosch, Schnabeltier, Kugelfisch als Wesen; Koch mit Mütze
        T = ["Drei Tiere, die niedlich aussehen.", "Nummer eins: Der Pfeilgiftfrosch ist knallgelb.", "Sein Hautgift reicht für zehn Menschen.",
             "Schon eine Berührung ist gefährlich.", "Nummer zwei: das Schnabeltier.", "Männchen tragen am Hinterbein einen Giftsporn.",
             "Das Gift tötet dich zwar nicht, verursacht aber extreme Schmerzen.", "Nummer drei: der Kugelfisch.", "Bei Gefahr bläst er sich zur Stachelkugel auf.",
             "Nur ausgebildete Köche dürfen den Kugelfisch zubereiten.", "Ich habe einen Frosch im Hals."]
        sc = [{"text": t_, "place": "livingroom", "time": "day", "props": [], "actors": [{"id": "du", "action": "walk", "pos": "offleft", "to": "center"}]} for t_ in T]
        sc[1].update(place="forest", actors=[], props=["pfeilgiftfrosch"], shot="insert")
        sc[4].update(place="river", actors=[{"id": "pete", "kind": "cat"}])
        sc[7].update(place="underwater", actors=[], props=["kugelfisch"], shot="event")
        sd = stage.direct(sc, [(i_ * 4, i_ * 4 + 4) for i_ in range(len(sc))], "Tiere, die niedlich aussehen, aber gefährlich sind", "tiere")
        kinds = [[str(a_.get("kind") or "") for a_ in s_.get("actors") or []] for s_ in sd]
        acts = [[str(a_.get("action") or "") for a_ in s_.get("actors") or []] for s_ in sd]
        assert kinds[1] == ["frog"] and sd[1].get("shot") != "insert" and not sd[1].get("props"), ("Pfeilgiftfrosch als Wesen", kinds[1], sd[1].get("shot"))
        assert kinds[2] == ["frog"], ("„Sein Hautgift …“ bleibt beim Frosch", kinds[2])
        assert kinds[3] == ["", "frog"] and acts[3][0] == "cower", ("Berührung: Mensch weicht vor dem Frosch zurück", kinds[3], acts[3])
        assert kinds[4] == ["platypus"] and kinds[5] == ["platypus"] and acts[5] == ["spur"], ("Schnabeltier zeigt den Sporn", kinds[4], kinds[5], acts[5])
        assert "platypus" not in kinds[6], ("Satz über den Menschen: kein Schnabeltier", kinds[6])
        assert kinds[7] == ["puffer"] and acts[7] == ["idle"] and places.resolve(sd[7]["place"]) == "underwater", ("Kugelfisch unter Wasser", kinds[7], acts[7])
        assert kinds[8] == ["puffer"] and acts[8] == ["puff"], ("Kugelfisch bläst sich auf", kinds[8], acts[8])
        assert kinds[9] == [""] and (sd[9]["actors"][0].get("look") or {}).get("hat") == "chef" and places.resolve(sd[9]["place"]) == "kitchen", ("Koch mit Mütze in der Küche", sd[9]["actors"])
        assert "frog" not in kinds[10], "Frosch im Hals ist kein Frosch"
        sd3 = stage.direct([{"text": "Drei süße Tiere, die giftig sind.", "place": "river", "actors": [{"id": "du"}]},
                            {"text": "Nummer eins, der Pfeilgiftfrosch, ist knallgelb.", "place": "forest", "actors": [{"id": "du"}]},
                            {"text": "Er passt problemlos auf deine Handfläche.", "place": "forest", "shot": "close", "actors": [{"id": "du"}]},
                            {"text": "Das Gift eines einzigen Froschs würde für rund zehn Menschen reichen.", "place": "forest", "shot": "graphic", "graphic": {"type": "number", "value": "10", "label": "MENSCHEN"}},
                            {"text": "Es sitzt direkt in seiner Haut, und die grelle Farbe warnt alle Fressfeinde.", "place": "forest", "actors": [{"id": "du", "action": "talk"}]},
                            {"text": "Nummer zwei ist das Schnabeltier.", "place": "river", "actors": [{"id": "du"}]},
                            {"text": "Welches der drei hättest du gestreichelt?", "place": "river", "actors": [{"id": "du"}], "overlay": {"type": "choice", "a": "Frosch", "b": "Schnabeltier"}}],
                           [(i_ * 4, i_ * 4 + 4) for i_ in range(7)], "Drei niedliche Tiere, die du besser nie anfasst", "tiere")
        k3 = [[str(a_.get("kind") or "") for a_ in s_.get("actors") or []] for s_ in sd3]
        assert k3[0] == ["frog", "platypus"], ("erstes Bild zeigt die Tiere", k3[0])
        assert k3[2] == ["frog"] and sd3[2].get("shot") != "close", ("Handfläche: der Frosch bleibt im Bild", k3[2])
        assert k3[4] == ["frog"], ("nach der Zahl-Grafik bleibt „Es sitzt in seiner Haut“ beim Frosch", k3[4])
        assert not sd3[6].get("overlay"), "Auswahl mit zwei Antworten zur Frage nach den dreien entfällt"
        frame(sd3[0])
        sd4 = stage.direct([{"text": "Drei Tiere sind giftig.", "place": "park", "actors": [{"id": "du"}]},
                            {"text": "Und das Gift der Nummer drei schlägt jedes Zyankali.", "place": "underwater", "actors": [{"id": "fisch", "kind": "fish"}]},
                            {"text": "Nummer drei ist der Kugelfisch.", "place": "underwater", "actors": []},
                            {"text": "Ende.", "place": "park", "actors": [{"id": "du"}]}], [(i_ * 4, i_ * 4 + 4) for i_ in range(4)], "Drei niedliche Tiere", "tiere")
        assert [str(a_.get("kind") or "") for a_ in sd4[1].get("actors") or []] == ["puffer"], "Goldfisch der Text-KI wird im Kugelfisch-Video zum Kugelfisch"
        assert stage.poster_hero("Süß, aber giftig – das Schnabeltier aus Australien", sd) != "alien", "Australien ist kein Alien (Titelbild von Video 163 zeigte einen Außerirdischen)"
        assert stage.poster_hero("Aliens landen auf der Erde", []) == "alien"
        for k_, a_ in (("frog", ""), ("frog", "hop"), ("platypus", ""), ("platypus", "spur"), ("puffer", ""), ("puffer", "puff")):
            for f_ in (1, -1):
                assert extras.creature(k_, 1.3, facing=f_, action=a_)[0].getbbox(), (k_, a_)
        for i_ in (1, 3, 5, 8, 9):
            frame(sd[i_])
        frame({"place": "kitchen", "actors": [{"id": "k", "look": {"hat": "chef", "shirt": "weiß"}}]})
    check("Niedliche Gifttiere: Pfeilgiftfrosch, Schnabeltier, Kugelfisch; Koch mit Mütze (Prüfung 19.11., Plan 21 Uhr)", _cute)

    def _funeral():                                              # Prüfung 20.11.2026 (Plan „Unpassend lachen“): Kirche von innen, Trauerkleidung, Staubsauger
        T = [("Ich stand auf einer Beerdigung und musste plötzlich lachen.", "graveyard", [{"id": "du", "action": "jump"}], [], "sad"),
             ("Alles begann, als mein Staubsauger mit einem lauten Knall explodierte.", "livingroom", [{"id": "du", "action": "shocked"}], ["staubsauger", "smoke"], ""),
             ("In der Kirche war es so leise, dass man Stecknadeln hören konnte.", "church", [{"id": "du", "action": "freeze"}], ["car"], "walk"),
             ("Oma weinte leise und alle blickten betroffen auf den Boden.", "church", [{"id": "oma", "action": "sad"}], [], ""),
             ("Vor der Kirche atmete ich tief durch.", "church", [{"id": "du", "action": "pant"}], [], ""),
             ("In der Kirche dachte ich nur an den Staubsauger.", "church", [{"id": "du", "action": "think"}], ["staubsauger"], "")]
        sf = stage.direct([{"text": t_, "place": pl_, "actors": a_, "props": pr_, "crowd": cr_} for t_, pl_, a_, pr_, cr_ in T],
                          [(i_ * 4, i_ * 4 + 4) for i_ in range(len(T))], "Warum wir in unpassenden Situationen lachen", "comedy")
        kn = lambda i_: [str(q.get("type") if isinstance(q, dict) else q) for q in sf[i_].get("props") or []]
        assert sf[0].get("_mourn") and sf[0].get("crowd") == "sad" and stage.crowd_ok(sf[0]), "Trauergäste am Grab"
        assert "vacuum_broken" in kn(1) and "smoke" not in kn(1), f"kaputter Staubsauger im Bild: {kn(1)}"
        assert sf[2]["place"] == "chapel" and sf[2].get("crowd") == "sad" and "car" not in kn(2), f"in der Kirche: Kirchenraum, Trauergäste, kein Auto: {sf[2]['place']} {sf[2].get('crowd')} {kn(2)}"
        assert sf[3]["place"] == "chapel" and sf[3].get("_mourn"), "Folgesatz bleibt im Kirchenraum"
        assert sf[4]["place"] == "church", "vor der Kirche bleibt draußen"
        assert sf[5]["place"] == "chapel" and not kn(5), f"an den Staubsauger denken stellt ihn nicht in die Kirche: {kn(5)}"
        assert places.resolve("kapelle") == "chapel" and stage._prepare({"place": "chapel", "_mourn": True, "actors": [{"id": "oma"}]}, {"oma": {"shirt": "lila", "hat": "beanie"}})[3][0]["look"].hat == ""
        no = stage.direct([{"text": "In der Kirche heiraten zwei.", "place": "church", "actors": [{"id": "du"}]}], [(0, 4)], "Hochzeit", "fakten")
        assert no[0]["place"] == "church" and not no[0].get("_mourn"), "ohne Beerdigung greift die Regel nicht"
        co = [{"text": "Ich stand auf einer Beerdigung und musste lachen.", "place": "graveyard", "actors": [{"id": "du", "action": "talk"}]},
              {"text": "Zwei.", "place": "livingroom", "actors": [{"id": "du"}]},
              {"text": "Ich rannte los.", "place": "livingroom", "props": ["fire"], "weather": "storm", "actors": [{"id": "du", "action": "run"}]}] + [
              {"text": "Und weiter.", "place": "livingroom", "actors": [{"id": "du"}]} for _ in range(3)]
        stage._cold_open(co)
        assert co[0]["place"] == "graveyard" and not co[0].get("_cold_open"), "der erste Satz nennt seinen Ort: kein Vorgriff aufs Wohnzimmer (Video 167)"
        for sc_ in sf:
            frame(sc_, {"du": {"shirt": "schwarz"}, "oma": {"hat": "beanie"}})
        frame({"place": "chapel", "time": "night", "actors": [{"id": "du"}]})
        for k_ in ("vacuum", "vacuum_broken"):
            for t_ in (0.1, 0.6, 2.4):
                frame({"place": "livingroom", "props": [k_], "actors": [{"id": "du"}]}, None, t_)
    check("Beerdigung: Kirchenraum, Trauerkleidung, Staubsauger (Prüfung 20.11., Plan 18 Uhr)", _funeral)
    print(f"{count[0]} Prüfungen, {len(errors)} Fehler")
    import collections
    for line, n in collections.Counter(e.strip().splitlines()[-1] + "  @ " + e.strip().splitlines()[-3].strip()[:90] for e in errors).most_common(30):
        print(f"{n:4d}× {line}")
    for e in errors[:6]:
        print("-" * 60 + "\n" + e)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
