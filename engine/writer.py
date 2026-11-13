"""Themenfindung (auch aus aktuellen Trends) und Drehbuch mit Titel, Beschreibung, Tags und Thumbnail-Idee."""
import datetime as dt
import os
import re

from . import ai, trends
from .state import VIDEOS, cfg


def audience():
    return str(cfg("audience") or "").strip()

SYSTEM = """Du schreibst virale deutsche Kurzvideos (YouTube Shorts / TikTok) im Stil animierter Cartoon-Erklärvideos.
Regeln für die Sprechertexte:
- Der erste Satz ist ein starker Hook (Frage, überraschende Behauptung oder Konflikt) – keine Begrüßung, kein "Heute erkläre ich".
- Gesprochene, einfache Sprache, kurze Sätze, Du-Ansprache erlaubt. Zahlen ausschreiben, wie man sie spricht.
- Keine Emojis, keine Regieanweisungen, keine Klammern im Sprechertext.
- Der letzte Satz ist eine Pointe oder Wendung, gern mit kurzer Aufforderung wie "Folg für mehr".
- AUFBAU WIE BEI ERFOLGREICHEN SHORTS – durchdacht, nicht aneinandergereiht:
  1. Hook in höchstens drei Sekunden – IMMER das Thema kurz und spannend nennen, mit Cliffhanger:
     Satz 1 (höchstens zwölf Wörter) sagt, worum es geht, und macht es unwiderstehlich: was daran unmöglich, verboten, gefährlich,
     verrückt oder überraschend ist. Beispiele: „Drei Tier-Superkräfte, die eigentlich unmöglich sind.“ · „Dieses Tier überlebt
     sogar im Weltall.“ · „Was passiert, wenn du eine Woche nicht schläfst?“ · „Mein KI-Agent hat gerade gekündigt.“ (Ich-Geschichte).
     Bei Listen die Anzahl nennen. Nicht den Titel wörtlich vorlesen, nicht mit „Was wäre, wenn“, „Stell dir vor“, „Heute“,
     „In diesem Video“ oder „Wusstest du“ beginnen.
     Satz 2 ist der Cliffhanger: ein offenes Versprechen, das erst später eingelöst wird („Und die letzte kann dir sogar das Leben
     retten.“ · „Aber ab Tag drei wird es richtig gefährlich.“) – bei Listen kommt das Beste zuletzt. Natürlich formuliert, nicht
     marktschreierisch, keine falschen Versprechen: Was der Einstieg verspricht, kommt im Video auch vor.
  2. Roter Faden mit „aber“ und „also“: Jede Szene folgt aus der vorigen – Problem, Folge, neue Wendung. Keine losen Fakten
     hintereinander („und dann … und außerdem …“). Der Zuschauer soll bei jedem Satz wissen wollen, was als Nächstes passiert.
  3. Höhepunkt in der Mitte: die verblüffendste Zahl, der größte Schreck oder der beste Witz – danach kurz Luft holen lassen.
  4. Schluss löst das Versprechen aus dem Hook ein (Auflösung, Pointe) – kurz, ohne Zusammenfassung. Am besten passt der letzte
     Satz so, dass das Video von vorn wieder Sinn ergibt.
- LISTEN („Drei Dinge, die …“): genau so viele Punkte wie im ersten Satz angekündigt, höchstens fünf. Jeder Punkt bekommt zwei bis
  vier Sätze: was passiert, warum, welche Folge oder welcher Witz daraus entsteht. Niemals zehn oder zwanzig Punkte mit je einem Satz
  herunterzählen. Nur der erste Satz eines Punkts darf mit „Nummer zwei“/„Zweitens“ beginnen – nicht jeder Satz mit „Erster …:“, „Zweiter …:“.
  Jeder Satz muss für sich Sinn ergeben und zum Thema gehören; lieber ein Punkt weniger als ein Satz, den niemand versteht.
- Lehrreich UND unterhaltsam: In jedem Video stecken mindestens drei handfeste, überprüfbare Dinge, die man danach weiß
  (Zahl, Ursache, Vergleich aus dem Alltag: „so schwer wie zwei Autos“). Kein Füllsatz, keine Wiederholung, keine Floskel.
- So wenige Wörter wie möglich: ein Gedanke pro Satz. Was das Bild zeigt, muss der Sprecher nicht beschreiben – das Bild erzählt
  dazu, was der Satz nicht sagt (Reaktion, Folge, Größenvergleich).
- Alle drei bis vier Sekunden ändert sich sichtbar etwas: neue Einstellung, neue Handlung, Grafik oder Großaufnahme.
  Jede Szene ist EIN kurzer Satz (höchstens 14 Wörter). Kein Satz darf ein Bild brauchen, das länger als fünf Sekunden steht.
- NIEMAND DARF SICH LANGWEILEN: Jede Szene bringt etwas Neues (Zahl, Wendung, Folge, Witz) – keine Wiederholung, keine Überleitung
  ohne Inhalt („Aber das ist noch nicht alles“ ist verboten). Offene Fragen und kleine Ankündigungen halten die Spannung
  („… und dann wird es richtig seltsam“), aber höchstens zweimal pro Video. "highlight" nennt das Wort, bei dem die Kamera auf die Figur springt.
- Inhaltlich korrekt bleiben: nichts als Tatsache ausgeben, was erfunden ist. Bei aktuellen Themen nur das verwenden,
  was in den mitgelieferten Schlagzeilen steht oder allgemein bekanntes Hintergrundwissen ist; keine erfundenen Details,
  Zitate oder Zahlen. Lieber den zeitlosen Hintergrund erklären als Gerüchte wiedergeben.
- GEDANKENSPIELE („Was wäre, wenn …“) bleiben echte Wissenschaft: Beschreibe nur Folgen, die sich aus Physik, Biologie oder Technik
  wirklich ergeben, in der richtigen Größenordnung und im genannten Zeitraum (in fünf Sekunden kocht kein Ozean und zerbricht keine
  Erdkruste). Lieber wenige, richtig erklärte und überraschende Folgen mit Ursache („weil …“) als erfundenes Weltuntergangs-Spektakel.
  Keine ausgedachten Zahlen: Nenne eine Zahl nur, wenn sie stimmt oder sich einfach nachrechnen lässt – auch in Einblendungen und Zählern.
  Ist etwas unsicher, sag das offen („vermutlich“, „wahrscheinlich“). Erfinde keine Studien, Forscher-Aussagen, Schadenssummen oder Opferzahlen.
  Einblendungen und Grafiken zeigen genau die Zahl und Aussage des Satzes, zu dem sie gehören – nichts anderes.
- Sauberes Deutsch: Jeder Satz wird vor der Abgabe auf Rechtschreibung und Grammatik geprüft (Einzahl/Mehrzahl, Fälle, keine Tippfehler).
- Ton für eine junge TikTok-Zielgruppe: locker, direkt, selbstbewusst, gern mit aktueller Umgangssprache, aber nicht cringe
  oder übertrieben jugendlich. Nie belehrend, nie wie für Kinder.
- Erfundene Geschichten (Grusel, Lustiges) klar als Geschichte erzählen ('Stell dir vor …', 'Eine Legende erzählt …'):
  keine erfundenen 'echten' Ereignisse, Trends, Apps, Studien oder Personen als Tatsache ausgeben, und keine Titel wie 'Die Wahrheit über …' dafür.
- Keine Videos über einzelne echte Personen (auch keine Promis): nimm das allgemeine Thema dahinter.
- Nenne im Sprechertext, in Titel, Beschreibung und Einblendungen KEINE Marken-, Firmen-, Produkt- oder App-Namen, auch nicht als
  Beispiel. Umschreibe sie allgemein („ein großer Online-Händler“, „ein Videoportal“, „ein bekannter Autobauer“, „ein Chatbot“).
- Schreibe immer echte Umlaute und ß (ä, ö, ü, ß) – niemals ae, oe, ue oder ss als Ersatz, auch nicht in GROSSBUCHSTABEN.
- ALLES auf Deutsch: Sprechertext, Titel, Beschreibung, Titelbild-Text, Orts-/Zeitangaben und jeder Text in Einblendungen
  (Karten, Notizen, Listen, Handy, Balken, A/B-Frage). Keine englischen Wörter oder Gaming-Begriffe wie "Inventory", "Level",
  "Boss", "Respawn", "Fact" – nimm das deutsche Wort (Liste, Stufe, Chef, Fakt). Erlaubt sind nur Eigennamen und Wörter,
  die im Deutschen ganz normal sind (Handy, Internet, App). Deutsche Einheiten und Schreibweise (Liter, Meter, Grad).
- Sprechertext zum Vorlesen schreiben: Zahlen und Einheiten ausschreiben ("dreißigtausend Grad", "zwanzig Prozent"),
  keine Abkürzungen, Klammern, Emojis oder Sonderzeichen; kurze, klare Sätze. In Einblendungen dürfen Ziffern stehen.
- Keine Beleidigungen, nichts Anzügliches, keine echten Privatpersonen, keine Marken- oder Filmfiguren im Bild.
- Baue Themen nie um urheberrechtlich geschützte Figuren, Filme, Serien, Spiele oder Marken (z. B. Godzilla, Pokémon,
  Marvel, Disney, Minecraft). Nimm stattdessen eigene, namenlose Wesen oder echte Natur/Wissenschaft (z. B. 'ein 100 Meter großes Monster').
HUMOR – jedes Video ist auch unterhaltsam (in Comedy und Lustigem stark, in Grusel und ernsten Storys nur ein Augenzwinkern):
- Mindestens zwei Lacher pro Video: trockene Untertreibung („Das war … suboptimal.“), Übertreibung mit Zahl („achtundvierzig Tabs“),
  ein Running Gag, der zweimal wiederkommt und beim dritten Mal kippt, oder eine Figur/ein Ding, das plötzlich Gefühle hat.
- Pointe kommt am Satzende, kurz und ohne Erklärung. Kein Witz auf Kosten von Gruppen, keine Beleidigungen, nichts Anzügliches.
- Bild und Text spielen zusammen: Der Satz sagt das eine, die Figur reagiert sichtbar (Gefühl, Symbol, Sprechblase mit 1–2 Wörtern).
Regeln für die Bild-Prompts (Englisch):
- Beschreibe exakt eine Szene: wer/was, Pose, Gesichtsausdruck, Ort, Blickwinkel. Hauptmotiv mittig.
- Keine Schrift im Bild. Keine bekannten Figuren, Marken oder realen Personen (auch nicht bei Trend-Themen: stelle sie symbolisch dar).
- Lege wiederkehrende Figuren in "cast" und wiederkehrende Orte in "places" EINMAL genau fest und nutze sie in vielen Szenen –
  so sieht das Video aus wie aus einem Guss (gleiche Figur, gleiches Zimmer). Wenige Orte (1–3), wenige Figuren (1–2).
- Erzählstil wie erfolgreiche Erklär-Shorts: oft aus Sicht einer Figur oder in Du-Perspektive ('Du wachst auf …'), mit Spannung.
Antworte ausschließlich mit JSON."""

