"""Videoschnitt mit ffmpeg: lebendige Kamerafahrten, animierte Einblendungen, Übergänge, Soundeffekte,
Wort-für-Wort-Untertitel mit hervorgehobenen Schlüsselwörtern, Uhr/Countdown oben, Musik."""
import random
import re
import subprocess
from pathlib import Path

from . import overlays
from .state import FONTS as FONTS_DIR, MUSIC as MUSIC_DIR, log

W, H, FPS = 1080, 1920, 30
FONT = "Poppins"
XF = 0.25          # Länge der Übergänge (s)


def ff(args, cwd=None):
    p = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
                       cwd=cwd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg: " + p.stderr[-800:])


# ---------------------------------------------------------------- Szenen-Timing

def _norm(w):
    return re.sub(r"[^\wäöüß]", "", w.lower())


def scene_times(scenes, words, total):
    """Ordnet jeder Szene Start/Ende zu, indem die Wörter der Szenen auf die gesprochenen Wort-Zeiten gelegt werden."""
    counts = [len(s["text"].split()) for s in scenes]
    n_script, n_spoken = sum(counts), len(words)
    starts, cum = [], 0
    for c in counts:
        idx = min(n_spoken - 1, round(cum * n_spoken / max(1, n_script)))
        starts.append(0.0 if not starts else words[idx][1])
        cum += c
    ends = starts[1:] + [total]
    return list(zip(starts, ends))


# ---------------------------------------------------------------- Untertitel, Uhr, Countdown (ASS)

def _ts(t):
    t = max(0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def _clean(w, lower):
    w = w.replace("{", "").replace("}", "").replace("\\", "")
    w = re.sub(r"^[\"„“'«»(]+|[\"“”'«»),.;:!?]+$", "", w)
    return w.lower() if lower else w.upper()


def build_ass(words, scenes, times, path, lower=True, hud=None, countdown=None):
    # Wörter zu kurzen Häppchen (1–2 Wörter, max. 14 Zeichen) zusammenfassen
    chunks, cur = [], []
    for w, s, e in words:
        cur.append((w, s, e))
        txt = " ".join(x[0] for x in cur)
        if len(cur) >= 2 or len(txt) >= 12 or re.search(r"[.!?,;:]$", w):
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)

    # Schlüsselwörter je Szene (werden gelb)
    hl_by_time = []
    for sc, (s, e) in zip(scenes, times):
        keys = {_norm(k) for k in (sc.get("highlight") or []) for k in str(k).split()}
        hl_by_time.append((s, e, keys))

    def is_key(word, t):
        n = _norm(word)
        for s, e, keys in hl_by_time:
            if s - 0.05 <= t < e + 0.05:
                return n in keys and len(n) > 1
        return False

    pop = r"{\fscx72\fscy72\t(0,90,\fscx108\fscy108)\t(90,170,\fscx100\fscy100)}"
    lines = []
    for i, ch in enumerate(chunks):
        start = ch[0][1]
        end = chunks[i + 1][0][1] if i + 1 < len(chunks) else ch[-1][2] + 0.4
        end = min(end, ch[-1][2] + 0.6)
        parts = []
        for w, s, _ in ch:
            c = _clean(w, lower)
            if not c:
                continue
            parts.append(r"{\c&H003FD2FF&}" + c + r"{\c&H00FFFFFF&}" if is_key(w, s) else c)
        text = " ".join(parts).strip()
        if text:
            lines.append(f"Dialogue: 1,{_ts(start)},{_ts(end)},Cap,,0,0,0,,{pop}{text}")

    total = times[-1][1] + 0.4
    # Ecke oben links: Ort/Zeit-Angabe der Geschichte (z. B. „TAG 1 · 3:12 UHR“), je Szene änderbar
    if hud:
        for sc, (s, e) in zip(scenes, times):
            lab = str(sc.get("hud") or hud or "").replace("{", "").replace("}", "").upper()[:28]
            if lab:
                lines.append(f"Dialogue: 3,{_ts(s)},{_ts(e)},Hud,,0,0,0,,{lab}")
    # Countdown oben rechts: läuft sichtbar herunter, wird zum Ende hin rot
    if countdown and countdown.get("seconds"):
        start_v = max(10, int(countdown["seconds"]))
        rate = max(1.0, start_v * 0.6 / max(1.0, total))      # Story-Zeit läuft schneller als echte Zeit
        lab = str(countdown.get("label") or "").replace("{", "").replace("}", "").upper()[:16]
        t = 0.0
        while t < total:
            v = max(0, int(start_v - t * rate))
            col = r"{\c&H003C3AE2&}" if v < start_v * 0.25 else r"{\c&H003FD2FF&}"
            lines.append(f"Dialogue: 3,{_ts(t)},{_ts(min(total, t + 1))},Cnt,,0,0,0,,"
                         + (r"{\fs34\c&H00DDDDDD&}" + lab + r"\N" if lab else "") + col + f"{v // 60}:{v % 60:02d}")
            t += 1.0

    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{FONT},{86 if lower else 92},&H00FFFFFF,&H00FFFFFF,&H00141414,&H96000000,-1,0,0,0,100,100,{0 if lower else 2},0,1,8,4,2,60,60,560,1
