# Local mock_storage fixture for API endpoint tests
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_storage():
    return MagicMock()


# flake8: noqa: E402
# above flake8 ignore is to allow imports after sys.path modification
"""Integration tests for ingestion flow - Mock-based approach for endpoint tests"""

import os
import sys

sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../services/ingestion/app")
    ),
)

import shutil
import tempfile
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

# Set up a temporary directory for storage (still needed for unit tests only)
TEMP_STORAGE_DIR = tempfile.mkdtemp()
os.environ["STORAGE_DIR"] = TEMP_STORAGE_DIR

from app import app, storage
from discoverer import MARPDocumentDiscoverer
from events import EventTypes
from extractor import PDFLinkExtractor
from storage import DocumentStorage

# --- Dependency Stubs/Mocks/Fakes for Fast, Isolated Tests ---


# Vector DB (Qdrant) Fake
class FakeQdrantClient:
    """Fake Qdrant client for testing without actual vector database"""

    def __init__(self):
        self.collections = {}
        self.points = {}

    def create_collection(self, collection_name, vectors_config):
        """Create a fake collection"""
        self.collections[collection_name] = {"vectors_config": vectors_config}
        self.points[collection_name] = []
        return True

    def upsert(self, collection_name, points):
        """Upsert points into fake collection"""
        if collection_name not in self.collections:
            raise ValueError(f"Collection {collection_name} does not exist")
        if collection_name not in self.points:
            self.points[collection_name] = []
        self.points[collection_name].extend(points)
        return True

    def search(self, collection_name, query_vector, limit=5):
        """Search fake collection"""
        if collection_name not in self.points:
            return []
        # Simple mock search - return all points up to limit
        return self.points[collection_name][:limit]

    def get_collection(self, collection_name):
        """Get collection info"""
        if collection_name in self.collections:
            return self.collections[collection_name]
        return None


# RabbitMQ Fake/Mock (in-memory queue)
class FakeRabbitMQ:
    """Fake RabbitMQ for testing event publishing"""

    def __init__(self):
        self.queue = []
        self.connected = True

    def publish_event(self, event_type, event, correlation_id=None):
        """Publish event to in-memory queue"""
        self.queue.append((event_type, event, correlation_id))
        return True

    def get_events(self):
        """Get all published events"""
        return self.queue

    def _ensure_connection(self):
        """Mock connection check"""
        return self.connected

    def clear_queue(self):
        """Clear all events"""
        self.queue = []


# --- Pytest Fixtures ---


@pytest.fixture
def temp_storage_dir():
    """Create a temporary directory for document storage"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def fake_rabbitmq():
    """Provide a fake RabbitMQ instance"""
    return FakeRabbitMQ()


@pytest.fixture
def fake_qdrant():
    """Provide a fake Qdrant client"""
    return FakeQdrantClient()


@pytest.fixture
def document_storage(temp_storage_dir):
    """Create a real DocumentStorage instance with temporary directory for integration tests."""
    from services.ingestion.app.storage import DocumentStorage

    if DocumentStorage is None:
        pytest.skip("DocumentStorage not importable")
    return DocumentStorage(temp_storage_dir)


@pytest.fixture
def sample_pdf_content():
    """Sample PDF content for testing"""
    return (
        b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<\n/Type /Catalog\n"
        b"/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n"
        b"/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n"
        b"/Type /Page\n/Parent 2 0 R\n/Resources <<\n/Font <<\n"
        b"/F1 4 0 R\n>>\n>>\n/MediaBox [0 0 612 792]\n"
        b"/Contents 5 0 R\n>>\nendobj\n4 0 obj\n<<\n/Type /Font\n"
        b"/Subtype /Type1\n/BaseFont /Helvetica\n>>\nendobj\n5 0 obj\n"
        b"<<\n/Length 44\n>>\nstream\nBT\n/F1 12 Tf\n100 700 Td\n"
        b"(Test PDF) Tj\nET\nendstream\nendobj\nxref\n0 6\n"
        b"0000000000 65535 f\n0000000015 00000 n\n"
        b"0000000068 00000 n\n0000000125 00000 n\n"
        b"0000000277 00000 n\n0000000356 00000 n\ntrailer\n<<\n"
        b"/Size 6\n/Root 1 0 R\n>>\nstartxref\n449\n%%EOF"
    )


@pytest.fixture
def sample_html_with_pdfs():
    """Sample HTML content with PDF links"""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>MARP Documents</title></head>
    <body>
        <h1>Manual of Academic Regulations and Procedures</h1>
        <div class="content">
            <a href="/documents/general-regulations.pdf">
                General Regulations</a>
            <a href="/documents/assessment-framework.pdf">
                Assessment Framework</a>
            <a href="https://lancaster.ac.uk/docs/student-handbook.pdf">
                Student Handbook</a>
            <a href="/documents/not-a-pdf.html">Not a PDF</a>
        </div>
    </body>
    </html>
    """


