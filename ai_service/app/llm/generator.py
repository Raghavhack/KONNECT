"""
Answer Generator with Grounded Citations.
Synthesizes answers from PCST-retrieved knowledge graph context and extracts verifiable citations.
"""

import re
import logging
from typing import List, Dict, Any, Tuple
from .client import LLMClient

logger = logging.getLogger(__name__)

ANSWER_SYSTEM_PROMPT = """You are KONNECT's AI reasoning engine.
Your mission is to answer user queries truthfully, grounded strictly in the provided Knowledge Graph context.

Guidelines:
1. Ground every claim in the entities and relationships provided.
2. Whenever you mention or rely on information from an entity, cite it explicitly using bracket notation: [Entity Name].
3. If the context does not contain sufficient information to answer the question, state so transparently.
4. Provide structured, lucid, and comprehensive responses.
"""


class AnswerGenerator:
    """Generates answers and extracts citations referencing retrieved graph entities."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def generate_answer_with_citations(
        self,
        query: str,
        context_str: str,
        retrieved_nodes: List[Dict[str, Any]],
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Generates response and parses citations.
        Returns:
            - answer_text (str)
            - citations: list of dicts {entity_name, relevance_score, quote}
        """
        prompt = (
            f"Question:\n{query}\n\n"
            f"{context_str}\n\n"
            f"Please synthesize a detailed answer with explicit citations [Entity Name]:"
        )

        answer_text = self.llm.generate(
            prompt=prompt,
            system_prompt=ANSWER_SYSTEM_PROMPT,
            temperature=0.1,
        )

        # Parse bracketed citations e.g. [Entity Name]
        cited_names = set(re.findall(r"\[([a-zA-Z0-9_\s\.\-]+)\]", answer_text))
        node_map = {n.get("name", "").lower(): n for n in retrieved_nodes}

        citations = []
        for name in cited_names:
            norm_name = name.strip().lower()
            if norm_name in node_map:
                node_data = node_map[norm_name]
                citations.append({
                    "entity_id": node_data.get("id", name),
                    "entity_name": node_data.get("name", name),
                    "document_id": node_data.get("document_id", "doc_primary"),
                    "quote": node_data.get("description", "")[:120],
                    "relevance_score": float(node_data.get("importance_score", 1.0)),
                })

        # If no explicit bracket citations, cite top nodes in retrieved subgraph
        if not citations and retrieved_nodes:
            for n in retrieved_nodes[:3]:
                citations.append({
                    "entity_id": n.get("id", n.get("name")),
                    "entity_name": n.get("name"),
                    "document_id": n.get("document_id", "doc_primary"),
                    "quote": n.get("description", "")[:120],
                    "relevance_score": float(n.get("importance_score", 1.0)),
                })

        return answer_text, citations
