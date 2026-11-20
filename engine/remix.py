"""Remixe für die Musik-Kugel: bekannte gemeinfreie Melodien als moderner Track (Phonk, Trap, EDM, Lo-Fi, Sped Up) –
komplett selbst erzeugt (Schlagzeug, 808-Bass, Akkorde, Lead), daher frei von fremden Rechten.

Die Melodie spielt das Lead-Instrument; jeder Melodie-Ton ist ein Aufprall der Kugel. Die Akkorde werden je Takt aus der
Melodie bestimmt (der Dreiklang der Tonart, der die Töne des Takts am besten abdeckt)."""
import math
import wave
from pathlib import Path

import numpy as np

SR = 44100
PEAK = 0.6                       # frühere Aussteuerung nach der Abtast-Spitze – seit 20.11.2026 gilt TRUE_PEAK (siehe unten)

# Tonart und Taktart je Melodie: (Grundton 0=C … 11=H, "dur"/"moll", Schläge pro Takt)
KEYS = {"fuer_elise": (9, "moll", 3), "ode_freude": (0, "dur", 4), "bergkoenig": (11, "moll", 4), "korobeiniki": (9, "moll", 4),
        "jingle_bells": (0, "dur", 4), "nachtmusik": (7, "dur", 4), "funkel": (0, "dur", 4), "wiegenlied": (0, "dur", 3),
        "greensleeves": (9, "moll", 3), "saints": (0, "dur", 4), "auld_lang_syne": (5, "dur", 4),
        "bella_ciao": (9, "moll", 4), "cucaracha": (5, "dur", 4)}

STYLES = {
    "phonk": {"name": "Phonk", "tempo": 1.18, "shift": 0, "lead": "cowbell", "drums": "phonk", "bass": "808", "pad": False},
    "trap": {"name": "Trap", "tempo": 1.0, "shift": 0, "lead": "pluck", "drums": "trap", "bass": "808", "pad": True},
    "edm": {"name": "EDM", "tempo": 1.12, "shift": 0, "lead": "saw", "drums": "house", "bass": "offbeat", "pad": True},
    "lofi": {"name": "Lo-Fi", "tempo": 0.86, "shift": 0, "lead": "keys", "drums": "lofi", "bass": "sub", "pad": True},
    # Glas: wie die erfolgreichen Kugel-Videos – hohe, kurz angeschlagene Melodie, leichter Bass, kein Schlagzeug, Klirren auf jedem Ton
    # (an einem Vorbild gemessen: Klangschwerpunkt ~1500–2000 Hz, gut die Hälfte Anschläge, ~20 % Bass, keine regelmäßige Kick)
    "glas": {"name": "Glas", "tempo": 1.0, "shift": 12, "lead": "glass", "drums": "none", "bass": "sub", "pad": False,
             "glass": 5.0, "lead_gain": 1.3, "bass_gain": 0.45},
    "pop": {"name": "Pop", "tempo": 1.08, "shift": 0, "lead": "pluck", "drums": "dance", "bass": "offbeat", "pad": True},
    "spedup": {"name": "Sped Up", "tempo": 1.28, "shift": 3, "lead": "bell", "drums": "pop", "bass": "sub", "pad": True},
}

DRUMS = {   # Schlagzeug je Takt (in Schlägen): kick, snare, hat (Abstand), open
    "phonk": {"kick": (0, 0.75, 2.5), "snare": (1, 3), "hat": 0.5, "roll": True},
    "trap": {"kick": (0, 2.25, 3.5), "snare": (2,), "hat": 0.25, "roll": True},
    "house": {"kick": (0, 1, 2, 3), "snare": (1, 3), "hat": None, "open": (0.5, 1.5, 2.5, 3.5)},
    "lofi": {"kick": (0, 1.75, 2.5), "snare": (1, 3), "hat": 0.5, "swing": 0.08},
    "pop": {"kick": (0, 2, 2.5), "snare": (1, 3), "hat": 0.5},
    "none": {"kick": (), "snare": (), "hat": None},                                   # Glas: nur Melodie, Bass und Klirren – kein Schlagzeug
    "dance": {"kick": (0, 1, 2, 3), "snare": (1, 3), "hat": 0.5, "open": (1.5, 3.5)},   # Radio-Pop: gerader Kick, Klatscher auf 2 und 4
}


TRUE_PEAK = 0.75                 # höchste Spitze zwischen den Abtastwerten (−2,5 dBTP); AAC legt bei harten Anschlägen bis zu 2,7 dB drauf
LOWPASS = (15000.0, 19000.0)     # über 15 kHz läuft der Mix weich aus: das Klirren ist zweifach differenziertes Rauschen mit der meisten
                                 # Energie an der halben Abtastrate – unhörbar, aber genau das erzeugt die Spitzen zwischen den Abtastwerten


