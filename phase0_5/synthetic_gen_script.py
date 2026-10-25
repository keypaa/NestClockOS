#!/usr/bin/env python3
"""NestClockOS Phase 0.5 Section 4 — Subagent A (Generator).

Generates synthetic_dataset_raw.csv:
  header phrase,expected_category,language,split
  2500 rows: 2000 train + 500 held_out_eval (separate template banks per split)
  categories ~20% each | languages ~45% fr / ~35% en / ~20% mixed per split
  over-weighted clusters: (a) FR timer idioms, (b) volume, (c) fallback boundary,
  (d) plain-ASCII French.

Ground-truth criteria follow ROUTING_QUESTIONS in phase0_pipeline_test.py.
Labels: alarm/timer/music/weather/fallback. See BORDERLINE DECISIONS at bottom.

Usage: python3 synthetic_gen_script.py
Writes ./synthetic_dataset_raw.csv, re-reads it, verifies, prints report.
"""
import csv
import random
import re
import unicodedata
from collections import Counter

OUT_CSV = "/home/keypaa/Projects/NestClockOS/synthetic_dataset_raw.csv"

# ---------------------------------------------------------------- normalization
PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)

def norm(s: str) -> str:
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
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

def is_ascii(s: str) -> bool:
    return all(ord(c) < 128 for c in s)

# ---------------------------------------------------------------- cluster regex
IDIOM_RE = re.compile(
    r"(o[uù]\s+en\s+est|en\s+est[\s-]*o[uù]|ça\s+en\s+est\s+o[uù]|ca\s+en\s+est\s+ou|"
    r"il\s+en\s+est\s+o[uù]|on\s+en\s+est|o[uù]\s+ça\s+en\s+est|ou\s+ca\s+en\s+est|"
    r"ça\s+en\s+est\s+rest[eé]|combien\s+de\s+temps\s+restant|il\s+reste\s+combien|"
    r"reste\s+combien|combien\s+il\s+reste|c['’]est\s+o[uù])",
    re.IGNORECASE)
VOLUME_RE = re.compile(
    r"(turn\s+\S*\s*(up|down)|volume|louder|quieter|\bmute\b|unmute|crank|pump\s+it|"
    r"raise the sound|lower the sound|soften|blast it|dial the|silence( the speaker)?|"
    r"notch|bring the (sound|volume)|make it (louder|quieter)|monte|baisse|"
    r"augmente|diminue|plus fort|moins fort|coupe le son|remets le son|"
    r"pousse le son|remonte|redescends|trop fort|au max|au maximum|au minimum|"
    r"moiti[eé]|à moitié|a moitie|tout bas|mute le son|mets le (son|volume)|"
    r"\bfond\b|\bdix\b|\bvingt\b|z[eé]ro)",
    re.IGNORECASE)

# ---------------------------------------------------------------- slot pools
T_EN = ["5 am", "5:30 am", "6 am", "6:15 am", "6:30 am", "6:45 am", "7 am", "7:10 am",
        "7:30 am", "7:45 am", "8 am", "8:30 am", "9 am", "9:30 am", "10 am", "10 pm",
        "11 pm", "11:30 pm", "midnight", "noon", "quarter past six", "half past seven"]
T_FR_ACC = ["5h", "5h30", "6h", "6h15", "6h30", "6h45", "7h", "7h10", "7h30", "7h45",
            "8h", "8h30", "9h", "9h30", "10h", "22h", "22h30", "23h", "minuit", "midi",
            "6h et quart", "7h et demie"]
T_FR_ASCII = ["5h", "5h30", "6h", "6h15", "6h30", "6h45", "7h", "7h10", "7h30", "7h45",
              "8h", "8h30", "9h", "9h30", "10h", "22h", "22h30", "23h", "minuit", "midi",
              "6h et quart", "7h et demie"]
DUR_EN = ["2 minutes", "3 minutes", "5 minutes", "7 minutes", "10 minutes", "12 minutes",
          "15 minutes", "20 minutes", "25 minutes", "30 minutes", "40 minutes", "45 minutes",
          "an hour", "an hour and a half", "2 hours", "30 seconds", "45 seconds", "90 seconds"]
DUR_FR_ACC = ["2 minutes", "3 minutes", "5 minutes", "7 minutes", "10 minutes", "12 minutes",
              "15 minutes", "20 minutes", "25 minutes", "30 minutes", "40 minutes", "45 minutes",
              "une heure", "une heure et demie", "2 heures", "30 secondes", "45 secondes", "90 secondes"]
DUR_FR_ASCII = DUR_FR_ACC  # no accents in these strings by construction
DAY_EN = ["tomorrow", "on Monday", "on Tuesday", "on weekdays", "every weekday", "daily",
          "on weekends", "on Saturday", "next week", "every morning"]
DAY_FR_ACC = ["demain", "lundi", "mardi", "en semaine", "tous les jours", "chaque matin",
              "le week-end", "samedi", "la semaine prochaine", "tous les matins"]
DAY_FR_ASCII = ["demain", "lundi", "mardi", "en semaine", "tous les jours", "chaque matin",
                "le week-end", "samedi", "la semaine prochaine", "tous les matins"]
EXTRA_MIN = ["1 minute", "2 minutes", "3 minutes", "5 minutes", "10 minutes"]
EXTRA_MIN_FR = ["1 minute", "2 minutes", "3 minutes", "5 minutes", "10 minutes"]
PLAY_EN = ["my morning playlist", "my workout mix", "some jazz", "something relaxing",
           "my evening chill mix", "yesterday's hits", "some classical piano", "my road-trip playlist",
           "lofi beats", "my favorites", "some 80s rock", "a focus playlist"]
PLAY_FR_ACC = ["ma playlist du matin", "mon mix sport", "du jazz", "quelque chose de calme",
               "ma playlist du soir", "les hits du moment", "du piano classique", "ma playlist road-trip",
               "de la lofi", "mes favoris", "du rock des années 80", "une playlist concentration"]
PLAY_FR_ASCII = ["ma playlist du matin", "mon mix sport", "du jazz", "quelque chose de calme",
                 "ma playlist du soir", "les hits du moment", "du piano classique", "ma playlist road-trip",
                 "de la lofi", "mes favoris", "du rock des annees 80", "une playlist concentration"]
SONG_EN = ["the next song", "this track", "this song", "the last track"]
CITY_FR_ACC = ["Paris", "Lyon", "Marseille", "Demain", "ce week-end"]
CITY_FR_ASCII = ["Paris", "Lyon", "Marseille", "demain", "ce week-end"]

# ---- generic slot pools (every {placeholder} used in templates must exist here)
NUM1 = [str(n) for n in range(2, 21)]
COUNTRY_EN = ["france", "germany", "italy", "spain", "japan", "brazil", "canada",
              "egypt", "portugal", "norway", "greece", "thailand"]
TOPIC_EN = ["black holes", "the ocean", "dinosaurs", "chess", "history", "science",
            "dogs", "movies", "space", "cooking", "trains", "bees"]
HOLIDAY_EN = ["christmas", "new year", "easter", "halloween", "my birthday", "summer vacation"]
TASK_EN = ["call mom", "buy milk", "water the plants", "pay the bills", "feed the cat",
           "book the dentist", "charge my phone", "take out the trash"]
FOOD_EN = ["pancakes", "soup", "pasta", "cookies", "curry", "salad", "bread", "omelette"]
SPORT_EN = ["football", "tennis", "basketball", "rugby", "cycling", "swimming"]
EVENT_EN = ["concert", "movie", "game", "show", "match", "play"]
WHEN_EN = ["this morning", "yesterday", "last night", "on monday", "all day", "again"]
CITY_W_EN = ["paris", "london", "berlin", "madrid", "rome", "new york", "tokyo", "lisbon"]
DAY_W_EN = ["today", "tomorrow", "this weekend", "right now", "this afternoon",
            "this evening", "on sunday", "next week"]
VOL_UP_EN = ["a bit", "a little", "a lot", "way", "one notch", "two notches"]
PCT_EN = ["half", "a quarter", "ten percent", "thirty percent", "fifty percent", "full"]
COUNTRY_FR_ACC = ["France", "Allemagne", "Italie", "Espagne", "Japon", "Brésil",
                  "Canada", "Égypte", "Portugal", "Norvège", "Grèce", "Thaïlande"]
COUNTRY_FR_ASCII = ["France", "Allemagne", "Italie", "Espagne", "Japon", "Bresil",
                    "Canada", "Egypte", "Portugal", "Norvege", "Grece", "Thailande"]
TOPIC_FR_ACC = ["les trous noirs", "l'océan", "les dinosaures", "les échecs", "l'histoire",
                "la science", "les chiens", "le cinéma", "l'espace", "la cuisine"]
TOPIC_FR_ASCII = ["les trous noirs", "l'ocean", "les dinosaures", "les echecs", "l'histoire",
                  "la science", "les chiens", "le cinema", "l'espace", "la cuisine"]
TASK_FR_ACC = ["appeler maman", "acheter du lait", "arroser les plantes", "payer les factures",
               "nourrir le chat", "prendre rendez-vous chez le dentiste"]
TASK_FR_ASCII = ["appeler maman", "acheter du lait", "arroser les plantes", "payer les factures",
                 "nourrir le chat", "prendre rendez-vous chez le dentiste"]
FOOD_FR_ACC = ["crêpes", "soupe", "pâtes", "cookies", "curry", "salade", "pain", "omelette"]
FOOD_FR_ASCII = ["crepes", "soupe", "pates", "cookies", "curry", "salade", "pain", "omelette"]
SPORT_FR_ACC = ["football", "tennis", "basket", "rugby", "vélo", "natation"]
SPORT_FR_ASCII = ["football", "tennis", "basket", "rugby", "velo", "natation"]
EVENT_FR_ACC = ["concert", "film", "match", "spectacle", "pièce"]
EVENT_FR_ASCII = ["concert", "film", "match", "spectacle", "piece"]
WHEN_FR_ACC = ["ce matin", "hier", "cette nuit", "lundi", "toute la journée", "encore"]
WHEN_FR_ASCII = ["ce matin", "hier", "cette nuit", "lundi", "toute la journee", "encore"]
DAY_W_FR_ACC = ["demain", "ce week-end", "ce soir", "dimanche", "lundi",
                "la semaine prochaine", "vendredi", "cet après-midi"]
DAY_W_FR_ASCII = ["demain", "ce week-end", "ce soir", "dimanche", "lundi",
                  "la semaine prochaine", "vendredi", "cet apres-midi"]
CITY_W_FR = ["paris", "lyon", "marseille", "bordeaux", "lille", "nantes", "toulouse", "nice"]

