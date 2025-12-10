# Testing Guide

## Overview

This document provides comprehensive information about the testing infrastructure for the MARP Guide RAG Chatbot project. The project uses a multi-layered testing approach with both unit and integration tests to ensure code quality, reliability, and maintainability.

### Test Statistics

- **Total Tests**: 287 tests (190 unit + 97 integration)
- **Status**: ✅ All passing, 0 skipped
- **Test Files**: 8 unit test files, 7 integration test files
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

1. **Unit Tests (Foundation)** - Fast, isolated tests for individual components
2. **Integration Tests (Middle)** - Tests for service interactions and workflows
3. **System Tests (Top)** - Docker-based validation of complete system

### Testing Principles

- **Isolation**: Unit tests should not depend on external services
- **Speed**: Fast feedback loop for developers
- **Reliability**: Deterministic tests that pass consistently
- **Coverage**: Comprehensive coverage of critical paths
- **Maintainability**: Clear, readable test code

---

## Test Structure

```
tests/
├── __init__.py
├── conftest.py                     # Shared fixtures and configuration
├── unit/                           # Unit tests (fast, isolated)
│   ├── __init__.py
│   ├── test_chat_service.py       # Chat service events & models
│   ├── test_chunking.py           # Semantic chunking logic
│   ├── test_citation_extraction.py # Citation extraction
│   ├── test_discoverer.py         # Document discovery
│   ├── test_events.py             # Event schemas
│   ├── test_retrieval.py          # Consolidated retrieval tests (all retrieval logic)
│   ├── test_retriever.py          # Vector search retriever
│   └── test_storage.py            # Document storage
│
├── integration/                    # Integration tests (slower, multi-component)
│   ├── __init__.py
│   ├── test_e2e_pipeline.py       # Complete pipeline workflows
│   ├── test_end_to_end_flow.py    # Event handling & schema validation
│   ├── test_indexing_flow.py      # Document indexing pipeline
│   ├── test_ingestion_app.py      # Ingestion API integration
│   ├── test_ingestion_flow.py     # End-to-end ingestion
│   ├── test_search_api.py         # Search API integration
│   └── test_vector_components.py  # Vector DB operations
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

### Run Tests in Docker

```bash
# Run tests in isolated container
docker-compose -f docker-compose.test.yml up --abort-on-container-exit

# Clean up after tests
docker-compose -f docker-compose.test.yml down -v
```

---

## Unit Tests

Unit tests focus on testing individual functions, classes, and modules in isolation.

### Test Summary

- **Total Unit Tests**: 190 tests across 8 test files
- **Status**: ✅ All passing, 0 skipped
- **Coverage Target**: ≥80% line coverage

### Coverage by Service

| Service | Test File | Focus Areas | Tests |
|---------|-----------|-------------|-------|
| **Chat** | `test_chat_service.py` | Event handling, LLM integration, response generation | 30+ |
| **Retrieval** | `test_retrieval.py` (consolidated)<br>`test_retriever.py` | Vector search<br>Query processing<br>Result ranking<br>RabbitMQ integration<br>API endpoints | 45+ |
| **Indexing** | `test_chunking.py`<br>`test_events.py` | Semantic chunking<br>Token limits<br>Embedding generation<br>Event schemas | 35+ |
| **Ingestion** | `test_discoverer.py`<br>`test_storage.py` | Document discovery<br>PDF extraction<br>File system storage<br>URL parsing | 40+ |
| **Extraction** | `test_citation_extraction.py` | Citation parsing<br>Metadata extraction<br>Pattern matching | 40+ |

**Note**: `test_retrieval.py` consolidates previously separate files (`test_retrieval_app.py`, `test_retrieval_rabbitmq.py`, `test_retrieval_service.py`, and original `test_retrieval.py`) for better maintainability.

### Key Testing Patterns

#### Mocking External Services

```python
from unittest.mock import Mock, patch

