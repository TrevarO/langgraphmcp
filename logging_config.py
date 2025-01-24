import logging
import logging.config  # Add this import
import sys
from typing import Dict, Optional

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'detailed': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        },
        'simple': {
            'format': '%(levelname)s - %(message)s'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'simple',
            'stream': sys.stdout
        },
        'file': {
            'class': 'logging.FileHandler',
            'level': 'DEBUG',
            'formatter': 'detailed',
            'filename': 'langgraph_mcp.log',
            'mode': 'a'
        },
        'cleanup': {
            'class': 'logging.FileHandler',
            'level': 'DEBUG',
            'formatter': 'detailed',
            'filename': 'cleanup.log',
            'mode': 'w'  # Overwrite each run
        }
    },
    'loggers': {
        'cleanup': {
            'handlers': ['console', 'cleanup'],
            'level': 'DEBUG',
            'propagate': False
        },
        'httpcore': {
            'handlers': ['file'],
            'level': 'WARNING',
            'propagate': False
        },
        'httpx': {
            'handlers': ['file'],
            'level': 'WARNING',
            'propagate': False
        },
        'openai': {
            'handlers': ['file'],
            'level': 'WARNING',
            'propagate': False
        }
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO'
    }
}

def setup_logging():
    """Configure logging with separate cleanup logger"""
    logging.config.dictConfig(LOGGING_CONFIG)
    logger = logging.getLogger('cleanup')
    return logger

cleanup_logger = setup_logging()