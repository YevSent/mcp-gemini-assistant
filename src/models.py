"""Data models for the Gemini MCP server."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ProcessedFile:
    """Information about a processed file."""

    file_type: str
    file_uri: str
    mime_type: str
    file_name: str
    file_path: str
    gemini_file_id: str


@dataclass
class Session:
    """Chat session with Gemini."""

    session_id: str
    chat: Any
    created: datetime
    last_used: datetime
    message_count: int
    problem_description: Optional[str] = None
    code_context: Optional[str] = None
    processed_files: Dict[str, ProcessedFile] = None
    requested_files: List[str] = None
    search_queries: List[str] = None

    def __post_init__(self) -> None:
        if self.processed_files is None:
            self.processed_files = {}
        if self.requested_files is None:
            self.requested_files = []
        if self.search_queries is None:
            self.search_queries = []
