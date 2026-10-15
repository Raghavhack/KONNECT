"""
Community Detection & Summarization Module.
Interfaces with Neo4j Graph Data Science (GDS) library for Leiden community detection,
scoped to local neighborhoods for incremental updates, with local NetworkX modularity fallback.
"""

import logging
import hashlib
from typing import List, Dict, Any, Optional
import networkx as nx

from .neo4j_client import Neo4jClient
from ..extraction.models import Community
from ..extraction.prompts import COMMUNITY_SUMMARY_PROMPT

logger = logging.getLogger(__name__)


class CommunityDetector:
    """
    Manages community detection (Leiden) and LLM-driven hierarchical community summarization.
    Keeps Leiden computation colocated with Neo4j GDS or falls back to local modularity.
    """

    def __init__(self, client: Neo4jClient, llm_client: Any):
        self.client = client
        self.llm = llm_client
        self.communities: Dict[str, Community] = {}

    def detect_communities_incremental(
        self, affected_entity_names: List[str], neighborhood_nodes: List[Dict[str, Any]], neighborhood_edges: List[Dict[str, Any]]
    ) -> List[Community]:
        """
        Executes community detection scoped to the local neighborhood of affected entities.
        """
        if not neighborhood_nodes:
            return []

        # 1. Attempt Neo4j GDS Leiden if available
        if self.client.is_connected:
            try:
                gds_communities = self._run_gds_leiden(affected_entity_names)
                if gds_communities:
                    return gds_communities
            except Exception as e:
                logger.debug(f"GDS Leiden call failed ({e}). Using local neighborhood community detection.")

        # 2. Local neighborhood modularity clustering via NetworkX
        return self._run_local_community_detection(neighborhood_nodes, neighborhood_edges)

    def _run_gds_leiden(self, affected_names: List[str]) -> List[Community]:
        """Runs GDS Leiden algorithm over projected neighborhood graph."""
        cypher_stream = """
        CALL gds.leiden.stream('konnectNeighborhoodGraph')
        YIELD nodeId, communityId
        RETURN gds.util.asNode(nodeId).name AS name, communityId
        """
        records = self.client.execute_query(cypher_stream)
        if not records:
            return []

        clusters: Dict[int, List[str]] = {}
        for r in records:
            cid = r["communityId"]
            clusters.setdefault(cid, []).append(r["name"])

        return self._build_community_objects(clusters)

    def _run_local_community_detection(
        self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]
    ) -> List[Community]:
        """Local modularity/Leiden approximation on the neighborhood graph."""
        G = nx.Graph()
        for n in nodes:
            name = n.get("name")
            if name:
                G.add_node(name)

        for e in edges:
            src = e.get("src")
            tgt = e.get("tgt")
            w = float(e.get("weight", 1.0))
            if src and tgt and src in G and tgt in G:
                G.add_edge(src, tgt, weight=w)

        if len(G.nodes) == 0:
            return []

        try:
            # Louvain community detection (built into networkx)
            communities_gen = nx.community.louvain_communities(G, weight="weight", seed=42)
            clusters = {idx: list(c) for idx, c in enumerate(communities_gen)}
        except Exception:
            # Fallback connected components
            comp = list(nx.connected_components(G))
            clusters = {idx: list(c) for idx, c in enumerate(comp)}

        return self._build_community_objects(clusters)

    def _build_community_objects(self, clusters: Dict[Any, List[str]]) -> List[Community]:
        """Builds and optionally summarizes community objects."""
        results = []
        for cid, members in clusters.items():
            if not members:
                continue
            comm_id = hashlib.sha256(f"comm:{cid}:{','.join(sorted(members))}".encode()).hexdigest()[:16]
            title = f"Community {cid}: {', '.join(members[:3])}"
            summary = f"Cluster containing {len(members)} interconnected entities: {', '.join(members)}."

            comm = Community(
                id=comm_id,
                title=title,
                summary=summary,
                member_entity_names=members,
                level=0,
            )
            results.append(comm)
            self.communities[comm_id] = comm
        return results

    def summarize_community_with_llm(
        self, community: Community, entity_descriptions: Dict[str, str], relationships: List[Dict[str, Any]]
    ) -> Community:
        """Invokes LLM to generate a deep summary for the community."""
        ent_str = "\n".join([f"- {m}: {entity_descriptions.get(m, '')}" for m in community.member_entity_names])
        rel_str = "\n".join([
            f"- {r.get('src')} --[{r.get('type')}]--> {r.get('tgt')}: {r.get('description', '')}"
            for r in relationships
            if r.get("src") in community.member_entity_names and r.get("tgt") in community.member_entity_names
        ])

        prompt = COMMUNITY_SUMMARY_PROMPT.format(
            entities_str=ent_str or "None specified",
            relationships_str=rel_str or "None specified",
        )

        try:
            raw = self.llm.generate(prompt=prompt, temperature=0.0)
            import json
            parsed = json.loads(raw.strip().strip("```json").strip("```"))
            community.title = parsed.get("title", community.title)
            community.summary = parsed.get("summary", community.summary)
        except Exception as e:
            logger.debug(f"LLM community summary error ({e}). Keeping default heuristic summary.")

        return community
