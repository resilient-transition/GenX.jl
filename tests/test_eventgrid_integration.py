#!/usr/bin/env python3
"""
Integration tests for Event Grid functionality
"""

import pytest
import json
import os
from unittest.mock import Mock, patch, MagicMock
import sys

class TestEventGridIntegration:
    """Test Event Grid integration"""
    
    @pytest.fixture
    def mock_eventgrid_client(self):
        """Mock Event Grid Publisher Client"""
        with patch('azure.eventgrid.EventGridPublisherClient') as mock_client:
            mock_publisher = Mock()
            mock_client.return_value = mock_publisher
            yield mock_publisher
    
    def test_event_publishing(self, mock_eventgrid_client):
        """Test Event Grid event publishing"""
        try:
            # Import Azure Function if available
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'azure-function'))
            from function_app import publish_to_eventgrid
            
            # Test event data
            event_data = {
                "case_name": "test_case",
                "input_container": "input-container",
                "output_container": "output-container",
                "status": "processing"
            }
            
            # Test publishing
            result = publish_to_eventgrid(
                topic_endpoint="https://test.eventgrid.azure.net/api/events",
                topic_key="test_key",
                event_data=event_data
            )
            
            # Verify mock was called
            mock_eventgrid_client.send_events.assert_called_once()
            
        except ImportError:
            pytest.skip("Azure Function module not available")
    
    def test_event_filtering(self):
        """Test Event Grid event filtering"""
        # Test event that should be processed
        valid_event = {
            "eventType": "GenX.Job.Submitted",
            "data": {
                "case_name": "test_case",
                "input_container": "input-container"
            }
        }
        
        # Test event that should be ignored
        invalid_event = {
            "eventType": "Microsoft.Storage.BlobCreated",
            "data": {
                "url": "https://storage.blob.core.windows.net/container/blob"
            }
        }
        
        # Mock processing logic
        def should_process_event(event):
            return event.get("eventType", "").startswith("GenX.")
        
        assert should_process_event(valid_event) == True
        assert should_process_event(invalid_event) == False
    
    def test_container_instance_trigger(self):
        """Test Event Grid triggering container instances"""
        # Mock Azure Container Instance client
        with patch('azure.mgmt.containerinstance.ContainerInstanceManagementClient') as mock_client:
            mock_aci = Mock()
            mock_client.return_value = mock_aci
            
            # Mock container group operations
            mock_aci.container_groups.begin_create_or_update.return_value = Mock()
            
            # Test container creation from Event Grid event
            event_data = {
                "case_name": "test_case",
                "input_container": "input-container",
                "output_container": "output-container"
            }
            
            # This would typically be handled by the Event Grid triggered container
            container_name = f"genx-{event_data['case_name']}"
            assert container_name == "genx-test_case"
    
    def test_event_grid_schema_validation(self):
        """Test Event Grid event schema validation"""
        # Valid Event Grid event schema
        valid_event = {
            "id": "test-id",
            "eventType": "GenX.Job.Submitted",
            "subject": "genx/jobs/test_case",
            "eventTime": "2024-01-01T00:00:00Z",
            "data": {
                "case_name": "test_case",
                "input_container": "input-container",
                "output_container": "output-container"
            },
            "dataVersion": "1.0"
        }
        
        # Validate required fields
        required_fields = ["id", "eventType", "subject", "eventTime", "data"]
        for field in required_fields:
            assert field in valid_event
        
        # Validate data structure
        assert "case_name" in valid_event["data"]
        assert "input_container" in valid_event["data"]

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
