#!/usr/bin/env python3
"""NestClockOS Phase 0.5 Run-2 augmentation — Subagent A (Generator, Run-2).

Targeted anchor-free rows for the three missing-anchor buckets from the
Run-1 root-cause analysis. 150 rows, ALL split=train:
  Bucket 1 (~50, music): volume/comparative intent WITHOUT son/volume/sound/
    musique/mute nouns (comparatives + pronouns + cran/touch/notch only).
  Bucket 2 (~50, music): playback continuation / vague listening intent WITHOUT
    play verbs or track nouns (continuer/reprendre/ecouter/hear/keep/go on).
    No song-ID questions (who sings / who is this artist -> fallback rule).
  Bucket 3 (~50: 35 timer + 15 fallback): timer-status idioms using minuteur
    SYNONYMS only (chrono / compteur / compte a rebours / countdown / counter,
    never minuteur/timer); plus fallback rows with collision verbs passe/pass
    used non-musically (no playback object).

Labels follow ROUTING_QUESTIONS criteria in phase0_pipeline_test.py.
Reproducible: hardcoded phrase lists + seeded shuffle (seed=7).
Dedup bar: novelty vs ALL 2500 rows of synthetic_dataset_raw.csv on
  norm, accent-stripped norm, and strong-norm (filler-stripped) forms,
  plus internal novelty on the same keys. Overlap must be 0.

Usage: python3 synthetic_augment_script.py
Writes ./synthetic_augment_raw.csv, verifies, prints report.
"""
import csv
import random
import re
import unicodedata
from collections import Counter

SEED = 7
OUT_CSV = "/home/keypaa/Projects/NestClockOS/synthetic_augment_raw.csv"
EXISTING_CSV = "/home/keypaa/Projects/NestClockOS/synthetic_dataset_raw.csv"

# ---------------------------------------------------------------- normalization
PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)


def norm(s: str) -> str:
    s = s.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    s = s.lower()
    s = PUNCT_RE.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


FILLER_TOKENS = {"um", "uh", "uhm", "euh", "ben", "alors", "bon", "hey", "nest",
                 "please", "thanks", "merci", "stp", "sil", "plait", "te", "dis", "donc"}


def strong_norm(s: str) -> str:
    toks = [t for t in strip_accents(norm(s)).split() if t not in FILLER_TOKENS]
    return " ".join(toks)


def keys(s: str):
    n = norm(s)
    return (n, strip_accents(n), strong_norm(s))


# ============================================================ Bucket 1 (music, volume, anchor-free)
# Forbidden: sound nouns (son/volume/sound/musique/music/speaker...), mute,
# standalone "loud" (louder/softer/quieter allowed), parle* (mic-gain/fallback
# confusion), coupe/pause/stop (playback anchors).
B1_FORBID = re.compile(
    r"\b(son|volume|volumes|sound|sounds|musique|musiques|music|musics|enceinte|"
    r"speaker|haut.parleur|mute|muted|unmute|parle|parler|parlez|coupe|couper|"
    r"pause|stop|stops)\b|\bloud\b", re.IGNORECASE)

B1 = [  # (phrase, lang)
    # -- fr (20)
    ("encore nettement moins fort", "fr"),
    ("un peu plus fort encore la", "fr"),
    ("monte d'un cran encore", "fr"),
    ("baisse d'un cran s'il te plait", "fr"),
    ("monte-le un peu", "fr"),
    ("baisse-le d'un cran", "fr"),
    ("plus fort encore", "fr"),
    ("moins fort la", "fr"),
    ("euh monte encore un cran", "fr"),
    ("remonte d'un petit cran", "fr"),
    ("redescends d'un cran s'il te plait", "fr"),
    ("un cran plus fort s'il te plait", "fr"),
    ("un cran moins fort la", "fr"),
    ("encore un peu plus fort", "fr"),
    ("baisse encore un peu la", "fr"),
    ("monte encore, c'est trop bas", "fr"),
    ("euh baisse ca d'un cran", "fr"),
    ("mets-le un peu plus fort", "fr"),
    ("vas-y monte un peu", "fr"),
    ("non baisse, trop fort la", "fr"),
    # -- en (17)
    ("a notch softer please", "en"),
    ("could you turn it down a touch", "en"),
    ("louder", "en"),
    ("softer", "en"),
    ("a little louder please", "en"),
    ("could you turn it up a touch", "en"),
    ("bring it down a notch", "en"),
    ("one notch louder please", "en"),
    ("down a touch please", "en"),
    ("a bit louder, yeah", "en"),
    ("make it a touch softer", "en"),
    ("softer please, just a touch", "en"),
    ("um turn it up a notch", "en"),
    ("crank it down a bit", "en"),
    ("that's blasting, turn it down a bit", "en"),
    ("could you bring it up a touch", "en"),
    ("could you make it quieter", "en"),
    # -- mixed (13)
    ("turn it up un peu", "mixed"),
    ("baisse it a notch", "mixed"),
    ("monte it up please now", "mixed"),
    ("un peu louder please", "mixed"),
    ("encore softer s'il te plait", "mixed"),
    ("moins fort, turn it down", "mixed"),
    ("plus fort, a touch louder", "mixed"),
    ("monte-le a notch stp", "mixed"),
    ("turn it down doucement", "mixed"),
    ("baisse-le down a touch", "mixed"),
    ("louder, encore plus fort", "mixed"),
    ("encore, turn it up a bit", "mixed"),
    ("un cran louder, vas-y", "mixed"),
]

