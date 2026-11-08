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


def stats_due(state=None):
    state = state if state is not None else _load("state.json")
    has_tokens = any((ROOT / "tokens").glob("*.enc"))
    return has_tokens and time.time() - float(state.get("last_stats") or 0) >= STATS_EVERY * 0.95


def main():
    action = (os.environ.get("IN_ACTION") or "auto").strip() or "auto"
    if action == "auto":
        slot = due_slot()
        run, media = (1, 1) if slot else ((1, 0) if stats_due() else (0, 0))
    else:
        run, media = 1, 1 if action == "make" else 0
    print(f"run={run}")
    print(f"media={media}")


if __name__ == "__main__":
    main()
