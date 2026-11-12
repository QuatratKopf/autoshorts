"""KI-Anbieter für Text, Stimme und Bilder.

Kostenlos:  Text = Gemini (Gratis-Kontingent) → Pollinations (ohne Schlüssel)
            Stimme = Microsoft Edge Neural Voices (edge-tts)
            Bilder = Cloudflare Workers AI (FLUX schnell, Gratis-Kontingent) → Pollinations (ohne Schlüssel)
Premium:    OpenAI (Text, Stimme, Bilder), ElevenLabs (Stimme)

Fällt der gewählte Anbieter aus, wird automatisch der nächste kostenlose versucht.
"""
import asyncio
import base64
import io
import json
import os
import re
import subprocess
import time
import urllib.parse

import requests
from PIL import Image

from .state import cfg, log, secret

TIMEOUT = 180
W, H = 1080, 1920


_T0 = time.time()
WAIT_BUDGET = 14 * 60          # so lange darf ein Lauf insgesamt auf gestörte Text-KIs warten (GitHub bricht nach 30 Minuten ab)


def _may_wait():
    return time.time() - _T0 < WAIT_BUDGET


class ProviderError(Exception):
    pass


def _check(r: requests.Response, who: str):
    if r.status_code >= 400:
        raise ProviderError(f"{who} HTTP {r.status_code}: {r.text[:300]}")


# ---------------------------------------------------------------- Text

def _parse_json(txt: str) -> dict:
    txt = txt.strip()
    txt = re.sub(r"^```(?:json)?|```$", "", txt, flags=re.M).strip()
    a, b = txt.find("{"), txt.rfind("}")
    if a < 0 or b < 0:
        raise ProviderError("Antwort enthält kein JSON")
    try:
        js = json.loads(txt)
        if isinstance(js, list) and js and isinstance(js[0], dict):   # manche Modelle packen das Objekt in eine Liste
            return js[0]
        if isinstance(js, dict):
            return js
    except ValueError:
        pass
    try:
        js = json.loads(txt[a:b + 1])
    except ValueError:
        js = _repair_json(txt[a:])
    if not isinstance(js, dict):
        raise ProviderError("Antwort ist kein JSON-Objekt")
    return js


def _repair_json(txt: str):
    """Rettet typische Fehler freier Modelle: Komma vor } oder ], Zeilenumbrüche in Zeichenketten und – am häufigsten –
    ungeschützte Anführungszeichen im Text (deutsch „Wort" mit geradem Schlusszeichen). Abgeschnittene Antworten werden NICHT
    ergänzt (sonst entstünde ein zu kurzes Drehbuch): dann kommt der ursprüngliche Fehler und der Anbieter wird neu gefragt."""
    t = re.sub(r",\s*([}\]])", r"\1", txt)
    try:
        return json.loads(t)
    except ValueError as e:
        first = e
    out, in_str, esc, n = [], False, False, len(t)
    for i, ch in enumerate(t):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                j = i + 1
                while j < n and t[j] in " \t\r\n":
                    j += 1
                if j < n and t[j] not in ",:}]":      # kein Ende der Zeichenkette, sondern ein Anführungszeichen im Text
                    out.append('\\"')
                    continue
                in_str = False
            elif ch == "\n":
                out.append("\\n")
                continue
        elif ch == '"':
            in_str = True
        out.append(ch)
    try:
        return json.loads(re.sub(r",\s*([}\]])", r"\1", "".join(out)))
    except ValueError:
        raise first


GEMINI_TEXT = ("gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-flash-lite-latest")


