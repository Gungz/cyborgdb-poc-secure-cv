#!/usr/bin/env python3
"""Development helper script for SecureHR project."""

import subprocess
import sys
import os
import argparse
from pathlib import Path


def run_command(command, cwd=None, description=None):
    """Run a shell command and handle errors."""
    if description:
        print(f"Running: {description}")
    
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            check=True, 
            cwd=cwd,
            capture_output=False
        )
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"Error: Command failed with exit code {e.returncode}")
        return False


def start_backend():
    """Start the FastAPI backend server."""
    print("Starting FastAPI backend server...")
    backend_dir = Path("backend")
    
    if not backend_dir.exists():
        print("Error: backend directory not found")
        return False
    
    # Activate virtual environment and start server
    command = "source venv/bin/activate && uvicorn main:app --reload --host 0.0.0.0 --port 8000"
    return run_command(command, cwd=backend_dir, description="Starting backend server")


def start_frontend():
    """Start the React frontend server."""
    print("Starting React frontend server...")
    frontend_dir = Path("frontend")
    
    if not frontend_dir.exists():
        print("Error: frontend directory not found")
        return False
    
    # Check if node_modules exists
    if not (frontend_dir / "node_modules").exists():
        print("Installing frontend dependencies...")
        if not run_command("npm install", cwd=frontend_dir):
            return False
    
    return run_command("npm start", cwd=frontend_dir, description="Starting frontend server")


def run_tests():
    """Run all tests."""
    print("Running backend tests...")
    backend_dir = Path("backend")
    
    command = "source venv/bin/activate && python -m pytest tests/ -v"
    return run_command(command, cwd=backend_dir, description="Running tests")


def lint_code():
    """Run linting and formatting tools."""
    print("Running code formatting and linting...")
    backend_dir = Path("backend")
    
    commands = [
        ("source venv/bin/activate && black .", "Formatting with black"),
        ("source venv/bin/activate && isort .", "Sorting imports with isort"),
        ("source venv/bin/activate && flake8 .", "Linting with flake8"),
    ]
    
    for command, description in commands:
        if not run_command(command, cwd=backend_dir, description=description):
            return False
    
    return True


def setup_project():
    """Set up the project for development."""
    print("Setting up SecureHR project for development...")
    
    # Backend setup
    backend_dir = Path("backend")
    if backend_dir.exists():
        print("Setting up backend...")
        commands = [
            ("python -m venv venv", "Creating virtual environment"),
            ("source venv/bin/activate && pip install -r requirements.txt", "Installing dependencies"),
            ("source venv/bin/activate && pip install black isort flake8 mypy", "Installing dev tools"),
        ]
        
        for command, description in commands:
            if not run_command(command, cwd=backend_dir, description=description):
                return False
    
    # Frontend setup
    frontend_dir = Path("frontend")
    if frontend_dir.exists():
        print("Setting up frontend...")
        if not run_command("npm install", cwd=frontend_dir, description="Installing frontend dependencies"):
            return False
    
    print("✓ Project setup complete!")
    return True


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="SecureHR Development Helper")
    parser.add_argument("command", choices=[
        "setup", "backend", "frontend", "test", "lint", "verify"
    ], help="Command to run")
    
    args = parser.parse_args()
    
    if args.command == "setup":
        success = setup_project()
    elif args.command == "backend":
        success = start_backend()
    elif args.command == "frontend":
        success = start_frontend()
    elif args.command == "test":
        success = run_tests()
    elif args.command == "lint":
        success = lint_code()
    elif args.command == "verify":
        success = run_command("python verify_setup.py", description="Running setup verification")
    else:
        print(f"Unknown command: {args.command}")
        success = False
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())