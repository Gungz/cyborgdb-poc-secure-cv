"""Basic tests for the main application."""

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_root_endpoint():
    """Test the root endpoint returns expected response."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "SecureHR API is running"}


def test_app_title():
    """Test that the app has the correct title."""
    assert app.title == "SecureHR API"
    assert app.version == "1.0.0"