def _gemini(system, user, temperature):
    """Schnelle Flash-Modelle mit kurzer Denkphase; liefert eines kein gültiges JSON oder antwortet nicht, kommt das nächste.
    (Gemessen: gemini-3.5-flash ≈ 6 s, die „latest“-Modelle brauchen oft über 2 Minuten oder sind überlastet.)"""
    key = secret("GEMINI_API_KEY")
    if not key:
        raise ProviderError("kein GEMINI_API_KEY")
    chosen = cfg("gemini_model") or GEMINI_TEXT[0]
    if chosen in ("gemini-flash-latest", "gemini-pro-latest"):
        chosen = GEMINI_TEXT[0]
    models = [chosen] + [m for m in GEMINI_TEXT if m != chosen]
    gc = {"temperature": temperature, "responseMimeType": "application/json", "maxOutputTokens": 16384}
    body = {"systemInstruction": {"parts": [{"text": system}]}, "contents": [{"role": "user", "parts": [{"text": user}]}]}
    last, busy = None, 0
    waits = (0, 20, 45, 90)            # Überlastung (503) hält manchmal Minuten an: mehrere Runden mit wachsender Pause
    for rnd, wait in enumerate(waits):
        if rnd:
            if not busy or not _may_wait():   # kein Überlastungs-Fehler (z. B. Schlüssel ungültig) oder Zeit aufgebraucht
                break
            if rnd == 1:
                models += [m for m in _gemini_more(key) if m not in models][:2]
            log(f"Gemini ausgelastet – neuer Versuch in {wait} s (Runde {rnd + 1}/{len(waits)})")
            time.sleep(wait)
        busy = 0
        for m in models:
            for think in ({"thinkingLevel": "low"}, None):
                cfg_ = {**gc, "thinkingConfig": think} if think else gc
                try:
                    r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                                      headers={"x-goog-api-key": key}, json={**body, "generationConfig": cfg_}, timeout=70)
                except requests.RequestException as e:
                    last = f"{m}: {type(e).__name__}"
                    busy += 1
                    break
                if r.status_code == 400 and think:
                    continue                      # Modell kennt die Denk-Vorgabe nicht → ohne
                if r.status_code != 200:
                    last = f"{m}: HTTP {r.status_code}"
                    busy += r.status_code in (429, 500, 502, 503, 504)
                    break
                try:
                    parts = r.json()["candidates"][0]["content"]["parts"]
                    txt = "".join(p.get("text", "") for p in parts if not p.get("thought"))
                    _parse_json(txt)
                    return txt
                except Exception as e:  # noqa: BLE001
                    last = f"{m}: ungültige Antwort ({str(e)[:60]})"
                    busy += 1
                    break
            log(f"Gemini {last} – versuche Ersatzmodell")
    raise ProviderError(f"Gemini: {last}")


_MORE = None


def _gemini_more(key):
    """Weitere Flash-Textmodelle, die der Schlüssel gerade kennt (falls die Standard-Modelle überlastet sind)."""
    global _MORE
    if _MORE is None:
        _MORE = []
        try:
            r = requests.get("https://generativelanguage.googleapis.com/v1beta/models", headers={"x-goog-api-key": key},
                             params={"pageSize": 200}, timeout=20)
            for it in r.json().get("models", []) if r.status_code == 200 else []:
                n = str(it.get("name", "")).split("/")[-1]
                if ("flash" in n and "generateContent" in (it.get("supportedGenerationMethods") or [])
                        and not re.search(r"tts|image|audio|live|embed|vision|exp|thinking", n)):
                    _MORE.append(n)
            _MORE.sort(key=lambda n: ("lite" in n, "preview" in n, n), reverse=False)
        except Exception as e:  # noqa: BLE001
            log(f"Gemini-Modellliste: {e}")
    return _MORE


def _openai_text(system, user, temperature):
    key = secret("OPENAI_API_KEY")
    if not key:
        raise ProviderError("kein OPENAI_API_KEY")
    r = requests.post("https://api.openai.com/v1/chat/completions",
                      headers={"Authorization": f"Bearer {key}"},
                      json={"model": cfg("openai_text_model"), "temperature": temperature,
                            "response_format": {"type": "json_object"},
                            "messages": [{"role": "system", "content": system},
                                         {"role": "user", "content": user}]},
                      timeout=TIMEOUT)
    _check(r, "OpenAI")
    return r.json()["choices"][0]["message"]["content"]


