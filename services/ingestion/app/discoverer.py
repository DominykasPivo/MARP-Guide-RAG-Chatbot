"""Document discovery module for finding and tracking MARP PDFs."""
import os
import logging
import hashlib
import json
import shutil
from typing import Dict, List, Optional
import requests
from extractor import PDFLinkExtractor
from events import DocumentDiscovered

# Configure logging
logger = logging.getLogger(__name__)

class MARPDocumentDiscoverer:
    """Discovers and tracks MARP documents from the Lancaster University website."""
    
    BASE_URL = "https://www.lancaster.ac.uk/academic-standards-and-quality/regulations-and-policies/manual-of-academic-regulations-and-procedures/"
    CACHE_FILE = "discovered_documents.json"
    
    def __init__(self, storage_dir: str):
        """Initialize the document discoverer.
        
        Args:
            storage_dir: Directory to store downloaded PDFs and cache
        """
        self.storage_dir = storage_dir
        self.cache_path = os.path.join(storage_dir, self.CACHE_FILE)
        self.discovered_docs = self._load_cache()
        self.extractor = PDFLinkExtractor(self.BASE_URL)
        
    def _load_cache(self) -> Dict:
        """Load previously discovered documents from cache."""
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.error("Failed to load document cache, starting fresh")
        return {}
    
    def _save_cache(self):
        """Save discovered documents to cache."""
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
        with open(self.cache_path, 'w') as f:
            json.dump(self.discovered_docs, f, indent=2)
    
    def _get_document_hash(self, url: str) -> str:
        """Get hash of document content to detect changes."""
        try:
            response = requests.head(url, allow_redirects=True)
            response.raise_for_status()
            # Use last modified header if available, otherwise use etag or content length
            last_modified = response.headers.get('last-modified')
            if last_modified:
                return hashlib.md5(last_modified.encode()).hexdigest()
            etag = response.headers.get('etag')
            if etag:
                return hashlib.md5(etag.encode()).hexdigest()
            return hashlib.md5(str(response.headers.get('content-length', '')).encode()).hexdigest()
        except requests.RequestException as e:
            logger.error(f"Failed to get document hash for {url}: {str(e)}")
            return ""
    
    def discover_document_urls(self) -> List[str]:
        """First step: Discover PDF URLs from the MARP website.
        
        Returns:
            List of discovered PDF URLs
        """
        try:
            # Fetch main MARP page
            response = requests.get(self.BASE_URL)
            response.raise_for_status()
            
            # Extract just the URLs first
            return self.extractor.get_pdf_urls(response.text)
            
        except requests.RequestException as e:
            logger.error(f"Failed to discover documents: {str(e)}")
            return []
    
    def _download_pdf(self, url: str, doc_id: str) -> Optional[str]:
        """Download a PDF file and store it locally.
        
        Args:
            url: URL of the PDF to download
            doc_id: Document ID to use in filename
            
        Returns:
            Path to stored PDF if successful, None otherwise
        """
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            # Create PDFs directory if it doesn't exist
            pdf_dir = os.path.join(self.storage_dir, 'pdfs')
            os.makedirs(pdf_dir, exist_ok=True)
            
            # Store PDF with document ID as filename
            pdf_path = os.path.join(pdf_dir, f"{doc_id}.pdf")
            with open(pdf_path, 'wb') as f:
                shutil.copyfileobj(response.raw, f)
                
            return pdf_path
            
        except (requests.RequestException, IOError) as e:
            logger.error(f"Failed to download PDF from {url}: {str(e)}")
            return None
    
    def process_documents(self, urls: List[str]) -> List[DocumentDiscovered]:
        """Second step: Download PDFs and prepare document discovery events.
        
        Args:
            urls: List of PDF URLs to process
            
        Returns:
            List of DocumentDiscovered events for new or updated documents
        """
        discovered_docs = []
        
        # Process each URL
        for url in urls:
            current_hash = self._get_document_hash(url)
            if not current_hash:
                continue
                
            # Check if document is new or updated
            if url not in self.discovered_docs or self.discovered_docs[url]['hash'] != current_hash:
                # Extract metadata
                metadata = self.extractor.extract_metadata(url)
                if not metadata:
                    continue
                    
                # Generate document ID
                doc_id = hashlib.md5(url.encode()).hexdigest()
                
                # Download PDF
                pdf_path = self._download_pdf(url, doc_id)
                if not pdf_path:
                    continue
                
                # Create document discovery event
                event = DocumentDiscovered(
                    document_id=doc_id,
                    title=metadata['title'],
                    source_url=url,
                    file_path=pdf_path,
                    discovered_at=metadata['discovered_at'],
                    last_modified=metadata.get('last_modified'),
                    page_count=metadata.get('page_count')
                )
                
                # Update cache with document info
                self.discovered_docs[url] = {
                    'id': doc_id,
                    'url': url,
                    'title': metadata['title'],
                    'hash': current_hash,
                    'discovered_at': metadata['discovered_at'],
                    'last_modified': metadata.get('last_modified'),
                    'page_count': metadata.get('page_count'),
                    'file_path': pdf_path
                }
                
                discovered_docs.append(event)
        
        # Save updated cache
        self._save_cache()
        return discovered_docs
        
    def discover_and_process_documents(self) -> List[DocumentDiscovered]:
        """Convenience method to run both discovery and processing in one call.
        
        Returns:
            List of DocumentDiscovered events for new or updated documents
        """
        urls = self.discover_document_urls()
        return self.process_documents(urls)

    def get_document_info(self, url: str) -> Optional[Dict]:
        """Get cached information about a discovered document."""
        return self.discovered_docs.get(url)