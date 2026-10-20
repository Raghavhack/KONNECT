"""
KONNECT Python Intelligence Service - Main Entry Point.
Wires together the entire end-to-end intelligence pipeline:
spaCy Preprocessing -> GraphRAG Extraction -> Neo4j Knowledge Store ->
ROLAND Hierarchical GRU Dynamic Re-Embedding -> Leiden Community Detection ->
Redis Semantic Cache Invalidation & Query Answering -> PCST Subgraph Retrieval ->
LLM Generation with Grounded Citations -> FastAPI REST & gRPC Servicer.
"""

import os
import sys
import logging
import threading
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Project root path setup
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import settings
from app.preprocessing.text_processor import TextProcessor
from app.preprocessing.chunker import SemanticChunker
from app.embeddings.embedder import SentenceTransformerEmbedder
from app.llm.client import LLMClient
from app.llm.generator import AnswerGenerator
from app.extraction.graphrag_extractor import GraphRAGIncrementalExtractor
from app.graph.neo4j_client import Neo4jClient
from app.graph.store import Neo4jGraphStore
from app.graph.community import CommunityDetector
from app.gnn.roland_gru import RolandHierarchicalGRU
from app.gnn.neighborhood import BoundedNeighborhoodManager
from app.cache.semantic_cache import SemanticCache
from app.retrieval.pcst_retriever import PCSTSubgraphRetriever
from app.pipeline.incremental_engine import IncrementalEngine
from app.pipeline.query_engine import QueryEngine
from app.api.routes import router as api_router, pipeline_container
try:
    from app.grpc.servicer import IntelligenceServicer
    from app.grpc.server import GRPCServer
    GRPC_ENABLED = True
except ImportError:
    IntelligenceServicer = None
    GRPCServer = None
    GRPC_ENABLED = False

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
)
logger = logging.getLogger("konnect-main")


