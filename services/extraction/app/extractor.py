"""PDF text extraction functionality."""
import os
from datetime import datetime, timezone
import time
import re
from typing import Dict, Optional
import magic
import pypdf
import pdfplumber
import logging
import pika
import uuid
import json


# Configure logging
logger = logging.getLogger('extraction.extractor')


class PDFExtractor:
    """Handles PDF text and metadata extraction."""

    def check_file_type(self, file_path: str) -> str:
        """Check the file type and return its MIME type."""
        try:
            mime_type = magic.from_file(file_path, mime=True)
            return mime_type
        except Exception as e:
            logger.error(f"Failed to check file type: {str(e)}")
            raise
    
    def extract_document(self, file_path: str, source_url: str) -> Dict:
        """Extract text and metadata from a PDF document using pdfplumber, returning per-page text blocks for semantic chunking.
        Args:
            file_path: Path to the PDF file
            source_url: URL of the document source
        Returns:
            Dictionary containing:
                - page_texts: List of cleaned text blocks, one per page
                - metadata: Document metadata
        Raises:
            ValueError: If file is not a valid PDF
            FileNotFoundError: If file does not exist
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        if self.check_file_type(file_path) != 'application/pdf':
            raise ValueError(f"File is not a PDF: {self.check_file_type(file_path)}")
    

        try:
            # Extract text per page using pdfplumber
            page_texts = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    cleaned = self._basic_clean(text)
                    page_texts.append(cleaned)

            # Extract metadata using PyPDF2
            metadata = self._extract_metadata(file_path, source_url)

            return {
                "page_texts": page_texts,
                "metadata": metadata
            }

        except Exception as e:
            logger.error(f"Failed to extract document: {str(e)}")
            raise
            
    def _basic_clean(self, text: str) -> str:
        """Perform basic text cleaning for OCR artifacts.
        
        Args:
            text: Raw text to clean
            
        Returns:
            Cleaned text
        """
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Fix common OCR artifacts
        text = text.replace('|', 'I')  # Common I/| confusion
        text = re.sub(r'(?<=[a-z])\.(?=[A-Z])', '. ', text)  # Fix missing space after period
        
        return text.strip()

    def _extract_metadata(self, file_path: str, source_url: str) -> Dict:
        """Extract metadata from PDF file.
        
        Args:
            file_path: Path to the PDF file
            source_url: URL of the document source
            
        Returns:
            Dictionary containing metadata fields
        """
        try:
            with open(file_path, 'rb') as file:
                reader = pypdf.PdfReader(file)
                # Get basic metadata
                info = reader.metadata if reader.metadata else {}
                page_count = len(reader.pages)
                return {
                    "title": info.get('/Title', os.path.basename(file_path)),
                    "pageCount": page_count,
                    "sourceUrl": source_url
                }

        except Exception as e:
            logger.error(f"Failed to extract metadata: {str(e)}")
            return {
                "title": os.path.basename(file_path),
                "pageCount": 0,
                "sourceUrl": source_url
            }
            
    def _parse_pdf_date(self, date_str: Optional[str]) -> Optional[str]:
        """Parse PDF date string into ISO format.
        
        Args:
            date_str: PDF date string or None
            
        Returns:
            ISO formatted date string or None
        """
        if not date_str:
            return None
            
        try:
            # Remove 'D:' prefix and timezone if present
            date_str = date_str.replace('D:', '')[:14]
            # Parse date
            date = datetime.strptime(date_str, '%Y%m%d%H%M%S')
            # Return ISO format
            return date.isoformat()
        except Exception:
            return None
        

class ExtractionService:
    """Service for extracting text and metadata from documents."""
    
    

    def __init__(self, rabbitmq_host: str = 'rabbitmq'):
        """Initialize the service.
        
        Args:
            rabbitmq_host: Hostname of the RabbitMQ server
        """
        from rabbitmq import EventConsumer
        self.consumer = EventConsumer(rabbitmq_host)
        self.extractor = PDFExtractor()
        self.ingestion_url = os.getenv('INGESTION_SERVICE_URL', 'http://ingestion:8000')
        
    def _handle_event(self, ch, method, properties, body):
        """Handle incoming RabbitMQ messages.
        
        Args:
            ch: Channel
            method: Method frame
            properties: Message properties
            body: Message body
        """
        # Get or generate correlation ID
        correlation_id = properties.correlation_id if properties and properties.correlation_id else str(uuid.uuid4())
        
        # Call _handle_document_wrapper to ensure proper correlation ID handling
        self._handle_document_wrapper(ch, method, properties, body)
            
    def start(self):
        from events import EventTypes
        """Start the service."""
        logger.info("Starting extraction service...")
        
        # Subscribe to document.discovered events
        if self.consumer.subscribe(EventTypes.DOCUMENT_DISCOVERED.value, self._handle_event):
            self.consumer.start_consuming()
        else:
            raise RuntimeError("Failed to subscribe to events")
            
    def _handle_document_wrapper(self, ch, method, properties, body):
        """Wrapper to ensure correlation ID is preserved before calling handle_document."""
        # Get or generate correlation ID
        correlation_id = properties.correlation_id if properties and properties.correlation_id else str(uuid.uuid4())
        
        if not properties or not properties.correlation_id:
            logger.warning("No correlation ID in message properties, generating new one", extra={
                'correlation_id': correlation_id,
                'routing_key': method.routing_key if method else None
            })
            
            # Create new properties with correlation ID
            properties = pika.BasicProperties(
                correlation_id=correlation_id,
                content_type=properties.content_type if properties else None,
                delivery_mode=2  # Make message persistent
            )
        
        # Call handle_document with properties containing correlation ID
        self.handle_document(ch, method, properties, body)
            
    def handle_document(self, ch, method, properties, body):
        from events import DocumentDiscovered, EventTypes
        """Handle a document.discovered event.
        
        Args:
            ch: Channel
            method: Method frame
            properties: Message properties
            body: Message body
        """
        # Get correlation ID from properties (should be set by wrapper)
        correlation_id = properties.correlation_id if properties and properties.correlation_id else str(uuid.uuid4())
        logger.info(f"Handling document message", extra={'correlation_id': correlation_id})
        try:
            # Parse message body
            message = json.loads(body)
            event_data = message.get('data', {})

            logger.info("Handling document message", extra={'correlation_id': correlation_id})

            # Deserialize to DocumentDiscovered event  -> Full event structure
            discovered = DocumentDiscovered(
                eventType=message['eventType'],
                eventId=message['eventId'],
                timestamp=message['timestamp'],
                correlationId=message['correlationId'],
                source=message['source'],
                version=message['version'],
                payload=message['payload'] # This is where the document data lives
            )
             # Extract the actual document data from the payload

            logger.info("Processing document", extra={
                'correlation_id': discovered.correlationId,
                'document_id': discovered.payload['documentId'],
                'source_url': discovered.payload['sourceUrl'],
                'discovered_at': discovered.payload['discoveredAt']
            })
            
            # Debug log to inspect the payload of DocumentDiscovered
            logger.debug(f"Discovered event: {discovered}")
            
            # Extract text and metadata
            start_time = time.time()
            file_path = discovered.payload["filePath"]
            result = self.extractor.extract_document(file_path, discovered.payload.get("sourceUrl"))
            extracted_file_time = datetime.now(timezone.utc).isoformat()
            processing_time = (time.time() - start_time) * 1000  # ms
            
            # Extract metadata from the result
            metadata = result.get("metadata", {})
            
            # Use page count from event if present, otherwise fallback to PDF extraction
            page_count = metadata.get("pageCount")
            
            # version to reflect backward-compatible changes
            event_version = os.getenv("EVENT_VERSION", "1.0")
            time_now = datetime.now(timezone.utc).isoformat()

            #get the file type
            fileType = self.extractor.check_file_type(file_path)
            fileType = fileType.split('/')[-1]  # Keep only the part after the last '/'  normally it would be application/pdf
            
            # Refactor event_data to match the new schema

            event_data = {
                "eventType": "DocumentExtracted",
                "eventId": str(uuid.uuid4()),
                "timestamp": time_now,
                "correlationId": correlation_id,
                "source": "extraction-service",
                "version": event_version,  # Incremented version to reflect backward-compatible changes
                "payload": {
                    "documentId": discovered.payload.get("documentId"),
                    "textContent": "\n\n".join(result.get("page_texts", [])),  # Ensure page_texts is handled safely
                    "page_texts": result.get("page_texts", []),
                    "fileType": fileType,
                    "metadata": {
                        "title": metadata.get("title", "Unknown Title"),  # Default to "Unknown Title" if missing
                        "sourceUrl": discovered.payload.get("sourceUrl", "Unknown Source"),  # Default to "Unknown Source" if missing
                        "pageCount": page_count
                    },
                    "extractedAt": extracted_file_time
                }
            }
            
            logger.info(f"DOCUMENT_EXTRACTED event data: {json.dumps(event_data, indent=2)}")
            
            # Publish the event with correlation ID
            if self.consumer.publish("document.extracted", EventTypes.DOCUMENT_EXTRACTED.value, event_data, correlation_id=correlation_id):
                logger.info("Document extraction completed", extra={
                    'correlation_id': correlation_id,
                    'document_id': discovered.payload['documentId'],
                    'title':  metadata.get("title", "Unknown Title"),
                    'page_count': page_count,
                    'processing_time_ms': processing_time
                })
            else:
                logger.error("Failed to publish extracted event", extra={
                    'document_id': discovered.document_id,
                    'error': 'RabbitMQ publish failed'
                })
            
        except Exception as e:
            logger.error(f"Failed to process document", extra={
                'correlation_id': correlation_id if 'correlation_id' in locals() else None,
                'document_id': event_data.get('document_id') if 'event_data' in locals() else None,
                'error': str(e)
            }, exc_info=True)
            # TODO: Handle error (dead letter queue?)