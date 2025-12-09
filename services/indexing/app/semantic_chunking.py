import re

import tiktoken


def chunk_document(text: str, metadata: dict, max_tokens: int = 400) -> list:
    """
    Split document into semantic chunks (by paragraph), estimating token count.
    Each chunk is a dict with 'text' and 'metadata'.
    Args:
        text: The full document text.
        metadata: Metadata to attach to each chunk (e.g., title, url, page).
        max_tokens: Target maximum tokens per chunk (default 400).
    Returns:
        List of dicts: [{"text": ..., "metadata": {...}}, ...]
    """

    # Chunking strategy (Semantic): Paragraph level > Sentence level > Token
    # level

    # Split text into paragraphs using double newlines (\n\n)
    # This preserves semantic meaning by keeping natural paragraph boundaries

    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = ""
    chunk_start = 0
    chunk_index = 0

    # Use tiktoken's cl100k_base encoding
    enc = tiktoken.get_encoding("cl100k_base")

    def split_by_tokens(text, max_tokens):
        """Split long text by tokens, preferring sentence boundaries."""
        # Split by sentences (simple regex)
        sentences = re.split(r"(?<=[.!?])\s+", text)
        pieces = []
        current = ""
        for sent in sentences:
            if not sent.strip():
                continue
            candidate = (current + " " + sent).strip() if current else sent.strip()
            if len(enc.encode(candidate)) > max_tokens:
                if current:
                    pieces.append(current.strip())
                # If the sentence itself is too long, split by tokens
                if len(enc.encode(sent)) > max_tokens:
                    tokens = enc.encode(sent)
                    for i in range(0, len(tokens), max_tokens):
                        subtext = enc.decode(tokens[i : i + max_tokens])
                        pieces.append(subtext.strip())
                    current = ""
                else:
                    current = sent.strip()
            else:
                current = candidate
        if current:
            pieces.append(current.strip())
        return pieces

    for para in paragraphs:
        para_tokens = len(enc.encode(para))
        # If paragraph itself is too large, split it further
        if para_tokens > max_tokens:
            subchunks = split_by_tokens(para, max_tokens)
        else:
            subchunks = [para]
        for subchunk in subchunks:
            len(enc.encode(subchunk))
            if current_chunk:
                combined = current_chunk + "\n\n" + subchunk
                combined_tokens = len(enc.encode(combined))
                if combined_tokens > max_tokens:
                    chunk_text = current_chunk.strip()
                    chunk_end = chunk_start + len(chunk_text)
                    chunk_metadata = metadata.copy()
                    chunk_metadata.update(
                        {
                            "chunk_index": chunk_index,
                            "chunk_start": chunk_start,
                            "chunk_end": chunk_end,
                            "chunk_length": len(chunk_text),
                        }
                    )
                    chunks.append({"text": chunk_text, "metadata": chunk_metadata})
                    chunk_index += 1
                    chunk_start = chunk_end + 2  # +2 for the two newlines
                    current_chunk = subchunk
                else:
                    current_chunk = combined
            else:
                current_chunk = subchunk
    # Add the last chunk if any
    if current_chunk.strip():
        chunk_text = current_chunk.strip()
        chunk_end = chunk_start + len(chunk_text)
        chunk_metadata = metadata.copy()
        chunk_metadata.update(
            {
                "chunk_index": chunk_index,
                "chunk_start": chunk_start,
                "chunk_end": chunk_end,
                "chunk_length": len(chunk_text),
            }
        )
        chunks.append({"text": chunk_text, "metadata": chunk_metadata})
    # Check for offset correctness and overlaps
    for i in range(1, len(chunks)):
        prev: dict = chunks[i - 1]["metadata"]  # type: ignore
        curr: dict = chunks[i]["metadata"]  # type: ignore
        if curr["chunk_start"] < prev["chunk_end"]:  # type: ignore
            import logging

            logging.warning(
                f"Chunk offset overlap or out-of-order: chunk {i - 1} ends at "
                f"{prev['chunk_end']}, chunk {i} starts at {curr['chunk_start']}"
            )
    return chunks
