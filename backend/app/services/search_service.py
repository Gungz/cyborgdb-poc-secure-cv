"""Search service for SecureHR application."""

import logging
import re
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session

from .cyborgdb_service import CyborgDBService
from ..models.database import UserDB

logger = logging.getLogger(__name__)


class SearchService:
    """Service for handling job requirement searches and candidate matching."""
    
    def __init__(self):
        """Initialize the search service."""
        self.cyborgdb_service = CyborgDBService()
    
    def preprocess_search_query(self, requirements_text: str) -> str:
        """
        Preprocess and validate search query text.
        
        Args:
            requirements_text: Raw job requirements text
            
        Returns:
            Cleaned and validated requirements text
            
        Raises:
            ValueError: If requirements text is invalid
        """
        if not requirements_text or not requirements_text.strip():
            raise ValueError("Job requirements cannot be empty")
        
        # Remove excessive whitespace
        cleaned_text = " ".join(requirements_text.strip().split())
        
        # Validate minimum length (at least 10 characters for meaningful search)
        if len(cleaned_text) < 10:
            raise ValueError("Job requirements must be at least 10 characters long")
        
        # Remove special characters that might interfere with search
        # Keep alphanumeric, spaces, and common punctuation
        cleaned_text = re.sub(r'[^\w\s\.,;:\-\(\)\/]', ' ', cleaned_text)
        cleaned_text = " ".join(cleaned_text.split())
        
        logger.info(f"Preprocessed search query: {len(cleaned_text)} characters")
        return cleaned_text
    
    def validate_search_parameters(
        self, 
        requirements_text: str,
        limit: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Validate search parameters before executing search.
        
        Args:
            requirements_text: Job requirements text
            limit: Maximum number of results
            filters: Optional search filters
            
        Returns:
            Validated parameters dictionary
            
        Raises:
            ValueError: If parameters are invalid
        """
        validated_params = {}
        
        # Validate requirements text
        if not requirements_text or not requirements_text.strip():
            raise ValueError("Job requirements cannot be empty")
        validated_params["requirements_text"] = requirements_text.strip()
        
        # Validate limit
        if limit is not None:
            if not isinstance(limit, int) or limit < 1:
                raise ValueError("Limit must be a positive integer")
            if limit > 100:
                raise ValueError("Limit cannot exceed 100 results")
            validated_params["limit"] = limit
        else:
            validated_params["limit"] = 10  # Default limit
        
        # Validate filters
        if filters is not None:
            if not isinstance(filters, dict):
                raise ValueError("Filters must be a dictionary")
            # Add filter validation logic here as needed
            validated_params["filters"] = filters
        else:
            validated_params["filters"] = {}
        
        logger.info(f"Validated search parameters: limit={validated_params['limit']}")
        return validated_params
    
    def rank_search_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Rank and score search results based on similarity and other factors.
        
        Args:
            results: Raw search results from CyborgDB
            
        Returns:
            Ranked and scored results
        """
        if not results:
            return results
        
        # Sort by similarity score (descending)
        ranked_results = sorted(
            results, 
            key=lambda x: x.get("similarity_score", 0.0), 
            reverse=True
        )
        
        # Add ranking information
        for i, result in enumerate(ranked_results):
            result["rank"] = i + 1
            result["score_tier"] = self._get_score_tier(result.get("similarity_score", 0.0))
        
        logger.info(f"Ranked {len(ranked_results)} search results")
        return ranked_results
    
    def _get_score_tier(self, similarity_score: float) -> str:
        """
        Categorize similarity score into tiers.
        
        Args:
            similarity_score: Similarity score between 0 and 1
            
        Returns:
            Score tier category
        """
        if similarity_score >= 0.8:
            return "excellent"
        elif similarity_score >= 0.6:
            return "good"
        elif similarity_score >= 0.4:
            return "fair"
        else:
            return "poor"
    
    def filter_search_results(
        self, 
        results: List[Dict[str, Any]], 
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Apply additional filtering to search results.
        
        Args:
            results: Search results to filter
            filters: Filter criteria
            
        Returns:
            Filtered results
        """
        if not filters or not results:
            return results
        
        filtered_results = results.copy()
        
        # Apply minimum similarity score filter
        min_score = filters.get("min_similarity_score")
        if min_score is not None:
            filtered_results = [
                r for r in filtered_results 
                if r.get("similarity_score", 0.0) >= min_score
            ]
        
        # Apply maximum results filter
        max_results = filters.get("max_results")
        if max_results is not None and isinstance(max_results, int):
            filtered_results = filtered_results[:max_results]
        
        # Apply score tier filter
        score_tiers = filters.get("score_tiers")
        if score_tiers and isinstance(score_tiers, list):
            filtered_results = [
                r for r in filtered_results 
                if r.get("score_tier") in score_tiers
            ]
        
        logger.info(f"Filtered results: {len(results)} -> {len(filtered_results)}")
        return filtered_results
    
    def paginate_results(
        self, 
        results: List[Dict[str, Any]], 
        page: int = 1, 
        page_size: int = 10
    ) -> Dict[str, Any]:
        """
        Paginate search results.
        
        Args:
            results: Search results to paginate
            page: Page number (1-based)
            page_size: Number of results per page
            
        Returns:
            Paginated results with metadata
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 10
        if page_size > 100:
            page_size = 100
        
        total_results = len(results)
        total_pages = (total_results + page_size - 1) // page_size
        
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        
        paginated_results = results[start_idx:end_idx]
        
        return {
            "results": paginated_results,
            "pagination": {
                "current_page": page,
                "page_size": page_size,
                "total_results": total_results,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_previous": page > 1
            }
        }
    
    async def search_candidates(
        self,
        requirements_text: str,
        db: Session,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        exclude_candidate_ids: Optional[List[str]] = None,
        page: int = 1,
        page_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Search for candidates matching job requirements with ranking and filtering.
        
        Args:
            requirements_text: Job requirements text
            db: Database session for fetching candidate info
            limit: Maximum number of results to return from CyborgDB
            filters: Optional search filters
            exclude_candidate_ids: Candidate IDs to exclude from results
            page: Page number for pagination
            page_size: Results per page (if None, no pagination)
            
        Returns:
            Search results with ranking, filtering, and optional pagination
            
        Raises:
            ValueError: If search parameters are invalid
            RuntimeError: If search operation fails
        """
        try:
            # Validate search parameters
            validated_params = self.validate_search_parameters(
                requirements_text=requirements_text,
                limit=limit,
                filters=filters
            )
            
            # Preprocess the search query
            cleaned_requirements = self.preprocess_search_query(
                validated_params["requirements_text"]
            )
            
            # Search using CyborgDB (it will generate embeddings automatically)
            raw_results = await self.cyborgdb_service.search_similar_vectors(
                query_text=cleaned_requirements,
                limit=validated_params["limit"],
                exclude_candidate_ids=exclude_candidate_ids
            )
            
            # Fetch candidate info from database
            candidate_ids = [r.get("candidate_id") for r in raw_results if r.get("candidate_id")]
            candidate_info_map = {}
            if candidate_ids:
                candidates = db.query(UserDB).filter(UserDB.id.in_(candidate_ids)).all()
                candidate_info_map = {
                    c.id: {
                        "first_name": c.first_name,
                        "last_name": c.last_name,
                        "email": c.email
                    }
                    for c in candidates
                }
            
            # Enrich results with candidate info
            for result in raw_results:
                candidate_id = result.get("candidate_id")
                if candidate_id and candidate_id in candidate_info_map:
                    result["first_name"] = candidate_info_map[candidate_id]["first_name"]
                    result["last_name"] = candidate_info_map[candidate_id]["last_name"]
                    result["email"] = candidate_info_map[candidate_id]["email"]
            
            # Rank results by similarity score
            ranked_results = self.rank_search_results(raw_results)
            
            # Apply additional filtering
            filtered_results = self.filter_search_results(ranked_results, filters)
            
            # Apply pagination if requested
            if page_size is not None:
                paginated_data = self.paginate_results(filtered_results, page, page_size)
                logger.info(f"Search completed with pagination: {len(filtered_results)} total, page {page}")
                return paginated_data
            else:
                logger.info(f"Search completed: found {len(filtered_results)} candidates")
                return {"results": filtered_results}
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Candidate search failed: {e}")
            raise RuntimeError(f"Search operation failed: {str(e)}")
