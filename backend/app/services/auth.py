"""Authentication service for SecureHR application."""

from datetime import datetime, timedelta
from typing import Optional, Union
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.config import settings
from app.models.database import UserDB
from app.models.user import UserRole, Candidate, Recruiter


class AuthenticationService:
    """Service for handling user authentication and JWT tokens."""
    
    def __init__(self):
        """Initialize authentication service with password context."""
        # Use pbkdf2_sha256 instead of bcrypt to avoid compatibility issues
        self.pwd_context = CryptContext(
            schemes=["pbkdf2_sha256"], 
            deprecated="auto"
        )
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify a plain password against its hash.
        
        Args:
            plain_password: The plain text password
            hashed_password: The hashed password from database
            
        Returns:
            bool: True if password matches, False otherwise
        """
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """
        Hash a plain password.
        
        Args:
            password: The plain text password
            
        Returns:
            str: The hashed password
        """
        return self.pwd_context.hash(password)
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """
        Create a JWT access token.
        
        Args:
            data: The data to encode in the token
            expires_delta: Optional expiration time delta
            
        Returns:
            str: The encoded JWT token
        """
        to_encode = data.copy()
        now = datetime.utcnow()
        if expires_delta:
            expire = now + expires_delta
        else:
            expire = now + timedelta(minutes=settings.access_token_expire_minutes)
        
        # Add issued at timestamp with microseconds to ensure token uniqueness
        to_encode.update({
            "exp": expire,
            "iat": now.timestamp()  # Use timestamp with microseconds for uniqueness
        })
        encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Optional[dict]:
        """
        Verify and decode a JWT token.
        
        Args:
            token: The JWT token to verify
            
        Returns:
            dict: The decoded token payload if valid, None otherwise
        """
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
            return payload
        except JWTError:
            return None
    
    def authenticate_user(self, db: Session, email: str, password: str) -> Optional[UserDB]:
        """
        Authenticate a user with email and password.
        
        Args:
            db: Database session
            email: User email
            password: Plain text password
            
        Returns:
            UserDB: The authenticated user if valid, None otherwise
        """
        user = db.query(UserDB).filter(UserDB.email == email).first()
        if not user:
            return None
        if not self.verify_password(password, user.password_hash):
            return None
        return user
    
    def get_user_by_id(self, db: Session, user_id: str) -> Optional[UserDB]:
        """
        Get a user by their ID.
        
        Args:
            db: Database session
            user_id: The user ID
            
        Returns:
            UserDB: The user if found, None otherwise
        """
        return db.query(UserDB).filter(UserDB.id == user_id).first()
    
    def update_last_login(self, db: Session, user: UserDB) -> None:
        """
        Update the user's last login timestamp.
        
        Args:
            db: Database session
            user: The user to update
        """
        user.last_login_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
    
    def convert_db_user_to_pydantic(self, db_user: UserDB) -> Union[Candidate, Recruiter]:
        """
        Convert a database user model to a Pydantic user model.
        
        Args:
            db_user: The database user model
            
        Returns:
            Union[Candidate, Recruiter]: The appropriate Pydantic user model
        """
        base_data = {
            "id": db_user.id,
            "email": db_user.email,
            "password_hash": db_user.password_hash,
            "created_at": db_user.created_at,
            "last_login_at": db_user.last_login_at,
            "is_active": db_user.is_active,
        }
        
        if db_user.role == UserRole.CANDIDATE:
            return Candidate(
                **base_data,
                first_name=db_user.first_name,
                last_name=db_user.last_name,
                cv_uploaded_at=db_user.cv_uploaded_at,
                cv_processing_status=db_user.cv_processing_status,
                vector_id=db_user.vector_id,
            )
        else:  # UserRole.RECRUITER
            return Recruiter(
                **base_data,
                company_name=db_user.company_name,
                job_title=db_user.job_title,
            )


# Global authentication service instance
auth_service = AuthenticationService()