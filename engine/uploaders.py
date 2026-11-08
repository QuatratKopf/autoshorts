"""YouTube- und TikTok-Anbindung: Anmeldung (OAuth), Upload, Statistiken."""
import datetime as dt
import os
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

def upload_video(v, path):
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


def _put_channel(plat, n, name):
    rows = STATS["ch"].setdefault(plat, [])
    point = [today(), int(n)]
    if rows and rows[-1][0] == point[0]:
        rows[-1] = point
    else:
        rows.append(point)
    STATE["connected"][plat] = {"name": name, "since": STATE["connected"].get(plat, {}).get("since") or today()}


def refresh_stats():
    log("Hole Statistiken …")
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
    STATS["updated"] = time.time()
    STATE["last_stats"] = time.time()
