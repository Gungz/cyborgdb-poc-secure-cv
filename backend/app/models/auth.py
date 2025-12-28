"""Authentication models for SecureHR application."""

from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime
import re

from .user import UserRole


class LoginRequest(BaseModel):
    """Login request model."""
    email: str
    password: str


class CandidateRegistrationRequest(BaseModel):
    """Candidate registration request model."""
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        return v
    
    @field_validator('first_name', 'last_name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate name is not empty and has reasonable length."""
        v = v.strip()
        if not v:
            raise ValueError('Name cannot be empty')
        if len(v) > 100:
            raise ValueError('Name cannot exceed 100 characters')
        return v


class RecruiterRegistrationRequest(BaseModel):
    """Recruiter registration request model."""
    email: EmailStr
    password: str
    company_name: str
    job_title: str
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        return v
    
    @field_validator('company_name')
    @classmethod
    def validate_company_name(cls, v: str) -> str:
        """Validate company name."""
        v = v.strip()
        if not v:
            raise ValueError('Company name cannot be empty')
        if len(v) > 200:
            raise ValueError('Company name cannot exceed 200 characters')
        return v
    
    @field_validator('job_title')
    @classmethod
    def validate_job_title(cls, v: str) -> str:
        """Validate job title."""
        v = v.strip()
        if not v:
            raise ValueError('Job title cannot be empty')
        if len(v) > 100:
            raise ValueError('Job title cannot exceed 100 characters')
        return v


class TokenResponse(BaseModel):
    """Token response model."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until expiration
    user_id: str
    user_role: UserRole


class TokenValidationResponse(BaseModel):
    """Token validation response model."""
    valid: bool
    user_id: Optional[str] = None
    user_role: Optional[UserRole] = None
    expires_at: Optional[datetime] = None


class LogoutResponse(BaseModel):
    """Logout response model."""
    message: str = "Successfully logged out"


class CurrentUserResponse(BaseModel):
    """Current user response model."""
    id: str
    email: str
    role: UserRole
    created_at: datetime
    last_login_at: Optional[datetime]
    is_active: bool
    
    # Candidate-specific fields (optional)
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    cv_uploaded_at: Optional[datetime] = None
    cv_processing_status: Optional[str] = None
    
    # Recruiter-specific fields (optional)
    company_name: Optional[str] = None
    job_title: Optional[str] = None