_last_poll_text = 0.0


def _pollinations_text(system, user, temperature):
    global _last_poll_text
    wait = 31 - (time.time() - _last_poll_text)
    if wait > 0:
        time.sleep(wait)
    for attempt in range(3):
        _last_poll_text = time.time()
        try:
            r = requests.post("https://text.pollinations.ai/openai",
                              json={"messages": [{"role": "system", "content": system + "\nAntworte nur mit JSON."},
                                                 {"role": "user", "content": user}],
                                    "temperature": temperature, "max_tokens": 12000,
                                    **({"reasoning_effort": "low"} if attempt == 0 else {"model": "openai-fast"})},
                              timeout=120)
        except requests.RequestException as e:   # Zeitüberschreitung/Verbindung: kurz warten, neu versuchen
            if attempt == 2:
                raise ProviderError(f"Pollinations-Text nicht erreichbar ({type(e).__name__})") from e
            log("Pollinations antwortet nicht, neuer Versuch …")
            time.sleep(20)
            continue
        if r.status_code >= 500 and attempt < 2:
            time.sleep(20)
            continue
        if r.status_code == 400 and attempt < 2:          # z. B. Antwort-Limit beim Nachdenk-Modell: mit dem schnellen Modell noch einmal
            time.sleep(5)
            continue
        if r.status_code in (402, 429) and attempt < 2:
            time.sleep(int(r.headers.get("Retry-After", "35")) + 1)
            continue
        _check(r, "Pollinations-Text")
        return r.json()["choices"][0]["message"]["content"]
    raise ProviderError("Pollinations-Text: Limit erreicht")


TEXT_PROVIDERS = {"gemini": _gemini, "openai": _openai_text, "pollinations": _pollinations_text}


def chat_json(system: str, user: str, temperature: float = 0.9) -> tuple[dict, str]:
    """JSON von der Text-KI. Reihenfolge: gewählter Anbieter, dann die übrigen. Sind alle nur vorübergehend gestört
    (überlastet, Zeitüberschreitung, kaputtes JSON), wird nach zwei Minuten noch eine Runde versucht."""
    chosen = cfg("text_provider") or "gemini"
    order = [chosen] + [p for p in ("gemini", "pollinations") if p != chosen]
    errors = []
    for rnd in range(2):
        errors = []
        for p in order:
            for attempt in range(2 if p == "pollinations" else 1):   # freies Modell: kaputtes JSON → noch einmal fragen
                try:
                    return _parse_json(TEXT_PROVIDERS[p](system, user, temperature)), p
                except Exception as e:  # noqa: BLE001
                    err = f"{p}: {e}"
                    if attempt == 0 and p == "pollinations" and isinstance(e, ValueError):
                        log("Pollinations lieferte ungültiges JSON – frage noch einmal")
                        continue
                    errors.append(err)
                    break
            log(f"Text über {p} fehlgeschlagen, versuche nächsten Anbieter …")
        temporary = all(re.search(r"HTTP (429|5\d\d)|Timeout|ConnectionError|JSON|delimiter|Expecting|Unterminated|ungültige Antwort|nicht erreichbar|Limit", e)
                        for e in errors)
        if rnd == 0 and temporary and secret("GEMINI_API_KEY") and _may_wait():
            log("Alle Text-Anbieter gerade gestört – warte 2 Minuten und versuche es noch einmal")
            time.sleep(120)
            continue
        break
    hint = " Tipp: Gemini-Schlüssel in der App unter Einstellungen → Zugangsdaten speichern." \
        if not os.environ.get("GEMINI_API_KEY") else ""
    raise ProviderError("Kein Text-Anbieter erreichbar. " + " | ".join(errors) + hint)


# ---------------------------------------------------------------- Stimme
# Rückgabe: Liste von (wort, start_s, ende_s) für die Untertitel

