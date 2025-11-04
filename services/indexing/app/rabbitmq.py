import pika
import json
import os
from threading import Thread

RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'rabbitmq')
EXCHANGE_NAME = 'document_events'
QUEUE_NAME = 'indexing_queue'
ROUTING_KEY = 'document.extracted'

class RabbitMQConsumer(Thread):
    def __init__(self, callback):
        super().__init__(daemon=True)
        self.callback = callback
        self.connection = None
        self.channel = None

    def run(self):
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        self.channel = self.connection.channel()
        self.channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type='topic', durable=True)
        self.channel.queue_declare(queue=QUEUE_NAME, durable=True)
        self.channel.queue_bind(exchange=EXCHANGE_NAME, queue=QUEUE_NAME, routing_key=ROUTING_KEY)
        self.channel.basic_consume(queue=QUEUE_NAME, on_message_callback=self.on_message, auto_ack=True)
        print(f"[*] Waiting for '{ROUTING_KEY}' events. To exit press CTRL+C")
        self.channel.start_consuming()

    def on_message(self, ch, method, properties, body):
        try:
            message = json.loads(body)
            self.callback(message)
        except Exception as e:
            print(f"[!] Error processing message: {e}")

# Example usage in your Flask app:
# from rabbitmq import RabbitMQConsumer
# def handle_extracted_event(event):
#     print("Received event:", event)
# consumer = RabbitMQConsumer(handle_extracted_event)
# consumer.start()
