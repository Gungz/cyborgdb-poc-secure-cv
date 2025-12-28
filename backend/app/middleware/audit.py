"""Audit middleware for automatic request logging."""

import time
import json
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import StreamingResponse

from app.services.audit_service import audit_service, AuditEventType, SecurityEventType


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware for automatic audit logging of all requests."""
    
    def __init__(self, app):
        super().__init__(app)
        # Endpoints that should not be logged (health checks, etc.)
        self.excluded_paths = {"/", "/health", "/metrics", "/docs", "/openapi.json"}
        # Sensitive endpoints that require special handling
        self.sensitive_endpoints = {"/auth/login", "/auth/register", "/cv/upload"}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Skip logging for excluded paths
        if request.url.path in self.excluded_paths:
            return await call_next(request)
        
        # Extract user info from request if available
        user_id = None
        user_email = None
        session_id = None
        
        # Try to get user info from JWT token or session
        if hasattr(request.state, "user"):
            user_id = getattr(request.state.user, "id", None)
            user_email = getattr(request.state.user, "email", None)
        
        # Get session ID from headers or cookies
        session_id = request.headers.get("X-Session-ID") or request.cookies.get("session_id")
        
        # Generate request ID for tracing
        request_id = f"req_{int(time.time() * 1000000)}"
        request.state.request_id = request_id
        
        # Process the request
        response = await call_next(request)
        
        # Calculate processing time
        process_time = time.time() - start_time
        
        # Determine event type based on endpoint and method
        event_type = self._determine_event_type(request.url.path, request.method)
        
        # Prepare audit details
        details = {
            "processing_time_ms": round(process_time * 1000, 2),
            "request_size": request.headers.get("content-length", 0),
            "response_size": response.headers.get("content-length", 0) if hasattr(response, "headers") else 0
        }
        
        # Add query parameters (sanitized)
        if request.query_params:
            details["query_params"] = dict(request.query_params)
        
        # Log the audit event
        if event_type:
            audit_service.log_audit_event(
                event_type=event_type,
                request=request,
                user_id=user_id,
                user_email=user_email,
                status_code=response.status_code,
                details=details,
                session_id=session_id,
                request_id=request_id
            )
        
        # Log security events for failed requests
        if response.status_code >= 400:
            self._log_security_event_if_needed(request, response, user_id)
        
        # Add audit headers to response
        if hasattr(response, "headers"):
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Processing-Time"] = str(round(process_time * 1000, 2))
        
        return response
    
    def _determine_event_type(self, path: str, method: str) -> AuditEventType:
        """Determine audit event type based on endpoint and method."""
        # Authentication endpoints
        if "/auth/login" in path:
            return AuditEventType.USER_LOGIN
        elif "/auth/logout" in path:
            return AuditEventType.USER_LOGOUT
        elif "/auth/register" in path:
            return AuditEventType.USER_REGISTRATION
        
        # CV endpoints
        elif "/cv/upload" in path:
            return AuditEventType.CV_UPLOAD
        elif "/cv/" in path and method == "DELETE":
            return AuditEventType.CV_DELETION
        elif "/cv/" in path:
            return AuditEventType.CV_PROCESSING
        
        # Search endpoints
        elif "/search" in path:
            return AuditEventType.SEARCH_QUERY
        
        # Profile endpoints
        elif "/profile" in path:
            if method == "GET":
                return AuditEventType.PROFILE_VIEW
            elif method in ["PUT", "PATCH"]:
                return AuditEventType.PROFILE_UPDATE
            elif method == "DELETE":
                return AuditEventType.PROFILE_DELETION
        
        # Default to data access for other endpoints
        return AuditEventType.DATA_ACCESS
    
    def _log_security_event_if_needed(self, request: Request, response: Response, user_id: str):
        """Log security events for failed requests."""
        status_code = response.status_code
        
        # Authentication failures
        if status_code == 401:
            audit_service.log_security_event(
                event_type=SecurityEventType.UNAUTHORIZED_ACCESS_ATTEMPT,
                severity="MEDIUM",
                request=request,
                details={
                    "status_code": status_code,
                    "endpoint": request.url.path,
                    "user_id": user_id
                },
                user_id=user_id
            )
        
        # Authorization failures
        elif status_code == 403:
            audit_service.log_security_event(
                event_type=SecurityEventType.UNAUTHORIZED_ACCESS_ATTEMPT,
                severity="HIGH",
                request=request,
                details={
                    "status_code": status_code,
                    "endpoint": request.url.path,
                    "user_id": user_id
                },
                user_id=user_id
            )
        
        # Rate limiting
        elif status_code == 429:
            audit_service.log_security_event(
                event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
                severity="MEDIUM",
                request=request,
                details={
                    "status_code": status_code,
                    "endpoint": request.url.path
                },
                user_id=user_id,
                blocked=True,
                action_taken="request_blocked"
            )
        
        # Bad requests (potential attacks)
        elif status_code == 400:
            audit_service.log_security_event(
                event_type=SecurityEventType.MALICIOUS_INPUT_DETECTED,
                severity="LOW",
                request=request,
                details={
                    "status_code": status_code,
                    "endpoint": request.url.path
                },
                user_id=user_id
            )


class PrivacyComplianceMiddleware(BaseHTTPMiddleware):
    """Middleware for privacy compliance monitoring."""
    
    def __init__(self, app):
        super().__init__(app)
        # Endpoints that handle personal data
        self.personal_data_endpoints = {
            "/cv/upload": "cv_data",
            "/profile": "profile_data",
            "/search": "search_data"
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check if this endpoint handles personal data
        data_type = None
        for endpoint, dtype in self.personal_data_endpoints.items():
            if endpoint in request.url.path:
                data_type = dtype
                break
        
        if data_type:
            # Log data access
            user_id = getattr(request.state, "user_id", None)
            user_email = getattr(request.state, "user_email", None)
            
            if user_id and user_email:
                audit_service.log_data_access(
                    request=request,
                    user_id=user_id,
                    user_email=user_email,
                    data_type=data_type,
                    operation=request.method.lower(),
                    details={
                        "endpoint": request.url.path,
                        "timestamp": time.time()
                    }
                )
        
        response = await call_next(request)
        
        # Monitor for potential data leaks in responses
        if hasattr(response, "body") and data_type:
            self._check_response_for_data_leaks(response, data_type)
        
        return response
    
    def _check_response_for_data_leaks(self, response: Response, data_type: str):
        """Check response for potential data leaks."""
        # This is a simplified check - in production, you'd want more sophisticated detection
        if hasattr(response, "body") and response.body:
            try:
                # Check for common PII patterns in response
                body_str = response.body.decode() if isinstance(response.body, bytes) else str(response.body)
                
                # Check for email patterns
                import re
                if re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', body_str):
                    audit_service.log_security_event(
                        event_type=SecurityEventType.DATA_BREACH_ATTEMPT,
                        severity="HIGH",
                        request=None,  # We don't have request context here
                        details={
                            "data_type": data_type,
                            "potential_leak": "email_pattern_detected",
                            "response_size": len(body_str)
                        }
                    )
            except Exception:
                # Don't let privacy monitoring break the response
                pass