SLOT = {
    "en": {
        "t": T_EN, "d": DAY_EN, "d2": DAY_W_EN, "du": DUR_EN, "ex": EXTRA_MIN,
        "pl": PLAY_EN, "s": SONG_EN, "a": NUM1, "b": NUM1,
        "country": COUNTRY_EN, "topic": TOPIC_EN, "holiday": HOLIDAY_EN, "task": TASK_EN,
        "food": FOOD_EN, "sport": SPORT_EN, "event": EVENT_EN, "when": WHEN_EN,
        "city": CITY_W_EN, "iv": VOL_UP_EN, "pct": PCT_EN,
        "ud": ["up", "down"], "udx": ["up a little", "down a notch", "back up"],
        "lj": ["louder", "quieter", "a bit louder", "a touch quieter"],
        "mutev": ["mute", "unmute", "silence"], "crank": ["crank", "pump", "dial"],
        "wx": ["rain", "snow", "storm", "freeze", "hail"],
        "name": ["alice", "bob", "charlie", "diana", "eric", "fatima", "george", "hannah"],
        "langto": ["spanish", "french", "german", "italian", "english", "portuguese"],
        "landmark": ["the eiffel tower", "the louvre", "big ben", "the grand canyon",
                     "the sahara", "mount everest", "the colosseum", "niagara falls"],
        "meal": ["tonight", "for dinner", "this weekend", "tomorrow night", "for lunch", "on sunday"],
        "thing": ["color", "movie", "song", "book", "food", "animal"],
        "subject": ["homework", "math", "essay", "science project", "history revision"],
        "game": ["chess", "a quiz", "trivia", "hangman", "cards"],
        "news": ["morning", "evening", "latest", "weekend"],
        "word": ["necessary", "rhythm", "serendipity", "embarrass", "mnemonic", "broccoli",
                 "rhinoceros", "chandelier"],
        "word3": ["serendipity", "nostalgia", "ephemeral", "sonder", "wanderlust", "petrichor"],
        "art": ["the mona lisa", "the starry night", "guernica", "the scream",
                "girl with a pearl earring"],
        "where": ["downtown", "on the highway", "near the airport", "on main street"],
        "stuffy": ["stuffy", "freezing", "humid", "dry"],
        "org": ["organize it", "fix it", "sort it out", "plan it"],
        "dream": ["flying", "being late", "an exam I forgot", "a beach", "showing up with no shoes"],
        "candles": ["candles", "fairy lights", "flowers", "incense"],
        "lull": ["lullaby", "song to fall asleep to", "bedtime song"],
        "late": ["late already", "running late", "oversleeping again"],
        "wrong": ["wrong", "late", "too cheerful", "depressing"],
        "device": ["alarm clock", "speaker", "radio", "lamp"],
        "aud": ["music", "track", "song", "playback"],
        "s2": ["this song", "this track", "the playlist", "the album"],
        "s3": ["this song", "this track", "this tune"],
        "skipv": ["skip", "jump past", "move past"],
        "daypart": ["morning", "evening", "workout", "weekend", "chill"],
    },
    "fra": {
        "t": T_FR_ACC, "d": DAY_FR_ACC, "d2": DAY_W_FR_ACC, "du": DUR_FR_ACC, "ex": EXTRA_MIN_FR,
        "pl": PLAY_FR_ACC, "a": NUM1, "b": NUM1,
        "country": COUNTRY_FR_ACC, "topic": TOPIC_FR_ACC, "holiday": ["noël", "le nouvel an",
                 "pâques", "halloween", "mon anniversaire", "les grandes vacances"],
        "task": TASK_FR_ACC, "food": FOOD_FR_ACC, "sport": SPORT_FR_ACC, "event": EVENT_FR_ACC,
        "when": WHEN_FR_ACC, "city": CITY_W_FR, "d2x": DAY_W_FR_ACC,
        "iv": ["un peu", "beaucoup", "encore", "à fond", "au maximum"],
        "lvl": ["moitié", "fond", "dix", "vingt", "zéro"],
        "pm": ["plus", "moins"], "more": ["plus", "moins"],
        "pousse": ["pousse", "remonte", "redescends"],
        "qq": ["là", "maintenant", "au juste", "exactement"],
        "name": ["léa", "hugo", "chloé", "louis", "emma", "gabriel"],
        "langto": ["anglais", "espagnol", "allemand", "italien", "portugais"],
        "landmark": ["la tour eiffel", "le louvre", "le mont-blanc", "la seine",
                     "le colisée", "les pyramides"],
        "meal": ["ce soir", "pour dîner", "ce week-end", "demain soir", "pour déjeuner", "dimanche"],
        "thing": ["couleur", "film", "chanson", "livre", "plat", "animal"],
        # R3 fix: plural-only subjects so 'mes {subject}' always agrees
        # ('mes devoirs', 'mes maths', 'mes dissertations', ... all plural).
        "subject": ["devoirs", "maths", "dissertations", "exposés de sciences", "révisions d'histoire"],
        "game": ["échecs", "quiz", "trivial pursuit", "pendu", "cartes"],
        "word": ["nécessaire", "rythme", "sérendipité", "embarrasser", "mnémotechnique", "brocoli"],
        "where": ["au centre-ville", "sur l'autoroute", "près de l'aéroport", "rue principale"],
        "stuffy": ["lourd", "glacial", "humide", "sec"],
        "dream": ["voler", "être en retard", "un examen oublié", "une plage", "mes dents qui tombent"],
        "lull": ["berceuse", "chanson pour m'endormir", "chanson douce"],
        "device": ["réveil", "enceinte", "radio", "lampe"],
        "plat": ["poulet", "poisson", "riz", "légumes", "boeuf", "salade"],
        "daydream": ["vacances", "plage", "week-end", "sieste", "voyage"],
        "piece": ["l'étage", "le salon", "la chambre", "le jardin"],
        "artfr": ["la joconde", "la nuit étoilée", "guernica", "le cri",
                  "la jeune fille à la perle"],
        "audfr": ["la musique", "la chanson", "le morceau", "la playlist"],
        "sfr": ["la suivante", "la prochaine", "la chanson suivante"],
        "sfr2": ["la lecture", "le morceau", "la chanson"],
        "sfr3": ["cette chanson", "ce morceau", "ce titre"],
    },
    "frx": {
        "t": T_FR_ASCII, "d": DAY_FR_ASCII, "d2": DAY_W_FR_ASCII, "du": DUR_FR_ASCII,
        "ex": EXTRA_MIN_FR, "pl": PLAY_FR_ASCII, "a": NUM1, "b": NUM1,
        "country": COUNTRY_FR_ASCII, "topic": TOPIC_FR_ASCII, "holiday": ["noel", "le nouvel an",
                 "paques", "halloween", "mon anniversaire", "les grandes vacances"],
        "task": TASK_FR_ASCII, "food": FOOD_FR_ASCII, "sport": SPORT_FR_ASCII,
        "event": EVENT_FR_ASCII, "when": WHEN_FR_ASCII, "city": CITY_W_FR, "d2x": DAY_W_FR_ASCII,
        "iv": ["un peu", "beaucoup", "encore", "a fond", "au maximum"],
        "lvl": ["moitie", "fond", "dix", "vingt", "zero"],
        "pm": ["plus", "moins"], "more": ["plus", "moins"],
        "pousse": ["pousse", "remonte", "redescends"],
        "qq": ["la", "maintenant", "au juste", "exactement"],
        "name": ["lea", "hugo", "chloe", "louis", "emma", "gabriel"],
        "langto": ["anglais", "espagnol", "allemand", "italien", "portugais"],
        "landmark": ["la tour eiffel", "le louvre", "le mont-blanc", "la seine",
                     "le colisee", "les pyramides"],
        "meal": ["ce soir", "pour diner", "ce week-end", "demain soir", "pour dejeuner", "dimanche"],
        "thing": ["couleur", "film", "chanson", "livre", "plat", "animal"],
        # R3 fix (ASCII mirror of plural-only subjects above).
        "subject": ["devoirs", "maths", "dissertations", "exposes de sciences", "revisions d'histoire"],
        "game": ["echecs", "quiz", "trivial pursuit", "pendu", "cartes"],
        "word": ["necessaire", "rythme", "serendipite", "embarrasser", "brocoli", "mnemotechnique"],
        "where": ["au centre-ville", "sur l'autoroute", "pres de l'aeroport", "rue principale"],
        "stuffy": ["lourd", "glacial", "humide", "sec"],
        "dream": ["voler", "etre en retard", "un examen oublie", "une plage", "mes dents qui tombent"],
        "lull": ["berceuse", "chanson pour m'endormir", "chanson douce"],
        "device": ["reveil", "enceinte", "radio", "lampe"],
        "plat": ["poulet", "poisson", "riz", "legumes", "boeuf", "salade"],
        "daydream": ["vacances", "plage", "week-end", "sieste", "voyage"],
        "piece": ["l'etage", "le salon", "la chambre", "le jardin"],
        "artfr": ["la joconde", "la nuit etoilee", "guernica", "le cri",
                  "la jeune fille a la perle"],
        "audfr": ["la musique", "la chanson", "le morceau", "la playlist"],
        "sfr": ["la suivante", "la prochaine", "la chanson suivante"],
        "sfr2": ["la lecture", "le morceau", "la chanson"],
        "sfr3": ["cette chanson", "ce morceau", "ce titre"],
    },
    "mix": {
        "t": T_EN + T_FR_ASCII, "d": DAY_EN + DAY_FR_ASCII, "d2": DAY_W_EN + DAY_W_FR_ASCII,
        "du": DUR_EN + DUR_FR_ASCII, "ex": EXTRA_MIN, "pl": PLAY_EN + PLAY_FR_ASCII,
        "a": NUM1, "b": NUM1, "country": COUNTRY_EN, "topic": TOPIC_EN,
        "task": TASK_EN + TASK_FR_ASCII, "food": FOOD_EN, "sport": SPORT_EN,
        "event": EVENT_EN + EVENT_FR_ASCII, "when": WHEN_EN + WHEN_FR_ASCII,
        "city": CITY_W_EN + CITY_W_FR, "iv": ["un peu", "a bit", "encore", "a little", "bien"],
        "ud": ["up", "down"], "thing": ["color", "film", "chanson", "book", "plat"],
        "qq": ["la", "maintenant", "au juste"],
        "meal": ["tonight", "ce soir", "tomorrow", "demain", "this weekend", "ce week-end"],
        "stuffy": ["stuffy", "lourd", "freezing", "glacial"],
        "name": ["alice", "lea", "hugo", "bob", "emma", "louis"],
    },
}

EN_PRE = ["", "", "", "", "hey, ", "hey nest, ", "um, ", "uh, ", "okay, "]
EN_POST = ["", "", "", "", " please", " thanks"]
FR_PRE_ACC = ["", "", "", "", "dis, ", "euh, ", "ben, ", "alors, ", "hey nest, "]
FR_PRE_ASCII = ["", "", "", "", "dis, ", "euh, ", "ben, ", "alors, ", "hey nest, "]
FR_POST_ACC = ["", "", "", "", " s'il te plaît", " merci"]
FR_POST_ASCII = ["", "", "", "", " stp", " merci"]
MIX_PRE = ["", "", "", "", "hey nest, ", "euh, ", "um, "]
MIX_POST = ["", "", "", "", " please", " stp", " s'il te plaît"]

# ============================================================ TRAIN templates
# ---- alarm en train
ALARM_EN_TR = [
    "wake me up at {t}", "set an alarm for {t}", "set an alarm for {t} {d}",
    "can you wake me up at {t}", "i need to get up at {t} {d}",
    "put an alarm on for {t}", "create an alarm for {t} {d}",
    "wake me at {t} {d}", "set my alarm to {t}", "i have to be up by {t} {d}",
    "cancel my alarm", "turn off the alarm", "delete the {t} alarm",
    "switch off my alarm for {d}", "remove my {t} alarm", "kill the alarm",
    "cancel the alarm for {d}", "disable my morning alarm",
    "snooze the alarm", "snooze it for ten minutes", "push the alarm back a bit",
    "change my alarm to {t}", "move my alarm to {t}", "shift the alarm to {t}",
    "is my alarm still set", "do i have an alarm set for {d}",
    "check whether my alarm is on", "is the {t} alarm active",
    "set a recurring alarm for {t} {d}", "remind me with an alarm at {t}",
    "wake me up in time for work at {t}", "make sure i'm up by {t}",
]
ALARM_EN_EV = [
    "get me up at {t}", "i need an alarm at {t} {d}", "program an alarm for {t}",
    "please wake me at {t} {d}", "set a wake-up alarm for {t}",
    "i want to be woken at {t}", "alarm at {t} {d}, make it happen",
    "turn my alarm off", "shut off the alarm", "erase the {t} alarm",
    "call off my alarm for {d}", "deactivate the alarm",
    "hit snooze on the alarm", "delay the alarm by five minutes",
    "reschedule my alarm for {t}", "push my alarm to {t}",
    "is my morning alarm enabled", "tell me if my alarm is set",
    "wake me {d} at {t}", "set two alarms starting at {t}",
]
ALARM_FR_TR_ACC = [
    "mets une alarme pour {t}", "réveille-moi à {t}", "peux-tu me réveiller à {t} {d}",
    "programme une alarme pour {t} {d}", "j'ai besoin de me lever à {t} {d}",
    "mets une alarme tous les jours à {t}", "crée une alarme pour {t}",
    "réveille-moi {d} à {t}",
    "annule l'alarme", "éteins l'alarme", "supprime l'alarme de {t}",
    "désactive mon alarme", "coupe l'alarme du matin",
    "repousse l'alarme", "repousse l'alarme de dix minutes",
    "change l'alarme à {t}", "décale mon alarme à {t}",
    "est-ce que mon alarme est toujours active", "mon alarme est-elle encore activée",
    "vérifie que mon alarme est bien mise",
]
ALARM_FR_TR_ASCII = [
    "mets une alarme pour {t}", "reveille-moi a {t}", "peux-tu me reveiller a {t} {d}",
    "programme une alarme pour {t} {d}", "j'ai besoin de me lever a {t} {d}",
    "mets une alarme tous les jours a {t}", "cree une alarme pour {t}",
    "reveille-moi {d} a {t}",
    "annule l'alarme", "eteins l'alarme", "supprime l'alarme de {t}",
    "desactive mon alarme", "coupe l'alarme du matin",
    "repousse l'alarme", "repousse l'alarme de dix minutes",
    "change l'alarme a {t}", "decale mon alarme a {t}",
    "est-ce que mon alarme est toujours active", "mon alarme est-elle encore activee",
    "verifie que mon alarme est bien mise",
]
ALARM_FR_EV_ACC = [
    "mets-moi une alarme à {t} {d}", "je veux une alarme pour {t}",
    # R1 fix round 2: was 'réveille-moi demain à {t}' which collides row-level
    # with train 'réveille-moi {d} à {t}' when {d} draws 'demain' (day words
    # are slot-masked, both give 'reveille moi SLOT a NUM'). Added 'matin'.
    "réveille-moi demain matin à {t}", "ajoute une alarme à {t}",
    "enlève l'alarme de {t}", "arrête l'alarme",
    "mets l'alarme en pause", "retarde l'alarme de cinq minutes",
    "modifie mon alarme pour {t}", "l'alarme est-elle bien réglée",
    "dis-moi si mon alarme sonnera {d}",
]
ALARM_FR_EV_ASCII = [
    "mets-moi une alarme a {t} {d}", "je veux une alarme pour {t}",
    # R1 fix round 2 (ASCII mirror).
    "reveille-moi demain matin a {t}", "ajoute une alarme a {t}",
    "enleve l'alarme de {t}", "arrete l'alarme",
    "retarde l'alarme de cinq minutes",
    "modifie mon alarme pour {t}", "l'alarme est-elle bien reglee",
    "dis-moi si mon alarme sonnera {d}",
]
ALARM_MIX_TR = [
    "mets une alarme for {t} demain", "can you wake me up à {t}",
    "set an alarm pour {d} matin", "cancel mon alarme de {t}",
    "reveille-moi at {t} please", "snooze l'alarme for ten minutes",
    "change mon alarme to {t}", "est-ce que my alarm is still set",
    "delete l'alarme de {t}", "set une alarme every weekday at {t}",
]
ALARM_MIX_EV = [
    "wake me up à {t} {d}", "mets an alarm pour {t}",
    "turn off mon alarme stp", "repousse the alarm de dix minutes",
    "is mon alarme still active", "programme an alarm for {t} {d}",
    "supprime my {t} alarm", "decales mon alarm à {t}",
]

