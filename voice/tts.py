"""Voxtral TTS (play through sounddevice)."""
import base64
import os
import tempfile
from pathlib import Path


DEFAULT_VOICES = {
    "en": os.environ.get("NESTCLOCK_TTS_VOICE_EN", "82c99ee6-f932-423f-a4a3-d403c8914b8d"),
    "fr": os.environ.get("NESTCLOCK_TTS_VOICE_FR", "5a271406-039d-46fe-835b-fbbb00eaf08d"),
}


def speak(client, text, language="en", voice_id=None):
    if not text:
        return
    try:
        if voice_id is None:
            voice_id = DEFAULT_VOICES.get(language if language in DEFAULT_VOICES else "en")
        response = client.audio.speech.complete(
            model=os.environ.get("NESTCLOCK_TTS_MODEL", "voxtral-mini-tts-3-0"),
            input=text,
            voice_id=voice_id,
            response_format="wav",
        )
    except Exception as e:
        print(f"TTS error: {e}")
        return
    audio = base64.b64decode(response.audio_data)
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "tts.wav"
        path.write_bytes(audio)
        # play via sounddevice
        try:
            import sounddevice as sd, wave, numpy as np
            with wave.open(str(path), "rb") as w:
                sr = w.getframerate()
                data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype("float32") / 32768.0
                sd.play(data, sr)
                sd.wait()
        except Exception as e:
            print(f"TTS playback error: {e}")
