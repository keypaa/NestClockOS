"""Deterministic bilingual slot parsing for a few sub-intents (Slice 2)."""
import re

_NUMS = {
    "zero":0,"un":1,"une":1,"deux":2,"trois":3,"quatre":4,"cinq":5,"six":6,"sept":7,
    "huit":8,"neuf":9,"dix":10,"onze":11,"douze":12,"treize":13,"quatorze":14,
    "quinze":15,"seize":16,"vingt":20,"thirty":30,"half":30,
    "one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,
    "nine":9,"ten":10,"eleven":11,"twelve":12,"fifteen":15,"twenty":20,
}


def _first_number(s):
    m = re.search(r"(\d+)", s)
    if m:
        return int(m.group(1))
    for w, v in _NUMS.items():
        if re.search(r"\b" + re.escape(w) + r"\b", s, re.I):
            return v
    return None


def parse_timer_start(text):
    t = text.lower()
    total = 0
    # explicit mm:ss or "X minutes Y seconds"
    m = re.search(r"(\d+)\s*:\s*(\d+)", t)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    for word in ("hour", "heure", "hours", "heures"):
        if word in t:
            v = _first_number(t.split(word)[0].split()[-1:]) if False else None
    # seconds
    for pat in (r"(\d+)\s*(?:seconds?|secondes?|secs?)",):
        for m in re.finditer(pat, t, re.I):
            total += int(m.group(1))
    # minutes
    for pat in (r"(\d+)\s*(?:minutes?|mins?)", r"(\d+)\s*(?:min\b)",):
        for m in re.finditer(pat, t, re.I):
            total += int(m.group(1)) * 60
    # hours
    for pat in (r"(\d+)\s*(?:hours?|heures?)",):
        for m in re.finditer(pat, t, re.I):
            total += int(m.group(1)) * 3600
    # word numbers + units
    if total == 0:
        # fallback: first number + unit guess
        n = _first_number(t)
        if n is not None:
            if "second" in t or "sec" in t:
                total = n
            elif "hour" in t or "heure" in t:
                total = n * 3600
            elif "min" in t:
                total = n * 60
    if "half an hour" in t or "une demi-heure" in t or "demie" in t:
        total = max(total, 1800) if total else 1800
    return total if total > 0 else None


def parse_alarm_time(text):
    t = text.lower()
    # hh:mm / hh.hmm / 7h30 / 8:30
    m = re.search(r"(\d{1,2})\s*[h:.]\s*(\d{0,2})", t)
    if m:
        h = int(m.group(1)) % 24
        mm = int(m.group(2)) if m.group(2) else 0
        return h, mm
    # named hours
    for name, val in _NUMS.items():
        if re.search(r"\b" + name + r"\s*(?:heure|h)\b", t, re.I):
            mm = 30 if ("demie" in t or "half" in t) else 0
            return val % 24, mm
    return None


def parse_alarm_set(text):
    time = parse_alarm_time(text)
    if time is None:
        return None
    h, m = time
    once = "demain" in text.lower() or "tomorrow" in text.lower()
    from datetime import date, timedelta, datetime
    today = date.today()
    target = today
    if once:
        target = today + timedelta(days=1)
    return {"hour": h, "minute": m, "once": once, "date": target.isoformat() if once else None}


def parse_music_subintent(text):
    t = text.lower()
    if any(w in t for w in ("suivant", "next", "skip")):
        return "next"
    if any(w in t for w in ("précédent", "previous", "back")):
        return "prev"
    if any(w in t for w in ("pause", "stop", "coupe", "arrête")):
        return "pause"
    if any(w in t for w in ("play", "mets", "reprends", "resume", "lance")):
        return "play"
    if any(w in t for w in ("monte", "augmente", "up", "plus fort", "plus haut")):
        return "vol_up"
    if any(w in t for w in ("baisse", "diminue", "down", "moins fort", "moins haut")):
        return "vol_down"
    return "play"


def parse_weather_query(text):
    t = text.lower()
    when = "today"
    if "demain" in t or "tomorrow" in t:
        when = "tomorrow"
    if "week" in t or "weekend" in t or "week-end" in t:
        when = "weekend"
    kind = "general"
    if any(w in t for w in ("pluie", "rain", "pleuvoir")):
        kind = "rain"
    if any(w in t for w in ("vent", "wind")):
        kind = "wind"
    if any(w in t for w in ("temp", "degré", "degree", "chaud", "froid")):
        kind = "temp"
    return {"when": when, "kind": kind}