# ---- timer en
TIMER_EN_TR = [
    "set a timer for {du}", "start a {du} timer", "launch a countdown of {du}",
    "put on a timer for {du}", "start counting down {du}",
    "how much time is left on the timer", "how long is left on my timer",
    "is the timer still running", "check the timer for me",
    "how far along is the timer", "tell me the remaining time",
    "cancel the timer", "stop the timer", "kill the timer", "clear the timer",
    "pause the timer", "hold the timer", "freeze the countdown",
    "resume the timer", "restart the timer", "restart the countdown",
    "add {ex} to the timer", "take two minutes off the timer",
    "extend the timer by {ex}", "set a countdown for {du}",
    "give me a {du} countdown", "how much longer on the countdown",
]
TIMER_EN_EV = [
    "i need a timer for {du}", "kick off a {du} timer", "run a countdown of {du}",
    "how much time remains on the timer", "what's left on my timer",
    "is my countdown still going", "where is my timer at",
    "call off the timer", "end the timer now",
    "put the timer on hold", "unpause the timer",
    "start the timer over", "tack on {ex} to the timer",
    "lengthen my timer by {ex}", "begin a {du} countdown",
]
# ---- timer fr: idiomatic status-check cluster vs general
TIMER_FR_IDIOM_ACC = [
    "où en est le minuteur", "où en est mon minuteur", "ça en est où le minuteur",
    "ça en est où, le minuteur", "il en est où le minuteur", "on en est où avec le minuteur",
    "où ça en est le minuteur", "le minuteur en est où",
    "où en est le compte à rebours", "ça en est où le compte à rebours",
    "il en est où le compte à rebours", "on en est où du compte à rebours",
    "combien de temps il reste sur le minuteur", "il reste combien sur le minuteur",
    "il reste combien de temps au minuteur", "combien de temps restant au minuteur",
    "c'est où le minuteur là", "le minuteur il en est où là",
    "dis-moi où en est le minuteur", "tu peux me dire où en est le minuteur",
    "où en est le minuteur de {du}", "ça en est où le minuteur de {du}",
    "il en est où le minuteur de {du}", "il reste combien au minuteur de {du}",
    "où en est le minuteur {qq}", "le minuteur en est où {qq}",
    "ça en est où le minuteur {qq}", "il reste combien sur le minuteur {qq}",
]
TIMER_FR_IDIOM_ASCII = [
    "ou en est le minuteur", "ou en est mon minuteur", "ca en est ou le minuteur",
    "ca en est ou, le minuteur", "il en est ou le minuteur", "on en est ou avec le minuteur",
    "ou ca en est le minuteur", "le minuteur en est ou",
    "ou en est le compte a rebours", "ca en est ou le compte a rebours",
    "il en est ou le compte a rebours", "on en est ou du compte a rebours",
    "combien de temps il reste sur le minuteur", "il reste combien sur le minuteur",
    "il reste combien de temps au minuteur", "combien de temps restant au minuteur",
    "c'est ou le minuteur la", "le minuteur il en est ou la",
    "dis-moi ou en est le minuteur", "tu peux me dire ou en est le minuteur",
    "ou en est le minuteur de {du}", "ca en est ou le minuteur de {du}",
    "il en est ou le minuteur de {du}", "il reste combien au minuteur de {du}",
    "ou en est le minuteur {qq}", "le minuteur en est ou {qq}",
    "ca en est ou le minuteur {qq}", "il reste combien sur le minuteur {qq}",
]
TIMER_FR_GEN_ACC = [
    "lance un minuteur de {du}", "mets un minuteur de {du}", "démarre un compte à rebours de {du}",
    "lance un chrono de {du}", "mets un chrono de {du}",
    "annule le minuteur", "arrête le minuteur", "supprime le minuteur",
    "mets en pause le minuteur", "mets le minuteur sur pause",
    "reprends le minuteur", "redémarre le minuteur", "relance le minuteur",
    "ajoute {ex} au minuteur", "rajoute {ex} au minuteur", "prolonge le minuteur de {ex}",
    "enlève deux minutes au minuteur", "le minuteur est-il encore en marche",
    "est-ce que le minuteur tourne toujours", "vérifie le minuteur",
]
TIMER_FR_GEN_ASCII = [
    "lance un minuteur de {du}", "mets un minuteur de {du}", "demarre un compte a rebours de {du}",
    "lance un chrono de {du}", "mets un chrono de {du}",
    "annule le minuteur", "arrete le minuteur", "supprime le minuteur",
    "mets en pause le minuteur", "mets le minuteur sur pause",
    "reprends le minuteur", "redemarre le minuteur", "relance le minuteur",
    "ajoute {ex} au minuteur", "rajoute {ex} au minuteur", "prolonge le minuteur de {ex}",
    "enleve deux minutes au minuteur", "le minuteur est-il encore en marche",
    "est-ce que le minuteur tourne toujours", "verifie le minuteur",
]
TIMER_FR_IDIOM_EV_ACC = [
    "le minuteur, ça en est où",
    # R1 fix: replaced 'alors, où en est le minuteur' (stripped -> 'ou en est
    # le minuteur', identical to a train template). Novel: different pronoun
    # structure, still idiom ('on en est où').
    "alors, on en est où du minuteur",
    "le compte à rebours en est où", "il en est où, mon chrono",
    "on en est où là avec le minuteur",
    # R1 fix: replaced 'dis, le minuteur en est où' (stripped -> 'le minuteur
    # en est ou', identical to train). Novel determiner 'ce'.
    "dis, où en est ce minuteur",
    "reste combien au minuteur", "combien il reste au chrono",
    "le minuteur, il reste combien de temps", "où en est le chrono",
    # R1 fix: replaced 'où en est le minuteur de {du}' (identical to train).
    # Novel noun+determiner, still idiom.
    "où en est ce chrono de {du}",
    # R1 fix: replaced 'il reste combien au minuteur de {du}' (identical to
    # train). Novel preposition+determiner+duration noun, still idiom.
    "il reste combien de temps sur ce minuteur de {du}",
    "le chrono en est où {qq}", "ça en est où le chrono de {du}",
]
TIMER_FR_IDIOM_EV_ASCII = [
    "le minuteur, ca en est ou",
    # R1 fix (ASCII mirror of above).
    "alors, on en est ou du minuteur",
    "le compte a rebours en est ou", "il en est ou, mon chrono",
    "on en est ou la avec le minuteur",
    # R1 fix (ASCII mirror).
    "dis, ou en est ce minuteur",
    "reste combien au minuteur", "combien il reste au chrono",
    "le minuteur, il reste combien de temps", "ou en est le chrono",
    # R1 fix (ASCII mirrors).
    "ou en est ce chrono de {du}",
    "il reste combien de temps sur ce minuteur de {du}",
    "le chrono en est ou {qq}", "ca en est ou le chrono de {du}",
]
TIMER_FR_GEN_EV_ACC = [
    "déclenche un minuteur de {du}", "programme un minuteur de {du}",
    "mets en route un compte à rebours de {du}", "stoppe le minuteur",
    "mets le chrono en pause", "fais reprendre le minuteur",
    "recommence le minuteur", "ajoute encore {ex} au minuteur",
    "le minuteur tourne-t-il encore", "regarde où en est mon minuteur s'il te plaît",
]
TIMER_FR_GEN_EV_ASCII = [
    "declenche un minuteur de {du}", "programme un minuteur de {du}",
    "mets en route un compte a rebours de {du}", "stoppe le minuteur",
    "mets le chrono en pause", "fais reprendre le minuteur",
    "recommence le minuteur", "ajoute encore {ex} au minuteur",
    "le minuteur tourne-t-il encore",
]
TIMER_MIX_TR = [
    "can you lancer un minuteur de {du}", "start a timer pour {du}",
    "cancel le timer please", "mets en pause the timer",
    "ou en est the timer", "combien de temps left sur le minuteur",
    "restart le minuteur stp", "ajoute {ex} to the timer",
    "lance a countdown de {du}", "is le minuteur still running",
]
TIMER_MIX_EV = [
    # R2 fix: was 'lance un timer de {du} please' (FR + please-only weak when
    # du is neutral/FR like '5 minutes'/'une heure'). 'now' is strong EN.
    "lance un timer de {du} now please",
    # R2 fix: was 'pause le timer deux secondes' (all FR/neutral, no EN).
    "pause le timer deux secondes now",
    "ca en est ou the timer", "stop le minuteur now",
    "remets {ex} on the timer", "le timer tourne-t-il still",
    "start le compte à rebours de {du}", "kill le timer stp",
]

