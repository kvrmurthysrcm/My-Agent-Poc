# Ollama Local Testing Guide

Use these PowerShell commands to verify Ollama before running the RAG ingestion API.

## Start Ollama

Start Ollama in the foreground:

```powershell
$env:OLLAMA_EMBEDDINGS="1"
ollama serve
```

Or use the background helper script:

```powershell
cd D:\py-workspace\My-Agent-Poc\modules\rag-ingest-service\ollama
.\start_ollama_with_embeddings.bat
```

Expected result:

```text
Ollama starts and listens on 127.0.0.1:11434.
```

## Stop Ollama

```powershell
Get-Process ollama -ErrorAction SilentlyContinue | Stop-Process -Force
```

Expected result:

```text
No output means the process was stopped or was not running.
```

## Check Ollama Is Running

Check the process:

```powershell
Get-Process ollama -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,StartTime,Path
```

Expected response:

```text
Id    ProcessName    StartTime              Path
--    -----------    ---------              ----
1234  ollama         ...                    ...\ollama.exe
```

Check the port:

```powershell
Test-NetConnection -ComputerName 127.0.0.1 -Port 11434 | Select-Object ComputerName,RemotePort,TcpTestSucceeded
```

Expected response:

```text
ComputerName RemotePort TcpTestSucceeded
------------ ---------- ----------------
127.0.0.1         11434             True
```

Check the API:

```powershell
Invoke-RestMethod http://127.0.0.1:11434/api/tags
```

Expected response:

```text
models
------
{...}
```

## List All Available Models

CLI:

```powershell
ollama list
```

API:

```powershell
(Invoke-RestMethod http://127.0.0.1:11434/api/tags).models | Select-Object name, model, modified_at
```

Expected response:

```text
name                       model                      modified_at
----                       -----                      -----------
embeddinggemma:latest      embeddinggemma:latest      ...
nomic-embed-text:latest    nomic-embed-text:latest    ...
mxbai-embed-large:latest   mxbai-embed-large:latest   ...
mistral:latest             mistral:latest             ...
```

## Check Model Capabilities

Use `ollama show`:

```powershell
ollama show mistral:latest
ollama show embeddinggemma
ollama show nomic-embed-text
ollama show mxbai-embed-large
```

Expected generative/NLQ model response includes:

```text
Capabilities
  completion
  tools
```

Expected embedding model response includes:

```text
Capabilities
  embedding
```

RAG module model usage:

```text
LLM_PROVIDER=ollama
LLM_MODEL=mistral:latest

EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=embeddinggemma
EMBEDDING_DIMENSION=768
```

Use `mistral:latest` for NLQ/generative text processing. Use `embeddinggemma` for embeddings.

## Test Generative / NLQ Model

Test `mistral:latest` with non-streaming generation:

```powershell
$body = @{
  model = "mistral:latest"
  prompt = "Say OK only."
  stream = $false
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:11434/api/generate -ContentType "application/json" -Body $body
```

Expected response fields:

```text
model      : mistral:latest
response   : OK
done       : True
```

If this succeeds, the model works for generative/NLQ text processing.

## Test Embedding Model

Test `embeddinggemma`:

```powershell
$body = @{
  model = "embeddinggemma"
  input = "RAG embedding smoke test"
} | ConvertTo-Json

$response = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:11434/api/embed -ContentType "application/json" -Body $body
$response.embeddings[0].Count
```

Expected response:

```text
768
```

If this returns `768`, `embeddinggemma` is working for embeddings.

Test optional embedding models:

```powershell
$models = @("nomic-embed-text", "mxbai-embed-large")

foreach ($model in $models) {
  $body = @{
    model = $model
    input = "RAG embedding smoke test"
  } | ConvertTo-Json

  $response = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:11434/api/embed -ContentType "application/json" -Body $body
  "$model dimension = $($response.embeddings[0].Count)"
}
```

Expected response:

```text
nomic-embed-text dimension = 768
mxbai-embed-large dimension = 1024
```

## Common Failure Responses

If an embedding call returns:

```text
This server does not support embeddings.
```

Then the current Ollama server/model combination is not serving embeddings. Use a model whose capability includes `embedding`, such as:

```text
embeddinggemma
nomic-embed-text
mxbai-embed-large
```

If a generation call fails with model not found:

```text
model "mistral:latest" not found
```

Pull the model:

```powershell
ollama pull mistral:latest
```

If an embedding model is missing:

```powershell
ollama pull embeddinggemma
ollama pull nomic-embed-text
ollama pull mxbai-embed-large
```

## RAG API Quick Preflight

Before testing `/rag/ingest`, verify:

```powershell
Test-NetConnection -ComputerName 127.0.0.1 -Port 11434
ollama show embeddinggemma
ollama show mistral:latest
```

Then verify embeddings:

```powershell
$body = @{ model = "embeddinggemma"; input = "test" } | ConvertTo-Json
(Invoke-RestMethod -Method Post -Uri http://127.0.0.1:11434/api/embed -ContentType "application/json" -Body $body).embeddings[0].Count
```

Expected:

```text
768
```
