"""
NestClockOS — Phase 0: voice pipeline validation.

Two modes:

  record  — live mic test. Press Enter, speak, press Enter again.
            Runs the full chain: mic -> Mistral Voxtral STT -> Laya router.
            Use this to sanity-check the whole thing works end to end.

  batch   — text-only accuracy test. Reads a CSV of phrases with expected
            categories (no mic, no STT) and scores Laya's classification
            in isolation. Use this to find out whether routing itself is
            reliable, separately from transcription quality.

Usage:
    python phase0_pipeline_test.py record
    python phase0_pipeline_test.py batch test_phrases.csv

Setup (run once):
    pip install torch --index-url https://download.pytorch.org/whl/cpu
    pip install laya --no-deps
    pip install transformers safetensors huggingface_hub
    pip install mistralai sounddevice scipy

    export MISTRAL_API_KEY="your-key-here"
"""

import argparse
import csv
import os
import re
import sys
import tempfile
import time

# ---------------------------------------------------------------------------
# Shared: the routing question we ask Laya for every utterance.
# Categories map to the skills sketched for NestClockOS. Adjust freely —
# this is exactly the kind of thing Phase 0 is meant to help you tune.
# ---------------------------------------------------------------------------

ROUTING_QUESTIONS = {
    "category": {
        "type": "choice",
        "instructions": "What kind of request is this smart-clock command?",
        "criteria": {
            "alarm": "setting, changing, or cancelling an alarm",
            "timer": "setting, checking, or cancelling a countdown timer",
            "music": "playing, pausing, skipping, or controlling Spotify playback, including turning the volume up or down",
            "weather": "asking about current or forecast weather",
            "fallback": "anything that is not directly an alarm, timer, music, or weather command — open-ended questions, general conversation, unclear or incomplete speech, or anything else",
        },
    },
    "is_complete": {
        "type": "noul",
        "instructions": "Is this a complete, actionable command rather than a trailing-off or partial sentence?",
    },
}


def _norm_override_text(text: str) -> str:
    return text.replace("’", "'").lower()


# ---------------------------------------------------------------------------
# Deterministic application-layer override (Phase 0.5 Addendum 4).
# The mic-gain / self-referential-volume family ("parle plus fort",
# "je ne t'entends pas", "speak up", "I can't hear you") survived three RLCD
# rounds (0.97 -> 0.68 -> 0.94 on the identical phrase) while further training
# traded other problems for new ones. This family is small and enumerable, so
# safety is guaranteed downstream instead of chased through the router:
# applied to the router's OUTPUT, forces fallback regardless of confidence.
# See also phase1_design_notes.md (destructive-action confirmation rule) —
# both are cases for downstream logic, not router training.
# ---------------------------------------------------------------------------
PARLE_FAMILY_RE = re.compile(
    r"(\bparl(?:e[sz]?|ez|er)\b.{0,16}\bfort\b"  # parle/parles/parlez/parler + fort
    r"|\bt[’']entends?\s+(pas|mal)\b"  # je (ne) t'entends pas/mal
    r"|\bentends?\s+pas\b"
    r"|\bcan[’']?t hear you\b|\bcannot hear you\b"  # I can't hear you
    r"|\bspeak\s+(up|louder)\b)",  # speak up / speak louder
    re.IGNORECASE,
)


def classify(router, text: str, model: str = None, use_override: bool = True) -> dict:
    kwargs = {"model": model} if model else {}
    result = router.predict({"text": text}, ROUTING_QUESTIONS, **kwargs)
    answers = result["answers"]
    out = {
        "category": answers["category"]["choice"],
        "category_confidence": answers["category"]["confidence"],
        "is_complete": answers["is_complete"]["noul"],
        "routed_model": result["routing"]["model"],
        "overridden": False,
    }
    if use_override and PARLE_FAMILY_RE.search(_norm_override_text(text)):
        out["category"] = "fallback"
        out["category_confidence"] = 1.0
        out["overridden"] = True
    return out


