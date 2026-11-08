"""AutoShorts-Motor. Wird von GitHub Actions aufgerufen.

python -m engine.main auto                          Zeitplan prüfen, ggf. Video bauen; Statistik alle 3 h
python -m engine.main make --category grusel --topic "…" [--upload 0]
python -m engine.main upload --id 12                Upload wiederholen
python -m engine.main stats                         Zahlen holen
"""
import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import time

from PIL import Image

from . import ai, render, thumbnail, trends, uploaders, writer
from .schedule import due_slot, stats_due
from .state import load, CONFIG, OUT, STATE, THUMBS, VIDEOS, WORK, cat_trends, category, cfg, drop_token, log, save_all, video

RELEASE = "videos"


# ---------------------------------------------------------------- Video-Dateien als GitHub-Release-Anhang

def _gh(*args, check=True):
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=check)


def publish_mp4(path):
    if not os.environ.get("GH_TOKEN"):
        log("Kein GH_TOKEN – MP4 bleibt nur lokal.")
        return False
    try:
        if _gh("release", "view", RELEASE, check=False).returncode != 0:
            _gh("release", "create", RELEASE, "--title", "Videos", "--latest=false",
                "--notes", "Fertige Videos von AutoShorts. Wird automatisch befüllt.")
        _gh("release", "upload", RELEASE, *[str(p) for p in ([path] if not isinstance(path, list) else path)], "--clobber")
        return True
    except subprocess.CalledProcessError as e:
        log(f"MP4 konnte nicht gespeichert werden: {e.stderr[-300:]}")
        return False


def fetch_mp4(vid):
    path = OUT / f"{vid}.mp4"
    if not path.exists():
        _gh("release", "download", RELEASE, "-p", f"{vid}.mp4", "-D", str(OUT), "--clobber")
        _gh("release", "download", RELEASE, "-p", f"{vid}-cover.jpg", "-D", str(OUT), "--clobber", check=False)
    return path


def want_trend(cat):
    mode = cfg("trend_mode") or "half"
    if mode == "off" or not cat_trends(cat):
        return False
    if mode == "always":
        return True
    STATE["trend_flip"] = not STATE.get("trend_flip", False)   # jedes zweite Video
    return STATE["trend_flip"]


# ---------------------------------------------------------------- Auswahl

def pick(category_slug=None, topic=None):
    """Manuell gewählte Kategorie, sonst Warteschlange zuerst, sonst nächste aktive Kategorie im Wechsel."""
    if category_slug:
        cat = category(category_slug)
        if not cat:
            raise RuntimeError(f"Kategorie '{category_slug}' gibt es nicht.")
        return cat, topic, None, None
    used = set(STATE["used_queue"])
    queue = sorted((q for q in CONFIG["queue"] if q.get("id") not in used and category(q.get("category"))),
                   key=lambda q: q.get("created", 0))
    if queue:
        q = queue[0]
        return category(q["category"]), q["text"], q["id"], q.get("trend")
    cats = [c for c in CONFIG["categories"] if c.get("enabled")]
    if not cats:
        raise RuntimeError("Keine Kategorie aktiv – bitte im Studio mindestens eine einschalten.")
    slugs = [c["slug"] for c in cats]
    last = STATE.get("last_category")
    return (cats[(slugs.index(last) + 1) % len(cats)] if last in slugs else cats[0]), None, None, None


# ---------------------------------------------------------------- Video bauen

def find_trend(trend_id):
    if not trend_id:
        return None
    for it in load("trends.json", {"items": []}).get("items", []):
        if it.get("id") == trend_id:
            return {"title": it["title"], "source": it["source"], "news": it.get("news", [])[:3], "summary": it.get("summary", "")}
    return None