def audio_duration(path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                          "default=nk=1:nw=1", str(path)], capture_output=True, text=True).stdout
    return float(out.strip() or 0)


def _even_words(text, dur):
    words = text.split()
    total = sum(len(w) + 1 for w in words) or 1
    t, out = 0.0, []
    for w in words:
        d = dur * (len(w) + 1) / total
        out.append((w, t, t + d))
        t += d
    return out


def _edge(text, out, cat):
    import edge_tts

    async def go():
        sp = float(cfg("voice_speed") or 1.0)
        kw = dict(rate=f"{round((sp - 1) * 100):+d}%" if abs(sp - 1) > 0.01 else "+0%", pitch=cat.get("voice_pitch") or "+0Hz")
        try:
            comm = edge_tts.Communicate(text, cat.get("voice") or "de-DE-ConradNeural", boundary="WordBoundary", **kw)
        except TypeError:  # ältere edge-tts-Version
            comm = edge_tts.Communicate(text, cat.get("voice") or "de-DE-ConradNeural", **kw)
        words = []
        with open(out, "wb") as f:
            async for ch in comm.stream():
                if ch["type"] == "audio":
                    f.write(ch["data"])
                elif ch["type"] == "WordBoundary":
                    s = ch["offset"] / 1e7
                    words.append((ch["text"], s, s + ch["duration"] / 1e7))
        return words

    words = asyncio.run(go())
    return words or _even_words(text, audio_duration(out))


def _whisper_words(path, text):
    key = secret("OPENAI_API_KEY")
    if key:
        try:
            with open(path, "rb") as f:
                r = requests.post("https://api.openai.com/v1/audio/transcriptions",
                                  headers={"Authorization": f"Bearer {key}"},
                                  files={"file": ("voice.mp3", f, "audio/mpeg")},
                                  data={"model": "whisper-1", "response_format": "verbose_json",
                                        "timestamp_granularities[]": "word", "language": "de"},
                                  timeout=TIMEOUT)
            _check(r, "Whisper")
            ws = r.json().get("words") or []
            if ws:
                return [(w["word"], w["start"], w["end"]) for w in ws]
        except Exception as e:  # noqa: BLE001
            log(f"Wort-Zeiten über Whisper fehlgeschlagen ({e}), verteile gleichmäßig")
    return _even_words(text, audio_duration(path))


def _openai_tts(text, out, cat):
    key = secret("OPENAI_API_KEY")
    if not key:
        raise ProviderError("kein OPENAI_API_KEY")
    r = requests.post("https://api.openai.com/v1/audio/speech",
                      headers={"Authorization": f"Bearer {key}"},
                      json={"model": cfg("openai_tts_model"), "voice": cfg("openai_voice"),
                            "input": text, "instructions": cat.get("voice_instructions") or "",
                            "response_format": "mp3"},
                      timeout=TIMEOUT)
    _check(r, "OpenAI-TTS")
    with open(out, "wb") as f:
        f.write(r.content)
    return _whisper_words(out, text)


def _elevenlabs(text, out, cat):
    key, voice = secret("ELEVENLABS_API_KEY"), cfg("elevenlabs_voice_id")
    if not key or not voice:
        raise ProviderError("ElevenLabs-Key oder Voice-ID fehlt")
    r = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps",
                      params={"output_format": "mp3_44100_128"}, headers={"xi-api-key": key},
                      json={"text": text, "model_id": "eleven_multilingual_v2"}, timeout=TIMEOUT)
    _check(r, "ElevenLabs")
    js = r.json()
    with open(out, "wb") as f:
        f.write(base64.b64decode(js["audio_base64"]))
    al = js.get("alignment") or {}
    chars, st, en = al.get("characters", []), al.get("character_start_times_seconds", []), al.get("character_end_times_seconds", [])
    words, cur, cs = [], "", None
    for ch, s, e in zip(chars, st, en):
        if ch.isspace():
            if cur:
                words.append((cur, cs, last))
            cur, cs = "", None
        else:
            if cs is None:
                cs = s
            cur += ch
            last = e
    if cur:
        words.append((cur, cs, last))
    return words or _even_words(text, audio_duration(out))


