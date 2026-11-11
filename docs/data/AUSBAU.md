# Ausbau der AutoShorts-Engine (Anleitung für die nächtliche Ausbau-Sitzung)

Die Engine zeichnet alle Videos selbst (`engine/toon/`). Was einem Video gefehlt hat, steht in `docs/data/wishes.json`
(`{"wort": {"n": Anzahl, "last": "Videotitel", "done": true|fehlt}}`). Vorläufige, automatisch von der Text-KI gezeichnete
Gegenstände stehen in `docs/data/shapes.json` mit `"auto": true`.

## Zuerst: was das nächste Video braucht
`docs/data/plans.json` enthält die vorbereiteten Videos der nächsten Termine (`{"2026-11-11 18:00": {"topic", "title", "script", "needs": [...]}}`).
Alles in `needs` MUSS vor dem Termin gebaut sein – sonst wird das Video nicht hochgeladen. Diese Wörter haben Vorrang vor der
übrigen Wunschliste. Lies dazu das Drehbuch im Plan (`script.scenes[].text`), damit das Gebaute zu den Sätzen passt, und sorge
dafür, dass es auch erscheint: Bibliotheks-Gegenstände erscheinen automatisch, wenn ihr Name oder ein Alias im Satz vorkommt;
für Code-Requisiten einen Eintrag in `TEXT_PROPS` (engine/toon/stage.py) ergänzen. Prüfe am Ende mit
`python3 -c "from engine import main; print([w for w in NEEDS if not main.known_thing(w)])"`, dass nichts mehr fehlt.

## Stil seit dem Umbau vom 11.11.2026 (bitte einhalten)
- Figuren (`rig.py`): großer Kopf mit Frisur, Augenbrauen, Wangenrot; Kapuzenpulli mit Schattenkante, Jeans, Turnschuhe. Jede Farbfläche
  hat eine dunklere Schattenseite (`_dark`) – neue Kleidung/Kopfbedeckungen genauso zeichnen.
- Hintergründe (`places.py`): weiche Bausteine `grad` (Verlauf), `veil`/`fade` (Licht, Schatten, Dunst), `blobs` (Kronen/Büsche als eine
  Form mit Licht und Schatten), `cloud`, `window(…, curtain=…)`, `rug`, `books`, `floor_lamp`, `plant`. Jeder Ort endet mit `p.vignette()`
  – das legt Fensterlicht, Dunst, leichte Weichzeichnung und Körnung darüber. Kein kahler Raum: mindestens Fenster oder Bild, ein Möbel,
  eine Pflanze oder ein Teppich.
- Bewegung (`stage.py`): Kamera (`_camera`) mit Ruck beim Schnitt und Sprung auf das Schlüsselwort (`highlight`), Dinge springen ins Bild,
  Figuren federn. Neue Requisiten brauchen dafür nichts Besonderes.
- Requisiten (`extras.py`): Grundformen `_o` (Ellipse) und `_r` (abgerundetes Rechteck) zeichnen automatisch Umriss, Schattenseite unten
  rechts und Glanz; für freie Flächen `_poly`, für Kronen/Wolken/Büsche `_blobs`. Neue Requisiten mit diesen Bausteinen zeichnen, nicht mit
  nackten `d.ellipse`/`d.polygon`-Flächen.
- Tiere/Wesen (`extras.creature`): nach rechts blickend in Wesen-Koordinaten zeichnen (Helfer `ell`, `rr`, `poly`, `stroke`, `eye`, `brow`,
  `cheek`, `mouthf`), gespiegelt wird automatisch. Augen wie bei den Figuren (`rig._eye`), Wangenrot, Kopf immer mit Hals/Körper verbunden.
- Bildgestaltung wie in den Vorbild-Shorts: Halbnahe statt Totale (`_camera` mit `tight`, Zoom passt sich an die Breite von
  Gruppe und Requisiten an, nichts wird angeschnitten); Licht (`stage._light`): bei unheimlich/angespannt/traurig und nachts drinnen
  Halbdunkel mit Lichtkegel auf den Figuren, nachts draußen dunkelblau mit warmen Fenstern und Lichtfleck um die Figuren, sonst läuft der
  Boden unten weich ins Dunkle. Großaufnahme (`shot: close`, automatisch bei starkem Gefühl): Figur 2,6-fach groß und scharf vor
  unscharfer Kulisse. Beschriftungs-Schild `{"type": "tag", "text": "AUGUST 1914"}`; Datum/Jahr/Anlass im Satz setzt es automatisch.
