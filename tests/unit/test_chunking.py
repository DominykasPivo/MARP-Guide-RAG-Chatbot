import pytest
import tiktoken  # noqa: F401

from services.indexing.app.semantic_chunking import chunk_document  # noqa: F401

# --- Dependency Stub for Fast, Isolated Tests ---


@pytest.fixture
def sample_metadata():

    return {"title": "TestDoc", "page": 1, "url": "http://example.com"}