def _silences(path, noise="-34dB", dur=0.16):
    """Sprechpausen in der Tonspur: Liste (start, ende)."""
    p = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", f"silencedetect=noise={noise}:d={dur}",
                        "-f", "null", "-"], capture_output=True, text=True)
    st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", p.stderr)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", p.stderr)]
    return list(zip(st, en))


def align_words(text, path):
    """Wort-Zeiten ohne Zeitstempel vom Anbieter: Wörter nach Länge verteilen, Satzenden auf echte Sprechpausen legen."""
    total = audio_duration(path)
    words = text.split()
    if not words:
        return []
    sil = _silences(path)
    lead = sil[0][1] if sil and sil[0][0] < 0.05 else 0.0
    tail = sil[-1][0] if sil and sil[-1][1] > total - 0.08 else total
    gaps = [(a, b) for a, b in sil if a > lead + 0.05 and b < tail - 0.05]
    weight = [len(re.sub(r"\W", "", w)) + 2.0 for w in words]
    pause = [0.9 if re.search(r"[.!?…:]$", w) else 0.35 if re.search(r"[,;–-]$", w) else 0.0 for w in words]
    gap_total = sum(b - a for a, b in gaps)
    speech = max(0.5, (tail - lead) - gap_total)
    per = speech / sum(weight)
    # 1. Schätzung: Wörter nacheinander, Pausen proportional zu den gemessenen Pausen
    psum = sum(pause) or 1.0
    t, est = lead, []
    for w, wt, pz in zip(words, weight, pause):
        est.append([w, t, t + wt * per])
        t += wt * per + pz / psum * gap_total
    # 2. Satzenden auf die nächste echte Pause schieben und die Wörter dazwischen strecken/stauchen
    anchors = [(0, lead, lead)]          # (Wortindex, Ende des vorigen Satzes, Start des nächsten)
    for i, pz in enumerate(pause[:-1]):
        if pz >= 0.9 and gaps:
            a, b = min(gaps, key=lambda g: abs(g[0] - est[i][2]))
            if abs(a - est[i][2]) < 2.5 and i + 1 > anchors[-1][0] and a > anchors[-1][2] + 0.2:
                anchors.append((i + 1, a, b))
                gaps = [g for g in gaps if g[0] > a]
    anchors.append((len(words), tail, tail))
    out = []
    for (i0, _, t0), (i1, end, _) in zip(anchors, anchors[1:]):
        seg = est[i0:i1]
        if not seg:
            continue
        e0, e1 = seg[0][1], seg[-1][2]
        k = (end - t0) / max(0.01, e1 - e0)
        for w, a, b in seg:
            out.append((w, t0 + (a - e0) * k, t0 + (b - e0) * k))
    return out or _even_words(text, total)


def _norm_word(w):
    return re.sub(r"[^a-z0-9äöüß]", "", w.lower())


_whisper = None


def listen(path):
    """Hört die Aufnahme ab (lokales Spracherkennungs-Modell) und gibt die erkannten Wörter mit Zeiten zurück – oder None."""
    global _whisper
    try:
        from faster_whisper import WhisperModel
        if _whisper is None:
            _whisper = WhisperModel("small", device="cpu", compute_type="int8")
        import numpy as np
        raw = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path), "-f", "f32le", "-ac", "1",
                              "-ar", "16000", "-"], capture_output=True, check=True).stdout
        audio = np.frombuffer(raw, dtype=np.float32)      # selbst dekodieren: unabhängig von der Audio-Bibliothek des Modells
        segs, _ = _whisper.transcribe(audio, language="de", word_timestamps=True, beam_size=2,
                                      condition_on_previous_text=False, vad_filter=False)
        heard = []
        for sg in segs:
            for w in (sg.words or []):
                for part in w.word.split():
                    if _norm_word(part):
                        heard.append((part, float(w.start), float(w.end)))
        return heard or None
    except Exception as e:  # noqa: BLE001
        log(f"Sprach-Abgleich nicht möglich ({str(e)[:120]}) – Zeiten werden geschätzt")
        return None


