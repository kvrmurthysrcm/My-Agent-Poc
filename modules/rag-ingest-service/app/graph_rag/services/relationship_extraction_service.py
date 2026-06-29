import json

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
        data = self.llm.generate_json(prompt, root_key="relationships")
        relationships = data.get("relationships", [])
        if not isinstance(relationships, list):
            raise ValueError("Mistral relationship response must contain a relationships list")
        return [
            ExtractedRelationship.model_validate(item)
            for item in relationships
            if isinstance(item, dict) and item.get("source_entity") and item.get("target_entity")
        ]

    def extract_batch(self, chunks: list[dict]) -> dict[str, list[ExtractedRelationship]]:
        if not chunks:
            return {}
        if len(chunks) == 1:
            chunk = chunks[0]
            return {chunk["chunk_id"]: self.extract(chunk["chunk_text"], chunk["entities"])}

        chunk_payload = []
        for chunk in chunks:
            entities = chunk["entities"]
            chunk_payload.append(
                {
                    "chunk_id": chunk["chunk_id"],
                    "chunk_index": chunk.get("chunk_index"),
                    "entities": [{"name": entity.name, "entity_type": entity.entity_type} for entity in entities],
                    "text": chunk["chunk_text"],
                }
            )
        prompt = f"""
Extract knowledge graph relationships from each chunk below.

Rules:
- Use only facts explicitly present in each chunk.
- Only create relationships between the entities listed for that same chunk.
- Return strict JSON only.
- Do not include markdown.
- Keep each chunk's output under that same chunk_id.
- Use concise relationship types such as AUTHORED, FOUNDED, LOCATED_IN, PART_OF, MENTIONS, RELATED_TO.

JSON schema:
{{
  "chunks": [
    {{
      "chunk_id": "same chunk_id from input",
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
  ]
}}

Chunks:
{json.dumps(chunk_payload, ensure_ascii=False)}
"""
        chunks_with_entities = [chunk for chunk in chunks if chunk["entities"]]
        if not chunks_with_entities:
            return {chunk["chunk_id"]: [] for chunk in chunks}
        data = self.llm.generate_json(prompt, root_key="chunks")
        rows = data.get("chunks", [])
        if not isinstance(rows, list):
            raise ValueError("Mistral batched relationship response must contain a chunks list")
        by_chunk_id = {chunk["chunk_id"]: [] for chunk in chunks}
        for row in rows:
            if not isinstance(row, dict):
                continue
            chunk_id = str(row.get("chunk_id") or "")
            if chunk_id not in by_chunk_id:
                continue
            relationships = row.get("relationships", [])
            if not isinstance(relationships, list):
                continue
            by_chunk_id[chunk_id] = [
                ExtractedRelationship.model_validate(item)
                for item in relationships
                if isinstance(item, dict) and item.get("source_entity") and item.get("target_entity")
            ]
        return by_chunk_id
