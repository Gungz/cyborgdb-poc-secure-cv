"""Search models for SecureHR application."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class ExportFormat(str, Enum):
    """Export format enumeration."""
    CSV = "csv"
    JSON = "json"
    PDF = "pdf"


class SearchRequest(BaseModel):
    """Search request model for job requirements."""
    requirements: str = Field(..., min_length=10, max_length=5000, description="Job requirements text")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Optional search filters")
    limit: Optional[int] = Field(default=10, ge=1, le=100, description="Maximum number of results")


class SearchResult(BaseModel):
    """Individual search result model."""
    candidate_id: str = Field(..., description="Candidate identifier")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Similarity score between 0 and 1")
    first_name: Optional[str] = Field(default=None, description="Candidate first name")
    last_name: Optional[str] = Field(default=None, description="Candidate last name")
    email: Optional[str] = Field(default=None, description="Candidate email")
    matched_skills: Optional[List[str]] = Field(default=None, description="Skills that matched the search")
    experience_level: Optional[str] = Field(default=None, description="Candidate experience level")


class SearchResponse(BaseModel):
    """Search response model."""
    results: List[SearchResult] = Field(..., description="List of search results")
    total_results: int = Field(..., description="Total number of results found")
    query_processed: str = Field(..., description="Processed search query")
    search_time_ms: Optional[float] = Field(default=None, description="Search execution time in milliseconds")


class SavedSearch(BaseModel):
    """Saved search model."""
    id: str = Field(..., description="Saved search identifier")
    name: str = Field(..., min_length=1, max_length=100, description="Search name")
    criteria: SearchRequest = Field(..., description="Search criteria")
    created_at: datetime = Field(..., description="Creation timestamp")
    last_used_at: Optional[datetime] = Field(default=None, description="Last usage timestamp")


class SavedSearchCreateRequest(BaseModel):
    """Request model for creating a saved search."""
    name: str = Field(..., min_length=1, max_length=100, description="Search name")
    criteria: SearchRequest = Field(..., description="Search criteria to save")


class SavedSearchUpdateRequest(BaseModel):
    """Request model for updating a saved search."""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Updated search name")
    criteria: Optional[SearchRequest] = Field(None, description="Updated search criteria")


class SavedSearchResponse(BaseModel):
    """Response model for saved search operations."""
    id: str = Field(..., description="Saved search identifier")
    name: str = Field(..., description="Search name")
    criteria: SearchRequest = Field(..., description="Search criteria")
    created_at: datetime = Field(..., description="Creation timestamp")
    last_used_at: Optional[datetime] = Field(default=None, description="Last usage timestamp")
    use_count: int = Field(default=0, description="Number of times this search has been used")
    
    class Config:
        from_attributes = True  # For SQLAlchemy model conversion


class SavedSearchListResponse(BaseModel):
    """Response model for listing saved searches."""
    searches: List[SavedSearchResponse] = Field(..., description="List of saved searches")
    total_count: int = Field(..., description="Total number of saved searches")


class SearchHistoryEntry(BaseModel):
    """Search history entry model."""
    search_id: Optional[str] = Field(None, description="Saved search ID if applicable")
    search_name: Optional[str] = Field(None, description="Search name if saved")
    requirements: str = Field(..., description="Search requirements")
    executed_at: datetime = Field(..., description="Execution timestamp")
    results_count: int = Field(..., description="Number of results returned")
    search_time_ms: Optional[float] = Field(None, description="Search execution time")


class SearchHistoryResponse(BaseModel):
    """Response model for search history."""
    history: List[SearchHistoryEntry] = Field(..., description="List of search history entries")
    total_count: int = Field(..., description="Total number of history entries")


class SearchExportRequest(BaseModel):
    """Request model for exporting search results."""
    search_id: Optional[str] = Field(None, description="Saved search ID to export")
    search_criteria: Optional[SearchRequest] = Field(None, description="Search criteria for one-time export")
    format: ExportFormat = Field(..., description="Export format")
    include_metadata: bool = Field(default=True, description="Include search metadata in export")
    max_results: Optional[int] = Field(default=100, ge=1, le=1000, description="Maximum results to export")


class SearchExportResponse(BaseModel):
    """Response model for search export."""
    export_id: str = Field(..., description="Export identifier")
    download_url: str = Field(..., description="URL to download the exported file")
    format: ExportFormat = Field(..., description="Export format")
    total_results: int = Field(..., description="Number of results exported")
    expires_at: datetime = Field(..., description="When the download link expires")


class SearchShareRequest(BaseModel):
    """Request model for sharing search results."""
    search_id: Optional[str] = Field(None, description="Saved search ID to share")
    search_criteria: Optional[SearchRequest] = Field(None, description="Search criteria for one-time share")
    recipient_emails: List[str] = Field(..., min_items=1, max_items=10, description="Email addresses to share with")
    message: Optional[str] = Field(None, max_length=500, description="Optional message to include")
    expires_in_days: int = Field(default=7, ge=1, le=30, description="Number of days until share expires")


class SearchShareResponse(BaseModel):
    """Response model for search sharing."""
    share_id: str = Field(..., description="Share identifier")
    share_url: str = Field(..., description="URL to access shared results")
    expires_at: datetime = Field(..., description="When the share expires")
    recipients: List[str] = Field(..., description="Email addresses shared with")


class SearchAnalytics(BaseModel):
    """Search analytics model."""
    total_searches: int = Field(..., description="Total number of searches performed")
    average_results_per_search: float = Field(..., description="Average number of results per search")
    most_common_keywords: List[str] = Field(..., description="Most frequently searched keywords")
    search_success_rate: float = Field(..., ge=0.0, le=1.0, description="Percentage of searches that returned results")
    average_search_time_ms: float = Field(..., description="Average search execution time in milliseconds")
    peak_search_hours: List[int] = Field(..., description="Hours of day with most search activity")
    top_saved_searches: List[Dict[str, Any]] = Field(..., description="Most frequently used saved searches")


class SearchPerformanceMetrics(BaseModel):
    """Search performance metrics model."""
    cache_hit_rate: float = Field(..., ge=0.0, le=1.0, description="Percentage of searches served from cache")
    average_response_time_ms: float = Field(..., description="Average response time in milliseconds")
    total_cache_entries: int = Field(..., description="Number of entries in search cache")
    cache_memory_usage_mb: float = Field(..., description="Memory usage of search cache in MB")
    database_query_time_ms: float = Field(..., description="Average database query time")
    vector_search_time_ms: float = Field(..., description="Average vector search time")