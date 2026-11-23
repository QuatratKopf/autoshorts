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
- Frauenfiguren (`rig.py`): Frisuren long, bob (fließend mit runden Spitzen und Strähnen am Gesicht), ponytail, curly, bun; `fem`
  (automatisch bei diesen Frisuren oder `gender: "w"`) gibt Wimpern, feinere Brauen, Lippenfarbe und einen eigenen Seitenscheitel-Pony.
  `stage.balance_cast`: „du“ ist in jedem zweiten Video eine Frau (benannte Figuren und „ich“ bleiben); GROUP_LOOKS sind gemischt.
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
  Kleines (Spinne, Chip, Schuh) wird nie kleiner als `MIN_PROP_PX` gezeichnet. Ohne Einblendung im Drehbuch erklärt
  `stage._auto_explain` den Satz selbst: Aufzählung → Liste/„SPEISEKARTE“, Temperatur → `thermo`, Prozent mit Bezug → `bar`,
  Signalwort → `stamp` (Liste `STAMPS`, verneinte Wörter zählen nicht). Experten-Aussage („Forscher warnen, dass …“) →
  `quote` (nur die Rolle, nie ein Name). `_time_weather`: „nachts“, „um Mitternacht“ → Nacht; Regen, Schnee, Sturm, Wind, Hitze → Wetter
  (nur draußen, verneint zählt nicht). Nennt der Titel ein Tier/Wesen aus `TOPIC_CREATURES`
  (Spinne, Katze, Hund, Biene, Hai, Roboter …), ist es die Hauptfigur: groß (`HERO_SIZE`), mit Gefühl, in fast jeder Szene (`_topic_creature`).
  Abstrakte Begriffe als Figur: `agent` (KI, Bot, Assistent), `virus` (Virus, Bakterie, Erreger), `cell` (Zelle, Immunsystem). Mehrzahl ohne
  Menschen („Die Agenten arbeiten …“) → Gruppe aus drei. Schnitt mitten im Satz (`_cut_plan`, ab `CUT_MIN` s): beim Schlüsselwort hart auf
  das genannte Ding groß oder die Großaufnahme der Figur – jede dritte Szene bleibt ruhig. Neue Orte: `cinema` (Kinosaal), `restaurant` mit Essen.
- Meerestiere und Winzlinge (`extras.creature`: `shrimp` Pistolenkrebs mit Knallschere, `mantis` Fangschreckenkrebs mit Keulenschlag, `jelly` Qualle,
  `axolotl`, `tardigrade` Bärtierchen; Requisite `aquarium` mit Goldfisch): Nennt der Satz das Tier (`stage.SEA_CREATURES`, `ANY_CREATURES`), ist es
  groß und allein die Figur der Szene – Meerestiere unter Wasser, das Bärtierchen an dem Ort, von dem der Satz spricht. Folgesätze bleiben beim Tier
  (höchstens drei, bis ein Satz von Menschen handelt – `HUMAN_RE`), Ankündigungen („Nummer drei“) zeigen schon das nächste. Unter Wasser stehen nur
  Dinge, auf die das Tier zielt (`SEA_TARGETS`); kein Mensch, keine Explosion, keine Symbole. Neue Tiere dieser Art: zeichnen, in die Liste eintragen,
  Größe in `HERO_SIZE`/`CREATURE_SIZE`, Breite in `LONG_KINDS`, Fall im Selbsttest (`_sea`) ergänzen.
- Mimik und Gesten (`stage.lips`, `stage._mouth`, `stage.gesture_plan`, `rig.GESTURES`): Die Figur bewegt die Lippen nur, wenn sie selbst
  spricht (Ich-/Wir-Satz oder wörtliche Rede) – erzählt die Stimme über sie („Du wachst auf …“), hört sie mit geschlossenem Mund zu.
  Beim Sprechen öffnet jede Silbe den Mund in der Form ihres Vokals (a offen, o/u rund, e/i breit), in Pausen ist er zu. Gesten kommen aus
  den Wörtern: Frage → Schultern hoch, nie/kein → Kopfschütteln, riesig/Millionen → Arme weit, plötzlich/gefährlich → Hände an den Kopf,
  vielleicht/warum → Hand ans Kinn, leider → traurig, toll/endlich → Freude, ja/genau → Nicken, ich/du nur beim Selbst-Sprechen;
  dazwischen mindestens `GAP` Sekunden ruhige Grundhaltung. Neue Gesten: Eintrag in `rig.GESTURES` und Wörter in `stage.CUES`.
- Bewegung und Schnitt: Jede Szene hat eine echte Kamerafahrt (`_camera`, `move`: push, pull, pan_l, pan_r im Wechsel). Übergänge sind
  meist harte Schnitte (`render.TOON_TRANSITIONS`, „cut“), dazwischen ein Wisch – keine Unschärfe-Blende. Ruhige Szenen ohne Schnitt
  höchstens `CALM_MAX` Sekunden; geht kein Insert oder keine Großaufnahme, schneidet `_cut_plan` auf den Gegenschnitt („flip“: gespiegelt,
  näher, andere Fahrt). Großaufnahmen nur bei einer Figur; bei Tieren zielt sie auf den Kopf. `_vary_repeats`: gleiches Bild wie die
  Szene davor → Wesen bewegt sich durchs Bild, Seiten gespiegelt oder Großaufnahme. Wesen ohne Bewegung treiben sanft hin und her.
- Himmels-Dinge (Sonne, Mond, Wolken) rücken in der Regie selbst an eine Stelle mit freiem Himmel (`stage._open_sky_x`) – nicht hinter Bäume.
- Grafik-Einschübe (`number`, `question`, `badge`, `round`, `versus`, `score`, `compare`, `share`, `timer`, `calendar`) rendert
  HyperFrames als HTML/GSAP-Animation (`engine/hyper.py`); fehlt HyperFrames oder scheitert es, zeichnet `graphics.py` sie wie bisher.
  Neue Grafik-Arten zuerst in `graphics.py` (Rückfall), dann optional in `hyper.BUILD`. Abschalten: `AS_HYPER=0`.

- Bibliothek: englische „falsche Freunde“ (`library.FALSE_FRIENDS`: bug, gift, rock …) sind nie Alias; für Begriffe in `main.NO_THINGS`
  (Bug, Glitch, Regel …) wird nichts gelernt. Aufzählungen prüft `writer.list_trouble` (nie mehr Punkte als angekündigt, höchstens fünf).
  Nummern-Schilder und Stempel bleiben nur am Satz, der Nummer bzw. Wort nennt; `stage._carry_thing` lässt das zuvor genannte Ding im
  Folgesatz stehen („diese Früchte … eine Tonne“), bei großer Zahl dreifach.

- Handlung mit einem kleinen Ding (`stage.GIVE_RE`, `TAKE_RE`): „teilt sein Stück Kuchen“, „schenkt“, „isst einen Apfel“ → eine Figur hält das genannte
  Ding vor sich (beim Geben die zweite Figur, sonst die Hauptfigur) statt es nur auf den Boden zu stellen; Kleines in der Hand ist mindestens 84 px groß.
  Einsatzfahrzeuge: `ambulance` (Rettungswagen; Einsatzkräfte, Notruf, Sanitäter) und `police` (Streifenwagen) – ersetzen das beliebige rote Auto.
  Konfetti gibt es nur noch, wenn gefeiert wird (`PARTY_RE`) oder eine Menge jubelt, nicht in jeder fröhlichen Szene. Schilder (`tag`) mit einer Zahl,
  die der Satz nicht nennt, entfallen (Jahreszahlen bleiben). Die Handy-Einblendung zeigt höchstens drei Nachrichten in großer Schrift, ohne Emojis.

- Nie zweimal hintereinander dieselbe Karte/Weltkugel (die zweite Szene spielt mit der Hauptfigur im Zimmer) und nie zweimal hintereinander dieselbe
  Grafik-Art (zwei Zahlen-Tafeln); Zahl-Grafik „3 PRO KETTE“ behält nur die Zahl. Schilder (`tag`) bis 30 Zeichen in kleinerer Schrift; gekürzte
  Einblendungen enden nie auf Artikel oder Verhältniswort (`overlays._DANGLING`).

- Tiefsee-Technik (Flugzeug-Suche, Wracks): `places.underwater(night=True)` zeichnet die dunkle Tiefsee (`_deepsea`: Schlick, Felsrücken, Schlot,
  Meeresschnee). Requisiten `submersible` (Forschungs-Tauchboot mit Scheinwerfer und Sonar-Ringen; Wörter Sonar, Tauchboot, Tauchroboter, U-Boot –
  `stage.SUB_RE`) und `ping` (Signal-Ringe über einem Sender, setzt nur die Regie); Bibliothek: `blackbox` (orange, wie echte Flugschreiber), `wrack`.
  Regie: Nennt der Satz Meeresboden/Tiefsee/„Metern Tiefe“ (`DEEP_RE`) oder gibt das Drehbuch `underwater` an, spielt die Szene unter Wasser – auch
  gegen eine Baukasten-Landschaft mit Meeresoberfläche. Mit Blackbox, Wrack oder Tauchboot im Satz (`DEEP_THING_RE`) wird es die Tiefsee: nur die
  Technik im Bild (Boot links, Wrack/Blackbox rechts am Grund, beim Wrack leuchtet ein Tauchboot), kein Flugzeug, kein Mensch, kein Fisch, keine
  Zahlen-Tafel. Tauchboot und Sonar erscheinen nur unter Wasser (Fledermaus-„Sonar“ im Wald bleibt ohne Boot). Selbsttest: `_deep`.

- Meeresoberfläche (`stage.SURFACE_RE`, `DEBRIS_RE`, Schlussdurchgang in `direct`): „auf dem Ozean“, „über dem Meer“, treibende Trümmerteile spielen auf dem
  Meer mit Himmel (Baukasten `ground: water`) – nicht am Meeresgrund, nicht am Palmenstrand. Dort steht kein Mensch und kein Karton auf dem Wasser:
  Es treibt die Requisite `debris` (Rumpfstück, Sitzkissen, Koffer), sonst fährt ein Schiff. Steht nur ein Flugzeug/Satellit am Himmel, rückt die
  Einblendung tiefer ins freie Bild (`_ov_low`, `render.scene_clip`). Satelliten-Sätze spielen im All (Satellit vor der Erde); eine Europakarte ohne
  Land im Satz (`GEO_RE`) entfällt. Grafik `radar` (Radarschirm, mit `"sub": "lost"` erlischt der Leuchtpunkt) – ab dem zweiten Satz automatisch bei
  „Radar“, „Funkkontakt“, „Transponder“. Bibliothek: `muschel`. Selbsttest: `_surface`.

- Telefonat (`stage._call_story`, greift, wenn das Thema vom Telefonieren handelt und zwei Sätze, sonst wenn drei Sätze `CALL_RE` treffen –
  Anruf, Telefon, „rufst … an“, auflegen, Freizeichen): Wer telefoniert, hält das Handy ans Ohr (Hand-Gegenstand `call`, Armhaltung
  `stage.CALL_ARM`) und bleibt allein zu Hause – keine Stadtstraße, kein Rechenzentrum, niemand kommt zur Tür herein. Der Angerufene
  („Er geht ran“, „bei ihm“, „sein Mikrofon“) ist allein in seinem eigenen Zimmer, nie im selben Raum. Nach dem Auflegen (`CALL_END_RE`) hält
  die Figur das Handy vor sich; ein neuer Anruf beginnt erst wieder mit `CALL_START_RE`. Technik-Sätze über Echo, Leitung, Lautsprecher,
  Mikrofon, Signal (`CALL_TECH_RE`) zeigen das Schaubild `echo` (`graphics._g_echo`: zwei Handys, die Stimme läuft oben hinüber und kommt unten
  blasser zurück; `"sub": "filter"` – eine Sperre hält das Echo auf, automatisch bei „unterdrückt/filtert/verschwindet“) im Wechsel mit dem
  Handy des Angerufenen auf laut. Sätze über Schädelknochen bzw. „so hören dich andere“ zeigen das Schaubild `voice` (`graphics._g_voice`: Kopf,
  Schall außen durch die Luft und innen durch den Knochen; `"sub": "air"` nur der Luftweg). „Kopfhörer“ beim Freund: er trägt sie – und nur dort (`_no_headphones` nimmt sie ihm in allen anderen Szenen ab, auch wenn die
  Besetzung sie als Kopfbedeckung vorgibt). Klang-Sätze (Tonhöhen, blechern) sind keine Echo-Sätze; eine Karte mit einem langen Wort wird kleiner
  gesetzt (`overlays.card`); `writer.hook_drops` behält Satz 2, wenn Satz 3 mit „Doch/Dann/Plötzlich“ an ihn anknüpft. Eine Ecken-Zeile mit vorangestellter Uhrzeit, die niemand sagt
  („23:42 UHR · ANRUF LÄUFT“), entfällt samt Zustand (`render.build_ass`). Selbsttest: `_call`.

- Raumsonde (`stage._probe_story`, greift bei `PROBE_RE` – Raumsonde, Weltraumsonde, Voyager – in Thema oder Sätzen): gezeichnete Sonde
  (`extras._probe`: Schüssel, Gerätekasten in Goldfolie, Ausleger, Gittermast; kein Schriftzug) als `probe` (groß), `probe_far` (klein, die Sonne
  nur noch ein Stern), `probe_signal` (funkt), `probe_uplink` (Befehl von der Erde, die Erde als blauer Punkt), `probe_glitch` (zerhackte rote
  Wellen, Datenmüll). Jeder Satz, der im All spielt und keine Figur hat, zeigt die zum Satz passende Fassung vor `places.space_deep` (Sterne und
  Nebel, kein Mondboden) – nie zweimal hintereinander dieselbe; Einblendungen stehen ganz oben. Im Kontrollraum kommt die Figur nur einmal zur Tür
  herein, danach arbeitet sie am Rechner. `SPACE_RE` kennt Raumsonde/Voyager/„des Alls“; „Speicher“ neben Computer-Wörtern ist kein Dachboden
  (`COMPUTER_MEM_RE`), „sendet nur noch Müll“ keine Müllkippe (`JUNK_TALK_RE`). Eine Ecken-Zeile mit Entfernung („… KM VON DER ERDE“) steht nur
  über Szenen im All (`render.build_ass`); der Zähler schreibt „1 TAG“ statt „1 TAGE“. Sonden-Szenen spielen auch dann im tiefen All, wenn das
  Drehbuch einen eigenen Hintergrund mitgibt (Wiese mit Mond); Schilder werden zur Karte ganz oben (`_ov_low` 3, die Ecken-Zeile entfällt dort),
  kein Schnitt und kein Kamerasprung (`_no_cut`). „zweiundzwanzig Komma fünf Stunden“ ergibt 22,5 (`find_figure`); handelt das Video von
  Computerspeicher (`MEM_TOPIC_RE`, `_CTX`), ist „im Speicher“ nie der Dachboden; eine Ecken-Zeile mit einer Jahreszahl, die der Satz nicht nennt,
  und Regie-Wörter als Ecken-Zeile („REHOOK“, „FINTE“) entfallen. Selbsttest: `_probe`.
