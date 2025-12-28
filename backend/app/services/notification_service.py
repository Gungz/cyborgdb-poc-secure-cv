"""Notification service for SecureHR application."""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.database import UserDB
from app.models.user import UserRole, CVProcessingStatus

logger = logging.getLogger(__name__)


class NotificationType(str, Enum):
    """Notification type enumeration."""
    CV_PROCESSING_SUCCESS = "cv_processing_success"
    CV_PROCESSING_FAILURE = "cv_processing_failure"
    CV_REPLACEMENT_SUCCESS = "cv_replacement_success"
    CV_REPLACEMENT_FAILURE = "cv_replacement_failure"
    PROFILE_DELETION_SUCCESS = "profile_deletion_success"
    PROFILE_DELETION_FAILURE = "profile_deletion_failure"
    CONCURRENT_UPLOAD_WARNING = "concurrent_upload_warning"
    SYSTEM_ERROR = "system_error"


class NotificationSeverity(str, Enum):
    """Notification severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"


class Notification(BaseModel):
    """Notification model."""
    id: str
    user_id: str
    type: NotificationType
    severity: NotificationSeverity
    title: str
    message: str
    details: Optional[Dict[str, Any]] = None
    created_at: datetime
    read: bool = False


class NotificationService:
    """Service for handling user notifications and error reporting."""
    
    def __init__(self):
        """Initialize notification service."""
        self._notifications: Dict[str, List[Notification]] = {}
    
    def create_notification(
        self,
        user_id: str,
        notification_type: NotificationType,
        severity: NotificationSeverity,
        title: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> Notification:
        """
        Create a new notification for a user.
        
        Args:
            user_id: ID of the user to notify
            notification_type: Type of notification
            severity: Severity level
            title: Notification title
            message: Notification message
            details: Optional additional details
            
        Returns:
            Created notification
        """
        import uuid
        
        notification = Notification(
            id=str(uuid.uuid4()),
            user_id=user_id,
            type=notification_type,
            severity=severity,
            title=title,
            message=message,
            details=details,
            created_at=datetime.utcnow()
        )
        
        # Store notification in memory (in production, use database)
        if user_id not in self._notifications:
            self._notifications[user_id] = []
        
        self._notifications[user_id].append(notification)
        
        # Log notification
        logger.info(f"Created {severity.value} notification for user {user_id}: {title}")
        
        return notification
    
    def get_user_notifications(
        self,
        user_id: str,
        unread_only: bool = False,
        limit: Optional[int] = None
    ) -> List[Notification]:
        """
        Get notifications for a user.
        
        Args:
            user_id: ID of the user
            unread_only: Only return unread notifications
            limit: Maximum number of notifications to return
            
        Returns:
            List of notifications
        """
        user_notifications = self._notifications.get(user_id, [])
        
        if unread_only:
            user_notifications = [n for n in user_notifications if not n.read]
        
        # Sort by creation time (newest first)
        user_notifications.sort(key=lambda x: x.created_at, reverse=True)
        
        if limit:
            user_notifications = user_notifications[:limit]
        
        return user_notifications
    
    def mark_notification_read(self, user_id: str, notification_id: str) -> bool:
        """
        Mark a notification as read.
        
        Args:
            user_id: ID of the user
            notification_id: ID of the notification
            
        Returns:
            True if notification was found and marked as read
        """
        user_notifications = self._notifications.get(user_id, [])
        
        for notification in user_notifications:
            if notification.id == notification_id:
                notification.read = True
                logger.info(f"Marked notification {notification_id} as read for user {user_id}")
                return True
        
        return False
    
    def notify_cv_processing_success(
        self,
        user_id: str,
        filename: str,
        processing_time: Optional[float] = None
    ) -> Notification:
        """
        Notify user of successful CV processing.
        
        Args:
            user_id: ID of the candidate
            filename: Name of the processed file
            processing_time: Time taken to process (in seconds)
            
        Returns:
            Created notification
        """
        details = {"filename": filename}
        if processing_time:
            details["processing_time_seconds"] = processing_time
        
        return self.create_notification(
            user_id=user_id,
            notification_type=NotificationType.CV_PROCESSING_SUCCESS,
            severity=NotificationSeverity.SUCCESS,
            title="CV Processing Complete",
            message=f"Your CV '{filename}' has been successfully processed and is now searchable by recruiters.",
            details=details
        )
    
    def notify_cv_processing_failure(
        self,
        user_id: str,
        filename: str,
        error_message: str,
        resolution_guidance: Optional[str] = None
    ) -> Notification:
        """
        Notify user of CV processing failure.
        
        Args:
            user_id: ID of the candidate
            filename: Name of the failed file
            error_message: Error that occurred
            resolution_guidance: Guidance for resolving the issue
            
        Returns:
            Created notification
        """
        details = {
            "filename": filename,
            "error": error_message
        }
        
        if resolution_guidance:
            details["resolution_guidance"] = resolution_guidance
        
        # Provide default resolution guidance based on error type
        if not resolution_guidance:
            if "file format" in error_message.lower():
                resolution_guidance = "Please ensure your CV is in PDF, DOC, or DOCX format."
            elif "file size" in error_message.lower():
                resolution_guidance = "Please reduce your file size to under 10MB."
            elif "text content" in error_message.lower():
                resolution_guidance = "Please ensure your CV contains readable text content."
            else:
                resolution_guidance = "Please try uploading your CV again. If the problem persists, contact support."
        
        message = f"Failed to process your CV '{filename}': {error_message}"
        if resolution_guidance:
            message += f" {resolution_guidance}"
        
        return self.create_notification(
            user_id=user_id,
            notification_type=NotificationType.CV_PROCESSING_FAILURE,
            severity=NotificationSeverity.ERROR,
            title="CV Processing Failed",
            message=message,
            details=details
        )
    
    def notify_cv_replacement_success(
        self,
        user_id: str,
        old_filename: Optional[str],
        new_filename: str
    ) -> Notification:
        """
        Notify user of successful CV replacement.
        
        Args:
            user_id: ID of the candidate
            old_filename: Name of the replaced file
            new_filename: Name of the new file
            
        Returns:
            Created notification
        """
        details = {
            "old_filename": old_filename,
            "new_filename": new_filename
        }
        
        message = f"Your CV has been successfully replaced with '{new_filename}'."
        if old_filename:
            message += f" The previous CV '{old_filename}' has been removed."
        
        return self.create_notification(
            user_id=user_id,
            notification_type=NotificationType.CV_REPLACEMENT_SUCCESS,
            severity=NotificationSeverity.SUCCESS,
            title="CV Replacement Complete",
            message=message,
            details=details
        )
    
    def notify_concurrent_upload_warning(
        self,
        user_id: str,
        filename: str
    ) -> Notification:
        """
        Notify user about concurrent upload handling.
        
        Args:
            user_id: ID of the candidate
            filename: Name of the file being queued
            
        Returns:
            Created notification
        """
        return self.create_notification(
            user_id=user_id,
            notification_type=NotificationType.CONCURRENT_UPLOAD_WARNING,
            severity=NotificationSeverity.WARNING,
            title="CV Upload Queued",
            message=f"Your CV '{filename}' has been queued for processing. Please wait for the current upload to complete before uploading another file.",
            details={"filename": filename}
        )
    
    def notify_profile_deletion_success(self, user_id: str) -> Notification:
        """
        Notify user of successful profile deletion.
        
        Args:
            user_id: ID of the candidate
            
        Returns:
            Created notification
        """
        return self.create_notification(
            user_id=user_id,
            notification_type=NotificationType.PROFILE_DELETION_SUCCESS,
            severity=NotificationSeverity.SUCCESS,
            title="Profile Deleted",
            message="Your profile and all associated data have been successfully deleted from our system.",
            details={"deleted_at": datetime.utcnow().isoformat()}
        )
    
    def get_error_resolution_guidance(self, error_type: str, error_message: str) -> str:
        """
        Get resolution guidance for common errors.
        
        Args:
            error_type: Type of error
            error_message: Error message
            
        Returns:
            Resolution guidance string
        """
        error_lower = error_message.lower()
        
        if "file format" in error_lower or "file type" in error_lower:
            return "Please ensure your CV is in PDF, DOC, or DOCX format and try again."
        
        if "file size" in error_lower:
            return "Your file is too large. Please reduce the file size to under 10MB and try again."
        
        if "text content" in error_lower or "extract" in error_lower:
            return "We couldn't extract text from your CV. Please ensure it contains readable text and isn't password-protected."
        
        if "corrupted" in error_lower or "invalid" in error_lower:
            return "Your file appears to be corrupted. Please try saving your CV in a different format and upload again."
        
        if "network" in error_lower or "connection" in error_lower:
            return "There was a network issue. Please check your connection and try again."
        
        if "server" in error_lower or "internal" in error_lower:
            return "We're experiencing technical difficulties. Please try again in a few minutes."
        
        return "Please try again. If the problem persists, contact our support team for assistance."


# Global notification service instance
notification_service = NotificationService()