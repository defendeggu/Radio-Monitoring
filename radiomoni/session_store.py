#!/usr/bin/env python3
"""
Session Store - shared SessionManager instance for streaming sessions.

Kept in its own module so blueprints, jobs and the scheduler can import it
without circular imports.
"""

from radiomoni.decoders.streaming import SessionManager

session_manager = SessionManager()
