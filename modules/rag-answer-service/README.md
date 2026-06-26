# RAG Answer Service

FastAPI service that turns retrieval results from `rag-search-service` into grounded LLM answers.

## Endpoints

- `GET /` or `GET /ui/answer`
- `GET /health`
- `GET /ready`
- `POST /rag/answer`

## Run Locally

```powershell
cd modules\rag-answer-service
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --port 8002
```

The service expects `rag-search-service` to be running:

```text
RAG_SEARCH_BASE_URL=http://127.0.0.1:8001
ANSWER_DEFAULT_TOP_K=10
ANSWER_CONTEXT_TOP_K=10
ANSWER_MAX_CONTEXT_CHARS=12000
ANSWER_MAX_CHARS_PER_SOURCE=1800
```

Open the UI:

```text
http://localhost:8002/ui/answer
```

## LLM Configuration

Default local Ollama configuration:

```text
LLM_PROVIDER=ollama
LLM_MODEL=mistral:latest
OLLAMA_BASE_URL=http://127.0.0.1:11434
LLM_TEMPERATURE=0.1
LLM_TIMEOUT_SECONDS=180
```

OpenAI configuration:

```text
LLM_PROVIDER=openai
OPENAI_MODEL=gpt-4.1-mini
OPENAI_API_KEY=<your key>
```

## Answer Flow

1. `POST /rag/answer` receives a user question.
2. The service calls `rag-search-service` with `include_chunk_text=true`.
3. Top retrieved chunks are formatted as grounded, query-focused context. Directly relevant excerpts are placed earlier in the prompt while retaining original source rank labels.
4. The configured LLM receives the question and context.
5. The answer and source snippets are returned.

The LLM is instructed to use only retrieved context. If retrieval returns no context, the service returns a no-context answer instead of guessing.

## Example

```powershell
curl.exe -X POST http://localhost:8002/rag/answer `
  -H "Content-Type: application/json" `
  -d "{\"query\":\"what was the impression perceived by Paul Brenton when he met Ramana Maharshi?\",\"search_mode\":\"hybrid\",\"top_k\":10,\"context_top_k\":10}"
```

## Tests

```powershell
cd modules\rag-answer-service
pytest
```