Style: Hud,{FONT},54,&H00FFFFFF,&H00FFFFFF,&H00141414,&H64000000,-1,0,0,0,100,100,1,0,1,5,2,7,60,60,190,1
Style: Cnt,{FONT},76,&H003FD2FF,&H003FD2FF,&H00141414,&H64000000,-1,0,0,0,100,100,1,0,1,6,2,9,60,60,170,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    Path(path).write_text(head + "\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- Clips

MOTIONS = ("zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "zoom_in")


def scene_clip(img, dur, out, idx, motion=None, ov=None, work=None):
    """Bild → bewegter Clip: Kamerafahrt + leichtes „Atmen“, optional Wackeln, darüber die Einblendung."""
    f = max(2, round(dur * FPS))
    motion = motion if motion in ("zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "shake", "still") \
        else MOTIONS[idx % len(MOTIONS)]
    breath = "0.006*sin(2*PI*on/48)"
    z = {"zoom_in": f"1.04+0.14*on/{f}", "zoom_out": f"1.18-0.14*on/{f}", "shake": "1.12",
         "still": "1.06"}.get(motion, "1.14")
    x = "iw/2-iw/zoom/2"
    y = "ih/2-ih/zoom/2"
    if motion == "pan_left":
        x = f"(iw-iw/zoom)*(1-on/{f})"
    elif motion == "pan_right":
        x = f"(iw-iw/zoom)*on/{f}"
    elif motion == "pan_up":
        y = f"(ih-ih/zoom)*(1-on/{f})"
    elif motion == "shake":   # kräftig am Anfang, klingt ab
        x = f"iw/2-iw/zoom/2+38*sin(on*2.3)*max(0,1-on/14)"
        y = f"ih/2-ih/zoom/2+30*cos(on*2.9)*max(0,1-on/14)"
    vf = (f"scale={W * 2}:{H * 2}:flags=lanczos,zoompan=z='{z}+{breath}':x='{x}':y='{y}':d={f}:s={W}x{H}:fps={FPS}")
    args = ["-i", str(img)]
    fc = f"[0:v]{vf},format=yuv420p[bg]"
    last = "bg"
    if ov and work is not None:
        res = overlays.write_frames(ov, work / f"ov{idx:02d}")
        if res:
            pattern, cy, ow, oh = res
            args += ["-framerate", str(FPS), "-i", pattern]
            ox, oy = (W - ow) // 2, max(140, min(H - oh - 520, cy - oh // 2))
            fc += f";[1:v]format=rgba,setpts=PTS+0.18/TB[ov];[bg][ov]overlay={ox}:{oy}:eof_action=repeat:format=auto[vo]"
            last = "vo"
    ff([*args, "-filter_complex", fc + f";[{last}]setsar=1,format=yuv420p[out]", "-map", "[out]", "-frames:v", str(f),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-r", str(FPS), str(out)])


# ---------------------------------------------------------------- Soundeffekte (werden synthetisch erzeugt)

SFX = {
    "whoosh": "anoisesrc=d=0.5:c=pink:a=0.5,highpass=f=400,lowpass=f=2600,afade=t=in:d=0.22,afade=t=out:st=0.22:d=0.28",
    "pop": "sine=f=520:d=0.12,asetrate=44100*1.6,aresample=44100,afade=t=out:st=0.02:d=0.1,volume=0.9",
    "ding": "sine=f=1318:d=0.7,afade=t=out:st=0:d=0.7,volume=0.6",
    "boom": "sine=f=52:d=0.9,afade=t=out:st=0.05:d=0.85,volume=2.2",
    "tick": "sine=f=2000:d=0.03,afade=t=out:st=0:d=0.03,volume=0.5",
}


def make_sfx(work: Path):
    out = {}
    for name, src in SFX.items():
        p = work / f"sfx_{name}.wav"
        try:
            ff(["-f", "lavfi", "-i", src, "-ac", "2", "-ar", "44100", str(p)])
            out[name] = p
        except RuntimeError as e:
            log(f"Soundeffekt {name} übersprungen: {e}")
    return out


def pick_music(slug):
    for d in (MUSIC_DIR / slug, MUSIC_DIR):
        if d.is_dir():
            files = [p for p in d.iterdir() if p.suffix.lower() in (".mp3", ".m4a", ".wav", ".ogg")]
            if files:
                return random.choice(files)
    return None


# ---------------------------------------------------------------- Zusammenbau

TRANSITIONS = ("fade", "slideleft", "fade", "smoothup", "fade", "slideright", "circleopen")


def render(work: Path, scenes, times, voice, ass, out, music=None, music_volume=0.10, cover=None, sfx_volume=0.35):
    """Gibt die Stelle (ms) zurück, an der das Cover-Bild im Video steht (für TikTok), sonst None."""
    n = len(scenes)
    durs = [(e - s) for s, e in times]
    durs[-1] += 0.35
    clips = []
    for i, sc in enumerate(scenes):
        clip = work / f"clip{i:02d}.mp4"
        extra = XF if i < n - 1 else 0          # Überlappung für den Übergang zur nächsten Szene
        scene_clip(work / f"img{i:02d}.jpg", durs[i] + extra, clip, i, sc.get("camera"), sc.get("overlay"), work)
        clips.append(clip)
        log(f"Szene {i + 1}/{n} geschnitten")

    # Übergänge: Szene k+1 beginnt genau an ihrer Sprech-Startzeit, die vorige Szene blendet darüber aus
    inputs, fc, prev = [], [], "0:v"
    for c in clips:
        inputs += ["-i", c.name]
    for k in range(1, n):
        tr = "slideleft" if scenes[k].get("sfx") == "whoosh" else TRANSITIONS[k % len(TRANSITIONS)]
        off = sum(durs[:k])
        fc.append(f"[{prev}][{k}:v]xfade=transition={tr}:duration={XF}:offset={off:.3f}[x{k}]")
        prev = f"x{k}"
    total = sum(durs)
    cover_ms = None
    if cover:   # Cover als letztes kurzes Standbild: TikTok nimmt es als Titelbild, im Loop fällt es kaum auf
        inputs += ["-loop", "1", "-t", "0.2", "-i", str(cover)]
        fc.append(f"[{n}:v]scale={W}:{H},setsar=1,fps={FPS},format=yuv420p[cv];[{prev}][cv]concat=n=2:v=1:a=0[vc]")
        prev = "vc"
        cover_ms = int((total + 0.1) * 1000)
        total += 0.2
    if n == 1 and not cover:
        fc.append("[0:v]null[vfinal]")
    else:
        fc.append(f"[{prev}]null[vfinal]")
    ff([*inputs, "-filter_complex", ";".join(fc), "-map", "[vfinal]", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "19", "-pix_fmt", "yuv420p", "-r", str(FPS), "video.mp4"], cwd=work)

    # Ton: Stimme + Musik + Soundeffekte an den Szenenwechseln / Einblendungen
    fonts = str(FONTS_DIR) if FONTS_DIR.is_dir() else "/usr/share/fonts"
    sfx = make_sfx(work) if sfx_volume > 0 else {}
    args = ["-i", "video.mp4", "-i", str(voice)]
    parts, mix = [], ["[vo]"]
    parts.append("[1:a]apad=pad_dur=0.8[vo]")
    idx = 2
    if music:
        args += ["-stream_loop", "-1", "-i", str(music)]
        parts.append(f"[{idx}:a]volume={music_volume},afade=t=in:d=1[m]")
        mix.append("[m]")
        idx += 1
    events = []
    for i, (sc, (s, _)) in enumerate(zip(scenes, times)):
        name = str(sc.get("sfx") or "").lower()
        if name in sfx:
            events.append((s, name))
        if isinstance(sc.get("overlay"), dict) and sc["overlay"].get("type") and name != "pop" and "pop" in sfx:
            events.append((s + 0.2, "pop"))
    for k, (t, name) in enumerate(events[:40]):
        args += ["-i", str(sfx[name])]
        ms = int(t * 1000)
        parts.append(f"[{idx}:a]volume={sfx_volume},adelay={ms}|{ms}[s{k}]")
        mix.append(f"[s{k}]")
        idx += 1
    if len(mix) > 1:
        parts.append(f"{''.join(mix)}amix=inputs={len(mix)}:duration=first:dropout_transition=0:normalize=0,"
                     "loudnorm=I=-14:TP=-1.5[a]")
    else:
        parts.append("[vo]loudnorm=I=-14:TP=-1.5[a]")
    vf = f"[0:v]ass={Path(ass).name}:fontsdir={fonts}[v]"
    ff([*args, "-filter_complex", vf + ";" + ";".join(parts), "-map", "[v]", "-map", "[a]", "-t", f"{total:.2f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-movflags", "+faststart", str(out)], cwd=work)
    return cover_ms
