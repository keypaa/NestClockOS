"""Voxtral TTS (play through sounddevice)."""
import base64
import os
import tempfile
from pathlib import Path


def speak(client, text, voice_id="gb_jane_neutral"):
    if not text:
        return
    try:
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
