# RAG Answer Service

FastAPI service that turns retrieval results from `rag-search-service` into grounded LLM answers.

## Endpoints

- `GET /` or `GET /ui/answer`
- `GET /health`
- `GET /ready`
- `POST /rag/answer`
- `POST /rag/answer/compare`
- `POST /rag/answer/compare/stream`

## Run Locally

```powershell
cd modules\rag-answer-service
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --port 8002
```

Find the process ID listening on the answer port when you need to stop or inspect it:

```powershell
Get-NetTCPConnection -LocalPort 8002 -State Listen -ErrorAction SilentlyContinue | Select-Object `
  -ExpandProperty OwningProcess -Unique
```

The service expects `rag-search-service` to be running:

```text
RAG_SEARCH_BASE_URL=http://127.0.0.1:8001
ANSWER_DEFAULT_TOP_K=10
ANSWER_CONTEXT_TOP_K=10
ANSWER_MAX_CONTEXT_CHARS=12000
ANSWER_MAX_CHARS_PER_SOURCE=1800
ANSWER_COMPARE_MODELS=mistral:latest,gemma4,llama3:8b,gemma:7b,gemini:gemini-2.5-flash
ANSWER_SYSTEM_INSTRUCTION=You are a grounded RAG answer assistant...
ANSWER_SYNTHESIS_INSTRUCTION=Answer the question by combining all relevant facts...
ANSWER_GUARDRAIL_INSTRUCTION=Safety and quality guardrails...
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

### Ollama dependency checks

When `LLM_PROVIDER=ollama`, the service checks `OLLAMA_BASE_URL/api/tags` during startup and logs either a passing check or an actionable error with the required `ollama pull` command. A failed check does not stop the API process, but `/ready` and answer requests return `503` with an `ollama_unavailable` or `ollama_model_unavailable` message until the dependency is fixed.

OpenAI configuration:

```text
LLM_PROVIDER=openai
OPENAI_MODEL=gpt-4.1-mini
OPENAI_API_KEY=<your key>
```

Gemini API configuration:

```text
LLM_PROVIDER=gemini
GEMINI_MODEL=gemini-2.5-flash
GEMINI_API_KEY=<your key>
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta
```

`gemini-2.5-flash` is the default Gemini option because it is the practical free-tier-friendly model for Google AI Studio/Gemini API testing. Keep the key in PyCharm run configuration environment variables or another local secret store when possible; `.env.example` intentionally leaves it blank.

## Answer Flow

1. `POST /rag/answer` receives a user question.
2. The service calls `rag-search-service` with `include_chunk_text=true`.
3. Top retrieved chunks are formatted as grounded, query-focused context. Directly relevant excerpts are placed earlier in the prompt while retaining original source rank labels.
4. The configured LLM receives the question and context.
5. The answer and source snippets are returned.

The LLM is instructed to use only retrieved context. If retrieval returns no context, the service returns a no-context answer instead of guessing.

## Compare Local LLMs

The answer UI can compare multiple Ollama models for the same question. The service calls `rag-search-service` once, packs one shared context, then asks each configured model to answer from that same context. This makes the outputs easier to compare because search results and selected chunks are held constant.

Models are called sequentially, not in parallel. This avoids overloading local Ollama CPU/RAM and keeps timing comparisons more realistic. The UI uses the streaming endpoint so each model card appears as soon as that model finishes, while the next model continues running.

Default comparison models:

```text
ANSWER_COMPARE_MODELS=mistral:latest,gemma4,llama3:8b,gemma:7b,gemini:gemini-2.5-flash
```

The UI lets you override this list with comma-separated model names. Plain names use the configured `LLM_PROVIDER`. To compare a model from another provider, prefix it with the provider name:

```text
gemini:gemini-2.5-flash
openai:gpt-4.1-mini
ollama:mistral:latest
```

The API also accepts `compare_models`:

```powershell
curl.exe -X POST http://localhost:8002/rag/answer/compare `
  -H "Content-Type: application/json" `
  -d "{\"query\":\"what did Scrooge learn?\",\"search_mode\":\"hybrid\",\"top_k\":10,\"context_top_k\":8,\"compare_models\":[\"mistral:latest\",\"gemma4\",\"llama3:8b\",\"gemini:gemini-2.5-flash\"]}"
```

If one model fails or is not installed locally, the response includes a failed result for that model while returning the other model outputs.

For incremental UI-style consumption, use:

```text
POST /rag/answer/compare/stream
```

The stream uses Server-Sent Events (`text/event-stream`). Events are emitted in this order:

```text
search_complete
model_started
model_result
model_started
model_result
...
complete
```

## Prompt Tuning

The service keeps the stable prompt structure in code because the citation verifier depends on predictable source-rank and chunk citations. The main prompt behavior is configurable from `.env`:

```text
ANSWER_SYSTEM_INSTRUCTION=You are a grounded RAG answer assistant...
ANSWER_SYNTHESIS_INSTRUCTION=Answer the question by combining all relevant facts...
```

Use these settings to tune answer style and synthesis behavior. Keep these constraints in any custom prompt:

- use only retrieved context
- read all context blocks before answering
- synthesize relevant facts across multiple source ranks
- cite every factual sentence using source rank and chunk
- answer supported facts even when another part of the question is missing
- return exactly `insufficient_context` only when no retrieved context supports the question at all

The prompt intentionally asks models not to insert `[insufficient_context]` inside a partial answer. For partial support, the model should cite the supported facts and then say which requested detail was not found in the context.

The service also applies verifier-side guardrails after generation. This is intentional because local models may ignore parts of the prompt. The verifier rejects answers when:

- the answer has no source-rank citation
- the answer cites a source rank or chunk that was not selected
- the answer uses inference language such as `can be inferred`, `might have`, or `not directly mentioned`
- capitalized named anchors from the question, such as a person or place name, are missing from the selected context

For example, if the question asks about `Paul Brenton` and `Ramana Maharshi`, but the retrieved context only contains unrelated Upanishad or Ramayan chunks, the answer is replaced with `insufficient_context` even if the model writes a plausible answer.

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
