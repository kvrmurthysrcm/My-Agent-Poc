import os


os.environ["DATABASE_URL"] = "sqlite:///./rag_ingest_test.db"
os.environ["EMBEDDING_PROVIDER"] = "openai"
os.environ["EMBEDDING_MODEL"] = "text-embedding-3-small"
os.environ["EMBEDDING_DIMENSION"] = "1536"
os.environ["ALLOW_FAKE_EMBEDDINGS"] = "true"
os.environ["AUTO_MIGRATE_ON_STARTUP"] = "false"
