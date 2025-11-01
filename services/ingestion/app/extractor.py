"""PDF link extraction module for MARP documents."""
import logging
from typing import Dict, List, Optional
from datetime import datetime
import io
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from PyPDF2 import PdfReader

# Configure logging
logger = logging.getLogger(__name__)

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
        
        # Find all links that might be PDFs
        for link in soup.find_all('a'):
            href = link.get('href')
            if not href:
                continue
                
            # Make URL absolute
            url = urljoin(self.base_url, href)
            
            # Check if it's a PDF link
            if url.lower().endswith('.pdf'):
                pdf_urls.append(url)
        
        return pdf_urls
    
    def extract_metadata(self, url: str) -> Optional[Dict]:
        """Second step: Extract metadata for a specific PDF URL.
        
        Args:
            url: URL of the PDF to extract metadata for
            
        Returns:
            Dictionary containing metadata if successful, None otherwise
        """
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            # Get webpage content for title
            headers = {'User-Agent': 'Mozilla/5.0'}
            page_response = requests.get(url.replace('.pdf', ''), headers=headers)
            page_response.raise_for_status()
            soup = BeautifulSoup(page_response.text, 'lxml')
            
            # Try to get title from different sources
            title = None
            if title_tag := soup.title:
                title = title_tag.get_text(strip=True)
            elif h1_tag := soup.find('h1'):
                title = h1_tag.get_text(strip=True)
            
            # If no title found from HTML, use filename
            if not title:
                title = url.split('/')[-1].replace('.pdf', '').replace('-', ' ').title()
            
            # Get PDF metadata
            last_modified = response.headers.get('last-modified')
            if last_modified:
                pdf_date = datetime.strptime(last_modified, '%a, %d %b %Y %H:%M:%S %Z').isoformat()
            else:
                pdf_date = None
                
            # Get actual page count using PyPDF2
            pdf_content = io.BytesIO(response.content)
            pdf_reader = PdfReader(pdf_content)
            page_count = len(pdf_reader.pages)
            
            return {
                'title': title,
                'last_modified': pdf_date,
                'page_count': page_count,
                'discovered_at': datetime.utcnow().isoformat()
            }
            
        except (requests.RequestException, Exception) as e:
            logger.error(f"Failed to extract metadata for {url}: {str(e)}")
            return None
    
    def _extract_title(self, link_element) -> str:
        """Extract title from link element or surrounding context.
        
        Args:
            link_element: BeautifulSoup link element
            
        Returns:
            Extracted title or empty string if no title found
        """
        # Try direct link text first
        title = link_element.get_text(strip=True)
        if title:
            return title
            
        # Look for nearby headings or list items
        parent_li = link_element.find_parent('li')
        if parent_li:
            return parent_li.get_text(strip=True)
            
        prev_heading = link_element.find_previous(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        if prev_heading:
            return prev_heading.get_text(strip=True)
            
        return ""