def match_words(text, heard, total):
    """Legt die Drehbuch-Wörter auf die gehörten Wörter. Gibt (Wort-Zeiten, Trefferquote 0..1) zurück."""
    import difflib
    words = text.split()
    a = [_norm_word(w) for w in words]
    b = [_norm_word(h[0]) for h in heard]
    times = [None] * len(words)
    hit = 0
    for blk in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            times[blk.a + k] = (heard[blk.b + k][1], heard[blk.b + k][2])
            hit += 1
    # zusammengezogene/getrennte Wörter: „supervulkan“ ↔ „super vulkan“ zählen als gehört
    ratio = hit / max(1, len(words))
    # Lücken zwischen sicheren Wörtern gleichmäßig nach Wortlänge füllen
    known = [(-1, 0.0, 0.0)] + [(i, t[0], t[1]) for i, t in enumerate(times) if t] + [(len(words), total, total)]
    for (i0, _, e0), (i1, s1, _) in zip(known, known[1:]):
        gap = list(range(i0 + 1, i1))
        if not gap:
            continue
        span = max(0.05 * len(gap), s1 - e0)
        wsum = sum(len(a[g]) + 2 for g in gap)
        t = e0
        for g in gap:
            d = span * (len(a[g]) + 2) / wsum
            times[g] = (t, t + d * 0.92)
            t += d
    out, last = [], 0.0
    for w, (s0, e0) in zip(words, times):      # Zeiten streng aufsteigend halten
        s0 = max(s0, last)
        e0 = max(e0, s0 + 0.06)
        out.append((w, s0, e0))
        last = s0 + 0.01
    return out, ratio


def spoken_words(text, path):
    """Wort-Zeiten für eine Aufnahme ohne Zeitstempel: abhören und abgleichen. Spricht der Anbieter davor oder danach
    etwas Zusätzliches (z. B. die Regieanweisung), wird das weggeschnitten; weicht die Aufnahme sonst stark vom Text ab,
    gilt sie als misslungen."""
    heard = listen(path)
    if not heard:
        return align_words(text, path)
    total = audio_duration(path)
    words, ratio = match_words(text, heard, total)
    n_text = len(text.split())
    # erster/letzter sicher erkannter Textteil → alles davor und danach abschneiden
    import difflib
    a = [_norm_word(w) for w in text.split()]
    b = [_norm_word(h[0]) for h in heard]
    blocks = [m for m in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks() if m.size >= 2]
    if blocks:
        first, last = blocks[0], blocks[-1]
        lead_extra = first.b - first.a                       # gehörte Wörter vor dem Textanfang
        tail_extra = (len(b) - (last.b + last.size)) - (len(a) - (last.a + last.size))
        t0 = heard[first.b][1] - 0.12 if lead_extra > 3 else 0.0
        t1 = heard[last.b + last.size - 1][2] + 0.35 if tail_extra > 3 else total
        if t0 > 0.5 or t1 < total - 0.8:
            tmp = str(path) + ".cut.mp3"
            p = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(path), "-ss", f"{max(0, t0):.2f}",
                                "-to", f"{t1:.2f}", "-b:a", "160k", tmp], capture_output=True, text=True)
            if p.returncode == 0:
                os.replace(tmp, str(path))
                log(f"Aufnahme zugeschnitten (vorn {max(0, t0):.1f} s, hinten {total - t1:.1f} s zusätzlich Gesprochenes entfernt)")
                heard = [(w, s0 - max(0, t0), e0 - max(0, t0)) for w, s0, e0 in heard if s0 >= t0 - 0.05 and e0 <= t1 + 0.05]
                total = audio_duration(path)
                words, ratio = match_words(text, heard, total)
    log(f"Sprach-Abgleich: {round(ratio * 100)} % der Wörter erkannt")
    if ratio < 0.7 or len(heard) > n_text * 1.2 or len(heard) < n_text * 0.7:
        raise ProviderError(f"Aufnahme weicht vom Text ab ({round(ratio * 100)} % Treffer, {len(heard)} statt {n_text} Wörter)")
    return words


