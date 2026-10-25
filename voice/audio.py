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
