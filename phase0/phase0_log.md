# NestClockOS — Phase 0 Log: Voice Pipeline Validation

**Goal:** before writing any app code, validate whether the proposed voice pipeline
(wake word → Voxtral STT → Laya local router → dispatch to local action or cloud LLM)
actually works well enough to build on, and find out *where* it breaks before it's
buried under a real application.

**Status at end of session: Phase 0 core question answered. Result: the router
layer needs fine-tuning before Phase 1+. Promoted to its own sub-phase (0.5).**

---

## Architecture under test

```
speech → Voxtral (Mistral) transcription → Laya Router.predict() → category + confidence
```

Laya was asked two questions per utterance in one forward pass:
- `category` (choice): alarm / timer / music / weather / fallback
- `is_complete` (noul): is this a complete, actionable command

Two test tools were built:
- `phase0_pipeline_test.py record` — full pipeline, live mic, one utterance at a time
- `phase0_pipeline_test.py batch <csv>` — text-only, no mic/STT, scores Laya's
  classification in isolation against a labelled CSV. This was the tool actually
  used all session — STT accuracy was never tested (see Open Items).

---

## Timeline of iterations

### 1. First run — 30 phrases, 6-way categories (alarm/timer/music/weather/**general_chat**/**other**)
**Result: 73.3% overall.**
Nearly every device-skill phrase (alarm/timer/music/weather) was correct. Almost
all misses were `general_chat` vs `other` confusion — both are semantically
similar "none of the above" buckets, too close for the classifier to separate.

**Action:** collapsed `general_chat` + `other` into a single `fallback` category.

### 2. Same 30 phrases, 5-way (fallback collapsed)
**Result: 83.3% overall.** Fallback confusion mostly resolved.
New failure surfaced: volume commands ("Turn up the volume", "Baisse le son")
missed at very low confidence (0.07–0.11) — the `music` category description
didn't mention volume control at all.

**Action:** reworded the `music` criterion to explicitly include volume control.

### 3. Same 30 phrases, reworded music criterion
**Result: 83.3% overall — unchanged, digit for digit, on 28/30 rows.**
The two volume phrases still missed, at almost identical (slightly worse)
confidence. **Conclusion: this isn't a wording problem.** Phrases like "turn up
the volume" carry no domain vocabulary (no "music", "song", "Spotify") — nothing
for a classifier to anchor on without shared context a human would infer for free.
This is a sparse-lexical-signal failure, not a criteria-clarity failure.

### 4. Same 30 phrases, forced `laya-typed-decisions` checkpoint (via `--model` override)
**Result: 83.3% overall — same score, different specific misses.** One miss
flipped to correct, a different one flipped to wrong; net wash. Confidence
values were uniformly lower and more compressed (max 0.56 vs max 1.00 on the
base router). **Conclusion:** typed-decisions (fine-tuned on invoice/support-ticket
workflows) doesn't transfer to smart-clock commands — it's differently
specialized, not more accurate here. Stuck with the base auto-router from here on.

### 5. First confidence-gating analysis, still on 30 phrases
Built a threshold sweep: for each candidate confidence threshold, count
`local_WRONG` (confident mistakes that would execute without ever reaching the
cloud LLM — the dangerous case) vs `deferred_wrong` (caught safely). Result:
one single high-confidence French miss ("Où en est le minuteur", 0.71 conf,
wrong) forced the safe threshold all the way to 0.8, which would send ~2/3 of
all traffic to the cloud. **Flagged as unreliable: n=1 is not enough data to
set a real threshold on.**

### 6. Expanded test set: 125 phrases, balanced EN/FR/mixed (54/54/17), extra
density on the two known failure clusters (French status-check idioms, volume commands)
**Result: 75.2% overall. en 90.7%, fr 57.4%, mixed 82.4%.**
The English/mixed accuracy held steady from the small test; **French collapsed**
on the larger, harder set — a real, stable ~33-point gap, not sampling noise.
French fallback phrases specifically kept misclassifying as `music` at
meaningfully high confidence.

### 7. Confidence-gating on the 125-phrase set
Same pattern as the small test, worse: needed threshold 0.8 to reach
`local_WRONG == 0`, at the cost of only 34% of traffic staying local — not a
usable gate.

### 8. Broke `local_WRONG` down by language — two different breakdowns
- By the **CSV's own language label** (ground truth, not available at runtime):
  French reached zero confident-mistakes at threshold 0.5; English needed 0.5 too.
- By **`routing.model`** (the router's actual checkpoint choice — the only signal
  that really exists at inference time): English-checkpoint-routed reached zero
  only at 0.8, multilingual-checkpoint-routed also needed 0.8.

These two tables disagreed with each other — the signal that something deeper
was going on.

