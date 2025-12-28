"""Vector generation and encryption service for SecureHR application."""

import hashlib
import logging
from typing import List, Optional
import numpy as np
from sentence_transformers import SentenceTransformer
import base64
import json

logger = logging.getLogger(__name__)


class VectorService:
    """Service for generating and encrypting CV vectors."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the vector service with a sentence transformer model.
        
        Args:
            model_name: Name of the sentence transformer model to use
        """
        self.model_name = model_name
        self._model: Optional[SentenceTransformer] = None
        self._encryption_key: Optional[bytes] = None
    
    def _get_model(self) -> SentenceTransformer:
        """
        Lazy load the sentence transformer model.
        
        Returns:
            Loaded sentence transformer model
        """
        if self._model is None:
            logger.info(f"Loading sentence transformer model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
            logger.info("Model loaded successfully")
        return self._model
    
    def _get_encryption_key(self) -> bytes:
        """
        Get or generate encryption key for vector encryption.
        
        In production, this should be loaded from secure key management.
        For now, we'll generate a deterministic key based on a secret.
        
        Returns:
            Encryption key bytes
        """
        if self._encryption_key is None:
            # In production, load from environment or key management service
            secret = "securehr_vector_encryption_key_2024"  # This should be from config
            key_material = hashlib.sha256(secret.encode()).digest()
            self._encryption_key = base64.urlsafe_b64encode(key_material)
        return self._encryption_key
    
    def generate_vector(self, text: str) -> np.ndarray:
        """
        Generate vector embedding from text content.
        
        Args:
            text: Input text to vectorize
            
        Returns:
            Vector embedding as numpy array
            
        Raises:
            ValueError: If text is empty or invalid
            RuntimeError: If vector generation fails
        """
        if not text or not text.strip():
            raise ValueError("Text content cannot be empty")
        
        try:
            model = self._get_model()
            
            # Preprocess text - remove excessive whitespace and normalize
            cleaned_text = " ".join(text.strip().split())
            
            # Generate embedding
            vector = model.encode(cleaned_text, convert_to_numpy=True)
            
            # Ensure vector is normalized (unit length)
            vector_norm = np.linalg.norm(vector)
            if vector_norm > 0:
                vector = vector / vector_norm
            
            logger.info(f"Generated vector with dimensions: {vector.shape}")
            return vector
            
        except Exception as e:
            logger.error(f"Vector generation failed: {e}")
            raise RuntimeError(f"Failed to generate vector: {str(e)}")
    
    def encrypt_vector(self, vector: np.ndarray, candidate_id: str) -> str:
        """
        Encrypt vector for secure storage.
        
        Args:
            vector: Vector to encrypt
            candidate_id: ID of the candidate (used for additional entropy)
            
        Returns:
            Base64 encoded encrypted vector data
            
        Raises:
            ValueError: If vector is invalid
            RuntimeError: If encryption fails
        """
        if vector is None or vector.size == 0:
            raise ValueError("Vector cannot be empty")
        
        try:
            # For now, we'll use a simple base64 encoding as a placeholder
            # In production, implement proper encryption using cryptography library
            vector_data = {
                "vector": vector.tolist(),
                "dimensions": int(vector.shape[0]),
                "candidate_id": candidate_id,
                "model": self.model_name
            }
            
            # Serialize and encode (placeholder for encryption)
            vector_json = json.dumps(vector_data, separators=(',', ':'))
            encoded_data = base64.b64encode(vector_json.encode()).decode('utf-8')
            
            logger.info(f"Encoded vector for candidate {candidate_id}")
            return encoded_data
            
        except Exception as e:
            logger.error(f"Vector encoding failed: {e}")
            raise RuntimeError(f"Failed to encode vector: {str(e)}")
    
    def decrypt_vector(self, encrypted_vector: str, expected_candidate_id: str) -> np.ndarray:
        """
        Decrypt vector from storage.
        
        Args:
            encrypted_vector: Base64 encoded encrypted vector
            expected_candidate_id: Expected candidate ID for validation
            
        Returns:
            Decrypted vector as numpy array
            
        Raises:
            ValueError: If encrypted data is invalid
            RuntimeError: If decryption fails
            SecurityError: If candidate ID doesn't match
        """
        if not encrypted_vector:
            raise ValueError("Encrypted vector cannot be empty")
        
        try:
            # Create decryption cipher
            key = self._get_encryption_key()
            cipher = Fernet(key)
            
            # Decode and decrypt
            encrypted_data = base64.b64decode(encrypted_vector.encode())
            decrypted_json = cipher.decrypt(encrypted_data).decode('utf-8')
            
            # Parse decrypted data
            vector_data = json.loads(decrypted_json)
            
            # Validate candidate ID
            if vector_data.get("candidate_id") != expected_candidate_id:
                raise SecurityError("Candidate ID mismatch in encrypted vector")
            
            # Reconstruct vector
            vector_list = vector_data["vector"]
            vector = np.array(vector_list, dtype=np.float32)
            
            logger.info(f"Decrypted vector for candidate {expected_candidate_id}")
            return vector
            
        except Exception as e:
            logger.error(f"Vector decryption failed: {e}")
            raise RuntimeError(f"Failed to decrypt vector: {str(e)}")
    
    def generate_search_vector(self, requirements_text: str) -> np.ndarray:
        """
        Generate search vector from job requirements text.
        
        Args:
            requirements_text: Job requirements text
            
        Returns:
            Search vector as numpy array
        """
        # Use the same vector generation process for consistency
        return self.generate_vector(requirements_text)
    
    def calculate_similarity(self, vector1: np.ndarray, vector2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two vectors.
        
        Args:
            vector1: First vector
            vector2: Second vector
            
        Returns:
            Similarity score between 0 and 1
        """
        try:
            # Ensure vectors are normalized
            v1_norm = vector1 / np.linalg.norm(vector1)
            v2_norm = vector2 / np.linalg.norm(vector2)
            
            # Calculate cosine similarity
            similarity = np.dot(v1_norm, v2_norm)
            
            # Ensure result is between 0 and 1
            similarity = max(0.0, min(1.0, float(similarity)))
            
            return similarity
            
        except Exception as e:
            logger.error(f"Similarity calculation failed: {e}")
            return 0.0


class SecurityError(Exception):
    """Custom exception for security-related errors."""
    pass