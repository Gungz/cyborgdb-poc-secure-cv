"""Tests for search functionality."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

from app.services.search_service import SearchService
from app.services.saved_search_service import SavedSearchService
from app.services.advanced_search_service import AdvancedSearchService, SearchCache
from app.api.search import router
from app.models.search import (
    SearchRequest, SearchResult, SavedSearchCreateRequest, SavedSearchUpdateRequest,
    SearchExportRequest, ExportFormat, SearchResponse
)
from app.models.database import Base, SavedSearchDB
from main import app

client = TestClient(app)


class TestSearchService:
    """Test cases for SearchService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.search_service = SearchService()
    
    def test_preprocess_search_query_valid(self):
        """Test preprocessing of valid search query."""
        query = "  Looking for Python developer with 5 years experience  "
        result = self.search_service.preprocess_search_query(query)
        
        assert result == "Looking for Python developer with 5 years experience"
        assert len(result) >= 10
    
    def test_preprocess_search_query_empty(self):
        """Test preprocessing of empty search query."""
        with pytest.raises(ValueError, match="Job requirements cannot be empty"):
            self.search_service.preprocess_search_query("")
    
    def test_preprocess_search_query_too_short(self):
        """Test preprocessing of too short search query."""
        with pytest.raises(ValueError, match="Job requirements must be at least 10 characters long"):
            self.search_service.preprocess_search_query("Python")
    
    def test_preprocess_search_query_special_characters(self):
        """Test preprocessing removes special characters."""
        query = "Python developer with @#$% experience!!!"
        result = self.search_service.preprocess_search_query(query)
        
        assert "@#$%" not in result
        assert "Python developer with experience" in result
    
    def test_validate_search_parameters_valid(self):
        """Test validation of valid search parameters."""
        result = self.search_service.validate_search_parameters(
            requirements_text="Python developer with experience",
            limit=20,
            filters={"min_score": 0.5}
        )
        
        assert result["requirements_text"] == "Python developer with experience"
        assert result["limit"] == 20
        assert result["filters"] == {"min_score": 0.5}
    
    def test_validate_search_parameters_invalid_limit(self):
        """Test validation with invalid limit."""
        with pytest.raises(ValueError, match="Limit must be a positive integer"):
            self.search_service.validate_search_parameters(
                requirements_text="Python developer",
                limit=0
            )
    
    def test_validate_search_parameters_limit_too_high(self):
        """Test validation with limit too high."""
        with pytest.raises(ValueError, match="Limit cannot exceed 100 results"):
            self.search_service.validate_search_parameters(
                requirements_text="Python developer",
                limit=150
            )
    
    def test_rank_search_results(self):
        """Test ranking of search results."""
        results = [
            {"candidate_id": "1", "similarity_score": 0.7},
            {"candidate_id": "2", "similarity_score": 0.9},
            {"candidate_id": "3", "similarity_score": 0.5}
        ]
        
        ranked = self.search_service.rank_search_results(results)
        
        assert len(ranked) == 3
        assert ranked[0]["candidate_id"] == "2"  # Highest score first
        assert ranked[0]["rank"] == 1
        assert ranked[0]["score_tier"] == "excellent"
        assert ranked[1]["candidate_id"] == "1"
        assert ranked[2]["candidate_id"] == "3"
    
    def test_rank_search_results_empty(self):
        """Test ranking of empty results."""
        result = self.search_service.rank_search_results([])
        assert result == []
    
    def test_get_score_tier(self):
        """Test score tier categorization."""
        assert self.search_service._get_score_tier(0.9) == "excellent"
        assert self.search_service._get_score_tier(0.7) == "good"
        assert self.search_service._get_score_tier(0.5) == "fair"
        assert self.search_service._get_score_tier(0.3) == "poor"
    
    def test_filter_search_results_min_score(self):
        """Test filtering by minimum similarity score."""
        results = [
            {"candidate_id": "1", "similarity_score": 0.7},
            {"candidate_id": "2", "similarity_score": 0.9},
            {"candidate_id": "3", "similarity_score": 0.3}
        ]
        filters = {"min_similarity_score": 0.6}
        
        filtered = self.search_service.filter_search_results(results, filters)
        
        assert len(filtered) == 2
        assert all(r["similarity_score"] >= 0.6 for r in filtered)
    
    def test_filter_search_results_max_results(self):
        """Test filtering by maximum results."""
        results = [
            {"candidate_id": "1", "similarity_score": 0.7},
            {"candidate_id": "2", "similarity_score": 0.9},
            {"candidate_id": "3", "similarity_score": 0.5}
        ]
        filters = {"max_results": 2}
        
        filtered = self.search_service.filter_search_results(results, filters)
        
        assert len(filtered) == 2
    
    def test_paginate_results(self):
        """Test result pagination."""
        results = [{"candidate_id": str(i)} for i in range(25)]
        
        paginated = self.search_service.paginate_results(results, page=2, page_size=10)
        
        assert len(paginated["results"]) == 10
        assert paginated["pagination"]["current_page"] == 2
        assert paginated["pagination"]["total_pages"] == 3
        assert paginated["pagination"]["total_results"] == 25
        assert paginated["pagination"]["has_next"] is True
        assert paginated["pagination"]["has_previous"] is True
    
    def test_paginate_results_last_page(self):
        """Test pagination on last page."""
        results = [{"candidate_id": str(i)} for i in range(25)]
        
        paginated = self.search_service.paginate_results(results, page=3, page_size=10)
        
        assert len(paginated["results"]) == 5  # Remaining results
        assert paginated["pagination"]["has_next"] is False
        assert paginated["pagination"]["has_previous"] is True
    
    @pytest.mark.asyncio
    @patch('app.services.search_service.CyborgDBService')
    async def test_search_candidates_success(self, mock_cyborgdb_service):
        """Test successful candidate search."""
        # Mock CyborgDB service
        mock_cyborgdb_instance = AsyncMock()
        mock_cyborgdb_instance.search_similar_vectors.return_value = [
            {
                "candidate_id": "1",
                "similarity_score": 0.8,
                "metadata": {"skills": ["Python", "Django"]}
            }
        ]
        mock_cyborgdb_service.return_value = mock_cyborgdb_instance
        
        # Mock database session
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        search_service = SearchService()
        result = await search_service.search_candidates(
            requirements_text="Python developer with Django experience",
            db=mock_db,
            limit=10
        )
        
        assert "results" in result
        assert len(result["results"]) == 1
        assert result["results"][0]["candidate_id"] == "1"
        assert result["results"][0]["similarity_score"] == 0.8
    
    @pytest.mark.asyncio
    async def test_search_candidates_invalid_requirements(self):
        """Test search with invalid requirements."""
        mock_db = Mock()
        with pytest.raises(ValueError):
            await self.search_service.search_candidates(
                requirements_text="",
                db=mock_db,
                limit=10
            )