# ============================================================ Bucket 2 (music, continuation, anchor-free)
# Forbidden: play verbs (incl. the remettre family) + track/collection nouns +
# playback noun 'lecture' + song-ID/fallback-adjacent words.
# R1 FIX (Run-2 resubmit): old B2_FORBID used '\bmets\b' which never matches
# 'remets' (no interior word boundary), leaking 4 remets rows; 'lecture' and
# 'favoris/favorites' were unsampled-but-unforbidden, leaking 2 verbatim
# eval-core rows + 2 collection-noun rows. Now explicitly forbidden:
#   - remettre family via 'remet\w*' (remet/remets/remettre/remettez/...),
#   - 'lecture/lectures' (base eval template core),
#   - 'favori*'/'favorit*'/'favourite*' (base {pl} slot value family).
B2_FORBID = re.compile(
    r"\b(play|playing|played|joue|jouer|joues|jouez|mets|mettre|mettez|remet\w*|"
    r"lance|lancer|lancez|shuffle|melange|melanger|skip|skipping|pause|paused|"
    r"stop|stopped|coupe|couper|balance|envoie|rejoue|throw|thrown|cue|put|puts|"
    r"song|songs|track|tracks|chanson|chansons|morceau|morceaux|titre|titres|"
    r"playlist|playlists|musique|musiques|music|musics|radio|radios|artiste|"
    r"artistes|artist|artists|chante|chanter|tune|tunes|melody|melodie|air|airs|"
    r"lullaby|berceuse|lecture|lectures|favori\w*|favorit\w*|favourite\w*|"
    r"who\s+is\s+this|qui\s+chante)\b", re.IGNORECASE)

# Independent broad scan (deliberately NOT the same regex as B2_FORBID):
# catches remettre/lecture/favoris/track-noun leaks even if B2_FORBID regresses.
B2_BROAD_SCAN = re.compile(
    r"remet\w*|lecture|favori\w*|favorit\w*|favourite\w*|\bmets\b|\bmettre\b|"
    r"\bjoue\w*|\bplay\w*|song|track|chanson|morceau|playlist|musique|\bmusic\b",
    re.IGNORECASE)

