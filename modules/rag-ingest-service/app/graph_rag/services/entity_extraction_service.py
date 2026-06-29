import json

from app.graph_rag.schemas import ExtractedEntity
from app.graph_rag.services.ollama_generation_client import OllamaGenerationClient


class EntityExtractionService:
    def __init__(self, llm: OllamaGenerationClient):
        self.llm = llm

    def extract(self, chunk_text: str) -> list[ExtractedEntity]:
        prompt = f"""
Extract knowledge graph entities from the chunk below.

Rules:
- Use only facts explicitly present in the chunk.
- Return strict JSON only.
- Do not include markdown.
- Prefer reusable entity types such as PERSON, ORGANIZATION, LOCATION, EVENT, WORK, CONCEPT, DATE, OTHER.
- Keep descriptions brief and grounded in the chunk.

JSON schema:
{{
  "entities": [
    {{
      "name": "entity display name",
      "entity_type": "PERSON",
      "description": "short grounded description",
      "confidence_score": 0.0
    }}
  ]
}}

Chunk:
\"\"\"{chunk_text}\"\"\"
"""
        data = self.llm.generate_json(prompt, root_key="entities")
        entities = data.get("entities", [])
        if not isinstance(entities, list):
            raise ValueError("Mistral entity response must contain an entities list")
        return [ExtractedEntity.model_validate(item) for item in entities if isinstance(item, dict) and item.get("name")]

    def extract_batch(self, chunks: list[dict[str, str]]) -> dict[str, list[ExtractedEntity]]:
        if not chunks:
            return {}
        if len(chunks) == 1:
            chunk = chunks[0]
            return {chunk["chunk_id"]: self.extract(chunk["chunk_text"])}

        chunk_payload = [
            {
                "chunk_id": chunk["chunk_id"],
                "chunk_index": chunk.get("chunk_index"),
                "text": chunk["chunk_text"],
            }
            for chunk in chunks
        ]
        prompt = f"""
Extract knowledge graph entities from each chunk below.

Rules:
- Use only facts explicitly present in each chunk.
- Return strict JSON only.
- Do not include markdown.
- Keep each chunk's output under that same chunk_id.
- Prefer reusable entity types such as PERSON, ORGANIZATION, LOCATION, EVENT, WORK, CONCEPT, DATE, OTHER.
- Keep descriptions brief and grounded in the chunk.

JSON schema:
{{
  "chunks": [
    {{
      "chunk_id": "same chunk_id from input",
      "entities": [
        {{
          "name": "entity display name",
          "entity_type": "PERSON",
          "description": "short grounded description",
          "confidence_score": 0.0
        }}
      ]
    }}
  ]
}}

Chunks:
{json.dumps(chunk_payload, ensure_ascii=False)}
"""
        data = self.llm.generate_json(prompt, root_key="chunks")
        rows = data.get("chunks", [])
        if not isinstance(rows, list):
            raise ValueError("Mistral batched entity response must contain a chunks list")
        by_chunk_id = {chunk["chunk_id"]: [] for chunk in chunks}
        for row in rows:
            if not isinstance(row, dict):
                continue
            chunk_id = str(row.get("chunk_id") or "")
            if chunk_id not in by_chunk_id:
                continue
            entities = row.get("entities", [])
            if not isinstance(entities, list):
                continue
            by_chunk_id[chunk_id] = [
                ExtractedEntity.model_validate(item)
                for item in entities
                if isinstance(item, dict) and item.get("name")
            ]
        return by_chunk_id
