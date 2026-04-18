import os
import subprocess # 用于执行终端命令
from pathlib import Path
from typing import Optional
import json

from anthropic import Anthropic
from anthropic.types import ToolParam
from dotenv import load_dotenv

load_dotenv(override=True)

# if os.getenv("ANTHROPIC_BASE_URL"):
#     os.environ.pop("ANTHROPIC_API_KEY", None)

WORKDIR = Path.cwd()
TASK_DIR = WORKDIR / ".tasks"

client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"),api_key=os.getenv("ANTHROPIC_API_KEY") )
MODEL = os.environ["MODEL_ID"]

SYSTEM = f"You are a coding agent at {WORKDIR}. Use task tools to plan and track work."

# 定义任务管理器
class TaskManager:
    def __init__(self, task_dir: Path):
        self.dir = task_dir
        self.dir.mkdir(exist_ok=True)
        self._next_id = self._max_id() + 1

    def _max_id(self):
        ids = [int(f.stem.split("_")[1]) for f in self.dir.glob("task_*.json")]
        return max(ids) if ids else 0
    
    def _load(self, task_id: int):
        path = self.dir / f"task_{task_id}.json"
        if not path.exists():
            raise ValueError(f"Task {task_id} not found")
        return json.loads(path.read_text())
    
    def _save(self, task: dict):
        path = self.dir / f"task_{task['id']}.json"
        path.write_text(json.dumps(task, indent=2, ensure_ascii=False))

    def create(self, subject: str, description: str = "") -> str:
        task = {
            "id": self._next_id,
            "subject": subject,
            "description": description,
            "status": "pending",
            "blocked_by": [],
            "owner": "",
        }

        self._save(task)
        self._next_id += 1
        return json.dumps(task, indent=2, ensure_ascii=False)


    def get(self, task_id: int) -> str:
        return json.dumps(self._load(task_id), indent=2, ensure_ascii=False)


    def update(self, task_id: int, status: Optional[str] = None, 
               add_blocked_by: Optional[list] = None, remove_blocked_by: Optional[list] = None) -> str:
        task = self._load(task_id)
        if status:
            if status not in ("pending", "in_progress", "completed"):
                raise ValueError(f"Invalid status: {status}")
            task["status"] = status
            if status == "completed":
                self._clear_dependency(task_id)
        if add_blocked_by:
            task["blocked_by"] = list(set(task["blocked_by"] + add_blocked_by))
        if remove_blocked_by:
            task["blocked_by"] = [x for x in task["blocked_by"] if x not in remove_blocked_by]

        self._save(task)
        return json.dumps(task, indent=2, ensure_ascii=False)

    def _clear_dependency(self, completed_id: int):
        for f in self.dir.glob("task_*.json"):
            task = json.loads(f.read_text())
            if completed_id in task.get("blockedBy", []):
                task["blockedBy"].remove(completed_id)
                self._save(task)

    
    def list_all(self) -> str:
        tasks = []
        files = sorted(
            self.dir.glob("task_*.json"),
            key=lambda f: int(f.stem.split("_")[1])
        )
        for f in files:
            tasks.append(json.loads(f.read_text()))
        if not tasks:
            return "No tasks."
        lines = []
        for t in tasks:
            marker = {"pending": "[ ]", "in_progress": "[>]", "completed": "[x]"}.get(t["status"], "[?]")
            blocked = f" (blocked by: {t['blockedBy']})" if t.get("blockedBy") else ""
            lines.append(f"{marker} #{t['id']}: {t['subject']}{blocked}")
        return "\n".join(lines)

TASKS = TaskManager(TASK_DIR)