- Heißluftballon (Ballonflucht, Ballonfahrt – `stage._balloon_story`, greift bei `HOTAIR_RE` in Thema oder Sätzen; ein „Luftballon“ zählt nicht): Requisiten
  `balloon` (fliegt, acht Köpfe in der Plattform-Gondel, Brennerflamme), `balloon_dark` (Gas aus), `balloon_out` (sackt schräg durch), `balloon_fill`
  (richtet sich am Boden mit Flamme auf), `balloon_ground` (Stoffberg mit Gondel), `balloon_down` (Hülle im Gebüsch), `gondola` (Gondel ganz nah),
  `searchlight` (zwei schwenkende Lichtkegel); dazu `sewing` (Nähmaschine mit Stoffbahnen, Wörter nähen/Nähmaschine) und `fabric` (Stoffballen).
  Ort `highsky` (`places.highsky`: hoher Himmel, Wolken, tief unten das Land). Die Regie führt Buch, ob der Ballon in der Luft ist (`B_UP_RE` …
  `B_DOWN_RE`): Flug-Sätze spielen ohne Figuren vor dem hohen Himmel (Suchscheinwerfer, Gas aus, Absturz je ein eigenes Bild), der erste Satz zeigt
  den Ballon im Scheinwerferlicht, am Boden steht die Wiese ohne Bäume und Windräder davor. Einblendungen stehen über dem Ballon (`_ov_low` 3),
  nachts leuchtet er im eigenen Schein (`GLOWS`, `_light`). Selbsttest: `_balloon`.
  Vorgriff am Anfang („kurz vor dem Ziel geht das Gas aus“) zeigt den dunklen Ballon, ohne dass die Geschichte schon fliegt; nach der Gondel ganz nah
  zeigt der Folgesatz (Geländer, Wäscheleine, Gasflaschen) die leere Gondel `gondola_empty` auf der Wiese; „bauen … auf“ zeigt den Stoffberg auch
  ohne das Wort Ballon; ein Ballon aus dem Drehbuch in einem Satz, der nicht vom Ballon handelt, entfällt; Zähler werden über dem Ballon zum Schild.
  Nähmaschine: Figur steht daneben, kein Schnitt auf die Maschine allein (`_no_cut`).
  Abheben und Landung zeigen den Ballon (eine Zahlen-Tafel wird dort zum Schild). Nach der Landung spielt der Schluss auf der Wiese am Dorfrand mit
  der Hauptfigur – keine Großstadtstraße, kein beliebiges Auto, nicht nur ein Streifenwagen vor leeren Häusern.
- Schatz im See (versenkte Kisten, Taucher – `stage._lake_story`, greift bei `LAKE_RE` im Thema oder in zwei Sätzen plus Wörtern wie versenkt/Grund/Taucher):
  Unter Wasser zeigt `places.lakebed` den dunklen Seegrund (Felswände, Schlick, Stämme) statt des Meeresbodens (`scene["_lake"]`, `places.LAKE`).
  Wesen `diver` (Taucher im Neoprenanzug mit Lampe und Blasen – in jedem Video statt des Ersatz-Fischs, wenn die Figur „taucher“ heißt oder der Satz von
  Tauchern spricht: `stage._divers`). Requisiten `crate`/`crates` (Holzkisten statt Pappkarton), `crates_sink` (Kisten sinken trudelnd), `cashcrate` (offene
  Kiste voller Scheine, ohne echtes Banknoten-Motiv), `goldbars`, `logs` (Schicht versunkener Baumstämme), `rocketpart` (verrostetes Versuchsteil am Grund
  statt startender Rakete). An Land spielt die Geschichte am Seeufer (nicht im Büro), ohne Passanten; „Soldaten bringen Kisten“ zeigt zwei Figuren mit
  schlichtem Helm (`hat: army`, ohne Abzeichen) neben dem Kistenstapel; „kein Gold“ zeigt keine Barren. Nie zweimal dasselbe Bild am Grund. Selbsttest: `_lake`.
- Videospiel-Themen (`stage._game_story`, greift bei `GAME_TOPIC_RE` im Kern des Themas): Die Grafik `game` (`graphics._g_game`) zeigt die Spielwelt als eigenes
  Pixel-Bild mit einer Spielfigur in den Farben der Kanal-Figur – `sub`: `world` (Landschaft mit verborgener Tür), `room` (Labyrinth, geheimer Raum hinter der
  Wand mit blinkender Schrift), `minus` (Mauer, dann endloses Unterwasser-Level), `far` (Blocklandschaft zerbricht am Rand der Welt zur löchrigen Riesenwand);
  `label` = welches Bild dieser Welt (0 davor, 1 der Moment, 2 danach, 3 Sonderbild: bei `far` nur Wand, bei `minus` die Vorstellung des Levels) – das bestimmt
  der Satz (`stage._game_step`: grauer Punkt/Wand → 1, Name/blinkt → 2, Mauer/rutscht → 0, Wasser/endlos → 2, Millionen/verrechnet → 1, zerbricht/Wände/Löcher → 2), nicht die Reihenfolge. Sätze über Menschen
  (`GAME_REAL_RE`: Programmierer, Firma, der Junge, Streamer) und der Schlusssatz spielen im Büro am Rechner bzw. im Wohnzimmer vor dem Bildschirm, bei Tag,
  ohne Passanten. Höchstens zwei Spielbilder hintereinander ohne neues Stichwort. Nie Figuren oder Welten echter Spiele nachzeichnen. Weitere Spielwelten:
  Zweig in `_g_game`, Kürzel in `GAME_SUBS`, Stichwörter in `GAME_*_RE`, Fall im Selbsttest (`_game`).
  Stempel: Fällt das Stempel-Wort nur in einer Frage, die der Satz gleich verneint („Du denkst, das war verboten? Falsch, …“ – `stage.refuted`), entfällt er.
  Zähler-Einblendung: Eine Einheit über 16 Zeichen („BIS ZUR ENTDECKUNG“) steht als Unterzeile statt abgeschnitten neben der Zahl.
- Grafiken: „Milliarden“ gesagt, aber „BILLIONEN“ gezeigt → wird berichtigt; Währung in der Unterzeile, die niemand nennt, entfällt; Fragezeichen-Grafik
  an einem Satz ohne Frage wird zur Plakette (`stage.direct`, Anfang).
- Familie im Bild (`stage._family`, `FAMILY_RE`): Spricht der Satz von Familien, Frauen und Kindern, stehen neben der Hauptfigur eine Frau und ein
  Kind (Nebenfiguren dürfen über `look` jetzt auch `size`, `gender`, `hair_color` mitbringen).
- Ecken-Zeilen (`render.build_ass`): Die Zeile oben links wird am Wortende gekürzt; bleibt sie das ganze Video gleich, entfällt eine Uhrzeit darin.
  Eine einzelne Zustands-Angabe oben rechts gilt nur zwei Sätze weiter; nennt sie eine Zahl, die niemand sagt, entfällt sie.
  Eine Uhrzeit in der Ecken-Zeile oder über einer Zahl-Grafik, die der Satz nicht nennt, entfällt (`stage.direct`, Anfang); eine Orts-Angabe je Szene
  („WALD“) gilt nur zwei Sätze weiter und ist keine Überschrift für eine Zahl. Auswahl-Einblendung (`choice`) nur an einer Frage oder einem „oder“.
- Motivationsrede (Rubrik `motivation`, `caption_style: word` – Prüfung 21.11.2026, Videos 173–175): Das große Wort steht ÜBER dem Kopf
  (`render.build_ass`, Stil `Big`, Rand 1220) – nie auf Gesicht oder Hals; deshalb zeichnet `stage._speech` dort keine Zeichen über dem Kopf (`emote: none`).
  `_speech` sorgt außerdem dafür, dass in jedem Bild die Hauptfigur steht (keine Menschenmenge, keine Panik ohne Anlass, kein Bild nur mit einem Ding).
  Für alle Videos: Wer im Bett am Handy scrollt, schläft nicht; eine Wanduhr steht nur bei Uhr/Zeit im Satz; „Handy bleibt im anderen Zimmer“ → kein Handy
  in der Hand; „Speicher dir das“ ist kein Dachboden. `stage._jogging`: „Lauf eine Runde“, „du rennst“ → die Figur läuft die ganze Szene quer durchs helle Bild.
  `_carry_thing`: eine Uhrzeit ist keine Menge, und „diese Meile/Formel“ nennt etwas Neues (`_carry_other`) – der Wecker wandert nicht in die nächsten Szenen.
  Leerer öffentlicher Raum in einem Du-Satz zeigt die Hauptfigur statt jubelnder Fremder. Selbsttest: `_speech173`.
- Reise in die Vergangenheit (`stage._past_story`, greift, wenn der Kern des Themas ein Jahr bis 1849 oder das Mittelalter nennt – `PAST_TOPIC_RE`;
  Prüfung 22.11.2026, Video 185 „Smartphone im Jahr 1800“ spielte vor Läden mit Markisen, mit Passanten im Kapuzenpulli, Wache mit Bauhelm, Bassbox,
  Trinkglas und Kühltürmen): Orte `oldtown` (Baukasten `ground: cobble`, `elements: [oldtown]` – Fachwerkhäuser, Kopfsteinpflaster, Brunnen, Öllaterne),
  `throneroom` (Steinsaal, Thron, Banner ohne Wappen, Fackeln), `royalmuseum` (Kabinett mit Gemälden und einer Vitrine, in der ein erloschenes Handy auf
  Samt liegt); „kein einziger Mobilfunkmast“ spielt im Dorf. Kleidung (`rig.Look.outfit`): `period` (Rock mit Knöpfen bzw. langes Kleid mit Schürze),
  `king` (roter Mantel mit Hermelin, Krone), `guard` (blauer Uniformrock, weiße Gurte); Hüte `tricorn` (Dreispitz) und `bonnet` (Haube). Die Regie gibt
  jeder Figur `_outfit` mit (Hauptfigur `modern` – sie bleibt im Pulli, das ist der Witz), Passanten tragen in solchen Szenen von selbst die Kleidung der
  Zeit (`stage.ERA`). Die Regie führt Buch, wo die Geschichte ist (Stadt → König/Thron/vorgeführt → Museum; Schlussfrage wieder auf dem Platz) und setzt je
  Satz das Bild: Foto/Blitz → Handy mit Blitz (`phoneflash`), zwei erschrockene Bürger; Hexerei → Bürger zeigen auf die Figur; Wachen/Ketten → zwei Wachen
  links und rechts; Taschenlampe → `phonelight` (Lichtkegel auf den König); Musik → `phonemusic` (Noten); Akku → Figur allein, erschrocken; „Display wird
  schwarz/geht aus“ → Requisite `phone_dead` groß (`insert`), danach hält die Figur `phonedead`; Museum → zwei Besucher an der Vitrine. Alle Requisiten,
  Wetter, Baukasten-Landschaften und Handy-/Zettel-Einblendungen des Drehbuchs entfallen dort (nichts Modernes im Bild); ein Zahlen-Schaubild zu
  „nach zwei Sekunden bemerkst du …“ wird zur Szene mit Schild, ein Zähler „5 MINUTEN“ zum Schild „NACH 5 MINUTEN“. „Die Gelehrten des Königs …“ zeigt zwei
  ratlose Gelehrte; ein zweiter Satz zum selben Moment (Musik) holt eine staunende Wache dazu statt dasselbe Bild zu wiederholen. Für alle Videos (Video 186):
  ein Zähler ohne Einheit mit einer Jahreszahl wird zum Schild („ERSTER SATELLIT 1957“ statt hochzählender „1.957“), unter einem Zähler schneidet
  `_cut_plan` nicht auf die Großaufnahme (die Zahl läge auf dem Gesicht), und die gesperrte Überschrift der Plakette (`hyper._badge`) behält ihre Wortlücken. Nennt ein Satz ein anderes Jahr als das der Geschichte („erst 1882“), zeigt er es als Plakette („ERST SPÄTER · JAHR 1882“) –
  nie zwei Schaubilder hintereinander. Kein Halbdunkel in diesen Szenen (`mood` leer). `writer.hook_drops` (Video 187): Satz 2 bleibt beim Schärfen des
  Einstiegs, wenn Satz 3 ihn begründet („Kein Wunder, denn …“, „Deshalb …“); wird ein Einstiegssatz ersetzt, entfällt seine Einblendung, wenn sie zum neuen
  Satz kein Wort mehr gemeinsam hat („KEIN EMPFANG“ über dem Museum). Nach Video 188: zeigt der Folgesatz dasselbe Jahr schon als Schaubild, entfällt die
  Plakette davor (13 Sekunden nur „1882“); liegt das Handy schon in der Vitrine, spielen spätere König-Sätze dort (König staunt neben einem Besucher) –
  die Hauptfigur hält es nicht wieder in der Hand. Offen: die Ecken-Zeile „1800 · MARKTPLATZ“ steht auch über Thronsaal-Szenen. Selftest: `_past`. Fehlt noch: Kutsche, Pferd, Kerker, Marktstände, Kirche der Zeit.

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

