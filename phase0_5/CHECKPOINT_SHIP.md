# Run-3 checkpoint — shipping manifest (Phase 0.5 close-out)

## What to download (from the run-3 Colab session, BEFORE it is wiped)

Directory: `laya_multilingual_nestclock_r3/` — the full output dir, containing:
- `model.safetensors` (fine-tuned weights, fp16)
- `encoder/` (mmBERT-base config)
- `tokenizer/`
- `rl_agent_config.json` (includes fitted calibration temperatures +
  `model_name: laya-multilingual-nestclock`; verify temps on download —
  run 3's exact fitted values were not pasted back, read them from this file)
- `checkpoint_latest/` (rolling checkpoint, same content as final)

## Provenance (exact recipe, reproducible)

- Base: `convaiinnovations/laya-multilingual` (mmBERT-base, 322M)
- Train data: `synthetic_dataset_raw.csv` @ split=train, 2190 rows
  (2000 base + 150 run-2 anchor-free augmentation + 40 run-3 hard negatives;
  10 train relabels: L2601 + 9 song-ID rows → fallback)
- Eval: same file @ split=held_out_eval, 500 rows (4 corrected labels:
  L1203, L2402, L2450, L2263)
- Loop/hyperparams: `train_single_t4.py` verbatim (RLCD, 4 epochs, eff. batch
  64, GRPO group 4, LR 2.5e-5/1e-4, σ 0.4→0.1, stratified calib holdout)
- Scripts at the pinned repo state accompanying this manifest
  (`prep_items.py`, `train_single_t4.py`, `eval_finetuned.py`,
  `dump_errors.py`, `test_override.py`)

## Recorded eval (held_out_eval, n=500)

Overall 476/500 = 95.2%, EN 171/175 = 96.6%, FR 209/225 = 92.9%,
mixed 98/100; clusters (a) 100% / (b) 97.4%; ECE 0.046.
Direction split: 1 fallback→action (parle-plus-fort, handled by the
deterministic override in `phase0_pipeline_test.py` — verify with
`test_override.py`) + 23 action→fallback (accepted residual, see
`french_syntax_residual.md`).

## Publishing (Colab cell, needs a write token)

```python
from huggingface_hub import HfApi
api = HfApi(token="hf_...")  # or Colab secret
api.create_repo("YOUR_USER/laya-multilingual-nestclock", exist_ok=True)
api.upload_folder(folder_path="laya_multilingual_nestclock_r3",
                  repo_id="YOUR_USER/laya-multilingual-nestclock")
```

Phase-1 consumption: load via `laya.Agent(repo_or_dir)` and keep the
parle-plus-fort override + destructive-action confirmation rule
(`phase1_design_notes.md`) in front of it — both are application-layer
guarantees, part of the shipped system, not optional extras.
