"""
Prompts for GraphRAG Entity & Relationship Extraction and Community Summarization.
"""

GRAPHRAG_EXTRACTION_SYSTEM_PROMPT = """You are an expert knowledge graph extraction agent.
Your task is to analyze the input text chunk and extract all salient entities and relationships connecting them.

Output ONLY a valid JSON object with two arrays: "entities" and "relationships".

Format:
{
  "entities": [
    {
      "name": "Entity Name (canonical and concise)",
      "type": "ORGANIZATION | PERSON | LOCATION | EVENT | CONCEPT | TECHNOLOGY | DOCUMENT",
      "description": "Comprehensive explanation of what this entity is in the context of the text.",
      "importance_score": 1.0 (float between 0.1 and 1.0)
    }
  ],
  "relationships": [
    {
      "source": "Exact Name of Source Entity",
      "target": "Exact Name of Target Entity",
      "relation_type": "HIERARCHICAL | INTERACTION | CAUSAL | DEPENDENCY | AFFILIATION | SIMILAR_TO",
      "description": "Specific explanation of how source and target interact or relate.",
      "weight": 1.0 (float between 0.1 and 1.0)
    }
  ]
}

Guidelines:
1. Prefer specific entity names over general terms.
2. Every relationship must connect two entities present in the entities list or clearly identifiable.
3. Ensure descriptions are grounded strictly in the provided text.
4. Do not include markdown formatting or commentary, only raw JSON.
"""

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
