"""
Initial Full-Corpus Bootstrap Indexing Script.
Wraps the initial batch ingestion pipeline for bootstrapping the Neo4j Knowledge Graph.
"""

import os
import sys
import argparse
import logging
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import settings
from app.preprocessing.text_processor import TextProcessor
from app.preprocessing.chunker import SemanticChunker
from app.embeddings.embedder import SentenceTransformerEmbedder
from app.llm.client import LLMClient
from app.extraction.graphrag_extractor import GraphRAGIncrementalExtractor
from app.graph.neo4j_client import Neo4jClient
from app.graph.store import Neo4jGraphStore
from app.graph.community import CommunityDetector

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("bootstrap")


def run_bootstrap(docs_dir: str):
    logger.info(f"Starting bootstrap indexing from directory: {docs_dir}")
    doc_path = Path(docs_dir)
    if not doc_path.exists():
        logger.error(f"Directory {docs_dir} does not exist!")
        return

    # Initialize subsystems
    processor = TextProcessor(model_name=settings.SPACY_MODEL)
    chunker = SemanticChunker(processor=processor)
    embedder = SentenceTransformerEmbedder(model_name=settings.EMBEDDING_MODEL_NAME)
    llm = LLMClient(provider=settings.LLM_PROVIDER, openai_api_key=settings.OPENAI_API_KEY)
    extractor = GraphRAGIncrementalExtractor(llm_client=llm, embedder=embedder)

    neo4j_client = Neo4jClient(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD,
    )
    store = Neo4jGraphStore(client=neo4j_client)
    community_detector = CommunityDetector(client=neo4j_client, llm_client=llm)

    files = list(doc_path.glob("*.txt")) + list(doc_path.glob("*.md"))
    logger.info(f"Discovered {len(files)} files to bootstrap.")

    total_chunks = 0
    total_entities = 0
    total_relationships = 0

    for idx, f in enumerate(files):
        doc_id = f.stem
        text = f.read_text(encoding="utf-8", errors="ignore")
        logger.info(f"[{idx+1}/{len(files)}] Processing document '{doc_id}' ({len(text)} chars)...")

        chunks = chunker.chunk_document(document_id=doc_id, text=text)
        entities, relationships = extractor.extract_from_document(
            document_id=doc_id, title=doc_id, chunks=chunks
        )

        store.upsert_document_and_chunks(doc_id, doc_id, chunks)
        store.upsert_entities(entities, document_id=doc_id)
        store.upsert_relationships(relationships)

        total_chunks += len(chunks)
        total_entities += len(entities)
        total_relationships += len(relationships)

    logger.info(
        f"Bootstrap indexing complete! Ingested {len(files)} docs, {total_chunks} chunks, "
        f"{total_entities} entities, {total_relationships} relationships."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bootstrap index documents into Neo4j")
    parser.add_argument("--docs-dir", type=str, default="./sample_docs", help="Path to documents folder")
    args = parser.parse_args()
    run_bootstrap(args.docs_dir)
