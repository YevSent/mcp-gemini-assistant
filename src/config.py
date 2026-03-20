"""Configuration constants for the Gemini MCP server."""

import os
import sys

# Validate required environment variables
if not os.getenv('GEMINI_API_KEY'):
    print("Error: GEMINI_API_KEY environment variable is required", file=sys.stderr)
    sys.exit(1)

# Model configuration
MODEL_NAME = os.getenv('GEMINI_MODEL', 'gemini-3.1-pro-preview')

# Session configuration
SESSION_TTL = 3600  # 1 hour in seconds