# 定义路径沙箱
def safe_path(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Unsafe path: {p}")
    return path

# 定义工具
def run_bash(command: str) -> str:
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Command rejected for safety reasons."
    try:
        r = subprocess.run(command, shell=True, cwd=WORKDIR, capture_output=True, text=True, timeout=100)
        out = (r.stdout + r.stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"



def run_read(file_path: str, limit: Optional[int] = None) -> str:
    try:
        text = safe_path(file_path).read_text()
        lines = text.splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
        return "\n".join(lines)[:50000]
    except Exception as e:
        return f"Error: {e}"

def run_write(file_path: str, content: str) -> str:
    try:
        fp = safe_path(file_path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
        return f"Wrote {len(content)} bytes to {file_path}"
    except Exception as e:
        return f"Error: {e}"

def run_edit(file_path: str, old_content: str, new_content: str) -> str:
    try:
        fp = safe_path(file_path)
        content = fp.read_text()
        if old_content not in content:
            return f"Error: Text not found in {file_path}"
        fp.write_text(content.replace(old_content, new_content, 1))
        return f"Edited {file_path}"
    except Exception as e:
        return f"Error: {e}"



# -- 并发安全分级 --
# 只读类工具（只看不改）可以放心地并行运行；
# 而修改类工具（会动数据的）必须串行执行（一个接一个排队）。

CONCURRENCY_SAFE = {"read_file"}
CONCURRENCY_UNSAFE = {"write_file", "edit_file"}

# --dispatch map: {tool_name: handler} --
TOOL_HANDLERS = {
    "bash":             lambda **kwargs: run_bash(kwargs["command"]),
    "read_file":        lambda **kwargs: run_read(kwargs["file_path"], kwargs.get("limit")),
    "write_file":       lambda **kwargs: run_write(kwargs["file_path"], kwargs["content"]),
    "edit_file":        lambda **kwargs: run_edit(kwargs["file_path"], kwargs["old_content"], kwargs["new_content"]),
    "task_create":      lambda **kwargs: TASKS.create(kwargs["subject"], kwargs.get("description", "")),
    "task_update":      lambda **kwargs: TASKS.update(kwargs["task_id"], kwargs.get("status"), kwargs.get("addBlockedBy"), kwargs.get("removeBlockedBy")),
    "task_list":        lambda **kwargs: TASKS.list_all(),
    "task_get":         lambda **kwargs: TASKS.get(kwargs["task_id"]),
}

"""
输入参数必须是一个对象（字典），而不是单一字符串、数字或数组。
对于 bash 工具，输入必须是：
{
  "command": "ls -l"
}
"type": "object" 是为了让输入参数有结构化的定义和校验，保证传入的数据格式正确、可扩展。
"""

    
TOOLS :list[ToolParam] = [
    {
        "name": "bash",
        "description": "Execute a bash command and return the output. Use this to run terminal commands, scripts, or any shell operations. Input should be a string representing the command to execute.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"}
            },
            "required": ["command"]
        }
    },
    {
        "name": "read_file",
        "description": "Read the content of a file. Input should be a string representing the file path. Optionally, you can specify a 'limit' parameter to read only the first N characters of the file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "limit": {"type": "integer"}
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "write_file",
        "description": "Write content to a file. Input should be an object with 'file_path' (string) and 'content' (string) fields. This will overwrite the existing content of the file or create it if it doesn't exist.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "content": {"type": "string"}
            },
            "required": ["file_path", "content"]
        }
    },
    {
        "name": "edit_file",
        "description": "Edit an existing file by replacing old content with new content. Input should be an object with 'file_path' (string), 'old_content' (string), and 'new_content' (string) fields. This will find all occurrences of 'old_content' in the specified file and replace them with 'new_content'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "old_content": {"type": "string"},
                "new_content": {"type": "string"}
            },
            "required": ["file_path", "old_content", "new_content"]
        }
    },
    {"name": "task_create", 
     "description": "Create a new task.",
     "input_schema": {"type": "object", "properties": {"subject": {"type": "string"}, "description": {"type": "string"}}, "required": ["subject"]}},
    {"name": "task_update", 
     "description": "Update a task's status or dependencies.",
     "input_schema": {"type": "object", "properties": {"task_id": {"type": "integer"}, "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}, "addBlockedBy": {"type": "array", "items": {"type": "integer"}}, "removeBlockedBy": {"type": "array", "items": {"type": "integer"}}}, "required": ["task_id"]}},
    {"name": "task_list", 
     "description": "List all tasks with status summary.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "task_get", 
     "description": "Get full details of a task by ID.",
     "input_schema": {"type": "object", "properties": {"task_id": {"type": "integer"}}, "required": ["task_id"]}},
]


# 消息规范化
def normalize_messages(messages: list) -> list:
    """
    在向 API 发送之前清理消息。

    三项工作：
    1. 剥离 API 无法理解的内部元数据字段
    2. 确保每个 tool_use 都有匹配的 tool_result（如果缺失则插入占位符）
    3. 合并连续的同角色消息（API 要求严格的交替格式）
    """
    if not messages:
        return []
    
    processed = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")
        
        # --- 核心修复：防御 NoneType ---
        if content is None:
            new_content = [{"type": "text", "text": ""}]
        elif isinstance(content, str):
            new_content = [{"type": "text", "text": content}]
        elif isinstance(content, list):
            new_content = []
            for block in content:
                # 兼容 SDK 对象和普通字典
                if hasattr(block, "model_dump"):
                    b = block.model_dump()
                elif isinstance(block, dict):
                    b = block
                else:
                    # 应对字符串混入列表的情况
                    b = {"type": "text", "text": str(block)}
                
                new_content.append({k: v for k, v in b.items() if not k.startswith("_")})
        else:
            new_content = [{"type": "text", "text": str(content)}]
            
        processed.append({"role": role, "content": new_content})

    # 合并同角色消息 (保持不变)
    merged = []
    for msg in processed:
        if merged and merged[-1]["role"] == msg["role"]:
            merged[-1]["content"].extend(msg["content"])
        else:
            merged.append(msg)
            
    return merged


def agent_loop(messages: list):
    while True:
        # 调用模型生成回复
        response = client.messages.create(
            model=MODEL,
            system=SYSTEM,
            messages=normalize_messages(messages),
            tools=TOOLS,
            max_tokens=8000,
        )

        # 追加assitant回复
        messages.append({"role": "assistant", "content": response.content})
        print("stop_reason:", response.stop_reason)
        if response.stop_reason != "tool_use":
            break
    
        # 执行工具
        results = []
        for block in response.content:
            if block.type == "tool_use":
                handler = TOOL_HANDLERS.get(block.name)
                if handler:
                    output = handler(**block.input)
                else:
                    output = f"Tool not found: {block.name}"
                print(f"> {block.name}:")
                print(output[:200])

                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(output)
                })

        messages.append({"role": "user", "content": results})
            

if __name__ == "__main__":
    history = []

    while True:
        try:
            query = input("\033[36mQlunee_code_v07 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        history.append({"role": "user", "content": query})
        agent_loop(history)
        response_content = history[-1]["content"]
        if isinstance(response_content, list):
            for block in response_content:
                # 在打印之前，先检查当前的 block 对象是否拥有 "text" 这个属性
                if hasattr(block, "text"):
                    print(block.text)
        print()
    
