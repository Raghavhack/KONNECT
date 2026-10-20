import json, random, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]             # repo root
RAW = Path(__file__).resolve().parents[1] / "KONNECT_benchmarking_dataset" / "data" / "dev.json"
OUT_DIR = ROOT / "data" / "splits"
DOCS = OUT_DIR / "eval_docs"
SEED = 42
PER_TYPE = {"comparison": 13, "inference": 13, "compositional": 12, "bridge_comparison": 12}  # 50 total


def slug(t):
    s = re.sub(r'[^a-zA-Z0-9]+', '_', t.strip()).strip('_').lower()
    return s or "doc"


if DOCS.exists() and any(DOCS.glob("*.txt")):
    raise SystemExit(f"{DOCS} already has files. Eval set is frozen; delete it deliberately if you really want to regenerate.")

data = json.load(open(RAW, encoding="utf-8"))
rng = random.Random(SEED)
chosen = []
for typ, n in PER_TYPE.items():
    pool = [q for q in data if q["type"] == typ]
    if len(pool) < n:
        raise SystemExit(f"Only {len(pool)} '{typ}' questions in dev.json, need {n}")
    chosen += rng.sample(pool, n)

DOCS.mkdir(parents=True, exist_ok=True)
seen = set()
for q in chosen:
    for title, sents in q["context"]:
        s = slug(title)
        if s in seen:
            continue
        seen.add(s)
        (DOCS / f"{s}.txt").write_text(title + "\n" + " ".join(sents), encoding="utf-8")

json.dump(chosen, open(OUT_DIR / "eval_questions.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"{len(chosen)} questions, {len(seen)} eval docs written to {DOCS}")