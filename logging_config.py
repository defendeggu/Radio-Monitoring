"""
Centralized Logging Configuration for Radio Monitoring System

Provides structured JSON logging for better integration with ELK stack.
Includes correlation IDs for request tracing and consistent log formatting.
"""

import logging
import logging.config
import uuid
from typing import Optional
from contextvars import ContextVar
from pythonjsonlogger import jsonlogger

# Context variable for request correlation ID
correlation_id_ctx: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)


class CorrelationIdFilter(logging.Filter):
    """Add correlation ID to log records for request tracing"""

    def filter(self, record):
        """Add correlation_id to log record"""
        record.correlation_id = correlation_id_ctx.get() or 'N/A'
        return True


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields"""

    def add_fields(self, log_record, record, message_dict):
        """Add custom fields to JSON log output"""
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)

        # Add timestamp in ISO format
        if not log_record.get('timestamp'):
            log_record['timestamp'] = self.formatTime(record, self.datefmt)

        # Add service name
        log_record['service'] = 'radio-monitoring'

        # Add severity level
        log_record['severity'] = record.levelname

        # Add logger name
        log_record['logger'] = record.name

        # Add correlation ID
        log_record['correlation_id'] = getattr(record, 'correlation_id', 'N/A')

        # Add source location
        log_record['source'] = {
            'file': record.filename,
            'line': record.lineno,
            'function': record.funcName
        }


def setup_logging(log_level: str = 'INFO', json_format: bool = True):
    """
    Configure logging for the application

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: Use JSON format (True) or plain text (False)
    """

    if json_format:
        # JSON format for ELK stack
        formatter = CustomJsonFormatter(
            '%(timestamp)s %(severity)s %(logger)s %(message)s',
            datefmt='%Y-%m-%dT%H:%M:%S'
        )
    else:
        # Plain text format for development
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - [%(correlation_id)s] - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    # Configure root logger
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.addFilter(CorrelationIdFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    root_logger.handlers = []
    root_logger.addHandler(handler)

    # Suppress noisy third-party loggers
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('elasticsearch').setLevel(logging.WARNING)
    logging.getLogger('elastic_transport').setLevel(logging.WARNING)
    logging.getLogger('docker').setLevel(logging.WARNING)

    return root_logger


def set_correlation_id(correlation_id: Optional[str] = None):
    """
    Set correlation ID for current context (request/task)

    Args:
        correlation_id: Custom correlation ID or None to generate UUID
    """
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
    correlation_id_ctx.set(correlation_id)
    return correlation_id


def get_correlation_id() -> str:
    """Get current correlation ID"""
    return correlation_id_ctx.get() or 'N/A'


def clear_correlation_id():
    """Clear correlation ID from current context"""
    correlation_id_ctx.set(None)


# Example usage
if __name__ == '__main__':
    # Setup JSON logging
    logger = setup_logging(log_level='INFO', json_format=True)

    # Example logs without correlation ID
    logger.info('Application started')

    # Example logs with correlation ID (simulating a request)
    request_id = set_correlation_id()
    logger.info('Processing request', extra={'user_id': 123, 'action': 'capture'})
    logger.warning('Low disk space', extra={'disk_free_gb': 5})
    logger.error('Failed to connect to SDR', extra={'device': 'HackRF One', 'error': 'USB timeout'})
    clear_correlation_id()

    # Example logs after clearing correlation ID
    logger.info('Request completed')
