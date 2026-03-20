#!/usr/bin/env python3
"""Gemini Coding Assistant MCP Server — tool definitions and entry point."""

import asyncio
import os
import sys
from datetime import datetime
from typing import List, Optional

from mcp.server.fastmcp import FastMCP

from src.client import GeminiClient
from src.server import GeminiMCPServer

# Create server instances
mcp = FastMCP("gemini-coding-assistant")
server = GeminiMCPServer()


@mcp.tool()
async def consult_gemini(
    specific_question: str,
    session_id: Optional[str] = None,
    problem_description: Optional[str] = None,
    code_context: Optional[str] = None,
    attached_files: Optional[List[str]] = None,
    file_descriptions: Optional[dict] = None,
    additional_context: Optional[str] = None,
    preferred_approach: str = "solution",
) -> str:
    """Start or continue a conversation with Gemini about complex coding problems.

    Args:
        specific_question: The specific question you want answered.
        session_id: Optional session ID to continue a previous conversation.
        problem_description: Detailed description of the coding problem (required for new sessions).
        code_context: All relevant code — will be cached for the session (required for new sessions).
        attached_files: Array of file paths to upload and attach to the conversation.
        file_descriptions: Optional object mapping file paths to descriptions.
        additional_context: Additional context, updates, or what changed since last question.
        preferred_approach: Type of assistance needed (solution, review, debug, optimize, explain, follow-up).

    Returns:
        Gemini's response with session metadata.
    """
    await server.rate_limit()
    server.sessions.ensure_cleanup_started()

    try:
        session = server.sessions.get_or_create(session_id)

        # New session — require initial context
        if session.message_count == 0:
            if not problem_description:
                raise ValueError("problem_description is required for new sessions")
            if not code_context and not attached_files:
                raise ValueError(
                    "Either code_context or attached_files are required for new sessions"
                )

            session.problem_description = problem_description
            session.code_context = code_context

            context_parts = [
                f"I'm Claude, an AI assistant, and I need your help with a complex coding problem. "
                f"Here's the context:\n\n**Problem Description:**\n{problem_description}"
            ]

            if code_context:
                context_parts.append(f"\n**Code Context:**\n{code_context}")

            if attached_files:
                context_parts.append("\n**Attached Files:**")

                print(
                    f"[{datetime.now().isoformat()}] Session {session.session_id}: "
                    f"Starting parallel upload of {len(attached_files)} files",
                    file=sys.stderr,
                )
                upload_tasks = [
                    server.sessions.process_file(file_path, session)
                    for file_path in attached_files
                ]
                file_results = await asyncio.gather(
                    *upload_tasks, return_exceptions=True
                )

                for file_path, result in zip(attached_files, file_results):
                    if isinstance(result, Exception):
                        print(
                            f"[{datetime.now().isoformat()}] Session {session.session_id}: "
                            f"Failed to process file {file_path}: {result}",
                            file=sys.stderr,
                        )
                        context_parts.append(
                            f"\n- {os.path.basename(file_path)} (failed to upload: {result!s})"
                        )
                    else:
                        file_info = result
                        print(
                            f"[{datetime.now().isoformat()}] Session {session.session_id}: "
                            f"File {file_info.file_name} processed successfully",
                            file=sys.stderr,
                        )
                        description = (
                            file_descriptions.get(file_path, "")
                            if file_descriptions
                            else ""
                        )
                        if description:
                            description = f" - {description}"
                        context_parts.append(
                            f"\n- {file_info.file_name}{description}"
                        )

                print(
                    f"[{datetime.now().isoformat()}] Session {session.session_id}: "
                    f"Parallel upload completed",
                    file=sys.stderr,
                )

            context_parts.append(
                "\n\nPlease help me solve this problem. I may have follow-up questions, "
                "so please maintain context throughout our conversation."
            )

            # Build message content — text + uploaded file references
            message_content = ["".join(context_parts)]

            client = GeminiClient.get()
            for file_path in attached_files or []:
                if file_path in session.processed_files:
                    file_info = session.processed_files[file_path]
                    uploaded_file = client.files.get(name=file_info.gemini_file_id)
                    message_content.append(uploaded_file)

            response = await asyncio.get_event_loop().run_in_executor(
                None, session.chat.send_message, message_content
            )
            session.message_count += 1

            file_count = len(session.processed_files)
            code_length = len(code_context) if code_context else 0
            print(
                f"[{datetime.now().isoformat()}] Session {session.session_id}: "
                f"Initial context sent ({code_length} chars, {file_count} files)",
                file=sys.stderr,
            )

        # Build the question
        question_parts = [f"**Question:** {specific_question}"]

        if additional_context:
            question_parts.append(
                f"\n\n**Additional Context/Updates:**\n{additional_context}"
            )

        if preferred_approach != "follow-up":
            question_parts.append(
                f"\n\n**Type of Help Needed:** {preferred_approach}"
            )

        question_prompt = "".join(question_parts)

        print(
            f"[{datetime.now().isoformat()}] Session {session.session_id}: "
            f"Question #{session.message_count + 1} ({preferred_approach})",
            file=sys.stderr,
        )

        response = await asyncio.get_event_loop().run_in_executor(
            None, session.chat.send_message, question_prompt
        )
        session.message_count += 1

        response_text = response.text

        server.sessions.extract_requests(response_text, session)

        # Build response with session info
        result_parts = [
            f"**Session ID:** {session.session_id}",
            f"**Message #{session.message_count}**\n",
            response_text,
        ]

        if session.requested_files or session.search_queries:
            result_parts.append("\n\n---")
            if session.requested_files:
                result_parts.append(
                    f"\n**Files Requested:** {', '.join(session.requested_files)}"
                )
            if session.search_queries:
                result_parts.append(
                    f"\n**Searches Requested:** {'; '.join(session.search_queries)}"
                )

        result_parts.append(
            f'\n\n---\n*Use session_id: "{session.session_id}" for follow-up questions*'
        )

        return "\n".join(result_parts)

    except Exception as e:
        print(f"[{datetime.now().isoformat()}] Error: {e}", file=sys.stderr)

        error_message = str(e)
        if "RESOURCE_EXHAUSTED" in error_message:
            error_message = "Gemini API quota exceeded. Please try again later."
        elif "INVALID_ARGUMENT" in error_message:
            error_message = "Request too large. Try reducing code context size."

        return f"Error: {error_message}"


