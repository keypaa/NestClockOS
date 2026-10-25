import numpy as np
from voice.endpoint import Endpointer
from voice.audio import RingBuffer
from voice.slots import parse_timer_start, parse_alarm_set
from voice.text import normalize, wer


def test_endpointer_basic():
    ep = Endpointer(calib_s=0.1, silence_s=0.1, min_speech_s=0.05)
    # calibrate quiet
    for _ in range(5):
        ep.feed(0.001)
    # speech
    for _ in range(20):
        ep.feed(0.5)
    assert ep.state == "speech"


def test_ring_buffer_wrap():
    rb = RingBuffer(seconds=0.1, sample_rate=100)
    rb.append(np.arange(50, dtype="float32"))
    rb.append(np.arange(50, 150, dtype="float32"))
    snap = rb.snapshot()
    assert len(snap) == 10
    assert snap[-1] == 149


def test_slots():
    assert parse_timer_start("set timer for 5 minutes") == 300
    a = parse_alarm_set("alarm 7h30 demain")
    assert a["hour"] == 7 and a["minute"] == 30 and a["once"] is True


def test_text():
    assert normalize("L'alarme, 7h!") == ["l", "alarme", "7h"]
    assert wer(["a","b"], ["a","b"]) == 0.0
