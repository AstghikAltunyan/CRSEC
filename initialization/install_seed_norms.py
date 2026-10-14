"""
Install fixed, researcher-designed seed norms for the committed-minority agents
(identity == "entrepreneur") in the base simulation, and reset every other agent
to a clean, norm-free start.

Run AFTER initialization.py and BEFORE starting reverie.py.
When reverie.py asks "Regenerate norms? (y or n)", answer n.

Usage (from the CRSEC folder):
    python initialization/install_seed_norms.py
"""
import argparse
import json
import os
import shutil
from glob import glob

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# The researcher-designed seed norms (identical for every entrepreneur, every run).
SEED_NORMS = [
    {"type": "injunctive",
     "content": "Communities must take urgent action on climate change.",
     "subject": "communities", "predicate": "must take",
     "object": "urgent action on climate change", "utility": 85},
    {"type": "injunctive",
     "content": "Cleanliness and sustainability practices should be encouraged in public spaces.",
     "subject": "cleanliness and sustainability practices", "predicate": "should be encouraged",
     "object": "in public spaces", "utility": 75},
    {"type": "descriptive",
     "content": "Everyone engages in activities that raise awareness about climate change and its impacts on health and the environment.",
     "subject": "everyone", "predicate": "engages in",
     "object": "activities that raise awareness about climate change and its impacts on health and the environment",
     "utility": 85},
    {"type": "injunctive",
     "content": "Government cannot be trusted to tackle climate change.",
     "subject": "government", "predicate": "cannot be trusted",
     "object": "to tackle climate change", "utility": 85},
    {"type": "descriptive",
     "content": "Most residents rely on communities rather than institutions for climate commitments.",
     "subject": "most residents", "predicate": "rely on",
     "object": "communities rather than institutions for climate commitments", "utility": 70},
]


def build_norm_file():
    out = {}
    for i, n in enumerate(SEED_NORMS, start=1):
        out[f"norm_{i}"] = {
            "ID": i,
            "type": n["type"],
            "content": n["content"],
            "subject": n["subject"],
            "predicate": n["predicate"],
            "object": n["object"],
            "related_desc": "",
            "utility": n["utility"],
            "poi_reason": "researcher-designed seed norm",
            "activation_state": True,
            "validity_state": True,
        }
    return out


def main():
    parser = argparse.ArgumentParser(description="Install fixed seed norms for entrepreneurs.")
    parser.add_argument(
        "--base-storage-dir",
        default=os.path.join(BASE_DIR, "..", "environment", "frontend_server",
                             "storage", "base_the_ville_n10"),
    )
    args = parser.parse_args()
    base = os.path.abspath(args.base_storage_dir)

    scratch_paths = sorted(glob(os.path.join(base, "personas", "*", "bootstrap_memory", "scratch.json")))
    if not scratch_paths:
        raise SystemExit(f"No personas found under {base}")

    norms = build_norm_file()
    entrepreneurs = []
    for sp in scratch_paths:
        persona_dir = os.path.dirname(os.path.dirname(sp))
        norms_dir = os.path.join(persona_dir, "norms")
        with open(sp, encoding="utf-8") as f:
            scratch = json.load(f)
        name = scratch.get("name", os.path.basename(persona_dir))

        # Clear any norms left over from earlier runs.
        if os.path.isdir(norms_dir):
            shutil.rmtree(norms_dir)

        if scratch.get("identity") == "entrepreneur":
            os.makedirs(norms_dir, exist_ok=True)
            for fname in ("personal_norm_database.json", "personal_norm_database_validity.json"):
                with open(os.path.join(norms_dir, fname), "w", encoding="utf-8") as f:
                    json.dump(norms, f, ensure_ascii=False, indent=2)
            scratch["norm_count"] = len(SEED_NORMS)
            scratch["act_norm_count"] = len(SEED_NORMS)
            entrepreneurs.append(name)
        else:
            scratch["norm_count"] = 0
            scratch["act_norm_count"] = 0

        # Reset the norm-evaluation state to its starting values.
        scratch["norm_evaluate"] = False
        scratch["norm_conflict"] = False
        if "norm_evaluate_trigger_max" in scratch:
            scratch["norm_evaluate_trigger_curr"] = scratch["norm_evaluate_trigger_max"]
        if "norm_importance_trigger_max" in scratch:
            scratch["norm_importance_trigger_curr"] = scratch["norm_importance_trigger_max"]

        with open(sp, "w", encoding="utf-8") as f:
            json.dump(scratch, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"{name:16} identity={scratch.get('identity'):12} norms={scratch['norm_count']}")

    # Keep a copy of this run's stance table inside the base, so every simulation
    # forked from it carries its own bio-initialization.txt.
    bio = os.path.join(BASE_DIR, "bio-initialization.txt")
    if os.path.exists(bio):
        shutil.copy(bio, os.path.join(base, "bio-initialization.txt"))
        print(f"\nCopied bio-initialization.txt into {base}")

    print(f"\nSeed norms installed for: {', '.join(entrepreneurs) if entrepreneurs else 'nobody (null condition)'}")
    print('When reverie.py asks "Regenerate norms? (y or n)", answer: n')


if __name__ == "__main__":
    main()
