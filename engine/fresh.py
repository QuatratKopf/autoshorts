"""Neu einrichten: eine Kopie (Fork) des Repositorys für einen anderen Kanal auf null setzen.

Löscht in DIESER Kopie die Video-Liste, Zahlen, Warteschlange, Pläne, Drehbücher, Vorschaubilder und Anmeldungen und leert die
Kanal-Angaben (Client-IDs, Kanal-Namen). Behält Motor, Video-Arten, Klang-Bibliothek und gelernte Gegenstände. Vergibt ein neues
Kanal-Merkmal, damit die Kopie andere Themen, Figuren und Melodien wählt als das Original.

Sicherheitssperren: läuft nur auf GitHub, nie im Original-Repository, und nur mit dem Namen der Kopie als Bestätigung."""
import json
import os
import secrets
import shutil

from .state import CONFIG, DATA, DEFAULT_STATE, ROOT, STATE, STATS, VIDEOS, log, save

ORIGINAL = "quatratkopf/autoshorts"
# Kanal-Angaben, die zum alten Kanal gehören und in der Kopie leer starten
CHANNEL_KEYS = ("youtube_client_id", "tiktok_client_key", "tiktok_handle", "youtube_handle", "channel_name", "channel_focus")


def new_seed():
    return secrets.token_hex(4)


def reset(confirm: str):
    repo = (os.environ.get("GITHUB_REPOSITORY") or "").strip()
    if not repo:
        raise RuntimeError("„Neu einrichten“ läuft nur auf GitHub")
    if repo.lower() == ORIGINAL:
        raise RuntimeError("Das Original-Repository wird nie zurückgesetzt – nur eine eigene Kopie (Fork)")
    if (confirm or "").strip().lower() != repo.lower():
        raise RuntimeError(f"Bestätigung fehlt: als Thema genau „{repo}“ angeben")
    VIDEOS.clear()                                        # im Speicher leeren: main speichert am Ende alles
    STATE.clear()
    STATE.update(json.loads(json.dumps(DEFAULT_STATE)))
    STATS.clear()
    STATS.update({"v": {}, "ch": {}, "updated": 0})
    for name, empty in (("insights.json", {}), ("wishes.json", []), ("plans.json", {})):
        if (DATA / name).exists():
            save(name, empty)
    for d in (DATA / "scripts", ROOT / "docs" / "thumbs"):
        if d.is_dir():
            shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)
        (d / ".gitkeep").write_text("", encoding="utf-8")
    adm = ROOT / "docs" / "admin"                         # Zugangsliste des Admins gehört nicht in eine Kopie
    if adm.is_dir():
        shutil.rmtree(adm)
    tok = ROOT / "tokens"
    for f in tok.glob("*.enc") if tok.is_dir() else []:
        f.unlink()
    tok.mkdir(exist_ok=True)
    (tok / ".gitkeep").write_text("", encoding="utf-8")
    st = CONFIG.setdefault("settings", {})
    for k in CHANNEL_KEYS:
        st[k] = ""
    st["channel_seed"] = new_seed()
    CONFIG["queue"] = []
    save("config.json", CONFIG)
    log(f"{repo} neu eingerichtet: Videos, Zahlen, Warteschlange und Anmeldungen geleert, Kanal-Merkmal {st['channel_seed']}")
    return st["channel_seed"]


UPSTREAM = "https://github.com/QuatratKopf/autoshorts.git"
# Was „Motor aktualisieren“ aus dem Original holt – nie Daten, Einstellungen, Anmeldungen oder Videos dieser Kopie
ENGINE_PATHS = ("engine", "assets", "music", "docs/data/shapes.json", "README.md")


# Was der Admin bestimmt, solange der Gast es laut seinen Rechten (Admin-Tab) nicht selbst einstellen darf
ADMIN_SETTINGS = {"laenge": ("target_seconds", "min_seconds"),
                  "trends": ("trend_mode", "trend_regions", "make_thumbnail", "youtube_thumbnail", "audience"),
                  "ki": ("text_provider", "tts_provider", "gemini_voice", "voice_speed", "voice_style", "gemini_model"),
                  "stil": ("look", "caption_style", "subtitles_lowercase", "sfx_volume", "music_volume", "plan_ahead", "hold_missing", "auto_learn"),
                  "zahlen": ("stats_minutes", "stats_live")}
CAT_ADMIN = ("name", "emoji", "description", "script_style", "image_mood", "voice", "voice_rate", "voice_pitch", "voice_instructions",
             "caption_style", "look", "music_volume", "special", "every_days", "topic_examples", "topic_rules", "trends", "niche_queries")


