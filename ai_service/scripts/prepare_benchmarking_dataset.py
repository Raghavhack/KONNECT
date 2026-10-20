import json, random, re, glob, os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]            # repo root (KONNECT/)
RAW = Path(__file__).resolve().parents[1] / "KONNECT_benchmarking_dataset" / "data" / "train.json"
EVAL_DIR = ROOT / "data" / "splits" / "eval_docs"
OUT = ROOT / "data" / "train_stream.jsonl"
N_DOCS = 300


def slug(t):  # same rule as make_splits.py
    s = re.sub(r'[^a-zA-Z0-9]+', '_', t.strip()).strip('_').lower()
    return s or "doc"


eval_files = glob.glob(str(EVAL_DIR / "*.txt"))
if not eval_files:
    raise SystemExit(f"No eval docs found in {EVAL_DIR}. Restore them first, or the leakage check is meaningless.")

eval_slugs = {os.path.splitext(os.path.basename(f))[0] for f in eval_files}
eval_slugs |= {re.sub(r'^\d+_', '', s) for s in eval_slugs}   # also match without a numeric prefix

data = json.load(open(RAW, encoding="utf-8"))
random.Random(43).shuffle(data)

seen, out = set(), []
for q in data:
    for title, sents in q["context"]:
        s = slug(title)
        if s in seen or s in eval_slugs:
            continue
        seen.add(s)
        out.append({"doc_id": s + ".txt", "text": title + "\n" + " ".join(sents)})
    if len(out) >= N_DOCS:
        break

out = out[:N_DOCS]
OUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    for r in out:
        f.write(json.dumps(r) + "\n")
print(f"{len(out)} edits written to {OUT} (checked against {len(eval_files)} eval docs)")