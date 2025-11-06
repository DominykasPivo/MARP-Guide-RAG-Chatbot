import os
import time
import json
from typing import List
from pydantic import BaseModel, Field

class Chunk(BaseModel):
    """Represents a retrieved document chunk."""
    text: str = Field(..., description="The content of the document chunk.")
    title: str = Field(..., description="Document name for citation (e.g., 'General Regulations').")
    page: int = Field(..., description="Page number where information appears.")
    url: str = Field(..., description="Direct link to the PDF source.")

class Citation(BaseModel):
    """Represents a source citation returned to the user."""
    title: str
    page: int
    url: str

class ChatRequest(BaseModel):
    """The request body for the /chat endpoint."""
    query: str

class ChatResponse(BaseModel):
    """The final response body for the user."""
    answer: str
    citations: List[Citation]