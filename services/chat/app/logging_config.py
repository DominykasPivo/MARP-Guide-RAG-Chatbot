import logging
import sys
from pythonjsonlogger import jsonlogger

def setup_logger(name: str) -> logging.Logger:
    """Set up structured JSON logging.
    
    Args:
        name: Logger name (e.g., 'chat', 'chat.llm')
        
    Returns:
        logging.Logger: Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Remove existing handlers
    logger.handlers = []
    
    # Create console handler with JSON formatter
    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(name)s %(levelname)s %(message)s',
        timestamp=True
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger