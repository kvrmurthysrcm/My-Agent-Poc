import os


os.environ["RAG_SEARCH_BASE_URL"] = "http://search.test"
os.environ["LLM_PROVIDER"] = "ollama"
os.environ["LLM_MODEL"] = "mistral:latest"
os.environ["OLLAMA_BASE_URL"] = "http://ollama.test"
