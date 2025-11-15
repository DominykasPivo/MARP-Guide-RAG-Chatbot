import json
from collections import Counter

# Load all points from Qdrant scroll API output (replace with your actual file if needed)
with open('chunks.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# If using /debug/chunks endpoint
chunks = data.get('result', {}).get('points', [])

# If using Qdrant /scroll endpoint, use:
# chunks = data.get('result', {}).get('points', [])

# Extract document_ids
if chunks and 'metadata' in chunks[0]:
    doc_ids = [chunk['metadata']['document_id'] for chunk in chunks if 'metadata' in chunk and 'document_id' in chunk['metadata']]
else:
    # For Qdrant /scroll output
    doc_ids = [chunk['payload']['document_id'] for chunk in chunks if 'payload' in chunk and 'document_id' in chunk['payload']]

unique_doc_ids = set(doc_ids)

print(f"Total chunks: {len(chunks)}")
print(f"Unique documents: {len(unique_doc_ids)}")
print("Document IDs:")
for doc_id in unique_doc_ids:
    print(doc_id)