def _lowpass(y, band=LOWPASS):
    """Höhen oberhalb von band[0] weich ausblenden (Kosinus-Flanke bis band[1])."""
    F = np.fft.rfft(y)
    fr = np.fft.rfftfreq(len(y), 1 / SR)
    k = np.clip((fr - band[0]) / (band[1] - band[0]), 0, 1)
    return np.fft.irfft(F * (0.5 + 0.5 * np.cos(np.pi * k)), len(y))


def true_peak(y, over=4):
    """Größter Ausschlag des Signals zwischen den Abtastwerten (vierfach überabgetastet)."""
    n = len(y)
    F = np.fft.rfft(y)
    G = np.zeros(n * over // 2 + 1, complex)
    G[:len(F)] = F
    return float(np.max(np.abs(np.fft.irfft(G, n * over)))) * over


def _f(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def _env(n, a=0.005, d=0.3, sustain=0.0, length=None):
    t = np.arange(n) / SR
    e = np.minimum(1.0, t / max(a, 1e-4)) * (sustain + (1 - sustain) * np.exp(-t / max(d, 1e-3)))
    if length is not None:                               # Note loslassen
        rel = np.clip((t - length) / 0.08, 0, 1)
        e *= 1 - rel
    return e


def _add(buf, t, sig, gain=1.0):
    i = int(t * SR)
    if i >= len(buf):
        return
    sig = sig[: len(buf) - i]
    buf[i:i + len(sig)] += sig * gain


# ---------------------------------------------------------------- Instrumente

def lead_note(kind, m, dur):
    f = _f(m)
    n = int((dur + 0.6) * SR)
    t = np.arange(n) / SR
    if kind == "cowbell":                                # Phonk-Kuhglocke: zwei harte, verstimmte Töne, kurzer Nachhall
        s = np.sign(np.sin(2 * np.pi * f * t)) * 0.5 + np.sign(np.sin(2 * np.pi * f * 1.48 * t)) * 0.35
        s = np.convolve(s, np.ones(6) / 6, mode="same") * _env(n, 0.002, 0.16)
    elif kind == "pluck":                                # gezupft: Obertöne klingen unterschiedlich schnell aus
        s = sum(np.sin(2 * np.pi * f * k * t) / k * np.exp(-t * (3 + 2.2 * k)) for k in range(1, 9))
        s *= _env(n, 0.002, 0.9)
    elif kind == "saw":                                  # EDM-Lead: zwei leicht verstimmte Sägezähne
        s = sum(np.sin(2 * np.pi * f * k * t * (1 + 0.004 * ((-1) ** k))) / k for k in range(1, 13)) * 0.6
        s *= _env(n, 0.01, 0.5, 0.65, dur)
    elif kind == "keys":                                 # Lo-Fi-E-Piano mit leichtem Beben
        s = (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2 * f * t) + 0.12 * np.sin(2 * np.pi * 3.5 * f * t) * np.exp(-t * 9))
        s *= (1 + 0.08 * np.sin(2 * np.pi * 5 * t)) * _env(n, 0.004, 0.8)
    elif kind == "glass":                                # Glas-Ton: hell, kurz angeschlagen, klingt in ~0,1 s ab (wie in den Kugel-Videos)
        s = (np.sin(2 * np.pi * f * t) * np.exp(-t * 11) * 0.6 + np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 18) * 0.25
             + np.sin(2 * np.pi * 4.2 * f * t) * np.exp(-t * 30) * 0.1 + np.sin(2 * np.pi * 0.5 * f * t) * np.exp(-t * 6) * 0.12) * _env(n, 0.002, 10)
    else:                                                # Glockenspiel
        s = (np.sin(2 * np.pi * f * t) * np.exp(-t * 3.2) * 0.62 + np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 6) * 0.22
             + np.sin(2 * np.pi * 3.01 * f * t) * np.exp(-t * 9) * 0.12) * _env(n, 0.003, 10)
    return s


def shatter(rng):
    """Glas zerspringt: kurzes, helles Rauschen plus ein paar klirrende Splitter-Töne."""
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    noise = np.diff(np.diff(np.concatenate([[0, 0], rng.standard_normal(n)])))    # nur Höhen
    s = noise * np.exp(-t * 40) * 0.18
    for _ in range(5):
        fr, t0 = rng.uniform(3000, 7500), rng.uniform(0, 0.06)
        s += np.sin(2 * np.pi * fr * np.clip(t - t0, 0, None)) * np.exp(-np.clip(t - t0, 0, None) * rng.uniform(18, 35)) * (t >= t0) * 0.07
    return s


