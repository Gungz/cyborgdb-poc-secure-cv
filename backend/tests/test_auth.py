"""Tests for authentication service and endpoints."""

import pytest
import os
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set high rate limits for testing BEFORE importing the app
os.environ["RATE_LIMIT_PER_MINUTE"] = "10000"
os.environ["RATE_LIMIT_PER_HOUR"] = "100000"
os.environ["RATE_LIMIT_BURST"] = "1000"
os.environ["DDOS_SUSPICIOUS_THRESHOLD"] = "10000"
os.environ["MAX_CONNECTIONS_PER_IP"] = "1000"

# Clear the settings cache to pick up new values
from app.config import get_settings
get_settings.cache_clear()

from main import app
from app.database import get_db
from app.models.database import Base, UserDB
from app.models.user import UserRole, CVProcessingStatus
from app.services.auth import auth_service
from app.config import settings


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_candidate(db_session):
    """Create a sample candidate user for testing."""
    user = UserDB(
        email="candidate@example.com",
        password_hash=auth_service.get_password_hash("testpassword123"),
        role=UserRole.CANDIDATE,
        first_name="John",
        last_name="Doe",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def sample_recruiter(db_session):
    """Create a sample recruiter user for testing."""
    user = UserDB(
        email="recruiter@example.com",
        password_hash=auth_service.get_password_hash("testpassword123"),
        role=UserRole.RECRUITER,
        company_name="Test Company",
        job_title="HR Manager",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestAuthenticationService:
    """Test cases for the AuthenticationService class."""
    
    def test_password_hashing(self):
        """Test password hashing and verification."""
        password = "testpassword123"
        hashed = auth_service.get_password_hash(password)
        
        # Hash should be different from original password
        assert hashed != password
        
        # Verification should work
        assert auth_service.verify_password(password, hashed) is True
        
        # Wrong password should fail
        assert auth_service.verify_password("wrongpassword", hashed) is False
    
    def test_create_access_token(self):
        """Test JWT token creation."""
        data = {"sub": "test-user-id", "role": "candidate"}
        token = auth_service.create_access_token(data)
        
        # Token should be a string
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Should be able to verify the token
        payload = auth_service.verify_token(token)
        assert payload is not None
        assert payload["sub"] == "test-user-id"
        assert payload["role"] == "candidate"
    
    def test_create_access_token_with_expiration(self):
        """Test JWT token creation with custom expiration."""
        data = {"sub": "test-user-id"}
        expires_delta = timedelta(minutes=5)
        token = auth_service.create_access_token(data, expires_delta)
        
        payload = auth_service.verify_token(token)
        assert payload is not None
        
        # Check expiration is set correctly (within reasonable margin)
        exp_time = datetime.utcfromtimestamp(payload["exp"])
        expected_exp = datetime.utcnow() + expires_delta
        time_diff = abs((exp_time - expected_exp).total_seconds())
        assert time_diff < 5  # Within 5 seconds margin
    
    def test_verify_invalid_token(self):
        """Test verification of invalid tokens."""
        # Invalid token should return None
        assert auth_service.verify_token("invalid-token") is None
        assert auth_service.verify_token("") is None
    
    def test_authenticate_user_success(self, db_session, sample_candidate):
        """Test successful user authentication."""
        user = auth_service.authenticate_user(
            db_session, 
            "candidate@example.com", 
            "testpassword123"
        )
        
        assert user is not None
        assert user.email == "candidate@example.com"
        assert user.role == UserRole.CANDIDATE
    
    def test_authenticate_user_wrong_password(self, db_session, sample_candidate):
        """Test authentication with wrong password."""
        user = auth_service.authenticate_user(
            db_session, 
            "candidate@example.com", 
            "wrongpassword"
        )
        
        assert user is None
    
    def test_authenticate_user_nonexistent(self, db_session):
        """Test authentication with nonexistent user."""
        user = auth_service.authenticate_user(
            db_session, 
            "nonexistent@example.com", 
            "password"
        )
        
        assert user is None
    
    def test_get_user_by_id(self, db_session, sample_candidate):
        """Test getting user by ID."""
        user = auth_service.get_user_by_id(db_session, sample_candidate.id)
        
        assert user is not None
        assert user.id == sample_candidate.id
        assert user.email == sample_candidate.email
    
    def test_get_user_by_id_nonexistent(self, db_session):
        """Test getting nonexistent user by ID."""
        user = auth_service.get_user_by_id(db_session, "nonexistent-id")
        assert user is None
    
    def test_update_last_login(self, db_session, sample_candidate):
        """Test updating last login timestamp."""
        original_login = sample_candidate.last_login_at
        
        auth_service.update_last_login(db_session, sample_candidate)
        
        # Last login should be updated
        assert sample_candidate.last_login_at != original_login
        assert sample_candidate.last_login_at is not None


class TestAuthenticationEndpoints:
    """Test cases for authentication API endpoints."""
    
    def test_login_success_candidate(self, db_session, sample_candidate):
        """Test successful login for candidate."""
        response = client.post("/auth/login", json={
            "email": "candidate@example.com",
            "password": "testpassword123"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user_id"] == sample_candidate.id
        assert data["user_role"] == "candidate"
        assert data["expires_in"] == settings.access_token_expire_minutes * 60
    
    def test_login_success_recruiter(self, db_session, sample_recruiter):
        """Test successful login for recruiter."""
        response = client.post("/auth/login", json={
            "email": "recruiter@example.com",
            "password": "testpassword123"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user_id"] == sample_recruiter.id
        assert data["user_role"] == "recruiter"
    
    def test_login_wrong_password(self, db_session, sample_candidate):
        """Test login with wrong password."""
        response = client.post("/auth/login", json={
            "email": "candidate@example.com",
            "password": "wrongpassword"
        })
        
        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]
    
    def test_login_nonexistent_user(self, db_session):
        """Test login with nonexistent user."""
        response = client.post("/auth/login", json={
            "email": "nonexistent@example.com",
            "password": "password"
        })
        
        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]
    
    def test_login_inactive_user(self, db_session, sample_candidate):
        """Test login with inactive user."""
        # Make user inactive
        sample_candidate.is_active = False
        db_session.commit()
        
        response = client.post("/auth/login", json={
            "email": "candidate@example.com",
            "password": "testpassword123"
        })
        
        assert response.status_code == 401
        assert "Account is inactive" in response.json()["detail"]
    
    def test_validate_token_valid(self, db_session, sample_candidate):
        """Test token validation with valid token."""
        # First login to get a token
        login_response = client.post("/auth/login", json={
            "email": "candidate@example.com",
            "password": "testpassword123"
        })
        token = login_response.json()["access_token"]
        
        # Validate the token
        response = client.post("/auth/validate-token", json={"token": token})
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["valid"] is True
        assert data["user_id"] == sample_candidate.id
        assert data["user_role"] == "candidate"
        assert data["expires_at"] is not None
    
    def test_validate_token_invalid(self, db_session):
        """Test token validation with invalid token."""
        response = client.post("/auth/validate-token", json={"token": "invalid-token"})
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["valid"] is False
        assert data["user_id"] is None
        assert data["user_role"] is None
    
    def test_get_current_user_info_candidate(self, db_session, sample_candidate):
        """Test getting current user info for candidate."""
        # Login to get token
        login_response = client.post("/auth/login", json={
            "email": "candidate@example.com",
            "password": "testpassword123"
        })
        token = login_response.json()["access_token"]
        
        # Get user info
        response = client.get("/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == sample_candidate.id
        assert data["email"] == "candidate@example.com"
        assert data["role"] == "candidate"
        assert data["first_name"] == "John"
        assert data["last_name"] == "Doe"
        assert data["is_active"] is True
    
    def test_get_current_user_info_recruiter(self, db_session, sample_recruiter):
        """Test getting current user info for recruiter."""
        # Login to get token
        login_response = client.post("/auth/login", json={
            "email": "recruiter@example.com",
            "password": "testpassword123"
        })
        token = login_response.json()["access_token"]
        
        # Get user info
        response = client.get("/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == sample_recruiter.id
        assert data["email"] == "recruiter@example.com"
        assert data["role"] == "recruiter"
        assert data["company_name"] == "Test Company"
        assert data["job_title"] == "HR Manager"
    
    def test_get_current_user_info_unauthorized(self, db_session):
        """Test getting current user info without token."""
        response = client.get("/auth/me")
        
        assert response.status_code == 403  # No Authorization header
    
    def test_get_current_user_info_invalid_token(self, db_session):
        """Test getting current user info with invalid token."""
        response = client.get("/auth/me", headers={
            "Authorization": "Bearer invalid-token"
        })
        
        assert response.status_code == 401
    
    def test_logout_success(self, db_session, sample_candidate):
        """Test successful logout."""
        # Login to get token
        login_response = client.post("/auth/login", json={
            "email": "candidate@example.com",
            "password": "testpassword123"
        })
        token = login_response.json()["access_token"]
        
        # Logout
        response = client.post("/auth/logout", headers={
            "Authorization": f"Bearer {token}"
        })
        
        assert response.status_code == 200
        assert response.json()["message"] == "Successfully logged out"
    
    def test_logout_unauthorized(self, db_session):
        """Test logout without token."""
        response = client.post("/auth/logout")
        
        assert response.status_code == 403  # No Authorization header
    
    def test_refresh_token(self, db_session, sample_candidate):
        """Test token refresh."""
        # Login to get token
        login_response = client.post("/auth/login", json={
            "email": "candidate@example.com",
            "password": "testpassword123"
        })
        original_token = login_response.json()["access_token"]
        
        # Refresh token
        response = client.post("/auth/refresh-token", headers={
            "Authorization": f"Bearer {original_token}"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user_id"] == sample_candidate.id
        assert data["user_role"] == "candidate"
        
        # New token should be different from original
        new_token = data["access_token"]
        assert new_token != original_token



class TestRegistrationEndpoints:
    """Test cases for user registration endpoints."""
    
    def test_register_candidate_success(self, db_session):
        """Test successful candidate registration."""
        response = client.post("/auth/register/candidate", json={
            "email": "newcandidate@example.com",
            "password": "TestPass123",
            "first_name": "Jane",
            "last_name": "Smith"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user_role"] == "candidate"
        assert data["user_id"] is not None
        assert data["expires_in"] == settings.access_token_expire_minutes * 60
        
        # Verify user was created in database
        user = db_session.query(UserDB).filter(UserDB.email == "newcandidate@example.com").first()
        assert user is not None
        assert user.first_name == "Jane"
        assert user.last_name == "Smith"
        assert user.role == UserRole.CANDIDATE
        assert user.is_active is True
    
    def test_register_candidate_duplicate_email(self, db_session, sample_candidate):
        """Test candidate registration with existing email."""
        response = client.post("/auth/register/candidate", json={
            "email": "candidate@example.com",  # Already exists
            "password": "TestPass123",
            "first_name": "Jane",
            "last_name": "Smith"
        })
        
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]
    
    def test_register_candidate_weak_password(self, db_session):
        """Test candidate registration with weak password."""
        # Too short
        response = client.post("/auth/register/candidate", json={
            "email": "newcandidate@example.com",
            "password": "short",
            "first_name": "Jane",
            "last_name": "Smith"
        })
        
        assert response.status_code == 422
        assert "8 characters" in str(response.json())
    
    def test_register_candidate_password_no_uppercase(self, db_session):
        """Test candidate registration with password missing uppercase."""
        response = client.post("/auth/register/candidate", json={
            "email": "newcandidate@example.com",
            "password": "testpass123",
            "first_name": "Jane",
            "last_name": "Smith"
        })
        
        assert response.status_code == 422
        assert "uppercase" in str(response.json())
    
    def test_register_candidate_password_no_digit(self, db_session):
        """Test candidate registration with password missing digit."""
        response = client.post("/auth/register/candidate", json={
            "email": "newcandidate@example.com",
            "password": "TestPassword",
            "first_name": "Jane",
            "last_name": "Smith"
        })
        
        assert response.status_code == 422
        assert "digit" in str(response.json())
    
    def test_register_candidate_invalid_email(self, db_session):
        """Test candidate registration with invalid email."""
        response = client.post("/auth/register/candidate", json={
            "email": "not-an-email",
            "password": "TestPass123",
            "first_name": "Jane",
            "last_name": "Smith"
        })
        
        assert response.status_code == 422
    
    def test_register_candidate_empty_name(self, db_session):
        """Test candidate registration with empty name."""
        response = client.post("/auth/register/candidate", json={
            "email": "newcandidate@example.com",
            "password": "TestPass123",
            "first_name": "",
            "last_name": "Smith"
        })
        
        assert response.status_code == 422
        assert "empty" in str(response.json()).lower()
    
    def test_register_recruiter_success(self, db_session):
        """Test successful recruiter registration."""
        response = client.post("/auth/register/recruiter", json={
            "email": "newrecruiter@example.com",
            "password": "TestPass123",
            "company_name": "Tech Corp",
            "job_title": "Senior Recruiter"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user_role"] == "recruiter"
        assert data["user_id"] is not None
        assert data["expires_in"] == settings.access_token_expire_minutes * 60
        
        # Verify user was created in database
        user = db_session.query(UserDB).filter(UserDB.email == "newrecruiter@example.com").first()
        assert user is not None
        assert user.company_name == "Tech Corp"
        assert user.job_title == "Senior Recruiter"
        assert user.role == UserRole.RECRUITER
        assert user.is_active is True
    
    def test_register_recruiter_duplicate_email(self, db_session, sample_recruiter):
        """Test recruiter registration with existing email."""
        response = client.post("/auth/register/recruiter", json={
            "email": "recruiter@example.com",  # Already exists
            "password": "TestPass123",
            "company_name": "Tech Corp",
            "job_title": "Senior Recruiter"
        })
        
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]
    
    def test_register_recruiter_weak_password(self, db_session):
        """Test recruiter registration with weak password."""
        response = client.post("/auth/register/recruiter", json={
            "email": "newrecruiter@example.com",
            "password": "weak",
            "company_name": "Tech Corp",
            "job_title": "Senior Recruiter"
        })
        
        assert response.status_code == 422
        assert "8 characters" in str(response.json())
    
    def test_register_recruiter_empty_company(self, db_session):
        """Test recruiter registration with empty company name."""
        response = client.post("/auth/register/recruiter", json={
            "email": "newrecruiter@example.com",
            "password": "TestPass123",
            "company_name": "",
            "job_title": "Senior Recruiter"
        })
        
        assert response.status_code == 422
        assert "empty" in str(response.json()).lower()
    
    def test_register_recruiter_empty_job_title(self, db_session):
        """Test recruiter registration with empty job title."""
        response = client.post("/auth/register/recruiter", json={
            "email": "newrecruiter@example.com",
            "password": "TestPass123",
            "company_name": "Tech Corp",
            "job_title": ""
        })
        
        assert response.status_code == 422
        assert "empty" in str(response.json()).lower()
    
    def test_register_candidate_can_login(self, db_session):
        """Test that a registered candidate can login."""
        # Register
        register_response = client.post("/auth/register/candidate", json={
            "email": "logintest@example.com",
            "password": "TestPass123",
            "first_name": "Login",
            "last_name": "Test"
        })
        assert register_response.status_code == 200
        
        # Login with same credentials
        login_response = client.post("/auth/login", json={
            "email": "logintest@example.com",
            "password": "TestPass123"
        })
        
        assert login_response.status_code == 200
        data = login_response.json()
        assert "access_token" in data
        assert data["user_role"] == "candidate"
    
    def test_register_recruiter_can_login(self, db_session):
        """Test that a registered recruiter can login."""
        # Register
        register_response = client.post("/auth/register/recruiter", json={
            "email": "recruiterlogin@example.com",
            "password": "TestPass123",
            "company_name": "Test Corp",
            "job_title": "HR Manager"
        })
        assert register_response.status_code == 200
        
        # Login with same credentials
        login_response = client.post("/auth/login", json={
            "email": "recruiterlogin@example.com",
            "password": "TestPass123"
        })
        
        assert login_response.status_code == 200
        data = login_response.json()
        assert "access_token" in data
        assert data["user_role"] == "recruiter"
