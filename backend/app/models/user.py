"""User models for SecureHR application."""

from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    """User role enumeration."""
    CANDIDATE = "candidate"
    RECRUITER = "recruiter"


class CVProcessingStatus(str, Enum):
    """CV processing status enumeration."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class BaseUser(BaseModel):
    """Base user model with common fields."""
    id: str
    email: str
    password_hash: str
    created_at: datetime
    last_login_at: Optional[datetime] = None
    is_active: bool = True


class Candidate(BaseUser):
    """Candidate user model."""
    role: UserRole = UserRole.CANDIDATE
    first_name: str
    last_name: str
    cv_uploaded_at: Optional[datetime] = None
    cv_processing_status: CVProcessingStatus = CVProcessingStatus.PENDING
    vector_id: Optional[str] = None


class Recruiter(BaseUser):
    """Recruiter user model."""
    role: UserRole = UserRole.RECRUITER
    company_name: str
    job_title: str


# Request/Response models for API
class UserRegistrationRequest(BaseModel):
    """Base user registration request."""
    email: str
    password: str


class CandidateRegistrationRequest(UserRegistrationRequest):
    """Candidate registration request."""
    first_name: str
    last_name: str


class RecruiterRegistrationRequest(UserRegistrationRequest):
    """Recruiter registration request."""
    company_name: str
    job_title: str


class UserResponse(BaseModel):
    """Base user response model."""
    id: str
    email: str
    created_at: datetime
    last_login_at: Optional[datetime]
    is_active: bool


class CandidateResponse(UserResponse):
    """Candidate response model."""
    role: UserRole = UserRole.CANDIDATE
    first_name: str
    last_name: str
    cv_uploaded_at: Optional[datetime]
    cv_processing_status: CVProcessingStatus
    cv_filename: Optional[str] = None


class RecruiterResponse(UserResponse):
    """Recruiter response model."""
    role: UserRole = UserRole.RECRUITER
    company_name: str
    job_title: str