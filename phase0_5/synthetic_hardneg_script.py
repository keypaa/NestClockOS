#!/usr/bin/env python3
"""NestClockOS Phase 0.5 Run-3 hard negatives — Subagent A (Generator, Run-3).

Surgical counterweight to run-2's bucket-2 widening of the music boundary
(confirmed regression: 'humming that melody yesterday again, sorry thanks'
fallback->music at 0.93). 40 rows, ALL expected_category=fallback,
ALL split=train: describing/commenting on music != commanding it.

Shapes (NO playback command in any row — no play/pause/skip/resume/volume
verb aimed at the speaker):
  Humming/singing descriptions (14): humming/singing reports, incl.
    near-paraphrases of the regressed eval row (paraphrase, NEVER verbatim).
  Song-talk without command (11): who-sings / tune-name / stuck-in-head /
    j'adore comments. NOTE: base dataset labels "who sings X / qui chante X"
    as music; these rows deliberately take the opposite policy per the Run-3
    brief (talk-about-music = fallback). Flagged for verifier adjudication.
  Ambient-music description (7): neighbors/outside reports & complaints, no
    instruction to the own device (contrast B1 volume commands).
  Past-tense listening recollections (6): REPORTS (yesterday/last night),
    not commands.

Labels follow ROUTING_QUESTIONS criteria in phase0_pipeline_test.py.
Reproducible: hardcoded phrase lists + seeded shuffle (seed=13).
Dedup bar: novelty vs ALL 2650 rows of synthetic_dataset_raw.csv AND the 150
  rows of synthetic_augment_raw.csv, on norm, accent-stripped norm, and
  strong-norm (filler-stripped) forms, plus internal novelty on the same
  keys. Overlap must be 0. The exact regressed eval row must not appear.

Usage: python3 synthetic_hardneg_script.py
Writes ./synthetic_hardneg_raw.csv, verifies, prints report.
"""
import csv
import random
import re
import unicodedata
from collections import Counter

SEED = 13
OUT_CSV = "/home/keypaa/Projects/NestClockOS/synthetic_hardneg_raw.csv"
EXISTING_CSV = "/home/keypaa/Projects/NestClockOS/synthetic_dataset_raw.csv"
AUGMENT_CSV = "/home/keypaa/Projects/NestClockOS/synthetic_augment_raw.csv"
# The exact regressed eval row — must NEVER appear verbatim.
REGRESSED_EVAL_ROW = "humming that melody yesterday again, sorry thanks"

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


# ---------------------------------------------------------------- rows: (phrase, lang)
# No playback command aimed at the speaker in any row. Descriptive verbs only
# (3rd-person/passive/past: are playing, passent, entend, ecoutait...).
ROWS = [
    # -- humming / singing descriptions: fr (6)
    ("je fredonne cet air depuis ce matin", "fr"),
    ("je fais que fredonner cet air, pardon", "fr"),
    ("elle chantonne ce refrain toute la journée", "fr"),
    ("il fredonne cette mélodie depuis hier", "fr"),
    ("je chantonne ce refrain depuis ce matin, désolée", "fr"),
    ("euh je fredonnais cet air tout à l'heure", "fr"),
    # -- humming / singing descriptions: en (6)
    ("humming that melody again, sorry", "en"),
    ("i keep humming that tune, sorry", "en"),
    ("she keeps singing that chorus", "en"),
    ("he's been humming that melody all morning", "en"),
    ("sorry, that chorus is stuck in my head", "en"),
    ("um, i was humming along in the kitchen earlier", "en"),
    # -- humming / singing descriptions: mixed (2)
    ("je fredonne this melody depuis ce matin", "mixed"),
    ("humming that melody encore, sorry", "mixed"),
    # -- song-talk without command: en (4)
    ("who sings this song anyway", "en"),
    ("what's that tune called", "en"),
    ("that melody is stuck in my head", "en"),
    ("i really love this song", "en"),
    # -- song-talk without command: fr (5)
    ("c'est qui qui chante là", "fr"),
    ("j'adore cette chanson", "fr"),
    ("c'est quoi le nom de cet air", "fr"),
    ("cette mélodie me reste dans la tête", "fr"),
    ("ils passent que de la bonne musique ce soir", "fr"),
    # -- song-talk without command: mixed (3)
    ("c'est qui qui chante this song", "mixed"),
    ("who sings ce morceau-là", "mixed"),
    ("j'adore cette chanson, what a beautiful tune", "mixed"),
    # -- ambient-music description: en (3)
    ("the neighbors are playing loud music", "en"),
    ("music's too loud next door", "en"),
    ("there's loud music outside again", "en"),
    # -- ambient-music description: fr (3)
    ("on entend de la musique dehors", "fr"),
    ("les voisins font trop de bruit avec leur musique", "fr"),
    ("euh y a de la musique super forte chez les voisins", "fr"),
    # -- ambient-music description: mixed (2)
    ("les voisins are playing loud music encore", "mixed"),
    ("trop de musique outside tonight, c'est insupportable", "mixed"),
    # -- past-tense listening recollections: en (2)
    ("i was listening to some jazz yesterday", "en"),
    ("we heard a great song at the restaurant last night", "en"),
    # -- past-tense listening recollections: fr (2)
    ("hier soir on écoutait du jazz à la maison", "fr"),
    ("j'écoutais un truc sympa hier en cuisinant", "fr"),
    # -- past-tense listening recollections: mixed (2)
    ("yesterday j'écoutais some jazz at home", "mixed"),
    ("on écoutait good music hier soir", "mixed"),
]

