"""Musik-Kugel: Eine Kugel fällt und springt – bei jedem Ton der Melodie trifft sie genau eine Glasscheibe, die klingt und zerspringt.

Wie es funktioniert: Aus der Melodie (Tonhöhe + Zeitpunkt jeder Note) wird rückwärts ein Flugweg gebaut. Zwischen zwei Tönen fliegt die
Kugel eine echte Wurfparabel (Schwerkraft); am Ort jedes Aufpralls steht eine Scheibe, deren Neigung genau die Richtungsänderung der
Kugel erklärt. Deshalb trifft jeder Aufprall exakt einen Ton. Der Ton wird selbst erzeugt (Glockenspiel-Klang + Glas-Klirren).

Nur gemeinfreie Melodien (Komponist seit über 70 Jahren tot bzw. Volkslied): bekannte Chart-Songs sind auch nachgespielt geschützt
(Content ID sperrt oder kassiert das Video)."""
import colorsys
import math
import random
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .state import log

W, H, FPS, SR = 1080, 1920, 30, 44100
G = 2600.0                       # Schwerkraft (px/s²)
BOX = (150, 520, 930, 1580)      # Bereich, in dem die Kugel springt (x0, y0, x1, y1)
BALL_R = 22
PANE_LEN, PANE_W = 118, 18
SHOW_AHEAD = 5.0                 # so lange vor dem Aufprall steht eine Scheibe schon da (s) – der Flugweg hält ihren Platz frei
STRICT_STEPS = 6000
GRAZE = 0.3                     # Kugel trifft die Scheibe nicht zu flach (sonst streift sie vorher deren Ende)
AHEAD_N = 12                     # höchstens so viele Scheiben stehen gleichzeitig da (bei schnellen Melodien wird es sonst unübersichtlich)


def appear_at(times, j):
    """Ab wann steht die Scheibe j da: SHOW_AHEAD vor ihrem Ton, aber erst wenn die Scheibe AHEAD_N davor zersprungen ist;
    die ersten stehen ab Bild 1 da."""
    a = max(0.0, times[j] - SHOW_AHEAD)
    return max(a, times[j - AHEAD_N]) if j >= AHEAD_N else a
FALL = 0.55                      # die Kugel liegt am Anfang auf einer Startklappe; so lange fällt sie bis zum ersten Ton (s)
CLEAR = PANE_LEN / 2 + PANE_W / 2 + BALL_R + 14   # so weit bleibt die Kugel von Scheiben weg, die schon dastehen

# Melodien: (Name, Komponist/Herkunft, Tempo in Schlägen pro Minute, [(MIDI-Ton oder None für Pause, Dauer in Schlägen), ...])
_C = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}


def _n(s):
    """'E5' → MIDI-Nummer, 'r' → Pause."""
    if s in ("r", "-"):
        return None
    name, octv = s[:-1], int(s[-1])
    return 12 * (octv + 1) + _C[name]


def _seq(text):
    """'E5:.25 D#5:.25 …' → [(midi, dauer), …]"""
    out = []
    for tok in text.split():
        n, d = tok.split(":")
        out.append((_n(n), float(d)))
    return out


