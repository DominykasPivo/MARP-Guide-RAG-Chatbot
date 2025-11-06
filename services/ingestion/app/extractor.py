"""PDF link extraction module for MARP documents."""
from typing import Dict, List, Optional
from datetime import datetime
import io
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from logging_config import setup_logger

# Configure logging
logger = setup_logger('ingestion.extractor')

import PyPDF2

class PDFLinkExtractor:
    """Extracts PDF links and metadata from HTML content."""
    
    def __init__(self, base_url: str):
        """Initialize the PDF link extractor.
        
        Args:
            base_url: Base URL for making relative URLs absolute
        """
        self.base_url = base_url

    def get_pdf_urls(self, html_content: str, correlation_id: Optional[str] = None) -> List[str]:
        """First step: Extract just the PDF URLs from HTML content.
        
        Args:
            html_content: Raw HTML content to parse
            correlation_id: Optional correlation ID for request tracing
            
        Returns:
            List of discovered PDF URLs
        """
        soup = BeautifulSoup(html_content, 'lxml')
        pdf_urls = []
        
        logger.info("Looking for PDF links in HTML content...", extra={'correlation_id': correlation_id})
        
        # Find all links that might be PDFs
        for link in soup.find_all('a'):
            href = link.get('href')
            if not href:
                continue
                
            # Make URL absolute
            url = urljoin(self.base_url, href)
            
            # Check if it's a PDF link
            if url.lower().endswith('.pdf'):
                logger.info(f"Found PDF link: {url}", extra={'correlation_id': correlation_id})
                pdf_urls.append(url)
        
        logger.info(f"Found {len(pdf_urls)} PDF links", extra={'correlation_id': correlation_id})
        return pdf_urls
    
    def extract_metadata(self, url: str, correlation_id: Optional[str] = None) -> Optional[Dict]:
        """Second step: Extract metadata for a specific PDF URL.
        
        Args:
            url: URL of the PDF to extract metadata for
            correlation_id: Optional correlation ID for request tracing
            
        Returns:
            Dictionary containing metadata if successful, None otherwise
        """
        try:
            logger.info(f"Fetching PDF from: {url}", extra={'correlation_id': correlation_id})
            response = requests.get(url, stream=True)
            response.raise_for_status()

            # Just use the filename as title, as the MARP filenames are good enough
            title = url.split('/')[-1].replace('.pdf', '').replace('-', ' ').title()
            logger.info(f"Got title: {title}", extra={'correlation_id': correlation_id})

            # Get PDF metadata from headers
            last_modified = response.headers.get('last-modified')
            logger.info(f"Last-Modified header: {last_modified}", extra={'correlation_id': correlation_id})

            if last_modified: 
                try:
                    pdf_date = datetime.strptime(last_modified, '%a, %d %b %Y %H:%M:%S %Z').isoformat()
                    logger.info(f"Parsed date: {pdf_date}", extra={'correlation_id': correlation_id})
                except ValueError:
                    try:
                        # Try another common format
                        pdf_date = datetime.strptime(last_modified, '%a, %d %b %Y %H:%M:%S %z').isoformat()
                        logger.info(f"Parsed date (alternate format): {pdf_date}", extra={'correlation_id': correlation_id})
                    except ValueError:
                        logger.warning(f"Could not parse last-modified date: {last_modified}", extra={'correlation_id': correlation_id})
                        pdf_date = None
            else:
                logger.info("No Last-Modified header found", extra={'correlation_id': correlation_id})
                pdf_date = None

            # Save PDF content to file
            logger.info("Saving PDF content", extra={'correlation_id': correlation_id})
            pdf_content = io.BytesIO(response.content)

            # Extract page count using PyPDF2
            try:
                pdf_content.seek(0)
                reader = PyPDF2.PdfReader(pdf_content)
                page_count = len(reader.pages)
                logger.info(f"Extracted page count: {page_count}", extra={'correlation_id': correlation_id})
            except Exception as e:
                logger.warning(f"Could not extract page count: {e}", extra={'correlation_id': correlation_id})
                page_count = None

            metadata = {
                'title': title,
                'source_url': url,  
                'date': datetime.utcnow().isoformat(),
                'page_count': page_count
            }
            logger.info(f"Extracted metadata: {metadata}", extra={'correlation_id': correlation_id})
            return metadata

        except (requests.RequestException, Exception) as e:
            logger.error(f"Failed to extract metadata for {url}: {str(e)}", extra={'correlation_id': correlation_id})
            return None

    def download_pdf(self, url: str, correlation_id: Optional[str] = None) -> Optional[bytes]:
        """Download a PDF file with retry logic.
        Args:
            url: URL of the PDF to download
            correlation_id: Optional correlation ID for request tracing
        Returns:
            PDF content as bytes if successful, None otherwise
        """
        max_retries = 3
        base_delay = 2  # seconds
        for attempt in range(max_retries):
            try:
                logger.info(f"Attempting to download PDF from {url} (attempt {attempt+1}/{max_retries})", extra={'correlation_id': correlation_id})
                response = requests.get(url)
                response.raise_for_status()
                content_type = response.headers.get('content-type', '')
                content_length = len(response.content)
                logger.info(f"Downloaded PDF - Content-Type: {content_type}, Size: {content_length} bytes", 
                            extra={'correlation_id': correlation_id})
                return response.content
            except requests.RequestException as e:
                logger.warning(f"Failed to download PDF from {url} (attempt {attempt+1}/{max_retries}): {str(e)}", extra={'correlation_id': correlation_id})
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # exponential backoff
                    logger.info(f"Retrying in {delay} seconds...", extra={'correlation_id': correlation_id})
                    import time
                    time.sleep(delay)
                else:
                    logger.error(f"Giving up on downloading PDF from {url} after {max_retries} attempts.", extra={'correlation_id': correlation_id})
        return None