# Clean the global TEMP_STORAGE_DIR before and after EVERY test
@pytest.fixture(autouse=True)
def clean_global_storage():
    """Clear the global TEMP_STORAGE_DIR before and after every test"""
    # Clear BEFORE the test
    if os.path.exists(TEMP_STORAGE_DIR):
        for filename in os.listdir(TEMP_STORAGE_DIR):
            file_path = os.path.join(TEMP_STORAGE_DIR, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception:
                pass
    yield
    # Clear AFTER the test
    if os.path.exists(TEMP_STORAGE_DIR):
        for filename in os.listdir(TEMP_STORAGE_DIR):
            file_path = os.path.join(TEMP_STORAGE_DIR, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception:
                pass


@pytest.fixture
def mock_http_responses(sample_pdf_content):
    """Mock HTTP responses for document discovery"""

    def mock_get(url, *args, **kwargs):
        response = Mock()
        response.status_code = 200

        if url.endswith(".pdf"):
            response.content = sample_pdf_content
            response.headers = {
                "content-type": "application/pdf",
                "content-length": str(len(sample_pdf_content)),
                "last-modified": "Wed, 27 Nov 2024 12:00:00 GMT",
            }
        else:
            response.content = b"<html><body>Test</body></html>"
            response.headers = {"content-type": "text/html"}

        response.raise_for_status = Mock()
        return response

    def mock_head(url, *args, **kwargs):
        response = Mock()
        response.status_code = 200
        response.headers = {
            "last-modified": "Wed, 27 Nov 2024 12:00:00 GMT",
            "content-type": "application/pdf",
        }
        response.raise_for_status = Mock()
        return response

    return {"get": mock_get, "head": mock_head}


# --- Unit Tests for Components ---


@pytest.mark.skipif(PDFLinkExtractor is None, reason="PDFLinkExtractor not importable")
def test_pdf_link_extractor(sample_html_with_pdfs):
    """Test PDF link extraction from HTML"""
    # Explicitly import the real PDFLinkExtractor
    from services.ingestion.app.extractor import PDFLinkExtractor

    extractor = PDFLinkExtractor("https://lancaster.ac.uk/marp/")
    urls = extractor.get_pdf_urls(sample_html_with_pdfs)

    assert isinstance(urls, list)
    assert len(urls) == 3
    assert all(url.endswith(".pdf") for url in urls)
    assert any("general-regulations.pdf" in url for url in urls)
    assert any("assessment-framework.pdf" in url for url in urls)
    assert any("student-handbook.pdf" in url for url in urls)


@pytest.mark.skipif(DocumentStorage is None, reason="DocumentStorage not importable")
def test_document_storage_store_and_retrieve(document_storage, sample_pdf_content):
    """Test storing and retrieving documents"""
    doc_id = "test-doc-001"
    metadata = {
        "url": "https://example.com/test.pdf",
        "hash": "abc123",
        "date": "2024-11-27T12:00:00",
        "correlation_id": "test-correlation-id",
    }

    # Store document
    success = document_storage.store_document(doc_id, sample_pdf_content, metadata)
    assert success

    # Retrieve document
    retrieved_pdf = document_storage.get_pdf(doc_id)
    assert retrieved_pdf == sample_pdf_content

    # Check index
    documents = document_storage.list_documents()
    assert len(documents) == 1
    assert documents[0]["document_id"] == doc_id
    assert documents[0]["url"] == metadata["url"]


@pytest.mark.skipif(DocumentStorage is None, reason="DocumentStorage not importable")
def test_document_storage_delete(document_storage, sample_pdf_content):
    """Test deleting documents"""
    doc_id = "test-doc-delete"
    metadata = {
        "url": "https://example.com/delete.pdf",
        "hash": "def456",
        "date": "2024-11-27T12:00:00",
        "correlation_id": "test-correlation-id",
    }

    # Store and delete
    document_storage.store_document(doc_id, sample_pdf_content, metadata)
    success = document_storage.delete_document(doc_id)
    assert success

    # Verify deletion
    documents = document_storage.list_documents()
    assert len(documents) == 0
    assert document_storage.get_pdf(doc_id) is None


@pytest.mark.skipif(DocumentStorage is None, reason="DocumentStorage not importable")
def test_document_storage_update(document_storage, sample_pdf_content):
    """Test updating existing document"""
    doc_id = "test-doc-update"
    metadata_v1 = {
        "url": "https://example.com/update.pdf",
        "hash": "hash-v1",
        "date": "2024-11-27T12:00:00",
        "correlation_id": "corr-1",
    }

    metadata_v2 = {
        "url": "https://example.com/update.pdf",
        "hash": "hash-v2",
        "date": "2024-11-28T12:00:00",
        "correlation_id": "corr-2",
    }

    # Store initial version
    document_storage.store_document(doc_id, sample_pdf_content, metadata_v1)

    # Update with new version
    new_content = sample_pdf_content + b"\n% Updated"
    document_storage.store_document(doc_id, new_content, metadata_v2)

    # Verify update
    retrieved_pdf = document_storage.get_pdf(doc_id)
    assert retrieved_pdf == new_content

    documents = document_storage.list_documents()
    assert len(documents) == 1
    assert documents[0]["hash"] == "hash-v2"


# --- Integration Tests for Ingestion Flow ---


@pytest.mark.skipif(
    MARPDocumentDiscoverer is None, reason="MARPDocumentDiscoverer not importable"
)
def test_document_discoverer_skip_unchanged(
    temp_storage_dir, mock_http_responses, sample_pdf_content
):
    """Test that unchanged documents are skipped"""
    with (
        patch("discoverer.requests.get", side_effect=mock_http_responses["get"]),
        patch("discoverer.requests.head", side_effect=mock_http_responses["head"]),
    ):

        discoverer = MARPDocumentDiscoverer(temp_storage_dir)
        correlation_id = "test-correlation-002"
        test_url = "https://lancaster.ac.uk/docs/test.pdf"

        # First discovery - should process
        discovered_docs_1 = discoverer.process_documents([test_url], correlation_id)
        assert len(discovered_docs_1) == 1

        # Second discovery - should skip (same hash)
        discovered_docs_2 = discoverer.process_documents([test_url], correlation_id)
        assert len(discovered_docs_2) == 0


@pytest.mark.skipif(
    MARPDocumentDiscoverer is None, reason="MARPDocumentDiscoverer not importable"
)
def test_document_discoverer_detect_update(
    temp_storage_dir, mock_http_responses, sample_pdf_content
):
    """Test that document updates are detected"""
    call_count = [0]

    def mock_head_changing(url, *args, **kwargs):
        response = Mock()
        response.status_code = 200
        call_count[0] += 1
        # Change last-modified header on second call
        response.headers = {
            "last-modified": f"Wed, 27 Nov 2024 12:00:0{call_count[0]} GMT",
            "content-type": "application/pdf",
        }
        response.raise_for_status = Mock()
        return response

    with (
        patch("discoverer.requests.get", side_effect=mock_http_responses["get"]),
        patch("discoverer.requests.head", side_effect=mock_head_changing),
    ):

        discoverer = MARPDocumentDiscoverer(temp_storage_dir)
        correlation_id = "test-correlation-003"
        test_url = "https://lancaster.ac.uk/docs/test.pdf"

        # First discovery
        discovered_docs_1 = discoverer.process_documents([test_url], correlation_id)
        assert len(discovered_docs_1) == 1

        # Second discovery with changed hash - should process again
        discovered_docs_2 = discoverer.process_documents([test_url], correlation_id)
        assert len(discovered_docs_2) == 1


# --- FastAPI Endpoint Integration Tests ---


@pytest.mark.skipif(app is None, reason="FastAPI app not importable")
def test_api_home():
    """Test home endpoint"""
    with patch("services.ingestion.app.app.event_publisher", MagicMock()):
        client = TestClient(app)
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Ingestion Service" in resp.json()["message"]


@pytest.mark.skipif(app is None, reason="FastAPI app not importable")
def test_api_health():
    """Test health endpoint"""
    with patch("services.ingestion.app.app.event_publisher", MagicMock()):
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code in (200, 503)
        assert "status" in resp.json()
        assert "rabbitmq" in resp.json()["dependencies"]


@pytest.mark.skipif(app is None, reason="FastAPI app not importable")
def test_api_documents_empty(mock_storage):
    """Test documents endpoint with empty storage"""
    mock_storage.list_documents.return_value = []
    with patch("app.storage", mock_storage):
        client = TestClient(app)
        resp = client.get("/documents")
        assert resp.status_code == 200
        assert "documents" in resp.json()
        assert resp.json()["documents"] == []


@pytest.mark.skipif(app is None, reason="FastAPI app not importable")
def test_api_documents_list(mock_storage):
    """Test listing documents"""
    doc_id = "test-doc-api"
    mock_storage.list_documents.return_value = [
        {
            "document_id": doc_id,
            "url": "https://example.com/test.pdf",
            "hash": "abc123",
            "date": "2024-11-27T12:00:00",
            "correlation_id": "test-corr",
        }
    ]
    with patch("app.storage", mock_storage):
        client = TestClient(app)
        resp = client.get("/documents")
        assert resp.status_code == 200
        docs = resp.json()["documents"]
        assert len(docs) == 1
        assert docs[0]["document_id"] == doc_id


@pytest.mark.skipif(app is None, reason="FastAPI app not importable")
def test_api_document_download(mock_storage, sample_pdf_content, tmp_path):
    """Test document download endpoint"""
    doc_id = "test-doc-download"
    # Create a temporary PDF file
    test_pdf = tmp_path / f"{doc_id}.pdf"
    test_pdf.write_bytes(sample_pdf_content)
    mock_storage.get_pdf_path.return_value = str(test_pdf)
    with patch("app.storage", mock_storage):
        client = TestClient(app)
        resp = client.get(f"/documents/{doc_id}")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert sample_pdf_content in resp.content


@pytest.mark.skipif(app is None, reason="FastAPI app not importable")
def test_api_document_download_not_found(mock_storage):
    """Test document download with non-existent document"""
    mock_storage.get_pdf_path.return_value = None
    with patch("app.storage", mock_storage):
        client = TestClient(app)
        resp = client.get("/documents/nonexistent-doc")
        assert resp.status_code == 404


@pytest.mark.skipif(app is None, reason="FastAPI app not importable")
def test_api_discovery_start(mock_storage):
    """Test discovery start endpoint"""
    mock_rabbitmq = MagicMock()
    mock_discoverer = MagicMock()
    with (
        patch("app.storage", mock_storage),
        patch("app.event_publisher", mock_rabbitmq),
        patch("app.document_discoverer", mock_discoverer),
    ):
        client = TestClient(app)
        resp = client.post("/discovery/start")
        assert resp.status_code == 200
        assert "discovery started" in resp.json()["message"].lower()
        assert resp.json()["job_status"] == "running"


# --- Edge Case Tests ---


def test_fake_qdrant_create_collection(fake_qdrant):
    """Test fake Qdrant collection creation"""
    success = fake_qdrant.create_collection(
        "test_collection", {"size": 384, "distance": "Cosine"}
    )
    assert success
    assert "test_collection" in fake_qdrant.collections


def test_fake_qdrant_upsert_and_search(fake_qdrant):
    """Test fake Qdrant upsert and search"""
    fake_qdrant.create_collection("test_collection", {"size": 384})

    # Upsert points
    points = [
        {"id": "1", "vector": [0.1, 0.2, 0.3], "payload": {"text": "test1"}},
        {"id": "2", "vector": [0.4, 0.5, 0.6], "payload": {"text": "test2"}},
    ]
    fake_qdrant.upsert("test_collection", points)

    # Search
    results = fake_qdrant.search("test_collection", [0.1, 0.2, 0.3], limit=2)
    assert len(results) == 2


def test_fake_rabbitmq_publish_and_retrieve(fake_rabbitmq):
    """Test fake RabbitMQ event publishing and retrieval"""
    if EventTypes is None:
        pytest.skip("EventTypes not importable")

    event = {"document_id": "test-doc", "url": "https://example.com/test.pdf"}
    correlation_id = "test-corr-123"

    success = fake_rabbitmq.publish_event(
        EventTypes.DOCUMENT_DISCOVERED, event, correlation_id
    )
    assert success

    events = fake_rabbitmq.get_events()
    assert len(events) == 1
    assert events[0][0] == EventTypes.DOCUMENT_DISCOVERED
    assert events[0][2] == correlation_id


@pytest.mark.skipif(DocumentStorage is None, reason="DocumentStorage not importable")
def test_storage_corrupted_index():
    """Test handling of corrupted index file"""
    # Create corrupted index
    index_path = os.path.join(TEMP_STORAGE_DIR, "documents", "discovered_docs.json")
    os.makedirs(os.path.dirname(index_path), exist_ok=True)
    with open(index_path, "w") as f:
        f.write("{ corrupted json }")

    # Storage should handle gracefully
    storage = DocumentStorage(TEMP_STORAGE_DIR)
    documents = storage.list_documents()
    assert documents == []


@pytest.mark.skipif(DocumentStorage is None, reason="DocumentStorage not importable")
def test_storage_concurrent_access(sample_pdf_content):
    """Test thread-safe storage access"""
    import threading

    storage = DocumentStorage(TEMP_STORAGE_DIR)
    errors = []

    def store_doc(doc_id):
        try:
            metadata = {
                "url": f"https://example.com/{doc_id}.pdf",
                "hash": f"hash-{doc_id}",
                "date": "2024-11-27T12:00:00",
                "correlation_id": "test-corr",
            }
            storage.store_document(doc_id, sample_pdf_content, metadata)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=store_doc, args=(f"doc-{i}",)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    documents = storage.list_documents()
    assert len(documents) == 5
