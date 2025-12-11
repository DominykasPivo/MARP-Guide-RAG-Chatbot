"""PDF link extraction for MARP documents."""

import logging
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

logger = logging.getLogger("ingestion.extractor")


class PDFLinkExtractor:
    """Extract PDF links from HTML content."""

    def __init__(self, base_url: str):
        self.base_url = base_url

    def get_pdf_urls(self, html_content: str, correlation_id: Optional[str] = None) -> List[str]:
        """Extract PDF URLs from HTML content."""
        soup = BeautifulSoup(html_content, "lxml")
        pdf_urls: List[str] = []

        logger.info("Scanning HTML content for PDF links.", extra={"correlation_id": correlation_id})

        for link in soup.find_all("a"):
            href = link.get("href")
            if not href or not isinstance(href, str):
                continue

            url: str = urljoin(self.base_url, href)

            if url.lower().endswith(".pdf"):
                logger.info(f"PDF link found: {url}", extra={"correlation_id": correlation_id})
                pdf_urls.append(url)

        logger.info(f"PDF links found: {len(pdf_urls)}", extra={"correlation_id": correlation_id})
        return pdf_urls
