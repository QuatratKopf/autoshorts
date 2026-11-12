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
    for w in ("rain", "storm", "snow", "wind", "ash", "quake", "heat", "dark", "steam", "unbekannt"):
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
          {"type": "news"}, {"type": "pulse", "value": "1", "label": "Eine Sekunde"}, {"type": "pulse", "value": "x" * 30}, {"type": "radio", "kicker": "Funk · Kanal 4", "text": "Bergwacht"},
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
    def _hook():                                                 # Einstieg: schwache Anfänge erkannt, erstes Bild mit Reaktion und Ruck
        from .. import writer
        assert writer.hook_weak({"title": "Was passiert ohne Schwerkraft?", "scenes": [{"text": "Was wäre, wenn die Schwerkraft verschwindet?"}]})
        assert not writer.hook_weak({"title": "KI-Agenten", "scenes": [{"text": "Mein Laptop hat gerade gekündigt."}]})
        scs = stage.direct([{"text": "Dein Auto fliegt gleich davon.", "place": "street", "actors": [{"id": "du"}]},
                            {"text": "Weiter.", "place": "street"}, {"text": "Schluss.", "place": "street"}], [(0, 3), (3, 6), (6, 9)], "Test")
        assert scs[0]["actors"][0]["emotion"], scs[0]["actors"]
        fr = frame(scs[0], t=0.1)
        for t in (0.0, 0.2, 0.49, 0.6):
            assert stage._camera(fr.convert("RGB"), t, 3.0, {"opener": True}).size == (1080, 1920)
    check("Einstieg", _hook)
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
