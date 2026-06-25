from app.services.chunking_service import ChunkingService


def test_intelligent_recursive_chunking_preserves_existing_behavior():
    chunks = ChunkingService().chunk(
        "CLAIMS:\nOne two three four five six seven eight nine ten.",
        5,
        1,
        strategy="INTELLIGENT_RECURSIVE",
    )
    assert chunks
    assert chunks[0].chunk_index == 0
    assert chunks[0].chunk_hash_sha256
    assert chunks[0].token_count > 0
    assert chunks[0].section_title == "CLAIMS"
    assert chunks[0].metadata["strategy"] == "INTELLIGENT_RECURSIVE"


def test_semantic_recursive_groups_paragraphs_before_fixed_windows():
    text = "\n\n".join(
        [
            "INTRODUCTION:",
            "This paragraph introduces the topic and should remain intact.",
            "This paragraph continues the same idea and should be grouped with nearby text.",
            "A final short paragraph closes the section.",
        ]
    )

    chunks = ChunkingService().chunk(text, 40, 5, strategy="SEMANTIC_RECURSIVE")

    assert chunks
    assert chunks[0].metadata["strategy"] == "SEMANTIC_RECURSIVE"
    assert chunks[0].chunk_type == "paragraph_group"
    assert "This paragraph introduces" in chunks[0].chunk_text


def test_semantic_recursive_falls_back_for_oversized_paragraphs():
    text = "LONG:\n" + " ".join(f"word{i}" for i in range(30))

    chunks = ChunkingService().chunk(text, 10, 2, strategy="SEMANTIC_RECURSIVE")

    assert len(chunks) > 1
    assert {chunk.chunk_type for chunk in chunks} == {"fallback_token_window"}
