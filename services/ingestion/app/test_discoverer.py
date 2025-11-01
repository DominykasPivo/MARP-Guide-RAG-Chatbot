"""Test script for MARP document discoverer."""
import os
import sys
from pathlib import Path

# Add the app directory to Python path
sys.path.append(str(Path(__file__).parent))

from discoverer import MARPDocumentDiscoverer

def main():
    # Create a storage directory in the current folder
    storage_dir = os.path.join(os.path.dirname(__file__), 'storage')
    os.makedirs(storage_dir, exist_ok=True)
    
    # Initialize the discoverer
    discoverer = MARPDocumentDiscoverer(storage_dir)
    
    print("Starting MARP document discovery...")
    
    # First test: just discover URLs
    print("\nTesting URL discovery:")
    urls = discoverer.discover_document_urls()
    print(f"Found {len(urls)} PDF URLs:")
    for url in urls[:5]:  # Show first 5 URLs
        print(f"- {url}")
    
    # Second test: process documents
    print("\nTesting document processing:")
    discovered = discoverer.discover_and_process_documents()
    print(f"\nDiscovered {len(discovered)} new/updated documents:")
    for doc in discovered:
            print(f"\nDocument: {doc.title}")
            print(f"ID: {doc.document_id}")
            print(f"URL: {doc.source_url}")
            print(f"Stored at: {doc.file_path}")
            print(f"Discovered at: {doc.discovered_at}")
            print(f"Last modified: {doc.last_modified}")
            print(f"Pages: {doc.page_count}")

if __name__ == "__main__":
    main()