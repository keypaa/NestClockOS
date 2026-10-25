# NestClockOS Phase 0.5 Run-2 — Subagent B (Verifier) Report: Augmentation Set

**Artifact:** `synthetic_augment_raw.csv` (150 rows, all split=train) + `synthetic_augment_script.py`
**Verdict: FAIL** (1 narrow rejection class, 6 rows; resubmit after fix, no re-audit of passed parts needed)
**Method:** fully independent re-run (own regex/lexicons/norms, not the generator's self-checks).
Scripts: `/tmp/opencode/verify_augment1.py`, `/tmp/opencode/verify_augment3.py`, `/tmp/opencode/dump_augment.py`.
Bucket mapping recovered by importing the generator's `B1/B2/B3A/B3B` lists (oracle for grouping only —
all content judgments below use own criteria). All 150 examples individually audited (numbered L2–L151 = CSV line numbers).

## 0. Shape / counts — PASS
- 150 rows, header `phrase,expected_category,language,split`, all `split=train`. No missing fields, no unfilled slots.
- music 100 (fr 40 / en 34 / mixed 26) = B1 50 + B2 50 ✓; timer 35 (fr 14 / en 12 / mixed 9) = B3a ✓;
  fallback 15 (fr 6 / en 5 / mixed 4) = B3b ✓. Matches the authorized 50/50/35/15 split.

## 1. Per-example audit (ALL 150) — category/language/naturalness PASS; anchor-free FAIL (6 rows, see R1)
- **Category vs ROUTING_QUESTIONS: 150/150 correct.**
  B1 comparatives (`plus/moins fort`, `louder/softer/quieter`, `cran/notch/touch`, `monte/baisse/turn/crank`) →
  music (volume is explicitly music per criteria) ✓. B2 continuation/vague-listening (`continue/reprendre`,
  `ecouter/entendre/listen/hear`, `keep/go on`, `run it back`, `one more time`) → music, consistent with the
  addendum's authorized vocabulary and base-dataset precedent (`pick up where we left off` is already music
  in the base eval bank) ✓. B3a status checks with chrono/compteur/compte-à-rebours/countdown/counter → timer ✓
  (incl. `is the countdown still running`, `has the countdown finished yet` as timer checks). B3b
  passe/pass used non-musically (greetings, visits, salt/bread, store) → fallback ✓.
- **Language label: 150/150 correct (after manual review).** A naive row-derived EN-only/FR-only lexicon
  initially flagged 3 mixed rows (L6 `pass me le sel…`, L24 `encore softer…`, L43 `turn it down doucement`) —
  all three are **method artifacts** (novel augment vocabulary `pass/softer/doucement` is unsampled in the base
  en/fr rows, so the derived lexicon has gaps), each manually confirmed genuinely mixed (EN verb phrase +
  FR object/phrasing and vice versa). All 39 mixed rows hold FR+EN content under manual review; en rows are
  pure ASCII English; fr rows are French (plain-ASCII by design — the intended stress case).
- **Naturalness: 0 fails.** No slot-composition bugs (no duplications, no agreement errors, no unfilled slots).
  Minor non-fails: L98 `keep going` bare and L128 `keep it coming` / L151 `more of that calm stuff` are
  maximally elliptical (upheld as elliptical continuation per precedent, noted as over-broad rather than wrong);
  L113 `monte it up please now` is redundant code-switching but plausible speech. None rise to rejection.
- **Anchor-free as claimed: FAIL — 6 rows (R1).**
  - B1 (claim: no son/volume/sound/musique nouns): **50/50 clean** — own broad noun regex finds 0 hits;
    no `parle*` (mic-gain) and no stop/coupe/pause leaks. (L136 `mets-le un peu plus fort` contains `mets`,
    but inside the volume construction attested in base (`mets {more} fort`) — not the sound-noun anchor of
    interest. PASS.)
  - B3a (claim: synonym present, no minuteur/timer): **35/35 clean** ✓.
  - B3b (claim: passe/pass non-musical, no playback object): **15/15 clean** ✓.
  - B2 (claim: no play verbs/track nouns AND no song-ID questions): **44/50 clean; 6 FAIL** —
    song-ID: 0 anywhere in the file ✓, but:
    - **L77 `remets my favorites now`, L87 `remets ce qu'on ecoutait`, L118 `remets mes favoris`,
      L141 `remets depuis le debut`** contain the play verb ***remets*** (remettre = put back on, governing a
      playback object — the same verb family as base `mets {pl}` / `remets cette chanson…`). Load-bearing:
      these are playback-paired-with-play-verb rows, i.e. more of the anchored shape the addendum forbids.
    - L30 `continue la lecture now`, L32 `continue la lecture ou on en etait` contain the playback noun
      ***lecture*** reusing the base eval template's core (`continue la lecture`) verbatim plus an adverb —
      anchor-adjacent with weak novelty (supporting, minor).
    - L77/L118 additionally contain the collection noun ***favorites/favoris*** (track/playlist-adjacent;
      `my favorites` is a base `{pl}` slot value — supporting, minor).
    - `resume where we were` (L96) is NOT counted: `resume` = reprendre, legitimate authorized continuation
      vocabulary, not a play verb.

