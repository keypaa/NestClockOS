# NestClockOS Phase 0.5 — Colab T4 runbook (training + evaluation)

One run, report numbers, stop for a human decision (spec Section 7).
Files to upload to Colab (all in this repo):
`prep_items.py`, `train_single_t4.py`, `eval_finetuned.py`,
`synthetic_dataset_raw.csv` (verified PASS data: 2000 train / 500 held_out_eval).

## RUN 2 (spec Addendum) — deltas vs Run 1

Re-upload (changed since Run 2): `synthetic_dataset_raw.csv` (L2601→fallback,
9 song-ID train rows→fallback, +40 verified hard negatives → 2190 train /
500 eval), `train_single_t4.py` (unchanged — stratified holdout + same
hyperparams). New output dir `laya_multilingual_nestclock_r3`.
Expect ~2190 prep items, 219-row stratified holdout.
Scores against the direction-based criterion (zero-tolerance fallback→action,
documented residual for action→fallback) — `eval_finetuned.py` prints the
classic table; classify the residual by DIRECTION when reporting.

Re-upload (changed since Run 1): `prep_items.py` (lang/cat metadata),
`train_single_t4.py` (**stratified** calib holdout, Addendum item 2),
`synthetic_dataset_raw.csv` (3 corrected eval labels + 150 verified
anchor-free train rows → 2150 train / 500 eval).
Same hyperparameters otherwise (Addendum item 3). New output dir
`laya_multilingual_nestclock_r2` (keeps run-1 weights intact for comparison).
Cells below are the full sequence; only the noted lines differ from Run 1.
Corrected run-1 reference (analytical rescore, predictions known): overall
96.8%, EN 97.7%, FR 94.7%, local_WRONG@0.5 = 14, @0.9 = 5.

## RUN 3 (spec Addendum 2) — deltas vs Run 2

Re-upload (changed since Run 2): `synthetic_dataset_raw.csv` (L2601→fallback,
9 song-ID train rows→fallback, +40 verified hard negatives → 2190 train /
500 eval). `train_single_t4.py` unchanged (stratified holdout, same
hyperparams). New output dir `laya_multilingual_nestclock_r3`; eval writes
`eval_report_r3.json`. Expect ~2190 prep items, 219-row stratified holdout
(script prints its `calib mix` — check it mirrors train).
Score against the DIRECTION-based criterion (zero-tolerance fallback→action,
documented residual for action→fallback): from the eval table + a
`dump_errors.py --threshold 0.0` full-error dump, classify every residual
error by direction when reporting. Step 4 (passe rows) SKIPPED per Addendum 2
— run-2 weights are gone so persistence is unconfirmed, and run-3's own eval
re-checks all 4 passe rows anyway.

## Cell 1 — GPU check (single T4 per spec Section 5)

```python
!nvidia-smi --query-gpu=name,memory.total --format=csv
import torch
assert torch.cuda.is_available(), "need a GPU runtime (Runtime > Change runtime type > T4 GPU)"
print(torch.cuda.get_device_properties(0).name)
```

## Cell 2 — install

```
!pip install -q "laya>=0.1.6" "transformers>=4.48.0" safetensors huggingface_hub pandas scipy
```

## Cell 3 — download base (verifies Section 3 checkpoint + file layout)

```python
from huggingface_hub import snapshot_download
model_dir = snapshot_download("convaiinnovations/laya-multilingual")
print(model_dir)
```

Expected: repo contains `encoder/config.json` (mmBERT-base), `model.safetensors`,
`rl_agent_config.json`, `tokenizer/`. Training script reads `model_dir` from this output.

## Cell 4 — build training items (train split only, category/one-hot)

```
!python prep_items.py --csv synthetic_dataset_raw.csv --out train_items.pt
```

Expected: ~2150 items (skipped=0). `is_complete` is
intentionally NOT trained (no labels in the verified set; inventing them would
violate Section 4 — approved, backlogged).

## Cell 5 — train (single T4, RLCD loop + hyperparams verbatim from Laya's reference)

```
!python train_single_t4.py "$model_dir" laya_multilingual_nestclock_r2 --items train_items.pt
```

What it does: 4 epochs, eff. batch 64 (8×8, == reference 8×2×4), GRPO group 4,
LR 2.5e-5 encoder / 1e-4 head, sigma 0.4→0.1, `proper_reward` w_sph=0.75,
loss = RL + 1.0×CE-guidance (the reference's own term, not an added SFT phase),
215-item **stratified** calibration holdout (language×category mirror of train),
per-qtype temperature fit, rolling
checkpoint per epoch (`laya_multilingual_nestclock_r2/checkpoint_latest/`).
Time estimate: minutes (ref: 6000 decisions in ~4–6 min on 2×T4; here 2000
items on 1×T4). T4 has no bf16 — script uses fp16 autocast explicitly.
If OOM: lower `--micro-batch` to 4 and raise `--grad-accum` to 16 (same eff. batch).

## Cell 6 — evaluate on held_out_eval (spec Section 1 criteria)

```
!python eval_finetuned.py --model-dir laya_multilingual_nestclock_r2 --csv synthetic_dataset_raw.csv --out eval_report_r2.json
```

Report maps to: Tier 1 = FR ≥ 85% AND EN ≥ 82% · Tier 2 = FR ≥ 80% ·
`local_WRONG == 0` at some threshold ≤ 0.5 per slice · ECE ≤ 0.15 ·
clusters (a)/(b) ≥ 80% each.

## Cell 7 — hand back

Paste the full Cell 6 output + `eval_report_r2.json`, and note anything odd in
Cells 4–5 (loss/reward trace, fitted temperatures, printed calib mix). Then stop — no autonomous
re-runs. Also download `laya_multilingual_nestclock_r2/` (weights + config) so a
later subtask never needs retraining to re-evaluate (spec Section 8).

## Pre-training reference (for the after/before comparison)

| | en | fr | gating |
|---|---|---|---|
| forced multilingual (baseline) | 81.1% (142/175) | 56.0% (126/225) | local_WRONG@0.9 = 21 |
| forced english (Tier-1 ref) | 84.0% (147/175) | — | — |
| default router (system today) | 84.0% | 55.1% | local_WRONG@0.9 = 8 |
