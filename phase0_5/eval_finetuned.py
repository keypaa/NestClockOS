#!/usr/bin/env python3
"""NestClockOS Phase 0.5 — evaluate a fine-tuned checkpoint on held_out_eval.

Scores the fine-tuned laya-multilingual Agent against Section 1's acceptance
criteria and prints the Tier mapping. One run, report numbers, stop — the
human decides the tier, this script only computes the mapping.

Criteria (spec Section 1, revised bars):
- Tier 1: FR >= 85% AND EN >= 82% (fine-tuned multilingual, forced --model)
- Tier 2: FR >= 80%
- local_WRONG == 0 at some threshold <= 0.5, per traffic slice
  (en slice ~= english-checkpoint traffic, fr+mixed slice ~= multilingual
  traffic under Tier 2; plus overall)
- Post-temperature-scaling ECE <= 0.15 on held_out_eval
- Failure clusters individually >= 80%%: (a) FR idiomatic status checks,
  (b) volume commands both languages

Cluster regexes below are VERBATIM from synthetic_gen_script.py (the
generator/verifier's own patterns) — provenance, not duplication by accident.

Usage (Colab, after train_single_t4.py):
    python eval_finetuned.py --model-dir laya_multilingual_nestclock \
        --csv synthetic_dataset_raw.csv --split held_out_eval --out eval_report.json
"""
import argparse
import csv
import json
import re

import numpy as np

import laya
from laya.common import ece_score

# VERBATIM from phase0_pipeline_test.py ROUTING_QUESTIONS (category only).
QUESTIONS = {
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
}
CAT_KEYS = list(QUESTIONS["category"]["criteria"].keys())

# VERBATIM from synthetic_gen_script.py (cluster definitions the data was
# verified against — reusing them keeps eval consistent with verification).
IDIOM_RE = re.compile(
    r"(o[uù]\s+en\s+est|en\s+est[\s-]*o[uù]|ça\s+en\s+est\s+o[uù]|ca\s+en\s+est\s+ou|"
    r"il\s+en\s+est\s+o[uù]|on\s+en\s+est|o[uù]\s+ça\s+en\s+est|ou\s+ca\s+en\s+est|"
    r"ça\s+en\s+est\s+rest[eé]|combien\s+de\s+temps\s+restant|il\s+reste\s+combien|"
    r"reste\s+combien|combien\s+il\s+reste|c['’]est\s+o[uù])",
    re.IGNORECASE)
VOLUME_RE = re.compile(
    r"(turn\s+\S*\s*(up|down)|volume|louder|quieter|\bmute\b|unmute|crank|pump\s+it|"
    r"raise the sound|lower the sound|soften|blast it|dial the|silence( the speaker)?|"
    r"notch|bring the (sound|volume)|make it (louder|quieter)|monte|baisse|"
    r"augmente|diminue|plus fort|moins fort|coupe le son|remets le son|"
    r"pousse le son|remonte|redescends|trop fort|au max|au maximum|au minimum|"
    r"moiti[eé]|à moitié|a moitie|tout bas|mute le son|mets le (son|volume)|"
    r"\bfond\b|\bdix\b|\bvingt\b|z[eé]ro)",
    re.IGNORECASE)

THRESHOLDS = (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)


def gating(rows, thresholds=THRESHOLDS):
    """rows: list of (confidence, ok). Returns {t: {local_ok, local_WRONG, ...}}."""
    out = {}
    for t in thresholds:
        out[t] = {
            "local_ok": sum(1 for c, ok in rows if c >= t and ok),
            "local_WRONG": sum(1 for c, ok in rows if c >= t and not ok),
            "deferred_ok": sum(1 for c, ok in rows if c < t and ok),
            "deferred_wrong": sum(1 for c, ok in rows if c < t and not ok),
        }
    return out


