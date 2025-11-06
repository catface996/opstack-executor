"""
API module for hierarchical multi-agent system.

This module provides HTTP API endpoints for managing hierarchical teams,
executing them, and retrieving results.
"""

from .teams import router as teams_router
from .executions import router as executions_router

__all__ = ["teams_router", "executions_router"]