def sync_admin_settings(admin_cfg, perms):
    """Einstellungen des Admins in diese Kopie übernehmen – nur, was der Gast nicht selbst einstellen darf. Gibt die Zahl der Änderungen zurück."""
    st = CONFIG.setdefault("settings", {})
    a_st = (admin_cfg or {}).get("settings") or {}
    n = 0
    for perm, keys in ADMIN_SETTINGS.items():
        if perms.get(perm):
            continue                                      # darf der Gast selbst einstellen: seine Wahl bleibt
        for k in keys:
            if k in a_st and st.get(k) != a_st[k]:
                st[k], n = a_st[k], n + 1
    mine = {c.get("slug"): c for c in CONFIG.setdefault("categories", []) if isinstance(c, dict)}
    for ac in (admin_cfg or {}).get("categories") or []:
        if not isinstance(ac, dict) or not ac.get("slug"):
            continue
        c = mine.get(ac["slug"])
        if c is None:                                     # neue Video-Art des Admins: kommt dazu
            CONFIG["categories"].append(json.loads(json.dumps(ac)))
            n += 1
            continue
        if perms.get("rubriken_bearbeiten"):
            continue                                      # der Gast pflegt seine Video-Arten selbst
        for k in CAT_ADMIN:
            if k in ac and c.get(k) != ac[k]:
                c[k], n = json.loads(json.dumps(ac[k])), n + 1
        if not perms.get("rubriken") and c.get("enabled") != ac.get("enabled"):
            c["enabled"], n = ac.get("enabled"), n + 1    # an/aus bestimmt dann auch der Admin
    if n:
        save("config.json", CONFIG)
    return n


def _admin_sync():
    """Einstellungen und Video-Arten des Admins holen (öffentliche Dateien des Originals) und passend übernehmen."""
    import subprocess
    import urllib.request
    base = "https://raw.githubusercontent.com/QuatratKopf/autoshorts/main/docs/"
    get = lambda f: json.loads(urllib.request.urlopen(urllib.request.Request(base + f, headers={"User-Agent": "AutoShorts/1.0"}), timeout=30).read(3_000_000))
    admin_cfg = get("data/config.json")
    try:
        acc = get("admin/access.json")
    except Exception:  # noqa: BLE001
        acc = {}
    aid = str(CONFIG.get("settings", {}).get("access_id") or "")
    e = next((x for x in acc.get("access", []) if isinstance(x, dict) and str(x.get("id")) == aid), None)
    perms = {**(acc.get("defaults") or {}), **((e or {}).get("perms") or {})}
    n = sync_admin_settings(admin_cfg, perms)
    if n:
        subprocess.run(["git", "add", "docs/data/config.json"], cwd=ROOT, check=False)   # der Speicher-Schritt nimmt es mit
        log(f"Einstellungen des Admins übernommen: {n} Änderungen (nur, was dieser Kanal nicht selbst einstellen darf)")
    return n


def update_engine():
    """Kopie auf den neuesten Motor des Originals bringen (ohne „Sync fork“, das auch die Video-Daten des Originals mitbrächte)."""
    import subprocess
    repo = (os.environ.get("GITHUB_REPOSITORY") or "").strip()
    if not repo:
        raise RuntimeError("„Motor aktualisieren“ läuft nur auf GitHub")
    if repo.lower() == ORIGINAL:
        log("Das ist das Original – der Motor ist schon aktuell")
        return 0
    shapes_f = DATA / "shapes.json"
    try:                                                  # was diese Kopie selbst gelernt hat (fehlende Gegenstände nachgezeichnet)
        own = json.loads(shapes_f.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        own = {}
    subprocess.run(["git", "fetch", "-q", "--depth", "1", UPSTREAM, "main"], cwd=ROOT, check=True, timeout=300)
    subprocess.run(["git", "checkout", "FETCH_HEAD", "--", *ENGINE_PATHS], cwd=ROOT, check=True, timeout=120)
    try:                                                  # zusammenführen statt überschreiben: Gelerntes der Kopie bleibt, Neues vom Original kommt dazu
        merged = json.loads(shapes_f.read_text(encoding="utf-8"))
        kept = {k: v for k, v in own.items() if k not in merged}
        if kept and isinstance(merged, dict):
            merged.update(kept)
            save("shapes.json", merged)
            log(f"Eigene gelernte Gegenstände behalten: {len(kept)}")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        log(f"Gelernte Gegenstände nicht zusammengeführt ({e})")
    changed = subprocess.run(["git", "status", "--porcelain", "--", *ENGINE_PATHS], cwd=ROOT, capture_output=True, text=True).stdout.splitlines()
    log(f"Motor aus dem Original geholt: {len(changed)} Dateien neu oder geändert (Daten, Einstellungen und Videos bleiben)")
    try:
        n_set = _admin_sync()
    except Exception as e:  # noqa: BLE001 – ohne Einstellungs-Abgleich läuft der Kanal trotzdem weiter
        log(f"Einstellungen des Admins nicht abgeglichen ({str(e)[:120]})")
        n_set = 0
    return len(changed) + n_set
