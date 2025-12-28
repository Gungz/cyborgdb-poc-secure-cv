"""Advanced search service for SecureHR application."""

import json
import csv
import io
import hashlib
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import Counter
import uuid

from ..models.search import (
    SearchRequest, SearchResponse, SearchResult,
    SearchExportRequest, SearchExportResponse, SearchShareRequest, SearchShareResponse,
    SearchAnalytics, SearchPerformanceMetrics, ExportFormat
)

logger = logging.getLogger(__name__)


class SearchCache:
    """Simple in-memory search cache."""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        """
        Initialize search cache.
        
        Args:
            max_size: Maximum number of cached entries
            ttl_seconds: Time to live for cache entries in seconds
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.access_times: Dict[str, datetime] = {}
    
    def _generate_cache_key(self, search_request: SearchRequest) -> str:
        """
        Generate cache key from search request.
        
        Args:
            search_request: Search request to generate key for
            
        Returns:
            Cache key string
        """
        # Create a deterministic key from search parameters
        key_data = {
            "requirements": search_request.requirements,
            "filters": search_request.filters or {},
            "limit": search_request.limit or 10
        }
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def get(self, search_request: SearchRequest) -> Optional[Dict[str, Any]]:
        """
        Get cached search results.
        
        Args:
            search_request: Search request to look up
            
        Returns:
            Cached results or None if not found/expired
        """
        cache_key = self._generate_cache_key(search_request)
        
        if cache_key not in self.cache:
            return None
        
        # Check if entry has expired
        cached_time = self.access_times.get(cache_key)
        if cached_time and (datetime.utcnow() - cached_time).total_seconds() > self.ttl_seconds:
            # Remove expired entry
            del self.cache[cache_key]
            del self.access_times[cache_key]
            return None
        
        # Update access time
        self.access_times[cache_key] = datetime.utcnow()
        
        logger.info(f"Cache hit for search key: {cache_key[:8]}...")
        return self.cache[cache_key]
    
    def set(self, search_request: SearchRequest, results: Dict[str, Any]):
        """
        Cache search results.
        
        Args:
            search_request: Search request to cache
            results: Search results to cache
        """
        cache_key = self._generate_cache_key(search_request)
        
        # Remove oldest entries if cache is full
        if len(self.cache) >= self.max_size:
            # Remove oldest entry
            oldest_key = min(self.access_times.keys(), key=lambda k: self.access_times[k])
            del self.cache[oldest_key]
            del self.access_times[oldest_key]
        
        self.cache[cache_key] = results
        self.access_times[cache_key] = datetime.utcnow()
        
        logger.info(f"Cached search results for key: {cache_key[:8]}...")
    
    def clear(self):
        """Clear all cached entries."""
        self.cache.clear()
        self.access_times.clear()
        logger.info("Search cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Cache statistics
        """
        return {
            "total_entries": len(self.cache),
            "max_size": self.max_size,
            "ttl_seconds": self.ttl_seconds,
            "memory_usage_estimate_mb": len(json.dumps(self.cache).encode()) / (1024 * 1024)
        }


