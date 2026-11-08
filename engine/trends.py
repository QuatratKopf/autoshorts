"""Was gerade im Trend ist – aus kostenlosen Quellen, ohne Schlüssel.

- Google Trends (Deutschland): Suchbegriffe, die heute stark steigen, mit passenden Schlagzeilen
- Wikipedia (deutsch): meistgelesene Artikel von gestern
- YouTube (Deutschland): angesagte Videos (nur wenn YouTube verbunden ist)

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
                d = {"source": "Google Trends", "news": []}
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
            log(f"Google Trends: {e}")
    return out[:25]


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
                out.append({"source": "Wikipedia", "title": title, "traffic": f"{a.get('views', 0):,}".replace(",", ".") + " Aufrufe",
                            "summary": (a.get("description") or "") + (" – " + a["extract"][:280] if a.get("extract") else ""),
                            "news": []})
            if out:
                return out[:25]
        except Exception as e:  # noqa: BLE001
            log(f"Wikipedia-Trends: {e}")
    return []


def youtube_trending(region="DE"):
    try:
        from .uploaders import _yt_access, connected
        if not connected("youtube"):
            return []
        r = requests.get("https://www.googleapis.com/youtube/v3/videos", headers={"Authorization": "Bearer " + _yt_access()},
                         params={"part": "snippet,statistics", "chart": "mostPopular", "regionCode": region, "maxResults": 25},
                         timeout=T)
        if r.status_code != 200:
            return []
        out = []
        for it in r.json().get("items", []):
            sn = it.get("snippet", {})
            out.append({"source": "YouTube", "title": sn.get("title", ""), "traffic": f"{int(it.get('statistics', {}).get('viewCount', 0)):,}".replace(",", ".") + " Aufrufe",
                        "summary": (sn.get("description") or "")[:200], "news": []})
        return out
    except Exception as e:  # noqa: BLE001
        log(f"YouTube-Trends: {e}")
        return []


def refresh():
    log("Sammle Trends …")
    items = google_trends() + wikipedia_mostread() + youtube_trending()
    for i, it in enumerate(items):
        it["id"] = f"t{int(time.time())}-{i}"
    data = {"updated": time.time(), "items": items}
    save("trends.json", data)
    log(f"{len(items)} Trends gefunden")
    return data


def current(max_age=3 * 3600):
    data = load("trends.json", {"updated": 0, "items": []})
    if time.time() - float(data.get("updated") or 0) > max_age or not data.get("items"):
        data = refresh()
    return data.get("items", [])


def as_prompt_list(items, limit=40):
    lines = []
    for i, it in enumerate(items[:limit]):
        extra = "; ".join(n["title"] for n in it.get("news", [])[:2]) or it.get("summary", "")
        lines.append(f"[{i}] ({it['source']}, {it.get('traffic', '')}) {it['title']}" + (f" – {extra[:220]}" if extra else ""))
    return "\n".join(lines)


def trend_mode():
    return cfg("trend_mode") or "half"
