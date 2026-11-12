"""Was gerade im Trend ist – aus kostenlosen Quellen, ohne Schlüssel. Ausgerichtet auf die Gen-Z-/TikTok-Bubble,
standardmäßig USA und Deutschland (Einstellung trend_regions).

- TikTok: angesagte Sounds des Tages (kworb.net, je Land)
- (YouTube-Daten werden bewusst NICHT genutzt: die YouTube API dient nur dem Hochladen und den eigenen Zahlen)
- Reddit: was in Gen-Z-nahen Communities heute oben steht (USA: r/GenZ, r/OutOfTheLoop …; DE: r/de, r/ich_iel …)
- Google Trends: Suchbegriffe, die heute stark steigen (je Land)
- Wikipedia (englisch/deutsch): meistgelesene Artikel von gestern

Ergebnis landet in docs/data/trends.json und wird in der App unter Studio angezeigt.
"""
import datetime as dt
import html
import re
import time
import xml.etree.ElementTree as ET

import requests

from .state import cfg, load, log, save

UA = {"User-Agent": "AutoShorts/1.0 (github.com/QuatratKopf/autoshorts)"}
T = 25
SKIP_WIKI = re.compile(r"^(Wikipedia:|Spezial:|Datei:|Hauptseite|Portal:|Liste der|Deaths in|Nekrolog)", re.I)


COUNTRY = {"US": "USA", "DE": "Deutschland", "GB": "UK", "AT": "Österreich", "CH": "Schweiz"}
BROWSER = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/130.0 Safari/537.36", "Accept-Language": "en-US,en;q=0.9,de;q=0.8"}


def regions():
    out = [r.strip().upper() for r in str(cfg("trend_regions") or "US,DE").split(",") if r.strip()]
    return out or ["US", "DE"]


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def google_trends(geo="DE"):
    out = []
    for url in (f"https://trends.google.com/trending/rss?geo={geo}",
                f"https://trends.google.de/trends/trendingsearches/daily/rss?geo={geo}"):
        try:
            r = requests.get(url, headers=UA, timeout=T)
            if r.status_code != 200:
                continue
            root = ET.fromstring(r.content)
            for item in root.iter("item"):
                d = {"source": "Google Trends", "region": geo, "news": []}
                for ch in item:
                    n = _local(ch.tag)
                    if n == "title":
                        d["title"] = (ch.text or "").strip()
                    elif n == "approx_traffic":
                        d["traffic"] = (ch.text or "").strip()
                    elif n == "pubDate":
                        d["date"] = (ch.text or "").strip()
                    elif n == "news_item":
                        news = {_local(x.tag): html.unescape((x.text or "").strip()) for x in ch}
                        if news.get("news_item_title"):
                            d["news"].append({"title": news["news_item_title"], "url": news.get("news_item_url", ""),
                                              "source": news.get("news_item_source", "")})
                if d.get("title"):
                    d["news"] = d["news"][:3]
                    out.append(d)
            if out:
                break
        except Exception as e:  # noqa: BLE001
            log(f"Google Trends ({geo}): {e}")
    return out[:20]


def wikipedia_mostread(lang="de"):
    day = dt.date.today() - dt.timedelta(days=1)
    for url in (f"https://{lang}.wikipedia.org/api/rest_v1/feed/featured/{day:%Y/%m/%d}",
                f"https://api.wikimedia.org/feed/v1/wikipedia/{lang}/featured/{day:%Y/%m/%d}"):
        try:
            r = requests.get(url, headers=UA, timeout=T)
            if r.status_code != 200:
                continue
            arts = (r.json().get("mostread") or {}).get("articles") or []
            out = []
            for a in arts:
                title = a.get("normalizedtitle") or (a.get("titles") or {}).get("normalized") or a.get("title", "")
                if not title or SKIP_WIKI.search(title):
                    continue
                out.append({"source": "Wikipedia", "region": "US" if lang == "en" else "DE", "title": title, "traffic": f"{a.get('views', 0):,}".replace(",", ".") + " Aufrufe",
                            "summary": (a.get("description") or "") + (" – " + a["extract"][:280] if a.get("extract") else ""),
                            "news": []})
            if out:
                return out[:15]
        except Exception as e:  # noqa: BLE001
            log(f"Wikipedia-Trends: {e}")
    return []


YT_CATS = {"20": "Gaming", "10": "Musik", "24": "Unterhaltung", "23": "Comedy"}


def youtube_trending(region="DE"):
    try:
        from .uploaders import _yt_access, connected
        if not connected("youtube"):
            return []
        token = _yt_access()
    except Exception as e:  # noqa: BLE001
        log(f"YouTube-Trends: {e}")
        return []
    out, seen = [], set()
    for cat_id, cat_name in [(None, "")] + list(YT_CATS.items()):
        params = {"part": "snippet,statistics", "chart": "mostPopular", "regionCode": region, "maxResults": 8}
        if cat_id:
            params["videoCategoryId"] = cat_id
        try:
            r = requests.get("https://www.googleapis.com/youtube/v3/videos", headers={"Authorization": "Bearer " + token},
                             params=params, timeout=T)
            if r.status_code != 200:
                continue
            for it in r.json().get("items", []):
                sn = it.get("snippet", {})
                if it.get("id") in seen or not sn.get("title"):
                    continue
                seen.add(it.get("id"))
                out.append({"source": "YouTube" + (f" {cat_name}" if cat_name else ""), "region": region, "title": sn["title"],
                            "traffic": f"{int(it.get('statistics', {}).get('viewCount', 0)):,}".replace(",", ".") + " Aufrufe",
                            "summary": (sn.get("channelTitle", "") + ": " + (sn.get("description") or "")[:160]).strip(": "),
                            "news": []})
        except Exception as e:  # noqa: BLE001
            log(f"YouTube-Trends: {e}")
    return out[:20]


