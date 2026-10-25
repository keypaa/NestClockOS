"""Glue for one voice interaction: STT (P2) + routing, returning a result dict."""
from voice.stt import transcribe_parallel
from voice.text import non_latin
from voice.router import RouterService


def choose_best(en, fr, route_en, route_fr):
    best = None
    for lang, txt, r in (("en", en, route_en), ("fr", fr, route_fr)):
        if not txt.strip():
            continue
        if (lang == "en" and non_latin(txt)) or (lang == "fr" and non_latin(txt)):
            continue
        cand = {"lang": lang, "text": txt, "route": r}
        if best is None or r.get("category_confidence", 0) > best["route"].get("category_confidence", 0):
            best = cand
    if best is None:
        for lang, txt in (("en", en), ("fr", fr)):
            if txt.strip():
                best = {"lang": lang, "text": txt, "route": {"category": "fallback",
                        "category_confidence": 0.0, "overridden": False, "ms": 0.0}}
                break
    return best


def run_text_pipeline(router_service, en_text, fr_text):
    re_ = router_service.route(en_text) if en_text.strip() else None
    rf_ = router_service.route(fr_text) if fr_text.strip() else None
    best = choose_best(en_text, fr_text, re_ or {}, rf_ or {})
    return {
        "transcript": best["text"] if best else "",
        "language": best["lang"] if best else "",
        "category": best["route"].get("category") if best else "fallback",
        "confidence": best["route"].get("category_confidence", 0.0) if best else 0.0,
        "overridden": best["route"].get("overridden", False) if best else False,
        "route_ms": best["route"].get("ms", 0.0) if best else 0.0,
    }