GEMINI_VOICES = {"grusel": "Enceladus", "lustig": "Puck", "tiere": "Sulafat", "mysterien": "Algenib"}


def _gemini_tts(text, out, cat):
    key = secret("GEMINI_API_KEY")
    if not key:
        raise ProviderError("kein GEMINI_API_KEY")
    voice = cfg("gemini_voice") or GEMINI_VOICES.get(cat.get("slug"), "Puck")
    style = (cfg("voice_style") or cat.get("voice_instructions") or "Ruhig und natürlich.").strip()
    speed = max(0.8, min(1.15, float(cfg("voice_speed") or 1.0)))
    # kurze Regieanweisung: lange Anweisungen liest das Modell manchmal mit vor
    short = style.split("–")[0].split(".")[0].strip()[:60]
    prompt = f"Sprich {short[0].lower() + short[1:] if short else 'ruhig'}, deutlich:\n\n{text}"
    last = None
    for model in [m for m in (cfg("gemini_tts_model"), "gemini-3.8-flash-tts", "gemini-3.8-flash-tts",
                              "gemini-3.1-flash-tts-preview", "gemini-2.5-flash-preview-tts") if m]:
        try:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                              headers={"x-goog-api-key": key},
                              json={"contents": [{"parts": [{"text": prompt}]}],
                                    "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {
                                        "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}},
                              timeout=240)
            if r.status_code != 200:
                last = f"{model}: HTTP {r.status_code} {' '.join(r.text.split())[:200]}"
                log(f"Gemini-Stimme {last}")
                continue
            part = r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
            raw = base64.b64decode(part["data"])
            mime = str(part.get("mimeType", "")).lower()
            tmp = str(out) + (".wav" if "wav" in mime else ".pcm")
            with open(tmp, "wb") as f:
                f.write(raw)
            rate = (re.search(r"rate=(\d+)", mime) or [0, "24000"])[1]
            src = ["-i", tmp] if tmp.endswith(".wav") else ["-f", "s16le", "-ar", rate, "-ac", "1", "-i", tmp]
            p = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *src,
                                "-af", "silenceremove=start_periods=1:start_threshold=-45dB,highpass=f=70"
                                + (f",atempo={speed:.2f}" if abs(speed - 1) > 0.01 else ""),
                                "-ar", "44100", "-b:a", "160k", str(out)], capture_output=True, text=True)
            os.remove(tmp)
            if p.returncode != 0:
                last = f"{model}: {p.stderr[-160:]}"
                continue
            if audio_duration(out) < max(3.0, len(text.split()) / 6):   # deutlich zu kurz → abgebrochen
                last = f"{model}: Aufnahme unvollständig"
                continue
            try:
                return spoken_words(text, out)
            except ProviderError as e:
                last = f"{model}: {e}"
                log(f"Gemini-Stimme {last} – neuer Versuch")
                continue
        except Exception as e:  # noqa: BLE001  (Netzfehler, leere Antwort ohne Ton …)
            last = f"{model}: {type(e).__name__} {str(e)[:80]}"
            log(f"Gemini-Stimme {last} – neuer Versuch")
    raise ProviderError(f"Gemini-Stimme: {last}")


TTS_PROVIDERS = {"edge": _edge, "openai": _openai_tts, "elevenlabs": _elevenlabs, "gemini": _gemini_tts}


