# Privacy Policy – AutoShorts

*Last updated: 8 November 2026 · Deutsche Fassung unten*

AutoShorts is a private tool that its owner uses to create short videos and publish them to the owner's **own** YouTube and TikTok accounts. It is not offered to other users.

## What data AutoShorts accesses
When the owner connects an account, AutoShorts receives access tokens from Google (YouTube) and TikTok with the permissions the owner approves. It uses them only to:
- upload videos to the connected account,
- read basic profile information (display name, follower count),
- read view, like, comment and share counts of the account's own videos for the owner's statistics dashboard.

## How data is stored
- Access tokens are stored **encrypted** in the owner's own GitHub repository (`tokens/`). The decryption key is kept in GitHub Actions secrets and on the owner's computer.
- Video statistics are stored in `docs/data/` of the same repository.
- AutoShorts does not collect data about other TikTok or YouTube users or viewers.

## Sharing
No data is sold or shared with third parties. Video scripts, voice-overs and images are generated through AI services chosen by the owner (e.g. Google Gemini, Cloudflare Workers AI, Microsoft Edge text-to-speech, OpenAI); only the video topic and generated text are sent to these services, no account data.

## Deleting data
The owner can disconnect an account at any time in the app, revoke access in the Google or TikTok account settings, and delete the repository.

## Contact
Questions: open an issue at https://github.com/QuatratKopf/autoshorts/issues

---

# Datenschutzerklärung – AutoShorts

*Stand: 8. November 2026*

AutoShorts ist ein privates Werkzeug, mit dem der Inhaber kurze Videos erstellt und auf seinen **eigenen** YouTube- und TikTok-Konten veröffentlicht. Es wird anderen Nutzern nicht angeboten.

**Welche Daten:** Nach der Verbindung erhält AutoShorts Zugangstokens von Google und TikTok mit den Rechten, die der Inhaber freigibt. Sie werden nur genutzt, um Videos auf das verbundene Konto hochzuladen, Basis-Profilangaben (Anzeigename, Follower) zu lesen und Aufrufe, Likes, Kommentare und Shares der eigenen Videos für das Dashboard abzurufen.

**Speicherung:** Tokens liegen **verschlüsselt** im eigenen GitHub-Repository des Inhabers; der Schlüssel liegt in den GitHub-Secrets und auf dem PC des Inhabers. Statistiken liegen unter `docs/data/`. Über andere Nutzer oder Zuschauer werden keine Daten erhoben.

**Weitergabe:** Keine Weitergabe oder Verkauf an Dritte. An die genutzten KI-Dienste gehen nur Thema und erzeugte Texte, keine Kontodaten.

**Löschen:** Konto in der App trennen, Zugriff in den Google- bzw. TikTok-Einstellungen widerrufen, Repository löschen.

**Kontakt:** https://github.com/QuatratKopf/autoshorts/issues