SONGS = {
    "fuer_elise": ("Für Elise", "Ludwig van Beethoven", 72, _seq(
        "E5:.25 D#5:.25 E5:.25 D#5:.25 E5:.25 B4:.25 D5:.25 C5:.25 A4:.75 C4:.25 E4:.25 A4:.25 B4:.75 E4:.25 G#4:.25 B4:.25 C5:.75 "
        "E4:.25 E5:.25 D#5:.25 E5:.25 D#5:.25 E5:.25 B4:.25 D5:.25 C5:.25 A4:.75 C4:.25 E4:.25 A4:.25 B4:.75 E4:.25 C5:.25 B4:.25 A4:1 "
        "r:.25 E5:.25 D#5:.25 E5:.25 D#5:.25 E5:.25 B4:.25 D5:.25 C5:.25 A4:.75 C4:.25 E4:.25 A4:.25 B4:.75 E4:.25 G#4:.25 B4:.25 C5:.75 "
        "E4:.25 E5:.25 D#5:.25 E5:.25 D#5:.25 E5:.25 B4:.25 D5:.25 C5:.25 A4:.75 C4:.25 E4:.25 A4:.25 B4:.75 E4:.25 C5:.25 B4:.25 A4:1.5")),
    "ode_freude": ("Ode an die Freude", "Ludwig van Beethoven", 132, _seq(
        "E4:1 E4:1 F4:1 G4:1 G4:1 F4:1 E4:1 D4:1 C4:1 C4:1 D4:1 E4:1 E4:1.5 D4:.5 D4:2 "
        "E4:1 E4:1 F4:1 G4:1 G4:1 F4:1 E4:1 D4:1 C4:1 C4:1 D4:1 E4:1 D4:1.5 C4:.5 C4:2 "
        "D4:1 D4:1 E4:1 C4:1 D4:1 E4:.5 F4:.5 E4:1 C4:1 D4:1 E4:.5 F4:.5 E4:1 D4:1 C4:1 D4:1 G3:2 "
        "E4:1 E4:1 F4:1 G4:1 G4:1 F4:1 E4:1 D4:1 C4:1 C4:1 D4:1 E4:1 D4:1.5 C4:.5 C4:2")),
    "bergkoenig": ("In der Halle des Bergkönigs", "Edvard Grieg", 132, _seq(
        ("B3:.5 C#4:.5 D4:.5 E4:.5 F#4:.5 D4:.5 F#4:1 F4:.5 C#4:.5 F4:1 E4:.5 C4:.5 E4:1 "
         "B3:.5 C#4:.5 D4:.5 E4:.5 F#4:.5 D4:.5 F#4:.5 B4:.5 A4:.5 F#4:.5 D4:.5 F#4:.5 A4:2 ") * 1
        + ("B4:.5 C#5:.5 D5:.5 E5:.5 F#5:.5 D5:.5 F#5:1 F5:.5 C#5:.5 F5:1 E5:.5 C5:.5 E5:1 "
           "B4:.5 C#5:.5 D5:.5 E5:.5 F#5:.5 D5:.5 F#5:.5 B5:.5 A5:.5 F#5:.5 D5:.5 F#5:.5 A5:2"))),
    "korobeiniki": ("Korobeiniki (die Tetris-Melodie)", "russisches Volkslied", 150, _seq(
        "E5:1 B4:.5 C5:.5 D5:1 C5:.5 B4:.5 A4:1 A4:.5 C5:.5 E5:1 D5:.5 C5:.5 B4:1.5 C5:.5 D5:1 E5:1 C5:1 A4:1 A4:1 r:1 "
        "r:.5 D5:1 F5:.5 A5:1 G5:.5 F5:.5 E5:1.5 C5:.5 E5:1 D5:.5 C5:.5 B4:1 B4:.5 C5:.5 D5:1 E5:1 C5:1 A4:1 A4:1 r:1 "
        "E5:1 B4:.5 C5:.5 D5:1 C5:.5 B4:.5 A4:1 A4:.5 C5:.5 E5:1 D5:.5 C5:.5 B4:1.5 C5:.5 D5:1 E5:1 C5:1 A4:1 A4:2")),
    "jingle_bells": ("Jingle Bells", "James Lord Pierpont", 160, _seq(
        "E4:1 E4:1 E4:2 E4:1 E4:1 E4:2 E4:1 G4:1 C4:1.5 D4:.5 E4:4 F4:1 F4:1 F4:1.5 F4:.5 F4:1 E4:1 E4:1 E4:.5 E4:.5 "
        "E4:1 D4:1 D4:1 E4:1 D4:2 G4:2 E4:1 E4:1 E4:2 E4:1 E4:1 E4:2 E4:1 G4:1 C4:1.5 D4:.5 E4:4 "
        "F4:1 F4:1 F4:1.5 F4:.5 F4:1 E4:1 E4:1 E4:.5 E4:.5 G4:1 G4:1 F4:1 D4:1 C4:4")),
    "nachtmusik": ("Eine kleine Nachtmusik", "Wolfgang Amadeus Mozart", 132, _seq(
        "G4:1 r:.5 D4:.5 G4:1 r:.5 D4:.5 G4:.5 D4:.5 G4:.5 B4:.5 D5:2 C5:1 r:.5 A4:.5 C5:1 r:.5 A4:.5 C5:.5 A4:.5 F#4:.5 A4:.5 D4:2 "
        "G4:1 r:.5 D4:.5 G4:1 r:.5 D4:.5 G4:.5 D4:.5 G4:.5 B4:.5 D5:2 C5:1 r:.5 A4:.5 C5:1 r:.5 A4:.5 C5:.5 A4:.5 F#4:.5 A4:.5 G4:2")),
    "funkel": ("Morgen kommt der Weihnachtsmann / Twinkle Twinkle", "französisches Volkslied", 120, _seq(
        "C5:1 C5:1 G5:1 G5:1 A5:1 A5:1 G5:2 F5:1 F5:1 E5:1 E5:1 D5:1 D5:1 C5:2 G5:1 G5:1 F5:1 F5:1 E5:1 E5:1 D5:2 "
        "G5:1 G5:1 F5:1 F5:1 E5:1 E5:1 D5:2 C5:1 C5:1 G5:1 G5:1 A5:1 A5:1 G5:2 F5:1 F5:1 E5:1 E5:1 D5:1 D5:1 C5:2")),
    "wiegenlied": ("Guten Abend, gut' Nacht (Wiegenlied)", "Johannes Brahms", 100, _seq(
        "E4:.5 E4:.5 G4:2 E4:.5 E4:.5 G4:2 E4:.5 G4:.5 C5:1 B4:1.5 A4:.5 A4:1 G4:1 D4:.5 E4:.5 F4:1 D4:1 D4:.5 E4:.5 F4:2 "
        "D4:.5 F4:.5 B4:.5 A4:.5 G4:1 B4:1 C5:2 C4:.5 C4:.5 C5:2 A4:.5 F4:.5 G4:2 E4:.5 C4:.5 F4:1 G4:1 A4:1 G4:2 "
        "C4:.5 C4:.5 C5:2 A4:.5 F4:.5 G4:2 E4:.5 C4:.5 F4:1 E4:1 D4:1 C4:3")),
    "greensleeves": ("Greensleeves", "englisches Volkslied", 112, _seq(
        "A4:1 C5:2 D5:1 E5:1.5 F5:.5 E5:1 D5:2 B4:1 G4:1.5 A4:.5 B4:1 C5:2 A4:1 A4:1.5 G#4:.5 A4:1 B4:2 G#4:1 E4:2 "
        "A4:1 C5:2 D5:1 E5:1.5 F5:.5 E5:1 D5:2 B4:1 G4:1.5 A4:.5 B4:1 C5:1.5 B4:.5 A4:1 G#4:1.5 F#4:.5 G#4:1 A4:3")),
    "saints": ("When the Saints Go Marching In", "Gospel (traditionell)", 150, _seq(
        "C4:1 E4:1 F4:1 G4:4 r:1 C4:1 E4:1 F4:1 G4:4 r:1 C4:1 E4:1 F4:1 G4:2 E4:2 C4:2 E4:2 D4:4 r:1 "
        "E4:1 E4:1 D4:1 C4:3 C4:1 E4:2 G4:2 G4:1 F4:3 r:1 E4:1 F4:1 G4:1 E4:2 C4:2 D4:2 C4:4")),
    "auld_lang_syne": ("Auld Lang Syne (Nehmt Abschied, Brüder)", "schottisches Volkslied", 100, _seq(
        "C4:1 F4:1.5 F4:.5 F4:1 A4:1 G4:1.5 F4:.5 G4:1 A4:1 F4:1.5 F4:.5 A4:1 C5:1 D5:3 D5:1 C5:1.5 A4:.5 A4:1 F4:1 "
        "G4:1.5 F4:.5 G4:1 A4:1 F4:1.5 D4:.5 D4:1 C4:1 F4:3")),
    "bella_ciao": ("Bella Ciao", "italienisches Volkslied", 120, _seq(
        "E4:.5 A4:.5 B4:.5 C5:.5 A4:2 E4:.5 A4:.5 B4:.5 C5:.5 A4:2 "
        "E4:.5 A4:.5 B4:.5 C5:1 B4:.5 A4:.5 C5:1 B4:.5 A4:.5 E5:1 E5:1 E5:1 r:.5 "
        "D5:.5 E5:.5 F5:.5 F5:2 F5:.5 E5:.5 D5:.5 F5:.5 E5:2 E5:.5 D5:.5 C5:.5 B4:1 E5:1 C5:1 B4:1 A4:2")),
    "cucaracha": ("La Cucaracha", "mexikanisches Volkslied", 140, _seq(
        "C4:.5 C4:.5 C4:.5 F4:1 A4:1.5 C4:.5 C4:.5 C4:.5 F4:1 A4:1.5 r:.5 "
        "F4:.5 F4:.5 E4:.5 E4:.5 D4:.5 D4:.5 C4:2 r:.5 "
        "C4:.5 C4:.5 C4:.5 E4:1 G4:1.5 C4:.5 C4:.5 C4:.5 E4:1 G4:1.5 r:.5 "
        "C5:.5 D5:.5 C5:.5 A#4:.5 A4:.5 G4:.5 F4:2")),
}


def notes(song, start=0.9):
    """[(Zeit s, MIDI)] der Melodie; kurze Melodien laufen zweimal (das zweite Mal etwas schneller)."""
    _name, _who, bpm, seq = SONGS[song]
    beat = 60.0 / bpm
    out, t = [], start
    total = sum(d for _, d in seq) * beat
    rounds = 2 if total < 26 else 1
    for r in range(rounds):
        b = beat * (0.88 if r else 1.0)
        for m, d in seq:
            if m is not None:
                out.append((round(t, 4), m))
            t += d * b
        t += b
    return out, t + 0.6


# ------------------------------------------------------------------ eigenes Lied (aus der App hochgeladen)