## 2. Dedup (own norms) — PASS
- Vs all 2500 existing rows: **0** on norm, **0** on accent-stripped, **0** on own conservative strong-norm
  (decorations only), **0** on generator-exact strong-norm. Internal (within-150): **0** on all four keys.
- (An early over-aggressive variant stripping content words produced phantom collisions; discarded as artifact
  per the original report's precedent. Both fair norms agree on 0.)

## 3. Core demand: vary syntax + drop the anchor — PASS with the R1 exception
- 20-row spot-check (seed 42) vs all 2500 base rows on deco-stripped + slot-masked structure:
  **0/20 exact structural overlaps** under the fair R1-consistent criterion (`now`/`maintenant` correctly treated
  as surviving content, not decoration — an earlier run over-stripping them produced 1 false J=1.00 hit on L30,
  corrected). Nearest-neighbor Jaccards are paraphrase-level (0.2–0.8), the expected family resemblance
  (e.g. `monte d'un cran encore` vs `monte le son d'un cran…` J≈0.57 — the anchor `le son` dropped, syntax varied).
- Qualitatively the set does what the addendum demands: B1 drops `son/volume` for bare comparatives +
  cran/notch/touch; B3a swaps minuteur→synonym inside the idiom family (intended); B3b uses non-musical
  passe/pass — **except the 4 `remets` rows**, which keep the play-verb anchor in the same shape
  (verb + playback object), and the 2 `lecture` rows, which reuse the eval template's core verbatim.

## 4. Danger check (wrong-lesson rows) — PASS, 0 true hits
- No mic-gain (`parle plus fort`) labeled music; no imperative stop/coupe/pause labeled continuation;
  no song-ID labeled music (song-ID regex over all 150: 0).
- Two regex hits on `arr[eê]te` (L19 `on continue ou on s'etait arrete`, L116 `allez reprends ou on s'etait
  arrete`) are **false positives**: past-tense `s'était arrêté` = "where we (had) stopped/left off", a location
  reference inside a resume request correctly labeled music — not a stop command.

## REJECTION (Generator must change — do NOT silently patch; resubmit for re-audit of these rows only)

**R1 — B2 play-verb anchor leak (criterion: "WITHOUT play verbs" as claimed).**
Reason: the generator's `B2_FORBID` regex `\bmets\b` never matches `remets` (no word boundary inside the word),
so its self-check passed 4 anchored-shape rows. Independent broad scan catches them.
Affected rows (CSV line numbers): **L77, L87, L118, L141** (all `remets` + playback object; L77/L118 also carry
`favorites/favoris`); supporting minor: **L30, L32** (`lecture` + verbatim eval-template core).
Fix:
1. Extend `B2_FORBID` to catch the remettre family (e.g. `remet\w*` / explicit `remets|remettre|remet`) and
   decide `lecture` + `favoris/favorites` explicitly (recommend forbidding `lecture` — it duplicates the eval
   template core — and replacing the favoris rows; at minimum document the choice instead of claiming
   "WITHOUT track nouns" while sampling a base `{pl}` value).
2. Regenerate/replace the 6 rows with genuinely anchor-free continuation (continuer/reprendre/ecouter/hear/
   keep/go-on vocabulary, vague objects only), keeping music 100 with fr/en/mixed counts and B2=50 unchanged.
3. Re-verify with an independent broad play-verb/track-noun scan (not the patched regex alone) showing 0 hits
   before resubmitting.

## Resubmit checklist
1. 0 play-verb/track-noun/song-ID hits on B2 rows under an independent broad scan (list the scan in the script output).
2. No verbatim reuse of a base eval template's core (`continue la lecture` family rephrased or replaced).
3. B2=50 / B1=50 / B3a=35 / B3b=15, language cells, all-train split, and §2-dedup 0 on all four norms unchanged.

---
# Re-review (R2, 2026-09-26) — Subagent B, independent re-verification of resubmission
**Artifacts re-checked:** `synthetic_augment_raw.csv` (150 rows, regenerated by updated script) + `synthetic_augment_script.py` (R1-FIX version).
**Method:** own checks only (own regexes/norms, not the generator's). Bucket oracle recovered by importing the generator's B1/B2/B3A/B3B lists (grouping only).
**Verdict: PASS** — R1 fixed, no regressions. File may be consumed.

## R2-1. The 6 replacement rows — PASS (all six)
Replacements (per script comments + confirmed present in CSV):
- fr: `reprends ou on en etait`, `encore une fois, continue comme ca`, `je veux continuer a ecouter tranquille`, `allez reprends comme ca encore`
- mixed: `reprends where we left off stp`, `encore une fois, keep going now`
- Anchor-free: 0/6 hits under own broad scan
  `remet\w*|\bremis\b|lecture\w*|favori\w*|favorit\w*|favourite\w*|\bmet\w*\b|\bplay\w*|\bjoue\w*|\bjouer\b|lan[cz]\w*|song\w*|track\w*|chanson\w*|morceau\w*|playlist\w*|musique\w*|\bmusic\b|titre\w*|radio\w*|skip|cue\b` — clean.
- Full B2 (50/50) under same own scan: **0 hits**. Generator's `B2_FORBID` + `B2_BROAD_SCAN` also report 0 on B2 rows.
- Labels: all 6 `expected_category=music` (correct — continuer/reprendre/ecouter/keep/go-on continuation + vague objects, consistent with R1 §1 precedent); language fr×4 pure French, mixed×2 genuinely FR+EN (`reprends where we left off stp`; `encore une fois, keep going now`) — correct.
- Naturalness: 0 fails. `je veux continuer a ecouter tranquille` is elliptical (adverbial `tranquille`) but plausible speech; the rest are plainly natural. No slot bugs.
- Script fix confirmed by reading: `B2_FORBID` now contains `remet\w*`, `lecture|lectures`, `favori\w*|favorit\w*|favourite\w*` (lines ~139-147) plus independent `B2_BROAD_SCAN` asserted 0; `MIX_FR_CORE` additions (`fois/tranquille/allez/bien`) are purity-lexicon only, documented, no content effect.

## R2-2. The 6 rejected phrases are gone — PASS
Exact-norm AND accent-stripped-norm search over all 150 rows: `remets my favorites now`, `remets ce qu'on ecoutait`, `remets mes favoris`, `remets depuis le debut`, `continue la lecture now`, `continue la lecture ou on en etait` — **0/6 present**. Substring scan for `remet`/`lecture`/`favori`/`favorites`/`favourite`: only hit is B1 `mets-le un peu plus fort` (the R1-upheld `mets {more} fort` volume construction, inside B1 not B2 — not a leak).

## R2-3. No regression on the other 144 — PASS
- Shape: 150 rows, header intact, all `split=train`, no missing fields; buckets b1=50/b2=50/b3a=35/b3b=15; language cells music fr40/en34/mixed26, timer fr14/en12/mixed9, fallback fr6/en5/mixed4 — unchanged per checklist item 3.
- Spot-check 30 (seed 99, b1×11/b2×12/b3a×7) + all 15 B3b rows individually: category/language/naturalness correct on every row inspected (B1 bare comparatives→music; B2 vague continuation→music; B3a synonym idioms→timer; B3b non-musical passe/pass→fallback; mixed rows genuinely mixed).
- Dedup (own norms + generator-exact strong-norm): vs all 2500 existing rows **0/0/0/0** (norm / accent-stripped / own strong / generator strong); internal within-150 **0**. Regenerated-file rerun of `synthetic_augment_script.py` exits 0, prints `OVERLAP COUNT = 0`, `ALL CHECKS PASSED`.
- Danger scan (own): no mic-gain (`parle plus fort`) labeled music; no stop-command (`stop/coupe/pause/arrête`-initial) labeled music; no song-ID anywhere. The only `arrête` hits remain the two R1-upheld false positives (`on continue ou on s'etait arrete`, `allez reprends ou on s'etait arrete` — past-tense location reference, correctly music).
- B1/B3a/B3b own re-scans: B1 0 true hits (standalone-`loud` + sound-noun regex; 8 naive `louder`-substring hits correctly excluded — `louder` is authorized comparative vocabulary); B3a 0 forbidden + 0 missing-synonym; B3b 0 playback-object hits.
- Note: rerunning the script reshuffles row order (seeded shuffle) — content set verified identical (all bucket/language counts unchanged, 0 unmapped phrases); CSV line numbers from R1 no longer apply, which is expected and immaterial.
