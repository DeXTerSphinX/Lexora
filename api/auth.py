"""Authentication API routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from core.database import get_db, User, RefreshToken
from core.auth.models import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    RefreshRequest,
    UserResponse,
)
from core.auth.password import get_password_hash, verify_password
from core.auth.token import create_access_token, create_refresh_token, verify_token
from core.auth.config import ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DELTA
from api.dependencies import get_current_user
import hashlib

router = APIRouter()


@router.post("/register", response_model=TokenResponse)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user and return access/refresh tokens.

    Args:
        request: RegisterRequest with email, full_name, password, role
        db: Database session

    Returns:
        TokenResponse with access and refresh tokens

    Raises:
        HTTPException: 400 if email already exists or validation fails
    """
    # Check if email already exists (case-insensitive)
    existing_user = db.query(User).filter(
        User.email.ilike(request.email)
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Create new user
    user = User(
        email=request.email.lower(),
        full_name=request.full_name,
        password_hash=get_password_hash(request.password),
        role=request.role if request.role in ["student", "admin"] else "student",
        is_active=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    # Create tokens
    access_token = create_access_token(
        data={"sub": user.id, "email": user.email, "role": user.role}
    )

    plain_refresh_token, refresh_token_hash = create_refresh_token()

    # Store refresh token in database
    db_refresh_token = RefreshToken(
        user_id=user.id,
        token_hash=refresh_token_hash,
        expires_at=datetime.utcnow() + REFRESH_TOKEN_EXPIRE_DELTA,
    )
    db.add(db_refresh_token)
    db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=plain_refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate user and return access/refresh tokens.

    Args:
        request: LoginRequest with email and password
        db: Database session

    Returns:
        TokenResponse with access and refresh tokens

    Raises:
        HTTPException: 401 if credentials are invalid
    """
    # Find user by email (case-insensitive)
    user = db.query(User).filter(User.email.ilike(request.email)).first()

    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
        )

    # Create tokens
    access_token = create_access_token(
        data={"sub": user.id, "email": user.email, "role": user.role}
    )

    plain_refresh_token, refresh_token_hash = create_refresh_token()

    # Store refresh token in database
    db_refresh_token = RefreshToken(
        user_id=user.id,
        token_hash=refresh_token_hash,
        expires_at=datetime.utcnow() + REFRESH_TOKEN_EXPIRE_DELTA,
    )
    db.add(db_refresh_token)
    db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=plain_refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(request: RefreshRequest, db: Session = Depends(get_db)):
    """Refresh an access token using a refresh token.

    Args:
        request: RefreshRequest with refresh_token
        db: Database session

    Returns:
        TokenResponse with new access token (refresh token may be rotated)

    Raises:
        HTTPException: 401 if refresh token is invalid/expired/revoked
    """
    # Hash the provided refresh token to look it up
    token_hash = hashlib.sha256(request.refresh_token.encode()).hexdigest()

    # Find the refresh token in database
    db_refresh_token = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash
    ).first()

    if not db_refresh_token or db_refresh_token.is_revoked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked refresh token",
        )

    # Check if token is expired
    if datetime.utcnow() > db_refresh_token.expires_at:
        db_refresh_token.is_revoked = True
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
        )

    # Get user
    user = db.query(User).filter(User.id == db_refresh_token.user_id).first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Create new access token
    access_token = create_access_token(
        data={"sub": user.id, "email": user.email, "role": user.role}
    )

    # Optionally rotate refresh token
    plain_refresh_token, refresh_token_hash = create_refresh_token()
    new_db_refresh_token = RefreshToken(
        user_id=user.id,
        token_hash=refresh_token_hash,
        expires_at=datetime.utcnow() + REFRESH_TOKEN_EXPIRE_DELTA,
    )
    db.add(new_db_refresh_token)

    # Revoke old refresh token
    db_refresh_token.is_revoked = True
    db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=plain_refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout")
def logout(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Logout user by revoking all their refresh tokens.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        Success message
    """
    # Revoke all refresh tokens for this user
    db.query(RefreshToken).filter(RefreshToken.user_id == current_user.id).update(
        {"is_revoked": True}
    )
    db.commit()

    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user's information.

    Args:
        current_user: Current authenticated user

    Returns:
        UserResponse with user details
    """
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at.isoformat(),
    )
