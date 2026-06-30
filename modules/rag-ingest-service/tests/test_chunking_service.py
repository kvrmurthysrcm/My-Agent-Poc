from app.services.chunking_service import ChunkingService
from app.services.chunk_quality import filter_quality_chunks
from app.services.chunking_types import TextChunk


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


def test_single_letter_pdf_drop_cap_is_not_promoted_to_heading():
    chunks = ChunkingService().chunk(
        "M\n\narley was dead: to begin with.",
        40,
        5,
        strategy="SEMANTIC_RECURSIVE",
    )

    assert chunks
    assert chunks[0].section_title is None


def test_prose_line_ending_with_colon_is_not_promoted_to_heading():
    chunks = ChunkingService().chunk(
        (
            "Scrooge cried in great excitement:\n"
            "This is ordinary story text that continues the sentence after a colon."
        ),
        40,
        5,
        strategy="SEMANTIC_RECURSIVE",
    )

    assert chunks
    assert chunks[0].section_title is None
    assert "Scrooge cried in great excitement" in chunks[0].chunk_text


def test_semantic_recursive_falls_back_for_oversized_paragraphs():
    text = "LONG:\n" + " ".join(f"word{i}" for i in range(30))

    chunks = ChunkingService().chunk(text, 10, 2, strategy="SEMANTIC_RECURSIVE")

    assert len(chunks) > 1
    assert {chunk.chunk_type for chunk in chunks} == {"fallback_token_window"}


def test_chunking_preserves_page_marker_range():
    chunks = ChunkingService().chunk(
        "[Page 2]\nFirst page content.\n\n[Page 3]\nSecond page content.",
        40,
        5,
        strategy="SEMANTIC_RECURSIVE",
    )

    assert chunks[0].page_start == 2
    assert chunks[0].page_end == 3
    assert "[Page 2]" not in chunks[0].chunk_text


def test_chunking_filters_low_value_publisher_chunks():
    chunks = ChunkingService().chunk(
        "Publications Division,\n\nT.T.D, Tirupati.",
        40,
        5,
        strategy="SEMANTIC_RECURSIVE",
    )

    assert chunks == []


def test_chunking_keeps_real_short_content_after_cleaning_page_markers():
    chunks = ChunkingService().chunk(
        "[Page 57]\nThe very gold and silver fish appeared to know that something was going on.",
        40,
        5,
        strategy="SEMANTIC_RECURSIVE",
    )

    assert len(chunks) == 1
    assert chunks[0].chunk_text.startswith("The very gold")
    assert chunks[0].metadata["quality"] == "searchable"


def test_chunking_keeps_long_front_matter_with_metadata_flags():
    chunks = ChunkingService().chunk(
        (
            "Second Impression 1977. This preface explains the publication history and the editorial context "
            "for readers before the main document begins. It contains enough descriptive text to be retained."
        ),
        80,
        5,
        strategy="SEMANTIC_RECURSIVE",
    )

    assert len(chunks) == 1
    assert chunks[0].metadata["quality"] == "front_matter"
    assert chunks[0].metadata["front_matter"] is True
    assert chunks[0].metadata["boilerplate"] is False
    assert chunks[0].metadata["searchable"] is False


def test_chunking_marks_holybooks_front_matter_not_searchable():
    chunks = ChunkingService().chunk(
        (
            "This free e-book was downloaded from www.holybooks.com\n"
            "http://www.holybooks.com/ashtavakra-gita/\n"
            "Ashtavakra Gita\n"
            "Translator's Preface\n"
            "This preface explains the publication context before the main text begins."
        ),
        80,
        5,
        strategy="SEMANTIC_RECURSIVE",
    )

    assert len(chunks) == 1
    assert chunks[0].metadata["quality"] == "front_matter"
    assert chunks[0].metadata["searchable"] is False
    assert chunks[0].metadata["boilerplate"] is True


def test_semantic_recursive_keeps_verse_marker_with_body():
    chunks = ChunkingService().chunk(
        (
            "Ashtavakra said:\n"
            "1.8\n"
            "The thought: I am the doer is bondage.\n"
            "1.9\n"
            "I am the One Awareness, consumes all suffering in the fire of an instant.\n"
            "Be happy."
        ),
        18,
        0,
        strategy="SEMANTIC_RECURSIVE",
    )

    assert chunks
    assert not any(chunk.chunk_text.rstrip().endswith("1.9") for chunk in chunks)
    assert any("1.9" in chunk.chunk_text and "I am the One Awareness" in chunk.chunk_text for chunk in chunks)
    assert chunks[-1].metadata["verse_end"] == "1.9"


def test_semantic_recursive_moves_trailing_chapter_heading_to_next_metadata():
    chunks = ChunkingService().chunk(
        (
            "Janaka said:\n"
            "1.20\n"
            "The timeless, all-pervasive One exists as Totality. 2: Joy of Self-Realization\n"
            "2.1\n"
            "I am now spotless and at peace, aware, silent, and free."
        ),
        40,
        0,
        strategy="SEMANTIC_RECURSIVE",
    )

    assert len(chunks) == 2
    assert "2: Joy of Self-Realization" not in chunks[0].chunk_text
    assert chunks[1].metadata["chapter_number"] == 2
    assert chunks[1].metadata["chapter_title"] == "Joy of Self-Realization"
    assert chunks[1].metadata["verse_start"] == "2.1"


def test_semantic_recursive_splits_long_verse_groups_without_orphaning_markers():
    text = "Ashtavakra said:\n" + "\n".join(
        f"18.{index}\n" + " ".join(f"word{index}_{word}" for word in range(8))
        for index in range(1, 13)
    )

    chunks = ChunkingService().chunk(text, 35, 0, strategy="SEMANTIC_RECURSIVE")

    assert len(chunks) > 1
    assert all(not chunk.chunk_text.rstrip().endswith(tuple(f"18.{index}" for index in range(1, 13))) for chunk in chunks)
    assert chunks[0].metadata["verse_start"] == "18.1"
    assert chunks[-1].metadata["verse_end"] == "18.12"


def test_chunk_quality_keeps_numeric_table_heavy_chunks_when_enabled():
    raw = TextChunk(
        chunk_index=0,
        chunk_text=(
            "Invoice table | INV-1001 | 2026-06-25 | 1500.75 | CLAIM-8891\n"
            "Invoice table | INV-1002 | 2026-06-26 | 2750.20 | CLAIM-8892\n"
            "Invoice table | INV-1003 | 2026-06-27 | 3250.99 | CLAIM-8893"
        ),
        token_count=20,
        char_count=180,
        chunk_hash_sha256="raw",
    )

    chunks = filter_quality_chunks([raw], keep_numeric_table_chunks=True, min_alpha_ratio=0.70)

    assert len(chunks) == 1
    assert chunks[0].metadata["numeric_table_heavy"] is True
    assert chunks[0].metadata["searchable"] is True


def test_chunk_quality_can_filter_numeric_table_heavy_chunks_when_disabled():
    raw = TextChunk(
        chunk_index=0,
        chunk_text="Invoice | INV-1001 | 2026-06-25 | 1500.75 | CLAIM-8891",
        token_count=8,
        char_count=60,
        chunk_hash_sha256="raw",
    )

    chunks = filter_quality_chunks([raw], keep_numeric_table_chunks=False, min_alpha_ratio=0.70)

    assert chunks == []
