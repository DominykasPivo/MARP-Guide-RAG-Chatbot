"""
End-to-end integration tests for the complete pipeline using real MARP documents.

Tests the full document lifecycle:
1. Ingestion: Document discovery and storage
2. Extraction: PDF text and metadata extraction
3. Indexing: Chunking and vector embedding
4. Retrieval: Search and relevance ranking

Uses actual MARP PDFs from data/documents/pdfs for realistic testing.
"""

import tempfile
from pathlib import Path

import pytest

# ============================================================================
# TEST FIXTURES
# ============================================================================


@pytest.fixture
def sample_marp_pdf():
    """Get path to a real MARP PDF for testing."""
    test_pdf = Path(__file__).parent.parent / "pdfs" / "sample_marp.pdf"
    if not test_pdf.exists():
        pytest.skip("Sample MARP PDF not available for testing")

    return str(test_pdf)


@pytest.fixture
def temp_storage():
    """Create temporary storage directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


# ============================================================================
# INGESTION -> EXTRACTION PIPELINE TESTS
# ============================================================================


class TestIngestionToExtraction:
    """Test document flow from ingestion through extraction."""

    def test_document_ingestion_and_storage(self, sample_marp_pdf, temp_storage):
        """Test that discovered documents are properly stored."""
        from services.ingestion.app.storage import DocumentStorage

        storage = DocumentStorage(temp_storage)

        # Read the PDF content
        with open(sample_marp_pdf, "rb") as f:
            pdf_content = f.read()

        # Store the document
        doc_id = "test-doc-001"
        metadata = {
            "url": "http://example.com/test.pdf",
            "hash": "test-hash",
            "date": "2025-01-01",
            "correlation_id": "test-corr-001",
        }

        success = storage.store_document(doc_id, pdf_content, metadata)

        assert success is True
        assert doc_id in storage.index
        assert storage.get_pdf(doc_id) is not None

    def test_extraction_after_ingestion(self, sample_marp_pdf, temp_storage):
        """Test that ingested documents can be extracted."""
        from services.extraction.app.extractor import PDFExtractor
        from services.ingestion.app.storage import DocumentStorage

        # First, ingest the document
        storage = DocumentStorage(temp_storage)
        with open(sample_marp_pdf, "rb") as f:
            pdf_content = f.read()

        doc_id = "test-doc-002"
        storage.store_document(
            doc_id, pdf_content, {"url": "http://test.com", "correlation_id": "test"}
        )

        # Get the stored path
        pdf_path = storage.get_pdf_path(doc_id)
        assert pdf_path is not None

        # Extract the document
        extractor = PDFExtractor()
        result = extractor.extract_document(pdf_path, "http://test.com")

        assert "page_texts" in result
        assert "metadata" in result
        assert len(result["page_texts"]) > 0


# ============================================================================
# EXTRACTION -> INDEXING PIPELINE TESTS
# ============================================================================


class TestExtractionToIndexing:
    """Test document flow from extraction through indexing."""

    def test_extracted_text_chunking(self, sample_marp_pdf):
        """Test that extracted text is properly chunked."""
        from services.extraction.app.extractor import PDFExtractor
        from services.indexing.app.semantic_chunking import chunk_document

        # Extract the document
        extractor = PDFExtractor()
        extracted = extractor.extract_document(sample_marp_pdf, "http://test.com")

        # Combine page texts for chunking
        full_text = "\n\n".join(extracted["page_texts"])

        # Chunk the extracted text
        chunks = chunk_document(full_text, extracted["metadata"])

        assert len(chunks) > 0
        assert all(isinstance(chunk, dict) for chunk in chunks)
        assert all("text" in chunk for chunk in chunks)
        # Each chunk should have reasonable length
        assert all(len(chunk["text"]) > 10 for chunk in chunks)

    def test_chunks_preserve_content(self, sample_marp_pdf):
        """Test that chunking preserves original content."""
        from services.extraction.app.extractor import PDFExtractor
        from services.indexing.app.semantic_chunking import chunk_document

        extractor = PDFExtractor()
        extracted = extractor.extract_document(sample_marp_pdf, "http://test.com")

        full_text = "\n\n".join(extracted["page_texts"])
        chunks = chunk_document(full_text, extracted["metadata"])

        # Verify chunks contain meaningful content from original
        combined_chunks = " ".join([chunk["text"] for chunk in chunks])

        # Check that some content from original is in chunks
        # (allowing for some loss due to cleaning/chunking)
        original_words = full_text.split()[:100]  # First 100 words
        preserved_words = sum(
            1 for word in original_words if word.lower() in combined_chunks.lower()
        )

        # At least 70% of words should be preserved
        assert preserved_words / len(original_words) > 0.7


# ============================================================================
# INDEXING -> RETRIEVAL PIPELINE TESTS
# ============================================================================


class TestIndexingToRetrieval:
    """Test document flow from indexing through retrieval."""

    def test_indexed_chunks_retrievable(self, sample_marp_pdf):
        """Test that indexed chunks can be retrieved via search."""
        from unittest.mock import MagicMock, patch

        from services.extraction.app.extractor import PDFExtractor
        from services.indexing.app.embed_chunks import embed_chunks
        from services.indexing.app.semantic_chunking import chunk_document

        # Extract and chunk
        extractor = PDFExtractor()
        extracted = extractor.extract_document(sample_marp_pdf, "http://test.com")

        # Chunk the text
        full_text = "\n\n".join(extracted["page_texts"])
        metadata = extracted["metadata"]
        chunks = chunk_document(full_text, metadata)

        # Embed chunks (uses model from environment)
        embedded_chunks = embed_chunks(chunks)

        # Verify embeddings were created
        assert len(embedded_chunks) > 0
        assert all("embedding" in chunk for chunk in embedded_chunks)
        assert all(len(chunk["embedding"]) > 0 for chunk in embedded_chunks)

        # Mock Qdrant storage and retrieval
        mock_qdrant = MagicMock()
        mock_qdrant.search.return_value = [
            MagicMock(
                payload={"text": chunk["text"], "metadata": chunk.get("metadata", {})},
                score=0.85,
            )
            for chunk in embedded_chunks[:5]
        ]

        with patch(
            "services.retrieval.app.retriever.QdrantClient", return_value=mock_qdrant
        ):
            # Verify we can search (mocked)
            from services.retrieval.app.retriever import Retriever

            retriever = Retriever()
            results = retriever.search("academic policy", top_k=5)

            # Verify results structure
            assert len(results) > 0
            assert all("text" in result for result in results)
            assert all("relevanceScore" in result for result in results)

    def test_chunk_metadata_structure(self, sample_marp_pdf):
        """Test that chunk metadata has required structure for indexing."""
        from services.extraction.app.extractor import PDFExtractor

        extractor = PDFExtractor()
        extracted = extractor.extract_document(sample_marp_pdf, "http://test.com")

        metadata = extracted["metadata"]

        required_fields = ["title", "pageCount", "sourceUrl"]
        for field in required_fields:
            assert (
                field in metadata
            ), f"Metadata missing required field for indexing: {field}"


# ============================================================================
# FULL PIPELINE TESTS
# ============================================================================


class TestFullPipeline:
    """Test the complete pipeline from ingestion to retrieval."""

    def test_document_lifecycle(self, sample_marp_pdf, temp_storage):
        """Test complete document lifecycle through all services."""
        from services.extraction.app.extractor import PDFExtractor
        from services.indexing.app.semantic_chunking import chunk_document
        from services.ingestion.app.storage import DocumentStorage

        # 1. INGESTION: Store document
        storage = DocumentStorage(temp_storage)
        with open(sample_marp_pdf, "rb") as f:
            pdf_content = f.read()

        doc_id = "lifecycle-test-001"
        storage.store_document(
            doc_id,
            pdf_content,
            {"url": "http://test.com/doc.pdf", "correlation_id": "lifecycle-001"},
        )

        # Verify storage
        assert doc_id in storage.index
        stored_path = storage.get_pdf_path(doc_id)
        assert stored_path is not None

        # 2. EXTRACTION: Extract text
        extractor = PDFExtractor()
        extracted = extractor.extract_document(stored_path, "http://test.com/doc.pdf")

        # Verify extraction
        assert len(extracted["page_texts"]) > 0
        assert extracted["metadata"]["pageCount"] > 0

        # 3. INDEXING: Chunk the text
        full_text = "\n\n".join(extracted["page_texts"])
        chunks = chunk_document(full_text, extracted["metadata"])

        # Verify chunking
        assert len(chunks) > 0
        assert all(len(chunk["text"]) > 10 for chunk in chunks)

        # 4. RETRIEVAL: Would search chunks (skipped without Qdrant)
        # This would require embeddings and Qdrant connection

    def test_error_recovery_in_pipeline(self, temp_storage):
        """Test that pipeline handles errors gracefully."""
        from services.extraction.app.extractor import PDFExtractor

        # Try to extract non-existent document
        extractor = PDFExtractor()

        with pytest.raises(FileNotFoundError):
            extractor.extract_document("/nonexistent/doc.pdf", "http://test.com")

    def test_correlation_id_tracking(self, sample_marp_pdf, temp_storage):
        """Test that correlation ID can be tracked through pipeline."""
        from services.ingestion.app.storage import DocumentStorage

        correlation_id = "pipeline-test-123"

        # Store with correlation ID
        storage = DocumentStorage(temp_storage)
        with open(sample_marp_pdf, "rb") as f:
            pdf_content = f.read()

        doc_id = "corr-test-001"
        metadata = {
            "url": "http://test.com/doc.pdf",
            "hash": "test-hash",
            "correlation_id": correlation_id,
        }

        storage.store_document(doc_id, pdf_content, metadata)

        # Verify correlation ID is preserved in storage
        assert storage.index[doc_id]["correlation_id"] == correlation_id


# ============================================================================
# DATA QUALITY TESTS
# ============================================================================


class TestDataQuality:
    """Test data quality throughout the pipeline."""

    def test_no_data_loss_in_extraction(self, sample_marp_pdf):
        """Test that extraction doesn't lose significant content."""
        from services.extraction.app.extractor import PDFExtractor

        extractor = PDFExtractor()
        result = extractor.extract_document(sample_marp_pdf, "http://test.com")

        # Verify we extracted meaningful content
        total_chars = sum(len(text) for text in result["page_texts"])
        assert total_chars > 100, "Extraction should produce substantial text"

        # Verify metadata is complete
        assert result["metadata"]["pageCount"] > 0
        assert len(result["metadata"]["title"]) > 0

    def test_chunking_size_consistency(self, sample_marp_pdf):
        """Test that chunks are reasonably sized."""
        from services.extraction.app.extractor import PDFExtractor
        from services.indexing.app.semantic_chunking import chunk_document

        extractor = PDFExtractor()
        extracted = extractor.extract_document(sample_marp_pdf, "http://test.com")

        full_text = "\n\n".join(extracted["page_texts"])
        chunks = chunk_document(full_text, extracted["metadata"])

        # Chunks should be reasonably sized (not too small or too large)
        for chunk in chunks:
            # Min 10 chars, max 5000 chars (typical semantic chunk size)
            assert (
                10 < len(chunk["text"]) < 5000
            ), f"Chunk size out of range: {len(chunk['text'])}"

    def test_text_cleaning_quality(self, sample_marp_pdf):
        """Test that text cleaning improves quality."""
        from services.extraction.app.extractor import PDFExtractor

        extractor = PDFExtractor()
        result = extractor.extract_document(sample_marp_pdf, "http://test.com")

        for page_text in result["page_texts"]:
            # Should not have excessive whitespace
            assert "    " not in page_text, "Cleaned text should not have 4+ spaces"

            # Should not have pipe characters (OCR artifact)
            pipe_count = page_text.count("|")
            char_count = len(page_text)
            if char_count > 0:
                # Less than 1% pipe characters
                assert pipe_count / char_count < 0.01


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================


