"""Centralized logging configuration."""
import logging
import os
import json
from datetime import datetime

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
            record.correlation_id = 'no-correlation-id'
        return True

def setup_logger(service_name: str = 'retrieval'):
    """Set up application logging with correlation IDs.
    
    Args:
        service_name: Name of the service (for logger naming)
    Returns:
        The configured root logger
    """
    # Set up formatter
    human_formatter = CorrelationFormatter(
        '\033[32m%(asctime)s\033[0m [\033[1m%(levelname)s\033[0m] \033[36m%(correlation_id)s\033[0m - %(message)s'
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(human_formatter)
    console_handler.setLevel(logging.INFO)

    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Add correlation ID filter
    correlation_filter = CorrelationIDFilter()
    console_handler.addFilter(correlation_filter)

    # Remove existing handlers and add ours
    root_logger.handlers = []
    root_logger.addHandler(console_handler)

    return root_logger