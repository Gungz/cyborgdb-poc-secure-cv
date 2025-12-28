"""Profile management API endpoints for SecureHR application."""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_active_user
from app.models.database import UserDB, CVVectorDB
from app.models.user import UserRole, CVProcessingStatus, CandidateResponse, RecruiterResponse
from app.services.cv_processor import CVProcessorService
from app.services.cyborgdb_service import CyborgDBService
from app.services.notification_service import notification_service, Notification, NotificationSeverity
from app.services.upload_queue import upload_queue_manager, UploadTask
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profile", tags=["profile"])


class ProfileUpdateRequest(BaseModel):
    """Request model for updating candidate profile."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class ProfileDeleteResponse(BaseModel):
    """Response model for profile deletion."""
    message: str
    deleted_at: datetime


class CVReplacementResponse(BaseModel):
    """Response model for CV replacement."""
    message: str
    processing_status: CVProcessingStatus
    uploaded_at: datetime
    task_id: Optional[str] = None  # For tracking async processing


class NotificationResponse(BaseModel):
    """Response model for notifications."""
    id: str
    type: str
    severity: str
    title: str
    message: str
    details: Optional[Dict[str, Any]] = None
    created_at: datetime
    read: bool


class UploadStatusResponse(BaseModel):
    """Response model for upload status."""
    task_id: str
    status: str
    filename: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


@router.get("/me", response_model=CandidateResponse)
async def get_candidate_profile(
    current_user: UserDB = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get current candidate's profile information.
    
    Args:
        current_user: The current authenticated user
        db: Database session
        
    Returns:
        CandidateResponse: Current candidate profile information
        
    Raises:
        HTTPException: If user is not a candidate or profile not found
    """
    # Verify user is a candidate
    if current_user.role != UserRole.CANDIDATE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only candidates can access candidate profiles"
        )
    
    # Get CV filename from cv_vectors table
    cv_filename = None
    cv_vector = db.query(CVVectorDB).filter(CVVectorDB.candidate_id == current_user.id).first()
    if cv_vector:
        cv_filename = cv_vector.original_filename
    
    # Return candidate profile information
    return CandidateResponse(
        id=current_user.id,
        email=current_user.email,
        created_at=current_user.created_at,
        last_login_at=current_user.last_login_at,
        is_active=current_user.is_active,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        cv_uploaded_at=current_user.cv_uploaded_at,
        cv_processing_status=current_user.cv_processing_status,
        cv_filename=cv_filename
    )