# ---- music: playback vs volume cluster
MUSIC_PLAY_EN_TR = [
    "play some music", "put on {pl}", "play {pl}", "play {pl} {when}",
    "shuffle {pl}", "shuffle {pl} {when}", "play something relaxing",
    "play my {daypart} playlist", "skip to {s}", "{skipv} this song",
    "play the next track", "go to the next song",
    "pause the {aud}", "stop the {aud}", "cut the music",
    "resume playback", "keep playing", "restart {s2}",
    "what's playing right now", "who sings {s3}",
]
MUSIC_VOL_EN_TR = [
    "turn up the volume {iv}", "turn down the volume {iv}",
    "turn it {ud} {iv}", "turn it {ud} a touch",
    "{crank} it {ud}", "make it {lj}",
    "set the volume to {pct}", "{mutev} the speaker",
    "volume {ud} please", "raise the sound {iv}", "lower the sound {iv}",
    "notch the volume {ud}", "bring the volume {udx}",
    "turn the music {ud} {iv}", "turn the sound {ud} {iv}",
    "soften the music {iv}", "blast it a little louder",
    "dial the volume back {iv}", "pump up the volume {iv}",
]
MUSIC_PLAY_EN_EV = [
    "throw on {pl}", "start playing {pl}", "i want to hear {pl}",
    "next song please", "skip this one", "jump to the next track",
    "hold the music", "cease playback", "pick up where we left off",
    "play that again", "who is this artist",
    # R1 fix: replaced 'play {pl} {when}' (identical to train 'play {pl}
    # {when}'). Novel verb, still playback.
    "cue up {pl} {when}",
]
MUSIC_VOL_EN_EV = [
    "bump the volume {ud} {iv}", "drop the volume {iv}",
    "raise the sound a bit", "soften the music a touch",
    "blast it louder", "dial the volume back",
    "silence the speaker for a sec", "bring the sound back up",
    "notch the volume {ud} {iv}", "turn that racket {ud}",
    "set volume to {pct}", "make the music {lj}",
]
MUSIC_PLAY_FR_TR_ACC = [
    "mets de la musique", "mets {pl}", "mets {pl} {when}", "joue {pl}",
    "joue {pl} {when}", "mélange {pl}", "joue quelque chose de calme",
    "mets ma playlist du matin", "mélange ma musique",
    "passe à la chanson suivante", "passe à {sfr}",
    "chanson suivante", "mets {audfr}", "mets la musique en pause",
    "coupe {audfr}", "arrête la chanson", "reprends {sfr2}",
    "recommence {sfr2}", "qui chante {sfr3}",
]
MUSIC_VOL_FR_TR_ACC = [
    "monte le son {iv}", "baisse le son {iv}",
    "monte le volume {iv}", "baisse le volume {iv}",
    "augmente le volume {iv}", "diminue le volume {iv}",
    "mets {more} fort", "mets le son {more} fort",
    "mets le volume {more} fort", "coupe le son", "remets le son",
    "{pousse} le son {iv}", "{pousse} le volume {iv}",
    "mets le son à {lvl}", "mets le volume à {lvl}",
    "fais pas trop fort", "ne mets pas le son trop fort",
]
MUSIC_PLAY_FR_TR_ASCII = [
    "mets de la musique", "mets {pl}", "mets {pl} {when}", "joue {pl}",
    "joue {pl} {when}", "melange {pl}", "joue quelque chose de calme",
    "mets ma playlist du matin", "melange ma musique",
    "passe a la chanson suivante", "passe a {sfr}",
    "chanson suivante", "mets {audfr}", "mets la musique en pause",
    "coupe {audfr}", "arrete la chanson", "reprends {sfr2}",
    "recommence {sfr2}", "qui chante {sfr3}",
]
MUSIC_VOL_FR_TR_ASCII = [
    "monte le son {iv}", "baisse le son {iv}",
    "monte le volume {iv}", "baisse le volume {iv}",
    "augmente le volume {iv}", "diminue le volume {iv}",
    "mets {more} fort", "mets le son {more} fort",
    "mets le volume {more} fort", "coupe le son", "remets le son",
    "{pousse} le son {iv}", "{pousse} le volume {iv}",
    "mets le son a {lvl}", "mets le volume a {lvl}",
    "fais pas trop fort", "ne mets pas le son trop fort",
]
MUSIC_PLAY_FR_EV_ACC = [
    "lance {pl}", "lance {pl} {when}",
    # R1 fix: replaced 'balance {pl}' (decoration-stripped -> 'balance slot',
    # identical to train-mixed 'balance {pl} stp' stripped). Novel verb.
    "envoie {pl}", "je veux écouter {pl}",
    # R1 fix round 2: was 'passe à la suivante' which collides row-level with
    # train 'passe à {sfr}' when sfr draws 'la suivante' (both give
    # 'passe a la suivante' after masking). Novel verb 'saute'.
    "saute à la suivante", "zappe cette chanson",
    "fais une pause sur la musique", "continue la lecture",
    "remets cette chanson depuis le début",
]
MUSIC_PLAY_FR_EV_ASCII = [
    "lance {pl}", "lance {pl} {when}",
    # R1 fix (ASCII mirror).
    "envoie {pl}", "je veux ecouter {pl}",
    # R1 fix round 2 (ASCII mirror).
    "saute a la suivante", "zappe cette chanson",
    "fais une pause sur la musique", "continue la lecture",
    "remets cette chanson depuis le debut",
]
MUSIC_VOL_FR_EV_ASCII = [
    # R1 fix: all 7 previously overlapping volume templates below were
    # slot-masked-identical to train (e.g. 'monte le son SLOT'). Each keeps a
    # volume keyword (monte/baisse/mets/coupe -> still counts for cluster
    # (b)) but adds surviving structure ('d'un cran', 'd'un coup', 'direct')
    # so decoration-stripped keys are novel.
    "monte le son d'un cran {iv}", "baisse le son d'un cran {iv}",
    "monte le volume d'un cran {iv}", "baisse le volume d'un cran {iv}",
    "mets {more} fort d'un coup", "encore {more} fort", "mets le son au {lvl} directement",
    "coupe le son direct", "un peu plus fort", "un peu moins fort",
]
MUSIC_VOL_FR_EV_ACC = [
    # R1 fix (ACC mirrors): 'd'un cran' / 'd'un coup' / 'directement' survive
    # decoration-stripping (unlike 's'il te plaît'), so keys are novel while
    # volume keywords keep cluster (b) counts.
    "monte le son d'un cran {iv} s'il te plaît", "baisse le volume d'un cran {iv}",
    "mets le son {more} fort d'un coup", "mets le son au {lvl} directement",
    "augmente le volume d'un cran {iv}", "diminue le son {iv}",
]
MUSIC_MIX_TR_PLAY = [
    # R2 fix: every template below is now inherently mixed in its FIXED words
    # (not relying on slot draws or weak please/stp alone). 'play'+'pour moi',
    # 'mets'+'on shuffle'/'for me', 'joue'+'now'/'for me', 'pause'+'now'.
    # NOTE: 'balance' avoided: it appears only in mixed rows so the
    # verifier's data-driven lexicon (en/fr rows) would count it as neutral.
    # 'mets'/'joue' appear in FR rows -> FR-only evidence.
    "play {pl} pour moi", "play {pl} {when} pour moi", "mets {pl} on shuffle now",
    "mets {pl} {when} on shuffle now",
    "joue {pl} now please", "skip à la next song", "pause la musique now please",
    "joue my morning playlist", "reprends the playback stp",
    "lance {pl} for me", "mets {pl} for me stp",
]
MUSIC_MIX_TR_VOL = [
    "turn up le son {iv}", "turn down le son {iv}",
    "baisse the volume {iv}", "monte the volume {iv}",
    # R2 fix: was 'turn it {ud} {iv} stp' (stp-only weak when iv is EN).
    # 'pour moi' is strong FR content, so EN+FR regardless of iv.
    "turn it {ud} {iv} pour moi", "mets le volume {ud}",
    # R2 fix: were pure-FR when iv drew FR ('un peu'/'bien'/'encore').
    # Trailing 'now' (EN content, survives deco-strip) forces mixing.
    "baisse le son {iv} now", "monte le son {iv} now",
    "crank up le volume {iv}", "mets the volume louder",
]
MUSIC_MIX_EV_PLAY = [
    # R2 fix: was 'lance {pl} stp' (FR + stp-only weak when pl is FR).
    "lance {pl} now stp",
    # R1+R2 fix: was 'mets {pl} please' (stripped -> 'mets slot', overlapping
    # train 'mets {pl}'; plus FR+please-only weak when pl is FR).
    "mets {pl} now please",
    # R1+R2 fix: was 'play {pl} {when}' (identical to train; plus pure-EN when
    # both slots draw EN). 'maintenant' forces FR content + novel key.
    # NOTE: train uses '...pour moi'; eval uses '...maintenant' so the two
    # banks stay disjoint (not the same fix on both sides).
    "play {pl} {when} maintenant",
    "next chanson stp", "mets en pause the music",
    # R2 fix: 'rejoue' appears only in mixed rows (neutral to the verifier's
    # data-driven lexicon), so keep strong FR 'cette' + strong EN 'now'.
    # Was 'rejoue cette track' (FR + neutral 'track' -> pure FR).
    "rejoue cette track now",
    # R1+R2 fix: was 'balance {pl} stp' (identical to train stripped; plus
    # 'balance' neutral to data-driven). 'joue' is FR-only via FR rows.
    "joue {pl} for me stp",
]
MUSIC_MIX_EV_VOL = [
    "turn {ud} le volume {iv}",
    # R1+R2 fix: was 'monte le son {iv}' (identical to train; pure-FR when iv
    # is FR). 'right now' forces EN + novel key. NOTE: train uses lone 'now';
    # eval uses 'right now' so banks stay disjoint.
    "monte le son {iv} right now",
    # R1 fix: was 'baisse the volume {iv}' (identical to train-mixed).
    # Trailing 'un peu' (strong FR) keeps mixing + novel key.
    # R2 fix round 2: was 'mute le son stp' ('mute' appears only in mixed
    # rows when unsampled in EN, so row-derived lexicon counts it neutral and
    # auto-flags; manual review saves it, but add 'now' so it passes
    # automatically too).
    "baisse the volume {iv} un peu", "mute le son now stp",
    "plus fort the music please", "mets le son louder",
]

# ---- weather
WEATHER_EN_TR = [
    "what's the weather like in {city} {d2}", "how's the weather in {city} {d2}",
    "is it going to rain in {city} {d2}", "will it rain in {city} {d2}",
    "what's the temperature in {city} {d2}", "how cold is it in {city} right now",
    "will it snow in {city} {d2}", "is it supposed to {wx} in {city} {d2}",
    "do i need an umbrella in {city} {d2}", "should i bring a jacket {d2}",
    "what's the forecast for {city} {d2}", "give me the {d2} forecast for {city}",
    "is it sunny in {city} right now", "is it cloudy in {city} {d2}",
    "how windy is it in {city} {d2}", "what's the humidity like in {city}",
    "will it be sunny in {city} {d2}", "any storms coming to {city} {d2}",
    "what's the high for {city} {d2}", "how warm will it get in {city} {d2}",
    "is it supposed to snow this weekend", "do i need sunglasses in {city} today",
]
WEATHER_EN_EV = [
    "tell me the weather in {city} {d2}", "how does it look in {city} {d2}",
    "any rain expected in {city} {d2}", "is rain on the way to {city}",
    "how hot is it in {city} right now", "what does it feel like in {city} {d2}",
    "are we getting snow in {city} {d2}", "do i need sunglasses in {city} {d2}",
    "should i grab an umbrella for {city}", "what's the outlook for {city} {d2}",
    "is the sun out in {city}", "how strong is the wind in {city} {d2}",
    "will the skies clear over {city} {d2}", "what's the low in {city} tonight",
    # R1 fix round 2: was 'will it {wx} in {city} {d2}' which collides
    # row-level with train 'will it snow in {city} {d2}' when wx draws 'snow'
    # (weather words are not slot-masked). Novel structure.
    "will we get {wx} in {city} {d2}", "how cold will it get in {city} {d2}",
]
WEATHER_FR_TR_ACC = [
    "quel temps fait-il à {city} {d2}", "il fait quel temps à {city} {d2}",
    "va-t-il pleuvoir à {city} {d2}", "est-ce qu'il va pleuvoir à {city} {d2}",
    "quelle est la température à {city} {d2}", "il fait combien à {city} {d2}",
    "va-t-il neiger à {city} {d2}", "est-ce qu'il va neiger à {city} {d2}",
    "faut-il prendre un parapluie à {city} {d2}", "ai-je besoin d'un parapluie {d2}",
    "quelles sont les prévisions pour {city} {d2}", "donne-moi la météo de {city} {d2}",
    "fait-il beau à {city} {d2}", "est-ce qu'il fait soleil à {city}",
    "y a-t-il du vent à {city} {d2}", "il y a beaucoup de vent à {city}",
    "va-t-il faire beau à {city} {d2}", "quelle est la maximale à {city} {d2}",
    "est-ce qu'il va faire froid à {city} {d2}", "quel temps fera-t-il à {city} {d2}",
    "dois-je prendre une veste {d2}", "il pleut en ce moment à {city}",
]
WEATHER_FR_TR_ASCII = [
    "quel temps fait-il a {city} {d2}", "il fait quel temps a {city} {d2}",
    "va-t-il pleuvoir a {city} {d2}", "est-ce qu'il va pleuvoir a {city} {d2}",
    "quelle est la temperature a {city} {d2}", "il fait combien a {city} {d2}",
    "va-t-il neiger a {city} {d2}", "est-ce qu'il va neiger a {city} {d2}",
    "faut-il prendre un parapluie a {city} {d2}", "ai-je besoin d'un parapluie {d2}",
    "quelles sont les previsions pour {city} {d2}", "donne-moi la meteo de {city} {d2}",
    "fait-il beau a {city} {d2}", "est-ce qu'il fait soleil a {city}",
    "y a-t-il du vent a {city} {d2}", "il y a beaucoup de vent a {city}",
    "va-t-il faire beau a {city} {d2}", "quelle est la maximale a {city} {d2}",
    "est-ce qu'il va faire froid a {city} {d2}", "quel temps fera-t-il a {city} {d2}",
    "dois-je prendre une veste {d2}", "il pleut en ce moment a {city}",
]
WEATHER_FR_EV_ACC = [
    # R1 fix: replaced 'donne-moi la météo de {city} {d2}' (identical to
    # train). Novel interrogative, still weather.
    "c'est quoi la météo à {city} {d2}", "il pleut à {city} en ce moment",
    # R1 fix: replaced "est-ce qu'il va pleuvoir à {city} {d2}" (identical to
    # train). Novel 'sur ... ou pas' structure, still weather/rain.
    "il va pleuvoir sur {city} {d2} ou pas", "quelle température il fait à {city}",
    "il neige sur {city}", "dois-je prendre une veste pour {city}",
    "les prévisions de {city} {d2} s'il te plaît", "c'est ensoleillé à {city}",
    "le vent souffle fort à {city}", "il fera combien à {city} {d2}",
    "quel temps à {city} {d2}", "est-ce qu'il gèle à {city} {d2}",
]
WEATHER_FR_EV_ASCII = [
    # R1 fix (ASCII mirrors).
    "c'est quoi la meteo a {city} {d2}", "il pleut a {city} en ce moment",
    "est-ce qu il pleut sur {city} {d2}", "quelle temperature il fait a {city}",
    "dois-je prendre une veste pour {city}", "il fera combien a {city} {d2}",
    "c'est ensoleille a {city}", "quel temps a {city} {d2}",
    "est-ce qu'il gele a {city} {d2}",
]
# R2 fix: WEATHER_MIX_TR/EV templates below are now inherently mixed in fixed
# words. Previously 'va-t-il faire beau...' and 'du vent...ou pas' were pure
# FR when slots drew FR; 'la météo de...stp' / 'temperature de...please' were
# FR + weak-affix-only when slots drew FR.
WEATHER_MIX_TR = [
    "what's la météo à {city} {d2}", "is it going to pleuvoir à {city} {d2}",
    "quelle est the temperature à {city}",
    "tell me va-t-il faire beau à {city} {d2}",
    "dois-je prendre un umbrella pour {city}", "il fait sunny à {city}",
    "what's la forecast pour {city} {d2}", "est-ce qu'il va snow à {city} {d2}",
    "how's la météo à {city} {d2}", "is there du vent à {city} {d2} ou pas",
]
WEATHER_MIX_EV = [
    "tell me la météo de {city} {d2} stp", "will it pleuvoir à {city} {d2}",
    "how's la météo à {city}", "fait-il cold à {city}",
    "temperature de {city} {d2} now please", "du vent today à {city} ou pas",
    "is it sunny à {city} {d2}", "il va neiger à {city} {d2} or not",
]

