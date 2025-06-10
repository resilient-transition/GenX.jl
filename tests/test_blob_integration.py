#!/usr/bin/env python3
"""
Integration tests for Azure Blob Storage operations
"""

import pytest
import os
import tempfile
import json
from unittest.mock import Mock, patch, MagicMock
import sys

# Add the scripts directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

class TestBlobIntegration:
    """Test Azure Blob Storage integration"""
    
    @pytest.fixture
    def mock_blob_service(self):
        """Mock Azure Blob Service Client"""
        with patch('azure.storage.blob.BlobServiceClient') as mock_client:
            mock_service = Mock()
            mock_client.return_value = mock_service
            
            # Mock container client
            mock_container = Mock()
            mock_service.get_container_client.return_value = mock_container
            
            # Mock blob client
            mock_blob = Mock()
            mock_container.get_blob_client.return_value = mock_blob
            
            yield mock_service
    
    def test_blob_upload(self, mock_blob_service):
        """Test blob upload functionality"""
        try:
            from upload_blob import upload_file_to_blob
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
                f.write('{"test": "data"}')
                temp_file = f.name
            
            try:
                # Test upload
                result = upload_file_to_blob(
                    account_name="testaccount",
                    container_name="test-container",
                    blob_name="test.json",
                    file_path=temp_file,
                    account_key="test_key"
                )
                assert result is not None
            finally:
                os.unlink(temp_file)
                
        except ImportError:
            # If upload_blob module doesn't exist, pass
            pytest.skip("upload_blob module not available")
    
    def test_blob_download(self, mock_blob_service):
        """Test blob download functionality"""
        try:
            from download_blob import download_blob_to_file
            
            # Mock blob data
            mock_blob_service.get_container_client().get_blob_client().download_blob().readall.return_value = b'{"test": "data"}'
            
            with tempfile.TemporaryDirectory() as temp_dir:
                output_file = os.path.join(temp_dir, "downloaded.json")
                
                result = download_blob_to_file(
                    account_name="testaccount",
                    container_name="test-container",
                    blob_name="test.json",
                    file_path=output_file,
                    account_key="test_key"
                )
                assert result is not None
                
        except ImportError:
            # If download_blob module doesn't exist, pass
            pytest.skip("download_blob module not available")
    
    def test_blob_operations_with_managed_identity(self, mock_blob_service):
        """Test blob operations using managed identity"""
        # Test that operations work without explicit credentials
        try:
            from upload_blob import upload_file_to_blob
            
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
                f.write('{"test": "data"}')
                temp_file = f.name
            
            try:
                # Test upload with managed identity (no account_key)
                with patch('azure.identity.DefaultAzureCredential'):
                    result = upload_file_to_blob(
                        account_name="testaccount",
                        container_name="test-container",
                        blob_name="test.json",
                        file_path=temp_file
                    )
                    assert result is not None
            finally:
                os.unlink(temp_file)
                
        except ImportError:
            pytest.skip("upload_blob module not available")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