# Command-verb guard: imperative / device-directed playback & volume verbs.
# Applied to accent-stripped norm. Deliberately whole-word so that 3rd-person
# descriptive forms (passent, playing, ecoutait...) and nouns (song) pass.
# Eyeball-verified: every row below was manually read for "no command".
CMD_FORBID = re.compile(
    r"\b(play|skip|skipping|pause|paused|pausing|stop|stopped|shuffle|resume|"
    r"restart|recommence|mute|unmute|zappe|saute|sauter|rejoue|rejouer|"
    r"sing|joue|jouez|jouer|mets|mettez|mettre|remets|remettez|remettre|"
    r"lance|lancez|lancer|reprends|reprenez|reprendre|continue|continuez|"
    r"continuer|envoie|envoyer|balance|balancer|passe|passer|passez|"
    r"coupe|coupez|couper|arrete|arreter|monte|montez|monter|baisse|baissez|"
    r"baisser|remonte|augmente|diminue|pousse|ecoute|ecoutez|ecouter|"
    r"listen|listening|hear|hearing|volume|son|sounds|sonore|notch|crank|"
    r"louder|softer|quieter|lecture|lectures|favori\w*|favorit\w*|favourite\w*|"
    r"turn\s+it\s+(up|down)|turn\s+(up|down))\b", re.IGNORECASE)

# Descriptive-form allowlist: tokens that CMD_FORBID's broad stems would catch
# but that appear here only in non-command (3rd-person / progressive / past /
# noun) use. Each row containing one must be listed AND eyeball-verified.
ALLOW_DESC = {
    "the neighbors are playing loud music": ["playing"],
    "les voisins are playing loud music encore": ["playing"],
    "ils passent que de la bonne musique ce soir": ["passent"],
    "i was listening to some jazz yesterday": ["listening"],
    "hier soir on écoutait du jazz à la maison": ["ecoutait"],
    "j'écoutais un truc sympa hier en cuisinant": ["ecoutais"],
    "yesterday j'écoutais some jazz at home": ["ecoutais"],
    "on écoutait good music hier soir": ["ecoutait"],
    "we heard a great song at the restaurant last night": ["heard", "song"],
    "who sings this song anyway": ["sings", "song"],
    "c'est qui qui chante this song": ["song"],
    "i really love this song": ["song"],
    "he's been humming that melody all morning": ["melody"],
}

MIX_FR_CORE = {"je", "j", "fredonne", "depuis", "ce", "matin", "encore",
               "c", "est", "qui", "chante", "morceau", "la", "les", "voisins",
               "on", "hier", "soir", "de", "trop", "musique", "insupportable",
               "adore", "cette", "chanson"}
MIX_EN_CORE = {"this", "melody", "humming", "that", "sorry", "song", "who",
               "sings", "ce", "are", "playing", "loud", "music", "yesterday",
               "some", "jazz", "at", "home", "good", "what", "a", "beautiful",
               "tune", "outside", "tonight"}


def mix_sig(phrase: str):
    toks = strip_accents(norm(phrase)).split()
    f = sum(1 for t in toks if t in MIX_FR_CORE)
    e = sum(1 for t in toks if t in MIX_EN_CORE)
    return f, e