def build_router():
    from laya import Router
    # preload=True keeps both checkpoints resident so language switches
    # (French <-> English) don't pay a reload cost mid-conversation.
    return Router(preload=True)


# ---------------------------------------------------------------------------
# Mode: record — full pipeline, one utterance at a time
# ---------------------------------------------------------------------------

def record_clip(seconds: float, samplerate: int = 16000):
    import numpy as np
    import sounddevice as sd

    print(f"Recording for {seconds:.1f}s... speak now.")
    audio = sd.rec(int(seconds * samplerate), samplerate=samplerate, channels=1, dtype="int16")
    sd.wait()
    return audio, samplerate


def save_wav(audio, samplerate: int) -> str:
    from scipy.io import wavfile

    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    wavfile.write(path, samplerate, audio)
    return path


def transcribe(client, path: str) -> str:
    model = "voxtral-mini-latest"
    with open(path, "rb") as f:
        response = client.audio.transcriptions.complete(
            model=model,
            file={"content": f, "file_name": os.path.basename(path)},
            # language intentionally omitted: Voxtral auto-detects, which is
            # exactly what we want to stress-test for French/English mixing.
        )
    return response.text


def run_record_mode():
    from mistralai import Mistral

    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        sys.exit("Set MISTRAL_API_KEY before running record mode.")

    client = Mistral(api_key=api_key)
    router = build_router()

    print("Loaded. Ctrl+C to stop.\n")
    while True:
        input("Press Enter to record a 4s clip...")
        audio, sr = record_clip(seconds=4.0)
        wav_path = save_wav(audio, sr)

        t0 = time.time()
        text = transcribe(client, wav_path)
        stt_ms = (time.time() - t0) * 1000

        t0 = time.time()
        result = classify(router, text)
        route_ms = (time.time() - t0) * 1000

        os.remove(wav_path)

        print(f"\n  transcript      : {text!r}")
        print(f"  category        : {result['category']} (confidence {result['category_confidence']:.2f})")
        print(f"  is_complete     : {result['is_complete']:.2f}")
        print(f"  routed to       : {result['routed_model']}")
        print(f"  latency         : stt {stt_ms:.0f} ms, routing {route_ms:.0f} ms\n")


# ---------------------------------------------------------------------------
# Mode: batch — text-only, scores Laya against known-correct labels
# ---------------------------------------------------------------------------

def analyze_thresholds(rows: list, thresholds=(0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)):
    """
    rows: list of dicts with keys 'confidence' (float) and 'ok' (bool).

    For each threshold, splits results into:
      - local_correct   : confidence >= threshold AND correct
                           (handled locally, no LLM call, and it was right)
      - local_wrong     : confidence >= threshold AND wrong
                           (the dangerous case: a confident mistake that would
                           execute without ever reaching the LLM safety net)
      - deferred_correct: confidence <  threshold AND was actually correct
                           (unnecessarily sent to the LLM, but harmless)
      - deferred_wrong  : confidence <  threshold AND wrong
                           (correctly caught before it could do damage)
    """
    print("\nConfidence-gating analysis")
    print(f"{'threshold':<10} {'local_ok':<10} {'local_WRONG':<12} {'deferred_ok':<12} {'deferred_wrong':<15} {'% stays local'}")
    print("-" * 80)

    for t in thresholds:
        local_correct = sum(1 for r in rows if r["confidence"] >= t and r["ok"])
        local_wrong = sum(1 for r in rows if r["confidence"] >= t and not r["ok"])
        deferred_correct = sum(1 for r in rows if r["confidence"] < t and r["ok"])
        deferred_wrong = sum(1 for r in rows if r["confidence"] < t and not r["ok"])
        pct_local = (local_correct + local_wrong) / len(rows) * 100

        flag = "  <-- confident mistakes slip through" if local_wrong > 0 else ""
        print(f"{t:<10} {local_correct:<10} {local_wrong:<12} {deferred_correct:<12} {deferred_wrong:<15} {pct_local:.0f}%{flag}")

    print(
        "\nRead this as: 'local_WRONG' is the only row that matters for safety — "
        "any nonzero value there means a wrong classification would confidently "
        "execute without ever reaching the LLM fallback. 'deferred_wrong' is fine: "
        "those get caught and re-routed. Pick the lowest threshold with local_WRONG == 0."
    )


