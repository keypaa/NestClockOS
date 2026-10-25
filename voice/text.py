"""Text normalisation and WER."""
import re
import unicodedata


def normalize(text):
    t = unicodedata.normalize("NFKC", text).lower()
    t = re.sub(r"[’'`\-]", " ", t)
    t = re.sub(r"[^\w\s]", " ", t)
    return t.split()


def wer(ref, hyp):
    if not ref:
        return 0.0 if not hyp else 1.0
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i]
        for j, h in enumerate(hyp, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h)))
        prev = cur
    return prev[-1] / len(ref)
