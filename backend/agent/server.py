from __future__ import annotations

import json
import threading
from typing import Any, Literal, cast

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import agent as core_agent


class HealthResponse(BaseModel):
    ok: bool
    workdir: str
    tasks: int
    inbox_files: int


class TaskItem(BaseModel):
    id: int
    subject: str
    description: str = ""
    status: Literal["pending", "in_progress", "completed", "deleted"] = "pending"
    owner: str | None = None
    blockedBy: list[int] = Field(default_factory=list)


TaskStatus = Literal["pending", "in_progress", "completed", "deleted"]


def _to_task_status(value: Any) -> TaskStatus:
    if value in {"pending", "in_progress", "completed", "deleted"}:
        return cast(TaskStatus, value)
    return "pending"


class TasksResponse(BaseModel):
    items: list[TaskItem]
    count: int


class TaskCreateRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=120)
    description: str = ""


class TaskUpdateRequest(BaseModel):
    status: Literal["pending", "in_progress", "completed", "deleted"] | None = None
    owner: str | None = None
    blockedBy: list[int] | None = None


class ChatRequest(BaseModel):
    conversationId: str
    message: str = Field(min_length=1)


class ChatResponse(BaseModel):
    text: str
    model: str


class InboxMessage(BaseModel):
    type: str
    from_: str = Field(alias="from")
    content: str
    timestamp: float
    request_id: str | None = None
    approve: bool | None = None
    feedback: str | None = None


class InboxResponse(BaseModel):
    items: list[InboxMessage]
    count: int


app = FastAPI(title="Qlunee Agent API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Web chat conversation store. Each conversation reuses the same history
# so the backend can preserve the same context behavior as agent.py REPL.
_CHAT_SESSIONS: dict[str, list[dict[str, Any]]] = {}
_CHAT_LOCK = threading.Lock()


def _assistant_text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            text = getattr(block, "text", None)
            if text:
                parts.append(str(text))
                continue
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "\n".join(part for part in parts if part).strip()

    return ""


def _get_last_assistant_text(history: list[dict[str, Any]]) -> str:
    for msg in reversed(history):
        if msg.get("role") != "assistant":
            continue
        text = _assistant_text_from_content(msg.get("content"))
        if text:
            return text
    return ""


def _task_items_for_api() -> list[TaskItem]:
    task_files = sorted(core_agent.TASKS_DIR.glob("task_*.json"))
    items: list[TaskItem] = []
    for task_file in task_files:
        task = json.loads(task_file.read_text())
        if task.get("status") == "deleted":
            continue
        items.append(
            TaskItem(
                id=int(task.get("id")),
                subject=str(task.get("subject", "")),
                description=str(task.get("description", "")),
                status=_to_task_status(task.get("status", "pending")),
                owner=task.get("owner"),
                blockedBy=list(task.get("blockedBy", [])),
            )
        )
    return items


def _run_web_repl_command(history: list[dict[str, Any]], message: str) -> str | None:
    query = message.strip()
    if query == "/tasks":
        return core_agent.TASK_MGR.list_all()
    if query == "/team":
        return core_agent.TEAM.list_all()
    if query == "/inbox":
        return json.dumps(core_agent.BUS.read_inbox("lead"), ensure_ascii=False, indent=2)
    if query == "/compact":
        if history:
            history[:] = core_agent.auto_compact(history)
        return "Conversation compressed."
    return None


def _should_force_tool_use(message: str) -> bool:
    lower = message.lower()
    keywords = [
        "list",
        "file",
        "files",
        "directory",
        "folder",
        "tree",
        "read",
        "edit",
        "write",
        "bash",
        "command",
        "pwd",
        "项目",
        "文件",
        "目录",
        "列出",
        "读取",
        "修改",
    ]
    return any(keyword in lower for keyword in keywords)


def _run_agent_turn_with_full_tools(history: list[dict[str, Any]], force_tool_first: bool) -> None:
    rounds_without_todo = 0
    first_call = True
    web_token_threshold = 50000

    for _ in range(12):
        core_agent.microcompact(history)
        if core_agent.estimate_tokens(history) > web_token_threshold:
            history[:] = core_agent.auto_compact(history)

        notifs = core_agent.BG.drain()
        if notifs:
            txt = "\n".join(f"[bg:{n['task_id']}] {n['status']}: {n['result']}" for n in notifs)
            history.append({"role": "user", "content": f"<background-results>\n{txt}\n</background-results>"})

        inbox = core_agent.BUS.read_inbox("lead")
        if inbox:
            history.append({"role": "user", "content": f"<inbox>{json.dumps(inbox, ensure_ascii=False, indent=2)}</inbox>"})

        request_kwargs: dict[str, Any] = {
            "model": core_agent.MODEL,
            "system": core_agent.SYSTEM_PROMPT,
            "messages": history,
            "tools": core_agent.TOOLS,
            "max_tokens": 8000,
        }
        if force_tool_first and first_call:
            request_kwargs["tool_choice"] = {"type": "any"}

        response = core_agent.client.messages.create(**request_kwargs)
        first_call = False

        history.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            return

        results: list[dict[str, Any]] = []
        used_todo = False
        manual_compress = False

        for block in response.content:
            if block.type != "tool_use":
                continue
            if block.name == "compress":
                manual_compress = True

            handler = core_agent.TOOL_HANDLERS.get(block.name)
            if block.name == "compress":
                output = "Compression is disabled in web chat sessions."
            else:
                try:
                    output = handler(**block.input) if handler else f"Unknown tool: {block.name}"
                except Exception as exc:
                    output = f"Error: {exc}"

            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(output)[:50000],
                }
            )
            if block.name == "TodoWrite":
                used_todo = True

        rounds_without_todo = 0 if used_todo else rounds_without_todo + 1
        if core_agent.TODO.has_open_items() and rounds_without_todo >= 3:
            results.append({"type": "text", "text": "<reminder>Update your todos.</reminder>"})

        history.append({"role": "user", "content": results})
        if manual_compress:
            return

    history.append(
        {
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": "Stopped after max web tool rounds. Please narrow the request and try again.",
                }
            ],
        }
    )


