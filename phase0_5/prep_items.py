#!/usr/bin/env python3
"""NestClockOS Phase 0.5 — build RLCD training items from the verified synthetic set.

Reads synthetic_dataset_raw.csv (split=train), emits tokenized items for
train_single_t4.py. Category question ONLY (choice, 5 options, one-hot target).

Why no is_complete items: the verified dataset carries no is_complete labels
(spec Section 4's CSV format is phrase,expected_category,language,split), and
inventing them post-verification would violate Section 4's "no synthetic
example enters training without passing both stages". is_complete stays
zero-shot; no acceptance criterion judges it. Flagged in the training handoff.

Criteria below are VERBATIM from phase0_pipeline_test.py ROUTING_QUESTIONS.
Do not edit here — edit there and re-verify before/after comparability breaks.

Usage (Colab):
    python prep_items.py --csv synthetic_dataset_raw.csv --out train_items.pt
"""
import argparse
import csv
import json
import os

import torch
from transformers import AutoTokenizer
from huggingface_hub import snapshot_download

# --- import path: laya installed via pip in Colab ---
from laya.agent import _fix_tokenizer_config
from laya.common import build_sequence, render_options, QTYPES

MODEL_ID = "convaiinnovations/laya-multilingual"

# VERBATIM from phase0_pipeline_test.py ROUTING_QUESTIONS (category only).
CATEGORY_INSTRUCTIONS = "What kind of request is this smart-clock command?"
CATEGORY_CRITERIA = {
    "alarm": "setting, changing, or cancelling an alarm",
    "timer": "setting, checking, or cancelling a countdown timer",
    "music": "playing, pausing, skipping, or controlling Spotify playback, including turning the volume up or down",
    "weather": "asking about current or forecast weather",
    "fallback": "anything that is not directly an alarm, timer, music, or weather command — open-ended questions, general conversation, unclear or incomplete speech, or anything else",
}
CATEGORY_KEYS = list(CATEGORY_CRITERIA.keys())  # fixed order; eval uses the same dict


def build_training_item(phrase, expected, language, tok, max_len, head_max_len):
    target = [1.0 if k == expected else 0.0 for k in CATEGORY_KEYS]
    label = CATEGORY_KEYS.index(expected)
    k = len(render_options({"t": "choice", "crit": CATEGORY_CRITERIA}))
    # state shape {"text": phrase} is byte-identical to inference
    # (phase0_pipeline_test.classify -> router.predict({"text": text}, ...)).
    seq, markers = build_sequence(
        tok, {"text": phrase},
        {"t": "choice", "ins": CATEGORY_INSTRUCTIONS, "crit": CATEGORY_CRITERIA},
        max_len, head_max_len,
    )
    if len(markers) != k:
        return None
    return {
        "ids": seq,
        "markers": markers,
        "qtype": QTYPES["choice"],
        "target": target,
        "label": label,
        # Stratification metadata for the calibration holdout (train_single_t4.py).
        # Ignored by collate; lets the holdout mirror train's language×category mix
        # instead of a uniform shuffle (Run-1 holdout under-sampled English by 8pts).
        "lang": language,
        "cat": expected,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="synthetic_dataset_raw.csv")
    ap.add_argument("--out", default="train_items.pt")
    ap.add_argument("--model-id", default=MODEL_ID)
    ap.add_argument("--split", default="train")
    args = ap.parse_args()

    print(f"Fetching tokenizer and config from {args.model_id}...")
    model_dir = snapshot_download(args.model_id)
    _fix_tokenizer_config(model_dir)

    tok = AutoTokenizer.from_pretrained(os.path.join(model_dir, "tokenizer"))
    with open(os.path.join(model_dir, "rl_agent_config.json")) as f:
        cfg = json.load(f)
    max_len, head_max_len = cfg["max_len"], cfg["head_max_len"]
    print(f"max_len={max_len} head_max_len={head_max_len} "
          f"qtype_choice={QTYPES['choice']}")

    items, skipped, per_cat = [], 0, {k: 0 for k in CATEGORY_KEYS}
    with open(args.csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("split", "all") != args.split:
                continue
            it = build_training_item(
                row["phrase"], row["expected_category"], row.get("language", "?"),
                tok, max_len, head_max_len)
            if it is None:
                skipped += 1
                continue
            items.append(it)
            per_cat[row["expected_category"]] += 1

    print(f"Built {len(items)} items (skipped={skipped}) from split={args.split}")
    print("per-category:", per_cat)
    assert len(items) > 0 and skipped == 0, "unexpected skips — inspect"
    torch.save(items, args.out)
    print(f"Saved {args.out}")


if __name__ == "__main__":
    main()
