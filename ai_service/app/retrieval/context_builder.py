"""
Context Builder for PCST Subgraph Retrieval.
Formats graph elements into clean, citation-ready context for LLM generation.
"""

from typing import List, Dict, Any


class ContextBuilder:
    """Formats retrieved PCST subgraphs and community summaries into LLM context."""

    @staticmethod
    def build_llm_context(
        subgraph: Dict[str, Any],
        communities: List[Dict[str, Any]] = None,
        chunks: List[Dict[str, Any]] = None,
    ) -> str:
        nodes = subgraph.get("nodes", [])
        edges = subgraph.get("edges", [])
        prizes = subgraph.get("prizes", {})

        context_lines = []

        # 1. Source Document Excerpts (Direct Ground Truth Facts)
        if chunks:
            context_lines.append("### RELEVANT DOCUMENT EXCERPTS (Primary Ground Truth):\n")
            for c in chunks:
                doc_title = c.get("title") or c.get("document_id", "Document")
                text = c.get("text", "").strip()
                if text:
                    context_lines.append(f"Source Document: [{doc_title}]")
                    context_lines.append(f'"""\n{text}\n"""\n')

        context_lines.append("### KNOWLEDGE GRAPH CONTEXT (Retrieved via PCST):\n")

        # Entities
        context_lines.append("#### Key Entities:")
        if nodes:
            for n in nodes:
                name = n.get("name", "Unknown")
                ent_type = n.get("type", "CONCEPT")
                desc = n.get("description", "No description available.")
                prize = prizes.get(name, 0.0)
                context_lines.append(
                    f"- **[{name}]** ({ent_type}) [Relevance: {prize:.2f}]: {desc}"
                )
        else:
            context_lines.append("No specific entities identified.")

        context_lines.append("")

        # Relationships
        context_lines.append("#### Entity Relationships:")
        if edges:
            for e in edges:
                src = e.get("src", "")
                tgt = e.get("tgt", "")
                rel_type = e.get("type", "RELATES_TO")
                desc = e.get("description", "")
                w = e.get("weight", 1.0)
                detail = f" — {desc}" if desc else ""
                context_lines.append(
                    f"- [{src}] ==[{rel_type} (weight: {w:.1f})]==> [{tgt}]{detail}"
                )
        else:
            context_lines.append("No direct relationships connecting retrieved entities.")

        # Communities
        if communities:
            context_lines.append("\n#### Surrounding Community Syntheses:")
            for c in communities:
                title = c.get("title", "Community")
                summary = c.get("summary", "")
                context_lines.append(f"- **{title}**: {summary}")

        return "\n".join(context_lines)
