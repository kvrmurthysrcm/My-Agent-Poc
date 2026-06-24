@echo off
setlocal

echo Stopping any existing Ollama process...
taskkill /IM ollama.exe /F >nul 2>&1

echo Enabling Ollama embeddings for this session...
set OLLAMA_EMBEDDINGS=1

echo Starting Ollama server with embeddings enabled in the background...
start "Ollama Embeddings Server" /MIN cmd /c "set OLLAMA_EMBEDDINGS=1 && ollama serve"

timeout /t 3 /nobreak >nul
echo Ollama background process started. You can close this window.
endlocal
