#!/usr/bin/env python3
"""Setup script for SecureHR backend development environment."""

import os
import subprocess
import sys


def run_command(command, description):
    """Run a shell command and handle errors."""
    print(f"Running: {description}")
    try:
        result = subprocess.run(
            command, shell=True, check=True, capture_output=True, text=True
        )
        print(f"✓ {description} completed successfully")
        return result
    except subprocess.CalledProcessError as e:
        print(f"✗ {description} failed: {e}")
        print(f"Error output: {e.stderr}")
        return None


def main():
    """Set up the development environment."""
    print("Setting up SecureHR backend development environment...")

    # Check if we're in a virtual environment
    if not hasattr(sys, "real_prefix") and not (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    ):
        print("Warning: Not running in a virtual environment")
        print(
            "Consider creating one with: python -m venv venv && source venv/bin/activate"
        )

    # Install dependencies
    run_command("pip install -r requirements.txt", "Installing dependencies")

    # Install development dependencies
    run_command("pip install black isort flake8 mypy", "Installing development tools")

    # Create .env file if it doesn't exist
    if not os.path.exists(".env"):
        run_command("cp .env.example .env", "Creating .env file")
        print("Please edit .env with your actual configuration values")

    print("\n✓ Setup complete!")
    print("\nNext steps:")
    print("1. Edit .env with your configuration")
    print("2. Run: uvicorn main:app --reload")
    print("3. Visit: http://localhost:8000/docs")


if __name__ == "__main__":
    main()
