"""SQLAlchemy database models for SecureHR application."""

from sqlalchemy import Column, String, DateTime, Boolean, Enum as SQLEnum, Text, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime
import uuid

from .user import UserRole, CVProcessingStatus

Base = declarative_base()


def generate_uuid():
    """Generate a UUID string."""
    return str(uuid.uuid4())


class UserDB(Base):
    """Base user database model."""
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(SQLEnum(UserRole), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Candidate-specific fields
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    cv_uploaded_at = Column(DateTime(timezone=True), nullable=True)
    cv_processing_status = Column(
        SQLEnum(CVProcessingStatus), 
        default=CVProcessingStatus.PENDING,
        nullable=True
    )
    vector_id = Column(String, nullable=True)
    
    # Recruiter-specific fields
    company_name = Column(String, nullable=True)
    job_title = Column(String, nullable=True)

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"


class CVVectorDB(Base):
    """CV vector metadata model for tracking vectors stored in CyborgDB."""
    __tablename__ = "cv_vectors"

    id = Column(String, primary_key=True, default=generate_uuid)
    candidate_id = Column(String, nullable=False, index=True)
    cyborgdb_vector_id = Column(String, nullable=False, index=True)  # Reference to vector in CyborgDB
    vector_dimensions = Column(String, nullable=False)  # Store as string for flexibility
    original_filename = Column(String, nullable=True)  # Original CV filename
    file_hash = Column(String, nullable=True)  # Hash of original file for integrity checking
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<CVVector(id={self.id}, candidate_id={self.candidate_id}, cyborgdb_id={self.cyborgdb_vector_id})>"


class SavedSearchDB(Base):
    """Saved search database model for recruiters."""
    __tablename__ = "saved_searches"

    id = Column(String, primary_key=True, default=generate_uuid)
    recruiter_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    requirements = Column(Text, nullable=False)  # Job requirements text
    filters = Column(JSON, nullable=True)  # Search filters as JSON
    limit = Column(String, nullable=True)  # Search limit
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    use_count = Column(String, default="0", nullable=False)  # Number of times used

    def __repr__(self):
        return f"<SavedSearch(id={self.id}, name={self.name}, recruiter_id={self.recruiter_id})>"