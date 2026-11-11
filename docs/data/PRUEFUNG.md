# Prüfung vor dem Upload (Anleitung für die tägliche Prüf-Sitzung)

Ziel: Kein Video geht ungeprüft online. Die Sitzung baut das Video für den nächsten Termin, sieht es sich Szene für Szene an,
behebt Fehler in der Engine, lässt es neu bauen und lädt es erst hoch, wenn es stimmt. Der Kanalinhaber hat diesen Ablauf
ausdrücklich so beauftragt (öffentlicher Upload auf YouTube und TikTok nach bestandener Prüfung ist erlaubt).

Repo: `QuatratKopf/autoshorts`, Branch `main`. Antworten und Berichte auf Deutsch.

## Ablauf
1. `git pull --rebase`. Video bauen lassen (ohne Upload):
   `gh api -X POST repos/QuatratKopf/autoshorts/actions/workflows/autoshorts.yml/dispatches -f ref=main -f 'inputs[action]=review_make'`
   Auf das Ende des Laufs warten (`gh api 'repos/QuatratKopf/autoshorts/actions/runs?event=workflow_dispatch&per_page=5'`, Lauf mit Titel
   `review_make`, alle 30 s `status` prüfen; dauert 6–10 Minuten). Danach `git pull --rebase`.
   Meldet das Protokoll „kein Termin in den nächsten Stunden offen“ oder gibt es kein Video mit `"status": "review"` in
   `docs/data/videos.json`: nichts weiter tun, kurz berichten.
2. Material holen: Video `<id>.mp4` aus den Release-Assets
   (`gh api repos/QuatratKopf/autoshorts/releases --paginate -q '.[].assets[] | select(.name=="<id>.mp4") | .id'`, dann
   `gh api -H "Accept: application/octet-stream" repos/QuatratKopf/autoshorts/releases/assets/<asset>` in eine Datei),
   Bildplan `docs/data/scripts/<id>.json` (Satz, Ort, Dinge, Figuren je Szene) und den Eintrag in `videos.json` (Titel, Beschreibung, Hashtags).
3. Ansehen: mit ffmpeg Bildübersichten bauen – mindestens 2 Bilder pro Szene (z. B. `fps=48/<dauer>,scale=300:-2,tile=8x6`, bei Bedarf
   einzelne Szenen größer) – und jede Szene mit eigenen Augen gegen ihren Satz prüfen.
4. Prüfliste – jede Szene und das Ganze:
   - Zeigt das Bild genau das, wovon der Satz spricht (Ort, Dinge, Handlung)? Kein Verlegenheitsbild, kein falscher Gegenstand.
   - Beschreibt der Satz eine Handlung, tut eine Figur genau das (nicht bloß ein Gegenstand im Bild).
   - Größenverhältnisse stimmen (Tiere, Autos, Dinge neben Menschen). Nichts schwebt, nichts steckt ineinander, nichts ist abgeschnitten.
   - Körperhaltung stimmt: Sitzen, Liegen, Fallen, Schweben sehen anatomisch richtig aus (Beine unten, nichts verdreht). Dafür jede
     Einstellung mit Figur mindestens einmal groß ansehen (Einzelbild in halber Auflösung) – in der kleinen Übersicht fällt das nicht auf.
   - Stimmung passt: Panik/Rennen nur bei Panik im Satz; Gefühle und Zeichen über den Köpfen passen.
   - Menschen nur dort, wo sie hingehören (keine Passanten im Keller, auf dem Feld, im Wald). Kein leeres Bild, in dem nichts passiert.
   - Einblendungen lesbar, nicht abgeschnitten, überdecken sich nicht und nicht die Untertitel; Zahlen stimmen mit dem Sprechertext überein.
   - Nicht dieselbe Einstellung mehrmals hintereinander; Szenenwechsel passen zum Satzwechsel.
   - Tag/Nacht, Wetter, innen/außen stimmen (keine Sonne im Zimmer, kein Feuer im Haus ohne Grund).
   - Titel, Beschreibung und Hashtags handeln vom Thema des Videos; echte Umlaute; keine Marken, keine echten Personen.
   - Länge über 60 Sekunden; Untertitel laufen bis zum Schluss mit.
   - Fesselnd? Alle drei bis vier Sekunden ein neues Bild, Kamera springt auf das Schlüsselwort, keine zwei Szenen hintereinander mit
     demselben Aufbau, kein Satz ohne neuen Inhalt. Der Fortschrittsbalken oben läuft bis zum Ende durch.