def _decode(path, sr=22050, start=0.0, dur=None):
    args = ["ffmpeg", "-v", "error", "-ss", f"{start:.2f}", "-i", str(path)] + (["-t", f"{dur:.2f}"] if dur else []) + \
           ["-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    raw = subprocess.run(args, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def song_hits(path, length=40.0):
    """Töne und Beats in einem Lied finden: den mitreißendsten Abschnitt (meist der Refrain: lauteste {length} s) und darin die
    deutlichen Einsätze (Spektral-Fluss mit beweglicher Schwelle). Gibt (Startzeit im Lied, Dauer, [(Zeit, Tonhöhe)]) zurück."""
    sr = 11025
    y = _decode(path, sr)
    if len(y) < sr * 8:
        raise RuntimeError("Lied zu kurz")
    total = len(y) / sr
    length = min(length, total - 1)
    hop = int(sr * 0.5)                                  # lautester Abschnitt (Refrain) – nicht ganz am Anfang oder Ende
    rms = np.sqrt(np.convolve(y ** 2, np.ones(hop) / hop, mode="valid")[::hop])
    win = int(length / 0.5)
    best, best_e = 0.0, -1.0
    for k in range(int(len(rms) * 0.12), max(int(len(rms) * 0.12) + 1, len(rms) - win)):
        e_ = float(np.mean(rms[k:k + win]))
        if e_ > best_e:
            best, best_e = k * 0.5, e_
    seg = y[int(best * sr): int((best + length) * sr)]
    chosen = melody_onsets(seg, sr, max_rate=4.0)
    return best, length, chosen


def _median_filter(a, size, axis):
    """Gleitender Median (nur numpy) entlang einer Achse – für die Trennung von Tönen (waagerecht) und Schlägen (senkrecht)."""
    pad = size // 2
    a2 = np.moveaxis(a, axis, -1)
    p = np.pad(a2, [(0, 0)] * (a2.ndim - 1) + [(pad, pad)], mode="edge")
    out = np.median(np.lib.stride_tricks.sliding_window_view(p, size, axis=-1), axis=-1)
    return np.moveaxis(out, -1, axis)


HK, TH, FL = [5], [0.8], [20]                       # Ton-Glättung (Frames), Einsatz-Schwelle, Leiseste 20 % zählen nicht – an Remixen gemessen
LOCAL_FLUX, PITCH_CHANGE = [False], [False]             # gemessen an Remixen mit bekannten Tönen: so am genauesten


def melody_onsets(seg, sr, max_rate=4.0, lo=220.0, hi=2000.0):
    """Einsätze der MELODIE (nicht des Schlagzeugs): Das Spektrogramm wird in Töne (waagerechte Linien) und Schläge (senkrechte
    Striche) getrennt (HPSS per Median); nur der Ton-Anteil im Melodiebereich zählt. Ein neuer Ton = Energiesprung im Ton-Anteil
    ODER die führende Tonhöhe springt auf einen anderen Halbton und bleibt dort. Gibt [(Zeit, midi)] zurück."""
    n_fft, hp = 2048, 256
    if len(seg) < n_fft * 4:
        return []
    frames = np.lib.stride_tricks.sliding_window_view(seg, n_fft)[::hp] * np.hanning(n_fft)
    mag = np.abs(np.fft.rfft(frames, axis=1)).astype(np.float32)
    k0, k1 = int(lo * n_fft / sr), int(hi * n_fft / sr)
    band = mag[:, k0:k1]
    harm = _median_filter(band, HK[0], 0)                 # über die Zeit glätten: bleibt, was klingt (Ton)
    perc = _median_filter(band, 17, 1)                   # über die Frequenz glätten: bleibt, was knallt (Schlag)
    h = band * (harm ** 2 / (harm ** 2 + perc ** 2 + 1e-9))
    dt = hp / sr
    off = 0.5 * n_fft / sr + 0.04                        # Einsatz: Fenstermitte + Anschwellen des Tons (an Remixen mit bekannten Tönen gemessen)
    energy = h.sum(axis=1)
    floor = np.percentile(energy, FL[0])
    peak_bin = np.argmax(h, axis=1) + k0
    freq = peak_bin * sr / n_fft
    midi = np.round(69 + 12 * np.log2(np.maximum(freq, 30) / 440)).astype(int)
    logh = np.log1p(h * 10)
    dif = np.maximum(0, np.diff(logh, axis=0))
    if LOCAL_FLUX[0]:                                    # nur rund um die führende Tonhöhe: Akkordwechsel im Hintergrund zählen nicht
        pb = np.argmax(h, axis=1)
        idx = np.minimum(len(pb) - 1, np.arange(len(dif)) + 2)
        cols = np.arange(h.shape[1])[None, :]
        near = np.abs(cols - pb[idx][:, None]) <= np.maximum(2, pb[idx][:, None] * 0.06)
        flux = (dif * near).sum(axis=1)
    else:
        flux = dif.sum(axis=1)
    flux = (flux - flux.mean()) / (flux.std() + 1e-6)
    med = np.array([np.median(flux[max(0, i - 20): i + 20]) for i in range(len(flux))])
    cand = {}
    for i in range(1, len(flux) - 1):                    # Energiesprung im Ton-Anteil
        if flux[i] > flux[i - 1] and flux[i] >= flux[i + 1] and flux[i] > med[i] + TH[0] and energy[min(len(energy) - 1, i + 2)] > floor:
            cand[i + 1] = float(flux[i])
    hold = 3 if PITCH_CHANGE[0] else 10 ** 6             # Tonhöhenwechsel ohne neuen Anschlag (gebundene Melodie)
    for i in range(1, max(1, len(midi) - hold)):
        if energy[i] > floor and midi[i] != midi[i - 1] and all(midi[i + j] == midi[i] for j in range(hold)) \
                and all(abs(i - c) > 3 for c in cand):
            cand[i] = 0.5
    order = sorted(cand, key=lambda i: -cand[i])
    chosen = []
    for i in order:                                      # stärkste zuerst, mindestens 0,13 s Abstand, höchstens max_rate pro Sekunde
        tt = i * dt + off
        if all(abs(tt - c) >= 0.13 for c, _ in chosen):
            j = min(len(midi) - 1, i + 2)
            chosen.append((round(tt, 4), int(midi[j])))
        if len(chosen) >= len(seg) / sr * max_rate:
            break
    chosen.sort()
    return chosen


def file_song(path, work, lead=0.9):
    """Eigenes Lied vorbereiten: Abschnitt schneiden (weich ein/aus), Töne finden, leises Glasklirren auf jeden Aufprall legen."""
    start, length, found = song_hits(path)
    hits = [(round(t + lead, 4), m) for t, m in found]
    total = lead + length + 0.6
    clip = Path(work) / "song_clip.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.2f}", "-t", f"{length:.2f}", "-i", str(path),
                    "-af", f"afade=t=in:d=0.4,afade=t=out:st={length - 1.5:.2f}:d=1.5,adelay={int(lead * 1000)}|{int(lead * 1000)},"
                           f"apad=pad_dur=0.6,loudnorm=I=-14:TP=-1.5", "-ac", "2", "-ar", str(SR), str(clip)], check=True)
    tink = Path(work) / "tink.wav"
    audio(hits, total, tink, 1)
    out = Path(work) / "bounce.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(clip), "-i", str(tink), "-filter_complex",
                    "[1:a]volume=0.18[t];[0:a][t]amix=inputs=2:duration=first:normalize=0", str(out)], check=True)
    return hits, total, out


# ------------------------------------------------------------------ Flugweg

RESTITUTION = (0.86, 1.08)       # wie viel Schwung ein Abprall behält (Glas federt leicht nach)
SPRINGY = (1.0, 2.0)             # nur wenn ein langer Ton sonst nicht erreichbar ist: federnde Scheibe (Winkel bleibt echt)


def _reflect(v, n, e):
    """Echter Abprall: die Geschwindigkeit senkrecht zur Scheibe dreht um (mal e), die entlang der Scheibe bleibt."""
    vn = v[0] * n[0] + v[1] * n[1]
    return (v[0] - (1 + e) * vn * n[0], v[1] - (1 + e) * vn * n[1])


def _fly(p, v, dt):
    return (p[0] + v[0] * dt, p[1] + v[1] * dt + 0.5 * G * dt * dt), (v[0], v[1] + G * dt)