# ---- fallback: general vs boundary-stress
FALLBACK_GEN_EN_TR = [
    "what time is it", "tell me a joke about {topic}", "what's the capital of {country}",
    "can you help me with my {subject}", "what's {a} plus {b}",
    "what is {a} times {b}", "tell me something interesting about {topic}",
    "how are you today", "how's it going {when}", "what's your name",
    "can you explain {topic} to me", "let's play {game}",
    "play a game with me", "umm so like", "i don't know what i want",
    "read me the {news} news headlines", "how old are you",
    "what's your favorite {thing}", "tell me a fun fact about {topic}",
    "what's the meaning of life", "who won the {sport} game last night",
    "what should i cook {meal}", "how do you spell {word}",
    "translate hello into {langto}", "what's on tv {meal}",
    "remind me to {task}", "how many days until {holiday}",
    "tell me about the roman empire", "teach me about {topic}",
    "i'm bored, entertain me", "what's the traffic like {where}",
    "give me a recipe for {food}", "how tall is {landmark}",
    "what does {word3} mean", "who painted {art}",
    "can you do math for me", "what's new in tech today",
]
FALLBACK_BND_EN_TR = [
    "my alarm didn't go off {when} and i was late",
    "that song on the radio {when} was great",
    "i love that tune on the radio {when}",
    "is it too loud in here or is it just me",
    "what time does the {event} start {when}",
    "can you set the mood with some {candles}",
    "the air in here feels {stuffy}, open a window",
    "my morning routine is a mess, help me {org}",
    "i had a dream about {dream} last night",
    "do you think it'll be a good day {when}",
    # Resubmit checklist #5: 'good day' boundary was unsampled (0 rows).
    # Weight it 3x with distinct paraphrases so >=3 rows are guaranteed.
    "think it'll be a good day {when}, huh",
    "will it be a good day {when}, you reckon",
    "turn it, turn it, oh never mind",
    "that playlist {when} was great by the way",
    "what song is playing on the radio {when}",
    "is the kitchen timer loud enough to hear {where}",
    "i need to buy a new {device}, any advice",
    # R3 fix: was 'sing me a {lull} to fall asleep' which duplicated with
    # lull slot 'song to fall asleep to' -> '...to to fall asleep'. Bare
    # '{lull}' fits all slot values ('a lullaby', 'a song to fall asleep to').
    "sing me a {lull}",
    "wake up, i think we're {late}",
    "time flies when you're having fun",
    "the forecast says my team will win, you agree",
    "it might rain on my parade {when}, figuratively",
    "volume one of the encyclopedia, chapter {a}",
    "my watch stopped ticking, what time do you have",
    "play it by ear, we'll see how it goes",
    "how do metronomes keep time so steadily",
    "is there static in this recording or my ears",
    "the radio weather guy is always {wrong}",
    "humming that melody {when}, sorry",
    "that alarm at the office kept ringing {when}",
]
FALLBACK_GEN_EN_EV = [
    "what day is it today", "make me laugh about {topic}",
    "which artist painted {art}", "help me study my {subject}",
    "what is {a} minus {b}", "how is your day going {when}",
    "do you have a name", "explain {topic} to me",
    "i feel like chatting", "hmm, let me think for a second",
    "give me a recipe with {food}", "how high is {landmark}",
    "define {word3} for me", "any news about {topic} today",
    "what's your opinion on {topic}", "tell {name} I said hi",
]
FALLBACK_BND_EN_EV = [
    "the alarm at the office kept ringing {when}",
    "that tune is stuck in my head {when}",
    "could you speak up, i can barely hear you",
    "what time do the shops close {when}",
    "my sleep schedule is all over the place",
    "is this mic even on right now",
    "{when} it poured and i forgot my coat",
    "i'm just thinking out loud here, ignore me",
    "do clocks dream of electric sheep",
    "that weather guy on the radio is always {wrong}",
    "humming that melody {when} again, sorry",
    "remind me what i was saying {when}",
    "my {device} stopped working {when}",
    "is that feedback or my ears ringing",
]
FALLBACK_GEN_FR_TR_ACC = [
    "quelle heure est-il", "raconte-moi une blague sur {topic}",
    "quelle est la capitale de {country}", "peux-tu m'aider avec mes {subject}",
    "combien font {a} plus {b}", "combien font {a} fois {b}",
    "dis-moi quelque chose d'intéressant sur {topic}", "comment vas-tu aujourd'hui",
    "comment tu t'appelles", "peux-tu m'expliquer {topic}",
    "raconte-moi une histoire sur {topic}", "euh ouais donc en fait",
    "je ne sais pas ce que je veux", "lis-moi les nouvelles {when}",
    "quel âge as-tu", "quelle est ta {thing} préférée",
    "qui a gagné le match de {sport} hier soir", "qu'est-ce que je cuisine {meal}",
    "comment ça s'écrit, {word}", "traduis bonjour en {langto}",
    "rappelle-moi de {task}", "c'est quand {holiday}",
    "je m'ennuie, distrais-moi", "explique-moi {topic}",
    "jouons à {game}", "donne-moi une recette de {food}",
    "parle-moi de {landmark}", "tu connais {name}",
    "je rêve de {daydream} en ce moment",
]
FALLBACK_BND_FR_TR_ACC = [
    "mon réveil n'a pas sonné {when}, je suis en retard",
    "j'adore cette chanson qui passe à la radio {when}",
    "ça fait quel effet d'être un réveil intelligent",
    "à quelle heure commence le {event} {when}",
    "mets l'ambiance avec des bougies",
    "il fait {stuffy} ici, il faudrait aérer",
    "je rêve de {daydream} en ce moment",
    "tu trouves pas qu'il fait trop calme ici",
    "euh mets, mets, oh laisse tomber",
    "la playlist {when} était vraiment bien",
    "c'est quoi cette chanson à la radio {when}",
    "le minuteur de la cuisine s'entend depuis {piece}",
    # R3 fix: was 'chante-moi une {lull} pour m'endormir' which duplicated
    # with slot 'chanson pour m'endormir'. Bare '{lull}' fits all values.
    "chante-moi une {lull}",
    "le temps passe vite quand on s'amuse",
    "mon {device} est en panne, tu aurais un conseil",
    "je réfléchis à voix haute, fais pas attention",
    "quelle heure il est à {city} en ce moment",
    "le bulletin météo de la radio se trompe toujours",
    "je fredonne cet air {when}, pardon",
    "c'était quoi déjà ce que je disais",
    "le réveil du bureau a sonné {when}",
    "tu m'entends mal, parle plus fort",
    "je pense tout haut {when}, fais pas attention",
]
FALLBACK_GEN_FR_TR_ASCII = [
    "quelle heure est-il", "raconte-moi une blague sur {topic}",
    "quelle est la capitale de {country}", "peux-tu m'aider avec mes {subject}",
    "combien font {a} plus {b}", "combien font {a} fois {b}",
    "dis-moi quelque chose d'interessant sur {topic}", "comment vas-tu aujourd'hui",
    "comment tu t'appelles", "peux-tu m'expliquer {topic}",
    "raconte-moi une histoire sur {topic}", "euh ouais donc en fait",
    "je ne sais pas ce que je veux", "lis-moi les nouvelles {when}",
    "quel age as-tu", "quelle est ta {thing} preferee",
    "qui a gagne le match de {sport} hier soir", "qu'est-ce que je cuisine {meal}",
    "comment ca s'ecrit, {word}", "traduis bonjour en {langto}",
    "rappelle-moi de {task}", "c'est quand {holiday}",
    "je m'ennuie, distrais-moi", "explique-moi {topic}",
    "jouons a {game}", "donne-moi une recette de {food}",
    "parle-moi de {landmark}", "tu connais {name}",
    "je reve de {daydream} en ce moment",
]
FALLBACK_BND_FR_TR_ASCII = [
    "mon reveil n'a pas sonne {when}, je suis en retard",
    "j'adore cette chanson qui passe a la radio {when}",
    "ca fait quel effet d'etre un reveil intelligent",
    "a quelle heure commence le {event} {when}",
    "mets l'ambiance avec des bougies",
    "il fait {stuffy} ici, il faudrait aerer",
    "je reve de {daydream} en ce moment",
    "tu trouves pas qu'il fait trop calme ici",
    "euh mets, mets, oh laisse tomber",
    "la playlist {when} etait vraiment bien",
    "c'est quoi cette chanson a la radio {when}",
    "le minuteur de la cuisine s'entend depuis {piece}",
    # R3 fix (ASCII mirror): bare '{lull}' avoids '...pour m'endormir pour m'endormir'.
    "chante-moi une {lull}",
    "le temps passe vite quand on s'amuse",
    "mon {device} est en panne, tu aurais un conseil",
    "je reflechis a voix haute, fais pas attention",
    "quelle heure il est a {city} en ce moment",
    "le bulletin meteo de la radio se trompe toujours",
    "je fredonne cet air {when}, pardon",
    "c'etait quoi deja ce que je disais",
    "le reveil du bureau a sonne {when}",
    "tu m'entends mal, parle plus fort",
    "je pense tout haut {when}, fais pas attention",
]
FALLBACK_GEN_FR_EV_ACC = [
    "on est quel jour aujourd'hui", "fais-moi rire",
    "quel artiste a peint {artfr}", "aide-moi à réviser mes {subject}",
    "combien font neuf fois {a}", "comment se passe ta journée",
    "donne-moi une recette avec {food}", "définis {word}",
    "quoi de neuf dans la tech {when}", "c'est loin d'ici {where}",
    "tu connais l'histoire de {landmark}", "passe le bonjour à {name}",
]
FALLBACK_BND_FR_EV_ACC = [
    "l'alarme du bureau a sonné toute la journée",
    "cet air me trotte dans la tête {when}",
    "tu peux parler plus fort, je t'entends mal",
    "à quelle heure ferment les magasins {when}",
    "mon rythme de sommeil est complètement déréglé",
    "{when} il a plu des cordes et j'ai oublié mon manteau",
    "les horloges rêvent-elles de moutons électriques",
    "mon {device} ne marche plus {when}",
    "c'est du larsen ou mes oreilles qui sifflent",
]
FALLBACK_GEN_FR_EV_ASCII = [
    "on est quel jour aujourd'hui", "fais-moi rire",
    "quel artiste a peint {artfr}", "aide-moi a reviser mes {subject}",
    "combien font neuf fois {a}", "comment se passe ta journee",
    "donne-moi une recette avec {food}", "definis {word}",
    "quoi de neuf dans la tech {when}", "c'est loin d'ici {where}",
    "tu connais l'histoire de {landmark}", "passe le bonjour a {name}",
]
FALLBACK_BND_FR_EV_ASCII = [
    "l'alarme du bureau a sonne toute la journee",
    "cet air me trotte dans la tete {when}",
    "tu peux parler plus fort, je t'entends mal",
    "a quelle heure ferment les magasins {when}",
    "mon rythme de sommeil est completement deregle",
    "{when} il a plu des cordes et j'ai oublie mon manteau",
    "les horloges revent-elles de moutons electriques",
    "mon {device} ne marche plus {when}",
    "c'est du larsen ou mes oreilles qui sifflent",
]
FALLBACK_MIX_TR_GEN = [
    # R2 fix round 2: was "what's ton nom" ('ton'/'nom' appear only in mixed
    # rows, so the verifier's row-derived lexicon counts them as neutral and
    # auto-flags the row; manual review saves it, but add 'à toi' with accent
    # so it passes automatically too).
    "umm je ne sais pas quoi dire", "what's ton nom à toi",
    "tell me une histoire sur {topic}", "quelle heure is it",
    "raconte-moi a joke sur {topic}", "help me avec mes devoirs",
    # R2 fix: was 'combien font {a} plus {b}' (pure FR: numbers are neutral,
    # decorations alone don't count). 'tell me' forces EN content.
    # R1 note: stripped key is now novel vs any train-FR template.
    "tell me combien font {a} plus {b}", "je m'ennuie, entertain me",
    "dis-moi a fun fact sur {topic}", "what's la capitale de {country}",
    "remind me de {task}", "what should on manger {meal}",
    "tell {name} que je dis salut",
    # R2 fix: was 'raconte-moi a joke please' (FR + please-only weak when
    # topic draws... topic pool here is EN-only so currently mixed, but make
    # it robust with strong EN 'now' instead of relying on slot).
    "raconte-moi a joke now",
]
FALLBACK_MIX_TR_BND = [
    "mon alarme didn't go off {when}", "j'adore this song à la radio {when}",
    "what time commence le {event}", "mets l'ambiance with some candles",
    "il fait {stuffy} in here, open a window",
    "la playlist {when} was vraiment bien",
    "c'est quoi this chanson {when}",
    "le temps passe vite when you're having fun",
    "je réfléchis out loud, ignore-moi",
    "what song c'est à la radio {when}",
    "mon réveil didn't sonner {when}", "il fait {stuffy} in here",
]
FALLBACK_MIX_EV_GEN = [
    "dis-moi a joke please", "what's ton nom déjà",
    "aide-moi to study {topic}",
    # R1+R2 fix: was 'combien font {a} fois {b}' (slot-masked-identical to
    # train-FR 'combien font...fois...'; plus pure-FR). 'tell me' fixes both.
    "tell me combien font {a} fois {b}",
    "rappelle-moi to {task}", "tell me un fun fact stp",
]
FALLBACK_MIX_EV_BND = [
    "cet air stuck in my head {when}",
    "mon réveil est cassé, any advice",
    "parle plus fort, i can't hear you",
    "il a plu {when} et j'ai oublié my coat",
    "à quelle heure close les shops {when}",
    "j'ai cet air in my head {when}",
]

# ============================================================ plan
# (category, language) -> dict(split -> (general_bases, cluster_bases, n_cluster, slots))
def slot_time(rng, lang):
    if lang == "en":
        return {"t": rng.choice(T_EN), "d": rng.choice(DAY_EN)}
    return {"t": rng.choice(T_FR_ACC), "d": rng.choice(DAY_FR_ACC)}

def slot_time_ascii(rng):
    return {"t": rng.choice(T_FR_ASCII), "d": rng.choice(DAY_FR_ASCII)}

def slot_dur(rng, lang):
    if lang == "en":
        return {"du": rng.choice(DUR_EN), "ex": rng.choice(EXTRA_MIN)}
    return {"du": rng.choice(DUR_FR_ACC), "ex": rng.choice(EXTRA_MIN_FR)}

def slot_dur_ascii(rng):
    return {"du": rng.choice(DUR_FR_ASCII), "ex": rng.choice(EXTRA_MIN_FR)}

def slot_play(rng, lang):
    if lang == "en":
        return {"pl": rng.choice(PLAY_EN), "s": rng.choice(SONG_EN)}
    return {"pl": rng.choice(PLAY_FR_ACC)}

def slot_play_ascii(rng):
    return {"pl": rng.choice(PLAY_FR_ASCII)}

def slot_w(rng, lang):
    if lang == "en":
        return {"d": rng.choice(["tomorrow", "this weekend", "tonight", "on sunday"])}
    if lang == "fr_acc":
        return {"d": rng.choice(["demain", "ce week-end", "ce soir", "dimanche"])}
    return {"d": rng.choice(["demain", "ce week-end", "ce soir", "dimanche"])}

