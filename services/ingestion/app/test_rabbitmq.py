"""Test cases for RabbitMQ event publisher."""
import logging
import unittest
from datetime import datetime

from rabbitmq import EventPublisher
from events import DocumentDiscovered, EventTypes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class TestEventPublisher(unittest.TestCase):
    """Test suite for RabbitMQ event publisher."""
    
    def setUp(self):
        """Set up test environment before each test."""
        self.publisher = EventPublisher(host='localhost')
        
    def tearDown(self):
        """Clean up after each test."""
        if self.publisher:
            self.publisher.close()
            
    def test_connection(self):
        """Test RabbitMQ connection."""
        # Test initial connection
        self.assertTrue(self.publisher._ensure_connection())
        
    def test_publish_event(self):
        """Test publishing an event."""
        # Create a test event
        test_event = DocumentDiscovered(
            document_id="test123",
            title="Test Document",
            source_url="https://example.com/test.pdf",
            file_path="/test/path/doc.pdf",
            discovered_at=datetime.now().isoformat())
        
        # Publish the event
        result = self.publisher.publish_event(EventTypes.DOCUMENT_DISCOVERED, test_event)
        self.assertTrue(result, "Event publishing should succeed")
        
    def test_connection_failure(self):
        """Test behavior when connection fails."""
        # Force connection failure by setting incorrect host
        publisher = EventPublisher(host='nonexistent-host')
        self.assertIsNone(publisher.connection, "Connection should be None after failed connection attempt")
        
if __name__ == '__main__':
    unittest.main(verbosity=2)