def kick(drive=1.0):
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    ph = 2 * np.pi * np.cumsum(45 + 110 * np.exp(-t * 38)) / SR
    return np.tanh(np.sin(ph) * np.exp(-t * 7) * 1.6 * drive)


def snare(rng):
    n = int(0.25 * SR)
    t = np.arange(n) / SR
    noise = np.diff(np.concatenate([[0], rng.standard_normal(n)]))
    return noise * np.exp(-t * 16) * 0.55 + np.sin(2 * np.pi * 185 * t) * np.exp(-t * 22) * 0.5


def hat(rng, open_=False):
    n = int((0.18 if open_ else 0.05) * SR)
    t = np.arange(n) / SR
    noise = np.diff(np.diff(np.concatenate([[0, 0], rng.standard_normal(n)])))
    return noise * np.exp(-t * (14 if open_ else 70)) * 0.18


def bass_note(kind, m, dur):
    f = _f(m)
    n = int((dur + 0.3) * SR)
    t = np.arange(n) / SR
    if kind == "808":                                    # 808: tiefer Sinus, rutscht von oben in den Ton, angezerrt
        ph = 2 * np.pi * np.cumsum(f * (1 + 0.7 * np.exp(-t * 40))) / SR
        return np.tanh(np.sin(ph) * 1.8) * _env(n, 0.003, 0.9, 0.35, dur) * 0.75
    if kind == "offbeat":
        return sum(np.sin(2 * np.pi * f * k * t) / k for k in range(1, 6)) * _env(n, 0.004, 0.12, 0.0, dur) * 0.5
    return np.sin(2 * np.pi * f * t) * _env(n, 0.01, 0.6, 0.5, dur) * 0.7


def pad_chord(notes, dur):
    n = int((dur + 0.4) * SR)
    t = np.arange(n) / SR
    s = sum(sum(np.sin(2 * np.pi * _f(m) * k * t) / (k * k) for k in range(1, 5)) for m in notes)
    e = np.minimum(1.0, t / 0.18) * np.clip((dur + 0.3 - t) / 0.3, 0, 1)
    return s * e * 0.12


# ---------------------------------------------------------------- Harmonie

def _scale(tonic, mode):
    steps = (0, 2, 4, 5, 7, 9, 11) if mode == "dur" else (0, 2, 3, 5, 7, 8, 10)
    return [(tonic + s) % 12 for s in steps]


def _chords(tonic, mode):
    """Dreiklänge der Tonart (in Moll mit Dur-Dominante): [(Grundton pc, [pcs])]."""
    sc = _scale(tonic, mode)
    out = []
    for deg in (0, 3, 4, 5, 1, 2) if mode == "dur" else (0, 3, 4, 5, 2, 6):
        pcs = [sc[deg], sc[(deg + 2) % 7], sc[(deg + 4) % 7]]
        if mode == "moll" and deg == 4:
            pcs[1] = (pcs[1] + 1) % 12                   # harmonisches Moll: Dur-Dominante
        out.append((sc[deg], pcs))
    return out


def harmonize(events, tonic, mode, bar):
    """Je Takt den Akkord, der die Melodietöne (nach Dauer gewichtet) am besten trifft; erster und letzter Takt auf der Tonika."""
    chords = _chords(tonic, mode)
    total = max(b + d for b, _m, d in events)
    n_bars = int(math.ceil(total / bar))
    out = []
    for k in range(n_bars):
        w = {}
        for b, m, d in events:
            if m is not None and k * bar <= b < (k + 1) * bar:
                w[m % 12] = w.get(m % 12, 0) + d * (1.4 if abs(b - k * bar) < 1e-6 else 1.0)
        best, best_s = chords[0], -1e9
        for i, (root, pcs) in enumerate(chords):
            s = sum(v if pc in pcs else -0.4 * v for pc, v in w.items()) - 0.05 * i
            if k in (0, n_bars - 1) and i == 0:
                s += 0.6
            if s > best_s:
                best, best_s = (root, pcs), s
        out.append(best)
    return out


# ---------------------------------------------------------------- Zusammenbau

