#!/usr/bin/env python3
"""
Session Store - shared SessionManager instance for streaming sessions.

Kept in its own module so blueprints, jobs and the scheduler can import it
without circular imports.
"""

from streaming_decoder_service import SessionManager

session_manager = SessionManager()