## Video nachbauen (Aktion `remake`)
Die App lädt ein Vorlagen-Video in das Release `inbox` und startet `-f 'inputs[action]=remake' -f 'inputs[video_id]=<Dateiname>'`.
`engine/remake.py` hört es an (Spracherkennung), schickt zehn Einzelbilder mit dem Text an die Text-KI (Ablauf, Thema, Video-Art) und
`writer.write_script(..., source=…)` schreibt daraus ein eigenes Drehbuch: gleiche Idee und gleiches Tempo, eigene Worte, keine Namen,
Marken oder Figuren der Vorlage. Danach wird die Vorlage aus `inbox` gelöscht. Statt einer Datei geht auch ein TikTok-/YouTube-Link:
die App lädt ihn auf dem PC mit yt-dlp (bei Bedarf einmal per `pip --user` eingerichtet) und legt die Datei in `inbox`; klappt das nicht,
bekommt der Lauf den Link als `video_id`, `remake.download` versucht es dort, und als letzter Ausweg baut `remake.analyze_link_text` nach
Titel/Beschreibung (oEmbed). „Als Nächstes einplanen“ (App): Vorlage wird ebenso bereitgelegt, aber statt eines Laufs entsteht ein
Warteschlangen-Eintrag `{"remake": Dateiname|Link, "url", "next": true, "category": ""}` – `pick` nimmt ihn zuerst, `queue_remake` baut
ihn nach (Video-Art aus der Vorlage, wenn keine gewählt) und überholt dabei ein schon vorbereitetes Drehbuch. Kategorie `comedy`: absurde Ich-Geschichten mit Humor.

## Einstieg (erste drei Sekunden)
`writer.sharpen_hook` schärft nach jedem Drehbuch die ersten zwei Sätze: Satz 1 nennt IMMER das Thema kurz und spannend (höchstens zwölf
Wörter, z. B. „Drei Tier-Superkräfte, die eigentlich unmöglich sind.“; bei Listen die Anzahl; nicht den Titel wörtlich, keine Floskel wie
„Was wäre, wenn“/„Stell dir vor“), Satz 2 ist der Cliffhanger, den erst das Ende einlöst („Und die letzte kann dir das Leben retten.“) –
übernommen wird nur, was die Prüfung (`hook_weak`: Thema genannt, kurz, ohne Floskel) besteht. Im ersten Bild steht der Titelbild-Text als
Schild (`tag`). `stage._opening`: im ersten Bild reagiert die Hauptfigur sichtbar; die Kamera ruckt kräftig ins Bild (`opener`), Musik und
ein Auftakt-Ton sind ab der ersten Sekunde da. `stage._cold_open`: zeigt das erste Bild nur Menschen, die dastehen, kommt dort schon das
stärkste Bild aus den ersten zwei Dritteln (Vorgriff, `_scene_punch`). Schluss ohne Aufforderung, als Schleife zurück zum ersten Satz;
die Frage an die Zuschauer steht in der Beschreibung. Spannungsbogen (`writer.loop_pass`, nach dem Einstieg): nach jeder Auflösung bzw.
jedem Listenpunkt ein Rehook (neue konkrete Frage), genau eine ehrliche Finte („Du denkst … Falsch – …“); die Text-KI formuliert höchstens fünf
Sätze um, übernommen wird nur, was die Information des alten Satzes behält (≥ 50 % der Inhaltswörter), keine neuen Zahlen, Satz 1/2 und Schluss bleiben. Der Sprecher wird für die Mindestlänge höchstens um 4 % verlangsamt.

## Zahlen und Kanal-Analyse
- TikTok-Follower ohne eigene TikTok-Anmeldung (Upload über Zernio): `uploaders.tiktok_followers_fallback` – erst Zernio-Kontodaten,
  sonst öffentliche Profilseite (`tiktok_handle` in den Einstellungen). YouTube ohne Anmeldung genauso über `youtube_handle` (`uploaders.yt_public`).
- Live im Dashboard (`/api/live` im App-Server, jede Minute): YouTube mit Anmeldung über die API (Abos, Aufrufe des Kanals, Likes der eigenen
  Videos; Anmeldung aus `tokens/youtube.enc`, alle 2 Minuten), sonst öffentliche Kanalseite; TikTok: Follower und Likes vom Profil, Aufrufe
  aus der Videoliste (yt-dlp) oder den einzelnen Video-Seiten. Was live nicht kommt, nimmt die App aus dem letzten gespeicherten Stand.
- `engine/niche.py`: je Video-Art die erfolgreichsten Shorts anderer Kanäle der letzten 14 Tage (YouTube-API, sonst öffentliche Suche),
  bewertet nach Aufrufen pro Tag und Faktor Aufrufe/Abonnenten; die Text-KI macht daraus eigene Themen. Läuft mit den Trends (höchstens
  alle 6 Stunden, „Aktualisieren“ in der App sofort), liegt in `trends.json` unter `niche` und fließt in `writer.new_topic` ein.
  Eigene Suchbegriffe je Video-Art: Feld `niche_queries` in der Kategorie.


## Ton (earshot, Openverse, real-sfx)
- `engine/sound.py`: Klang-Bibliothek in `assets/sfx/` (Liste `manifest.json`, Quellen `CREDITS.md`), gebaut mit der Aktion `sounds`:
  earshot-Soundeffekte (MIT, im Code gebaut, je Rolle mehrere Takes mit gemessenem Einsatz/Spitze) und Openverse-Aufnahmen
  (nur CC0/Public Domain) als Hintergrund-Geräusch je Ort/Wetter, dazu freie Musik in `music/<Video-Art>/`.
- Platzierung nach real-sfx: Whoosh-Spitze 37 ms nach dem Schnitt, Pop 30 ms danach, Tick/Knock leicht davor; Mindestabstand je Rolle;
  kleiner Klang neben großem fällt weg; Musik wird unter der Stimme abgesenkt (sidechain). Ereignisse kommen aus der Animation
  (`scene["_sfx"]`: Dinge springen ins Bild → pop, Schreck → hit, Schnitt im Satz → swish/shutter, Geste „shock“ → hit …) und aus
  Einblendungen (stamp → stamp, tag → shutter, thermo/bar → tick). Ohne Bibliothek bleiben die alten ffmpeg-Klänge.
- Skills für Claude-Sitzungen liegen in `.claude/skills/` (earshot: Ton „hören“ und prüfen; real-sfx: Ton-Design echter Aufnahmen).

- Ausbau 15.11.2026: Bibliothek von Hand neu gezeichnet: `pistole` (schlichte Pistole ohne Vorbild-Modell), `sprungfeder`, `geländewagen`, `lüftungsschacht`,
  `schweißbrenner`, `usb-stick`. Die vorläufige Zeichnung `tuer` ist entfernt – die eingebaute Tür (`door`) kennt jetzt auch „tuer“, „Türe“, „Türen“,
  „Haustür“. Die vorläufige Krabbe `krebs` ist entfernt: ein bloßes „Krebs“ ist im Meer der Krebs als Figur (`stage._sea_kind`), sonst die Krankheit –
  als Bibliotheks-Gegenstand stünde bei jedem Satz über die Krankheit eine rote Krabbe im Bild. `main.known_thing` kennt „Krebs“ deshalb fest.

- Video über ein einziges Meerestier (Prüfung 15.11.2026, „Fangschreckenkrebs“): Nennt das Thema genau ein Meerestier (`stage._sea_default`), meint ein bloßes
  „Krebs“ – im Satz wie als Figuren-Kennung – dieses Tier und nicht mehr den Pistolenkrebs. Damit nicht jede Szene dasselbe Bild ist: Stellt das Drehbuch bei einem
  Satz über Menschen („ein menschlicher Wimpernschlag“, „Menschen haben drei Farbrezeptoren“ – `SEA_HUMAN_RE`) einen Menschen unter Wasser, spielt der Satz als
  Großaufnahme der Figur im Zimmer; mit Becken/Aquarium im Satz (`TANK_RE`) steht die Figur im Labor neben dem Forschungsbecken `tank` (Aquarium mit Krebs).
  Vor der Keule erscheint, wovon der Satz spricht (`SEA_TARGETS`): die Requisite `cavitation` (Dampfblase wächst, fällt zusammen, blitzt mit Druckringen – Wörter
  Dampfblase, Kavitation, Blase kollabiert, Druckwelle: `CAVI_RE`) oder die Sprungfeder aus der Bibliothek; zweimal hintereinander steht das Bild gespiegelt.
  Dinge neben dem groß gezeichneten Tier sind mindestens 300 px hoch (`_PROP_MIN`), Blitz, Glasscheibe und Feder stehen auch bei dunkler Stimmung im Licht (`GLOWS`).
  Küchendampf (`steam`) gibt es unter Wasser nicht. „Mehrere tausend Grad“ ergibt keinen Zähler „1.000 GRAD“ (`find_figure`). `writer.polish` streicht den
  Schlusssatz auch dann, wenn er den ersten mit Vorspann wiederholt („Und hier kommen drei Fakten …“). Selbsttest: `_one_animal`.
  Zielt das Tier auf ein Ding (Glas, Dampfblase, Feder), schwimmt es nicht aus dem Bild (`_vary_repeats` lässt solche Szenen in Ruhe). Eine Figur „taucher“
  bleibt in einem Satz über Taucher ein Taucher und wird nicht zum Krebs. Titelbild (`stage.poster`): Nennt der Kern des Themas das Tier, steht das Tier auf dem
  Titelbild – Gegenstände werden nur noch im Kern des Themas gesucht, nicht in den Vorgaben dahinter („kein Panzerglas“ ergab eine Glasscheibe als Motiv).
  `poster_hero`: Das Tier, das Titel/Thema nennen, steht immer auf dem Titelbild – auch wenn es beim letzten (verworfenen) Bau schon dort war. Tier und Ziel
  stehen sich gegenüber (Tier 400, Ding 860); ein Notizzettel/eine Liste über einer solchen Szene entfällt (schob den Krebs an den Rand). Der Menschen-Satz
  bleibt eine Großaufnahme (Figur läuft nicht durchs Zimmer). `writer.polish` streicht einen abgebrochenen Schlusssatz („Und genau deshalb –“); die Unterzeile
  einer Zahl-Grafik, die nur die Zahl wiederholt, entfällt.
  Menschen-Sätze werden auch erkannt, wenn das Drehbuch dort das Tier hinstellt („Menschen haben drei Arten von Farbrezeptoren“, „schneller als ein
  Wimpernschlag“ – `SEA_PEOPLE_RE`): Dann steht die Hauptfigur im Bild.

- Zugefrorenes Meer (Prüfung 15.11.2026, „Was wäre, wenn die Ostsee zufriert?“ – `stage._ice_story`, Schlussdurchgang in `direct`; greift, wenn Thema oder
  Sätze von Zufrieren/Eisdecke sprechen (`FROZEN_RE`) und ein Meer genannt ist (`FROZEN_SEA_RE`)): Ort `icesea` (`places.OUTDOOR_SPECS`: Boden `ice`, Elemente
  `packice` = aufgeschobene Schollen bis zum Horizont, `icecracks` = Risse und Glanz) statt offener Wellen, Palmenstrand oder Hochgebirge (`snow`). Der einzelne
  Eisberg (`ice`) steht nur noch, wenn der Satz „Eisberg“ sagt. Schiffe stecken fest: Requisite `ship_ice` (Containerschiff schief im Eis, Schollen am Rumpf) statt
  des fahrenden Dampfers. Unter Wasser (`ICE_UNDER_RE` oder Ort `underwater`): `scene["_ice"]` → `places.underice` (Eisdecke oben, dämmriges Wasser) – kein
  Eisberg am Meeresgrund, kein Tiefsee-Schwarz; ohne Tier schwimmt ein Fisch. Delfin/Schweinswal + Atemloch/Sauerstoff: Requisite `icehole` (Loch im Eis, der
  Delfin taucht auf und atmet aus); sonst unter Wasser das Wesen `dolphin`. Küsten-Sätze (`ICE_LAND_RE`) zeigen ein verschneites Dorf vor dem Packeis (`ICE_COAST`),
  „auf dem Eis“ mit Reisenden/Soldaten/Wirtshäusern bekommt Leute aufs Eis. Dürre-, Zimmer- und Karten-Szenen bleiben, wie sie sind. Selftest: `_ice`.
  Thermometer: „sinken um fünfzehn Grad“ ist ein Unterschied, kein Stand – kein Thermometer, das auf +15 °C steigt (Zahl bleibt als Tafel/Zähler);
  „minus zwanzig Grad“ lässt die Säule unter null fallen. Schluss: `writer.polish` beendet einen Schlusssatz, der im Gedankenstrich hängen bleibt, mit Punkt;
  die Drehbuch-Vorgabe verlangt einen vollständigen letzten Satz.
- Neue Wesen (`extras.creature`, Größen in `HERO_SIZE`/`CREATURE_SIZE`): `dolphin` (Delfin/Schweinswal, schwimmt), `cow` (Kuh), `pig` (Schwein), `chimp`
  (Schimpanse, sitzt aufrecht), `mosquito` (Mücke), `fly` (Fliege). Die Text-KI darf sie besetzen (`writer`: "kind"). `stage._named_animals`
  (Schlussdurchgang, `NAMED_ANIMALS`): Nennt der Satz Kuh/Rind, Schwein, Schimpanse/Affe, Mücke, Fliege, Spinne, Katze oder Hund und steht noch kein Tier im
  Bild, kommt es dazu – neben dem Menschen (der rückt nach links), in der Mehrzahl ohne Menschen-Satz als Dreiergruppe in normaler Größe. Redewendungen
  („Schwein gehabt“, `ANIMAL_IDIOM_RE`) zählen nicht. Spricht das Thema von sprechenden Tieren (`TALKING_RE`), bewegt das Tier den Mund, der Mensch hört zu.
  Selftest: `_animals`.
- Karten nur bei Ländern (`stage._map_sense`): Ort `germany` (Leuchtpunkt-Karte) mit zwei oder mehr Ländern im Satz („von Deutschland nach Dänemark und
  Schweden“) wird zur Europakarte mit leuchtenden Ländern (`graphic: map`); eine Karte zu einem Satz ohne Land/Welt („Du denkst, das ist Science-Fiction?“)
  entfällt – die Figur steht in Großaufnahme am Ort der Szene davor. Armee/Soldaten auf dem Eis (`ICE_ARMY_RE`): viele Leute ziehen übers Eis, nicht eine Figur.
  Auf der Eisfläche am Tag gibt es kein Halbdunkel mit Lichtkegel (angespannt/traurig) – es macht aus Weiß Grau.
