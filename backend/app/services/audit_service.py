"""Audit logging and monitoring service for SecureHR application."""

import json
import logging
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
from fastapi import Request
import hashlib
import os

from app.config import get_settings

settings = get_settings()

# Configure audit logger
audit_logger = logging.getLogger("securehr.audit")
audit_logger.setLevel(logging.INFO)

# Create audit log handler
audit_handler = logging.FileHandler("audit.log")
audit_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
audit_handler.setFormatter(audit_formatter)
audit_logger.addHandler(audit_handler)

# Security event logger
security_logger = logging.getLogger("securehr.security")
security_logger.setLevel(logging.WARNING)

security_handler = logging.FileHandler("security.log")
security_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
security_handler.setFormatter(security_formatter)
security_logger.addHandler(security_handler)


class AuditEventType(str, Enum):
    """Types of audit events."""
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_REGISTRATION = "user_registration"
    CV_UPLOAD = "cv_upload"
    CV_PROCESSING = "cv_processing"
    CV_DELETION = "cv_deletion"
    SEARCH_QUERY = "search_query"
    PROFILE_VIEW = "profile_view"
    PROFILE_UPDATE = "profile_update"
    PROFILE_DELETION = "profile_deletion"
    DATA_ACCESS = "data_access"
    VECTOR_STORAGE = "vector_storage"
    VECTOR_RETRIEVAL = "vector_retrieval"
    AUTHENTICATION_FAILURE = "authentication_failure"
    AUTHORIZATION_FAILURE = "authorization_failure"
    SECURITY_VIOLATION = "security_violation"
    SYSTEM_ERROR = "system_error"


class SecurityEventType(str, Enum):
    """Types of security events."""
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    DDOS_ATTACK_DETECTED = "ddos_attack_detected"
    MALICIOUS_INPUT_DETECTED = "malicious_input_detected"
    UNAUTHORIZED_ACCESS_ATTEMPT = "unauthorized_access_attempt"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    DATA_BREACH_ATTEMPT = "data_breach_attempt"
    ENCRYPTION_FAILURE = "encryption_failure"
    SESSION_HIJACK_ATTEMPT = "session_hijack_attempt"
    BRUTE_FORCE_ATTACK = "brute_force_attack"
    SQL_INJECTION_ATTEMPT = "sql_injection_attempt"
    XSS_ATTEMPT = "xss_attempt"
    PATH_TRAVERSAL_ATTEMPT = "path_traversal_attempt"


@dataclass
class AuditEvent:
    """Audit event data structure."""
    event_id: str
    timestamp: str
    event_type: AuditEventType
    user_id: Optional[str]
    user_email: Optional[str]
    ip_address: str
    user_agent: str
    endpoint: str
    method: str
    status_code: Optional[int]
    resource_id: Optional[str]
    resource_type: Optional[str]
    details: Dict[str, Any]
    session_id: Optional[str]
    request_id: Optional[str]


@dataclass
class SecurityEvent:
    """Security event data structure."""
    event_id: str
    timestamp: str
    event_type: SecurityEventType
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    ip_address: str
    user_agent: str
    endpoint: str
    method: str
    details: Dict[str, Any]
    user_id: Optional[str]
    blocked: bool
    action_taken: str


