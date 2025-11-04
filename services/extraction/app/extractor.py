"""PDF text extraction functionality."""
import os
from datetime import datetime
import re
from typing import Dict, Optional

import magic
import PyPDF2
import pdfplumber
from logging_config import setup_logger

# Configure logging
logger = setup_logger('extraction.pdf')

class PDFExtractor:
    """Handles PDF text and metadata extraction."""
    
    def extract_document(self, file_path: str) -> Dict:
        """Extract text and metadata from a PDF document using pdfplumber, returning per-page text blocks for semantic chunking.
        Args:
            file_path: Path to the PDF file
        Returns:
            Dictionary containing:
                - page_texts: List of cleaned text blocks, one per page
                - metadata: Document metadata
        Raises:
            ValueError: If file is not a valid PDF
            FileNotFoundError: If file does not exist
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # Verify file is PDF
        mime_type = magic.from_file(file_path, mime=True)
        if mime_type != 'application/pdf':
            raise ValueError(f"File is not a PDF: {mime_type}")

        try:
            # Extract text per page using pdfplumber
            page_texts = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    cleaned = self._basic_clean(text)
                    page_texts.append(cleaned)

            # Extract metadata using PyPDF2
            metadata = self._extract_metadata(file_path)

            return {
                "page_texts": page_texts,
                "metadata": metadata
            }

        except Exception as e:
            logger.error(f"Failed to extract document: {str(e)}")
            raise
            
    def _basic_clean(self, text: str) -> str:
        """Perform basic text cleaning for OCR artifacts.
        
        Args:
            text: Raw text to clean
            
        Returns:
            Cleaned text
        """
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Fix common OCR artifacts
        text = text.replace('|', 'I')  # Common I/| confusion
        text = re.sub(r'(?<=[a-z])\.(?=[A-Z])', '. ', text)  # Fix missing space after period
        
        return text.strip()
            
    def _extract_metadata(self, file_path: str) -> Dict:
        """Extract metadata from PDF file.
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Dictionary containing metadata fields
        """
        try:
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                
                # Get basic metadata
                info = reader.metadata if reader.metadata else {}
                
                return {
                    "title": info.get('/Title', os.path.basename(file_path)),
                    "author": info.get('/Author', 'Unknown'),
                    "creation_date": self._parse_pdf_date(info.get('/CreationDate')),
                    "last_modified": self._parse_pdf_date(info.get('/ModDate')),
                    "file_type": "pdf",
                    "page_count": len(reader.pages)
                }
                
        except Exception as e:
            logger.error(f"Failed to extract metadata: {str(e)}")
            raise
            
    def _parse_pdf_date(self, date_str: Optional[str]) -> Optional[str]:
        """Parse PDF date string into ISO format.
        
        Args:
            date_str: PDF date string or None
            
        Returns:
            ISO formatted date string or None
        """
        if not date_str:
            return None
            
        try:
            # Remove 'D:' prefix and timezone if present
            date_str = date_str.replace('D:', '')[:14]
            # Parse date
            date = datetime.strptime(date_str, '%Y%m%d%H%M%S')
            # Return ISO format
            return date.isoformat()
        except Exception:
            return None