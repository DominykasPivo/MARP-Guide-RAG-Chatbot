import pytest
from unittest.mock import Mock, patch

from events import publish_event

class TestEvents:
    
    @patch('events.pika.BlockingConnection')
    def test_publish_event_success(self, mock_connection):
        """Test event publishing succeeds"""
        mock_channel = Mock()
        mock_conn_instance = Mock()
        mock_conn_instance.channel.return_value = mock_channel
        mock_connection.return_value = mock_conn_instance
        
        payload = {
            "queryId": "test-query-123",
            "query": "What is MARP?",
            "resultsCount": 3,
            "topScore": 0.95
        }
        
        result = publish_event("RetrievalCompleted", payload)
        
        assert result == True
        mock_channel.exchange_declare.assert_called_once_with(
            exchange='marp_events',
            exchange_type='topic',
            durable=True
        )
        mock_channel.basic_publish.assert_called_once()
        mock_conn_instance.close.assert_called_once()
    
    @patch('events.pika.BlockingConnection')
    def test_publish_event_failure(self, mock_connection):
        """Test event publishing handles failures"""
        mock_connection.side_effect = Exception("Connection failed")
        
        payload = {"queryId": "test-123", "query": "test"}
        result = publish_event("RetrievalCompleted", payload)
        
        assert result == False