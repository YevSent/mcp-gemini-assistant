"""Session lifecycle management for the Gemini MCP server."""

import asyncio
import re
import sys
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from google.genai import types

from src.client import GeminiClient
from src.config import MODEL_NAME, SESSION_TTL
from src.file_handler import FileHandler
from src.models import ProcessedFile, Session
from src.prompts import SYSTEM_PROMPT


class SessionManager:
    """Manages Gemini chat session lifecycle — create, get, cleanup, and request tracking."""

    def __init__(self, file_handler: FileHandler) -> None:
        self._sessions: Dict[str, Session] = {}
        self._file_handler = file_handler
        self._cleanup_task: Optional[asyncio.Task] = None

    @property
    def client(self):
        """Return the shared Gemini client."""
        return GeminiClient.get()

    # ------------------------------------------------------------------
    # Session CRUD
    # ------------------------------------------------------------------

    def get_or_create(self, session_id: Optional[str] = None) -> Session:
        """Return an existing session or create a new one.

        Args:
            session_id: Optional ID of an existing session to resume.

        Returns:
            The existing or newly created Session.
        """
        if not session_id:
            session_id = str(uuid.uuid4())

        if session_id in self._sessions:
            session = self._sessions[session_id]
            session.last_used = datetime.now()
            return session

        chat = self.client.chats.create(
            model=MODEL_NAME,
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=8192,
                top_p=0.95,
                top_k=40,
                system_instruction=SYSTEM_PROMPT,
            ),
        )

        session = Session(
            session_id=session_id,
            chat=chat,
            created=datetime.now(),
            last_used=datetime.now(),
            message_count=0,
        )

        self._sessions[session_id] = session
        print(
            f"[{datetime.now().isoformat()}] New session created: {session_id}",
            file=sys.stderr,
        )
        return session

    def get(self, session_id: str) -> Optional[Session]:
        """Return a session by ID, or None if not found.

        Args:
            session_id: The session ID to look up.

        Returns:
            The Session if it exists, otherwise None.
        """
        return self._sessions.get(session_id)

    def exists(self, session_id: str) -> bool:
        """Check whether a session exists.

        Args:
            session_id: The session ID to check.

        Returns:
            True if the session exists.
        """
        return session_id in self._sessions

    def list_all(self) -> Dict[str, Session]:
        """Return all active sessions.

        Returns:
            A dict mapping session IDs to Session objects.
        """
        return dict(self._sessions)

    async def end(self, session_id: str) -> bool:
        """End a session — clean up its files and remove it.

        Args:
            session_id: The session ID to end.

        Returns:
            True if the session was found and removed, False otherwise.
        """
        if session_id not in self._sessions:
            return False

        await self._cleanup_files(session_id)
        del self._sessions[session_id]
        print(
            f"[{datetime.now().isoformat()}] Session {session_id} ended by user",
            file=sys.stderr,
        )
        return True

    # ------------------------------------------------------------------
    # File management (delegates to FileHandler)
    # ------------------------------------------------------------------

    async def process_file(self, file_path: str, session: Session) -> ProcessedFile:
        """Upload a file and associate it with the session.

        Args:
            file_path: Path to the file to upload.
            session: The session to attach the file to.

        Returns:
            ProcessedFile with upload metadata.
        """
        return await self._file_handler.process_file(file_path, session)

    # ------------------------------------------------------------------
    # Response request extraction
    # ------------------------------------------------------------------

    @staticmethod
    def extract_requests(response_text: str, session: Session) -> None:
        """Parse Gemini's response for file and search requests.

        Args:
            response_text: The text of Gemini's response.
            session: The session to track requests in.
        """
        file_patterns = [
            r"show me (?:the )?([^\s]+\.[a-zA-Z]+)",
            r"share (?:the )?([^\s]+\.[a-zA-Z]+)",
            r"can you (?:show|share) (?:me )?([^\s]+\.[a-zA-Z]+)",
            r"(?:I need to see|please provide) ([^\s]+\.[a-zA-Z]+)",
        ]

        for pattern in file_patterns:
            matches = re.findall(pattern, response_text, re.IGNORECASE)
            for match in matches:
                if match not in session.requested_files:
                    session.requested_files.append(match)

        search_patterns = [
            r"I would search for: ([^\n]+)",
            r"search for (?:the )?([^\n]+)",
            r"Let me search for ([^\n]+)",
        ]

        for pattern in search_patterns:
            matches = re.findall(pattern, response_text, re.IGNORECASE)
            for match in matches:
                if match not in session.search_queries:
                    session.search_queries.append(match.strip())

    # ------------------------------------------------------------------
    # Periodic cleanup
    # ------------------------------------------------------------------

    def ensure_cleanup_started(self) -> None:
        """Start the periodic cleanup task if not already running."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self) -> None:
        """Periodically remove expired sessions."""
        while True:
            await asyncio.sleep(300)  # Check every 5 minutes
            now = datetime.now()
            expired = [
                sid
                for sid, s in self._sessions.items()
                if (now - s.last_used).total_seconds() > SESSION_TTL
            ]

            for session_id in expired:
                await self._cleanup_files(session_id)
                del self._sessions[session_id]
                print(
                    f"[{datetime.now().isoformat()}] Session {session_id} expired and removed",
                    file=sys.stderr,
                )

    async def _cleanup_files(self, session_id: str) -> None:
        """Clean up uploaded files for a session.

        Args:
            session_id: The session whose files should be deleted.
        """
        session = self._sessions.get(session_id)
        if session is None:
            return
        await self._file_handler.cleanup_session_files(session)