- Keine leere Eisfläche (`stage._ice_story`, nach Video 110 – dort zeigte ein Drittel des Videos nur Eis mit einem Schild): Hat eine Eis-Szene am Ende weder
  Figur noch Requisite noch Leute, steht die Hauptfigur staunend auf dem Eis. Passanten laufen nur übers Eis, wenn der Satz von Leuten, Armee oder „zu Fuß“
  spricht (sonst füllte die Regie jede leere Eis-Szene mit Spaziergängern). Schweinswal/Delfin in einem Satz, der nicht unter Wasser spielt, zeigt immer das
  Atemloch `icehole` – auch ohne das Wort „Atemloch“ („müssen regelmäßig atmen“).
- Doppelt erzähltes Drehbuch (`writer.repeat_trouble`, nach Video 109): Stehen zwei oder mehr Aussagen fast wortgleich doppelt im Drehbuch (die Text-KI
  schreibt die Vorgaben ab und erzählt dann alles noch einmal, der Schlusssatz steht mitten im Video), lässt `write_script` es bis zu zweimal neu schreiben
  und baut sonst kein Video. `fix_years` läuft nach Lektorat und Spannungsbogen noch einmal.
- Füllstand (`bar`) aus dem Drehbuch mit einer Zahl, die der Sprecher nicht nennt („SAUERSTOFF 15 %“ zu „der Sauerstoff wird knapp“), entfällt – wie schon
  Zähler und Thermometer mit ungesagter Zahl. Selftest: `_ice`.
- Geprüfte Jahreszahlen (`writer.fix_years`): Nennt das Thema Jahreszahlen und verlangt „Keine anderen Jahreszahlen“, wird eine abweichende Jahreszahl
  desselben Jahrhunderts im Sprechertext (ausgeschrieben, `year_words`) und in Einblendungen auf die vorgegebene gesetzt („neunzehnhunderteinundachtzig“ → 1987).
- Alltags-Geschichten mit Dingen als Figur (Prüfung 15.11.2026, „Ich lebte wie 1348“ – `stage._household`, Schlussdurchgang in `direct`): Heißt eine Figur
  „kuehlschrank“ (`FRIDGE_ID_RE`), ist sie das Wesen `fridge` (`extras.creature`: Kühlschrank mit Gesicht, Armen, Beinen; wütend/zeigend hebt er den Arm) –
  kein Roboter neben einem Kühlschrank, kein zweiter Kühlschrank als Requisite, keine gesichtslose Großaufnahme. Nennt der Satz Katze oder Hund (`PET_RE`) und
  steht kein Tier im Bild, kommt es dazu; „gerannt/flieht“ lässt es aus dem Bild laufen. Abmahnung, Brief, Einschreiben (`LETTER_RE`): die Figur hält den
  Umschlag `letter` (`extras.HELD`); ein Radio in der Hand, von dem der Satz nicht spricht, entfällt. „Zähne … grün/gelb/schwarz“ (`TEETH_RE`): die Figur zeigt
  verfärbte Zähne in Großaufnahme (`rig`: `pose.teeth`). „Schrubben/putzen/reiben mit <kleines Ding>“ (`SCRUB_RE`): das Ding liegt in der Hand. Plakette
  (`badge`), die kein einziges Wort des Satzes aufgreift, entfällt – der Satz bekommt ein echtes Bild. Ich-Geschichten: `balance_cast` lässt die Figur, wie das
  Drehbuch sie besetzt (sie ist die erzählende Stimme). Großaufnahme steht höher (`CLOSE_FOOT`), damit die Untertitel nicht über dem Gesicht liegen. Zustands-Zeile
  oben rechts wird nicht mehr mitten im Wort gekappt („KLAGE EINGER“): bis 20 Zeichen in kleinerer Schrift, sonst am Wortende gekürzt. Bibliothek: `salbeiblatt`.
  Selftest: `_household`.
  Ist der Kühlschrank eine Figur der Geschichte, steht er nirgends mehr als gesichtsloses „Ding des Themas“ (Bad, Flur) und kommt mit Gesicht aufs Titelbild.
  Auch „Gebiss … grün“ färbt die Zähne. Titelbild-Text: Eine Zahl, die im Titel steht („1348“), bleibt; nach dem Streichen einer Zahl bleibt nie ein Rest, der auf
  „WIE“, „MIT“, „DER“ … endet (`writer.polish`).
  Neben der Kühlschrank-Figur steht keine Zimmertür („schließt seine Tür“ meint die Kühlschranktür). Das Haustier aus dem Satz kommt auch in
  Ereignis-Einstellungen dazu. Ein Notizzettel ohne Nummern-Titel, dessen Text kein Wort des Satzes aufgreift („FAZIT: …“), entfällt. Schrubben/Putzen mit
  einem Ding in der Hand ist kein Ausschütteln (nichts rieselt heraus).

- Ausbau 16.11.2026 (Musik-Video „Warum du bei Musik Gänsehaut bekommst“ und Hafen):
  Bibliothek von Hand gezeichnet: `kopfhörer`, `bassbox` (Lautsprecher, pulsiert; erscheint auch bei „Bassdrop“, „Lautsprecher“, „Subwoofer“), `muskel`
  (angespannter Oberarm), `achterbahn` (Hügel, Looping, Wagen; als Bild 14 m hoch, damit der Wagen oben nicht aus dem Bild ragt – steht nie im Zimmer,
  beim Wort „Achterbahnfahren“ kann der Schnitt sie groß zeigen); neu gezeichnet statt der vorläufigen Fassung: `wecker` (ohne Alias „uhr“ – das ist die
  eingebaute Wanduhr), `döner` (spitze Brottasche im Papier).
  Kopfhörer auf dem Kopf (`rig`: `hat: "headphones"`, Farbe über `hat_color`): `stage._music` (Schlussdurchgang) setzt sie der Hauptfigur im ganzen Video
  auf, wenn der Kern des Themas von Musik, Songs, Liedern, Playlist, Kopfhörern spricht (`MUSIC_TOPIC_RE`), sonst nur im Satz, der Kopfhörer nennt
  (Feld `wear` an der Figur; Gehirn-/Kühlschrank-Figuren bekommen keine). Die Kopfhörer liegen dann nicht zusätzlich am Boden.
  Requisite `goosebumps` (Schautafel: Hautschnitt, Haarbalgmuskeln ziehen sich zusammen, Haare richten sich auf, Haut wölbt sich): erscheint bei
  Haarwurzel/Haarbalg/Härchen (`TEXT_PROPS`) und drinnen bei „Gänsehaut“ (`GOOSE_RE`, in `_music` – bewusst nicht als „Ding des Themas“ in jeder
  zweiten Szene). Steht die Tafel im Video, bleibt der Oberarm-`muskel` nur in Sätzen, die Muskel/Bizeps nennen. Selbsttest: `_music`.
  Ort `harbor` (`places.OUTDOOR_SPECS`: Boden `quay` = Betonkai mit gelber Kante, Pollern, Kranschienen; Element `harbor` = Pier mit Containerstapeln,
  zwei Containerbrücken, Frachter an der Kaimauer, fernes Ufer). Wörter Hafen, Häfen, Kai, Containerterminal, Werft (`stage.HARBOR_RE`, `HINTS`;
  „haftet“ zählt nicht). Im Hafenbecken laufen keine Wellen-Bögen (sie liefen über Pier und Schiff). Zugefrorenes Meer: Hafen-Sätze spielen am Kai vor
  dem Eis (`ICE_HARBOR`: `packice` + `harbor`) – ohne zusätzliches Schiff im Eis, der Frachter liegt schon an der Mauer.
  Noch offen (vorläufige Zeichnungen der Text-KI): kaffeebohne, tarantel, insekt, erdloch, schloss, keule, radar, kunststoffbecken, knoblauch, kessel,
  kamin, pinzette, nachricht, zigarette. Offene Wünsche ohne Zeichnung: staub, raum, polyp, knie, anwaltstitel, toplitzsee, miete, algorithmus,
  statistik, musik, kompass (davon sind nur polyp, knie und kompass greifbare Dinge).

- Ausbau 17.11.2026 (Video „Warum bekommen wir Gänsehaut?“, 13-Uhr-Termin: fell, luftschicht, kälte, adrenalin):
  Schautafel `fur` (`extras.p_fur`: dichtes Fell liegt flach, die Kälte – blaue Pfeile – kommt bis an die Haut; dann richtet es sich auf und schließt
  eine warme Luftschicht ein, an der die Kälte abprallt). Wörter Luftschicht, Luftpolster, „Fell stellt sich auf“ (`stage.FUR_RE`, `TEXT_PROPS`);
  Schlussdurchgang `stage._fur_story`: ersetzt dort die Gänsehaut-Tafel des Drehbuchs, der Folgesatz über Kälte/Wärme/Schutz behält die Fell-Tafel,
  nie beide Tafeln nebeneinander. Ein bloßes „Fell“ zeigt weiter den Affen (`ANCESTOR_RE`, jetzt auch „Vorfahren hatten … viel dichteres Fell“ und
  „Aufgestellt wirkten unsere Vorfahren größer“): mit „aufgestellt/sträubt/größer“ sträubt er das Fell (`extras.creature` chimp, `action: "puff"`).
  Schautafel `adrenaline` (`extras.p_adrenaline`: Oberkörper, Nieren mit gelben Nebennieren, die pulsieren; Tropfen strömen durch die Adern zum
  rasenden Herzen und in den Kopf). Wörter Adrenalin, Nebenniere, Stresshormon; ein Herz aus der Bibliothek daneben entfällt, die Figur steht links
  und zeigt darauf. Beide Tafeln teilen sich den Rahmen `extras._board`.
  Wetter `cold` (`extras.draw_weather`, `extras.COLD`): kaltes blaues Licht, treibende Eiskristalle; `stage._frame` zeichnet jeder stehenden Figur eine
  Atemwolke vor den Mund (`extras.draw_breath`). Regie: `stage.COLD_RE` in `WEATHER_RE` (Kälte, Frost, eisig, Minusgrade, frieren – nur draußen,
  verneint zählt nicht); Menschen frieren dann sichtbar (`rig.pose_at`: `shiver`, Arme um den Körper, bibbert – `stage._shiver`, auch bei Schnee +
  Kälte-Satz). Ton: Wind. `main.known_thing` kennt „kälte“ und „frost“.
  Bibliothek von Hand gezeichnet: `vorhängeschloss` und `burg` statt der vorläufigen Zeichnung `schloss` – das Wort „schloss“ ist meist das Verb
  („schloss eine Luftschicht ein“, „schloss die Augen“) und stellte ein Märchenschloss in drei Szenen des Gänsehaut-Videos; ein bloßes „Schloss“ zeigt
  deshalb nichts mehr, nur Vorhänge-/Tür-/Zahlenschloss bzw. Burg, Märchenschloss, Festung, Palast. Neu: `vokabel` (Karteikarten; Vokabeln,
  Karteikarte); neu gezeichnet statt der vorläufigen Fassung: `synapse` (Endknöpfchen mit Bläschen, Spalt, Empfänger – pulsiert), `festplatte`.
  „Hautschnitt“ ist die Gänsehaut-Tafel. Selbsttest: `_fur`.
  Noch offen (vorläufige Zeichnungen der Text-KI): kaffeebohne, tarantel, insekt, erdloch, keule, radar, kunststoffbecken, knoblauch, kessel, kamin,
  pinzette, nachricht, zigarette, notenschluessel, schwamm, maus, ohr. Offene Wünsche ohne Zeichnung: staub, raum, polyp, knie, anwaltstitel,
  toplitzsee, miete, algorithmus, statistik, musik, kompass, knall (greifbar davon: polyp, knie, kompass).

- Prüfung 17.11.2026 (Video „Warum bekommen wir Gänsehaut?“): `writer.named_person` – ein Trend-Thema, das eine echte Person, Firma oder Marke
  beim Namen nennt („Warum König Charles … Spudbros-Kiosk“), wird nicht gebaut (die Text-KI meldet Namen im Feld `names`, dazu Titel + Name im Thema
  und Namen aus dem Trend-Titel). `writer.given_meta`: „Titel: …?“ endet am Frage-/Ausrufezeichen und vor „Titelbild-Text:“.
  Katze sträubt ihr Fell (`stage.CAT_PUFF_RE`): die Katze mit Buschschwanz und abstehendem Rückenfell (`extras.creature` cat, `action: "puff"`) –
  nicht der Affen-Vorfahre. Figur mit Kennung „vorfahre“/„urahn“ ist in einem Fell-Video der Affe (`stage._fur_ancestor`), steht rechts neben dem
  Menschen. „Das wirkte wie eine dickere Jacke“ (`FUR_LIKE_RE`) behält die Fell-Tafel statt einer einzelnen Jacke im Schnee. Adrenalin- und
  Gänsehaut-Tafel nie an derselben Stelle (nennt der Satz Adrenalin, bleibt die Adrenalin-Tafel). „Dir ist kalt“ zählt als Kälte (`COLD_RE`,
  verneint nicht). Bibliothek von Hand gezeichnet: `maus` (weiße Labormaus statt der vorläufigen Computermaus), `gans`, `gerupfte gans`;
  `library.text_props`: ein mehrteiliger Name („gerupfte Gans“) sperrt den einfachen („Gans“) an derselben Stelle. Selbsttest: `_goose`.
  `writer.hook_drops`: Der geschärfte Einstieg ersetzt Satz 2 nicht, wenn dieser eine Tatsache trägt, die sonst nirgends im Drehbuch steht (in
  Fassung 132 fehlte so die ganze Erklärung mit dem Muskel an der Haarwurzel); der Einstieg darf nichts behaupten, was das Thema nicht hergibt.
  „… Luftschicht ein, wie eine dickere Jacke“: keine Jacke neben der Fell-Tafel. Der Muskel an der Haarwurzel zeigt keinen Oberarm (`muskel`).
  Kälte-Wetter (`cold`: Eiskristalle, Atemwolke) entfällt am Ende von `direct`, wenn die Szene drinnen spielt (in Video 133 schneite es im Wohnzimmer).
