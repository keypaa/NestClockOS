"""Tiny local reply-language detector (stop-word counts, default French)."""
_FR = {"le","la","les","un","une","des","de","du","et","est","sont","je","tu","il","elle",
       "nous","vous","pas","ne","que","qui","quoi","où","comment","combien","quel","quelle"}
_EN = {"the","a","an","and","is","are","i","you","he","she","we","they","not","what",
       "how","when","where","do","does","please","alarm","timer"}


def detect_reply_language(text, default="fr"):
    toks = [w.strip(".,?!'’").lower() for w in text.split()]
    fr = sum(1 for w in toks if w in _FR)
    en = sum(1 for w in toks if w in _EN)
    if fr > en:
        return default if default in ("fr", "en") else "fr"
    if en > fr:
        return "en"
    return "fr"
