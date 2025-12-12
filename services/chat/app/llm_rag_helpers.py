import asyncio
import logging
import os
import time
from typing import Any, Dict, List, Tuple

import httpx
from models import Chunk, Citation, LLMResponse

logger = logging.getLogger("chat.llm_rag_helpers")

LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2000"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "60"))
OPENROUTER_API_URL = os.getenv(
    "OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions"
)

logger.info("Started consuming ChunksIndexed events (metrics and logging)")

RAG_PROMPT_TEMPLATE = """
You are an expert AI assistant for the MARP-Guide.
Your task is to answer the user's question ONLY based on the provided CONTEXT.
If the answer is not found in the context, n\
clearly state that you cannot answer based on the information provided.
Do not use any external knowledge.

CONTEXT:
---
{context}
---

QUESTION: "{query}"
"""


async def generate_answer_with_citations_async(
    query: str, chunks: list, api_key: str, model: str
) -> tuple:
    """
    Call an external LLM API asynchronously to generate an answer and extract citations.
    Retries on 429 errors with exponential backoff.
    Returns (answer: str, citations: List[Citation], generation_time: float)
    """
    start_time = time.time()
    rag_prompt = build_rag_prompt(query, chunks)

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
        "max_tokens": LLM_MAX_TOKENS,
        "temperature": LLM_TEMPERATURE,
    }
    answer = ""

    max_retries = 5
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    OPENROUTER_API_URL,
                    headers=headers,
                    json=payload,
                    timeout=float(LLM_TIMEOUT),
                )

                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        wait_time = min(2**attempt, 30)
                        logger.info(
                            f"Rate limited for {model}. Waiting {wait_time}s "
                            f"before retry ({attempt + 1}/{max_retries})"
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error(
                            f"Rate limit exceeded for {model} after "
                            f"{max_retries} attempts"
                        )
                        answer = (
                            "[LLM Error] Rate limit exceeded. "
                            "Please wait and try again."
                        )
                        break

                response.raise_for_status()
                data = response.json()

                if "choices" in data and len(data["choices"]) > 0:
                    answer = data["choices"][0]["message"]["content"]

                    if not answer or not answer.strip():
                        logger.warning(
                            f"Model {model} returned empty content. Response: {data}"
                        )
                        answer = "The model did not generate a response."
                    else:
                        answer = answer.strip()
                    break

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                if attempt < max_retries - 1:
                    wait_time = min(2**attempt, 30)
                    logger.info(
                        f"Rate limited for {model}. Waiting {wait_time}s "
                        f"before retry ({attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    answer = (
                        "[LLM Error] Rate limit exceeded. " "Please wait and try again."
                    )
                    break
            else:
                logger.error(f"HTTP error calling model {model}: {str(e)}")
                answer = f"[LLM Error] {str(e)}"
                break
        except Exception as e:
            logger.error(f"Error calling model {model}: {str(e)}")
            answer = f"[LLM Error] {str(e)}"
            break

    generation_time = time.time() - start_time
    citations = extract_citations(chunks)
    logger.info(
        f"Generating answer for model: {model} "
        f"(context length: {len(rag_prompt)} chars)"
    )
    return answer, citations, generation_time


async def generate_answers_parallel(
    query: str, chunks: list, api_key: str, models: List[str]
) -> List[LLMResponse]:
    """
    Call multiple LLM models in parallel and return responses.
    Adds small delays between calls to reduce rate limiting.
    """
    logger.info(f"Generating answers from {len(models)} models in parallel: {models}")

    async def call_with_delay(model: str, delay: float):
        """Call model with a delayed start to space requests."""
        if delay > 0:
            await asyncio.sleep(delay)
        return await generate_answer_with_citations_async(query, chunks, api_key, model)

    tasks = [call_with_delay(model, idx * 0.3) for idx, model in enumerate(models)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    llm_responses = []
    for model, result in zip(models, results):
        if isinstance(result, Exception):
            logger.error(f"Model {model} failed with exception: {str(result)}")
            llm_responses.append(
                LLMResponse(
                    model=model,
                    answer=f"[Error] Failed to generate answer: {str(result)}",
                    citations=[],
                    generation_time=0.0,
                )
            )
        else:
            if not isinstance(result, tuple):
                logger.error(
                    f"Model {model} returned unexpected result type: {type(result)}"
                )
                llm_responses.append(
                    LLMResponse(
                        model=model,
                        answer="[Error] Unexpected result format",
                        citations=[],
                        generation_time=0.0,
                    )
                )
                continue
            answer, citations, generation_time = result
            logger.info(f"Model {model} completed in {generation_time:.2f}s")
            llm_responses.append(
                LLMResponse(
                    model=model,
                    answer=answer,
                    citations=citations,
                    generation_time=generation_time,
                )
            )

    return llm_responses


def build_rag_prompt(query: str, context_chunks: List[Chunk]) -> str:
    """Build RAG prompt with context from chunks."""
    context_strings = [
        f"Document: {c.title}, Page: {c.page}\nContent: {c.text}"
        for c in context_chunks
    ]
    context = "\n\n---\n\n".join(context_strings)
    return RAG_PROMPT_TEMPLATE.format(context=context, query=query)


def extract_citations(chunks: List[Chunk]) -> List[Citation]:
    """
    Extract citation metadata from retrieved chunks.
    Filters out citations with score below 0.3.
    """
    if not chunks:
        logger.warning("No chunks provided to extract_citations")
        return []

    logger.info(f"Extracting citations from {len(chunks)} chunks")

    citation_map: dict[Tuple[str, int, str], Citation] = {}
    for chunk in chunks:
        key = (chunk.title, chunk.page, chunk.url)
        if key not in citation_map or (chunk.score or 0.0) > citation_map[key].score:
            citation_map[key] = Citation(
                title=chunk.title,
                page=chunk.page,
                url=chunk.url,
                score=chunk.score or 0.0,
            )

    unique_citations = list(citation_map.values())
    logger.info(f"Found {len(unique_citations)} unique citations after deduplication")

    threshold = 0.3
    filtered_citations = [c for c in unique_citations if c.score >= threshold]

    if filtered_citations:
        filtered_citations.sort(key=lambda c: c.score, reverse=True)
        logger.info(
            f"Returning {len(filtered_citations)} citations above threshold {threshold}"
        )
        return filtered_citations

    logger.warning(
        f"No citations meet the score threshold of {threshold}. Returning empty list."
    )
    return []


def _build_context_from_chunks(
    query: str, chunk_list: list[Chunk]
) -> tuple[str, Dict[str, Any]]:
    """Build context string and citation map from chunks."""
    context_parts = []
    citation_map: Dict[str, Any] = {}
    for i, c in enumerate(chunk_list, start=1):
        context_parts.append(f"Chunk {i}: {c.text}")
        citation_map[f"Chunk {i}"] = {
            "title": c.title,
            "page": c.page,
            "url": c.url,
            "score": c.score,
        }
    context = "\n\n".join(context_parts)
    return context, citation_map
