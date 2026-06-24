from app.services.chunking_service import ChunkingService


def test_chunking_preserves_metadata_fields():
    chunks = ChunkingService().chunk("CLAIMS:\nOne two three four five six seven eight nine ten.", 5, 1)
    assert chunks
    assert chunks[0].chunk_index == 0
    assert chunks[0].chunk_hash_sha256
    assert chunks[0].token_count > 0
    assert chunks[0].section_title == "CLAIMS"
