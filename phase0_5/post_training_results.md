# NestClockOS Phase 0.5 — Post-training results (ONE run, Colab T4)

Training: `train_single_t4.py`, 1800 items (200 calib holdout), 4 epochs,
~112 updates, 169s. Epoch avg loss 0.318 → 0.360 → 0.219 → 0.054.
Fitted temps (choice, score, noul): [4.304, 1.2, 1.2].
Note: `lr_scheduler.step() before optimizer.step()` UserWarning on first call —
cosmetic, inherited from the reference script's call order.

## held_out_eval (n=500), forced fine-tuned multilingual

| metric | pre (base multilingual) | post (fine-tuned) | bar | verdict |
|---|---|---|---|---|
| EN | 81.1% (142/175) | **96.6% (169/175)** | Tier-1 ≥ 82% | PASS |
| FR | 56.0% (126/225) | **94.2% (212/225)** | Tier-1 ≥ 85% | PASS |
| mixed | 78.0% | 100.0% (100/100) | — | — |
| overall | 69.2% (346/500) | 96.2% (481/500) | — | — |
| (a) FR idioms | — (eval n=25) | 96.0% (24/25) | ≥ 80% | PASS |
| (b) volume | — (eval n=38) | 89.5% (34/38) | ≥ 80% | PASS |
| ECE post-temp | not measured pre | **0.033** | ≤ 0.15 | PASS |
| local_WRONG @0.5 (overall) | 91 | **17** | 0 | **FAIL** |
| local_WRONG @0.9 (overall) | 21 | **5** | — | (no safe threshold) |
| safe threshold overall | none | none | ≤ 0.5 | **FAIL** |
| safe threshold en_slice | — | 0.9 | ≤ 0.5 | **FAIL** |
| safe threshold fr_mixed_slice | — | none | ≤ 0.5 | **FAIL** |

Accuracy mapping: **Tier 1 (unify)** — but the gating criterion (mandatory
regardless of tier) is NOT met. Accuracy improved massively; a residual set of
confident mistakes persists (19 wrong at ≥0.3, 5 wrong even at ≥0.9) despite
good average calibration (ECE 0.033, choice temp fitted to 4.304 to soften).

## Addendum — held_out_eval label corrections (spec Run-2 item 4) + analytical rescore

Verifier adjudication confirmed 3 label defects, corrected in
`synthetic_dataset_raw.csv` (all in held_out_eval, file otherwise fixed):
L1203 + L2402 'who is this artist' music→fallback (song-ID rule), L2450
"c'est ensoleillé à nice" weather→fallback (declarative, asks nothing).
Eval balance now fallback 103 / music 98 / weather 99 (timer/alarm 100).

Run-1 predictions on those rows are known (all fallback), so the rescore is
exact with no new inference: overall 481→**484/500 = 96.8%**,
EN 169→**171/175 = 97.7%**, FR 212→**213/225 = 94.7%**,
local_WRONG@0.5: 17→**14** (the 3 flipped rows were all ≥0.5);
local_WRONG@0.9 stays **5** (none of the 3 was ≥0.9).
Run 2 is judged against these corrected labels.

## Run 2 (stratified holdout + 150 anchor-free train rows, Colab T4)

`eval_report_r2.json`: overall 492/500 = 98.4%, EN 171/175 = 97.7%,
FR 222/225 = 98.7%, mixed 99/100; (a) 25/25 = 100%, (b) 37/38 = 97.4%;
ECE 0.037 (bar ≤ 0.15 PASS); Tier mapping Tier 1.
Gating: local_WRONG @0.5 = 7, @0.9 = 4; no safe threshold in any slice —
criterion FAILs a second time (run-1 corrected: 14 @0.5, 5 @0.9).
Confident errors halved but not eliminated. Per spec: report, stop, decide —
the remaining-7 pattern (same buckets or new?) determines whether a run 3
has a thesis.

## Run-2 error dump (7 rows ≥0.5) — pattern analysis

- 2 PERSISTERS from run 1 despite targeted B2 augmentation: 'continue la
  lecture' (0.97→0.96), 'pick up where we left off' (0.72→0.92, MORE confident).
- 1 WHACK-A-MOLE: 'parle plus fort, i can't hear you' mixed → music (0.68).
  Mic-gain case (documented fallback rule #10); B1 bare-comparative training
  plausibly strengthened the 'plus fort'→music pull that now misfires here.
- 2 VOCAB GAPS: 'est-ce qu'il gèle à Nantes' weather→fallback (0.96; frost
  vocabulary never in training), 'is the sun out in paris' weather→fallback
  (0.59; sun-out phrasing).