- Prüfung 17.11.2026, Termin 21:00 („Dieses winzige Tier ist zäher als ein Löwe“, Bärtierchen): Neues Wesen `lion` (Löwe mit Mähne; `roar` brüllt,
  `walk` schreitet), neuer Ort `savannah` (trockenes Grasland, Schirmakazien `acacia`), neue Requisite `moss` (Moospolster), Bärtierchen-Haltung `tun`
  (eingerolltes, ausgetrocknetes Tönnchen). `stage._one_tiny`/`_tiny_story`: Nennt das Drehbuch genau einen Winzling (`TINY_KINDS`), ist er das Tier des
  ganzen Videos – jeder Satz ohne Menschen zeigt ihn (vorher nur der Satz mit seinem Namen), Menschen-Sätze über das Tier zeigen es kleiner neben dem
  Menschen (`_ksz`: Größe je Figur), im All treibt es schwerelos, der Vergleich mit dem Löwen zeigt Löwe und Winzling in der Savanne, ab „trocknet aus“
  bleibt es Tönnchen bis „erwacht/krabbelt/lebt“ (`TUN_RE`, `WAKE_RE`). „Löwe“ steht in `NAMED_ANIMALS` (nicht „Löwenanteil“).
  `main.too_similar`: Frage- und Fürwörter („warum“, „dieses“) zählen nicht als Thema, bei alten Videos zählt nur der Kern vor dem Gedankenstrich
  (`_topic_core`) – der vorbereitete Bärtierchen-Plan wurde als „gab es gerade erst (Warum du bei Musik Gänsehaut bekommst)“ übergangen. Selbsttest: `_tiny`.
  Nach den Neubauten 137–139: Stehen nur Tiere am Boden im Bild, zoomt die Kamera um einen Punkt unter der Bodenlinie (`cam["ay"]`) – der Fixpunkt oben
  schob das Tier in die Untertitel. Ein Einschub über das Tier oder Moos wird zur Szene (vorher Tür und Moos frei vor leerem Grund). „Enormer Druck“ spielt
  in der Tiefsee, Hitze-Zahlen stehen als Zähler über dem Tönnchen, „auf Dächern und Mauern“ zeigt das Tier klein am Moospolster, das Schutz-Eiweiß als
  neue Requisite `shield` (Schild mit Erbgut-Strang). Größe je Figur `_ksz` überlebt jetzt `sanitize`. Titelbild eines Winzling-Videos zeigt das Tier
  (die Bibliothek hatte „tönnchen“ als Holzfass mit Alias „tonne“ gelernt – entfernt, `main.NO_THINGS` ergänzt). `writer.polish`: Beschreibung ohne
  „ · “ als Zeilentrenner und ohne Zeilen mit Zahlen, die niemand sagt.

## Musik-Kugel (Video-Art `musik`, einmal am Tag)
- `engine/bounce.py`: Eine Kugel springt durch Glasscheiben, jeder Aufprall ist ein Ton der Melodie. Der Flugweg wird aus den Tonzeiten
  rückwärts gebaut (echte Wurfparabel zwischen zwei Tönen, die Scheibe liegt so, dass sie die Richtungsänderung erklärt) – deshalb sitzt
  jeder Aufprall exakt auf dem Ton. Ton selbst erzeugt (Glockenspiel + Glasklirren + Hall), oben „Erkennst du das Lied?“, am Ende die Auflösung.
- NUR gemeinfreie Melodien in `SONGS` (Komponist seit über 70 Jahren tot oder Volkslied) – Chart-Songs sind auch nachgespielt geschützt.
  Neue Melodie: Eintrag `slug: (Name, Komponist, Tempo, _seq("E5:.25 D#5:.25 …"))`, Dauer in Schlägen, `r` = Pause.
- Physik (`path`): an jedem Ton ein echter Abprall (`_reflect`: Einfallswinkel = Ausfallswinkel, Schwung 0,86–1,08; nur wenn ein
  langer Ton sonst unerreichbar ist, federt die Scheibe stärker, `SPRINGY`). Gesucht wird mit Rückwärtssuche (geht einen Ton zurück, wenn es
  nicht weitergeht). Pausen über `MAX_AIR` bekommen stille Zwischen-Aufpralle (`with_ghosts`). `appear_times`: eine Scheibe erscheint erst,
  wenn die Kugel nicht mehr durch ihren Platz fliegt.
- Eigene Lieder: App → „Musik-Kugel: eigene Lieder“ lädt Audiodateien ins Release `songs` (Name „Künstler - Titel.mp3“). Sie haben Vorrang
  (das am längsten nicht gespielte); `song_hits` nimmt die lautesten 40 s (Refrain) und findet die Einsätze (Spektral-Fluss), `file_song`
  mischt den Original-Ton mit leisem Glasklirren. Rechte an den Liedern liegen beim Nutzer – die Engine lädt keine Lieder selbst aus dem Netz.
- Remixe (`engine/remix.py`): ohne eigene Lieder wird automatisch eine bekannte gemeinfreie Melodie als moderner Track produziert
  (Stile `STYLES`: Phonk, Trap, EDM, Lo-Fi, Sped Up – im Wechsel): Schlagzeug, 808/Bass, Akkorde je Takt aus der Melodie (`harmonize`), Lead
  spielt die Melodie, jeder Melodie-Ton ist ein Aufprall. Neue Melodie: Eintrag in `bounce.SONGS` UND Tonart/Takt in `remix.KEYS`.
- Freie Tracks (`bounce.cc_track`): ccMixter/Jamendo über Openverse, nur CC0 und CC BY (kein NC/ND); die Namensnennung (`credit`) kommt in die
  Beschreibung und ans Videoende. `make_bounce` wechselt ohne eigene Lieder zwischen Remix und freiem Track (`STATE["bounce_src"]`);
  Thema „cc“ oder „remix“ im Studio erzwingt die Quelle.
- Kategorie mit `every_days: 1` und `special: "bounce"`: `main.pick` nimmt sie, sobald ein Tag seit der letzten um ist (`STATE["last_musik"]`),
  sonst nie; `make_bounce` rendert ohne Drehbuch und Sprecher und lädt hoch wie jedes Video.
- Prüfung 17.11.2026 (Video 134, erste geprüfte Musik-Kugel): Nach dem letzten Ton lief der Beat vier Sekunden über einem leeren Bild weiter.
  `bounce.end_time`: Das Video endet `END_HOLD` (0,8 s) nachdem die Kugel aus dem Bild ist, der Ton blendet aus (`END_FADE`). Ab dem letzten Ton
  steht oben „Welches Lied war das? / Schreib es in die Kommentare“ (`OUTRO`, nur beim Rate-Video). Stille Zwischen-Aufpralle (`with_ghosts`)
  sind keine bunten Glasscheiben mehr, sondern blasse Banden (`GHOST_COL`), die nicht zerspringen – „Jede Scheibe ist ein Ton“ stimmt wieder.
  `remix.PEAK` 0,6 statt 0,89 (Spitzen lagen über Vollausschlag). Neubau derselben Fassung: Thema „saints pop“ (Melodie-Schlüssel aus
  `bounce.SONGS`, optional Stil aus `remix.STYLES`) bei `make` mit Kategorie `musik`.
- Prüfung 20.11.2026 (Video 165, „Bella Ciao“ im Glas-Stil): Zwei Scheiben lagen über Eck aufeinander, gleich im ersten Bild und noch einmal
  bei 20 s. `bounce._candidates` verwirft jetzt jede Neigung, bei der die neue Scheibe eine gleichzeitig dastehende berührt (`_pane_rect`,
  `_rects_touch`, Abstand `PANE_GAP`); findet sich keine, geht die Suche wie bisher einen Ton zurück. Ton: Das Klirren (`remix.shatter`) ist
  zweifach differenziertes Rauschen mit der meisten Energie an der halben Abtastrate – bei 0,6 Abtast-Spitze lag die Spitze zwischen den
  Abtastwerten auf +4,4 dBTP, im fertigen Video waren Abtastwerte abgeschnitten. `remix.build` blendet den Mix über 15 kHz weich aus
  (`_lowpass`, `LOWPASS`) und steuert nach der überabgetasteten Spitze aus (`true_peak`, `TRUE_PEAK` = −2,5 dBTP; `PEAK` gilt nicht mehr).
  Gemessen danach: Glas rund −15 LUFS, Pop rund −11 LUFS, nach AAC kein abgeschnittener Abtastwert. Selftest: beides in `_bounce`.

- Ausbau 22.11.2026 (13-Uhr-Termin „Doppelgänger am Telefon: Hörst du dich selbst?“: display; dazu die Wünsche aus dem Raumsonden-Video):
  Neue Requisite `display` (`extras.p_display`: Smartphone aufrecht im Ständer, der Bildschirm flackert – hell, fast aus, Störstreifen –, darauf ein
  Anrufbild ohne Schrift mit rotem Auflegen-Knopf). Wörter Display, Handydisplay, Handybildschirm, Touchscreen, Sperrbildschirm (`TEXT_PROPS`);
  leuchtet nachts im eigenen Schein (`GLOWS`), als Einschub (`shot: insert`) groß allein im Bild. Der Plan-Satz „Das Display flackert kurz auf …“
  gab vorher ein leeres Bild (das Drehbuch setzte dort `phone`, das es nur in der Hand gibt).
  Neuer Ort `controlroom` (`places.controlroom`: dunkler Kontrollraum mit Anzeigewand – Erde mit Flugbahn, Balken, Messkurve, Rundanzeige,
  Meldezeilen –, links und rechts Bedienpulte mit Monitoren; Lämpchen blinken, das Ziel pulsiert: `extras.draw_ambient`). Wörter Kontrollraum,
  Kontrollzentrum, Leitwarte, Leitstand, Leitstelle, Bodenstation, Flugleitung, Mission Control (`HINTS`, `places.ALIASES`); die Text-KI darf
  ihn wählen. Die Raumsonden-Regie (`_probe_story`) lässt Labor-Szenen, wie sie sind – der Kontrollraum kommt nur, wenn Satz oder Drehbuch ihn nennen.
  Bibliothek von Hand neu gezeichnet statt der vorläufigen Fassung: `messgerät` (gelbes Multimeter mit Anzeige, Drehschalter und zwei Messspitzen),
  `insekt` (Marienkäfer von der Seite; auch Käfer, Krabbeltier), `zigarette` (im Aschenbecher mit Rauchfaden; auch Kippe, Aschenbecher).
  Entfernt: `raumsonde` (es gibt die gezeichnete Sonde `probe`; die Notfassung hängte sich mit dem Alias „satellit“
  zusätzlich an jeden Satelliten-Satz), `kontrollraum` (ein Ort, kein Gegenstand – jetzt `controlroom`), `tarantel` (Alias „spinne“; Tarantel und
  Vogelspinne sind das Wesen `spider`, auch in `NAMED_ANIMALS`), `nachricht` (stellte bei jedem „Nachricht“ einen Briefumschlag ins Bild –
  jetzt `briefumschlag` mit Siegel, nur bei Briefumschlag/Kuvert; „Nachricht“ steht in `main.NO_THINGS`). `wasserrohr` verliert den Alias
  „leitung“ („Echos in der Leitung“ stellte im Telefon-Plan zweimal ein Wasserrohr ins Bild). Selbsttest: `_ausbau2211`.
  Noch offen (vorläufige Zeichnungen der Text-KI): erdloch (Alias „loch“ zu weit), kunststoffbecken (Alias „becken“ zu weit), ohr (Körperteil
  allein im Bild). Offene Wünsche ohne Zeichnung: raum, polyp, knie, anwaltstitel, toplitzsee, miete, algorithmus, statistik, musik, knall,
  friteuse, dach, hand, handfläche, steuererklärung (greifbar davon: polyp, friteuse, dach, steuererklärung).

- Prüfung 16.11.2026 (Gänsehaut-Video): `writer.polish` streicht am Schlusssatz einen angefangenen Nebensatz („… jedes Mal wieder, sobald.“ –
  Liste `_DANGLING`). `stage.direct`: Siegertreppchen (`podium`) bleibt nur, wenn mindestens zwei der drei Plätze im Satz oder in den Nachbarsätzen
  genannt werden; Plakette ohne Fragezeichen, wenn der Satz nichts fragt; folgt eine Plakette direkt auf eine andere Vollbild-Grafik, weicht sie
  dem Bild der Szene; stand ein Ding eben als Einschub groß allein im Bild, schneidet der nächste Satz nicht noch einmal darauf (`_no_insert`).
  Nach dem 1. Neubau: `_time_weather` stellt ein Video, das die Text-KI ohne Grund fast ganz in die Nacht legt (kein Wort von Nacht, Schlaf,
  Dunkelheit – `NIGHT_WHY_RE`), auf Tag. `_music`: „winzige Muskeln“ im Gänsehaut-Video sind das Schaubild `goosebumps`, kein Oberarm.
  `ANCESTOR_RE` („behaarte Vorfahren“, „aufgestelltes Fell“): ein Affe im Wald statt der Hauptfigur. „blitzschnell“ ist kein Blitz.
  Zitat-Karte (`overlays.quote`): lange Aussage in kleinerer Schrift auf vier Zeilen, nie mit Artikel am abgeschnittenen Ende.
  Nach dem 2. Neubau: Steht das Schaubild `goosebumps` neben einer Figur, steht sie links davon und zeigt darauf (kein Laufen durch die Tafel,
  kein `event`). `poster_hero`: Ein Wesen, das nur in ein, zwei Szenen eines langen Videos vorkommt, kommt nicht aufs Titelbild.
  Nach Video 120: „gesteuert“ ist nicht „teuer“ (kein Geldstapel), „der Spiegel im Kopf steigt“ ist kein Badezimmer; für Körperteile
  (Haar, Haut, Kopf …) wird nichts gelernt (`main.NO_THINGS`), der gelernte Haarschopf ist aus `shapes.json` entfernt.

