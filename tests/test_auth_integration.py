"""Integration tests for authentication API endpoints."""

import pytest
from fastapi.testclient import TestClient
from core.database import SessionLocal, Base, engine, User, RefreshToken
from api.app import app


@pytest.fixture(scope="function")
def setup_db():
    """Setup and teardown database for each test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(setup_db):
    """Provide FastAPI test client."""
    return TestClient(app)


class TestRegisterEndpoint:
    """Tests for POST /auth/register"""

    def test_register_success(self, client):
        """Test successful user registration."""
        response = client.post("/auth/register", json={
            "email": "newuser@example.com",
            "full_name": "New User",
            "password": "secure_password_123",
            "role": "student"
        })

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_register_duplicate_email(self, client):
        """Test that duplicate email fails."""
        # Register first user
        client.post("/auth/register", json={
            "email": "user@example.com",
            "full_name": "User One",
            "password": "password123",
            "role": "student"
        })

        # Try to register with same email
        response = client.post("/auth/register", json={
            "email": "user@example.com",
            "full_name": "User Two",
            "password": "different_password",
            "role": "student"
        })

        assert response.status_code == 409
        assert "already registered" in response.json()["detail"].lower()

    def test_register_case_insensitive_email(self, client):
        """Test that emails are case-insensitive for duplicate check."""
        # Register with lowercase
        client.post("/auth/register", json={
            "email": "user@example.com",
            "full_name": "User",
            "password": "password123",
            "role": "student"
        })

        # Try to register with different case
        response = client.post("/auth/register", json={
            "email": "USER@EXAMPLE.COM",
            "full_name": "User Two",
            "password": "password123",
            "role": "student"
        })

        assert response.status_code == 409

    def test_register_invalid_email(self, client):
        """Test that invalid email format fails."""
        response = client.post("/auth/register", json={
            "email": "invalid-email",
            "full_name": "User",
            "password": "password123",
            "role": "student"
        })

        assert response.status_code == 422  # Validation error

    def test_register_short_password(self, client):
        """Test that short password fails validation."""
        response = client.post("/auth/register", json={
            "email": "user@example.com",
            "full_name": "User",
            "password": "short",  # less than 8 chars
            "role": "student"
        })

        assert response.status_code == 422

    def test_register_missing_fields(self, client):
        """Test that missing required fields fails."""
        response = client.post("/auth/register", json={
            "email": "user@example.com",
            "full_name": "User"
            # missing password and role
        })

        assert response.status_code == 422


class TestLoginEndpoint:
    """Tests for POST /auth/login"""

    def test_login_success(self, client):
        """Test successful login."""
        # Register user first
        client.post("/auth/register", json={
            "email": "user@example.com",
            "full_name": "Test User",
            "password": "password123",
            "role": "student"
        })

        # Login
        response = client.post("/auth/login", json={
            "email": "user@example.com",
            "password": "password123",
            "role": "student"
        })

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_login_invalid_email(self, client):
        """Test login with non-existent email."""
        response = client.post("/auth/login", json={
            "email": "nonexistent@example.com",
            "password": "password123",
            "role": "student"
        })

        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    def test_login_wrong_password(self, client):
        """Test login with wrong password."""
        # Register user
        client.post("/auth/register", json={
            "email": "user@example.com",
            "full_name": "Test User",
            "password": "password123",
            "role": "student"
        })

        # Try to login with wrong password
        response = client.post("/auth/login", json={
            "email": "user@example.com",
            "password": "wrong_password",
            "role": "student"
        })

        assert response.status_code == 401

    def test_login_case_insensitive_email(self, client):
        """Test that login email is case-insensitive."""
        # Register with lowercase
        client.post("/auth/register", json={
            "email": "user@example.com",
            "full_name": "Test User",
            "password": "password123",
            "role": "student"
        })

        # Login with uppercase
        response = client.post("/auth/login", json={
            "email": "USER@EXAMPLE.COM",
            "password": "password123",
            "role": "student"
        })

        assert response.status_code == 200


class TestRefreshEndpoint:
    """Tests for POST /auth/refresh"""

    def test_refresh_success(self, client):
        """Test successful token refresh."""
        # Register and login
        register_response = client.post("/auth/register", json={
            "email": "user@example.com",
            "full_name": "Test User",
            "password": "password123",
            "role": "student"
        })
        refresh_token = register_response.json()["refresh_token"]

        # Refresh token
        response = client.post("/auth/refresh", json={
            "refresh_token": refresh_token
        })

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_refresh_invalid_token(self, client):
        """Test refresh with invalid token."""
        response = client.post("/auth/refresh", json={
            "refresh_token": "invalid_token_12345"
        })

        assert response.status_code == 401

    def test_refresh_creates_new_token(self, client):
        """Test that refresh invalidates old token."""
        # Register
        register_response = client.post("/auth/register", json={
            "email": "user@example.com",
            "full_name": "Test User",
            "password": "password123",
            "role": "student"
        })
        old_refresh_token = register_response.json()["refresh_token"]

        # First refresh
        response1 = client.post("/auth/refresh", json={
            "refresh_token": old_refresh_token
        })
        assert response1.status_code == 200

        # Try to use old token again (should fail)
        response2 = client.post("/auth/refresh", json={
            "refresh_token": old_refresh_token
        })
        assert response2.status_code == 401


class TestLogoutEndpoint:
    """Tests for POST /auth/logout"""

    def test_logout_success(self, client):
        """Test successful logout."""
        # Register and get token
        register_response = client.post("/auth/register", json={
            "email": "user@example.com",
            "full_name": "Test User",
            "password": "password123",
            "role": "student"
        })
        access_token = register_response.json()["access_token"]

        # Logout
        response = client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"}
        )

        assert response.status_code == 200
        assert "successfully" in response.json()["message"].lower()

    def test_logout_without_auth(self, client):
        """Test logout without authentication."""
        response = client.post("/auth/logout")

        assert response.status_code == 403  # Forbidden (no credentials)


class TestCurrentUserEndpoint:
    """Tests for GET /auth/me"""

    def test_get_current_user_success(self, client):
        """Test getting current user info."""
        # Register
        register_response = client.post("/auth/register", json={
            "email": "user@example.com",
            "full_name": "Test User",
            "password": "password123",
            "role": "student"
        })
        access_token = register_response.json()["access_token"]

        # Get user info
        response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "user@example.com"
        assert data["full_name"] == "Test User"
        assert data["role"] == "student"

    def test_get_current_user_without_auth(self, client):
        """Test that getting user info without auth fails."""
        response = client.get("/auth/me")

        assert response.status_code == 403  # Forbidden


class TestProtectedEndpoints:
    """Tests for endpoint protection with authentication."""

    def test_analyze_without_auth(self, client):
        """Test that analyze endpoint requires authentication."""
        response = client.post("/v1/analyze", json={
            "text": "This is a test sentence."
        })

        assert response.status_code == 403  # Forbidden

    def test_analyze_with_auth(self, client):
        """Test that analyze endpoint works with valid token."""
        # Register and get token
        register_response = client.post("/auth/register", json={
            "email": "user@example.com",
            "full_name": "Test User",
            "password": "password123",
            "role": "student"
        })
        access_token = register_response.json()["access_token"]

        # Call analyze with auth
        response = client.post(
            "/v1/analyze",
            json={"text": "This is a test sentence."},
            headers={"Authorization": f"Bearer {access_token}"}
        )

        assert response.status_code == 200

    def test_health_endpoint_public(self, client):
        """Test that health endpoint is public."""
        response = client.get("/health")

        assert response.status_code == 200

    def test_root_endpoint_public(self, client):
        """Test that root endpoint is public."""
        response = client.get("/")

        assert response.status_code == 200
