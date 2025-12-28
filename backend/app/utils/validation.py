"""Input validation utilities for SecureHR application."""

import re
import html
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
import logging

logger = logging.getLogger(__name__)


class InputValidator:
    """Comprehensive input validation and sanitization utilities."""
    
    # Security patterns
    SQL_INJECTION_PATTERNS = [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b)",
        r"(--|#|/\*|\*/)",
        r"(\b(OR|AND)\s+\d+\s*=\s*\d+)",
        r"(\'\s*(OR|AND)\s*\'\w*\'\s*=\s*\'\w*)",
        r"(\bEXEC\s*\()",
        r"(\bSP_\w+)",
    ]
    
    XSS_PATTERNS = [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"on\w+\s*=",
        r"<iframe[^>]*>.*?</iframe>",
        r"<object[^>]*>.*?</object>",
        r"<embed[^>]*>.*?</embed>",
        r"<link[^>]*>",
        r"<meta[^>]*>",
        r"vbscript:",
        r"data:text/html",
    ]
    
    PATH_TRAVERSAL_PATTERNS = [
        r"\.\./",
        r"\.\.\\",
        r"%2e%2e%2f",
        r"%2e%2e\\",
        r"\.\.%2f",
        r"\.\.%5c",
    ]
    
    # File validation
    ALLOWED_FILE_EXTENSIONS = {'.pdf', '.doc', '.docx'}
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    # Text validation
    MAX_TEXT_LENGTH = 10000
    MAX_EMAIL_LENGTH = 254
    MAX_NAME_LENGTH = 100
    MAX_COMPANY_LENGTH = 200
    
    @classmethod
    def validate_email(cls, email: str) -> str:
        """Validate and sanitize email address."""
        if not email or not isinstance(email, str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is required"
            )
        
        email = email.strip().lower()
        
        if len(email) > cls.MAX_EMAIL_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address too long"
            )
        
        # Basic email regex
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email format"
            )
        
        # Check for malicious patterns
        if cls._contains_malicious_patterns(email, cls.SQL_INJECTION_PATTERNS + cls.XSS_PATTERNS):
            logger.warning(f"Malicious email detected: {email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email format"
            )
        
        return email
    
    @classmethod
    def validate_password(cls, password: str) -> str:
        """Validate password strength."""
        if not password or not isinstance(password, str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password is required"
            )
        
        if len(password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long"
            )
        
        if len(password) > 128:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password too long"
            )
        
        # Check for at least one uppercase, lowercase, digit, and special character
        if not re.search(r'[A-Z]', password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must contain at least one uppercase letter"
            )
        
        if not re.search(r'[a-z]', password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must contain at least one lowercase letter"
            )
        
        if not re.search(r'\d', password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must contain at least one digit"
            )
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must contain at least one special character"
            )
        
        return password
    
    @classmethod
    def validate_name(cls, name: str, field_name: str = "Name") -> str:
        """Validate and sanitize name fields."""
        if not name or not isinstance(name, str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} is required"
            )
        
        name = name.strip()
        
        if len(name) > cls.MAX_NAME_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} too long"
            )
        
        # Allow only letters, spaces, hyphens, and apostrophes
        if not re.match(r"^[a-zA-Z\s\-']+$", name):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} contains invalid characters"
            )
        
        # Check for malicious patterns
        if cls._contains_malicious_patterns(name, cls.SQL_INJECTION_PATTERNS + cls.XSS_PATTERNS):
            logger.warning(f"Malicious {field_name.lower()} detected: {name}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid {field_name.lower()} format"
            )
        
        return cls.sanitize_text(name)
    
    @classmethod
    def validate_company_name(cls, company_name: str) -> str:
        """Validate and sanitize company name."""
        if not company_name or not isinstance(company_name, str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Company name is required"
            )
        
        company_name = company_name.strip()
        
        if len(company_name) > cls.MAX_COMPANY_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Company name too long"
            )
        
        # Allow letters, numbers, spaces, and common business characters
        if not re.match(r"^[a-zA-Z0-9\s\-'&.,()]+$", company_name):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Company name contains invalid characters"
            )
        
        # Check for malicious patterns
        if cls._contains_malicious_patterns(company_name, cls.SQL_INJECTION_PATTERNS + cls.XSS_PATTERNS):
            logger.warning(f"Malicious company name detected: {company_name}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid company name format"
            )
        
        return cls.sanitize_text(company_name)
    
    @classmethod
    def validate_text_content(cls, text: str, field_name: str = "Text", max_length: Optional[int] = None) -> str:
        """Validate and sanitize general text content."""
        if not text or not isinstance(text, str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} is required"
            )
        
        text = text.strip()
        max_len = max_length or cls.MAX_TEXT_LENGTH
        
        if len(text) > max_len:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} too long (max {max_len} characters)"
            )
        
        # Check for malicious patterns
        if cls._contains_malicious_patterns(text, cls.SQL_INJECTION_PATTERNS + cls.XSS_PATTERNS):
            logger.warning(f"Malicious {field_name.lower()} detected")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid {field_name.lower()} content"
            )
        
        return cls.sanitize_text(text)
    
    @classmethod
    def validate_file_upload(cls, filename: str, file_size: int) -> str:
        """Validate file upload parameters."""
        if not filename or not isinstance(filename, str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename is required"
            )
        
        # Sanitize filename
        filename = cls.sanitize_filename(filename)
        
        # Check file extension
        file_ext = '.' + filename.lower().split('.')[-1] if '.' in filename else ''
        if file_ext not in cls.ALLOWED_FILE_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type not allowed. Allowed types: {', '.join(cls.ALLOWED_FILE_EXTENSIONS)}"
            )
        
        # Check file size
        if file_size > cls.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large. Maximum size: {cls.MAX_FILE_SIZE // (1024*1024)}MB"
            )
        
        return filename
    
    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """Sanitize filename to prevent path traversal and other attacks."""
        if not filename:
            return filename
        
        # Remove path components
        filename = filename.split('/')[-1].split('\\')[-1]
        
        # Remove dangerous characters
        filename = re.sub(r'[<>:"|?*\x00-\x1f]', '', filename)
        
        # Check for path traversal
        if cls._contains_malicious_patterns(filename, cls.PATH_TRAVERSAL_PATTERNS):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid filename"
            )
        
        # Ensure filename is not empty after sanitization
        if not filename.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid filename"
            )
        
        return filename.strip()
    
    @classmethod
    def sanitize_text(cls, text: str) -> str:
        """Sanitize text input by escaping HTML and removing dangerous characters."""
        if not isinstance(text, str):
            return text
        
        # HTML escape
        sanitized = html.escape(text)
        
        # Remove null bytes
        sanitized = sanitized.replace('\x00', '')
        
        # Remove control characters except newlines, tabs, and carriage returns
        sanitized = ''.join(char for char in sanitized 
                          if ord(char) >= 32 or char in '\n\t\r')
        
        return sanitized
    
    @classmethod
    def validate_search_query(cls, query: str) -> str:
        """Validate search query parameters."""
        if not query or not isinstance(query, str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Search query is required"
            )
        
        query = query.strip()
        
        if len(query) > cls.MAX_TEXT_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Search query too long"
            )
        
        # Check for malicious patterns
        if cls._contains_malicious_patterns(query, cls.SQL_INJECTION_PATTERNS):
            logger.warning("Malicious search query detected")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid search query"
            )
        
        return cls.sanitize_text(query)
    
    @classmethod
    def _contains_malicious_patterns(cls, text: str, patterns: List[str]) -> bool:
        """Check if text contains any malicious patterns."""
        if not isinstance(text, str):
            return False
        
        text_lower = text.lower()
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return True
        return False
    
    @classmethod
    def validate_pagination_params(cls, skip: int = 0, limit: int = 10) -> tuple:
        """Validate pagination parameters."""
        if skip < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Skip parameter must be non-negative"
            )
        
        if limit < 1 or limit > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Limit parameter must be between 1 and 100"
            )
        
        return skip, limit