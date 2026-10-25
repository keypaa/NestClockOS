# NestClockOS Phase 0.5 Run-3 — Subagent B (Verifier) Report: Hard-Negative Set

**Artifact:** `synthetic_hardneg_raw.csv` (40 rows, all fallback/train) + `synthetic_hardneg_script.py`
**Spec:** `phase0_5_finetune_spec.md` incl. both Addendums (Run-3 scope = Addendum 2, items 1–5)
**Ground truth:** `ROUTING_QUESTIONS` in `phase0_pipeline_test.py`; labeling rules incl. upheld
song-ID→fallback rule in `synthetic_verification_report.md`
**Method:** fully independent checks (own regex/lexicons/norms, not the generator's).
Fresh commands this session; no generator self-checks trusted.
**Verdict: PASS** — zero per-example FAILs, dedup 0, scope clean.
**Blocking note:** item-4 adjudication confirms a real train/train + train/eval
contradiction on song-ID that the controller must resolve before merging
(see §4). PASS means *this artifact is correctly labeled*; it does **not** mean
*safe to merge without resolving §4*.

## 1. Per-example audit (all 40, H2–H41 = CSV lines 2–41)

Criteria per row: (a) fallback correct per ROUTING_QUESTIONS (music = playing /
pausing / skipping / controlling Spotify playback incl. volume; fallback =
anything not directly an alarm/timer/music/weather command); (b) natural
phrasing; (c) language label accurate; (d) genuinely command-free (no
playback/volume verb aimed at the own speaker — imperatives, device-directed
modals; 3rd-person/past/progressive descriptives are clean).

Result: **40/40 PASS, 0 FAILs.** No fail list.

- Humming/singing descriptions (14): H2, H7, H10–H12, H19, H26–H27, H30,
  H33–H34, H37, H39, H8 — all descriptive (1st/3rd-person, progressive/past)
  or fragments; no command; fallback correct; language correct; natural.
  H30 (`humming that melody again, sorry`) is a near-paraphrase of the
  regressed eval row (`humming that melody yesterday again, sorry thanks`)
  but NOT verbatim (drops `yesterday` + `thanks`) — as required.
- Song-talk without command (8): H3, H4, H9, H23–H24, H29, H38, H40, plus
  H18/H22/H32/H41 in adjacent shapes — all interrogatives, exclamations, or
  comments about music with no playback/volume instruction; fallback correct
  **under the upheld song-ID→fallback rule**; command-free; natural.
  H9/H29/H38/H40 (`who sings…` / `qui chante…`) are the adjudicated set —
  individually correct per the upheld rule, but they contradict 9 base-train
  music labels (see §4, REPORT ONLY, not counted as row FAILs since the
  rows follow the upheld rule and the Run-3 brief).
- Ambient-music descriptions (7): H6, H14–H16, H20–H21, H25, H31 — complaints /
  reports about others' or outside music, no instruction to the own device
  (contrast B1 volume commands). Fallback correct. H25 (`…musique super
  forte…`) uses an absolute loudness descriptor inside a complaint — not a
  comparative, not a command (see §3). H18 (`ils passent que de la bonne
  musique…`) reviewed: `passent` is 3rd-person descriptive ("they're playing"),
  not imperative — clean.
- Past-tense recollections (6): H5, H13, H17, H28, H35–H36 — reports
  (`yesterday` / `last night` / imperfect `écoutait`), not commands.
  `listening`/`écoutait`/`heard`/`song`/`melody`/`playing`/`sings` appear only
  in descriptive (past/progressive/3rd-person/noun) use — each occurrence
  eyeball-verified command-free.

Language (own lexicon + accent check, then manual review of all flags):
fr 16 / en 15 / mixed 9 — **all 9 mixed rows genuinely mixed**
(FR evidence + EN evidence both present in every one). All 15 en rows pure
ASCII. Two auto-flags manually adjudicated as lexicon artifacts, NOT fails:
H28 (`we heard a great song at the restaurant last night`) — flag came from
English article "a" colliding with French "a" in my wordlist; row is pure
English. H36 (`hier soir on écoutait du jazz à la maison`) — flag came from
`jazz` (standard French loanword, cf. accents `écoutait`/`à`); row is pure
French. No other flags.

Naturalness: no garbled/slot-duplication/agreement errors in any row.
Colloquial forms (H2 `je fais que fredonner`, H40 `c'est qui qui chante là`,
H16 code-switch complaint) are natural speech, not defects.

Schema: header `phrase,expected_category,language,split` exact; 40/40
`fallback`/`train`. Counter: (fallback,fr,train)=16, (fallback,en,train)=15,
(fallback,mixed,train)=9.

## 2. Dedup (own norms, independent of generator's) — PASS, 0/0/0

- Own normalizations: (i) exact-norm (lowercase, punctuation→space, collapse);
  (ii) accent-stripped norm; (iii) own strong-norm with a *differently chosen*
  filler set from the generator's (mine additionally strips content-light
  tokens such as `quoi/encore/hier/journee/soir/matin/song/melody`-class —
  deliberately harsher, so a 0 here is stronger than the generator's 0).
- Overlap hardneg (40) vs `synthetic_dataset_raw.csv` (2650 rows): **0 exact,
  0 accent-stripped, 0 own-strong.**
- Internal (within the 40): **0 exact-norm dupes.**
- Cross-checked against `synthetic_augment_raw.csv` (150) implicitly via the
  merged working file (all 150 augment phrases are verbatim in the dataset,
  L2502–L2651); no hardneg row collides with any of them.
- Nearest-label-clash scan (same strong-norm, different label): **0** — i.e.,
  no hardneg row is a filler-word swap of an oppositely labeled base row.
  (H38 `who sings this song anyway` vs base L1894 `who sings this song` differ
  by content word `anyway`, so they do not share strong-norm keys — the clash
  is semantic/paraphrase-level, covered in §4, not a dedup-rule violation.)

## 3. Scope check (Addendum-2 item 5) — PASS, nothing smuggled in

Independent screens on accent-stripped lowercase text:
- Continuer verbs (`continu*/reprend*/repren*/resume/pick up/reste sur/keep
  on/carry on/poursuiv*`): **0 hits.**
- Chrono idioms (`chrono*/minuteur/minut*/countdown/timer`): **0 hits.**
- Volume comparatives (`plus fort*/moins fort*/louder/quieter/softer/turn it
  up-down/monter/baisser/augmente/diminue/crank/volume`): **0 hits.**
- Only `fort*` hit in the file is H25 `super forte` — absolute descriptor in a
  third-party complaint (`chez les voisins`), no comparative, no command.
  Explicitly clean, not a volume-comparative row.
- `encore` in H21/H26 = "again/still", not a volume instruction. Clean.

## 4. ADJUDICATION — generator's borderline #1 (song-ID→fallback vs base-train music labels)

**Verified against the actual CSV: the contradiction is real.**

- Base train contains **9 rows labeling `who sings X` / `qui chante X` as
  MUSIC** (all split=train): L661 `euh, qui chante ce morceau quoi`,
  L863 `who sings this tune`, L991 `qui chante ce titre`, L1617 `qui chante
  ce morceau`, L1894 `who sings this song`, L1936 `hey nest, who sings this
  track thanks`, L2026 `euh, qui chante cette chanson`, L2423 `okay, who
  sings this tune`, L2443 `qui chante cette chanson s'il te plaît`.
- The upheld rule (`synthetic_verification_report.md` §4, "song-ID→fallback"
  among 15 upheld borderline decisions) says song-ID questions are fallback:
  under ROUTING_QUESTIONS, asking *who* sings is an open-ended/general question,
  not playing/pausing/skipping/controlling playback — fallback is the
  criteria-correct label.
- Held-out eval already sides with the upheld rule: L1203 `hey, who is this
  artist` and L2402 `okay, who is this artist` are both **fallback/en/eval**.
  (Painter rows `quel artiste a peint…` are a different intent and not in play.)
- The 4 new hardneg song-ID rows (H9 `who sings ce morceau-là`, H29 `c'est qui
  qui chante this song`, H38 `who sings this song anyway`, H40 `c'est qui qui
  chante là`, all fallback/train) therefore follow the upheld rule — but
  H38 is a near-verbatim sibling of train L1894 (`who sings this song`, music)
  with the opposite label, and the set as a whole deepens an existing split:
  **train now contains 9× music vs 4× fallback on the same song-ID intent,
  while eval labels the same intent fallback.**
- **Ruling:** the 9 base-train music labels contradict the upheld rule; the
  new rows do not. The defect is in base train, not in this artifact.
- **Implication (for the controller):** as long as both policies coexist in
  train, the model cannot satisfy both, and whichever policy eval follows, one
  side scores as error — with the dangerous direction (`fallback→action`) in
  play if the model learns the train-music policy and meets eval's fallback
  song-ID rows at confidence. Resolve before Run-3 training: either relabel
  the 9 base-train song-ID rows to fallback (consistent with the upheld rule,
  eval, and these 4 rows) or explicitly carve song-ID out of this hardneg set
  (4 rows) and re-affirm a song-ID→music policy (which would then require
  fixing eval L1203/L2402 instead). REPORT ONLY — no train edits made here.
- Adjacent observation (not in scope, no action taken): the Addendum-2 item-2
  fix (L2601 `let's pick up where we left off` train→fallback to match eval
  L2263) **is already present** in the working `synthetic_dataset_raw.csv`
  (L2601 = fallback/en/train; augment block merged at L2502–L2651), while the
  standalone `synthetic_augment_raw.csv` A101 still carries the stale
  `music` label for the same phrase. Do not re-merge the standalone augment
  file naively or the corrected label will be clobbered.

## Resubmit checklist — n/a (PASS, no resubmit required)

Artifact meets all four checks. Controller decision required only on §4
(song-ID policy) before merging + training.
