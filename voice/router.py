"""Laya router wrapper: load a local checkpoint, classify with the override."""
import os
import re
import time

ROUTING_QUESTIONS = {
    "category": {
        "type": "choice",
        "instructions": "What kind of request is this smart-clock command?",
        "criteria": {
            "alarm": "setting, changing, or cancelling an alarm",
            "timer": "setting, checking, or cancelling a countdown timer",
            "music": "playing, pausing, skipping, or controlling Spotify playback, including turning the volume up or down",
            "weather": "asking about current or forecast weather",
            "fallback": "anything that is not directly an alarm, timer, music, or weather command",
        },
    },
    "is_complete": {
        "type": "noul",
        "instructions": "Is this a complete, actionable command rather than a trailing-off or partial sentence?",
    },
}

PARLE_FAMILY_RE = re.compile(
    r"(\bparl(?:e[sz]?|ez|er)\b.{0,16}\bfort\b"
    r"|\bt[’']entends?\s+(pas|mal)\b"
    r"|\bentends?\s+pas\b"
    r"|\bcan[’']?t hear you\b|\bcannot hear you\b"
    r"|\bspeak\s+(up|louder)\b)",
    re.IGNORECASE,
)

# "met de la musique" and "mais de la musique" are homophones in spoken French;
# Voxtral defaults to the more common word, so route the music intent explicitly
# rather than trusting the STT's spelling. EN variants included.
MUSIC_FAMILY_RE = re.compile(
    r"\b(mais|mets|met|mettez|mettons)\s+de\s+la\s+(musique|music)\b"
    r"|\bput\s+on\s+(some\s+)?(music|musique)\b"
    r"|\bplay\s+(some\s+)?(music|musique)\b"
    r"|\bpasse\s+de\s+la\s+(musique|music)\b",
    re.IGNORECASE,
)

# Bare control phrases (English or French): route as music even without "musique",
# unless the user is clearly talking about an alarm/timer.
MUSIC_CONTROL_RE = re.compile(
    r"\b(next|suivant|suivante|skip|skipp)\b"
    r"|\b(previous|pr[eé]c[eé]dent(?:e)?|pr[eé]c[eé]dente|back|rewind|recule|retour)\b"
    r"|\b(pause|stop|play|joue|lance|r[eé]sume|resume)\b"
    r"|\bvol(?:ume)?\s*(up|down|monte|baisse)\b",
    re.IGNORECASE,
)


def classify(router, text):
    kwargs = {}
    result = router.predict({"text": text}, ROUTING_QUESTIONS, **kwargs)
    answers = result["answers"]
    out = {
        "category": answers["category"]["choice"],
        "category_confidence": float(answers["category"].get("confidence", 0.0)),
        "is_complete": answers["is_complete"]["noul"],
        "overridden": False,
    }
    if PARLE_FAMILY_RE.search(text.replace("’", "'").lower()):
        out["category"] = "fallback"
        out["category_confidence"] = 1.0
        out["overridden"] = True
    if MUSIC_FAMILY_RE.search(text.replace("’", "'").lower()):
        out["category"] = "music"
        out["category_confidence"] = 1.0
        out["overridden"] = True
    return out


class RouterService:
    def __init__(self, model_dir=None):
        self.model_dir = model_dir or os.environ.get("NESTCLOCK_ROUTER_DIR")
        self.router = None
        self._loaded = False

    def load(self):
        if not self.model_dir or not os.path.isdir(self.model_dir):
            print("Router: no model dir; routing disabled.")
            self._loaded = True
            return
        try:
            from laya import Agent
            self.router = Agent(self.model_dir, device="cpu")
            try:
                self.router.predict({"text": "test"}, ROUTING_QUESTIONS)
            except Exception:
                pass
            print("Router: loaded and warmed up.")
        except Exception as e:
            print(f"Router: failed to load: {e}")
            self.router = None
        self._loaded = True

    def route(self, text):
        if not text:
            return {"category": "fallback", "category_confidence": 0.0,
                    "overridden": False, "ms": 0.0, "model": None}
        # STT homophone overrides — run before the model so they work even
        # when the router is absent (e.g. "mais de la musique" vs "met de la
        # musique" are identical in speech; Voxtral defaults to the common word)
        norm = text.replace("’", "'").lower()
        if MUSIC_FAMILY_RE.search(norm):
            return {"category": "music", "category_confidence": 1.0,
                    "overridden": True, "ms": 0.0, "model": "homophone-override"}
        if MUSIC_CONTROL_RE.search(norm) and not any(w in norm for w in ("alarm", "timer", "minuteur", "alarme", "rappel", "timmer")):
            return {"category": "music", "category_confidence": 1.0,
                    "overridden": True, "ms": 0.0, "model": "control-override"}
        if PARLE_FAMILY_RE.search(norm):
            return {"category": "fallback", "category_confidence": 1.0,
                    "overridden": True, "ms": 0.0, "model": "homophone-override"}
        if self.router is None:
            return {"category": "fallback", "category_confidence": 0.0,
                    "overridden": False, "ms": 0.0, "model": None}
        t0 = time.time()
        try:
            res = classify(self.router, text)
        except Exception as e:
            return {"category": "fallback", "category_confidence": 0.0,
                    "overridden": False, "ms": (time.time() - t0) * 1000, "error": str(e)}
        ms = (time.time() - t0) * 1000
        res["ms"] = ms
        res["model"] = self.model_dir
        return res