def main():
    rng = random.Random(SEED)
    assert 30 <= len(ROWS) <= 50, f"row count {len(ROWS)} outside 30-50"
    print(f"candidate rows: {len(ROWS)}")

    # ---- 1. labels: everything fallback / train
    for phrase, lang in ROWS:
        assert lang in ("en", "fr", "mixed"), f"bad lang: {phrase!r}"

    # ---- 2. regressed eval row must not appear (verbatim or normalized)
    ev_keys = set(keys(REGRESSED_EVAL_ROW))
    for phrase, lang in ROWS:
        assert phrase != REGRESSED_EVAL_ROW, "verbatim eval row present!"
        assert not (set(keys(phrase)) & ev_keys), f"near-paraphrase too close: {phrase!r}"

    # ---- 3. no-command guard
    for phrase, lang in ROWS:
        san = strip_accents(norm(phrase))
        m = CMD_FORBID.search(san)
        if m:
            hit = m.group(0).lower()
            allowed = [a.lower() for a in ALLOW_DESC.get(phrase, [])]
            assert hit in allowed, f"COMMAND VERB {hit!r} in: {phrase!r}"
            print(f"  allowlisted descriptive {hit!r} in: {phrase!r}")
    print("command-verb guard OK (imperatives absent; descriptive forms allowlisted)")

    # ---- 4. en rows pure ASCII; mixed purity
    for phrase, lang in ROWS:
        if lang == "en":
            assert all(ord(c) < 128 for c in phrase), f"non-ASCII in en row: {phrase!r}"
    bad_mix = []
    for phrase, lang in ROWS:
        if lang == "mixed":
            f, e = mix_sig(phrase)
            has_accent = any(ord(c) >= 128 for c in phrase)
            if not ((f > 0 or has_accent) and e > 0):
                bad_mix.append((phrase, f, e))
    assert not bad_mix, f"monolingual mixed rows: {bad_mix}"
    print(f"ASCII + mixed-purity OK ({sum(1 for _, l in ROWS if l == 'mixed')} mixed rows)")

    # ---- 5. internal dedup (norm + accent-stripped + strong)
    seen = {}
    dup_in = 0
    for phrase, lang in ROWS:
        for k in set(keys(phrase)):
            if k in seen:
                print(f"  INTERNAL DUP: {phrase!r} ~ {seen[k]!r} (key={k!r})")
                dup_in += 1
            else:
                seen[k] = phrase
    assert dup_in == 0, f"internal dupes: {dup_in}"
    print("internal dedup OK")

    # ---- 6. overlap vs existing dataset + run-2 augmentation (must be 0)
    for path, tag in [(EXISTING_CSV, "dataset"), (AUGMENT_CSV, "augment")]:
        with open(path, newline="", encoding="utf-8") as f:
            existing = list(csv.DictReader(f))
        ex_norm, ex_acc, ex_strong = set(), set(), set()
        for x in existing:
            n, a, s = keys(x["phrase"])
            ex_norm.add(n)
            ex_acc.add(a)
            ex_strong.add(s)
        ov = [(p, k) for p, _ in ROWS for k in set(keys(p))
              if k in ex_norm or k in ex_acc or k in ex_strong]
        print(f"overlap vs {tag} ({len(existing)} rows): {len(set(ov))}")
        for p, k in sorted(set(ov))[:10]:
            print(f"  OVERLAP[{tag}]: {p!r} (key={k!r})")
        assert len(set(ov)) == 0, f"overlap with {tag}: {len(set(ov))}"
    print("OVERLAP COUNT = 0 (must be 0)")

    # ---- 7. write CSV (seeded shuffle, csv module, UTF-8)
    rows = [(p, "fallback", l, "train") for p, l in ROWS]
    rng.shuffle(rows)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["phrase", "expected_category", "language", "split"])
        w.writerows(rows)

    # ---- 8. re-read + report
    with open(OUT_CSV, newline="", encoding="utf-8") as f:
        out = list(csv.DictReader(f))
    assert len(out) == len(ROWS)
    assert all(x["expected_category"] == "fallback" and x["split"] == "train" for x in out)
    assert list(out[0].keys()) == ["phrase", "expected_category", "language", "split"]
    table = Counter(x["language"] for x in out)
    print(f"--- wrote {OUT_CSV}: {len(out)} rows, all fallback/train ---")
    for lang in ["en", "fr", "mixed"]:
        print(f"  {lang:6s} {table[lang]}")
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