# ---------------------------------------------------------------- mixed-purity guard
# Generator-side self-check mirroring the verifier's tight lexicon method
# (verify6): weak affixes/decorations + loanwords + proper nouns + single
# letters are NEUTRAL and do NOT count as language evidence. A 'mixed' row
# must contain >=1 strong FR content token AND >=1 strong EN content token.
# This is enforced in gen_cell (retry loop), not just asserted afterwards.
_MIX_NEUTRAL = {"hey", "nest", "um", "uh", "uhm", "euh", "ben", "alors", "bon",
    "hmm", "quoi", "like", "please", "thanks", "merci", "stp", "plait", "okay",
    "s", "t", "playlist", "playlists", "lofi", "mix", "shuffle", "track",
    "tracks", "beat", "beats", "hit", "hits", "rock", "jazz", "piano",
    "classical", "week", "end", "show", "games", "game", "match", "concert",
    "quiz", "trivia", "pendu", "cartes", "paris", "lyon", "marseille",
    "bordeaux", "lille", "nantes", "toulouse", "nice", "london", "berlin",
    "madrid", "rome", "tokyo", "lisbon", "york", "new", "france", "allemagne",
    "italie", "espagne", "japon", "bresil", "canada", "egypte", "portugal",
    "norvege", "grece", "thailande", "germany", "italy", "spain", "japan",
    "brazil", "egypt", "norway", "thailand", "greece", "alice", "bob",
    "charlie", "diana", "eric", "fatima", "george", "hannah", "lea", "hugo",
    "chloe", "louis", "emma", "gabriel", "lundi", "mardi", "samedi",
    "dimanche", "vendredi", "monday", "tuesday", "saturday", "sunday", "noel",
    "christmas", "paques", "easter", "halloween", "birthday", "summer",
    "vacation", "am", "pm", "h", "demi", "quart", "demie", "durie", "a", "en",
    "y", "de", "du", "des", "le", "la", "les", "un", "l", "d", "c", "j", "m",
    "qu", "n", "il", "elle", "ils", "je", "tu", "nous", "vous", "on"}
_MIX_FR = {"mets", "met", "mettez", "une", "avec", "dans", "pour", "plus",
    "moins", "son", "mon", "ma", "mes", "ton", "ta", "tes", "notre", "votre",
    "leur", "leurs", "est", "sont", "suis", "etes", "etre", "faire", "fait",
    "font", "fais", "faut", "peux", "peut", "veux", "veut", "dois", "doit",
    "vais", "va", "allons", "vont", "quel", "quelle", "quelles", "quels",
    "comment", "pourquoi", "combien", "quand", "qui", "dont", "cela", "ceci",
    "celui", "celle", "ceux", "celles", "cet", "cette", "ces", "chez", "sur",
    "sous", "entre", "vers", "sans", "pendant", "depuis", "voici", "voila",
    "oui", "tres", "aussi", "comme", "tout", "tous", "toute", "toutes",
    "autre", "meme", "chaque", "quelque", "plusieurs", "beaucoup", "assez",
    "toujours", "jamais", "souvent", "parfois", "maintenant", "aujourd",
    "hier", "demain", "bientot", "tard", "tot", "vite", "lentement", "bien",
    "mieux", "reveil", "alarme", "minuteur", "chrono", "musique", "chanson",
    "chansons", "meteo", "pluie", "pleuvoir", "pleut", "soleil", "soleille",
    "ensoleille", "vent", "neige", "neiger", "froid", "gele", "chaud", "beau",
    "mauvais", "grand", "petit", "nouveau", "bonne", "meilleur", "premier",
    "dernier", "heure", "heures", "temps", "journee", "semaine", "nuit",
    "matin", "matins", "soir", "soirs", "jour", "jours", "mois", "annee",
    "minute", "minutes", "secondes", "midi", "minuit", "bonjour", "bonsoir",
    "salut", "lance", "lancer", "arrete", "arret", "coupe", "reprends",
    "recommence", "recommencer", "continue", "continuer", "programme",
    "programmer", "rappelle", "rappeler", "raconte", "raconter", "explique",
    "expliquer", "donne", "donner", "prendre", "prends", "manger", "cuisine",
    "cuisiner", "recette", "recettes", "aide", "aider", "reviser", "connais",
    "connaitre", "reve", "rever", "dormir", "endormir", "oublie", "oublier",
    "pense", "penser", "reflechis", "reflechir", "ecoute", "ecouter",
    "entends", "entendre", "parle", "parler", "chante", "chanter",
    "fredonne", "fredonner", "souffle", "souffler", "ferment", "fermer",
    "sonne", "sonner", "marche", "marcher", "tombe", "tomber", "dormez",
    "leve", "lever", "reveille", "reveiller", "decale", "decaler",
    "repousse", "repousser", "retarde", "retarder", "annule", "annuler",
    "eteins", "eteindre", "supprime", "supprimer", "desactive", "desactiver",
    "change", "changer", "modifie", "modifier", "ajoute", "ajouter",
    "rajoute", "rajouter", "prolonge", "prolonger", "enleve", "enlever",
    "verifie", "verifier", "regarde", "regarder", "monte", "monter",
    "baisse", "baisser", "augmente", "augmenter", "diminue", "diminuer",
    "pousse", "pousser", "remonte", "remonter", "redescends", "redescendre",
    "remets", "remettre", "fort", "fond", "moitie", "dix", "vingt", "zero",
    "maximum", "minimum", "reste", "restant", "restants", "dis", "joue",
    "jouer", "balance", "balancer", "passe", "passer", "suivante",
    "prochaine", "prochain", "derniere", "debut", "fin", "aucun", "aucune",
    "rien", "personne", "histoire", "blague", "capitale", "devoirs", "maths",
    "dissertation", "dissertations", "expose", "exposes", "revision",
    "revisions", "cinema", "ocean", "espace", "science", "etoile", "etoilee",
    "cri", "perle", "fille", "jeune", "peinture", "artiste", "peint",
    "tableau", "berceuse", "envoie", "rejoue"}
# NOTE: 'rejoue'/'envoie' are FR markers; 'tell'/'now'/'cue'/'for' are EN
# markers (defined in _MIX_EN_CORE below).
_MIX_FR_EXTRA = {"rejoue", "envoie"}
_MIX_EN_EXTRA = {"tell", "now"}
_MIX_FR_FULL = ((_MIX_FR | _MIX_FR_EXTRA) - _MIX_NEUTRAL)
_MIX_EN_CORE = {"the", "this", "that", "these", "those", "there", "here",
    "then", "than", "very", "just", "only", "is", "are", "was", "were",
    "have", "has", "had", "does", "did", "will", "would", "could", "shall",
    "should", "might", "must", "what", "when", "where", "which", "whom",
    "whose", "why", "wake", "woken", "cancel", "cancelled", "delete",
    "deleted", "remove", "turn", "turning", "raise", "lower", "increase",
    "decrease", "volume", "louder", "quieter", "mute", "unmute", "silence",
    "silenced", "crank", "pump", "dial", "notch", "blast", "soften", "bring",
    "bringing", "make", "bump", "drop", "restart", "resume", "pause",
    "paused", "hold", "freeze", "extend", "snooze", "remind", "set", "get",
    "put", "play", "playing", "played", "stop", "stopped", "start",
    "started", "skip", "skipping", "launch", "launched", "run", "running",
    "kick", "begin", "say", "said", "says", "speak", "talk", "ask", "asked",
    "answer", "help", "explain", "define", "spell", "translate", "mean",
    "means", "meaning", "think", "know", "remember", "forget", "love",
    "hate", "want", "need", "going", "come", "coming", "take", "buy",
    "call", "cook", "sing", "dream", "sleep", "late", "early", "wrong",
    "time", "day", "days", "hour", "hours", "minute", "minutes", "second",
    "seconds", "month", "months", "year", "years", "song", "songs", "radio",
    "weather", "rain", "rains", "snow", "snows", "sunny", "cloudy", "windy",
    "storm", "storms", "forecast", "temperature", "outside", "humidity",
    "umbrella", "jacket", "sunglasses", "freeze", "hail", "alarm", "alarms",
    "timer", "timers", "countdown", "morning", "evening", "night",
    "afternoon", "today", "tomorrow", "tonight", "with", "from", "about",
    "into", "over", "after", "before", "between", "through", "during",
    "without", "within", "your", "yours", "mine", "ours", "theirs", "them",
    "they", "him", "her", "hers", "me", "us", "we", "tell", "now", "for",
    "my", "your", "the", "to", "still", "on", "up", "down", "cue"}
_MIX_EN_FULL = ((_MIX_EN_CORE | _MIX_EN_EXTRA) - _MIX_NEUTRAL)

def _mix_sig(phrase: str):
    toks = [t for t in strip_accents(norm(phrase)).split()
            if t not in _MIX_NEUTRAL and not t.isdigit()]
    return (sum(1 for t in toks if t in _MIX_FR_FULL),
            sum(1 for t in toks if t in _MIX_EN_FULL))

# ---------------------------------------------------------------- data-driven
# mixed guard (mirrors verifier R2: EN-only/FR-only tokens derived from the
# actual en/fr template banks + accent check, manually reviewed).
# The hardcoded _MIX_* sets above are incomplete (miss 'left', 'restart',
# 'now', 'joue', 'next', ...), so a strict check against them false-rejects
# valid mixed rows (e.g. 'can you wake me up à ...' via accent, 'cancel le
# timer' via 'le'). Instead derive evidence tokens from the banks themselves:
# a token counts as FR-only if it appears in FR-bank templates but never in
# EN-bank templates (and vice versa), excluding proper-noun/loanword/
# politeness tokens that the verifier also neutralizes. An accented character
# additionally counts as FR evidence (verifier accent check).
_PROPER_NEUTRAL = {"hey", "nest", "um", "uh", "uhm", "euh", "ben", "alors",
    "bon", "hmm", "quoi", "like", "okay", "please", "thanks", "merci", "stp",
    "plait", "playlist", "playlists", "lofi", "mix", "shuffle", "track",
    "tracks", "beat", "beats", "hit", "hits", "rock", "jazz", "piano",
    "classical", "week", "end", "show", "games", "game", "match", "concert",
    "quiz", "trivia", "pendu", "cartes", "cards", "film", "paris", "lyon",
    "marseille", "bordeaux", "lille", "nantes", "toulouse", "nice", "london",
    "berlin", "madrid", "rome", "tokyo", "lisbon", "york", "new", "france",
    "allemagne", "italie", "espagne", "japon", "bresil", "canada", "egypte",
    "portugal", "norvege", "grece", "thailande", "germany", "italy", "spain",
    "japan", "brazil", "egypt", "portugal", "norway", "greece", "thailand",
    "alice", "bob", "charlie", "diana", "eric", "fatima", "george", "hannah",
    "lea", "hugo", "chloe", "louis", "emma", "gabriel", "lundi", "mardi",
    "samedi", "dimanche", "vendredi", "monday", "tuesday", "saturday",
    "sunday", "noel", "christmas", "paques", "easter", "halloween",
    "birthday", "summer", "vacation", "am", "pm", "h", "demi", "quart",
    "demie", "stop", "stoppe", "zappe", "zap"}

def _bank_tokens(banks):
    toks = set()
    for b in banks:
        for t in b:
            t2 = re.sub(r"\{[^}]+\}", " ", t)
            for w in strip_accents(norm(t2)).split():
                if not w.isdigit():
                    toks.add(w)
    return toks

_EN_BANKS_FOR_GUARD = [ALARM_EN_TR, ALARM_EN_EV, TIMER_EN_TR, TIMER_EN_EV,
                       MUSIC_PLAY_EN_TR, MUSIC_VOL_EN_TR, MUSIC_PLAY_EN_EV,
                       MUSIC_VOL_EN_EV, WEATHER_EN_TR, WEATHER_EN_EV,
                       FALLBACK_GEN_EN_TR, FALLBACK_BND_EN_TR,
                       FALLBACK_GEN_EN_EV, FALLBACK_BND_EN_EV]
_FR_BANKS_FOR_GUARD = [ALARM_FR_TR_ACC, ALARM_FR_TR_ASCII, ALARM_FR_EV_ACC,
                       ALARM_FR_EV_ASCII, TIMER_FR_GEN_ACC,
                       TIMER_FR_GEN_ASCII, TIMER_FR_IDIOM_ACC,
                       TIMER_FR_IDIOM_ASCII, TIMER_FR_GEN_EV_ACC,
                       TIMER_FR_GEN_EV_ASCII, TIMER_FR_IDIOM_EV_ACC,
                       TIMER_FR_IDIOM_EV_ASCII, MUSIC_PLAY_FR_TR_ACC,
                       MUSIC_VOL_FR_TR_ACC, MUSIC_PLAY_FR_TR_ASCII,
                       MUSIC_VOL_FR_TR_ASCII, MUSIC_PLAY_FR_EV_ACC,
                       MUSIC_PLAY_FR_EV_ASCII, MUSIC_VOL_FR_EV_ASCII,
                       MUSIC_VOL_FR_EV_ACC, WEATHER_FR_TR_ACC,
                       WEATHER_FR_TR_ASCII, WEATHER_FR_EV_ACC,
                       WEATHER_FR_EV_ASCII, FALLBACK_GEN_FR_TR_ACC,
                       FALLBACK_BND_FR_TR_ACC, FALLBACK_GEN_FR_TR_ASCII,
                       FALLBACK_BND_FR_TR_ASCII, FALLBACK_GEN_FR_EV_ACC,
                       FALLBACK_BND_FR_EV_ACC, FALLBACK_GEN_FR_EV_ASCII,
                       FALLBACK_BND_FR_EV_ASCII]
