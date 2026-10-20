"""
Initial Full-Corpus Bootstrap Indexing Script.
Wraps the initial batch ingestion pipeline for bootstrapping the Neo4j Knowledge Graph.
"""

import os
import sys
import argparse
import logging
from pathlib import Path

from app.main import logger

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

from app.gnn.roland_gru import RolandHierarchicalGRU
from app.gnn.neighborhood import BoundedNeighborhoodManager


def run_bootstrap(docs_dir: str):
    logger.info(f"Starting bootstrap indexing from directory: {docs_dir}")
    doc_path = Path(docs_dir)
    if not doc_path.exists():
        logger.error(f"Directory {docs_dir} does not exist!")
        return

    # Initialize subsystems
    processor = TextProcessor(model_name=settings.SPACY_MODEL)
    chunker = SemanticChunker(processor=processor)
    embedder = SentenceTransformerEmbedder(
        model_name=settings.EMBEDDING_MODEL_NAME,
        embedding_dim=settings.NEO4J_EMBEDDING_DIM,
    )
    llm = LLMClient.from_settings(settings)
    extractor = GraphRAGIncrementalExtractor(llm_client=llm, embedder=embedder)

    neo4j_client = Neo4jClient(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD,
        database=settings.NEO4J_DATABASE,
        vector_index_name=settings.NEO4J_VECTOR_INDEX_NAME,
        embedding_dim=settings.NEO4J_EMBEDDING_DIM,
    )
    store = Neo4jGraphStore(client=neo4j_client)
    community_detector = CommunityDetector(client=neo4j_client, llm_client=llm)

    files = list(doc_path.glob("*.txt")) + list(doc_path.glob("*.md"))
    logger.info(f"Discovered {len(files)} files to bootstrap.")

    total_chunks = 0
    all_entity_names = set()
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
        for e in entities:
            all_entity_names.add(e.name)
        total_relationships += len(relationships)

    logger.info(
        f"Corpus ingestion complete! Ingested {len(files)} docs, {total_chunks} chunks, "
        f"{len(all_entity_names)} entities, {total_relationships} relationships."
    )

    # Load the trained ROLAND model (train separately: python -m scripts.train_roland --stream ...)
    checkpoint_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", settings.ROLAND_MODEL_PATH)
    )
    if os.path.exists(checkpoint_path):
        roland = RolandHierarchicalGRU.from_checkpoint(checkpoint_path)
    else:
        logger.warning("No ROLAND checkpoint at %s: bootstrapping with UNTRAINED weights.", checkpoint_path)
        roland = RolandHierarchicalGRU(
            in_dim=settings.NEO4J_EMBEDDING_DIM, hidden_dim=settings.GNN_HIDDEN_DIM,
            out_dim=settings.NEO4J_EMBEDDING_DIM, num_layers=settings.GNN_NUM_LAYERS,
            gnn_type=settings.GNN_TYPE, dropout=settings.GNN_DROPOUT, residual=True,
        ).eval()

    # Execute GNN initial embedding pass over entire bootstrap graph
    if all_entity_names:
        logger.info(f"Running initial ROLAND GNN embedding pass on {len(all_entity_names)} entities...")
        neighborhood_mgr = BoundedNeighborhoodManager(roland_model=roland, default_k=settings.DEFAULT_K_HOPS)
        nodes, edges = store.get_k_hop_neighborhood(
            seed_entity_names=list(all_entity_names),
            k=settings.DEFAULT_K_HOPS,
        )
        updated_embeddings, metrics = neighborhood_mgr.run_bounded_update(
            seed_entity_names=list(all_entity_names),
            neighborhood_nodes=nodes,
            neighborhood_edges=edges,
            k=settings.DEFAULT_K_HOPS,
        )
        store.update_node_embeddings(updated_embeddings)
        logger.info(
            f"Committed {len(updated_embeddings)} initial GNN representations to store in {metrics['processing_time_ms']}ms."
        )

        # Scoped initial community detection
        logger.info("Computing initial Leiden communities...")
        communities = community_detector.detect_communities_incremental(
            affected_entity_names=list(all_entity_names),
            neighborhood_nodes=nodes,
            neighborhood_edges=edges,
        )
        logger.info(f"Detected {len(communities)} communities.")

    logger.info("Bootstrap indexing and GNN initialization complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bootstrap index documents into Neo4j and run GNN")
    parser.add_argument("--docs-dir", type=str, default="./sample_docs", help="Path to documents folder")
    args = parser.parse_args()
    run_bootstrap(args.docs_dir)