- Bild passt zum Satz (Vorrang vor allem anderen): Nennt der Satz einen Ort („in deinen Garten“, „im Keller“, „im Kino“), gilt er
  (`stage._said_place`) – auch gegen das Drehbuch. Ergibt der Titel einen Schauplatz (Hollywood → `cinema`), spielen ortlose
  Wohnzimmer-Szenen dort (`TOPIC_PLACES`). Das Ding des Themas steht auch drinnen jede zweite Szene und immer, wenn der Satz es nennt.
  Kleines (Spinne, Chip, Schuh) wird nie kleiner als `MIN_PROP_PX` gezeichnet. Neue Orte: `cinema` (Kinosaal), `restaurant` mit Essen.
- Himmels-Dinge (Sonne, Mond, Wolken) rücken in der Regie selbst an eine Stelle mit freiem Himmel (`stage._open_sky_x`) – nicht hinter Bäume.
- Grafik-Einschübe (`number`, `question`, `badge`, `round`, `versus`, `score`, `compare`, `share`, `timer`, `calendar`) rendert
  HyperFrames als HTML/GSAP-Animation (`engine/hyper.py`); fehlt HyperFrames oder scheitert es, zeichnet `graphics.py` sie wie bisher.
  Neue Grafik-Arten zuerst in `graphics.py` (Rückfall), dann optional in `hyper.BUILD`. Abschalten: `AS_HYPER=0`.

## Was zu tun ist
1. Offene Wünsche (ohne `"done": true`) und `"auto": true`-Einträge durchgehen, höchstens 8 pro Sitzung, häufigste zuerst.
2. Einzelne Gegenstände: sauber als Eintrag in `docs/data/shapes.json` zeichnen (Format siehe Kopf von `engine/toon/library.py`:
   Zeichenfläche 400×400, Boden bei y=400, 8–30 Formen, echte Höhe in Metern, sinnvolle `aliases` inkl. Mehrzahl) und `"auto"` entfernen.
   Stil: flach, klare Flächen, gedeckte Farben, passend zu den eingebauten Requisiten in `engine/toon/extras.py`.
3. Was kein einzelner Gegenstand ist (Ort, Landschafts-Baustein, Tier, Bewegung, Wetter, Einblendung): im Code ergänzen
   (`places.py`, `extras.py`, `rig.py`, `stage.py`, `overlays.py`) und in der Drehbuch-Anleitung `engine/writer.py` (Abschnitt TOON) eintragen,
   dazu passende Text-Hinweise in `stage.py` (`HINTS`, `TEXT_PROPS`).
4. Jedes neue Teil ansehen: Bild rendern (z. B. mit `engine.toon.selftest.frame(...)` oder `python -m engine.main learn` ist NICHT nötig)
   und mit eigenen Augen prüfen – Größenverhältnis zu den Figuren, Lesbarkeit, Stil.
5. `FONTS_DIR=/usr/share/fonts/truetype/google-fonts python3 -m engine.toon.selftest` muss mit 0 Fehlern enden.
6. Erledigte Wünsche in `wishes.json` mit `"done": true` markieren. Committen (`Engine-Ausbau: …`), `git pull --rebase`, auf `main` pushen.

## Grenzen
- Keine echten Personen, Marken, Logos oder geschützten Figuren zeichnen.
- Nichts an Zugangsdaten, `tokens/`, Upload-Code, Workflow-Zeitplan oder App-Einstellungen ändern. Keine Videos hochladen.
- Die App (`quellcode/`, `AutoShorts.cmd`) nur anfassen, wenn ein Ausbau ohne das nicht funktioniert.
- Schlägt der Selbsttest fehl und lässt sich das nicht beheben: nichts pushen, sondern berichten.