5. Etwas passt nicht → Ursache in der Engine beheben (meist `engine/toon/stage.py` Regie-Regeln, `engine/writer.py` Drehbuch-Vorgaben,
   `extras.py`/`places.py`/`graphics.py` Zeichnung), nicht nur dieses eine Video flicken. Den Bildplan mit
   `stage.direct(...)` und `engine.toon.selftest.frame(...)` lokal nachstellen und das Ergebnis ansehen.
   `FONTS_DIR=/usr/share/fonts/truetype/google-fonts python3 -m engine.toon.selftest` muss mit 0 Fehlern enden (dauert seit dem
   Umbau der Animation rund 15 Minuten – im Hintergrund starten und inzwischen weiterarbeiten). Committen
   (`Prüfung: …`), `git pull --rebase`, pushen.
   Dann die alte Fassung verwerfen (`-f 'inputs[action]=discard' -f 'inputs[video_id]=<id>' -f 'inputs[topic]=<Grund>'`) und mit demselben
   Thema und derselben Kategorie neu bauen: `-f 'inputs[action]=make' -f 'inputs[category]=<slug>' -f 'inputs[upload]=0' -f 'inputs[topic]=<Thema>'`.
   Neue Fassung wieder komplett prüfen. Höchstens 3 Neubauten.
6. Passt alles → hochladen: `-f 'inputs[action]=upload' -f 'inputs[video_id]=<id>'`, Lauf abwarten, in `videos.json` prüfen, dass
   `status` = `published` ist.
7. Nach 3 Neubauten immer noch grobe Fehler (falscher Inhalt, Unsinn im Bild): NICHT hochladen, letzte Fassung verwerfen und berichten,
   was nicht zu beheben war. Nur noch Kleinigkeiten offen: die beste Fassung hochladen und die Kleinigkeiten im Bericht nennen.
8. Kurzer Bericht am Ende: Titel, Link (`https://www.youtube.com/watch?v=<yt_id>`), was gefunden und behoben wurde, was offen ist.

## Auftrag des Inhabers: alles selbst beheben
Alles, was bei der Prüfung auffällt – auch Kleinigkeiten und Dinge, die nicht in der Prüfliste stehen –, wird ohne Rückfrage sofort in der
Engine behoben (Ursache, nicht nur dieses Video), mit Selbsttest geprüft, committet und gepusht. Das gilt auch, wenn das Video schon
hochgeladen ist oder die drei Neubauten verbraucht sind: Dann wird der Fehler für die nächsten Videos behoben und im Bericht genannt.
Meldet der Inhaber selbst einen Fehler, gilt dasselbe – beheben, ansehen, pushen, berichten.

## Grenzen
- Nichts an Zugangsdaten, `tokens/`, Upload-Code (`engine/uploaders.py`), Workflow-Zeitplan oder App-Einstellungen ändern.
- Keine echten Personen, Marken, Logos oder geschützten Figuren zeichnen. Die E-Mail-Adresse des Inhabers nie ins Repo schreiben.
- Nur das eine Video des Termins hochladen; keine weiteren Videos veröffentlichen, nichts löschen.
- Bleibt ein Video unbearbeitet im Zustand `review`, lädt der Autopilot es nach 3 Stunden selbst hoch – verworfene Fassungen deshalb
  immer mit `discard` kennzeichnen.
