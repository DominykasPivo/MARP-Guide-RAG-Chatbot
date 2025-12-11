"""Document storage management for the ingestion service."""

import json
import logging
import os
import threading
from typing import Dict, List, Optional

logger = logging.getLogger("ingestion.storage")


class DocumentStorage:
    """Manage storage of PDFs and a document index."""

    def __init__(self, base_path: str = "/data"):
        self._lock = threading.RLock()
        self.base_path = base_path
        documents_path = os.path.join(base_path, "documents")
        os.makedirs(documents_path, exist_ok=True)
        self.pdfs_path = os.path.join(documents_path, "pdfs")
        self.index_path = os.path.join(documents_path, "discovered_docs.json")
        os.makedirs(self.pdfs_path, exist_ok=True)
        self._load_index()

    def get_document_path(self, document_id: str) -> Optional[str]:
        """Return the absolute path to the PDF for a document, or None if not found."""
        self._load_index()
        entry = self.index.get(document_id)
        if not entry:
            return None
        pdf_path = os.path.join(self.base_path, entry["pdf"])
        return pdf_path if os.path.exists(pdf_path) else None

    def _load_index(self) -> None:
        """Load the document index."""
        with self._lock:
            if os.path.exists(self.index_path):
                try:
                    with open(self.index_path, "r") as f:
                        self.index = json.load(f)
                except Exception:
                    logger.warning("Index file is corrupted; creating a new index.")
                    self.index = {}
                    self._save_index()
            else:
                self.index = {}
                self._save_index()

    def _save_index(self) -> None:
        """Persist the document index to disk."""
        with self._lock:
            with open(self.index_path, "w") as f:
                json.dump(self.index, f, indent=2)

    def store_document(self, document_id: str, pdf_content: bytes, metadata: Dict) -> bool:
        """Store PDF and update index with metadata."""
        with self._lock:
            try:
                os.makedirs(self.pdfs_path, exist_ok=True)
                pdf_path = os.path.join(self.pdfs_path, f"{document_id}.pdf")
                with open(pdf_path, "wb") as f:
                    f.write(pdf_content)

                self.index[document_id] = {
                    "pdf": os.path.relpath(pdf_path, self.base_path),
                    "url": metadata.get("url"),
                    "hash": metadata.get("hash"),
                    "date": metadata.get("date"),
                    "correlation_id": metadata.get("correlation_id"),
                }
                self._save_index()
                logger.info(f"Stored document {document_id}.")
                return True
            except Exception as e:
                logger.error(f"Error storing document {document_id}: {e}")
                return False

    def get_pdf(self, document_id: str) -> Optional[bytes]:
        """Retrieve the PDF content for a document."""
        with self._lock:
            self._load_index()
            entry = self.index.get(document_id)
            if not entry:
                return None
            pdf_path = os.path.join(self.base_path, entry["pdf"])
            try:
                with open(pdf_path, "rb") as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Error reading PDF for {document_id}: {e}")
                return None

    def get_pdf_path(self, document_id: str) -> Optional[str]:
        """Return the absolute path to the PDF file for a given document ID."""
        with self._lock:
            self._load_index()
            entry = self.index.get(document_id)
            if not entry:
                return None
            pdf_path = os.path.join(self.base_path, entry["pdf"])
            return pdf_path if os.path.exists(pdf_path) else None

    def list_documents(self) -> List[Dict]:
        """List all documents with their metadata from the index."""
        with self._lock:
            self._load_index()
            return [{"document_id": doc_id, **entry} for doc_id, entry in self.index.items()]

    def delete_document(self, document_id: str) -> bool:
        """Delete a document's PDF and index entry."""
        with self._lock:
            entry = self.index.get(document_id)
            if not entry:
                return False
            pdf_path = os.path.join(self.base_path, entry["pdf"])
            try:
                if os.path.exists(pdf_path):
                    os.remove(pdf_path)
                del self.index[document_id]
                self._save_index()
                logger.info(f"Deleted document {document_id}.")
                return True
            except Exception as e:
                logger.error(f"Error deleting document {document_id}: {e}")
                return False