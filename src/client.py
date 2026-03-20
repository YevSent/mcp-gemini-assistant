"""Gemini API client initialization."""

import os

from google import genai


class GeminiClient:
    """Wrapper around the Google GenAI client.

    Provides a singleton-style access to the configured Gemini client instance.
    """

    _instance: genai.Client | None = None

    @classmethod
    def get(cls) -> genai.Client:
        """Return the shared Gemini client, creating it on first call.

        Returns:
            Configured genai.Client instance.
        """
        if cls._instance is None:
            cls._instance = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
        return cls._instance