def _ok_target(q, v, dt):
    """Landet die Kugel im Feld und fliegt dabei nicht oben aus dem Bild?"""
    x0, y0, x1, y1 = BOX
    if not (x0 <= q[0] <= x1 and y0 <= q[1] <= y1):
        return False
    if v[1] < 0:                                         # steigt: der Scheitelpunkt darf nicht oben aus dem Bild (über den Titel) fliegen
        p_y = q[1] - v[1] * dt - 0.5 * G * dt * dt
        if p_y - v[1] ** 2 / (2 * G) < 380:
            return False
    return True


PANE_GAP = 12                    # so viel Luft bleibt zwischen zwei Scheiben, die gleichzeitig dastehen (px)


def _pane_rect(p, n, grow=0.0):
    """Ecken der Scheibe, an der die Kugel im Punkt p mit der Normale n abprallt (grow = Rand ringsum)."""
    cx, cy = p[0] - n[0] * (BALL_R + PANE_W / 2), p[1] - n[1] * (BALL_R + PANE_W / 2)
    ux, uy = -n[1], n[0]
    hl, hw = PANE_LEN / 2 + grow, PANE_W / 2 + grow
    return [(cx + sx * ux + sy * n[0], cy + sx * uy + sy * n[1]) for sx, sy in ((-hl, -hw), (hl, -hw), (hl, hw), (-hl, hw))]


def _rects_touch(a, b):
    """Überdecken sich zwei Rechtecke (Trennachsen-Test)?"""
    for poly in (a, b):
        for k in range(4):
            ax, ay = poly[k][1] - poly[(k + 1) % 4][1], poly[(k + 1) % 4][0] - poly[k][0]
            pa = [x * ax + y * ay for x, y in a]
            pb = [x * ax + y * ay for x, y in b]
            if max(pa) < min(pb) or max(pb) < min(pa):
                return False
    return True


def _candidates(p, v_in, t, dn, rnd, recent, trail=(), strict=False, t_show=None, standing=()):
    """Mögliche echte Abpraller an diesem Punkt, beste zuerst (erst normale, dann federnde Scheiben).
    standing = Ecken der Scheiben, die gleichzeitig mit dieser dastehen: die neue darf keine davon berühren."""
    x0, y0, x1, y1 = BOX
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    sp_in = math.hypot(*v_in)
    a_in = math.atan2(-v_in[1], -v_in[0])                # Richtung, aus der die Kugel kommt
    out = []
    for e_rng in (RESTITUTION, SPRINGY):
        cands = []
        for _ in range(200):
            ang = a_in + rnd.uniform(-1.45, 1.45)        # Normale zeigt zur Kugel hin (sonst kein Aufprall)
            n = (math.cos(ang), math.sin(ang))
            if n[0] * v_in[0] + n[1] * v_in[1] > -GRAZE * sp_in:
                continue
            vo = _reflect(v_in, n, rnd.uniform(*e_rng))
            q, v_next = _fly(p, vo, dn)
            if not _ok_target(q, vo, dn):
                continue
            if standing:                                 # zwei Scheiben lagen über Eck aufeinander (Video 165, gleich im ersten Bild)
                mine = _pane_rect(p, n, PANE_GAP)
                if any(_rects_touch(mine, r) for r in standing):
                    continue
            sp = math.hypot(*vo)
            sc = max(0, sp - 2700) * 3 + max(0, 500 - sp) * 2
            sc += (abs(q[0] - cx) / (x1 - x0) + abs(q[1] - cy) / (y1 - y0)) * 120          # lieber in der Mitte bleiben
            sc += max(0, 130 - math.hypot(q[0] - p[0], q[1] - p[1])) * 30                 # nächste Scheibe nicht direkt daneben
            sc += sum(max(0, 170 - math.hypot(q[0] - r[0], q[1] - r[1])) * 8 for rt, r in recent if t - rt < SHOW_AHEAD + 0.4)
            t_show = t + dn - SHOW_AHEAD if t_show is None else t_show   # ab da steht die Scheibe für den nächsten Ton schon da:
            clash = sum(1 for tt, bx, by in trail if tt >= t_show and math.hypot(q[0] - bx, q[1] - by) < CLEAR)
            k_s = 1                                      # … die Kugel darf vorher nicht durch ihren Platz fliegen (auch nicht auf dem Weg dorthin)
            while k_s * 0.012 < dn - 0.18:
                fx, fy = p[0] + vo[0] * k_s * 0.012, p[1] + vo[1] * k_s * 0.012 + 0.5 * G * (k_s * 0.012) ** 2
                clash += math.hypot(q[0] - fx, q[1] - fy) < CLEAR
                k_s += 1
            if clash and strict:
                continue                                 # streng: lieber einen Ton zurückgehen und dort anders abprallen
            sc += clash * 4000
            cands.append((sc, n, vo, q, v_next))
        out += sorted(cands, key=lambda c: c[0])[:14]
    return out


MAX_AIR = 1.35                   # länger kann die Kugel nicht fliegen, ohne oben aus dem Bild zu steigen (Schwerkraft)


def with_ghosts(hits):
    """Lange Pausen (Haltetöne, Pausen, ruhige Stellen im Lied): stille Zwischen-Aufpralle einfügen (Tonhöhe None = kein Ton),
    damit die Kugel nie physikalisch unmöglich lange in der Luft hängt."""
    out = []
    for k, (t, m) in enumerate(hits):
        out.append((t, m))
        if k + 1 < len(hits):
            gap = hits[k + 1][0] - t
            n = int(gap / MAX_AIR)
            for j in range(1, n + 1):
                out.append((round(t + gap * j / (n + 1), 4), None))
    return out


