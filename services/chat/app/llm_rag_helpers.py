import os
import time
from typing import List

from models import Chunk, Citation, ChatRequest, ChatResponse
from services.chat.app.rabbitmq import publish_rag_job, poll_rag_result

# The System Instruction guides the LLM to use the context and avoid hallucination.
RAG_PROMPT_TEMPLATE = """
You are an expert AI assistant for the MARP-Guide.
Your task is to answer the user's question ONLY based on the provided CONTEXT.
If the answer is not found in the context, clearly state that you cannot answer based on the information provided.
Do not use any external knowledge.

CONTEXT:
---
{context}
---

QUESTION: "{query}"
"""

def build_rag_prompt(query: str, chunks: List[Chunk]) -> str:
    """Combines retrieved chunks into a context string and fills the RAG template."""
    context_strings = [
        # Format the context to include source info directly for the LLM
        f"Document: {c.title}, Page: {c.page}\nContent: {c.text}" 
        for c in chunks
    ]
    context = "\n\n---\n\n".join(context_strings)
    
    # Fill the template
    rag_prompt = RAG_PROMPT_TEMPLATE.format(context=context, query=query)
    return rag_prompt

def extract_citations(chunks: List[Chunk]) -> List[Citation]:
    """Extracts citation metadata from the retrieved chunks."""
    citations = []
    # Use a set to avoid duplicate citations if multiple chunks come from the same page/source
    unique_citations = set()

    for chunk in chunks:
        # Create a tuple key for uniqueness check
        key = (chunk.title, chunk.page, chunk.url)
        if key not in unique_citations:
            unique_citations.add(key)
            citations.append(Citation(
                title=chunk.title,
                page=chunk.page,
                url=chunk.url
            ))
            
    # As a minimum, ensure at least one citation if chunks were retrieved
    if not citations and chunks:
        citations.append(Citation(title="Unknown Source", page=0, url="#"))

    return citations
