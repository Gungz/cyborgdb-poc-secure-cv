#!/usr/bin/env python3
"""
Script to seed the database with test candidates and their CVs.
Simulates the registration and CV upload API flow.
If user already exists, it will still process and upload their CV.
"""

import asyncio
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from sqlalchemy.orm import Session
from app.database import get_db, engine
from app.models.database import Base, UserDB
from app.models.user import UserRole, CVProcessingStatus
from app.services.cv_processor import CVProcessorService
from app.services.auth import auth_service
from fastapi import UploadFile
import uuid
import io


# Test CV folder path (relative to project root, one level up from backend/)
CV_FOLDER = str(Path(__file__).parent.parent / "test_cvs")

# Common password for all test users
PASSWORD = "secureHRPa55$$"

# Candidate data extracted from CV files
CANDIDATES = [
    {
        "cv_file": "01_software_engineer.pdf",
        "first_name": "Alex",
        "last_name": "Chen",
        "email": "alex.chen@email.com"
    },
    {
        "cv_file": "02_data_scientist.pdf",
        "first_name": "Sarah",
        "last_name": "Johnson",
        "email": "sarah.johnson@email.com"
    },
    {
        "cv_file": "03_product_manager.pdf",
        "first_name": "Michael",
        "last_name": "Rodriguez",
        "email": "michael.rodriguez@email.com"
    },
    {
        "cv_file": "04_ux_designer.pdf",
        "first_name": "Emily",
        "last_name": "Park",
        "email": "emily.park@email.com"
    },
    {
        "cv_file": "05_devops_engineer.pdf",
        "first_name": "James",
        "last_name": "Wilson",
        "email": "james.wilson@email.com"
    },
    {
        "cv_file": "06_marketing_manager.pdf",
        "first_name": "Jennifer",
        "last_name": "Martinez",
        "email": "jennifer.martinez@email.com"
    },
    {
        "cv_file": "07_financial_analyst.pdf",
        "first_name": "David",
        "last_name": "Kim",
        "email": "david.kim@email.com"
    },
    {
        "cv_file": "08_hr_manager.pdf",
        "first_name": "Amanda",
        "last_name": "Thompson",
        "email": "amanda.thompson@email.com"
    },
    {
        "cv_file": "09_sales_executive.pdf",
        "first_name": "Robert",
        "last_name": "Anderson",
        "email": "robert.anderson@email.com"
    },
    {
        "cv_file": "10_project_manager.pdf",
        "first_name": "Lisa",
        "last_name": "Chen",
        "email": "lisa.chen@email.com"
    },
]


class MockUploadFile:
    """Mock UploadFile class to simulate FastAPI file upload."""
    
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.content_type = "application/pdf"
        self.size = os.path.getsize(filepath)
        self._file = None
    
    async def read(self) -> bytes:
        with open(self.filepath, "rb") as f:
            return f.read()
    
    async def seek(self, position: int):
        pass
    
    def __enter__(self):
        self._file = open(self.filepath, "rb")
        return self
    
    def __exit__(self, *args):
        if self._file:
            self._file.close()