def test_vector_search(mock_qdrant):
    """Test vector search with mocked Qdrant"""
    mock_qdrant.search.return_value = [
        {"id": "chunk-1", "score": 0.95}
    ]

    result = search_vectors(query="test")
    assert len(result) == 1
    assert result[0]["score"] == 0.95
```

#### Testing Events

```python
def test_document_extracted_event():
    """Test DocumentExtracted event creation"""
    event = DocumentExtracted(
        eventType="DocumentExtracted",
        eventId="evt-001",
        timestamp="2025-01-01T00:00:00Z",
        correlationId="corr-001",
        source="extraction-service",
        version="1.0",
        payload={
            "documentId": "doc-001",
            "textContent": "Sample text"
        }
    )

    assert event.eventType == "DocumentExtracted"
    assert event.payload["documentId"] == "doc-001"
```

#### Testing API Endpoints

```python
from fastapi.testclient import TestClient

def test_health_endpoint():
    """Test health check endpoint"""
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
```

---

## Integration Tests

Integration tests validate interactions between multiple components and services.

### Test Summary

- **Total Integration Tests**: 97 tests across 7 test files
- **Status**: ✅ All passing, 0 skipped
- **Coverage Target**: ≥70% line coverage

### Test Scenarios

#### 1. Document Ingestion Flow

**File:** `test_ingestion_flow.py`

Tests the complete document ingestion pipeline:
- Document discovery from URL
- PDF download and extraction
- Storage in file system
- Event publishing to RabbitMQ

```python
def test_ingestion_pipeline():
    """Test complete ingestion workflow"""
    # 1. Discover documents
    docs = discover_documents(source_url)

    # 2. Extract content
    extracted = extract_pdf(docs[0])

    # 3. Store document
    doc_id = store_document(extracted)

    # 4. Verify event published
    assert event_published("document.ingested", doc_id)
```

#### 2. Indexing Flow

**File:** `test_indexing_flow.py`

Tests document chunking and vector embedding:
- Semantic chunking with token limits
- Embedding generation
- Vector storage in Qdrant
- Event publishing

#### 3. Search API Integration

**File:** `test_search_api.py`

Tests the retrieval service API:
- Query endpoint
- Vector similarity search
- Result ranking and filtering
- Response formatting

#### 4. Event-Driven Workflows

**File:** `test_end_to_end_flow.py`

Tests RabbitMQ event handling and complete workflows:
- Event consumption and schema validation
- Message processing across services
- Error handling and retries
- Event correlation
- End-to-end pipeline integration

### Integration Test Best Practices

1. **Use Fakes/Stubs**: Create lightweight fakes for external services
2. **Test Boundaries**: Focus on service interactions, not internal logic
3. **Clean State**: Reset state between tests
4. **Realistic Data**: Use production-like test data
5. **End-to-End Flows**: Test complete user scenarios

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
from fastapi.testclient import TestClient


@pytest.fixture
def test_client():
    """Create test client for API testing"""
    from app import app
    return TestClient(app)


def test_[endpoint_name]_integration(test_client):
    """Test [endpoint_name] end-to-end flow"""
    # Arrange
    request_data = {"query": "test"}

    # Act
    response = test_client.post("/endpoint", json=request_data)

    # Assert
    assert response.status_code == 200
    assert "expected_field" in response.json()
```

### Testing Best Practices

1. **Use Descriptive Names**: Test names should describe what is being tested
2. **Follow AAA Pattern**: Arrange, Act, Assert
3. **One Assertion Per Test**: Focus on single behavior
4. **Use Fixtures**: Share setup code between tests
5. **Mock External Dependencies**: Keep tests fast and reliable
6. **Test Edge Cases**: Invalid input, boundary conditions, errors
7. **Avoid Test Interdependence**: Each test should be independent

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
- ✅ Test structure and organization
- ✅ Running unit and integration tests
- ✅ Code coverage measurement
- ✅ CI/CD integration
- ✅ Writing effective tests
- ✅ Troubleshooting common issues

For questions or issues, please refer to the [project documentation](./docs/) or open a GitHub issue.
