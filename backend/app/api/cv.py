"""CV processing API endpoints."""

import logging
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

from ..database import get_db
from ..middleware.auth import get_current_user
from ..models.user import Candidate, CVProcessingStatus
from ..models.database import UserDB
from ..services.cv_processor import CVProcessorService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cv", tags=["cv"])
security = HTTPBearer()


@router.post("/upload", response_model=Dict[str, Any])
async def upload_cv(
    file: UploadFile = File(...),
    current_user: Candidate = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Upload and process a CV file.
    
    Args:
        file: The CV file to upload (PDF, DOCX supported)
        current_user: The authenticated candidate user
        db: Database session
        
    Returns:
        Processing result with vector storage info
        
    Raises:
        HTTPException: If file processing fails
    """
    # Ensure only candidates can upload CVs
    if current_user.role != "candidate":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only candidates can upload CVs"
        )
    
    try:
        # Initialize CV processor service
        cv_processor = CVProcessorService()
        
        # Process CV completely: extract text, generate vector, encrypt, and store
        cyborgdb_vector_id = await cv_processor.process_cv_complete(
            file=file,
            candidate_id=current_user.id,
            db=db
        )
        
        # Update user's CV status fields
        user = db.query(UserDB).filter(UserDB.id == current_user.id).first()
        if user:
            user.cv_uploaded_at = datetime.utcnow()
            user.cv_processing_status = CVProcessingStatus.COMPLETED
            user.vector_id = cyborgdb_vector_id
            db.commit()
        
        logger.info(f"Successfully processed CV for candidate {current_user.id}")
        
        # Return processing result
        return {
            "message": "CV processed and stored successfully",
            "filename": file.filename,
            "candidate_id": current_user.id,
            "cyborgdb_vector_id": cyborgdb_vector_id,
            "status": "completed"
        }
        
    except HTTPException:
        # Update status to failed on HTTP exceptions
        user = db.query(UserDB).filter(UserDB.id == current_user.id).first()
        if user:
            user.cv_processing_status = CVProcessingStatus.FAILED
            db.commit()
        raise
    except Exception as e:
        # Update status to failed on general exceptions
        user = db.query(UserDB).filter(UserDB.id == current_user.id).first()
        if user:
            user.cv_processing_status = CVProcessingStatus.FAILED
            db.commit()
        logger.error(f"CV upload failed for candidate {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="CV processing failed. Please try again."
        )


@router.get("/status")
async def get_cv_status(
    current_user: Candidate = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get CV processing status for the current candidate.
    
    Args:
        current_user: The authenticated candidate user
        
    Returns:
        CV status information
    """
    # Ensure only candidates can check CV status
    if current_user.role != "candidate":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only candidates can check CV status"
        )
    
    return {
        "candidate_id": current_user.id,
        "cv_uploaded_at": current_user.cv_uploaded_at,
        "cv_processing_status": current_user.cv_processing_status,
        "has_cv": current_user.vector_id is not None
    }