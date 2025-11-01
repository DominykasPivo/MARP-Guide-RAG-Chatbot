"""RabbitMQ event publisher for ingestion service."""
import json
import logging
import time
from dataclasses import asdict
from typing import Optional
import pika
from pika.exceptions import AMQPConnectionError, AMQPChannelError, AMQPError
from events import DocumentDiscovered, EventTypes

# Configure logging
logger = logging.getLogger(__name__)

# Constants
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
EXCHANGE_NAME = 'document_events'

class EventPublisher:
    """Handles publishing events to RabbitMQ with automatic reconnection and retries."""
    
    def __init__(self, host: str = 'localhost'):
        """Initialize the event publisher.
        
        Args:
            host: RabbitMQ host address
        """
        self.host = host
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.channel.Channel] = None
        # Don't raise if initial connection fails
        try:
            self._connect()
        except AMQPError as e:
            logger.error(f"Failed to establish initial connection: {str(e)}")
        
    def _connect(self) -> bool:
        """Establish connection to RabbitMQ and set up exchange.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            if self.connection and not self.connection.is_closed:
                return True
                
            # Create connection with heartbeat and blocked connection timeouts
            parameters = pika.ConnectionParameters(
                host=self.host,
                heartbeat=60,  # Heartbeat every 60 seconds
                blocked_connection_timeout=30,
                connection_attempts=MAX_RETRIES,
                retry_delay=RETRY_DELAY
            )

            logger.info(f"Attempting to connect to RabbitMQ at {self.host}...")
            
            try:
                self.connection = pika.BlockingConnection(parameters)
                self.channel = self.connection.channel()
                
                # Declare exchange
                self.channel.exchange_declare(
                    exchange=EXCHANGE_NAME,
                    exchange_type='topic',
                    durable=True
                )
                
                logger.info("Successfully connected to RabbitMQ")
                return True
                
            except AMQPConnectionError as e:
                logger.error(f"Failed to connect to RabbitMQ: {str(e)}")
                self.connection = None
                self.channel = None
                return False
                
        except Exception as e:
            logger.error(f"Unexpected error connecting to RabbitMQ: {str(e)}")
            self.connection = None
            self.channel = None
            return False
                    
        return False
    
    def publish_event(self, event_type: EventTypes, event: DocumentDiscovered) -> bool:
        """Publish an event to RabbitMQ with retry logic.
        
        Args:
            event_type: Type of the event (from EventTypes enum)
            event: Event object to publish
            
        Returns:
            bool: True if message was published successfully, False otherwise
        """
        # Convert event to dictionary
        event_data = asdict(event)
        
        for attempt in range(MAX_RETRIES):
            try:
                # Ensure connection is alive
                if not self._ensure_connection():
                    continue

                # Publish the event
                self.channel.basic_publish(
                    exchange=EXCHANGE_NAME,
                    routing_key=event_type.value,
                    body=json.dumps(event_data),
                    properties=pika.BasicProperties(
                        delivery_mode=2,  # Make message persistent
                        content_type='application/json'
                    )
                )
                logger.info(f"Successfully published event: {event_type.value}")
                return True
                
            except (AMQPConnectionError, AMQPChannelError) as e:
                if attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_DELAY * (attempt + 1)
                    logger.warning(f"Failed to publish event (attempt {attempt + 1}/{MAX_RETRIES}). "
                                f"Retrying in {wait_time} seconds... Error: {str(e)}")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to publish event after {MAX_RETRIES} attempts: {str(e)}")
                    return False
                    
        return False
            
    def _ensure_connection(self) -> bool:
        """Ensure that the connection to RabbitMQ is active.
        
        Returns:
            bool: True if connection is active or successfully reconnected, False otherwise
        """
        try:
            if self.connection and not self.connection.is_closed:
                return True
            return self._connect()
        except AMQPError as e:
            logger.error(f"Connection check failed: {str(e)}")
            return False
            
    def close(self):
        """Close the connection to RabbitMQ."""
        if self.connection and not self.connection.is_closed:
            try:
                self.connection.close()
                logger.info("Closed RabbitMQ connection")
            except AMQPError as e:
                logger.error(f"Error closing RabbitMQ connection: {str(e)}")
        self.connection = None
        self.channel = None