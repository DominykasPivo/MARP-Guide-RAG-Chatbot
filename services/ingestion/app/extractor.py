"""PDF link extraction module for MARP documents."""
from typing import Dict, List, Optional
from datetime import datetime
import io
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from logging_config import setup_logger

# Configure logging
logger = setup_logger('ingestion.pdf')

import PyPDF2

class PDFLinkExtractor:
    """Extracts PDF links and metadata from HTML content."""
    
    def __init__(self, base_url: str):
        """Initialize the PDF link extractor.
        
        Args:
            base_url: Base URL for making relative URLs absolute
        """
        self.base_url = base_url

    def get_pdf_urls(self, html_content: str) -> List[str]:
        """First step: Extract just the PDF URLs from HTML content.
        
        Args:
            html_content: Raw HTML content to parse
            
        Returns:
            List of discovered PDF URLs
        """
        soup = BeautifulSoup(html_content, 'lxml')
        pdf_urls = []
        
        logger.info("Looking for PDF links in HTML content...")
        
        # Find all links that might be PDFs
        for link in soup.find_all('a'):
            href = link.get('href')
            if not href:
                continue
                
            # Make URL absolute
            url = urljoin(self.base_url, href)
            
            # Check if it's a PDF link
            if url.lower().endswith('.pdf'):
                logger.info(f"Found PDF link: {url}")
                pdf_urls.append(url)
        
        logger.info(f"Found {len(pdf_urls)} PDF links")
        return pdf_urls
    
    def extract_metadata(self, url: str) -> Optional[Dict]:
        """Second step: Extract metadata for a specific PDF URL.
        
        Args:
            url: URL of the PDF to extract metadata for
            
        Returns:
            Dictionary containing metadata if successful, None otherwise
        """
        try:
            logger.info(f"Fetching PDF from: {url}")
            response = requests.get(url, stream=True)
            response.raise_for_status()

            # Just use the filename as title, as the MARP filenames are good enough
            title = url.split('/')[-1].replace('.pdf', '').replace('-', ' ').title()
            logger.info(f"Got title: {title}")

            # Get PDF metadata from headers
            last_modified = response.headers.get('last-modified')
            logger.info(f"Last-Modified header: {last_modified}")

            if last_modified:
                try:
                    pdf_date = datetime.strptime(last_modified, '%a, %d %b %Y %H:%M:%S %Z').isoformat()
                    logger.info(f"Parsed date: {pdf_date}")
                except ValueError:
                    try:
                        # Try another common format
                        pdf_date = datetime.strptime(last_modified, '%a, %d %b %Y %H:%M:%S %z').isoformat()
                        logger.info(f"Parsed date (alternate format): {pdf_date}")
                    except ValueError:
                        logger.warning(f"Could not parse last-modified date: {last_modified}")
                        pdf_date = None
            else:
                logger.info("No Last-Modified header found")
                pdf_date = None

            # Save PDF content to file
            logger.info("Saving PDF content")
            pdf_content = io.BytesIO(response.content)

            # Extract page count using PyPDF2
            try:
                pdf_content.seek(0)
                reader = PyPDF2.PdfReader(pdf_content)
                page_count = len(reader.pages)
                logger.info(f"Extracted page count: {page_count}")
            except Exception as e:
                logger.warning(f"Could not extract page count: {e}")
                page_count = None

            metadata = {
                'title': title,
                'last_modified': pdf_date,
                'discovered_at': datetime.utcnow().isoformat(),
                'page_count': page_count
            }
            logger.info(f"Extracted metadata: {metadata}")
            return metadata

        except (requests.RequestException, Exception) as e:
            logger.error(f"Failed to extract metadata for {url}: {str(e)}")
            return None
    