B2 = [
    # -- fr (20)
    # R1 FIX: replaced 4 rejected fr rows ('continue la lecture ou on en etait',
    # 'remets mes favoris', 'remets depuis le debut', "remets ce qu'on ecoutait")
    # with anchor-free continuation (no play verbs/track nouns/lecture/favoris).
    ("reprends ou on en etait", "fr"),
    ("encore une fois, continue comme ca", "fr"),
    ("j'ai envie d'ecouter quelque chose de calme", "fr"),
    ("je veux continuer a ecouter tranquille", "fr"),
    ("allez reprends comme ca encore", "fr"),
    ("continue comme avant", "fr"),
    ("laisse continuer comme ca", "fr"),
    ("je veux entendre quelque chose de doux", "fr"),
    ("continue encore, c'est bien comme ca", "fr"),
    ("continue ce qu'on ecoutait", "fr"),
    ("reprends comme tout a l'heure", "fr"),
    ("euh continue, laisse aller", "fr"),
    ("j'ai envie d'ecouter un truc pose", "fr"),
    ("vas-y continue", "fr"),
    ("on continue ou on s'etait arrete", "fr"),
    ("je veux ecouter un petit truc doux", "fr"),
    ("reste sur ce qu'on ecoutait", "fr"),
    ("on reprend comme avant, vas-y", "fr"),
    ("j'ai envie d'entendre quelque chose de reposant", "fr"),
    ("allez reprends ou on s'etait arrete", "fr"),
    # -- en (17)
    ("let's pick up where we left off", "en"),
    ("i'd really like to hear something relaxing", "en"),
    ("keep going", "en"),
    ("keep it coming", "en"),
    ("carry on listening", "en"),
    ("just keep listening", "en"),
    ("i feel like hearing something soft", "en"),
    ("let's listen to something gentle", "en"),
    ("go on, keep it rolling", "en"),
    ("resume where we were", "en"),
    ("back to what we were hearing", "en"),
    ("i want to listen to something quiet", "en"),
    ("more of that calm stuff", "en"),
    ("i want to keep hearing this kind of calm", "en"),
    ("let's hear something calm now", "en"),
    ("that was nice, one more time", "en"),
    ("run it back, that was good", "en"),
    # -- mixed (13)
    # R1 FIX: replaced 2 rejected mixed rows ('continue la lecture now',
    # 'remets my favorites now') with anchor-free continuation.
    ("reprends where we left off stp", "mixed"),
    ("encore une fois, keep going now", "mixed"),
    ("keep going, continue comme ca", "mixed"),
    ("je veux ecouter something relaxing", "mixed"),
    ("i want to hear quelque chose de calme", "mixed"),
    ("reprends encore, that was nice", "mixed"),
    ("let's continue ou on en etait", "mixed"),
    ("keep listening, reste sur un truc calme", "mixed"),
    ("la meme chose qu'avant, keep it coming", "mixed"),
    ("i want to keep hearing ce genre calme", "mixed"),
    ("vas-y, run it back", "mixed"),
    ("encore le meme, that was nice", "mixed"),
    ("je veux entendre something de doux", "mixed"),
]

# ============================================================ Bucket 3a (timer, synonym idioms)
# Forbidden: minuteur / timer. Required: chrono/compteur/compte a rebours/countdown/counter.
B3A_FORBID = re.compile(r"\b(minuteur|minuteurs|timer|timers)\b", re.IGNORECASE)
B3A_REQUIRE = re.compile(r"(chrono|compteur|compte\s+a\s+rebours|countdown|counter)", re.IGNORECASE)

B3A = [
    # -- fr (14)
    ("le chrono, on en est ou", "fr"),
    ("il reste combien au chrono", "fr"),
    ("ou en est le compte a rebours au juste", "fr"),
    ("ou en est le compteur", "fr"),
    ("le compteur en est ou", "fr"),
    ("il reste combien sur le compteur", "fr"),
    ("euh le chrono, il en est ou", "fr"),
    ("dis-moi ou en est le compteur", "fr"),
    ("combien il reste au compte a rebours", "fr"),
    ("le compte a rebours, il en est ou au juste", "fr"),
    ("il reste combien de temps au compteur", "fr"),
    ("on en est ou avec le chrono", "fr"),
    ("c'est ou le chrono la", "fr"),
    ("tu peux me dire ou en est le chrono", "fr"),
    # -- en (12)
    ("where are we on the countdown", "en"),
    ("how much is left on the countdown", "en"),
    ("where's the countdown at", "en"),
    ("how far along is the countdown", "en"),
    ("is the countdown still running", "en"),
    ("how much time is left on the counter", "en"),
    ("how much longer on the counter", "en"),
    ("how much remains on the chrono", "en"),
    ("euh how is the countdown coming along", "en"),
    ("tell me where the countdown is at", "en"),
    ("has the countdown finished yet", "en"),
    ("um how much time is left on the chrono", "en"),
    # -- mixed (9)
    ("ou en est le chrono now", "mixed"),
    ("how much left sur le chrono", "mixed"),
    ("il reste combien on the countdown stp", "mixed"),
    ("le compteur en est ou now", "mixed"),
    ("ou en est the countdown", "mixed"),
    ("where are we avec le chrono", "mixed"),
    ("dis-moi where the countdown is at", "mixed"),
    ("euh le chrono, how much left", "mixed"),
    ("il en est ou the countdown", "mixed"),
]

# ============================================================ Bucket 3b (fallback, passe/pass non-musical)
# Required: passe/pass verb. Forbidden: playback objects (suivante/next/song/...).
B3B_FORBID = re.compile(
    r"\b(suivante|prochaine|next|song|chanson|track|morceau|playlist|musique|music)\b",
    re.IGNORECASE)