async def create_or_get_user(db: Session, candidate_data: dict) -> tuple[UserDB, bool]:
    """
    Get existing user or create a new one.
    Returns (user, is_new) tuple.
    """
    existing_user = db.query(UserDB).filter(UserDB.email == candidate_data["email"]).first()
    
    if existing_user:
        return existing_user, False
    
    # Create new user
    user_id = str(uuid.uuid4())
    password_hash = auth_service.get_password_hash(PASSWORD)
    
    new_user = UserDB(
        id=user_id,
        email=candidate_data["email"],
        password_hash=password_hash,
        role=UserRole.CANDIDATE,
        first_name=candidate_data["first_name"],
        last_name=candidate_data["last_name"],
        is_active=True,
        created_at=datetime.utcnow(),
        cv_processing_status=CVProcessingStatus.PENDING
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user, True


async def process_cv_for_user(db: Session, user: UserDB, cv_path: str) -> dict:
    """
    Process CV for a user and return timing information.
    Returns dict with timing details.
    """
    cv_processor = CVProcessorService()
    mock_file = MockUploadFile(cv_path)
    
    # Time the entire CV processing
    total_start = time.time()
    
    # Process CV completely: extract text, generate vector, encrypt, and store
    cyborgdb_vector_id = await cv_processor.process_cv_complete(
        file=mock_file,
        candidate_id=user.id,
        db=db
    )
    
    total_time = time.time() - total_start
    
    # Update user's CV status fields
    user.cv_uploaded_at = datetime.utcnow()
    user.cv_processing_status = CVProcessingStatus.COMPLETED
    user.vector_id = cyborgdb_vector_id
    db.commit()
    
    return {
        "vector_id": cyborgdb_vector_id,
        "total_time_ms": total_time * 1000
    }


async def process_candidate(db: Session, candidate_data: dict, index: int, total: int) -> dict:
    """
    Process a single candidate: create/get user and upload CV.
    Returns result dict with status and timing.
    """
    cv_path = os.path.join(CV_FOLDER, candidate_data["cv_file"])
    result = {
        "email": candidate_data["email"],
        "name": f"{candidate_data['first_name']} {candidate_data['last_name']}",
        "success": False,
        "user_created": False,
        "cv_processed": False,
        "timing_ms": 0,
        "error": None
    }
    
    print(f"\n[{index}/{total}] Processing: {result['name']}")
    
    # Check if CV file exists
    if not os.path.exists(cv_path):
        result["error"] = f"CV file not found: {cv_path}"
        print(f"  ❌ {result['error']}")
        return result
    
    try:
        # Step 1: Create or get user
        user, is_new = await create_or_get_user(db, candidate_data)
        result["user_created"] = is_new
        
        if is_new:
            print(f"  ✓ Created new user: {candidate_data['email']} (ID: {user.id})")
        else:
            print(f"  ℹ️  Using existing user: {candidate_data['email']} (ID: {user.id})")
        
        # Step 2: Process CV
        print(f"  ⏳ Processing CV: {candidate_data['cv_file']}...")
        cv_result = await process_cv_for_user(db, user, cv_path)
        
        result["cv_processed"] = True
        result["timing_ms"] = cv_result["total_time_ms"]
        result["success"] = True
        
        print(f"  ✓ CV stored in CyborgDB (Vector ID: {cv_result['vector_id']})")
        print(f"  ⏱️  Time: {cv_result['total_time_ms']:.2f}ms")
        
    except Exception as e:
        db.rollback()
        result["error"] = str(e)
        print(f"  ❌ Error: {e}")
    
    return result


async def main():
    """Main function to seed the database."""
    print("=" * 70)
    print("SecureHR Database Seeder")
    print("=" * 70)
    print(f"\nCV Folder: {CV_FOLDER}")
    print(f"Password for all users: {PASSWORD}")
    print(f"Candidates to process: {len(CANDIDATES)}")
    print("-" * 70)
    
    # Get database session
    db = next(get_db())
    
    results = []
    total_start = time.time()
    
    for i, candidate in enumerate(CANDIDATES, 1):
        result = await process_candidate(db, candidate, i, len(CANDIDATES))
        results.append(result)
    
    total_time = time.time() - total_start
    
    # Calculate statistics
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    new_users = [r for r in results if r["user_created"]]
    existing_users = [r for r in successful if not r["user_created"]]
    
    cv_times = [r["timing_ms"] for r in successful if r["timing_ms"] > 0]
    avg_time = sum(cv_times) / len(cv_times) if cv_times else 0
    min_time = min(cv_times) if cv_times else 0
    max_time = max(cv_times) if cv_times else 0
    
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"\nResults:")
    print(f"  ✓ Successfully processed: {len(successful)}")
    print(f"  ✗ Failed: {len(failed)}")
    print(f"  + New users created: {len(new_users)}")
    print(f"  ℹ️  Existing users updated: {len(existing_users)}")
    
    print(f"\nCyborgDB Vector Storage Timing:")
    print(f"  Average: {avg_time:.2f}ms")
    print(f"  Min: {min_time:.2f}ms")
    print(f"  Max: {max_time:.2f}ms")
    print(f"  Total processing time: {total_time:.2f}s")
    
    print(f"\nDatabase Stats:")
    print(f"  Total candidates: {db.query(UserDB).filter(UserDB.role == UserRole.CANDIDATE).count()}")
    
    if failed:
        print(f"\nFailed items:")
        for r in failed:
            print(f"  - {r['name']}: {r['error']}")
    
    db.close()


if __name__ == "__main__":
    asyncio.run(main())
