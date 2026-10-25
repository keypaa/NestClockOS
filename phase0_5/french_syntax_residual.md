# Accepted residual: French statement-syntax weather questions → fallback
(Status: documented and accepted at Phase 0.5 close-out. No run 4.)

## What it is

23 held_out_eval rows (17 French weather, 6 music-continuation) that run 3's
model routes to `fallback` with confidence up to 0.94. Representative:
"il pleut à Lyon en ce moment" (is it raining in Lyon?), "il pleut à Nice…",
"est-ce qu'il gèle à Nantes" (the frost row is genuinely weather-vocabulary,
same bucket by symptom). All fail SAFE by construction: nothing executes,
each costs one unnecessary cloud-LLM call. Correctness is unaffected — the
LLM answers these fine.

## Mechanism (established, not suspected)

French yes-no questions use statement word order — "il pleut à Lyon" *is*
the question; there is no do-support inversion distinguishing it from a
statement. Run 3's 40 hard negatives taught "declarative sentence shape →
fallback" (aimed at humming/melody *descriptions*) and the rule collided
with French interrogative syntax. The model learned what it was taught.

## Why accepted rather than fixed

Three rounds show the boundary is now sensitive enough that fixes arrive
with addressed collateral (bucket-2 → humming; hard negatives → this).
The correct fix is music-domain-specific hard negatives (describing vs.
commanding *music*), not declarative-sentence negatives in general — a
genuinely harder, more linguistic problem, and a 4.6% cloud-call overhead
does not justify a fourth round against a Tier-1-complete system.

## Revisit scope (if ever)

- Data: French statement-form questions WITH weather intent labeled weather,
  paired against declarative non-questions labeled fallback (minimal pairs:
  "il pleut à Lyon" [question intonation/context] vs. "il pleut à Lyon."
  [report]). Hard to source synthetically without prosody labels — the
  text-only pipeline may be the wrong place to fix this at all.
- Alternative: Voxtral prosody/punctuation cues at the STT layer (a question
  mark from intonation disambiguates what text cannot).
- Track: re-score this exact 23-row list after any future data round; the
  list is recoverable from `run3_all_errors.csv` (threshold-0.0 dump) minus
  the single parle-plus-fort row.