- Prüfung 16.11.2026, 18-Uhr-Termin (Schlaf-Video „5 Dinge, die dein Gehirn tut, während du schläfst“, Video 121 verworfen):
  Regie-Wörter der Drehbuch-Anleitung als Einblendung („CLIFFHANGER“, „REHOOK“, „HOOK“, „FINTE“ … – `stage.META_LABEL_RE`) entfallen, wenn der Satz
  das Wort nicht selbst sagt; englische Listentitel („NIGHT SHIFT“, `ENGLISH_TITLE_RE`) werden zu „CHECKLISTE“. `writer`: Einblendungen nur deutsch,
  aus dem Satz, ohne ungesagte Zahl. Schlussdurchgang `stage._sleep_story` (Kern des Themas nennt Schlaf/Traum/nachts – `SLEEP_TOPIC_RE`): eine
  nebenbei genannte Tageszeit („was du mittags gegessen hast“) macht aus der Nacht keinen Tag, nur Aufwachen/Wecker (`WAKE_RE`); nachts laufen
  keine Passanten durch Büro/Labor, wenn der Satz nicht von Leuten spricht – stattdessen zeigt die Figur des Videos auf das Ding.
  Schlafende im Bett (`stage._frame`, `places.bedroom`): Das Bett ist länger (`places.BED_END`), die Figur liegt auf Kissen und Matratze und ist
  zugedeckt (Decke hebt sich mit dem Atem) – vorher lag sie steif obenauf, die Beine ragten übers Bettende. Die Kamera nimmt das ganze Bett
  (`BED_SPAN`), kein Gegenschnitt (er schnitt die Liegende am Rand ab). `poster_hero`: Nennt das Thema das Gehirn und spielt die Gehirn-Figur
  in mindestens drei Szenen mit, steht sie auf dem Titelbild. Selbsttest: `_sleep`.
  Nach dem 1. Neubau (Video 122 verworfen): `stage._sleep_story` verlegt Wohnzimmer-Szenen eines Schlaf-Videos ins Schlafzimmer (die Schlafende lag
  vor dem Sofa auf dem Boden); steht dort nachts nur die Gehirn-Figur, liegt die Hauptfigur schlafend im Bett und das Gehirn steht rechts daneben
  (das Gehirn wird in `_frame` nach seinem sichtbaren Umriss begrenzt, nicht nach der breiten Zeichenfläche). `extras._r`: ein winziges Rechteck
  (Glühbirnen-Sockel, während das Zeichen ins Bild springt) wirft keinen Fehler mehr – zwei Szenen fielen deshalb auf die Ersatzfassung mit der
  falschen Figur zurück. `writer.given_meta`: „Titel: …“ und „Titelbild-Text: …“ im Thema gelten wörtlich (die Text-KI machte aus dem Thema den
  Titel „5 Dinge, die dein Gehirn schläft“; das Lektorat war wegen überlasteter Text-KI ausgefallen). Titelbild (`stage.poster`): Bei zwei oder
  drei Textzeilen rückt das Motiv tiefer und wird kleiner – der Text lag über dem Kopf des Gehirns.
  Nach dem 2. Neubau (Video 123 verworfen): Der Orts-Hinweis „ernte“ gilt nur am Wortanfang – „Gelernte Vokabeln“ spielte auf dem Bauernhof, und
  als Vorgriff begann das Video dort. Nennt das Drehbuch einen Raum und dazu einen Landschafts-Baukasten, von dem kein Satz spricht, gilt der Raum
  (`stage.ROOMS`, `OUTSIDE_RE`, Anfang von `direct`). `stage._indoor_sense`: Bibliotheks-Dinge ab 4 m echter Höhe (Schloss, Wasserturm, Gebäude)
  stehen in keinem Zimmer – zu „schaltet die Muskeln ab“ stand sechs Sekunden ein Märchenschloss neben dem Bett (gemeint war ein Vorhängeschloss).
  Im leeren Schlafzimmer eines Schlaf-Videos liegt nachts die Hauptfigur im Bett. `render.build_ass`: Eine Ecken-Zeile, die nur aus einer Uhrzeit
  besteht und sich nie ändert („03:14 UHR“), entfällt.
  Nach Video 124 (veröffentlicht): `writer.polish` streicht einen Schlusssatz, der auf einem Artikel endet („Und das sind genau die“).