FORMAT = """Gib JSON in genau diesem Format zurück:
{
  "title": "kurzer, neugierig machender Titel mit dem wichtigsten Suchbegriff vorne (max. 70 Zeichen, ohne Hashtags, ohne Clickbait-Lügen)",
  "description": "Beschreibung wie bei erfolgreichen Shorts, in Du-Form, 3 kurze Zeilen mit \\n getrennt: Zeile 1 = starker Aufhänger (Frage oder verblüffende Behauptung, höchstens 90 Zeichen, enthält den wichtigsten Suchbegriff, 1 passendes Emoji) · Zeile 2 = was im Video passiert, konkret und spannend, ohne die Auflösung zu verraten · Zeile 3 = eine einfache Entweder-oder-Frage für die Kommentare. Verboten sind lahme Einstiege wie 'Erfahre', 'In diesem Video', 'Wir blicken auf', 'Wir zeigen' und jedes Wir.",
  "hashtags": ["#shorts", "… 5–8 passende Hashtags: was auf TikTok gerade läuft (auch englische wie #fyp oder #viral, wenn passend) plus spezifische deutsche"],
  "tags": ["8–15 Suchbegriffe ohne #, z. B. 'spinnen im haus', 'tierfakten'"],
  "thumbnail": {"image": "English prompt for ONE eye-catching cover image: the most surprising moment of the story, close-up, exaggerated facial expression, bold simple composition, strong contrast, empty space in the upper third for text",
                "text": "2–4 deutsche Wörter Cover-Text in GROSSBUCHSTABEN, macht neugierig, verrät die Auflösung nicht"},
  "cast": {"held": "English description of each recurring character (species/body, colors, clothes, face) – identical in every scene"},
  "places": {"zimmer": "English description of each recurring location (room/landscape, colors, key objects)"},
  "hud": "optional: kurze Orts-/Zeitangabe oben links für Geschichten, z. B. 'TAG 1 · 3:12 UHR' – sonst leerer String",
  "countdown": "optional: nur bei Wettlauf gegen die Zeit {\"label\": \"EINSCHLAG IN\", \"seconds\": 900}, sonst null",
  "scenes": [
    {"text": "Sprechertext dieser Szene (1–2 kurze Sätze)",
     "image": "English: ONLY action, pose, facial expression and camera framing of this scene (who/where comes from cast/places)",
     "who": ["held"],
     "place": "zimmer",
     "camera": "zoom_in | zoom_out | pan_left | pan_right | pan_up | shake | still",
     "sfx": "whoosh | pop | boom | ding | tick | none",
     "highlight": ["1–2 Schlüsselwörter aus dem Sprechertext, die wichtig sind"],
     "hud": "optional: neue Orts-/Zeitangabe ab dieser Szene, sonst weglassen",
     "status": "optional, nur bei Geschichten ohne countdown: Zustands-Anzeige oben rechts als 'WORT: WERT', z. B. 'SEIL: LÄUFT', später 'SEIL: STEHT' oder 'WIND: 96 KM/H' – gilt weiter bis zur nächsten Angabe",
     "overlay": null}
  ]
}
Einblendungen (overlay) – nutze sie in etwa jeder zweiten Szene, passend zum Inhalt, sonst null:
- {"type": "card", "text": "1–3 WÖRTER"}  große Infokarte: Zahl, Fakt, Warnung (z. B. "VIERMAL HELLER", "-80 °C")
- {"type": "tag", "text": "HEILIGABEND"}  kleines Schild, das Ort, Zeit oder das Ding der Szene benennt (1–3 Wörter, z. B. "AUGUST 1914",
  "DER GRUND", "100 METER", "POST AUS DER HEIMAT") – gern alle 2–3 Szenen, wenn keine andere Einblendung passt
- {"type": "thermo", "value": 22}  Thermometer mit Gradzahl – bei jeder Temperatur (auch minus)
- {"type": "stamp", "text": "VERBOTEN", "color": "red|green|orange|purple"}  Stempel für ein Urteil: VERBOTEN, GIFTIG, GRATIS, PLEITE, REKORD …
- {"type": "note", "title": "REGEL #2", "text": "kurzer Merksatz"}  Notizzettel für Regeln, Tipps, Merksätze
- {"type": "phone", "title": "3:12", "items": ["Mama: Wo bist du??", "Warnung: Bleib drinnen"]}  Handy mit Nachrichten/Alarmen
- {"type": "checklist", "title": "SPEISEKARTE", "items": [["Motten", true], ["Fliegen", true], ["Käfer", false]]}  Listen, Vergleiche
- {"type": "bar", "label": "WASSER", "value": 24}  Füllstand/Prozent/Energie
- {"type": "counter", "label": "ZUCKER IM SEE", "value": 4.4, "unit": "MRD. TONNEN", "sub": "= 23 JAHRE WELTPRODUKTION"}
  großer Zähler, der hochläuft – für jede beeindruckende Zahl (Menge, Jahre, Grad, Euro, Menschen); "sub" ist optional
- {"type": "choice", "a": "Im Bunker bleiben", "b": "Zu Mama rennen"}  NUR in der letzten Szene von Geschichten: Was würdest du tun?
Kamera: 'shake' bei Schreck/Aufprall (mit sfx 'boom'), sonst ruhige Fahrten; sfx sparsam (nicht in jeder Szene)."""

TOON = """
EIGENE ANIMATION: Das Video wird mit fertigen Cartoon-Figuren, Tieren, Orten und Requisiten animiert (keine KI-Bilder).
Fülle deshalb zusätzlich aus und nutze NUR die genannten Werte:
- "cast": Aussehen je Figur, z. B. {"mia": {"shirt": "blau", "hat": "", "hair": "long", "glasses": false, "skin": "weiß"},
                                   "rex": {"kind": "dino"}}
  Menschen: shirt/hat_color: blau, rot, grün, gelb, orange, lila, pink, türkis, grau, braun · hat: cap, helmet, beanie, bow, crown oder ""
            hair: long, bun oder "" (kurz) · hair_color: braun, dunkelbraun, schwarz, blond, rot, grau · skin: weiß, hell, mittel, dunkel
            (gib jeder Figur eine andere Kombination aus Pulli-, Haarfarbe und Frisur, damit man sie sofort auseinanderhält)
  Tiere/Wesen statt Mensch: "kind": cat, dog, spider, ghost, alien, robot, bird, dino, monster, fish, shark, bee, wasp
  Meerestiere: shrimp (Pistolenkrebs, Garnele, Krebs – die Knallschere schnappt zu), mantis (Fangschreckenkrebs – schlägt mit der Keule), jelly (Qualle),
  axolotl (rosa Schwanzlurch mit Kiemenästen) · überall: tardigrade (Bärtierchen).
  Wildtiere an Land und in der Luft: cheetah (Gepard – action "run" = Galopp), eagle (Adler, fliegt), flea (Floh – action "jump" = springt hoch).
  Nennt der Satz Gepard, Adler oder Floh, zeigt die Regie das Tier von selbst groß und allein im Bild.
  Sie spielen am Ort underwater; nie monster oder fish als Ersatz für ein Tier nehmen, das es hier gibt.
  sowie Begriffe als Figur mit Gesicht: agent (KI, Bot, Assistent – oranges Kästchen), virus (Virus, Bakterie, Erreger), cell (Zelle),
  brain (das Gehirn als rosa Figur – für Sätze wie „dein Gehirn schlägt Alarm“; Kennung z. B. "gehirn").
  Für Comedy: Dinge und Begriffe als Figuren mit eigenem Willen einsetzen, die reagieren, streiken, sich freuen oder beleidigt sind
  Höchstens 3 Figuren, jede klar unterscheidbar. Bei Du-Geschichten ist die Hauptfigur „du“.
- BILDPLAN ZUERST: Überlege bei jeder Szene, bevor du sie ausfüllst: Was genau sieht der Zuschauer, während dieser Satz gesprochen wird?
  Schreib das als erstes Feld "see" auf (ein deutscher Satz: wer, wo, was passiert) und fülle Ort, Requisiten und Figuren danach genau so aus.
  Das Bild zeigt immer das, wovon der Satz handelt – nicht bloß das Thema des Videos. Redet der Satz von Kellern, sieht man einen Keller
  (ohne Passanten); redet er von Panik, rennen Menschen; redet er von einer Zahl, kommt eine Grafik.
- KEIN LEERES BILD: In mindestens jeder zweiten Szene steht eine Figur in "actors", die erlebt, wovon der Satz spricht. Ein leeres Zimmer
  oder eine leere Wiese ist nie eine Szene. Auch bei Tier- und Naturthemen gibt es eine menschliche Hauptfigur (z. B. "du"), die reagiert.
- Tiere erscheinen in echter Größe: Eine Spinne, Biene oder Katze ist neben Menschen klein. Soll man sie gut sehen, zeig sie als
  "shot": "insert" groß und allein. Setz dasselbe Tier nicht in jede Szene in die Mitte – zeig, was es auslöst.
- Passanten ("crowd") gibt es nur dort, wo wirklich Menschen unterwegs sind: Stadt, Dorf, Park, Strand, Bahnhof, Supermarkt, Krankenhaus,
  Büro, Schule. Nicht auf dem Feld, im Wald, im Keller oder in der Wüste.
- In jeder Szene:
  "place": drinnen: bedroom, livingroom, kitchen, bathroom, office, classroom, lab, hospital, basement, supermarket,
           supermarket_empty (leergekaufte Regale), station (Bahnhof), restaurant, cave, underwater, space,
           germany (Deutschlandkarte), worldmap (Weltkugel), hallway (Flur mit Türen: Hotel, Wohnhaus), attic (Dachboden),
           serverroom (Rechenzentrum mit Serverschränken – für Internet, Cloud, KI, Rechenleistung)
           draußen: headquarters (Büroturm einer großen Firma in der Stadt – für Konzerne, Firmensitze; ohne Logo), street (Häuserzeile mit Läden und Straße), park, forest, beach, desert, snow, mountain, farm, village,
           gasstation, powerplant, graveyard, ruins, camp (Zelte), moon, church, lake, river, fields, landfill (Müllhalde)
           (genau eines dieser Wörter – jede Szene braucht einen Ort aus dieser Liste, auch Ereignis-Einstellungen)
  "backdrop": für Landschaften draußen statt "place" – ein Baukasten, mit dem JEDE Umgebung passend gebaut wird:
           {"sky": "day|night|sunset|storm|red|haze", "ground": "grass|sand|snow|road|rock|soil|dry|water|ice|lava",
            "elements": [bis zu 4 aus: mountains, hills, dunes, forest, trees, deadtrees, palms, cactus, city (Skyline),
                         street (Häuserzeile), village, ruins, factory, powerplant, farm, gasstation, bridge, powerlines,
                         windturbines, camp, graves, sea, glacier, fields, river, dryriver, lake, cracks, rocks, flowers,
                         asphalt (aufgerissene Fahrbahn mit hochgedrückten Platten – für Asphalt, kaputte Straßen)]}
           Beispiele: Wald mit Fluss = {"elements": ["forest", "river"]} · Dürre = {"sky": "haze", "ground": "dry",
           "elements": ["deadtrees", "dryriver"]} · Bauernhof = {"elements": ["farm", "fields"]} · zerstörte Stadt =
           {"sky": "red", "ground": "road", "elements": ["ruins"]} · Bergsee = {"elements": ["mountains", "lake", "flowers"]}
  DER HINTERGRUND MUSS ZUM SATZ PASSEN: Redet der Sprecher vom Wald, ist ein Wald zu sehen; bei Flüssen ein Fluss, bei Ernte
  ein Feld, beim Meer das Meer. Nimm "street" nur, wenn es wirklich um die Stadt geht – nie als Verlegenheitslösung.
  Wechsle den Hintergrund, sobald der Text den Schauplatz wechselt.
  "time": "day" oder "night"
  "weather": rain, storm, snow, wind (Sturm, Orkan), heat, dark, ash (Ascheregen), quake (Erdbeben: Bild wackelt), steam (Dampf steigt auf) oder ""
  "props": 0–2 Requisiten. Alle Dinge erscheinen automatisch in echter Größe im Verhältnis zu den Menschen.
           Dinge: car, bus, truck, bike, house, tree, rock, box, cart (Einkaufswagen), shelf (Regal), fridge, table, tv, computer,
                  money, cans (Konserven), canister, candle, generator, tent, fire, streetlamp, trafficlight, rocket, sprout,
                  door, clock, pile (wachsender Haufen: Zucker, Salz, Schnee), sandpile, trash, faucet (Wasserhahn), glass, barrel,
                  solarpanel, cctv (Überwachungskamera am Mast)
           Himmel/Natur (Schaubilder, groß): drone (Drohne mit Kamera), plane, satellite, ship, ufo, meteor, explosion, earth, sun, moon, tornado, wave,
                  flood, ice, volcano, cloud, stormcloud, lightning, crack, smoke, aurora, eclipse
           (meteor fällt und schlägt ein, rocket startet, wave/flood steigen, crack reißt den Boden auf, eclipse verdunkelt
            die Sonne, sprout wächst zur Blume, volcano spuckt Lava)
           Nimm nur Requisiten, die an diesen Ort gehören (kein Karton mitten auf der Straße als Ersatz für einen Supermarkt –
           dafür gibt es den Ort "supermarket").
  "actors": 1–2 Figuren, z. B. [{"id": "mia", "action": "run", "emotion": "scared", "emote": "!", "pos": "offleft", "to": "center", "speaks": true}]
     action: idle, talk, walk, run, wave, point, shocked, sad, jump, think, sit, sleep, dance, look_around, fall, shake (schüttelt aus, was sie hält – NICHT für Kopfschütteln, dafür idle),
             float (schwebt schwerelos in der Luft – dann schweben auch die Dinge aus "props" mit; für Sätze über Schweben, Abheben, fehlende Schwerkraft)
     hold (optional): was die Figur in der Hand hält – phone, flashlight, bag, bottle, umbrella, sign, map, radio oder jeder kleine Gegenstand
          aus "props"/"wishes" (z. B. "schuh", "glass", "candle")
     HANDLUNG STATT GEGENSTAND: Beschreibt der Satz, dass jemand etwas mit einem Ding tut (Schuhe ausschütteln, Kerze halten, Glas heben),
     dann zeig eine Figur, die genau das tut ("hold" plus passende "action") – nicht den Gegenstand allein als "insert".
     emotion: happy, sad, angry, scared, worried, shocked oder ""
     emote (Symbol über dem Kopf, sparsam): "!", "?", heart, idea, sweat, anger, music oder ""
     say (optional, selten): Sprechblase mit ein, zwei Wörtern, die die Figur gerade sagt, z. B. "PSST." oder "LAUF!" – höchstens 14 Zeichen
     pos / to: left, center, right, offleft, offright ("to" nur wenn die Figur sich bewegt)
     speaks: true bei der Figur, um die es in dieser Szene geht
     hold (optional, Gegenstand in der Hand): phone, flashlight, bag, bottle, umbrella, sign, map, radio
     Die Gefühle müssen zum Satz passen: niemand ist erschrocken oder panisch, wenn der Satz ruhig oder sachlich ist.
  "crowd": Menschen im Bild, die die Stimmung zeigen (draußen und in Supermarkt, Bahnhof, Krankenhaus, Büro, Schule):
           "walk" (Alltag, Leute gehen vorbei), "worried" (stehen unruhig, sehen sich besorgt um), "panic" (rennen in Panik
           durcheinander – NUR wenn der Satz wirklich von Panik, Flucht oder Schreien handelt), "cheer" (jubeln),
           "sad" (stehen gebeugt), "watch" (staunen, zeigen) oder ""
  "mood": Stimmung der Szene als Farbe/Wirkung: "calm", "tense", "panic", "scary", "sad" oder "happy" – genau so stark wie
          der Satz. Die meisten Szenen sind "calm" oder "tense"; "panic" höchstens in ein bis zwei Szenen am Höhepunkt.
          Sachliche Erklärungen sind "calm".
  JEDE SZENE BRAUCHT SICHTBARE BEWEGUNG: Figur, die etwas tut, eine Menschenmenge, animierte Requisite oder Wetter.
  Kein leeres Standbild.
  "shot": "event" = Ereignis-Einstellung: das Geschehen (Requisiten, Wetter, Ort) füllt das Bild, "actors" ist [] oder
          höchstens eine kleine Figur am Rand, die zuschaut · "close" = Nahaufnahme einer Figur (selten, nur bei starker
          Reaktion) · "graphic" = bewegte Grafik (siehe unten) · "insert" = ein einzelner Gegenstand aus "props" groß und allein im Bild, wenn der Satz genau von
          diesem Ding handelt (z. B. Kühlschrank, Kerze, Konserven) · sonst "wide"
- WICHTIG – das Thema zeigen, nicht die Figur: Die Figuren sind Nebensache und klein im Bild. Immer wenn der Sprecher über
  Natur, Wetter, Weltall, Katastrophen, Tiere oder ein Phänomen redet, nimm "shot": "event" mit passenden Requisiten, Wetter
  und Ort (z. B. Vulkanausbruch: place mountain, props ["volcano","smoke"], weather "ash", actors []). Bei Natur-,
  Wissens- und What-If-Themen ist mindestens jede zweite Szene eine Ereignis-Einstellung. Figuren zeigen nur kurz die
  Reaktion oder die Folgen für Menschen.
- BEWEGTE GRAFIKEN ("shot": "graphic" plus "graphic": {...}, ohne Figuren) für Zahlen, Fristen und Fragen – 2 bis 4 pro Video:
    {"type": "number", "kicker": "SCHWEDEN · NOV. 2024", "value": "5 MIO.", "label": "HAUSHALTE"}   große Zahl läuft hoch
    {"type": "timer", "value": "72:00:00", "kicker": "SO LANGE BIST DU ALLEIN"}                      Countdown läuft herunter
    {"type": "calendar", "kicker": "VORRAT FÜR", "value": "3", "label": "TAGE"}                      Kalenderblatt
    {"type": "question", "text": "WARUM?"}                                                           großes Fragezeichen mit Strahlen
    {"type": "houses", "value": "45.000", "label": "HAUSHALTE", "dark": true}                        Häuserreihen, Fenster gehen aus (dark) oder an
    {"type": "badge", "kicker": "MIND.", "text": "72 STUNDEN"}                                       Plakette im Sternenkranz
    {"type": "map", "text": "72 STUNDEN ALLEIN", "value": "sweden,germany"}                          Europakarte; value = betroffene Länder aus:
        iberia, france, uk, ireland, benelux, germany, alps, italy, poland, czech, balkans, denmark, norway, sweden, finland, baltics, east
    {"type": "city", "kicker": "BERLIN · JANUAR", "text": "45.000 OHNE STROM", "dark": true}         Stadt von oben, Fenster gehen aus (dark)
    {"type": "share", "value": "1 VON 7", "label": "TRÄUMT DAVON"}                                   Reihe von Menschen, der Anteil leuchtet auf (höchstens „von 12“)
    {"type": "compare", "left": "DOSE", "right": "KAFFEE", "value": "80 mg", "sub": "180 mg"}        zwei Balken wachsen um die Wette (value links, sub rechts)
    {"type": "podium", "kicker": "KÖRPERTEILE", "text": "FUSS", "left": "HAND", "right": "BEIN"}     Siegertreppchen: text = Platz 1, left = Platz 2, right = Platz 3
    {"type": "news", "kicker": "TALBLATT", "text": "GONDEL 7 ABGESTÜRZT", "sub": "Unglück im Nebel"}  Zeitungsseite fliegt herein – für Rückblicke und
                                                                                                     Enthüllungen; kicker = erfundener Zeitungsname, nie eine echte Zeitung
    {"type": "pulse", "value": "1", "label": "EINE SEKUNDE"}                                         Herzschlag-Linie mit rotem Pochen – der Moment, in dem alles stillsteht
    {"type": "radio", "kicker": "FUNK · KANAL 4", "text": "BERGWACHT"}                               Funkspruch oder Durchsage mit Wellenform
    {"type": "chart", "kicker": "AKTIENKURS", "value": "3 BIO.", "label": "DOLLAR"}                   Kurve schießt nach oben ("dark": true = stürzt ab) – für Kurse,
                                                                                                     Umsatz, Wachstum, Nachfrage; value/label nur, wenn der Sprecher die Zahl nennt
    {"type": "distance", "value": "100 m", "left": "IHR", "right": "ZIEL"}                           Entfernung als Messlinie zwischen zwei Punkten
    {"type": "days", "text": "30 TAGE ÜBERLEBEN", "value": "1", "sub": "30", "label": "NOCH 2 MINUTEN"}  Monatskalender: heute ist Tag "value" von "sub" (höchstens 35),
                                                                                                     vergangene Tage werden abgehakt – ideal für Geschichten über mehrere Tage, gern mehrmals im Video
    {"type": "phone", "mode": "alert", "kicker": "LIVE · GANZ DEUTSCHLAND", "text": "FANG IHN", "value": "10.000.000 €", "label": "ICH HAB IHN GESEHEN"}
                                                                                                     Handy in der Hand mit Eilmeldung: Schlagwort, Betrag zählt hoch, Knopf
    {"type": "phone", "mode": "lock", "value": "07:49", "kicker": "UNBEKANNT", "text": "Wir wissen, wo du bist."}   Sperrbildschirm mit Uhrzeit, eine Nachricht rutscht herein
    {"type": "phone", "mode": "chat", "kicker": "Oma", "text": "Junge, stimmt das mit den 10 Millionen?", "sub": "Oma, bitte nicht."}
                                                                                                     Nachrichten-Verlauf: text = Nachricht der anderen Person, sub = eigene Antwort
    {"type": "versus", "left": "ENERGY", "right": "KAFFEE", "kicker": "5 RUNDEN"}                    Duell-Bild mit großem VS
    {"type": "round", "kicker": "RUNDE 1", "text": "KOFFEIN"}                                        Banner kündigt die nächste Runde an
    {"type": "score", "left": "ENERGY", "right": "KAFFEE", "value": "0:2", "kicker": "RUNDE 3/5"}    Punktestand nach einer Runde
- DUELL-FORMAT: Vergleicht das Thema zwei Dinge („X oder Y“, „X gegen Y“, „Was ist besser/gesünder/schneller?“), bau das Video als Duell:
  zuerst "versus", dann 3 bis 5 Runden – jede beginnt mit "round", zeigt den Vergleich (gern "compare" mit echten Zahlen) und endet mit
  "score". Am Schluss steht der Sieger fest. Bei „Top 3“ oder „Platz 1“ passt "podium".
- ABWECHSLUNG WIE IN VIRALEN ERKLÄRVIDEOS: Höchstens jede zweite Szene zeigt eine redende Figur. Die anderen Szenen zeigen
  das Geschehen ("shot": "event", actors []), einen Gegenstand groß ("shot": "insert" mit einem Ding aus "props") oder eine
  Zahl als Zähler (overlay "counter"). Das Ding, um das sich das Video dreht, ist mindestens zweimal groß im Bild.
  Für „in ganz Deutschland“ gibt es den Ort "germany" (Karte mit aufleuchtenden Punkten), für „weltweit“ den Ort "worldmap".
- FIRMEN- UND TECHNIK-GESCHICHTEN: Zeig die Stationen der Geschichte, nicht fünfmal dasselbe Büro: Anfang im Zimmer oder Restaurant,
  Firmensitz ("headquarters"), Rechenzentrum ("serverroom"), Kurs oder Wachstum als Grafik ("chart"), das Produkt groß ("shot": "insert").
  Spricht der Satz von mehreren Menschen („drei Gründer“, „zwei Freunde“), stehen so viele Figuren in "actors". Der Weltraum ("space")
  kommt nur vor, wenn der Satz vom Weltall handelt. Keine Firmenlogos, keine echten Personen – Gründer sind neutrale Figuren.
  Zahlen in Einblendungen und Grafiken müssen im Sprechertext derselben Szene vorkommen.
- Wechsle Orte, Aktionen und Requisiten ab: nicht zweimal hintereinander dieselbe Kombination; jede Szene zeigt sichtbar,
  wovon der Sprecher gerade redet (Bewegung statt Herumstehen: reinkommen, rennen, erschrecken, zeigen, springen).
- Erklärendes (Zahlen, Listen, Regeln) kommt in die Einblendungen (overlay).
- "thumbnail": {"text": "2–4 deutsche WÖRTER", "place": "...", "time": "day|night", "actor": "id aus cast", "action": "shocked",
                "emotion": "shocked", "props": ["meteor"], "weather": ""}  – der spannendste Moment als Titelbild,
                am besten mit dem Ereignis (Requisite) groß im Bild.
- "image" je Szene darf leer bleiben.
- "wishes": Liste von einzelnen, greifbaren Gegenständen (deutsch, ein Wort, Einzahl, z. B. "Wasserturm", "Mikroskop"), die
  dieses Video braucht, die aber in den Listen oben fehlen. Die Engine zeichnet sie automatisch nach: Trage das Wort deshalb
  zusätzlich in "props" der passenden Szene ein (genau gleich geschrieben). Keine Orte, kein Wetter, keine Personen, keine Marken.
  Leere Liste, wenn alles da war."""