class AdvancedSearchService:
    """Service for advanced search features including caching, analytics, and export."""
    
    def __init__(self):
        """Initialize the advanced search service."""
        self.cache = SearchCache()
        self.search_history: List[Dict[str, Any]] = []
        self.performance_metrics = {
            "total_searches": 0,
            "cache_hits": 0,
            "total_response_time_ms": 0.0,
            "database_query_time_ms": 0.0,
            "vector_search_time_ms": 0.0
        }
    
    def record_search_execution(
        self,
        search_request: SearchRequest,
        results: SearchResponse,
        search_time_ms: float,
        cache_hit: bool = False,
        recruiter_id: Optional[str] = None
    ):
        """
        Record search execution for analytics.
        
        Args:
            search_request: The search request
            results: The search results
            search_time_ms: Search execution time
            cache_hit: Whether this was a cache hit
            recruiter_id: ID of the recruiter who performed the search
        """
        # Update performance metrics
        self.performance_metrics["total_searches"] += 1
        if cache_hit:
            self.performance_metrics["cache_hits"] += 1
        self.performance_metrics["total_response_time_ms"] += search_time_ms
        
        # Record in search history
        history_entry = {
            "recruiter_id": recruiter_id,
            "requirements": search_request.requirements,
            "filters": search_request.filters,
            "limit": search_request.limit,
            "results_count": len(results.results),
            "search_time_ms": search_time_ms,
            "cache_hit": cache_hit,
            "executed_at": datetime.utcnow(),
            "keywords": self._extract_keywords(search_request.requirements)
        }
        
        self.search_history.append(history_entry)
        
        # Keep only last 10000 entries to prevent memory issues
        if len(self.search_history) > 10000:
            self.search_history = self.search_history[-10000:]
        
        logger.info(f"Recorded search execution: {len(results.results)} results in {search_time_ms:.2f}ms")
    
    def _extract_keywords(self, requirements_text: str) -> List[str]:
        """
        Extract keywords from requirements text for analytics.
        
        Args:
            requirements_text: Job requirements text
            
        Returns:
            List of extracted keywords
        """
        # Simple keyword extraction - split on whitespace and filter
        words = requirements_text.lower().split()
        
        # Filter out common stop words and short words
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
            "by", "is", "are", "was", "were", "be", "been", "have", "has", "had", "do", "does",
            "did", "will", "would", "could", "should", "may", "might", "must", "can", "shall"
        }
        
        keywords = [
            word.strip(".,!?;:()[]{}\"'") for word in words
            if len(word) > 2 and word.lower() not in stop_words
        ]
        
        return keywords[:10]  # Return top 10 keywords
    
    def get_search_analytics(
        self,
        recruiter_id: Optional[str] = None,
        days_back: int = 30
    ) -> SearchAnalytics:
        """
        Get search analytics for a recruiter or globally.
        
        Args:
            recruiter_id: Recruiter ID to filter by (None for global analytics)
            days_back: Number of days to look back
            
        Returns:
            Search analytics
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        
        # Filter search history
        filtered_history = [
            entry for entry in self.search_history
            if entry["executed_at"] >= cutoff_date and
            (recruiter_id is None or entry.get("recruiter_id") == recruiter_id)
        ]
        
        if not filtered_history:
            return SearchAnalytics(
                total_searches=0,
                average_results_per_search=0.0,
                most_common_keywords=[],
                search_success_rate=0.0,
                average_search_time_ms=0.0,
                peak_search_hours=[],
                top_saved_searches=[]
            )
        
        # Calculate analytics
        total_searches = len(filtered_history)
        total_results = sum(entry["results_count"] for entry in filtered_history)
        successful_searches = sum(1 for entry in filtered_history if entry["results_count"] > 0)
        total_search_time = sum(entry["search_time_ms"] for entry in filtered_history)
        
        # Extract all keywords
        all_keywords = []
        for entry in filtered_history:
            all_keywords.extend(entry.get("keywords", []))
        
        # Get most common keywords
        keyword_counts = Counter(all_keywords)
        most_common_keywords = [keyword for keyword, _ in keyword_counts.most_common(10)]
        
        # Calculate peak search hours
        search_hours = [entry["executed_at"].hour for entry in filtered_history]
        hour_counts = Counter(search_hours)
        peak_search_hours = [hour for hour, _ in hour_counts.most_common(5)]
        
        return SearchAnalytics(
            total_searches=total_searches,
            average_results_per_search=total_results / total_searches if total_searches > 0 else 0.0,
            most_common_keywords=most_common_keywords,
            search_success_rate=successful_searches / total_searches if total_searches > 0 else 0.0,
            average_search_time_ms=total_search_time / total_searches if total_searches > 0 else 0.0,
            peak_search_hours=peak_search_hours,
            top_saved_searches=[]  # Would need saved search usage data
        )
    
    def get_performance_metrics(self) -> SearchPerformanceMetrics:
        """
        Get search performance metrics.
        
        Returns:
            Performance metrics
        """
        total_searches = self.performance_metrics["total_searches"]
        cache_stats = self.cache.get_stats()
        
        return SearchPerformanceMetrics(
            cache_hit_rate=self.performance_metrics["cache_hits"] / total_searches if total_searches > 0 else 0.0,
            average_response_time_ms=self.performance_metrics["total_response_time_ms"] / total_searches if total_searches > 0 else 0.0,
            total_cache_entries=cache_stats["total_entries"],
            cache_memory_usage_mb=cache_stats["memory_usage_estimate_mb"],
            database_query_time_ms=self.performance_metrics["database_query_time_ms"] / total_searches if total_searches > 0 else 0.0,
            vector_search_time_ms=self.performance_metrics["vector_search_time_ms"] / total_searches if total_searches > 0 else 0.0
        )
    
    def export_search_results(
        self,
        results: SearchResponse,
        export_request: SearchExportRequest,
        recruiter_id: str
    ) -> SearchExportResponse:
        """
        Export search results to specified format.
        
        Args:
            results: Search results to export
            export_request: Export configuration
            recruiter_id: ID of the recruiter requesting export
            
        Returns:
            Export response with download information
        """
        export_id = str(uuid.uuid4())
        
        # Limit results if requested
        export_results = results.results
        if export_request.max_results and len(export_results) > export_request.max_results:
            export_results = export_results[:export_request.max_results]
        
        # Generate export content based on format
        if export_request.format == ExportFormat.CSV:
            content = self._export_to_csv(export_results, results, export_request.include_metadata)
            filename = f"search_results_{export_id}.csv"
        elif export_request.format == ExportFormat.JSON:
            content = self._export_to_json(export_results, results, export_request.include_metadata)
            filename = f"search_results_{export_id}.json"
        elif export_request.format == ExportFormat.PDF:
            content = self._export_to_pdf(export_results, results, export_request.include_metadata)
            filename = f"search_results_{export_id}.pdf"
        else:
            raise ValueError(f"Unsupported export format: {export_request.format}")
        
        # In a real implementation, you would save the file to a storage service
        # For now, we'll simulate with a download URL
        download_url = f"/api/search/exports/{export_id}/download"
        expires_at = datetime.utcnow() + timedelta(hours=24)
        
        logger.info(f"Generated export {export_id} for recruiter {recruiter_id}: {len(export_results)} results")
        
        return SearchExportResponse(
            export_id=export_id,
            download_url=download_url,
            format=export_request.format,
            total_results=len(export_results),
            expires_at=expires_at
        )
    
    def _export_to_csv(
        self,
        results: List[SearchResult],
        search_response: SearchResponse,
        include_metadata: bool
    ) -> str:
        """Export results to CSV format."""
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        headers = ["Candidate ID", "Similarity Score", "Matched Skills", "Experience Level"]
        if include_metadata:
            headers.extend(["Search Query", "Total Results", "Search Time (ms)"])
        writer.writerow(headers)
        
        # Write data rows
        for result in results:
            row = [
                result.candidate_id,
                f"{result.similarity_score:.3f}",
                ", ".join(result.matched_skills or []),
                result.experience_level or "N/A"
            ]
            if include_metadata:
                row.extend([
                    search_response.query_processed,
                    search_response.total_results,
                    search_response.search_time_ms or 0
                ])
            writer.writerow(row)
        
        return output.getvalue()
    
    def _export_to_json(
        self,
        results: List[SearchResult],
        search_response: SearchResponse,
        include_metadata: bool
    ) -> str:
        """Export results to JSON format."""
        export_data = {
            "results": [result.dict() for result in results],
            "total_exported": len(results)
        }
        
        if include_metadata:
            export_data["metadata"] = {
                "search_query": search_response.query_processed,
                "total_results": search_response.total_results,
                "search_time_ms": search_response.search_time_ms,
                "exported_at": datetime.utcnow().isoformat()
            }
        
        return json.dumps(export_data, indent=2)
    
    def _export_to_pdf(
        self,
        results: List[SearchResult],
        search_response: SearchResponse,
        include_metadata: bool
    ) -> str:
        """Export results to PDF format (simplified - would use a PDF library in practice)."""
        # This is a simplified implementation
        # In practice, you would use a library like reportlab or weasyprint
        content = f"Search Results Export\n"
        content += f"=" * 50 + "\n\n"
        
        if include_metadata:
            content += f"Search Query: {search_response.query_processed}\n"
            content += f"Total Results: {search_response.total_results}\n"
            content += f"Search Time: {search_response.search_time_ms or 0:.2f}ms\n"
            content += f"Exported: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        content += f"Results ({len(results)} candidates):\n"
        content += "-" * 30 + "\n\n"
        
        for i, result in enumerate(results, 1):
            content += f"{i}. Candidate ID: {result.candidate_id}\n"
            content += f"   Similarity Score: {result.similarity_score:.3f}\n"
            if result.matched_skills:
                content += f"   Matched Skills: {', '.join(result.matched_skills)}\n"
            if result.experience_level:
                content += f"   Experience Level: {result.experience_level}\n"
            content += "\n"
        
        return content
    
    def share_search_results(
        self,
        results: SearchResponse,
        share_request: SearchShareRequest,
        recruiter_id: str
    ) -> SearchShareResponse:
        """
        Create a shareable link for search results.
        
        Args:
            results: Search results to share
            share_request: Share configuration
            recruiter_id: ID of the recruiter sharing results
            
        Returns:
            Share response with access information
        """
        share_id = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(days=share_request.expires_in_days)
        
        # In a real implementation, you would:
        # 1. Store the shared results in a database with the share_id
        # 2. Send emails to recipients with the share link
        # 3. Implement access control for the shared link
        
        share_url = f"/shared/search/{share_id}"
        
        logger.info(f"Created share {share_id} for recruiter {recruiter_id} with {len(share_request.recipient_emails)} recipients")
        
        return SearchShareResponse(
            share_id=share_id,
            share_url=share_url,
            expires_at=expires_at,
            recipients=share_request.recipient_emails
        )