"""
Unit tests for DocumentStorage class.

Target: services/ingestion/app/storage.py
Coverage: 94 statements at 0%
"""

import json
import os
import shutil
import tempfile
from unittest.mock import patch


class TestDocumentStorage:
    """Test DocumentStorage initialization and basic operations."""

    def test_storage_initialization(self):
        """Test storage creates required directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from services.ingestion.app.storage import DocumentStorage

            storage = DocumentStorage(tmpdir)

            assert storage.base_path == tmpdir
            assert os.path.exists(os.path.join(tmpdir, "documents"))
            assert os.path.exists(storage.pdfs_path)
            assert os.path.exists(storage.index_path)

    def test_storage_loads_existing_index(self):
        """Test storage loads existing index file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from services.ingestion.app.storage import DocumentStorage

            # Create existing index
            docs_path = os.path.join(tmpdir, "documents")
            os.makedirs(docs_path, exist_ok=True)
            index_path = os.path.join(docs_path, "discovered_docs.json")
            existing_index = {
                "doc1": {"pdf": "documents/pdfs/doc1.pdf", "url": "http://test.com"}
            }

            with open(index_path, "w") as f:
                json.dump(existing_index, f)

            storage = DocumentStorage(tmpdir)

            assert storage.index == existing_index

    def test_storage_handles_corrupted_index(self):
        """Test storage creates new index if existing one is corrupted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from services.ingestion.app.storage import DocumentStorage

            # Create corrupted index
            docs_path = os.path.join(tmpdir, "documents")
            os.makedirs(docs_path, exist_ok=True)
            index_path = os.path.join(docs_path, "discovered_docs.json")

            with open(index_path, "w") as f:
                f.write("invalid json{{{")

            storage = DocumentStorage(tmpdir)

            assert storage.index == {}

    def test_store_document_success(self):
        """Test storing document PDF and metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from services.ingestion.app.storage import DocumentStorage

            storage = DocumentStorage(tmpdir)
            pdf_content = b"fake pdf content"
            metadata = {
                "url": "http://example.com/doc.pdf",
                "hash": "abc123",
                "date": "2025-01-01",
                "correlation_id": "test-123",
            }

            result = storage.store_document("doc1", pdf_content, metadata)

            assert result is True
            assert "doc1" in storage.index
            assert storage.index["doc1"]["url"] == metadata["url"]
            assert storage.index["doc1"]["hash"] == metadata["hash"]

            # Verify PDF was written
            pdf_path = os.path.join(storage.pdfs_path, "doc1.pdf")
            assert os.path.exists(pdf_path)
            with open(pdf_path, "rb") as f:
                assert f.read() == pdf_content

    def test_store_document_creates_directory_if_deleted(self):
        """Test store_document recreates pdfs directory if it was deleted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from services.ingestion.app.storage import DocumentStorage

            storage = DocumentStorage(tmpdir)

            # Delete the pdfs directory
            shutil.rmtree(storage.pdfs_path)
            assert not os.path.exists(storage.pdfs_path)

            # Try to store document
            result = storage.store_document(
                "doc1", b"content", {"url": "http://test.com"}
            )

            assert result is True
            assert os.path.exists(storage.pdfs_path)

    def test_store_document_handles_errors(self):
        """Test store_document handles write errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from services.ingestion.app.storage import DocumentStorage

            storage = DocumentStorage(tmpdir)

            # On Windows, chmod doesn't work the same way,
            # so mock the write operation instead
            import builtins

            original_open = builtins.open

            def mock_open_failure(*args, **kwargs):
                if "wb" in args or kwargs.get("mode") == "wb":
                    raise PermissionError("Permission denied")
                return original_open(*args, **kwargs)

            with patch("builtins.open", side_effect=mock_open_failure):
                result = storage.store_document("doc1", b"content", {"url": "test"})
                assert result is False

    def test_get_pdf_success(self):
        """Test retrieving PDF content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from services.ingestion.app.storage import DocumentStorage

            storage = DocumentStorage(tmpdir)
            pdf_content = b"test pdf data"

            storage.store_document("doc1", pdf_content, {"url": "test"})

            retrieved = storage.get_pdf("doc1")

            assert retrieved == pdf_content

    def test_get_pdf_not_found(self):
        """Test get_pdf returns None for non-existent document."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from services.ingestion.app.storage import DocumentStorage

            storage = DocumentStorage(tmpdir)

            result = storage.get_pdf("nonexistent")

            assert result is None

    def test_get_pdf_file_deleted(self):
        """Test get_pdf handles case where index exists but file is deleted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from services.ingestion.app.storage import DocumentStorage

            storage = DocumentStorage(tmpdir)
            storage.store_document("doc1", b"content", {"url": "test"})

            # Delete the PDF file
            pdf_path = os.path.join(storage.pdfs_path, "doc1.pdf")
            os.remove(pdf_path)

            result = storage.get_pdf("doc1")

            assert result is None

    def test_get_pdf_path_success(self):
        """Test get_pdf_path returns correct path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from services.ingestion.app.storage import DocumentStorage

            storage = DocumentStorage(tmpdir)
            storage.store_document("doc1", b"content", {"url": "test"})

            path = storage.get_pdf_path("doc1")

            assert path is not None
            assert os.path.exists(path)
            assert path.endswith("doc1.pdf")

    def test_get_pdf_path_not_found(self):
        """Test get_pdf_path returns None for non-existent document."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from services.ingestion.app.storage import DocumentStorage

            storage = DocumentStorage(tmpdir)

            path = storage.get_pdf_path("nonexistent")

            assert path is None

    def test_get_document_path_success(self):
        """Test get_document_path returns correct path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from services.ingestion.app.storage import DocumentStorage

            storage = DocumentStorage(tmpdir)
            storage.store_document("doc1", b"content", {"url": "test"})

            path = storage.get_document_path("doc1")

            assert path is not None
            assert os.path.exists(path)

    def test_list_documents_empty(self):
        """Test list_documents returns empty list for new storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from services.ingestion.app.storage import DocumentStorage

            storage = DocumentStorage(tmpdir)

            docs = storage.list_documents()

            assert docs == []

    def test_list_documents_with_documents(self):
        """Test list_documents returns all stored documents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from services.ingestion.app.storage import DocumentStorage

            storage = DocumentStorage(tmpdir)

            storage.store_document("doc1", b"content1", {"url": "http://test1.com"})
            storage.store_document("doc2", b"content2", {"url": "http://test2.com"})

            docs = storage.list_documents()

            assert len(docs) == 2
            doc_ids = [doc["document_id"] for doc in docs]
            assert "doc1" in doc_ids
            assert "doc2" in doc_ids

    def test_delete_document_success(self):
        """Test deleting a document removes PDF and index entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from services.ingestion.app.storage import DocumentStorage

            storage = DocumentStorage(tmpdir)
            storage.store_document("doc1", b"content", {"url": "test"})

            pdf_path = os.path.join(storage.pdfs_path, "doc1.pdf")
            assert os.path.exists(pdf_path)
            assert "doc1" in storage.index

            result = storage.delete_document("doc1")

            assert result is True
            assert not os.path.exists(pdf_path)
            assert "doc1" not in storage.index

    def test_delete_document_not_found(self):
        """Test delete_document returns False for non-existent document."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from services.ingestion.app.storage import DocumentStorage

            storage = DocumentStorage(tmpdir)

            result = storage.delete_document("nonexistent")

            assert result is False

    def test_delete_document_file_already_deleted(self):
        """Test delete_document handles case where file is already deleted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from services.ingestion.app.storage import DocumentStorage

            storage = DocumentStorage(tmpdir)
            storage.store_document("doc1", b"content", {"url": "test"})

            # Delete the PDF file manually
            pdf_path = os.path.join(storage.pdfs_path, "doc1.pdf")
            os.remove(pdf_path)

            result = storage.delete_document("doc1")

            # Should still succeed (removes index entry)
            assert result is True
            assert "doc1" not in storage.index

    def test_thread_safety_with_lock(self):
        """Test that storage operations use thread lock."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from services.ingestion.app.storage import DocumentStorage

            storage = DocumentStorage(tmpdir)

            # Verify lock exists
            assert storage._lock is not None

            # Store and retrieve should work with lock
            storage.store_document("doc1", b"content", {"url": "test"})
            result = storage.get_pdf("doc1")

            assert result == b"content"