def path(hits, seed=0):
    """Flugweg mit echter Physik: zwischen zwei Tönen eine Wurfparabel, an jedem Ton ein echter Abprall an einer Scheibe
    (Einfallswinkel = Ausfallswinkel, etwas Schwungverlust; nur wo ein langer Ton es verlangt, federt die Scheibe stärker).
    Gesucht wird je Ton die Neigung der Scheibe, mit der die Kugel genau zum nächsten Ton wieder auf eine Scheibe trifft – im Bild,
    nicht zu schnell, nicht auf anderen Scheiben. Findet sich keine, geht die Suche einen Ton zurück und probiert dort eine andere.
    Gibt [{t, p, v_in, v_out, n}] und die Startposition zurück."""
    rnd = random.Random(seed)
    x0, y0, x1, y1 = BOX
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    start = (cx + rnd.uniform(-120, 120), y0 - 60.0)
    p0, v0 = _fly(start, (0.0, 0.0), min(FALL, hits[0][0]))
    N = len(hits)
    stack = []                                           # je Ton: {p, v_in, cands, idx}
    steps = 0
    i = 0
    while i < N:
        steps += 1
        if i == len(stack):
            p, v_in = (p0, v0) if i == 0 else (stack[i - 1]["cands"][stack[i - 1]["idx"]][3], stack[i - 1]["cands"][stack[i - 1]["idx"]][4])
            dn = max(0.05, (hits[i + 1][0] - hits[i][0]) if i + 1 < N else 0.7)
            recent = [(hits[k][0], stack[k]["p"]) for k in range(max(0, i - 14), i)]
            trail = []                                   # bisheriger Flugweg der letzten SHOW_AHEAD Sekunden (Zeit, x, y)
            times = [h[0] for h in hits]
            t_lo = appear_at(times, i + 1) if i + 1 < N else hits[i][0]
            for k in range(i - 1, -1, -1):
                if hits[k + 1][0] < t_lo:
                    break
                fk = stack[k]
                vo_k = fk["cands"][fk["idx"]][2]
                n_k = max(1, int(fk["dn"] / 0.012))
                trail += [(hits[k][0] + fk["dn"] * j / n_k, fk["p"][0] + vo_k[0] * fk["dn"] * j / n_k,
                           fk["p"][1] + vo_k[1] * fk["dn"] * j / n_k + 0.5 * G * (fk["dn"] * j / n_k) ** 2) for j in range(n_k)]
            if hits[0][0] >= t_lo:                       # der Fall von der Startklappe
                f0 = min(FALL, hits[0][0])
                trail += [(hits[0][0] - f0 + f0 * j / 10, start[0], start[1] + 0.5 * G * (f0 * j / 10) ** 2) for j in range(10)]
            t_me = appear_at(times, i)                   # ab da steht die Scheibe dieses Tons da – zusammen mit allen früheren, die dann noch nicht zersprungen sind
            standing = [_pane_rect(stack[k]["p"], stack[k]["cands"][stack[k]["idx"]][1]) for k in range(i) if hits[k][0] > t_me] if steps < STRICT_STEPS else []
            stack.append({"p": p, "v_in": v_in, "dn": dn, "idx": 0,
                          "cands": _candidates(p, v_in, hits[i][0], dn, rnd, recent, trail, steps < STRICT_STEPS, t_lo, standing)})
        fr = stack[i]
        if fr["idx"] < len(fr["cands"]) or i == 0 or steps > 6000:
            if fr["idx"] >= len(fr["cands"]):            # Notfall (praktisch nie): Ziel in der Mitte, Abprall nur ungefähr
                p, v_in, dn = fr["p"], fr["v_in"], fr["dn"]
                q = (cx + rnd.uniform(-150, 150), cy + rnd.uniform(-150, 150))
                vo = ((q[0] - p[0]) / dn, (q[1] - p[1] - 0.5 * G * dn * dn) / dn)
                dv = (vo[0] - v_in[0], vo[1] - v_in[1])
                ln = math.hypot(*dv) or 1.0
                fr["cands"].append((0, (dv[0] / ln, dv[1] / ln), vo, q, (vo[0], vo[1] + G * dn)))
                fr["idx"] = len(fr["cands"]) - 1
            i += 1
            continue
        stack.pop()                                      # keine Möglichkeit mehr: einen Ton zurück, dort die nächste Neigung probieren
        i -= 1
        stack[i]["idx"] += 1
        del stack[i + 1:]
    out = []
    for k, fr in enumerate(stack):
        _sc, n, vo, _q, _vn = fr["cands"][fr["idx"]]
        out.append({"t": hits[k][0], "p": fr["p"], "v_in": fr["v_in"], "v_out": vo, "n": n})
    return out, start


def _can_continue(p, v_in, hits, j, rnd):
    dn = max(0.05, (hits[j + 1][0] - hits[j][0]) if j + 1 < len(hits) else 0.7)
    sp_in = math.hypot(*v_in)
    a_in = math.atan2(-v_in[1], -v_in[0])
    for k in range(80):
        ang = a_in + rnd.uniform(-1.35, 1.35)
        n = (math.cos(ang), math.sin(ang))
        if n[0] * v_in[0] + n[1] * v_in[1] > -GRAZE * sp_in:
            continue
        vo = _reflect(v_in, n, rnd.uniform(*(RESTITUTION if k < 50 else SPRINGY)))
        q, _v = _fly(p, vo, dn)
        if _ok_target(q, vo, dn):
            return True
    return False


def appear_times(segs, start):
    """Wann darf jede Scheibe erscheinen? Spätestens SHOW_AHEAD vor ihrem Ton – aber erst, wenn die Kugel nicht mehr durch ihren
    Platz fliegt (sonst flöge sie sichtbar durch eine Scheibe hindurch)."""
    out = []
    reach = BALL_R + PANE_W / 2 + 6
    for j, s in enumerate(segs):
        nx, ny = s["n"]
        c = (s["p"][0] - nx * (BALL_R + PANE_W / 2), s["p"][1] - ny * (BALL_R + PANE_W / 2))
        ux, uy = -ny, nx                                  # Richtung entlang der Scheibe
        appear = appear_at([g["t"] for g in segs], j)
        tt = appear
        while tt < s["t"] - 0.04:
            bx, by = ball_at(tt, segs, start)
            dx, dy = bx - c[0], by - c[1]
            along = max(-PANE_LEN / 2, min(PANE_LEN / 2, dx * ux + dy * uy))
            if math.hypot(dx - along * ux, dy - along * uy) < reach:
                appear = tt + 0.05
            tt += 1 / 120
        out.append(min(appear, s["t"] - 0.08))
    return out


def ball_at(t, segs, start):
    """Position der Kugel zur Zeit t."""
    if not segs or t <= segs[0]["t"]:                    # liegt auf der Startklappe, bis sie aufgeht; dann freier Fall
        td = (segs[0]["t"] - min(FALL, segs[0]["t"])) if segs else 0.0
        return (start[0], start[1] + 0.5 * G * max(0.0, t - td) ** 2)
    prev = segs[0]
    for s in segs[1:]:
        if t < s["t"]:
            break
        prev = s
    dt = t - prev["t"]
    return (prev["p"][0] + prev["v_out"][0] * dt, prev["p"][1] + prev["v_out"][1] * dt + 0.5 * G * dt * dt)


# ------------------------------------------------------------------ Ton

def _freq(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def audio(hits, total, out: Path, seed=0):
    """Glockenspiel-Ton je Aufprall + leises Glasklirren + etwas Raumhall, als WAV."""
    rng = np.random.default_rng(seed)
    n = int((total + 1.5) * SR)
    y = np.zeros(n, dtype=np.float64)
    L = int(1.6 * SR)
    tt = np.arange(L) / SR
    for t, m in hits:
        if m is None:                                    # stiller Zwischen-Aufprall: kein Ton
            continue
        f = _freq(m)
        note = (np.sin(2 * np.pi * f * tt) * np.exp(-tt * 3.2) * 0.62
                + np.sin(2 * np.pi * 2 * f * tt) * np.exp(-tt * 6.0) * 0.22
                + np.sin(2 * np.pi * 3.01 * f * tt) * np.exp(-tt * 9.0) * 0.12
                + np.sin(2 * np.pi * 5.4 * f * tt) * np.exp(-tt * 22.0) * 0.06)
        att = np.minimum(1.0, tt / 0.003)
        note *= att
        k = int(0.07 * SR)                               # Glas-Klirren: kurzes, helles Rauschen
        crack = rng.standard_normal(k) * np.exp(-np.arange(k) / SR * 70)
        crack = np.diff(np.concatenate([[0.0], crack])) * 0.18
        i = int(t * SR)
        seg = note[: max(0, min(L, n - i))]
        y[i:i + len(seg)] += seg
        y[i:i + min(k, n - i)] += crack[: max(0, min(k, n - i))]
    ir_n = int(1.1 * SR)                                 # einfacher Raumhall
    ir = rng.standard_normal(ir_n) * np.exp(-np.arange(ir_n) / SR * 4.5) * 0.02
    ir[0] = 1.0
    nfft = 1 << int(math.ceil(math.log2(n + ir_n)))
    wet = np.fft.irfft(np.fft.rfft(y, nfft) * np.fft.rfft(ir, nfft), nfft)[:n]
    y = wet / max(1e-6, np.max(np.abs(wet))) * 0.85
    fade = int(0.8 * SR)
    y[-fade:] *= np.linspace(1, 0, fade)
    st = np.stack([y, y], axis=1)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((st * 32767).astype("<i2").tobytes())


# ------------------------------------------------------------------ Bild

def _hue_col(h, s=0.62, v=0.95):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return int(r * 255), int(g * 255), int(b * 255)


def _background(seed):
    rnd = random.Random(seed)
    bg = Image.new("RGB", (W, H), (12, 12, 22))
    d = ImageDraw.Draw(bg)
    for y in range(0, H, 6):                             # dunkler Verlauf
        k = y / H
        d.rectangle((0, y, W, y + 6), fill=(int(14 + 10 * k), int(13 + 6 * k), int(26 + 16 * k)))
    for _ in range(90):                                  # feine Sterne
        x, y = rnd.uniform(0, W), rnd.uniform(0, H)
        r = rnd.uniform(0.8, 2.2)
        c = rnd.randint(60, 120)
        d.ellipse((x - r, y - r, x + r, y + r), fill=(c, c, c + 20))
    return bg


def _font(size):
    """Poppins wie im Rest der Videos; fehlt sie, eine fette Systemschrift – nie die winzige Pixel-Ersatzschrift."""
    from PIL import ImageFont
    from .overlays import font
    f = font(size)
    if isinstance(f, ImageFont.FreeTypeFont) and isinstance(getattr(f, "path", None), str):   # echte Schriftdatei, nicht der Ersatz
        return f
    for p in ("/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"):
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size=size)


