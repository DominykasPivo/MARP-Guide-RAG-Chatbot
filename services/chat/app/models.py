import os
import time
import json
from typing import List, Optional
from pydantic import BaseModel, Field

class Chunk(BaseModel):
    """Represents a retrieved document chunk."""
    text: str = Field(..., description="The content of the document chunk.")
    title: str = Field(..., description="Document name for citation (e.g., 'General Regulations').")
    page: int = Field(..., description="Page number where information appears.")
    url: str = Field(..., description="Direct link to the PDF source.")
    score: Optional[float] = Field(default=0.0, description="Relevance score of the chunk.")

class Citation(BaseModel):
    """Represents a source citation returned to the user."""
    title: str
    page: int
    url: str
    score: float = Field(default=0.0, description="Relevance score of this citation.")

class LLMResponse(BaseModel):
    """Represents a response from a single LLM model."""
    model: str = Field(..., description="Name of the LLM model used (e.g., 'claude-3.5-sonnet').")
    answer: str = Field(..., description="The generated answer from this model.")
    citations: List[Citation] = Field(default=[], description="Citations used for this answer.")
    generation_time: float = Field(..., description="Time taken to generate this response in seconds.")

class ChatRequest(BaseModel):
    """The request body for the /chat endpoint."""
    query: str

class ChatResponse(BaseModel):
    """The final response body for the user with multiple LLM responses."""
    responses: List[LLMResponse] = Field(..., description="Responses from different LLM models.")
    query: str = Field(..., description="The original query.")