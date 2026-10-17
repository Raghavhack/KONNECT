"""
Query Answering Engine.
Coordinates: Redis Semantic Cache Check -> PCST Subgraph Retrieval ->
Context Synthesis -> LLM Generation -> Verifiable Citations -> Cache Update.
"""

import time
import logging
from typing import Dict, Any, Optional

from ..embeddings.embedder import SentenceTransformerEmbedder
from ..cache.semantic_cache import SemanticCache
from ..retrieval.pcst_retriever import PCSTSubgraphRetriever
from ..retrieval.context_builder import ContextBuilder
from ..llm.generator import AnswerGenerator

logger = logging.getLogger(__name__)


class QueryEngine:
    """
    Orchestrates the PCST semantic query answering pipeline with caching and citations.
    """

    def __init__(
        self,
        embedder: SentenceTransformerEmbedder,
        semantic_cache: SemanticCache,
        pcst_retriever: PCSTSubgraphRetriever,
        answer_generator: AnswerGenerator,
    ):
        self.embedder = embedder
        self.semantic_cache = semantic_cache
        self.pcst_retriever = pcst_retriever
        self.answer_generator = answer_generator

    def execute_query(
        self,
        query: str,
        query_id: Optional[str] = None,
        bypass_cache: bool = False,
        cost_weight: Optional[float] = None,
        similarity_threshold: Optional[float] = None,
        use_gnn: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Executes query answering:
        1. Embeds query string.
        2. Checks semantic cache (unless bypassed).
        3. If miss, runs PCST retrieval to identify optimal subgraph.
        4. Synthesizes answer with citations via LLM.
        5. Commits result to semantic cache.
        """
        t_start = time.perf_counter()
        q_id = query_id or f"q_{int(t_start * 1000)}"

        # Step 1: Embed query
        q_emb = self.embedder.embed_text(query)

        # Step 2: Semantic Cache Lookup
        if not bypass_cache:
            cached_match = self.semantic_cache.lookup(q_emb)
            if cached_match:
                elapsed_ms = (time.perf_counter() - t_start) * 1000.0
                return {
                    "query_id": q_id,
                    "query": query,
                    "answer": cached_match["answer"],
                    "citations": cached_match.get("citations", []),
                    "subgraph": cached_match.get("subgraph", {}),
                    "cache_hit": True,
                    "retrieval_time_ms": 0.0,
                    "generation_time_ms": 0.0,
                    "total_latency_ms": round(elapsed_ms, 2),
                }

        # Step 3: PCST Subgraph Retrieval (From Scratch prize assignment + PCST solver)
        t_ret = time.perf_counter()
        subgraph = self.pcst_retriever.retrieve_subgraph(
            query=query,
            cost_weight=cost_weight,
            threshold=similarity_threshold,
            use_gnn=use_gnn,
        )
        retrieval_time_ms = (time.perf_counter() - t_ret) * 1000.0

        # Step 4: Build structured context
        context_str = ContextBuilder.build_llm_context(subgraph=subgraph)

        # Step 5: Answer generation with citations
        t_gen = time.perf_counter()
        answer, citations = self.answer_generator.generate_answer_with_citations(
            query=query,
            context_str=context_str,
            retrieved_nodes=subgraph.get("nodes", []),
        )
        generation_time_ms = (time.perf_counter() - t_gen) * 1000.0

        # Step 6: Store in Semantic Cache
        cited_entity_names = [c["entity_name"] for c in citations if "entity_name" in c]
        if not cited_entity_names and subgraph.get("nodes"):
            cited_entity_names = [n["name"] for n in subgraph["nodes"] if "name" in n]

        self.semantic_cache.store(
            query=query,
            query_embedding=q_emb,
            answer=answer,
            citations=citations,
            subgraph=subgraph,
            cited_entity_names=cited_entity_names,
        )

        total_latency_ms = (time.perf_counter() - t_start) * 1000.0

        return {
            "query_id": q_id,
            "query": query,
            "answer": answer,
            "citations": citations,
            "subgraph": subgraph,
            "cache_hit": False,
            "retrieval_time_ms": round(retrieval_time_ms, 2),
            "generation_time_ms": round(generation_time_ms, 2),
            "total_latency_ms": round(total_latency_ms, 2),
        }
