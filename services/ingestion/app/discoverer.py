"""Document discovery for locating and tracking MARP PDFs."""

import hashlib
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import requests
from events import DocumentDiscovered
from extractor import PDFLinkExtractor
from storage import DocumentStorage

logger = logging.getLogger("ingestion.discoverer")

EVENT_VERSION = os.getenv("EVENT_VERSION", "1.0")
DISCOVERY_TIMEOUT = int(os.getenv("DISCOVERY_TIMEOUT", "10"))
DOWNLOAD_TIMEOUT = int(os.getenv("DOWNLOAD_TIMEOUT", "60"))


class MARPDocumentDiscoverer:
    """Discover and track MARP documents from the Lancaster website."""

    BASE_URL = (
        "https://www.lancaster.ac.uk/"
        "academic-standards-and-quality/"
        "regulations-and-policies/"
        "manual-of-academic-regulations-and-procedures/"
    )

    def __init__(self, storage_dir: str = "/data"):
        self.storage = DocumentStorage(storage_dir)
        self.extractor = PDFLinkExtractor(self.BASE_URL)
        logger.info("Document discoverer initialized.", extra={"correlation_id": None})

    def _get_document_hash(self, url: str, correlation_id: Optional[str] = None) -> str:
        """Compute a content hash using headers to detect changes."""
        try:
            response = requests.head(
                url, allow_redirects=True, timeout=DISCOVERY_TIMEOUT
            )
            response.raise_for_status()

            title = url.split("/")[-1].split(".")[0]
            last_modified = response.headers.get("last-modified")
            if last_modified:
                hash_input = f"{title}-{last_modified}"
            else:
                etag = response.headers.get("etag")
                if etag:
                    hash_input = f"{title}-{etag}"
                else:
                    content_length = response.headers.get("content-length", "")
                    hash_input = f"{title}-{content_length}"

            return hashlib.sha256(hash_input.encode()).hexdigest()
        except requests.RequestException as e:
            logger.error(
                f"Failed to compute document hash for {url}: {str(e)}",
                extra={"correlation_id": correlation_id},
            )
            return ""

    def discover_document_urls(self, correlation_id: Optional[str] = None) -> List[str]:
        """Fetch the MARP page and extract PDF URLs."""
        try:
            logger.info(
                f"Fetching content from {self.BASE_URL}.",
                extra={"correlation_id": correlation_id},
            )
            response = requests.get(self.BASE_URL, timeout=DOWNLOAD_TIMEOUT)
            response.raise_for_status()

            logger.info(
                f"Response status: {response.status_code}",
                extra={"correlation_id": correlation_id},
            )
            logger.info(
                f"Content length: {len(response.text)}",
                extra={"correlation_id": correlation_id},
            )
            logger.info("Content fetched.", extra={"correlation_id": correlation_id})

            pdf_urls: List[str] = self.extractor.get_pdf_urls(response.text)
            return pdf_urls

        except requests.RequestException as e:
            logger.error(
                f"Document discovery failed: {str(e)}",
                extra={"correlation_id": correlation_id},
            )
            return []

    def process_documents(
        self, urls: List[str], correlation_id: str
    ) -> List[DocumentDiscovered]:
        """Download PDFs and prepare document discovery events."""
        logger.info(
            f"Processing {len(urls)} documents.",
            extra={"correlation_id": correlation_id},
        )
        discovered_docs: List[DocumentDiscovered] = []

        for url in urls:
            logger.info(
                f"Processing URL: {url}", extra={"correlation_id": correlation_id}
            )
            current_hash = self._get_document_hash(url, correlation_id)
            if not current_hash:
                logger.error(
                    f"Hash computation failed for {url}",
                    extra={"correlation_id": correlation_id},
                )
                continue
            logger.info(
                f"Hash computed: {current_hash}",
                extra={"correlation_id": correlation_id},
            )

            doc_id = hashlib.sha256(url.encode()).hexdigest()
            pdf_path = os.path.join(
                self.storage.base_path, "documents", "pdfs", f"{doc_id}.pdf"
            )
            file_missing = not os.path.exists(pdf_path)
            is_new_or_updated = (
                doc_id not in self.storage.index
                or self.storage.index[doc_id].get("hash") != current_hash
                or file_missing
            )

            if is_new_or_updated:
                if file_missing:
                    logger.info(
                        "PDF missing; re-downloading.",
                        extra={"correlation_id": correlation_id},
                    )
                else:
                    logger.info(
                        "Document is new or updated.",
                        extra={"correlation_id": correlation_id},
                    )

                try:
                    response = requests.get(url, timeout=60)
                    response.raise_for_status()
                    pdf_content = response.content
                except Exception as e:
                    logger.error(
                        f"PDF download failed for {url}: {e}",
                        extra={"correlation_id": correlation_id},
                    )
                    continue

                logger.info(
                    f"PDF downloaded: {len(pdf_content)} bytes.",
                    extra={"correlation_id": correlation_id},
                )

                stored = self.storage.store_document(
                    document_id=doc_id,
                    pdf_content=pdf_content,
                    metadata={
                        "url": url,
                        "document_id": doc_id,
                        "hash": current_hash,
                        "date": datetime.now(timezone.utc).isoformat(),
                        "correlation_id": correlation_id,
                    },
                )
                if not stored:
                    logger.error(
                        "Document storage failed.",
                        extra={"correlation_id": correlation_id},
                    )
                    continue

                logger.info(
                    f"Document stored: {doc_id}",
                    extra={"correlation_id": correlation_id},
                )

                event = DocumentDiscovered(
                    eventType="DocumentDiscovered",
                    eventId=str(uuid.uuid4()),
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    correlationId=correlation_id,
                    source="ingestion-service",
                    version=EVENT_VERSION,
                    payload={
                        "documentId": doc_id,
                        "sourceUrl": url,
                        "filePath": os.path.join(
                            "/data", "documents", "pdfs", f"{doc_id}.pdf"
                        ),
                        "discoveredAt": datetime.now(timezone.utc).isoformat(),
                    },
                )
                discovered_docs.append(event)
                logger.info(
                    "Document discovery event created.",
                    extra={"correlation_id": correlation_id},
                )

        return discovered_docs

    def discover_and_process_documents(
        self, correlation_id: str
    ) -> List[DocumentDiscovered]:
        """Run discovery and processing end-to-end."""
        urls = self.discover_document_urls(correlation_id)
        return self.process_documents(urls, correlation_id)
