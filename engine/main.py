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
from .schedule import due_slot, plan_slot, review_slot, review_stale, stats_due
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
    try:                                                  # Analyse: was besser läuft, kommt öfter dran
        from . import insights
        best = insights.pick_category(cats, STATE)
        if best:
            log(f"Analyse: {best['name']} ist dran (läuft überdurchschnittlich oder wird ausprobiert)")
            return best, None, None, None
    except Exception as e:  # noqa: BLE001
        log(f"Analyse übersprungen ({e})")
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


def known_thing(word):
    """Kann die Engine das zeichnen? (Requisite, Gegenstand in der Hand, Wesen, Ort, Landschafts-Baustein, gelernte Bibliothek)"""
    from .toon import extras, places, stage
    w = str(word or "").lower().strip()
    if len(w) < 3:
        return True
    pool = (set(extras.PROPS) | set(extras.PROP_ALIASES) | set(extras.HELD) | set(extras.CREATURES) | set(places.PLACES) | set(places.ALIASES)
            | set(places.OUTDOOR_SPECS) | set(places.EL_ALIASES) | set(places.BACK) | set(places.MID) | set(places.FRONT_EL)
            | {"mensch", "menschen", "leute", "person", "personen", "figur", "mann", "frau", "kind", "kinder", "menge", "familie",
               "katze", "hund", "spinne", "geist", "roboter", "vogel", "vögel", "dinosaurier", "fisch", "fische", "hai", "biene", "bienen",
               "wespe", "gehirn", "hirn", "himmel", "boden", "licht", "dunkelheit", "nacht", "regen", "schnee", "sturm", "wind", "nebel", "erdbeben", "hitze"})
    forms = {w, w.rstrip("n"), w.rstrip("en"), w.rstrip("e"), w.rstrip("s"), w + "e", w + "n", w + "en"}
    if forms & pool:
        return True
    if any(len(k) >= 4 and (k in w or (len(w) >= 5 and w in k)) for k in pool):
        return True
    import re as _re
    return any(_re.search(pat, w) for pat, _ in stage.TEXT_PROPS + stage._lib_props() + stage.GRAPHIC_WORDS + stage.SEA_CREATURES + stage.ANY_CREATURES) or any(_re.search(pat, w) for pat, _ in stage.HINTS)


def missing_things(script, topic):
    """Was braucht dieses Video, das die Engine (noch) nicht zeichnen kann? Wünsche des Drehbuchs + Gegenprobe zum Thema."""
    from .state import load
    from .toon import library
    library.load_all(load("shapes.json", {}))
    words = [w for w in (script.get("wishes") or []) if isinstance(w, str)]
    try:
        words += writer.needed_things(topic, script)
    except Exception as e:  # noqa: BLE001
        log(f"Gegenprobe zum Thema nicht möglich ({e})")
    out = []
    for w in words:
        k = w.strip().lower()
        if k and k not in out and not known_thing(k):
            out.append(k)
    return out[:6]


def _stems(text):
    import re as _re
    return {w[:6] for w in _re.findall(r"[a-zäöüß]{5,}", str(text or "").lower())
            if w not in ("wäre", "würde", "passiert", "plötzlich", "morgen", "menschen", "alles", "unsere", "wirklich", "komplett", "einfach")}


def too_similar(topic, trend=None, published_only=False, skip_slot=None):
    """Gab es dieses Thema in den letzten Videos schon (fast) genauso? Vergleicht die tragenden Wörter.
    Zählt auch, was für einen anderen Termin schon vorbereitet ist (plans.json) – sonst entsteht aus demselben Trend
    an zwei Terminen hintereinander zweimal dasselbe Video. published_only: nur veröffentlichte Videos zählen."""
    a = _stems(topic)
    olds = [o for o in VIDEOS[-40:] if not published_only or o.get("status") == "published"]
    if not published_only:
        try:
            from .state import load
            olds += [{"topic": pl.get("topic"), "title": pl.get("title"), "trend": pl.get("trend")}
                     for k, pl in load("plans.json", {}).items() if k != skip_slot and isinstance(pl, dict)]
        except Exception:  # noqa: BLE001
            pass
    for old in olds:
        if trend and old.get("trend") and old["trend"].get("title") == trend.get("title"):
            return old.get("title") or old.get("topic")
        b = _stems(f"{old.get('topic') or ''} {old.get('title') or ''}")
        if a and b and len(a & b) >= max(2, round(0.5 * len(a))):
            return old.get("title") or old.get("topic")
    return None


