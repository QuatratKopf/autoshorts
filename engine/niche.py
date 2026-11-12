"""Kanal-Analyse: Was läuft gerade bei anderen Kanälen derselben Art (KI-Fakten, What If, Tierwelt, Grusel …)?

Je Video-Art werden die meistgesehenen Shorts der letzten zwei Wochen gesucht (YouTube; mit Anmeldung über die API, sonst über die
öffentliche Suche), bewertet und die besten in eigene Themen-Vorschläge für unseren Kanal übersetzt:
  pro_tag  = Aufrufe pro Tag seit Veröffentlichung (wie schnell es gerade läuft)
  faktor   = Aufrufe geteilt durch Abonnenten des Kanals (ein Video, das weit über seinem Kanal liegt, hat ein starkes Thema –
             nicht nur einen großen Kanal)
Gespeichert in docs/data/trends.json unter "niche"; die App zeigt es im Studio, der Autopilot nimmt daraus Themen."""
import datetime as dt
import json
import re
import time

import requests

from .state import CONFIG, cfg, load, log

T = 25
EVERY = 6 * 3600                 # höchstens alle sechs Stunden neu suchen (YouTube-Kontingent: eine Suche kostet 100 Einheiten)
DAYS = 14
# Suchbegriffe je Video-Art: so suchen Zuschauer nach genau dieser Art von Shorts (deutsch, plus ein englischer Begriff für die USA)
QUERIES = {
    "fakten": ["krasse fakten", "fakten die du nicht wusstest"],
    "whatif": ["was wäre wenn", "what if animation"],
    "tiere": ["tier fakten", "unglaubliche tiere"],
    "mysterien": ["ungelöste rätsel", "mysteriöse orte"],
    "grusel": ["gruselgeschichte", "creepy story animation"],
    "storys": ["wahre geschichte", "unglaubliche wahre geschichte"],
    "lustig": ["lustige geschichte animation"],
    "comedy": ["lustige animation", "ich habe mir"],
}


def _queries(cat):
    if cat.get("niche_queries"):
        return [str(q) for q in cat["niche_queries"]][:2]
    return QUERIES.get(cat.get("slug"), [str(cat.get("name") or "")])


def _days_since(iso):
    try:
        t = dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        return max(0.5, (dt.datetime.now(dt.timezone.utc) - t).total_seconds() / 86400)
    except ValueError:
        return float(DAYS)


def _api_search(token, q):
    """YouTube-API: Shorts der letzten zwei Wochen zur Suche, mit Aufrufen und Abonnenten des Kanals."""
    h = {"Authorization": "Bearer " + token}
    after = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = requests.get("https://www.googleapis.com/youtube/v3/search", headers=h, timeout=T,
                     params={"part": "snippet", "q": q + " #shorts", "type": "video", "videoDuration": "short", "order": "viewCount",
                             "publishedAfter": after, "relevanceLanguage": "de", "maxResults": 15})
    r.raise_for_status()
    ids = [it["id"]["videoId"] for it in r.json().get("items", []) if it.get("id", {}).get("videoId")]
    if not ids:
        return []
    r = requests.get("https://www.googleapis.com/youtube/v3/videos", headers=h, timeout=T,
                     params={"part": "snippet,statistics", "id": ",".join(ids)})
    r.raise_for_status()
    vids = r.json().get("items", [])
    chans = list({v["snippet"]["channelId"] for v in vids})
    subs = {}
    if chans:
        r = requests.get("https://www.googleapis.com/youtube/v3/channels", headers=h, timeout=T,
                         params={"part": "statistics", "id": ",".join(chans[:50])})
        if r.status_code == 200:
            subs = {c["id"]: int(c.get("statistics", {}).get("subscriberCount") or 0) for c in r.json().get("items", [])}
    out = []
    for v in vids:
        sn, st = v.get("snippet", {}), v.get("statistics", {})
        out.append({"vid": v["id"], "orig": sn.get("title", ""), "channel": sn.get("channelTitle", ""),
                    "views": int(st.get("viewCount") or 0), "days": _days_since(sn.get("publishedAt")),
                    "subs": subs.get(sn.get("channelId"), 0)})
    return out