def _chat_with_full_agent(conversation_id: str, user_message: str) -> ChatResponse:
    with _CHAT_LOCK:
        history = _CHAT_SESSIONS.setdefault(conversation_id, [])

        repl_output = _run_web_repl_command(history, user_message)
        if repl_output is not None:
            history.append({"role": "user", "content": user_message})
            history.append({"role": "assistant", "content": repl_output})
            return ChatResponse(text=repl_output, model=core_agent.MODEL)

        history.append({"role": "user", "content": user_message})
        try:
            _run_agent_turn_with_full_tools(
                history,
                force_tool_first=_should_force_tool_use(user_message),
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Agent execution failed: {exc}") from exc

        text = _get_last_assistant_text(history)
        if not text:
            text = "(agent returned no text content)"
        return ChatResponse(text=text, model=core_agent.MODEL)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "Qlunee Agent API",
        "mode": "full-agent",
        "health": "/api/health",
        "chat": "/api/chat",
        "tasks": "/api/tasks",
        "docs": "/docs",
    }


@app.get("/api/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    core_agent.TASKS_DIR.mkdir(parents=True, exist_ok=True)
    core_agent.INBOX_DIR.mkdir(parents=True, exist_ok=True)
    task_count = len(list(core_agent.TASKS_DIR.glob("task_*.json")))
    inbox_files = len(list(core_agent.INBOX_DIR.glob("*.jsonl")))
    return HealthResponse(
        ok=True,
        workdir=str(core_agent.WORKDIR),
        tasks=task_count,
        inbox_files=inbox_files,
    )


@app.post("/api/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    return _chat_with_full_agent(payload.conversationId, payload.message)


@app.get("/api/inbox/lead", response_model=InboxResponse)
def read_lead_inbox() -> InboxResponse:
    raw_items = core_agent.BUS.read_inbox("lead")
    items = [InboxMessage.model_validate(item) for item in raw_items]
    return InboxResponse(items=items, count=len(items))


@app.get("/api/tasks", response_model=TasksResponse)
def list_tasks() -> TasksResponse:
    items = _task_items_for_api()
    return TasksResponse(items=items, count=len(items))


@app.post("/api/tasks", response_model=TaskItem)
def create_task(payload: TaskCreateRequest) -> TaskItem:
    raw = core_agent.TASK_MGR.create(payload.subject, payload.description)
    task = json.loads(raw)
    return TaskItem(
        id=int(task["id"]),
        subject=str(task.get("subject", "")),
        description=str(task.get("description", "")),
        status=_to_task_status(task.get("status", "pending")),
        owner=task.get("owner"),
        blockedBy=list(task.get("blockedBy", [])),
    )


@app.patch("/api/tasks/{task_id}", response_model=TaskItem)
def update_task(task_id: int, payload: TaskUpdateRequest) -> TaskItem:
    try:
        raw = core_agent.TASK_MGR.get(task_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found") from exc

    current = json.loads(raw)
    status = payload.status if payload.status is not None else current.get("status")
    add_blocked_by: list[int] = []
    remove_blocked_by: list[int] = []

    if payload.blockedBy is not None:
        current_set = set(current.get("blockedBy", []))
        target_set = set(payload.blockedBy)
        add_blocked_by = list(target_set - current_set)
        remove_blocked_by = list(current_set - target_set)

    updated_raw = core_agent.TASK_MGR.update(
        task_id,
        status=status,
        add_blocked_by=add_blocked_by or None,
        remove_blocked_by=remove_blocked_by or None,
    )
    updated = json.loads(updated_raw)

    if payload.owner is not None:
        updated["owner"] = payload.owner
        core_agent.TASK_MGR._save(updated)

    return TaskItem(
        id=int(updated["id"]),
        subject=str(updated.get("subject", "")),
        description=str(updated.get("description", "")),
        status=_to_task_status(updated.get("status", "pending")),
        owner=updated.get("owner"),
        blockedBy=list(updated.get("blockedBy", [])),
    )
