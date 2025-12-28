"""Authentication API endpoints for SecureHR application."""

from datetime import datetime, timedelta
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.auth import auth_service
from app.middleware.auth import get_current_active_user, verify_token_optional
from app.models.auth import (
    LoginRequest,
    TokenResponse,
    TokenValidationResponse,
    LogoutResponse,
    CurrentUserResponse,
    CandidateRegistrationRequest,
    RecruiterRegistrationRequest
)
from app.models.database import UserDB
from app.models.user import UserRole, CVProcessingStatus
from app.config import settings


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register/candidate", response_model=TokenResponse)
async def register_candidate(
    registration_request: CandidateRegistrationRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new candidate account.
    
    Args:
        registration_request: Candidate registration data
        db: Database session
        
    Returns:
        TokenResponse: JWT token and user information
        
    Raises:
        HTTPException: If email already exists or validation fails
    """
    # Check if email already exists
    existing_user = db.query(UserDB).filter(UserDB.email == registration_request.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists"
        )
    
    # Create new candidate user
    user_id = str(uuid.uuid4())
    password_hash = auth_service.get_password_hash(registration_request.password)
    
    new_user = UserDB(
        id=user_id,
        email=registration_request.email,
        password_hash=password_hash,
        role=UserRole.CANDIDATE,
        first_name=registration_request.first_name,
        last_name=registration_request.last_name,
        is_active=True,
        cv_processing_status=CVProcessingStatus.PENDING,
        created_at=datetime.utcnow()
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = auth_service.create_access_token(
        data={"sub": new_user.id, "role": new_user.role.value},
        expires_delta=access_token_expires
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
        user_id=new_user.id,
        user_role=new_user.role
    )


@router.post("/register/recruiter", response_model=TokenResponse)
async def register_recruiter(
    registration_request: RecruiterRegistrationRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new recruiter account.
    
    Args:
        registration_request: Recruiter registration data
        db: Database session
        
    Returns:
        TokenResponse: JWT token and user information
        
    Raises:
        HTTPException: If email already exists or validation fails
    """
    # Check if email already exists
    existing_user = db.query(UserDB).filter(UserDB.email == registration_request.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists"
        )
    
    # Create new recruiter user
    user_id = str(uuid.uuid4())
    password_hash = auth_service.get_password_hash(registration_request.password)
    
    new_user = UserDB(
        id=user_id,
        email=registration_request.email,
        password_hash=password_hash,
        role=UserRole.RECRUITER,
        company_name=registration_request.company_name,
        job_title=registration_request.job_title,
        is_active=True,
        created_at=datetime.utcnow()
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = auth_service.create_access_token(
        data={"sub": new_user.id, "role": new_user.role.value},
        expires_delta=access_token_expires
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
        user_id=new_user.id,
        user_role=new_user.role
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    login_request: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return JWT token.
    
    Args:
        login_request: Login credentials
        db: Database session
        
    Returns:
        TokenResponse: JWT token and user information
        
    Raises:
        HTTPException: If credentials are invalid
    """
    # Authenticate user
    user = auth_service.authenticate_user(db, login_request.email, login_request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive"
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = auth_service.create_access_token(
        data={"sub": user.id, "role": user.role.value},
        expires_delta=access_token_expires
    )
    
    # Update last login timestamp
    auth_service.update_last_login(db, user)
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,  # Convert to seconds
        user_id=user.id,
        user_role=user.role
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    current_user: UserDB = Depends(get_current_active_user)
):
    """
    Logout the current user.
    
    Note: Since JWT tokens are stateless, this endpoint primarily serves
    as a confirmation that the token is valid. The client should discard
    the token after receiving this response.
    
    Args:
        current_user: The current authenticated user
        
    Returns:
        LogoutResponse: Logout confirmation message
    """
    return LogoutResponse(message="Successfully logged out")


@router.post("/validate-token", response_model=TokenValidationResponse)
async def validate_token(
    request: dict
):
    """
    Validate a JWT token and return user information.
    
    Args:
        request: Dictionary containing the token to validate
        
    Returns:
        TokenValidationResponse: Token validation result and user info
    """
    token = request.get("token") if isinstance(request, dict) else request
    payload = verify_token_optional(token)
    
    if payload is None:
        return TokenValidationResponse(valid=False)
    
    # Extract information from token
    user_id = payload.get("sub")
    user_role_str = payload.get("role")
    exp_timestamp = payload.get("exp")
    
    # Convert role string to enum
    user_role = None
    if user_role_str:
        try:
            user_role = UserRole(user_role_str)
        except ValueError:
            user_role = None
    
    # Convert expiration timestamp to datetime
    expires_at = None
    if exp_timestamp:
        expires_at = datetime.utcfromtimestamp(exp_timestamp)
    
    return TokenValidationResponse(
        valid=True,
        user_id=user_id,
        user_role=user_role,
        expires_at=expires_at
    )


@router.get("/me", response_model=CurrentUserResponse)
async def get_current_user_info(
    current_user: UserDB = Depends(get_current_active_user)
):
    """
    Get information about the current authenticated user.
    
    Args:
        current_user: The current authenticated user
        
    Returns:
        CurrentUserResponse: Current user information
    """
    response_data = {
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.role,
        "created_at": current_user.created_at,
        "last_login_at": current_user.last_login_at,
        "is_active": current_user.is_active,
    }
    
    # Add role-specific fields
    if current_user.role == UserRole.CANDIDATE:
        response_data.update({
            "first_name": current_user.first_name,
            "last_name": current_user.last_name,
            "cv_uploaded_at": current_user.cv_uploaded_at,
            "cv_processing_status": current_user.cv_processing_status.value if current_user.cv_processing_status else None,
        })
    elif current_user.role == UserRole.RECRUITER:
        response_data.update({
            "company_name": current_user.company_name,
            "job_title": current_user.job_title,
        })
    
    return CurrentUserResponse(**response_data)


@router.post("/refresh-token", response_model=TokenResponse)
async def refresh_token(
    current_user: UserDB = Depends(get_current_active_user)
):
    """
    Refresh the JWT token for the current user.
    
    Args:
        current_user: The current authenticated user
        
    Returns:
        TokenResponse: New JWT token and user information
    """
    # Create new access token
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = auth_service.create_access_token(
        data={"sub": current_user.id, "role": current_user.role.value},
        expires_delta=access_token_expires
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,  # Convert to seconds
        user_id=current_user.id,
        user_role=current_user.role
    )