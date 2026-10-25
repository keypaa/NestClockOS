#!/usr/bin/env python3
"""NestClockOS Phase 0.5 — single-GPU (Colab T4) RLCD fine-tune of laya-multilingual.

Single-GPU port of Laya's reference 2xT4 DDP script from
laya_finetune_typed_decisions_2xT4_kaggle.ipynb (train_ddp.py). Cherry-picked
per spec Section 5: RLCD loop structure, hyperparameter defaults, calibration
temperature fitting. NOT reused: reference dataset, schema, English-only
assumptions (base here is mmBERT-base multilingual, same repo file layout).

Deviations from the reference (all deliberate, all noted):
- No DDP/torchrun: spec Section 5 says start with a single Colab T4. The base
  checkpoint's own config records training.world_size=1, so single-GPU is the
  native regime, not a downgrade.
- GRAD_ACCUM 8 (ref: 4 over 2 GPUs) with MICRO_BATCH 8 keeps the identical
  effective batch of 64 sequences (8*1*8 == 8*2*4).
- fp16 autocast (ref-identical): T4 (sm75) has no bf16 support, so the config's
  amp_dtype=bf16 is NOT used; autocast dtype is hardcoded to float16.
- loss = loss_rl + 1.0 * loss_ce is the REFERENCE's own term, kept verbatim.
  It is guidance inside the RL loop, not a separate SFT phase — spec Section 2
  forbids SFT-first, which this is not. Flagged explicitly so the term is not
  mistaken for an added supervised phase.

Usage (Colab, GPU runtime):
    python prep_items.py --csv synthetic_dataset_raw.csv --out train_items.pt
    python train_single_t4.py <model_dir> <output_dir> --items train_items.pt
where <model_dir> is the snapshot_download dir of convaiinnovations/laya-multilingual
(see runbook; prep prints it, or pass --model-id to auto-download here).
"""
import argparse
import json
import os
import random
import time

import torch
from safetensors.torch import load_file, save_file
from transformers import AutoTokenizer
from huggingface_hub import snapshot_download

from laya.agent import _fix_tokenizer_config
from laya.common import build_model, proper_reward


def collate_train_batch(items, pad_id):
    n, L = len(items), max(len(it["ids"]) for it in items)
    kmax = max(len(it["markers"]) for it in items)
    ids = torch.full((n, L), pad_id, dtype=torch.long)
    att = torch.zeros((n, L), dtype=torch.long)
    mpos = torch.zeros((n, kmax), dtype=torch.long)
    mmask = torch.zeros((n, kmax), dtype=torch.bool)
    target = torch.zeros((n, kmax), dtype=torch.float32)
    for i, it in enumerate(items):
        ids[i, : len(it["ids"])] = torch.tensor(it["ids"])
        att[i, : len(it["ids"])] = 1
        k = len(it["markers"])
        mpos[i, :k] = torch.tensor(it["markers"])
        mmask[i, :k] = True
        target[i, : len(it["target"])] = torch.tensor(it["target"], dtype=torch.float32)
    return {
        "input_ids": ids,
        "attention_mask": att,
        "marker_pos": mpos,
        "marker_mask": mmask,
        "target": target,
        "qtype": torch.tensor([it["qtype"] for it in items]),
        "label": torch.tensor([it["label"] for it in items]),
    }


