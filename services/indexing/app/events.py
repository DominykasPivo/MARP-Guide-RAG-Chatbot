# --- Event processing logic for indexing service ---
from tenacity import retry, stop_after_attempt, wait_exponential
import json, uuid
from datetime import datetime
import logging
import qdrant_client
import os
from semantic_chunking import chunk_document
from embed_chunks import embed_chunks
from qdrant_store import store_chunks_in_qdrant
from rabbitmq import pika, EXCHANGE_NAME
from enum import Enum
from typing import Dict
from dataclasses import dataclass
import uuid

EVENT_VERSION = os.getenv("EVENT_VERSION", "1.0")


logger = logging.getLogger('indexing.events')


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def process_extracted_event(message):
    # logger.info(f"📨 Received raw message: {json.dumps(message, indent=2)}")

    # Check if this is a valid document.extracted event
    data = message.get("data", {})
    event_type = data.get("eventType")
    if event_type != "DocumentExtracted":
        logger.warning(f"⚠️  Ignoring non-document.extracted event: {event_type}")
        return

    # Extract fields from the DocumentExtracted event
    payload = data.get("payload", {})
    document_id = payload.get("documentId")
    text_content = payload.get("textContent", "")
    extracted_at = payload.get("extractedAt")

    # Log the payload structure for debugging (removed for cleaner logs)
    # logger.info(f"🔍 Payload structure: {list(payload.keys())}")
    # logger.info(f"📄 Document ID: {document_id}, Text length: {len(text_content)}")

    if not document_id:
        logger.error(f"❌ No documentId found in payload")
        return

    if not text_content:
        logger.error(f"❌ Document {document_id} has no text content to process. Full payload: {json.dumps(payload, indent=2)}")
        return

    # Get metadata
    metadata = payload.get("metadata", {})
    file_type = metadata.get("fileType", payload.get("fileType", "unknown"))
    correlation_id = data.get("correlationId")

    # logger.info(f"✅ Processing document {document_id} with {len(text_content)} characters", extra={"correlation_id": correlation_id})


    # --- Per-page chunking for correct page metadata ---
    page_texts = payload.get("page_texts")
    all_chunks = []
    if page_texts and isinstance(page_texts, list):
        for page_num, page_text in enumerate(page_texts, start=1):
            chunk_metadata = {
                "document_id": document_id,
                "file_type": file_type,
                "correlation_id": correlation_id,
                **metadata,
                "page": page_num
            }
            url = metadata.get("url") or metadata.get("sourceUrl")
            if url is not None:
                chunk_metadata["url"] = url
            chunks = chunk_document(page_text, chunk_metadata)
            all_chunks.extend(chunks)
        # logger.info(f"📊 Generated {len(all_chunks)} chunks from document {document_id} (per-page)", extra={"correlation_id": correlation_id})
    else:
        # Fallback: chunk the whole document as before
        chunk_metadata = {
            "document_id": document_id,
            "file_type": file_type,
            "correlation_id": correlation_id,
            **metadata
        }
        url = metadata.get("url") or metadata.get("sourceUrl")
        if url is not None:
            chunk_metadata["url"] = url
        all_chunks = chunk_document(text_content, chunk_metadata)
        # logger.info(f"📊 Generated {len(all_chunks)} chunks from document {document_id} (whole doc)", extra={"correlation_id": correlation_id})



    # Assign unique, sequential chunk_index to each chunk
    for idx, chunk in enumerate(all_chunks):
        chunk['metadata']['chunk_index'] = idx

    # Debug: Log all_chunks before deduplication
    # logger.info(f"DEBUG: all_chunks count for {document_id}: {len(all_chunks)}")
    # for idx, chunk in enumerate(all_chunks):
    #     logger.info(f"DEBUG: all_chunks[{idx}] chunk_index={{}} text_len={{}}".format(chunk['metadata'].get('chunk_index'), len(chunk['text'])))

    # Deduplicate chunks by text before embedding
    unique_chunks = []
    seen_texts = set()
    for chunk in all_chunks:
        text = chunk.get('text', '').strip()
        if text and text not in seen_texts:
            unique_chunks.append(chunk)
            seen_texts.add(text)
    chunks = unique_chunks

    # Debug: Log chunks after deduplication
    # logger.info(f"DEBUG: unique_chunks count for {document_id}: {len(chunks)}")
    # for idx, chunk in enumerate(chunks):
    #     logger.info(f"DEBUG: unique_chunks[{idx}] chunk_index={{}} text_len={{}}".format(chunk['metadata'].get('chunk_index'), len(chunk['text'])))

    # ADD DEBUG: Check what chunks look like before embedding
    # if chunks:
    #     first_chunk = chunks[0]
    #     logger.info(f"🔍 First chunk structure: keys={list(first_chunk.keys())}, text_length={len(first_chunk.get('text', ''))}", extra={"correlation_id": correlation_id})

    embedded_chunks = embed_chunks(chunks, correlation_id=correlation_id)

    # ADD DEBUG: Check what embedded chunks look like
    # logger.info(f"📊 Generated {len(embedded_chunks)} embedded chunks", extra={"correlation_id": correlation_id})
    # if embedded_chunks:
    #     first_embedded = embedded_chunks[0]
    #     logger.info(f"🔍 First embedded chunk: has_text={bool(first_embedded.get('text'))}, has_embedding={bool(first_embedded.get('embedding'))}, has_metadata={bool(first_embedded.get('metadata'))}", extra={"correlation_id": correlation_id})
    #     if first_embedded.get('embedding'):
    #         logger.info(f"🔍 Embedding length: {len(first_embedded['embedding'])}", extra={"correlation_id": correlation_id})

    # Log details of each chunk before storing  """"""""""
    # for idx, chunk in enumerate(embedded_chunks):
    #     chunk_id = chunk.get('metadata', {}).get('chunk_id', f"{document_id}_chunk_{idx}")
    #     meta = chunk.get('metadata', {})
    #     text_preview = chunk.get('text', '')[:100].replace('\n', ' ')
    #     logger.info(
    #         f"📝 Chunk {idx}: id={chunk_id}, meta={json.dumps(meta)}, text_preview='{text_preview}'",
    #         extra={"correlation_id": correlation_id}
    #     )


    # Store in Qdrant
    store_chunks_in_qdrant(embedded_chunks, collection_name="chunks", correlation_id=correlation_id)
    logger.info(f"✅ Stored {len(embedded_chunks)} chunks in Qdrant", extra={"correlation_id": correlation_id})

    # Publish ChunksIndexed events (one per chunk)
    embedding_model = "all-MiniLM-L6-v2"
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host="rabbitmq"))
        channel = connection.channel()
        channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type='topic', durable=True)
        total_chunks = len(embedded_chunks)
        published_count = 0
        for chunk in embedded_chunks:
            chunk_meta = chunk.get("metadata", {})
            chunk_index = chunk_meta.get("chunk_index", 0)
            chunk_id = f"{document_id}_chunk_{chunk_index}"
            indexed_event = {
                "eventType": "ChunksIndexed",
                "eventId": str(uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat(),
                "correlationId": correlation_id,
                "source": "indexing-service",
                "version": EVENT_VERSION,
                "payload": {
                    "documentId": document_id,
                    "chunkId": chunk_id,
                    "chunkIndex": chunk_index,
                    "chunkText": chunk["text"][:2000] + "..." if len(chunk["text"]) > 2000 else chunk["text"],
                    "totalChunks": total_chunks,
                    "embeddingModel": embedding_model,
                    "metadata": {
                        "title": chunk_meta.get("title", "Unknown Title"),
                        "pageCount": chunk_meta.get("pageCount", 0),
                        "sourceUrl": chunk_meta.get("sourceUrl", "Unknown Source")
                    },
                    "indexedAt": datetime.utcnow().isoformat()
                }
            }
            # Log the ChunksIndexed event without chunkText for brevity
            indexed_event_log = dict(indexed_event)
            if "payload" in indexed_event_log:
                indexed_event_log["payload"] = dict(indexed_event_log["payload"])
                if "chunkText" in indexed_event_log["payload"]:
                    indexed_event_log["payload"]["chunkText"] = "<omitted>"
            event_json = json.dumps(indexed_event_log, indent=2, ensure_ascii=False)
            logger.info(f"\n========== 📦 ChunksIndexed Event ==========" \
                        f"\n{event_json[:4000]}" \
                        f"\n============================================", extra={"correlation_id": correlation_id})
            channel.basic_publish(
                exchange=EXCHANGE_NAME,
                routing_key="chunks.indexed",
                body=json.dumps(indexed_event),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    content_type='application/json',
                    correlation_id=correlation_id
                )
            )
            published_count += 1
        connection.close()
        logger.info(f"📤 Published {published_count} ChunksIndexed events for document {document_id}", extra={"correlation_id": correlation_id})
    except Exception as e:
        logger.error(f"❌ Failed to publish ChunksIndexed events: {e}", extra={"correlation_id": correlation_id}, exc_info=True)