def safe_threshold(g):
    ok = [t for t in THRESHOLDS if g[t]["local_WRONG"] == 0]
    return min(ok) if ok else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--csv", default="synthetic_dataset_raw.csv")
    ap.add_argument("--split", default="held_out_eval")
    ap.add_argument("--out", default="eval_report.json")
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()

    agent = laya.Agent(args.model_dir, device=args.device)

    rows = []
    with open(args.csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("split", "all") != args.split:
                continue
            res = agent.predict({"text": row["phrase"]}, QUESTIONS)
            ans = res["answers"] if "answers" in res else res
            cat = ans["category"]
            got = cat["choice"]
            probs = cat.get("probabilities", {})
            conf = float(cat.get("confidence",
                                 max(probs.values()) if probs else 0.0))
            ok = got == row["expected_category"]
            rows.append({"phrase": row["phrase"], "lang": row.get("language", "?"),
                         "expected": row["expected_category"], "got": got,
                         "conf": conf, "ok": ok})

    def acc(sel):
        s = [r for r in rows if sel(r)]
        return (sum(r["ok"] for r in s), len(s),
                sum(r["ok"] for r in s) / len(s) if s else float("nan"))

    en = acc(lambda r: r["lang"] == "en")
    fr = acc(lambda r: r["lang"] == "fr")
    mx = acc(lambda r: r["lang"] == "mixed")
    allr = acc(lambda r: True)
    idiom = acc(lambda r: r["lang"] == "fr" and IDIOM_RE.search(r["phrase"]))
    vol = acc(lambda r: VOLUME_RE.search(r["phrase"]))

    confs = np.array([r["conf"] for r in rows])
    oks = np.array([float(r["ok"]) for r in rows])
    ece = ece_score(confs, oks)

    g_all = gating([(r["conf"], r["ok"]) for r in rows])
    g_en = gating([(r["conf"], r["ok"]) for r in rows if r["lang"] == "en"])
    g_frmx = gating([(r["conf"], r["ok"]) for r in rows if r["lang"] != "en"])
    safe = {"overall": safe_threshold(g_all), "en_slice": safe_threshold(g_en),
            "fr_mixed_slice": safe_threshold(g_frmx)}

    tier = ("Tier 1 (unify)" if fr[2] >= 0.85 and en[2] >= 0.82
            else "Tier 2 (keep two)" if fr[2] >= 0.80 else "Tier 3 (manual)")

    print(f"=== held_out_eval (n={len(rows)}) ===")
    print(f"EN: {en[0]}/{en[1]} = {en[2]:.1%}  (baseline 81.1%, Tier-1 bar 82%)")
    print(f"FR: {fr[0]}/{fr[1]} = {fr[2]:.1%}  (baseline 56.0%, Tier-1 bar 85% / Tier-2 bar 80%)")
    print(f"mixed: {mx[0]}/{mx[1]} = {mx[2]:.1%}   overall: {allr[0]}/{allr[1]} = {allr[2]:.1%}")
    print(f"(a) FR idioms: {idiom[0]}/{idiom[1]} = {idiom[2]:.1%}  (bar 80%)")
    print(f"(b) volume: {vol[0]}/{vol[1]} = {vol[2]:.1%}  (bar 80%)")
    print(f"ECE (post-temp): {ece:.3f}  (bar <= 0.15)")
    print(f"safe thresholds (local_WRONG==0): {safe}  (bar: exists at <= 0.5)")
    print(f"mapping: {tier}")
    print("\ngating (overall):")
    for t in THRESHOLDS:
        g = g_all[t]
        print(f"  {t}: local_ok={g['local_ok']} local_WRONG={g['local_WRONG']} "
              f"deferred_ok={g['deferred_ok']} deferred_wrong={g['deferred_wrong']}")

    report = {
        "n": len(rows),
        "en": {"correct": en[0], "total": en[1], "acc": en[2]},
        "fr": {"correct": fr[0], "total": fr[1], "acc": fr[2]},
        "mixed": {"correct": mx[0], "total": mx[1], "acc": mx[2]},
        "overall": {"correct": allr[0], "total": allr[1], "acc": allr[2]},
        "cluster_a_fr_idioms": {"correct": idiom[0], "total": idiom[1], "acc": idiom[2]},
        "cluster_b_volume": {"correct": vol[0], "total": vol[1], "acc": vol[2]},
        "ece": ece,
        "safe_thresholds": safe,
        "tier_mapping": tier,
    }
    with open(args.out, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
