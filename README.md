# AutoShorts

Erstellt jeden Tag automatisch ein KI-Short im Cartoon-Erklärstil und lädt es auf **YouTube Shorts** und **TikTok** hoch. Gesteuert wird alles über die App **AutoShorts** auf deinem PC: Dashboard, Kalender, Studio und Einstellungen.

Die Videos baut der Motor kostenlos auf GitHub Actions, auch wenn dein PC aus ist.

## Starten

1. **AutoShorts.cmd** herunterladen (oben auf die Datei klicken → Download-Symbol).
2. In einen festen Ordner legen, z. B. Dokumente (nicht direkt aus der ZIP starten, vorher entpacken).
3. Doppelklick. Fehlt Python, wird es einmalig automatisch installiert.
4. Die App öffnet sich in einem eigenen Fenster und legt ein Symbol **AutoShorts** auf dem Desktop an.

Mac/Linux: `python3 AutoShorts.cmd`

## Updates

Beim Start prüft die App, ob hier eine neue Version liegt, und fragt **„Jetzt aktualisieren?“**. In **Einstellungen → App & Updates** gibt es zusätzlich den Knopf **„Nach Updates suchen“** und den Schalter für automatische Updates. Einstellungen bleiben erhalten (Ordner `AutoShorts-Daten` neben der Datei).

| Datei | Zweck |
|---|---|
| `AutoShorts.cmd` | Die komplette App in einer Datei |
| `version.json` | Versionsnummer und Prüfsumme für das Update |
| `releases/` | Jede Version als eigene Datei (Quelle für Updates) |
| `quellcode/` | Quellcode der App (`python3 quellcode/build_onefile.py 1.1.0 "Notiz"`) |
| `engine/` | Der Motor, der auf GitHub die Videos baut |
| `docs/data/` | Einstellungen, Videos und Zahlen (schreiben App und Motor) |

## Einrichtung (einmalig)

### 1. App mit GitHub verbinden
Die App führt dich beim ersten Start durch das Erstellen eines Zugangsschlüssels:
[github.com/settings/personal-access-tokens/new](https://github.com/settings/personal-access-tokens/new) → Fine-grained token → nur dieses Repository → Berechtigungen **Actions**, **Contents** und **Secrets** auf *Read and write*.

### 2. Kostenlose KI-Schlüssel
In der App unter **Einstellungen → Zugangsdaten** einfügen und „Speichern“ tippen. Die App verschlüsselt sie und legt sie als GitHub-Secret ab.

| Schlüssel | Woher | Kosten |
|---|---|---|
| Gemini API-Key | aistudio.google.com → „Get API key“ | Gratis-Kontingent |
| Cloudflare Account-ID | dash.cloudflare.com → Workers AI | – |
| Cloudflare API-Token | dash.cloudflare.com → Profil → API-Tokens → Vorlage „Workers AI“ | Gratis-Kontingent |

Der Sprecher (Microsoft-Edge-Stimmen) braucht keinen Schlüssel.

**Test:** Im Studio „direkt hochladen“ ausschalten und „Video erstellen“ tippen. Nach etwa 10 Minuten steht das Video im Dashboard, mit Knopf „MP4“.

### 3. YouTube verbinden
1. **console.cloud.google.com** → neues Projekt → „APIs & Dienste“ → Bibliothek → **YouTube Data API v3** aktivieren.
2. **OAuth-Zustimmungsbildschirm**: Extern, App-Name, deine E-Mail, Bereiche `youtube.upload` und `youtube.readonly`. Veröffentlichungsstatus auf **„In Produktion“** stellen (sonst läuft die Anmeldung nach 7 Tagen ab).
3. **Anmeldedaten → OAuth-Client-ID → Desktop-App**. Eine Weiterleitungs-URL musst du nicht eintragen.
4. In der App: Client-ID unter **Plattformen** eintragen und speichern, Client-Secret unter **Zugangsdaten** speichern → **Verbinden**. Die Warnung „App nicht überprüft“ mit „Erweitert → Weiter“ bestätigen.

Bis Google dein Projekt geprüft hat, landen API-Uploads auf **„Privat“** (Formular „YouTube API Services – Audit and Quota Extension“, kostenlos).

### 4. TikTok verbinden
1. **developers.tiktok.com** → App erstellen → Produkte **Login Kit** (Plattform **Desktop**) und **Content Posting API** (mit „Direct Post“).
2. Scopes: `user.info.stats` dazu; `user.info.basic` kommt mit Login Kit, `video.publish` und `video.upload` mit der Content Posting API. `video.list` ist optional (falls verfügbar: Aufrufe je Video).
3. Redirect-URI: `http://127.0.0.1:8791/oauth/`
4. In der App: Client Key unter **Plattformen**, Client Secret unter **Zugangsdaten** → **Verbinden**.

Bis TikTok die App geprüft hat, sind API-Uploads nur als **„Nur ich“** erlaubt. Alternative: Upload-Art **„Als Entwurf in die TikTok-App“**.

## Später upgraden
**Einstellungen → KI-Anbieter**: Skript, Stimme und Bilder einzeln auf OpenAI oder ElevenLabs umstellen und den Schlüssel unter Zugangsdaten speichern. Die App zeigt die Kosten pro Video. Fällt ein bezahlter Dienst aus, nimmt der Motor automatisch den kostenlosen.

## Gut zu wissen
- **TikTok Creator Rewards** zahlt nur für Videos über 1 Minute, daher 70 Sekunden Ziel-Länge.
- **YouTube** schließt sehr gleichförmige Massenvideos von der Monetarisierung aus. Kategorien wechseln und Themen pflegen hilft.
- Die **KI-Kennzeichnung** ist standardmäßig an.
- GitHub startet geplante Läufe manchmal bis zu einer Stunde später.
- Das Repository ist öffentlich: Code und Zahlen sind sichtbar, deine Schlüssel nicht (GitHub-Secrets; Anmeldungen liegen verschlüsselt in `tokens/`).
- Hintergrundmusik: lizenzfreie MP3s in `music/` hochladen, pro Kategorie optional in Unterordner wie `music/grusel/`.
