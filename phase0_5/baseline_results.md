# NestClockOS Phase 0.5 — Pre-fine-tune baselines (held_out_eval, n=500)

Dataset: `synthetic_dataset_raw.csv` @ split=held_out_eval (fr 225 / en 175 / mixed 100).
Tool: `phase0_pipeline_test.py batch --split held_out_eval [--model X] [--quiet]`.
Note: laya logs `invalid temperatures → using 0.5, treat confidence as uncalibrated` on these runs.

## 1. Forced multilingual (the comparison point post-training judgments use)
`--model multilingual` (local run)
- en (EN_baseline_multilingual): 142/175 = 81.1%
- fr (FR_baseline_multilingual): 126/225 = 56.0%
- mixed: 78/100 = 78.0%
- overall: 346/500 = 69.2%
- gating: local_WRONG@0.9 = 21 (no safe threshold)

## 2. Forced english (Tier-1 reference on the same eval set)
`--model english` (local run)
- en: 147/175 = 84.0%
- overall (all rows forced through english): 338/500 = 67.6%
- fr/mixed under forced-english: not captured (off-label; no tier routes French to the english checkpoint)

## 3. Default router (honest system-today, misrouting included)
no `--model` (Colab run)
- en: 147/175 = 84.0%
- fr: 124/225 = 55.1%
- mixed: 72/100 = 72.0%
- overall: 343/500 = 68.6%
- gating: local_WRONG@0.9 = 8 (no safe threshold ≤ 0.9)

## Readout
- Misrouting cost on this set is small: fr 56.0% (forced multilingual) vs 55.1% (router).
  (Phase 0's hand set showed a bigger drop, 61.8% → 50.0% — the synthetic set behaves slightly differently here.)
- English rows auto-route to the english checkpoint already (router en 84.0% == forced-english en 84.0%).

## FLAG back (frozen-spec §1 Tier-1 bar vs new reference) — RESOLVED by spec revision
Spec originally set Tier-1 English bar at ≥88% ("~2 points below 90.7%").
Measured on the actual judgment set, the dedicated checkpoint scored 84.0%.
Spec now revises Tier-1 to French ≥ 85% AND English ≥ 82%, preserving the
"~2 points below the reference, measured on the same set" intent.
Post-training judgment uses: FR ≥ 85% / EN ≥ 82% (Tier 1), FR ≥ 80% (Tier 2).
