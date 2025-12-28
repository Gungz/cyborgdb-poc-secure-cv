"""Application configuration settings."""

import os
from typing import List
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Load .env file from backend directory
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


class Settings:
    """Application settings."""

    # Database - PostgreSQL (shared with CyborgDB)
    database_url: str = os.getenv("DATABASE_URL", "postgresql://securehr:securehr_password@localhost:5432/securehr")

    # JWT
    secret_key: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # CyborgDB
    cyborgdb_host: str = os.getenv("CYBORGDB_HOST", "localhost")
    cyborgdb_port: int = int(os.getenv("CYBORGDB_PORT", "8100"))
    cyborgdb_api_key: str = os.getenv("CYBORGDB_API_KEY", "your-api-key")
    cyborgdb_db_type: str = os.getenv("CYBORGDB_DB_TYPE", "postgres")
    cyborgdb_connection_string: str = os.getenv("CYBORGDB_CONNECTION_STRING", "postgresql://securehr:securehr_password@localhost:5432/securehr")

    # Vector Processing
    vector_model_name: str = os.getenv("VECTOR_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
    vector_encryption_key: str = os.getenv("VECTOR_ENCRYPTION_KEY", "securehr_vector_encryption_key_2024")

    # File Upload
    max_file_size_mb: int = int(os.getenv("MAX_FILE_SIZE_MB", "10"))
    allowed_file_types: List[str] = ["pdf", "doc", "docx"]

    # Security
    enforce_https: bool = os.getenv("ENFORCE_HTTPS", "false").lower() == "true"
    allowed_origins: List[str] = os.getenv("ALLOWED_ORIGINS", "*").split(",")
    session_timeout_minutes: int = int(os.getenv("SESSION_TIMEOUT_MINUTES", "30"))
    max_login_attempts: int = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
    account_lockout_duration_minutes: int = int(os.getenv("ACCOUNT_LOCKOUT_DURATION_MINUTES", "15"))
    
    # Rate limiting
    rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    rate_limit_per_hour: int = int(os.getenv("RATE_LIMIT_PER_HOUR", "1000"))
    rate_limit_burst: int = int(os.getenv("RATE_LIMIT_BURST", "10"))
    
    # DDoS protection
    max_connections_per_ip: int = int(os.getenv("MAX_CONNECTIONS_PER_IP", "50"))
    ddos_suspicious_threshold: int = int(os.getenv("DDOS_SUSPICIOUS_THRESHOLD", "100"))
    ddos_block_duration_seconds: int = int(os.getenv("DDOS_BLOCK_DURATION_SECONDS", "300"))

    # Development
    debug: bool = os.getenv("DEBUG", "True").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
