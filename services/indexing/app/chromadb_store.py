import chromadb
from chromadb.config import Settings
import os
import logging

logger = logging.getLogger("indexing")


def get_chromadb_client():
    """
    Initialize and return a ChromaDB client.
    """
    return chromadb.Client(Settings())

def store_chunks_in_chromadb(chunks, collection_name="chunks", correlation_id=None):
    """
    Store chunk embeddings, text, and metadata in a ChromaDB collection using persistent storage.
    Args:
        chunks: List of dicts with 'embedding', 'text', and optional 'metadata'.
        collection_name: Name of the ChromaDB collection.
    """
    chromadb_path = "/data/chromadb"
    if not os.path.exists(chromadb_path):
        os.makedirs(chromadb_path)
    client = chromadb.PersistentClient(path=chromadb_path)
    collection = client.get_or_create_collection(name=collection_name)

    # Use document_id and chunk_index as unique chunk id if available, else fallback to index
    chunk_ids = []
    for idx, chunk in enumerate(chunks):
        meta = chunk.get("metadata", {})
        doc_id = meta.get("document_id")
        chunk_index = meta.get("chunk_index", idx)
        if doc_id is not None:
            chunk_id = f"{doc_id}_chunk_{chunk_index}"
        else:
            chunk_id = str(idx)
        chunk_ids.append(chunk_id)

    # Check for existing ids in ChromaDB
    existing = set()
    if chunk_ids:
        try:
            existing_results = collection.get(ids=chunk_ids)
            existing = set(existing_results.get('ids', []))
        except Exception as e:
            logger.warning(f"Could not check for existing chunk ids: {e}", extra={"correlation_id": correlation_id})

    # Filter out chunks whose ids already exist
    new_chunks = []
    new_ids = []
    new_embeddings = []
    new_documents = []
    new_metadatas = []
    for idx, chunk in enumerate(chunks):
        chunk_id = chunk_ids[idx]
        if chunk_id in existing:
            logger.info(f"Skipping duplicate chunk with id {chunk_id}", extra={"correlation_id": correlation_id})
            continue
        new_chunks.append(chunk)
        new_ids.append(chunk_id)
        new_embeddings.append(chunk["embedding"])
        new_documents.append(chunk["text"])
        meta = chunk.get("metadata", {})
        if meta is None or not isinstance(meta, dict):
            logger.warning(f"Chunk {idx} has invalid metadata: {meta}. Replacing with empty dict.", extra={"correlation_id": correlation_id})
            meta = {}
        new_metadatas.append(meta)

    logger.info(f"Prepared {len(new_metadatas)} new metadatas for ChromaDB. Example: {new_metadatas[0] if new_metadatas else None}")

    if new_ids:
        collection.add(
            ids=new_ids,
            embeddings=new_embeddings,
            documents=new_documents,
            metadatas=new_metadatas
        )
        logger.info(f"Stored {len(new_chunks)} new chunks in ChromaDB.", extra={"correlation_id": correlation_id})
    else:
        logger.info(f"No new chunks to add (all were duplicates).", extra={"correlation_id": correlation_id})


