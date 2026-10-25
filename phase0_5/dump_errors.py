#!/usr/bin/env python3
"""Dump fine-tuned model's confident mistakes for pattern analysis.

Re-runs held_out_eval through the fine-tuned Agent and writes every row with
confidence >= --threshold AND wrong prediction, so a human can judge whether
the residual errors cluster (fixable with data) or scatter (noise).

Usage (Colab, same session as training — model dir still on disk):
    python dump_errors.py --model-dir laya_multilingual_nestclock \
        --csv synthetic_dataset_raw.csv --threshold 0.5 --out confident_errors.csv
"""
import argparse
import csv

import laya

from eval_finetuned import QUESTIONS

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--csv", default="synthetic_dataset_raw.csv")
    ap.add_argument("--split", default="held_out_eval")
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--out", default="confident_errors.csv")
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()

    agent = laya.Agent(args.model_dir, device=args.device)
    bad = []
    with open(args.csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("split", "all") != args.split:
                continue
            res = agent.predict({"text": row["phrase"]}, QUESTIONS)
            ans = res["answers"] if "answers" in res else res
            cat = ans["category"]
            probs = cat.get("probabilities", {})
            conf = float(cat.get("confidence",
                                 max(probs.values()) if probs else 0.0))
            if conf >= args.threshold and cat["choice"] != row["expected_category"]:
                bad.append({"phrase": row["phrase"], "language": row.get("language", "?"),
                            "expected": row["expected_category"], "got": cat["choice"],
                            "confidence": round(conf, 4)})

    bad.sort(key=lambda r: -r["confidence"])
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["phrase", "language", "expected", "got", "confidence"])
        w.writeheader()
        w.writerows(bad)
    print(f"{len(bad)} rows with conf >= {args.threshold} AND wrong -> {args.out}")
    for r in bad:
        print(f"  {r['confidence']:.2f} [{r['language']}] {r['phrase'][:60]!r} "
              f"expected={r['expected']} got={r['got']}")


if __name__ == "__main__":
    main()
