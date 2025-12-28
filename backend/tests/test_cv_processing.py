"""Tests for CV processing functionality."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi import UploadFile
import io

from app.services.cv_processor import CVProcessorService


class TestCVProcessorService:
    """Test cases for CV processor service."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cv_processor = CVProcessorService()

    def test_validate_file_valid_pdf(self):
        """Test file validation with valid PDF."""
        # Create mock UploadFile
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "test.pdf"
        mock_file.content_type = "application/pdf"
        mock_file.size = 1024 * 1024  # 1MB
        
        # Should not raise exception
        CVProcessorService.validate_file(mock_file)

    def test_validate_file_invalid_extension(self):
        """Test file validation with invalid extension."""
        from fastapi import HTTPException
        
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "test.txt"
        mock_file.content_type = "text/plain"
        mock_file.size = 1024
        
        with pytest.raises(HTTPException) as exc_info:
            CVProcessorService.validate_file(mock_file)
        
        assert exc_info.value.status_code == 400
        assert "not supported" in str(exc_info.value.detail)

    def test_validate_file_too_large(self):
        """Test file validation with oversized file."""
        from fastapi import HTTPException
        
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "test.pdf"
        mock_file.content_type = "application/pdf"
        mock_file.size = 20 * 1024 * 1024  # 20MB (over 10MB limit)
        
        with pytest.raises(HTTPException) as exc_info:
            CVProcessorService.validate_file(mock_file)
        
        assert exc_info.value.status_code == 413
        assert "exceeds maximum limit" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_extract_text_from_pdf_success(self):
        """Test successful PDF text extraction."""
        # Create a simple PDF content (mock)
        pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"
        
        with patch('app.services.cv_processor.PyPDF2.PdfReader') as mock_reader:
            # Mock PDF reader
            mock_page = Mock()
            mock_page.extract_text.return_value = "This is a test CV with experience in software development."
            
            mock_pdf = Mock()
            mock_pdf.pages = [mock_page]
            mock_reader.return_value = mock_pdf
            
            result = await CVProcessorService.extract_text_from_pdf(pdf_content)
            
            assert result == "This is a test CV with experience in software development."

    @pytest.mark.asyncio
    async def test_extract_text_from_docx_success(self):
        """Test successful DOCX text extraction."""
        docx_content = b"PK\x03\x04"  # Mock DOCX header
        
        with patch('app.services.cv_processor.Document') as mock_document:
            # Mock document
            mock_paragraph = Mock()
            mock_paragraph.text = "This is a test CV with experience in software development."
            
            mock_doc = Mock()
            mock_doc.paragraphs = [mock_paragraph]
            mock_doc.tables = []
            mock_document.return_value = mock_doc
            
            result = await CVProcessorService.extract_text_from_docx(docx_content)
            
            assert result == "This is a test CV with experience in software development."

    @pytest.mark.asyncio
    async def test_extract_text_success(self):
        """Test complete text extraction workflow."""
        # Create mock file
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "test.pdf"
        mock_file.content_type = "application/pdf"
        mock_file.size = 1024
        mock_file.read = AsyncMock(return_value=b"mock pdf content")
        mock_file.seek = AsyncMock()
        
        with patch.object(CVProcessorService, 'extract_text_from_pdf') as mock_extract:
            mock_extract.return_value = "This is a test CV with experience in software development and project management skills."
            
            text, file_hash = await CVProcessorService.extract_text(mock_file)
            
            assert len(text) > 50  # Should pass minimum length validation
            assert file_hash is not None
            assert len(file_hash) == 64  # SHA256 hash length

    @pytest.mark.asyncio
    async def test_extract_text_too_short(self):
        """Test text extraction with content too short."""
        from fastapi import HTTPException
        
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "test.pdf"
        mock_file.content_type = "application/pdf"
        mock_file.size = 1024
        mock_file.read = AsyncMock(return_value=b"mock pdf content")
        mock_file.seek = AsyncMock()
        
        with patch.object(CVProcessorService, 'extract_text_from_pdf') as mock_extract:
            mock_extract.return_value = "Short"  # Too short
            
            with pytest.raises(HTTPException) as exc_info:
                await CVProcessorService.extract_text(mock_file)
            
            assert exc_info.value.status_code == 400
            assert "too short" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_process_cv_complete_success(self):
        """Test complete CV processing pipeline."""
        from sqlalchemy.orm import Session
        
        # Mock dependencies
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "test.pdf"
        
        mock_db = Mock(spec=Session)
        mock_db.add = Mock()
        mock_db.commit = Mock()
        
        candidate_id = "test-candidate-123"
        
        # Mock the extract_text method
        with patch.object(self.cv_processor, 'extract_text') as mock_extract:
            mock_extract.return_value = ("This is a comprehensive CV with extensive experience in software development.", "abc123hash")
            
            # Mock CyborgDB service
            with patch.object(self.cv_processor.cyborgdb_service, 'store_vector') as mock_store:
                mock_store.return_value = candidate_id
                
                result = await self.cv_processor.process_cv_complete(
                    file=mock_file,
                    candidate_id=candidate_id,
                    db=mock_db
                )
                
                assert result == candidate_id
                mock_db.add.assert_called_once()
                mock_db.commit.assert_called_once()
                mock_store.assert_called_once()