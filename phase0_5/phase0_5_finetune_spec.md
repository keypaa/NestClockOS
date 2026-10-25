# NestClockOS — Phase 0.5 Task Spec: Laya-Multilingual Fine-Tuning

**Status:** frozen brief. Do not renegotiate scope mid-task — if something here turns
out to be wrong or infeasible, stop and flag it back to Keylhan rather than silently
reinterpreting this document.

**Context:** Phase 0 (see `phase0_log.md`) established that Laya's zero-shot routing
of smart-clock voice commands is reliable in English (~91%) but genuinely weak in
French (~62% even under correct routing), which matches Laya's own published
MASSIVE-intent benchmark gap (0.783 EN vs 0.451 multilingual). This is not a
threshold-tuning problem or a wording problem — both were tried and ruled out.
The fix is fine-tuning.

This document assumes the agent team has read `phase0_log.md` in full before
starting. It is not restated here.

---

## 1. Objective

Fine-tune `convaiinnovations/laya-multilingual` so that its category-routing
accuracy on French smart-clock commands closes most of the gap to English,
**without regressing English accuracy**, and **without breaking calibration**
(Laya's whole training paradigm — RLCD — exists specifically to keep reported
confidence trustworthy; don't undo that).

### Prerequisite — measure a baseline that Phase 0 never isolated

Phase 0's English-labeled phrases were almost always auto-routed to the dedicated
`english` checkpoint, so we never measured **`laya-multilingual`'s own zero-shot
accuracy on English** smart-clock phrases. This matters: Laya's published benchmark
shows base multilingual scoring 0.657 on English MASSIVE-intent, well below the
English checkpoint's 0.783 — so multilingual's English baseline is likely
meaningfully below the 90.7% we measured for the separate English checkpoint.

**Before training**, run the existing `test_phrases_large.csv` English rows through
`laya-multilingual` explicitly (`model="multilingual"` override, bypassing the
Router). Record this number — call it `EN_baseline_multilingual`. All "did
fine-tuning hurt English" judgments below are relative to this number, **not** to
the 90.7% English-checkpoint figure, which is a different model entirely.

### Three-tier outcome, decided by the numbers — not a subjective call

**Tier 1 — unify to a single model (best case).**
If the fine-tuned checkpoint reaches **French ≥ 85%** AND **English ≥ 82%**
(i.e., within ~2 points of the dedicated English checkpoint's *own* score on the
`held_out_eval` set — see the revision note below) — this means the fine-tuned
`laya-multilingual` is now good enough at English to replace the English checkpoint
entirely. In this case, drop the `Router`'s automatic language detection altogether
and send everything to the one fine-tuned checkpoint. This isn't just a
simplification — it structurally eliminates the ASCII-French misrouting bug found
in Phase 0, since there's no longer a routing decision to get wrong.

> **Revision (post data-pipeline, pre-training):** this bar was originally set at
> ≥88%, derived as "~2 points below 90.7%" — the English checkpoint's Phase 0 score
> on the 125-phrase hand-written set. Once `held_out_eval` (the actual set training
> judgments run against) was built, the dedicated English checkpoint scored 84.0%
> on it, not 90.7% — a different eval set, a different number. Keeping the bar at
> 88% would have silently made it *harder* than originally intended (beating the
> reference by 4 points instead of trailing it by ~2). Revised to 82% to preserve
> the original "~2 points below the reference, measured on the same set" intent.
> `EN_baseline_multilingual` on `held_out_eval` is 81.1% — so the fine-tune needs a
> real gain here too, not just on French.

**Tier 2 — keep two checkpoints (today's architecture, improved).**
If **French ≥ 80%** (a real improvement over the 62% baseline) but English doesn't
clear Tier 1's bar — keep the existing split: dedicated `english` checkpoint for
English-routed traffic, fine-tuned `laya-multilingual` for everything else. Apply
the `lang_guess` fix (Voxtral's detected language, bypassing the internal
heuristic) at this point, since misrouting now costs more with a bigger quality
gap between the two checkpoints than before fine-tuning.

**Tier 3 — manual language selection (last resort).**
If French still can't clear roughly 75–80% even after a real fine-tuning attempt —
stop trying to make automatic routing work reliably. Let the user pick a fixed
language in the app's settings, and load only that one checkpoint deterministically.
This trades convenience for reliability rather than continuing to patch an approach
that isn't working.

**I'm proposing these specific cutoffs (85/88 for Tier 1, 80 for Tier 2, 75–80 for
Tier 3), not stating them as guaranteed-achievable or objectively correct — they're
a reasonable starting bar given what fine-tuning has already done for Laya on other
domains (typed-decisions went from ~36% to 76.6%), but nobody has run this specific
fine-tune yet. Revise them if the first run's numbers suggest they were set wrong.**

Other acceptance criteria, unchanged regardless of tier:
- At some confidence threshold ≤ 0.5, `local_WRONG == 0` for **both** checkpoints
  simultaneously (this is the real target — a fine-tune that raises accuracy but
  still needs threshold 0.8 to be safe hasn't actually fixed the problem)
- Post-temperature-scaling ECE ≤ 0.15 on the held-out set (Laya's own README
  reports 0.081–0.106 achievable after calibration; use that as the bar, not raw
  uncalibrated confidence)
- The two specific known failure clusters from Phase 0 are explicitly re-tested
  and must individually clear 80%: (a) French idiomatic status-check phrasing
  ("où en est X", "ça en est où X"), (b) volume-control commands in both languages

If any criterion isn't met after one training run, that's a normal outcome —
report the actual numbers and stop for a decision, don't keep iterating
autonomously hoping the next run fixes it.

---

## 2. Training method — RL only, not SFT

Laya's decision head is trained from scratch via **RLCD** (Reinforcement Learning
for Calibrated Decisions): policy reports a probability distribution, exploration
adds Gaussian noise to logits, reward is a strictly proper scoring rule (log +
spherical), REINFORCE update with a group-mean baseline (GRPO-style). There is no
supervised cross-entropy phase in Laya's own training — do not add one. An
SFT-first approach risks optimizing for argmax correctness at the expense of the
calibration property RLCD is specifically designed to protect.

**Continue the same RLCD scheme** the checkpoint was already trained with, on our
own labeled data, matching the approach in Laya's own fine-tuning notebook.

---

## 3. Base checkpoint

`convaiinnovations/laya-multilingual` (mmBERT-base backbone, 322M params). **Not**
`laya-typed-decisions` — its backbone (ModernBERT-large) is the English-only
architecture per its own model card, so fine-tuning it would not add multilingual
capability. Not the plain `laya` root checkpoint either, for the same reason.

---

## 4. Data pipeline — two-subagent handoff

**This is a required process, not a suggestion.** No synthetic example enters the
training set without passing through both stages.

### Subagent A — Generator
- Produces labeled examples matching the schema below.
- Must explicitly over-weight, relative to uniform random sampling:
  - French idiomatic constructions (status checks, indirect phrasing)
  - Volume-control commands, both languages
  - The alarm/timer/music/weather vs. fallback boundary generally
  - Plain-ASCII French (no diacritics) specifically, since Phase 0 found this is
    where Laya's *router* (not the classifier itself) misfires — even though
    fine-tuning targets the classifier, the eval set needs this stress case
    covered so a routing regression would still be caught
- Target volume: low thousands of examples (exact number left to the agent's
  judgment, but must be enough to be a training set, not another validation set —
  Phase 0's 125-phrase set was explicitly too small for this purpose)
- Output format: same CSV schema as `test_phrases_large.csv`
  (`phrase,expected_category,language`), extended with a `split` column
  (`train` / `held_out_eval`) decided at generation time, not after — the held-out
  eval set must be generated separately, not carved out of the training set after
  the fact, to avoid near-duplicate leakage between train and eval.

### Subagent B — Verifier
- Independently reviews Subagent A's output. Does not simply re-run Subagent A's
  own reasoning — must be able to genuinely disagree with a label.
- Checks, per example: is the expected_category actually correct as written; is
  the phrase natural (not garbled or nonsensical); is the language label accurate;
  is this a near-duplicate of another example already in the set (paraphrase-level
  duplicates reduce effective dataset diversity without adding signal).
- Checks, on the set as a whole: category balance, language balance, whether the
  over-weighted failure clusters actually got over-weighted (don't just trust
  Subagent A's claim — count it), and whether `train`/`held_out_eval` are
  free of near-duplicates across the split.
- Rejects and returns to Subagent A anything failing the above, with a specific
  reason. Does not silently fix and re-label an example itself.
- Only a dataset that has passed Subagent B moves on to training.

---

## 5. Compute

Start with a **Colab T4** — matches the hardware Laya's own reference notebook
already targets, zero setup friction, free. Move to a Modal L4 only if the T4 run
demonstrably fails (OOM, or wall-clock time that's actually blocking iteration) —
don't preemptively reach for more hardware. Note if this happens: Modal requires
its own packaging (can't just point it at a plain script), so that's a real setup
cost, not a drop-in swap.

Laya's own **2×T4 Kaggle notebook** (`laya_finetune_typed_decisions_2xT4_kaggle.ipynb`)
is for `typed-decisions`, not `multilingual` — do not run it as-is. Cherry-pick:
- the RLCD training loop structure and hyperparameter defaults as a starting point
- the calibration-temperature-fitting step (per (question type, option count), per
  the README) — this is reusable regardless of checkpoint
- the evaluation/scoring harness shape

Do **not** reuse: its dataset (built for invoice/support-ticket/security-incident
workflows, irrelevant here), its schema, or any assumption that the base is
English-only (it targets a ModernBERT-large backbone; multilingual is mmBERT-base
and needs its own tokenizer/data handling checked, not assumed identical).

---

## 6. Schema (category set — unchanged from Phase 0)

```
category: choice — alarm / timer / music / weather / fallback
is_complete: noul — is this a complete, actionable command
```

Do not add categories or change wording of the criteria without flagging it back —
Phase 0 already spent real effort tuning these, and a silent change here would
make before/after comparisons meaningless.

---

## 7. Non-goals for this task

- No production deployment decisions (that's Phase 1+, out of scope here)
- No changes to the `Router`'s language-detection heuristic itself (the
  ASCII-French misrouting bug) — that's a separate, already-understood fix
  (pass `lang_guess` from Voxtral's detected language) to make later in the real
  application, not part of this fine-tuning task
- No autonomous retraining loop or self-triggered re-runs — one run, report
  against Section 1's criteria, stop for a human decision
- No OpenCode-specific tooling — Claude Code / Zenno only, per Zenno's own
  design scope

---

## 8. Process notes for the agent team

- Read this document and `phase0_log.md` in full before starting. Re-read this
  document at the start of each subtask rather than relying on carried-over
  context from earlier in a long session.
- Each of the four subtasks (data generation, data verification, training,
  evaluation) should be independently checkpointed — a later subtask failing
  should not require redoing an earlier one that already passed its own checks.
- Report actual numbers against Section 1's criteria at the end, not a
  qualitative summary. "It's much better now" is not an acceptable report;
  "French: 62% → 84%, English: 91% → 89%, ECE: 0.31 → 0.11" is.

---

## Addendum — Run 1 results and Run 2 authorization

**Run 1 (Colab T4, single run per §8):** massive accuracy gains — EN 81.1%→96.6%,
FR 56.0%→94.2%, mixed 78.0%→100%, both clearing their Tier-1 bars. ECE post-temp
0.033 (well under the 0.15 bar). **Gating criterion FAILED**: no safe threshold at
or below 0.5 overall or on the fr_mixed slice even at 0.9; 5/500 confident (≥0.9)
mistakes remain. Per this spec's own rule, gating is mandatory regardless of tier —
a large accuracy win does not waive it.

**Root-cause analysis (verifier-subagent diagnosis of the 17 errors at ≥0.5):**
- 3 buckets share one mechanism — **missing-anchor generalization**: the model
  learned intent-plus-anchor-word (e.g. volume commands paired with "son"/"volume",
  playback intent paired with a play verb, "minuteur" specifically rather than the
  synonym "chrono") rather than the underlying intent class. Anchor-free phrasing
  falls through at near-certainty (up to 0.98).
- 1 bucket (3–4 rows) is a suspected **eval-labeling defect**, not a model error —
  e.g. "who is this artist" → fallback may match the generator's own documented
  song-ID rule, meaning `held_out_eval` itself may be wrong on these rows.
- Calibration holdout was **not stratified** (uniform shuffle skewed it ~8 points
  under on English vs. train's mix) — a concrete, plausible contributor, though
  assessed as likely a small effect, not the primary cause.

**Run 2 authorized**, scoped as:
1. ~100–200 new rows via the same generate→verify handoff, targeting the three
   missing-anchor buckets specifically with anchor-free phrasing (not more of the
   same anchored shape)
2. Calibration holdout stratified by language + category to mirror train's mix
3. Same hyperparameters otherwise — this is a data-coverage gap, not a training
   config problem
4. Bucket 4's disputed labels adjudicated by the verifier subagent and, if
   confirmed mislabeled, corrected in `held_out_eval` **before** run 2 is scored
   against it (held_out_eval otherwise stays fixed for a fair comparison)
5. `lang_temperatures` (per-language calibration) explicitly deferred — named as
   the run-3 fallback only if run 2 still fails gating, not built preemptively

Gating bar unchanged: `local_WRONG == 0` at threshold ≤ 0.5, mandatory. Run 2
remains one run — report results and stop for a decision, same as run 1.

---

## Addendum 2 — Run 2 diagnosis, criterion revision, and Run 3 (narrow scope)

**Run 2 result:** FR 94.7%→98.7%, EN 97.7% (unchanged), ECE 0.037, both clusters
(FR idioms, volume) solved. Gating still failed: 7 wrong at ≥0.5, 4 at ≥0.9.

**Eval correction:** `held_out_eval` row L2263 ("pick up where we left off")
relabeled music→fallback by verifier adjudication — anaphoric, no antecedent,
names no playback action; falls under fallback's own "unclear or incomplete
speech" criterion. Rescored run 2 against the correction: overall 98.6%,
EN 98.3%, local_WRONG@0.5 7→6, @0.9 4→3. **Disclosed tension, unresolved:**
train row L2601 ("let's pick up where we left off" = music, added in run 2's
augmentation) now contradicts this corrected eval label. Left standing per this
addendum (changing train without retraining is meaningless), but is a **required
fix in Run 3**, not optional cleanup.

**Run-1 reproduction diagnostic (settles the whack-a-mole question from
Addendum 1):** recreated run 1 from scratch (same data, hyperparams, uniform
holdout) to get a real per-row error list to compare run 2 against, since run 1's
original per-row predictions were never saved.
- **"humming that melody" → music (0.93, run 2): confirmed regression.** Absent
  from the run-1 repro's error list entirely — run 1 got it right. A
  correct→confident-wrong flip across a purely data-only delta is as close to
  proven as approximate-weight reproduction allows. Cause: run 2's bucket-2
  "je veux écouter…" augmentation plausibly widened the music decision boundary
  until melody-adjacent descriptive speech gets pulled in.
- **"parle plus fort" mic-gain confusion: pre-existing, not whack-a-mole.**
  Wrong in the run-1 repro too (0.97). Addendum 1's "possibly B1-caused" theory
  is retracted — run 2 actually moved this the right direction (0.97→0.68)
  without finishing the job.
- **"continue la lecture": confirmed persister, wrong direction.** 0.61→0.96
  across run 2 despite 50 targeted rows — verb-level hardness (continuer vs.
  reprendre), now 0-for-2 on targeted attempts.
- **"pick up where we left off": correct in the repro**, under the corrected
  label — consistent with the convergence read in Addendum 1, not a new problem.

**Criterion revision — adopted, effective this addendum:** the original
`local_WRONG == 0` bar treated every misclassification as equally dangerous, but
the category schema cannot express sub-actions (an `alarm` misroute can't be
distinguished from "cancel" vs. "set" at the router level — this is a real
router limitation, not a data gap; see `phase1_design_notes.md`, filed
separately, on why destructive-action safety must be enforced downstream via a
confirmation step, not chased through router confidence at any accuracy level).
The gating bar is revised to be **direction-based**, which the schema *can*
express and which run 2's own errors split cleanly along:

- **`fallback → action` (executes unreviewed): zero-tolerance, at any confidence.**
  This is the dangerous direction — the system acts on something it should have
  deferred.
- **`action → fallback` (defers to the cloud LLM): a small, documented residual
  is acceptable.** This fails safe by construction — nothing executes, it just
  costs an unnecessary LLM call.

Under this revision, 11 of run 2's original 15 errors (the "chrono"/timer-status
rows, the volume-comparative rows, the jazz/playlist rows, "continue la lecture")
are accepted residual, not defects to keep chasing — further targeting them would
be diminishing-returns effort against a case the criterion no longer requires
fixing. What remains actionable is the dangerous-direction set:
"parle plus fort" → music, "humming that melody" → music, and the two
"passe le bonjour à [name]" → music collisions **if still present in run 2**
(status not yet re-checked against run 2's actual output — first task of Run 3).

**Run 3 authorized, narrow scope:**
1. Confirm whether the two "passe le bonjour" collisions are still wrong in run 2
   — this decides whether item 4 below is needed at all
2. Fix L2601 (relabel train row to match the corrected eval label)
3. Hard-negative rows distinguishing describing/commenting on music (humming,
   singing along, "that melody", similar) from commanding it — targets the
   confirmed regression
4. Targeted rows for the "passe"/"parle plus fort" lexical collisions, **only if
   item 1 confirms they're still unresolved**
5. **Explicitly do not** add further continuer-verb, chrono-idiom, or
   volume-comparative rows — these are now accepted safe-direction residual,
   not open problems

Same generate→verify handoff, same hyperparameters, same held_out_eval (with
L2263's correction applied). This is a small, targeted round — not a repeat of
Run 2's broader scope. Report results against the revised direction-based
criterion, and stop for a decision, same as runs 1 and 2.

---

## Addendum 3 — Run 3 execution: two decisions made mid-run

**Song-ID train contradiction (discovered during Run 3, not in original scope):**
verifier found 9 base-train rows ("who sings / qui chante" phrasing) labeled
`music`, contradicting the song-ID→fallback rule already established via
L2263's correction. **Decision: relabel all 9 to fallback.** Justification:
this is dangerous-direction training signal (teaches the model to act on what
the policy says should defer) and plausibly a contributing cause of the humming
regression alongside bucket-2's augmentation — fixing it serves Run 3's actual
purpose even though it wasn't enumerated as a step. This is the same class of
fix as L2601, just discovered mid-run instead of pre-run.

**Passe-le-bonjour "quiet-wrong" question:** run 2's output is clean on all 4
passe/parle-plus-fort rows at ≥0.5 (no local_WRONG), but whether they're
quiet-wrong (<0.5) can't be confirmed without run-2's actual weights.
**Resolution rule:** if the weights still exist anywhere, settle it exactly with
one `dump_errors` pass — cheap and removes ambiguity. If they don't, don't spend
effort recovering or re-deriving them — **quiet-wrong is safe by construction
under the confidence gate** (anything below the local-execution threshold defers
to the cloud LLM regardless of predicted category), so this is a diagnostic
curiosity, not a live safety gap. Run 3's own post-training eval will surface it
for free if it's still present.

---

## Addendum 4 — Run 3 results and final decision (Phase 0.5 closes)

**Run 3 result:** FR 92.9% (down from 98.7%), EN 96.6% (down from 97.7%),
ECE 0.046, blanket local_WRONG@0.5 = 24 (up from 7). Read naively, this looks
like a regression across the board. **It is not, once split by direction —
which is the metric that actually governs the adopted criterion:**

- **Dangerous (`fallback→action`): 1 of 24** — "parle plus fort..." → music,
  now at 0.94 confidence (worse than run 2's 0.68 on the same single row, but
  the *same* single row — not a new dangerous case). Humming, confirmed fixed
  (absent from run 3's errors). All 4 passe/parle collision rows from earlier
  addenda: correct.
- **Safe (`action→fallback`): 23 of 24** — 17 are French weather questions in
  statement word order ("il pleut à Lyon en ce moment" and variants), 6 are
  music-continuation phrasing. All fail safe by construction (defer to cloud
  LLM, execute nothing).

**Root cause, precisely identified:** the 40 hard-negative rows added in Run 3
taught "declarative sentence shape → fallback" (meant to fix humming/melody
descriptions). French yes-no questions use statement word order — there's no
do-support inversion like English "is it raining?" vs. "it is raining" — so
"il pleut à Lyon" *is* the question, not just a statement resembling one. The
fix over-generalized across a syntactic feature (declarative shape) it was
never meant to key on, rather than the intended semantic one (describing vs.
commanding). This is a genuinely harder, more specific linguistic problem than
any earlier bucket, and the right scope for it (if ever revisited) is
music-domain-specific hard negatives, not declarative-sentence hard negatives
in general.

**Comparison to Run 2, correctly framed:** Run 2 had ~2 dangerous-direction
errors at ≥0.5 (humming + parle-plus-fort). Run 3 has 1 (humming fixed,
parle-plus-fort persists, more confidently wrong on the exact same phrase).
**On the metric the adopted criterion actually cares about, Run 3 is an
improvement, not a regression** — the apparent "went backwards" read comes
from the blanket accuracy/error-count metrics that Addendum 2 explicitly
superseded.

**Decision: no Run 4.** Three rounds have moved this specific residual
(0.97→0.68→0.94 confidence on the identical phrase) without eliminating it,
while each attempt at broader fixes has traded one problem for another
(bucket-2 → humming regression; hard negatives → French-syntax collision).
This is no longer a data-volume problem; further RLCD rounds on the same
recipe are not expected to converge it to zero.

**Instead: close the last dangerous case deterministically, not statistically.**
"Parle plus fort" and its self-referential-volume relatives ("je ne t'entends
pas," "speak up," "I can't hear you") are a small, enumerable phrase family,
not a pattern a classifier needs to generalize. Add a keyword/regex override
applied to the router's output (same technique already used for verifier
cluster-tagging) that forces `fallback` for this known family regardless of
Laya's confidence. This is an application-layer fix, filed alongside the
destructive-action confirmation rule in `phase1_design_notes.md` — both are
cases where the right place to guarantee safety is downstream logic, not
further router training.

**Final outcome — Phase 0.5 closes here:**
- Ship Run 3's checkpoint (Run 2's weights no longer exist, so this is also
  the only viable candidate, not just the preferred one)
- Add the deterministic override for the parle-plus-fort phrase family →
  dangerous-direction count becomes 0, satisfying the zero-tolerance bar via
  application logic rather than model behavior
- Accept the 23-row French-statement-syntax safe residual as a documented,
  known limitation: costs an unnecessary cloud call on some naturally-phrased
  French weather questions, does not affect correctness, has a scoped future
  fix (music-domain-specific hard negatives) if ever worth revisiting
- No further fine-tuning rounds authorized under this spec
