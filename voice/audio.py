"""Audio helpers shared by the CLI and companion."""
import collections
import queue
import time

import numpy as np

SAMPLE_RATE = 16000


def to_16k(audio, rate):
    if rate == SAMPLE_RATE:
        return audio
    try:
        from math import gcd
        from scipy.signal import resample_poly
        g = gcd(SAMPLE_RATE, rate)
        return resample_poly(audio, SAMPLE_RATE // g, rate // g).astype(np.float32)
    except ImportError:
        n = int(len(audio) * SAMPLE_RATE / rate)
        return np.interp(np.linspace(0, len(audio) - 1, n), np.arange(len(audio)), audio).astype(np.float32)


class RingBuffer:
    """Fixed-capacity float32 ring buffer for the always-open input stream."""
    def __init__(self, seconds=10, sample_rate=SAMPLE_RATE):
        self.sample_rate = sample_rate
        self.capacity = max(1, int(seconds * sample_rate))
        self.buf = np.zeros(self.capacity, dtype="float32")
        self.pos = 0
        self.filled = 0

    def append(self, samples):
        samples = np.asarray(samples, dtype="float32").ravel()
        n = len(samples)
        if n >= self.capacity:
            self.buf[:] = samples[-self.capacity:]
            self.pos = 0
            self.filled = self.capacity
            return
        end = self.pos + n
        if end <= self.capacity:
            self.buf[self.pos:end] = samples
        else:
            first = self.capacity - self.pos
            self.buf[self.pos:] = samples[:first]
            self.buf[:n - first] = samples[first:]
        self.pos = (self.pos + n) % self.capacity
        self.filled = min(self.capacity, self.filled + n)

    def snapshot(self):
        if self.filled == 0:
            return np.zeros(0, dtype="float32")
        if self.filled < self.capacity:
            return self.buf[:self.filled].copy()
        return np.concatenate((self.buf[self.pos:], self.buf[:self.pos])).copy()


class MicCapture:
    """Always-open microphone input with a ring buffer and one-utterance capture."""
    def __init__(self, device=None):
        self.device = device
        self.rate = None
        self.channels = 1
        self.stream = None
        self.ring = None
        self._queue = queue.Queue(maxsize=200)

    def open(self):
        import sounddevice as sd
        from stt_session import _open_settings
        rate, ch = _open_settings(self.device)
        self.rate = rate
        self.channels = ch
        self.ring = RingBuffer(seconds=10, sample_rate=rate)

        def callback(indata, frames, time_info, status):
            mono = indata[:, 0] if (indata.ndim > 1 and indata.shape[1] > 1) else indata.ravel()
            mono = mono.astype("float32", copy=False)
            self.ring.append(mono)
            try:
                self._queue.put_nowait(mono.copy())
            except Exception:
                pass

        self.stream = sd.InputStream(device=self.device, channels=ch, samplerate=rate,
                                    dtype="float32", blocksize=int(rate * 0.05), callback=callback)
        self.stream.start()

    def close(self):
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None

    def capture_one(self, info=None):
        from collections import deque
        from voice.endpoint import Endpointer, TAIL_FRAMES
        if info is None:
            info = {}
        if self.stream is None:
            raise RuntimeError("MicCapture not opened")
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except Exception:
                break
        ep = Endpointer()
        recent = deque(maxlen=6)
        speech = []
        peak = 0.0
        glitches = 0
        started = False
        deadline = time.monotonic() + 12.0
        while time.monotonic() < deadline:
            try:
                frame = self._queue.get(timeout=0.2)
            except Exception:
                continue
            rms = float(np.sqrt(np.mean(frame ** 2))) if len(frame) else 0.0
            if rms > peak:
                peak = rms
            if rms >= 0.5:
                glitches += 1
            result = ep.feed(rms)
            if ep.state == "speech" and not started:
                started = True
                speech.extend(list(recent))
            if ep.state == "speech":
                speech.append(frame)
            recent.append(frame)
            if result == "done":
                for _ in range(TAIL_FRAMES):
                    try:
                        speech.append(self._queue.get(timeout=0.2))
                    except Exception:
                        break
                break
            if result == "timeout":
                break
        info["floor"] = ep.floor
        info["threshold"] = ep.threshold
        info["peak"] = peak
        info["glitches"] = glitches
        if not speech:
            return None
        raw = np.concatenate(speech).astype("float32")
        if self.rate == SAMPLE_RATE:
            audio = raw
        else:
            audio = to_16k(raw, self.rate)
        # convert to int16 at 16 kHz
        if self.rate != SAMPLE_RATE:
            return (audio * 32767).clip(-32768, 32767).astype("int16")
        # already 16k raw float; resample not needed but convert
        return (raw * 32767).clip(-32768, 32767).astype("int16")
