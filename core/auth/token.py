"""JWT token generation and validation utilities."""

from datetime import datetime, timedelta
from typing import Any, Dict
import secrets
from jose import JWTError, jwt
from core.auth.config import (
    ALGORITHM,
    JWT_SECRET_KEY,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
)


def create_access_token(data: Dict[str, Any], expires_delta: timedelta = None) -> str:
    """Create a JWT access token.

    Args:
        data: Dictionary of claims to encode (should include 'sub' with user_id)
        expires_delta: Custom expiration time, defaults to ACCESS_TOKEN_EXPIRE_MINUTES

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()

    # JWT 'sub' claim must be a string
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "type": "access"})

    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token() -> tuple:
    """Generate a refresh token.

    Returns:
        Tuple of (plain_token, token_hash) for DB storage
    """
    # Generate random 64-character token
    plain_token = secrets.token_urlsafe(64)
    # Hash it for storage (using simple SHA256)
    import hashlib
    token_hash = hashlib.sha256(plain_token.encode()).hexdigest()
    return plain_token, token_hash


def verify_token(token: str) -> Dict[str, Any]:
    """Verify and decode a JWT access token.

    Args:
        token: JWT token string

    Returns:
        Decoded payload dictionary

    Raises:
        JWTError: If token is invalid, expired, or wrong type
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])

        # Ensure this is an access token
        if payload.get("type") != "access":
            raise JWTError("Invalid token type")

        return payload
    except JWTError:
        raise


def get_user_id_from_token(token: str) -> int:
    """Extract user_id from access token.

    Args:
        token: JWT access token

    Returns:
        User ID from token

    Raises:
        JWTError: If token is invalid
    """
    payload = verify_token(token)
    user_id = payload.get("sub")

    if not user_id:
        raise JWTError("Token missing subject claim")

    return int(user_id)
