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
    # Split text into paragraphs using double newlines (\n\n)
    # This preserves semantic meaning by keeping natural paragraph boundaries
    paragraphs = text.split('\n\n')
    chunks = []
    current_chunk = ""
    current_tokens = 0
    
    # Use tiktoken's cl100k_base encoding 
    enc = tiktoken.get_encoding("cl100k_base")
    for para in paragraphs:
        para_tokens = len(enc.encode(para))
        # If adding this paragraph would exceed max_tokens, save current chunk
        if current_chunk:
            combined = current_chunk + "\n\n" + para
            combined_tokens = len(enc.encode(combined))
            if combined_tokens > max_tokens:
                chunks.append({
                    "text": current_chunk.strip(),
                    "metadata": metadata.copy()
                })
                current_chunk = para
                current_tokens = para_tokens
            else:
                current_chunk = combined
                current_tokens = combined_tokens
        else:
            current_chunk = para
            current_tokens = para_tokens
    # Add the last chunk if any
    if current_chunk.strip():
        chunks.append({
            "text": current_chunk.strip(),
            "metadata": metadata.copy()
        })
    return chunks