class TestSavedSearchService:
    """Test cases for SavedSearchService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create in-memory SQLite database for testing
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        
        # Create session
        SessionLocal = sessionmaker(bind=self.engine)
        self.db = SessionLocal()
        
        # Initialize service
        self.saved_search_service = SavedSearchService(self.db)
        
        # Test data
        self.recruiter_id = "test-recruiter-123"
        self.search_criteria = SearchRequest(
            requirements="Python developer with 5 years experience",
            filters={"min_score": 0.7},
            limit=20
        )
    
    def teardown_method(self):
        """Clean up after tests."""
        self.db.close()
    
    def test_create_saved_search_success(self):
        """Test successful creation of saved search."""
        request = SavedSearchCreateRequest(
            name="Python Developers",
            criteria=self.search_criteria
        )
        
        result = self.saved_search_service.create_saved_search(
            recruiter_id=self.recruiter_id,
            request=request
        )
        
        assert result.name == "Python Developers"
        assert result.criteria.requirements == self.search_criteria.requirements
        assert result.criteria.filters == self.search_criteria.filters
        assert result.criteria.limit == self.search_criteria.limit
        assert result.use_count == 0
        assert result.last_used_at is None
    
    def test_create_saved_search_duplicate_name(self):
        """Test creation with duplicate name fails."""
        request = SavedSearchCreateRequest(
            name="Python Developers",
            criteria=self.search_criteria
        )
        
        # Create first search
        self.saved_search_service.create_saved_search(
            recruiter_id=self.recruiter_id,
            request=request
        )
        
        # Try to create duplicate
        with pytest.raises(ValueError, match="Search with name 'Python Developers' already exists"):
            self.saved_search_service.create_saved_search(
                recruiter_id=self.recruiter_id,
                request=request
            )
    
    def test_get_saved_searches_empty(self):
        """Test getting saved searches when none exist."""
        result = self.saved_search_service.get_saved_searches(self.recruiter_id)
        
        assert result.total_count == 0
        assert len(result.searches) == 0
    
    def test_get_saved_searches_with_data(self):
        """Test getting saved searches with existing data."""
        # Create test searches
        for i in range(3):
            request = SavedSearchCreateRequest(
                name=f"Search {i}",
                criteria=self.search_criteria
            )
            self.saved_search_service.create_saved_search(
                recruiter_id=self.recruiter_id,
                request=request
            )
        
        result = self.saved_search_service.get_saved_searches(self.recruiter_id)
        
        assert result.total_count == 3
        assert len(result.searches) == 3
        # Should be ordered by creation date (newest first)
        search_names = [search.name for search in result.searches]
        assert "Search 0" in search_names
        assert "Search 1" in search_names
        assert "Search 2" in search_names
    
    def test_get_saved_searches_with_pagination(self):
        """Test getting saved searches with pagination."""
        # Create test searches
        for i in range(5):
            request = SavedSearchCreateRequest(
                name=f"Search {i}",
                criteria=self.search_criteria
            )
            self.saved_search_service.create_saved_search(
                recruiter_id=self.recruiter_id,
                request=request
            )
        
        result = self.saved_search_service.get_saved_searches(
            recruiter_id=self.recruiter_id,
            limit=2,
            offset=1
        )
        
        assert result.total_count == 5
        assert len(result.searches) == 2
    
    def test_get_saved_search_exists(self):
        """Test getting a specific saved search that exists."""
        request = SavedSearchCreateRequest(
            name="Python Developers",
            criteria=self.search_criteria
        )
        
        created = self.saved_search_service.create_saved_search(
            recruiter_id=self.recruiter_id,
            request=request
        )
        
        result = self.saved_search_service.get_saved_search(
            recruiter_id=self.recruiter_id,
            search_id=created.id
        )
        
        assert result is not None
        assert result.id == created.id
        assert result.name == "Python Developers"
    
    def test_get_saved_search_not_exists(self):
        """Test getting a saved search that doesn't exist."""
        result = self.saved_search_service.get_saved_search(
            recruiter_id=self.recruiter_id,
            search_id="non-existent-id"
        )
        
        assert result is None
    
    def test_update_saved_search_name(self):
        """Test updating saved search name."""
        # Create search
        request = SavedSearchCreateRequest(
            name="Python Developers",
            criteria=self.search_criteria
        )
        created = self.saved_search_service.create_saved_search(
            recruiter_id=self.recruiter_id,
            request=request
        )
        
        # Update name
        update_request = SavedSearchUpdateRequest(name="Senior Python Developers")
        result = self.saved_search_service.update_saved_search(
            recruiter_id=self.recruiter_id,
            search_id=created.id,
            request=update_request
        )
        
        assert result is not None
        assert result.name == "Senior Python Developers"
        assert result.criteria.requirements == self.search_criteria.requirements
    
    def test_update_saved_search_criteria(self):
        """Test updating saved search criteria."""
        # Create search
        request = SavedSearchCreateRequest(
            name="Python Developers",
            criteria=self.search_criteria
        )
        created = self.saved_search_service.create_saved_search(
            recruiter_id=self.recruiter_id,
            request=request
        )
        
        # Update criteria
        new_criteria = SearchRequest(
            requirements="Senior Python developer with Django",
            filters={"min_score": 0.8},
            limit=15
        )
        update_request = SavedSearchUpdateRequest(criteria=new_criteria)
        result = self.saved_search_service.update_saved_search(
            recruiter_id=self.recruiter_id,
            search_id=created.id,
            request=update_request
        )
        
        assert result is not None
        assert result.criteria.requirements == "Senior Python developer with Django"
        assert result.criteria.filters == {"min_score": 0.8}
        assert result.criteria.limit == 15
    
    def test_update_saved_search_not_exists(self):
        """Test updating a saved search that doesn't exist."""
        update_request = SavedSearchUpdateRequest(name="New Name")
        result = self.saved_search_service.update_saved_search(
            recruiter_id=self.recruiter_id,
            search_id="non-existent-id",
            request=update_request
        )
        
        assert result is None
    
    def test_delete_saved_search_success(self):
        """Test successful deletion of saved search."""
        # Create search
        request = SavedSearchCreateRequest(
            name="Python Developers",
            criteria=self.search_criteria
        )
        created = self.saved_search_service.create_saved_search(
            recruiter_id=self.recruiter_id,
            request=request
        )
        
        # Delete search
        result = self.saved_search_service.delete_saved_search(
            recruiter_id=self.recruiter_id,
            search_id=created.id
        )
        
        assert result is True
        
        # Verify it's deleted
        deleted_search = self.saved_search_service.get_saved_search(
            recruiter_id=self.recruiter_id,
            search_id=created.id
        )
        assert deleted_search is None
    
    def test_delete_saved_search_not_exists(self):
        """Test deleting a saved search that doesn't exist."""
        result = self.saved_search_service.delete_saved_search(
            recruiter_id=self.recruiter_id,
            search_id="non-existent-id"
        )
        
        assert result is False
    
    def test_use_saved_search_success(self):
        """Test using a saved search successfully."""
        # Create search
        request = SavedSearchCreateRequest(
            name="Python Developers",
            criteria=self.search_criteria
        )
        created = self.saved_search_service.create_saved_search(
            recruiter_id=self.recruiter_id,
            request=request
        )
        
        # Use search
        result = self.saved_search_service.use_saved_search(
            recruiter_id=self.recruiter_id,
            search_id=created.id
        )
        
        assert result is not None
        assert result.requirements == self.search_criteria.requirements
        assert result.filters == self.search_criteria.filters
        assert result.limit == self.search_criteria.limit
        
        # Verify usage statistics updated
        updated_search = self.saved_search_service.get_saved_search(
            recruiter_id=self.recruiter_id,
            search_id=created.id
        )
        assert updated_search.use_count == 1
        assert updated_search.last_used_at is not None
    
    def test_use_saved_search_not_exists(self):
        """Test using a saved search that doesn't exist."""
        result = self.saved_search_service.use_saved_search(
            recruiter_id=self.recruiter_id,
            search_id="non-existent-id"
        )
        
        assert result is None
    
    def test_validate_search_criteria_valid(self):
        """Test validation of valid search criteria."""
        result = self.saved_search_service.validate_search_criteria(self.search_criteria)
        
        assert result["valid"] is True
        assert len(result["issues"]) == 0
    
    def test_validate_search_criteria_invalid_requirements(self):
        """Test validation with invalid requirements."""
        # Create criteria with short requirements that bypasses Pydantic validation
        # by creating the object directly and testing our service validation
        try:
            # This should pass Pydantic validation but fail our service validation
            invalid_criteria = SearchRequest(
                requirements="Python developer with experience",  # Valid for Pydantic
                limit=10
            )
            # Manually set short requirements to test our validation
            invalid_criteria.requirements = "short"
            
            with pytest.raises(ValueError, match="Requirements must be at least 10 characters long"):
                self.saved_search_service.validate_search_criteria(invalid_criteria)
        except Exception:
            # If Pydantic validation prevents this, test with empty string
            invalid_criteria = SearchRequest(
                requirements="Python developer with experience",
                limit=10
            )
            invalid_criteria.requirements = ""
            
            with pytest.raises(ValueError, match="Requirements must be at least 10 characters long"):
                self.saved_search_service.validate_search_criteria(invalid_criteria)
    
    def test_validate_search_criteria_invalid_limit(self):
        """Test validation with invalid limit."""
        # Create valid criteria first, then modify limit to test our validation
        invalid_criteria = SearchRequest(
            requirements="Python developer with experience",
            limit=50  # Valid for Pydantic
        )
        # Manually set invalid limit to test our validation
        invalid_criteria.limit = 150
        
        with pytest.raises(ValueError, match="Limit must be between 1 and 100"):
            self.saved_search_service.validate_search_criteria(invalid_criteria)


