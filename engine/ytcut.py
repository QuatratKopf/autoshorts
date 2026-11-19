"""Kürzere YouTube-Fassung: Shorts mit 45–55 Sekunden werden öfter zu Ende geschaut und weiter verteilt, TikTok braucht
für das Creator-Programm über eine Minute. Aus dem fertigen Video werden deshalb ein paar Nebensätze (Zusatz-Beispiel,
Nebendetail) herausgeschnitten – Bild, Stimme und Untertitel passend neu zusammengesetzt. TikTok bekommt die volle Fassung."""
import json
import shutil
import subprocess
from pathlib import Path

from .state import cfg, log

CUT = """Du schneidest ein deutsches Kurzvideo für YouTube Shorts kürzer. Du bekommst die Sätze (Nummer, Dauer in Sekunden, Text).
Wähle Sätze, die man WEGLASSEN kann, zusammen mindestens {need:.0f} Sekunden – so, dass das Video ohne sie genauso verständlich und
spannend bleibt: Zusatz-Beispiele, Wiederholungen, Nebendetails, ein zweiter Witz zum selben Punkt.
NIE weglassen: die ersten zwei Sätze, die letzten zwei Sätze, einen Satz, der eine Nummer einer Liste ankündigt („Nummer zwei …“),
einen Satz, auf den sich ein späterer Satz bezieht („Das ist der Grund, warum …“, „Genau deshalb …“), die Auflösung oder Pointe.
Lieber ein paar Sekunden zu wenig kürzen als die Geschichte kaputt machen. Antworte nur mit JSON: {{"drop": [Nummern]}}"""


def plan(scenes, times, target, chat):
    """Welche Szenen bleiben? Gibt die Liste der Szenen-Nummern zurück oder None (schon kurz genug / nichts sinnvoll zu kürzen)."""
    from .render import ITEM_RE
    n = len(scenes)
    total = times[-1][1]
    if not target or n < 8 or total <= target + 3:
        return None
    need = total - target
    lines = [f"{i}. ({e - s:.1f} s) {str(sc.get('text') or '')}" for i, (sc, (s, e)) in enumerate(zip(scenes, times))]
    js, _ = chat(CUT.format(need=need), "\n".join(lines), 0.3)
    ok = set(range(2, n - 2)) - {i for i, sc in enumerate(scenes) if ITEM_RE.search(str(sc.get("text") or ""))}
    drop = sorted({int(x) for x in (js.get("drop") or []) if str(x).lstrip("-").isdigit() and int(x) in ok})
    gain = sum(times[i][1] - times[i][0] for i in drop)
    if not drop or gain < 4:
        return None
    while drop and total - gain < target - 8:            # nicht zu viel: lieber knapp über dem Ziel als ein gehetztes Video
        i = max(drop, key=lambda k: -(times[k][1] - times[k][0]))   # den kürzesten Wegfall zurücknehmen
        drop.remove(i)
        gain -= times[i][1] - times[i][0]
    if not drop:
        return None
    return [i for i in range(n) if i not in drop]


def build(work: Path, scenes, times, words, voice, keep, out: Path, ass_args, render_args):
    """Rendert die gekürzte Fassung nach out. ass_args/render_args: die Einstellungen der vollen Fassung (ohne Szenen/Zeiten)."""
    from . import render
    sub = work / "yt"
    shutil.rmtree(sub, ignore_errors=True)
    sub.mkdir()
    total = render_args.pop("_total")
    segs, new_times, t = [], [], 0.0
    for j, i in enumerate(keep):
        s0, e0 = times[i]
        if i == len(times) - 1:
            e0 = total
        segs.append((s0, e0))
        new_times.append((t, t + (e0 - s0)))
        t += e0 - s0
        for kind in ("toon", "img"):
            src = work / (f"{kind}{i:02d}.mp4" if kind == "toon" else f"img{i:02d}.jpg")
            if src.exists():
                (sub / src.name.replace(f"{i:02d}", f"{j:02d}")).symlink_to(src.resolve())
    # Stimme: die behaltenen Abschnitte hintereinander, mit 20 ms Blende an jeder Naht (kein Knacken)
    fc = []
    for k, (s0, e0) in enumerate(segs):
        fc.append(f"[0:a]atrim={s0:.3f}:{e0:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.02,afade=t=out:st={max(0.0, e0 - s0 - 0.02):.3f}:d=0.02[a{k}]")
    fc.append("".join(f"[a{k}]" for k in range(len(segs))) + f"concat=n={len(segs)}:v=0:a=1[out]")
    v_short = sub / "voice.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(voice), "-filter_complex", ";".join(fc), "-map", "[out]", str(v_short)], check=True)
    new_words = []
    for (s0, e0), (n0, _n1) in zip(segs, new_times):
        new_words += [(w, ws - s0 + n0, we - s0 + n0) for w, ws, we in words if s0 - 0.01 <= ws < e0 - 0.01]
    sc_short = [json.loads(json.dumps(scenes[i], default=str)) for i in keep]
    for a, b in zip(sc_short, (scenes[i] for i in keep)):
        if b.get("_sfx"):
            a["_sfx"] = b["_sfx"]
    ass = sub / "subs.ass"
    render.build_ass(new_words, sc_short, new_times, ass, **ass_args)
    render.render(sub, sc_short, new_times, v_short, ass, out, **render_args)
    log(f"YouTube-Fassung: {t:.0f} s statt {total:.0f} s ({len(scenes) - len(keep)} Sätze weggelassen)")
    return t


def make(work, scenes, times, words, voice, out, ass_args, render_args, total, chat):
    """Kürzere YouTube-Fassung bauen, wenn eingestellt und sinnvoll. Gibt (Pfad, Dauer) oder (None, None) zurück."""
    target = float(cfg("youtube_seconds") or 0)
    if not target:
        return None, None
    keep = plan(scenes, times, target, chat)
    if not keep:
        return None, None
    dur = build(work, scenes, times, words, voice, keep, out, ass_args, dict(render_args, _total=total))
    return out, dur
