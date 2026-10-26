"""Wake-word scaffold (E4).

Built-in `EnergyTrigger` is a placeholder that only reacts to a loud onset.
`OpenWakeWordDetector` adapts dscrapka/openWakeWord (Apache 2.0 runtime;
model weights have their own license depending on training data) and runs on
the always-open ring buffer in ~80 ms frames.
"""
import os
import time

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None


class WakeWordDetector:
    def detect(self, frame) -> bool:
        raise NotImplementedError

    def reset(self):
        pass


class EnergyTrigger(WakeWordDetector):
    """Placeholder: fires on a loud onset. High false-accept rate; plumbing only."""
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


class OpenWakeWordDetector(WakeWordDetector):
    """Adapter for an openWakeWord-trained model. Requires `openwakeword` and `onnxruntime`.

    model_path points at the exported .onnx (or a model name resolvable by the
    openwakeword library). Construction reports missing deps clearly.
    """
    def __init__(self, model_path, threshold=0.5, cooldown_s=1.5):
        self.model_path = model_path
        self.threshold = float(threshold)
        self.cooldown_s = float(cooldown_s)
        self._last = 0.0
        self._last_dbg = 0.0
        self._model = None
        self._lib = None
        self._error = None
        self._available_libs()
        if self._error:
            import sys
            print(f"WakeWord: {self._error}", file=sys.stderr)

    def _available_libs(self):
        try:
            import openwakeword
        except ImportError:
            self._error = "openwakeword not installed"
            return
        try:
            import onnxruntime
        except ImportError:
            self._error = "onnxruntime not installed"
            return
        self._lib = openwakeword
        path = self.model_path
        if not path.lower().endswith(".onnx"):
            import os as _os
            import openwakeword
            base = _os.path.join(_os.path.dirname(openwakeword.__file__), "resources", "models")
            cand = _os.path.join(base, self.model_path if self.model_path.endswith(".onnx") else self.model_path + ".onnx")
            if os.path.exists(cand):
                path = cand
            else:
                self._error = f"model file not found: {cand}"
                return
        try:
            self._model = openwakeword.Model(wakeword_model_paths=[path])
        except Exception as e:
            self._error = f"failed to load model: {e}"
            self._model = None

    def available(self) -> bool:
        return self._model is not None

    def detect(self, frame):
        if self._model is None:
            return False
        import numpy as np
        arr = np.asarray(frame)
        if arr.dtype.kind == "f":
            arr = (arr * 32767).clip(-32768, 32767).astype("int16")
        else:
            arr = arr.astype("int16")
        try:
            pred = self._model.predict(arr)
        except Exception:
            return False
        scores = pred.values() if hasattr(pred, "values") else [pred]
        score = max((float(s) for s in scores), default=0.0)
        self.last_score = score
        now = time.monotonic()
        if os.environ.get("NESTCLOCK_WAKE_DEBUG") == "1":
            if score >= 0.2 and (now - self._last_dbg) >= 2.0:
                self._last_dbg = now
                print(f"WakeWord: score {score:.2f} (threshold {self.threshold})")
        if score >= self.threshold and (now - self._last) >= self.cooldown_s:
            self._last = now
            return True
        return False

    def reset(self):
        if self._model is not None:
            try:
                self._model.reset()
            except Exception:
                pass


def build_detector():
    """Pick a detector from env vars. Defaults to the placeholder."""
    path = os.environ.get("NESTCLOCK_WAKE_MODEL", "hey_jarvis_v0.1")
    if path:
        try:
            thr = float(os.environ.get("NESTCLOCK_WAKE_THRESHOLD", "0.5"))
        except ValueError:
            thr = 0.5
        d = OpenWakeWordDetector(path, threshold=thr)
        if d.available():
            print(f"WakeWord: openWakeWord model '{path}' loaded (threshold {thr}).")
            return d
        print(f"WakeWord: falling back to EnergyTrigger ({d._error})")
    return EnergyTrigger()


def run_loop(mic_capture, on_trigger, frame_seconds=0.08, cooldown_s=2.0,
             detector=None):
    import time
    if detector is None:
        detector = build_detector()
    sr = getattr(mic_capture, "rate", 16000) or 16000
    n = int(sr * frame_seconds)
    last_written = 0
    while True:
        ring = getattr(mic_capture, "ring", None)
        snap = ring.snapshot() if ring is not None else None
        if snap is None or len(snap) < n:
            time.sleep(frame_seconds)
            continue
        # Detect new audio by the cumulative write counter: a full ring buffer's
        # snapshot length never changes, so length comparison would stop detection
        # after the first `seconds` of uptime.
        written = ring.written()
        if written == last_written:
            time.sleep(frame_seconds)
            continue
        last_written = written
        frame = snap[-n:]
        if detector.detect(frame):
            score = getattr(detector, "last_score", float("nan"))
            print(f"WakeWord: trigger (score {score:.2f}) — starting voice pipeline")
            on_trigger()
        time.sleep(frame_seconds)
