"""Saved search service for SecureHR application."""

import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..models.database import SavedSearchDB
from ..models.search import (
    SearchRequest, SavedSearchCreateRequest, SavedSearchUpdateRequest,
    SavedSearchResponse, SavedSearchListResponse, SearchHistoryEntry, SearchHistoryResponse
)

logger = logging.getLogger(__name__)


class SavedSearchService:
    """Service for managing saved searches and search history."""
    
    def __init__(self, db: Session):
        """Initialize the saved search service."""
        self.db = db
    
    def create_saved_search(
        self, 
        recruiter_id: str, 
        request: SavedSearchCreateRequest
    ) -> SavedSearchResponse:
        """
        Create a new saved search for a recruiter.
        
        Args:
            recruiter_id: ID of the recruiter creating the search
            request: Saved search creation request
            
        Returns:
            Created saved search response
            
        Raises:
            ValueError: If search name already exists for this recruiter
            RuntimeError: If database operation fails
        """
        try:
            # Check if search name already exists for this recruiter
            existing_search = self.db.query(SavedSearchDB).filter(
                SavedSearchDB.recruiter_id == recruiter_id,
                SavedSearchDB.name == request.name
            ).first()
            
            if existing_search:
                raise ValueError(f"Search with name '{request.name}' already exists")
            
            # Convert filters to JSON string if present
            filters_json = None
            if request.criteria.filters:
                filters_json = json.dumps(request.criteria.filters)
            
            # Create new saved search
            saved_search = SavedSearchDB(
                recruiter_id=recruiter_id,
                name=request.name,
                requirements=request.criteria.requirements,
                filters=filters_json,
                limit=str(request.criteria.limit) if request.criteria.limit else None
            )
            
            self.db.add(saved_search)
            self.db.commit()
            self.db.refresh(saved_search)
            
            logger.info(f"Created saved search '{request.name}' for recruiter {recruiter_id}")
            
            return self._convert_to_response(saved_search)
            
        except ValueError:
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create saved search: {e}")
            raise RuntimeError(f"Failed to create saved search: {str(e)}")
    
    def get_saved_searches(
        self, 
        recruiter_id: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> SavedSearchListResponse:
        """
        Get all saved searches for a recruiter.
        
        Args:
            recruiter_id: ID of the recruiter
            limit: Maximum number of searches to return
            offset: Number of searches to skip
            
        Returns:
            List of saved searches
        """
        try:
            query = self.db.query(SavedSearchDB).filter(
                SavedSearchDB.recruiter_id == recruiter_id
            ).order_by(desc(SavedSearchDB.created_at))
            
            # Get total count
            total_count = query.count()
            
            # Apply pagination if specified
            if offset:
                query = query.offset(offset)
            if limit:
                query = query.limit(limit)
            
            saved_searches = query.all()
            
            # Convert to response models
            search_responses = [
                self._convert_to_response(search) for search in saved_searches
            ]
            
            logger.info(f"Retrieved {len(search_responses)} saved searches for recruiter {recruiter_id}")
            
            return SavedSearchListResponse(
                searches=search_responses,
                total_count=total_count
            )
            
        except Exception as e:
            logger.error(f"Failed to get saved searches: {e}")
            raise RuntimeError(f"Failed to retrieve saved searches: {str(e)}")
    
    def get_saved_search(self, recruiter_id: str, search_id: str) -> Optional[SavedSearchResponse]:
        """
        Get a specific saved search by ID.
        
        Args:
            recruiter_id: ID of the recruiter
            search_id: ID of the saved search
            
        Returns:
            Saved search response or None if not found
        """
        try:
            saved_search = self.db.query(SavedSearchDB).filter(
                SavedSearchDB.id == search_id,
                SavedSearchDB.recruiter_id == recruiter_id
            ).first()
            
            if not saved_search:
                return None
            
            return self._convert_to_response(saved_search)
            
        except Exception as e:
            logger.error(f"Failed to get saved search {search_id}: {e}")
            raise RuntimeError(f"Failed to retrieve saved search: {str(e)}")
    
    def update_saved_search(
        self, 
        recruiter_id: str, 
        search_id: str, 
        request: SavedSearchUpdateRequest
    ) -> Optional[SavedSearchResponse]:
        """
        Update an existing saved search.
        
        Args:
            recruiter_id: ID of the recruiter
            search_id: ID of the saved search to update
            request: Update request with new values
            
        Returns:
            Updated saved search response or None if not found
            
        Raises:
            ValueError: If new search name already exists
            RuntimeError: If database operation fails
        """
        try:
            saved_search = self.db.query(SavedSearchDB).filter(
                SavedSearchDB.id == search_id,
                SavedSearchDB.recruiter_id == recruiter_id
            ).first()
            
            if not saved_search:
                return None
            
            # Check if new name conflicts with existing searches
            if request.name and request.name != saved_search.name:
                existing_search = self.db.query(SavedSearchDB).filter(
                    SavedSearchDB.recruiter_id == recruiter_id,
                    SavedSearchDB.name == request.name,
                    SavedSearchDB.id != search_id
                ).first()
                
                if existing_search:
                    raise ValueError(f"Search with name '{request.name}' already exists")
                
                saved_search.name = request.name
            
            # Update criteria if provided
            if request.criteria:
                saved_search.requirements = request.criteria.requirements
                
                # Update filters
                if request.criteria.filters:
                    saved_search.filters = json.dumps(request.criteria.filters)
                else:
                    saved_search.filters = None
                
                # Update limit
                if request.criteria.limit:
                    saved_search.limit = str(request.criteria.limit)
                else:
                    saved_search.limit = None
            
            self.db.commit()
            self.db.refresh(saved_search)
            
            logger.info(f"Updated saved search {search_id} for recruiter {recruiter_id}")
            
            return self._convert_to_response(saved_search)
            
        except ValueError:
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update saved search {search_id}: {e}")
            raise RuntimeError(f"Failed to update saved search: {str(e)}")
    
    def delete_saved_search(self, recruiter_id: str, search_id: str) -> bool:
        """
        Delete a saved search.
        
        Args:
            recruiter_id: ID of the recruiter
            search_id: ID of the saved search to delete
            
        Returns:
            True if deleted, False if not found
            
        Raises:
            RuntimeError: If database operation fails
        """
        try:
            saved_search = self.db.query(SavedSearchDB).filter(
                SavedSearchDB.id == search_id,
                SavedSearchDB.recruiter_id == recruiter_id
            ).first()
            
            if not saved_search:
                return False
            
            self.db.delete(saved_search)
            self.db.commit()
            
            logger.info(f"Deleted saved search {search_id} for recruiter {recruiter_id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to delete saved search {search_id}: {e}")
            raise RuntimeError(f"Failed to delete saved search: {str(e)}")
    
    def use_saved_search(self, recruiter_id: str, search_id: str) -> Optional[SearchRequest]:
        """
        Mark a saved search as used and return its criteria.
        
        Args:
            recruiter_id: ID of the recruiter
            search_id: ID of the saved search
            
        Returns:
            Search criteria or None if not found
        """
        try:
            saved_search = self.db.query(SavedSearchDB).filter(
                SavedSearchDB.id == search_id,
                SavedSearchDB.recruiter_id == recruiter_id
            ).first()
            
            if not saved_search:
                return None
            
            # Update usage statistics
            saved_search.last_used_at = datetime.utcnow()
            current_count = int(saved_search.use_count or "0")
            saved_search.use_count = str(current_count + 1)
            
            self.db.commit()
            
            # Convert back to SearchRequest
            filters = None
            if saved_search.filters:
                filters = json.loads(saved_search.filters)
            
            limit = None
            if saved_search.limit:
                limit = int(saved_search.limit)
            
            search_request = SearchRequest(
                requirements=saved_search.requirements,
                filters=filters,
                limit=limit
            )
            
            logger.info(f"Used saved search {search_id} for recruiter {recruiter_id}")
            return search_request
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to use saved search {search_id}: {e}")
            raise RuntimeError(f"Failed to use saved search: {str(e)}")
    
    def validate_search_criteria(self, criteria: SearchRequest) -> Dict[str, Any]:
        """
        Validate search criteria before saving.
        
        Args:
            criteria: Search criteria to validate
            
        Returns:
            Validation result
            
        Raises:
            ValueError: If criteria are invalid
        """
        validation_result = {
            "valid": True,
            "issues": []
        }
        
        # Validate requirements text
        if not criteria.requirements or len(criteria.requirements.strip()) < 10:
            validation_result["valid"] = False
            validation_result["issues"].append("Requirements must be at least 10 characters long")
        
        if len(criteria.requirements) > 5000:
            validation_result["valid"] = False
            validation_result["issues"].append("Requirements cannot exceed 5000 characters")
        
        # Validate limit
        if criteria.limit is not None:
            if criteria.limit < 1 or criteria.limit > 100:
                validation_result["valid"] = False
                validation_result["issues"].append("Limit must be between 1 and 100")
        
        # Validate filters
        if criteria.filters:
            if not isinstance(criteria.filters, dict):
                validation_result["valid"] = False
                validation_result["issues"].append("Filters must be a dictionary")
        
        if not validation_result["valid"]:
            raise ValueError(f"Invalid search criteria: {', '.join(validation_result['issues'])}")
        
        return validation_result
    
    def _convert_to_response(self, saved_search: SavedSearchDB) -> SavedSearchResponse:
        """
        Convert database model to response model.
        
        Args:
            saved_search: Database model
            
        Returns:
            Response model
        """
        # Parse filters from JSON
        filters = None
        if saved_search.filters:
            try:
                filters = json.loads(saved_search.filters)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in filters for saved search {saved_search.id}")
                filters = None
        
        # Parse limit
        limit = None
        if saved_search.limit:
            try:
                limit = int(saved_search.limit)
            except ValueError:
                logger.warning(f"Invalid limit value for saved search {saved_search.id}")
                limit = None
        
        # Create search criteria
        criteria = SearchRequest(
            requirements=saved_search.requirements,
            filters=filters,
            limit=limit
        )
        
        # Parse use count
        use_count = 0
        if saved_search.use_count:
            try:
                use_count = int(saved_search.use_count)
            except ValueError:
                logger.warning(f"Invalid use_count value for saved search {saved_search.id}")
                use_count = 0
        
        return SavedSearchResponse(
            id=saved_search.id,
            name=saved_search.name,
            criteria=criteria,
            created_at=saved_search.created_at,
            last_used_at=saved_search.last_used_at,
            use_count=use_count
        )