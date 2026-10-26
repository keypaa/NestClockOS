# Phase 4a report — speech → transcript → router

## 1. STT reality check (per session)

| session | condition | n | mean WER | exact | empty | non-Latin |
|---|---|---|---|---|---|---|
| rec1 | close mic, mixed | 37 | 16.3% | 18/37 | 0 | 1 (ja: "Lower the volume") |
| recA | close mic, quiet | 38 | 26.1% | 12/38 | 0 | 2 |
| recB | close mic, music | 39 | 29.8% | 9/39 | 0 | 1 |
| recC | 1-2 m + music | 33 | 38.9% | 6/33 | 0 | 1 |

rec1 detail: fr 19.2%, en 9.9%, mixed 21.5%, p50 257 ms.
recA detail: fr 26.4%, en 22.8%, mixed 31.3%, p50 264 ms.
recB detail: fr 32.5%, en 26.7%, mixed 28.0%, p50 271 ms.
recC detail: fr 37.5%, en 36.5%, mixed 51.7%, p50 269 ms.


| run | mean WER | exact | non-Latin |
|---|---|---|---|
| stt_rec1_test (original) | 19.7% | 20/37 | 1 |
| r_label (forced CSV language) | 17.1% | 19/37 | 0 |
| r_fr (forced fr) | 22.6% | 19/37 | 0 |
| r_en (forced en) | 16.3% | 18/37 | 0 |

r_en detail: fr 19.2%, en 9.9%, mixed 21.5%, all 16.3%; exact 49%; no empty transcripts; p50 257 ms.

Notable: "Lance un minuteur de 5 minutes" heard as "Dans 5 minutes, il y a 2-5 minutes." (117% WER); "Lower the volume a bit" appeared in Russian only in the original run (label/en fixed it).

## 2. Language policy experiment (E1.3)
- Candidate 1 (forced en/fr per utterance): no — wrong-language forcing is harmful.
- Candidate P1 (auto, retry on non-Latin): recovers the Russian outlier and few wording errors; needs P2-style for code-switched phrases.
- Candidate P2 (parallel en+fr, keep higher router confidence, Latin sanity guard): best for code-switched phrases (e.g. "mets une alarme for 8am demain" → 33% vs 100%, "Is it sunny outside" unaffected). Latency unchanged because calls are concurrent. **Adopt P2 as runtime STT policy.**

## 3. Router on real transcripts (via r_en_for_router.csv, --split all, --device cpu)
- Overall: 36/37 = 97.3%; EN 13/13 (100%), FR 17/18 (94.4%), mixed 6/6 (100%)
- ECE (post-temp): 0.083; safe thresholds (local_WRONG==0): overall 0.6, en_slice 0.3, fr_mixed_slice 0.6
- Tier mapping: Tier 1 (unify). 1 locally-executed error edged out via the 0.6 threshold.

## 4. Latency & memory (companion)
- STT p50 257 ms. Router: load 6619 ms, p50 353.9 ms, p90 400.1 ms, p99 449.9 ms (200 calls), peak RSS 2351 MB (CPU).

## 5. Exit criteria (E1)
- [x] recorder-side misses: 0 across all sessions (rec1/recA/recB/recC)
- [x] non-Latin outputs < 2% after the guard (P2 enforces Latin)
- [x] documented language policy with numbers (P2)
- [x] router accuracy on real transcripts recorded here (97.3%)

## E4. Wake-word acceptance

- Chosen wake phrase: `hey_pik_sel` (spoken "Hey pixel"; phonetic spelling for TTS).
- Model artifact: `my_custom_model/hey_pik_sel.onnx` (+ `.tflite`), produced by `automatic_model_training_patched.ipynb` on a Colab T4 runtime (espeak-ng replaces piper-phonemize).
- Companion wiring: `NESTCLOCK_WAKE_MODEL=<path to hey_pik_sel.onnx>` with `NESTCLOCK_WAKE_WORD=1`; detector loaded by `voice.wakeword.OpenWakeWordDetector`.
- Licensing: companion/runtime code Apache-2.0 (openWakeWord); enrolled model weights use openWakeWord's mixed weights licence — record the specific license printed by the training run before shipping. Code in this repo: Apache-2.0.
- CPU cost on the NestClockOS laptop: ~80 ms per 80 ms frame (single ONNX Runtime CPU session, threshold default 0.5); always-open ring buffer, no GPU required.
- Detection latency: target ≤ 80 ms frame hop + model inference; expected trigger within one frame after utterance end.
- False-accept rate: pending Colab training run; acceptance bar is ≤ 1/hour quiet, ≤ 3/hour with TV. Record measured rows (quiet room / with music / with TV / at 2 m) below once trained:
  | condition | runtime (h) | false accepts | false accepts/hour | detection @ 2 m |
  |---|---|---|---|---|
  | quiet room | TBD | TBD | TBD | TBD |
  | music | TBD | TBD | TBD | TBD |
  | TV | TBD | TBD | TBD | TBD |
- Note: the notebook's `target_word` is locked to `hey_pik_sel`; `number_of_examples`/`number_of_training_steps` defaults in the committed notebook are 1000 / 10000 and should be raised (30k–50k examples, longer training) for the production model.