UNSUITABLE = ("Ungeeignet sind: Themen, die sich um einzelne echte Personen drehen (Promis, Musiker, Sportler, Politiker, Creator), Todesfälle, Unglücke, Verbrechen, Krieg, Terror, Krankheiten einzelner Personen, "
              "Parteipolitik und Wahlen, Klatsch über Privatleben, Glücksspiel, geschützte Film-/Spielfiguren und Marken als Hauptthema, reine Sport-Ergebnisse ohne Hintergrundgeschichte "
              "und alles, was ohne Belege Spekulation wäre.")


def _learned():
    """Gegenstände aus der lernenden Bibliothek – stehen dem Drehbuch wie eingebaute Requisiten zur Verfügung."""
    try:
        from .state import load
        names = sorted(k for k in load("shapes.json", {}) if isinstance(k, str))[:150]
    except Exception:  # noqa: BLE001
        names = []
    return ("\n- Zusätzlich gelernte Requisiten (in \"props\" mit genau diesem Wort nutzbar): " + ", ".join(names)) if names else ""


_UML = [("fuenf", "fünf"), ("zwoelf", "zwölf"), ("dreissig", "dreißig"), ("fuer", "für"), ("ueber", "über"), ("tuer", "tür"), ("oeffn", "öffn"),
        ("waer", "wär"), ("koenn", "könn"), ("moecht", "möcht"), ("muess", "müss"), ("wuerd", "würd"), ("hoer", "hör"), ("schoen", "schön"),
        ("gruen", "grün"), ("frueh", "früh"), ("spaet", "spät"), ("naechst", "nächst"), ("zurueck", "zurück"), ("glueck", "glück"),
        ("stueck", "stück"), ("kuehl", "kühl"), ("fuehl", "fühl"), ("fuehr", "führ"), ("natuerlich", "natürlich"), ("ploetzlich", "plötzlich"),
        ("moeglich", "möglich"), ("gefaehr", "gefähr"), ("erklaer", "erklär"), ("haett", "hätt"), ("laesst", "lässt"), ("faellt", "fällt"),
        ("haelt", "hält"), ("traeg", "träg"), ("schlaef", "schläf"), ("zaehl", "zähl"), ("waehrend", "während"), ("aehnlich", "ähnlich"),
        ("aender", "änder"), ("maedchen", "mädchen"), ("raeum", "räum"), ("geraeusch", "geräusch"), ("schluessel", "schlüssel"),
        ("kueche", "küche"), ("buero", "büro"), ("strasse", "straße"), ("draussen", "draußen"), ("gross", "groß"), ("weiss", "weiß"),
        ("heiss", "heiß"), ("fuss", "fuß"), ("spass", "spaß"), ("naemlich", "nämlich"), ("spuer", "spür"), ("geoeffnet", "geöffnet"),
        ("verschwaend", "verschwänd"), ("taeglich", "täglich"), ("naecht", "nächt"), ("waend", "wänd"), ("haend", "händ"), ("zaehn", "zähn"),
        ("koerper", "körper"), ("groess", "größ"), ("hoeh", "höh"), ("loes", "lös"), ("stoer", "stör"), ("toet", "töt"), ("boes", "bös"),
        ("muede", "müde"), ("kuenst", "künst"), ("wuensch", "wünsch"), ("duenn", "dünn"), ("fluester", "flüster"), ("luege", "lüge"),
        ("pruef", "prüf"), ("rueck", "rück"), ("stuerz", "stürz"), ("schuetz", "schütz"), ("nuetz", "nütz"), ("drueck", "drück"), ("tuerm", "türm")]


