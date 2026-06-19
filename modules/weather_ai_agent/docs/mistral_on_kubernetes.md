# Running `mistral:latest` On Kubernetes

This document explains how to run a local/open-weight LLM such as `mistral:latest` on a Kubernetes pod, whether Ollama is required, what alternatives exist on Linux, and what to watch for around memory, concurrency, and default model behavior.

## Short Answer

You do not strictly need Ollama in a Linux Kubernetes pod.

Ollama is useful when you want:

- Simple local development.
- Easy model pulling and model lifecycle.
- A small HTTP API with minimal setup.
- Compatibility with the same flow used on a Windows laptop.

For production-style Linux/Kubernetes serving, better options often are:

- `vLLM`: best general choice for GPU-backed HTTP serving, high throughput, OpenAI-compatible APIs, batching, and memory-efficient KV cache handling.
- Hugging Face Text Generation Inference, also called TGI: good production server for Hugging Face models.
- `llama.cpp` or `llama-server`: good CPU or small-GPU option, especially with GGUF quantized models.
- Ollama: still fine for simple internal services, POCs, CPU serving, and low-traffic workloads.

For this project, if the existing code talks to Ollama today, the least disruptive Kubernetes path is to run Ollama as a service and set:

```env
LLM_PROVIDER=ollama
OLLAMA_MODEL=mistral:latest
OLLAMA_BASE_URL=http://ollama.default.svc.cluster.local:11434
```

If you want a more production-oriented serving layer, expose vLLM with an OpenAI-compatible endpoint and change the application config to call that endpoint instead.

## Do LLMs Use A Standard Pod Protocol?

No. Kubernetes only runs containers. It does not define an LLM protocol.

The serving container decides what API it exposes. Common patterns are:

| Server | Common API shape | Notes |
| --- | --- | --- |
| Ollama | `/api/generate`, `/api/chat`, plus OpenAI-compatible endpoints | Simple local/server workflow. |
| vLLM | OpenAI-compatible HTTP API | Common for production inference serving. |
| TGI | Hugging Face generation API, OpenAI-compatible modes depending on version/config | Strong Hugging Face ecosystem fit. |
| llama.cpp server | HTTP completion/chat endpoints, OpenAI-compatible modes depending on build/version | Good for GGUF and CPU-friendly deployments. |

The model itself is not the API. `mistral:latest` is model weights plus tokenizer/config metadata. The runtime server loads those weights and exposes an HTTP contract.

## What Is `mistral:latest` In Ollama?

In Ollama, `mistral:latest` is an Ollama model tag. It usually points to a packaged Mistral 7B-style model variant in Ollama's model library.

Important distinction:

- `mistral:latest` is an Ollama model name.
- vLLM usually expects a Hugging Face model ID, for example `mistralai/Mistral-7B-Instruct-v0.3`.
- llama.cpp usually expects a local GGUF file.

So you cannot always copy the exact same model string between runtimes. The model family may be the same, but the runtime-specific model identifier can differ.

## Mistral Default Behavior

Mistral 7B is a decoder-only transformer LLM designed for text generation. Mistral's original 7B model introduced grouped-query attention and sliding-window attention to improve inference efficiency for its size.

Practical behavior to expect:

- It predicts the next token autoregressively.
- It has no built-in live data access unless you connect tools or retrieval.
- It does not remember previous API calls unless your application sends the conversation history again.
- If you run a base model, it may not follow chat instructions well.
- If you run an instruct/chat-tuned model, it is better for assistant-style prompts.
- Output changes with sampling parameters such as `temperature`, `top_p`, `top_k`, stop tokens, and max output tokens.
- Longer prompts and longer outputs consume more memory through the KV cache.

For this weather agent, the safest behavior is to keep doing what the code already does:

1. Fetch live weather through deterministic code.
2. Send only those facts to the LLM.
3. Ask the LLM to summarize, not invent weather.

## Option 1: Run Ollama In Kubernetes

Use this when you want the simplest path from the current local setup.

### Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ollama
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ollama
  template:
    metadata:
      labels:
        app: ollama
    spec:
      containers:
        - name: ollama
          image: ollama/ollama:latest
          ports:
            - containerPort: 11434
          env:
            - name: OLLAMA_HOST
              value: "0.0.0.0:11434"
            - name: OLLAMA_KEEP_ALIVE
              value: "30m"
            - name: OLLAMA_NUM_PARALLEL
              value: "1"
            - name: OLLAMA_MAX_LOADED_MODELS
              value: "1"
            - name: OLLAMA_MAX_QUEUE
              value: "64"
          resources:
            requests:
              cpu: "2"
              memory: "10Gi"
            limits:
              cpu: "4"
              memory: "16Gi"
          volumeMounts:
            - name: ollama-models
              mountPath: /root/.ollama
      volumes:
        - name: ollama-models
          persistentVolumeClaim:
            claimName: ollama-models
