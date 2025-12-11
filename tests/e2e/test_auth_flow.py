"""
End-to-end tests for authentication flow.

Tests the complete auth service workflow including:
- User registration
- Login
- User verification
- Chat history management
"""


class TestAuthRegistrationFlow:
    """Test user registration end-to-end flow."""

    def test_register_new_user(self, auth_client, test_user):
        """Test complete user registration flow."""
        # Register user
        response = auth_client.post("/register", json=test_user)

        assert response.status_code == 201
        data = response.json()
        assert "user_id" in data
        assert data["username"] == test_user["username"]
        assert "message" in data

    def test_register_duplicate_username(self, auth_client, test_user):
        """Test that duplicate usernames are rejected."""
        # Register first time
        response = auth_client.post("/register", json=test_user)
        assert response.status_code == 201

        # Try to register again with same username
        response = auth_client.post("/register", json=test_user)
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()

    def test_register_validation(self, auth_client):
        """Test registration input validation."""
        # Username too short
        response = auth_client.post(
            "/register", json={"username": "ab", "password": "password123"}
        )
        assert response.status_code == 400

        # Password too short
        response = auth_client.post(
            "/register", json={"username": "validuser", "password": "12345"}
        )
        assert response.status_code == 400


class TestAuthLoginFlow:
    """Test user login end-to-end flow."""

    def test_login_success(self, auth_client, authenticated_user):
        """Test successful login with registered user."""
        response = auth_client.post(
            "/login",
            json={
                "username": authenticated_user["username"],
                "password": authenticated_user["password"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Login successful"
        assert data["user_id"] == authenticated_user["user_id"]
        assert data["username"] == authenticated_user["username"]

    def test_login_wrong_password(self, auth_client, authenticated_user):
        """Test login fails with incorrect password."""
        response = auth_client.post(
            "/login",
            json={
                "username": authenticated_user["username"],
                "password": "wrongpassword",
            },
        )

        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    def test_login_nonexistent_user(self, auth_client):
        """Test login fails with non-existent user."""
        response = auth_client.post(
            "/login",
            json={"username": "nonexistent", "password": "password123"},
        )

        assert response.status_code == 401


class TestAuthVerificationFlow:
    """Test user verification end-to-end flow."""

    def test_verify_existing_user(self, auth_client, authenticated_user):
        """Test verification of existing user."""
        response = auth_client.get(f"/verify/{authenticated_user['user_id']}")

        assert response.status_code == 200
        data = response.json()
        assert data["exists"] is True
        assert data["user_id"] == authenticated_user["user_id"]
        assert data["username"] == authenticated_user["username"]

    def test_verify_nonexistent_user(self, auth_client):
        """Test verification of non-existent user."""
        response = auth_client.get("/verify/99999")

        assert response.status_code == 200
        data = response.json()
        assert data["exists"] is False


class TestChatHistoryFlow:
    """Test chat history management end-to-end flow."""

    def test_save_and_retrieve_history(self, auth_client, authenticated_user):
        """Test saving and retrieving chat history."""
        user_id = authenticated_user["user_id"]

        # Save a chat message
        response = auth_client.post(
            "/save-chat",
            json={"query": "What is MARP?"},
            headers={"user-id": str(user_id)},
        )

        # Note: save-chat returns 200 even on success with {"saved": True/False}
        assert response.status_code == 200

        # Retrieve history
        response = auth_client.get("/history", headers={"user-id": str(user_id)})

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == user_id
        assert "history" in data

    def test_clear_history(self, auth_client, authenticated_user):
        """Test clearing chat history."""
        user_id = authenticated_user["user_id"]

        # Save a message
        auth_client.post(
            "/save-chat",
            json={"query": "Test message"},
            headers={"user-id": str(user_id)},
        )

        # Clear history
        response = auth_client.delete("/history", headers={"user-id": str(user_id)})

        assert response.status_code == 200
        assert "cleared" in response.json()["message"].lower()

        # Verify history is empty
        response = auth_client.get("/history", headers={"user-id": str(user_id)})
        assert response.status_code == 200
        # After clearing, history should be empty or have no entries
        assert len(response.json()["history"]) == 0

    def test_history_requires_authentication(self, auth_client):
        """Test that history endpoints require user-id header."""
        # Try to get history without user-id
        response = auth_client.get("/history")
        assert response.status_code == 401

        # Try to clear history without user-id
        response = auth_client.delete("/history")
        assert response.status_code == 401


class TestAuthHealthCheck:
    """Test auth service health check."""

    def test_health_check(self, auth_client):
        """Test auth service health endpoint."""
        response = auth_client.health()

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "auth-service"
        assert data["database"] == "connected"
