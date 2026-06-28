import os


os.environ["DATABASE_URL"] = os.getenv(
    "RAG_INGEST_TEST_DATABASE_URL",
    "postgresql://library_user:library_pass@localhost:5432/online_library_test",
)
os.environ["EMBEDDING_PROVIDER"] = "openai"
os.environ["EMBEDDING_MODEL"] = "text-embedding-3-small"
os.environ["EMBEDDING_DIMENSION"] = "1536"
os.environ["ALLOW_FAKE_EMBEDDINGS"] = "true"