```

### Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: ollama
spec:
  selector:
    app: ollama
  ports:
    - name: http
      port: 11434
      targetPort: 11434
```

### Persistent Volume Claim

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: ollama-models
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 30Gi
```

### Load The Model

After the pod starts:

```bash
kubectl exec deploy/ollama -- ollama pull mistral:latest
kubectl exec deploy/ollama -- ollama run mistral:latest ""
```

The empty run warms the model into memory.

### Test The Service

```bash
kubectl run curl-test --rm -it --image=curlimages/curl -- \
  curl http://ollama:11434/api/generate \
    -d '{"model":"mistral:latest","prompt":"Say OK only.","stream":false}'
```

### Configure This Weather Agent

```env
LLM_PROVIDER=ollama
OLLAMA_MODEL=mistral:latest
OLLAMA_BASE_URL=http://ollama:11434
```

## Option 1B: Ollama With NVIDIA GPU

This requires the NVIDIA device plugin installed in the Kubernetes cluster. Kubernetes exposes GPUs as extended resources such as `nvidia.com/gpu`.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ollama-gpu
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ollama-gpu
  template:
    metadata:
      labels:
        app: ollama-gpu
    spec:
      containers:
        - name: ollama
          image: ollama/ollama:latest
          ports:
            - containerPort: 11434
          env:
            - name: OLLAMA_HOST
              value: "0.0.0.0:11434"
            - name: OLLAMA_KEEP_ALIVE
              value: "30m"
            - name: OLLAMA_NUM_PARALLEL
              value: "1"
            - name: OLLAMA_FLASH_ATTENTION
              value: "1"
          resources:
            requests:
              cpu: "2"
              memory: "8Gi"
              nvidia.com/gpu: "1"
            limits:
              cpu: "4"
              memory: "16Gi"
              nvidia.com/gpu: "1"
          volumeMounts:
            - name: ollama-models
              mountPath: /root/.ollama
      volumes:
        - name: ollama-models
          persistentVolumeClaim:
            claimName: ollama-models
```

GPU requests are not like CPU millicores. You normally request whole GPUs, and the GPU must be available on the target node through a device plugin.

## Option 2: Run Mistral With vLLM

Use vLLM when you want better throughput and production-style serving on Linux GPUs.

vLLM exposes an OpenAI-compatible HTTP server. That means your application can call endpoints similar to `/v1/chat/completions` instead of Ollama's `/api/chat`.

### Deployment

This example uses a Hugging Face model ID. Replace it with the exact Mistral model you want to serve.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mistral-vllm
spec:
  replicas: 1
  selector:
    matchLabels:
      app: mistral-vllm
  template:
    metadata:
      labels:
        app: mistral-vllm
    spec:
      containers:
        - name: vllm
          image: vllm/vllm-openai:latest
          args:
            - "--model"
            - "mistralai/Mistral-7B-Instruct-v0.3"
            - "--served-model-name"
            - "mistral"
            - "--host"
            - "0.0.0.0"
            - "--port"
            - "8000"
            - "--max-model-len"
            - "4096"
            - "--gpu-memory-utilization"
            - "0.85"
          ports:
            - containerPort: 8000
          env:
            - name: HF_HOME
              value: /models/huggingface
          resources:
            requests:
              cpu: "4"
              memory: "16Gi"
              nvidia.com/gpu: "1"
            limits:
              cpu: "8"
              memory: "32Gi"
              nvidia.com/gpu: "1"
          volumeMounts:
            - name: hf-cache
              mountPath: /models/huggingface
      volumes:
        - name: hf-cache
          persistentVolumeClaim:
            claimName: hf-cache
```

### Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: mistral-vllm
spec:
  selector:
    app: mistral-vllm
  ports:
    - name: http
      port: 8000
      targetPort: 8000
```

### Test vLLM

```bash
kubectl run curl-test --rm -it --image=curlimages/curl -- \
  curl http://mistral-vllm:8000/v1/chat/completions \
    -H 'Content-Type: application/json' \
    -d '{
      "model": "mistral",
      "messages": [
        {"role": "user", "content": "Say OK only."}
      ],
      "max_tokens": 8,
      "temperature": 0
    }'
```

### App Configuration Impact

The current `weather_ai_agent` config supports Ollama and Gemini. To use vLLM directly, add a provider that creates an OpenAI-compatible client/LLM config, for example:

