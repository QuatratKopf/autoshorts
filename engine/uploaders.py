"""YouTube- und TikTok-Anbindung: Anmeldung (OAuth), Upload, Statistiken."""
import datetime as dt
import os
import re
import time
from zoneinfo import ZoneInfo

import requests

from .state import STATE, STATS, TIMEZONE, VIDEOS, cfg, drop_token, load_token, log, save_token, secret

T = 120
TZ = ZoneInfo(TIMEZONE)


def today():
    return dt.datetime.now(TZ).date().isoformat()


def connected(p):
    return load_token(p) is not None


# ================================================================ YouTube

def _yt_client():
    return cfg("youtube_client_id") or secret("GOOGLE_CLIENT_ID"), secret("GOOGLE_CLIENT_SECRET")


def _yt_access():
    tok = load_token("youtube")
    if not tok:
        raise RuntimeError("YouTube nicht verbunden")
    if time.time() > tok.get("expires_at", 0):
        cid, csec = _yt_client()
        r = requests.post("https://oauth2.googleapis.com/token", data={
            "client_id": cid, "client_secret": csec,
            "refresh_token": tok["refresh_token"], "grant_type": "refresh_token"}, timeout=T)
        if r.status_code == 400 and "invalid_grant" in r.text:
            drop_token("youtube")
            raise RuntimeError("YouTube-Anmeldung abgelaufen – bitte in der App neu verbinden "
                               "(Tipp: Google-App auf 'In Produktion' stellen, sonst läuft sie nach 7 Tagen ab).")
        r.raise_for_status()
        tok.update(r.json())
        tok["expires_at"] = time.time() + tok.get("expires_in", 3600) - 60
        save_token("youtube", tok)
    return tok["access_token"]


