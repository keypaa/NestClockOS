"""Offline WAV -> STT + router dry run."""
import sys, os


def run(path, model_dir=None):
    import wave, struct
    with wave.open(path, "rb") as w:
        if (w.getframerate(), w.getnchannels(), w.getsampwidth()) != (16000, 1, 2):
            raise ValueError("expected 16 kHz mono 16-bit wav")
        audio = __import__("numpy").frombuffer(w.readframes(w.getnframes()), dtype=__import__("numpy").int16)
    from mistralai import Mistral
    from .stt import transcribe_parallel
    from .router import RouterService
    import sys; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from stt_session import make_client
    client = make_client()
    res = transcribe_parallel(client, audio)
    rs = RouterService(model_dir or os.environ.get("NESTCLOCK_ROUTER_DIR"))
    rs.load()
    from .pipeline import run_text_pipeline
    out = run_text_pipeline(rs, res.get("en", {}).get("text", ""), res.get("fr", {}).get("text", ""))
    print(out)
    return out


if __name__ == "__main__":
    run(sys.argv[1])