def initialize_pipeline():
    """
    Instantiates and wires together all core subsystems in the intelligence pipeline.
    """
    logger.info("Initializing KONNECT intelligence pipeline subsystems...")

    # 1. Text Preprocessor & Chunker
    processor = TextProcessor(model_name=settings.SPACY_MODEL)
    chunker = SemanticChunker(
        processor=processor,
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
    )

    # 2. Text Embedder (MiniLM, 384 dimensions)
    embedder = SentenceTransformerEmbedder(
        model_name=settings.EMBEDDING_MODEL_NAME,
        device=settings.EMBEDDING_DEVICE,
        embedding_dim=settings.NEO4J_EMBEDDING_DIM,
    )

    # 3. LLM Client & GraphRAG Extractor
    llm_client = LLMClient(
        provider=settings.LLM_PROVIDER,
        openai_api_key=settings.OPENAI_API_KEY,
        anthropic_api_key=settings.ANTHROPIC_API_KEY,
        default_model=settings.OPENAI_MODEL if settings.LLM_PROVIDER == "openai" else settings.ANTHROPIC_MODEL,
        max_retries=settings.LLM_MAX_RETRIES,
        base_delay=settings.LLM_BASE_DELAY_SECONDS,
    )
    extractor = GraphRAGIncrementalExtractor(
        llm_client=llm_client,
        embedder=embedder,
    )

    # 4. Neo4j Graph Database & Knowledge Store
    neo4j_client = Neo4jClient(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD,
        database=settings.NEO4J_DATABASE,
        vector_index_name=settings.NEO4J_VECTOR_INDEX_NAME,
        embedding_dim=settings.NEO4J_EMBEDDING_DIM,
    )
    graph_store = Neo4jGraphStore(client=neo4j_client)

    # 5. Leiden Community Detector
    community_detector = CommunityDetector(
        client=neo4j_client,
        llm_client=llm_client,
    )

    # 6. ROLAND Hierarchical Dynamic Graph GRU Model
    # A checkpoint carries its own architecture; an invalid/old-format checkpoint is a hard error.
    checkpoint_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", settings.ROLAND_MODEL_PATH)
    )
    if os.path.exists(checkpoint_path):
        roland_model = RolandHierarchicalGRU.from_checkpoint(checkpoint_path)
    else:
        logger.warning(
            "No trained ROLAND checkpoint at %s: running with UNTRAINED weights. "
            "Train with `python -m scripts.train_roland --stream ...`.", checkpoint_path
        )
        roland_model = RolandHierarchicalGRU(
            in_dim=settings.NEO4J_EMBEDDING_DIM,
            hidden_dim=settings.GNN_HIDDEN_DIM,
            out_dim=settings.NEO4J_EMBEDDING_DIM,
            num_layers=settings.GNN_NUM_LAYERS,
            gnn_type=settings.GNN_TYPE,
            dropout=settings.GNN_DROPOUT,
            residual=True,
        ).eval()

    # 7. Bounded Neighborhood Re-embedding Manager
    neighborhood_manager = BoundedNeighborhoodManager(
        roland_model=roland_model,
        default_k=settings.DEFAULT_K_HOPS,
    )

    # 8. Redis Semantic Cache
    semantic_cache = SemanticCache(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD,
        db=settings.REDIS_DB,
        ttl_seconds=settings.SEMANTIC_CACHE_TTL_SECONDS,
        similarity_threshold=settings.SEMANTIC_CACHE_SIMILARITY_THRESHOLD,
    )

    # 9. PCST Subgraph Retriever
    pcst_retriever = PCSTSubgraphRetriever(
        embedder=embedder,
        graph_store=graph_store,
        cost_weight=settings.PCST_COST_WEIGHT,
        prize_threshold=settings.PCST_PRIZE_THRESHOLD,
        max_subgraph_nodes=settings.PCST_MAX_SUBGRAPH_NODES,
        use_gnn=settings.PCST_USE_GNN,
    )

    # 10. Grounded Answer Generator
    answer_generator = AnswerGenerator(llm_client=llm_client)

    # 11. Incremental Pipeline Orchestration Engine
    incremental_engine = IncrementalEngine(
        text_processor=processor,
        chunker=chunker,
        embedder=embedder,
        extractor=extractor,
        graph_store=graph_store,
        neighborhood_manager=neighborhood_manager,
        community_detector=community_detector,
        semantic_cache=semantic_cache,
    )

    # 12. Query Answering Engine
    query_engine = QueryEngine(
        embedder=embedder,
        semantic_cache=semantic_cache,
        pcst_retriever=pcst_retriever,
        answer_generator=answer_generator,
    )

    # Register into API container for FastAPI dependency injection
    pipeline_container["incremental_engine"] = incremental_engine
    pipeline_container["query_engine"] = query_engine
    pipeline_container["neighborhood_manager"] = neighborhood_manager
    pipeline_container["graph_store"] = graph_store
    pipeline_container["roland_model"] = roland_model
    pipeline_container["semantic_cache"] = semantic_cache
    pipeline_container["pcst_retriever"] = pcst_retriever

    logger.info("KONNECT intelligence pipeline successfully wired and ready.")
    return pipeline_container


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager: initializes pipelines and coordinates gRPC and REST services."""
    container = initialize_pipeline()

    # Start gRPC servicer in background thread
    grpc_server: Optional[GRPCServer] = None
    try:
        servicer = IntelligenceServicer(
            incremental_engine=container["incremental_engine"],
            query_engine=container["query_engine"],
            neighborhood_manager=container["neighborhood_manager"],
        )
        grpc_server = GRPCServer(
            servicer=servicer,
            host=settings.GRPC_HOST,
            port=settings.GRPC_PORT,
        )
        grpc_thread = threading.Thread(target=grpc_server.start, daemon=True)
        grpc_thread.start()
        logger.info(f"gRPC server started in background thread on {settings.GRPC_HOST}:{settings.GRPC_PORT}")
    except Exception as e:
        logger.warning(f"Could not start gRPC server: {e}")

    yield

    # Shutdown
    logger.info("Shutting down KONNECT Intelligence Service...")
    if grpc_server:
        grpc_server.stop(grace=2)
    neo4j_client = container["incremental_engine"].graph_store.client
    neo4j_client.close()
    logger.info("Shutdown completed.")


def create_app() -> FastAPI:
    """Builds and configures the FastAPI application instance."""
    app = FastAPI(
        title="KONNECT Intelligence Service",
        description="GraphRAG + ROLAND Dynamic GNN + PCST Subgraph Retrieval Intelligence API",
        version=settings.SERVICE_VERSION,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    @app.get("/", tags=["system"])
    async def root():
        return {
            "service": settings.SERVICE_NAME,
            "version": settings.SERVICE_VERSION,
            "status": "RUNNING",
            "docs": "/docs",
        }

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HTTP_HOST,
        port=settings.HTTP_PORT,
        reload=settings.DEBUG,
    )