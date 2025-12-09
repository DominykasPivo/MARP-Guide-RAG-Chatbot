"""
Unit tests for the ingestion service FastAPI application.

Target: services/ingestion/app/app.py
Coverage: 87 statements at 0%

This file tests:
- FastAPI endpoints (/, /health, /documents, /documents/{id}, /discovery/start)
- Background discovery functionality
- Error handling
"""

import sys
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient


class TestIngestionAppEndpoints:
    """Test FastAPI endpoints in ingestion service."""

    def test_home_endpoint(self):
        """Test GET / returns service running message."""
        from services.ingestion.app.app import app

        client = TestClient(app)
        response = client.get("/")

        assert response.status_code == 200
        assert response.json() == {"message": "Ingestion Service is running"}

    def test_health_endpoint_healthy(self):
        """Test /health returns healthy when RabbitMQ is up."""
        from services.ingestion.app.app import app, event_publisher

        # Mock RabbitMQ health check
        event_publisher._ensure_connection = Mock(return_value=True)

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "ingestion"
        assert data["status"] == "healthy"
        assert data["dependencies"]["rabbitmq"] == "healthy"

    def test_health_endpoint_unhealthy(self):
        """Test /health returns unhealthy when RabbitMQ is down."""
        from services.ingestion.app.app import app, event_publisher

        # Mock RabbitMQ health check failure
        event_publisher._ensure_connection = Mock(return_value=False)

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["dependencies"]["rabbitmq"] == "unhealthy"

    def test_list_documents_success(self):
        """Test GET /documents lists all documents."""
        from services.ingestion.app.app import app, storage

        # Mock storage list_documents
        mock_docs = [
            {"id": "doc-1", "title": "Test Doc 1"},
            {"id": "doc-2", "title": "Test Doc 2"},
        ]
        storage.list_documents = Mock(return_value=mock_docs)

        client = TestClient(app)
        response = client.get("/documents")

        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        assert isinstance(data["documents"], list)
        assert data["documents"] == mock_docs

    def test_list_documents_error(self):
        """Test GET /documents handles storage errors."""
        from services.ingestion.app.app import app, storage

        # Mock storage to raise exception
        storage.list_documents = Mock(side_effect=Exception("Storage error"))

        client = TestClient(app)
        response = client.get("/documents")

        assert response.status_code == 500
        assert "Failed to list documents" in response.json()["detail"]

    def test_get_document_success(self):
        """Test GET /documents/{id} returns document file."""
        import os

        # Create a temporary test file
        import tempfile

        from services.ingestion.app.app import app, storage

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(b"PDF content")
                tmp_path = tmp.name

            # Mock storage get_pdf_path
            storage.get_pdf_path = Mock(return_value=tmp_path)

            client = TestClient(app)
            response = client.get("/documents/doc-123")

            assert response.status_code == 200
            assert response.headers["content-type"] == "application/pdf"
            assert "attachment" in response.headers["content-disposition"]
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_get_document_not_found(self):
        """Test GET /documents/{id} returns 404 when document doesn't exist."""
        from services.ingestion.app.app import app, storage

        # Mock storage to return non-existent path
        storage.get_pdf_path = Mock(return_value=None)

        client = TestClient(app)
        response = client.get("/documents/nonexistent")

        assert response.status_code == 404
        assert "Document not found" in response.json()["detail"]

    def test_start_discovery_success(self):
        """Test POST /discovery/start triggers background discovery."""
        from services.ingestion.app.app import app, document_discoverer

        # Mock discoverer and event publisher
        mock_docs = [{"id": "doc-1", "title": "Found Doc"}]
        document_discoverer.discover_and_process_documents = Mock(
            return_value=mock_docs
        )
        sys.modules["events"].publish_document_discovered_event.return_value = True

        client = TestClient(app)
        response = client.post("/discovery/start")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Document discovery started in background"
        assert data["job_status"] == "running"

    def test_start_discovery_with_error(self):
        """Test POST /discovery/start handles discovery errors gracefully."""
        from services.ingestion.app.app import app, document_discoverer

        # Mock discoverer to raise exception
        document_discoverer.discover_and_process_documents = Mock(
            side_effect=Exception("Discovery failed")
        )

        client = TestClient(app)
        response = client.post("/discovery/start")

        # Should still return 200 since it's a background task
        assert response.status_code == 200
        assert response.json()["job_status"] == "running"


class TestIngestionBackgroundTasks:
    """Test background discovery functionality."""

    @patch("services.ingestion.app.app.threading.Thread")
    def test_run_discovery_background(self, mock_thread):
        """Test run_discovery_background starts daemon thread."""
        from services.ingestion.app.app import run_discovery_background

        run_discovery_background()

        # Verify thread was created with daemon=True
        mock_thread.assert_called_once()
        call_kwargs = mock_thread.call_args[1]
        assert call_kwargs["daemon"] is True

    @patch("services.ingestion.app.app.run_discovery_background")
    def test_startup_event_handler(self, mock_run_discovery):
        """Test startup event handler calls run_discovery_background."""
        from services.ingestion.app.app import start_background_discovery

        start_background_discovery()

        mock_run_discovery.assert_called_once()
