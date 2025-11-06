"""RabbitMQ event consumer for extraction service with enhanced retry and recovery."""
import json
import time
import uuid
import random
from datetime import datetime
from typing import Callable, Optional, Dict, Any
import pika
from pika.exceptions import AMQPConnectionError, AMQPChannelError, AMQPError
from logging_config import setup_logger

# Configure logging
logger = setup_logger('extraction')

# Constants
EXCHANGE_NAME = 'document_events'
MAX_RETRIES = 5  # Increased for better resilience
INITIAL_RETRY_DELAY = 1  # Initial delay in seconds
MAX_RETRY_DELAY = 30  # Maximum delay in seconds
JITTER_RANGE = 0.1  # +/- 10% random jitter
CONSUMER_RECONNECT_DELAY = 5  # Delay before consumer reconnection attempts

class EventConsumer:
    """Handles consuming events from RabbitMQ."""
    
    def __init__(self, host: str = 'rabbitmq'):
        """Initialize the event consumer.
        
        Args:
            host: RabbitMQ host address (default: rabbitmq for Docker network)
        """
        self.host = host
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.channel.Channel] = None
        self.queue_name = None
        self.start_time = time.time()
        # Don't raise if initial connection fails
        try:
            self._connect()
        except AMQPConnectionError as e:
            logger.error(f"Failed to establish initial connection: {str(e)}")
        
    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate retry delay with exponential backoff and jitter.
        
        Args:
            attempt: The current retry attempt number (0-based)
            
        Returns:
            float: The delay to wait before the next retry in seconds
        """
        # Calculate exponential backoff
        delay = min(INITIAL_RETRY_DELAY * (2 ** attempt), MAX_RETRY_DELAY)
        
        # Add jitter
        jitter = delay * JITTER_RANGE
        delay += random.uniform(-jitter, jitter)
        
        return max(0, delay)  # Ensure non-negative delay

    def _connect(self) -> bool:
        """Establish connection to RabbitMQ with enhanced retry logic."""
        try:
            # Create connection parameters
            parameters = pika.ConnectionParameters(
                host=self.host,
                heartbeat=60,
                blocked_connection_timeout=30,
                connection_attempts=MAX_RETRIES,
                retry_delay=INITIAL_RETRY_DELAY
            )
            
            # Establish connection
            logger.info(f"Connecting to RabbitMQ at {self.host}...")
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
            return False

    def publish(self, routing_key: str, event_type: str, event_data: dict, correlation_id: str = None) -> bool:
        """Publish an event to RabbitMQ with retry logic.
        
        Args:
            routing_key: The routing key for the message
            event_type: The type of event being published
            event_data: The event data to publish
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
            logger.warning("No correlation ID provided for publishing, generating new one", extra={
                'correlation_id': correlation_id
            })

        for attempt in range(MAX_RETRIES):
            try:
                if not self.channel or self.channel.is_closed:
                    if not self._connect():
                        wait_time = self._calculate_retry_delay(attempt)
                        logger.warning(
                            f"Connection failed (attempt {attempt + 1}/{MAX_RETRIES}), "
                            f"retrying in {wait_time:.2f} seconds...",
                            extra={
                                'correlation_id': correlation_id,
                                'attempt': attempt + 1,
                                'wait_time': wait_time
                            }
                        )
                        time.sleep(wait_time)
                        continue

                # Create message with event type and data
                message = {
                    "event_type": event_type,
                    "data": event_data,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                # Publish message
                self.channel.basic_publish(
                    exchange=EXCHANGE_NAME,
                    routing_key=routing_key,
                    body=json.dumps(message),
                    properties=pika.BasicProperties(
                        delivery_mode=2,  # make message persistent
                        content_type='application/json',
                        correlation_id=correlation_id,
                        headers={'correlation_id': correlation_id}  # Add to headers for redundancy
                    )
                )
                logger.info(f"Successfully published {event_type} event", extra={
                    'routing_key': routing_key,
                    'event_type': event_type,
                    'correlation_id': correlation_id,
                    'attempt': attempt + 1
                })
                return True

            except (AMQPConnectionError, AMQPChannelError) as e:
                if attempt < MAX_RETRIES - 1:
                    wait_time = self._calculate_retry_delay(attempt)
                    logger.warning(
                        f"Failed to publish event (attempt {attempt + 1}/{MAX_RETRIES}). "
                        f"Retrying in {wait_time:.2f} seconds... Error: {str(e)}",
                        extra={
                            'correlation_id': correlation_id,
                            'event_type': event_type,
                            'attempt': attempt + 1,
                            'wait_time': wait_time,
                            'error': str(e)
                        }
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(
                        f"Failed to publish event after {MAX_RETRIES} attempts",
                        extra={
                            'correlation_id': correlation_id,
                            'event_type': event_type,
                            'error': str(e)
                        }
                    )
        
        return False

    def subscribe(self, event_type: str, callback: Callable) -> bool:
        """Subscribe to an event type with automatic reconnection.
        
        Args:
            event_type: Type of event to subscribe to
            callback: Function to call when event is received
            
        Returns:
            bool: True if successful, False otherwise
        """
        for attempt in range(MAX_RETRIES):
            try:
                if not self.channel or self.channel.is_closed:
                    if not self._connect():
                        wait_time = self._calculate_retry_delay(attempt)
                        logger.warning(
                            f"Connection failed (attempt {attempt + 1}/{MAX_RETRIES}), "
                            f"retrying in {wait_time:.2f} seconds..."
                        )
                        time.sleep(wait_time)
                        continue
                
                # Declare durable named queue
                self.queue_name = 'extraction_queue'
                self.channel.queue_declare(queue=self.queue_name, durable=True)
                
                # Bind queue to exchange
                self.channel.queue_bind(
                    exchange=EXCHANGE_NAME,
                    queue=self.queue_name,
                    routing_key=event_type
                )
                
                # Set up consumer with wrapped callback and enable automatic recovery
                self.channel.basic_consume(
                    queue=self.queue_name,
                    on_message_callback=lambda ch, method, props, body: self._handle_message(callback, ch, method, props, body),
                    auto_ack=False  # Changed to false for better reliability
                )
                
                logger.info(f"Successfully subscribed to {event_type} events")
                return True
                
            except (AMQPConnectionError, AMQPChannelError) as e:
                if attempt < MAX_RETRIES - 1:
                    wait_time = self._calculate_retry_delay(attempt)
                    logger.warning(
                        f"Failed to subscribe (attempt {attempt + 1}/{MAX_RETRIES}). "
                        f"Retrying in {wait_time:.2f} seconds... Error: {str(e)}"
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to subscribe after {MAX_RETRIES} attempts: {str(e)}")
        
        return False
            
    def _handle_message(self, callback: Callable, ch, method, props, body):
        """Handle a received message with improved error handling and acknowledgment.
        
        Args:
            callback: Function to call with the message
            ch: Channel
            method: Method frame
            props: Properties
            body: Message body
        """
        try:
            # Try to get correlation ID from various sources
            correlation_id = None
            
            # Parse message body
            message = json.loads(body)
            event_data = message.get('data', {})
            
            # Check message properties in order of precedence
            if props:
                # First try correlation_id property
                if props.correlation_id:
                    correlation_id = props.correlation_id
                # Then check headers
                elif props.headers and 'correlation_id' in props.headers:
                    correlation_id = props.headers['correlation_id']
            
            # Then try message body
            if not correlation_id and isinstance(message, dict) and 'correlation_id' in message:
                correlation_id = message['correlation_id']
            
            # Finally, if no correlation ID found, generate one
            if not correlation_id:
                correlation_id = str(uuid.uuid4())
                logger.warning("No correlation ID found in message, generated new one", extra={
                    'correlation_id': correlation_id
                })
            
            try:
                # Call with full message details
                callback(ch, method, props, body)
                
                # Acknowledge message only after successful processing
                ch.basic_ack(delivery_tag=method.delivery_tag)
                logger.debug("Message processed and acknowledged", extra={
                    'correlation_id': correlation_id
                })
            except Exception as e:
                # Reject message on processing error
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                logger.error(f"Error processing message, requeued: {str(e)}", extra={
                    'correlation_id': correlation_id,
                    'error': str(e)
                })

            # Update properties with correlation ID
            if not props:
                props = pika.BasicProperties(
                    correlation_id=correlation_id,
                    content_type='application/json',
                    delivery_mode=2
                )
            elif not props.correlation_id:
                props = pika.BasicProperties(
                    correlation_id=correlation_id,
                    content_type=props.content_type or 'application/json',
                    delivery_mode=2
                )

            logger.info("Received message", extra={
                'correlation_id': correlation_id,
                'routing_key': method.routing_key if method else None,
                'document_id': event_data.get('document_id')
            })
        except Exception as e:
            logger.error(f"Failed to handle message: {str(e)}", extra={'correlation_id': correlation_id})
            
    def start_consuming(self):
        """Start consuming messages."""
        try:
            if self.channel:
                logger.info("Starting to consume messages...")
                self.channel.start_consuming()
            else:
                logger.error("No channel available for consuming")
        except (AMQPConnectionError, AMQPChannelError) as e:
            logger.error(f"Error while consuming: {str(e)}")
            self.connection = None
            self.channel = None