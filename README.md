# AutoShorts

Erstellt jeden Tag automatisch ein KI-Short im Cartoon-Erklärstil und lädt es auf **YouTube Shorts** und **TikTok** hoch. Gesteuert wird alles über eine einfache App:

**👉 https://quatratkopf.github.io/autoshorts/**

- **Dashboard:** Aufrufe pro Tag, Likes, Kommentare, Abos und Follower, beste Kategorie, alle Videos
- **Studio:** Kategorie antippen (Fakten, Grusel, Spannende Storys, Lustige Geschichten, Mysterien, Tierwelt oder eigene), Thema eingeben oder leer lassen, „Video erstellen“
- **Einstellungen:** Upload-Zeit, Plattformen, KI-Anbieter (kostenlos oder Premium)

Kein Server nötig: Die Videos baut GitHub Actions kostenlos, die App läuft über GitHub Pages.

---

## Einrichtung (einmalig, ca. 20 Minuten)

### 1. App einschalten
Im Repository auf **Settings → Pages** gehen.
Unter „Build and deployment“: Source **Deploy from a branch**, Branch **main**, Ordner **/docs** → **Save**.
Nach 1–2 Minuten ist die App unter dem Link oben erreichbar.

### 2. App mit GitHub verbinden
App öffnen. Sie führt dich durch das Erstellen eines Zugangsschlüssels (Fine-grained token, nur für dieses Repository, Rechte: Actions + Contents lesen/schreiben, Secrets lesen). Auf dem Handy: **Teilen → Zum Home-Bildschirm**, dann hast du AutoShorts mit eigenem Icon.

### 3. Kostenlose KI-Schlüssel
In der App unter **Einstellungen → Zugangsdaten** jeweils „Eintragen“ tippen:

| Name | Woher | Kosten |
|---|---|---|
| `GEMINI_API_KEY` | aistudio.google.com → „Get API key“ | Gratis-Kontingent |
| `CLOUDFLARE_ACCOUNT_ID` | dash.cloudflare.com → Workers AI (Account-ID steht dort) | – |
| `CLOUDFLARE_API_TOKEN` | dash.cloudflare.com → Profil → API-Tokens → Vorlage „Workers AI“ | Gratis-Kontingent |

Der Sprecher (Microsoft-Edge-Stimmen) braucht keinen Schlüssel. Ohne Gemini/Cloudflare springt AutoShorts auf Pollinations (kostenlos, ohne Anmeldung, aber langsamer).

**Test:** Im Studio „direkt hochladen“ ausschalten und „Video erstellen“ tippen. Nach etwa 10 Minuten steht das Video im Dashboard, mit Knopf „MP4“ zum Ansehen.

### 4. YouTube verbinden
1. **console.cloud.google.com** → neues Projekt.
2. „APIs & Dienste“ → Bibliothek → **YouTube Data API v3** aktivieren.
3. **OAuth-Zustimmungsbildschirm** → Extern → App-Name und deine E-Mail → Bereiche `youtube.upload` und `youtube.readonly`.
4. **Wichtig:** Veröffentlichungsstatus auf **„In Produktion“** stellen, sonst läuft die Anmeldung nach 7 Tagen ab. Die Warnung „App nicht überprüft“ beim Verbinden mit „Erweitert → Weiter“ bestätigen.
5. **Anmeldedaten → OAuth-Client-ID → Webanwendung**. Weiterleitungs-URI:
   `https://quatratkopf.github.io/autoshorts/callback.html`
6. Client-ID in der App unter Plattformen eintragen und speichern, Client-Secret als `GOOGLE_CLIENT_SECRET` hinterlegen → **Mit YouTube verbinden**.

Solange Google dein Projekt nicht geprüft hat, landen API-Uploads auf **„Privat“**. Für öffentliche Uploads das kostenlose Formular „YouTube API Services – Audit and Quota Extension“ ausfüllen; bis dahin im YouTube Studio auf „Öffentlich“ stellen.

### 5. TikTok verbinden
1. **developers.tiktok.com** → App erstellen.
2. Produkte **Login Kit** und **Content Posting API** (mit „Direct Post“) hinzufügen.
3. Scopes: `user.info.basic`, `user.info.stats`, `video.publish`, `video.upload`, `video.list`.
4. Redirect-URI: `https://quatratkopf.github.io/autoshorts/callback.html`
5. Als Website/Datenschutz/Nutzungsbedingungen kannst du die App-Adresse angeben. Zur Prüfung einreichen; zum Testen vorher den Sandbox-Modus mit deinem Konto als Testnutzer nutzen.
6. Client Key in der App eintragen und speichern, Client Secret als `TIKTOK_CLIENT_SECRET` hinterlegen → **Mit TikTok verbinden**.

Bis TikTok die App geprüft hat, sind API-Uploads nur als **„Nur ich“** erlaubt. Alternative: Upload-Art **„Als Entwurf in die TikTok-App“** – dann tippst du in der App einmal auf Posten.

---

## Später upgraden

In **Einstellungen → KI-Anbieter** jeden Schritt einzeln umstellen (OpenAI für Text, Stimme und Bilder, ElevenLabs für die Stimme). Den passenden Schlüssel unter Zugangsdaten hinterlegen. Die App zeigt die Kosten pro Video. Fällt ein bezahlter Dienst aus, nimmt der Motor automatisch den kostenlosen.

## Hintergrundmusik

Lizenzfreie MP3s in den Ordner `music/` hochladen (auf GitHub: „Add file → Upload files“), pro Kategorie optional in Unterordner wie `music/grusel/`. Quelle z. B. YouTube Studio → Audio-Mediathek.

## Gut zu wissen

- **TikTok Creator Rewards** zahlt nur für Videos über 1 Minute – Ziel-Länge steht deshalb auf 70 Sekunden.
- **YouTube** schließt sehr gleichförmige Massenvideos von der Monetarisierung aus. Kategorien wechseln und die Themen-Warteschlange pflegen hilft.
- Die **KI-Kennzeichnung** ist standardmäßig an.
- GitHub startet geplante Läufe manchmal bis zu einer Stunde später als eingestellt.
- Das Repository ist öffentlich: Code und Statistiken sind sichtbar, deine Schlüssel nicht (die liegen in den GitHub-Secrets, Anmeldungen verschlüsselt).
- Fertige Videos liegen unter **Releases → videos**.

## Aufbau

```
docs/                 die App (GitHub Pages) + Daten (docs/data/*.json) + Vorschaubilder
engine/ai.py          KI-Anbieter mit automatischem Ausweichen
engine/writer.py      Themenfindung und Drehbuch
engine/render.py      Schnitt mit ffmpeg: Kamerafahrten, Untertitel, Infokarten, Musik
engine/uploaders.py   YouTube- und TikTok-API, Statistik
engine/main.py        Ablauf (auto, make, upload, stats, connect)
.github/workflows/    stündliche Prüfung + Start aus der App
```
