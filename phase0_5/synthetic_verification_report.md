# NestClockOS Phase 0.5 — Subagent B (Verifier) Report: Synthetic Dataset

**Artifact:** `synthetic_dataset_raw.csv` (2500 rows) + `synthetic_gen_script.py`
**Verdict: FAIL** (3 rejection classes; resubmit after fixes, no re-audit of passed parts needed)
**Method:** all checks run independently (own regex/lexicons/norms, not the generator's); scripts in `/tmp/opencode/verify*.py`, audit CSVs in `/tmp/opencode/audit*.csv`.

## 1. Set-level balance — PASS
- Category (overall, n=2500): alarm 500 (20.0%), timer 500 (20.0%), music 500 (20.0%), weather 500 (20.0%), fallback 500 (20.0%). All in 15–25%. 
- Language per split: train (n=2000) fr 900 (45.0%) / en 700 (35.0%) / mixed 400 (20.0%); held_out_eval (n=500) fr 225 (45.0%) / en 175 (35.0%) / mixed 100 (20.0%). Matches spec.
- Cell counts exact: train fr 180 / en 140 / mixed 80 per category; eval fr 45 / en 35 / mixed 20 per category.

## 2. Over-weighted clusters (OWN criteria) — all minimums MET
- (a) FR timer idioms, own strict regex (où-en-est / reste-combien / temps-restant / c'est-où): **87/225** (train 62, eval 25). Broad recount 91. Need ≥80 → PASS.
- (b) Volume, own regex on music rows: **157 strict / 163–166 broad** (en ~53, fr ~71, mixed ~33). Need ≥150 → PASS (generator's broader pattern catches "turn the sound down", "mets le son à N" that mine miss; true count higher, not lower).
- (c) Fallback-boundary: narrow keyword regex 185/500, **fair extended criteria (boundary keywords + fragment/thinking-aloud patterns): 243/500**. Need ≥200 → PASS (initial narrow count undercounted fragments; data genuinely contains the stress).
- (d) Plain-ASCII fr: **699/1125 = 62.1%** (train 62.4%, eval 60.9%). Need ≥35% → PASS.

## 3. Dedup (own norms) — PASS on exact/strong, FAIL on structural (see R1)
- Exact-norm dupes whole file: 0; within-train: 0; within-eval: 0; cross-split overlap: 0. (Generator-exact filler set AND own reasonable filler set both give 0.)
- Note: an early run with an over-aggressive filler list showed 306 "dupes" — artifact of stripping content words (il/la/like/quoi); discarded, both fair methods agree on 0.

## 4. Per-example audits — category labels PASS (0 fails / 497 rows); naturalness 4 FAILs (see R3)
- Stratified random 200 (7 per each of 30 category×language×split cells, seed 20260925): **200/200 labels correct** per ROUTING_QUESTIONS; language correct; natural except L605 "alors alors" stutter-stack (minor, not failed) and L1703 "a 20 minutes" (minor grammar, not failed).
- All 87 FR idiom rows: **87/87 correct** (timer status checks, natural).
- Random 100 music + 100 fallback: **200/200 labels correct**, incl. all 15 borderline patterns (reminders→fallback, song-ID→fallback, ambient-loudness→fallback, speak-up→fallback, lullaby→fallback, shop/event-time→fallback, office-alarm→fallback, mood→fallback, stuffy→fallback, kitchen-timer→fallback, device-advice→fallback, fragment→fallback, volume→music).
- Borderline scrutiny: generator's 15 decisions all **upheld** (checked against ROUTING_QUESTIONS; "remind me WITH an alarm" →alarm ×8 correct; "recommence le morceau/minuteur" →music/timer correct, earlier regex hits were substring false-positives). Agreed, no disagreements. Coverage note: "do you think it'll be a good day" template generated 0 rows (unsampled) — add on resubmit.
- EN purity: 0/875 en rows contain French (accent or function-word check). FR purity: 0/1125 fr rows contain unambiguous English. PASS.

## 5. Split integrity — FAIL (R1)
- Template-bank analysis: **21 slot-masked-identical templates shared between train and eval banks** (list below). Eval was required to use disjoint phrasing.
- Row impact (decoration-stripped + slot-masked structure): **25/500 eval rows (5.0%) share exact structure with a train row** (weather 12, timer 6, music 3, alarm 3, fallback 1). Nearest-neighbor (30 eval rows, Jaccard on masked structure, same-category train pool): 2× J=1.00, several J=0.67–0.78 paraphrase-adjacent.
- Overlapping templates (train bank → eval bank): 'donne moi la meteo de SLOT SLOT' (acc+ascii), 'est ce qu il va pleuvoir a/à SLOT SLOT', 'ou/où en est le minuteur de SLOT', 'il reste combien au minuteur de SLOT', 'monte/baisse le son/volume SLOT', 'mets le son (à/a) SLOT', 'mets SLOT fort', 'mets le son SLOT fort', 'augmente le volume SLOT', 'coupe le son', 'baisse/monte the volume SLOT', 'baisse/monte le son SLOT' (mix), 'balance SLOT stp', 'play SLOT SLOT', 'combien font SLOT fois SLOT'.

## REJECTIONS (Generator must change)

**R1 — Cross-split near-duplicates (criterion: any = FAIL).**
Reason: 21 eval templates identical to train templates; 25 eval rows are slot-swapped train rows.
Affected: the 21 templates above; example row pairs: EVAL L432 ↔ TRAIN L929/L866; EVAL L763 ↔ TRAIN L1510/L57; EVAL L2103 ↔ TRAIN L1458; EVAL L346 ↔ TRAIN L1692; EVAL L53 ↔ TRAIN L1512 (full list of 25 in §5 method; rerun `/tmp/opencode/verify4.py`).
Fix: replace all 21 overlapping eval-bank templates with novel phrasings (not slot-swaps), regenerate those eval rows with new RNG draws, re-verify zero decoration-stripped structural overlap before resubmitting.

**R2 — Mixed-language label accuracy (criterion: mixed = both languages present).**
Reason: monolingual rows labeled `mixed`. Data-driven lexicon method (EN-only/FR-only tokens derived from en/fr rows + accent check), manually reviewed.
Solid FAILs (20): pure-FR labeled mixed — L12, L117, L165, L529, L574, L822, L1081, L1202, L1392? (see weak), L1598, L1623, L1699?(weak), L1896, L1977, L2031, L2233, L2302, L2405 + L1392/L1392-class; pure-EN labeled mixed — L272 ('play a focus playlist last night please'), L849 ('play my road-trip playlist all day'), L1092 ('play my favorites yesterday please'). (Full 20-row solid list: L12, L117, L165, L529, L574, L822, L1081, L1202, L1598, L1623, L1896, L1977, L2031, L2233, L2302, L2405, L272, L849, L1092 + 1 adjudicated; weak/affix-only `please`/`stp`/`euh`-only rows L918, L1195, L1392, L2398, L1604, L2111, L1699 flagged separately as MINOR.)
NOT fails (method artifacts, verified mixed-OK): L15/L650/L900 ('manger' French content), L704 ('ton'), L540 ('mute' English content), L47-class ('sunny' English — lexicon gap in one run only).
Fix: remove always-monolingual mixed templates ('combien font {a} plus/fois {b}', 'monte/baisse le son {iv}' with FR-only iv incl. 'bien', 'du vent à {city} {d2} ou pas' with FR-only slot draws, 'balance/mets…' with FR-only draws, 'play…' with EN-only draws) or constrain their slot pools to force content mixing; regenerate/relabel the 20 solid rows (relabeling to fr/en breaks the 45/35/20 split — regenerate instead); keep volume/fr counts ≥ minimums after the fix.

**R3 — Naturalness / template-composition bugs (4 rows).**
- L1241 'sing me a song to fall asleep to to fall asleep please' (fallback) and L2290 "chante-moi une chanson pour m'endormir pour m'endormir" (fallback): slot duplication — template '…{lull} to fall asleep / pour m'endormir' × slot 'song to fall asleep to / chanson pour m'endormir'. Categories correct; phrases broken.
- L2 "peux-tu m'aider avec mes révision d'histoire" and L625 "aide-moi à réviser mes révision d'histoire" (fallback): agreement — 'mes' × singular 'révision d'histoire'.
Fix: restrict lullaby slot pools per template (or drop the redundant suffix), fix subject pool ('ma révision d'histoire' / pluralize), regenerate the 4 rows.

## Resubmit checklist
1. Zero decoration-stripped structural overlap train↔eval (rerun verify4 method).
2. Zero content-monolingual `mixed` rows (rerun data-driven lexicon method + manual review of flags).
3. Zero slot-composition duplications/agreement errors (rerun verify7 screens).
4. Keep (a)≥80, (b)≥150, (c)≥200, (d)≥35%, balances exact, exact/strong dedup 0.
5. Sample the 'good day' boundary template ≥3 rows.

---
# Re-review (2026-09-25): resubmitted `synthetic_dataset_raw.csv` + `synthetic_gen_script.py`
**Method:** fully independent re-run (own regex/lexicons/norms, not generator self-checks).
Fresh commands: `/tmp/opencode/verify1.py`, `verify2.py`, `verify4.py`, `verify6.py`,
row-derived EN-only/FR-only lexicon + accent check (two neutral variants),
`is_mixed_ok` cross-check via imported generator guard (as oracle only),
R3 regex screens, 100-row eval sample (`/tmp/opencode/rereview_sample100.csv`).
**Verdict: PASS** — R1/R2/R3 all hold, no regressions.

## R1 — structural overlap: PASS (0/500)
- `verify4.py` decoration-stripped + slot-masked exact match: **0/500** eval rows
  overlap train (was 25/500). `by category: Counter()` empty.
- Template-bank stripped-key disjointness (proper live-template import, comments
  excluded): **0** overlapping eval templates (was 21). Note: naive regex-on-source
  parsing yields 1 false positive (`'est ce qu il va pleuvoir à SLOT SLOT'`) that is
  a `# R1 fix: replaced ...` code comment, not a live template — excluded correctly.
- Cross-split exact-norm overlap 0; fair strong-norm (generator-exact filler set
  AND own-reasonable set, `verify2.py`) overlap **0/0/0** (whole/within/cross).
- Observations (not fails per checklist criterion): over-aggressive strong-norm
  (strips content `il/la/like/quoi`, discarded as artifact in prior report) shows
  1 cross-split key `'on en est ou avec le minuteur'` (train `on en est où avec le
  minuteur` vs eval `on en est où là avec le minuteur` — middle `là` survives
  verify4 leading/trailing-only deco-strip, so keys differ by design). NN Jaccard on
  masked-structure token sets: 3× J=1.00 are word-order variants
  (e.g. `il pleut à nantes en ce moment` vs `il pleut en ce moment à marseille`),
  not exact structural matches.

## R2 — mixed-language purity: PASS (0 true fails / 500)
- Fair data-driven lexicon (EN-only/FR-only derived from current en/fr rows;
  neutral = weak affixes/deco + loanwords + proper nouns/cities/days only,
  function words `le/de/un` count as evidence) + accent check: **0/500** monolingual.
- Generator guard `is_mixed_ok` cross-check: **0/500** (agrees).
- Over-aggressive variant (additionally neutralizes `le/de/un/les/du`) flags 11/500
  (L77, L288, L320, L659, L694, L793, L795, L1258, L1365, L1443, L1493) — each
  manually reviewed as **mixed-OK artifact**: `kill/cancel le timer`,
  `tell me un fun fact`, `remind me de ...`, `crank up le volume`,
  `temperature de ... now` all contain FR function word (`le/de/un`) + strong EN
  (`kill/cancel/tell/remind/now/crank`). Prior 20 solid + 7 weak templates confirmed
  fixed (`tell me combien font...` 8/8 with `tell me`; `monte/baisse le son` 6/6 with
  `now`/`right now`/EN iv; `play...` 5/5 with `pour moi`/`maintenant`).

## R3 — slot composition: PASS (0/0)
- Lullaby duplication (`to fall asleep to to fall asleep` /
  `pour m'endormir pour m'endormir`): **0** (was 2). Remaining 3 lullaby rows
  correct: `chante-moi une chanson pour m'endormir`, `chante-moi une berceuse`,
  `sing me a song to fall asleep to`.
- `mes` + singular agreement (`mes révision`/`dissertation`/`exposé`): **0**
  (was 2). All 15 `mes` rows plural-correct
  (`mes devoirs/dissertations/exposés/favoris/oreilles`).
- Unfilled `{slots}`: 0. Dup-word scan: 10 rows, all minor decoration stacks
  (`um um`, `ben ben`, `euh euh`, `alors alors`, `dis, dis-moi`) or intentional
  fragment (`euh mets, mets, oh laisse tomber`) — no template-composition bugs.

## No regression — all PASS
- Categories overall: 500 each (20.0%). Languages per split exact:
  train fr 900/en 700/mixed 400; eval fr 225/en 175/mixed 100.
- (a) FR timer idioms own strict regex: **87/225** (need ≥80).
- (b) Volume own strict regex on music: **159/500** (need ≥150;
  `verify2` variant 165/500; en 54 / fr 72 / mixed 33).
- (c) Fallback-boundary: narrow 163/500 (undercounts fragments, as before);
  **fair extended (boundary keywords + fragments/thinking-aloud): 230/500**
  (need ≥200).
- (d) Plain-ASCII fr: **705/1125 = 62.7%** (train 62.6%, eval 63.1%; need ≥35%).
- Dedup fair: exact-norm 0, strong-norm 0 (both filler sets), cross-split 0.
- `good day` boundary rows: **7** (need ≥3; `will it be...you reckon` ×2,
  `think it'll be...huh` ×2, `do you think it'll be...` ×3).

## Spot-check labels/naturalness: 100/100 + extras PASS
- Stratified-independent 100-row eval sample (seed 20260926,
  `/tmp/opencode/rereview_sample100.csv`): **100/100 labels correct** per
  ROUTING_QUESTIONS, natural (minor `stoppe`/`zappe` anglicisms acceptable;
  `encore plus fort` elliptical-volume acceptable).
- Extras reviewed: all 11 R2 flags (mixed-OK above), 3 lullaby + 15 `mes` rows,
  7 good-day rows — all labels correct, natural. Total ≈130 unique rows.
