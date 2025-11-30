import pytest
import tiktoken
from services.indexing.app.semantic_chunking import chunk_document

# --- Dependency Stub for Fast, Isolated Tests ---

@pytest.fixture
def sample_metadata():
	return {"title": "TestDoc", "page": 1, "url": "http://example.com"}

def test_chunk_document_respects_max_tokens(sample_metadata):
	"""Test that chunks do not exceed max_tokens (token count)"""
	text = "A" * 1000
	max_tokens = 400
	chunks = chunk_document(text, sample_metadata, max_tokens=max_tokens)
	enc = tiktoken.get_encoding("cl100k_base")
	# Assert all chunks are within max_tokens (token count)
	assert all(len(enc.encode(chunk["text"])) <= max_tokens for chunk in chunks)

def test_chunk_document_handles_empty_input(sample_metadata):
	"""Test chunking with empty string"""
	chunks = chunk_document("", sample_metadata, max_tokens=400)
	assert chunks == []

# Edge case: Very short text
def test_chunk_document_short_text(sample_metadata):   
	text = "Short"
	chunks = chunk_document(text, sample_metadata, max_tokens=10)
	assert len(chunks) == 1
	assert chunks[0]["text"] == text

# Edge case: Text exactly at token limit
def test_chunk_document_exact_token_limit(sample_metadata):
	enc = tiktoken.get_encoding("cl100k_base")
	text = "A" * 400
	chunks = chunk_document(text, sample_metadata, max_tokens=400)
	# Only check that the output chunk does not exceed max_tokens
	assert len(chunks) == 1
	assert len(enc.encode(chunks[0]["text"])) <= 400

# Edge case: Lots of whitespace/newlines
def test_chunk_document_whitespace(sample_metadata): 
	text = "\n\n   \n\n"
	chunks = chunk_document(text, sample_metadata, max_tokens=10)
	# Should ignore empty chunks
	assert all(chunk["text"].strip() != "" for chunk in chunks)

# Edge case: Long sentence/paragraph
def test_chunk_document_long_sentence(sample_metadata): 
	text = "A" * 1000
	chunks = chunk_document(text, sample_metadata, max_tokens=100)
	enc = tiktoken.get_encoding("cl100k_base")
	assert all(len(enc.encode(chunk["text"])) <= 100 for chunk in chunks)

# Edge case: Unicode/multi-byte characters
def test_chunk_document_unicode(sample_metadata): 
	text = "😀" * 50
	chunks = chunk_document(text, sample_metadata, max_tokens=10)
	assert all("😀" in chunk["text"] for chunk in chunks)

# Edge case: Special characters
def test_chunk_document_special_chars(sample_metadata): 
	text = "!@#$%^&*()_+-=[]{}|;':,./<>?"
	chunks = chunk_document(text, sample_metadata, max_tokens=10)
	assert any(any(c in chunk["text"] for c in text) for chunk in chunks)

# Edge case: Metadata missing/empty/unusual
def test_chunk_document_empty_metadata():
	text = "A" * 100
	chunks = chunk_document(text, {}, max_tokens=50)
	assert all("metadata" in chunk for chunk in chunks)

# Edge case: Overlapping chunks (simulate by using paragraph breaks)
def test_chunk_document_overlap(sample_metadata):
	text = "Para1\n\nPara2" + "A" * 100
	chunks = chunk_document(text, sample_metadata, max_tokens=50)
	# Check chunk indices are unique and ordered
	indices = [chunk["metadata"]["chunk_index"] for chunk in chunks]
	assert indices == sorted(indices)

# Edge case: Large document
def test_chunk_document_large_doc(sample_metadata):
	text = "A" * 10000
	chunks = chunk_document(text, sample_metadata, max_tokens=500)
	assert len(chunks) > 0

# Edge case: Invalid input types
import pytest
def test_chunk_document_invalid_input():
	with pytest.raises(Exception):
		chunk_document(123, {}, max_tokens=10)
	with pytest.raises(Exception):
		chunk_document("text", "notadict", max_tokens=10)
