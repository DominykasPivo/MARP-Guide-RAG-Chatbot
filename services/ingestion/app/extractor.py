"""PDF link extraction module for MARP documents."""

import logging
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

# Configure logging
logger = logging.getLogger("ingestion.extractor")


class PDFLinkExtractor:
    """Extracts PDF links and metadata from HTML content."""

    def __init__(self, base_url: str):
        """Initialize the PDF link extractor.

        Args:
            base_url: Base URL for making relative URLs absolute
        """
        self.base_url = base_url

    def get_pdf_urls(
        self, html_content: str, correlation_id: Optional[str] = None
    ) -> List[str]:
        """First step: Extract just the PDF URLs from HTML content.

        Args:
            html_content: Raw HTML content to parse
            correlation_id: Optional correlation ID for request tracing

        Returns:
            List of discovered PDF URLs
        """
        soup = BeautifulSoup(html_content, "lxml")
        pdf_urls = []

        logger.info(
            "Looking for PDF links in HTML content...",
            extra={"correlation_id": correlation_id},
        )

        # Find all links that might be PDFs
        for link in soup.find_all("a"):
            href = link.get("href")
            if not href or not isinstance(href, str):
                continue

            # Make URL absolute
            url: str = urljoin(self.base_url, href)

            # Check if it's a PDF link
            if url.lower().endswith(".pdf"):
                logger.info(
                    f"Found PDF link: {url}", extra={"correlation_id": correlation_id}
                )
                pdf_urls.append(url)

        logger.info(
            f"Found {len(pdf_urls)} PDF links",
            extra={"correlation_id": correlation_id},
        )
        return pdf_urls