def draft(cat, topic, trend, v=None, source=None):
    """Thema finden und Drehbuch schreiben (ohne Ton und Bild)."""
    v = v if v is not None else {}
    if not topic and not source and want_trend(cat):
        log("Schaue, was gerade im Trend ist …")
        try:
            topic, trend = writer.trend_topic(cat)
        except Exception as e:  # noqa: BLE001
            log(f"Trend-Auswahl fehlgeschlagen ({e}) – nehme ein zeitloses Thema")
        dup = too_similar(topic, trend) if topic else None
        if dup:                                           # derselbe Trend wie neulich → lieber etwas Neues
            log(f"Das Trend-Thema gab es gerade erst („{dup}“) – nehme ein anderes")
            topic, trend = None, None
        if trend:
            log(f"Trend: {trend['title']} ({trend['source']})")
            v["trend"] = {"title": trend["title"], "source": trend["source"]}
        else:
            log("Kein passender Trend für diese Kategorie – nehme ein zeitloses Thema")
    if not topic:
        log("Suche ein neues Thema …")
        topic = writer.new_topic(cat)
        for _ in range(2):
            dup = too_similar(topic)
            if not dup:
                break
            log(f"Zu ähnlich zu „{dup}“ – suche noch einmal")
            topic = writer.new_topic(cat)
    v["topic"] = topic
    log(f"Thema: {topic}")
    log("Schreibe Drehbuch …")
    script, provider = writer.write_script(cat, topic, trend, source)
    return topic, trend, script, provider


def note_wishes(words, title):
    from .state import load, save
    wl = load("wishes.json", {})
    for w in words:
        k = w.strip().lower()
        if k:
            wl[k] = {"n": wl.get(k, {}).get("n", 0) + 1, "last": title}
    save("wishes.json", wl)


def prepare(slot):
    """Vorproduktion: Thema und Drehbuch für den nächsten Termin schon jetzt festlegen und aufschreiben, was der Engine dafür
    fehlt – so kann es bis zum Termin nachgebaut werden, bevor das Video entsteht und hochgeladen wird."""
    from .state import load, save
    plans = load("plans.json", {})
    if slot in plans:
        return plans[slot]
    cat, topic, qid, qtrend = pick(None, None)
    log(f"Vorproduktion für {slot}: {cat['emoji']} {cat['name']}")
    topic, trend, script, provider = draft(cat, topic, qtrend)
    if qid:
        STATE["used_queue"].append(qid)
    STATE["last_category"] = cat["slug"]
    needs = missing_things(script, topic) if script.get("toon") else []
    plans[slot] = {"category": cat["slug"], "topic": topic, "trend": trend, "script": script, "provider": provider,
                   "needs": needs, "title": script.get("title"), "created": time.time()}
    for k in sorted(plans)[:-4]:                          # nur die letzten Pläne aufheben
        plans.pop(k, None)
    save("plans.json", plans)
    if needs:
        note_wishes(needs, script.get("title") or topic)
        log("Für dieses Video muss noch gebaut werden: " + ", ".join(needs))
    else:
        log("Für dieses Video ist alles vorhanden.")
    return plans[slot]