def tiktok_songs(region="US"):
    """Angesagte TikTok-Sounds (Tageschart von kworb.net, je Land)."""
    try:
        r = requests.get(f"https://kworb.net/charts/tiktok/{region.lower()}.html", headers=BROWSER, timeout=T)
        if r.status_code != 200:
            log(f"TikTok-Songs ({region}): HTTP {r.status_code}")
            return []
        page = r.content.decode("utf-8", "replace")
        out = []
        for pos, move, name in re.findall(r"<tr><td>(\d+)</td><td>([^<]*)</td><td class=\"mp text\"><div>(.*?)</div>", page)[:12]:
            name = html.unescape(re.sub(r"<.*?>", "", name)).strip()
            if not name:
                continue
            artist, _, title = name.partition(" - ")
            out.append({"source": "TikTok Song", "region": region, "title": title or name,
                        "traffic": f"Platz {pos}" + (" · neu" if move == "NEW" else f" ({move})" if move not in ("=", "") else ""),
                        "summary": f"Sound von {artist}" if title else "", "news": []})
        return out
    except Exception as e:  # noqa: BLE001
        log(f"TikTok-Songs ({region}): {e}")
        return []


REDDIT = {"US": "GenZ+TikTokCringe+OutOfTheLoop+popculturechat+gaming+movies+television+Music",
          "DE": "de+ich_iel+germany+gaming_de"}


def reddit_trending(region="US"):
    """Meistgelesene Beiträge des Tages aus Gen-Z-nahen Communities (über den öffentlichen RSS-Feed)."""
    subs = REDDIT.get(region)
    if not subs:
        return []
    url = f"https://www.reddit.com/r/{subs}/top/.rss?t=day&limit=20"
    for attempt in range(3):
        try:
            r = requests.get(url, headers=BROWSER, timeout=T)
            if r.status_code == 429:   # Reddit erlaubt ohne Anmeldung nur wenige Abrufe kurz hintereinander
                time.sleep(30)
                continue
            if r.status_code != 200:
                log(f"Reddit ({region}): HTTP {r.status_code}")
                return []
            ns = {"a": "http://www.w3.org/2005/Atom"}
            out = []
            for e in ET.fromstring(r.content).findall("a:entry", ns):
                title = html.unescape(e.findtext("a:title", "", ns) or "").strip()
                cat = e.find("a:category", ns)
                sub = cat.get("label", "") if cat is not None else ""
                if title and not re.search(r"nsfw|\bnsfl\b", title, re.I):
                    out.append({"source": "Reddit " + (sub or "r/" + subs.split("+")[0]), "region": region,
                                "title": title[:200], "traffic": "", "summary": "", "news": []})
            return out[:15]
        except Exception as e:  # noqa: BLE001
            log(f"Reddit ({region}): {e}")
            return []
    log(f"Reddit ({region}): zu viele Abrufe, übersprungen")
    return []


def refresh(force=False):
    log("Sammle Trends (" + ", ".join(COUNTRY.get(r, r) for r in regions()) + ") …")
    items, counts = [], {}
    for name, fn in [("TikTok", lambda: [x for r in regions() for x in tiktok_songs(r)]),
                     ("Reddit", lambda: [x for r in regions() for x in reddit_trending(r)]),
                     ("Google", lambda: [x for r in regions() for x in google_trends(r)]),
                     ("Wikipedia", lambda: [x for r in regions() if r in ("US", "DE") for x in wikipedia_mostread("en" if r == "US" else "de")])]:
        got = fn()
        counts[name] = len(got)
        items += got
    for i, it in enumerate(items):
        it["id"] = f"t{int(time.time())}-{i}"
    data = {"updated": time.time(), "regions": regions(), "items": items}
    try:                                                   # was bei anderen Kanälen derselben Art gerade gut läuft
        from . import niche
        data["niche"] = niche.refresh(force)
        counts["Kanäle"] = len(data["niche"].get("items") or [])
    except Exception as e:  # noqa: BLE001
        log(f"Kanal-Analyse: {e}")
        data["niche"] = load("trends.json", {}).get("niche") or {}
    save("trends.json", data)
    log(f"{len(items)} Trends gefunden (" + ", ".join(f"{k} {v}" for k, v in counts.items()) + ")")
    return data


def current(max_age=3 * 3600):
    data = load("trends.json", {"updated": 0, "items": []})
    if time.time() - float(data.get("updated") or 0) > max_age or not data.get("items"):
        data = refresh()
    return data.get("items", [])


def as_prompt_list(items, limit=110):
    lines = []
    for i, it in enumerate(items[:limit]):
        extra = "; ".join(n["title"] for n in it.get("news", [])[:2]) or it.get("summary", "")
        reg = COUNTRY.get(it.get("region", ""), it.get("region", ""))
        lines.append(f"[{i}] ({it['source']}{', ' + reg if reg else ''}{', ' + it['traffic'] if it.get('traffic') else ''}) {it['title']}"
                     + (f" – {extra[:160]}" if extra else ""))
    return "\n".join(lines)


def trend_mode():
    return cfg("trend_mode") or "half"
