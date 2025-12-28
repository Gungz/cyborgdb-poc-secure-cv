"""Search API endpoints for recruiters."""

import logging
import time
from typing import Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

from ..database import get_db
from ..middleware.auth import get_current_user
from ..models.user import Recruiter
from ..models.search import (
    SearchRequest, SearchResponse, SearchResult,
    SavedSearchCreateRequest, SavedSearchUpdateRequest, SavedSearchResponse,
    SavedSearchListResponse, SearchExportRequest, SearchExportResponse,
    SearchShareRequest, SearchShareResponse, SearchAnalytics, SearchPerformanceMetrics
)
from ..services.search_service import SearchService
from ..services.saved_search_service import SavedSearchService
from ..services.advanced_search_service import AdvancedSearchService
from ..services.cyborgdb_service import CyborgDBService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])
security = HTTPBearer()


@router.post("/candidates", response_model=SearchResponse)
async def search_candidates(
    search_request: SearchRequest,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=10, ge=1, le=100, description="Results per page"),
    current_user: Recruiter = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> SearchResponse:
    """
    Search for candidates based on job requirements with pagination.
    
    Args:
        search_request: Search criteria including requirements and filters
        page: Page number for pagination
        page_size: Number of results per page
        current_user: The authenticated recruiter user
        db: Database session
        
    Returns:
        Search results with similarity scores and pagination info
        
    Raises:
        HTTPException: If search fails or user is not authorized
    """
    # Ensure only recruiters can search for candidates
    if current_user.role != "recruiter":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only recruiters can search for candidates"
        )
    
    try:
        # Initialize search service
        search_service = SearchService()
        
        # Record search start time
        start_time = time.time()
        
        # Perform candidate search with pagination
        search_data = await search_service.search_candidates(
            requirements_text=search_request.requirements,
            db=db,
            limit=search_request.limit or 100,  # Get more results for filtering
            filters=search_request.filters,
            page=page,
            page_size=page_size
        )
        
        # Calculate search time
        search_time_ms = (time.time() - start_time) * 1000
        
        # Extract results and pagination info
        search_results = search_data.get("results", [])
        pagination_info = search_data.get("pagination")
        
        # Process results into response format
        processed_results = []
        for result in search_results:
            search_result = SearchResult(
                candidate_id=result["candidate_id"],
                similarity_score=result["similarity_score"],
                first_name=result.get("first_name"),
                last_name=result.get("last_name"),
                email=result.get("email"),
                matched_skills=result.get("metadata", {}).get("skills"),
                experience_level=result.get("metadata", {}).get("experience_level")
            )
            processed_results.append(search_result)
        
        # Get processed query for response
        processed_query = search_service.preprocess_search_query(search_request.requirements)
        
        total_results = pagination_info["total_results"] if pagination_info else len(processed_results)
        
        logger.info(f"Search completed for recruiter {current_user.id}: {len(processed_results)} results in {search_time_ms:.2f}ms")
        
        return SearchResponse(
            results=processed_results,
            total_results=total_results,
            query_processed=processed_query,
            search_time_ms=search_time_ms
        )
        
    except ValueError as e:
        logger.warning(f"Invalid search request from recruiter {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Search failed for recruiter {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search operation failed. Please try again."
        )


