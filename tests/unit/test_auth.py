"""
Unit tests for the authentication service.

Tests user authentication, registration, password hashing,
database operations, and API endpoints using mocks and stubs.

Target: services/auth/app/app.py
"""

import sys
from unittest.mock import MagicMock, Mock, patch

import bcrypt
import pytest
from fastapi.testclient import TestClient

# Mock psycopg2 before any imports that use it
mock_psycopg2 = MagicMock()
mock_psycopg2.errors.UniqueViolation = type("UniqueViolation", (Exception,), {})
sys.modules["psycopg2"] = mock_psycopg2
sys.modules["psycopg2.errors"] = mock_psycopg2.errors


# ============================================================================
# TEST FIXTURES
# ============================================================================


@pytest.fixture
def mock_db_manager():
    """Create a mock database manager for testing."""
    mock_manager = Mock()
    mock_manager.cursor = Mock()
    mock_manager.conn = Mock()
    return mock_manager


@pytest.fixture
def auth_app(mock_db_manager):
    """Create FastAPI test client with mocked database."""
    # Import after patching to avoid real database connection
    import services.auth.app.app as auth_module
    from services.auth.app.app import app

    # Set the db_manager globally
    auth_module.db_manager = mock_db_manager

    client = TestClient(app)
    yield client


@pytest.fixture
def sample_user():
    """Sample user data for testing."""
    return {"username": "testuser", "password": "testpass123"}


@pytest.fixture
def sample_user_data():
    """Sample user data from database."""
    hashed = bcrypt.hashpw("testpass123".encode("utf-8"), bcrypt.gensalt())
    return (1, "testuser", hashed.decode("utf-8"))


# ============================================================================
# DATABASE MANAGER TESTS
# ============================================================================


