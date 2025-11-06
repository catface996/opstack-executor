#!/usr/bin/env python3
"""
Command-line interface for hierarchical multi-agent system.

This module provides CLI commands for running the hierarchical multi-agent system.
"""

import sys
import os
from pathlib import Path

def main():
    """Main CLI entry point."""
    import uvicorn
    
    # Add src directory to Python path if not already there
    src_dir = Path(__file__).parent.parent
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    
    print("Starting Hierarchical Multi-Agent System...")
    print("Access the API documentation at: http://localhost:8000/docs")
    print("Press Ctrl+C to stop the server")
    
    try:
        uvicorn.run(
            "hierarchical_agents.main:app",
            host="0.0.0.0",
            port=8000,
            reload=False,  # Disable reload for CLI
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()