class TestPipelinePerformance:
    """Test performance characteristics of the pipeline."""

    def test_extraction_performance(self, sample_marp_pdf):
        """Test extraction completes in reasonable time."""
        import time

        from services.extraction.app.extractor import PDFExtractor

        extractor = PDFExtractor()

        start_time = time.time()
        result = extractor.extract_document(sample_marp_pdf, "http://test.com")
        elapsed = time.time() - start_time

        # Extraction should complete within 30 seconds for typical PDFs
        assert elapsed < 30.0, f"Extraction took too long: {elapsed}s"
        assert len(result["page_texts"]) > 0

    def test_chunking_performance(self, sample_marp_pdf):
        """Test chunking completes in reasonable time."""
        import time

        from services.extraction.app.extractor import PDFExtractor
        from services.indexing.app.semantic_chunking import chunk_document

        extractor = PDFExtractor()
        extracted = extractor.extract_document(sample_marp_pdf, "http://test.com")

        full_text = "\n\n".join(extracted["page_texts"])

        start_time = time.time()
        chunks = chunk_document(full_text, extracted["metadata"])
        elapsed = time.time() - start_time

        # Chunking should complete within 60 seconds
        assert elapsed < 60.0, f"Chunking took too long: {elapsed}s"
        assert len(chunks) > 0
