# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development commands

### Backend
- Install Python dependencies: `pip install -e .`
- Start the FastAPI server: `uvicorn backend.agent.server:app --host 127.0.0.1 --port 8000 --reload`
- Run the CLI REPL agent: `python backend/agent/agent.py`
- Run tests: `python -m pytest`
- Run a single test file: `python -m pytest path/to/test_file.py`
- Run a single test case: `python -m pytest path/to/test_file.py -k test_name`

### Frontend
- Install dependencies: `npm --prefix frontend install`
- Start the Vite dev server: `npm --prefix frontend run dev`
- Build the frontend: `npm --prefix frontend run build`
- Preview the production build: `npm --prefix frontend run preview`

## Environment and runtime assumptions
- Python requirement is `>=3.13` from `pyproject.toml`.
- Backend startup depends on `.env` variables loaded in `backend/agent/agent.py`, especially `ANTHROPIC_API_KEY`, `MODEL_ID`, and optionally `QLUNEE_WORKDIR`.
- `QLUNEE_WORKDIR` controls the workspace root that all agent file tools are allowed to access. If it is unset, the backend uses the current working directory.
- The frontend talks to the backend through `VITE_API_BASE_URL` in `frontend/src/services/api.ts`; when unset it uses same-origin requests.
- The frontend can advertise `sse` or `websocket` modes, but `frontend/src/services/stream.ts` currently falls back to plain HTTP because the backend only exposes `/api/chat`.

## High-level architecture
This repository is a local multi-agent coding harness with a FastAPI backend and a Vue 3 frontend.

### Backend shape
- `backend/agent/agent.py` is the core runtime. It initializes the Anthropic client, defines the workspace boundary, and implements nearly all agent behavior: tool handlers, todo state, task persistence, background jobs, teammate messaging, idle/resume loops, and transcript compaction.
- `backend/agent/tools.py` is the model-facing tool schema. If you change available tools or tool input contracts, keep this file aligned with the handlers registered in `backend/agent/agent.py`.
- `backend/agent/server.py` wraps the core runtime in HTTP endpoints. The server is thin: it stores per-conversation message history in memory, forwards user turns into the same agent loop used by the CLI flow, and exposes task/inbox state for the frontend.

### State model
The backend persists most collaboration state on disk under the workspace root rather than in a database:
- `.tasks/` stores one JSON file per task.
- `.team/inbox/` stores JSONL inboxes for lead/teammates; reading an inbox drains it.
- `.team/config.json` tracks teammate metadata.
- `.transcripts/` stores compressed conversation snapshots.

This means backend behavior depends heavily on filesystem state. When debugging task, inbox, or teammate issues, inspect those directories first.

### Request flow
- Frontend messages are sent to `POST /api/chat`.
- `backend/agent/server.py` keeps a per-`conversationId` history in `_CHAT_SESSIONS` and passes that history into `_run_agent_turn_with_full_tools(...)`.
- That loop calls the model with the full tool list from `backend/agent/tools.py`, executes returned tool uses through handlers in `backend/agent/agent.py`, appends tool results back into history, and repeats until the model stops requesting tools.
- Special slash-style commands such as `/tasks`, `/team`, `/inbox`, and `/compact` are intercepted in the server before invoking the model.

### Frontend shape
- `frontend/src/stores/chat.ts` is the center of the client application. It owns chat sessions, persisted message history, health/task preview bootstrap, send/stop/retry behavior, and polling of the lead inbox.
- `frontend/src/services/api.ts` contains the REST client for `/api/health`, `/api/chat`, `/api/tasks`, and `/api/inbox/lead`.
- `frontend/src/services/stream.ts` simulates streaming by chunking the full HTTP response text; there is no true backend streaming transport yet.
- `frontend/src/App.vue` composes the app from the sidebar, message panel, and composer around the Pinia store.

## Important implementation details
- The same core agent powers both the CLI REPL and the web app, so behavior changes in `backend/agent/agent.py` usually affect both surfaces.
- Tool-triggering heuristics for web chat live in `backend/agent/server.py` (`_should_force_tool_use`). If the model is not inspecting files when it should, that is one of the first places to check.
- Inbox reads are destructive by design. The frontend polling loop in `frontend/src/stores/chat.ts` appends drained teammate messages into the active session, so repeated reads from other clients can make messages appear to disappear.
- Task updates in the API proxy into the file-based `TaskManager`; completing a task also removes that task ID from other tasks' `blockedBy` lists.
