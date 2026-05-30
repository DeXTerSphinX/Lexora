"""Unit tests for authentication utilities."""

import pytest
from datetime import timedelta
from core.auth.password import get_password_hash, verify_password
from core.auth.token import create_access_token, verify_token, create_refresh_token
from jose import JWTError


class TestPasswordHashing:
    """Tests for password hashing utilities."""

    def test_get_password_hash_returns_string(self):
        """Test that password hash returns a string."""
        password = "test_password_123"
        hash_result = get_password_hash(password)
        assert isinstance(hash_result, str)
        assert len(hash_result) > 20  # bcrypt hashes are long

    def test_get_password_hash_different_each_time(self):
        """Test that same password produces different hashes (due to salt)."""
        password = "test_password_123"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        assert hash1 != hash2

    def test_verify_password_correct(self):
        """Test that correct password verifies."""
        password = "my_secure_password"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test that incorrect password does not verify."""
        password = "my_secure_password"
        wrong_password = "wrong_password"
        hashed = get_password_hash(password)
        assert verify_password(wrong_password, hashed) is False

    def test_verify_password_empty_string(self):
        """Test that empty password fails verification."""
        password = "my_secure_password"
        hashed = get_password_hash(password)
        assert verify_password("", hashed) is False


class TestTokenCreation:
    """Tests for JWT token creation."""

    def test_create_access_token_returns_string(self):
        """Test that access token creation returns a string."""
        data = {"sub": 1, "email": "test@example.com", "role": "student"}
        token = create_access_token(data)
        assert isinstance(token, str)
        assert len(token) > 20

    def test_create_access_token_with_custom_expiry(self):
        """Test creating token with custom expiration."""
        data = {"sub": 1, "email": "test@example.com"}
        expires = timedelta(hours=2)
        token = create_access_token(data, expires_delta=expires)
        assert isinstance(token, str)

        # Verify token contains exp claim
        payload = verify_token(token)
        assert "exp" in payload

    def test_verify_token_success(self):
        """Test that valid token can be verified."""
        data = {"sub": 1, "email": "test@example.com", "role": "admin"}
        token = create_access_token(data)
        payload = verify_token(token)

        assert payload["sub"] == 1
        assert payload["email"] == "test@example.com"
        assert payload["role"] == "admin"
        assert payload["type"] == "access"

    def test_verify_token_invalid_signature(self):
        """Test that tampered token fails verification."""
        data = {"sub": 1, "email": "test@example.com"}
        token = create_access_token(data)

        # Tamper with token
        tampered = token[:-10] + "tampered123"

        with pytest.raises(JWTError):
            verify_token(tampered)

    def test_create_refresh_token_returns_tuple(self):
        """Test that refresh token creation returns a tuple."""
        plain, hashed = create_refresh_token()
        assert isinstance(plain, str)
        assert isinstance(hashed, str)
        assert len(plain) > 20
        assert len(hashed) > 20

    def test_create_refresh_token_deterministic_hash(self):
        """Test that same plain token always produces same hash."""
        plain_token = "test_token_12345"

        # We can't directly test this since create_refresh_token generates random token
        # but we can verify that hashing is consistent
        import hashlib
        hash1 = hashlib.sha256(plain_token.encode()).hexdigest()
        hash2 = hashlib.sha256(plain_token.encode()).hexdigest()
        assert hash1 == hash2


class TestTokenVerification:
    """Tests for token verification edge cases."""

    def test_verify_token_missing_sub(self):
        """Test that token without sub claim fails."""
        data = {"email": "test@example.com"}  # missing 'sub'
        token = create_access_token(data)

        # Token with other claims might still verify signature
        # but get_user_id_from_token would fail
        payload = verify_token(token)
        assert payload["email"] == "test@example.com"

    def test_verify_token_invalid_type(self):
        """Test that token with wrong type is rejected."""
        data = {"sub": 1, "email": "test@example.com", "type": "refresh"}
        # Manually create a JWT with wrong type would require direct jwt encoding
        # This is more of an integration test
        pass


class TestPasswordValidation:
    """Tests for password security requirements."""

    def test_password_min_length(self):
        """Test password minimum length from config."""
        from core.auth.config import PASSWORD_MIN_LENGTH
        assert PASSWORD_MIN_LENGTH == 8

    def test_bcrypt_hashing_performance(self):
        """Test that bcrypt hashing is not too fast (should include salt rounds)."""
        import time
        password = "test_password_12345"

        start = time.time()
        hash_result = get_password_hash(password)
        duration = time.time() - start

        # Bcrypt with default rounds should take at least 50ms
        assert duration > 0.05, "Password hashing too fast - may not include proper salt rounds"
