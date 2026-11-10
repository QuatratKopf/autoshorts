"""Analyse: Was läuft am besten? Wertet Aufrufe, Likes, Kommentare und geteilte Videos aus und leitet daraus ab,
welche Kategorien öfter drankommen und welche Art Themen und Titel die Text-KI bevorzugen soll.

Ergebnis in docs/data/insights.json – die App zeigt es an, der Autopilot nutzt es (Einstellung auto_optimize)."""
import re
import time

from .state import CONFIG, STATS, VIDEOS, cfg, load, save

MIN_AGE_H = 20          # jüngere Videos zählen noch nicht – ihre Zahlen sind nicht vergleichbar
MIN_VIDEOS = 6          # erst ab so vielen ausgewerteten Videos wird gesteuert
STOP = {"wäre", "würde", "passiert", "plötzlich", "morgen", "menschen", "alles", "unsere", "wirklich", "komplett", "einfach", "warum",
        "diese", "dieser", "dieses", "nicht", "einen", "einer", "eine", "wenn", "dein", "deine", "deinen", "sich", "noch", "immer", "schon",
        "über", "unter", "gibt", "jetzt", "heute", "ganz", "mehr", "kein", "keine", "wird", "sind", "haben", "macht", "passieren", "würden"}


def latest(vid):
    """Letzter Stand je Plattform: {plattform: (aufrufe, likes, kommentare, geteilt)}."""
    out = {}
    for plat, rows in (STATS.get("v", {}).get(str(vid)) or {}).items():
        if rows:
            r = rows[-1]
            out[plat] = tuple(int(x or 0) for x in (r[1:5] + [0, 0, 0, 0])[:4])
    return out


def score(views, likes, comments, shares):
    """Ein Wert pro Video: Aufrufe zählen, Reaktionen zählen mehrfach (sie zeigen, dass es wirklich gefallen hat)."""
    return views + 15 * likes + 30 * comments + 40 * shares


def _words(text):
    return {w for w in re.findall(r"[a-zäöüß]{4,}", str(text or "").lower()) if w not in STOP}