def make(category_slug=None, topic=None, upload=True, trend_id=None):
    cat, topic, qid, qtrend = pick(category_slug, topic)
    STATE["last_category"] = cat["slug"]
    vid = max([int(STATE.get("next_id") or 1)] + [int(v["id"]) + 1 for v in VIDEOS])
    STATE["next_id"] = vid + 1
    v = {"id": vid, "category": cat["slug"], "topic": topic or "", "status": "rendering", "created": time.time()}
    VIDEOS.append(v)
    work = WORK / f"v{vid}"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    final = OUT / f"{vid}.mp4"
    used = {}
    trend = qtrend or find_trend(trend_id)
    if trend:
        v["trend"] = {"title": trend["title"], "source": trend["source"]}
    log(f"Kategorie: {cat['emoji']} {cat['name']}")
    try:
        if not topic and want_trend(cat):
            log("Schaue, was gerade im Trend ist …")
            try:
                topic, trend = writer.trend_topic(cat)
            except Exception as e:  # noqa: BLE001
                log(f"Trend-Auswahl fehlgeschlagen ({e}) – nehme ein zeitloses Thema")
            if trend:
                log(f"Trend: {trend['title']} ({trend['source']})")
                v["trend"] = {"title": trend["title"], "source": trend["source"]}
            else:
                log("Kein passender Trend für diese Kategorie – nehme ein zeitloses Thema")
        if not topic:
            log("Suche ein neues Thema …")
            topic = writer.new_topic(cat)
        v["topic"] = topic
        if qid:
            STATE["used_queue"].append(qid)
        log(f"Thema: {topic}")

        log("Schreibe Drehbuch …")
        script, used["text"] = writer.write_script(cat, topic, trend)
        scenes = script["scenes"]
        v.update(title=script["title"], description=script["description"], hashtags=script["hashtags"],
                 tags=script.get("tags", []), thumb_text=script["thumbnail"]["text"])
        log(f"Titel: {script['title']} · {len(scenes)} Szenen")

        log("Spreche Text ein …")
        voice = work / "voice.mp3"
        words, used["voice"] = ai.speak(" ".join(s["text"] for s in scenes), voice, cat)
        total = ai.audio_duration(voice)
        times = render.scene_times(scenes, words, total)
        log(f"Sprecher fertig ({total:.0f} s)")

        seed = random.randint(1, 10_000_000)
        img_used = set()
        for i, sc in enumerate(scenes):
            out = work / f"img{i:02d}.jpg"
            try:
                img_used.add(ai.image(writer.image_prompt(sc, cat), out, seed + i * 7))
                log(f"Bild {i + 1}/{len(scenes)} fertig")
            except Exception as e:  # noqa: BLE001
                if i == 0:
                    raise
                log(f"Bild {i + 1} fehlgeschlagen ({e}) – nehme vorheriges Bild")
                shutil.copy(work / f"img{i - 1:02d}.jpg", out)
        used["images"] = ", ".join(sorted(img_used))

        cover = None
        if cfg("make_thumbnail"):
            log("Gestalte Thumbnail …")
            raw = work / "cover_raw.jpg"
            try:
                ai.image(writer.image_prompt({"image": script["thumbnail"]["image"]}, cat), raw, seed + 999)
            except Exception as e:  # noqa: BLE001
                log(f"Thumbnail-Bild fehlgeschlagen ({e}) – nehme das erste Szenenbild")
                shutil.copy(work / "img00.jpg", raw)
            cover = OUT / f"{vid}-cover.jpg"
            thumbnail.make_thumbnail(raw, script["thumbnail"]["text"] or script["title"], cover)

        log("Schneide Video …")
        ass = work / "subs.ass"
        render.build_ass(words, scenes, times, ass, bool(cfg("subtitles_lowercase")))
        v["cover_ms"] = render.render(work, scenes, times, voice, ass, final, render.pick_music(cat["slug"]),
                                      float(cfg("music_volume") or 0.1), cover)
        Image.open(cover or (work / "img00.jpg")).resize((360, 640)).save(THUMBS / f"{vid}.jpg", quality=82)
        v.update(status="rendered", duration=round(total + 0.35, 1), providers=used, thumb=True)
        v["mp4"] = publish_mp4([final, cover] if cover else final)
        log(f"Video {vid} fertig")
    except Exception as e:
        v.update(status="error", error=str(e)[:900])
        raise
    finally:
        shutil.rmtree(work, ignore_errors=True)
        save_all()

    if upload:
        uploaders.upload_video(v, final)
        save_all()
    return v


def upload(vid):
    v = video(vid)
    if not v:
        raise RuntimeError(f"Video {vid} nicht gefunden")
    uploaders.upload_video(v, fetch_mp4(vid))


# ---------------------------------------------------------------- Einstieg

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("action", nargs="?", default="auto")
    ap.add_argument("--category", default="")
    ap.add_argument("--topic", default="")
    ap.add_argument("--upload", default="1")
    ap.add_argument("--id", default="")
    ap.add_argument("--trend", default="")
    a = ap.parse_args(argv)
    failed = False
    try:
        if a.action == "auto":
            slot = due_slot(CONFIG, STATE)
            if slot:
                STATE["done_slots"].append(slot)
                save_all()
                log(f"Autopilot: Video für {slot}")
                try:
                    make()
                except Exception as e:  # noqa: BLE001
                    failed = True
                    log(f"FEHLER: {e}")
            if stats_due(STATE):
                uploaders.refresh_stats()
                try:
                    trends.refresh()
                except Exception as e:  # noqa: BLE001
                    log(f"Trends: {e}")
        elif a.action == "make":
            make(a.category.strip() or None, a.topic.strip() or None, a.upload != "0", a.trend.strip() or None)
        elif a.action == "upload":
            upload(int(a.id))
        elif a.action == "stats":
            uploaders.refresh_stats()
            trends.refresh()
        elif a.action == "disconnect":   # Plattform trennen: Anmeldung und abgerufene Zahlen löschen
            plat = a.category.strip()
            if plat not in ("youtube", "tiktok"):
                raise SystemExit("Plattform fehlt")
            drop_token(plat)
            log(f"{plat} getrennt, Anmeldung und Zahlen gelöscht")
        elif a.action == "trends":
            trends.refresh()
        else:
            raise SystemExit(f"Unbekannte Aktion: {a.action}")
    except Exception as e:  # noqa: BLE001
        failed = True
        log(f"FEHLER: {e}")
    finally:
        save_all()
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        last = VIDEOS[-1] if VIDEOS else None
        with open(summary, "a", encoding="utf-8") as f:
            f.write(f"### AutoShorts · {a.action}\n\n")
            if last and a.action in ("make", "auto", "upload"):
                f.write(f"Letztes Video: **{last.get('title') or last.get('topic')}** – Status `{last.get('status')}`\n")
            f.write("\n```json\n" + json.dumps(STATE.get("connected"), ensure_ascii=False) + "\n```\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