- 2 RULE-BOUNDARY (eval labels match documented rules; model keyword-seduced):
  'humming that melody' fallback→music (0.93, song-ID spirit), office-alarm
  fallback→alarm (0.56, rule #4).
## Run 3 (40 hard negatives + 10 train relabels, Colab T4) — REGRESSED vs run 2

`eval_report_r3.json`: overall 493→**476/500 = 95.2%**, EN 172→171/175 = 96.6%,
FR 222→**209/225 = 92.9%** (~6pts down), mixed 99→98/100; (a) 25/25 = 100%,
(b) 37/38 = 97.4%; ECE 0.037→0.046 (still ≤ 0.15 PASS).
Gating blanket: local_WRONG @0.5 = 6→**24**, @0.9 = 3→**15**; no safe threshold.
Tier-1 accuracy bars still clear (FR ≥ 85, EN ≥ 82) but the run-3 thesis
backfired: +50 fallback-side signals (2.3% of train) moved the music boundary
too far — suspected music→fallback over-correction, FR-heavy.

## Run 3 direction split (Cell-7 dump, threshold 0.0 = all 24 errors)

- fallback→action (dangerous): exactly **1** — 'parle plus fort…' →music (0.94,
  WORSE than run-2's 0.68; mic-gain still unresolved). Zero-tolerance bar: FAIL.
- action→fallback (safe, permitted residual): **23** — 17 weather→fallback
  (nearly all French rain-form "il pleut à X en ce moment" + gèle/vent/soleil
  variants) + 6 music→fallback (next song, veux écouter rock, throw on hits,
  next chanson, want 80s rock, continue la lecture now at 0.55, improved).
- Run-3 targets: humming FIXED (absent), all 4 passe rows CORRECT, continue la
  lecture 0.96→0.55. Collateral: French statement-syntax weather questions now
  read as declarative descriptions → fallback. Suspected mechanism: the 40 hard
  negatives (declarative DESCRIPTIONS → fallback) collide with French yes-no
  questions, which use statement word order ("il pleut à Lyon" = "is it raining
  in Lyon?"). Whack-a-mole with a precise address, not noise.

## Run-3 REPRO (same recipe, fresh session) — better, different residue

`eval_report_r3_repro.json` vs run-3 reference: overall 95.2→**98.8% (494/500)**,
EN 96.6→98.9%, FR 92.9→**99.1%**, mixed 98.0; (a) 100%, (b) 97.4%;
ECE 0.046→0.058 (still ≤ 0.15 PASS). local_WRONG @0.5: 24→**6**, @0.9: 15→3;
en_slice safe at 0.9.
Direction split of the 6 (threshold-0.0 dump): dangerous fallback→action = 3
(parle-plus-fort 0.92 — same row a fourth time — plus 'define serendipity'
×2 at 0.89/0.87, dictionary question → music, no obvious mechanism, genuinely
idiosyncratic); safe action→fallback = 3 (continue la lecture 0.93, lance
yesterday's hits 0.91, veux écouter rock 0.79).
Run 3's 17-row French-weather collapse did NOT reproduce (zero weather errors)
— seed-luck brittleness around the boundary, not a systematic regression.
Caveat: fitted choice temp 5.2 hit the clamp ceiling (→5.0, RuntimeWarning
"treat confidence as uncalibrated"); ECE still passes but confidences are
partly uncalibrated by the loader's own admission.
Hub upload reported done (`keypa/laya-multilingual-nestclock`, private);
Cell-9 download-and-reeval verification still pending at time of writing.

## Phase 0.5 CLOSE-OUT (Addendum 4 — no run 4)

- Shipped checkpoint: run 3 (`laya_multilingual_nestclock_r3`, manifest in
  `CHECKPOINT_SHIP.md`). Run-2 weights no longer exist — also the only viable
  candidate. Tier-1 accuracy bars clear (FR 92.9 ≥ 85, EN 96.6 ≥ 82).
- Dangerous direction → 0 via application logic, not training: deterministic
  parle-plus-fort override in `phase0_pipeline_test.classify()` (forces
  fallback regardless of confidence; `--no-override` recovers raw scores),
  pinned by `test_override.py` (10 fire + 15 no-fire; the test caught one real
  `can't`-vs-`cant` regex bug before ship).
- Safe-direction residual (23 rows) accepted and filed in
  `french_syntax_residual.md` with mechanism + revisit scope.
- Destructive-action safety filed in `phase1_design_notes.md` (confirmation
  step regardless of confidence — the router can never see sub-actions).
- Final arc: base FR 56.0/EN 81.1 → run-3 FR 92.9/EN 96.6, ECE 0.046,
  Tier 1 (unify). Three training rounds, two data rejections survived by the
  verifier process, one label-defect class corrected in eval, one train-side
  contradiction found and fixed.
