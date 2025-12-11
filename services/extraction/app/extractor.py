"""PDF text extraction."""

import json
import logging
import os
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

import magic
import pdfplumber
import pika
import pypdf

logger = logging.getLogger("extraction.extractor")


class PDFExtractor:
    """PDF text and metadata extraction."""

    def check_file_type(self, file_path: str) -> str:
        """Return file MIME type."""
        try:
            mime_type = magic.from_file(file_path, mime=True)
            return str(mime_type)
        except Exception as e:
            logger.error(f"File type check failed: {str(e)}")
            raise

    def extract_document(self, file_path: str, source_url: str) -> Dict:
        """Extract per-page text and metadata."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        if self.check_file_type(file_path) != "application/pdf":
            raise ValueError(f"File is not a PDF: {self.check_file_type(file_path)}")

        try:
            page_texts = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    cleaned = self._basic_clean(text)
                    page_texts.append(cleaned)

            metadata = self._extract_metadata(file_path, source_url)
            return {"page_texts": page_texts, "metadata": metadata}
        except Exception as e:
            logger.error(f"Document extraction failed: {str(e)}")
            raise

    def _basic_clean(self, text: str) -> str:
        """Basic normalization for OCR artifacts."""
        text = re.sub(r"\s+", " ", text)
        text = text.replace("|", "I")
        text = re.sub(r"(?<=[a-z])\.(?=[A-Z])", ". ", text)
        return text.strip()

    def _extract_metadata(self, file_path: str, source_url: str) -> Dict:
        """Extract metadata from PDF."""
        try:
            with open(file_path, "rb") as file:
                reader = pypdf.PdfReader(file)
                info = reader.metadata if reader.metadata else {}
                page_count = len(reader.pages)
                return {
                    "title": info.get("/Title", os.path.basename(file_path)),
                    "pageCount": page_count,
                    "sourceUrl": source_url,
                }
        except Exception as e:
            logger.error(f"Metadata extraction failed: {str(e)}")
            return {
                "title": os.path.basename(file_path),
                "pageCount": 0,
                "sourceUrl": source_url,
            }

    def _parse_pdf_date(self, date_str: Optional[str]) -> Optional[str]:
        """Parse PDF date to ISO format."""
        if not date_str:
            return None
        try:
            date_str = date_str.replace("D:", "")[:14]
            date = datetime.strptime(date_str, "%Y%m%d%H%M%S")
            return date.isoformat()
        except Exception:
            return None


class ExtractionService:
    """Service for PDF extraction and event publishing."""

    def __init__(self, rabbitmq_host: str = "rabbitmq"):
        from rabbitmq import EventConsumer

        self.consumer = EventConsumer(rabbitmq_host)
        self.extractor = PDFExtractor()
        self.ingestion_url = os.getenv("INGESTION_SERVICE_URL", "http://ingestion:8000")

    def _handle_event(self, ch, method, properties, body):
        """Top-level event handler."""
        self._handle_document_wrapper(ch, method, properties, body)

    def start(self):
        from events import EventTypes

        logger.info("Starting extraction service")
        if self.consumer.subscribe(EventTypes.DOCUMENT_DISCOVERED.value, self._handle_event):
            self.consumer.start_consuming()
        else:
            raise RuntimeError("Event subscription failed")

    def _handle_document_wrapper(self, ch, method, properties, body):
        """Ensure correlation ID and delegate to handler."""
        correlation_id = (
            properties.correlation_id if properties and properties.correlation_id else str(uuid.uuid4())
        )

        if not properties or not properties.correlation_id:
            logger.warning(
                "Missing correlation ID in message; generated new one",
                extra={"correlation_id": correlation_id, "routing_key": (method.routing_key if method else None)},
            )
            properties = pika.BasicProperties(
                correlation_id=correlation_id,
                content_type=properties.content_type if properties else None,
                delivery_mode=2,
            )

        self.handle_document(ch, method, properties, body)

    def handle_document(self, ch, method, properties, body):
        from events import DocumentDiscovered, EventTypes

        """Handle document.discovered event."""
        correlation_id = (
            properties.correlation_id if properties and properties.correlation_id else str(uuid.uuid4())
        )
        logger.info("Handling document", extra={"correlation_id": correlation_id})

        try:
            message = json.loads(body)
            event_data = message.get("data", {})

            logger.info("Handling document", extra={"correlation_id": correlation_id})

            discovered = DocumentDiscovered(
                eventType=message["eventType"],
                eventId=message["eventId"],
                timestamp=message["timestamp"],
                correlationId=message["correlationId"],
                source=message["source"],
                version=message["version"],
                payload=message["payload"],
            )

            logger.info(
                "Processing document",
                extra={
                    "correlation_id": discovered.correlationId,
                    "document_id": discovered.payload["documentId"],
                    "source_url": discovered.payload["sourceUrl"],
                    "discovered_at": discovered.payload["discoveredAt"],
                },
            )

            logger.debug("Discovered event parsed")

            start_time = time.time()
            file_path = discovered.payload["filePath"]
            result = self.extractor.extract_document(file_path, discovered.payload.get("sourceUrl"))
            extracted_file_time = datetime.now(timezone.utc).isoformat()
            processing_time = (time.time() - start_time) * 1000

            metadata = result.get("metadata", {})
            page_count = metadata.get("pageCount")
            event_version = os.getenv("EVENT_VERSION", "1.0")
            time_now = datetime.now(timezone.utc).isoformat()

            fileType = self.extractor.check_file_type(file_path)
            fileType = fileType.split("/")[-1]

            event_data = {
                "eventType": "DocumentExtracted",
                "eventId": str(uuid.uuid4()),
                "timestamp": time_now,
                "correlationId": correlation_id,
                "source": "extraction-service",
                "version": event_version,
                "payload": {
                    "documentId": discovered.payload.get("documentId"),
                    "textContent": "\n\n".join(result.get("page_texts", [])),
                    "page_texts": result.get("page_texts", []),
                    "fileType": fileType,
                    "metadata": {
                        "title": metadata.get("title", "Unknown Title"),
                        "sourceUrl": discovered.payload.get("sourceUrl", "Unknown Source"),
                        "pageCount": page_count,
                    },
                    "extractedAt": extracted_file_time,
                },
            }

            logger.info("Prepared DocumentExtracted event")
            if self.consumer.publish(
                "document.extracted",
                EventTypes.DOCUMENT_EXTRACTED.value,
                event_data,
                correlation_id=correlation_id,
            ):
                logger.info(
                    "Document extraction completed",
                    extra={
                        "correlation_id": correlation_id,
                        "document_id": discovered.payload["documentId"],
                        "title": metadata.get("title", "Unknown Title"),
                        "page_count": page_count,
                        "processing_time_ms": processing_time,
                    },
                )
            else:
                logger.error(
                    "Publish failed",
                    extra={"document_id": discovered.document_id, "error": "RabbitMQ publish failed"},
                )

        except Exception as e:
            logger.error(
                "Document processing failed",
                extra={
                    "correlation_id": (correlation_id if "correlation_id" in locals() else None),
                    "document_id": (event_data.get("document_id") if "event_data" in locals() else None),
                    "error": str(e),
                },
                exc_info=True,
            )