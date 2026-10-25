# Phase 4a report — speech → transcript → router

## 1. STT reality check (recordings)
- Session folders: rec*/ (each a permanent fixture)
- Result files: stt_results.csv, r_fr.csv, r_en.csv, r_label.csv, r_fr_for_router.csv, ...
- Metrics (from `summarize`):
  - WER by language, exact-match %, empty transcripts %, p50/p90 latency
  - recorder-side misses < 3% target
  - non-Latin outputs < 2% after guard target

## 2. Language policy experiment (E1.3)
- Policies tested: auto, label (oracle), fr, en, P1 (retry on non-Latin), P2 (parallel en+fr, pick higher confidence)
- Compare on routing accuracy and fallback→action count (not WER)
- Chosen policy: _TBD_

## 3. Router on real transcripts
- Accuracy on held-out real transcripts: _TBD_
- fallback→action / action→fallback counts: _TBD_

## 4. Latency & memory (companion)
- Router p50/p90 ms, idle/peak RAM: _TBD_

## 5. Exit criteria (E1)
- [ ] recorder-side misses < 3%
- [ ] non-Latin outputs < 2% after guard
- [ ] documented language policy with numbers
- [ ] router accuracy on real transcripts recorded here