def _text_center(d, y, text, size, fill):
    """Text mittig – wird kleiner und notfalls zweizeilig, damit er nie über den Bildrand läuft."""
    max_w = W - 90
    lines = [text]
    f = _font(size)
    while d.textlength(text, font=f) > max_w and size > 44:
        size -= 4
        f = _font(size)
    if d.textlength(text, font=f) > max_w:              # immer noch zu breit: an einem Leerzeichen nahe der Mitte umbrechen
        words = text.split()
        best = min(range(1, len(words)), key=lambda k: abs(len(" ".join(words[:k])) - len(" ".join(words[k:]))), default=1)
        lines = [" ".join(words[:best]), " ".join(words[best:])]
    for k, ln in enumerate(lines):
        w = d.textlength(ln, font=f)
        yy = y + k * int(size * 1.15) - (int(size * 0.55) if len(lines) > 1 else 0)
        d.text(((W - w) / 2 + 3, yy + 3), ln, font=f, fill=(0, 0, 0))
        d.text(((W - w) / 2, yy), ln, font=f, fill=fill)
    return len(lines)


def _launcher(d, start, t, td):
    """Startklappe: kleine Glas-Halterung, auf der die Kugel am Anfang liegt. Bei td klappt der Boden nach unten auf,
    danach blendet die Halterung aus (die Kugel soll später nicht durch sie hindurchfliegen)."""
    fade = 1.0 if t < td + 0.35 else max(0.0, 1 - (t - td - 0.35) / 0.5)
    if fade <= 0:
        return
    a = int(255 * fade)
    sx, sy = start
    floor = sy + BALL_R + 4
    col = (200, 210, 235)
    for side in (-1, 1):                                 # Seitenwände
        x = sx + side * (BALL_R + 12)
        d.rounded_rectangle((x - 5, sy - BALL_R - 26, x + 5, floor + 6), 4, fill=col + (int(a * 0.85),))
    open_ = 0.0 if t < td else min(1.0, (t - td) / 0.12)   # Boden klappt nach unten weg (Scharnier links)
    ang = math.radians(90 * open_)
    hx, hy = sx - BALL_R - 12, floor
    ln = 2 * (BALL_R + 12)
    ex, ey = hx + ln * math.cos(ang), hy + ln * math.sin(ang)
    d.line((hx, hy, ex, ey), fill=col + (a,), width=9)
    d.ellipse((hx - 6, hy - 6, hx + 6, hy + 6), fill=(255, 255, 255, a))
    if t < td:                                           # kurz vor dem Öffnen: kleines Aufleuchten als Ankündigung
        glow = max(0.0, 1 - (td - t) / 0.4)
        if glow > 0:
            r = BALL_R + 10 + 14 * glow
            d.ellipse((sx - r, sy - r, sx + r, sy + r), outline=(255, 255, 255, int(120 * glow)), width=3)


TITLE_TOP = "Erkennst du das Lied?"
OUTRO = ("Welches Lied war das?", "Schreib es in die Kommentare")   # steht ab dem letzten Ton oben (nur beim Rate-Video)
GHOST_COL = (205, 210, 230)      # stille Zwischen-Aufpralle: blasse Bande statt bunter Glasscheibe
END_HOLD = 0.8                   # so lange läuft das Video weiter, nachdem die Kugel nach dem letzten Ton aus dem Bild ist (s)
END_FADE = 0.8                   # Ton blendet am gekürzten Schluss aus (s)


def end_time(segs, start):
    """Schluss des Videos: END_HOLD nachdem die Kugel nach dem letzten Ton das Bild verlassen hat (vorher lief der Beat noch
    bis zu vier Sekunden über einem leeren Bild weiter)."""
    if not segs:
        return 0.0
    t = segs[-1]["t"]
    while t < segs[-1]["t"] + 3.0:
        bx, by = ball_at(t, segs, start)
        if by > H + BALL_R or bx < -BALL_R or bx > W + BALL_R:
            break
        t += 1 / FPS
    return t + END_HOLD


