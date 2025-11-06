"""Centralized logging configuration."""
import logging
import os
import json
from flask import g

class CorrelationFormatter(logging.Formatter):
    """Custom formatter that handles missing correlation_id gracefully."""
    def format(self, record):
        if not hasattr(record, 'correlation_id'):
            record.correlation_id = 'no-correlation-id'
        return super().format(record)

class CorrelationIDFilter(logging.Filter):
    """Filter that injects correlation ID into log records."""
    def filter(self, record):
        if not hasattr(record, 'correlation_id'):
            try:
                # Try getting correlation ID from Flask's g
                record.correlation_id = getattr(g, 'correlation_id', 'no-correlation-id')
            except:
                # Default value for non-Flask/missing context
                record.correlation_id = 'no-correlation-id'
        return True

class JsonFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    def __init__(self):
        super().__init__()
        self.default_keys = ['timestamp', 'level', 'correlation_id', 'message', 'logger']

    def format(self, record):
        log_data = {
            'timestamp': self.formatTime(record, datefmt='%Y-%m-%d %H:%M:%S'),
            'level': record.levelname,
            'correlation_id': getattr(record, 'correlation_id', 'no-correlation-id'),
            'message': record.getMessage(),
            'logger': record.name
        }

        # Add extra fields from the record, but only if they are JSON serializable
        for key, value in record.__dict__.items():
            if key not in self.default_keys and not key.startswith('_'):
                try:
                    # Try to serialize the value to verify it's JSON compatible
                    json.dumps({key: value})
                    log_data[key] = value
                except (TypeError, ValueError, OverflowError):
                    # If serialization fails, convert the value to a string representation
                    log_data[key] = str(value)

        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_data)

def setup_logger(service_name: str = 'ingestion'):
    """Set up application logging with correlation IDs and human-readable formatting to stdout/stderr only.
    Args:
        service_name: Name of the service (for logger naming)
    Returns:
        The configured root logger
    """
    # Set up formatter
    human_formatter = CorrelationFormatter(
        '\033[32m%(asctime)s\033[0m [\033[1m%(levelname)s\033[0m] \033[36m%(correlation_id)s\033[0m - %(message)s'
    )

    # Console handler (human-readable format with colors)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(human_formatter)
    console_handler.setLevel(logging.INFO)

    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Add correlation ID filter to handler
    correlation_filter = CorrelationIDFilter()
    console_handler.addFilter(correlation_filter)

    # Remove any existing handlers and add our new one
    root_logger.handlers = []
    root_logger.addHandler(console_handler)

    return root_logger