BRANDS = {"amazon": "ein großer Online-Händler", "google": "eine Suchmaschine", "apple": "ein Handy-Hersteller", "microsoft": "ein Software-Riese",
          "facebook": "ein soziales Netzwerk", "instagram": "eine Foto-App", "tiktok": "eine Video-App", "youtube": "ein Videoportal",
          "netflix": "ein Streamingdienst", "tesla": "ein E-Auto-Hersteller", "spacex": "eine Raumfahrtfirma", "samsung": "ein Handy-Hersteller",
          "nike": "ein Sportartikel-Hersteller", "adidas": "ein Sportartikel-Hersteller", "mcdonald's": "eine Burgerkette", "mcdonalds": "eine Burgerkette",
          "coca-cola": "ein Limonadenhersteller", "openai": "eine KI-Firma", "chatgpt": "ein Chatbot", "whatsapp": "ein Messenger",
          "snapchat": "eine Foto-App", "twitter": "ein Kurznachrichtendienst", "uber": "ein Fahrdienst", "disney": "ein Filmstudio",
          "ikea": "ein Möbelhaus", "dhl": "ein Paketdienst", "paypal": "ein Bezahldienst", "ebay": "ein Online-Marktplatz", "spotify": "ein Musikdienst",
          "playstation": "eine Spielkonsole", "xbox": "eine Spielkonsole", "nintendo": "ein Spielehersteller", "iphone": "ein Smartphone",
          "bmw": "ein Autobauer", "mercedes": "ein Autobauer", "audi": "ein Autobauer", "volkswagen": "ein Autobauer", "porsche": "ein Autobauer",
          "aldi": "ein Discounter", "lidl": "ein Discounter", "rewe": "ein Supermarkt", "edeka": "ein Supermarkt", "starbucks": "eine Kaffeekette",
          "nvidia": "ein Chip-Hersteller", "geforce": "eine neue Grafikkarte", "intel": "ein Chip-Hersteller", "amd": "ein Chip-Hersteller", "sega": "ein Spielehersteller",
          "denny's": "ein Diner", "dennys": "ein Diner", "fortnite": "ein Videospiel", "minecraft": "ein Videospiel", "huawei": "ein Handy-Hersteller", "sony": "ein Elektronik-Riese",
          "red bull": "ein Energydrink", "temu": "ein Online-Shop", "shein": "ein Online-Shop", "zalando": "ein Online-Shop", "twitch": "ein Streamingportal",
          "marvel": "ein Superhelden-Comic", "pixar": "ein Trickfilmstudio", "pokémon": "ein Sammelspiel", "pokemon": "ein Sammelspiel",
          "lego": "ein Bausteine-Hersteller", "star wars": "ein Weltraum-Film", "harry potter": "ein Zauberer-Film"}
_BRAND_RE = re.compile(r"(?i)(?<![\wäöüß])(?:giganten wie |firmen wie |konzerne wie |unternehmen wie |wie )?(" + "|".join(re.escape(b) for b in sorted(BRANDS, key=len, reverse=True)) + r")(?:s)?(?![\wäöüß])")


def strip_brands(js):
    """Marken- und Firmennamen aus allem Gesprochenen und Eingeblendeten entfernen (allgemeine Umschreibung statt Name)."""
    hit = set()

    def conv(v):
        def rep(m):
            hit.add(m.group(1).lower())
            pre = m.group(0)[:m.start(1) - m.start(0)]
            gen = BRANDS[m.group(1).lower()]
            if pre.lower().endswith("wie "):                      # „Giganten wie X“ → „große Tech-Konzerne“ / „… wie <Umschreibung>“
                return "große Konzerne" if pre.lower() != "wie " else "wie " + gen
            if m.start(0) == 0 or m.string[:m.start(0)].rstrip()[-1:] in ".!?":
                gen = gen[0].upper() + gen[1:]
            return gen.upper() if m.group(0).isupper() and len(m.group(0)) > 3 else gen
        return _BRAND_RE.sub(rep, v)

    def walk(o):
        if isinstance(o, dict):
            return {k: (walk(v) if k not in ("place", "backdrop", "props", "actors", "cast", "sfx", "camera", "shot", "mood", "crowd", "time", "weather", "type", "wishes", "hashtags", "tags") else v) for k, v in o.items()}
        if isinstance(o, list):
            return [walk(v) for v in o]
        return conv(o) if isinstance(o, str) else o
    out = walk(js)
    if hit:
        ai.log("Markennamen im Drehbuch umschrieben: " + ", ".join(sorted(hit)))
    return out


def needed_things(topic, script):
    """Gegenprobe: Welche greifbaren Dinge muss man für dieses Thema im Bild sehen? (kurze Liste deutscher Hauptwörter)"""
    text = " ".join(str(sc.get("text") or "") for sc in script.get("scenes", []) if isinstance(sc, dict))[:1500]
    js, _ = ai.chat_json(
        "Du planst die Bilder für ein kurzes Cartoon-Erklärvideo. Antworte NUR mit JSON: {\"things\": [..]}.",
        f"Thema: {topic}\nSprechertext: {text}\n\nNenne die 3 bis 6 wichtigsten greifbaren Dinge, Tiere oder Orte, die man in diesem Video "
        "unbedingt sehen muss, damit das Thema erkennbar ist – jeweils ein deutsches Hauptwort in der Einzahl (z. B. \"Drohne\", "
        "\"Wasserturm\", \"Mikroskop\"). Keine Gefühle, keine Vorgänge, keine Eigenschaften, keine Menschen, keine Marken.", 0.2)
    return [w.strip() for w in (js.get("things") or []) if isinstance(w, str) and 2 < len(w.strip()) < 30][:6]


def fix_umlauts(js):
    """Manche Ersatz-Modelle schreiben „fuer“, „Tuer“, „oeffnen“. Wenn im ganzen Drehbuch kein einziger Umlaut steht,
    werden die häufigen Wörter zurückverwandelt (nur bekannte Wortstämme, damit „neue“ oder „Feuer“ heil bleiben)."""
    text = " ".join(str(sc.get("text") or "") for sc in js.get("scenes", []) if isinstance(sc, dict))
    if len(text) < 150 or re.search(r"[äöüßÄÖÜ]", text) or not re.search(r"(?i)\b(fuer|ueber|waer|koenn|muess|wuerd|tuer|oeffn)", text):
        return js

    def conv(v):
        for a, b in _UML:
            v = re.sub(a, lambda m, b=b: (b.upper().replace("ß".upper(), "SS") if m.group(0).isupper() else b.capitalize() if m.group(0)[0].isupper() else b), v, flags=re.I)
        return v

    def walk(o, key=""):
        if isinstance(o, dict):
            return {k: (walk(v, k) if k not in ("place", "backdrop", "hashtags", "tags", "props", "actors", "cast", "sfx", "camera", "shot", "mood", "crowd", "time", "weather", "type") else v) for k, v in o.items()}
        if isinstance(o, list):
            return [walk(v, key) for v in o]
        return conv(o) if isinstance(o, str) else o
    ai.log("Drehbuch kam ohne Umlaute – häufige Wörter korrigiert")
    return walk(js)


_ESZETT = [("ausser", "außer"), ("draussen", "draußen"), ("schliesslich", "schließlich"), ("heiss", "heiß"), ("weiss", "weiß"), ("gross", "groß"),
           ("grösst", "größt"), ("grösser", "größer"), ("strasse", "straße"), ("spass", "spaß"), ("fuss", "fuß"), ("füsse", "füße"), ("mass", "maß"),
           ("regelmässig", "regelmäßig"), ("gemäss", "gemäß"), ("mässig", "mäßig"), ("fleissig", "fleißig"), ("süss", "süß"), ("stoss", "stoß"),
           ("stösst", "stößt"), ("schliess", "schließ"), ("reiss", "reiß"), ("beiss", "beiß"), ("giess", "gieß"), ("fliess", "fließ"), ("geniess", "genieß"),
           ("schiess", "schieß"), ("weisst", "weißt"), ("heisst", "heißt"), ("blos", "bloß"), ("gruss", "gruß"), ("grüss", "grüß"), ("dreissig", "dreißig")]
_ESZETT_RE = re.compile(r"\b(?:" + "|".join(sorted({a for a, _ in _ESZETT if a != "blos" and a != "mass"}, key=len, reverse=True)) + r")\w*|\b(?:blos|mass)\b", re.I)
_ESZETT_KEEP = re.compile(r"(?i)^(masse\w*|massiv\w*|massen\w*|massage\w*|grossist\w*|weissag\w*|fussel\w*|strasser|mässigen)$")
_DENGLISH = {"effect": "Effekt", "effects": "Effekte", "fact": "Fakt", "facts": "Fakten", "physics": "Physik", "brain": "Gehirn", "control": "Kontrolle",
             "magic": "Magie", "science": "Wissenschaft", "energy": "Energie", "danger": "Gefahr", "warning": "Warnung", "error": "Fehler",
             "result": "Ergebnis", "the end": "Ende", "logic": "Logik"}
_DENGLISH_RE = re.compile(r"(?<![\w-])(?:" + "|".join(sorted(map(re.escape, _DENGLISH), key=len, reverse=True)) + r")(?![\w])", re.I)


def _case_like(src, rep):
    return rep.upper().replace("ß".upper(), "ß") if src.isupper() and len(src) > 1 else rep.capitalize() if src[:1].isupper() else rep


def fix_eszett(text, upper_ss=False):
    """„Ausser“, „gross“, „Strasse“ → mit ß (häufige Wortstämme; „Masse“, „massiv“ bleiben). In GROSSBUCHSTABEN bleibt SS, wenn upper_ss."""
    def rep(m):
        w = m.group(0)
        if _ESZETT_KEEP.match(w) or (w.isupper() and upper_ss):
            return w
        low = w.lower()
        for a, b in sorted(_ESZETT, key=lambda ab: -len(ab[0])):
            if low.startswith(a):
                out = b + low[len(a):]
                return out.upper().replace("SS", "SS") if w.isupper() else out.capitalize() if w[:1].isupper() else out
        return w
    return _ESZETT_RE.sub(rep, str(text))


def _near(a, b):
    """Unterscheiden sich zwei Wörter nur um einen Buchstaben (eingefügt, gelöscht oder vertauscht)?"""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    lo, hi = (a, b) if len(a) < len(b) else (b, a)
    return any(hi[:i] + hi[i + 1:] == lo for i in range(len(hi)))


def fix_label_typos(label, sentence):
    """Wort einer Einblendung, das sich nur um einen Buchstaben von einem Wort des gesprochenen Satzes unterscheidet („TAGEELANG“ zu
    „tagelang“), ist ein Tippfehler: das Wort aus dem Satz gilt. Echte Beugungen (Tag/Tage, heiß/heißt) bleiben."""
    said = {w.lower() for w in re.findall(r"[A-Za-zÄÖÜäöüß]{6,}", str(sentence or ""))}

    def rep(m):
        w = m.group(0)
        low = w.lower()
        if low in said or low.replace("ss", "ß") in said:
            return w
        hit = [x for x in said if _near(low, x) and x[:3] == low[:3] and x[-2:] == low[-2:]]   # Anfang und Endung gleich: kein anderer Fall, kein anderes Wort
        return _case_like(w, hit[0]) if len(hit) == 1 else w
    return re.sub(r"[A-Za-zÄÖÜäöüß]{6,}", rep, str(label))