_EN_TOKS_GUARD = _bank_tokens(_EN_BANKS_FOR_GUARD)
_FR_TOKS_GUARD = _bank_tokens(_FR_BANKS_FOR_GUARD)
# Manual extras: true FR/EN content words that appear only in mixed templates
# or only as slot values, so template-bank derivation would miss them while
# the verifier's row-derived lexicon (which sees slot-filled rows) and manual
# review count them. Without these the guard would false-reject valid rows.
_FR_MANUAL_GUARD = {"ton", "nom", "deja", "manger", "moi", "rejoue",
                    "envoie", "balance", "adore", "commence", "sonner",
                    "casse", "casse", "meme"}
_EN_MANUAL_GUARD = {"mute", "unmute", "now", "tell", "cue", "left",
                    "restart", "still", "next", "advice", "close", "shops",
                    "go", "off", "didn", "fun", "fact"}
_FR_ONLY_GUARD = ((_FR_TOKS_GUARD | _FR_MANUAL_GUARD) - _EN_TOKS_GUARD) \
    - _PROPER_NEUTRAL
_EN_ONLY_GUARD = ((_EN_TOKS_GUARD | _EN_MANUAL_GUARD) - _FR_TOKS_GUARD) \
    - _PROPER_NEUTRAL

def _mix_sig_guarded(phrase: str):
    toks = [t for t in strip_accents(norm(phrase)).split()
            if t not in _PROPER_NEUTRAL and not t.isdigit()]
    f = sum(1 for t in toks if t in _FR_ONLY_GUARD)
    e = sum(1 for t in toks if t in _EN_ONLY_GUARD)
    return f, e

def is_mixed_ok(phrase: str) -> bool:
    # Verifier R2 criterion: both languages present (content, not just weak
    # please/stp/euh affixes — those are in _PROPER_NEUTRAL so they never
    # count). Accent counts as FR evidence per verifier accent check.
    f, e = _mix_sig_guarded(phrase)
    has_accent = any(ord(c) >= 128 for c in phrase)
    return (f > 0 or has_accent) and e > 0

def fill_slots(tmpl, rng, lang, ascii_fr=False):
    group = "en" if lang == "en" else ("mix" if lang == "mixed" else ("frx" if ascii_fr else "fra"))
    pool = SLOT[group]
    kw = {}
    for k, vals in pool.items():
        if "{" + k + "}" in tmpl:
            kw[k] = rng.choice(vals)
    try:
        return tmpl.format(**kw)
    except KeyError as e:
        raise RuntimeError(f"missing slot {e} for template {tmpl!r} in group {group}")

def decorate(phrase, rng, lang, ascii_fr=False):
    if lang == "en":
        pre = rng.choice(EN_PRE)
        post = rng.choice(EN_POST)
    elif lang == "mixed":
        pre = rng.choice(MIX_PRE)
        post = rng.choice(MIX_POST)
    else:
        pre = rng.choice(FR_PRE_ASCII if ascii_fr else FR_PRE_ACC)
        post = rng.choice(FR_POST_ASCII if ascii_fr else FR_POST_ACC)
    # avoid stacking politeness when the base already ends with one
    if post and re.search(r"(please|thanks|merci|stp|plait|plait|s'il te pla[iî]t)\W*$",
                          phrase, re.IGNORECASE):
        post = ""
    # disfluency injection ~8%
    r = rng.random()
    if r < 0.04:
        pre = (rng.choice(["um ", "uh ", "euh ", "ben "]) if lang != "fr"
               else rng.choice(["euh ", "ben ", "alors "])) + pre
    elif r < 0.08:
        if lang == "en":
            phrase = phrase + rng.choice([" uh", " hmm", " like"])
        elif lang == "mixed":
            phrase = phrase + rng.choice([" euh", " hmm", " quoi", " la"])
        elif ascii_fr:
            phrase = phrase + rng.choice([" euh", " hmm", " quoi", " la"])
        else:
            phrase = phrase + rng.choice([" euh", " hmm", " quoi", " là"])
    return (pre + phrase + post).strip()

def gen_cell(rng, bases_general, bases_cluster, n_cluster, n_total, lang,
             ascii_frac=0.0, seen=None, tag=""):
    """Returns list of (phrase, tag). Cluster rows drawn from cluster bases first."""
    out = []
    if lang == "fr":
        n_ascii = round(n_total * ascii_frac)
        idxs = list(range(n_total))
        rng.shuffle(idxs)
        ascii_set = set(idxs[:n_ascii])
        order = [(i < n_cluster, i in ascii_set) for i in range(n_total)]
        gen_order = list(range(n_total))
        rng.shuffle(gen_order)
    else:
        order = [(i < n_cluster, False) for i in range(n_total)]
        gen_order = list(range(n_total))
        rng.shuffle(gen_order)
    for i in gen_order:
        is_cluster, want_ascii = order[i]
        pool = bases_cluster if (is_cluster and bases_cluster) else bases_general
        for _ in range(2000):
            if lang == "fr" and isinstance(pool, tuple):
                acc_list, asc_list = pool
                base = rng.choice(asc_list if want_ascii else acc_list)
            else:
                base = rng.choice(pool)
            phrase = fill_slots(base, rng, lang, ascii_fr=bool(want_ascii))
            phrase = decorate(phrase, rng, lang, ascii_fr=bool(want_ascii))
            if want_ascii and not is_ascii(phrase):
                raise RuntimeError(f"non-ASCII leak in ascii-flagged phrase: {phrase!r}")
            # R2 guard: mixed rows must carry CONTENT in both languages, not
            # just a weak please/stp/euh affix. Reject + retry otherwise.
            if lang == "mixed" and not is_mixed_ok(phrase):
                continue
            n1, n2 = norm(phrase), strong_norm(phrase)
            if n1 not in seen[0] and n2 not in seen[1]:
                seen[0].add(n1)
                seen[1].add(n2)
                out.append((phrase, tag if is_cluster else ""))
                break
        else:
            raise RuntimeError(f"could not generate unique phrase for {tag or lang} after 2000 tries")
    return out

