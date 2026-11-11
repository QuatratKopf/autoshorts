"""Leichte Vorprüfung ohne Zusatzpakete: Ist jetzt etwas zu tun?

Ausgabe für GitHub Actions:  run=1|0  media=1|0  (media = ffmpeg & Schriften nötig)
"""
import datetime as dt
import json
import os
import time
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(os.environ.get("AUTOSHORTS_ROOT") or Path(__file__).resolve().parent.parent)
TZ = ZoneInfo("Europe/Berlin")
STATS_EVERY = 3 * 3600


def _load(name):
    try:
        return json.loads((ROOT / "docs" / "data" / name).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def parse_times(s):
    out = []
    for part in str(s or "").replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        h, _, m = part.partition(":")
        try:
            h, m = int(h), int(m or 0)
        except ValueError:
            continue
        if 0 <= h < 24 and 0 <= m < 60:
            out.append((h, m))
    return sorted(out) or [(18, 0)]


def due_slot(config=None, state=None, now=None):
    """Gibt die fällige Upload-Zeit zurück ('2026-11-08 18:00') oder None.
    Ein Termin gilt bis 3 Stunden nach der Uhrzeit als fällig (GitHub startet geplante Läufe manchmal verspätet)."""
    config = config if config is not None else _load("config.json")
    state = state if state is not None else _load("state.json")
    settings = config.get("settings", {})
    if not settings.get("autopilot", True):
        return None
    now = now or dt.datetime.now(TZ)
    done = set(state.get("done_slots", []))
    for day in (now.date() - dt.timedelta(days=1), now.date()):
        for h, m in parse_times(settings.get("upload_times", "18:00")):
            slot = dt.datetime(day.year, day.month, day.day, h, m, tzinfo=TZ)
            sid = slot.strftime("%Y-%m-%d %H:%M")
            if slot <= now < slot + dt.timedelta(hours=3) and sid not in done:
                return sid
    return None


def plan_slot(config=None, state=None, now=None, force=False):
    """Nächster Termin, für den schon jetzt Thema und Drehbuch vorbereitet werden sollen (bis 26 Stunden vorher) – so bleibt
    Zeit, fehlende Dinge nachzubauen, bevor das Video entsteht. Gibt '2026-11-11 18:00' zurück oder None."""
    config = config if config is not None else _load("config.json")
    state = state if state is not None else _load("state.json")
    settings = config.get("settings", {})
    if not settings.get("autopilot", True) and not force:
        return None
    if settings.get("plan_ahead") is False and not force:
        return None
    now = now or dt.datetime.now(TZ)
    done = set(state.get("done_slots", []))
    best = None
    for day in (now.date(), now.date() + dt.timedelta(days=1), now.date() + dt.timedelta(days=2)):
        for h, m in parse_times(settings.get("upload_times", "18:00")):
            slot = dt.datetime(day.year, day.month, day.day, h, m, tzinfo=TZ)
            sid = slot.strftime("%Y-%m-%d %H:%M")
            if slot > now and sid not in done and (force or slot - now <= dt.timedelta(hours=26)):
                if best is None or sid < best:
                    best = sid
    return best


def review_slot(config=None, state=None, now=None, hours=4):
    """Termin, für den jetzt ein Video zur Prüfung gebaut wird: gerade fällig oder in den nächsten Stunden."""
    config = config if config is not None else _load("config.json")
    state = state if state is not None else _load("state.json")
    now = now or dt.datetime.now(TZ)
    done = set(state.get("done_slots", []))
    for day in (now.date() - dt.timedelta(days=1), now.date(), now.date() + dt.timedelta(days=1)):
        for h, m in parse_times(config.get("settings", {}).get("upload_times", "18:00")):
            slot = dt.datetime(day.year, day.month, day.day, h, m, tzinfo=TZ)
            sid = slot.strftime("%Y-%m-%d %H:%M")
            if slot - dt.timedelta(hours=hours) <= now < slot + dt.timedelta(hours=3) and sid not in done:
                return sid
    return None


def review_stale(hours=3):
    """Videos, die auf die Prüfung warten, aber seit Stunden niemand freigegeben hat – der Autopilot lädt sie dann selbst hoch."""
    vids = _load("videos.json")
    vids = vids if isinstance(vids, list) else vids.get("videos", [])
    return [v["id"] for v in vids if v.get("status") == "review" and time.time() - float(v.get("review_at") or 0) > hours * 3600]


def plan_due():
    sid = plan_slot()
    return bool(sid) and sid not in _load("plans.json")


def stats_due(state=None):
    state = state if state is not None else _load("state.json")
    settings = _load("config.json").get("settings", {})
    has_tokens = any((ROOT / "tokens").glob("*.enc")) or settings.get("upload_via") == "zernio"
    try:
        every = max(15, float(settings.get("stats_minutes") or 30)) * 60
    except (TypeError, ValueError):
        every = STATS_EVERY
    return has_tokens and time.time() - float(state.get("last_stats") or 0) >= every * 0.9


def main():
    action = (os.environ.get("IN_ACTION") or "auto").strip() or "auto"
    if action == "auto":
        slot = due_slot()
        run, media = (1, 1) if slot else ((1, 0) if (stats_due() or plan_due() or review_stale()) else (0, 0))
    else:
        run, media = 1, 1 if action in ("make", "review_make") else 0
    print(f"run={run}")
    print(f"media={media}")


if __name__ == "__main__":
    main()