class AuditService:
    """Service for audit logging and monitoring."""
    
    def __init__(self):
        self.settings = get_settings()
        self._event_counter = 0
    
    def _generate_event_id(self) -> str:
        """Generate unique event ID."""
        self._event_counter += 1
        timestamp = int(time.time() * 1000000)  # microseconds
        return f"evt_{timestamp}_{self._event_counter}"
    
    def _get_client_info(self, request: Request) -> tuple:
        """Extract client IP and user agent from request."""
        # Get client IP (handle proxy headers)
        client_ip = "unknown"
        if request.client:
            client_ip = request.client.host
        
        # Check for forwarded headers
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            client_ip = real_ip
        
        user_agent = request.headers.get("User-Agent", "unknown")
        
        return client_ip, user_agent
    
    def log_audit_event(
        self,
        event_type: AuditEventType,
        request: Request,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        status_code: Optional[int] = None,
        resource_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None
    ):
        """Log an audit event."""
        client_ip, user_agent = self._get_client_info(request)
        
        event = AuditEvent(
            event_id=self._generate_event_id(),
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type,
            user_id=user_id,
            user_email=user_email,
            ip_address=client_ip,
            user_agent=user_agent,
            endpoint=str(request.url.path),
            method=request.method,
            status_code=status_code,
            resource_id=resource_id,
            resource_type=resource_type,
            details=details or {},
            session_id=session_id,
            request_id=request_id
        )
        
        # Log to audit log
        audit_logger.info(json.dumps(asdict(event), default=str))
        
        # Also log to console in debug mode
        if self.settings.debug:
            print(f"AUDIT: {event_type} - User: {user_email} - IP: {client_ip} - Endpoint: {request.url.path}")
    
    def log_security_event(
        self,
        event_type: SecurityEventType,
        severity: str,
        request: Request,
        details: Dict[str, Any],
        user_id: Optional[str] = None,
        blocked: bool = False,
        action_taken: str = "logged"
    ):
        """Log a security event."""
        client_ip, user_agent = self._get_client_info(request)
        
        event = SecurityEvent(
            event_id=self._generate_event_id(),
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type,
            severity=severity,
            ip_address=client_ip,
            user_agent=user_agent,
            endpoint=str(request.url.path),
            method=request.method,
            details=details,
            user_id=user_id,
            blocked=blocked,
            action_taken=action_taken
        )
        
        # Log to security log
        security_logger.warning(json.dumps(asdict(event), default=str))
        
        # Also log to console
        print(f"SECURITY: {event_type} - Severity: {severity} - IP: {client_ip} - Blocked: {blocked}")
        
        # Send alert for high severity events
        if severity in ["HIGH", "CRITICAL"]:
            self._send_security_alert(event)
    
    def _send_security_alert(self, event: SecurityEvent):
        """Send security alert for high severity events."""
        # In a real implementation, this would send alerts via email, Slack, etc.
        # For now, we'll just log it prominently
        alert_message = (
            f"SECURITY ALERT: {event.event_type} detected from {event.ip_address} "
            f"at {event.timestamp}. Severity: {event.severity}. "
            f"Details: {json.dumps(event.details)}"
        )
        
        # Log to both security and audit logs
        security_logger.critical(alert_message)
        audit_logger.critical(alert_message)
        
        # Print to console for immediate visibility
        print(f"🚨 {alert_message}")
    
    def log_data_access(
        self,
        request: Request,
        user_id: str,
        user_email: str,
        data_type: str,
        operation: str,
        resource_id: Optional[str] = None,
        success: bool = True,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log data access events for privacy compliance."""
        event_details = {
            "data_type": data_type,
            "operation": operation,
            "success": success,
            **(details or {})
        }
        
        self.log_audit_event(
            event_type=AuditEventType.DATA_ACCESS,
            request=request,
            user_id=user_id,
            user_email=user_email,
            resource_id=resource_id,
            resource_type=data_type,
            details=event_details
        )
    
    def log_cv_processing(
        self,
        request: Request,
        user_id: str,
        user_email: str,
        cv_id: str,
        operation: str,
        success: bool = True,
        file_hash: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log CV processing events."""
        event_details = {
            "operation": operation,
            "success": success,
            "file_hash": file_hash,
            **(details or {})
        }
        
        event_type = AuditEventType.CV_PROCESSING
        if operation == "upload":
            event_type = AuditEventType.CV_UPLOAD
        elif operation == "deletion":
            event_type = AuditEventType.CV_DELETION
        
        self.log_audit_event(
            event_type=event_type,
            request=request,
            user_id=user_id,
            user_email=user_email,
            resource_id=cv_id,
            resource_type="cv",
            details=event_details
        )
    
    def log_search_activity(
        self,
        request: Request,
        user_id: str,
        user_email: str,
        search_query: str,
        results_count: int,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log search activity."""
        # Hash the search query for privacy
        query_hash = hashlib.sha256(search_query.encode()).hexdigest()[:16]
        
        event_details = {
            "query_hash": query_hash,
            "results_count": results_count,
            "query_length": len(search_query),
            **(details or {})
        }
        
        self.log_audit_event(
            event_type=AuditEventType.SEARCH_QUERY,
            request=request,
            user_id=user_id,
            user_email=user_email,
            details=event_details
        )
    
    def log_authentication_event(
        self,
        request: Request,
        user_email: str,
        success: bool,
        user_id: Optional[str] = None,
        failure_reason: Optional[str] = None
    ):
        """Log authentication events."""
        event_details = {
            "success": success,
            "failure_reason": failure_reason
        }
        
        if success:
            self.log_audit_event(
                event_type=AuditEventType.USER_LOGIN,
                request=request,
                user_id=user_id,
                user_email=user_email,
                details=event_details
            )
        else:
            self.log_audit_event(
                event_type=AuditEventType.AUTHENTICATION_FAILURE,
                request=request,
                user_email=user_email,
                details=event_details
            )
            
            # Log as security event for failed attempts
            self.log_security_event(
                event_type=SecurityEventType.UNAUTHORIZED_ACCESS_ATTEMPT,
                severity="MEDIUM",
                request=request,
                details=event_details
            )
    
    def log_vector_operation(
        self,
        request: Request,
        user_id: str,
        user_email: str,
        operation: str,
        vector_id: Optional[str] = None,
        success: bool = True,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log vector storage/retrieval operations."""
        event_details = {
            "operation": operation,
            "success": success,
            **(details or {})
        }
        
        event_type = AuditEventType.VECTOR_STORAGE if operation in ["store", "update"] else AuditEventType.VECTOR_RETRIEVAL
        
        self.log_audit_event(
            event_type=event_type,
            request=request,
            user_id=user_id,
            user_email=user_email,
            resource_id=vector_id,
            resource_type="vector",
            details=event_details
        )
    
    def get_audit_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get audit summary for the last N hours."""
        # In a real implementation, this would query the audit logs
        # For now, return a placeholder structure
        return {
            "period_hours": hours,
            "total_events": 0,
            "event_types": {},
            "security_events": 0,
            "failed_logins": 0,
            "data_access_events": 0,
            "top_ips": [],
            "suspicious_activity": []
        }


# Global audit service instance
audit_service = AuditService()