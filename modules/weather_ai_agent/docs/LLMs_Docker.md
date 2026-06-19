# Local LLMs With Docker

This document lists efficient local LLMs that can be tested with Docker, explains the difference between models and runtimes, and gives practical recommendations for this weather-agent project.

## Key Distinction

Ollama is not an LLM.

Ollama is a local runtime and HTTP server for downloading, managing, and running LLMs. The model is something like:

- `mistral:latest`
- `llama3.2:3b`
- `qwen3:4b`
- `gemma3:4b`

The same model family may also run through other runtimes, but the exact model name and file format can differ.

## Good Local Models To Try

| Model | Why Try It | Laptop Fit |
| --- | --- | --- |
| `mistral:latest` | Solid 7B general-purpose baseline. | Good |
| `llama3.2:3b` | Small, fast, low memory. Good for simple summaries. | Very good |
| `qwen3:4b` or `qwen3:8b` | Strong newer general/reasoning family. | Good |
| `gemma3:4b` or `gemma3:12b` | Efficient, capable, good general model. | 4B good, 12B needs more RAM/VRAM |
| `gemma4:e4b` or another small Gemma 4 variant | Newer Gemma line; good candidate if available locally. | Good |
| `phi4-mini` | Small, efficient, reasoning/math oriented. | Good |
| `mistral-nemo:12b` | Better long-context Mistral-family option than old 7B Mistral. | Heavier |
| `mistral-small` or `mistral-small3.2` | Stronger than 7B Mistral, but much heavier. | Usually not laptop-friendly unless the machine has strong GPU/RAM |

For this weather-agent use case, the model does not need deep reasoning. It mainly needs concise factual summarization. A smaller model may be better because it is faster, cheaper to run, and easier to scale.

## Recommended Test Order

Start with small models and move upward only if answer quality is not good enough.

```powershell
docker exec -it ollama ollama pull llama3.2:3b
docker exec -it ollama ollama pull qwen3:4b
docker exec -it ollama ollama pull gemma3:4b
docker exec -it ollama ollama pull mistral:latest
```

Then configure this project with one model at a time:

```env
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.2:3b
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

Run:

```powershell
.\.venv\Scripts\python.exe -m modules.weather_ai_agent.cli --city Atlanta --state GA --country US
```

Change `OLLAMA_MODEL` and repeat the same prompt so latency and answer quality can be compared fairly.

## Runtime Options

| Runtime | Use When |
| --- | --- |
| Ollama | Best default for local testing. Easy model pull, run, and API access. |
| llama.cpp server | Best for low-level control, GGUF quantized models, and CPU-focused testing. |
| vLLM | Better for production Linux/GPU serving, high throughput, batching, and OpenAI-compatible APIs. |
| Hugging Face TGI | Production-style Hugging Face serving, usually GPU oriented. |
| SGLang | High-performance serving for more advanced inference workloads. |

## Local Docker Recommendation

For laptop testing:

1. Use Docker plus Ollama.
2. Test small models first.
3. Watch CPU, memory, and latency.
4. Compare answer quality with the same weather prompt.
5. Increase model size only when needed.

Useful monitoring command:

```powershell
docker stats ollama
```

Useful logs command:

```powershell
docker logs -f ollama
```

## Production Recommendation

For Kubernetes production, do not assume Ollama is the best serving layer if high concurrency matters.

Recommended direction:

- Keep Ollama for laptop and POC testing.
- Use vLLM or Hugging Face TGI for GPU-backed production serving.
- Use OpenAI-compatible APIs where possible so the application is not tightly coupled to one runtime.
- Keep model serving separate from the weather application pods.

## Practical Bottom Line

For this project:

- Start local testing with `llama3.2:3b`, `qwen3:4b`, `gemma3:4b`, and `mistral:latest`.
- Prefer the smallest model that gives acceptable summaries.
- Use Ollama locally because it is simple and productive.
- Use vLLM or TGI in production when throughput and concurrency matter.

## References

- Ollama model library: https://ollama.com/library
- vLLM supported models: https://docs.vllm.ai/en/latest/models/supported_models/
- llama.cpp: https://github.com/ggml-org/llama.cpp
- Hugging Face Text Generation Inference: https://huggingface.co/docs/text-generation-inference/index
