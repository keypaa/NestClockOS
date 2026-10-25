"""Wake-word scaffolding (E4).

The detector is pluggable. The built-in `EnergyTrigger` is a placeholder that
fires on a loud onset; it is not a true wake word and exists for plumbing/tests
until a real detector is selected by licence/CPU/accuracy review.
"""
import time


class WakeWordDetector:
    def detect(self, frame) -> bool:
        raise NotImplementedError

    def reset(self):
        pass


class EnergyTrigger(WakeWordDetector):
    def __init__(self, threshold=0.08, cooldown_s=2.0):
        self.threshold = threshold
        self.cooldown_s = cooldown_s
        self._last = 0.0
        self._smooth = 0.0

    def detect(self, frame):
        import numpy as np
        arr = np.asarray(frame, dtype="float32")
        rms = float(np.sqrt(np.mean(arr ** 2))) if arr.size else 0.0
        self._smooth = 0.9 * self._smooth + 0.1 * rms
        now = time.monotonic()
        if rms > max(self.threshold, self._smooth * 4) and (now - self._last) >= self.cooldown_s:
            self._last = now
            return True
        return False


def run_loop(mic_capture, on_trigger, frame_seconds=0.08, cooldown_s=2.0):
    import time
    detector = EnergyTrigger(cooldown_s=cooldown_s)
    sr = getattr(mic_capture, "rate", 16000) or 16000
    n = int(sr * frame_seconds)
    last_len = 0
    while True:
        snap = mic_capture.ring.snapshot() if getattr(mic_capture, "ring", None) is not None else None
        if snap is None or len(snap) < n:
            time.sleep(frame_seconds)
            continue
        frame = snap[-n:]
        if len(snap) == last_len:
            time.sleep(frame_seconds)
            continue
        last_len = len(snap)
        if detector.detect(frame):
            on_trigger()
        time.sleep(frame_seconds)
