"""
Unit tests for semantic chunking logic.

Target: services/indexing/app/semantic_chunking.py
Tests critical chunking behavior including the max_tokens=None bug fix.
"""

from services.indexing.app.semantic_chunking import chunk_document


class TestChunkDocumentCriticalLogic:
    """Test critical chunking logic that caused production bugs."""

    def test_chunk_document_with_none_max_tokens(self):
        """Test that max_tokens=None doesn't cause TypeError."""
        text = "This is a test paragraph.\n\nThis is another paragraph."
        metadata = {"title": "TestDoc", "url": "http://example.com"}

        # Previously caused TypeError with int/NoneType comparison
        chunks = chunk_document(text, metadata, max_tokens=None)

        assert len(chunks) > 0
        assert all("text" in chunk for chunk in chunks)
        assert all("metadata" in chunk for chunk in chunks)

    def test_chunk_document_respects_max_tokens(self):
        """Test that chunks respect the max_tokens limit."""
        # Create text that will definitely exceed 50 tokens
        long_text = " ".join(["word"] * 200)
        metadata = {"title": "LongDoc"}
        max_tokens = 50

        chunks = chunk_document(long_text, metadata, max_tokens=max_tokens)

        # Verify chunks were created
        assert len(chunks) > 1

        # Import tiktoken to count tokens
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")

        # Each chunk should be under or near the limit (allow small buffer)
        for chunk in chunks:
            token_count = len(enc.encode(chunk["text"]))
            # Allow 10% buffer due to splitting logic
            assert (
                token_count <= max_tokens * 1.1
            ), f"Chunk has {token_count} tokens, limit is {max_tokens}"

    def test_chunk_document_preserves_metadata(self):
        """Test that original metadata is preserved and chunk metadata is added."""
        text = "First paragraph.\n\nSecond paragraph."
        metadata = {
            "title": "TestDoc",
            "url": "http://example.com",
            "page": 1,
            "custom_field": "custom_value",
        }

        chunks = chunk_document(text, metadata, max_tokens=100)

        for i, chunk in enumerate(chunks):
            chunk_meta = chunk["metadata"]

            # Original metadata preserved
            assert chunk_meta["title"] == "TestDoc"
            assert chunk_meta["url"] == "http://example.com"
            assert chunk_meta["page"] == 1
            assert chunk_meta["custom_field"] == "custom_value"

            # Chunk-specific metadata added
            assert "chunk_index" in chunk_meta
            assert "chunk_start" in chunk_meta
            assert "chunk_end" in chunk_meta
            assert "chunk_length" in chunk_meta
            assert chunk_meta["chunk_index"] == i

    def test_chunk_document_splits_by_paragraphs(self):
        """Test that document is split by paragraph boundaries (\\n\\n)."""
        text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
        metadata = {"title": "MultiPara"}

        chunks = chunk_document(text, metadata, max_tokens=500)

        # With high max_tokens, should create one chunk with all paragraphs
        assert len(chunks) == 1
        assert "Paragraph one" in chunks[0]["text"]
        assert "Paragraph two" in chunks[0]["text"]
        assert "Paragraph three" in chunks[0]["text"]

    def test_chunk_document_splits_long_paragraph(self):
        """Test that paragraphs exceeding max_tokens are split into smaller chunks."""
        # Create a very long paragraph without \\n\\n breaks
        long_paragraph = " ".join([f"Sentence {i}." for i in range(100)])
        metadata = {"title": "LongPara"}

        chunks = chunk_document(long_paragraph, metadata, max_tokens=50)

        # Should split into multiple chunks
        assert len(chunks) > 1

        # Verify each chunk has content
        for chunk in chunks:
            assert len(chunk["text"]) > 0

    def test_chunk_document_handles_empty_text(self):
        """Test that empty text returns empty chunk list."""
        metadata = {"title": "EmptyDoc"}

        chunks = chunk_document("", metadata, max_tokens=100)

        assert chunks == []

    def test_chunk_document_handles_whitespace_only(self):
        """Test that whitespace-only text returns empty chunk list."""
        metadata = {"title": "WhitespaceDoc"}

        chunks = chunk_document("   \n\n   \n\n   ", metadata, max_tokens=100)

        assert chunks == []

    def test_chunk_offsets_are_sequential(self):
        """Test that chunk offsets don't overlap and are in order."""
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        metadata = {"title": "OffsetTest"}

        chunks = chunk_document(text, metadata, max_tokens=100)

        # Verify offsets are sequential
        for i in range(1, len(chunks)):
            prev_end = chunks[i - 1]["metadata"]["chunk_end"]
            curr_start = chunks[i]["metadata"]["chunk_start"]
            # Current chunk should start after or at previous chunk's end
            assert curr_start >= prev_end, f"Chunk {i} overlaps with chunk {i-1}"

    def test_chunk_lengths_match_text_length(self):
        """Test that chunk_length metadata matches actual text length."""
        text = "Test paragraph one.\n\nTest paragraph two."
        metadata = {"title": "LengthTest"}

        chunks = chunk_document(text, metadata, max_tokens=100)

        for chunk in chunks:
            actual_length = len(chunk["text"])
            metadata_length = chunk["metadata"]["chunk_length"]
            assert actual_length == metadata_length

    def test_chunk_document_with_special_characters(self):
        """Test chunking with special characters and unicode."""
        text = (
            "Paragraph with émojis 😀 and special chars: <>&\"'.\n\n"
            "Another paragraph with 中文."
        )
        metadata = {"title": "SpecialChars"}

        chunks = chunk_document(text, metadata, max_tokens=100)

        # Should handle special characters without errors
        assert len(chunks) > 0
        assert "émojis" in chunks[0]["text"] or "中文" in chunks[0]["text"]

    def test_chunk_document_uses_default_max_tokens(self):
        """Test that default max_tokens from environment is used when not specified."""
        import os

        # Get the default from environment or fallback
        default_max_tokens = int(os.getenv("CHUNK_MAX_TOKENS", "400"))

        # Create text that will exceed default limit
        long_text = " ".join(["word"] * 500)
        metadata = {"title": "DefaultTest"}

        # Call without max_tokens parameter
        chunks = chunk_document(long_text, metadata)

        # Should create multiple chunks using default limit
        assert len(chunks) > 1

        # Verify chunks respect the default limit
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        for chunk in chunks:
            token_count = len(enc.encode(chunk["text"]))
            # Allow buffer for splitting logic
            assert token_count <= default_max_tokens * 1.1

    def test_chunk_document_with_very_small_max_tokens(self):
        """Test chunking with very small max_tokens forces aggressive splitting."""
        text = "This is a single sentence that should be split into multiple chunks."
        metadata = {"title": "SmallTokenTest"}

        # Use very small max_tokens to force splitting
        chunks = chunk_document(text, metadata, max_tokens=5)

        # Should create multiple chunks
        assert len(chunks) > 1

    def test_chunk_indices_are_sequential(self):
        """Test that chunk_index values are sequential starting from 0."""
        text = "\n\n".join([f"Paragraph {i}" for i in range(5)])
        metadata = {"title": "IndexTest"}

        chunks = chunk_document(text, metadata, max_tokens=20)

        # Verify indices are sequential
        for i, chunk in enumerate(chunks):
            assert chunk["metadata"]["chunk_index"] == i
