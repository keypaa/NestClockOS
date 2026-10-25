# Phase 4a report — speech → transcript → router

## 1. STT reality check (rec1, 37 utterances)

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
- [x] recorder-side misses: 0/37 (0%)
- [x] non-Latin outputs < 2% after the guard (P2 enforces Latin)
- [x] documented language policy with numbers (P2)
- [x] router accuracy on real transcripts recorded here (97.3%)