class EventTypes(Enum):
    """
    Events that the indexing service handles and emits.
    """
    DOCUMENT_EXTRACTED = "document.extracted"  # Consumed from extraction service
    CHUNKS_INDEXED = "chunks.indexed"      # Emitted after successful chunk indexing

@dataclass
class DocumentExtracted:
    """Event data for an extracted document."""
    eventType: str
    eventId: str
    timestamp: str
    correlationId: str
    source: str
    version: str
    payload: Dict 

    # "payload": {
    #     "documentId": "string",
    #     "textContent": "string",
    #     "metadata": {
    #       "title": "string",
    #       "sourceUrl": "string",
    #       "fileType": "string",
    #       "pageCount": "integer"
    #     },
    #     "extractedAt": "string"
    #   }
@dataclass
class ChunksIndexed:
    """Emitted after a document is successfully indexed."""
    eventType: str
    eventId: str
    timestamp: str
    correlationId: str
    source: str
    version: str
    payload: Dict 
    

    #         "eventType": "ChunksIndexed",
    #         "eventId": str(uuid.uuid4()),
    #         "timestamp": datetime.utcnow().isoformat(),
    #         "correlationId": self.correlation_id,
    #         "source": "indexing-service",
    #         "version": "1.0",
    #         "payload": {
    #             "documentId": self.document_id,
    #             "chunkId": self.chunk_id,
    #             "chunkIndex": self.chunk_index,
    #             "chunkText": self.chunk_text,
    #             "totalChunks": self.total_chunks,
    #             "embeddingModel": self.embedding_model,
    #             "metadata": {
    #                 "title": self.metadata.get("title", "Unknown Title"),
    #                 "pageCount": self.metadata.get("pageCount", 0),
    #                 "sourceUrl": self.metadata.get("sourceUrl", "Unknown Source")
    #             },
    #             "indexedAt": self.indexed_at
    #         }

