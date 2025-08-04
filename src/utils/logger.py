"""
Logger module for course content generation.

This module provides a configured logger instance. The logging configuration
is automatically set up when the src package is imported.
"""

import logging

# Get logger instance - configuration is handled automatically by src/__init__.py
log = logging.getLogger(__name__)