@router.get("/candidates/{candidate_id}/cv", response_model=Dict[str, Any])
async def get_candidate_cv_content(
    candidate_id: str,
    current_user: Recruiter = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get CV content for a specific candidate.
    
    Args:
        candidate_id: ID of the candidate
        current_user: The authenticated recruiter user
        
    Returns:
        CV content and metadata
        
    Raises:
        HTTPException: If CV not found or user is not authorized
    """
    # Ensure only recruiters can view CV content
    if current_user.role != "recruiter":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only recruiters can view candidate CVs"
        )
    
    try:
        # Initialize CyborgDB service
        cyborgdb_service = CyborgDBService()
        
        # Retrieve CV content
        cv_text, metadata = await cyborgdb_service.retrieve_vector(candidate_id)
        
        logger.info(f"Retrieved CV content for candidate {candidate_id} by recruiter {current_user.id}")
        
        return {
            "candidate_id": candidate_id,
            "cv_content": cv_text,
            "metadata": metadata
        }
        
    except RuntimeError as e:
        logger.warning(f"CV not found for candidate {candidate_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CV not found for this candidate"
        )
    except Exception as e:
        logger.error(f"Failed to retrieve CV for candidate {candidate_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve CV content. Please try again."
        )


@router.get("/candidates/similar", response_model=SearchResponse)
async def search_similar_candidates(
    requirements: str = Query(..., min_length=10, max_length=5000, description="Job requirements text"),
    limit: int = Query(default=10, ge=1, le=100, description="Maximum number of results"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=10, ge=1, le=100, description="Results per page"),
    current_user: Recruiter = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> SearchResponse:
    """
    Search for similar candidates using query parameters (alternative endpoint).
    
    Args:
        requirements: Job requirements text
        limit: Maximum number of results to return
        page: Page number for pagination
        page_size: Results per page
        current_user: The authenticated recruiter user
        db: Database session
        
    Returns:
        Search results with similarity scores
        
    Raises:
        HTTPException: If search fails or user is not authorized
    """
    # Ensure only recruiters can search for candidates
    if current_user.role != "recruiter":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only recruiters can search for candidates"
        )
    
    # Create search request from query parameters
    search_request = SearchRequest(
        requirements=requirements,
        limit=limit
    )
    
    # Use the main search endpoint logic
    return await search_candidates(search_request, page, page_size, current_user, db)


@router.post("/validate", response_model=Dict[str, Any])
async def validate_search_query(
    search_request: SearchRequest,
    current_user: Recruiter = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Validate search query without executing the search.
    
    Args:
        search_request: Search criteria to validate
        current_user: The authenticated recruiter user
        
    Returns:
        Validation result with processed query
        
    Raises:
        HTTPException: If validation fails or user is not authorized
    """
    # Ensure only recruiters can validate search queries
    if current_user.role != "recruiter":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only recruiters can validate search queries"
        )
    
    try:
        # Initialize search service
        search_service = SearchService()
        
        # Validate search parameters
        validated_params = search_service.validate_search_parameters(
            requirements_text=search_request.requirements,
            limit=search_request.limit,
            filters=search_request.filters
        )
        
        # Preprocess query
        processed_query = search_service.preprocess_search_query(
            search_request.requirements
        )
        
        logger.info(f"Search query validated for recruiter {current_user.id}")
        
        return {
            "valid": True,
            "processed_query": processed_query,
            "validated_params": validated_params,
            "message": "Search query is valid and ready for execution"
        }
        
    except ValueError as e:
        logger.warning(f"Invalid search query from recruiter {current_user.id}: {e}")
        return {
            "valid": False,
            "error": str(e),
            "message": "Search query validation failed"
        }
    except Exception as e:
        logger.error(f"Search validation failed for recruiter {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search validation failed. Please try again."
        )


