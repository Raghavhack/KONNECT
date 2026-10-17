"""
KONNECT Python Intelligence Layer - Configuration
Manages service parameters, Neo4j, Redis, LLM, and model settings.
"""

from typing import Optional, List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Service Configuration
    SERVICE_NAME: str = "konnect-intelligence-service"
    SERVICE_VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    DEBUG: bool = Field(default=False, env="DEBUG")

    # Network Ports
    HTTP_PORT: int = Field(default=8000, env="HTTP_PORT")
    HTTP_HOST: str = Field(default="0.0.0.0", env="HTTP_HOST")
    GRPC_PORT: int = Field(default=50051, env="GRPC_PORT")
    GRPC_HOST: str = Field(default="0.0.0.0", env="GRPC_HOST")

    # Neo4j Graph Database
    NEO4J_URI: str = Field(default="bolt://localhost:7687", env="NEO4J_URI")
    NEO4J_USER: str = Field(default="neo4j", env="NEO4J_USER")
    NEO4J_PASSWORD: str = Field(default="password", env="NEO4J_PASSWORD")
    NEO4J_DATABASE: str = Field(default="neo4j", env="NEO4J_DATABASE")
    NEO4J_VECTOR_INDEX_NAME: str = "entity_embeddings_index"
    NEO4J_EMBEDDING_DIM: int = 384

    # Redis Cache & Queue
    REDIS_HOST: str = Field(default="localhost", env="REDIS_HOST")
    REDIS_PORT: int = Field(default=6379, env="REDIS_PORT")
    REDIS_PASSWORD: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    REDIS_DB: int = Field(default=0, env="REDIS_DB")
    SEMANTIC_CACHE_TTL_SECONDS: int = 86400  # 24 hours
    SEMANTIC_CACHE_SIMILARITY_THRESHOLD: float = 0.92

    # Text Preprocessing & NLP (spaCy)
    SPACY_MODEL: str = Field(default="en_core_web_sm", env="SPACY_MODEL")
    CHUNK_SIZE: int = 500  # Target tokens per chunk
    CHUNK_OVERLAP: int = 50  # Token overlap between consecutive chunks

    # Embedding Model (Sentence Transformers)
    EMBEDDING_MODEL_NAME: str = Field(
        default="all-MiniLM-L6-v2",
        env="EMBEDDING_MODEL_NAME"
    )
    EMBEDDING_DEVICE: str = Field(default="cpu", env="EMBEDDING_DEVICE")
    EMBEDDING_BATCH_SIZE: int = 32

    # GNN & ROLAND Dynamic Graph Model
    GNN_HIDDEN_DIM: int = 128
    GNN_OUT_DIM: int = 384  # Matches NEO4J_EMBEDDING_DIM for residual readout in text space
    GNN_NUM_LAYERS: int = 2
    GNN_TYPE: str = "GAT"  # "GAT" or "GraphSAGE"
    GNN_DROPOUT: float = 0.1
    DEFAULT_K_HOPS: int = Field(default=2, env="DEFAULT_K_HOPS")  # Tunable parameter for Section 7 evaluation
    ROLAND_LEARNING_RATE: float = 0.005
    ROLAND_TRUNCATED_BPTT_STEPS: int = 3
    ROLAND_MODEL_PATH: str = Field(default="models/roland_model.pt", env="ROLAND_MODEL_PATH")

    # PCST (Prize-Collecting Steiner Tree) Retrieval
    PCST_COST_WEIGHT: float = 0.15
    PCST_PRIZE_THRESHOLD: float = 0.40
    PCST_MAX_SUBGRAPH_NODES: int = 25
    PCST_PRUNING: str = "gw"  # Goemans-Williamson
    PCST_USE_GNN: bool = Field(default=True, env="PCST_USE_GNN")  # Set False for Arm D ablation

    # LLM Settings (OpenAI / Anthropic)
    LLM_PROVIDER: str = Field(default="openai", env="LLM_PROVIDER")  # "openai" or "anthropic"
    OPENAI_API_KEY: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    OPENAI_MODEL: str = Field(default="gpt-4o", env="OPENAI_MODEL")
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    ANTHROPIC_MODEL: str = Field(default="claude-3-5-sonnet-20241022", env="ANTHROPIC_MODEL")
    LLM_TEMPERATURE: float = 0.0
    LLM_MAX_RETRIES: int = 5
    LLM_BASE_DELAY_SECONDS: float = 0.5


# Singleton settings instance
settings = Settings()