def yt_upload(v, path):
    h = {"Authorization": "Bearer " + _yt_access()}
    tags = v.get("hashtags") or []
    desc = (v.get("description") or "") + "\n\n" + " ".join(tags)
    kw = (v.get("tags") or []) + [t.lstrip("#") for t in tags if t.lower() != "#shorts"]
    keep, n = [], 0
    for k in kw:   # YouTube erlaubt zusammen max. 500 Zeichen
        if k and k not in keep and n + len(k) + 1 < 480:
            keep.append(k)
            n += len(k) + 1
    meta = {"snippet": {"title": v["title"][:100], "description": desc[:4900],
                        "tags": keep,
                        "categoryId": str(cfg("youtube_category") or "24"),
                        "defaultLanguage": "de", "defaultAudioLanguage": "de"},
            "status": {"privacyStatus": cfg("youtube_privacy") or "public",
                       "selfDeclaredMadeForKids": False,
                       "containsSyntheticMedia": bool(cfg("ai_label"))}}
    size = os.path.getsize(path)
    r = requests.post("https://www.googleapis.com/upload/youtube/v3/videos",
                      params={"uploadType": "resumable", "part": "snippet,status"},
                      headers={**h, "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)},
                      json=meta, timeout=T)
    if r.status_code >= 400:
        raise RuntimeError(f"YouTube {r.status_code}: {r.text[:400]}")
    with open(path, "rb") as f:
        r2 = requests.put(r.headers["Location"], headers={**h, "Content-Type": "video/mp4"}, data=f, timeout=900)
    if r2.status_code >= 400:
        raise RuntimeError(f"YouTube-Upload {r2.status_code}: {r2.text[:400]}")
    js = r2.json()
    cover = path.parent / f"{v['id']}-cover.jpg"
    if cfg("youtube_thumbnail") and cover.exists():
        try:
            with open(cover, "rb") as f:
                r3 = requests.post("https://www.googleapis.com/upload/youtube/v3/thumbnails/set", params={"videoId": js["id"], "uploadType": "media"},
                                   headers={**h, "Content-Type": "image/jpeg"}, data=f, timeout=120)
            if r3.status_code >= 400:
                log("YouTube-Thumbnail nicht gesetzt (eigene Thumbnails gehen erst, wenn der Kanal per Telefon "
                    f"bestätigt ist: youtube.com/verify): {r3.text[:160]}")
            else:
                log("YouTube-Thumbnail gesetzt")
        except Exception as e:  # noqa: BLE001
            log(f"YouTube-Thumbnail: {e}")
    return js["id"], js.get("status", {}).get("privacyStatus", "")


def yt_stats(ids):
    out, h = {}, {"Authorization": "Bearer " + _yt_access()}
    for i in range(0, len(ids), 50):
        r = requests.get("https://www.googleapis.com/youtube/v3/videos",
                         params={"part": "statistics,status", "id": ",".join(ids[i:i + 50])}, headers=h, timeout=T)
        r.raise_for_status()
        for it in r.json().get("items", []):
            s = it.get("statistics", {})
            out[it["id"]] = dict(views=int(s.get("viewCount", 0)), likes=int(s.get("likeCount", 0)),
                                 comments=int(s.get("commentCount", 0)), shares=0,
                                 privacy=it.get("status", {}).get("privacyStatus", ""))
    return out


def yt_channel():
    r = requests.get("https://www.googleapis.com/youtube/v3/channels", params={"part": "statistics,snippet", "mine": "true"},
                     headers={"Authorization": "Bearer " + _yt_access()}, timeout=T)
    r.raise_for_status()
    it = (r.json().get("items") or [{}])[0]
    return int(it.get("statistics", {}).get("subscriberCount", 0)), it.get("snippet", {}).get("title", "")


# ================================================================ TikTok

TT_API = "https://open.tiktokapis.com/v2"


def _tt_token(data):
    r = requests.post(TT_API + "/oauth/token/", data={"client_key": cfg("tiktok_client_key") or secret("TIKTOK_CLIENT_KEY"),
                                                      "client_secret": secret("TIKTOK_CLIENT_SECRET"), **data},
                      headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=T)
    js = r.json()
    if r.status_code >= 400 or "access_token" not in js:
        raise RuntimeError(f"TikTok-Anmeldung: {js}")
    js["expires_at"] = time.time() + js.get("expires_in", 86400) - 120
    save_token("tiktok", js)


def _tt_h():
    tok = load_token("tiktok")
    if not tok:
        raise RuntimeError("TikTok nicht verbunden")
    if time.time() > tok.get("expires_at", 0):
        try:
            _tt_token({"grant_type": "refresh_token", "refresh_token": tok["refresh_token"]})
        except Exception:
            drop_token("tiktok")
            raise RuntimeError("TikTok-Anmeldung abgelaufen – bitte in der App neu verbinden.")
        tok = load_token("tiktok")
    return {"Authorization": "Bearer " + tok["access_token"], "Content-Type": "application/json; charset=UTF-8"}


def _tt_ok(r, what):
    js = r.json() if r.content else {}
    err = js.get("error", {})
    if r.status_code >= 400 or (err and err.get("code") not in (None, "", "ok")):
        raise RuntimeError(f"TikTok {what}: {err.get('code')} – {err.get('message') or r.text[:300]}")
    return js.get("data", {})


def tt_upload(v, path):
    h = _tt_h()
    size = os.path.getsize(path)
    chunk = size if size <= 64 * 1024 * 1024 else 10 * 1024 * 1024
    count = max(1, size // chunk)
    source = {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": chunk, "total_chunk_count": count}
    if (cfg("tiktok_mode") or "direct") == "direct":
        info = _tt_ok(requests.post(TT_API + "/post/publish/creator_info/query/", headers=h, json={}, timeout=T),
                      "Creator-Info")
        options = info.get("privacy_level_options") or ["SELF_ONLY"]
        want = cfg("tiktok_privacy") or "SELF_ONLY"
        privacy = want if want in options else ("SELF_ONLY" if "SELF_ONLY" in options else options[0])
        caption = f"{v['title']}\n\n{' '.join(v.get('hashtags') or [])}"[:2100]
        body = {"post_info": {"title": caption, "privacy_level": privacy, "disable_comment": False,
                              "disable_duet": False, "disable_stitch": False,
                              "is_aigc": bool(cfg("ai_label")),
                              **({"video_cover_timestamp_ms": int(v["cover_ms"])} if v.get("cover_ms") else {}),
                              "brand_content_toggle": False, "brand_organic_toggle": False},
                "source_info": source}
        data = _tt_ok(requests.post(TT_API + "/post/publish/video/init/", headers=h, json=body, timeout=T), "Init")
    else:
        privacy = "Entwurf"
        data = _tt_ok(requests.post(TT_API + "/post/publish/inbox/video/init/", headers=h,
                                    json={"source_info": source}, timeout=T), "Init")
    pid, url = data["publish_id"], data["upload_url"]
    with open(path, "rb") as f:
        for i in range(count):
            start = i * chunk
            n = size - start if i == count - 1 else chunk
            r = requests.put(url, data=f.read(n), timeout=900, headers={
                "Content-Type": "video/mp4", "Content-Length": str(n),
                "Content-Range": f"bytes {start}-{start + n - 1}/{size}"})
            if r.status_code >= 400:
                raise RuntimeError(f"TikTok-Upload {r.status_code}: {r.text[:300]}")
    status, post_id = "PROCESSING", ""
    for _ in range(60):
        time.sleep(5)
        d = _tt_ok(requests.post(TT_API + "/post/publish/status/fetch/", headers=_tt_h(),
                                 json={"publish_id": pid}, timeout=T), "Status")
        status = d.get("status", "")
        ids = d.get("publicaly_available_post_id") or d.get("publicly_available_post_id") or []
        if ids:
            post_id = str(ids[0])
        if status == "FAILED":
            raise RuntimeError(f"TikTok: Veröffentlichung fehlgeschlagen ({d.get('fail_reason')})")
        if status in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX"):
            break
    return pid, post_id, {"PUBLISH_COMPLETE": "veröffentlicht", "SEND_TO_USER_INBOX": "als Entwurf in der App"}.get(
        status, status.lower()) + (f" · {privacy}" if privacy != "Entwurf" else "")


def tt_videos():
    out, cursor = [], None
    for _ in range(3):
        body = {"max_count": 20, **({"cursor": cursor} if cursor else {})}
        d = _tt_ok(requests.post(TT_API + "/video/list/", headers=_tt_h(), json=body, timeout=T,
                                 params={"fields": "id,title,video_description,create_time,share_url,"
                                                   "view_count,like_count,comment_count,share_count"}), "Videoliste")
        out += d.get("videos", [])
        if not d.get("has_more"):
            break
        cursor = d.get("cursor")
    return out


def tt_user():
    d = _tt_ok(requests.get(TT_API + "/user/info/", headers=_tt_h(), timeout=T,
                            params={"fields": "display_name,follower_count,likes_count,video_count"}), "Profil")
    u = d.get("user", {})
    return int(u.get("follower_count", 0)), u.get("display_name", "")


# ================================================================ Gemeinsam

# ================================================================ Zernio (ein Zugang für YouTube + TikTok)
# Offizielle Schnittstelle des Dienstes: https://docs.zernio.com – das Video wird über seine öffentliche Adresse
# (GitHub-Release) übergeben; Zernio lädt es über seine eigenen, von den Plattformen zugelassenen Apps hoch.

ZERNIO = "https://zernio.com/api/v1"


def zernio_ready():
    return (cfg("upload_via") or "direct") == "zernio" and bool(secret("ZERNIO_API_KEY"))


def _z(method, path, **kw):
    r = requests.request(method, ZERNIO + path, headers={"Authorization": "Bearer " + secret("ZERNIO_API_KEY")}, timeout=T, **kw)
    try:
        data = r.json()
    except ValueError:
        data = {"raw": r.text[:300]}
    if r.status_code >= 300:
        msg = (data.get("error") or data.get("message") or data) if isinstance(data, dict) else data
        raise RuntimeError(f"Zernio HTTP {r.status_code}: {str(msg)[:300]}")
    return data


def zernio_accounts():
    """Verbundene Konten: {plattform: Konto-ID} (erstes Konto je Plattform)."""
    data = _z("GET", "/accounts")
    rows = data if isinstance(data, list) else next((data[k] for k in ("accounts", "data", "items") if isinstance(data.get(k), list)), [])
    out = {}
    for a in rows:
        if isinstance(a, dict) and a.get("platform") and (a.get("_id") or a.get("id")):
            out.setdefault(str(a["platform"]).lower(), str(a.get("_id") or a.get("id")))
    return out


def zernio_upload(v):
    """Ein Auftrag für alle eingeschalteten Plattformen. Gibt {plattform: (status, adresse)} zurück."""
    repo = os.environ.get("GITHUB_REPOSITORY") or "QuatratKopf/autoshorts"
    base = f"https://github.com/{repo}/releases/download/videos/"
    acc = zernio_accounts()
    tags = v.get("hashtags") or []
    kw, n = [], 0
    for k in (v.get("tags") or []) + [t.lstrip("#") for t in tags if t.lower() != "#shorts"]:
        if k and k not in kw and n + len(k) + 1 < 480:
            kw.append(k)
            n += len(k) + 1
    media = {"type": "video", "url": base + f"{v['id']}.mp4"}
    if cfg("make_thumbnail") and v.get("thumb"):
        media["thumbnail"] = base + f"{v['id']}-cover.jpg"
    plats = []
    if cfg("youtube_enabled") and acc.get("youtube") and not v.get("yt_id"):
        plats.append({"platform": "youtube", "accountId": acc["youtube"],
                      "platformSpecificData": {"title": v["title"][:100], "visibility": cfg("youtube_privacy") or "public",
                                               "categoryId": str(cfg("youtube_category") or "24"), "madeForKids": False}})
    if cfg("tiktok_enabled") and acc.get("tiktok") and not v.get("tt_publish_id"):
        plats.append({"platform": "tiktok", "accountId": acc["tiktok"]})
    if not plats:
        raise RuntimeError("Bei Zernio ist kein passendes Konto verbunden (YouTube/TikTok) – verbinde die Konten auf zernio.com.")
    foot = str(cfg("description_footer") or "").strip()
    body = {"content": ((v.get("description") or v["title"]) + ("\n\n" + foot if foot else "") + "\n\n" + " ".join(tags))[:2100], "tags": kw, "mediaItems": [media],
            "platforms": plats, "publishNow": True}
    if any(p["platform"] == "tiktok" for p in plats):
        body["tiktokSettings"] = {"privacy_level": cfg("tiktok_privacy") or "PUBLIC_TO_EVERYONE", "allow_comment": True, "allow_duet": True,
                                  "allow_stitch": True, "content_preview_confirmed": True, "express_consent_given": True,
                                  "draft": (cfg("tiktok_mode") or "direct") == "inbox"}
        if v.get("cover_ms"):                              # Titelbild = das eigens gestaltete Standbild am Ende des Videos
            body["tiktokSettings"]["video_cover_timestamp_ms"] = int(v["cover_ms"])
    data = _z("POST", "/posts", json=body)
    post = data.get("post") if isinstance(data.get("post"), dict) else data
    pid = post.get("_id") or post.get("id")
    v["zernio_id"] = pid
    for _ in range(18):                                   # bis zu drei Minuten auf das Ergebnis warten
        rows = post.get("platforms") or []
        if rows and all(str(r.get("status") or "").lower() in ("published", "failed", "error") for r in rows if isinstance(r, dict)):
            break
        if not pid:
            break
        time.sleep(10)
        try:
            d2 = _z("GET", f"/posts/{pid}")
            post = d2.get("post") if isinstance(d2.get("post"), dict) else d2
        except Exception:  # noqa: BLE001 – Abfrage nicht möglich: mit dem letzten Stand weiter
            break
    out = {}
    for r in post.get("platforms") or []:
        if isinstance(r, dict) and r.get("platform"):
            out[str(r["platform"]).lower()] = (str(r.get("status") or "unbekannt").lower(), r.get("platformPostUrl") or "",
                                               str(r.get("errorMessage") or r.get("error") or "")[:200])
    return out


def _upload_zernio(v):
    errors = []
    try:
        log("Übergebe das Video an Zernio …")
        res = zernio_upload(v)
        for plat, (status, url, err) in res.items():
            ok = status not in ("failed", "error")
            if plat == "youtube":
                v["yt_status"] = ("Zernio: " + status) if ok else "Fehler"
                if ok:
                    v["yt_id"] = (url.rstrip("/").split("/")[-1].split("=")[-1] if url else "") or f"zernio:{v.get('zernio_id')}"
            elif plat == "tiktok":
                v["tt_status"] = ("Zernio: " + status) if ok else "Fehler"
                if ok:
                    v["tt_publish_id"] = f"zernio:{v.get('zernio_id')}"
            log(f"Zernio · {plat}: {status}" + (f" · {url}" if url else "") + (f" · {err}" if err else ""))
            if not ok:
                errors.append(f"{plat} (Zernio): {err or status}")
        if not res:
            log("Zernio hat den Auftrag angenommen; das Ergebnis je Plattform steht in deinem Zernio-Konto.")
            v["yt_status"] = v["tt_status"] = "Zernio: angenommen"
            v["tt_publish_id"] = v["tt_publish_id"] if v.get("tt_publish_id") else f"zernio:{v.get('zernio_id')}"
    except Exception as e:  # noqa: BLE001
        errors.append(f"Zernio: {e}")
        log(f"Zernio-Fehler: {e}")
    done = bool(v.get("yt_id")) or bool(v.get("tt_publish_id"))
    v["status"] = "published" if done and not errors else ("partial" if done else ("error" if errors else "rendered"))
    v["error"] = "\n".join(errors)[:900] or None


def upload_video(v, path):
    if zernio_ready():
        return _upload_zernio(v)
    errors = []
    if cfg("youtube_enabled") and connected("youtube") and not v.get("yt_id"):
        try:
            log("Lade auf YouTube hoch …")
            v["yt_id"], v["yt_status"] = yt_upload(v, path)
            log(f"YouTube fertig ({v['yt_status']}): https://youtube.com/shorts/{v['yt_id']}")
        except Exception as e:  # noqa: BLE001
            errors.append(f"YouTube: {e}")
            v["yt_status"] = "Fehler"
            log(f"YouTube-Fehler: {e}")
    if cfg("tiktok_enabled") and connected("tiktok") and not v.get("tt_publish_id"):
        try:
            log("Lade auf TikTok hoch …")
            v["tt_publish_id"], v["tt_post_id"], v["tt_status"] = tt_upload(v, path)
            log(f"TikTok fertig: {v['tt_status']}")
        except Exception as e:  # noqa: BLE001
            errors.append(f"TikTok: {e}")
            v["tt_status"] = "Fehler"
            log(f"TikTok-Fehler: {e}")
    done = bool(v.get("yt_id")) or bool(v.get("tt_publish_id"))
    v["status"] = "published" if done and not errors else ("partial" if done else ("error" if errors else "rendered"))
    v["error"] = "\n".join(errors)[:900] or None
    if not errors and not done:
        log("Keine Plattform verbunden – das Video liegt fertig in der App zum Herunterladen.")


def _put(vid, plat, s):
    rows = STATS["v"].setdefault(str(vid), {}).setdefault(plat, [])
    point = [today(), int(s.get("views", 0)), int(s.get("likes", 0)), int(s.get("comments", 0)), int(s.get("shares", 0))]
    if rows and rows[-1][0] == point[0]:
        rows[-1] = point
    else:
        rows.append(point)


def _put_channel(plat, n, name, login=True):
    rows = STATS["ch"].setdefault(plat, [])
    point = [today(), int(n)]
    if rows and rows[-1][0] == point[0]:
        rows[-1] = point
    else:
        rows.append(point)
    if login:                                              # nur echte Anmeldung zählt als „verbunden“ (nicht die öffentlichen Zahlen)
        STATE["connected"][plat] = {"name": name, "since": STATE["connected"].get(plat, {}).get("since") or today()}


def zernio_stats():
    """Zahlen der über Zernio veröffentlichten Videos (Aufrufe, Likes, Kommentare, Geteilt) je Plattform."""
    vids = [v for v in VIDEOS if v.get("zernio_id")][-40:]
    n = 0
    for v in vids:
        try:
            data = _z("GET", "/analytics", params={"postId": v["zernio_id"]})
        except Exception as e:  # noqa: BLE001
            if "analytics_addon_required" in str(e) or "HTTP 402" in str(e):
                log("Zernio-Statistik: Dein Zernio-Tarif enthält keine Analytics (Zusatzpaket nötig).")
                return n
            if "HTTP 429" in str(e):
                log("Zernio-Statistik: Abruf-Grenze erreicht – der Rest folgt beim nächsten Mal.")
                return n
            log(f"Zernio-Statistik für Video {v['id']}: {e}")
            continue
        for row in data.get("platformAnalytics") or []:
            a = row.get("analytics") if isinstance(row, dict) else None
            plat = str(row.get("platform") or "").lower() if isinstance(row, dict) else ""
            if plat in ("youtube", "tiktok") and isinstance(a, dict):
                _put(v["id"], plat, {k: a.get(k) or 0 for k in ("views", "likes", "comments", "shares")})
                n += 1
                url = row.get("platformPostUrl") or ""
                if plat == "tiktok" and url and not v.get("tt_url"):
                    v["tt_url"] = url
                if plat == "youtube" and url and str(v.get("yt_id") or "").startswith("zernio:"):
                    v["yt_id"] = url.rstrip("/").split("/")[-1].split("=")[-1]
    return n


def zernio_thumbnails():
    """Titelbild auf YouTube nachtragen (Zernio: POST /posts/{id}/update-metadata mit thumbnailUrl). Beim Veröffentlichen
    übernimmt YouTube es oft nicht; sobald das Video eine echte YouTube-ID hat, wird es hier gesetzt – höchstens dreimal
    versucht, das Ergebnis steht am Video (yt_thumb) und im Protokoll."""
    if not (cfg("youtube_thumbnail") and cfg("make_thumbnail")):
        return 0
    repo = os.environ.get("GITHUB_REPOSITORY") or "QuatratKopf/autoshorts"
    base = f"https://github.com/{repo}/releases/download/videos/"
    acc = None
    n = 0
    for v in [v for v in VIDEOS if v.get("zernio_id") and v.get("thumb")][-15:]:
        if v.get("yt_thumb") == "gesetzt":
            continue
        no_perm = "permission" in str(v.get("yt_thumb") or "").lower()   # Kanal noch nicht bestätigt: täglich neu versuchen
        if (no_perm and time.time() - float(v.get("yt_thumb_at") or 0) < 20 * 3600) or \
                (not no_perm and int(v.get("yt_thumb_tries") or 0) >= 3):
            continue
        v["yt_thumb_at"] = time.time()
        yid = str(v.get("yt_id") or "")
        if yid.startswith("zernio:"):                     # echte YouTube-ID aus dem Zernio-Auftrag holen
            try:
                d = _z("GET", f"/posts/{v['zernio_id']}")
                post = d.get("post") if isinstance(d.get("post"), dict) else d
                for r in post.get("platforms") or []:
                    if isinstance(r, dict) and str(r.get("platform") or "").lower() == "youtube":
                        url_p = str(r.get("platformPostUrl") or "")
                        st = str(r.get("status") or "").lower()
                        if url_p:
                            v["yt_id"] = yid = url_p.rstrip("/").split("/")[-1].split("=")[-1]
                        if st:
                            v["yt_status"] = "Zernio: " + st
            except Exception as e:  # noqa: BLE001
                log(f"Zernio-Auftrag {v['zernio_id']}: {str(e)[:120]}")
        if not yid or yid.startswith("zernio:"):
            continue
        v["yt_thumb_tries"] = int(v.get("yt_thumb_tries") or 0) + 1
        url = base + f"{v['id']}-cover.jpg"
        try:
            try:
                _z("POST", f"/posts/{v['zernio_id']}/update-metadata", json={"platform": "youtube", "thumbnailUrl": url})
            except RuntimeError as e:
                if "HTTP 4" not in str(e) or "HTTP 403" in str(e):
                    raise
                acc = acc if acc is not None else zernio_accounts()
                _z("POST", "/posts/_/update-metadata", json={"platform": "youtube", "videoId": yid, "accountId": acc.get("youtube"),
                                                            "thumbnailUrl": url})
            v["yt_thumb"] = "gesetzt"
            n += 1
            log(f"YouTube-Titelbild für Video {v['id']} gesetzt")
        except Exception as e:  # noqa: BLE001
            msg = str(e)[:240]
            v["yt_thumb"] = msg
            hint = (" – eigene Titelbilder gehen erst, wenn der YouTube-Kanal per Telefon bestätigt ist (youtube.com/verify)"
                    if re.search(r"verif|permission|forbidden|403", msg, re.I) else "")
            log(f"YouTube-Titelbild für Video {v['id']} nicht gesetzt: {msg}{hint}")
    return n


UA_WEB = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"


def tt_public(handle):
    """Öffentliche Profilzahlen ohne Anmeldung: (Follower, Likes, Videos, Name) aus der Profilseite – oder None."""
    h = re.sub(r"[^A-Za-z0-9._]", "", str(handle or "").lstrip("@"))
    if not h:
        return None
    r = requests.get(f"https://www.tiktok.com/@{h}", timeout=T, headers={"User-Agent": UA_WEB, "Accept-Language": "de-DE,de;q=0.9"})
    if r.status_code != 200:
        raise RuntimeError(f"TikTok-Profil HTTP {r.status_code}")
    f = re.search(r'"followerCount"\s*:\s*(\d+)', r.text)
    if not f:
        raise RuntimeError("TikTok-Profil: keine Zahlen gefunden (Seite verändert oder gesperrt)")
    g = lambda k: int((re.search(r'"' + k + r'"\s*:\s*(\d+)', r.text) or [0, 0])[1])   # noqa: E731
    name = (re.search(r'"nickname"\s*:\s*"([^"]{1,60})"', r.text) or [0, "@" + h])[1]
    return int(f.group(1)), g("heartCount"), g("videoCount"), name


def zernio_profile():
    """TikTok-Konto bei Zernio: (Benutzername, Follower oder None) – je nachdem, was Zernio mitliefert."""
    data = _z("GET", "/accounts")
    rows = data if isinstance(data, list) else next((data[k] for k in ("accounts", "data", "items") if isinstance(data.get(k), list)), [])
    for a in rows:
        if isinstance(a, dict) and str(a.get("platform") or "").lower() == "tiktok":
            user = a.get("username") or a.get("handle") or (a.get("profile") or {}).get("username") or ""
            n = None
            for k in ("followers", "followersCount", "followerCount", "follower_count"):
                for src in (a, a.get("profile") or {}, a.get("stats") or {}, a.get("metadata") or {}):
                    if isinstance(src, dict) and isinstance(src.get(k), (int, float)) and not isinstance(src.get(k), bool):
                        n = int(src[k])
            return str(user).lstrip("@"), n
    return "", None


def _num_text(txt):
    """„1,23 Tsd. Abonnenten“, „12.345 Aufrufe“ → Zahl."""
    m = re.search(r"([\d.,]+)\s*(tsd|mio|mrd|k|m|b)?\.?", str(txt or "").lower().replace("\xa0", " "))
    if not m:
        return 0
    raw, unit = m.group(1), m.group(2)
    if unit:
        v = float(raw.replace(",", ".")) if raw.count(",") + raw.count(".") <= 1 else float(raw.replace(".", "").replace(",", "."))
    else:
        v = float(re.sub(r"[.,]", "", raw) or 0)
    return int(v * {"tsd": 1e3, "k": 1e3, "mio": 1e6, "m": 1e6, "mrd": 1e9, "b": 1e9}.get(unit or "", 1))


def yt_public(handle):
    """Öffentliche YouTube-Kanalseite ohne Anmeldung: (Abonnenten, Name) – YouTube rundet die Abonnenten selbst."""
    h = re.sub(r"[^A-Za-z0-9._-]", "", str(handle or "").lstrip("@"))
    if not h:
        return None
    r = requests.get(f"https://www.youtube.com/@{h}/about", params={"hl": "de", "gl": "DE"}, timeout=T,
                     headers={"User-Agent": UA_WEB, "Accept-Language": "de-DE,de;q=0.9"})
    r.raise_for_status()
    m = (re.search(r'"subscriberCountText"\s*:\s*(?:\{"simpleText"\s*:\s*)?"([^"]{1,60})"', r.text)
         or re.search(r'"content"\s*:\s*"([\d.,\s]+(?:Tsd\.|Mio\.)?\s*Abonnent(?:en|in))"', r.text))
    if not m:
        raise RuntimeError("YouTube-Kanal: keine Abonnenten gefunden (Name richtig?)")
    name = (re.search(r'<meta property="og:title" content="([^"]{1,80})"', r.text) or [0, "@" + h])[1]
    return _num_text(m.group(1)), name


def tiktok_followers_fallback():
    """TikTok ohne eigene Anmeldung (Upload über Zernio): Follower über Zernio, sonst über das öffentliche Profil."""
    handle = str(cfg("tiktok_handle") or "").lstrip("@").strip()
    zn = None
    if zernio_ready():
        try:
            zh, zn = zernio_profile()
            handle = handle or zh
        except Exception as e:  # noqa: BLE001
            log(f"Zernio-Konto: {e}")
    if handle:
        STATE.setdefault("connected", {})
        STATE["tiktok_handle"] = handle
    if zn is not None:
        _put_channel("tiktok", zn, "@" + handle if handle else "TikTok", login=False)
        return zn
    if handle:
        res = tt_public(handle)
        if res:
            _put_channel("tiktok", res[0], res[3], login=False)
            return res[0]
    return None


def refresh_stats():
    log("Hole Statistiken …")
    if (cfg("upload_via") or "direct") == "zernio" and secret("ZERNIO_API_KEY"):
        try:
            log(f"Zernio: {zernio_stats()} Zahlenreihen aktualisiert")
            zernio_thumbnails()
        except Exception as e:  # noqa: BLE001
            log(f"Zernio-Statistik: {e}")
    for p in ("youtube", "tiktok"):
        if not connected(p):
            STATE["connected"].pop(p, None)
    if connected("youtube"):
        try:
            vids = [v for v in VIDEOS if v.get("yt_id")]
            st = yt_stats([v["yt_id"] for v in vids]) if vids else {}
            for v in vids:
                s = st.get(v["yt_id"])
                if s:
                    _put(v["id"], "youtube", s)
                    if s["privacy"]:
                        v["yt_status"] = s["privacy"]
            _put_channel("youtube", *yt_channel())
        except Exception as e:  # noqa: BLE001
            log(f"YouTube-Statistik: {e}")
    if connected("tiktok"):
        try:
            _put_channel("tiktok", *tt_user())
        except Exception as e:  # noqa: BLE001
            log(f"TikTok-Profil: {e}")
        try:
            remote = tt_videos()   # braucht den Scope video.list (nicht bei jeder App verfügbar)
            by_id = {str(x["id"]): x for x in remote}
            for v in [v for v in VIDEOS if v.get("tt_publish_id")]:
                x = by_id.get(str(v.get("tt_post_id") or ""))
                if not x:
                    t = (v.get("title") or "")[:40].lower()
                    x = next((r for r in remote if t and t in (r.get("title") or r.get("video_description") or "").lower()), None)
                    if x:
                        v["tt_post_id"] = str(x["id"])
                if x:
                    _put(v["id"], "tiktok", {"views": x.get("view_count", 0), "likes": x.get("like_count", 0),
                                             "comments": x.get("comment_count", 0), "shares": x.get("share_count", 0)})
        except Exception as e:  # noqa: BLE001
            log(f"TikTok-Videozahlen nicht verfügbar (Scope video.list fehlt?): {e}")
    if not connected("tiktok"):
        try:
            n = tiktok_followers_fallback()
            if n is not None:
                log(f"TikTok-Follower: {n}")
        except Exception as e:  # noqa: BLE001
            log(f"TikTok-Follower: {e}")
    if not connected("youtube") and cfg("youtube_handle"):   # Upload über Zernio: Abonnenten von der öffentlichen Kanalseite
        try:
            res = yt_public(cfg("youtube_handle"))
            if res:
                _put_channel("youtube", res[0], res[1], login=False)
                log(f"YouTube-Abonnenten: {res[0]}")
        except Exception as e:  # noqa: BLE001
            log(f"YouTube-Abonnenten: {e}")
    STATS["updated"] = time.time()
    STATE["last_stats"] = time.time()
    try:                                                  # Auswertung: was läuft am besten?
        from . import insights
        ins = insights.build()
        if ins.get("advice"):
            log("Analyse: " + ins["advice"][0])
    except Exception as e:  # noqa: BLE001
        log(f"Analyse: {e}")
