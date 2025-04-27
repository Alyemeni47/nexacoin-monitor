"""
Logging configuration for the NexaCoin Monitor Bot
"""
import os
import logging
import logging.handlers
import sys
from datetime import datetime

from utils import redact_sensitive_data

class SensitiveDataFilter(logging.Filter):
    """Filter to redact sensitive information from logs"""
    
    def filter(self, record):
        if isinstance(record.msg, str):
            record.msg = redact_sensitive_data(record.msg)
        return True

def setup_logging():
    """Configure logging for the application"""
    # Get logging level from environment or use INFO as default
    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    
    # Get log file path from environment or use default
    log_file = os.getenv("LOG_FILE", "nexacoin_monitor.log")
    
    # Create logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Create the sensitive data filter
    sensitive_filter = SensitiveDataFilter()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    console_handler.addFilter(sensitive_filter)
    root_logger.addHandler(console_handler)
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    file_handler.addFilter(sensitive_filter)
    root_logger.addHandler(file_handler)
    
    # Log startup information
    logger = logging.getLogger(__name__)
    logger.info("=" * 80)
    logger.info(f"NexaCoin Monitor Bot starting at {datetime.now().isoformat()}")
    logger.info(f"Log level set to {log_level_name}")
    logger.info("=" * 80)
    
    return root_logger
