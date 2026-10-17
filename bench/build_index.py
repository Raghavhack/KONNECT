"""
Corpus Bootstrap Indexing CLI.
Initializes a clean graph and indexes a prefix of the eval corpus.
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path

# Add project root to path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "ai_service"))

from bench.common import init_pipeline, reset_all, install_extraction_cache, bootstrap_corpus

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("build_index")


def main():
    parser = argparse.ArgumentParser(description="Bootstrap index a corpus prefix into KONNECT")
    parser.add_argument("--prefix", type=int, default=500, help="Number of documents to index from corpus_order")
    parser.add_argument("--k", type=int, default=2, help="k-hop neighborhood size for GNN")
    parser.add_argument("--config", type=str, default="bench/config.json", help="Path to frozen config.json")
    args = parser.parse_args()

    config = json.load(open(REPO_ROOT / args.config))
    cache_dir = REPO_ROOT / config.get("cache_dir", "data/cache/extraction_cache")
    corpus_order_path = REPO_ROOT / "data" / "splits" / "corpus_order.json"
    eval_docs_dir = REPO_ROOT / "data" / "splits" / "eval_docs"

    corpus_order = json.load(open(corpus_order_path))
    selected_slugs = corpus_order[:args.prefix]
    doc_paths = [eval_docs_dir / f"{slug}.txt" for slug in selected_slugs]

    logger.info(f"Initializing pipeline and indexing prefix {args.prefix} ({len(doc_paths)} docs)...")
    container = init_pipeline(strict=True)
    reset_all(container)

    extractor = container["incremental_engine"].extractor
    install_extraction_cache(extractor, str(cache_dir), config.get("llm_model", "gpt-4o"))

    timings = bootstrap_corpus(container, doc_paths, k_hops=args.k)
    logger.info(f"Indexing completed! Timings: {json.dumps(timings, indent=2)}")


if __name__ == "__main__":
    main()
