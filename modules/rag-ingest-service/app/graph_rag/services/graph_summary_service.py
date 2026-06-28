import json

from app.graph_rag.services.ollama_generation_client import OllamaGenerationClient


class GraphSummaryService:
    def __init__(self, llm: OllamaGenerationClient):
        self.llm = llm

    def summarize_resource(self, facts: dict) -> str:
        compact = json.dumps(facts, ensure_ascii=False)[:12000]
        prompt = f"""
Summarize this compact knowledge graph for Graph RAG retrieval.

Rules:
- Return strict JSON only.
- Do not include markdown.
- Mention key entities, relationship patterns, and important clusters.
- Keep the summary under 300 words.

JSON schema:
{{"summary": "resource graph summary"}}

Graph facts:
{compact}
"""
        data = self.llm.generate_json(prompt)
        summary = data.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            raise ValueError("Mistral graph summary response must contain summary")
        return summary.strip()
