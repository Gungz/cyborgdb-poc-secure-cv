"""Models package initialization."""

from .user import (
    UserRole,
    CVProcessingStatus,
    BaseUser,
    Candidate,
    Recruiter,
    UserRegistrationRequest,
    CandidateRegistrationRequest,
    RecruiterRegistrationRequest,
    UserResponse,
    CandidateResponse,
    RecruiterResponse,
)
from .database import Base, UserDB, CVVectorDB

__all__ = [
    # Enums
    "UserRole",
    "CVProcessingStatus",
    # Pydantic models
    "BaseUser",
    "Candidate",
    "Recruiter",
    "UserRegistrationRequest",
    "CandidateRegistrationRequest",
    "RecruiterRegistrationRequest",
    "UserResponse",
    "CandidateResponse",
    "RecruiterResponse",
    # SQLAlchemy models
    "Base",
    "UserDB",
    "CVVectorDB",
]