@router.get("/health", response_model=Dict[str, Any])
async def search_health_check(
    current_user: Recruiter = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Check search service health and CyborgDB connectivity.
    
    Args:
        current_user: The authenticated recruiter user
        
    Returns:
        Health status information
    """
    # Ensure only recruiters can check search health
    if current_user.role != "recruiter":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only recruiters can check search health"
        )
    
    try:
        # Initialize search service
        search_service = SearchService()
        
        # Check CyborgDB health
        cyborgdb_healthy = await search_service.cyborgdb_service.health_check()
        
        # Get vector count
        vector_count = await search_service.cyborgdb_service.get_vector_count()
        
        health_status = {
            "search_service": "healthy",
            "cyborgdb_status": "healthy" if cyborgdb_healthy else "unhealthy",
            "total_candidates": vector_count,
            "timestamp": time.time()
        }
        
        logger.info(f"Search health check completed for recruiter {current_user.id}")
        return health_status
        
    except Exception as e:
        logger.error(f"Search health check failed for recruiter {current_user.id}: {e}")
        return {
            "search_service": "unhealthy",
            "cyborgdb_status": "unknown",
            "total_candidates": 0,
            "error": str(e),
            "timestamp": time.time()
        }


# Saved Search Endpoints

@router.post("/saved", response_model=SavedSearchResponse)
async def create_saved_search(
    request: SavedSearchCreateRequest,
    current_user: Recruiter = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> SavedSearchResponse:
    """
    Create a new saved search for the current recruiter.
    
    Args:
        request: Saved search creation request
        current_user: The authenticated recruiter user
        db: Database session
        
    Returns:
        Created saved search
        
    Raises:
        HTTPException: If creation fails or user is not authorized
    """
    # Ensure only recruiters can create saved searches
    if current_user.role != "recruiter":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only recruiters can create saved searches"
        )
    
    try:
        # Initialize saved search service
        saved_search_service = SavedSearchService(db)
        
        # Validate search criteria
        saved_search_service.validate_search_criteria(request.criteria)
        
        # Create saved search
        saved_search = saved_search_service.create_saved_search(
            recruiter_id=current_user.id,
            request=request
        )
        
        logger.info(f"Created saved search '{request.name}' for recruiter {current_user.id}")
        return saved_search
        
    except ValueError as e:
        logger.warning(f"Invalid saved search request from recruiter {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to create saved search for recruiter {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create saved search. Please try again."
        )


@router.get("/saved", response_model=SavedSearchListResponse)
async def get_saved_searches(
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of searches to return"),
    offset: int = Query(default=0, ge=0, description="Number of searches to skip"),
    current_user: Recruiter = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> SavedSearchListResponse:
    """
    Get all saved searches for the current recruiter.
    
    Args:
        limit: Maximum number of searches to return
        offset: Number of searches to skip
        current_user: The authenticated recruiter user
        db: Database session
        
    Returns:
        List of saved searches
        
    Raises:
        HTTPException: If retrieval fails or user is not authorized
    """
    # Ensure only recruiters can get saved searches
    if current_user.role != "recruiter":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only recruiters can access saved searches"
        )
    
    try:
        # Initialize saved search service
        saved_search_service = SavedSearchService(db)
        
        # Get saved searches
        saved_searches = saved_search_service.get_saved_searches(
            recruiter_id=current_user.id,
            limit=limit,
            offset=offset
        )
        
        logger.info(f"Retrieved {len(saved_searches.searches)} saved searches for recruiter {current_user.id}")
        return saved_searches
        
    except Exception as e:
        logger.error(f"Failed to get saved searches for recruiter {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve saved searches. Please try again."
        )


@router.get("/saved/{search_id}", response_model=SavedSearchResponse)
async def get_saved_search(
    search_id: str,
    current_user: Recruiter = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> SavedSearchResponse:
    """
    Get a specific saved search by ID.
    
    Args:
        search_id: ID of the saved search
        current_user: The authenticated recruiter user
        db: Database session
        
    Returns:
        Saved search details
        
    Raises:
        HTTPException: If search not found or user is not authorized
    """
    # Ensure only recruiters can get saved searches
    if current_user.role != "recruiter":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only recruiters can access saved searches"
        )
    
    try:
        # Initialize saved search service
        saved_search_service = SavedSearchService(db)
        
        # Get saved search
        saved_search = saved_search_service.get_saved_search(
            recruiter_id=current_user.id,
            search_id=search_id
        )
        
        if not saved_search:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Saved search not found"
            )
        
        logger.info(f"Retrieved saved search {search_id} for recruiter {current_user.id}")
        return saved_search
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get saved search {search_id} for recruiter {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve saved search. Please try again."
        )


@router.put("/saved/{search_id}", response_model=SavedSearchResponse)
async def update_saved_search(
    search_id: str,
    request: SavedSearchUpdateRequest,
    current_user: Recruiter = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> SavedSearchResponse:
    """
    Update an existing saved search.
    
    Args:
        search_id: ID of the saved search to update
        request: Update request with new values
        current_user: The authenticated recruiter user
        db: Database session
        
    Returns:
        Updated saved search
        
    Raises:
        HTTPException: If update fails or user is not authorized
    """
    # Ensure only recruiters can update saved searches
    if current_user.role != "recruiter":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only recruiters can update saved searches"
        )
    
    try:
        # Initialize saved search service
        saved_search_service = SavedSearchService(db)
        
        # Validate search criteria if provided
        if request.criteria:
            saved_search_service.validate_search_criteria(request.criteria)
        
        # Update saved search
        updated_search = saved_search_service.update_saved_search(
            recruiter_id=current_user.id,
            search_id=search_id,
            request=request
        )
        
        if not updated_search:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Saved search not found"
            )
        
        logger.info(f"Updated saved search {search_id} for recruiter {current_user.id}")
        return updated_search
        
    except ValueError as e:
        logger.warning(f"Invalid saved search update from recruiter {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update saved search {search_id} for recruiter {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update saved search. Please try again."
        )


@router.delete("/saved/{search_id}")
async def delete_saved_search(
    search_id: str,
    current_user: Recruiter = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    """
    Delete a saved search.
    
    Args:
        search_id: ID of the saved search to delete
        current_user: The authenticated recruiter user
        db: Database session
        
    Returns:
        Deletion confirmation
        
    Raises:
        HTTPException: If deletion fails or user is not authorized
    """
    # Ensure only recruiters can delete saved searches
    if current_user.role != "recruiter":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only recruiters can delete saved searches"
        )
    
    try:
        # Initialize saved search service
        saved_search_service = SavedSearchService(db)
        
        # Delete saved search
        deleted = saved_search_service.delete_saved_search(
            recruiter_id=current_user.id,
            search_id=search_id
        )
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Saved search not found"
            )
        
        logger.info(f"Deleted saved search {search_id} for recruiter {current_user.id}")
        return {"message": "Saved search deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete saved search {search_id} for recruiter {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete saved search. Please try again."
        )


@router.post("/saved/{search_id}/execute", response_model=SearchResponse)
async def execute_saved_search(
    search_id: str,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=10, ge=1, le=100, description="Results per page"),
    current_user: Recruiter = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> SearchResponse:
    """
    Execute a saved search and return results.
    
    Args:
        search_id: ID of the saved search to execute
        page: Page number for pagination
        page_size: Number of results per page
        current_user: The authenticated recruiter user
        db: Database session
        
    Returns:
        Search results
        
    Raises:
        HTTPException: If execution fails or user is not authorized
    """
    # Ensure only recruiters can execute saved searches
    if current_user.role != "recruiter":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only recruiters can execute saved searches"
        )
    
    try:
        # Initialize services
        saved_search_service = SavedSearchService(db)
        search_service = SearchService()
        
        # Get and use saved search
        search_criteria = saved_search_service.use_saved_search(
            recruiter_id=current_user.id,
            search_id=search_id
        )
        
        if not search_criteria:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Saved search not found"
            )
        
        # Record search start time
        start_time = time.time()
        
        # Execute search using saved criteria
        search_data = await search_service.search_candidates(
            requirements_text=search_criteria.requirements,
            db=db,
            limit=search_criteria.limit or 100,
            filters=search_criteria.filters,
            page=page,
            page_size=page_size
        )
        
        # Calculate search time
        search_time_ms = (time.time() - start_time) * 1000
        
        # Extract results and pagination info
        search_results = search_data.get("results", [])
        pagination_info = search_data.get("pagination")
        
        # Process results into response format
        processed_results = []
        for result in search_results:
            search_result = SearchResult(
                candidate_id=result["candidate_id"],
                similarity_score=result["similarity_score"],
                first_name=result.get("first_name"),
                last_name=result.get("last_name"),
                email=result.get("email"),
                matched_skills=result.get("metadata", {}).get("skills"),
                experience_level=result.get("metadata", {}).get("experience_level")
            )
            processed_results.append(search_result)
        
        # Get processed query for response
        processed_query = search_service.preprocess_search_query(search_criteria.requirements)
        
        total_results = pagination_info["total_results"] if pagination_info else len(processed_results)
        
        logger.info(f"Executed saved search {search_id} for recruiter {current_user.id}: {len(processed_results)} results in {search_time_ms:.2f}ms")
        
        return SearchResponse(
            results=processed_results,
            total_results=total_results,
            query_processed=processed_query,
            search_time_ms=search_time_ms
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Invalid saved search execution from recruiter {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to execute saved search {search_id} for recruiter {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to execute saved search. Please try again."
        )


# Advanced Search Features

@router.post("/export", response_model=SearchExportResponse)
async def export_search_results(
    export_request: SearchExportRequest,
    current_user: Recruiter = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> SearchExportResponse:
    """
    Export search results to specified format.
    
    Args:
        export_request: Export configuration
        current_user: The authenticated recruiter user
        db: Database session
        
    Returns:
        Export response with download information
        
    Raises:
        HTTPException: If export fails or user is not authorized
    """
    # Ensure only recruiters can export search results
    if current_user.role != "recruiter":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only recruiters can export search results"
        )
    
    try:
        # Initialize services
        search_service = SearchService()
        advanced_search_service = AdvancedSearchService()
        
        # Get search results to export
        if export_request.search_id:
            # Export from saved search
            saved_search_service = SavedSearchService(db)
            search_criteria = saved_search_service.use_saved_search(
                recruiter_id=current_user.id,
                search_id=export_request.search_id
            )
            
            if not search_criteria:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Saved search not found"
                )
        elif export_request.search_criteria:
            # Export from provided criteria
            search_criteria = export_request.search_criteria
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either search_id or search_criteria must be provided"
            )
        
        # Execute search
        search_data = await search_service.search_candidates(
            requirements_text=search_criteria.requirements,
            db=db,
            limit=export_request.max_results or 100,
            filters=search_criteria.filters
        )
        
        # Convert to SearchResponse format
        search_results = search_data.get("results", [])
        processed_results = []
        for result in search_results:
            search_result = SearchResult(
                candidate_id=result["candidate_id"],
                similarity_score=result["similarity_score"],
                first_name=result.get("first_name"),
                last_name=result.get("last_name"),
                email=result.get("email"),
                matched_skills=result.get("metadata", {}).get("skills"),
                experience_level=result.get("metadata", {}).get("experience_level")
            )
            processed_results.append(search_result)
        
        processed_query = search_service.preprocess_search_query(search_criteria.requirements)
        
        search_response = SearchResponse(
            results=processed_results,
            total_results=len(processed_results),
            query_processed=processed_query,
            search_time_ms=0.0
        )
        
        # Export results
        export_response = advanced_search_service.export_search_results(
            results=search_response,
            export_request=export_request,
            recruiter_id=current_user.id
        )
        
        logger.info(f"Exported search results for recruiter {current_user.id}: {export_response.total_results} results")
        return export_response
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Invalid export request from recruiter {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to export search results for recruiter {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export search results. Please try again."
        )


@router.post("/share", response_model=SearchShareResponse)
async def share_search_results(
    share_request: SearchShareRequest,
    current_user: Recruiter = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> SearchShareResponse:
    """
    Create a shareable link for search results.
    
    Args:
        share_request: Share configuration
        current_user: The authenticated recruiter user
        db: Database session
        
    Returns:
        Share response with access information
        
    Raises:
        HTTPException: If sharing fails or user is not authorized
    """
    # Ensure only recruiters can share search results
    if current_user.role != "recruiter":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only recruiters can share search results"
        )
    
    try:
        # Initialize services
        search_service = SearchService()
        advanced_search_service = AdvancedSearchService()
        
        # Get search results to share
        if share_request.search_id:
            # Share from saved search
            saved_search_service = SavedSearchService(db)
            search_criteria = saved_search_service.use_saved_search(
                recruiter_id=current_user.id,
                search_id=share_request.search_id
            )
            
            if not search_criteria:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Saved search not found"
                )
        elif share_request.search_criteria:
            # Share from provided criteria
            search_criteria = share_request.search_criteria
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either search_id or search_criteria must be provided"
            )
        
        # Execute search
        search_data = await search_service.search_candidates(
            requirements_text=search_criteria.requirements,
            db=db,
            limit=search_criteria.limit or 100,
            filters=search_criteria.filters
        )
        
        # Convert to SearchResponse format
        search_results = search_data.get("results", [])
        processed_results = []
        for result in search_results:
            search_result = SearchResult(
                candidate_id=result["candidate_id"],
                similarity_score=result["similarity_score"],
                first_name=result.get("first_name"),
                last_name=result.get("last_name"),
                email=result.get("email"),
                matched_skills=result.get("metadata", {}).get("skills"),
                experience_level=result.get("metadata", {}).get("experience_level")
            )
            processed_results.append(search_result)
        
        processed_query = search_service.preprocess_search_query(search_criteria.requirements)
        
        search_response = SearchResponse(
            results=processed_results,
            total_results=len(processed_results),
            query_processed=processed_query,
            search_time_ms=0.0
        )
        
        # Share results
        share_response = advanced_search_service.share_search_results(
            results=search_response,
            share_request=share_request,
            recruiter_id=current_user.id
        )
        
        logger.info(f"Shared search results for recruiter {current_user.id} with {len(share_request.recipient_emails)} recipients")
        return share_response
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Invalid share request from recruiter {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to share search results for recruiter {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to share search results. Please try again."
        )


@router.get("/analytics", response_model=SearchAnalytics)
async def get_search_analytics(
    days_back: int = Query(default=30, ge=1, le=365, description="Number of days to analyze"),
    current_user: Recruiter = Depends(get_current_user)
) -> SearchAnalytics:
    """
    Get search analytics for the current recruiter.
    
    Args:
        days_back: Number of days to look back for analytics
        current_user: The authenticated recruiter user
        
    Returns:
        Search analytics data
        
    Raises:
        HTTPException: If analytics retrieval fails or user is not authorized
    """
    # Ensure only recruiters can get search analytics
    if current_user.role != "recruiter":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only recruiters can access search analytics"
        )
    
    try:
        # Initialize advanced search service
        advanced_search_service = AdvancedSearchService()
        
        # Get analytics for this recruiter
        analytics = advanced_search_service.get_search_analytics(
            recruiter_id=current_user.id,
            days_back=days_back
        )
        
        logger.info(f"Retrieved search analytics for recruiter {current_user.id}: {days_back} days")
        return analytics
        
    except Exception as e:
        logger.error(f"Failed to get search analytics for recruiter {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve search analytics. Please try again."
        )


@router.get("/performance", response_model=SearchPerformanceMetrics)
async def get_search_performance_metrics(
    current_user: Recruiter = Depends(get_current_user)
) -> SearchPerformanceMetrics:
    """
    Get search performance metrics.
    
    Args:
        current_user: The authenticated recruiter user
        
    Returns:
        Search performance metrics
        
    Raises:
        HTTPException: If metrics retrieval fails or user is not authorized
    """
    # Ensure only recruiters can get performance metrics
    if current_user.role != "recruiter":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only recruiters can access performance metrics"
        )
    
    try:
        # Initialize advanced search service
        advanced_search_service = AdvancedSearchService()
        
        # Get performance metrics
        metrics = advanced_search_service.get_performance_metrics()
        
        logger.info(f"Retrieved performance metrics for recruiter {current_user.id}")
        return metrics
        
    except Exception as e:
        logger.error(f"Failed to get performance metrics for recruiter {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve performance metrics. Please try again."
        )