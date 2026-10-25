"""Voxtral transcription with the E1.3 language policies (P2 default)."""
import io
import os
import tempfile
import time
import wave
from pathlib import Path

import numpy as np


def _write_wav(audio, path):
    import wave
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(audio.tobytes())


def transcribe_once(client, audio, language=None):
    """Return (text, latency_ms). audio is int16 numpy 16 kHz mono."""
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "utterance.wav"
        _write_wav(audio, path)
        t0 = time.time()
        with open(path, "rb") as f:
            kwargs = {"model": "voxtral-mini-latest", "file": {"content": f, "file_name": path.name}}
            if language:
                kwargs["language"] = language
            resp = client.audio.transcriptions.complete(**kwargs)
        ms = (time.time() - t0) * 1000
    return (resp.text or "").strip(), ms


def transcribe_parallel(client, audio):
    """P2: transcribe in English and French concurrently; return dict lang->(text, ms)."""
    import concurrent.futures
    out = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futs = {lang: pool.submit(transcribe_once, client, audio, lang) for lang in ("en", "fr")}
        for lang, fut in futs.items():
            try:
                text, ms = fut.result(timeout=30)
                out[lang] = {"text": text, "ms": ms, "error": None}
            except Exception as e:
                out[lang] = {"text": "", "ms": 0, "error": str(e)}
    return out
