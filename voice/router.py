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
    return out


class RouterService:
    def __init__(self, model_dir=None):
        self.model_dir = model_dir or os.environ.get("NESTCLOCK_ROUTER_DIR")
        self.router = None
        self._loaded = False

    def load(self):
        if not self.model_dir or not __import__("os").path.isdir(self.model_dir):
            print("Router: no model dir; routing disabled.")
            self._loaded = True
            return
        try:
            from laya import Router
            self.router = Router(self.model_dir, preload=True, device="cpu")
            # warm-up
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
        if not text or self.router is None:
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
