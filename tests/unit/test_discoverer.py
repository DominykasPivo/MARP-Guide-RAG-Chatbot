"""
Unit tests for MARPDocumentDiscoverer class.

Target: services/ingestion/app/discoverer.py
Coverage: 87 statements at 0%
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import requests

# Add service app directory to Python path to match Docker environment
# In Docker, working directory is /app with modules at root level
project_root = Path(__file__).parent.parent.parent
ingestion_app = project_root / "services" / "ingestion" / "app"
if str(ingestion_app) not in sys.path:
    sys.path.insert(0, str(ingestion_app))


class TestMARPDocumentDiscoverer:
    """Test MARPDocumentDiscoverer initialization and document discovery."""

    @patch("discoverer.DocumentStorage")
    @patch("discoverer.PDFLinkExtractor")
    def test_discoverer_initialization(self, mock_extractor_class, mock_storage_class):
        """Test MARPDocumentDiscoverer initializes correctly."""
        from discoverer import MARPDocumentDiscoverer

        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock instances
            mock_storage_instance = Mock()
            mock_storage_class.return_value = mock_storage_instance
            mock_extractor_instance = Mock()
            mock_extractor_class.return_value = mock_extractor_instance

            discoverer = MARPDocumentDiscoverer(storage_dir=tmpdir)

            assert discoverer.storage == mock_storage_instance
            assert discoverer.extractor == mock_extractor_instance
            mock_storage_class.assert_called_once_with(tmpdir)

    @patch("discoverer.DocumentStorage")
    @patch("discoverer.PDFLinkExtractor")
    @patch("discoverer.hashlib")
    @patch("discoverer.requests")
    def test_get_document_hash_success(
        self, mock_requests, mock_hashlib, mock_extractor_class, mock_storage_class
    ):
        """Test _get_document_hash generates hash from HTTP headers."""
        from discoverer import MARPDocumentDiscoverer

        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock DocumentStorage and PDFLinkExtractor
            mock_storage_class.return_value = Mock()
            mock_extractor_class.return_value = Mock()

            # Mock HTTP response with headers
            mock_response = Mock()
            mock_response.headers = {"last-modified": "2024-01-01"}
            mock_response.raise_for_status = Mock()
            mock_requests.head.return_value = mock_response

            # Mock hash computation
            mock_hash = Mock()
            mock_hash.hexdigest.return_value = "abc123def456"
            mock_hashlib.sha256.return_value = mock_hash

            discoverer = MARPDocumentDiscoverer(storage_dir=tmpdir)

        result = discoverer._get_document_hash("https://test.com/doc.pdf")

        assert result == "abc123def456"
        mock_requests.head.assert_called_once_with(
            "https://test.com/doc.pdf", allow_redirects=True, timeout=10
        )
        mock_hashlib.sha256.assert_called_once()

    @patch("discoverer.DocumentStorage")
    @patch("discoverer.PDFLinkExtractor")
    @patch("discoverer.requests")
    def test_get_document_hash_http_error(
        self, mock_requests, mock_extractor_class, mock_storage_class
    ):
        """Test _get_document_hash handles HTTP errors."""
        from discoverer import MARPDocumentDiscoverer

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_storage_class.return_value = Mock()
            mock_extractor_class.return_value = Mock()

            # Mock requests.RequestException properly
            mock_requests.RequestException = requests.RequestException
            mock_requests.head.side_effect = requests.RequestException(
                "Connection failed"
            )

            discoverer = MARPDocumentDiscoverer(storage_dir=tmpdir)

            result = discoverer._get_document_hash("https://test.com/doc.pdf")

            assert result == ""

    @patch("discoverer.DocumentStorage")
    @patch("discoverer.PDFLinkExtractor")
    @patch("discoverer.requests")
    def test_discover_document_urls_success(
        self, mock_requests, mock_extractor_class, mock_storage_class
    ):
        """Test discover_document_urls extracts PDF links from page."""
        from discoverer import MARPDocumentDiscoverer

        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock HTTP response
            mock_response = Mock()
            mock_response.text = "<html>mock html</html>"
            mock_response.status_code = 200
            mock_response.raise_for_status = Mock()
            mock_requests.get.return_value = mock_response

            # Mock storage and extractor
            mock_storage_class.return_value = Mock()
            mock_extractor = Mock()
            mock_extractor.get_pdf_urls.return_value = [
                "https://test.com/doc1.pdf",
                "https://test.com/doc2.pdf",
            ]
            mock_extractor_class.return_value = mock_extractor

            discoverer = MARPDocumentDiscoverer(storage_dir=tmpdir)

        urls = discoverer.discover_document_urls()

        assert len(urls) == 2
        assert "https://test.com/doc1.pdf" in urls
        assert "https://test.com/doc2.pdf" in urls

        mock_requests.get.assert_called_once()
        mock_extractor.get_pdf_urls.assert_called_once()

    @patch("discoverer.DocumentStorage")
    @patch("discoverer.PDFLinkExtractor")
    @patch("discoverer.requests")
    def test_discover_document_urls_http_error(
        self, mock_requests, mock_extractor_class, mock_storage_class
    ):
        """Test discover_document_urls handles HTTP errors."""
        from discoverer import MARPDocumentDiscoverer

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_storage_class.return_value = Mock()
            mock_extractor_class.return_value = Mock()

            # Mock requests.RequestException properly
            mock_requests.RequestException = requests.RequestException
            mock_requests.get.side_effect = requests.RequestException("404 Not Found")

            discoverer = MARPDocumentDiscoverer(storage_dir=tmpdir)

            urls = discoverer.discover_document_urls()

            assert urls == []

    @patch("discoverer.DocumentStorage")
    @patch("discoverer.PDFLinkExtractor")
    @patch("discoverer.os.path.exists")
    @patch("discoverer.hashlib")
    @patch("discoverer.requests")
    def test_process_documents_new_document(
        self,
        mock_requests,
        mock_hashlib,
        mock_exists,
        mock_extractor_class,
        mock_storage_class,
    ):
        """Test process_documents handles new document."""
        from discoverer import MARPDocumentDiscoverer

        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock storage
            mock_storage = Mock()
            mock_storage.index = {}  # Empty index (no existing documents)
            mock_storage.base_path = tmpdir
            mock_storage_class.return_value = mock_storage
            mock_extractor_class.return_value = Mock()

            # Mock file doesn't exist yet
            mock_exists.return_value = False

            # Mock hash for URL and content
            def sha256_side_effect(data):
                if data == b"https://test.com/new-doc.pdf":
                    mock_hash = Mock()
                    mock_hash.hexdigest.return_value = "newdocid"
                    return mock_hash
                else:
                    mock_hash = Mock()
                    mock_hash.hexdigest.return_value = "contenthash"
                    return mock_hash

            mock_hashlib.sha256.side_effect = sha256_side_effect

            # Mock HTTP responses
            mock_head_response = Mock()
            mock_head_response.headers = {"last-modified": "2024-01-01"}
            mock_head_response.raise_for_status = Mock()

            mock_get_response = Mock()
            mock_get_response.content = b"pdf content"
            mock_get_response.raise_for_status = Mock()

            mock_requests.head.return_value = mock_head_response
            mock_requests.get.return_value = mock_get_response
            mock_requests.RequestException = requests.RequestException

            discoverer = MARPDocumentDiscoverer(storage_dir=tmpdir)

            urls = ["https://test.com/new-doc.pdf"]
            discoverer.process_documents(urls, correlation_id="corr-123")

        # Verify document was stored
        mock_storage.store_document.assert_called_once()
        store_call = mock_storage.store_document.call_args

        assert store_call[1]["document_id"] == "newdocid"  # keyword arg
        assert store_call[1]["pdf_content"] == b"pdf content"

    @patch("discoverer.DocumentStorage")
    @patch("discoverer.PDFLinkExtractor")
    @patch("discoverer.os.path.exists")
    @patch("discoverer.hashlib")
    @patch("discoverer.requests")
    def test_process_documents_unchanged_document(
        self,
        mock_requests,
        mock_hashlib,
        mock_exists,
        mock_extractor_class,
        mock_storage_class,
    ):
        """Test process_documents skips unchanged document."""
        from discoverer import MARPDocumentDiscoverer

        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock storage with existing document
            mock_storage = Mock()
            mock_storage.index = {
                "existingid": {
                    "url": "https://test.com/existing-doc.pdf",
                    "hash": "samehash456",
                }
            }
            mock_storage.base_path = tmpdir
            mock_storage_class.return_value = mock_storage
            mock_extractor_class.return_value = Mock()

            # Mock file exists
            mock_exists.return_value = True

            # Mock hash computation returns same hash
            def sha256_side_effect(data):
                if data == b"https://test.com/existing-doc.pdf":
                    mock_hash = Mock()
                    mock_hash.hexdigest.return_value = "existingid"
                    return mock_hash
                else:
                    mock_hash = Mock()
                    mock_hash.hexdigest.return_value = "samehash456"
                    return mock_hash

            mock_hashlib.sha256.side_effect = sha256_side_effect

            mock_head_response = Mock()
            mock_head_response.headers = {"last-modified": "2024-01-01"}
            mock_head_response.raise_for_status = Mock()
            mock_requests.head.return_value = mock_head_response
            mock_requests.RequestException = requests.RequestException

            discoverer = MARPDocumentDiscoverer(storage_dir=tmpdir)

            urls = ["https://test.com/existing-doc.pdf"]
            discoverer.process_documents(urls, correlation_id="corr-unchanged")

        # Should not store since document unchanged
        mock_storage.store_document.assert_not_called()

    @patch("discoverer.DocumentStorage")
    @patch("discoverer.PDFLinkExtractor")
    @patch("discoverer.os.path.exists")
    @patch("discoverer.hashlib")
    @patch("discoverer.requests")
    def test_process_documents_updated_document(
        self,
        mock_requests,
        mock_hashlib,
        mock_exists,
        mock_extractor_class,
        mock_storage_class,
    ):
        """Test process_documents handles updated document with different hash."""
        from discoverer import MARPDocumentDiscoverer

        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock storage with existing document
            mock_storage = Mock()
            mock_storage.index = {
                "updatedid": {
                    "url": "https://test.com/updated-doc.pdf",
                    "hash": "oldhash789",
                }
            }
            mock_storage.base_path = tmpdir
            mock_storage_class.return_value = mock_storage
            mock_extractor_class.return_value = Mock()

            mock_exists.return_value = True

            # Mock different hash
            def sha256_side_effect(data):
                if data == b"https://test.com/updated-doc.pdf":
                    mock_hash = Mock()
                    mock_hash.hexdigest.return_value = "updatedid"
                    return mock_hash
                else:
                    mock_hash = Mock()
                    mock_hash.hexdigest.return_value = "newhash999"
                    return mock_hash

            mock_hashlib.sha256.side_effect = sha256_side_effect

            mock_head_response = Mock()
            mock_head_response.headers = {"last-modified": "2024-02-01"}
            mock_head_response.raise_for_status = Mock()

            mock_get_response = Mock()
            mock_get_response.content = b"updated content"
            mock_get_response.raise_for_status = Mock()

            mock_requests.head.return_value = mock_head_response
            mock_requests.get.return_value = mock_get_response
            mock_requests.RequestException = requests.RequestException

            discoverer = MARPDocumentDiscoverer(storage_dir=tmpdir)

            urls = ["https://test.com/updated-doc.pdf"]
            discoverer.process_documents(urls, correlation_id="update-123")

        # Should store updated document
        mock_storage.store_document.assert_called_once()

    @patch("discoverer.DocumentStorage")
    @patch("discoverer.PDFLinkExtractor")
    @patch("discoverer.os.path.exists")
    @patch("discoverer.hashlib")
    @patch("discoverer.requests")
    def test_process_documents_download_failure(
        self,
        mock_requests,
        mock_hashlib,
        mock_exists,
        mock_extractor_class,
        mock_storage_class,
    ):
        """Test process_documents handles PDF download failure."""
        from discoverer import MARPDocumentDiscoverer

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_storage = Mock()
            mock_storage.index = {}
            mock_storage.base_path = tmpdir
            mock_storage_class.return_value = mock_storage
            mock_extractor_class.return_value = Mock()

            mock_exists.return_value = False

            # Hash generation succeeds
            mock_hash = Mock()
            mock_hash.hexdigest.return_value = "failid"
            mock_hashlib.sha256.return_value = mock_hash

            # head() succeeds but get() fails
            mock_head_response = Mock()
            mock_head_response.headers = {"last-modified": "2024-01-01"}
            mock_head_response.raise_for_status = Mock()
            mock_requests.head.return_value = mock_head_response
            mock_requests.get.side_effect = Exception("Download failed")
            mock_requests.RequestException = requests.RequestException

            discoverer = MARPDocumentDiscoverer(storage_dir=tmpdir)

            urls = ["https://test.com/broken.pdf"]
            discoverer.process_documents(urls, correlation_id="fail-123")

        # Should not store or publish
        mock_storage.store_document.assert_not_called()

    @patch("discoverer.DocumentStorage")
    @patch("discoverer.PDFLinkExtractor")
    @patch("discoverer.os.path.exists")
    @patch("discoverer.hashlib")
    @patch("discoverer.requests")
    def test_process_documents_multiple_urls(
        self,
        mock_requests,
        mock_hashlib,
        mock_exists,
        mock_extractor_class,
        mock_storage_class,
    ):
        """Test process_documents handles multiple URLs."""
        from discoverer import MARPDocumentDiscoverer

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_storage = Mock()
            mock_storage.index = {}
            mock_storage.base_path = tmpdir
            mock_storage_class.return_value = mock_storage
            mock_extractor_class.return_value = Mock()

            mock_exists.return_value = False

            # Mock hash - need 2 hashes per URL (doc_id + content hash)
            mock_hash = Mock()
            mock_hash.hexdigest.side_effect = [
                "id1",
                "hash1",
                "id2",
                "hash2",
                "id3",
                "hash3",
            ]
            mock_hashlib.sha256.return_value = mock_hash

            # Mock responses
            mock_head_response = Mock()
            mock_head_response.headers = {"last-modified": "2024-01-01"}
            mock_head_response.raise_for_status = Mock()
            mock_requests.head.return_value = mock_head_response

            mock_get_response = Mock()
            mock_get_response.content = b"content"
            mock_get_response.raise_for_status = Mock()
            mock_requests.get.return_value = mock_get_response
            mock_requests.RequestException = requests.RequestException

            discoverer = MARPDocumentDiscoverer(storage_dir=tmpdir)

            urls = [
                "https://test.com/doc1.pdf",
                "https://test.com/doc2.pdf",
                "https://test.com/doc3.pdf",
            ]

            discoverer.process_documents(urls, correlation_id="multi-123")

        # Should process all URLs
        assert mock_storage.store_document.call_count == 3

    @patch("discoverer.DocumentStorage")
    @patch("discoverer.PDFLinkExtractor")
    @patch("discoverer.os.path.exists")
    @patch("discoverer.hashlib")
    @patch("discoverer.requests")
    def test_discover_and_process_documents_integration(
        self,
        mock_requests,
        mock_hashlib,
        mock_exists,
        mock_extractor_class,
        mock_storage_class,
    ):
        """Test discover_and_process_documents combines discovery and processing."""
        from discoverer import MARPDocumentDiscoverer

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_storage = Mock()
            mock_storage.index = {}
            mock_storage.base_path = tmpdir
            mock_storage_class.return_value = mock_storage

            # Mock extractor
            mock_extractor = Mock()
            mock_extractor.get_pdf_urls.return_value = ["https://test.com/doc.pdf"]
            mock_extractor_class.return_value = mock_extractor

            mock_exists.return_value = False

            # Mock hash
            mock_hash = Mock()
            mock_hash.hexdigest.side_effect = ["docid", "dochash"]
            mock_hashlib.sha256.return_value = mock_hash

            # Mock page response
            mock_page_response = Mock()
            mock_page_response.text = "<html>page</html>"
            mock_page_response.status_code = 200
            mock_page_response.raise_for_status = Mock()

            # Mock PDF head response
            mock_head_response = Mock()
            mock_head_response.headers = {"last-modified": "2024-01-01"}
            mock_head_response.raise_for_status = Mock()

            # Mock PDF get response
            mock_get_response = Mock()
            mock_get_response.content = b"pdf"
            mock_get_response.raise_for_status = Mock()

            def request_side_effect(url, *args, **kwargs):
                if "doc.pdf" in url:
                    return mock_get_response
                return mock_page_response

            mock_requests.get.side_effect = request_side_effect
            mock_requests.head.return_value = mock_head_response
            mock_requests.RequestException = requests.RequestException

            discoverer = MARPDocumentDiscoverer(storage_dir=tmpdir)

            discoverer.discover_and_process_documents(correlation_id="integration-123")

        # Should have discovered and processed
        assert mock_storage.store_document.call_count >= 1
