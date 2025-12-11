"""
Shared fixtures for end-to-end tests.

Provides Docker Compose service management, API clients,
and test data setup/teardown.
"""

import subprocess
import time
from pathlib import Path

import pytest
import requests

# ============================================================================
# DOCKER COMPOSE FIXTURES
# ============================================================================


@pytest.fixture(scope="session")
def docker_compose_file():
    """Path to docker-compose.e2e.yml file."""
    return Path(__file__).parent.parent.parent / "docker-compose.e2e.yml"


@pytest.fixture(scope="session")
def docker_services(docker_compose_file):
    """
    Start Docker Compose services for E2E tests.
    Runs once per test session.
    """
    # Check if docker-compose is available
    try:
        subprocess.run(["docker-compose", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("docker-compose not available")

    # Start services
    print("\n🚀 Starting Docker Compose services for E2E tests...")
    subprocess.run(
        ["docker-compose", "-f", str(docker_compose_file), "up", "-d", "--build"],
        check=True,
    )

    # Wait for services to be healthy
    max_wait = 120  # 2 minutes
    start_time = time.time()

    services = {
        "auth": "http://localhost:8001/health",
        "ingestion": "http://localhost:8002/health",
        "extraction": "http://localhost:8003/health",
        "indexing": "http://localhost:8004/health",
        "retrieval": "http://localhost:8005/health",
        "chat": "http://localhost:8006/health",
    }

    print("⏳ Waiting for services to be healthy...")
    for service_name, health_url in services.items():
        while time.time() - start_time < max_wait:
            try:
                response = requests.get(health_url, timeout=2)
                if response.status_code == 200:
                    print(f"✅ {service_name} is healthy")
                    break
            except requests.exceptions.RequestException:
                pass
            time.sleep(2)
        else:
            print(f"❌ {service_name} failed to become healthy")
            # Don't fail immediately, continue checking other services

    yield services

    # Teardown: Stop services
    print("\n🛑 Stopping Docker Compose services...")
    subprocess.run(
        ["docker-compose", "-f", str(docker_compose_file), "down", "-v"],
        check=False,
    )


# ============================================================================
# API CLIENT FIXTURES
# ============================================================================


@pytest.fixture
def auth_client(docker_services):
    """HTTP client for auth service."""
    return APIClient("http://localhost:8001")


@pytest.fixture
def ingestion_client(docker_services):
    """HTTP client for ingestion service."""
    return APIClient("http://localhost:8002")


@pytest.fixture
def extraction_client(docker_services):
    """HTTP client for extraction service."""
    return APIClient("http://localhost:8003")


@pytest.fixture
def indexing_client(docker_services):
    """HTTP client for indexing service."""
    return APIClient("http://localhost:8004")


@pytest.fixture
def retrieval_client(docker_services):
    """HTTP client for retrieval service."""
    return APIClient("http://localhost:8005")


@pytest.fixture
def chat_client(docker_services):
    """HTTP client for chat service."""
    return APIClient("http://localhost:8006")


class APIClient:
    """Simple HTTP client wrapper for service APIs."""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = requests.Session()

    def get(self, path: str, **kwargs):
        """GET request."""
        return self.session.get(f"{self.base_url}{path}", **kwargs)

    def post(self, path: str, **kwargs):
        """POST request."""
        return self.session.post(f"{self.base_url}{path}", **kwargs)

    def put(self, path: str, **kwargs):
        """PUT request."""
        return self.session.put(f"{self.base_url}{path}", **kwargs)

    def delete(self, path: str, **kwargs):
        """DELETE request."""
        return self.session.delete(f"{self.base_url}{path}", **kwargs)

    def health(self):
        """Check service health."""
        return self.get("/health")


# ============================================================================
# TEST DATA FIXTURES
# ============================================================================


@pytest.fixture
def test_user():
    """Test user credentials."""
    return {
        "username": f"testuser_{int(time.time())}",
        "password": "testpass123",
    }


@pytest.fixture
def authenticated_user(auth_client, test_user):
    """Register and login a test user, return user_id."""
    # Register
    response = auth_client.post("/register", json=test_user)
    assert response.status_code == 201
    user_id = response.json()["user_id"]

    # Login
    response = auth_client.post("/login", json=test_user)
    assert response.status_code == 200

    yield {"user_id": user_id, **test_user}

    # Cleanup: Delete user history (if endpoint exists)
    try:
        auth_client.delete("/history", headers={"user-id": str(user_id)})
    except Exception:
        pass


@pytest.fixture
def sample_pdf():
    """Path to a sample PDF for testing."""
    pdf_path = Path(__file__).parent.parent / "pdfs" / "sample_marp.pdf"
    if not pdf_path.exists():
        pytest.skip("Sample PDF not available for E2E testing")
    return pdf_path


# ============================================================================
# CLEANUP FIXTURES
# ============================================================================


@pytest.fixture(autouse=True)
def wait_between_tests():
    """Add a small delay between tests to avoid race conditions."""
    yield
    time.sleep(0.5)
