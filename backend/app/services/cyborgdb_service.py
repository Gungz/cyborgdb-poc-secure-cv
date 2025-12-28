"""CyborgDB integration service for SecureHR application."""

import logging
import os

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from cyborgdb import Client
import asyncio
from concurrent.futures import ThreadPoolExecutor

from ..config import get_settings

logger = logging.getLogger(__name__)


class CyborgDBService:
    """Service for managing encrypted vector storage and search in CyborgDB."""
    
    def __init__(self):
        """Initialize CyborgDB service."""
        self.settings = get_settings()
        self._client: Optional[Client] = None
        self._index = None
        self._executor = ThreadPoolExecutor(max_workers=4)
        self.index_name = "securehr_cv_vecs"
    
    def _get_client(self) -> Client:
        """
        Get or create CyborgDB client.
        
        Returns:
            CyborgDB Client instance
        """
        if self._client is None:
            # Initialize CyborgDB client with configuration
            base_url = f"http://{self.settings.cyborgdb_host}:{self.settings.cyborgdb_port}"
            api_key = getattr(self.settings, 'cyborgdb_api_key', 'your-api-key')
            
            self._client = Client(
                base_url=base_url,
                api_key=api_key
            )
            logger.info(f"CyborgDB client initialized with base_url: {base_url}")
        return self._client
    
    def _get_index_key(self) -> bytes:
        """
        Get the index key from file specified in environment variable.
        
        Returns:
            Index key as bytes
            
        Raises:
            RuntimeError: If CYBORGDB_INDEX_KEY_FILE is not set or file cannot be read
        """
        key_file_path = os.getenv("CYBORGDB_INDEX_KEY_FILE")
        if not key_file_path:
            raise RuntimeError("CYBORGDB_INDEX_KEY_FILE environment variable is not set")
        
        try:
            with open(key_file_path, "rb") as key_file:
                index_key = key_file.read().strip()
            return index_key
        except FileNotFoundError:
            raise RuntimeError(f"Index key file not found: {key_file_path}")
        except Exception as e:
            raise RuntimeError(f"Failed to read index key file: {e}")
    
    async def _get_or_create_index(self):
        """
        Get or create the CyborgDB index for CV vectors.
        
        Returns:
            CyborgDB index instance
        """
        if self._index is None:
            client = self._get_client()
            loop = asyncio.get_event_loop()
            
            # Get index key from environment variable
            index_key = self._get_index_key()
            
            # First, check if the index exists by listing indexes
            index_exists = False
            try:
                indexes = await loop.run_in_executor(
                    self._executor,
                    lambda: client.list_indexes()
                )
                # Check if our index is in the list
                if indexes:
                    if self.index_name in indexes:
                        index_exists = True
                logger.info(f"Index exists check: {index_exists}, available indexes: {indexes}")
            except Exception as e:
                logger.warning(f"Could not list indexes, will try to load/create: {e}")
            
            if index_exists:
                # Load existing index
                try:
                    self._index = await loop.run_in_executor(
                        self._executor,
                        lambda: client.load_index(self.index_name, index_key)
                    )
                    logger.info(f"Loaded existing CyborgDB index: {self.index_name}")
                except Exception as e:
                    logger.error(f"Failed to load existing index {self.index_name}: {e}")
                    raise RuntimeError(f"Failed to load index: {e}")
            else:
                # Create new index
                logger.info(f"Index {self.index_name} not found, creating new one")
                
                # Use sentence-transformers model for automatic embedding generation
                embedding_model = self.settings.vector_model_name
                
                try:
                    self._index = await loop.run_in_executor(
                        self._executor,
                        lambda: client.create_index(
                            index_name=self.index_name,
                            index_key=index_key,
                            embedding_model=embedding_model,
                            metric="cosine"  # Use cosine similarity for CV matching
                        )
                    )
                    logger.info(f"Created new CyborgDB index: {self.index_name} with embedding model: {embedding_model}")
                except Exception as e:
                    logger.error(f"Failed to create index {self.index_name}: {e}")
                    raise RuntimeError(f"Failed to create index: {e}")
        
        return self._index
    
    async def store_vector(
        self, 
        cv_text: str,  # Store the original CV text instead of encrypted vector
        candidate_id: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Store CV text in CyborgDB with automatic embedding generation.
        
        Args:
            cv_text: Original CV text content
            candidate_id: ID of the candidate
            metadata: Optional metadata to store with vector
            
        Returns:
            Item ID in CyborgDB
            
        Raises:
            RuntimeError: If storage operation fails
        """
        try:
            index = await self._get_or_create_index()
            
            # Prepare metadata
            vector_metadata = {
                "candidate_id": candidate_id,
                "type": "cv_vector",
                **(metadata or {})
            }
            
            # Prepare item for upsert - CyborgDB will generate embeddings automatically
            item = {
                "id": candidate_id,  # Use candidate_id as the item ID
                "contents": cv_text,  # CyborgDB will generate embeddings from this
                "metadata": vector_metadata
            }
            
            # Store in CyborgDB using upsert
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self._executor,
                lambda: index.upsert([item])
            )
            
            logger.info(f"Stored CV text for candidate {candidate_id} in CyborgDB")
            return candidate_id  # Return the item ID
            
        except Exception as e:
            logger.error(f"Failed to store CV in CyborgDB: {e}")
            raise RuntimeError(f"CV storage failed: {str(e)}")
    
    async def retrieve_vector(self, item_id: str) -> Tuple[str, Dict[str, Any]]:
        """
        Retrieve CV data from CyborgDB.
        
        Args:
            item_id: CyborgDB item ID (candidate_id)
            
        Returns:
            Tuple of (cv_text, metadata)
            
        Raises:
            RuntimeError: If retrieval operation fails
        """
        try:
            index = await self._get_or_create_index()
            
            # Retrieve from CyborgDB
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                self._executor,
                lambda: index.get([item_id])
            )
            
            if not results or len(results) == 0:
                raise RuntimeError(f"Item {item_id} not found")
            
            item = results[0]
            cv_text = item.get("contents", "")
            metadata = item.get("metadata", {})
            
            logger.info(f"Retrieved CV data for item {item_id} from CyborgDB")
            return cv_text, metadata
            
        except Exception as e:
            logger.error(f"Failed to retrieve CV from CyborgDB: {e}")
            raise RuntimeError(f"CV retrieval failed: {str(e)}")
    
    async def delete_vector(self, item_id: str) -> bool:
        """
        Delete CV data from CyborgDB.
        
        Args:
            item_id: CyborgDB item ID (candidate_id)
            
        Returns:
            True if deletion was successful
            
        Raises:
            RuntimeError: If deletion operation fails
        """
        try:
            index = await self._get_or_create_index()
            
            # Delete from CyborgDB
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self._executor,
                lambda: index.delete([item_id])
            )
            
            logger.info(f"Deleted CV data for item {item_id} from CyborgDB")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete CV from CyborgDB: {e}")
            raise RuntimeError(f"CV deletion failed: {str(e)}")
    
    async def search_similar_vectors(
        self, 
        query_text: str,  # Use text query instead of vector
        limit: int = 10,
        exclude_candidate_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar CVs in CyborgDB using text query.
        
        Args:
            query_text: Job requirements text for search
            limit: Maximum number of results to return
            exclude_candidate_ids: Candidate IDs to exclude from results
            
        Returns:
            List of search results with similarity scores
            
        Raises:
            RuntimeError: If search operation fails
        """
        try:
            index = await self._get_or_create_index()
            
            # Prepare metadata filters to exclude specific candidates
            filters = None
            if exclude_candidate_ids:
                # Use metadata filtering to exclude candidates
                filters = {
                    "candidate_id": {"$nin": exclude_candidate_ids}
                }
            
            # Perform search using automatic embedding generation
            loop = asyncio.get_event_loop()
            search_results = await loop.run_in_executor(
                self._executor,
                lambda: index.query(
                    query_contents=query_text,  # CyborgDB will generate embeddings automatically
                    top_k=limit,
                    filters=filters,
                    include=["distance", "metadata", "contents"]
                )
            )
            
            # Process results
            processed_results = []
            for result in search_results:
                processed_result = {
                    "item_id": result.get("id"),
                    "similarity_score": 1.0 - float(result.get("distance", 1.0)),  # Convert distance to similarity
                    "metadata": result.get("metadata", {}),
                    "candidate_id": result.get("metadata", {}).get("candidate_id"),
                    "contents": result.get("contents", "")  # Include CV text if needed
                }
                processed_results.append(processed_result)
            
            logger.info(f"Found {len(processed_results)} similar CVs for query")
            return processed_results
            
        except Exception as e:
            logger.error(f"Failed to search CVs in CyborgDB: {e}")
            raise RuntimeError(f"CV search failed: {str(e)}")
    
    async def get_vector_count(self) -> int:
        """
        Get total number of CVs stored in CyborgDB.
        
        Returns:
            Total CV count (approximate)
        """
        try:
            # CyborgDB doesn't have a direct count method, so we'll estimate
            # by doing a broad search and counting results
            index = await self._get_or_create_index()
            
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                self._executor,
                lambda: index.query(
                    query_contents="experience skills",  # Generic query
                    top_k=1000,  # Large number to get approximate count
                    include=["distance"]
                )
            )
            
            return len(results)
            
        except Exception as e:
            logger.error(f"Failed to get CV count from CyborgDB: {e}")
            return 0
    
    async def health_check(self) -> bool:
        """
        Check if CyborgDB is healthy and accessible.
        
        Returns:
            True if CyborgDB is healthy
        """
        try:
            client = self._get_client()
            
            loop = asyncio.get_event_loop()
            health = await loop.run_in_executor(
                self._executor,
                lambda: client.get_health()
            )
            
            return health.get("status") == "ok"
            
        except Exception as e:
            logger.error(f"CyborgDB health check failed: {e}")
            return False