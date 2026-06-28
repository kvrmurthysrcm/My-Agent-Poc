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
        data = self.llm.generate_json(prompt)
        entities = data.get("entities", [])
        if not isinstance(entities, list):
            raise ValueError("Mistral entity response must contain an entities list")
        return [ExtractedEntity.model_validate(item) for item in entities if isinstance(item, dict) and item.get("name")]