_NUM = {"k": 1e3, "tsd": 1e3, "mio": 1e6, "m": 1e6, "mrd": 1e9, "b": 1e9}


def _num(txt):
    m = re.search(r"([\d.,]+)\s*(k|tsd|mio|m|mrd|b)?\.?", str(txt or "").lower().replace(" ", " "))
    if not m:
        return 0
    raw = m.group(1)
    v = float(raw.replace(".", "").replace(",", ".")) if m.group(2) is None else float(raw.replace(",", "."))
    return int(v * _NUM.get(m.group(2) or "", 1))


def _ago_days(txt):
    m = re.search(r"(\d+)\s*(minute|stunde|tag|woche|monat|jahr|hour|day|week|month|year)", str(txt or "").lower())
    if not m:
        return float(DAYS)
    n, u = int(m.group(1)), m.group(2)
    return max(0.5, n * {"minute": 1 / 1440, "stunde": 1 / 24, "hour": 1 / 24, "tag": 1, "day": 1, "woche": 7, "week": 7,
                         "monat": 30, "month": 30, "jahr": 365, "year": 365}[u])


def _web_search(q):
    """Ohne YouTube-Anmeldung: öffentliche Suchseite (Filter „Kurz“, „Diese Woche“), Aufrufe und Alter aus den Seitendaten."""
    r = requests.get("https://www.youtube.com/results", timeout=T, params={"search_query": q + " #shorts", "sp": "EgQIAxgB", "hl": "de", "gl": "DE"},
                     headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36",
                              "Accept-Language": "de-DE,de;q=0.9"})
    r.raise_for_status()
    m = re.search(r"var ytInitialData\s*=\s*(\{.*?\});\s*</script>", r.text, re.S)
    if not m:
        return []
    out = []

    def walk(o):
        if isinstance(o, dict):
            if "videoRenderer" in o:
                v = o["videoRenderer"]
                title = "".join(x.get("text", "") for x in v.get("title", {}).get("runs", []))
                views = _num((v.get("viewCountText") or {}).get("simpleText"))
                if title and views:
                    out.append({"vid": v.get("videoId", ""), "orig": title, "views": views, "subs": 0,
                                "channel": "".join(x.get("text", "") for x in (v.get("ownerText") or {}).get("runs", [])),
                                "days": _ago_days((v.get("publishedTimeText") or {}).get("simpleText"))})
                return
            for x in o.values():
                walk(x)
        elif isinstance(o, list):
            for x in o:
                walk(x)
    walk(json.loads(m.group(1)))
    return out[:15]


def _score(x):
    per_day = x["views"] / max(0.5, x["days"])
    factor = x["views"] / max(1000, x["subs"]) if x["subs"] else 0.0
    return per_day, factor


def _ideas(rows):
    """Text-KI übersetzt die erfolgreichen Videos in eigene Themen für unseren Kanal (keine Kopie, keine Namen)."""
    from . import ai
    lst = "\n".join(f"[{i}] ({r['cat']}) „{r['orig']}“ – {r['views']:,} Aufrufe".replace(",", ".") for i, r in enumerate(rows))
    js, _ = ai.chat_json(
        "Du bist Themen-Scout für einen deutschen Shorts-Kanal mit animierten Erklärvideos. Antworte nur mit JSON.",
        "Diese Shorts anderer Kanäle laufen gerade sehr gut:\n" + lst + "\n\n"
        "Leite aus jedem ein EIGENES Thema für unseren Kanal ab: was macht das Video erfolgreich (Frage, Neugier, Gefühl), und welches "
        "Thema bedient dasselbe Interesse, ohne es zu kopieren? Keine Namen von Kanälen, Personen, Marken, Filmen oder Spielen, "
        "nichts Erfundenes als Tatsache. Kurz, konkret, auf Deutsch.\n"
        'JSON: {"items": [{"i": Nummer, "topic": "unser Thema", "why": "warum es zieht, in einem kurzen Satz"}]}', 0.6)
    out = {}
    for it in (js.get("items") or []) if isinstance(js, dict) else []:
        if isinstance(it, dict) and isinstance(it.get("i"), int) and 0 <= it["i"] < len(rows) and str(it.get("topic") or "").strip():
            out[it["i"]] = (str(it["topic"]).strip()[:140], str(it.get("why") or "").strip()[:160])
    return out