def render(song, out: Path, seed=0, title_top=TITLE_TOP, reveal=False, work: Path = None):
    """Ganzes Video rendern (Bild + Ton). Gibt (Dauer, Pfad zum Vorschaubild) zurück. work = Ordner für Zwischendateien."""
    work = Path(work) if work else out.parent
    if isinstance(song, dict) and song.get("remix"):     # Remix einer gemeinfreien Melodie: {"remix": Melodie, "style": Stil}
        from . import remix
        base = SONGS[song["remix"]]
        name, who = f"{base[0]} – {remix.STYLES[song['style']]['name']} Remix", base[1]
        wav = work / "bounce.wav"
        hits, total = remix.build(base, remix.KEYS[song["remix"]], song["style"], wav, seed=seed)
    elif isinstance(song, dict):                         # eigenes Lied: {"file", "name", "who"}
        name, who = song.get("name") or "?", song.get("who") or ""
        hits, total, wav = file_song(song["file"], work)
    else:
        name, who, _bpm, _seq_ = SONGS[song]
        hits, total = notes(song)
        wav = work / "bounce.wav"
        audio(hits, total, wav, seed)
    hits = with_ghosts(hits)
    segs, start = path(hits, seed)
    full = total
    total = min(total, end_time(segs, start))            # nach dem letzten Ton kein leeres Bild: Schluss, kurz nachdem die Kugel weg ist
    last_t = segs[-1]["t"] if segs else total
    outro = OUTRO if title_top == TITLE_TOP and not reveal else None
    rnd = random.Random(seed)
    hue0 = rnd.random()
    bg = _background(seed)
    panes = []
    appears = appear_times(segs, start)
    for i, s in enumerate(segs):
        nx, ny = s["n"]
        cx, cy = s["p"][0] - nx * (BALL_R + PANE_W / 2), s["p"][1] - ny * (BALL_R + PANE_W / 2)
        ang = math.atan2(ny, nx) + math.pi / 2           # Scheibe liegt quer zur Normale
        col = _hue_col(hue0 + 0.75 * i / max(1, len(segs)) + ((hits[i][1] or 0) % 12) * 0.004)
        shards = [(rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-260, 260), rnd.uniform(-420, -60), rnd.uniform(-9, 9), rnd.uniform(10, 26))
                  for _ in range(7)]
        panes.append({"t": s["t"], "c": (cx, cy), "a": ang, "col": col, "shards": shards, "v": s["v_out"], "show": s["t"] - appears[i],
                      "ghost": hits[i][1] is None})
    n_frames = int(total * FPS)
    ff = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-i", str(wav)]
                          + (["-af", f"afade=t=out:st={max(0.0, total - END_FADE):.3f}:d={END_FADE}"] if total < full - 0.05 else [])
                          + ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)],
                          stdin=subprocess.PIPE)
    trail = []
    thumb = work / "bounce_thumb.jpg"
    try:
        for fi in range(n_frames):
            t = fi / FPS
            fr = bg.copy()
            glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            gd = ImageDraw.Draw(glow)
            d = ImageDraw.Draw(fr, "RGBA")
            for pn in panes:
                dtp = pn["t"] - t
                cx, cy = pn["c"]
                ca, sa = math.cos(pn["a"]), math.sin(pn["a"])
                if 0 < dtp <= pn["show"]:                # Scheibe wartet (blendet ein – erst wenn die Kugel nicht mehr durchfliegt)
                    k = 1.0 if pn["t"] - pn["show"] <= 0.01 else min(1.0, (pn["show"] - dtp) / 0.35)   # ab Bild 1 schon da
                    hl = PANE_LEN / 2 * (0.6 + 0.4 * k)
                    pts = []
                    for sx, sy in ((-hl, -PANE_W / 2), (hl, -PANE_W / 2), (hl, PANE_W / 2), (-hl, PANE_W / 2)):
                        pts.append((cx + sx * ca - sy * sa, cy + sx * sa + sy * ca))
                    a = int(255 * k)
                    if pn["ghost"]:                      # stiller Zwischen-Aufprall: blasse Bande ohne Farbe und Lichtpunkte – kein Ton, kein Glas
                        d.polygon(pts, fill=GHOST_COL + (int(a * 0.16),), outline=GHOST_COL + (int(a * 0.5),), width=2)
                        continue
                    d.polygon(pts, fill=pn["col"] + (int(a * 0.55),), outline=pn["col"] + (a,), width=3)
                    for j in (-2, -1, 0, 1, 2):          # Glas-Lichtpunkte wie im Vorbild
                        px, py = cx + j * hl * 0.36 * ca, cy + j * hl * 0.36 * sa
                        d.ellipse((px - 2.5, py - 2.5, px + 2.5, py + 2.5), fill=(255, 255, 255, int(a * 0.8)))
                elif -0.9 < dtp <= 0:                    # zersprungen: Splitter fliegen und fallen
                    age = -dtp
                    if pn["ghost"]:                      # Bande zerspringt nicht: sie federt kurz nach und verblasst
                        if age < 0.3:
                            k = 1 - age / 0.3
                            off = 10 * math.sin(age * 40) * k
                            nxp, nyp = math.cos(pn["a"] - math.pi / 2), math.sin(pn["a"] - math.pi / 2)
                            pts = []
                            for sx, sy in ((-PANE_LEN / 2, -PANE_W / 2), (PANE_LEN / 2, -PANE_W / 2), (PANE_LEN / 2, PANE_W / 2), (-PANE_LEN / 2, PANE_W / 2)):
                                pts.append((cx + sx * ca - sy * sa - nxp * off, cy + sx * sa + sy * ca - nyp * off))
                            d.polygon(pts, fill=GHOST_COL + (int(40 * k),), outline=GHOST_COL + (int(128 * k),), width=2)
                        continue
                    if age < 0.18:                       # Lichtblitz am Aufprall
                        r = 30 + 260 * age
                        gd.ellipse((cx - r, cy - r, cx + r, cy + r), outline=pn["col"] + (int(255 * (1 - age / 0.18)),), width=6)
                    for (ox, oy, vx, vy, rot, sz) in pn["shards"]:
                        sx_ = cx + ox * PANE_LEN * 0.4 + (vx + pn["v"][0] * 0.12) * age
                        sy_ = cy + oy * 10 + (vy + pn["v"][1] * 0.12) * age + 0.5 * G * 0.55 * age * age
                        rr = sz * (1 - age / 0.9)
                        ang = rot * age
                        tri = [(sx_ + rr * math.cos(ang + q), sy_ + rr * math.sin(ang + q)) for q in (0, 2.3, 4.1)]
                        d.polygon(tri, fill=pn["col"] + (int(230 * (1 - age / 0.9)),))
            _launcher(d, start, t, segs[0]["t"] - min(FALL, segs[0]["t"]) if segs else 0.0)
            bx, by = ball_at(t, segs, start)
            trail.append((bx, by))
            trail = trail[-8:]
            for j, (tx, ty) in enumerate(trail[:-1]):    # kurze Leuchtspur
                r = BALL_R * (0.35 + 0.65 * j / len(trail))
                d.ellipse((tx - r, ty - r, tx + r, ty + r), fill=(255, 255, 255, int(40 + 90 * j / len(trail))))
            gd.ellipse((bx - BALL_R * 2.2, by - BALL_R * 2.2, bx + BALL_R * 2.2, by + BALL_R * 2.2), fill=(255, 255, 255, 50))
            fr = Image.alpha_composite(fr.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(10))).convert("RGB")
            d = ImageDraw.Draw(fr)
            d.ellipse((bx - BALL_R, by - BALL_R, bx + BALL_R, by + BALL_R), fill=(250, 250, 245))
            if reveal and t > total - 3.2:               # Auflösung am Ende
                n_l = _text_center(d, 180, name, 64, (255, 230, 120))
                _text_center(d, 262 + (40 if n_l > 1 else 0), who, 40, (220, 220, 230))
            elif outro and t >= last_t:                  # nach dem letzten Ton: Frage an die Zuschauer statt leerem Bild
                _text_center(d, 180, outro[0], 64, (255, 230, 120))
                _text_center(d, 262, outro[1], 40, (220, 220, 230))
            else:
                _text_center(d, 180, title_top, 64, (255, 255, 255))
                _text_center(d, 262, "Jede Scheibe ist ein Ton", 40, (200, 200, 215))
            if fi == int(min(total * 0.4, 8) * FPS):
                fr.save(thumb, quality=90)
            ff.stdin.write(fr.tobytes())
        ff.stdin.close()
        if ff.wait() != 0:
            raise RuntimeError("ffmpeg (Musik-Kugel) fehlgeschlagen")
    finally:
        if ff.poll() is None:
            ff.kill()
    log(f"Musik-Kugel: {name} – {len(hits)} Töne, {total:.0f} s")
    return total, thumb


def user_songs():
    """Eigene Lieder aus dem Release „songs“ (in der App hochgeladen): [{"asset", "name", "who"}]. Dateiname „Künstler - Titel.mp3“."""
    import json
    import re
    try:
        r = subprocess.run(["gh", "release", "view", "songs", "--json", "assets"], capture_output=True, text=True, timeout=60)
        assets = json.loads(r.stdout or "{}").get("assets") or [] if r.returncode == 0 else []
    except Exception:  # noqa: BLE001
        return []
    out = []
    for a in assets:
        nm = str(a.get("name") or "")
        if not re.search(r"\.(mp3|m4a|wav|ogg|aac|flac)$", nm, re.I):
            continue
        stem = re.sub(r"\.[^.]+$", "", nm).replace(".", " ").replace("_", " ").strip()
        who, _, title = stem.partition(" - ") if " - " in stem else ("", "", stem)
        out.append({"asset": nm, "name": (title or stem).strip(), "who": who.strip()})
    return out


