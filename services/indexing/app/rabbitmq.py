import pika
import json
import os
from threading import Thread
import logging

logger = logging.getLogger("indexing.rabbitmq")

RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'rabbitmq')
EXCHANGE_NAME = 'document_events'
QUEUE_NAME = 'indexing_queue'
ROUTING_KEY = 'document.extracted'

class EventConsumer(Thread):
    def __init__(self, event_type, callback):
        super().__init__(daemon=True)
        self.event_type = event_type
        self.callback = callback
        self.connection = None
        self.channel = None

    def run(self):
        try:
            self.connection = pika.BlockingConnection(pika.ConnectionParameters(
                host=RABBITMQ_HOST,
                heartbeat=600,
                blocked_connection_timeout=300
            ))
            self.channel = self.connection.channel()
            self.channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type='topic', durable=True)
            
            # Declare queue with arguments
            self.channel.queue_declare(queue=QUEUE_NAME, durable=True)
            
            self.channel.queue_bind(
                exchange=EXCHANGE_NAME, 
                queue=QUEUE_NAME, 
                routing_key=ROUTING_KEY
            )
            
            self.channel.basic_consume(
                queue=QUEUE_NAME, 
                on_message_callback=self.on_message, 
                auto_ack=False  # Change to manual acknowledgment
            )
            
            logger.info(f"🔄 Waiting for '{ROUTING_KEY}' events...")
            self.channel.start_consuming()
            
        except Exception as e:
            logger.error(f"❌ RabbitMQ consumer error: {e}")
            if self.connection:
                self.connection.close()

    def on_message(self, ch, method, properties, body):
        try:
            logger.info(f"📥 Received message with routing key: {method.routing_key}")
            logger.info(f"📦 Message properties: {properties.headers if properties.headers else 'No headers'}")
            
            # Parse the message
            if isinstance(body, bytes):
                body = body.decode('utf-8')
            
            message = json.loads(body)
            logger.info(f"✅ Successfully parsed JSON message")
            
            # Process the message
            self.callback(message)
            
            # Acknowledge the message after successful processing
            ch.basic_ack(delivery_tag=method.delivery_tag)
            logger.info(f"✅ Processed and acknowledged message")
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse JSON: {e}, raw body: {body}")
            # Reject the message without requeue
            ch.basic_reject(delivery_tag=method.delivery_tag, requeue=False)
        except Exception as e:
            logger.error(f"❌ Error processing message: {e}")
            # Reject the message and requeue for retry
            ch.basic_reject(delivery_tag=method.delivery_tag, requeue=True)
