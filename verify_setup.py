#!/usr/bin/env python3
"""Verification script for SecureHR project setup."""

import sys
import subprocess
import importlib
from pathlib import Path


def check_python_version():
    """Check if Python version is compatible."""
    print("Checking Python version...")
    version = sys.version_info
    if version.major == 3 and version.minor >= 8:
        print(f"✓ Python {version.major}.{version.minor}.{version.micro} is compatible")
        return True
    else:
        print(f"✗ Python {version.major}.{version.minor}.{version.micro} is not compatible (requires 3.8+)")
        return False


def check_dependencies():
    """Check if all required dependencies are installed."""
    print("\nChecking dependencies...")
    required_packages = [
        'fastapi',
        'uvicorn',
        'sqlalchemy',
        'psycopg2',  # PostgreSQL driver
        'pydantic',
        'pytest',
        'hypothesis',
        'cyborgdb',
        'cyborgdb_core',
        'sentence_transformers',
        'PyPDF2',
        'docx',  # python-docx imports as 'docx'
        'httpx'
    ]
    
    all_installed = True
    for package in required_packages:
        try:
            importlib.import_module(package)
            print(f"✓ {package}")
        except ImportError:
            print(f"✗ {package} not found")
            all_installed = False
    
    return all_installed


def check_docker_services():
    """Check if Docker services are running."""
    print("\nChecking Docker services...")
    
    try:
        import subprocess
        result = subprocess.run(
            ['docker', 'ps', '--format', '{{.Names}}'],
            capture_output=True,
            text=True
        )
        running_containers = result.stdout.strip().split('\n')
        
        services = {
            'securehr-postgres': False,
            'securehr-cyborgdb': False
        }
        
        for container in running_containers:
            if container in services:
                services[container] = True
        
        all_running = True
        for service, running in services.items():
            if running:
                print(f"✓ {service} is running")
            else:
                print(f"✗ {service} is not running")
                all_running = False
        
        if not all_running:
            print("  Run 'docker-compose up -d' to start services")
        
        return all_running
        
    except Exception as e:
        print(f"✗ Could not check Docker services: {e}")
        return False


def check_postgresql_connection():
    """Check PostgreSQL connection."""
    print("\nChecking PostgreSQL connection...")
    
    try:
        import psycopg2
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="securehr",
            user="securehr",
            password="securehr_password"
        )
        conn.close()
        print("✓ PostgreSQL connection successful")
        return True
    except Exception as e:
        print(f"✗ PostgreSQL connection failed: {e}")
        return False


def check_cyborgdb_connection():
    """Check CyborgDB service connection."""
    print("\nChecking CyborgDB connection...")
    
    try:
        import httpx
        response = httpx.get("http://localhost:8100/health", timeout=5.0)
        if response.status_code == 200:
            print("✓ CyborgDB service is healthy")
            return True
        else:
            print(f"✗ CyborgDB returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ CyborgDB connection failed: {e}")
        return False


def check_project_structure():
    """Check if project structure is correct."""
    print("\nChecking project structure...")
    required_paths = [
        'backend/main.py',
        'backend/app/__init__.py',
        'backend/app/models/__init__.py',
        'backend/app/services/__init__.py',
        'backend/app/api/__init__.py',
        'backend/tests/__init__.py',
        'backend/requirements.txt',
        'backend/pyproject.toml',
        'frontend/package.json',
        'frontend/src/App.tsx',
        'frontend/src/index.tsx',
        'README.md',
        'docker-compose.yml'
    ]
    
    all_exist = True
    for path in required_paths:
        if Path(path).exists():
            print(f"✓ {path}")
        else:
            print(f"✗ {path} missing")
            all_exist = False
    
    return all_exist


def run_basic_tests():
    """Run basic tests to verify setup."""
    print("\nRunning basic tests...")
    try:
        # Test FastAPI import and basic functionality
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        
        # Import our main app
        sys.path.append('backend')
        from main import app
        
        client = TestClient(app)
        response = client.get("/")
        
        if response.status_code == 200:
            print("✓ FastAPI app is working")
            return True
        else:
            print(f"✗ FastAPI app returned status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"✗ Error testing FastAPI app: {e}")
        return False


def main():
    """Main verification function."""
    print("SecureHR Project Setup Verification")
    print("=" * 40)
    
    checks = [
        check_python_version(),
        check_dependencies(),
        check_project_structure(),
        check_docker_services(),
        check_postgresql_connection(),
        check_cyborgdb_connection(),
        run_basic_tests()
    ]
    
    print("\n" + "=" * 40)
    if all(checks):
        print("✓ All checks passed! Project setup is complete.")
        print("\nNext steps:")
        print("1. Backend: cd backend && uvicorn main:app --reload")
        print("2. Frontend: cd frontend && npm install && npm start")
        return 0
    else:
        print("✗ Some checks failed. Please review the output above.")
        print("\nQuick fix:")
        print("1. Start Docker services: docker-compose up -d")
        print("2. Install dependencies: cd backend && pip install -r requirements.txt")
        return 1


if __name__ == "__main__":
    sys.exit(main())