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
    return json.loads(txt[a:b + 1])


def _gemini(system, user, temperature):
    key = secret("GEMINI_API_KEY")
    if not key:
        raise ProviderError("kein GEMINI_API_KEY")
    model = cfg("gemini_model") or "gemini-flash-latest"
    body = {"systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": temperature, "responseMimeType": "application/json"}}
    # 1. Versuch: eingestelltes Modell mit kurzer Denkphase (thinkingLevel low) – ohne diese Vorgabe denken
    #    die neuen Flash-Modelle oft mehrere Minuten. Kennt das Modell die Vorgabe nicht, ohne sie.
    # 2. Versuch: gemini-flash-lite-latest – sehr schnell, reicht notfalls für Skripte.
    gc = body["generationConfig"]
    tries = [(model, {**body, "generationConfig": {**gc, "thinkingConfig": {"thinkingLevel": "low"}}}, 150),
             (model, body, 150),
             ("gemini-flash-lite-latest", body, 120)]
    last, skip_plain = None, True
    for n, (m, b, to) in enumerate(tries):
        if n == 1 and skip_plain:
            continue   # nur nötig, wenn das Modell thinkingLevel ablehnt
        try:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                              headers={"x-goog-api-key": key}, json=b, timeout=to)
            if n == 0 and r.status_code == 400 and "think" in r.text.lower():
                skip_plain = False
                continue
            if r.status_code in (404, 429, 500, 503) and n < len(tries) - 1:
                last = ProviderError(f"Gemini {m}: HTTP {r.status_code}")
                log(f"Gemini {m}: HTTP {r.status_code}, versuche Ersatzmodell")
                skip_plain = True
                continue
            _check(r, "Gemini")
            parts = r.json()["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts if not p.get("thought"))
        except requests.Timeout as e:
            last = e
            skip_plain = True
            log(f"Gemini {m} antwortet nicht rechtzeitig, versuche Ersatzmodell")
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


TTS_PROVIDERS = {"edge": _edge, "openai": _openai_tts, "elevenlabs": _elevenlabs}


def speak(text: str, out, cat: dict) -> tuple[list, str]:
    chosen = cfg("tts_provider") or "edge"
    order = [chosen] + (["edge"] if chosen != "edge" else [])
    errors = []
    for p in order:
        try:
            return TTS_PROVIDERS[p](text, out, cat), p
        except Exception as e:  # noqa: BLE001
            errors.append(f"{p}: {e}")
            log(f"Stimme über {p} fehlgeschlagen, versuche nächsten Anbieter …")
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
                      json={"prompt": prompt[:2000], "steps": 6, "seed": seed}, timeout=TIMEOUT)
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
                if "fehlt" in err or "kein " in err:
                    break
        errors.append(f"{p}: {err}")
    raise ProviderError("Kein Bild-Anbieter erreichbar. " + " | ".join(errors))