- Prüfung 16.11.2026, 21-Uhr-Termin (Schreck-Video „Was in deinem Körper passiert, wenn du dich erschrickst“, Video 126 verworfen):
  Körper-Reaktionen als Haltung (`rig.pose_at`): `cower` (zuckt zusammen, Kopf eingezogen, Arme vor der Brust), `freeze` (Schreckstarre), `tremble`
  (zitternde Hände), `blink` (blinzelt), `pupils` (Pupillen weiten sich – `rig._eye(pupil=…)`), `pant` (atmet schnell, Hand an der Brust).
  Schlussdurchgang `stage._body_story` (`BODY_ACTS`): Beschreibt der Satz Zusammenzucken, Kopf einziehen, Erstarren, Zittern, Blinzeln, weite Pupillen,
  schnelles Atmen oder Herzklopfen, macht die Figur genau das vor (Blinzeln und Pupillen als Großaufnahme, Erstarren in der Totale) – vorher zeigten
  vierzehn von neunzehn Szenen dieselbe Schreck-Pose. Spricht der Satz vom Gehirn, Hirnstamm oder Mandelkern (`BODY_BRAIN_RE`) und steht nur ein Mensch
  im Bild, steht das Gehirn als Figur daneben; ein solcher Satz spielt nicht als Straßenbild mit Passanten. Ein Satz über Beine/Füße ist keine
  Großaufnahme des Gesichts. Der „Blick nach draußen“ der Abwechslungs-Regie (Straße mit Passanten) entfällt bei Sätzen mit du/dein/ich, Körper oder Gehirn.
  „Welle“ allein ist kein Strand (`HINTS`: nur Meer, Küste, Brandung, „Wellen schlagen“), „von oben nach unten“ keine Stadt-Grafik (`auto_graphic`).
  Ein Oberarm (`muskel`) aus der Bibliothek liegt nicht neben der Figur im Zimmer (`BODY_PROPS`). `writer.polish`: mitgesprochene Regie-Wörter am Satzanfang
  („Dann die Finte: …“) entfallen; Hashtags und Suchbegriffe bekommen echte Umlaute (`_UML`: „#koerper“ → „#körper“). Selbsttest: `_body`.
  Nach dem 1. Neubau (Video 128 verworfen): Der „Blick nach draußen“ entfällt bei jedem Satz über den Körper (`BODY_PARTS_RE`: Beine, Hände, Herz,
  Muskeln, Verdauung, Reflex, Adrenalin …) – zu „Die Beine reagieren zuletzt“ standen besorgte Passanten auf der Straße. `ai.match_words`: Die
  Spracherkennung dehnt das letzte Wort vor einer überhörten Stelle bis an deren Ende; die Dauer eines gehörten Worts ist jetzt begrenzt
  (0,45 s + 0,09 s je Buchstabe), damit der überhörte Satz seine Zeit behält – vorher vier Sekunden ohne Untertitel und mit dem Bild des Satzes davor.

- Ausbau 18.11.2026 (13-Uhr-Termin „Drei geheime Orte in Videospielen“: audiolog; dazu das Insekten-Video und die Pommes-Wünsche):
  Bibliothek von Hand gezeichnet: `audiolog` (Aufnahmegerät mit leuchtender Tonspur, Antenne, Lautsprecher – pulsiert; auch „Audiologs“,
  „Audio Log“, Tonaufnahme, Sprachaufnahme, Diktiergerät), `schmetterling` (Falter auf einer Blüte – als Himmels-Ding wäre er haushoch
  über der Straße geflogen, deshalb steht er am Boden; Falter, Tagfalter); neu gezeichnet statt der vorläufigen Fassung: `raupe` (kriecht
  nach rechts, auch „Larve“), `suppe` (Schüssel mit Löffel und Dampf), `kartoffel`, `krone`, `pommesbude` (Bude mit Markise und
  Pommestüten-Schild ohne Schrift; der falsche Alias „frittöse“ ist weg). Die vorläufige Spielzeug-`puppe` ist entfernt: der Wunsch kam aus
  dem Insekten-Video und meinte die Puppe eines Schmetterlings – jetzt `kokon` (grüne Puppe am Zweig; Wörter Kokon, Puppe, Puppen,
  Verpuppung, Schmetterlings-/Insektenpuppe). Ein Satz über eine Spielzeugpuppe zeigt damit ebenfalls den Kokon.
  Noch offen (vorläufige Zeichnungen der Text-KI): kaffeebohne, tarantel, insekt, erdloch, keule, radar, kunststoffbecken, knoblauch, kessel,
  kamin, pinzette, nachricht, zigarette, notenschluessel, schwamm, ohr, jacke. Offene Wünsche ohne Zeichnung: staub, raum, polyp, knie,
  anwaltstitel, toplitzsee, miete, algorithmus, statistik, musik, kompass, knall, friteuse, eiweiß, dach (greifbar davon: polyp, knie,
  kompass, friteuse, dach).

- Prüfung 18.11.2026 (Video 144 „Nachbarn“): Requisite `drill` (Akku-Bohrmaschine, rattert; `TEXT_PROPS` bei bohrt/Bohrmaschine/Akkuschrauber).
  `stage._last_look` läuft als allerletzter Durchgang der Regie: derselbe Zähler-Wert in zwei Sätzen hintereinander → der zweite entfällt;
  Abhak-Liste, von deren Punkten weder der Satz noch seine Nachbarsätze einen nennen, entfällt; Schild (`tag`), dessen Wörter weder im Satz, in den
  Nachbarsätzen noch im Thema vorkommen, entfällt; eine Tür ist keine Großaufnahme (fällt aus dem Einschub, allein → normale Szene mit Figur).
  `library.FALSE_FRIENDS` um club/clubs/bald erweitert („wie im Club“ zeigte eine Keule). `writer.list_trouble` meldet jetzt auch einen Einstieg
  „Vier Nachbarn, die …“, dem keine Aufzählung folgt (kein „Nummer eins“, keine Ordnungszahl) – das Drehbuch wird neu geschrieben.
  `rig`: Haltung `cower` setzt den Mund ernst (vorher Sorgenbrauen mit Lächeln in der Großaufnahme).

- Prüfung 18.11.2026, Termin 21:00 (Video 148 „Weihnachten mit der Familie eskaliert“, verworfen): Neuer Ort `diningroom` (`places.diningroom`: gedeckte
  Festtafel mit Braten, Klößen, Kerzen, Stühlen, Anrichte; Wörter Esszimmer, Esstisch, Festtafel, Festessen, „am Tisch“ – `HINTS`). „Nach dem ersten Gang“
  ist kein Flur mehr (`\bgang\b` gilt nur noch mit „im/durch den/auf dem Gang“). Weihnachts-Videos (`stage._feast_story`, `XMAS_RE` in Thema oder Text):
  `scene["_xmas"]` → `places.XMAS` – Wohn- und Esszimmer mit Girlande und geschmücktem Baum samt Geschenken (`places.xmas_tree`, eigener Cache-Schlüssel);
  Sätze vom Essen (`FEAST_TABLE_RE`) spielen an der Tafel, Sätze von Baum/Geschenken im Wohnzimmer; ein Fest hat eine Tageszeit (wie die erste Szene).
  Verwandte im Bild (`stage._relatives`, `RELATIVES`, in jedem Video): Nennt der Satz Oma, Opa, Onkel, Tante, Mama, Papa, Cousin, Cousine, Schwester,
  Bruder, steht die Person mit eigenem Aussehen da – allein, wenn der Satz kein du/ich enthält, sonst rechts neben der Hauptfigur; Tier-Szenen und
  Redewendungen (`RELATIVE_IDIOM_RE`) bleiben. `_prepare`: Eine Figuren-Kennung, die nicht in der Besetzung steht, aber ein Tier meint („vogel“, Besetzung
  „truthahn“ mit `kind: bird`), ist das Tier – kein Mensch im Pulli. `TEXT_PROPS`: „greifen“ ist kein Reifen. Selbsttest: `_feast`.
  Noch offen: Truthahn/Gans als eigenes Wesen (der Vogel ist ein Rotkehlchen), Figuren sitzen nicht am Tisch, sondern stehen davor.
  Nach dem 1. Neubau (Video 149 verworfen): Im Fest-Video spielen Essens-Sätze nie auf der Deutschlandkarte oder der Straße („In Deutschland liegt
  Kartoffelsalat vorn“, „noch vor der Gans“) – Hauptfigur am Esstisch, keine lebende Gans daneben; am Esstisch und in Szenen mit Verwandten kein Schnitt auf
  ein einzelnes Ding (`_no_insert` – drei Sekunden ein Kloß vor leerem Grund). Gruppen-Füllfiguren (`_team…`) werden zu den Verwandten des Videos.
  `writer.hook_drops`: Kündigt Satz 2 den ersten Listenpunkt an („Nummer eins, …“) und steht das sonst nirgends, bleibt er beim Schärfen des Einstiegs.
  Nach dem 2. Neubau (Video 150): Das Festzimmer ist hell erleuchtet – „Heiligabend“ als Nacht legte das ganze Video ins Halbdunkel (nur Stromausfall,
  Kerzenschein, Dunkelheit im Text lassen es dunkel). Nennt der Satz einen Verwandten, gibt es keinen Einschub auf ein Ding („Der Onkel sitzt auf dem Sofa“
  zeigte sechs Sekunden ein Sofa vor leerem Grund); ein Sofa als Requisite im Wohnzimmer entfällt (`PLACE_HAS`). `_last_look`: Auswahl-Einblendung über
  mehreren Sätzen ohne „oder“ entfällt („NACHSCHLAG KOMMT / VIERTER TYP“ zehn Sekunden über dem Schluss).
  Nach dem 3. Neubau (Video 151, veröffentlicht): `writer.loop_pass` übernimmt eine Umformulierung nicht, wenn ein Zahlwort des alten Satzes fehlt (die
  Pointe „… aber Oma legt den vierten drauf“ wurde zur offenen Frage „… weißt du, was Oma danach macht?“) oder wenn sie eine neue Frage direkt vor den
  nächsten Listenpunkt („Nummer zwei, …“) setzt, die niemand mehr beantwortet.

- Ausbau 19.11.2026 (13-Uhr-Termin „Was wäre, wenn du ein Super-Tier aus vier Arten baust?“: blauwal; dazu die Wünsche aus den Nachbarn-, Spiele- und
  Weihnachts-Videos): Neues Wesen `whale` (`extras.creature`: Blauwal – langer blaugrauer Körper, helle Kehle mit Furchen, kleine Finne weit hinten,
  breite Fluke, gleitet). Steht in `stage.SEA_CREATURES`/`SEA_KINDS`: Nennt der Satz Blauwal, Buckelwal, Pottwal oder „Wal/Wale“, ist er groß und allein
  die Figur der Szene unter Wasser, Folgesätze bleiben bei ihm (nicht bei Schweinswal/Delfin im selben Satz – das bleibt `dolphin`; „Wahl“ und „Walnuss“
  zählen nicht). Größen in `HERO_SIZE`/`CREATURE_SIZE`, `LONG_KINDS`; die Text-KI darf ihn besetzen (`writer`: "kind": whale). Selbsttest: `_sea`.
  Bibliothek von Hand neu gezeichnet statt der vorläufigen Fassung: `konsole` (flache Spielkonsole mit Gamepad, kein Vorbild-Modell), `mauer`
  (Ziegelmauer mit Abdeckplatte – der Alias „wand“ ist weg: „Die Wand vibriert“ stellte eine Ziegelmauer ins Wohnzimmer), `post-it` (gelbe Haftnotiz
  mit Kritzeln statt Schrift), `mischpult` (Regler und Pegelanzeige, pulsiert), `trillerpfeife` (ohne den Alias „pfeife“), `praline` (im
  Papierförmchen; ohne die Aliasse „schokolade“ und „trüffel“), `kloß` (drei Klöße in Soße auf dem Teller; auch Knödel).
  Noch offen (vorläufige Zeichnungen der Text-KI): kaffeebohne, tarantel, insekt, erdloch, keule, radar, kunststoffbecken, knoblauch, kessel, kamin,
  pinzette, nachricht, zigarette, notenschluessel, schwamm, ohr, jacke, ohrstöpsel, neonreklame, sofa. Offene Wünsche ohne Zeichnung: staub, raum,
  polyp, knie, anwaltstitel, toplitzsee, miete, algorithmus, statistik, musik, kompass, knall, friteuse, dach (greifbar davon: polyp, knie,
  kompass, friteuse, dach). „Wand“ und „Punkt“ stehen jetzt in `main.NO_THINGS` (jedes Zimmer hat Wände, ein Punkt ist kein Ding) – dafür wird
  nichts mehr gelernt; die Wünsche wand, punkt, tönnchen, eiweiß sind damit erledigt.

- Prüfung 19.11.2026 (13-Uhr-Termin, Video 152 „Was wäre, wenn du ein Super-Tier aus vier Arten baust?“ verworfen): Das gebaute Wesen war nie zu
  sehen – im ersten Bild („im Labor“) und in fünf weiteren Szenen schwamm ein Blauwal unter Wasser, zum „Haufen Zellen auf dem Tisch“ standen Passanten
  auf der Straße, zur „Weltherrschaft“ drei Waagen, in der Küche ein fremder Junge neben einem Eisberg (Regie-Figur `_tier` ohne Art).
  Neues Wesen `chimera` (`extras.creature`, im Gepard-Zweig): Gepard-Körper mit Adlerflügeln, großen gelb umrandeten Adleraugen und einem schlagenden
  roten Herzen in der Brust; `action` „run“ (Galopp) und „down“ (zusammengesackt, Herz grau, Augen zu). Größen in `HERO_SIZE`/`CREATURE_SIZE`, `LONG_KINDS`.
  Regie `stage._hybrid_story` (Schlussdurchgang, greift nur, wenn Thema/Titel ein Misch-Wesen nennen – `HYBRID_RE`: Super-Tier, Mischwesen, „Wesen aus …
  Tierarten“): Sätze über das Wesen (`HYBRID_BEING_RE`) und Sätze ohne Tiernamen spielen im Labor – Hauptfigur und Misch-Wesen nebeneinander, Seiten
  wechseln; „rennt/sprintet“ → Wesen im Galopp in der Savanne; „bricht zusammen/versagt“ (`HYBRID_FAIL_RE`) und „Haufen Zellen“ → Wesen liegt, Figur
  erschrocken. Nennt ein Satz ein Tier beim Namen, bleibt dieses Tier in seinem Lebensraum (höchstens ein Folgesatz mit „Es/Dieses …“). Keine Passanten,
  keine Requisiten aus Vorsätzen. Allgemein (jedes Video): Regie-Figuren (`_tier`, `_meer`) ohne Art werden gestrichen; Zahl-Grafik „KM“ wird „KM/H“,
  wenn der Satz „Kilometer pro Stunde“ sagt; Zähler „… GRAD“ bekommt die Überzeile „MINUS“, wenn der Satz „minus“ sagt (nur im Misch-Wesen-Durchgang).
  Untertitel (`render.build_ass`): kein Häppchen über einen Szenenwechsel hinweg – bei Sätzen ohne Punkt stand das erste Wort des nächsten Satzes noch
  im alten Bild („ANGREIFT DESHALB“). `writer.polish`: „mehrerenhundert“ → „mehreren hundert“; abgeschnittene Hashtags („#fakte“ → „#fakten“).
  Nach dem 1. Neubau (Video 153, verworfen: Bärtierchen im Bild zum Satz „Das Herz wiegt 180 Kilogramm“, Adler und Bärtierchen im Labor, Hauptfigur am
  Bildrand angeschnitten, Misch-Wesen statt Bärtierchen beim Weltraum-Satz): genannte Tiere stehen in ihrem Lebensraum (`HYBRID_HOME`; Schnee, Wüste,
  Weltraum aus Satz oder Drehbuch bleiben), bis zu zwei Folgesätze („Es …“, „Seine …“, „Im Jahr …“) bleiben beim Tier – auch über eine Zahl-Grafik
  hinweg –, ein Herz-Satz ohne Wal zeigt das Wesen; im Labor stehen Figur und Wesen weiter innen, ohne Schwenk und Gegenschnitt (`_no_cut`,
  `cam_move`); nach dem Zusammenbruch bleibt das Wesen bis zur Schlussfrage liegen.
  Nach dem 2. Neubau (Video 154, verworfen: Sprecher sagt „neunzig und drei Kilometer“, Zähler „3 KM“; „minus 271“ statt 272; Herz auf dem Titelbild):
  `writer.polish` dreht „neunzig und drei“ zu „dreiundneunzig“; Zähler-Einheit „KM“ wird „KM/H“ bei „Kilometer pro Stunde“; der Satz direkt nach
  einem Tier-Satz („In freier Wildbahn wurden … gemessen“) bleibt beim Tier, solange er keinen neuen Gedanken beginnt (Aber/Doch/Zutat/Superkraft …);
  Titelbild eines Misch-Wesen-Videos zeigt das Wesen (`poster_hero`, `poster`). Für Neubauten: Zahlen im Thema zusätzlich als Wort ausschreiben.
  Nach dem 3. Neubau (Video 155, veröffentlicht): Zähler aus „wenige/mehrere/einige hundert …“ entfällt („100 METER“ lag über dem Kopf des Gepards);
  im Misch-Wesen-Video steht das Bärtierchen im Wald klein am Moospolster statt baumhoch; `writer`: Umlaute für baertier/kaefer/loewe/voegel in
  Hashtags und Suchbegriffen. Selbsttest: `_hybrid`.
  Noch offen: In anderen Mehr-Tier-Videos steht das Bärtierchen weiter groß im Wald. Die Text-KI lässt die verlangte Schlussfrage weg; Zahlen im
  Thema werden nur verlässlich gesprochen, wenn sie zusätzlich als Wort dastehen („gesprochen: dreiundneunzig“). Die Aktion `upload` und der Weg über
  Zernio laden auf YouTube die volle Fassung hoch – die Kurzfassung aus `ytcut` entsteht nur beim direkten Bau mit Upload ohne Zernio.

- Sprechende Geräte (Prüfung 19.11.2026, „Wenn Technik die Kontrolle verliert“ / „Was wäre, wenn deine Geräte die Wahrheit sagen?“, Videos 156/157 –
  `stage._devices`, Schlussdurchgang in `direct`): Tut der Kühlschrank im Satz selbst etwas (`DEVICE_TALK_RE`: meldet, fragt, übernimmt, wirft …), steht er
  als Figur `fridge` neben dem Menschen (`_fridge_in`) – nicht als Großaufnahme ohne Gesicht mit Dosen vor blauem Grund. Folgesätze „Er sagt …“, „Und er
  fragt …“ bleiben bis zu zwei Sätze beim Gerät von eben (`DEVICES`: Kühlschrank-Figur, Fernseher, Router, Wecker). Wecker im Satz: Bibliotheks-`wecker`
  statt Wanduhr `clock`; „um drei Uhr nachts“ (`CLOCK_TIME_RE`) ist eine Uhrzeit und stellt keine Wanduhr auf den Boden. „Dein Router“ steht nicht im
  Rechenzentrum; „Im Auto behauptet das Navi“ spielt auf der Straße, nicht in der Werkstatt (Navi → `car` in `TEXT_PROPS`). Zähler-Einheit ohne Wörter,
  die niemand sagt („7 HEUTE“).
  Neuer Ort `transit` (`places.transit`: Innenraum von Bus/Straßenbahn/Bahn – Fensterband mit Stadt, Haltestangen mit Schlaufen, Sitzreihe): „im Bus“,
  „in der (vollen) Bahn“, „Fahrgäste“ (`HINTS`, `places.ALIASES`); ein Bahnsteig (`station`) mit Fahrgästen im Satz oder direkt nach einer Fahrzeug-Szene
  wird zum Innenraum. Dort läuft niemand durchs Bild, die Fahrgäste stehen und schauen her (`crowd: watch`). Die Text-KI darf `transit` wählen.
  Verneinung (`stage.denied`, `DENY_RE`): „nur ohne Burgen“, „weil er keinen Chip besitzt“ – wovon der Satz sagt, dass es fehlt, steht nicht im Bild
  (weder aus dem Drehbuch noch aus der Bibliothek, auch nicht als Großaufnahme). Der Fernseher im Wohnzimmer wird gezeichnet (`PLACE_HAS` behauptete, er
  stehe schon da – im Bild gab es nie einen). „fassungslos“ ist kein Fass. Kurve aus dem Drehbuch: Richtung nach dem Satz („stürzen ab“ → rot abwärts),
  Überschrift/Unterzeile nur mit Wörtern aus dem Satz (kein „DAX“). Vorgriff im ersten Bild (`_cold_open`) nimmt kein Alltagsbild mehr, das nur aus einem
  Ding und einer Geste besteht (Auto auf der Straße zum Satz „Deine Geräte packen aus“). Hook-Titel: `main` las `script["thumb"]`, das Drehbuch führt den
  Text aber unter `thumbnail.text` – der große Titel im ersten Bild fehlte deshalb in jedem Video. Bibliothek: die automatisch gelernte Zeichnung
  `gameboy` (Nachbild eines Markengeräts) ist entfernt, das Wort zeigt die neutrale `konsole`; für Marken-Geräte wird nichts mehr gelernt (`main.NO_THINGS`).
  `writer.polish`: „hineinschaußt“ → „hineinschaust“. Selbsttest: `_devices`.
  Nach Video 160 (veröffentlicht): ein einzelnes Auge aus der Bibliothek steht nirgends mehr neben Menschen („mustern dich mit großen Augen“ in der Bahn);
  beim Navi-/„im Auto“-Satz draußen sitzt die Figur nicht auf einer Kiste am Gehweg; `writer.polish`: „Es war nämlich nur du“ → „Es warst nämlich nur du“,
  Hashtag „#fy“ → „#fyp“, Umlaute für geraet/kuehlschrank in Hashtags und Suchbegriffen.
  Noch offen: Gäste und Freunde („zeigt allen Gästen“, „deine Freunde grinsen“) kommen nicht ins Bild; Großaufnahmen von Fernseher, Router, Auto stehen
  allein vor Farbgrund; Kaffeemaschine und Joghurt haben keine Zeichnung; die Wanduhr `clock` steht weiter am Boden statt an der Wand.

- Niedliche Gifttiere (Prüfung 19.11.2026, Termin 21 Uhr, Plan „Tödlich niedlich: Diese 3 Tiere …“, Video 161): Die Engine kannte weder Pfeilgiftfrosch
  noch Schnabeltier noch Kugelfisch – im Video standen ein grüner, automatisch gelernter Frosch-Klecks, ein Dampfer auf dem Fluss und ein Goldfisch.
  Neue gezeichnete Wesen (`extras.creature`): `frog` (knallgelber Pfeilgiftfrosch, `hop` = hüpft), `platypus` (Schnabeltier mit Entenschnabel und
  Biberschwanz, `spur` = hebt das Hinterbein und zeigt den Giftsporn mit Warn-Ring), `puffer` (Kugelfisch, `puff` = bläst sich zur Stachelkugel auf).
  Regie `stage._cute_animals` (Schlussdurchgang, `CUTE_ANIMALS`): Nennt der Satz eines der Tiere, steht es groß und allein in seinem Lebensraum (Frosch im
  Wald, Schnabeltier am sandigen Flussufer, Kugelfisch unter Wasser); bis zu zwei Folgesätze, die sichtbar weiter von ihm handeln (`CUTE_NEXT_RE`: „Sein
  Hautgift …“, „Er bläst sich auf …“), bleiben bei ihm – gespiegelt und mit Handlung. Geht es ums Anfassen (`CUTE_TOUCH_RE`), weicht der Mensch erschrocken
  zurück und das Tier sitzt klein daneben. Sätze über Essen und Köche (`CUTE_SKIP_RE`) und Redewendungen („Frosch im Hals“) bleiben, wie sie sind.
  Köche (`stage._cooks`, `COOK_RE`): Nennt der Satz einen Koch, steht eine Figur mit Kochmütze (`rig`, Hut `chef`) und weißer Jacke in der Küche –
  vorher lief die Hauptfigur durch die Küche. Die automatisch gelernten Notbehelfe `schnabeltier` und `pfeilgiftfrosch` sind aus `shapes.json` entfernt;
  die Wörter gelten als bekannt (`main.known_thing`). Die Text-KI darf `frog`, `platypus`, `puffer` besetzen. Selbsttest: `_cute`.
  Nach dem 1. Neubau (Video 162): „Er passt auf deine Handfläche“ (`CUTE_PALM_RE`) und „Es sitzt in seiner Haut …“ nach einer Zahl-Grafik bleiben
  beim Tier (vorher Großaufnahme des Menschen – Szenen ohne `actors` wurden übersprungen, die Grafik zählte nicht mit). Das erste Bild eines solchen
  Videos zeigt Frosch und Schnabeltier nebeneinander am Ufer statt eines Menschen am Fluss. Folgesätze wechseln die Blickrichtung. Kochmütze niedriger
  (füllte in der Großaufnahme das halbe Bild), der Koch redet statt mit Fragezeichen zu grübeln. Auswahl-Einblendung mit zwei Antworten zur Frage
  „Welches der drei …?“ entfällt. Kugelfisch ohne Zorn-Zeichen. Giftsporn größer gezeichnet.
  Nach dem 2. Neubau (Video 163): Das Titelbild zeigte einen grünen Außerirdischen – „Australien“ enthält „alien“ (`TOPIC_CREATURES`, Weltraum-Hinweis).
  Das Muster verlangt jetzt den Wortanfang.
  Nach dem 3. Neubau (Video 164, verworfen; veröffentlicht wurde 163): Besetzt die Text-KI in einem Kugelfisch-Video den Ersatz-Goldfisch (`fish`), wird er
  zum Kugelfisch. Folgesätze über Farbe, Fressfeinde, Nahrung bleiben beim Tier.
  Noch offen: Der geschärfte Einstieg der Text-KI macht aus „alle drei sind giftig“ ein „tödlich giftig“ samt Stempel, obwohl das Schnabeltier für
  Menschen nicht tödlich ist; „landet in Japan auf dem Teller“ spielt in einem Schnellrestaurant mit Passanten; Jäger mit Blasrohr haben kein Bild; eine
  Hand, auf der der Frosch sitzt, gibt es nicht; die verlangte Schlussfrage fehlt je nach Neubau.

- Ausbau 20.11.2026 (keine offenen `needs` in den Plänen; Wünsche aus den Mittelalter-, Weihnachts-, Gänsehaut- und Geräte-Videos):
  Bibliothek von Hand gezeichnet: `kompass` (Taschenkompass aus Messing mit rot-weißer Nadel; neu). Neu gezeichnet statt der vorläufigen Fassung:
  `knoblauch` (Knolle mit einzelner Zehe), `kessel` (gusseiserner Kochkessel auf drei Füßen mit Eintopf, Henkel und Dampf – ohne den Alias „topf“),
  `kamin` (gemauerter Kamin mit Holzsims und brennenden Scheiten – ohne den Alias „ofen“: „Backofen“/„Ofen“ ist kein Kamin), `kalender`
  (Abreißkalender zum Aufstellen, ein Tag rot markiert, keine Ziffern), `sofa` (blaues Zweisitzer-Sofa mit Kissen), `neonreklame` (Schild am Mast
  mit Neonröhren-Rahmen, Pfeil und Zickzack, ohne Schrift – pulsiert; als Bild 2,4 m hoch), `jacke` (orange Steppjacke am Kleiderbügel).
  Der Wunsch `navi` ist erledigt (seit der Prüfung vom 19.11. zeigt ein Navi-Satz das Auto auf der Straße).
  Noch offen (vorläufige Zeichnungen der Text-KI): kaffeebohne, tarantel, insekt, erdloch, keule, radar, kunststoffbecken, pinzette, nachricht,
  zigarette, notenschluessel, schwamm, ohr, ohrstöpsel. Offene Wünsche ohne Zeichnung: staub, raum, polyp, knie, anwaltstitel, toplitzsee, miete,
  algorithmus, statistik, musik, knall, friteuse, dach, hand, handfläche (greifbar davon: polyp, knie, friteuse, dach, hand/handfläche – eine
  Hand, auf der ein Tier sitzt, wäre eine eigene Haltung der Figur, kein Bibliotheks-Gegenstand).

- Prüfung 20.11.2026, Termin 18 Uhr (Plan „Unpassend lachen: Warum das Gehirn bei Beerdigungen ausrastet“):
  Neuer Ort `chapel` (`places.chapel`): Kirche von innen – Steinwand, drei Spitzbogenfenster mit buntem Glas, Altar mit Kerzen und Blumen,
  Bankreihen, roter Läufer. `church` bleibt die Kirche von außen. Neuer Schlussdurchgang `stage._funeral_story` (greift bei Beerdigung,
  Trauerfeier, Beisetzung, Sarg … in Thema oder Text): Szenen mit Ort `church` und Sätze „in der Kirche“, „Trauergäste“, „Pfarrer“ spielen im
  Kirchenraum (außer „vor der Kirche“, „Friedhof“, „draußen“); Kirchenraum und Friedhof bekommen `_mourn` – alle Menschen tragen Schwarz,
  niemand trägt Kappe oder bunte Mütze (`stage.MOURN`, auch die Menge aus `_crowd`), Trauergäste stehen auch am Grab (`crowd_ok`), niemand
  schlendert, jubelt, tanzt oder rennt, kein Auto und kein Wetter im Kirchenraum.
  Neue Requisiten `vacuum` (Bodenstaubsauger mit Schlauch und Düse) und `vacuum_broken` (Deckel aufgesprungen, Knall-Zacken, Staubwolke, Flusen
  am Boden). „Staubsauger“ im Satz stellt ihn ins Bild (`TEXT_PROPS`); sagt der Satz „explodiert / Knall / kaputt / raucht“, steht er ab da
  kaputt da und ersetzt Qualm und Feuer-Explosion (`stage._household`). Selbsttest-Fall `_funeral`.
  Nach Video 167/168 (erster Neubau): Der Vorgriff im ersten Bild (`_cold_open`) entfällt, wenn der erste Satz seinen Ort nennt und dort
  spielt („Ich stand auf einer Beerdigung …“ lief im Wohnzimmer); „Beerdigung“, „Begräbnis“, „Beisetzung“ sind Orts-Namen für `graveyard`,
  „Trauerfeier“ für `chapel`. Ein Staubsauger, an den nur gedacht wird, steht nicht im Kirchenraum; nie zwei Staubsauger ineinander.
  Neue Haltung `laugh` (`rig.pose_at`: Kopf im Nacken, Augen zugekniffen, Mund weit offen, Schultern beben) – „pruste los“, „loslachen“,
  „Lachkrampf“, „vor Lachen“ setzen sie (`BODY_ACTS`), mit fröhlichem Gesicht statt Schreck. Herzschlag-Grafik (`pulse`) nur zu einem Satz
  über Puls, Herz oder Adrenalin. Die Ecken-Zeile des Drehbuchs verliert eine Uhrzeit, die kein Satz nennt, auch wenn Szenen eigene Zeilen
  haben (`render.build_ass`). Satz ohne Figur im Kirchenraum oder am Grab: die Hauptfigur grübelt dort. Für „Teppich“, „Staub“,
  „Beerdigung“ wird nichts gelernt (der gelernte „Teppich“ war ein Tisch mit Muster und ist entfernt).

- Prüfung 20.11.2026, Termin 21 Uhr (Plan „Tattoo-Studio gegen Nagelstudio: Wer verdient wirklich mehr?“):
  Neue Orte `tattoostudio` (dunkle Wand mit gerahmten Motiv-Bögen, Leucht-Herz ohne Schrift, schwarze Liege, Rollwagen mit Farbfläschchen,
  Ringlicht) und `nailstudio` (rosa Wand, Regal voller Nagellack, runder Spiegel, Arbeitstisch mit Bogenlampe, Härtelampe, Hocker).
  Namen wie „tattoo_shop“, „Tattoo-Studio“, „nail_salon“, „Nagelstudio“, „Maniküre“ führen dorthin (`places.ALIASES`).
  Neue Requisiten `tattoomachine`, `nailfile`, `nailpolish` – klein, gedacht für die Hand der Figur (`hold`).
  Neuer Schlussdurchgang `stage._studio_story` (greift bei Tattoo/Tätowieren oder Nagelstudio/Nägel/Maniküre in Thema oder Text): Ein Satz
  übers Tätowieren bzw. über Nägel spielt im passenden Studio, die Figur hält Maschine bzw. Feile, kein Schnitt auf ein Ding allein
  (`_no_insert`). Jede Figur merkt sich ihr Studio: Folgesätze ohne eigenen Ort spielen wieder dort; stehen beide zusammen im Bild und der
  Satz nennt kein Studio, ist der Ort neutral. Drinnen kein Wetter, kein Auto, keine Passanten. Selbsttest-Fall `_studios`.
  Nach Video 171 (erster Neubau): `stage._unpaid` – sagt der Satz „unbezahlt“, „bezahlt … niemand“, „kostenlos“, liegt und hält niemand Geld
  (Tobi hielt bei „bezahlt ihm niemand“ einen Stapel Scheine). Fläschchen, Feile und Maschine liegen im Studio nie am Boden: in die Hand
  der Figur oder weg. Plan-Figuren unter `who` werden zu `actors` (`writer`).
  Nach Video 172 (zweiter Neubau, verworfen): `_studio_story` tauscht die Figur, wenn der Satz vom anderen handelt („nimmt Tobi dreimal so
  viel ein“ – im Bild war Nina; „Tätowierer verdienen …“ – Nina stand im Tattoo-Studio): die genannte Person bzw. die Besitzerin des
  Studios steht in ihrem Studio. `stage._score_labels`: der Punktestand trägt die Namen des Duell-Bilds (statt „PUNKT NÄGEL“).

- Ausbau 21.11.2026 (keine offenen `needs` in den Plänen; aufgeräumt wurden die ältesten vorläufigen Zeichnungen und das Studio-Video):
  Bibliothek von Hand neu gezeichnet statt der vorläufigen Fassung: `kaffeebohne` (zwei geröstete Bohnen mit Kerbe; auch „Bohne/Bohnen“), `keule`
  (Holzkeule mit Astknoten und Griffwicklung), `radar` (Radarstation: Häuschen, Gittermast, schräge Schüssel mit Funkwellen – pulsiert; als Bild 8 m,
  steht damit in keinem Zimmer), `pinzette` (offene Stahlpinzette; der Alias „zange“ ist weg), `notenschluessel` (Notenblatt mit Violinschlüssel und
  zwei Noten; auch „Notenschlüssel“, „Notenblatt“, „Notenlinien“), `schwamm` (gelber Küchenschwamm mit grüner Scheuerseite und Schaum), `ohrstöpsel`
  (zwei orange Schaumstoff-Stöpsel am Band, kein Markenname als Alias), `gelnagel` (Fächer bunter Kunstnägel auf einem Ständer statt eines einzelnen
  abgeschnittenen Fingers; ohne den Alias „fingernagel“).
  Entfernt: die vorläufigen Zeichnungen `tattoomaschine`, `nagelfeile`, `tätowiernadel` – dafür gibt es seit dem 20.11. die gezeichneten Requisiten
  `tattoomachine` und `nailfile`, die die Figur im Studio in der Hand hält; die Bibliotheks-Fassungen lagen zusätzlich am Boden. „Gel“ ist ein Stoff,
  kein Ding (`main.NO_THINGS`); „Nagelgel“, „UV-Gel“, „Aufbaugel“ zeigen das Fläschchen `nailpolish`.
  Noch offen (vorläufige Zeichnungen der Text-KI): tarantel (Alias „spinne“ – gehört als Wesen gezeichnet), insekt, erdloch (Alias „loch“ zu weit),
  kunststoffbecken (Alias „becken“ zu weit), nachricht (Briefumschlag bei jedem „Nachricht“), zigarette, ohr (Körperteil allein im Bild).
  Offene Wünsche ohne Zeichnung: raum, polyp, knie, anwaltstitel, toplitzsee, miete, algorithmus, statistik, musik, knall, friteuse, dach, hand,
  handfläche, steuererklärung (greifbar davon: polyp, friteuse, dach, steuererklärung).

- Ausbau 23.11.2026 (13-Uhr-Termin „3 Zeichen, dass deine Situationship in dich verliebt ist“: raum; dazu die vorläufigen Zeichnungen aus dem
  Smartphone-1800- und dem Telefon-Video): „Raum“ ist kein Ding (`main.NO_THINGS`: raum, räume) – jede Szene spielt in einem Raum, „Die Augen
  suchen dich im Raum“ braucht keine Zeichnung; der Plan ist damit nicht mehr blockiert.
  Bibliothek von Hand neu gezeichnet statt der vorläufigen Fassung: `kutsche` (rote Reisekutsche mit Speichenrädern, Kutschbock, Laterne und einem
  braunen Pferd an der Deichsel; auch Pferdekutsche, Postkutsche, Droschke – der Alias „wagen“ ist weg: „der Wagen bremst“ meint ein Auto),
  `funkmast` (rot-weißer Gittermast mit drei Sektor-Antennen, Richtfunk-Schüssel und Funkwellen; als Bild 15 m, damit die Spitze im Bild bleibt;
  auch Mobilfunkmast, Sendemast, Antennenmast), `steckdose` (weiße Wandsteckdose von vorn), `mikrofon` (Studiomikrofon mit Korb und Bügel auf
  Tischfuß; ohne den englischen Alias „mic“), `schädel` (Schädel von vorn; Totenkopf, Totenschädel – „Schädelknochen“ bleibt beim Schaubild
  `voice`), `fotoapparat` (Kamera von vorn mit großem Objektiv, ohne Vorbild-Modell; auch Kamera, Spiegelreflexkamera), `erdloch` (Loch im Boden
  mit Aushub-Hügel und Spaten; Grube – der Alias „loch“ ist weg). Selbsttest: `_ausbau2311`.
  Noch offen (vorläufige Zeichnungen der Text-KI): kunststoffbecken (Alias „becken“ zu weit; für den Krebs gibt es das Becken `tank`), ohr
  (Körperteil allein im Bild). Offene Wünsche ohne Zeichnung: polyp, knie, anwaltstitel, toplitzsee, miete, algorithmus, statistik, musik, knall,
  friteuse, dach, hand, handfläche, steuererklärung (greifbar davon: polyp, friteuse, dach, steuererklärung). Aus dem 1800-Video fehlen weiter
  Kerker, Marktstände und eine Kirche der Zeit; das Pferd gibt es bisher nur an der Kutsche, nicht als eigenes Wesen.
