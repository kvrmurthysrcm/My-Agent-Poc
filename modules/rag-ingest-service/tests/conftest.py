import os


os.environ["DATABASE_URL"] = "sqlite:///./rag_ingest_test.db"
os.environ["EMBEDDING_PROVIDER"] = "openai"
