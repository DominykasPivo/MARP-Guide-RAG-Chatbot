import asyncio
import logging
import time
from typing import List

import httpx
from models import (
    Chunk,
    Citation,
    LLMResponse,
)

logger = logging.getLogger("chat.llm_rag_helpers")

# The System Instruction guides the LLM to use the context and avoid
# hallucination.
RAG_PROMPT_TEMPLATE = """
You are an expert AI assistant for the MARP-Guide.
Your task is to answer the user's question ONLY based on the provided
CONTEXT. If the answer is not found in the context, clearly state that
you cannot answer based on the information provided.
Do not use any external knowledge.

CONTEXT:
---
{context}
---

QUESTION: "{query}"
"""


# Async LLM call version for a single model
async def generate_answer_with_citations_async(
    query: str, chunks: list, api_key: str, model: str
) -> tuple:
    """
    Calls an external LLM API asynchronously to generate an answer and
    extracts citations from the chunks.
    Returns (answer: str, citations: List[Citation], generation_time: float)
    """
    start_time = time.time()
    rag_prompt = build_rag_prompt(query, chunks)

    # Mistral-specific fix: add instruction at the end
    if "mistral" in model.lower():
        rag_prompt = rag_prompt + "\n\nProvide a detailed answer:"

    messages = [{"role": "user", "content": rag_prompt}]
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 2000,  # Increase token limit
        "temperature": 0.7,
    }
    answer = ""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()

            # Extract answer from LLM response (OpenAI/compatible format)
            if "choices" in data and len(data["choices"]) > 0:
                answer = data["choices"][0]["message"]["content"]

                # Log if empty
                if not answer or not answer.strip():
                    logger.warning(
                        f"Model {model} returned empty content. "
                        f"Full response: {data}"
                    )
                    answer = "The model did not generate a response."
                else:
                    answer = answer.strip()

    except Exception as e:
        logger.error(f"Error calling model {model}: {str(e)}")
        answer = f"[LLM Error] {str(e)}"

    generation_time = time.time() - start_time
    citations = extract_citations(chunks)
    return answer, citations, generation_time


async def generate_answers_parallel(
    query: str, chunks: list, api_key: str, models: List[str]
) -> List[LLMResponse]:
    """
    Calls multiple LLM models in parallel and returns all responses.
    Returns List[LLMResponse] containing responses from all models.
    """
    logger.info(
        f"🤖 Generating answers from {len(models)} models in parallel: "
        f"{models[:3]}..."
        if len(models) > 3
        else f"{models}"
    )

    # Create tasks for all models
    tasks = [
        generate_answer_with_citations_async(query, chunks, api_key, model)
        for model in models
    ]

    # Execute all tasks in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    llm_responses = []
    for model, result in zip(models, results):
        if isinstance(result, Exception):
            logger.error(f"❌ Model {model} failed with exception: {str(result)}")
            llm_responses.append(
                LLMResponse(
                    model=model,
                    answer=f"[Error] Failed to generate answer: {str(result)}",
                    citations=[],
                    generation_time=0.0,
                )
            )
        else:
            answer, citations, generation_time = result  # type: ignore
            logger.info(f"✅ Model {model} completed in {generation_time:.2f}s")
            llm_responses.append(
                LLMResponse(
                    model=model,
                    answer=answer,
                    citations=citations,
                    generation_time=generation_time,
                )
            )

    return llm_responses


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
    # Use a set to avoid duplicate citations if multiple chunks come from the
    # same page/source
    unique_citations = set()

    for chunk in chunks:
        # Create a tuple key for uniqueness check
        key = (chunk.title, chunk.page, chunk.url)
        if key not in unique_citations:
            unique_citations.add(key)
            citations.append(
                Citation(title=chunk.title, page=chunk.page, url=chunk.url)
            )

    # As a minimum, ensure at least one citation if chunks were retrieved
    if not citations and chunks:
        citations.append(Citation(title="Unknown Source", page=0, url="#"))

    return citations