class TestDatabaseManager:
    """Test DatabaseManager class methods."""

    def test_database_manager_initialization(self):
        """Test DatabaseManager initializes with database connection."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("psycopg2.connect", return_value=mock_conn):
            from services.auth.app.app import DatabaseManager

            db_manager = DatabaseManager()

            assert db_manager.conn == mock_conn
            assert db_manager.cursor == mock_cursor
            mock_cursor.execute.assert_called()  # create_tables called

    def test_database_manager_connection_error(self):
        """Test DatabaseManager handles connection errors gracefully."""
        with patch("psycopg2.connect", side_effect=Exception("Connection failed")):
            from services.auth.app.app import DatabaseManager

            db_manager = DatabaseManager()

            assert db_manager.cursor is None

    def test_get_user_success(self, mock_db_manager, sample_user_data):
        """Test getting user from database."""
        from services.auth.app.app import DatabaseManager

        mock_db_manager.cursor.fetchone.return_value = sample_user_data

        # Create instance and manually set attributes
        db = DatabaseManager.__new__(DatabaseManager)
        db.cursor = mock_db_manager.cursor
        db.conn = mock_db_manager.conn

        result = db.get_user("testuser")

        assert result == sample_user_data
        mock_db_manager.cursor.execute.assert_called_once()

    def test_get_user_not_found(self, mock_db_manager):
        """Test getting non-existent user returns None."""
        from services.auth.app.app import DatabaseManager

        mock_db_manager.cursor.fetchone.return_value = None

        db = DatabaseManager.__new__(DatabaseManager)
        db.cursor = mock_db_manager.cursor
        db.conn = mock_db_manager.conn

        result = db.get_user("nonexistent")

        assert result is None

    def test_get_user_by_id_success(self, mock_db_manager):
        """Test getting user by ID."""
        from services.auth.app.app import DatabaseManager

        mock_db_manager.cursor.fetchone.return_value = (1, "testuser")

        db = DatabaseManager.__new__(DatabaseManager)
        db.cursor = mock_db_manager.cursor
        db.conn = mock_db_manager.conn

        result = db.get_user_by_id(1)

        assert result == (1, "testuser")

    def test_insert_user_success(self, mock_db_manager):
        """Test inserting new user."""
        from services.auth.app.app import DatabaseManager

        mock_db_manager.cursor.fetchone.return_value = (1,)

        db = DatabaseManager.__new__(DatabaseManager)
        db.cursor = mock_db_manager.cursor
        db.conn = mock_db_manager.conn

        hashed_password = bcrypt.hashpw("password".encode("utf-8"), bcrypt.gensalt())
        result = db.insert_user("newuser", hashed_password)

        assert result == 1
        mock_db_manager.cursor.execute.assert_called_once()

    def test_save_message_success(self, mock_db_manager):
        """Test saving chat message."""
        from services.auth.app.app import DatabaseManager

        db = DatabaseManager.__new__(DatabaseManager)
        db.cursor = mock_db_manager.cursor
        db.conn = mock_db_manager.conn

        result = db.save_message(1, "user", "Hello")

        assert result is True
        mock_db_manager.cursor.execute.assert_called_once()

    def test_get_history_success(self, mock_db_manager):
        """Test retrieving chat history."""
        from services.auth.app.app import DatabaseManager

        # History is returned in DESC order from DB, then reversed
        mock_history = [
            ("assistant", "Hi there", "2025-01-01 10:00:05"),
            ("user", "Hello", "2025-01-01 10:00:00"),
        ]
        mock_db_manager.cursor.fetchall.return_value = mock_history

        db = DatabaseManager.__new__(DatabaseManager)
        db.cursor = mock_db_manager.cursor
        db.conn = mock_db_manager.conn

        result = db.get_history(1, limit=10)

        assert len(result) == 2
        # After reversal, oldest message (user) is first
        assert result[0][0] == "user"

    def test_clear_history_success(self, mock_db_manager):
        """Test clearing chat history."""
        from services.auth.app.app import DatabaseManager

        db = DatabaseManager.__new__(DatabaseManager)
        db.cursor = mock_db_manager.cursor
        db.conn = mock_db_manager.conn

        result = db.clear_history(1)

        assert result is True
        mock_db_manager.cursor.execute.assert_called_once()


# ============================================================================
# PASSWORD HASHING TESTS
# ============================================================================


class TestPasswordHashing:
    """Test password hashing and verification."""

    def test_password_hashing(self):
        """Test password is properly hashed with bcrypt."""
        password = "testpass123"
        salt = bcrypt.gensalt(12)
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)

        assert hashed != password.encode("utf-8")
        assert bcrypt.checkpw(password.encode("utf-8"), hashed)

    def test_password_verification_success(self):
        """Test correct password verification."""
        password = "testpass123"
        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

        result = bcrypt.checkpw(password.encode("utf-8"), hashed)

        assert result is True

    def test_password_verification_failure(self):
        """Test incorrect password verification."""
        password = "testpass123"
        wrong_password = "wrongpass"
        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

        result = bcrypt.checkpw(wrong_password.encode("utf-8"), hashed)

        assert result is False


# ============================================================================
# API ENDPOINT TESTS
# ============================================================================


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_check_success(self, auth_app, mock_db_manager):
        """Test health check returns ok when database connected."""
        response = auth_app.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["service"] == "auth-service"
        assert response.json()["database"] == "connected"

    def test_health_check_database_unavailable(self, auth_app, mock_db_manager):
        """Test health check fails when database unavailable."""
        mock_db_manager.cursor = None

        response = auth_app.get("/health")

        assert response.status_code == 503
        assert "Database not available" in response.json()["detail"]


class TestRegisterEndpoint:
    """Test user registration endpoint."""

    def test_register_success(self, auth_app, mock_db_manager):
        """Test successful user registration."""
        mock_db_manager.insert_user.return_value = 1

        response = auth_app.post(
            "/register", json={"username": "newuser", "password": "password123"}
        )

        assert response.status_code == 201
        assert response.json()["message"] == "User registered successfully"
        assert response.json()["user_id"] == 1
        assert response.json()["username"] == "newuser"

    def test_register_username_too_short(self, auth_app):
        """Test registration fails with short username."""
        response = auth_app.post(
            "/register", json={"username": "ab", "password": "password123"}
        )

        assert response.status_code == 400
        assert "at least 3 characters" in response.json()["detail"]

    def test_register_password_too_short(self, auth_app):
        """Test registration fails with short password."""
        response = auth_app.post(
            "/register", json={"username": "testuser", "password": "12345"}
        )

        assert response.status_code == 400
        assert "at least 6 characters" in response.json()["detail"]

    def test_register_duplicate_username(self, auth_app, mock_db_manager):
        """Test registration fails with duplicate username."""
        mock_db_manager.insert_user.return_value = None

        response = auth_app.post(
            "/register", json={"username": "existinguser", "password": "password123"}
        )

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_register_database_unavailable(self, auth_app, mock_db_manager):
        """Test registration fails when database unavailable."""
        mock_db_manager.cursor = None

        response = auth_app.post(
            "/register", json={"username": "newuser", "password": "password123"}
        )

        assert response.status_code == 503


class TestLoginEndpoint:
    """Test user login endpoint."""

    def test_login_success(self, auth_app, mock_db_manager, sample_user_data):
        """Test successful user login."""
        mock_db_manager.get_user.return_value = sample_user_data

        response = auth_app.post(
            "/login", json={"username": "testuser", "password": "testpass123"}
        )

        assert response.status_code == 200
        assert response.json()["message"] == "Login successful"
        assert response.json()["user_id"] == 1
        assert response.json()["username"] == "testuser"

    def test_login_user_not_found(self, auth_app, mock_db_manager):
        """Test login fails with non-existent user."""
        mock_db_manager.get_user.return_value = None

        response = auth_app.post(
            "/login", json={"username": "nonexistent", "password": "password123"}
        )

        assert response.status_code == 401
        assert "Invalid username or password" in response.json()["detail"]

    def test_login_wrong_password(self, auth_app, mock_db_manager, sample_user_data):
        """Test login fails with wrong password."""
        mock_db_manager.get_user.return_value = sample_user_data

        response = auth_app.post(
            "/login", json={"username": "testuser", "password": "wrongpassword"}
        )

        assert response.status_code == 401
        assert "Invalid username or password" in response.json()["detail"]

    def test_login_database_unavailable(self, auth_app, mock_db_manager):
        """Test login fails when database unavailable."""
        mock_db_manager.cursor = None

        response = auth_app.post(
            "/login", json={"username": "testuser", "password": "password123"}
        )

        assert response.status_code == 503


class TestVerifyUserEndpoint:
    """Test user verification endpoint."""

    def test_verify_user_exists(self, auth_app, mock_db_manager):
        """Test verifying existing user."""
        mock_db_manager.get_user_by_id.return_value = (1, "testuser")

        response = auth_app.get("/verify/1")

        assert response.status_code == 200
        assert response.json()["exists"] is True
        assert response.json()["user_id"] == 1
        assert response.json()["username"] == "testuser"

    def test_verify_user_not_exists(self, auth_app, mock_db_manager):
        """Test verifying non-existent user."""
        mock_db_manager.get_user_by_id.return_value = None

        response = auth_app.get("/verify/999")

        assert response.status_code == 200
        assert response.json()["exists"] is False

    def test_verify_database_unavailable(self, auth_app, mock_db_manager):
        """Test verify fails when database unavailable."""
        mock_db_manager.cursor = None

        response = auth_app.get("/verify/1")

        assert response.status_code == 503


class TestHistoryEndpoint:
    """Test chat history retrieval endpoint."""

    def test_get_history_success(self, auth_app, mock_db_manager):
        """Test retrieving chat history."""
        mock_db_manager.get_user_by_id.return_value = (1, "testuser")
        mock_db_manager.get_history.return_value = [
            ("user", "Hello", "2025-01-01 10:00:00"),
            ("assistant", "Hi", "2025-01-01 10:00:05"),
        ]

        response = auth_app.get("/history?limit=10", headers={"user-id": "1"})

        assert response.status_code == 200
        assert response.json()["user_id"] == 1
        assert len(response.json()["history"]) == 2
        assert response.json()["history"][0]["role"] == "user"

    def test_get_history_missing_header(self, auth_app):
        """Test get history fails without user-id header."""
        response = auth_app.get("/history")

        assert response.status_code == 401
        assert "Missing 'User-Id' header" in response.json()["detail"]

    def test_get_history_invalid_user_id(self, auth_app):
        """Test get history fails with invalid user-id."""
        response = auth_app.get("/history", headers={"user-id": "invalid"})

        assert response.status_code == 401
        assert "Invalid 'User-Id' header" in response.json()["detail"]

    def test_get_history_user_not_found(self, auth_app, mock_db_manager):
        """Test get history fails with non-existent user."""
        mock_db_manager.get_user_by_id.return_value = None

        response = auth_app.get("/history", headers={"user-id": "999"})

        assert response.status_code == 401
        assert "User not found" in response.json()["detail"]


class TestClearHistoryEndpoint:
    """Test chat history clearing endpoint."""

    def test_clear_history_success(self, auth_app, mock_db_manager):
        """Test clearing chat history."""
        mock_db_manager.get_user_by_id.return_value = (1, "testuser")
        mock_db_manager.clear_history.return_value = True

        response = auth_app.delete("/history", headers={"user-id": "1"})

        assert response.status_code == 200
        assert "cleared successfully" in response.json()["message"]

    def test_clear_history_missing_header(self, auth_app):
        """Test clear history fails without user-id header."""
        response = auth_app.delete("/history")

        assert response.status_code == 401

    def test_clear_history_invalid_user_id(self, auth_app):
        """Test clear history fails with invalid user-id."""
        response = auth_app.delete("/history", headers={"user-id": "invalid"})

        assert response.status_code == 401

    def test_clear_history_user_not_found(self, auth_app, mock_db_manager):
        """Test clear history fails with non-existent user."""
        mock_db_manager.get_user_by_id.return_value = None

        response = auth_app.delete("/history", headers={"user-id": "999"})

        assert response.status_code == 401

    def test_clear_history_failure(self, auth_app, mock_db_manager):
        """Test clear history handles database errors."""
        mock_db_manager.get_user_by_id.return_value = (1, "testuser")
        mock_db_manager.clear_history.return_value = False

        response = auth_app.delete("/history", headers={"user-id": "1"})

        assert response.status_code == 500


class TestSaveChatEndpoint:
    """Test save chat message endpoint."""

    def test_save_chat_success(self, auth_app, mock_db_manager):
        """Test saving chat message."""
        mock_db_manager.save_message.return_value = True

        response = auth_app.post(
            "/save-chat", json={"query": "Hello"}, headers={"user-id": "1"}
        )

        assert response.status_code == 200
        assert response.json()["saved"] is True

    def test_save_chat_missing_user_id(self, auth_app, mock_db_manager):
        """Test save chat without user-id header."""
        response = auth_app.post("/save-chat", json={"query": "Hello"})

        assert response.status_code == 200
        assert response.json()["saved"] is False
        assert "Missing user ID" in response.json()["error"]

    def test_save_chat_invalid_user_id(self, auth_app, mock_db_manager):
        """Test save chat with invalid user-id."""
        response = auth_app.post(
            "/save-chat", json={"query": "Hello"}, headers={"user-id": "invalid"}
        )

        assert response.status_code == 200
        assert response.json()["saved"] is False

    def test_save_chat_database_failure(self, auth_app, mock_db_manager):
        """Test save chat handles database errors."""
        mock_db_manager.save_message.return_value = False

        response = auth_app.post(
            "/save-chat", json={"query": "Hello"}, headers={"user-id": "1"}
        )

        assert response.status_code == 200
        assert response.json()["saved"] is False
