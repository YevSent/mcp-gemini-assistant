"""Gemini MCP server — thin orchestrator composing session and file management."""

import asyncio
import time

from src.file_handler import FileHandler
from src.session_manager import SessionManager


class GeminiMCPServer:
    """Top-level server that composes SessionManager with rate limiting."""

    def __init__(self) -> None:
        self.file_handler = FileHandler()
        self.sessions = SessionManager(self.file_handler)
        self._last_request_time: float = 0
        self._min_time_between_requests: float = 1.0  # 1 second

    async def rate_limit(self) -> None:
        """Enforce minimum interval between API requests."""
        now = time.time()
        time_since_last = now - self._last_request_time
        if time_since_last < self._min_time_between_requests:
            await asyncio.sleep(self._min_time_between_requests - time_since_last)
        self._last_request_time = time.time()