### 9. Printed the actual checkpoint per row + an explicit label/checkpoint mismatch report
**Found: 20 of 54 French-labelled phrases were routed to the English checkpoint
instead of multilingual.** Every single misrouted phrase was **plain-ASCII
French with zero accented characters** ("Annule l'alarme", "Baisse le son",
"Mets de la musique"...) — every correctly-routed French phrase had at least
one accent. This matches a limitation Laya's own changelog names directly:
router language-detection leans on diacritics/script and has known trouble with
plain-ASCII French/Spanish/Italian/Portuguese/German text.

### 10. Accuracy broken down by (label × actual checkpoint) — the final diagnostic
| group | accuracy |
|---|---|
| en → english (correct routing) | 49/54 = 90.7% |
| fr → multilingual (correct routing) | 21/34 = 61.8% |
| fr → english (misrouted) | 10/20 = 50.0% |
| mixed → english | 11/13 = 84.6% |
| mixed → multilingual | 3/4 = 75.0% |

**Conclusion: two real, stacked problems, not one.**
- Misrouting is real and costly (61.8% → 50.0% when misrouted) — worth fixing
  for free later (pass Voxtral's detected language as Laya's `lang_guess`
  instead of relying on its internal heuristic).
- But even under *perfect* routing, the multilingual checkpoint's own ceiling
  on this task is ~62%, nowhere near English's ~91%. This roughly matches
  Laya's own published MASSIVE-intent benchmark (0.783 English vs 0.451
  multilingual on other languages) — this is a documented, external
  characteristic of the checkpoint on this kind of task, not a bug in the test.

---

## Decision reached this session

A single global confidence threshold was rejected as a viable design: it either
lets confident French mistakes through, or drags English's local-execution rate
down to French's unreliable level. Defaulting all non-English traffic to the
cloud LLM was also rejected — it was pointed out that with unknown (likely
majority-French) real usage, that would gut the entire point of having a fast
local router in the first place.

**Decision: fine-tune the Laya multilingual checkpoint for this specific task**
rather than continue tuning thresholds or wording.

- Base checkpoint: `laya-multilingual` (mmBERT-base backbone, built for 100+
  languages) — **not** `laya-typed-decisions`, whose backbone (ModernBERT-large)
  is the English-only architecture per its own model card, so fine-tuning it
  would not recover multilingual capability.
- Training data: today's 125 hand-written phrases are validation-set size, not
  training-set size. Plan is an LLM-generated synthetic dataset (low thousands),
  deliberately over-weighted toward the failure clusters found by hand this
  session (French idiomatic constructions like "où en est X", volume commands,
  the fallback category boundary).
- Compute: will cherry-pick useful pieces (training loop structure, RLCD
  approach) from Laya's own published fine-tuning notebook — built for the
  typed-decisions checkpoint on 2×T4 — but it is not a direct fit and needs
  adapting for the multilingual checkpoint and this project's own schema.
  First compute attempt will be free/cheap: a Colab T4, a Colab TPU v5e-1
  (single chip), or a Modal L4 (needs Modal-specific packaging), rather than a
  paid dedicated rental.
- Process: will be built agent-driven via Superpowers + Zenno (Keylhan's own
  plugin), guided by a frozen written spec (strict AI/ML engineering practices,
  anti-"AI slop" rules, organization, observability) handed to the agent
  alongside the task prompt — not yet drafted as of end of this session.

---

## Open items (known unknowns, not yet tested)

- **Voxtral's real transcription and language-ID accuracy is completely
  untested.** All 125-phrase testing this session used `batch` mode, which
  bypasses STT entirely and feeds text straight to Laya. We don't know Voxtral's
  word-error-rate or language-detection reliability on real speech, in either
  language, at all. This matters directly for the "pass Voxtral's detected
  language as Laya's `lang_guess`" fix mentioned above — that fix assumes
  Voxtral's language-ID is more trustworthy than Laya's internal heuristic,
  which has not been verified.
- The 125-phrase set, while much better than 30, is still hand-written by one
  person and may not represent real speech patterns, disfluencies, or the
  specific way Keylhan phrases things day to day.
- `laya-typed-decisions` was tested and rejected for this task, but only once,
  on the small 30-phrase set — not retested on the full 125.

---

## Artifacts from this session

- `phase0_pipeline_test.py` — record mode (full pipeline) + batch mode (text-only
  Laya scoring), with confidence-gating analysis broken down by checkpoint and
  by label, plus a label/checkpoint mismatch report.
- `test_phrases.csv` — original 30-phrase set (superseded, kept for reference).
- `test_phrases_large.csv` — current 125-phrase set (54 en / 54 fr / 17 mixed),
  balanced across 5 categories, with extra density on the two known failure
  clusters.
