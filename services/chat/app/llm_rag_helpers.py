import asyncio
import logging
import time
from typing import List, Tuple

import httpx
from models import Chunk, Citation, LLMResponse

logger = logging.getLogger("chat.llm_rag_helpers")

# The System Instruction guides the LLM to use the context and avoid
# hallucination.
RAG_PROMPT_TEMPLATE = """
You are an expert AI assistant for the MARP-Guide.
Your task is to answer the user's question ONLY based on the provided \
CONTEXT.
If the answer is not found in the context, clearly state that you cannot \
answer based on the information provided.
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
    Automatically retries on 429 (rate limit) errors with exponential backoff.
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
        "max_tokens": 2000,
        "temperature": 0.7,
    }
    answer = ""

    # Retry logic for 429 errors (max 5 retries with exponential backoff)
    max_retries = 5
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=60.0,
                )

                # Handle 429 rate limit errors - retry automatically
                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        # Exponential backoff: 2^attempt seconds
                        # (2s, 4s, 8s, 16s, 32s)
                        wait_time = min(2**attempt, 30)  # Cap at 30 seconds
                        logger.info(
                            f"⏳ Rate limited for {model}. "
                            f"Waiting {wait_time}s before retry "
                            f"({attempt + 1}/{max_retries})"
                        )
                        await asyncio.sleep(wait_time)
                        continue  # Retry the request
                    else:
                        # All retries exhausted
                        logger.error(
                            f"❌ Rate limit exceeded for {model} after "
                            f"{max_retries} attempts"
                        )
                        answer = (
                            "[LLM Error] Rate limit exceeded. "
                            "Please wait a moment and try again."
                        )
                        break

                # For other HTTP errors, raise them
                response.raise_for_status()
                data = response.json()

                # Extract answer from LLM response
                if "choices" in data and len(data["choices"]) > 0:
                    answer = data["choices"][0]["message"]["content"]

                    if not answer or not answer.strip():
                        logger.warning(
                            f"Model {model} returned empty content. "
                            f"Full response: {data}"
                        )
                        answer = "The model did not generate a response."
                    else:
                        answer = answer.strip()

                    # Success - break out of retry loop
                    break

        except httpx.HTTPStatusError as e:
            # Handle other HTTP errors
            if e.response.status_code == 429:
                # Should be caught above, but handle here too
                if attempt < max_retries - 1:
                    wait_time = min(2**attempt, 30)
                    logger.info(
                        f"⏳ Rate limited for {model}. "
                        f"Waiting {wait_time}s before retry "
                        f"({attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    answer = (
                        "[LLM Error] Rate limit exceeded. "
                        "Please wait a moment and try again."
                    )
                    break
            else:
                # Other HTTP errors - log and return error
                logger.error(f"HTTP error calling model {model}: {str(e)}")
                answer = f"[LLM Error] {str(e)}"
                break
        except Exception as e:
            # Non-HTTP errors - don't retry, just return error
            logger.error(f"Error calling model {model}: {str(e)}")
            answer = f"[LLM Error] {str(e)}"
            break

    generation_time = time.time() - start_time
    citations = extract_citations(chunks)
    return answer, citations, generation_time


async def generate_answers_parallel(
    query: str, chunks: list, api_key: str, models: List[str]
) -> List[LLMResponse]:
    """
    Calls multiple LLM models in parallel and returns all responses.
    Adds small delays between calls to reduce rate limiting.
    Returns List[LLMResponse] containing responses from all models.
    """
    logger.info(
        f"🤖 Generating answers from {len(models)} models in parallel: " f"{models}"
    )

    # Create tasks with staggered delays to avoid rate limits
    async def call_with_delay(model: str, delay: float):
        """Call model with a delay to space out requests."""
        if delay > 0:
            await asyncio.sleep(delay)
        return await generate_answer_with_citations_async(query, chunks, api_key, model)

    # Stagger requests by 0.3 seconds each to reduce rate limit issues
    tasks = [call_with_delay(model, idx * 0.3) for idx, model in enumerate(models)]

    # Execute all tasks in parallel (they'll start with delays)
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    llm_responses = []
    for model, result in zip(models, results):
        if isinstance(result, Exception):
            logger.error(f"❌ Model {model} failed with exception: {str(result)}")
            llm_responses.append(
                LLMResponse(
                    model=model,
                    answer=(f"[Error] Failed to generate answer: {str(result)}"),
                    citations=[],
                    generation_time=0.0,
                )
            )
        else:
            # Type narrowing: result is a tuple from
            # generate_answer_with_citations_async
            # Check that it's actually a tuple to satisfy mypy
            if not isinstance(result, tuple):
                logger.error(
                    f"❌ Model {model} returned unexpected result type: "
                    f"{type(result)}"
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
    """
    Combines retrieved chunks into a context string and fills the RAG
    template.
    """
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
    """Extracts citation metadata from the retrieved chunks.
    Filters out citations with score below 0.3 threshold.
    Returns empty list if no citations meet the threshold.
    """
    if not chunks:
        logger.warning("⚠️ No chunks provided to extract_citations")
        return []

    logger.info(f"🔍 Extracting citations from {len(chunks)} chunks")

    # First, deduplicate by (title, page, url) and keep best score
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
    logger.info(
        f"📚 Found {len(unique_citations)} unique citations after " f"deduplication"
    )

    # Filter by score threshold (0.3)
    threshold = 0.3
    filtered_citations = [c for c in unique_citations if c.score >= threshold]

    if filtered_citations:
        filtered_citations.sort(key=lambda c: c.score, reverse=True)
        logger.info(
            f"✅ Returning {len(filtered_citations)} citations above "
            f"threshold {threshold}"
        )
        return filtered_citations

    # No citations meet threshold
    logger.warning(
        f"⚠️ No citations meet the score threshold of {threshold}. "
        f"Returning empty list."
    )
    return []
