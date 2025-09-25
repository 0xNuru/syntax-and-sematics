"""
Logging configuration for outbound AI agent.
Provides structured, environment-aware logging with configurable levels.
"""

import logging
import sys
import os
from datetime import datetime
from typing import Optional


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for different log levels"""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green  
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'       # Reset
    }
    
    def format(self, record):
        # Add color to levelname
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.COLORS['RESET']}"
        
        return super().format(record)


def setup_logging(
    level: Optional[str] = None,
    log_file: Optional[str] = None,
    environment: Optional[str] = None
) -> logging.Logger:
    """
    Setup logging configuration based on environment
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for file logging
        environment: Environment name (development, staging, production)
    
    Returns:
        Configured logger instance
    """
    # Get configuration from environment if not provided
    level = level or os.getenv("LOG_LEVEL", "INFO")
    environment = environment or os.getenv("ENVIRONMENT", "development")
    log_file = log_file or os.getenv("LOG_FILE")
    
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create root logger
    logger = logging.getLogger("outbound_ai_agent")
    logger.setLevel(numeric_level)
    
    # Clear any existing handlers and prevent propagation
    logger.handlers.clear()
    logger.propagate = False
    
    # Console handler with colors (for development)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    
    if environment == "development":
        # Colored, detailed format for development
        console_formatter = ColoredFormatter(
            '%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s',
            datefmt='%H:%M:%S'
        )
    else:
        # Structured format for production
        console_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        try:
            # Ensure log directory exists
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(numeric_level)
            
            # Structured format for file logging
            file_formatter = logging.Formatter(
                '%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(funcName)s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
            
        except Exception as e:
            logger.warning(f"Failed to setup file logging to {log_file}: {e}")
    
    # Set specific logger levels for noisy libraries
    logging.getLogger("urllib3").setLevel(logging.INFO)
    logging.getLogger("aiohttp").setLevel(logging.INFO)
    logging.getLogger("livekit").setLevel(logging.DEBUG)
    # Temporarily disable verbose Whispey logging
    logging.getLogger("whispey-sdk").setLevel(logging.WARNING)
    
    # Log startup information
    logger.info(f"🚀 Logging initialized - Level: {level.upper()}, Environment: {environment}")
    if log_file:
        logger.info(f"📁 File logging enabled: {log_file}")
    
    return logger


def get_logger(name: str = None) -> logging.Logger:
    """
    Get a logger instance for a specific module
    
    Args:
        name: Logger name (usually __name__)
    
    Returns:
        Logger instance
    """
    if name:
        return logging.getLogger(f"outbound_ai_agent.{name}")
    return logging.getLogger("outbound_ai_agent")


# Create module-level loggers for easy import
logger = get_logger()


# Convenience functions for common logging patterns
def log_call_event(event: str, phone_number: str = None, duration: int = None, room_name: str = None):
    """Log call lifecycle events with consistent formatting"""
    parts = [f"📞 {event}"]
    if phone_number:
        parts.append(f"Number: {phone_number}")
    if duration is not None:
        parts.append(f"Duration: {duration}s")
    if room_name:
        parts.append(f"Room: {room_name}")
    
    logger.info(" | ".join(parts))


def log_webhook_event(event: str, url: str, status: int = None, room_name: str = None):
    """Log webhook events with consistent formatting"""
    parts = [f"📡 {event}"]
    if room_name:
        parts.append(f"Room: {room_name}")
    parts.append(f"URL: {url}")
    if status is not None:
        parts.append(f"Status: {status}")
    
    if status and 200 <= status < 300:
        logger.info(" | ".join(parts))
    else:
        logger.error(" | ".join(parts))


def log_cost_event(event: str, total_cost: float = None, currency: str = "NGN", room_name: str = None):
    """Log cost-related events with consistent formatting"""
    parts = [f"💰 {event}"]
    if room_name:
        parts.append(f"Room: {room_name}")
    if total_cost is not None:
        parts.append(f"Total: {currency}{total_cost:.2f}")
    
    logger.info(" | ".join(parts))


def log_provider_event(event: str, providers: dict = None):
    """Log provider detection events with consistent formatting"""
    parts = [f"🔧 {event}"]
    if providers:
        provider_list = [f"{k.upper()}={v}" for k, v in providers.items()]
        parts.append(" | ".join(provider_list))
    
    logger.info(" | ".join(parts)) 