# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.2.0] - 2026-03-19

### feat
- Refactor monolithic `gemini_mcp.py` into modular `src/` package (`client`, `config`, `file_handler`, `models`, `prompts`, `server`, `session_manager`)
- Add `list_models` tool with response caching

### chore
- Switch from `venv`/`pip` to `uv` for dependency management
- Add `pyproject.toml` for project metadata and dependencies
- Add `Makefile` with `install` and `start` targets

### docs
- Simplify installation instructions to use `make install`
- Update Dev Kit links to point to YevSent fork
- Remove version history and LinkedIn sections from README

---

## [3.1.0] - 2025-07-04

### feat
- Add `get_gemini_requests` tool to retrieve all file/search requests made by Gemini in a session
- Implement request tracking (`requested_files`, `search_queries`) in `Session` dataclass
- Parse and display Gemini's explicit file and search requests in `consult_gemini` response

### fix
- Add `_extract_requests_from_response()` to reliably parse Gemini's collaboration requests

### docs
- Enhance system prompt with collaboration capabilities section and dialogue pattern examples
- Show request counts in `list_sessions` output

---

## [3.0.1] - 2025-07-10

### perf
- Implement parallel file uploads via `asyncio.gather()` — reduces multi-file upload time by 70–80% (e.g., 5 files: 15s → 3s)
- Add exponential backoff for file processing status checks (0.5s to 8s intervals)
- Reduce file processing timeout from 30s to 20s

### chore
- Add MIT LICENSE

### docs
- Add performance benchmarks and parallel upload details to README

---

## [3.0.0] - 2025-07-02

### feat
- Initial public release with session management, file attachments, context persistence, and follow-up question support
- `consult_gemini` tool with multi-file context and code snippet support
- `list_sessions` and `end_session` session lifecycle tools
- Automatic session expiry (TTL: 1 hour) with periodic cleanup task
- Rate limiting between Gemini API requests
- Configurable model via `GEMINI_MODEL` env var (default: `gemini-2.5-pro`)

### docs
- Full README with setup instructions, feature overview, and Dev Kit integration guide

---

## [2.1.0]

### feat
- Add file attachment system with automatic cleanup via Gemini Files API

## [2.0.0]

### feat
- Add session management and follow-up question support

## [1.0.0]

### feat
- Initial stateless implementation