class TestAdvancedSearchService:
    """Test cases for AdvancedSearchService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.advanced_search_service = AdvancedSearchService()
        self.search_request = SearchRequest(
            requirements="Python developer with 5 years experience",
            filters={"min_score": 0.7},
            limit=20
        )
    
    def test_search_cache_set_and_get(self):
        """Test caching search results."""
        cache = SearchCache()
        
        results = {"results": [{"candidate_id": "1", "similarity_score": 0.8}]}
        
        # Cache results
        cache.set(self.search_request, results)
        
        # Retrieve cached results
        cached_results = cache.get(self.search_request)
        
        assert cached_results is not None
        assert cached_results == results
    
    def test_search_cache_miss(self):
        """Test cache miss for non-existent search."""
        cache = SearchCache()
        
        # Try to get non-existent results
        cached_results = cache.get(self.search_request)
        
        assert cached_results is None
    
    def test_search_cache_expiration(self):
        """Test cache entry expiration."""
        cache = SearchCache(ttl_seconds=1)  # 1 second TTL
        
        results = {"results": [{"candidate_id": "1", "similarity_score": 0.8}]}
        
        # Cache results
        cache.set(self.search_request, results)
        
        # Immediately retrieve - should work
        cached_results = cache.get(self.search_request)
        assert cached_results is not None
        
        # Wait for expiration
        import time
        time.sleep(2)
        
        # Try to retrieve expired results
        cached_results = cache.get(self.search_request)
        assert cached_results is None
    
    def test_search_cache_max_size(self):
        """Test cache size limit."""
        cache = SearchCache(max_size=2)
        
        # Add 3 entries
        for i in range(3):
            request = SearchRequest(
                requirements=f"Python developer {i}",
                limit=10
            )
            results = {"results": [{"candidate_id": str(i)}]}
            cache.set(request, results)
        
        # Cache should only have 2 entries (oldest removed)
        stats = cache.get_stats()
        assert stats["total_entries"] == 2
    
    def test_extract_keywords(self):
        """Test keyword extraction from requirements text."""
        keywords = self.advanced_search_service._extract_keywords(
            "Looking for a Python developer with Django and REST API experience"
        )
        
        assert "python" in keywords
        assert "developer" in keywords
        assert "django" in keywords
        assert "rest" in keywords or "api" in keywords
        # Stop words should be filtered out
        assert "for" not in keywords
        assert "a" not in keywords
    
    def test_record_search_execution(self):
        """Test recording search execution for analytics."""
        search_response = SearchResponse(
            results=[
                SearchResult(candidate_id="1", similarity_score=0.8),
                SearchResult(candidate_id="2", similarity_score=0.7)
            ],
            total_results=2,
            query_processed="Python developer",
            search_time_ms=150.5
        )
        
        self.advanced_search_service.record_search_execution(
            search_request=self.search_request,
            results=search_response,
            search_time_ms=150.5,
            cache_hit=False,
            recruiter_id="test-recruiter"
        )
        
        # Verify metrics updated
        assert self.advanced_search_service.performance_metrics["total_searches"] == 1
        assert self.advanced_search_service.performance_metrics["cache_hits"] == 0
        assert len(self.advanced_search_service.search_history) == 1
    
    def test_get_search_analytics_empty(self):
        """Test getting analytics with no search history."""
        analytics = self.advanced_search_service.get_search_analytics(
            recruiter_id="test-recruiter",
            days_back=30
        )
        
        assert analytics.total_searches == 0
        assert analytics.average_results_per_search == 0.0
        assert len(analytics.most_common_keywords) == 0
    
    def test_get_search_analytics_with_data(self):
        """Test getting analytics with search history."""
        # Record some searches
        for i in range(3):
            search_response = SearchResponse(
                results=[SearchResult(candidate_id=str(i), similarity_score=0.8)],
                total_results=1,
                query_processed="Python developer",
                search_time_ms=100.0
            )
            
            self.advanced_search_service.record_search_execution(
                search_request=self.search_request,
                results=search_response,
                search_time_ms=100.0,
                cache_hit=False,
                recruiter_id="test-recruiter"
            )
        
        analytics = self.advanced_search_service.get_search_analytics(
            recruiter_id="test-recruiter",
            days_back=30
        )
        
        assert analytics.total_searches == 3
        assert analytics.average_results_per_search == 1.0
        assert analytics.search_success_rate == 1.0
        assert analytics.average_search_time_ms == 100.0
        assert len(analytics.most_common_keywords) > 0
    
    def test_get_performance_metrics(self):
        """Test getting performance metrics."""
        # Record a search
        search_response = SearchResponse(
            results=[SearchResult(candidate_id="1", similarity_score=0.8)],
            total_results=1,
            query_processed="Python developer",
            search_time_ms=150.0
        )
        
        self.advanced_search_service.record_search_execution(
            search_request=self.search_request,
            results=search_response,
            search_time_ms=150.0,
            cache_hit=True,
            recruiter_id="test-recruiter"
        )
        
        metrics = self.advanced_search_service.get_performance_metrics()
        
        assert metrics.cache_hit_rate == 1.0
        assert metrics.average_response_time_ms == 150.0
        assert metrics.total_cache_entries >= 0
    
    def test_export_to_csv(self):
        """Test exporting search results to CSV."""
        results = [
            SearchResult(
                candidate_id="1",
                similarity_score=0.8,
                matched_skills=["Python", "Django"],
                experience_level="Senior"
            ),
            SearchResult(
                candidate_id="2",
                similarity_score=0.7,
                matched_skills=["Python", "Flask"],
                experience_level="Mid"
            )
        ]
        
        search_response = SearchResponse(
            results=results,
            total_results=2,
            query_processed="Python developer",
            search_time_ms=100.0
        )
        
        csv_content = self.advanced_search_service._export_to_csv(
            results=results,
            search_response=search_response,
            include_metadata=True
        )
        
        assert "Candidate ID" in csv_content
        assert "Similarity Score" in csv_content
        assert "Python, Django" in csv_content
        assert "Senior" in csv_content
    
    def test_export_to_json(self):
        """Test exporting search results to JSON."""
        results = [
            SearchResult(
                candidate_id="1",
                similarity_score=0.8,
                matched_skills=["Python", "Django"],
                experience_level="Senior"
            )
        ]
        
        search_response = SearchResponse(
            results=results,
            total_results=1,
            query_processed="Python developer",
            search_time_ms=100.0
        )
        
        json_content = self.advanced_search_service._export_to_json(
            results=results,
            search_response=search_response,
            include_metadata=True
        )
        
        import json
        data = json.loads(json_content)
        
        assert "results" in data
        assert len(data["results"]) == 1
        assert data["results"][0]["candidate_id"] == "1"
        assert "metadata" in data
        assert data["metadata"]["search_query"] == "Python developer"