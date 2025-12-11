from typing import List, Optional

from pydantic import BaseModel, Field


class Chunk(BaseModel):
    """Retrieved document chunk."""

    text: str = Field(..., description="Content of the document chunk.")
    title: str = Field(..., description="Document name for citation.")
    page: int = Field(..., description="Page number where information appears.")
    url: str = Field(..., description="Direct link to the PDF source.")
    score: Optional[float] = Field(default=0.0, description="Relevance score.")


class Citation(BaseModel):
    """Source citation returned to the user."""

    title: str
    page: int
    url: str
    score: float = Field(default=0.0, description="Relevance score.")


class LLMResponse(BaseModel):
    """Response from a single LLM model."""

    model: str = Field(..., description="LLM model name.")
    answer: str = Field(..., description="Generated answer.")
    citations: List[Citation] = Field(default=[], description="Citations used.")
    generation_time: float = Field(..., description="Time taken in seconds.")


class ChatRequest(BaseModel):
    """Request body for the /chat endpoint."""

    query: str


class ChatResponse(BaseModel):
    """Final response body with multiple LLM responses."""

    responses: List[LLMResponse] = Field(..., description="Responses from models.")
    query: str = Field(..., description="Original query.")
