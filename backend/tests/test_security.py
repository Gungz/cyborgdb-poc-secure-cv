"""Tests for security middleware and audit logging."""

import pytest
import json
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from main import app
from app.services.audit_service import audit_service, AuditEventType
from app.services.monitoring_service import security_monitor


client = TestClient(app)


class TestSecurityMiddleware:
    """Test security middleware functionality."""
    
    def test_security_headers_added(self):
        """Test that security headers are added to responses."""
        response = client.get("/")
        
        # Check for security headers
        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert "X-XSS-Protection" in response.headers
        assert "Content-Security-Policy" in response.headers
        assert "Strict-Transport-Security" in response.headers
    
    def test_malicious_query_parameter_blocked(self):
        """Test that malicious query parameters are blocked."""
        # Test SQL injection attempt
        response = client.get("/?search='; DROP TABLE users; --")
        assert response.status_code == 400
        assert "Invalid query parameter" in response.json()["detail"]
        
        # Test XSS attempt
        response = client.get("/?name=<script>alert('xss')</script>")
        assert response.status_code == 400
    
    def test_path_traversal_blocked(self):
        """Test that path traversal attempts are blocked."""
        response = client.get("/../../../etc/passwd")
        assert response.status_code == 400
        assert "Invalid request path" in response.json()["detail"]
    
    def test_rate_limiting_headers(self):
        """Test that rate limiting headers are present."""
        response = client.get("/")
        
        # Check for rate limiting headers
        assert "X-RateLimit-Limit-Minute" in response.headers
        assert "X-RateLimit-Remaining-Minute" in response.headers
        assert "X-RateLimit-Limit-Hour" in response.headers
        assert "X-RateLimit-Remaining-Hour" in response.headers


class TestAuditService:
    """Test audit logging functionality."""
    
    @patch('app.services.audit_service.audit_logger')
    def test_audit_event_logging(self, mock_logger):
        """Test that audit events are logged correctly."""
        # Create a mock request
        mock_request = MagicMock()
        mock_request.url.path = "/test"
        mock_request.method = "GET"
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {"User-Agent": "test-agent"}
        
        # Log an audit event
        audit_service.log_audit_event(
            event_type=AuditEventType.DATA_ACCESS,
            request=mock_request,
            user_id="test-user",
            user_email="test@example.com",
            details={"test": "data"}
        )
        
        # Verify the logger was called
        mock_logger.info.assert_called_once()
        
        # Check the logged data structure
        logged_data = mock_logger.info.call_args[0][0]
        event_data = json.loads(logged_data)
        
        assert event_data["event_type"] == "data_access"
        assert event_data["user_id"] == "test-user"
        assert event_data["user_email"] == "test@example.com"
        assert event_data["ip_address"] == "127.0.0.1"
        assert event_data["endpoint"] == "/test"
        assert event_data["method"] == "GET"
        assert event_data["details"]["test"] == "data"
    
    def test_cv_processing_logging(self):
        """Test CV processing event logging."""
        mock_request = MagicMock()
        mock_request.url.path = "/cv/upload"
        mock_request.method = "POST"
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {"User-Agent": "test-agent"}
        
        with patch('app.services.audit_service.audit_logger') as mock_logger:
            audit_service.log_cv_processing(
                request=mock_request,
                user_id="test-user",
                user_email="test@example.com",
                cv_id="cv-123",
                operation="upload",
                success=True,
                file_hash="abc123"
            )
            
            mock_logger.info.assert_called_once()
            logged_data = json.loads(mock_logger.info.call_args[0][0])
            assert logged_data["event_type"] == "cv_upload"
            assert logged_data["resource_id"] == "cv-123"
            assert logged_data["details"]["file_hash"] == "abc123"
    
    def test_search_activity_logging(self):
        """Test search activity logging."""
        mock_request = MagicMock()
        mock_request.url.path = "/search"
        mock_request.method = "POST"
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {"User-Agent": "test-agent"}
        
        with patch('app.services.audit_service.audit_logger') as mock_logger:
            audit_service.log_search_activity(
                request=mock_request,
                user_id="test-user",
                user_email="test@example.com",
                search_query="python developer",
                results_count=5
            )
            
            mock_logger.info.assert_called_once()
            logged_data = json.loads(mock_logger.info.call_args[0][0])
            assert logged_data["event_type"] == "search_query"
            assert logged_data["details"]["results_count"] == 5
            assert "query_hash" in logged_data["details"]


