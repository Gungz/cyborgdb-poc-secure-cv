"""Tests for profile management functionality."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import AsyncMock, patch, MagicMock
import tempfile
import io
from datetime import datetime

from main import app
from app.database import get_db, Base
from app.models.database import UserDB, CVVectorDB
from app.models.user import UserRole, CVProcessingStatus
from app.services.auth import auth_service


# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_profile.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


class TestProfileManagement:
    """Test profile management functionality."""
    
    def setup_method(self):
        """Set up test data before each test."""
        # Clear database
        db = TestingSessionLocal()
        db.query(CVVectorDB).delete()
        db.query(UserDB).delete()
        db.commit()
        
        # Create test candidate
        self.candidate_data = {
            "id": "test-candidate-123",
            "email": "candidate@test.com",
            "password_hash": auth_service.get_password_hash("testpass123"),
            "role": UserRole.CANDIDATE,
            "first_name": "John",
            "last_name": "Doe",
            "is_active": True,
            "cv_processing_status": CVProcessingStatus.COMPLETED,
            "vector_id": "test-vector-123"
        }
        
        candidate = UserDB(**self.candidate_data)
        db.add(candidate)
        db.commit()
        
        # Create test recruiter
        self.recruiter_data = {
            "id": "test-recruiter-123",
            "email": "recruiter@test.com",
            "password_hash": auth_service.get_password_hash("testpass123"),
            "role": UserRole.RECRUITER,
            "company_name": "Test Company",
            "job_title": "HR Manager",
            "is_active": True
        }
        
        recruiter = UserDB(**self.recruiter_data)
        db.add(recruiter)
        db.commit()
        db.close()
        
        # Get authentication tokens
        self.candidate_token = self._get_auth_token("candidate@test.com", "testpass123")
        self.recruiter_token = self._get_auth_token("recruiter@test.com", "testpass123")
    
    def _get_auth_token(self, email: str, password: str) -> str:
        """Get authentication token for user."""
        response = client.post("/auth/login", json={
            "email": email,
            "password": password
        })
        assert response.status_code == 200
        return response.json()["access_token"]
    
    def test_get_candidate_profile_success(self):
        """Test successful candidate profile retrieval."""
        headers = {"Authorization": f"Bearer {self.candidate_token}"}
        
        response = client.get("/profile/me", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "candidate@test.com"
        assert data["first_name"] == "John"
        assert data["last_name"] == "Doe"
        assert data["role"] == "candidate"
        assert data["cv_processing_status"] == "completed"
    
    def test_get_candidate_profile_unauthorized(self):
        """Test candidate profile retrieval without authentication."""
        response = client.get("/profile/me")
        assert response.status_code == 403
    
    def test_get_candidate_profile_wrong_role(self):
        """Test candidate profile retrieval with recruiter token."""
        headers = {"Authorization": f"Bearer {self.recruiter_token}"}
        
        response = client.get("/profile/me", headers=headers)
        
        assert response.status_code == 403
        assert "Only candidates can access candidate profiles" in response.json()["detail"]
    
    def test_update_candidate_profile_success(self):
        """Test successful candidate profile update."""
        headers = {"Authorization": f"Bearer {self.candidate_token}"}
        update_data = {
            "first_name": "Jane",
            "last_name": "Smith"
        }
        
        response = client.put("/profile/me", headers=headers, json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Jane"
        assert data["last_name"] == "Smith"
        assert data["email"] == "candidate@test.com"  # Unchanged
    
    def test_update_candidate_profile_partial(self):
        """Test partial candidate profile update."""
        headers = {"Authorization": f"Bearer {self.candidate_token}"}
        update_data = {
            "first_name": "Jane"
            # last_name not provided
        }
        
        response = client.put("/profile/me", headers=headers, json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Jane"
        assert data["last_name"] == "Doe"  # Unchanged
    
    def test_update_candidate_profile_wrong_role(self):
        """Test candidate profile update with recruiter token."""
        headers = {"Authorization": f"Bearer {self.recruiter_token}"}
        update_data = {"first_name": "Jane"}
        
        response = client.put("/profile/me", headers=headers, json=update_data)
        
        assert response.status_code == 403
        assert "Only candidates can update candidate profiles" in response.json()["detail"]
    
    @patch('app.services.upload_queue.upload_queue_manager.is_user_processing')
    @patch('app.services.upload_queue.upload_queue_manager.queue_upload')
    def test_replace_cv_success(self, mock_queue_upload, mock_is_processing):
        """Test successful CV replacement."""
        mock_is_processing.return_value = False
        mock_queue_upload.return_value = "test-task-123"
        
        headers = {"Authorization": f"Bearer {self.candidate_token}"}
        
        # Create a test file
        test_file_content = b"Test CV content for replacement"
        files = {"file": ("test_cv.pdf", io.BytesIO(test_file_content), "application/pdf")}
        
        response = client.post("/profile/cv/replace", headers=headers, files=files)
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "CV replacement queued for processing"
        assert data["processing_status"] == "pending"
        assert data["task_id"] == "test-task-123"
        
        # Verify queue_upload was called
        mock_queue_upload.assert_called_once()
    
    @patch('app.services.upload_queue.upload_queue_manager.is_user_processing')
    def test_replace_cv_concurrent_upload(self, mock_is_processing):
        """Test CV replacement with concurrent upload."""
        mock_is_processing.return_value = True
        
        headers = {"Authorization": f"Bearer {self.candidate_token}"}
        
        # Create a test file
        test_file_content = b"Test CV content"
        files = {"file": ("test_cv.pdf", io.BytesIO(test_file_content), "application/pdf")}
        
        response = client.post("/profile/cv/replace", headers=headers, files=files)
        
        assert response.status_code == 409
        assert "Another CV upload is currently being processed" in response.json()["detail"]
    
    def test_replace_cv_wrong_role(self):
        """Test CV replacement with recruiter token."""
        headers = {"Authorization": f"Bearer {self.recruiter_token}"}
        
        test_file_content = b"Test CV content"
        files = {"file": ("test_cv.pdf", io.BytesIO(test_file_content), "application/pdf")}
        
        response = client.post("/profile/cv/replace", headers=headers, files=files)
        
        assert response.status_code == 403
        assert "Only candidates can replace CVs" in response.json()["detail"]
    
    @patch('app.services.cyborgdb_service.CyborgDBService.delete_vector')
    def test_delete_candidate_profile_success(self, mock_delete_vector):
        """Test successful candidate profile deletion."""
        mock_delete_vector.return_value = True
        
        headers = {"Authorization": f"Bearer {self.candidate_token}"}
        
        response = client.delete("/profile/me", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Profile and all associated data successfully deleted"
        assert "deleted_at" in data
        
        # Verify user was deleted from database
        db = TestingSessionLocal()
        user = db.query(UserDB).filter(UserDB.id == "test-candidate-123").first()
        assert user is None
        db.close()
    
    def test_delete_candidate_profile_wrong_role(self):
        """Test candidate profile deletion with recruiter token."""
        headers = {"Authorization": f"Bearer {self.recruiter_token}"}
        
        response = client.delete("/profile/me", headers=headers)
        
        assert response.status_code == 403
        assert "Only candidates can delete candidate profiles" in response.json()["detail"]
    
    def test_get_notifications_success(self):
        """Test getting user notifications."""
        headers = {"Authorization": f"Bearer {self.candidate_token}"}
        
        response = client.get("/profile/notifications", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_get_notifications_with_filters(self):
        """Test getting user notifications with filters."""
        headers = {"Authorization": f"Bearer {self.candidate_token}"}
        
        response = client.get("/profile/notifications?unread_only=true&limit=5", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_get_upload_status_success(self):
        """Test getting upload status."""
        headers = {"Authorization": f"Bearer {self.candidate_token}"}
        
        response = client.get("/profile/uploads", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_get_upload_status_wrong_role(self):
        """Test getting upload status with recruiter token."""
        headers = {"Authorization": f"Bearer {self.recruiter_token}"}
        
        response = client.get("/profile/uploads", headers=headers)
        
        assert response.status_code == 403
        assert "Only candidates can view upload status" in response.json()["detail"]
    
    @patch('app.services.upload_queue.upload_queue_manager.get_upload_status')
    def test_get_specific_upload_status_success(self, mock_get_status):
        """Test getting specific upload status."""
        from app.services.upload_queue import UploadTask, UploadStatus
        
        mock_task = UploadTask(
            task_id="test-task-123",
            candidate_id="test-candidate-123",
            filename="test.pdf",
            status=UploadStatus.COMPLETED,
            created_at=datetime.utcnow()
        )
        mock_get_status.return_value = mock_task
        
        headers = {"Authorization": f"Bearer {self.candidate_token}"}
        
        response = client.get("/profile/uploads/test-task-123", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "test-task-123"
        assert data["status"] == "completed"
        assert data["filename"] == "test.pdf"
    
    @patch('app.services.upload_queue.upload_queue_manager.get_upload_status')
    def test_get_specific_upload_status_not_found(self, mock_get_status):
        """Test getting specific upload status for non-existent task."""
        mock_get_status.return_value = None
        
        headers = {"Authorization": f"Bearer {self.candidate_token}"}
        
        response = client.get("/profile/uploads/nonexistent-task", headers=headers)
        
        assert response.status_code == 404
        assert "Upload task not found" in response.json()["detail"]
    
    def teardown_method(self):
        """Clean up after each test."""
        # Clear database
        db = TestingSessionLocal()
        db.query(CVVectorDB).delete()
        db.query(UserDB).delete()
        db.commit()
        db.close()