```env
LLM_PROVIDER=openai_compatible
OPENAI_BASE_URL=http://mistral-vllm:8000/v1
OPENAI_API_KEY=dummy
OPENAI_MODEL=mistral
```

The exact code change depends on whether CrewAI's `LLM` wrapper in the installed version supports `base_url` for OpenAI-compatible servers in the way you want. Conceptually, this is the cleanest production direction.

## Memory Sizing

LLM memory use has three major parts:

1. Model weights.
2. Runtime overhead.
3. KV cache for active prompts and generated tokens.

For a 7B class model:

- Full precision weights can require much more memory than a quantized model.
- A 4-bit quantized model can fit in much less memory, but may reduce quality.
- Long context increases KV cache memory.
- Parallel requests multiply KV cache pressure.
- GPU memory is usually the real bottleneck for fast inference.

For Ollama, official behavior to keep in mind:

- Default context length is 4096 tokens.
- `OLLAMA_CONTEXT_LENGTH` changes the default context length.
- `OLLAMA_NUM_PARALLEL` controls parallel requests per loaded model.
- Memory requirement scales with `OLLAMA_NUM_PARALLEL * OLLAMA_CONTEXT_LENGTH`.
- `OLLAMA_MAX_LOADED_MODELS` controls how many models may remain loaded at once.
- `OLLAMA_MAX_QUEUE` controls how many requests can wait before the server rejects new requests.
- `OLLAMA_KEEP_ALIVE` controls how long models stay loaded.
- Flash Attention can reduce memory use as context grows when supported.
- KV cache quantization can reduce context-cache memory, with possible quality tradeoffs.

## Recommended Ollama Settings For A Small Pod

For one model and predictable memory:

```yaml
env:
  - name: OLLAMA_CONTEXT_LENGTH
    value: "4096"
  - name: OLLAMA_NUM_PARALLEL
    value: "1"
  - name: OLLAMA_MAX_LOADED_MODELS
    value: "1"
  - name: OLLAMA_MAX_QUEUE
    value: "64"
  - name: OLLAMA_KEEP_ALIVE
    value: "30m"
```

For higher throughput, increase cautiously:

```yaml
env:
  - name: OLLAMA_NUM_PARALLEL
    value: "2"
  - name: OLLAMA_MAX_QUEUE
    value: "256"
```

Do this only after measuring memory. Parallelism is not free.

## Recommended vLLM Settings For A Small GPU Pod

Start conservative:

```text
--max-model-len 4096
--gpu-memory-utilization 0.85
```

Then tune:

- Increase `--max-model-len` only if the application needs long prompts.
- Lower `--gpu-memory-utilization` if the pod gets CUDA out-of-memory failures.
- Use quantized model variants if the model does not fit.
- Use more GPUs or tensor parallelism for larger models.
- Keep the model server as a separate deployment from the application, so app restarts do not reload the model.

## What Happens When Memory Is A Bottleneck

### In Kubernetes

If the container exceeds its memory limit, Linux cgroups can trigger an out-of-memory kill. Kubernetes may restart the container, and the pod can show statuses such as `OOMKilled` or repeated restarts.

If the pod requests too much memory or GPU, it may stay `Pending` because the scheduler cannot find a node with enough available resources.

If memory request is low but limit is high, the pod can be scheduled onto a node that later becomes memory pressured. The pod may then be evicted.

### In Ollama

Possible symptoms:

- Requests queue behind an already loaded model.
- New requests receive `503` if the queue limit is exceeded.
- Another loaded model is unloaded to make room.
- The server falls back to CPU or split CPU/GPU execution if GPU memory is insufficient.
- Latency increases sharply with long prompts, high `num_ctx`, or high parallelism.

### In vLLM

Possible symptoms:

- Model fails to load due to GPU memory pressure.
- Requests fail with CUDA out-of-memory errors.
- Throughput drops if max context is too large for the workload.
- Excessive concurrency increases KV cache pressure.

## Parallel Execution

There are two kinds of parallelism:

1. Request-level parallelism: multiple user requests being served at the same time.
2. Model-level parallelism: one model split across hardware, such as tensor parallelism across GPUs.

Ollama makes request-level parallelism simple with `OLLAMA_NUM_PARALLEL`, but memory grows with parallel contexts.

vLLM is designed for serving many requests efficiently. It uses batching and KV cache management to improve throughput. This is why vLLM is usually a better Linux/GPU production serving choice than Ollama for high request volume.

Kubernetes replica scaling is another layer:

- Scaling the application pod is cheap.
- Scaling model-serving pods is expensive because each replica loads model weights.
- A model server replica normally needs its own GPU or enough CPU/RAM.
- Horizontal scaling should be based on queue depth, latency, GPU utilization, and memory headroom, not just CPU.

