"""Upload queue management service for handling concurrent CV uploads."""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, Callable, Any
from enum import Enum
from pydantic import BaseModel
from fastapi import UploadFile

logger = logging.getLogger(__name__)


class UploadStatus(str, Enum):
    """Upload status enumeration."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class UploadTask(BaseModel):
    """Upload task model."""
    task_id: str
    candidate_id: str
    filename: str
    status: UploadStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True


class UploadQueueManager:
    """Manager for handling concurrent CV upload operations."""
    
    def __init__(self, max_concurrent_uploads: int = 1):
        """
        Initialize upload queue manager.
        
        Args:
            max_concurrent_uploads: Maximum number of concurrent uploads per user
        """
        self.max_concurrent_uploads = max_concurrent_uploads
        self._user_queues: Dict[str, asyncio.Queue] = {}
        self._user_tasks: Dict[str, Dict[str, UploadTask]] = {}
        self._processing_locks: Dict[str, asyncio.Lock] = {}
        self._worker_tasks: Dict[str, asyncio.Task] = {}
    
    def _get_user_queue(self, candidate_id: str) -> asyncio.Queue:
        """
        Get or create queue for a specific user.
        
        Args:
            candidate_id: ID of the candidate
            
        Returns:
            User's upload queue
        """
        if candidate_id not in self._user_queues:
            self._user_queues[candidate_id] = asyncio.Queue()
            self._user_tasks[candidate_id] = {}
            self._processing_locks[candidate_id] = asyncio.Lock()
        
        return self._user_queues[candidate_id]
    
    def _get_processing_lock(self, candidate_id: str) -> asyncio.Lock:
        """
        Get processing lock for a specific user.
        
        Args:
            candidate_id: ID of the candidate
            
        Returns:
            User's processing lock
        """
        if candidate_id not in self._processing_locks:
            self._processing_locks[candidate_id] = asyncio.Lock()
        
        return self._processing_locks[candidate_id]
    
    async def queue_upload(
        self,
        candidate_id: str,
        file: UploadFile,
        processor_func: Callable,
        *args,
        **kwargs
    ) -> str:
        """
        Queue a CV upload for processing.
        
        Args:
            candidate_id: ID of the candidate
            file: Upload file
            processor_func: Function to process the upload
            *args: Additional arguments for processor function
            **kwargs: Additional keyword arguments for processor function
            
        Returns:
            Task ID for tracking the upload
        """
        import uuid
        
        task_id = str(uuid.uuid4())
        
        # Create upload task
        upload_task = UploadTask(
            task_id=task_id,
            candidate_id=candidate_id,
            filename=file.filename or "unknown",
            status=UploadStatus.QUEUED,
            created_at=datetime.utcnow()
        )
        
        # Get user's queue and task tracking
        queue = self._get_user_queue(candidate_id)
        self._user_tasks[candidate_id][task_id] = upload_task
        
        # Add task to queue
        await queue.put({
            "task_id": task_id,
            "file": file,
            "processor_func": processor_func,
            "args": args,
            "kwargs": kwargs
        })
        
        # Start worker if not already running
        if candidate_id not in self._worker_tasks or self._worker_tasks[candidate_id].done():
            self._worker_tasks[candidate_id] = asyncio.create_task(
                self._process_user_queue(candidate_id)
            )
        
        logger.info(f"Queued upload task {task_id} for candidate {candidate_id}")
        return task_id
    
    async def _process_user_queue(self, candidate_id: str):
        """
        Process uploads for a specific user sequentially.
        
        Args:
            candidate_id: ID of the candidate
        """
        queue = self._get_user_queue(candidate_id)
        processing_lock = self._get_processing_lock(candidate_id)
        
        logger.info(f"Started upload queue worker for candidate {candidate_id}")
        
        while True:
            try:
                # Wait for next upload task
                task_data = await asyncio.wait_for(queue.get(), timeout=300)  # 5 minute timeout
                
                task_id = task_data["task_id"]
                file = task_data["file"]
                processor_func = task_data["processor_func"]
                args = task_data["args"]
                kwargs = task_data["kwargs"]
                
                # Get task from tracking
                upload_task = self._user_tasks[candidate_id].get(task_id)
                if not upload_task:
                    logger.error(f"Upload task {task_id} not found for candidate {candidate_id}")
                    continue
                
                # Acquire processing lock to ensure sequential processing
                async with processing_lock:
                    # Update task status
                    upload_task.status = UploadStatus.PROCESSING
                    upload_task.started_at = datetime.utcnow()
                    
                    logger.info(f"Processing upload task {task_id} for candidate {candidate_id}")
                    
                    try:
                        # Process the upload
                        result = await processor_func(file, candidate_id, *args, **kwargs)
                        
                        # Mark as completed
                        upload_task.status = UploadStatus.COMPLETED
                        upload_task.completed_at = datetime.utcnow()
                        
                        logger.info(f"Completed upload task {task_id} for candidate {candidate_id}")
                        
                    except Exception as e:
                        # Mark as failed
                        upload_task.status = UploadStatus.FAILED
                        upload_task.error_message = str(e)
                        upload_task.completed_at = datetime.utcnow()
                        
                        logger.error(f"Failed upload task {task_id} for candidate {candidate_id}: {e}")
                
                # Mark queue task as done
                queue.task_done()
                
            except asyncio.TimeoutError:
                # No more tasks in queue, exit worker
                logger.info(f"Upload queue worker timeout for candidate {candidate_id}")
                break
            except Exception as e:
                logger.error(f"Error in upload queue worker for candidate {candidate_id}: {e}")
                continue
        
        logger.info(f"Stopped upload queue worker for candidate {candidate_id}")
    
    def get_upload_status(self, candidate_id: str, task_id: str) -> Optional[UploadTask]:
        """
        Get status of a specific upload task.
        
        Args:
            candidate_id: ID of the candidate
            task_id: ID of the upload task
            
        Returns:
            Upload task if found, None otherwise
        """
        user_tasks = self._user_tasks.get(candidate_id, {})
        return user_tasks.get(task_id)
    
    def get_user_uploads(self, candidate_id: str) -> Dict[str, UploadTask]:
        """
        Get all upload tasks for a user.
        
        Args:
            candidate_id: ID of the candidate
            
        Returns:
            Dictionary of task_id -> UploadTask
        """
        return self._user_tasks.get(candidate_id, {})
    
    def is_user_processing(self, candidate_id: str) -> bool:
        """
        Check if user has any uploads currently processing.
        
        Args:
            candidate_id: ID of the candidate
            
        Returns:
            True if user has processing uploads
        """
        user_tasks = self._user_tasks.get(candidate_id, {})
        return any(
            task.status == UploadStatus.PROCESSING 
            for task in user_tasks.values()
        )
    
    def get_queue_size(self, candidate_id: str) -> int:
        """
        Get number of queued uploads for a user.
        
        Args:
            candidate_id: ID of the candidate
            
        Returns:
            Number of queued uploads
        """
        queue = self._user_queues.get(candidate_id)
        return queue.qsize() if queue else 0
    
    async def cancel_upload(self, candidate_id: str, task_id: str) -> bool:
        """
        Cancel a queued upload task.
        
        Args:
            candidate_id: ID of the candidate
            task_id: ID of the upload task
            
        Returns:
            True if task was cancelled, False if not found or already processing
        """
        upload_task = self.get_upload_status(candidate_id, task_id)
        
        if not upload_task:
            return False
        
        if upload_task.status == UploadStatus.PROCESSING:
            # Cannot cancel processing uploads
            return False
        
        if upload_task.status == UploadStatus.QUEUED:
            # Mark as failed/cancelled
            upload_task.status = UploadStatus.FAILED
            upload_task.error_message = "Upload cancelled by user"
            upload_task.completed_at = datetime.utcnow()
            
            logger.info(f"Cancelled upload task {task_id} for candidate {candidate_id}")
            return True
        
        return False
    
    def cleanup_completed_tasks(self, candidate_id: str, max_age_hours: int = 24):
        """
        Clean up completed/failed tasks older than specified age.
        
        Args:
            candidate_id: ID of the candidate
            max_age_hours: Maximum age of tasks to keep (in hours)
        """
        user_tasks = self._user_tasks.get(candidate_id, {})
        current_time = datetime.utcnow()
        
        tasks_to_remove = []
        for task_id, task in user_tasks.items():
            if task.status in [UploadStatus.COMPLETED, UploadStatus.FAILED]:
                if task.completed_at:
                    age_hours = (current_time - task.completed_at).total_seconds() / 3600
                    if age_hours > max_age_hours:
                        tasks_to_remove.append(task_id)
        
        for task_id in tasks_to_remove:
            del user_tasks[task_id]
            logger.info(f"Cleaned up old upload task {task_id} for candidate {candidate_id}")


# Global upload queue manager instance
upload_queue_manager = UploadQueueManager()