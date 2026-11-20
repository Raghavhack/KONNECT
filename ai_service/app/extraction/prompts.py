"""
Prompts for GraphRAG Entity & Relationship Extraction and Community Summarization.
"""

GRAPHRAG_EXTRACTION_SYSTEM_PROMPT = """Extract the top 5-8 salient entities and key relationships from the text as compact JSON.
Output ONLY raw JSON (no markdown formatting, no commentary):
{
  "entities": [
    {"name": "Entity Name", "type": "PERSON | ORG | TECH | CONCEPT | LOCATION"}
  ],
  "relationships": [
    {"source": "Entity1", "target": "Entity2", "relation_type": "RELATES_TO | MEMBER_OF | USES | CREATED"}
  ]
}
Rules:
1. Extract canonical entity names (e.g. "Pranay Mehta", "Flowcraft Systems", "AION").
2. No descriptions needed in JSON. Keep output under 150 tokens."""

ENTITY_DISAMBIGUATION_PROMPT = """You are an entity resolution expert.
Given a newly extracted entity and a list of existing candidate entities from our knowledge graph,
determine whether the new entity matches an existing one (as an alias, typo, or abbreviation) or is distinct.

New Entity:
Name: {new_name}
Type: {new_type}
Description: {new_description}

Existing Candidates:
{candidate_list}

Respond with a JSON object:
{{
  "match_found": true/false,
  "canonical_name": "Selected Canonical Name if match_found else {new_name}",
  "reasoning": "Brief explanation"
}}
"""

COMMUNITY_SUMMARY_PROMPT = """You are an expert knowledge graph analyst.
Given the following cluster of connected entities and their relationships, write a concise, informative community summary and descriptive title.

Entities:
{entities_str}

Relationships:
{relationships_str}

Respond with a JSON object:
{{
  "title": "Short descriptive title for this cluster",
  "summary": "Detailed synthesis explaining the key themes, connections, and significance of this community."
}}
"""
