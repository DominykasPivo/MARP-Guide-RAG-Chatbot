"""
End-to-end tests for document processing pipeline.

Tests the complete document workflow:
Ingestion → Extraction → Indexing
"""

import time

import pytest


class TestDocumentIngestionFlow:
    """Test document ingestion end-to-end flow."""

    def test_ingestion_health(self, ingestion_client):
        """Test ingestion service is healthy."""
        response = ingestion_client.health()

        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_discover_documents(self, ingestion_client):
        """Test document discovery endpoint."""
        response = ingestion_client.post("/discover", json={"source": "local"})

        assert response.status_code in [200, 202]
        # May return immediate results or accept for processing

    @pytest.mark.skip(reason="Requires actual PDF files in data directory")
    def test_upload_document(self, ingestion_client, sample_pdf):
        """Test document upload workflow."""
        with open(sample_pdf, "rb") as f:
            files = {"file": ("test.pdf", f, "application/pdf")}
            response = ingestion_client.post("/upload", files=files)

        assert response.status_code in [200, 201, 202]


class TestExtractionFlow:
    """Test document extraction end-to-end flow."""

    def test_extraction_health(self, extraction_client):
        """Test extraction service is healthy."""
        response = extraction_client.health()

        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    @pytest.mark.skip(reason="Requires integration with ingestion service")
    def test_extract_document(self, extraction_client, sample_pdf):
        """Test PDF extraction workflow."""
        # This would typically be triggered by ingestion service via RabbitMQ
        # For E2E test, we'd need to verify the end-to-end event flow
        pass


class TestIndexingFlow:
    """Test document indexing end-to-end flow."""

    def test_indexing_health(self, indexing_client):
        """Test indexing service is healthy."""
        response = indexing_client.health()

        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    @pytest.mark.skip(reason="Requires integration with extraction service")
    def test_index_document(self, indexing_client):
        """Test document indexing workflow."""
        # This would typically be triggered by extraction service via RabbitMQ
        # For E2E test, we'd need to verify the end-to-end event flow
        pass


class TestFullDocumentPipeline:
    """Test complete document pipeline end-to-end."""

    @pytest.mark.skip(reason="Requires full pipeline setup with sample documents")
    def test_end_to_end_document_processing(
        self,
        ingestion_client,
        extraction_client,
        indexing_client,
        retrieval_client,
        sample_pdf,
    ):
        """
        Test complete document processing pipeline:
        1. Upload document via ingestion
        2. Wait for extraction to complete
        3. Wait for indexing to complete
        4. Verify document is searchable via retrieval
        """
        # 1. Upload document
        with open(sample_pdf, "rb") as f:
            files = {"file": ("test.pdf", f, "application/pdf")}
            response = ingestion_client.post("/upload", files=files)

        assert response.status_code in [200, 201, 202]
        doc_id = response.json().get("doc_id") or response.json().get("document_id")

        # 2. Wait for processing (polling or event-based)
        max_wait = 30
        start_time = time.time()

        while time.time() - start_time < max_wait:
            # Check if document is indexed
            response = retrieval_client.post(
                "/search", json={"query": "test", "top_k": 5}
            )

            if response.status_code == 200:
                results = response.json()
                # Check if our document appears in results
                if any(r.get("doc_id") == doc_id for r in results.get("results", [])):
                    break

            time.sleep(2)
        else:
            pytest.fail("Document processing timed out")

        # 3. Verify document is searchable
        response = retrieval_client.post("/search", json={"query": "MARP", "top_k": 10})

        assert response.status_code == 200
        results = response.json()
        assert len(results.get("results", [])) > 0


class TestServiceHealthChecks:
    """Test all document pipeline services are healthy."""

    def test_all_services_healthy(
        self,
        ingestion_client,
        extraction_client,
        indexing_client,
        retrieval_client,
    ):
        """Verify all document pipeline services are running and healthy."""
        services = [
            ("Ingestion", ingestion_client),
            ("Extraction", extraction_client),
            ("Indexing", indexing_client),
            ("Retrieval", retrieval_client),
        ]

        for service_name, client in services:
            response = client.health()
            assert response.status_code == 200, f"{service_name} service is not healthy"
            assert response.json()["status"] in [
                "healthy",
                "ok",
            ], f"{service_name} returned bad status"