def make(category_slug=None, topic=None, upload=True, trend_id=None, plan=None, source=None):
    plan = plan or {}
    if plan.get("script") and category(plan.get("category")):
        dup = too_similar(f"{plan.get('topic') or ''} {plan.get('title') or ''}", published_only=True)
        if dup:                                           # derselbe Stoff ist inzwischen schon online: nicht noch einmal
            log(f"Vorbereitetes Thema gab es gerade erst („{dup}“) – suche ein neues Thema")
            category_slug, topic, plan = category_slug or plan.get("category"), None, {}
    if plan.get("script") and category(plan.get("category")):
        cat, topic, qid, qtrend = category(plan["category"]), plan.get("topic"), None, plan.get("trend")
    else:
        plan = {}
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
        if plan.get("script"):                           # vorbereitetes Drehbuch: reicht es noch für die Mindestlänge?
            wps_p = float(STATE.get("voice_wps") or 0)
            wps_p = wps_p if 1.6 <= wps_p <= 3.6 else 2.5
            n_plan = writer.spoken_words(plan["script"])
            min_p = float(cfg("min_seconds") or 0)
            if min_p and n_plan / wps_p < min_p - 5:      # viel zu kurz: sonst stünde am Ende sekundenlang ein stummes Standbild
                log(f"Vorbereitetes Drehbuch ist zu kurz ({n_plan} Wörter ≈ {n_plan / wps_p:.0f} s) – schreibe es zum selben Thema neu")
                try:
                    _t, _tr, fresh, prov = draft(cat, topic, trend, v)
                    if writer.spoken_words(fresh) > n_plan:
                        plan = {**plan, "script": fresh, "provider": prov, "needs": missing_things(fresh, topic) if fresh.get("toon") else []}
                except Exception as e:  # noqa: BLE001
                    log(f"Neu schreiben nicht möglich ({e}) – nehme das vorbereitete Drehbuch")
            else:
                try:
                    plan["script"] = writer.polish(plan["script"])       # ß und deutsche Einblendungen auch bei älteren Plänen
                except Exception:  # noqa: BLE001
                    pass
        if plan.get("script"):                           # vorbereitetes Drehbuch (am Vortag geplant, Fehlendes inzwischen nachgebaut)
            script, used["text"] = plan["script"], plan.get("provider") or "Plan"
            v["topic"] = topic
            log(f"Thema (vorbereitet): {topic}")
        else:
            topic, trend, script, used["text"] = draft(cat, topic, trend, v, source)
            if source:
                v["remake"] = True
            if qid:
                STATE["used_queue"].append(qid)
        scenes = script["scenes"]
        v.update(title=script["title"], description=script["description"], hashtags=script["hashtags"],
                 tags=script.get("tags", []), thumb_text=script["thumbnail"]["text"])
        log(f"Titel: {script['title']} · {len(scenes)} Szenen")
        needs = []
        if script.get("toon"):          # was fehlt der Engine für dieses Video (noch)?
            needs = [w for w in (plan.get("needs") or []) if not known_thing(w)] if plan else missing_things(script, topic)
            if needs and not plan:
                note_wishes(needs, script["title"])
            if needs:
                log("Der Engine fehlt für dieses Video: " + ", ".join(needs))
                script["wishes"] = needs
            else:
                script["wishes"] = []
        if script.get("toon"):          # lernende Bibliothek: Gelerntes laden, Fehlendes für dieses Video nachzeichnen lassen
            try:
                from .state import load, save
                from .toon import library
                shapes = load("shapes.json", {})
                library.load_all(shapes)
                if cfg("auto_learn") is not False and script.get("wishes"):
                    new = library.learn(script["wishes"], ai.chat_json, shapes, log)
                    if new:
                        shapes.update(new)
                        save("shapes.json", shapes)
            except Exception as e:  # noqa: BLE001 – die Bibliothek darf nie ein Video verhindern
                log(f"Bibliothek übersprungen ({type(e).__name__}: {e})")
            needs = [w for w in needs if not known_thing(w)]
        v["missing"] = needs or None

        log("Spreche Text ein …")
        voice = work / "voice.mp3"
        words, used["voice"] = ai.speak(" ".join(s["text"] for s in scenes), voice, cat)
        total = ai.audio_duration(voice)
        n_spoken = sum(len(s["text"].split()) for s in scenes)
        if total > 20 and n_spoken > 40:                 # Sprechtempo merken → nächstes Drehbuch trifft die Länge genauer
            STATE["voice_wps"] = round(0.5 * float(STATE.get("voice_wps") or n_spoken / total) + 0.5 * n_spoken / total, 3)
        min_s = float(cfg("min_seconds") or 0)
        if min_s and total < min_s + 0.5:                # zu kurz: etwas ruhiger sprechen lassen, Rest als Ausklang am Ende
            f = max(0.9, total / (min_s + 1.0))
            slow = work / "voice_slow.mp3"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(voice), "-af",
                            f"atempo={f:.4f},apad=pad_dur={max(0.0, min(8.0, min_s + 1.0 - total / f)):.2f}", str(slow)], check=True)
            shutil.move(str(slow), str(voice))
            words = [(w, s0 / f, e0 / f) for w, s0, e0 in words]
            new_total = ai.audio_duration(voice)
            log(f"Video wäre {total:.0f} s kurz gewesen – auf {new_total:.0f} s gebracht (Tempo ×{f:.2f}, Ausklang {max(0.0, new_total - total / f):.1f} s)")
            total = new_total
        times = render.scene_times(scenes, words, total)
        log(f"Sprecher fertig ({total:.0f} s)")

        seed = random.randint(1, 10_000_000)
        img_used = set()
        toon = bool(script.get("toon"))
        if toon:
            from .toon import stage
            log("Animiere Szenen …")
            stage.direct(scenes, times, f"{v.get('topic') or ''} {script.get('title') or ''}", cat["slug"], os.environ.get("AS_LOOK") or cat.get("look") or cfg("look") or "")
            try:                                          # Bildplan aufheben: so lässt sich später nachsehen, warum eine Szene so aussah
                from .state import DATA
                (DATA / "scripts").mkdir(exist_ok=True)
                (DATA / "scripts" / f"{v['id']}.json").write_text(json.dumps({"title": script.get("title"), "scenes": [
                    {k: sc_.get(k) for k in ("text", "see", "place", "backdrop", "time", "weather", "props", "actors", "shot", "mood", "crowd", "graphic", "overlay", "hud", "status")
                     if sc_.get(k) not in (None, "", [])} for sc_ in scenes]}, ensure_ascii=False, indent=1), encoding="utf-8")
                for old_f in sorted((DATA / "scripts").glob("*.json"), key=lambda f: f.stat().st_mtime)[:-20]:
                    old_f.unlink()
            except Exception:  # noqa: BLE001
                pass
            for i, (sc, (s0, e0)) in enumerate(zip(scenes, times)):
                d = (e0 - s0) + (0.35 if i == len(scenes) - 1 else 0.25)
                try:
                    stage.render_scene(sc, script.get("cast") or {}, d, work / f"toon{i:02d}.mp4", words, s0, work / f"img{i:02d}.jpg", index=i)
                except Exception as e:  # noqa: BLE001 – eine Szene darf nie das ganze Video kosten
                    log(f"Szene {i + 1} ließ sich nicht wie geplant zeichnen ({type(e).__name__}: {e}) – vereinfachte Fassung")
                    safe = {"text": sc.get("text"), "place": sc.get("place") if isinstance(sc.get("place"), str) else "park",
                            "time": sc.get("time"), "overlay": sc.get("overlay"), "crowd": "walk"}
                    try:
                        stage.render_scene(safe, script.get("cast") or {}, d, work / f"toon{i:02d}.mp4", words, s0, work / f"img{i:02d}.jpg")
                    except Exception:  # noqa: BLE001
                        stage.render_scene({"place": "park"}, {}, d, work / f"toon{i:02d}.mp4", words, s0, work / f"img{i:02d}.jpg")
                log(f"Szene {i + 1}/{len(scenes)} animiert")
            img_used.add("toon")
        for i, sc in enumerate([] if toon else scenes):
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
                if toon:
                    th = dict(script["thumbnail"])
                    if not th.get("place"):      # kein eigener Vorschlag → die Szene mit der stärksten Einblendung/erste Szene
                        base = scenes[0]
                        th.update(place=base.get("place"), time=base.get("time"),
                                  actor=(base.get("actors") or [{}])[0].get("id"))
                    try:                                  # eigens gestaltetes Titelbild – kein Ausschnitt aus dem Video
                        stage.poster(th, script.get("cast") or {}, raw, f"{script.get('title') or ''} {v.get('topic') or ''}")
                    except Exception as e:  # noqa: BLE001
                        log(f"Titelbild-Gestaltung fehlgeschlagen ({e}) – nehme eine Szene")
                        stage.cover(th, script.get("cast") or {}, raw)
                else:
                    ai.image(writer.image_prompt({"image": script["thumbnail"]["image"]}, cat), raw, seed + 999)
            except Exception as e:  # noqa: BLE001
                log(f"Thumbnail-Bild fehlgeschlagen ({e}) – nehme das erste Szenenbild")
                shutil.copy(work / "img00.jpg", raw)
            cover = OUT / f"{vid}-cover.jpg"
            thumbnail.make_thumbnail(raw, script["thumbnail"]["text"] or script["title"], cover)

        log("Schneide Video …")
        ass = work / "subs.ass"
        render.build_ass(words, scenes, times, ass, bool(cfg("subtitles_lowercase")),
                         script.get("hud"), script.get("countdown"), 480 if toon else 560,
                         cfg("caption_style") or "impact")
        v["cover_ms"] = render.render(work, scenes, times, voice, ass, final, render.pick_music(cat["slug"]),
                                      float(cfg("music_volume") or 0.1), cover,
                                      float(cfg("sfx_volume") if cfg("sfx_volume") is not None else 0.35), cat["slug"])
        Image.open(cover or (work / "img00.jpg")).resize((360, 640)).save(THUMBS / f"{vid}.jpg", quality=82)
        v.update(status="rendered", duration=round(total + 0.35, 1), providers=used, thumb=True,
                 look=(os.environ.get("AS_LOOK") or cat.get("look") or cfg("look") or "cartoon") if script.get("toon") else "ki")
        v["mp4"] = publish_mp4([final, cover] if cover else final)
        log(f"Video {vid} fertig")
    except Exception as e:
        v.update(status="error", error=str(e)[:900])
        raise
    finally:
        shutil.rmtree(work, ignore_errors=True)
        save_all()

    if upload and v.get("missing") and cfg("hold_missing") is not False:
        v["status"] = "rendered"
        v["error"] = "Nicht hochgeladen: Der Engine fehlt noch " + ", ".join(v["missing"]) + ". Nach dem Ausbau neu erstellen oder trotzdem von Hand hochladen."
        log(v["error"])
        save_all()
    elif upload:
        uploaders.upload_video(v, final)
        save_all()
    return v