B3B = [
    # -- fr (6)
    ("passe le bonjour a ta mere de ma part", "fr"),
    ("passe me voir demain quand tu veux", "fr"),
    ("passe-moi le sel s'il te plait", "fr"),
    ("tu passeras le bonjour a ton frere", "fr"),
    ("euh passe donc me voir ce week-end", "fr"),
    ("on passe te voir dimanche", "fr"),
    # -- en (5)
    ("pass the salt please", "en"),
    ("pass along my greetings to john", "en"),
    ("pass by tomorrow if you're around", "en"),
    ("could you pass me the bread please", "en"),
    ("i will pass by the store tomorrow", "en"),
    # -- mixed (4)
    ("passe le bonjour to alice de ma part", "mixed"),
    ("pass me le sel s'il te plait", "mixed"),
    ("pass by demain matin if you want", "mixed"),
    ("passe a la maison when you can", "mixed"),
]

# Light mixed-purity guard: accent counts as FR evidence; otherwise need >=1
# FR-content token and >=1 EN-content token from curated core sets.
MIX_FR_CORE = {"monte", "baisse", "remonte", "vas", "encore", "un", "une", "peu",
               "plus", "moins", "fort", "cran", "doucement", "reprends", "continue",
               "continuer", "ou", "en", "etait", "lecture", "veux", "ecouter",
               "entendre", "quelque", "chose", "calme", "doux", "reste", "truc",
               "comme", "ca", "remets", "mes", "favoris", "genre", "meme", "avant",
               "le", "la", "les", "de", "du", "des", "mon", "ma", "ta", "ce",
               "cette", "sur", "avec", "dis", "moi", "maintenant", "demain",
               "matin", "maison", "quand", "passe", "bonjour", "sel", "plait",
               "compteur", "chrono", "reste", "combien", "est", "sont", "suis",
               "es", "ete",
               # R1 FIX additions: vocabulary introduced by the 6 replacement
               # rows (kept old anchor tokens above so other purity checks are
               # unaffected; lecture/remets/favoris stay listed but are now
               # forbidden content in B2).
               "fois", "tranquille", "allez", "bien"}
MIX_EN_CORE = {"turn", "up", "down", "it", "notch", "notches", "touch", "louder",
               "softer", "quieter", "now", "please", "keep", "going", "continue",
               "coming", "where", "we", "left", "off", "pick", "lets", "let",
               "hear", "hearing", "listen", "listening", "something", "relaxing",
               "calm", "run", "back", "nice", "was", "that", "favorites", "my",
               "what", "were", "how", "much", "is", "the", "on", "countdown",
               "to", "me", "to", "by", "if", "want", "when", "you", "can", "still"}


def mix_sig(phrase: str):
    toks = strip_accents(norm(phrase)).split()
    f = sum(1 for t in toks if t in MIX_FR_CORE)
    e = sum(1 for t in toks if t in MIX_EN_CORE)
    return f, e


