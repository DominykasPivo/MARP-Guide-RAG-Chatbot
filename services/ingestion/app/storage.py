"""API-ready document storage management for the ingestion service."""

import os
import json
import threading
from typing import Dict, Optional, List
from logging_config import setup_logger

logger = setup_logger('ingestion.storage')

class DocumentStorage:
    def __init__(self, base_path: str = "/data"):
        self._lock = threading.RLock()
        self.base_path = base_path
        documents_path = os.path.join(base_path, 'documents')
        os.makedirs(documents_path, exist_ok=True)
        self.pdfs_path = os.path.join(documents_path, 'pdfs')
        self.metadata_path = os.path.join(documents_path, 'metadata')
        self.index_path = os.path.join(documents_path, 'discovered_docs.json')
        os.makedirs(self.pdfs_path, exist_ok=True)
        os.makedirs(self.metadata_path, exist_ok=True)
        self._load_index()

    def get_document_path(self, document_id: str) -> str | None:
        """Return the absolute path to the PDF for a document, or None if not found."""
        entry = self.index.get(document_id)
        if not entry:
            return None
        pdf_path = os.path.join(self.base_path, entry['pdf'])
        return pdf_path if os.path.exists(pdf_path) else None
    # Manages document storage and retrieval for PDFs, metadata, and index.

    def _load_index(self):
        with self._lock:
            if os.path.exists(self.index_path):
                try:
                    with open(self.index_path, 'r') as f:
                        self.index = json.load(f)
                except Exception:
                    logger.warning("Corrupted index file, creating new index")
                    self.index = {}
            else:
                self.index = {}
            self._save_index()

    def _save_index(self):
        with self._lock:
            with open(self.index_path, 'w') as f:
                json.dump(self.index, f, indent=2)

    def store_document(self, document_id: str, pdf_content: bytes, metadata: Dict) -> bool:
        """Store a PDF and its metadata, and update the index, preserving existing fields like 'hash'."""
        with self._lock:
            try:
                pdf_path = os.path.join(self.pdfs_path, f"{document_id}.pdf")
                with open(pdf_path, 'wb') as f:
                    f.write(pdf_content)
                meta_path = os.path.join(self.metadata_path, f"{document_id}.json")
                # Build the metadata dict to match discovered_docs.json entry
                meta_entry = {
                    'title': metadata.get('title'),
                    'url': metadata.get('url'),
                    'discovered_at': metadata.get('discovered_at'),
                    'last_modified': metadata.get('last_modified'),
                    'page_count': metadata.get('page_count'),
                    'hash': metadata.get('hash'),
                    'correlation_id': metadata.get('correlation_id'),
                }
                # Remove keys with None values for cleanliness
                meta_entry = {k: v for k, v in meta_entry.items() if v is not None}
                with open(meta_path, 'w') as f:
                    json.dump(meta_entry, f, indent=2)
                # Preserve existing fields (like 'hash') if present, but do not merge duplicate keys
                existing_entry = self.index.get(document_id, {})
                new_entry = {}
                # Only set each key once, in priority order: new metadata > existing entry > default
                new_entry['pdf'] = os.path.relpath(pdf_path, self.base_path)
                new_entry['metadata'] = os.path.relpath(meta_path, self.base_path)
                new_entry['title'] = metadata.get('title') or existing_entry.get('title', '')
                new_entry['created_at'] = metadata.get('discovered_at') or existing_entry.get('created_at', '')
                new_entry['last_modified'] = metadata.get('last_modified') or existing_entry.get('last_modified', '')
                new_entry['hash'] = metadata.get('hash') or existing_entry.get('hash', '')
                # Always include page_count and correlation_id, even if None
                new_entry['page_count'] = metadata.get('page_count')
                new_entry['correlation_id'] = metadata.get('correlation_id')
                # If there are any other fields in existing_entry not set above, add them (but don't overwrite)
                for k, v in existing_entry.items():
                    if k not in new_entry:
                        new_entry[k] = v
                self.index[document_id] = new_entry
                self._save_index()
                logger.info(f"Stored document {document_id} (PDF, metadata, index updated)")
                return True
            except Exception as e:
                logger.error(f"Error storing document {document_id}: {e}")
                return False

    def get_pdf(self, document_id: str) -> Optional[bytes]:
        """Retrieve the PDF content for a document."""
        with self._lock:
            entry = self.index.get(document_id)
            if not entry:
                return None
            pdf_path = os.path.join(self.base_path, entry['pdf'])
            try:
                with open(pdf_path, 'rb') as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Error reading PDF for {document_id}: {e}")
                return None

    def get_metadata(self, document_id: str) -> Optional[Dict]:
        """Retrieve the metadata for a document."""
        with self._lock:
            entry = self.index.get(document_id)
            if not entry:
                return None
            meta_path = os.path.join(self.base_path, entry['metadata'])
            try:
                with open(meta_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error reading metadata for {document_id}: {e}")
                return None

    def list_documents(self) -> List[Dict]:
        """List all documents with their metadata from the index."""
        with self._lock:
            return [
                {
                    'document_id': doc_id,
                    **entry
                }
                for doc_id, entry in self.index.items()
            ]

    def delete_document(self, document_id: str) -> bool:
        """Delete a document's PDF, metadata, and index entry."""
        with self._lock:
            entry = self.index.get(document_id)
            if not entry:
                return False
            pdf_path = os.path.join(self.base_path, entry['pdf'])
            meta_path = os.path.join(self.base_path, entry['metadata'])
            try:
                if os.path.exists(pdf_path):
                    os.remove(pdf_path)
                if os.path.exists(meta_path):
                    os.remove(meta_path)
                del self.index[document_id]
                self._save_index()
                logger.info(f"Deleted document {document_id} (PDF, metadata, index entry)")
                return True
            except Exception as e:
                logger.error(f"Error deleting document {document_id}: {e}")
                return False