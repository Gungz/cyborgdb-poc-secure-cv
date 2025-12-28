"""Vector models for SecureHR application."""

from typing import Optional
from pydantic import BaseModel
from datetime import datetime


class CVVector(BaseModel):
    """CV vector metadata model."""
    id: str
    candidate_id: str
    cyborgdb_vector_id: str  # Reference to vector stored in CyborgDB
    vector_dimensions: int
    original_filename: Optional[str] = None
    file_hash: Optional[str] = None  # Hash of original file for integrity
    created_at: datetime
    last_updated_at: datetime


class CVVectorCreateRequest(BaseModel):
    """Request model for creating a CV vector."""
    candidate_id: str
    cyborgdb_vector_id: str
    vector_dimensions: int
    original_filename: Optional[str] = None
    file_hash: Optional[str] = None


class CVVectorResponse(BaseModel):
    """Response model for CV vector operations."""
    id: str
    candidate_id: str
    cyborgdb_vector_id: str
    vector_dimensions: int
    original_filename: Optional[str] = None
    file_hash: Optional[str] = None
    created_at: datetime
    last_updated_at: datetime
    
    class Config:
        from_attributes = True  # For SQLAlchemy model conversion