def main():
    rng = random.Random(SEED)
    buckets = [("b1", "music", B1), ("b2", "music", B2),
               ("b3a", "timer", B3A), ("b3b", "fallback", B3B)]
    rows = []  # (phrase, cat, lang, split, bucket)
    for bname, cat, items in buckets:
        for phrase, lang in items:
            rows.append((phrase, cat, lang, "train", bname))

    total = len(rows)
    print(f"candidate rows: {total} (b1={sum(1 for r in rows if r[4]=='b1')} "
          f"b2={sum(1 for r in rows if r[4]=='b2')} "
          f"b3a={sum(1 for r in rows if r[4]=='b3a')} "
          f"b3b={sum(1 for r in rows if r[4]=='b3b')})")

    # ---- 1. anchor checks per bucket
    for phrase, cat, lang, split, b in rows:
        if b == "b1":
            assert not B1_FORBID.search(phrase), f"B1 anchor leak: {phrase!r}"
            assert cat == "music"
        elif b == "b2":
            assert not B2_FORBID.search(phrase), f"B2 anchor leak: {phrase!r}"
            assert cat == "music"
        elif b == "b3a":
            assert not B3A_FORBID.search(phrase), f"B3a minuteur/timer leak: {phrase!r}"
            assert B3A_REQUIRE.search(phrase), f"B3a missing synonym: {phrase!r}"
            assert cat == "timer"
        elif b == "b3b":
            assert "pass" in strip_accents(norm(phrase)), f"B3b missing passe/pass: {phrase!r}"
            assert not B3B_FORBID.search(phrase), f"B3b playback object leak: {phrase!r}"
            assert cat == "fallback"
    # global: no song-ID questions anywhere
    songid = re.compile(r"(who\s+is\s+this\s+artist|who\s+sings|qui\s+chante|c.t+est\s+quoi\s+cette\s+chanson)",
                        re.IGNORECASE)
    for r in rows:
        assert not songid.search(r[0]), f"song-ID leak: {r[0]!r}"
    # R1 FIX: independent broad scan over B2 rows (not just B2_FORBID) for
    # remettre/lecture/favoris/track-noun leaks. Must be 0 hits.
    broad_hits = [(r[0], r[4]) for r in rows if r[4] == "b2" and B2_BROAD_SCAN.search(r[0])]
    print(f"broad B2 scan (remettre/lecture/favoris/track-noun, regex={B2_BROAD_SCAN.pattern[:60]}...): "
          f"{len(broad_hits)} hits")
    for p, b in broad_hits:
        print(f"  BROAD-HIT[{b}]: {p!r}")
    assert len(broad_hits) == 0, f"broad B2 scan hits: {broad_hits}"
    # en rows must be pure ASCII (no accidental French)
    for r in rows:
        if r[2] == "en":
            assert all(ord(c) < 128 for c in r[0]), f"non-ASCII in en row: {r[0]!r}"
    # mixed purity
    bad_mix = []
    for r in rows:
        if r[2] == "mixed":
            f, e = mix_sig(r[0])
            has_accent = any(ord(c) >= 128 for c in r[0])
            if not ((f > 0 or has_accent) and e > 0):
                bad_mix.append((r[0], f, e))
    assert not bad_mix, f"monolingual mixed rows: {bad_mix}"
    print(f"anchor checks OK; mixed purity OK "
          f"({sum(1 for r in rows if r[2]=='mixed')} mixed rows)")

    # ---- 2. internal dedup
    seen = {}
    dup_in = 0
    for r in rows:
        for k in set(keys(r[0])):
            if k in seen:
                print(f"  INTERNAL DUP: {r[0]!r} ~ {seen[k]!r} (key={k!r})")
                dup_in += 1
            else:
                seen[k] = r[0]
    assert dup_in == 0, f"internal dupes: {dup_in}"
    print("internal dedup OK (norm + accent-stripped + strong)")

    # ---- 3. overlap vs existing synthetic_dataset_raw.csv
    with open(EXISTING_CSV, newline="", encoding="utf-8") as f:
        existing = list(csv.DictReader(f))
    ex_norm, ex_acc, ex_strong = set(), set(), set()
    for x in existing:
        n, a, s = keys(x["phrase"])
        ex_norm.add(n)
        ex_acc.add(a)
        ex_strong.add(s)
    ov_n = [(r[0], r[4]) for r in rows if norm(r[0]) in ex_norm]
    ov_a = [(r[0], r[4]) for r in rows if strip_accents(norm(r[0])) in ex_acc]
    ov_s = [(r[0], r[4]) for r in rows if strong_norm(r[0]) in ex_strong]
    for tag, ov in [("norm", ov_n), ("accent-stripped", ov_a), ("strong", ov_s)]:
        print(f"overlap vs existing ({len(existing)} rows) on {tag}: {len(ov)}")
        for p, b in ov[:10]:
            print(f"  OVERLAP[{b}]: {p!r}")
    overlap_total = len(set(ov_n) | set(ov_a) | set(ov_s))
    assert overlap_total == 0, f"overlap with existing set: {overlap_total}"
    print("OVERLAP COUNT = 0 (must be 0)")

    # ---- 4. write CSV (seeded shuffle, csv module, UTF-8)
    rng.shuffle(rows)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["phrase", "expected_category", "language", "split"])
        for phrase, cat, lang, split, _ in rows:
            assert split == "train"
            w.writerow([phrase, cat, lang, split])

    # ---- 5. re-read + report
    with open(OUT_CSV, newline="", encoding="utf-8") as f:
        out = list(csv.DictReader(f))
    assert len(out) == total
    assert all(x["split"] == "train" for x in out)
    assert list(out[0].keys()) == ["phrase", "expected_category", "language", "split"]
    table = Counter((x["expected_category"], x["language"]) for x in out)
    print(f"--- wrote {OUT_CSV}: {len(out)} rows, all split=train ---")
    for cat in ["music", "timer", "fallback"]:
        for lang in ["en", "fr", "mixed"]:
            print(f"{cat:9s} {lang:6s} {table[(cat, lang)]}")
    by_b = Counter()
    # recover bucket from phrase lookup
    back = {p: b for p, _, _, _, b in rows}
    for x in out:
        by_b[back[x["phrase"]]] += 1
    print("buckets:", dict(by_b))
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
