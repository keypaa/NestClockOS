"""Audio helpers shared by the CLI and companion."""
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
    """Fixed-capacity float32 ring buffer for the always-open input stream (E2.2 prep)."""
    def __init__(self, seconds=10, sample_rate=SAMPLE_RATE):
        self.sample_rate = sample_rate
        self.capacity = max(1, int(seconds * sample_rate))
        self.buf = __import__("numpy").zeros(self.capacity, dtype="float32")
        self.pos = 0
        self.filled = 0

    def append(self, samples):
        samples = __import__("numpy").asarray(samples, dtype="float32").ravel()
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
            return __import__("numpy").zeros(0, dtype="float32")
        if self.filled < self.capacity:
            return self.buf[:self.filled].copy()
        return __import__("numpy").concatenate((self.buf[self.pos:], self.buf[:self.pos])).copy()
