"""Security middleware for SecureHR application."""

import time
import logging
from typing import Dict, Optional, Set
from collections import defaultdict, deque
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse
import re
import html

from app.services.monitoring_service import security_monitor

# Configure logging
logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses."""
    
    def __init__(self, app, enforce_https: bool = True):
        super().__init__(app)
        self.enforce_https = enforce_https
    
    async def dispatch(self, request: Request, call_next):
        # HTTPS enforcement
        if self.enforce_https and request.url.scheme != "https" and not self._is_local_request(request):
            # Redirect HTTP to HTTPS
            https_url = request.url.replace(scheme="https")
            return RedirectResponse(url=str(https_url), status_code=301)
        
        response = await call_next(request)
        
        # Add security headers
        self._add_security_headers(response)
        
        return response
    
    def _is_local_request(self, request: Request) -> bool:
        """Check if request is from localhost (for development)."""
        host = request.client.host if request.client else ""
        return host in ["127.0.0.1", "localhost", "::1"]
    
    def _add_security_headers(self, response: Response):
        """Add comprehensive security headers."""
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        
        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # Enable XSS protection
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Strict Transport Security (HSTS)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        
        # Content Security Policy
        csp_policy = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        response.headers["Content-Security-Policy"] = csp_policy
        
        # Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions Policy (formerly Feature Policy)
        response.headers["Permissions-Policy"] = (
            "geolocation=(), "
            "microphone=(), "
            "camera=(), "
            "payment=(), "
            "usb=(), "
            "magnetometer=(), "
            "gyroscope=(), "
            "speaker=()"
        )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware with sliding window algorithm."""
    
    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        burst_limit: int = 10,
        window_size: int = 60
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.burst_limit = burst_limit
        self.window_size = window_size
        
        # Storage for rate limiting data
        self.minute_windows: Dict[str, deque] = defaultdict(deque)
        self.hour_windows: Dict[str, deque] = defaultdict(deque)
        self.burst_counters: Dict[str, int] = defaultdict(int)
        self.last_reset: Dict[str, float] = defaultdict(float)
    
    async def dispatch(self, request: Request, call_next):
        client_ip = self._get_client_ip(request)
        current_time = time.time()
        
        # Check rate limits
        if not self._check_rate_limits(client_ip, current_time):
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            
            # Record security event
            security_monitor.record_event(
                event_type="rate_limit_exceeded",
                ip_address=client_ip,
                user_agent=request.headers.get("User-Agent", ""),
                endpoint=str(request.url.path),
                details={"requests_per_minute": len(self.minute_windows[client_ip])}
            )
            
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later.",
                headers={"Retry-After": "60"}
            )
        
        # Record the request
        self._record_request(client_ip, current_time)
        
        response = await call_next(request)
        
        # Add rate limit headers
        self._add_rate_limit_headers(response, client_ip, current_time)
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check for forwarded headers (for reverse proxy setups)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"
    
    def _check_rate_limits(self, client_ip: str, current_time: float) -> bool:
        """Check if client has exceeded rate limits."""
        # Clean old entries
        self._cleanup_old_entries(client_ip, current_time)
        
        # Check burst limit (requests in last 10 seconds)
        burst_window_start = current_time - 10
        recent_requests = sum(
            1 for timestamp in self.minute_windows[client_ip]
            if timestamp > burst_window_start
        )
        
        if recent_requests >= self.burst_limit:
            return False
        
        # Check minute limit
        if len(self.minute_windows[client_ip]) >= self.requests_per_minute:
            return False
        
        # Check hour limit
        if len(self.hour_windows[client_ip]) >= self.requests_per_hour:
            return False
        
        return True
    
    def _record_request(self, client_ip: str, current_time: float):
        """Record a request for rate limiting."""
        self.minute_windows[client_ip].append(current_time)
        self.hour_windows[client_ip].append(current_time)
    
    def _cleanup_old_entries(self, client_ip: str, current_time: float):
        """Remove old entries from rate limiting windows."""
        minute_cutoff = current_time - 60
        hour_cutoff = current_time - 3600
        
        # Clean minute window
        while (self.minute_windows[client_ip] and 
               self.minute_windows[client_ip][0] < minute_cutoff):
            self.minute_windows[client_ip].popleft()
        
        # Clean hour window
        while (self.hour_windows[client_ip] and 
               self.hour_windows[client_ip][0] < hour_cutoff):
            self.hour_windows[client_ip].popleft()
    
    def _add_rate_limit_headers(self, response: Response, client_ip: str, current_time: float):
        """Add rate limiting headers to response."""
        minute_remaining = max(0, self.requests_per_minute - len(self.minute_windows[client_ip]))
        hour_remaining = max(0, self.requests_per_hour - len(self.hour_windows[client_ip]))
        
        response.headers["X-RateLimit-Limit-Minute"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining-Minute"] = str(minute_remaining)
        response.headers["X-RateLimit-Limit-Hour"] = str(self.requests_per_hour)
        response.headers["X-RateLimit-Remaining-Hour"] = str(hour_remaining)


class InputValidationMiddleware(BaseHTTPMiddleware):
    """Middleware for input validation and sanitization."""
    
    def __init__(self, app):
        super().__init__(app)
        # Patterns for detecting potential attacks
        self.sql_injection_patterns = [
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b)",
            r"(--|#|/\*|\*/)",
            r"(\b(OR|AND)\s+\d+\s*=\s*\d+)",
            r"(\'\s*(OR|AND)\s*\'\w*\'\s*=\s*\'\w*)",
        ]
        
        self.xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",
            r"<iframe[^>]*>.*?</iframe>",
            r"<object[^>]*>.*?</object>",
            r"<embed[^>]*>.*?</embed>",
        ]
        
        self.path_traversal_patterns = [
            r"\.\./",
            r"\.\.\\",
            r"%2e%2e%2f",
            r"%2e%2e\\",
        ]
    
    async def dispatch(self, request: Request, call_next):
        # Validate request path
        if self._contains_malicious_patterns(request.url.path, self.path_traversal_patterns):
            logger.warning(f"Path traversal attempt detected: {request.url.path}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid request path"
            )
        
        # Validate query parameters
        for key, value in request.query_params.items():
            if self._is_malicious_input(value):
                logger.warning(f"Malicious query parameter detected: {key}={value}")
                
                # Record security event
                security_monitor.record_event(
                    event_type="malicious_input_detected",
                    ip_address=self._get_client_ip(request),
                    user_agent=request.headers.get("User-Agent", ""),
                    endpoint=str(request.url.path),
                    details={"parameter": key, "attack_type": "query_parameter"}
                )
                
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid query parameter"
                )
        
        # For POST/PUT requests, we'll validate the body in the endpoint handlers
        # since we need to preserve the request body for FastAPI to process
        
        response = await call_next(request)
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check for forwarded headers (for reverse proxy setups)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"
    
    def _is_malicious_input(self, input_string: str) -> bool:
        """Check if input contains malicious patterns."""
        if not isinstance(input_string, str):
            return False
        
        # Check for SQL injection
        if self._contains_malicious_patterns(input_string, self.sql_injection_patterns):
            return True
        
        # Check for XSS
        if self._contains_malicious_patterns(input_string, self.xss_patterns):
            return True
        
        # Check for path traversal
        if self._contains_malicious_patterns(input_string, self.path_traversal_patterns):
            return True
        
        return False
    
    def _contains_malicious_patterns(self, text: str, patterns: list) -> bool:
        """Check if text contains any malicious patterns."""
        text_lower = text.lower()
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return True
        return False
    
    def sanitize_input(self, input_string: str) -> str:
        """Sanitize input string by escaping HTML and removing dangerous characters."""
        if not isinstance(input_string, str):
            return input_string
        
        # HTML escape
        sanitized = html.escape(input_string)
        
        # Remove null bytes
        sanitized = sanitized.replace('\x00', '')
        
        # Remove control characters except newlines and tabs
        sanitized = ''.join(char for char in sanitized 
                          if ord(char) >= 32 or char in '\n\t')
        
        return sanitized


