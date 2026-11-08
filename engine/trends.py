"""Was gerade im Trend ist – aus kostenlosen Quellen, ohne Schlüssel. Ausgerichtet auf die Gen-Z-/TikTok-Bubble,
standardmäßig USA und Deutschland (Einstellung trend_regions).

- TikTok Creative Center: angesagte Hashtags und Songs auf TikTok (je Land)
- YouTube: angesagte Videos aus Gaming, Musik, Unterhaltung, Comedy (je Land, wenn YouTube verbunden ist)
- Reddit: was in r/popular und Gen-Z-Communities gerade abgeht (USA/international)
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
            log(f"Google Trends: {e}")
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


def _next_data(url):
    r = requests.get(url, headers=BROWSER, timeout=T)
    if r.status_code != 200:
        return None
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.S)
    if not m:
        return None
    import json
    return json.loads(m.group(1))


def _find_lists(obj, key_hint):
    """Sucht in verschachtelten Daten Listen von Einträgen, die das Feld key_hint haben."""
    if isinstance(obj, list):
        if obj and isinstance(obj[0], dict) and key_hint in obj[0]:
            yield obj
        for x in obj:
            yield from _find_lists(x, key_hint)
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _find_lists(v, key_hint)


def tiktok_creative_center(region="US"):
    """Angesagte TikTok-Hashtags und -Songs aus dem öffentlichen TikTok Creative Center."""
    out = []
    pages = [("hashtag", "hashtag_name", "TikTok Hashtag"), ("music", "title", "TikTok Song")]
    for kind, field, label in pages:
        try:
            data = _next_data(f"https://ads.tiktok.com/business/creativecenter/inspiration/popular/{kind}/pc/en"
                              f"?region={region}&period=7")
            if not data:
                continue
            rows = next(_find_lists(data, field), [])
            for row in rows[:15 if kind == "hashtag" else 8]:
                name = str(row.get(field) or "").strip()
                if not name:
                    continue
                extra = []
                if row.get("industry_info", {}).get("value") if isinstance(row.get("industry_info"), dict) else None:
                    extra.append(row["industry_info"]["value"])
                if row.get("author"):
                    extra.append("von " + str(row["author"]))
                posts = row.get("publish_cnt") or row.get("video_views") or row.get("user_cnt")
                out.append({"source": label, "region": region, "title": ("#" + name) if kind == "hashtag" else name,
                            "traffic": (f"{int(posts):,}".replace(",", ".") + (" Posts" if row.get("publish_cnt") else " Aufrufe"))
                            if str(posts or "").isdigit() else "",
                            "summary": ", ".join(extra), "news": []})
        except Exception as e:  # noqa: BLE001
            log(f"TikTok-Trends ({kind}, {region}): {e}")
    return out


REDDIT_SUBS = ("popular", "GenZ", "TikTokCringe", "OutOfTheLoop", "gaming", "popculturechat")


def reddit_trending():
    out = []
    for sub in REDDIT_SUBS:
        try:
            r = requests.get(f"https://www.reddit.com/r/{sub}/top.json", params={"t": "day", "limit": 8},
                             headers={"User-Agent": "AutoShorts/1.0 (trend research)"}, timeout=T)
            if r.status_code != 200:
                continue
            for ch in r.json().get("data", {}).get("children", []):
                d = ch.get("data", {})
                if d.get("over_18") or d.get("stickied") or not d.get("title"):
                    continue
                out.append({"source": f"Reddit r/{d.get('subreddit') or sub}", "region": "US", "title": d["title"][:200],
                            "traffic": f"{int(d.get('ups', 0)):,}".replace(",", ".") + " Upvotes",
                            "summary": (d.get("selftext") or "")[:200], "news": []})
        except Exception as e:  # noqa: BLE001
            log(f"Reddit-Trends (r/{sub}): {e}")
    return out[:25]


def refresh():
    log("Sammle Trends (" + ", ".join(COUNTRY.get(r, r) for r in regions()) + ") …")
    items, counts = [], {}
    for name, fn in [("TikTok", lambda: [x for r in regions() for x in tiktok_creative_center(r)]),
                     ("YouTube", lambda: [x for r in regions() for x in youtube_trending(r)]),
                     ("Reddit", reddit_trending),
                     ("Google", lambda: [x for r in regions() for x in google_trends(r)]),
                     ("Wikipedia", lambda: [x for r in regions() if r in ("US", "DE") for x in wikipedia_mostread("en" if r == "US" else "de")])]:
        got = fn()
        counts[name] = len(got)
        items += got
    for i, it in enumerate(items):
        it["id"] = f"t{int(time.time())}-{i}"
    data = {"updated": time.time(), "regions": regions(), "items": items}
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
