#!/usr/bin/env python3
"""Safety tests for the parle-plus-fort deterministic override.

The override forces fallback for the mic-gain / self-referential-volume
family regardless of model confidence (Phase 0.5 Addendum 4). These tests pin
both directions:
- MUST fire: mic-gain phrasing (including the exact eval row that survived
  three training rounds at 0.97/0.68/0.94).
- MUST NOT fire: genuine speaker-volume commands (bare comparatives included —
  run 2 established those are music), playback, weather, and other fallback
  rows (firing there would be score-harmless but means the regex is over-broad).

Run: python3 test_override.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from phase0_pipeline_test import PARLE_FAMILY_RE, _norm_override_text


def fires(text):
    return PARLE_FAMILY_RE.search(_norm_override_text(text)) is not None


MUST_FIRE = [
    "parle plus fort, i can't hear you stp",  # the eval row (3 rounds: .97/.68/.94)
    "Parle plus fort",
    "parlez plus fort s'il vous plaît",
    "je ne t'entends pas",
    "je t'entends mal",
    "euh, je t'entends pas",
    "I can't hear you",
    "i can't hear you, speak up",
    "speak up please",
    "could you speak louder",
]

MUST_NOT_FIRE = [
    # speaker-volume commands (music) — incl. bare comparatives from run-2 B1
    "monte le son",
    "baisse le son",
    "Monte le son d'un cran",
    "turn up the volume",
    "turn the volume down a touch",
    "un peu plus fort",
    "un peu moins fort",
    "encore plus fort stp",
    "mets le son à dix",
    "augmente le volume",
    # playback / weather / other (override must stay narrow)
    "hey nest, continue la lecture",
    "what does it feel like in rome right now please",
    "passe le bonjour à chloe",
    "who is this artist",
    "is it going to rain tomorrow",
]


def main():
    fails = []
    for t in MUST_FIRE:
        if not fires(t):
            fails.append(f"SHOULD FIRE but did not: {t!r}")
    for t in MUST_NOT_FIRE:
        if fires(t):
            fails.append(f"SHOULD NOT FIRE but did: {t!r}")
    if fails:
        print(f"{len(fails)} FAILURES:")
        for f in fails:
            print("  " + f)
        sys.exit(1)
    print(f"OK: {len(MUST_FIRE)} fire + {len(MUST_NOT_FIRE)} no-fire, 0 failures")


if __name__ == "__main__":
    main()