class DDoSProtectionMiddleware(BaseHTTPMiddleware):
    """Basic DDoS protection middleware."""
    
    def __init__(
        self,
        app,
        max_connections_per_ip: int = 50,
        suspicious_threshold: int = 100,
        block_duration: int = 300  # 5 minutes
    ):
        super().__init__(app)
        self.max_connections_per_ip = max_connections_per_ip
        self.suspicious_threshold = suspicious_threshold
        self.block_duration = block_duration
        
        # Track connections and blocked IPs
        self.active_connections: Dict[str, int] = defaultdict(int)
        self.request_counts: Dict[str, deque] = defaultdict(deque)
        self.blocked_ips: Dict[str, float] = {}
    
    async def dispatch(self, request: Request, call_next):
        client_ip = self._get_client_ip(request)
        current_time = time.time()
        
        # Check if IP is currently blocked
        if self._is_ip_blocked(client_ip, current_time):
            logger.warning(f"Blocked IP attempted access: {client_ip}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="IP temporarily blocked due to suspicious activity",
                headers={"Retry-After": str(self.block_duration)}
            )
        
        # Check connection limits
        if self.active_connections[client_ip] >= self.max_connections_per_ip:
            logger.warning(f"Connection limit exceeded for IP: {client_ip}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many concurrent connections"
            )
        
        # Track request
        self._track_request(client_ip, current_time)
        
        # Check for suspicious activity
        if self._is_suspicious_activity(client_ip, current_time):
            self._block_ip(client_ip, current_time)
            logger.warning(f"IP blocked due to suspicious activity: {client_ip}")
            
            # Record security event
            security_monitor.record_event(
                event_type="ddos_attack_detected",
                ip_address=client_ip,
                user_agent=request.headers.get("User-Agent", ""),
                endpoint=str(request.url.path),
                details={"requests_per_minute": len([
                    t for t in self.request_counts[client_ip] 
                    if t > current_time - 60
                ])}
            )
            
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="IP blocked due to suspicious activity"
            )
        
        # Increment connection count
        self.active_connections[client_ip] += 1
        
        try:
            response = await call_next(request)
            return response
        finally:
            # Decrement connection count
            self.active_connections[client_ip] = max(0, self.active_connections[client_ip] - 1)
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"
    
    def _is_ip_blocked(self, client_ip: str, current_time: float) -> bool:
        """Check if IP is currently blocked."""
        if client_ip in self.blocked_ips:
            block_time = self.blocked_ips[client_ip]
            if current_time - block_time < self.block_duration:
                return True
            else:
                # Block expired, remove from blocked list
                del self.blocked_ips[client_ip]
        return False
    
    def _track_request(self, client_ip: str, current_time: float):
        """Track request for suspicious activity detection."""
        self.request_counts[client_ip].append(current_time)
        
        # Clean old entries (keep last 5 minutes)
        cutoff_time = current_time - 300
        while (self.request_counts[client_ip] and 
               self.request_counts[client_ip][0] < cutoff_time):
            self.request_counts[client_ip].popleft()
    
    def _is_suspicious_activity(self, client_ip: str, current_time: float) -> bool:
        """Check if IP shows suspicious activity patterns."""
        # Check request rate in last minute
        minute_ago = current_time - 60
        recent_requests = sum(
            1 for timestamp in self.request_counts[client_ip]
            if timestamp > minute_ago
        )
        
        return recent_requests >= self.suspicious_threshold
    
    def _block_ip(self, client_ip: str, current_time: float):
        """Block an IP address."""
        self.blocked_ips[client_ip] = current_time
        logger.info(f"IP blocked: {client_ip} at {current_time}")