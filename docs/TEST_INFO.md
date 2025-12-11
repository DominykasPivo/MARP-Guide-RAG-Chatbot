# Testing Guide

## Overview

This document provides comprehensive information about the testing infrastructure for the MARP Guide RAG Chatbot project. The project uses a multi-layered testing approach with unit, integration, and end-to-end tests to ensure code quality, reliability, and maintainability.

### Test Statistics

- **Total Tests**: 287+ tests across unit and integration suites
- **Status**: ✅ All passing, 0 skipped
- **Test Files**: 3 unit test files, 6 integration test files
- **Services Covered**: All 5 microservices (ingestion, extraction, indexing, retrieval, chat)
- **Coverage Target**: ≥85% combined coverage

## Table of Contents

- [Testing Strategy](#testing-strategy)
- [Test Structure](#test-structure)
- [Running Tests](#running-tests)
- [Unit Tests](#unit-tests)
- [Integration Tests](#integration-tests)
- [Code Coverage](#code-coverage)
- [CI/CD Integration](#cicd-integration)
- [Writing Tests](#writing-tests)
- [Testing Tools](#testing-tools)
- [Troubleshooting](#troubleshooting)

---

## Testing Strategy

The project follows a **pyramid testing strategy**:

1. **Unit Tests (Foundation)** – Fast, isolated tests for individual functions, classes, and modules using mocks and stubs.
2. **Integration Tests (Middle)** – Validate service interactions and workflows, primarily using fakes and mocks to simulate external dependencies (e.g., fake vector DBs, fake storage, mocked APIs). These tests do not require the full application stack to be running and are designed for speed and reliability.
3. **System Tests (Top)** – Docker-based validation of the complete system, with all services running for true end-to-end (E2E) testing. These tests exercise the full deployed stack and validate real service interactions.

**Note:** Integration tests in this project use fakes and mocks for external dependencies, allowing for fast feedback and deterministic results. For full E2E validation, use the system tests with Docker Compose.

### Testing Principles

- **Isolation**: Unit and integration tests avoid real external services by using mocks and fakes
- **Speed**: Fast feedback loop for developers
- **Reliability**: Deterministic tests that pass consistently
- **Coverage**: Comprehensive coverage of critical paths
- **Maintainability**: Clear, readable test code
- **Realism**: System/E2E tests validate the full stack with real service interactions

---

## Test Structure

```
tests/
├── __init__.py
├── conftest.py                     # Shared fixtures and configuration
├── unit/                           # Unit tests (fast, isolated)
│   ├── __init__.py
│   ├── test_chat.py               # Chat service (RAG, citations, events)
│   ├── test_chat_service.py       # Chat service (MARP quality, filtering)
│   └── test_retrieval.py          # Retrieval service (all retrieval logic)
│
├── integration/                    # Integration tests (slower, multi-component)
│   ├── __init__.py
│   ├── test_e2e_pipeline.py       # Complete pipeline with real PDFs
│   ├── test_end_to_end_flow.py    # Event flows & schema validation
│   ├── test_indexing_flow.py      # Indexing pipeline tests
│   ├── test_ingestion_app.py      # Ingestion FastAPI endpoints
│   ├── test_ingestion_flow.py     # End-to-end ingestion with fakes
│   ├── test_search_api.py         # Search API integration
│   └── test_vector_components.py  # Vector store & DB client tests
│
└── coverage/                       # Coverage reports
    ├── unit.xml                    # Unit test coverage (XML)
    ├── integration.xml             # Integration test coverage (XML)
    ├── unit_html/                  # Unit coverage HTML report
    └── integration_html/           # Integration coverage HTML report
```

---

## Running Tests

### Prerequisites

```bash
# Install dependencies
pip install -r services/ingestion/requirements.txt
pip install -r services/extraction/requirements.txt
pip install -r services/indexing/requirements.txt
pip install -r services/chat/requirements.txt
pip install -r services/retrieval/requirements.txt

# Install test tools
pip install pytest pytest-cov coverage
```

### Run All Tests

```bash
# Run all tests (unit + integration)
pytest

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov --cov-report=html
```

### Run Unit Tests Only

```bash
# Run all unit tests
pytest tests/unit/

# Run specific test file
pytest tests/unit/test_chat_service.py

# Run specific test function
pytest tests/unit/test_chat_service.py::TestChatServiceEvents::test_query_received_event

# Run with coverage
pytest tests/unit/ --cov --cov-report=html:coverage/unit_html --cov-report=xml:coverage/unit.xml
```

### Run Integration Tests Only

```bash
# Run all integration tests
pytest tests/integration/

# Run specific integration test
pytest tests/integration/test_ingestion_flow.py

# Run with verbose output
pytest tests/integration/ -v

# Run with coverage
pytest tests/integration/ --cov --cov-report=html:coverage/integration_html --cov-report=xml:coverage/integration.xml
```

---

## Unit Tests

Unit tests focus on testing individual functions, classes, and modules in isolation using mocks and stubs.

### Test Summary

- **Total Unit Tests**: 100+ tests across 3 test files
- **Status**: ✅ All passing, 0 skipped
- **Coverage Target**: ≥80% line coverage

### Coverage by Service

| Service | Test File | Focus Areas | Tests |
|---------|-----------|-------------|-------|
| **Chat** | `test_chat.py`<br>`test_chat_service.py` | RAG prompt generation<br>Citation extraction & filtering<br>Event structures<br>Correlation ID tracking<br>MARP quality requirements | 50+ |
| **Retrieval** | `test_retrieval.py` | Vector search<br>Query processing<br>Result ranking<br>RabbitMQ integration<br>API endpoints | 50+ |

### Key Test Files

#### `test_chat.py` (Unit Tests)

Comprehensive tests for chat service business logic:

- **RAG Prompt Generation**: Tests for `build_rag_prompt()` with chunks, empty chunks, formatting
- **Citation Extraction**: Tests for `extract_citations()` including filtering (<0.3 threshold), deduplication, sorting
- **Citation Filtering**: Tests for `filter_top_citations()` with min_citations enforcement
- **Event Structures**: Tests for `QueryReceived`, `ChunksRetrieved` event creation
- **Correlation ID**: Tests for correlation ID propagation through events
- **Context Building**: Tests for multi-chunk context assembly

#### `test_chat_service.py` (Unit Tests)

MARP-specific chat quality tests:

- **Citation Filtering**: Minimum citation enforcement, score-based sorting
- **Event Handling**: Query received, chunks retrieved event structures
- **Response Formatting**: Answer formatting with citations, required fields
- **Context Awareness**: Context from retrieved chunks with metadata

#### `test_retrieval.py` (Consolidated Unit Tests)

All retrieval service testing consolidated into one file:

- **Vector Search**: Query embedding, similarity search, result ranking
- **API Endpoints**: `/search` endpoint validation, error handling
- **Result Processing**: Deduplication, score filtering, metadata preservation
- **RabbitMQ Integration**: Event publishing, consumption, error recovery
- **Service Health**: Health check endpoints, dependency status

---

## Integration Tests

Integration tests validate interactions between multiple components and services, using fakes and mocks for external dependencies.

### Test Summary

- **Total Integration Tests**: 150+ tests across 6 test files
- **Status**: ✅ All passing, 0 skipped
- **Coverage Target**: ≥70% line coverage

### Test Files Overview

#### `test_ingestion_flow.py`

End-to-end ingestion with fakes and mocks:

- **PDF Link Extraction**: Tests for `PDFLinkExtractor` with sample HTML
- **Document Storage**: Store, retrieve, delete, update operations
- **Document Discovery**: Skip unchanged, detect updates
- **Fake Components**: `FakeQdrantClient`, `FakeRabbitMQ` for isolated testing
- **Edge Cases**: Corrupted index, concurrent access, missing files

#### `test_ingestion_app.py`

Ingestion service FastAPI application tests:

- **Endpoints**: `/`, `/health`, `/documents`, `/documents/{id}`, `/discovery/start`
- **Health Checks**: RabbitMQ dependency status
- **Background Tasks**: Discovery background execution, threading
- **Error Handling**: Storage errors, missing documents, discovery failures

#### `test_search_api.py`

Search API integration tests:

- **Search Endpoint**: `/search` with query validation, empty/missing queries
- **Result Validation**: Score filtering, deduplication, pagination
- **Edge Cases**: Large top_k, invalid top_k, special characters, Unicode queries
- **Error Handling**: Malformed requests, empty database, partial metadata

#### `test_vector_components.py`

Vector store and DB client tests:

- **VectorStore Initialization**: Environment variables, defaults
- **Collection Management**: Refresh collection, collection existence checks
- **Query Operations**: `query_by_text()` with limits, exception handling
- **Performance**: Long query truncation (100 chars)

#### `test_indexing_flow.py`

Document indexing pipeline tests:

- **Embedding Generation**: Vector creation, structure validation
- **Qdrant Integration**: Client initialization, chunk storage
- **Event Generation**: `ChunksIndexed` event creation, correlation
- **Metadata Preservation**: Chunk metadata structure, index assignment
- **RabbitMQ**: Event publishing structure, exchange configuration

#### `test_end_to_end_flow.py`

Event-driven workflow and schema validation:

- **Correlation ID Propagation**: Through ingestion → extraction → indexing → retrieval → chat
- **Event Schemas**: `DocumentDiscovered`, `DocumentExtracted`, `ChunksIndexed`, `QueryReceived`, `ChunksRetrieved`
- **Event Serialization**: JSON serialization/deserialization
- **Error Handling**: Malformed events, missing fields, empty content
- **Document Lifecycle**: Complete flow validation

#### `test_e2e_pipeline.py`

Complete pipeline with real MARP PDFs:

- **Ingestion → Extraction**: Document storage, text extraction
- **Extraction → Indexing**: Chunking, embedding generation
- **Indexing → Retrieval**: Vector search (mocked)
- **Full Pipeline**: Complete document lifecycle
- **Data Quality**: No data loss, chunk sizing, text cleaning
- **Performance**: Extraction and chunking performance benchmarks

---

## Code Coverage

### Coverage Goals

- **Unit Tests**: ≥ 80% line coverage
- **Integration Tests**: ≥ 70% line coverage
- **Combined**: ≥ 85% line coverage

### Generating Coverage Reports

```bash
# Generate HTML coverage report (unit)
pytest tests/unit/ --cov --cov-report=html:coverage/unit_html

# Generate HTML coverage report (integration)
pytest tests/integration/ --cov --cov-report=html:coverage/integration_html

# Generate XML report for CI/CD
pytest tests/unit/ --cov --cov-report=xml:coverage/unit.xml
pytest tests/integration/ --cov --cov-report=xml:coverage/integration.xml

# View HTML report
# Open coverage/unit_html/index.html in browser
```

### Understanding Coverage Reports

- **Line Coverage**: Percentage of code lines executed during tests
- **Branch Coverage**: Percentage of conditional branches tested
- **Function Coverage**: Percentage of functions called
- **Missing Lines**: Lines not covered by any test

### Improving Coverage

1. Identify uncovered code: `coverage report --show-missing`
2. Write tests for critical paths first
3. Use parametrized tests for multiple scenarios
4. Test error handling and edge cases

---

## CI/CD Integration

### GitHub Actions Workflow

The project uses GitHub Actions for continuous integration (`.github/workflows/ci.yml`):

```yaml
jobs:
  lint:           # Code quality checks
  type-check:     # Static type analysis
  security-scan:  # Security vulnerability scanning
  unit-tests:     # Unit test execution
  integration-tests: # Integration test execution
  docker-build:   # Docker image validation
```

### Test Matrix

Unit tests run across multiple Python versions:
- Python 3.10
- Python 3.11
- Python 3.12

### Coverage Upload

Coverage reports are automatically uploaded to:
- **Codecov**: For PR comments and coverage tracking
- **Artifacts**: Downloadable HTML reports for each run

### CI Test Commands

```bash
# Lint checks
black --check .
isort --check-only .
flake8 services/

# Type checks
mypy services/

# Security scans
bandit -r services/
safety check

# Unit tests (with coverage)
pytest tests/unit/ --cov --cov-report=xml:coverage/unit.xml --cov-report=html:coverage/unit_html

# Integration tests (with coverage)
pytest tests/integration/ --cov --cov-report=xml:coverage/integration.xml --cov-report=html:coverage/integration_html

# Docker builds
docker build -f services/chat/Dockerfile -t marp-chat:test services/chat
```

---

## Writing Tests

### Unit Test Template

```python
"""Unit tests for [module_name]"""
import pytest
from unittest.mock import Mock, patch


class Test[ComponentName]:
    """Test suite for [ComponentName]"""

    @pytest.fixture
    def mock_dependency(self):
        """Fixture for mocking external dependency"""
        return Mock()

    def test_[function_name]_success(self, mock_dependency):
        """Test [function_name] with valid input"""
        # Arrange
        input_data = "test input"
        expected_output = "expected result"

        # Act
        result = function_under_test(input_data)

        # Assert
        assert result == expected_output

    def test_[function_name]_error_handling(self):
        """Test [function_name] error handling"""
        with pytest.raises(ValueError):
            function_under_test(invalid_input)
```

### Integration Test Template

```python
"""Integration tests for [feature_name]"""
import pytest
from unittest.mock import Mock, patch


@pytest.fixture
def fake_external_service():
    """Create fake external service for testing"""
    class FakeService:
        def __init__(self):
            self.data = []
        
        def store(self, item):
            self.data.append(item)
            return True
    
    return FakeService()


def test_[component]_integration(fake_external_service):
    """Test [component] with fake dependencies"""
    # Arrange
    test_data = {"key": "value"}

    # Act
    result = component_under_test(test_data, fake_external_service)

    # Assert
    assert result is not None
    assert len(fake_external_service.data) == 1
```

---

## Testing Tools

### Core Testing Framework

- **pytest** (v7.4+): Primary test runner
- **pytest-cov** (v5.0.0): Coverage plugin
- **coverage** (v7.5.1): Coverage measurement

### Mocking and Fixtures

- **unittest.mock**: Built-in mocking library
- **pytest fixtures**: Test setup and teardown
- **MagicMock**: Advanced mocking for complex objects

### API Testing

- **FastAPI TestClient**: HTTP client for testing endpoints
- **httpx**: Async HTTP client testing

### Quality Tools

- **black** (v25.11.0): Code formatting
- **isort** (v7.0.0): Import sorting
- **flake8** (v7.3.0): Linting
- **mypy** (v1.19.0): Static type checking
- **bandit** (v1.9.2): Security scanning
- **safety** (v3.7.0): Dependency vulnerability scanning

---

## Troubleshooting

### Common Issues

#### 1. Import Errors

**Problem**: `ModuleNotFoundError` when running tests

**Solution**:
```bash
# Set PYTHONPATH to project root
export PYTHONPATH=$(pwd)

# Or in pytest.ini
[pytest]
pythonpath = .
```

#### 2. Fixture Not Found

**Problem**: `fixture 'mock_service' not found`

**Solution**: Ensure fixtures are defined in `conftest.py` or imported properly
```python
# conftest.py
import pytest

@pytest.fixture
def mock_service():
    return Mock()
```

#### 3. Flaky Tests

**Problem**: Tests pass sometimes but fail randomly

**Solution**:
- Remove timing dependencies
- Mock external services
- Use deterministic data
- Isolate test state

#### 4. Coverage Not Generated

**Problem**: Coverage report is empty or missing

**Solution**:
```bash
# Ensure pytest-cov is installed
pip install pytest-cov

# Run with explicit coverage
pytest --cov=services --cov-report=html
```

#### 5. Docker Test Failures

**Problem**: Tests fail in Docker but pass locally

**Solution**:
- Check environment variables in `docker-compose.test.yml`
- Verify volume mounts
- Check service dependencies and health checks
- Review Docker logs: `docker-compose logs`

### Debug Tips

```bash
# Run single test with verbose output
pytest tests/unit/test_chat_service.py::test_specific_function -v -s

# Show print statements during test
pytest -s

# Drop into debugger on failure
pytest --pdb

# Run tests matching pattern
pytest -k "test_ingestion"

# Show test execution time
pytest --durations=10
```

---

## Additional Resources

### Documentation

- [pytest Documentation](https://docs.pytest.org/)
- [unittest.mock Guide](https://docs.python.org/3/library/unittest.mock.html)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [Codecov Documentation](https://docs.codecov.com/)

### Project-Specific Docs

- [Architecture Documentation](./docs/detailed_architecture.md)
- [Service Documentation](./docs/services/)
- [Event Flow Diagram](./docs/events/Event%20Flow%20Diagram.drawio)
- [CI/CD Pipeline](../.github/workflows/ci.yml)

### Contributing

When adding new features:
1. Write unit tests first (TDD approach)
2. Ensure ≥80% coverage for new code
3. Add integration tests for new workflows
4. Update this documentation if needed
5. Run full test suite before submitting PR

---

## Summary

This testing guide provides comprehensive information about:
- ✅ Test structure and organization (3 unit files, 6 integration files)
- ✅ Running unit and integration tests
- ✅ Code coverage measurement
- ✅ CI/CD integration
- ✅ Writing effective tests with fakes/mocks
- ✅ Troubleshooting common issues

**Key Test Files:**
- **Unit**: `test_chat.py`, `test_chat_service.py`, `test_retrieval.py`
- **Integration**: `test_ingestion_flow.py`, `test_ingestion_app.py`, `test_search_api.py`, `test_vector_components.py`, `test_indexing_flow.py`, `test_end_to_end_flow.py`, `test_e2e_pipeline.py`

For questions or issues, please refer to the [project documentation](./docs/) or open a GitHub issue.