def upload(vid):
    v = video(vid)
    if not v:
        raise RuntimeError(f"Video {vid} nicht gefunden")
    uploaders.upload_video(v, fetch_mp4(vid))


# ---------------------------------------------------------------- Einstieg

def learn(words):
    """Lässt Gegenstände für die Bibliothek zeichnen und legt ein Übersichtsbild aller gelernten Dinge ab."""
    from .state import load, save
    from .toon import extras, library
    shapes = load("shapes.json", {})
    library.load_all(shapes)
    new = library.learn(words, ai.chat_json, shapes, log, limit=6)
    if new:
        shapes.update(new)
        save("shapes.json", shapes)
    log(f"Bibliothek: {len(new)} neu, {len(shapes)} insgesamt")
    names = library.names()[-24:]
    if names:
        from PIL import ImageDraw
        cols = min(6, len(names))
        rows = (len(names) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * 300, rows * 340), (36, 52, 96))
        dr = ImageDraw.Draw(sheet)
        for i, nm in enumerate(names):
            lay = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
            extras.draw_prop(lay, nm, 540, 1.0)
            box = lay.getbbox()
            if box:
                cut = lay.crop(box)
                f = min(260 / cut.width, 260 / cut.height)
                cut = cut.resize((max(1, int(cut.width * f)), max(1, int(cut.height * f))))
                sheet.paste(cut, ((i % cols) * 300 + 150 - cut.width // 2, (i // cols) * 340 + 150 - cut.height // 2), cut)
            dr.text(((i % cols) * 300 + 16, (i // cols) * 340 + 304), nm[:26], fill=(255, 255, 255))
        THUMBS.mkdir(parents=True, exist_ok=True)
        sheet.save(THUMBS / "bibliothek.jpg", quality=88)


SLOT_TRIES = 3                     # so oft wird ein Termin-Video versucht, bevor der Termin ausfällt


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
                    make(plan=load("plans.json", {}).get(slot))
                except Exception as e:  # noqa: BLE001
                    failed = True
                    log(f"FEHLER: {e}")
                    tries = STATE.setdefault("slot_tries", {})
                    tries[slot] = tries.get(slot, 0) + 1
                    for k in [k for k in tries if k < slot[:10]]:  # alte Zähler aufräumen
                        tries.pop(k, None)
                    if tries[slot] < SLOT_TRIES:          # Termin nicht verlieren: beim nächsten Lauf (30 min) neu versuchen
                        STATE["done_slots"] = [d for d in STATE["done_slots"] if d != slot]
                        log(f"Termin {slot} wird beim nächsten Lauf erneut versucht ({tries[slot]}/{SLOT_TRIES})")
            for vid in review_stale():                  # wartet seit Stunden auf die Prüfung: nicht liegen lassen
                try:
                    log(f"Video {vid} wurde nicht geprüft – lade es jetzt hoch")
                    upload(int(vid))
                except Exception as e:  # noqa: BLE001
                    log(f"FEHLER beim Hochladen von {vid}: {e}")
            nxt = plan_slot(CONFIG, STATE)
            if nxt and cfg("plan_ahead") is not False and nxt not in load("plans.json", {}):
                try:
                    prepare(nxt)
                except Exception as e:  # noqa: BLE001 – ohne Plan wird das Video am Termin wie bisher frisch geschrieben
                    log(f"Vorproduktion nicht möglich ({e})")
            if stats_due(STATE):
                uploaders.refresh_stats()
                try:
                    if time.time() - float(STATE.get("last_trends") or 0) > 3 * 3600:      # Trends nur alle drei Stunden neu sammeln
                        STATE["last_trends"] = time.time()
                        trends.refresh()
                except Exception as e:  # noqa: BLE001
                    log(f"Trends: {e}")
        elif a.action == "make":
            make(a.category.strip() or None, a.topic.strip() or None, a.upload != "0", a.trend.strip() or None)
        elif a.action == "review_make":  # Video für den nächsten Termin bauen, aber erst nach der Prüfung hochladen
            slot = review_slot(CONFIG, STATE)
            if not slot:
                log("Prüf-Video: kein Termin in den nächsten Stunden offen")
            else:
                STATE["done_slots"].append(slot)
                save_all()
                log(f"Prüf-Video für {slot}")
                v = make(plan=load("plans.json", {}).get(slot), upload=False)
                v.update(status="review", slot=slot, review_at=time.time())
                save_all()
        elif a.action == "discard":      # verworfene Fassung: wird nie hochgeladen
            v = video(int(a.id))
            if v and v.get("status") in ("review", "rendered"):
                v.update(status="discarded", error="Bei der Prüfung verworfen" + (": " + a.topic.strip()[:300] if a.topic.strip() else ""))
                save_all()
        elif a.action == "upload":
            upload(int(a.id))
        elif a.action == "remake":       # eingeschicktes Video in unserem Stil neu aufbauen (--id = Dateiname im Release „inbox“)
            from . import remake
            try:
                src = remake.analyze(remake.fetch(a.id.strip()))
            except Exception as e:  # noqa: BLE001 – Link gesperrt (YouTube/TikTok blocken Server oft): nur aus Titel/Beschreibung
                if not remake.is_link(a.id.strip()):
                    raise
                log(f"Video vom Link nicht ladbar ({str(e)[:160]}) – baue nach Titel und Beschreibung nach")
                src = remake.analyze_link_text(a.id.strip())
            log(f"Vorlage erkannt: {src['topic']} ({src['category'] or 'ohne Kategorie'})")
            slug = a.category.strip() or (src["category"] if category(src["category"]) else "comedy")
            try:
                make(slug if category(slug) else None, src["topic"], a.upload != "0", None, source=src)
            finally:
                remake.cleanup(a.id.strip())
        elif a.action == "stats":
            uploaders.refresh_stats()
            trends.refresh()
        elif a.action == "disconnect":   # Plattform trennen: Anmeldung und abgerufene Zahlen löschen
            plat = a.category.strip()
            if plat not in ("youtube", "tiktok"):
                raise SystemExit("Plattform fehlt")
            drop_token(plat)
            log(f"{plat} getrennt, Anmeldung und Zahlen gelöscht")
        elif a.action == "prepare":      # nächsten Termin jetzt schon vorbereiten
            nxt = plan_slot(CONFIG, STATE, force=True)
            if nxt:
                prepare(nxt)
        elif a.action == "learn":        # Gegenstände gezielt nachbauen lassen: --topic "Router, Mikroskop, Leiter"
            learn([w.strip() for w in a.topic.split(",") if w.strip()])
        elif a.action == "trends":       # „Aktualisieren“ in der App: Trends und Kanal-Analyse sofort neu
            trends.refresh(force=True)
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