@router.get("/recruiter/me", response_model=RecruiterResponse)
async def get_recruiter_profile(
    current_user: UserDB = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get current recruiter's profile information.
    
    Args:
        current_user: The current authenticated user
        db: Database session
        
    Returns:
        RecruiterResponse: Current recruiter profile information
        
    Raises:
        HTTPException: If user is not a recruiter or profile not found
    """
    # Verify user is a recruiter
    if current_user.role != UserRole.RECRUITER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only recruiters can access recruiter profiles"
        )
    
    # Return recruiter profile information
    return RecruiterResponse(
        id=current_user.id,
        email=current_user.email,
        created_at=current_user.created_at,
        last_login_at=current_user.last_login_at,
        is_active=current_user.is_active,
        company_name=current_user.company_name,
        job_title=current_user.job_title
    )


@router.put("/me", response_model=CandidateResponse)
async def update_candidate_profile(
    profile_update: ProfileUpdateRequest,
    current_user: UserDB = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Update current candidate's profile information.
    
    Args:
        profile_update: Profile update data
        current_user: The current authenticated user
        db: Database session
        
    Returns:
        CandidateResponse: Updated candidate profile information
        
    Raises:
        HTTPException: If user is not a candidate or update fails
    """
    # Verify user is a candidate
    if current_user.role != UserRole.CANDIDATE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only candidates can update candidate profiles"
        )
    
    try:
        # Update profile fields if provided
        if profile_update.first_name is not None:
            current_user.first_name = profile_update.first_name.strip()
        
        if profile_update.last_name is not None:
            current_user.last_name = profile_update.last_name.strip()
        
        # Commit changes
        db.commit()
        db.refresh(current_user)
        
        logger.info(f"Updated profile for candidate {current_user.id}")
        
        # Get CV filename from cv_vectors table
        cv_filename = None
        cv_vector = db.query(CVVectorDB).filter(CVVectorDB.candidate_id == current_user.id).first()
        if cv_vector:
            cv_filename = cv_vector.original_filename
        
        # Return updated profile
        return CandidateResponse(
            id=current_user.id,
            email=current_user.email,
            created_at=current_user.created_at,
            last_login_at=current_user.last_login_at,
            is_active=current_user.is_active,
            first_name=current_user.first_name,
            last_name=current_user.last_name,
            cv_uploaded_at=current_user.cv_uploaded_at,
            cv_processing_status=current_user.cv_processing_status,
            cv_filename=cv_filename
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update profile for candidate {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )


@router.post("/cv/replace", response_model=CVReplacementResponse)
async def replace_cv(
    file: UploadFile = File(...),
    current_user: UserDB = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Replace candidate's CV with a new one.
    
    This operation will:
    1. Queue the CV replacement for processing
    2. Delete the existing CV vector from CyborgDB
    3. Process the new CV file
    4. Store the new CV vector in CyborgDB
    5. Update the candidate's profile
    
    Args:
        file: New CV file to upload
        current_user: The current authenticated user
        db: Database session
        
    Returns:
        CVReplacementResponse: CV replacement confirmation
        
    Raises:
        HTTPException: If user is not a candidate or replacement fails
    """
    # Verify user is a candidate
    if current_user.role != UserRole.CANDIDATE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only candidates can replace CVs"
        )
    
    # Check if user already has uploads processing
    if upload_queue_manager.is_user_processing(current_user.id):
        # Notify about concurrent upload
        notification_service.notify_concurrent_upload_warning(
            user_id=current_user.id,
            filename=file.filename or "unknown"
        )
        
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another CV upload is currently being processed. Please wait for it to complete."
        )
    
    try:
        # Queue the CV replacement for processing
        task_id = await upload_queue_manager.queue_upload(
            candidate_id=current_user.id,
            file=file,
            processor_func=_process_cv_replacement,
            db=db
        )
        
        # Set processing status to pending
        current_user.cv_processing_status = CVProcessingStatus.PENDING
        db.commit()
        
        logger.info(f"Queued CV replacement task {task_id} for candidate {current_user.id}")
        
        return CVReplacementResponse(
            message="CV replacement queued for processing",
            processing_status=CVProcessingStatus.PENDING,
            uploaded_at=datetime.utcnow(),
            task_id=task_id
        )
        
    except Exception as e:
        logger.error(f"Failed to queue CV replacement for candidate {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue CV replacement: {str(e)}"
        )


async def _process_cv_replacement(file: UploadFile, candidate_id: str, db: Session):
    """
    Internal function to process CV replacement.
    
    Args:
        file: CV file to process
        candidate_id: ID of the candidate
        db: Database session
        
    Raises:
        Exception: If processing fails
    """
    cv_processor = CVProcessorService()
    cyborgdb_service = CyborgDBService()
    
    try:
        # Get user from database
        user = db.query(UserDB).filter(UserDB.id == candidate_id).first()
        if not user:
            raise Exception("User not found")
        
        # If user has an existing CV, delete it first
        old_filename = None
        if user.vector_id:
            try:
                # Get old filename from vector metadata
                existing_vector = db.query(CVVectorDB).filter(
                    CVVectorDB.candidate_id == candidate_id
                ).first()
                if existing_vector:
                    old_filename = existing_vector.original_filename
                
                # Delete from CyborgDB
                await cyborgdb_service.delete_vector(user.vector_id)
                
                # Delete vector metadata from local database
                if existing_vector:
                    db.delete(existing_vector)
                    db.commit()
                
                logger.info(f"Deleted existing CV for candidate {candidate_id}")
                
            except Exception as e:
                logger.warning(f"Failed to delete existing CV for candidate {candidate_id}: {e}")
                # Continue with replacement even if deletion fails
        
        # Process new CV
        start_time = datetime.utcnow()
        cyborgdb_item_id = await cv_processor.process_cv_complete(
            file=file,
            candidate_id=candidate_id,
            db=db
        )
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        # Update candidate profile
        user.vector_id = cyborgdb_item_id
        user.cv_uploaded_at = datetime.utcnow()
        user.cv_processing_status = CVProcessingStatus.COMPLETED
        db.commit()
        
        # Notify success
        if old_filename:
            notification_service.notify_cv_replacement_success(
                user_id=candidate_id,
                old_filename=old_filename,
                new_filename=file.filename or "unknown"
            )
        else:
            notification_service.notify_cv_processing_success(
                user_id=candidate_id,
                filename=file.filename or "unknown",
                processing_time=processing_time
            )
        
        logger.info(f"Successfully replaced CV for candidate {candidate_id}")
        
    except Exception as e:
        # Update status to failed
        user = db.query(UserDB).filter(UserDB.id == candidate_id).first()
        if user:
            user.cv_processing_status = CVProcessingStatus.FAILED
            db.commit()
        
        # Notify failure
        error_message = str(e)
        resolution_guidance = notification_service.get_error_resolution_guidance("cv_processing", error_message)
        
        notification_service.notify_cv_processing_failure(
            user_id=candidate_id,
            filename=file.filename or "unknown",
            error_message=error_message,
            resolution_guidance=resolution_guidance
        )
        
        logger.error(f"CV replacement failed for candidate {candidate_id}: {e}")
        raise


@router.delete("/me", response_model=ProfileDeleteResponse)
async def delete_candidate_profile(
    current_user: UserDB = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Delete current candidate's profile and all associated data.
    
    This operation will:
    1. Delete CV vector from CyborgDB
    2. Delete vector metadata from local database
    3. Delete user account from local database
    
    Args:
        current_user: The current authenticated user
        db: Database session
        
    Returns:
        ProfileDeleteResponse: Deletion confirmation
        
    Raises:
        HTTPException: If user is not a candidate or deletion fails
    """
    # Verify user is a candidate
    if current_user.role != UserRole.CANDIDATE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only candidates can delete candidate profiles"
        )
    
    cyborgdb_service = CyborgDBService()
    deletion_time = datetime.utcnow()
    
    try:
        # Delete CV vector from CyborgDB if it exists
        if current_user.vector_id:
            try:
                await cyborgdb_service.delete_vector(current_user.vector_id)
                logger.info(f"Deleted CV vector from CyborgDB for candidate {current_user.id}")
            except Exception as e:
                logger.error(f"Failed to delete CV vector from CyborgDB for candidate {current_user.id}: {e}")
                # Continue with profile deletion even if CyborgDB deletion fails
        
        # Delete vector metadata from local database
        vector_records = db.query(CVVectorDB).filter(
            CVVectorDB.candidate_id == current_user.id
        ).all()
        
        for vector_record in vector_records:
            db.delete(vector_record)
        
        # Delete user account
        db.delete(current_user)
        db.commit()
        
        # Notify success
        notification_service.notify_profile_deletion_success(current_user.id)
        
        logger.info(f"Successfully deleted profile for candidate {current_user.id}")
        
        return ProfileDeleteResponse(
            message="Profile and all associated data successfully deleted",
            deleted_at=deletion_time
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Profile deletion failed for candidate {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Profile deletion failed: {str(e)}"
        )


@router.get("/notifications", response_model=List[NotificationResponse])
async def get_notifications(
    unread_only: bool = False,
    limit: Optional[int] = 20,
    current_user: UserDB = Depends(get_current_active_user)
):
    """
    Get notifications for the current user.
    
    Args:
        unread_only: Only return unread notifications
        limit: Maximum number of notifications to return
        current_user: The current authenticated user
        
    Returns:
        List of notifications
    """
    notifications = notification_service.get_user_notifications(
        user_id=current_user.id,
        unread_only=unread_only,
        limit=limit
    )
    
    return [
        NotificationResponse(
            id=notification.id,
            type=notification.type.value,
            severity=notification.severity.value,
            title=notification.title,
            message=notification.message,
            details=notification.details,
            created_at=notification.created_at,
            read=notification.read
        )
        for notification in notifications
    ]


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: UserDB = Depends(get_current_active_user)
):
    """
    Mark a notification as read.
    
    Args:
        notification_id: ID of the notification to mark as read
        current_user: The current authenticated user
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If notification not found
    """
    success = notification_service.mark_notification_read(
        user_id=current_user.id,
        notification_id=notification_id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    return {"message": "Notification marked as read"}


@router.get("/uploads", response_model=List[UploadStatusResponse])
async def get_upload_status(
    current_user: UserDB = Depends(get_current_active_user)
):
    """
    Get upload status for all user's uploads.
    
    Args:
        current_user: The current authenticated user
        
    Returns:
        List of upload statuses
    """
    # Verify user is a candidate
    if current_user.role != UserRole.CANDIDATE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only candidates can view upload status"
        )
    
    user_uploads = upload_queue_manager.get_user_uploads(current_user.id)
    
    return [
        UploadStatusResponse(
            task_id=task.task_id,
            status=task.status.value,
            filename=task.filename,
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
            error_message=task.error_message
        )
        for task in user_uploads.values()
    ]


@router.get("/uploads/{task_id}", response_model=UploadStatusResponse)
async def get_specific_upload_status(
    task_id: str,
    current_user: UserDB = Depends(get_current_active_user)
):
    """
    Get status of a specific upload task.
    
    Args:
        task_id: ID of the upload task
        current_user: The current authenticated user
        
    Returns:
        Upload status
        
    Raises:
        HTTPException: If task not found
    """
    # Verify user is a candidate
    if current_user.role != UserRole.CANDIDATE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only candidates can view upload status"
        )
    
    upload_task = upload_queue_manager.get_upload_status(current_user.id, task_id)
    
    if not upload_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload task not found"
        )
    
    return UploadStatusResponse(
        task_id=upload_task.task_id,
        status=upload_task.status.value,
        filename=upload_task.filename,
        created_at=upload_task.created_at,
        started_at=upload_task.started_at,
        completed_at=upload_task.completed_at,
        error_message=upload_task.error_message
    )


@router.delete("/uploads/{task_id}")
async def cancel_upload(
    task_id: str,
    current_user: UserDB = Depends(get_current_active_user)
):
    """
    Cancel a queued upload task.
    
    Args:
        task_id: ID of the upload task to cancel
        current_user: The current authenticated user
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If task not found or cannot be cancelled
    """
    # Verify user is a candidate
    if current_user.role != UserRole.CANDIDATE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only candidates can cancel uploads"
        )
    
    success = await upload_queue_manager.cancel_upload(current_user.id, task_id)
    
    if not success:
        upload_task = upload_queue_manager.get_upload_status(current_user.id, task_id)
        if not upload_task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Upload task not found"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot cancel upload that is already processing or completed"
            )
    
    return {"message": "Upload task cancelled successfully"}