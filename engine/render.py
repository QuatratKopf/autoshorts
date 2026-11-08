"""Videoschnitt mit ffmpeg: Kamerafahrten über die Bilder, Wort-für-Wort-Untertitel, Infokarten, Musik."""
import random
import re
import subprocess
from pathlib import Path

from .state import FONTS as FONTS_DIR, MUSIC as MUSIC_DIR, log

W, H, FPS = 1080, 1920, 30
FONT = "Poppins"


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


# ---------------------------------------------------------------- Untertitel (ASS)

def _ts(t):
    t = max(0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def _clean(w, lower):
    w = w.replace("{", "").replace("}", "").replace("\\", "")
    w = re.sub(r"^[\"„“'«»(]+|[\"“”'«»),.;:]+$", "", w)
    return w.lower() if lower else w


def build_ass(words, scenes, times, path, lower=True):
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

    pop = r"{\fad(0,0)\fscx72\fscy72\t(0,90,\fscx108\fscy108)\t(90,170,\fscx100\fscy100)}"
    lines = []
    for i, ch in enumerate(chunks):
        start = ch[0][1]
        end = chunks[i + 1][0][1] if i + 1 < len(chunks) else ch[-1][2] + 0.4
        end = min(end, ch[-1][2] + 0.6)
        text = " ".join(_clean(w, lower) for w, _, _ in ch).strip()
        if text:
            lines.append(f"Dialogue: 1,{_ts(start)},{_ts(end)},Cap,,0,0,0,,{pop}{text}")

    for sc, (s, e) in zip(scenes, times):
        ov = sc.get("overlay", "").replace("{", "").replace("}", "").upper()
        if ov:
            rot = random.choice([-4, -3, 3, 4])
            anim = r"{\frz%d\fscx40\fscy40\t(0,140,\fscx110\fscy110)\t(140,240,\fscx100\fscy100)}" % rot
            lines.append(f"Dialogue: 2,{_ts(s + 0.15)},{_ts(e)},Card,,0,0,0,,{anim}{ov}")

    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{FONT},86,&H00FFFFFF,&H00FFFFFF,&H00141414,&H96000000,-1,0,0,0,100,100,0,0,1,7,4,2,60,60,560,1
Style: Card,{FONT},92,&H003F49D2,&H003F49D2,&H00F4F1EC,&H64000000,-1,0,0,0,100,100,2,0,3,22,6,8,80,80,330,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    Path(path).write_text(head + "\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- Clips

def kenburns(img, dur, out, idx):
    f = max(2, round(dur * FPS))
    mode = idx % 4 if idx else 0
    zx = {0: f"1+0.16*on/{f}", 1: f"1.16-0.16*on/{f}", 2: "1.14", 3: "1.14"}[mode]
    xx = {0: "iw/2-iw/zoom/2", 1: "iw/2-iw/zoom/2", 2: f"(iw-iw/zoom)*on/{f}", 3: "iw/2-iw/zoom/2"}[mode]
    yy = {0: "ih/2-ih/zoom/2", 1: "ih/2-ih/zoom/2", 2: "ih/2-ih/zoom/2", 3: f"(ih-ih/zoom)*(1-on/{f})"}[mode]
    vf = (f"scale={W * 2}:{H * 2},zoompan=z='{zx}':x='{xx}':y='{yy}':d={f}:s={W}x{H}:fps={FPS},"
          f"format=yuv420p")
    ff(["-i", str(img), "-vf", vf, "-frames:v", str(f), "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "20", "-r", str(FPS), str(out)])


def pick_music(slug):
    for d in (MUSIC_DIR / slug, MUSIC_DIR):
        if d.is_dir():
            files = [p for p in d.iterdir() if p.suffix.lower() in (".mp3", ".m4a", ".wav", ".ogg")]
            if files:
                return random.choice(files)
    return None


def render(work: Path, scenes, times, voice, ass, out, music=None, music_volume=0.10, cover=None):
    """Gibt die Stelle (ms) zurück, an der das Cover-Bild im Video steht (für TikTok), sonst None."""
    clips = []
    for i, (sc, (s, e)) in enumerate(zip(scenes, times)):
        clip = work / f"clip{i:02d}.mp4"
        dur = (e - s) + (0.35 if i == len(scenes) - 1 else 0)
        kenburns(work / f"img{i:02d}.jpg", dur, clip, i)
        clips.append(clip)
        log(f"Szene {i + 1}/{len(scenes)} geschnitten")
    cover_ms, extra = None, 0.0
    if cover:   # Cover als letztes kurzes Standbild: TikTok nimmt es als Titelbild, im Loop fällt es kaum auf
        cclip = work / "clipzz.mp4"
        ff(["-loop", "1", "-i", str(cover), "-t", "0.2", "-vf", f"scale={W}:{H},format=yuv420p", "-r", str(FPS),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(cclip)])
        clips.append(cclip)
        extra = 0.2
        cover_ms = int((times[-1][1] + 0.35 + 0.1) * 1000)
    (work / "list.txt").write_text("".join(f"file '{c.name}'\n" for c in clips))
    ff(["-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy", "video.mp4"], cwd=work)

    fonts = str(FONTS_DIR) if FONTS_DIR.is_dir() else "/usr/share/fonts"
    args = ["-i", "video.mp4", "-i", str(voice)]
    vf = f"[0:v]ass={Path(ass).name}:fontsdir={fonts}[v]"
    if music:
        args += ["-stream_loop", "-1", "-i", str(music)]
        af = (f"[2:a]volume={music_volume},afade=t=in:d=1[m];[1:a]apad=pad_dur=0.8[vo];"
              f"[vo][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,loudnorm=I=-14:TP=-1.5[a]")
    else:
        af = "[1:a]apad=pad_dur=0.8,loudnorm=I=-14:TP=-1.5[a]"
    total = times[-1][1] + 0.35 + extra
    ff([*args, "-filter_complex", f"{vf};{af}", "-map", "[v]", "-map", "[a]", "-t", f"{total:.2f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-movflags", "+faststart", str(out)], cwd=work)
    return cover_ms