def build():
    now = time.time()
    rows = []
    for v in VIDEOS:
        st = latest(v["id"])
        if not st or v.get("status") not in ("published", "partial"):
            continue
        views, likes, comments, shares = (sum(x[i] for x in st.values()) for i in range(4))
        age_h = (now - float(v.get("created") or now)) / 3600
        rows.append({"id": v["id"], "title": v.get("title") or v.get("topic") or "", "category": v.get("category") or "", "views": views,
                     "likes": likes, "comments": comments, "shares": shares, "score": score(views, likes, comments, shares),
                     "age_h": round(age_h, 1), "look": v.get("look") or "cartoon", "trend": bool(v.get("trend")),
                     "duration": v.get("duration") or 0, "counted": age_h >= MIN_AGE_H})
    counted = [r for r in rows if r["counted"]]
    enough = len(counted) >= MIN_VIDEOS
    avg_all = sum(r["score"] for r in counted) / len(counted) if counted else 0
    names = {c["slug"]: f"{c.get('emoji', '')} {c['name']}".strip() for c in CONFIG.get("categories", [])}
    cats = []
    for slug in sorted({r["category"] for r in counted}):
        rs = [r for r in counted if r["category"] == slug]
        views = sum(r["views"] for r in rs)
        cats.append({"slug": slug, "name": names.get(slug, slug), "n": len(rs), "avg_views": round(views / len(rs)),
                     "avg_likes": round(sum(r["likes"] for r in rs) / len(rs), 1),
                     "like_rate": round(100 * sum(r["likes"] for r in rs) / views, 2) if views else 0,
                     "avg_score": round(sum(r["score"] for r in rs) / len(rs))})
    cats.sort(key=lambda c: -c["avg_score"])
    weights = {}
    for c in CONFIG.get("categories", []):
        if not c.get("enabled"):
            continue
        hit = next((x for x in cats if x["slug"] == c["slug"]), None)
        if not enough or not avg_all:
            weights[c["slug"]] = 1.0
        elif not hit or hit["n"] < 2:
            weights[c["slug"]] = 1.2                                   # noch zu wenig Daten: bewusst ausprobieren
        else:
            weights[c["slug"]] = round(max(0.5, min(2.5, hit["avg_score"] / avg_all)), 2)
    ranked = sorted(counted, key=lambda r: -r["score"])
    third = max(1, len(ranked) // 3)
    top, flop = ranked[:third], ranked[-third:] if len(ranked) >= 3 else []
    good, bad = {}, {}
    for r in top:
        for w in _words(r["title"]):
            good[w] = good.get(w, 0) + 1
    for r in flop:
        for w in _words(r["title"]):
            bad[w] = bad.get(w, 0) + 1
    words_good = sorted([w for w, n in good.items() if n >= 2 and w not in bad], key=lambda w: -good[w])[:8]
    words_bad = sorted([w for w, n in bad.items() if n >= 2 and w not in good], key=lambda w: -bad[w])[:8]

    def split(key, label_a, label_b):
        a = [r["score"] for r in counted if key(r)]
        b = [r["score"] for r in counted if not key(r)]
        if len(a) >= 2 and len(b) >= 2:
            ma, mb = sum(a) / len(a), sum(b) / len(b)
            if max(ma, mb) > 1.25 * max(1, min(ma, mb)):
                return f"{label_a if ma > mb else label_b} laufen deutlich besser als {label_b if ma > mb else label_a} (Ø {round(max(ma, mb))} zu {round(min(ma, mb))} Punkte)."
        return None
    advice = []
    if not enough:
        advice.append(f"Noch zu wenig Daten: {len(counted)} von {MIN_VIDEOS} Videos sind alt genug zum Vergleichen. Bis dahin läuft alles im normalen Wechsel.")
    else:
        if cats:
            advice.append(f"Stärkste Kategorie: {cats[0]['name']} (Ø {cats[0]['avg_views']} Aufrufe, {cats[0]['like_rate']} % Likes).")
            if len(cats) > 1:
                advice.append(f"Schwächste Kategorie: {cats[-1]['name']} (Ø {cats[-1]['avg_views']} Aufrufe) – kommt seltener dran.")
        for s in (split(lambda r: r["trend"], "Trend-Themen", "zeitlose Themen"),
                  split(lambda r: r["look"] == "neon", "Videos im Neon-Stil", "Videos im Cartoon-Stil"),
                  split(lambda r: (r["duration"] or 0) >= 70, "Längere Videos (ab 70 s)", "kürzere Videos")):
            if s:
                advice.append(s)
        if words_good:
            advice.append("Wörter in starken Titeln: " + ", ".join(words_good) + ".")
    out = {"updated": now, "enough": enough, "counted": len(counted), "total": len(rows), "needed": MIN_VIDEOS, "categories": cats,
           "weights": weights, "advice": advice, "words_good": words_good, "words_bad": words_bad,
           "top": [{k: r[k] for k in ("id", "title", "category", "views", "likes", "comments", "shares", "score")} for r in ranked[:5]],
           "flop": [{k: r[k] for k in ("id", "title", "category", "views", "likes", "comments", "shares", "score")} for r in (ranked[-3:] if len(ranked) >= 6 else [])]}
    save("insights.json", out)
    return out


def get():
    return load("insights.json", {})


def active():
    ins = get()
    return ins if (cfg("auto_optimize") is not False and ins.get("enough")) else None


def pick_category(cats, state):
    """Gewichteter, fairer Wechsel: starke Kategorien kommen öfter dran, jede bleibt im Rennen."""
    ins = active()
    if not ins or len(cats) < 2:
        return None
    w = {c["slug"]: float(ins.get("weights", {}).get(c["slug"], 1.0)) for c in cats}
    credit = state.setdefault("cat_credit", {})
    for slug in list(credit):
        if slug not in w:
            credit.pop(slug)
    for slug, x in w.items():
        credit[slug] = float(credit.get(slug, 0)) + x
    best = max(cats, key=lambda c: credit[c["slug"]])
    credit[best["slug"]] -= sum(w.values())
    return best


def hint(cat):
    """Zeilen für die Themen-Suche der Text-KI: was in dieser Kategorie gut lief und was nicht."""
    ins = active()
    if not ins:
        return ""
    mine = [r for r in ins.get("top", []) if r["category"] == cat["slug"]] or ins.get("top", [])
    lines = []
    if mine:
        lines.append("Diese Videos kamen beim Publikum bisher am besten an (nimm Themen und Titel dieser Art, aber kein Thema doppelt): "
                     + " | ".join(f"„{r['title']}“ ({r['views']} Aufrufe)" for r in mine[:4]))
    if ins.get("flop"):
        lines.append("Diese liefen schwach (diese Art eher meiden): " + " | ".join(f"„{r['title']}“" for r in ins["flop"][:3]))
    if ins.get("words_good"):
        lines.append("Begriffe, die in starken Titeln vorkamen: " + ", ".join(ins["words_good"]))
    return ("\n" + "\n".join(lines) + "\n") if lines else ""