def main():
    rows = []  # (phrase, cat, lang, split, tag)
    seen = (set(), set())
    # per-split RNGs (separate passes)
    # Train seed unchanged (1234) for reproducibility; eval uses a NEW seed
    # (fix round) so the regenerated eval rows get fresh RNG draws.
    rng_tr = random.Random(1234)
    rng_ev = random.Random(20260926)

    # ---------------- TRAIN (2000): fr 180 / en 140 / mixed 80 per category
    plan_tr = [
        ("alarm", "en", 140, ALARM_EN_TR, None, 0, 0.0, rng_tr),
        ("alarm", "fr", 180, (ALARM_FR_TR_ACC, ALARM_FR_TR_ASCII), None, 0, 0.45, rng_tr),
        ("alarm", "mixed", 80, ALARM_MIX_TR, None, 0, 0.0, rng_tr),
        ("timer", "en", 140, TIMER_EN_TR, None, 0, 0.0, rng_tr),
        ("timer", "fr", 180, (TIMER_FR_GEN_ACC, TIMER_FR_GEN_ASCII),
         (TIMER_FR_IDIOM_ACC, TIMER_FR_IDIOM_ASCII), 64, 0.45, rng_tr),
        ("timer", "mixed", 80, TIMER_MIX_TR, None, 0, 0.0, rng_tr),
        ("music", "en", 140, MUSIC_PLAY_EN_TR, MUSIC_VOL_EN_TR, 50, 0.0, rng_tr),
        ("music", "fr", 180, (MUSIC_PLAY_FR_TR_ACC, MUSIC_PLAY_FR_TR_ASCII),
         (MUSIC_VOL_FR_TR_ACC, MUSIC_VOL_FR_TR_ASCII), 60, 0.45, rng_tr),
        ("music", "mixed", 80, MUSIC_MIX_TR_PLAY, MUSIC_MIX_TR_VOL, 25, 0.0, rng_tr),
        ("weather", "en", 140, WEATHER_EN_TR, None, 0, 0.0, rng_tr),
        ("weather", "fr", 180, (WEATHER_FR_TR_ACC, WEATHER_FR_TR_ASCII), None, 0, 0.45, rng_tr),
        ("weather", "mixed", 80, WEATHER_MIX_TR, None, 0, 0.0, rng_tr),
        ("fallback", "en", 140, FALLBACK_GEN_EN_TR, FALLBACK_BND_EN_TR, 60, 0.0, rng_tr),
        ("fallback", "fr", 180, (FALLBACK_GEN_FR_TR_ACC, FALLBACK_GEN_FR_TR_ASCII),
         (FALLBACK_BND_FR_TR_ACC, FALLBACK_BND_FR_TR_ASCII), 80, 0.45, rng_tr),
        ("fallback", "mixed", 80, FALLBACK_MIX_TR_GEN, FALLBACK_MIX_TR_BND, 40, 0.0, rng_tr),
    ]
    # ---------------- EVAL (500): fr 45 / en 35 / mixed 20 per category, different banks
    plan_ev = [
        ("alarm", "en", 35, ALARM_EN_EV, None, 0, 0.0, rng_ev),
        ("alarm", "fr", 45, (ALARM_FR_EV_ACC, ALARM_FR_EV_ASCII), None, 0, 0.45, rng_ev),
        ("alarm", "mixed", 20, ALARM_MIX_EV, None, 0, 0.0, rng_ev),
        ("timer", "en", 35, TIMER_EN_EV, None, 0, 0.0, rng_ev),
        ("timer", "fr", 45, (TIMER_FR_GEN_EV_ACC, TIMER_FR_GEN_EV_ASCII),
         (TIMER_FR_IDIOM_EV_ACC, TIMER_FR_IDIOM_EV_ASCII), 24, 0.45, rng_ev),
        ("timer", "mixed", 20, TIMER_MIX_EV, None, 0, 0.0, rng_ev),
        ("music", "en", 35, MUSIC_PLAY_EN_EV, MUSIC_VOL_EN_EV, 12, 0.0, rng_ev),
        ("music", "fr", 45, (MUSIC_PLAY_FR_EV_ACC, MUSIC_PLAY_FR_EV_ASCII),
         (MUSIC_VOL_FR_EV_ACC, MUSIC_VOL_FR_EV_ASCII), 15, 0.45, rng_ev),
        ("music", "mixed", 20, MUSIC_MIX_EV_PLAY, MUSIC_MIX_EV_VOL, 8, 0.0, rng_ev),
        ("weather", "en", 35, WEATHER_EN_EV, None, 0, 0.0, rng_ev),
        ("weather", "fr", 45, (WEATHER_FR_EV_ACC, WEATHER_FR_EV_ASCII), None, 0, 0.45, rng_ev),
        ("weather", "mixed", 20, WEATHER_MIX_EV, None, 0, 0.0, rng_ev),
        ("fallback", "en", 35, FALLBACK_GEN_EN_EV, FALLBACK_BND_EN_EV, 15, 0.0, rng_ev),
        ("fallback", "fr", 45, (FALLBACK_GEN_FR_EV_ACC, FALLBACK_GEN_FR_EV_ASCII),
         (FALLBACK_BND_FR_EV_ACC, FALLBACK_BND_FR_EV_ASCII), 20, 0.45, rng_ev),
        ("fallback", "mixed", 20, FALLBACK_MIX_EV_GEN, FALLBACK_MIX_EV_BND, 10, 0.0, rng_ev),
    ]
    tag_for = {("timer", "fr"): "fr_timer_idiom", ("music", "en"): "volume",
               ("music", "fr"): "volume", ("music", "mixed"): "volume",
               ("fallback", "en"): "fb_boundary", ("fallback", "fr"): "fb_boundary",
               ("fallback", "mixed"): "fb_boundary"}

    for cat, lang, n, gen_b, clu_b, n_clu, afrac, rng in plan_tr:
        for phrase, tag in gen_cell(rng, gen_b, clu_b, n_clu, n, lang,
                                    ascii_frac=afrac, seen=seen, tag=tag_for.get((cat, lang), "")):
            rows.append((phrase, cat, lang, "train", tag))
    for cat, lang, n, gen_b, clu_b, n_clu, afrac, rng in plan_ev:
        for phrase, tag in gen_cell(rng, gen_b, clu_b, n_clu, n, lang,
                                    ascii_frac=afrac, seen=seen, tag=tag_for.get((cat, lang), "")):
            rows.append((phrase, cat, lang, "held_out_eval", tag))

    # ---- write CSV (csv module, UTF-8)
    rng_shuf = random.Random(42)
    rng_shuf.shuffle(rows)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["phrase", "expected_category", "language", "split"])
        for phrase, cat, lang, split, _ in rows:
            w.writerow([phrase, cat, lang, split])

    # ---- re-read + verify
    with open(OUT_CSV, newline="", encoding="utf-8") as f:
        r = list(csv.DictReader(f))
    assert f is not None
    total = len(r)
    by_split = Counter(x["split"] for x in r)
    by_cat = Counter(x["expected_category"] for x in r)
    by_lang = Counter(x["language"] for x in r)
    table = Counter((x["expected_category"], x["language"], x["split"]) for x in r)

    # cluster audits (independent of generation tags: regex/programmatic)
    fr_timer_rows = [x for x in r if x["expected_category"] == "timer" and x["language"] == "fr"]
    n_idiom = sum(1 for x in fr_timer_rows if IDIOM_RE.search(x["phrase"]))
    music_rows = [x for x in r if x["expected_category"] == "music"]
    n_vol = sum(1 for x in music_rows if VOLUME_RE.search(x["phrase"]))
    n_bnd_tag = sum(1 for x in rows if x[4] == "fb_boundary")
    # boundary audit: at least the tagged ones; spot-check no music/alarm/timer/weather command in tagged
    fr_rows = [x for x in r if x["language"] == "fr"]
    n_ascii_fr = sum(1 for x in fr_rows if is_ascii(x["phrase"]))
    norms = [norm(x["phrase"]) for x in r]
    strongs = [strong_norm(x["phrase"]) for x in r]
    dup_norm = len(norms) - len(set(norms))
    dup_strong = len(strongs) - len(set(strongs))
    # cross-split leakage
    tr_norms = {norm(x["phrase"]) for x in r if x["split"] == "train"}
    ev_norms = {norm(x["phrase"]) for x in r if x["split"] == "held_out_eval"}
    cross = len(tr_norms & ev_norms)
    tr_strong = {strong_norm(x["phrase"]) for x in r if x["split"] == "train"}
    ev_strong = {strong_norm(x["phrase"]) for x in r if x["split"] == "held_out_eval"}
    cross_strong = len(tr_strong & ev_strong)

    print(f"total={total} train={by_split['train']} eval={by_split['held_out_eval']}")
    print("--- category x language x split ---")
    for cat in ["alarm", "timer", "music", "weather", "fallback"]:
        for lang in ["en", "fr", "mixed"]:
            for sp in ["train", "held_out_eval"]:
                print(f"{cat:9s} {lang:6s} {sp:13s} {table[(cat, lang, sp)]}")
    print("--- category share (overall) ---")
    for cat in ["alarm", "timer", "music", "weather", "fallback"]:
        print(f"{cat:9s} {by_cat[cat]/total:.1%}")
    print("--- language share per split ---")
    for sp in ["train", "held_out_eval"]:
        n = by_split[sp]
        for lang in ["fr", "en", "mixed"]:
            print(f"{sp:13s} {lang:6s} {table_total(table, lang, sp)/n:.1%}")
    print("--- clusters ---")
    print(f"(a) fr timer idiom (regex): {n_idiom} / {len(fr_timer_rows)} (need >=80)")
    print(f"(b) volume (regex on music): {n_vol} / {len(music_rows)} (need >=150)")
    print(f"(c) fallback boundary (gen tags): {n_bnd_tag} (need >=200)")
    print(f"(d) ascii-fr: {n_ascii_fr} / {len(fr_rows)} = {n_ascii_fr/len(fr_rows):.1%} (need >=35%)")
    print("--- dedup ---")
    print(f"exact-norm dupes: {dup_norm}; strong-norm dupes: {dup_strong}; "
          f"cross-split norm overlap: {cross}; cross-split strong overlap: {cross_strong}")

    # ---- R1: decoration-stripped structural overlap (verifier verify4 method)
    _PRE = {"hey", "nest", "um", "uh", "okay", "dis", "euh", "ben", "alors"}
    _POST = {"please", "thanks", "merci", "stp", "plait", "te", "sil", "s",
             "t", "il"}
    _TRAIL = {"euh", "hmm", "quoi", "la", "like"}

    def _strip_deco(s):
        toks = strip_accents(norm(s)).split()
        while toks and toks[0] in _PRE:
            toks.pop(0)
        while toks and (toks[-1] in _POST or toks[-1] in _TRAIL):
            toks.pop()
        return " ".join(toks)

    def _structkey(s):
        s = _strip_deco(s)
        s = re.sub(r"\b\d+[h:]\d*\b", "NUM", s)
        s = re.sub(r"\b\d+\b", "NUM", s)
        for w in ["lundi", "mardi", "samedi", "dimanche", "vendredi",
                  "demain", "week end", "ce soir", "matin", "soir", "paris",
                  "lyon", "marseille", "bordeaux", "lille", "nantes",
                  "toulouse", "nice", "london", "berlin", "madrid", "rome",
                  "tokyo", "lisbon", "playlist", "jazz", "lofi", "rock",
                  "classique", "classical", "mix", "favorites", "favoris",
                  "morning", "evening", "workout", "chill", "alice", "bob",
                  "charlie", "diana", "eric", "fatima", "george", "hannah",
                  "lea", "hugo", "chloe", "louis", "emma", "gabriel"]:
            s = re.sub(r"\b" + re.escape(w) + r"\b", "SLOT", s)
        s = re.sub(r"\b(minutes?|seconds?|secondes?|heure?s?|hours?)\b",
                   "DUR", s)
        return re.sub(r"\s+", " ", s).strip()

    tr_struct = {_structkey(x["phrase"]) for x in r if x["split"] == "train"}
    ev_struct_hits = [x for x in r if x["split"] == "held_out_eval"
                      and _structkey(x["phrase"]) in tr_struct]
    print(f"--- R1 structural overlap (deco-stripped): "
          f"{len(ev_struct_hits)}/500 eval rows (need 0)")
    for x in ev_struct_hits[:10]:
        print(f"  OVERLAP: {x['phrase']!r} [{x['expected_category']}/"
              f"{x['language']}] struct={_structkey(x['phrase'])!r}")

    # ---- R1b: template-bank stripped-key disjointness (train vs eval banks)
    def _tkey(t):
        t2 = re.sub(r"\{[^}]+\}", "SLOT", t)
        k = strip_accents(norm(t2))
        toks = k.split()
        while toks and toks[0] in _PRE:
            toks.pop(0)
        while toks and (toks[-1] in _POST or toks[-1] in _TRAIL):
            toks.pop()
        return " ".join(toks)

    _train_banks = [ALARM_EN_TR, ALARM_FR_TR_ACC, ALARM_FR_TR_ASCII,
                    ALARM_MIX_TR, TIMER_EN_TR, TIMER_FR_IDIOM_ACC,
                    TIMER_FR_IDIOM_ASCII, TIMER_FR_GEN_ACC,
                    TIMER_FR_GEN_ASCII, TIMER_MIX_TR, MUSIC_PLAY_EN_TR,
                    MUSIC_VOL_EN_TR, MUSIC_PLAY_FR_TR_ACC,
                    MUSIC_VOL_FR_TR_ACC, MUSIC_PLAY_FR_TR_ASCII,
                    MUSIC_VOL_FR_TR_ASCII, MUSIC_MIX_TR_PLAY,
                    MUSIC_MIX_TR_VOL, WEATHER_EN_TR, WEATHER_FR_TR_ACC,
                    WEATHER_FR_TR_ASCII, WEATHER_MIX_TR,
                    FALLBACK_GEN_EN_TR, FALLBACK_BND_EN_TR,
                    FALLBACK_GEN_FR_TR_ACC, FALLBACK_BND_FR_TR_ACC,
                    FALLBACK_GEN_FR_TR_ASCII, FALLBACK_BND_FR_TR_ASCII,
                    FALLBACK_MIX_TR_GEN, FALLBACK_MIX_TR_BND]
    _eval_banks = [ALARM_EN_EV, ALARM_FR_EV_ACC, ALARM_FR_EV_ASCII,
                   ALARM_MIX_EV, TIMER_EN_EV, TIMER_FR_IDIOM_EV_ACC,
                   TIMER_FR_IDIOM_EV_ASCII, TIMER_FR_GEN_EV_ACC,
                   TIMER_FR_GEN_EV_ASCII, TIMER_MIX_EV, MUSIC_PLAY_EN_EV,
                   MUSIC_VOL_EN_EV, MUSIC_PLAY_FR_EV_ACC,
                   MUSIC_PLAY_FR_EV_ASCII, MUSIC_VOL_FR_EV_ASCII,
                   MUSIC_VOL_FR_EV_ACC, MUSIC_MIX_EV_PLAY, MUSIC_MIX_EV_VOL,
                   WEATHER_EN_EV, WEATHER_FR_EV_ACC, WEATHER_FR_EV_ASCII,
                   WEATHER_MIX_EV, FALLBACK_GEN_EN_EV, FALLBACK_BND_EN_EV,
                   FALLBACK_GEN_FR_EV_ACC, FALLBACK_BND_FR_EV_ACC,
                   FALLBACK_GEN_FR_EV_ASCII, FALLBACK_BND_FR_EV_ASCII,
                   FALLBACK_MIX_EV_GEN, FALLBACK_MIX_EV_BND]
    _train_keys = {_tkey(t) for b in _train_banks for t in b}
    _eval_overlap = [(b_i, t) for b_i, b in enumerate(_eval_banks)
                     for t in b if _tkey(t) in _train_keys]
    print(f"--- R1 template-bank stripped overlap: "
          f"{len(_eval_overlap)} eval templates (need 0)")
    for _, t in _eval_overlap[:10]:
        print(f"  BANK OVERLAP: {t!r} key={_tkey(t)!r}")

    # ---- R2: mixed-purity (content in both languages, weak affixes excluded)
    mixed_rows = [x for x in r if x["language"] == "mixed"]
    mixed_bad = [x for x in mixed_rows if not is_mixed_ok(x["phrase"])]
    print(f"--- R2 mixed purity: {len(mixed_bad)}/{len(mixed_rows)} "
          f"monolingual (need 0)")
    for x in mixed_bad[:10]:
        print(f"  MIXED-FAIL: {x['phrase']!r} [{x['expected_category']}/"
              f"{x['split']}] sig={_mix_sig_guarded(x['phrase'])}")

    # ---- R3: slot-composition bugs (singular-only match; plurals are correct)
    lull_dupes = [x for x in r if re.search(
        r"to fall asleep to to fall asleep|pour m.endormir pour m.endormir",
        x["phrase"], re.IGNORECASE)]
    # 'mes dissertations' / 'mes exposés de sciences' / 'mes révisions' are
    # plural-correct; only flag singular 'mes révision', 'mes dissertation'
    # (no trailing s), 'mes exposé' (no s).
    agree_bad = [x for x in r if re.search(
        r"mes r[eé]vision d|mes dissertation\b(?!s)|mes expos[eé](?!s)",
        x["phrase"], re.IGNORECASE)]
    print(f"--- R3 lullaby duplications: {len(lull_dupes)} (need 0); "
          f"agreement errors: {len(agree_bad)} (need 0)")
    for x in lull_dupes[:5] + agree_bad[:5]:
        print(f"  COMPOSITION-FAIL: {x['phrase']!r}")

    # ---- checklist #5: 'good day' boundary sampled
    n_goodday = sum(1 for x in r if "good day" in x["phrase"].lower())
    print(f"--- good-day boundary rows: {n_goodday} (need >=3)")

    assert total == 2500, total
    assert by_split["train"] == 2000 and by_split["held_out_eval"] == 500
    for cat in ["alarm", "timer", "music", "weather", "fallback"]:
        share = by_cat[cat] / total
        assert 0.15 <= share <= 0.25, (cat, share)
    for sp, exp in [("train", (900, 700, 400)), ("held_out_eval", (225, 175, 100))]:
        n = by_split[sp]
        assert table_total(table, "fr", sp) == exp[0], (sp, "fr")
        assert table_total(table, "en", sp) == exp[1], (sp, "en")
        assert table_total(table, "mixed", sp) == exp[2], (sp, "mixed")
    assert n_idiom >= 80, n_idiom
    assert n_vol >= 150, n_vol
    assert n_bnd_tag >= 200, n_bnd_tag
    assert n_ascii_fr / len(fr_rows) >= 0.35
    assert dup_norm == 0 and cross == 0
    assert dup_strong == 0 and cross_strong == 0
    assert len(ev_struct_hits) == 0, \
        f"R1 structural overlap: {len(ev_struct_hits)} eval rows"
    assert len(_eval_overlap) == 0, \
        f"R1 template-bank overlap: {len(_eval_overlap)} templates"
    assert len(mixed_bad) == 0, f"R2 monolingual mixed: {len(mixed_bad)} rows"
    assert len(lull_dupes) == 0 and len(agree_bad) == 0, \
        f"R3 composition: {len(lull_dupes)} lullaby + {len(agree_bad)} agreement"
    assert n_goodday >= 3, f"good-day rows: {n_goodday}"
    print("ALL CHECKS PASSED")

def table_total(table, lang, sp):
    return sum(v for (c, l, s), v in table.items() if l == lang and s == sp)

if __name__ == "__main__":
    main()

# ---------------------------------------------------------------- BORDERLINE LABEL DECISIONS (for report)
# 1. Generic volume ("turn up the volume", "monte le son") -> music (per criterion incl. volume).
# 2. "remind me to call mom" (reminder, no alarm/time trigger) -> fallback, not alarm.
# 3. "what song is on the radio / stuck in my head" (identification, no playback cmd) -> fallback.
# 4. "metronome / watch stopped / office alarm rang" (time words, no command) -> fallback.
# 5. "set the mood with candles" ("set" but not timer/alarm) -> fallback.
# 6. "open a window, stuffy in here" (comfort, not weather Q) -> fallback.
# 7. "do you think it'll be a good day" (vague, no weather ask) -> fallback.
# 8. "is the kitchen timer loud enough" (asks about device, no control cmd) -> fallback.
# 9. "i need a new alarm clock, advice" (shopping, not setting) -> fallback.
# 10. "speak up, i can't hear you" (mic gain, not speaker volume cmd) -> fallback.
# 11. "is it too loud in here" (ambient, no clear volume target) -> fallback.
# 12. "sing me a lullaby" (vocal performance, not Spotify playback) -> fallback.
# 13. Fragments/trailing-offs ("euh mets, mets, oh laisse tomber") -> fallback (incomplete).
# 14. "what time do shops close / concert start" (event time, not clock) -> fallback.
# 15. Stopwatch wording avoided entirely (countdown-only per criterion) to prevent label noise.
