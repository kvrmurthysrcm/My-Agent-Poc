from app.graph_rag.schemas import ExtractedEntity, ExtractedRelationship
from app.graph_rag.services.ollama_generation_client import OllamaGenerationClient


class RelationshipExtractionService:
    def __init__(self, llm: OllamaGenerationClient):
        self.llm = llm

    def extract(self, chunk_text: str, entities: list[ExtractedEntity]) -> list[ExtractedRelationship]:
        entity_lines = "\n".join(f"- {entity.name} ({entity.entity_type})" for entity in entities)
        prompt = f"""
Extract knowledge graph relationships from the chunk below.

Rules:
- Use only facts explicitly present in the chunk.
- Only create relationships between the provided entities.
- Return strict JSON only.
- Do not include markdown.
- Use concise relationship types such as AUTHORED, FOUNDED, LOCATED_IN, PART_OF, MENTIONS, RELATED_TO.

Entities:
{entity_lines}

JSON schema:
{{
  "relationships": [
    {{
      "source_entity": "source entity display name",
      "target_entity": "target entity display name",
      "relationship_type": "RELATED_TO",
      "description": "short grounded relationship description",
      "confidence_score": 0.0
    }}
  ]
}}

Chunk:
\"\"\"{chunk_text}\"\"\"
"""
        if not entities:
            return []
        data = self.llm.generate_json(prompt)
        relationships = data.get("relationships", [])
        if not isinstance(relationships, list):
            raise ValueError("Mistral relationship response must contain a relationships list")
        return [
            ExtractedRelationship.model_validate(item)
            for item in relationships
            if isinstance(item, dict) and item.get("source_entity") and item.get("target_entity")
        ]