def build(song_seq, key, style_key, out: Path, lead_in_beats=None, seed=0):
    """Track rendern. song_seq: [(midi|None, Dauer in Schlägen)], bpm im Eintrag. Gibt ([(Zeit, midi)], Gesamtdauer) zurück."""
    name, who, bpm, seq = song_seq
    tonic, mode, bar = key
    st = STYLES[style_key]
    beat = 60.0 / (bpm * st["tempo"])
    shift = st["shift"]
    rng = np.random.default_rng(seed)
    lead_in = lead_in_beats if lead_in_beats is not None else bar     # ein Takt Beat vor der Melodie (die Kugel fällt)
    events, b = [], 0.0
    for m, d in seq:
        events.append((b, None if m is None else m + shift, d))
        b += d
    melody_beats = b
    rounds = 2 if melody_beats * beat < 20 else 1
    if rounds == 2:                                      # kurze Melodie: zweimal, mit einem Takt Beat dazwischen
        start2 = math.ceil(melody_beats / bar) * bar + bar
        events += [(b0 + start2, m, d) for b0, m, d in events]
    total_beats = lead_in + max(b0 + d for b0, _m, d in events) + bar
    total_beats = math.ceil(total_beats / bar) * bar
    total = total_beats * beat + 1.2
    buf = np.zeros(int(total * SR) + SR)
    hits = []
    for b0, m, d in events:                              # Melodie
        if m is None:
            continue
        t = (lead_in + b0) * beat
        _add(buf, t, lead_note(st["lead"], m, d * beat), 0.55 * st.get("lead_gain", 1.0))
        hits.append((round(t, 4), m))
    if st.get("glass"):                                  # jeder Melodieton zerbricht eine Scheibe: hörbares Klirren genau auf dem Ton
        for t_h, _m in hits:
            _add(buf, t_h, shatter(rng), float(st.get("glass") or 0.8))
    prog = harmonize([(b0, m, d) for b0, m, d in events], (tonic + shift) % 12, mode, bar)
    for k in range(int((total_beats - lead_in) / bar)):  # Akkorde und Bass je Takt
        root, pcs = prog[min(k, len(prog) - 1)]
        t = (lead_in + k * bar) * beat
        if st["pad"]:
            notes = sorted(55 + (pc - 55) % 12 for pc in pcs)   # Akkord zwischen G3 und F#4
            _add(buf, t, pad_chord(notes, bar * beat), st.get("pad_gain", 1.0))
        bass_m = 28 + (root - 4) % 12                    # Bass zwischen E1 und D#2
        if st["bass"] == "offbeat":
            for j in range(bar):
                _add(buf, t + (j + 0.5) * beat, bass_note("offbeat", bass_m + 12, 0.4 * beat), 0.9)
        else:
            _add(buf, t, bass_note(st["bass"], bass_m + (12 if st["bass"] == "sub" else 0), bar * beat * 0.95), st.get("bass_gain", 1.0))
    dr = DRUMS[st["drums"]]
    kk, sn = kick(1.3 if st["drums"] in ("phonk", "trap") else 1.0), snare(rng)
    first_drop = lead_in * beat
    for k in range(int(total_beats / bar)):              # Schlagzeug: im ersten Takt nur Hi-Hats, dann voller Beat
        t_bar = k * bar * beat
        intro = t_bar < first_drop - 1e-6
        for p in dr["kick"]:
            if p < bar and not intro:
                _add(buf, t_bar + p * beat, kk, 0.95)
        for p in dr["snare"]:
            if p < bar and not intro:
                _add(buf, t_bar + p * beat, sn, 0.55)
        if dr.get("hat"):
            steps = int(round(bar / dr["hat"]))
            for j in range(steps):
                sw = dr.get("swing", 0) * beat if j % 2 else 0
                _add(buf, t_bar + j * dr["hat"] * beat + sw, hat(rng), 0.8)
            if dr.get("roll") and k % 2 == 1 and not intro:   # Hi-Hat-Wirbel am Taktende (Trap/Phonk)
                for j in range(6):
                    _add(buf, t_bar + (bar - 0.5) * beat + j * beat / 12, hat(rng), 0.6)
        for p in dr.get("open", ()):
            if p < bar and not intro:
                _add(buf, t_bar + p * beat, hat(rng, True), 0.7)
    if style_key == "lofi":                              # Plattenknistern
        buf += (rng.random(len(buf)) > 0.9993) * rng.standard_normal(len(buf)) * 0.08
    if style_key == "edm":                               # Pumpen: alles außer Kick duckt kurz auf jedem Schlag
        tt = np.arange(len(buf)) / SR
        buf *= 1 - 0.35 * np.exp(-((tt - first_drop) % beat) / 0.11) * (tt > first_drop)
    y = _lowpass(np.tanh(buf * 1.15))
    y = y / max(1e-6, true_peak(y)) * TRUE_PEAK          # ausgesteuert wird nach der Spitze zwischen den Abtastwerten (Glas-Klirren lag bei
                                                         # 0,6 Abtast-Spitze auf +4,4 dBTP, im fertigen Video waren Abtastwerte abgeschnitten)
    fade = int(0.9 * SR)
    end = int(total * SR)
    y = y[:end]
    y[-fade:] *= np.linspace(1, 0, fade)
    st2 = np.stack([y, y], axis=1)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((st2 * 32767).astype("<i2").tobytes())
    return hits, total