def refresh(force=False):
    """Neue Kanal-Analyse (höchstens alle sechs Stunden). Gibt {"updated", "items"} zurück."""
    old = load("trends.json", {}).get("niche") or {}
    if not force and time.time() - float(old.get("updated") or 0) < EVERY and old.get("items"):
        return old
    token = None
    try:
        from .uploaders import _yt_access, connected
        if connected("youtube"):
            token = _yt_access()
    except Exception as e:  # noqa: BLE001
        log(f"Kanal-Analyse: YouTube-Anmeldung nicht nutzbar ({e}) – nehme die öffentliche Suche")
    cats = [c for c in CONFIG["categories"] if c.get("enabled")] or CONFIG["categories"]
    rows, seen = [], set()
    for c in cats:
        found = []
        for q in _queries(c):
            try:
                found += _api_search(token, q) if token else _web_search(q)
            except Exception as e:  # noqa: BLE001
                log(f"Kanal-Analyse „{q}“: {str(e)[:120]}")
                if token:                                  # Kontingent leer o. Ä.: öffentliche Suche als Ersatz
                    try:
                        found += _web_search(q)
                    except Exception:  # noqa: BLE001
                        pass
        for x in found:
            x["per_day"], x["factor"] = _score(x)
        uniq = {}
        for x in found:                                    # dasselbe Video aus zwei Suchbegriffen nur einmal
            uniq.setdefault(x["vid"] or x["orig"], x)
        found = [x for k, x in uniq.items() if k not in seen and x["views"] >= 5000]
        found.sort(key=lambda x: x["per_day"] * (1 + min(x["factor"], 20) / 4), reverse=True)
        for x in found[:5]:
            seen.add(x["vid"] or x["orig"])
            rows.append({**x, "cat": c["slug"]})
    if not rows:
        log("Kanal-Analyse: nichts gefunden")
        return old or {"updated": time.time(), "items": []}
    try:
        ideas = _ideas(rows)
    except Exception as e:  # noqa: BLE001
        log(f"Kanal-Analyse: Themen-Vorschläge nicht möglich ({e})")
        ideas = {}
    items = []
    for i, r in enumerate(rows):
        topic, why = ideas.get(i, (None, ""))
        items.append({"id": f"n{int(time.time())}-{i}", "source": "Kanäle", "category": r["cat"], "title": topic or r["orig"],
                      "orig": r["orig"], "channel": r["channel"], "views": r["views"], "per_day": int(r["per_day"]),
                      "factor": round(r["factor"], 1), "url": f"https://www.youtube.com/shorts/{r['vid']}" if r["vid"] else "",
                      "summary": why, "traffic": f"{int(r['per_day']):,} Aufrufe/Tag".replace(",", "."), "news": [], "region": "DE"})
    data = {"updated": time.time(), "items": items}
    log(f"Kanal-Analyse: {len(items)} erfolgreiche Shorts in {len({r['cat'] for r in rows})} Video-Arten")
    return data


def for_category(slug, n=8):
    """Gut laufende Themen anderer Kanäle für eine Video-Art (für die Themenwahl des Autopiloten)."""
    items = (load("trends.json", {}).get("niche") or {}).get("items") or []
    return [x for x in items if x.get("category") == slug][:n]
