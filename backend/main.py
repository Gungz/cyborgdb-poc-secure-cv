# FastAPI main application entry point
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, cv, search, profile, security
from app.database import init_db
from app.config import get_settings
from app.middleware.security import (
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
    InputValidationMiddleware,
    DDoSProtectionMiddleware
)
from app.middleware.audit import AuditMiddleware, PrivacyComplianceMiddleware

settings = get_settings()

app = FastAPI(title="SecureHR API", version="1.0.0")

# Security middleware (order matters - add from innermost to outermost)
# Privacy compliance monitoring (innermost)
app.add_middleware(PrivacyComplianceMiddleware)

# Audit logging
app.add_middleware(AuditMiddleware)

# DDoS protection (outermost)
app.add_middleware(
    DDoSProtectionMiddleware,
    max_connections_per_ip=settings.max_connections_per_ip,
    suspicious_threshold=settings.ddos_suspicious_threshold,
    block_duration=settings.ddos_block_duration_seconds
)

# Rate limiting
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=settings.rate_limit_per_minute,
    requests_per_hour=settings.rate_limit_per_hour,
    burst_limit=settings.rate_limit_burst
)

# Input validation
app.add_middleware(InputValidationMiddleware)

# Security headers and HTTPS enforcement
app.add_middleware(SecurityHeadersMiddleware, enforce_https=settings.enforce_https)

# Configure CORS (more restrictive for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(cv.router)
app.include_router(search.router)
app.include_router(profile.router)
app.include_router(security.router)


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_db()


@app.get("/")
async def root():
    return {"message": "SecureHR API is running"}
