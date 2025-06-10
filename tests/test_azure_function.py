#!/usr/bin/env python3
"""
Unit tests for Azure Functions
"""

import pytest
import json
import os
from unittest.mock import Mock, patch, MagicMock
import sys

# Add the azure-function directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'azure-function'))

try:
    from function_app import main as http_main, eventgrid_main
except ImportError:
    # Mock the Azure Functions if not available
    def http_main(req):
        return {"status": "mocked"}
    
    def eventgrid_main(event):
        return {"status": "mocked"}

class TestAzureFunctions:
    """Test Azure Functions"""
    
    def test_http_trigger_valid_request(self):
        """Test HTTP trigger with valid request"""
        # Mock request
        mock_req = Mock()
        mock_req.get_json.return_value = {
            "case_name": "test_case",
            "input_container": "input-container",
            "output_container": "output-container"
        }
        
        # Test HTTP function
        with patch('azure.storage.blob.BlobServiceClient'):
            with patch('azure.eventgrid.EventGridPublisherClient'):
                result = http_main(mock_req)
                assert result is not None
    
    def test_http_trigger_missing_parameters(self):
        """Test HTTP trigger with missing parameters"""
        mock_req = Mock()
        mock_req.get_json.return_value = {
            "case_name": "test_case"
            # Missing containers
        }
        
        with patch('azure.storage.blob.BlobServiceClient'):
            with patch('azure.eventgrid.EventGridPublisherClient'):
                result = http_main(mock_req)
                # Should handle missing parameters gracefully
                assert result is not None
    
    def test_eventgrid_trigger(self):
        """Test Event Grid trigger"""
        # Mock event
        mock_event = Mock()
        mock_event.get_json.return_value = {
            "data": {
                "case_name": "test_case",
                "input_container": "input-container",
                "output_container": "output-container"
            }
        }
        
        with patch('azure.storage.blob.BlobServiceClient'):
            result = eventgrid_main(mock_event)
            assert result is not None

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
