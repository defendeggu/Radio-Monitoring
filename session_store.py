#!/usr/bin/env python3
"""
Session Store - Shared session_manager instance

Extracted from api_service.py to break the circular import between
api_service.py and blueprints/streaming.py.
"""

import os
from streaming_decoder_service import SessionManager

session_manager = SessionManager(
    redis_host=os.getenv('REDIS_HOST', 'localhost'),
    redis_port=int(os.getenv('REDIS_PORT', 6379)),
    redis_db=int(os.getenv('REDIS_DB', 0)),
    redis_password=os.getenv('REDIS_PASSWORD') or None
)
