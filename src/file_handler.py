"""File management for the Gemini MCP server — upload, processing, and cleanup."""

import asyncio
import mimetypes
import os
import sys
from datetime import datetime

from google import genai

from src.client import GeminiClient
from src.models import ProcessedFile, Session

# Fallback MIME types for extensions that the stdlib mimetypes module doesn't recognize
EXTRA_MIME_TYPES: dict[str, str] = {
    '.jsx': 'text/javascript',
    '.tsx': 'text/typescript',
    '.ts': 'text/typescript',
    '.vue': 'text/html',
    '.svelte': 'text/html',
    '.md': 'text/markdown',
    '.json': 'application/json',
    '.py': 'text/x-python',
    '.js': 'text/javascript',
    '.css': 'text/css',
    '.html': 'text/html',
    '.xml': 'text/xml',
    '.yaml': 'text/yaml',
    '.yml': 'text/yaml',
    '.toml': 'text/plain',
    '.ini': 'text/plain',
    '.cfg': 'text/plain',
    '.conf': 'text/plain',
    '.sh': 'text/x-shellscript',
    '.bat': 'text/plain',
    '.sql': 'text/x-sql',
}


def resolve_mime_type(file_path: str) -> str:
    """Determine the MIME type for a file path.

    Uses the stdlib ``mimetypes`` module first, then falls back to
    ``EXTRA_MIME_TYPES`` for common dev-related extensions.

    Args:
        file_path: Path to the file.

    Returns:
        A MIME type string (defaults to ``text/plain``).
    """
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type:
        return mime_type
    ext = os.path.splitext(file_path)[1].lower()
    return EXTRA_MIME_TYPES.get(ext, 'text/plain')


class FileHandler:
    """Handles file uploads to the Gemini API and session-level cleanup."""

    def __init__(self) -> None:
        self._client: genai.Client | None = None

    @property
    def client(self) -> genai.Client:
        """Return the shared Gemini client."""
        if self._client is None:
            self._client = GeminiClient.get()
        return self._client

    async def process_file(self, file_path: str, session: Session) -> ProcessedFile:
        """Upload a file to Gemini and return processed file info.

        Args:
            file_path: Path to the file to upload.
            session: The session to associate the file with.

        Returns:
            ProcessedFile with upload metadata.

        Raises:
            FileNotFoundError: If the file does not exist.
            Exception: If the upload or processing fails.
        """
        # Already processed in this session
        if file_path in session.processed_files:
            return session.processed_files[file_path]

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        file_name = os.path.basename(file_path)
        mime_type = resolve_mime_type(file_path)

        print(
            f"[{datetime.now().isoformat()}] Session {session.session_id}: "
            f"Uploading file {file_name} ({mime_type})",
            file=sys.stderr,
        )

        try:
            uploaded_file = self.client.files.upload(file=file_path)
            uploaded_file = await self._wait_for_processing(
                uploaded_file, file_name, session.session_id
            )

            processed_file = ProcessedFile(
                file_type='file_data',
                file_uri=uploaded_file.uri,
                mime_type=uploaded_file.mime_type,
                file_name=file_name,
                file_path=file_path,
                gemini_file_id=uploaded_file.name,
            )

            session.processed_files[file_path] = processed_file

            print(
                f"[{datetime.now().isoformat()}] Session {session.session_id}: "
                f"File {file_name} uploaded successfully (URI: {uploaded_file.uri})",
                file=sys.stderr,
            )
            return processed_file

        except Exception as e:
            raise Exception(f"Failed to process file {file_path}: {e}")

    async def _wait_for_processing(
        self, uploaded_file, file_name: str, session_id: str
    ):
        """Wait for a Gemini file upload to finish processing.

        Args:
            uploaded_file: The file object returned by the upload call.
            file_name: Display name for logging.
            session_id: Session ID for logging.

        Returns:
            The updated file object after processing completes.

        Raises:
            Exception: On timeout or processing failure.
        """
        wait_intervals = [0.5, 0.5, 1, 1, 2, 3, 5, 8]
        total_wait = 0.0
        max_wait = 20

        for interval in wait_intervals:
            if uploaded_file.state != 'PROCESSING':
                break

            print(
                f"[{datetime.now().isoformat()}] Session {session_id}: "
                f"File {file_name} is processing... ({total_wait:.1f}s)",
                file=sys.stderr,
            )
            await asyncio.sleep(interval)
            total_wait += interval
            uploaded_file = self.client.files.get(name=uploaded_file.name)

            if total_wait >= max_wait:
                break

        if uploaded_file.state == 'PROCESSING':
            raise Exception(f"File processing timeout after {max_wait} seconds")

        if uploaded_file.state == 'FAILED':
            raise Exception(
                f"File upload failed: {getattr(uploaded_file, 'error', 'Unknown error')}"
            )

        return uploaded_file

    async def cleanup_session_files(self, session: Session) -> None:
        """Delete all uploaded files for a session from the Gemini API.

        Args:
            session: The session whose files should be cleaned up.
        """
        for file_path, file_info in session.processed_files.items():
            try:
                self.client.files.delete(file_info.gemini_file_id)
                print(
                    f"[{datetime.now().isoformat()}] Session {session.session_id}: "
                    f"Deleted file {file_info.file_name}",
                    file=sys.stderr,
                )
            except Exception as e:
                print(
                    f"[{datetime.now().isoformat()}] Session {session.session_id}: "
                    f"Failed to delete file {file_info.file_name}: {e}",
                    file=sys.stderr,
                )