def polish(js):
    """Letzter Schliff ohne Text-KI: ß in Sprechertext, Titel und Beschreibung; englische Wörter in Einblendungen und Grafiken
    („GEHIRN-EFFECT“) werden deutsch."""
    for k in ("title", "description"):
        if isinstance(js.get(k), str):
            js[k] = fix_eszett(js[k])
            js[k] = re.sub(r"[ \t]*[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]+", "", js[k]).strip()      # keine Emojis in Titel und Beschreibung
    if isinstance(js.get("description"), str):           # der Kanal spricht den Zuschauer an – kein „Wir zeigen dir“
        js["description"] = re.sub(r"\bWir zeigen(?: dir| euch)?, ", "Hier siehst du, ", js["description"])
        js["description"] = re.sub(r"\bWir zeigen(?: dir| euch)? ", "Hier siehst du ", js["description"])
        js["description"] = re.sub(r"\bWir (?:testen|checken|prüfen|vergleichen|untersuchen|erklären|klären) ", "Hier siehst du ", js["description"])
        js["description"] = re.sub(r"(?i)\b(welches|dein|das|ein) feature\b", lambda m: {"welches": "Welche", "dein": "Deine", "das": "Die", "ein": "Eine"}[m.group(1).lower()] + " Regel", js["description"])
    for sc in js.get("scenes", []):
        if not isinstance(sc, dict):
            continue
        if isinstance(sc.get("text"), str):
            sc["text"] = fix_eszett(sc["text"])
            sc["text"] = re.sub(r"(?i)\b([a-zäöüß]{4,}) \1\b", r"\1", sc["text"])      # „reine reine Fantasie“: versehentlich doppeltes Wort
            sc["text"] = re.sub(r"(?i)(zwei|drei|vier|fünf|sieben|acht|neun)s(hundert|tausend)", r"\1\2", sc["text"])   # „viertausendviershundert“
            sc["text"] = re.sub(r"(?i)\b([a-zäöüß]*tausend) ((?:ein|zwei|drei|vier|fünf|sechs|sieben|acht|neun)hundert)", r"\1\2", sc["text"])   # „viertausend siebenhundert“: eine Zahl
        for box in (sc.get("overlay"), sc.get("graphic")):
            if isinstance(box, dict) and box.get("type") == "counter" and isinstance(box.get("unit"), str):
                box["unit"] = re.sub(r"^\s*[\d.,]+\s*", "", box["unit"])     # „99“ + „99 STÜCK“ stand als „99 99 STÜCK“ im Bild
        for box in (sc.get("overlay"), sc.get("graphic")):
            if isinstance(box, dict):
                for k in _LABEL_KEYS:
                    if isinstance(box.get(k), str):
                        v = re.sub(r"(?i)(?<=[a-zäöü]-)(effects?|facts?)\b", lambda m: _case_like(m.group(0), _DENGLISH[m.group(0).lower()]), box[k])
                        box[k] = fix_eszett(_DENGLISH_RE.sub(lambda m: _case_like(m.group(0), _DENGLISH[m.group(0).lower()]), v), upper_ss=True)
                        box[k] = fix_label_typos(box[k], sc.get("text"))
    th = js.get("thumbnail")
    if isinstance(th, dict) and isinstance(th.get("text"), str):
        th["text"] = _DENGLISH_RE.sub(lambda m: _case_like(m.group(0), _DENGLISH[m.group(0).lower()]), th["text"])
        try:                                             # Zahl im Titelbild, die im Video niemand sagt („NEUNZIG MELONEN“ bei neunundneunzig): Zahl weg
            from .toon import stage as _st
            said = " ".join(str(s.get("text") or "") for s in js.get("scenes", []) if isinstance(s, dict))
            keep = []
            for w in th["text"].split():
                k = w.lower().strip(".,;:!?")
                n = _st._number(k) if k not in ("ein", "eine", "einen", "einem", "einer", "eins", "acht") else None
                if n is not None and not re.search(r"(?<![a-zäöüß])" + re.escape(k) + r"(?![a-zäöüß])", said.lower()) and not _st.spoken_number(n, said):
                    continue
                keep.append(w)
            if keep and len(keep) < len(th["text"].split()):
                th["text"] = " ".join(keep)
        except Exception:  # noqa: BLE001
            pass
    return js