def run_batch_mode(csv_path: str, model: str = None, split: str = None, quiet: bool = False,
                   use_override: bool = True):
    router = build_router()

    total = 0
    correct = 0
    by_language = {}
    by_split = {}
    all_rows = []

    if not quiet:
        print(f"{'phrase':<45} {'lang':<8} {'expected':<14} {'got':<14} {'conf':<6} ok?")
        print("-" * 95)

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            phrase = row["phrase"]
            expected = row["expected_category"]
            lang = row.get("language", "?")
            row_split = row.get("split", "all")
            if split and row_split != split:
                continue

            result = classify(router, phrase, model=model, use_override=use_override)
            got = result["category"]
            conf = result["category_confidence"]
            ok = got == expected
            overridden = result.get("overridden", False)

            total += 1
            correct += int(ok)
            stats = by_language.setdefault(lang, {"total": 0, "correct": 0})
            stats["total"] += 1
            stats["correct"] += int(ok)
            sstats = by_split.setdefault(row_split, {"total": 0, "correct": 0})
            sstats["total"] += 1
            sstats["correct"] += int(ok)
            all_rows.append({"phrase": phrase, "confidence": conf, "ok": ok})

            mark = "OK" if ok else "MISS"
            if overridden:
                mark += " [OVERRIDDEN]"
            if not quiet:
                print(f"{phrase[:44]:<45} {lang:<8} {expected:<14} {got:<14} {conf:<6.2f} {mark}")

    print("-" * 95)
    print(f"Overall: {correct}/{total} = {correct / total:.1%}")
    for lang, stats in by_language.items():
        print(f"  {lang}: {stats['correct']}/{stats['total']} = {stats['correct'] / stats['total']:.1%}")
    if len(by_split) > 1 or (len(by_split) == 1 and "all" not in by_split):
        for sp, stats in by_split.items():
            print(f"  split={sp}: {stats['correct']}/{stats['total']} = {stats['correct'] / stats['total']:.1%}")

    analyze_thresholds(all_rows)


# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="mode", required=True)

    sub.add_parser("record", help="live mic test through the full pipeline")

    batch_parser = sub.add_parser("batch", help="text-only Laya accuracy test from a CSV")
    batch_parser.add_argument("csv_path", help="path to a CSV with phrase,expected_category,language columns")
    batch_parser.add_argument(
        "--model",
        default=None,
        help="force a specific checkpoint (e.g. typed-decisions) instead of the router's auto choice",
    )
    batch_parser.add_argument(
        "--split",
        default=None,
        help="only score rows with this split value (e.g. train or held_out_eval); "
        "defaults to all rows. Supports the split column in synthetic_dataset_raw.csv; "
        "CSVs without a split column report split=all.",
    )

    batch_parser.add_argument(
        "--quiet",
        action="store_true",
        help="print only the summary (overall, by language/split, gating), not one line per phrase.",
    )
    batch_parser.add_argument(
        "--no-override",
        action="store_true",
        help="disable the deterministic parle-plus-fort override (raw model scores only).",
    )

    args = parser.parse_args()

    if args.mode == "record":
        run_record_mode()
    elif args.mode == "batch":
        run_batch_mode(args.csv_path, model=args.model, split=args.split, quiet=args.quiet,
                       use_override=not args.no_override)


if __name__ == "__main__":
    main()