def fit_one_temp(sel):
    if len(sel) < 10:
        return 1.0
    kmax = max(len(z) for z, _ in sel)
    Z = torch.full((len(sel), kmax), -1e4)
    T = torch.zeros((len(sel), kmax))
    for i, (z, t) in enumerate(sel):
        Z[i, :len(z)] = torch.tensor(z)
        T[i, :len(t)] = torch.tensor(t, dtype=torch.float32)
    log_t = torch.zeros(1, requires_grad=True)
    opt = torch.optim.LBFGS([log_t], lr=0.1, max_iter=100)

    def closure():
        opt.zero_grad()
        loss = -(T * torch.log_softmax(Z / log_t.exp(), -1)).sum(-1).mean()
        loss.backward()
        return loss

    opt.step(closure)
    return float(torch.clamp(log_t.exp(), 0.1, 10.0).item())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model_dir", help="snapshot dir of convaiinnovations/laya-multilingual")
    ap.add_argument("output_dir")
    ap.add_argument("--items", default="train_items.pt")
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--micro-batch", type=int, default=8)
    ap.add_argument("--grad-accum", type=int, default=8)  # 8*1*8 = 64 = ref 8*2*4
    ap.add_argument("--group-size", type=int, default=4)
    ap.add_argument("--lr-encoder", type=float, default=2.5e-5)
    ap.add_argument("--lr-head", type=float, default=1.0e-4)
    ap.add_argument("--sigma-start", type=float, default=0.4)
    ap.add_argument("--sigma-end", type=float, default=0.1)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--uniform-holdout", action="store_true",
                    help="force the legacy uniform-shuffle holdout (seed 20260922) "
                    "instead of the stratified one. Run-1 reproduction mode only: "
                    "recreates run 1's training recipe on run-1 data. NOT for new runs.")
    args = ap.parse_args()

    assert torch.cuda.is_available(), "no CUDA — use a Colab GPU runtime"
    device = torch.device("cuda", 0)
    print(f"GPU: {torch.cuda.get_device_properties(0).name}")

    with open(os.path.join(args.model_dir, "rl_agent_config.json")) as f:
        cfg = json.load(f)
    cfg["gradient_checkpointing"] = True
    cfg["max_tokens_per_batch"] = 4096
    cfg["max_len"] = 1024
    cfg["head_max_len"] = 256

    tok = AutoTokenizer.from_pretrained(os.path.join(args.model_dir, "tokenizer"))
    model = build_model(cfg, encoder_dir=os.path.join(args.model_dir, "encoder"))

    weights = load_file(os.path.join(args.model_dir, "model.safetensors"))
    model.load_state_dict(weights, strict=True)

    model.encoder.gradient_checkpointing_enable(
        gradient_checkpointing_kwargs={"use_reentrant": False})
    model.head_checkpointing = True
    model.to(device)
    model.train()

    all_items = torch.load(args.items, weights_only=False)

    # Calibration slice held out BEFORE training (reference verbatim rationale):
    # temperatures fitted on already-trained-on items measure fit, not
    # calibration — the model is near-certain there, so the optimiser returns
    # a degenerate scale.
    # Run-2 change (spec Addendum item 2): the holdout is STRATIFIED by
    # language×category to mirror train's mix. Run 1's uniform shuffle
    # under-sampled English by ~8pts (27% vs 35%) in the fitted rows.
    # Fixed seed => reproducible holdout. Legacy items without lang/cat
    # metadata fall back to the uniform path.
    CALIB_MAX = 400
    n_calib = min(CALIB_MAX, len(all_items) // 10)
    if not args.uniform_holdout and all("lang" in it and "cat" in it for it in all_items):
        import hashlib
        cells = {}
        for i, it in enumerate(all_items):
            cells.setdefault((it["lang"], it["cat"]), []).append(i)
        quotas, rema = {}, n_calib
        for cell, idxs in cells.items():
            q = n_calib * len(idxs) // len(all_items)
            quotas[cell] = q
            rema -= q
        for cell in sorted(cells, key=lambda c: (n_calib * len(cells[c]) % len(all_items), c), reverse=True)[:max(0, rema)]:
            quotas[cell] += 1
        calib_idx = set()
        for cell, idxs in cells.items():
            seed = 20260922 + int(hashlib.md5(repr(cell).encode()).hexdigest()[:8], 16)
            order = list(idxs)
            random.Random(seed).shuffle(order)
            calib_idx.update(order[:quotas[cell]])
        calib_items = [all_items[i] for i in sorted(calib_idx)]
        train_items = [all_items[i] for i in range(len(all_items)) if i not in calib_idx]
        from collections import Counter
        print("calib mix:", dict(Counter((it["lang"], it["cat"]) for it in calib_items)))
    else:
        order = list(range(len(all_items)))
        random.Random(20260922).shuffle(order)
        calib_items = [all_items[i] for i in sorted(order[:n_calib])]
        train_items = [all_items[i] for i in sorted(order[n_calib:])]

    EPOCHS = args.epochs
    MICRO_BATCH = args.micro_batch
    GRAD_ACCUM = args.grad_accum
    GROUP_SIZE = args.group_size

    enc_params = [p for n, p in model.named_parameters() if "encoder." in n]
    head_params = [p for n, p in model.named_parameters() if "encoder." not in n]
    optimizer = torch.optim.AdamW([
        {"params": enc_params, "lr": args.lr_encoder},
        {"params": head_params, "lr": args.lr_head},
    ], weight_decay=0.01)

    total_updates = (len(train_items) // (MICRO_BATCH * GRAD_ACCUM)) * EPOCHS
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=max(1, total_updates), eta_min=1e-6)
    scaler = torch.amp.GradScaler("cuda", enabled=True)

    print(f"Training: {len(train_items)} items ({len(calib_items)} held out for "
          f"calibration) | eff batch {MICRO_BATCH * GRAD_ACCUM} | {EPOCHS} epochs | "
          f"~{total_updates} updates")
    t0 = time.time()

    for epoch in range(EPOCHS):
        random.seed(args.seed + epoch)
        random.shuffle(train_items)
        epoch_loss, n_batches = 0.0, 0
        optimizer.zero_grad(set_to_none=True)
        accum_step = 0

        progress = epoch / max(1, EPOCHS - 1)
        sigma = args.sigma_start + (args.sigma_end - args.sigma_start) * progress

        for b_idx in range(0, len(train_items), MICRO_BATCH):
            chunk = train_items[b_idx:b_idx + MICRO_BATCH]
            if not chunk:
                continue
            batch = collate_train_batch(chunk, tok.pad_token_id)

            with torch.autocast("cuda", dtype=torch.float16):
                logits, act = model(
                    batch["input_ids"].to(device),
                    batch["attention_mask"].to(device),
                    batch["marker_pos"].to(device),
                    batch["marker_mask"].to(device),
                    batch["qtype"].to(device),
                )

            logits = logits.float()
            mask = batch["marker_mask"].to(device)
            k = mask.sum(-1, keepdim=True).float()
            target = batch["target"].to(device)

            # 1. Sample G noisy logit distributions with zero-mean projection
            eps = torch.randn((GROUP_SIZE,) + logits.shape, device=device) * sigma * mask
            eps = (eps - eps.sum(-1, keepdim=True) / k) * mask
            z = logits.detach().unsqueeze(0) + eps
            q = torch.softmax(z.masked_fill(~mask, -1e4), -1)

            # 2. Proper-scoring reward (reference defaults), GRPO-style baseline
            with torch.no_grad():
                r = proper_reward(q, target.unsqueeze(0),
                                  batch["qtype"].to(device), mask,
                                  w_sph=0.75, w_rps=1.0)
                adv = r - r.mean(0, keepdim=True)
                adv = adv / (adv.std() + 1e-6)

            # 3. Policy-gradient loss + reference's own 1.0 soft-CE guidance
            #    (part of Laya's loop, NOT an SFT phase — see module docstring)
            logp = -(((z - logits.unsqueeze(0)) ** 2) * mask).sum(-1) / (2 * sigma ** 2)
            loss_rl = -(adv * logp).mean()
            loss_ce = -(target * torch.log_softmax(
                logits.masked_fill(~mask, -1e4), -1)).sum(-1).mean()
            loss = (loss_rl + 1.0 * loss_ce) / GRAD_ACCUM + 0.0 * act.sum()

            scaler.scale(loss).backward()
            accum_step += 1

            if accum_step % GRAD_ACCUM == 0 or (b_idx + MICRO_BATCH) >= len(train_items):
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scaler.step(optimizer)
                scaler.update()
                scheduler.step()
                optimizer.zero_grad(set_to_none=True)

            epoch_loss += loss.item() * GRAD_ACCUM
            n_batches += 1

            if (n_batches % 25) == 0:
                print(f"  Epoch {epoch+1}/{EPOCHS} | Step {n_batches} | "
                      f"Loss: {loss.item()*GRAD_ACCUM:.4f} | "
                      f"Reward: {r.mean().item():.3f} | "
                      f"LR: {scheduler.get_last_lr()[0]:.2e}", flush=True)

        print(f"=== Epoch {epoch+1}/{EPOCHS} done in {time.time()-t0:.1f}s | "
              f"Avg loss: {epoch_loss/max(1, n_batches):.4f} ===", flush=True)

        ckpt_dir = os.path.join(args.output_dir, "checkpoint_latest")
        os.makedirs(ckpt_dir, exist_ok=True)
        ckpt_sd = {k: v.half().contiguous().cpu() for k, v in model.state_dict().items()}
        save_file(ckpt_sd, os.path.join(ckpt_dir, "model.safetensors"))
        model.encoder.config.save_pretrained(os.path.join(ckpt_dir, "encoder"))
        tok.save_pretrained(os.path.join(ckpt_dir, "tokenizer"))
        with open(os.path.join(ckpt_dir, "checkpoint_meta.json"), "w") as f:
            json.dump({"epoch": epoch + 1, "total_epochs": EPOCHS,
                       "avg_loss": epoch_loss / max(1, n_batches)}, f, indent=2)
        print(f"  Rolling checkpoint -> {ckpt_dir}", flush=True)

    # Post-training temperature calibration (rank-0 branch, micro-batched)
    print("\nFitting post-training calibration temperatures...")
    del optimizer, scaler, scheduler
    torch.cuda.empty_cache()
    model.eval()
    calib_preds = []
    with torch.no_grad():
        for c_idx in range(0, len(calib_items), 16):
            c_chunk = calib_items[c_idx:c_idx + 16]
            cb = collate_train_batch(c_chunk, tok.pad_token_id)
            with torch.autocast("cuda", dtype=torch.float16):
                l_sub, _ = model(
                    cb["input_ids"].to(device),
                    cb["attention_mask"].to(device),
                    cb["marker_pos"].to(device),
                    cb["marker_mask"].to(device),
                    cb["qtype"].to(device),
                )
            l_np = l_sub.float().cpu().numpy()
            for r, it in enumerate(c_chunk):
                k = len(it["markers"])
                calib_preds.append((it["qtype"], l_np[r, :k], it["target"]))

    fitted_temps = [1.2, 1.2, 1.2]
    try:
        for qt in range(3):
            sel = [(z, t) for q_type, z, t in calib_preds if q_type == qt]
            if sel:
                fitted_temps[qt] = fit_one_temp(sel)
        print("Fitted temperatures (choice, score, noul):",
              [round(t, 3) for t in fitted_temps])
    except Exception as e:
        print("Temperature fitting fallback:", e)
    os.makedirs(args.output_dir, exist_ok=True)
    sd = {k: v.half().contiguous().cpu() for k, v in model.state_dict().items()}
    save_file(sd, os.path.join(args.output_dir, "model.safetensors"))
    model.encoder.config.save_pretrained(os.path.join(args.output_dir, "encoder"))
    tok.save_pretrained(os.path.join(args.output_dir, "tokenizer"))

    cfg["fine_tuned"] = True
    cfg["model_name"] = "laya-multilingual-nestclock"
    cfg["temperature"] = fitted_temps
    cfg.pop("temperature_by_options", None)  # per-type fit; stale buckets would hide it
    with open(os.path.join(args.output_dir, "rl_agent_config.json"), "w") as f:
        json.dump(cfg, f, indent=2)
    print(f"Saved fine-tuned model -> {args.output_dir}")


if __name__ == "__main__":
    main()