_NUMW = {"zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "sechs": 6, "sieben": 7, "acht": 8, "neun": 9, "zehn": 10}
_ORD = {"erste": 1, "zweite": 2, "dritte": 3, "vierte": 4, "fünfte": 5, "sechste": 6, "siebte": 7, "siebente": 7, "achte": 8, "neunte": 9, "zehnte": 10,
        "elfte": 11, "zwölfte": 12, "dreizehnte": 13, "vierzehnte": 14, "fünfzehnte": 15, "sechzehnte": 16, "siebzehnte": 17, "achtzehnte": 18,
        "neunzehnte": 19, "zwanzigste": 20}
_ORD_RE = re.compile(r"(?i)\b(" + "|".join(sorted(_ORD, key=len, reverse=True)) + r")[rsnm]?\b")
_ORD_START = re.compile(r"(?i)^\s*(?:(?:und|aber|dann)\s+)?(?:(?:der|die|das)\s+)?(?:" + "|".join(sorted(_ORD, key=len, reverse=True))
                        + r")[rsnm]?\s+[\wäöüß-]+\s*[:,.–-]|^\s*(?:nummer|punkt|platz|regel|fakt)\s+\w+\s*[:,.–-]|^\s*(?:erstens|zweitens|drittens|viertens|fünftens)\b")


def list_trouble(js):
    """Stimmt die Aufzählung? Meldet (als kurzen Satz für die Text-KI), wenn mehr Punkte heruntergezählt werden als angekündigt
    („Drei Bugs …“ und dann „Neunzehnter Bug“), wenn mehr als fünf Punkte gezählt werden oder fast jeder Satz mit einer
    Ordnungszahl beginnt – so ein Video ist eine Strichliste ohne Erklärung. Sonst None."""
    texts = [str(s.get("text") or "") for s in js.get("scenes", []) if isinstance(s, dict)]
    if len(texts) < 4:
        return None
    m0 = re.match(r"\W*(?:(?:die|diese|hier sind|das sind|es gibt)\s+)?(" + "|".join(_NUMW) + r"|\d{1,2})\b", texts[0].lower())   # „Drei Bugs, die …“
    said = (_NUMW.get(m0.group(1)) or (int(m0.group(1)) if m0.group(1).isdigit() and 2 <= int(m0.group(1)) <= 10 else None)) if m0 else None
    top = max([_ORD[m.group(1).lower()] for t in texts for m in _ORD_RE.finditer(" ".join(t.split()[:3]))] or [0])   # nur am Satzanfang: „beim dritten Versuch“ zählt nicht
    starts = sum(1 for t in texts if _ORD_START.search(t))
    if said and top > said:
        return f"Der Einstieg kündigt {said} Punkte an, gezählt wird aber bis {top}."
    if top > 5:
        return f"Es werden {top} Punkte heruntergezählt – höchstens fünf, dafür jeder richtig erklärt."
    if starts > max(5, len(texts) // 2):
        return f"{starts} von {len(texts)} Sätzen beginnen mit einer Nummerierung – jeder Punkt braucht zwei bis vier Sätze Erklärung."
    return None


def spoken_words(js):
    return sum(len(str(x.get("text", "")).split()) for x in js.get("scenes", []) if isinstance(x, dict))


def _insight(cat):
    """Was laut Analyse beim Publikum gut ankommt (leer, solange zu wenig Daten da sind oder die Steuerung aus ist)."""
    try:
        from . import insights
        return insights.hint(cat)
    except Exception:  # noqa: BLE001
        return ""


def _past(cat):
    return [v["topic"] for v in VIDEOS if v.get("category") == cat["slug"] and v.get("topic")][-60:]


def _niche(cat):
    """Was bei anderen Kanälen dieser Art gerade gut läuft – als Anregung für die Themenwahl (nicht kopieren)."""
    try:
        from . import niche
        rows = niche.for_category(cat["slug"], 6)
    except Exception:  # noqa: BLE001
        return ""
    if not rows:
        return ""
    return ("\nDiese Themen laufen gerade bei anderen Kanälen dieser Art besonders gut (Aufrufe pro Tag) – nimm eines davon oder ein "
            "verwandtes, das dasselbe Interesse weckt, in eigener Umsetzung:\n- "
            + "\n- ".join(f"{r['title']} ({r.get('per_day', 0)}/Tag)" for r in rows) + "\n")


def new_topic(cat: dict) -> str:
    past = _past(cat)
    user = (f"Kategorie: {cat['name']} – {cat['description']}\n"
            f"Stilvorgabe: {cat['script_style']}\n"
            + (f"Zielgruppe: {audience()}\n" if audience() else "")
            + "Schlage EIN konkretes, neues Thema für ein 60-Sekunden-Short vor, das sehr hohe Neugier weckt "
            "und bei dieser Zielgruppe auf TikTok funktioniert (Thema, über das man in der Bubble redet, oder das man sofort teilen will).\n"
            "Diese Themen gab es schon (nicht wiederholen, auch nicht sehr ähnlich):\n- "
            + ("\n- ".join(past) if past else "(noch keine)")
            + _insight(cat)
            + _niche(cat)
            + '\nAntworte als JSON: {"topic": "…"}')
    js, _ = ai.chat_json("Du bist Redakteur für virale deutsche Kurzvideos. Antworte nur mit JSON.", user, 1.0)
    topic = str(js.get("topic", "")).strip()
    if not topic:
        raise ai.ProviderError("Kein Thema erhalten")
    return topic


def trend_topic(cat: dict):
    """Wählt aus den aktuellen Trends ein Thema, das zur Kategorie passt. Gibt (thema, trend) oder (None, None)."""
    items = trends.current()
    if not items:
        return None, None
    past = _past(cat)
    user = (f"Heute ist {dt.date.today():%d.%m.%Y}. Kategorie: {cat['name']} – {cat['description']}\n"
            f"Stilvorgabe: {cat['script_style']}\n"
            + (f"Zielgruppe: {audience()}\n" if audience() else "")
            + "\nDas ist gerade in den USA und in Deutschland im Trend (TikTok-Sounds, Reddit, "
            "Google-Suchen, Wikipedia):\n"
            f"{trends.as_prompt_list(items)}\n\n"
            "Wähle EINEN Trend, über den die Zielgruppe gerade redet, und mach daraus ein Short in dieser Kategorie, "
            "das ein deutsches Gen-Z-Publikum auf TikTok sofort anspricht. Bevorzuge in dieser Reihenfolge: "
            "TikTok-Trends, Internet-Kultur und Memes, Gaming, Musik und Artists, Serien und Filme, Creator, Tech und Apps, "
            "virale Momente aus den USA, die in Deutschland noch neu sind. "
            "Meide Lokalnachrichten (Stadtfeste, Regionales), Börse, Wetter, Randsportarten und alles, was nur ältere Leute interessiert. "
            "Ein TikTok-Sound ist nur geeignet, wenn du den Song, den Artist oder den Trend dazu sicher kennst – sonst lieber einen anderen Trend. "
            "Am besten: ein überraschender Fakt, die Geschichte dahinter oder eine Erklärung, warum alle gerade darüber reden, "
            "die auch in ein paar Tagen noch stimmt. " + UNSUITABLE + "\n"
            "WICHTIG: Das Thema muss wirklich zur Kategorie passen (z. B. Tierwelt = ein echtes Tier steht im Mittelpunkt; "
            "Grusel = eine Gruselgeschichte). Passt kein Trend sauber, antworte mit {\"index\": null} – lieber kein Trend als ein unpassender. "
            + _insight(cat).replace("\n", " ") +
            "Marken, Spiele, Filme, Serien und Apps dürfen nur der Anlass sein, nie das Thema selbst: mach daraus das allgemeine Thema "
            "dahinter (statt eines Spiels z. B. 'Warum wir Nostalgie lieben').\n"
            "Diese Themen gab es schon:\n- " + ("\n- ".join(past) if past else "(noch keine)") + "\n"
            'Antworte als JSON: {"index": Nummer des Trends, "topic": "konkretes Video-Thema auf Deutsch", "why": "kurz, warum es passt"} '
            'oder {"index": null}, wenn keiner passt.')
    js, _ = ai.chat_json("Du bist Trend-Scout für einen deutschen Gen-Z-TikTok-Kanal und kennst die Internet-Kultur in den USA "
                          "und Deutschland. Sorgfältig bei Fakten. Antworte nur mit JSON.", user, 0.7)
    idx, topic = js.get("index"), str(js.get("topic") or "").strip()
    if idx is None or not topic:
        return None, None
    try:
        tr = items[int(idx)]
    except (ValueError, IndexError, TypeError):
        return None, None
    return topic, {"title": tr["title"], "source": tr["source"], "news": tr.get("news", [])[:3], "summary": tr.get("summary", "")}



def fix_description(js, topic):
    """Die erste Zeile der Beschreibung muss vom Thema des Videos handeln – sonst wird sie aus dem Titel gebaut."""
    import re
    def keys(text):
        return {w[:6] for w in re.findall(r"[a-zäöüß]{5,}", str(text or "").lower())} - {"passie", "würde", "plötzl", "deutsc", "wirkli", "komple"}
    lines = [l for l in str(js.get("description") or "").split("\n") if l.strip()]
    want = keys(js.get("title")) | keys(topic) | keys(" ".join(str(t) for t in (js.get("tags") or []) + (js.get("hashtags") or [])))
    if lines and want and not (keys(lines[0]) & want):
        ai.log(f"Beschreibung passt nicht zum Thema („{lines[0][:60]}“) – erste Zeile aus dem Titel gebaut")
        lines[0] = str(js.get("title") or topic).strip()
        js["description"] = "\n".join(lines)
    return js


REVIEW = """Du bist der Regisseur eines animierten Kurzvideos und prüfst den Bildplan, bevor gedreht wird.
Unten steht jede Szene mit Sprechertext und dem, was dazu gezeigt werden soll. Prüfe Szene für Szene streng:
1. Zeigt das Bild genau das, wovon der Satz redet (richtiger Ort, richtige Dinge, richtige Handlung)?
2. Passt die Stimmung? Panik und rennende Menschen nur, wenn der Satz von Panik oder Flucht spricht – und dann auch wirklich.
3. Ist der Ort glaubwürdig? Keine Menschenmenge im Keller, auf dem Feld oder im Wald; kein Meer, wenn es nicht ums Meer geht.
4. Steht dasselbe Tier oder Ding in zu vielen Szenen einfach in der Mitte? Dann zeig stattdessen, was der Satz beschreibt:
   die Folgen, die Menschen, den Ort, eine Zahl als Grafik.
6. Kein leeres Bild: In mindestens jeder zweiten Szene ist eine Figur ("actors") zu sehen, die erlebt, was der Satz beschreibt
   (erschrickt, schaut sich um, zeigt, rennt, hält etwas). Leere Zimmer und leere Wiesen sind verboten.
7. Erfinde keine Requisite, die mit dem Satz nichts zu tun hat. Gibt es kein passendes Ding, zeig eine Figur mit passender Reaktion.
5. Kleine Tiere (Spinne, Biene, Vogel, Katze) sind klein. Soll man sie gut sehen, nimm "shot": "insert" (groß und allein im Bild).
Gib NUR die Szenen zurück, die du verbesserst, als JSON:
{"fixes": [{"i": 3, "why": "kurz", "place": "...", "backdrop": {...} oder null, "time": "day", "weather": "", "props": [...], "actors": [...],
            "shot": "", "mood": "", "crowd": ""}]}
Nenne in einem Fix nur die Felder, die sich ändern. Benutze ausschließlich Werte aus dieser Liste:
"""


PROOF = """Du bist Lektor und Faktenprüfer für ein deutsches Wissens-Kurzvideo. Unten stehen je Szene der Sprechertext ("text") und die
Texte der Einblendungen und Grafiken ("labels"). Prüfe streng und verbessere NUR, was falsch ist:
1. Rechtschreibung, Grammatik, verstümmelte oder erfundene Wörter – auch in Einblendungen.
   Erfundene Fachbegriffe („hypnagoger Zuckungsimpuls“) durch den gebräuchlichen ersetzen („Einschlafzuckung“).
2. Erfundene Quellen: „Forscher schätzen …“, „Studien zeigen …“, „Experten warnen …“ ohne allgemein bekannte Grundlage. Formuliere solche Sätze
   als eigene Überlegung um („vermutlich“, „wahrscheinlich“) oder ersetze sie durch eine nachvollziehbare Folge. Keine erfundenen Opferzahlen,
   Schadenssummen oder Prozentwerte.
3. Sachlich Falsches oder maßlos Übertriebenes (falsche Größenordnung, unmöglicher Zeitraum, falsche Ursache): ersetze es durch die richtige,
   anschauliche Aussage. Bei Gedankenspielen („Was wäre, wenn …“) zählt, was nach heutigem Wissen wirklich folgen würde.
   Prüfe jede Temperatur, Geschwindigkeit, Masse und Zeitspanne gegen das, was allgemein bekannt ist (ein Schweißbrenner hat rund dreitausend Grad,
   nicht zehntausend; Thermit gut zweitausend) – im Zweifel die Zahl weglassen und anschaulich umschreiben („heißer als Lava“).
   Ein Satz, der in sich keinen Sinn ergibt oder sich selbst widerspricht, wird durch eine klare, richtige Aussage zum selben Punkt ersetzt.
4. Einblendung oder Grafik passt nicht zum Satz (andere Zahl, anderes Thema, sinnloses Wort): korrigiere ihren Text.
5. Es ist ein Video: Der Zuschauer schaut zu, er „liest“ nicht.
Jeder verbesserte Satz bleibt etwa gleich lang (höchstens 20 % kürzer oder länger), im selben lockeren Ton, Zahlen ausgeschrieben, ohne Marken,
und passt weiter zu den Sätzen davor und danach. Gib NUR Änderungen zurück, als JSON:
{"fixes": [{"i": 3, "why": "kurz", "text": "neuer Sprechertext", "labels": {"alter Text der Einblendung": "neuer Text"}}]}
"text" und "labels" nur angeben, wenn sie sich ändern. Leere Liste, wenn alles stimmt.
Steht in der Beschreibung ein „Wir“/„uns“, ein Tippfehler oder etwas am Thema vorbei, gib zusätzlich "description" mit der verbesserten Fassung zurück
(drei kurze Zeilen in Du-Form, mit \n getrennt, gleiche Länge).
Hat der Titel oder der Titelbild-Text einen Tippfehler oder ein verstümmeltes Wort („NURS“ statt „NUR“), gib zusätzlich "title" bzw. "thumb" mit der
berichtigten Fassung zurück (gleiche Aussage, gleiche Länge; Titelbild-Text 2–4 Wörter in GROSSBUCHSTABEN)."""
_LABEL_KEYS = ("text", "title", "label", "kicker", "sub", "unit", "a", "b", "left", "right")


HOOK = """Du bist Redakteur für virale deutsche Kurzvideos. Verbessere NUR den Einstieg: die ersten zwei Sätze.
Ziel: Wer die ersten drei Sekunden sieht, weiß, worum es geht, und will unbedingt das Ende sehen – spannend, aber nicht übertrieben und ohne Lüge.
Satz 1: höchstens zwölf Wörter. Nennt das Thema kurz und macht es unwiderstehlich (was ist unmöglich, gefährlich, verrückt, überraschend?).
Muster: „Drei Tier-Superkräfte, die eigentlich unmöglich sind.“ · „Dieses Tier überlebt sogar im Weltall.“ · „Was passiert, wenn du eine
Woche nicht schläfst?“ · bei Ich-Geschichten mitten hinein („Mein KI-Agent hat gerade gekündigt.“). Bei Listen die Anzahl nennen.
Er liest nicht den Titel wörtlich vor und beginnt nicht mit „Was wäre, wenn“, „Stell dir vor“, „Heute“, „In diesem Video“ oder „Wusstest du“.
Satz 2: höchstens sechzehn Wörter, der Cliffhanger: ein offenes Versprechen, das erst das Ende einlöst („Und die letzte kann dir sogar das
Leben retten.“) und das im Video wirklich vorkommt. Er passt nahtlos zu Satz 3.
Gleicher Inhalt und gleiche Fakten wie vorher – nichts erfinden, keine Marken, echte Umlaute, Zahlen ausgeschrieben.
Ist der Einstieg schon so, gib ihn unverändert zurück. Antworte nur mit JSON: {"s0": "…", "s1": "…"}"""
WEAK_START = r"^(was wäre,? wenn|stell dir (mal )?vor|heute|in diesem video|wusstest du|hast du dich (schon mal|jemals) gefragt|hallo|hey leute)"


def hook_weak(js):
    """Schwacher Einstieg? (zu lang, Floskel am Anfang, der Titel wörtlich vorgelesen, oder das Thema kommt gar nicht vor)"""
    import re as _re
    sc = [s for s in js.get("scenes", []) if isinstance(s, dict)]
    if not sc:
        return False
    t0 = str(sc[0].get("text") or "").strip()
    words = _re.findall(r"[a-zäöüß]+", t0.lower())
    title_s = " ".join(_re.findall(r"[a-zäöüß0-9]+", str(js.get("title") or "").lower()))
    title = set(_re.findall(r"[a-zäöüß]{4,}", title_s))
    verbatim = bool(title_s) and " ".join(_re.findall(r"[a-zäöüß0-9]+", t0.lower())) == title_s
    stems = {w[:5] for w in title}
    names_topic = not title or any(w[:5] in stems for w in words if len(w) >= 4)
    return len(words) > 13 or bool(_re.search(WEAK_START, t0.lower())) or verbatim or not names_topic


def sharpen_hook(js, topic):
    """Lässt die Text-KI die ersten zwei Sätze schärfen; übernimmt sie nur, wenn sie kurz, deutsch und ohne Floskel sind."""
    import json as _json
    import re as _re
    sc = [s for s in js.get("scenes", []) if isinstance(s, dict)]
    if len(sc) < 3:
        return js
    user = (f"Thema: {topic}\nTitel: {js.get('title')}\n"
            + "\n".join(f"Satz {i + 1}: {_json.dumps(str(s.get('text') or ''), ensure_ascii=False)}" for i, s in enumerate(sc[:4])))
    for attempt in range(2):                              # zweiter Versuch mit Hinweis, wenn Satz 1 das Thema nicht nennt
        out, _ = ai.chat_json(HOOK, user + ("\nACHTUNG: Satz 1 muss das Thema nennen (Wörter aus dem Titel), kurz und spannend."
                                             if attempt else ""), 0.7)
        s0, s1 = (" ".join(str((out or {}).get(k) or "").split()) for k in ("s0", "s1"))
        ok0 = s0 and len(s0.split()) <= 13 and not _re.search(WEAK_START, s0.lower()) and not _foreign(s0) and not any(c in s0 for c in "{}[]<>()")
        ok0 = ok0 and not hook_weak({"title": js.get("title"), "scenes": [{"text": s0}]})   # nennt das Thema, liest nicht den Titel vor
        ok1 = s1 and len(s1.split()) <= 18 and not _foreign(s1) and not any(c in s1 for c in "{}[]<>()")
        if ok0 and ok1:
            if (s0, s1) != (sc[0].get("text"), sc[1].get("text")):
                ai.log(f"Einstieg geschärft: „{s0}“ / „{s1}“")
            sc[0]["text"], sc[1]["text"] = s0, s1
            break
    return js


META = """Du bist Korrektor für ein deutsches Kurzvideo. Prüfe NUR Rechtschreibung und Wortwahl von Titel, Titelbild-Text und Suchbegriffen:
verstümmelte, erfundene oder falsch geschriebene Wörter („Macks“ statt „Macken“, „körpersucken“ statt „körperzucken“), falsche Groß- und
Kleinschreibung (Adjektive im Titel klein: „3 sinnlose Gehirn-Macken“), fehlende Umlaute. Aussage, Länge und Stil bleiben gleich; nichts
hinzufügen, keine Marken, keine Emojis. Gib JSON zurück – nur die Felder, die sich ändern:
{"title": "…", "thumb": "…", "tags": {"falsch geschriebener begriff": "richtiger begriff"}}
Leeres Objekt {}, wenn alles stimmt."""


def proof_meta(js, topic):
    """Schlusskorrektur für das, was öffentlich über dem Video steht: Titel, Titelbild-Text und Suchbegriffe. Ein eigener, kurzer
    Durchgang – im großen Lektorat gehen Tippfehler im Titel („Gehirn-Macks“) zwischen den Szenen unter."""
    import json
    th = js.get("thumbnail") if isinstance(js.get("thumbnail"), dict) else {}
    tags = [t for t in (js.get("tags") or []) if isinstance(t, str)]
    user = (f"Thema: {topic}\nTitel: {js.get('title')}\nTitelbild-Text: {th.get('text') or ''}\n"
            f"Suchbegriffe: {json.dumps(tags, ensure_ascii=False)}")
    out, _ = ai.chat_json(META, user, 0.1)
    if not isinstance(out, dict):
        return js
    old_t, ti = str(js.get("title") or ""), out.get("title")
    if isinstance(ti, str) and ti.strip() and ti.strip() != old_t and 0.7 <= len(ti.strip()) / max(1, len(old_t)) <= 1.3 \
            and abs(len(ti.split()) - len(old_t.split())) <= 1 and not _foreign(ti) and not _BRAND_RE.search(ti):
        js["title"] = ti.strip()
        ai.log(f"Schlusskorrektur Titel: {old_t} → {js['title']}")
    old_b, tb = str(th.get("text") or ""), out.get("thumb")
    if isinstance(tb, str) and tb.strip() and old_b and tb.strip().upper() != old_b.upper() and 0.6 <= len(tb.strip()) / len(old_b) <= 1.4 \
            and len(tb.split()) <= 5 and not _foreign(tb) and not _BRAND_RE.search(tb):
        th["text"] = tb.strip().upper()
        ai.log(f"Schlusskorrektur Titelbild-Text: {old_b} → {th['text']}")
    fix = out.get("tags") if isinstance(out.get("tags"), dict) else {}
    for i, t in enumerate(js.get("tags") or []):
        new = fix.get(t)
        if isinstance(t, str) and isinstance(new, str) and new.strip() and new.strip() != t and 0.6 <= len(new.strip()) / max(1, len(t)) <= 1.5 \
                and not _foreign(new) and not _BRAND_RE.search(new):
            js["tags"][i] = new.strip()
            ai.log(f"Schlusskorrektur Suchbegriff: {t} → {new.strip()}")
    return js


def proofread(js, topic):
    """Lektorat vor dem Dreh: Die Text-KI prüft Sprechertexte und Einblendungen auf Tippfehler, verstümmelte Wörter, erfundene
    Quellen und sachlich Falsches und bessert einzelne Sätze nach – Länge und Reihenfolge bleiben."""
    import json
    scenes = [s for s in js.get("scenes", []) if isinstance(s, dict)]

    def labels(s):
        out = []
        for box in (s.get("overlay"), s.get("graphic")):
            if isinstance(box, dict):
                out += [box[k] for k in _LABEL_KEYS if isinstance(box.get(k), str) and box[k].strip()]
                out += [str(it[0] if isinstance(it, (list, tuple)) and it else it) for it in (box.get("items") or []) if it] if isinstance(box.get("items"), list) else []
        return out
    th0 = js.get("thumbnail") if isinstance(js.get("thumbnail"), dict) else {}
    user = (f"Thema: {topic}\nTitel: {js.get('title')}\nTitelbild-Text: {th0.get('text') or ''}\nBeschreibung: {json.dumps(str(js.get('description') or ''), ensure_ascii=False)}\n\n"
            + "\n".join(json.dumps({"i": i, "text": s.get("text"), **({"labels": labels(s)} if labels(s) else {})}, ensure_ascii=False) for i, s in enumerate(scenes)))
    out, _ = ai.chat_json(PROOF, user, 0.2)
    n = 0
    desc = out.get("description") if isinstance(out, dict) else None
    if isinstance(desc, str) and 40 <= len(desc.strip()) <= 400 and not _foreign(desc) and len(desc.strip()) >= 0.5 * len(str(js.get("description") or "")):
        js["description"] = desc.strip()
        ai.log("Lektorat: Beschreibung verbessert")
    if isinstance(out, dict):
        ti, tb = out.get("title"), out.get("thumb")
        old_t = str(js.get("title") or "")
        if isinstance(ti, str) and ti.strip() and ti.strip() != old_t and 0.6 <= len(ti.strip()) / max(1, len(old_t)) <= 1.4 and not _foreign(ti) and not _BRAND_RE.search(ti):
            js["title"] = ti.strip()
            ai.log("Lektorat: Titel berichtigt")
        old_b = str(th0.get("text") or "")
        if isinstance(tb, str) and tb.strip() and old_b and tb.strip() != old_b and 0.5 <= len(tb.strip()) / len(old_b) <= 1.5 and len(tb.split()) <= 5 \
                and not _foreign(tb) and not _BRAND_RE.search(tb):
            th0["text"] = tb.strip().upper()
            ai.log("Lektorat: Titelbild-Text berichtigt")
    for f in ((out.get("fixes") or []) if isinstance(out, dict) else [])[:len(scenes)]:
        if not isinstance(f, dict) or isinstance(f.get("i"), bool) or not isinstance(f.get("i"), int) or not 0 <= f["i"] < len(scenes):
            continue
        s, changed = scenes[f["i"]], False
        new = " ".join(str(f.get("text") or "").split())
        old_n = len(str(s.get("text") or "").split())
        if new and new != s.get("text") and old_n and 0.6 <= len(new.split()) / old_n <= 1.5 and not _foreign(new) and not any(c in new for c in "{}[]<>"):
            s["text"], changed = new, True
        for old, rep_ in (f.get("labels") or {}).items() if isinstance(f.get("labels"), dict) else []:
            if not isinstance(rep_, str) or not rep_.strip() or len(rep_) > 60 or _foreign(rep_):
                continue
            for box in (s.get("overlay"), s.get("graphic")):
                if isinstance(box, dict):
                    for k in _LABEL_KEYS:
                        if box.get(k) == old:
                            box[k], changed = rep_.strip(), True
        if changed:
            n += 1
            ai.log(f"Lektorat Szene {f['i'] + 1}: {str(f.get('why') or '')[:120]}")
    ai.log(f"Lektorat: {n} von {len(scenes)} Szenen verbessert")
    return js


STORYBOARD = """Du bist der Regisseur eines animierten Kurzvideos. Das Drehbuch unten hat Sprechertexte, aber noch keinen Bildplan.
Lege für JEDE Szene fest, was der Zuschauer sieht, während der Satz gesprochen wird – genau das, wovon der Satz handelt
(richtiger Ort, richtige Dinge, eine Figur, die es erlebt oder tut). Keine Verlegenheitsbilder: keine herumstehende, redende Figur,
wenn der Satz ein Ereignis beschreibt; keine Passanten, die gemütlich gehen, wenn der Satz von einer Katastrophe handelt.
Wechsle Orte, Einstellungen und Aktionen ab. Gib JSON zurück:
{"cast": {"du": {"shirt": "blau", "hair": "long", "skin": "hell"}},
 "thumbnail": {"place": "...", "time": "day", "actor": "du", "action": "shocked", "emotion": "shocked", "props": ["..."], "weather": ""},
 "scenes": [{"i": 0, "see": "deutscher Satz: wer, wo, was passiert", "place": "...", "backdrop": null, "time": "day", "weather": "", "props": [],
             "actors": [{"id": "du", "action": "...", "emotion": "...", "emote": "", "pos": "center", "speaks": true}], "crowd": "", "mood": "calm", "shot": "wide"}]}
Eine Szene je Sprechertext, gleiche Reihenfolge, "i" = Nummer der Szene. Benutze ausschließlich Werte aus dieser Liste:
"""
_PLAN_KEYS = ("see", "place", "backdrop", "time", "weather", "props", "actors", "shot", "mood", "crowd", "graphic")


def has_storyboard(js):
    """Hat die Text-KI den Bildplan ausgefüllt? (Mindestens jede zweite Szene nennt Figuren, Requisiten, Einstellung oder Landschaft.)"""
    scenes = [s for s in js.get("scenes", []) if isinstance(s, dict)]
    n = sum(1 for s in scenes if any(s.get(k) not in (None, "", [], {}) for k in ("actors", "props", "shot", "backdrop", "see", "graphic")))
    return bool(scenes) and n * 2 >= len(scenes)


def storyboard(js, topic):
    """Fehlt der Bildplan (nur Sprechertext und Ort geliefert), wird er in einem eigenen Durchgang nachgeholt – sonst stünde in
    jeder Szene bloß die Hauptfigur herum, egal wovon der Satz handelt."""
    import json
    scenes = [s for s in js.get("scenes", []) if isinstance(s, dict)]
    user = (f"Thema: {topic}\nTitel: {js.get('title')}\n\nSPRECHERTEXTE:\n"
            + "\n".join(json.dumps({"i": i, "text": s.get("text"), **({"overlay": (s.get("overlay") or {}).get("type")} if isinstance(s.get("overlay"), dict) else {})},
                                    ensure_ascii=False) for i, s in enumerate(scenes))
            + "\n\nERLAUBTE WERTE:\n" + TOON + _learned())
    out, _ = ai.chat_json(STORYBOARD, user, 0.5)
    n = 0
    for f in (out.get("scenes") or []) if isinstance(out, dict) else []:
        if not isinstance(f, dict) or isinstance(f.get("i"), bool) or not isinstance(f.get("i"), int) or not 0 <= f["i"] < len(scenes):
            continue
        for k in _PLAN_KEYS:
            if k in f and f[k] not in (None, ""):
                scenes[f["i"]][k] = f[k]
        n += 1
    if isinstance(out, dict) and isinstance(out.get("cast"), dict) and out["cast"] and not any(isinstance(v, dict) for v in (js.get("cast") or {}).values()):
        js["cast"] = out["cast"]
    if isinstance(out, dict) and isinstance(out.get("thumbnail"), dict):
        th = js.get("thumbnail") if isinstance(js.get("thumbnail"), dict) else {}
        js["thumbnail"] = {**{k: v for k, v in out["thumbnail"].items() if k not in ("text", "image")}, **th}
    ai.log(f"Bildplan nachgeholt: {n} von {len(scenes)} Szenen bebildert")
    return js


def review_scenes(js, topic):
    """Zweiter Blick vor dem Dreh: Die Text-KI prüft als Regisseur, ob jedes Bild zum Satz passt, und bessert nach."""
    import json
    scenes = [s for s in js.get("scenes", []) if isinstance(s, dict)]
    keys = ("place", "backdrop", "time", "weather", "props", "actors", "shot", "mood", "crowd")
    plan = [{"i": i, "text": s.get("text"), **{k: s.get(k) for k in keys if s.get(k) not in (None, "", [])},
             **({"graphic": (s.get("graphic") or {}).get("type")} if isinstance(s.get("graphic"), dict) else {}),
             **({"overlay": (s.get("overlay") or {}).get("type")} if isinstance(s.get("overlay"), dict) else {})} for i, s in enumerate(scenes)]
    user = (f"Thema: {topic}\nTitel: {js.get('title')}\nFiguren: {json.dumps(js.get('cast'), ensure_ascii=False)}\n\nBILDPLAN:\n"
            + "\n".join(json.dumps(p, ensure_ascii=False) for p in plan) + "\n\nERLAUBTE WERTE:\n" + TOON)
    out, _ = ai.chat_json(REVIEW, user, 0.3)
    n = 0
    for f in (out.get("fixes") or [])[:len(scenes)]:
        if not isinstance(f, dict) or not isinstance(f.get("i"), int) or not 0 <= f["i"] < len(scenes):
            continue
        s = scenes[f["i"]]
        if isinstance(s.get("graphic"), dict) and "shot" not in f:      # Grafik-Szenen bleiben, wie sie sind
            continue
        changed = False
        for k in keys:
            if k in f and f[k] != s.get(k):
                if k == "backdrop" and f[k] is None:
                    s.pop("backdrop", None)
                else:
                    s[k] = f[k]
                changed = True
        if changed:
            n += 1
            ai.log(f"Regie-Prüfung Szene {f['i'] + 1}: {str(f.get('why') or '')[:120]}")
    ai.log(f"Regie-Prüfung: {n} von {len(scenes)} Szenen verbessert")
    return js

def _foreign(text):
    """Schriftzeichen, die in einem deutschen Text nichts verloren haben (Ausrutscher der Text-KI wie „Erダンziehungskraft“)."""
    import unicodedata
    out = []
    for ch in str(text or ""):
        if ord(ch) > 0x24F and ch.isalpha():
            try:
                if not unicodedata.name(ch).startswith("LATIN"):
                    out.append(ch)
            except ValueError:
                out.append(ch)
    return out


def foreign_in(js):
    """Fremde Schriftzeichen im Sprechertext, Titel, in der Beschreibung oder in Einblendungen? Gibt die betroffenen Texte zurück."""
    bad = []

    def walk(o, key=""):
        if isinstance(o, str):
            if key not in ("image",) and _foreign(o):
                bad.append(o[:80])
        elif isinstance(o, dict):
            for k, v in o.items():
                if k not in ("cast", "places", "thumbnail_image"):
                    walk(v, str(k))
        elif isinstance(o, (list, tuple)):
            for v in o:
                walk(v, key)
    walk({k: js.get(k) for k in ("title", "description", "hashtags", "tags", "hud", "scenes")})
    walk((js.get("thumbnail") or {}).get("text") if isinstance(js.get("thumbnail"), dict) else "")
    return bad


def strip_foreign(js):
    """Letztes Sicherheitsnetz: fremde Schriftzeichen aus allen Texten entfernen."""
    def conv(o, key=""):
        if isinstance(o, str):
            return "".join(ch for ch in o if ch not in set(_foreign(o))) if key != "image" else o
        if isinstance(o, dict):
            return {k: conv(v, str(k)) for k, v in o.items()}
        if isinstance(o, list):
            return [conv(v, key) for v in o]
        return o
    return conv(js)


def write_script(cat: dict, topic: str, trend=None, source=None) -> tuple[dict, str]:
    secs = int(cfg("target_seconds") or 60)
    from .state import STATE
    wps = float(STATE.get("voice_wps") or 0)             # gemessenes Sprechtempo der letzten Videos (Wörter pro Sekunde)
    if not 1.6 <= wps <= 3.6:
        wps = 2.6 if str(cfg("tts_provider") or "") == "gemini" else 2.4
    min_secs = float(cfg("min_seconds") or 0)
    secs = max(secs, int(min_secs + 6)) if min_secs else secs     # Ziel mit Abstand über der Mindestlänge
    words = round(secs * wps)
    scenes = max(8, round(secs / 4.2))                   # kurze Szenen: alle rund vier Sekunden ein neues Bild
    toon = str(os.environ.get("AS_VISUAL") or cfg("visual_mode") or "ai") == "toon"
    char = cfg("main_character") if cfg("use_main_character") and not toon else ""
    ctx = ""
    if trend:
        heads = "\n".join(f"- {n['title']} ({n.get('source', '')})" for n in trend.get("news", []))
        ctx = (f"Aktueller Anlass: „{trend['title']}“ ist gerade im Trend ({trend['source']}).\n"
               + (f"Schlagzeilen dazu:\n{heads}\n" if heads else "")
               + (f"Hintergrund: {trend['summary']}\n" if trend.get("summary") else "")
               + "Nutze den Anlass im Hook, erkläre dann den zeitlosen, belegbaren Hintergrund.\n")
    if source:                                       # Vorlage aus einem eingeschickten Video: in unserem Stil neu aufbauen
        ctx += ("VORLAGE – ein Video, das nachgebaut werden soll. Übernimm Idee, Ablauf, Tempo und Art der Witze, aber schreibe ALLES "
                "in eigenen Worten neu (keinen Satz wörtlich), in unserem Stil und mit unseren Figuren und Orten. Keine Namen von Kanälen, "
                "Personen, Marken oder Figuren aus der Vorlage. Stimmen Fakten der Vorlage nicht, korrigiere sie.\n"
                f"Gesprochener Text der Vorlage:\n{str(source.get('transcript') or '')[:3500]}\n"
                + (f"Was im Bild passiert (Ablauf):\n{str(source.get('visuals') or '')[:2000]}\n" if source.get("visuals") else ""))
    user = (f"Kategorie: {cat['name']}\nStil: {cat['script_style']}\nThema: {topic}\n{ctx}"
            + (f"Zielgruppe: {audience()}\n" if audience() else "")
            + f"Länge: zwischen {round(words * 0.85)} und {words} Wörter gesprochen insgesamt (≈ {secs} Sekunden) – zähle nach; nicht kürzer, nicht länger. "
            f"Aufgeteilt auf {scenes} Szenen, also etwa {round(words / scenes)} Wörter pro Szene.\n"
            + (f"Wiederkehrende Hauptfigur (nur wenn passend einbauen, in den Bild-Prompts immer gleich beschreiben): {char}\n" if char else "")
            + FORMAT + (TOON + _learned() if toon else ""))
    js, provider = ai.chat_json(SYSTEM, user, 0.9)
    n_words = sum(len(str(x.get("text", "")).split()) for x in js.get("scenes", []) if isinstance(x, dict))
    if n_words > words * 1.25:       # zu lang geraten → einmal straffen lassen
        ai.log(f"Drehbuch hat {n_words} Wörter statt {words} – lasse es kürzen")
        try:
            js2, provider = ai.chat_json(SYSTEM, user + f"\n\nACHTUNG: Dein letzter Entwurf hatte {n_words} Wörter Sprechertext. "
                                         f"Schreibe das Drehbuch neu mit {round(words * 0.9)} bis {words} Wörtern insgesamt (nicht weniger!), "
                                         f"etwa {max(6, round(words / scenes))} Wörter pro Szene, gleiche Szenenzahl.", 0.7)
            n2 = sum(len(str(x.get("text", "")).split()) for x in js2.get("scenes", []) if isinstance(x, dict))
            if words * 0.75 <= n2 < n_words:
                js = js2
        except Exception as e:  # noqa: BLE001
            ai.log(f"Kürzen nicht möglich ({e}) – nehme den ersten Entwurf")
    elif n_words < words * 0.88:     # zu kurz geraten → verlängern lassen (Video soll sicher über der Mindestlänge liegen, ohne stummen Ausklang)
        for _try in range(2):        # bis zu zwei Anläufe: ein zu kurzes Drehbuch endet sonst mit sekundenlangem Standbild ohne Sprecher
            ai.log(f"Drehbuch hat nur {n_words} Wörter statt {words} – lasse es verlängern")
            try:
                js2, provider = ai.chat_json(SYSTEM, user + f"\n\nACHTUNG: Dein letzter Entwurf hatte nur {n_words} Wörter Sprechertext – das Video wird zu kurz. "
                                             f"Schreibe das Drehbuch neu mit {round(words * 0.95)} bis {round(words * 1.05)} Wörtern insgesamt: mehr konkrete Folgen, "
                                             f"Zahlen und Beispiele, keine Füllsätze. Etwa {max(9, round(words / scenes) + _try)} Wörter pro Szene, "
                                             f"{scenes} bis {scenes + 2} Szenen. Zähle die Wörter jeder Szene nach, bevor du antwortest.", 0.8)
                n2 = sum(len(str(x.get("text", "")).split()) for x in js2.get("scenes", []) if isinstance(x, dict))
                if n_words < n2 <= words * 1.3:
                    js, n_words = js2, n2
            except Exception as e:  # noqa: BLE001
                ai.log(f"Verlängern nicht möglich ({e}) – nehme den bisherigen Entwurf")
                break
            if n_words >= words * 0.88:
                break
    for attempt in range(2):                             # Strichliste statt Geschichte („Drei Bugs“ → „Neunzehnter Bug“): neu schreiben lassen
        trouble = list_trouble(js)
        if not trouble:
            break
        ai.log(f"Aufzählung stimmt nicht ({trouble}) – lasse das Drehbuch neu schreiben")
        try:
            js2, provider = ai.chat_json(SYSTEM, user + "\n\nACHTUNG: Dein letzter Entwurf war eine Strichliste. " + trouble
                                         + " Schreibe das Drehbuch neu, gleich lang: genau so viele Punkte wie im ersten Satz angekündigt "
                                         "(höchstens fünf), jeder Punkt mit zwei bis vier Sätzen (was passiert, warum, Folge oder Witz). "
                                         "Nur der erste Satz eines Punkts nennt die Nummer. Jeder Satz ergibt für sich Sinn.", 0.8)
            n2 = sum(len(str(x.get("text", "")).split()) for x in js2.get("scenes", []) if isinstance(x, dict))
            if n2 >= words * 0.75:
                js, n_words = js2, n2
        except Exception as e:  # noqa: BLE001
            ai.log(f"Neu schreiben nicht möglich ({e})")
            break
    if list_trouble(js) and not str(list_trouble(js)).startswith("Der Einstieg"):
        raise ai.ProviderError("Drehbuch ist eine Strichliste (" + str(list_trouble(js)) + ") – Video wird nicht gebaut")
    for attempt in range(2):                             # fremde Schriftzeichen mitten im Wort: das Drehbuch ist verdorben → neu schreiben lassen
        bad = foreign_in(js)
        if not bad:
            break
        ai.log("Drehbuch enthält fremde Schriftzeichen (" + " | ".join(bad[:3]) + ") – lasse es neu schreiben")
        try:
            js2, provider = ai.chat_json(SYSTEM, user + "\n\nACHTUNG: Dein letzter Entwurf enthielt fremde Schriftzeichen mitten in deutschen Wörtern. "
                                         "Schreibe das Drehbuch neu – ausschließlich mit deutschen Buchstaben, jedes Wort korrekt ausgeschrieben.", 0.7)
            n2 = sum(len(str(x.get("text", "")).split()) for x in js2.get("scenes", []) if isinstance(x, dict))
            if n2 >= words * 0.75 and len(foreign_in(js2)) < len(bad):
                js = js2
        except Exception as e:  # noqa: BLE001
            ai.log(f"Neu schreiben nicht möglich ({e})")
            break
    if any(_foreign(str(s_.get("text") or "")) for s_ in js.get("scenes", []) if isinstance(s_, dict)):
        raise ai.ProviderError("Drehbuch enthält verstümmelte Wörter (fremde Schriftzeichen im Sprechertext)")
    js = strip_foreign(js)
    try:
        js = fix_umlauts(js)
        found = sorted({m.group(1) for sc_ in js.get("scenes", []) if isinstance(sc_, dict) for m in _BRAND_RE.finditer(str(sc_.get("text") or ""))}
                       | {m.group(1) for m in _BRAND_RE.finditer(str(js.get("title") or ""))})
        if found:                                        # sauber neu formulieren lassen; das Ersetzen unten ist nur das Sicherheitsnetz
            ai.log("Drehbuch nennt Marken (" + ", ".join(found) + ") – lasse es ohne Markennamen neu formulieren")
            try:
                n0 = sum(len(str(x.get("text", "")).split()) for x in js.get("scenes", []) if isinstance(x, dict))
                js2, provider = ai.chat_json(SYSTEM, user + "\n\nACHTUNG: Dein letzter Entwurf nannte diese Marken-/Firmennamen: " + ", ".join(found)
                                             + ". Schreibe das Drehbuch neu, gleich lang, OHNE jeden Marken-, Firmen-, Produkt- oder App-Namen – "
                                             "umschreibe sie allgemein und grammatisch sauber (auch in Titel, Beschreibung, Hashtags und Einblendungen).", 0.7)
                n2 = sum(len(str(x.get("text", "")).split()) for x in js2.get("scenes", []) if isinstance(x, dict))
                if n2 >= n0 * 0.85:
                    js = fix_umlauts(js2)
            except Exception as e:  # noqa: BLE001
                ai.log(f"Neu formulieren nicht möglich ({e})")
        js = strip_brands(js)
        for k in ("hashtags", "tags"):                  # Marken-Hashtags fliegen ganz raus
            if isinstance(js.get(k), list):
                js[k] = [t for t in js[k] if isinstance(t, str) and not _BRAND_RE.search(t.replace("#", " "))]
    except Exception:  # noqa: BLE001
        pass
    try:
        js = fix_description(js, topic)
    except Exception:  # noqa: BLE001
        pass
    if hook_weak(js) or cfg("sharpen_hook") is not False:
        try:
            js = sharpen_hook(js, topic)
        except Exception as e:  # noqa: BLE001
            ai.log(f"Einstieg nicht geschärft ({e})")
    if cfg("proofread") is not False:
        try:
            js = proofread(js, topic)
        except Exception as e:  # noqa: BLE001
            ai.log(f"Lektorat nicht möglich ({e}) – nehme den Text, wie er ist")
        try:
            js = proof_meta(js, topic)
        except Exception as e:  # noqa: BLE001
            ai.log(f"Schlusskorrektur nicht möglich ({e})")
    try:
        js = polish(js)
    except Exception:  # noqa: BLE001
        pass
    if toon and not has_storyboard(js):
        ai.log("Drehbuch kam ohne Bildplan – lasse ihn eigens ausarbeiten")
        for attempt in (1, 2):
            try:
                js = storyboard(js, topic)
                break
            except Exception as e:  # noqa: BLE001
                ai.log(f"Bildplan nicht möglich ({e})" + (" – zweiter Versuch" if attempt == 1 else ""))
        if not has_storyboard(js):
            # Ohne Bildplan steht in fast jeder Szene dieselbe Figur im selben Zimmer – so ein Video sieht billig aus. Lieber keins als das.
            raise ai.ProviderError("Kein Bildplan zu bekommen (Text-KI nicht erreichbar) – Video wird nicht gebaut")
    if toon and cfg("review_script") is not False:
        try:
            js = review_scenes(js, topic)
        except Exception as e:  # noqa: BLE001
            ai.log(f"Regie-Prüfung nicht möglich ({e}) – nehme den Bildplan, wie er ist")
    try:
        js = polish(js)                                  # noch einmal: Bildplan und Regie-Prüfung können neue Einblendungen gebracht haben
    except Exception:  # noqa: BLE001
        pass
    sc = [s for s in js.get("scenes", []) if isinstance(s, dict) and str(s.get("text", "")).strip()]
    if len(sc) < 3:
        raise ai.ProviderError("Drehbuch hat zu wenige Szenen")
    raw_cast = js.get("cast") if isinstance(js.get("cast"), dict) else {}
    cast = {str(k): (str(v) if not isinstance(v, dict) else "") for k, v in raw_cast.items() if v}
    places = {str(k): str(v) for k, v in (js.get("places") or {}).items() if v} if isinstance(js.get("places"), dict) else {}
    for s in sc:
        s["text"] = " ".join(str(s["text"]).split())
        s["text"] = re.sub(r"hundert[ -]?und[ -]?(?=(?:ein|zwei|drei|vier|fünf|sechs|sieben|acht|neun)und|zehn|elf|zwölf|\w+zehn\b)", "hundert", s["text"])   # „neunzehnhundertunddreiundneunzig“
        s["image"] = str(s.get("image") or s["text"])
        ov = s.get("overlay")
        if isinstance(ov, str):   # altes Format: nur Text
            ov = {"type": "card", "text": ov} if ov.strip() else None
        s["overlay"] = ov if isinstance(ov, dict) and ov.get("type") else None
        who = s.get("who") or []
        who = [who] if isinstance(who, str) else who
        s["who_desc"] = "; ".join(cast[w] for w in who if w in cast)
        s["place_desc"] = places.get(str(s.get("place") or ""), "")
        s["highlight"] = [str(h) for h in (s.get("highlight") or []) if str(h).strip()][:3]
        s["camera"] = str(s.get("camera") or "")
        s["sfx"] = str(s.get("sfx") or "")
        s["hud"] = str(s.get("hud") or "").strip()
        s["status"] = str(s.get("status") or "").strip()[:30] if isinstance(s.get("status"), str) else ""
    tags = [t if str(t).startswith("#") else "#" + str(t) for t in js.get("hashtags", [])]
    tags = [t.replace(" ", "") for t in tags if len(t) > 1]
    if "#shorts" not in [t.lower() for t in tags]:
        tags.insert(0, "#shorts")
    th = js.get("thumbnail") if isinstance(js.get("thumbnail"), dict) else {}
    js["description"] = "\n".join(l.strip() for l in str(js.get("description") or "").replace("\\n", "\n").split("\n") if l.strip())
    return {"title": str(js.get("title") or topic)[:95], "description": str(js.get("description") or ""),
            "hashtags": tags[:10], "tags": [str(t).strip("# ")[:60] for t in js.get("tags", []) if str(t).strip("# ")][:15],
            "thumbnail": {**th, "image": str(th.get("image") or sc[0]["image"]), "text": str(th.get("text") or "").strip()[:40]},
            "wishes": [str(w)[:40] for w in (js.get("wishes") or []) if str(w).strip()][:8] if isinstance(js.get("wishes"), list) else [],
            "toon": toon, "cast": {str(k): v for k, v in raw_cast.items() if isinstance(v, dict)},
            "scenes": sc, "hud": str(js.get("hud") or "").strip()[:28],
            "countdown": js.get("countdown") if isinstance(js.get("countdown"), dict) else None}, provider


def image_prompt(scene: dict, cat: dict) -> str:
    style = cfg("image_style")
    who = f" Characters: {scene['who_desc']}." if scene.get("who_desc") else ""
    where = f" Setting: {scene['place_desc']}." if scene.get("place_desc") else ""
    return f"{scene['image']}.{who}{where} Mood: {cat.get('image_mood') or ''}. Style: {style}"