@mcp.tool()
async def get_gemini_requests(session_id: str) -> str:
    """Get the files and searches that Gemini has requested in a session.

    Args:
        session_id: The session ID to check.

    Returns:
        Summary of file and search requests made by Gemini.
    """
    session = server.sessions.get(session_id)
    if session is None:
        return f"Session {session_id} not found"

    result_parts = [f"**Session {session_id} Requests:**"]

    if session.requested_files:
        result_parts.append("\n\n**Files Requested:**")
        for file in session.requested_files:
            result_parts.append(f"- {file}")
    else:
        result_parts.append("\n\nNo files requested")

    if session.search_queries:
        result_parts.append("\n\n**Searches Requested:**")
        for query in session.search_queries:
            result_parts.append(f"- {query}")
    else:
        result_parts.append("\n\nNo searches requested")

    return "\n".join(result_parts)


@mcp.tool()
async def list_sessions() -> str:
    """List all active Gemini consultation sessions.

    Returns:
        Formatted list of active sessions with metadata.
    """
    all_sessions = server.sessions.list_all()

    if not all_sessions:
        return "No active sessions"

    session_text = "\n\n".join(
        f"- **{sid}**\n  Messages: {s.message_count}\n  Created: {s.created.isoformat()}\n  "
        f"Last used: {s.last_used.isoformat()}\n  Files attached: {len(s.processed_files)}\n  "
        f"Code context: {'Yes' if s.code_context else 'No'}\n  "
        f"Requests made: {len(s.requested_files) + len(s.search_queries)}\n  "
        f"Problem: {(s.problem_description[:100] + '...') if s.problem_description else 'No description'}"
        for sid, s in all_sessions.items()
    )

    return f"Active sessions:\n{session_text}"


_cached_models: Optional[str] = None


@mcp.tool()
async def list_models() -> str:
    """List available Gemini models.

    Returns:
        List of available model names.
    """
    global _cached_models
    if _cached_models is not None:
        return _cached_models

    try:
        client = GeminiClient.get()
        models = []
        async for model in await client.aio.models.list():
            models.append(model.name)

        if not models:
            return "No models available"

        _cached_models = "**Available Gemini Models:**\n" + "\n".join(f"- {name}" for name in models)
        return _cached_models

    except Exception as e:
        return f"Error listing models: {e}"


@mcp.tool()
async def end_session(session_id: str) -> str:
    """End a specific Gemini consultation session to free up memory.

    Args:
        session_id: The session ID to end.

    Returns:
        Confirmation message.
    """
    if await server.sessions.end(session_id):
        return f"Session {session_id} has been ended"
    return f"Session {session_id} not found or already expired"


if __name__ == "__main__":
    print(
        "Gemini Coding Assistant MCP Server v3.2.0 running (Python)", file=sys.stderr
    )
    print(
        "Features: Session management, file attachments, context persistence, "
        "follow-up questions, request tracking",
        file=sys.stderr,
    )
    print("Ready to help with complex coding problems!", file=sys.stderr)

    mcp.run()