def fetch_user_song(song, work):
    subprocess.run(["gh", "release", "download", "songs", "-p", song["asset"], "-D", str(work), "--clobber"], check=True, capture_output=True, timeout=300)
    return {**song, "file": str(Path(work) / song["asset"])}


CC_QUERIES = ["remix", "electronic remix", "edm", "trap beat", "phonk", "house", "dubstep", "future bass", "dance remix", "synthwave",
              "chill remix", "drum and bass"]


VOCAL_RE = r"vocal|voice|\bvox\b|sing|singer|sung|song ?writer|lyric|\brap\b|rapper|\bmc\b|spoken|choir|chant|acapella|a cappella|feat\.?|\bft\.|featuring|gesang|stimme"


def instrumental(it):
    """Nur Tracks, die ausdrücklich instrumental sind (Schlagwort) und nirgends Gesang, Rap oder Sprache erwähnen."""
    import re
    tags = [str((t or {}).get("name") or "").lower() for t in (it.get("tags") or []) if isinstance(t, dict)]
    text = " ".join([str(it.get("title") or ""), str(it.get("description") or "")] + tags).lower()
    if re.search(VOCAL_RE, text):
        return False
    return any("instrumental" in t for t in tags) or "instrumental" in str(it.get("title") or "").lower()


def cc_track(used, work):
    """Freier INSTRUMENTAL-Track von ccMixter oder Jamendo (über Openverse): nur CC0 oder CC BY – „nicht kommerziell“ (NC) und
    „keine Bearbeitung“ (ND) sind ausgeschlossen. CC BY verlangt Namensnennung: sie steht in credit und kommt in die Beschreibung."""
    import requests
    ua = {"User-Agent": "AutoShorts/1.0 (open source shorts generator)"}
    qs = CC_QUERIES[:]
    random.shuffle(qs)
    for q in qs[:5]:
        try:
            r = requests.get("https://api.openverse.org/v1/audio/", headers=ua, timeout=30,
                             params={"q": f"instrumental {q}", "license": "cc0,by", "category": "music", "source": "jamendo,ccmixter", "page_size": 20})
            if r.status_code != 200:
                log(f"Openverse „{q}“: HTTP {r.status_code}")
                continue
            res = r.json().get("results", [])
        except Exception as e:  # noqa: BLE001
            log(f"Openverse „{q}“: {str(e)[:100]}")
            continue
        random.shuffle(res)
        for it in res:
            lic = str(it.get("license") or "").lower()
            dur = (it.get("duration") or 0) / 1000
            aid = "cc:" + str(it.get("id"))
            if lic not in ("cc0", "by") or aid in used or not it.get("url") or not (50 <= dur <= 480) or (it.get("filesize") or 0) > 25_000_000:
                continue
            if not instrumental(it):                     # nur reine Melodie: kein Gesang, kein Rap, keine Sprache
                continue
            dest = Path(work) / ("cc_" + str(it["id"])[:8] + "." + (str(it.get("filetype") or "mp3").lower()[:4] or "mp3"))
            try:
                with requests.get(it["url"], headers=ua, timeout=90, stream=True) as d:
                    d.raise_for_status()
                    with open(dest, "wb") as f:
                        for chunk in d.iter_content(65536):
                            f.write(chunk)
            except Exception as e:  # noqa: BLE001
                log(f"Download {it.get('title')}: {str(e)[:100]}")
                continue
            title = str(it.get("title") or "Track").strip()[:80]
            creator = str(it.get("creator") or "unbekannt").strip()[:60]
            lic_txt = "CC0" if lic == "cc0" else f"CC BY {it.get('license_version') or ''}".strip()
            link = it.get("foreign_landing_url") or it.get("url")
            log(f"Freier Track: „{title}“ von {creator} ({lic_txt}, {it.get('source')})")
            return {"file": str(dest), "name": title, "who": creator, "asset": aid,
                    "credit": f"Musik: „{title}“ von {creator} – {lic_txt} – {link}", "license": lic_txt}
    raise RuntimeError("Kein passender freier Track gefunden")


def pick_song(used, rnd=None):
    """Melodie, die am längsten nicht dran war (rnd: Kanal-Zufall – jede Kopie der App spielt die Lieder in anderer Reihenfolge)."""
    order = list(SONGS)
    (rnd or random).shuffle(order)
    return sorted(order, key=lambda s: used.index(s) if s in used else -1)[0]


def meta(song):
    """Titel, Beschreibung, Hashtags fürs Hochladen. Der Name des Lieds steht weder im Video noch in der Beschreibung: geraten wird
    in den Kommentaren (bringt Kommentare und Wiederholungen)."""
    if isinstance(song, dict) and song.get("remix"):
        from . import remix
        style = remix.STYLES[song["style"]]["name"]
        name, who = f"{SONGS[song['remix']][0]} ({style} Remix)", SONGS[song["remix"]][1]
        title = random.choice([f"Bekanntes Lied als {style}-Remix – erkennst du es? 🎵", f"Dieses Lied kennt jeder – aber als {style} 🔥",
                               f"Jede Scheibe ein Ton: {style}-Remix eines Klassikers"])
        desc = (f"Ein Lied, das jeder kennt – als {style}-Remix, jede Glasscheibe ist ein Ton. Erkennst du es? 🎵\n"
                "Schreib in die Kommentare, welches Lied es ist – und welches als Nächstes einen Remix bekommen soll!")
        return title, desc, ["#musik", "#remix", f"#{style.lower().replace(' ', '').replace('-', '')}", "#satisfying", "#erkennstdudaslied", "#shorts"], name
    if isinstance(song, dict) and song.get("credit"):    # freier Track (ccMixter/Jamendo): Namensnennung ist Pflicht
        title = random.choice(["Diese Kugel spielt den ganzen Beat 🎧", "Jede Scheibe ein Beat – wie lange schaust du zu? 🎧",
                               "Kugel trifft jeden Beat 🔥", "Satisfying: Jede Scheibe ein Ton 🎶"])
        desc = ("Jede Glasscheibe ist ein Ton – die Kugel spielt den ganzen Track mit. 🎧\n"
                f"{song['credit']}\n"
                "Welche Musik soll die Kugel als Nächstes spielen? Schreib es in die Kommentare!")
        return title, desc, ["#musik", "#remix", "#beat", "#satisfying", "#oddlysatisfying", "#shorts"], song["name"]
    name, who = (song.get("name"), song.get("who") or "") if isinstance(song, dict) else SONGS[song][:2]
    titles = ["Erkennst du dieses Lied? 🎵", "Diese Kugel spielt ein Lied, das jeder kennt", "Jede Scheibe ein Ton – welches Lied ist das?",
              "Nach drei Tönen weißt du es 🎶"]
    title = random.choice(titles)
    desc = (f"Jede Glasscheibe ist ein Ton – erkennst du das Lied, bevor die Kugel fertig ist? 🎵\n"
            "Welches Lied ist es – und wie viele Töne hast du gebraucht? Schreib es in die Kommentare!")
    tags = ["#musik", "#melodie", "#satisfying", "#erkennstdudaslied", "#klassik", "#shorts"]
    return title, desc, tags, name
