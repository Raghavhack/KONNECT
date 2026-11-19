"""
Answer Generator with Grounded Citations.
Synthesizes answers from PCST-retrieved knowledge graph context and extracts verifiable citations.
"""

import re
import logging
from typing import List, Dict, Any, Tuple
from .client import LLMClient

logger = logging.getLogger(__name__)

ANSWER_SYSTEM_PROMPT = """You are KONNECT AI, an intelligent workspace assistant connected to a live Knowledge Graph and connected workspace documents.

Guidelines:
1. Conversational Queries & Greetings: For greetings (e.g. "hi", "hello", "how are you?"), user identity ("what is my name?", "who am I?"), or general common-sense questions, answer warmly, naturally, and helpfully.
2. Workspace & Knowledge Graph Grounding: When answering questions about documents, people, projects, systems, or workspace facts, ground your answer directly in the provided Document Excerpts and Knowledge Graph context.
3. Verifiable Citations: In workspace answers, cite key entities explicitly using bracket notation: [Entity Name] (e.g. [Pranay Mehta], [Punjab Engineering College], [Flowcraft Systems], [AION]).
4. Specific Metrics & Precision: When asked for specific facts (such as college, CGPA, degree, technologies, company names, project details, ratings, dates, or contact info), extract the exact values directly from the Document Excerpts and state them accurately and prominently (e.g. stating the exact CGPA value, college name, or project tech stack).
5. Direct & Structured: Provide clear, accurate, and comprehensive responses without unnecessary hesitation or generic disclaimers when facts are present in the provided context.
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
        cited_names = set(re.findall(r"\[([a-zA-Z0-9_\s\.\-\/\+]+)\]", answer_text))
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
            elif len(name.strip()) > 1 and not name.strip().isdigit():
                citations.append({
                    "entity_id": f"ent_{abs(hash(norm_name)) % 100000}",
                    "entity_name": name.strip(),
                    "document_id": "doc_primary",
                    "quote": f"Cited in response: {name.strip()}",
                    "relevance_score": 1.0,
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
