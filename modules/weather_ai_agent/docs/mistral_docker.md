# Running Mistral Locally With Docker

This guide explains how to run `mistral:latest` locally in Docker using Ollama, test the HTTP API, and monitor concurrent requests from a laptop.

## Use Case

This setup is useful for:

- Testing how Mistral responds before deploying to Kubernetes.
- Checking prompt quality and response format.
- Observing local CPU, memory, and latency behavior.
- Testing concurrent requests at small scale.
- Validating this project's Ollama configuration.

This setup is not a reliable predictor of production Kubernetes throughput unless the laptop hardware is similar to the production nodes.

## Start Ollama In Docker

Create a persistent Docker volume:

```powershell
docker volume create ollama
```

Run the Ollama container:

```powershell
docker run -d `
  --name ollama `
  -p 11434:11434 `
  -v ollama:/root/.ollama `
  ollama/ollama:latest
```

The service will be available at:

```text
http://127.0.0.1:11434
```

## Pull Mistral

```powershell
docker exec -it ollama ollama pull mistral:latest
```

Confirm installed models:

```powershell
docker exec -it ollama ollama list
```

## Test One Request

```powershell
Invoke-RestMethod http://127.0.0.1:11434/api/generate `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"model":"mistral:latest","prompt":"Say OK only.","stream":false}'
```

Expected behavior:

- The first request can be slow because the model must load into memory.
- Later requests are faster while the model remains loaded.
- If memory is tight, latency can rise sharply.

## Configure This Weather Agent

Set these values in:

```text
modules/weather_ai_agent/.env
```

```env
LLM_PROVIDER=ollama
OLLAMA_MODEL=mistral:latest
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

Then run the CLI:

```powershell
.\.venv\Scripts\python.exe -m modules.weather_ai_agent.cli --city Atlanta --state GA --country US
```

Or run the browser/API app:

```powershell
.\.venv\Scripts\python.exe -m uvicorn modules.weather_ai_agent.api:app --reload --port 8002
```

Open:

```text
http://127.0.0.1:8002
```

## Monitor The Container

Use Docker stats:

```powershell
docker stats ollama
```

Watch logs:

```powershell
docker logs -f ollama
```

Useful things to watch:

- CPU usage.
- Memory usage.
- Whether the container restarts.
- Request latency.
- Whether requests queue during concurrency tests.

## Test Concurrent Requests

Use a local load tool such as `hey` or `k6`.

Example with `hey`:

```powershell
hey -n 100 -c 10 -m POST `
  -H "Content-Type: application/json" `
  -d "{\"model\":\"mistral:latest\",\"prompt\":\"Summarize today's weather in one sentence.\",\"stream\":false}" `
  http://127.0.0.1:11434/api/generate
```

Meaning:

- `-n 100`: send 100 total requests.
- `-c 10`: run 10 requests concurrently.

Start small:

```powershell
hey -n 20 -c 2 -m POST `
  -H "Content-Type: application/json" `
  -d "{\"model\":\"mistral:latest\",\"prompt\":\"Say OK only.\",\"stream\":false}" `
  http://127.0.0.1:11434/api/generate
```

Then increase gradually:

```text
c=2 -> c=5 -> c=10 -> c=20
```

On a laptop, high concurrency usually causes queueing and slower responses. That is expected.

## Tune Ollama For Local Testing

Stop and remove the existing container:

```powershell
docker rm -f ollama
```

Run with explicit concurrency and context settings:

```powershell
docker run -d `
  --name ollama `
  -p 11434:11434 `
  -v ollama:/root/.ollama `
  -e OLLAMA_NUM_PARALLEL=2 `
  -e OLLAMA_MAX_QUEUE=64 `
  -e OLLAMA_CONTEXT_LENGTH=4096 `
  -e OLLAMA_KEEP_ALIVE=30m `
  ollama/ollama:latest
```

Setting notes:

- `OLLAMA_NUM_PARALLEL=2` allows more than one request to run in parallel for a loaded model.
- `OLLAMA_MAX_QUEUE=64` limits how many requests can wait.
- `OLLAMA_CONTEXT_LENGTH=4096` caps the default context length.
- `OLLAMA_KEEP_ALIVE=30m` keeps the model loaded for 30 minutes after use.

Higher parallelism uses more memory. Increase it only after watching `docker stats`.

## Test With Larger Prompts

Small prompts do not show the real memory and latency behavior of business requests.

For a better test:

- Try normal prompts near 1,000 tokens.
- Try worst-case prompts near 5,000 tokens.
- Keep output length realistic.
- Measure p95 and p99 latency, not only average latency.

## Practical Conclusion

Docker plus Ollama is a good local way to understand Mistral behavior, request latency, and memory pressure.

For laptop testing:

- Use Ollama.
- Start with low concurrency.
- Watch `docker stats`.
- Expect queueing at higher concurrency.

For production Kubernetes:

- Do not extrapolate laptop results directly.
- Use GPU-backed serving when latency and concurrency matter.
- Prefer a separate model-serving tier, such as vLLM, for high-throughput workloads.