class TestSecurityMonitoring:
    """Test security monitoring functionality."""
    
    def test_security_event_recording(self):
        """Test that security events are recorded correctly."""
        # Clear previous events
        security_monitor.event_history.clear()
        security_monitor.ip_activity.clear()
        
        # Record a security event
        security_monitor.record_event(
            event_type="authentication_failure",
            ip_address="192.168.1.100",
            user_id="test-user",
            user_agent="test-agent",
            endpoint="/auth/login",
            details={"reason": "invalid_password"}
        )
        
        # Check that event was recorded
        assert len(security_monitor.event_history) == 1
        assert len(security_monitor.ip_activity["192.168.1.100"]) == 1
        
        event = security_monitor.event_history[0]
        assert event["event_type"] == "authentication_failure"
        assert event["ip_address"] == "192.168.1.100"
        assert event["user_id"] == "test-user"
    
    def test_brute_force_detection(self):
        """Test brute force attack detection."""
        # Clear previous events and alerts
        security_monitor.event_history.clear()
        security_monitor.ip_activity.clear()
        security_monitor.alerts.clear()
        
        # Simulate multiple failed login attempts
        for i in range(12):  # Exceed threshold of 10
            security_monitor.record_event(
                event_type="authentication_failure",
                ip_address="192.168.1.100",
                user_agent="test-agent",
                endpoint="/auth/login"
            )
        
        # Check that IP was blocked and alert was created
        assert "192.168.1.100" in security_monitor.blocked_ips
        assert len(security_monitor.alerts) > 0
        
        # Check alert details
        brute_force_alerts = [
            alert for alert in security_monitor.alerts
            if alert.alert_type == "brute_force_attack_ip"
        ]
        assert len(brute_force_alerts) > 0
        assert brute_force_alerts[0].level == "CRITICAL"
    
    def test_security_dashboard(self):
        """Test security dashboard data."""
        dashboard = security_monitor.get_security_dashboard()
        
        # Check dashboard structure
        assert "timestamp" in dashboard
        assert "alerts" in dashboard
        assert "activity" in dashboard
        assert "top_event_types" in dashboard
        
        # Check alerts section
        assert "total" in dashboard["alerts"]
        assert "unresolved" in dashboard["alerts"]
        assert "critical" in dashboard["alerts"]
        assert "high" in dashboard["alerts"]
        
        # Check activity section
        assert "events_last_hour" in dashboard["activity"]
        assert "events_last_day" in dashboard["activity"]
        assert "unique_ips_last_hour" in dashboard["activity"]


class TestSecurityEndpoints:
    """Test security API endpoints."""
    
    def test_security_health_endpoint(self):
        """Test security health check endpoint."""
        response = client.get("/security/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "monitoring_active" in data
    
    @patch('app.api.security.get_current_user')
    def test_security_dashboard_endpoint(self, mock_get_user):
        """Test security dashboard endpoint."""
        # Mock authenticated user
        mock_user = MagicMock()
        mock_user.id = "test-user"
        mock_get_user.return_value = mock_user
        
        response = client.get("/security/dashboard")
        assert response.status_code == 200
        
        data = response.json()
        assert "alerts" in data
        assert "activity" in data
    
    @patch('app.api.security.get_current_user')
    def test_blocked_ips_endpoint(self, mock_get_user):
        """Test blocked IPs endpoint."""
        # Mock authenticated user
        mock_user = MagicMock()
        mock_user.id = "test-user"
        mock_get_user.return_value = mock_user
        
        response = client.get("/security/blocked-ips")
        assert response.status_code == 200
        
        data = response.json()
        assert "blocked_ips" in data
        assert "suspicious_ips" in data
        assert "count" in data


if __name__ == "__main__":
    pytest.main([__file__])