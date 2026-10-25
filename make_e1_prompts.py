"""Prepare a ~120-utterance prompt CSV for E1.2 recording sessions."""
import csv, random
rows = list(csv.DictReader(open("phase0_5/synthetic_dataset_raw.csv", encoding="utf-8")))
held = [r for r in rows if r.get("split") == "held_out_eval"]
mixed_src = [r for r in __import__("csv").DictReader(open("phase0/test_phrases_large.csv", encoding="utf-8"))]
# ensure mixed_src language tagged
for r in mixed_src:
    r.setdefault("language", "mixed" if "mixed" in r.get("language","") else r.get("language","mixed"))

random.seed(42)
picked = []
# stratify: 50% fr, 35% en, 15% mixed, equal categories within
targets = {"fr": 60, "en": 42, "mixed": 18}
for lang, want in targets.items():
    pool = [r for r in (held if lang != "mixed" else mixed_src) if r.get("language") == lang]
    # equal categories
    by_cat = {}
    for r in pool:
        by_cat.setdefault(r.get("expected_category", ""), []).append(r)
    cats = list(by_cat)
    out = []
    idx = 0
    while len(out) < want and any(by_cat.values()):
        for c in cats:
            if by_cat[c] and len(out) < want:
                out.append(by_cat[c].pop(random.randrange(len(by_cat[c]))))
    picked.extend(out)

random.shuffle(picked)
with open("phase4a_prompts.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["phrase", "expected_category", "language"])
    for r in picked:
        w.writerow([r["phrase"], r.get("expected_category", ""), r.get("language", "")])
print(f"wrote {len(picked)} prompts to phase4a_prompts.csv")