def speak(text: str, out, cat: dict) -> tuple[list, str]:
    chosen = cfg("tts_provider") or "edge"
    order = [chosen] + (["edge"] if chosen != "edge" else [])
    errors = []
    for p in order:
        try:
            return TTS_PROVIDERS[p](text, out, cat), p
        except Exception as e:  # noqa: BLE001
            errors.append(f"{p}: {e}")
            log(f"Stimme über {p} fehlgeschlagen ({str(e)[:260]}), versuche nächsten Anbieter …")
    raise ProviderError("Keine Stimme verfügbar. " + " | ".join(errors))


# ---------------------------------------------------------------- Bilder

def _cover(img: Image.Image) -> Image.Image:
    img = img.convert("RGB")
    s = max(W / img.width, H / img.height)
    img = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    x, y = (img.width - W) // 2, (img.height - H) // 2
    return img.crop((x, y, x + W, y + H))


def _cloudflare(prompt, seed):
    acct, tok = secret("CLOUDFLARE_ACCOUNT_ID"), secret("CLOUDFLARE_API_TOKEN")
    if not acct or not tok:
        raise ProviderError("Cloudflare-Zugang fehlt")
    r = requests.post(f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/@cf/black-forest-labs/flux-1-schnell",
                      headers={"Authorization": f"Bearer {tok}"},
                      json={"prompt": prompt[:2000], "steps": 8}, timeout=TIMEOUT)
    _check(r, "Cloudflare")
    return Image.open(io.BytesIO(base64.b64decode(r.json()["result"]["image"])))


_last_poll_img = 0.0


def _pollinations_img(prompt, seed):
    global _last_poll_img
    for attempt in range(3):
        wait = 46 - (time.time() - _last_poll_img)
        if wait > 0:
            time.sleep(wait)
        _last_poll_img = time.time()
        url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt[:900])
        r = requests.get(url, params={"width": 720, "height": 1280, "seed": seed, "nologo": "true"}, timeout=TIMEOUT)
        if r.status_code in (402, 429) and attempt < 2:
            time.sleep(int(r.headers.get("Retry-After", "45")))
            continue
        _check(r, "Pollinations-Bild")
        return Image.open(io.BytesIO(r.content))
    raise ProviderError("Pollinations-Bild: Limit erreicht")


def _openai_img(prompt, seed):
    key = secret("OPENAI_API_KEY")
    if not key:
        raise ProviderError("kein OPENAI_API_KEY")
    r = requests.post("https://api.openai.com/v1/images/generations",
                      headers={"Authorization": f"Bearer {key}"},
                      json={"model": cfg("openai_image_model"), "prompt": prompt, "n": 1,
                            "size": "1024x1536", "quality": cfg("openai_image_quality")},
                      timeout=TIMEOUT)
    _check(r, "OpenAI-Bild")
    return Image.open(io.BytesIO(base64.b64decode(r.json()["data"][0]["b64_json"])))


IMAGE_PROVIDERS = {"cloudflare": _cloudflare, "pollinations": _pollinations_img, "openai": _openai_img}


_img_warned = set()


def image(prompt: str, out, seed: int) -> str:
    chosen = cfg("image_provider") or "cloudflare"
    order = [chosen] + [p for p in ("cloudflare", "pollinations") if p != chosen]
    errors = []
    for p in order:
        for attempt in range(2):
            try:
                _cover(IMAGE_PROVIDERS[p](prompt, seed + attempt)).save(out, quality=92)
                return p
            except Exception as e:  # noqa: BLE001
                err = str(e)
                if p not in _img_warned:   # einmal pro Lauf zeigen, warum ein Anbieter ausfällt
                    _img_warned.add(p)
                    log(f"Bilder über {p} fehlgeschlagen: {err[:300]}")
                if "fehlt" in err or "kein " in err:
                    break
        errors.append(f"{p}: {err}")
    raise ProviderError("Kein Bild-Anbieter erreichbar. " + " | ".join(errors))