## Should The LLM Run In The Same Pod As The Weather App?

Usually no.

Prefer separate deployments:

```text
weather-ai-agent app -> ClusterIP service -> model server pod
```

Reasons:

- The model server has different CPU/GPU/memory needs.
- Model startup is slow and should not happen every time the app restarts.
- You can scale app pods independently from model pods.
- You can replace Ollama with vLLM later without rebuilding the weather app.
- Resource limits and monitoring are cleaner.

A same-pod sidecar is acceptable for a local POC, but it is usually not the right production shape.

## Recommended Direction For This Project

Use this path:

1. Keep the current Ollama integration for laptop and POC use.
2. For Kubernetes POC, deploy Ollama as a separate service and point `OLLAMA_BASE_URL` to it.
3. For production Linux/GPU serving, add an OpenAI-compatible provider to `config.py` and run Mistral through vLLM.
4. Keep the weather fetch outside the LLM. The LLM should summarize facts, not source facts.

## Example Kubernetes Architecture

```text
Browser / API Client
        |
        v
weather-ai-agent Service
        |
        v
weather-ai-agent Deployment
        |
        | HTTP
        v
model-server Service
        |
        v
Ollama or vLLM Deployment
        |
        v
Persistent model cache / GPU / CPU RAM
```

## Operational Checklist

- Pin model versions instead of relying on `latest` for production.
- Use persistent storage for model caches.
- Set memory requests and limits deliberately.
- Request GPUs explicitly when using GPU serving.
- Add startup probes because model loading can take time.
- Add readiness probes so traffic starts only after the server is usable.
- Track latency, queue depth, memory, GPU memory, and restart count.
- Limit max context length unless long context is required.
- Keep `temperature` low for factual summarization.
- Load test with realistic prompt sizes and concurrency before increasing parallelism.

## Our Expected Traffic

Requirement estimate:

- 10,000 to 20,000 requests per day.
- Around 1,000 concurrent requests during most business hours.
- Most requests around 1,000 tokens.
- Maximum request size around 5,000 tokens.

This is not a safe fit for one ordinary model-serving pod.

The daily request count is not the hard part. 20,000 requests per day is modest if spread out. The hard part is 1,000 concurrent LLM requests. Concurrency drives active KV cache memory, queue depth, tail latency, and GPU pressure.

For this traffic, assume the following:

- The weather app pods can scale horizontally and should handle this API traffic easily.
- The model-serving tier must be sized separately.
- A single Ollama pod is unlikely to handle 1,000 concurrent requests with acceptable latency.
- A single vLLM pod on one GPU may also be insufficient, depending on GPU size, quantization, prompt length, output length, and latency target.
- 5,000-token requests are much more expensive than 1,000-token requests because context/KV cache memory grows with token count.

Recommended architecture for this requirement:

```text
weather-ai-agent pods
        |
        v
LLM gateway / internal service
        |
        v
multiple vLLM model-serving pods
        |
        v
GPU nodes with autoscaling and queue metrics
```

For a first production test, use vLLM rather than Ollama and start with conservative assumptions:

- Use Mistral 7B instruct or a pinned equivalent model, not `latest`.
- Use GPUs with enough memory for the model plus concurrent KV cache.
- Cap max context length if most calls are around 1,000 tokens.
- Keep `max_tokens` for output low if the response is a short weather summary.
- Use request queueing and backpressure instead of allowing unlimited concurrency.
- Scale model-serving replicas based on queue depth, p95/p99 latency, GPU memory, and tokens per second.
- Load test with realistic input sizes: 1K-token normal requests and 5K-token worst-case requests.

Practical conclusion:

Do not plan for "one pod handles 1,000 concurrent LLM calls nicely" unless that pod is backed by serious GPU capacity and tested with the real prompt/output sizes. For this requirement, plan a horizontally scalable model-serving tier, preferably vLLM on GPU nodes, and treat Ollama as a POC or low-traffic serving option.

## Source References

- Ollama Docker guide: https://docs.ollama.com/docker
- Ollama API introduction: https://docs.ollama.com/api/introduction
- Ollama FAQ for context length, keep-alive, queueing, concurrency, Flash Attention, and KV cache settings: https://docs.ollama.com/faq
- vLLM online serving and OpenAI-compatible serving docs: https://docs.vllm.ai/en/latest/serving/online_serving/
- Kubernetes resource requests and limits: https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/
- Kubernetes GPU scheduling: https://kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/
- Mistral 7B announcement: https://mistral.ai/news/announcing-mistral-7b/
- Mistral 7B paper: https://arxiv.org/abs/2310.06825
