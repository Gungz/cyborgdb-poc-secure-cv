"""Authentication middleware for SecureHR application."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.services.auth import auth_service
from app.models.database import UserDB
from app.models.user import UserRole


# HTTP Bearer token scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> UserDB:
    """
    Get the current authenticated user from JWT token.
    
    Args:
        credentials: HTTP Bearer credentials containing the JWT token
        db: Database session
        
    Returns:
        UserDB: The authenticated user
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Verify the token
    payload = auth_service.verify_token(credentials.credentials)
    if payload is None:
        raise credentials_exception
    
    # Extract user ID from token
    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    
    # Get user from database
    user = auth_service.get_user_by_id(db, user_id)
    if user is None:
        raise credentials_exception
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user"
        )
    
    return user


async def get_current_active_user(
    current_user: UserDB = Depends(get_current_user)
) -> UserDB:
    """
    Get the current active user.
    
    Args:
        current_user: The current user from get_current_user
        
    Returns:
        UserDB: The active user
        
    Raises:
        HTTPException: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


async def get_current_candidate(
    current_user: UserDB = Depends(get_current_active_user)
) -> UserDB:
    """
    Get the current user if they are a candidate.
    
    Args:
        current_user: The current active user
        
    Returns:
        UserDB: The candidate user
        
    Raises:
        HTTPException: If user is not a candidate
    """
    if current_user.role != UserRole.CANDIDATE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Candidate role required."
        )
    return current_user


async def get_current_recruiter(
    current_user: UserDB = Depends(get_current_active_user)
) -> UserDB:
    """
    Get the current user if they are a recruiter.
    
    Args:
        current_user: The current active user
        
    Returns:
        UserDB: The recruiter user
        
    Raises:
        HTTPException: If user is not a recruiter
    """
    if current_user.role != UserRole.RECRUITER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Recruiter role required."
        )
    return current_user


def verify_token_optional(token: Optional[str] = None) -> Optional[dict]:
    """
    Verify a JWT token without raising exceptions.
    
    Args:
        token: The JWT token to verify
        
    Returns:
        dict: The decoded token payload if valid, None otherwise
    """
    if not token:
        return None
    
    return auth_service.verify_token(token)