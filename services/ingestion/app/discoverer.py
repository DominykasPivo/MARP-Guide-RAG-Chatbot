"""Document discovery module for finding and tracking MARP PDFs."""
import os
import hashlib
import json
from datetime import datetime
from typing import Dict, List, Optional
import requests
from extractor import PDFLinkExtractor
from events import DocumentDiscovered
from storage import DocumentStorage
from logging_config import setup_logger
import uuid

# Configure logging
logger = setup_logger('ingestion.discoverer')

class MARPDocumentDiscoverer:
    """Discovers and tracks MARP documents from the Lancaster University website."""
    
    BASE_URL = "https://www.lancaster.ac.uk/academic-standards-and-quality/regulations-and-policies/manual-of-academic-regulations-and-procedures/"
    
    def __init__(self, storage_dir: str = "/data"):
        """Initialize the document discoverer.
        
        Args:
            storage_dir: Directory to store downloaded PDFs and cache, defaults to /data
        """
        self.storage = DocumentStorage(storage_dir)
        self.extractor = PDFLinkExtractor(self.BASE_URL)
        logger.info(f"Initialized document discoverer with storage at: {storage_dir}", extra={'correlation_id': None})
        

    def _get_document_hash(self, url: str, correlation_id: str = None) -> str:
        """Get hash of document content to detect changes, including the document title.
        
        Args:
            url: URL of the document to hash
            correlation_id: Optional correlation ID for request tracing
        """
        try:
            response = requests.head(url, allow_redirects=True)
            response.raise_for_status()

            # Extract document title from the URL or headers
            title = url.split('/')[-1]  # Use the last part of the URL as the title
            title = title.split('.')[0]  # Remove file extension if present

            # Use last modified header if available, otherwise use etag or content length
            last_modified = response.headers.get('last-modified')
            if last_modified:
                hash_input = f"{title}-{last_modified}"
            else:
                etag = response.headers.get('etag')
                if etag:
                    hash_input = f"{title}-{etag}"
                else:
                    content_length = response.headers.get('content-length', '')
                    hash_input = f"{title}-{content_length}"

            # Generate hash including the title
            return hashlib.md5(hash_input.encode()).hexdigest()
        except requests.RequestException as e:
            logger.error(f"Failed to get document hash for {url}: {str(e)}", 
                         extra={'correlation_id': correlation_id})
            return ""
    
    def discover_document_urls(self, correlation_id: str = None) -> List[str]:
        """First step: Discover PDF URLs from the MARP website.
        
        Args:
            correlation_id: Optional correlation ID for request tracing
            
        Returns:
            List of discovered PDF URLs
        """
        try:
            # Fetch main MARP page
            logger.info(f"Fetching content from {self.BASE_URL}...", extra={'correlation_id': correlation_id})
            response = requests.get(self.BASE_URL)
            response.raise_for_status()
            
            logger.info(f"Got response with status {response.status_code}", extra={'correlation_id': correlation_id})
            logger.info(f"Content length: {len(response.text)} bytes", extra={'correlation_id': correlation_id})
            logger.info(f"Content preview: {response.text[:1000]}...", extra={'correlation_id': correlation_id})
            
            # Extract just the URLs first
            return self.extractor.get_pdf_urls(response.text)
            
        except requests.RequestException as e:
            logger.error(f"Failed to discover documents: {str(e)}", extra={'correlation_id': correlation_id})
            return []
    
    def process_documents(self, urls: List[str], correlation_id: str) -> List[DocumentDiscovered]:
        """Second step: Download PDFs and prepare document discovery events.
        
        Args:
            urls: List of PDF URLs to process
            correlation_id: Correlation ID for tracing this discovery process
            
        Returns:
            List of DocumentDiscovered events for new or updated documents
        """
        logger.info(f"Processing {len(urls)} documents... [correlation_id: {correlation_id}]")
        discovered_docs = []
        
        # Process each URL
        for url in urls:
            logger.info(f"Processing document URL: {url}", extra={'correlation_id': correlation_id})
            current_hash = self._get_document_hash(url, correlation_id)
            if not current_hash:
                logger.error(f"Failed to get hash for {url}", extra={'correlation_id': correlation_id})
                continue
            logger.info(f"Got hash {current_hash} for {url}", extra={'correlation_id': correlation_id})

            # Generate document ID (MD5 hash of URL)
            doc_id = hashlib.md5(url.encode()).hexdigest()

            # Check if document is new or updated
            if doc_id not in self.storage.index or self.storage.index[doc_id].get('hash') != current_hash:
                logger.info(f"Document {url} is new or updated", extra={'correlation_id': correlation_id})
                # Extract metadata

                metadata = self.extractor.extract_metadata(url, correlation_id)

                if not metadata:
                    logger.error(f"Failed to extract metadata for {url}", extra={'correlation_id': correlation_id})
                    continue
                else: logger.info(f"Got metadata for {url}: {metadata}", extra={'correlation_id': correlation_id})

                # Explicitly log page_count and correlation_id
                logger.info(f"Metadata for {url}: page_count={metadata.get('page_count')}, correlation_id={correlation_id}", extra={'correlation_id': correlation_id})

                # Store document
                logger.info(f"Attempting to store document {doc_id}", extra={'correlation_id': correlation_id})
                # Ensure page_count is always present in metadata dict
                meta_to_store = {
                    'title': metadata['title'],
                    'url': url,
                    'date': metadata['date'],  # Updated to match 'date' field from extractor.py
                    'last_modified': metadata.get('last_modified'),
                    'page_count': metadata.get('page_count', None),
                    'hash': current_hash,
                    'correlation_id': correlation_id
                }
                logger.info(f"Storing document with metadata: {meta_to_store}", extra={'correlation_id': correlation_id})
                
                # Download PDF using extractor
                pdf_content = self.extractor.download_pdf(url, correlation_id)
                if not pdf_content:
                    logger.error(f"Failed to download PDF for {url}", extra={'correlation_id': correlation_id})
                    continue
                logger.info(f"Successfully downloaded PDF ({len(pdf_content)} bytes) for {url}", extra={'correlation_id': correlation_id})
                
                stored = self.storage.store_document(
                    document_id=doc_id,
                    pdf_content=pdf_content,
                    metadata=meta_to_store
                )
                if not stored:
                    logger.error(f"Failed to store document for {url}", extra={'correlation_id': correlation_id})
                    continue
                logger.info(f"Stored document {doc_id}", extra={'correlation_id': correlation_id})



                event_version = os.getenv("EVENT_VERSION", "1.0")
                # Create document discovery event
                event = DocumentDiscovered(
                    eventType="DocumentDiscovered",
                    eventId=str(uuid.uuid4()),
                    timestamp=datetime.utcnow().isoformat(),
                    correlationId=correlation_id,
                    source="ingestion-service",
                    version=event_version,
                    payload={
                        "documentId": doc_id,
                        "title": metadata['title'],
                        "pageCount": metadata.get('page_count'),
                        "sourceUrl": metadata['source_url'],
                        "filePath": os.path.join('/data', 'documents', 'pdfs', f"{doc_id}.pdf"),
                        "discoveredAt": metadata['date']
                    }
                )
                logger.info(f"Created document discovery event for {url}", extra={'correlation_id': correlation_id})
                discovered_docs.append(event)
        
    # Removed cache save (no longer needed)
        return discovered_docs
        
    def discover_and_process_documents(self, correlation_id: str) -> List[DocumentDiscovered]:
        """Convenience method to run both discovery and processing in one call.
        
        Args:
            correlation_id: Correlation ID for tracing this discovery process
            
        Returns:
            List of DocumentDiscovered events for new or updated documents
        """
        urls = self.discover_document_urls(correlation_id)
        return self.process_documents(urls, correlation_id)