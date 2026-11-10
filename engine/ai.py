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
    js = json.loads(txt[a:b + 1])
    if not isinstance(js, dict):
        raise ProviderError("Antwort ist kein JSON-Objekt")
    return js


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
    gc = {"temperature": temperature, "responseMimeType": "application/json", "maxOutputTokens": 8192}
    body = {"systemInstruction": {"parts": [{"text": system}]}, "contents": [{"role": "user", "parts": [{"text": user}]}]}
    last = None
    for m in models:
        for think in ({"thinkingLevel": "low"}, None):
            cfg_ = {**gc, "thinkingConfig": think} if think else gc
            try:
                r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                                  headers={"x-goog-api-key": key}, json={**body, "generationConfig": cfg_}, timeout=70)
            except requests.RequestException as e:
                last = f"{m}: {type(e).__name__}"
                break
            if r.status_code == 400 and think:
                continue                      # Modell kennt die Denk-Vorgabe nicht → ohne
            if r.status_code != 200:
                last = f"{m}: HTTP {r.status_code}"
                break
            try:
                parts = r.json()["candidates"][0]["content"]["parts"]
                txt = "".join(p.get("text", "") for p in parts if not p.get("thought"))
                _parse_json(txt)
                return txt
            except Exception as e:  # noqa: BLE001
                last = f"{m}: ungültige Antwort ({str(e)[:60]})"
                break
        log(f"Gemini {last} – versuche Ersatzmodell")
    raise ProviderError(f"Gemini: {last}")


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
                                    "temperature": temperature},
                              timeout=90)
        except requests.RequestException as e:   # Zeitüberschreitung/Verbindung: kurz warten, neu versuchen
            if attempt == 2:
                raise ProviderError(f"Pollinations-Text nicht erreichbar ({type(e).__name__})") from e
            log("Pollinations antwortet nicht, neuer Versuch …")
            time.sleep(20)
            continue
        if r.status_code >= 500 and attempt < 2:
            time.sleep(20)
            continue
        if r.status_code in (402, 429) and attempt < 2:
            time.sleep(int(r.headers.get("Retry-After", "35")) + 1)
            continue
        _check(r, "Pollinations-Text")
        return r.json()["choices"][0]["message"]["content"]
    raise ProviderError("Pollinations-Text: Limit erreicht")


TEXT_PROVIDERS = {"gemini": _gemini, "openai": _openai_text, "pollinations": _pollinations_text}


def chat_json(system: str, user: str, temperature: float = 0.9) -> tuple[dict, str]:
    chosen = cfg("text_provider") or "gemini"
    order = [chosen] + [p for p in ("gemini", "pollinations") if p != chosen]
    errors = []
    for p in order:
        try:
            return _parse_json(TEXT_PROVIDERS[p](system, user, temperature)), p
        except Exception as e:  # noqa: BLE001
            errors.append(f"{p}: {e}")
            log(f"Text über {p} fehlgeschlagen, versuche nächsten Anbieter …")
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
        kw = dict(rate=cat.get("voice_rate") or "+0%", pitch=cat.get("voice_pitch") or "+0Hz")
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
        segs, _ = _whisper.transcribe(str(path), language="de", word_timestamps=True, beam_size=2,
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
    """Wort-Zeiten für eine Aufnahme ohne Zeitstempel: abhören und abgleichen; weicht die Aufnahme stark vom Text ab,
    gilt sie als misslungen (der Anbieter hat etwas anderes gesprochen)."""
    heard = listen(path)
    if not heard:
        return align_words(text, path)
    words, ratio = match_words(text, heard, audio_duration(path))
    log(f"Sprach-Abgleich: {round(ratio * 100)} % der Wörter erkannt")
    n_text, n_heard = len(text.split()), len(heard)
    if ratio < 0.7 or n_heard > n_text * 1.25 or n_heard < n_text * 0.7:
        raise ProviderError(f"Aufnahme weicht vom Text ab ({round(ratio * 100)} % Treffer, {n_heard} statt {n_text} Wörter)")
    return words


GEMINI_VOICES = {"grusel": "Enceladus", "lustig": "Puck", "tiere": "Sulafat", "mysterien": "Algenib"}


def _gemini_tts(text, out, cat):
    key = secret("GEMINI_API_KEY")
    if not key:
        raise ProviderError("kein GEMINI_API_KEY")
    voice = cfg("gemini_voice") or GEMINI_VOICES.get(cat.get("slug"), "Charon")
    style = (cat.get("voice_instructions") or "Fesselnd und natürlich.").strip()
    prompt = ("Sprich den folgenden deutschen Text als professioneller Erzähler für ein Kurzvideo. "
              f"Stil: {style} Flüssig und natürlich wie ein Mensch, der eine Geschichte erzählt – mit Betonung, "
              "kleinen Pausen an den Satzenden und lebendigem Tempo, nicht abgehackt, nicht vorgelesen. "
              "Sprich jedes Wort deutlich und vollständig aus, ziehe keine Wörter zusammen und verschlucke keine Silben. "
              "Sprich GENAU diesen Text Wort für Wort – nichts weglassen, nichts hinzufügen, nichts umformulieren, "
              "nichts davor oder danach:\n\n" + text)
    last = None
    for model in [m for m in (cfg("gemini_tts_model"), "gemini-3.8-flash-tts", "gemini-3.1-flash-tts-preview",
                              "gemini-2.5-flash-preview-tts") if m]:
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
                                "-af", "silenceremove=start_periods=1:start_threshold=-45dB,highpass=f=70",
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
        except requests.RequestException as e:
            last = f"{model}: {type(e).__name__}"
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
