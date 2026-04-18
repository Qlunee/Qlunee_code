import os
import subprocess # 用于执行终端命令
from pathlib import Path
from typing import Optional, cast, Any

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(override=True)

from tools import CHILD_TOOLS, PARENT_TOOLS
from utils import normalize_messages


# 初始化大模型客户端和系统提示
WORKDIR = Path.cwd()

client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"),api_key=os.getenv("ANTHROPIC_API_KEY") )
MODEL = os.environ["MODEL_ID"]

SYSTEM = f"""You are a coding agent at {WORKDIR}. 
Use the task tool to delegate exploration or subtasks.
"""

SUBAGENT_SYSTEM = f"""You are a coding subagent at {WORKDIR}. 
Use the todo tool to plan multi-step tasks to complete the given task. Mark in_progress before starting, completed when done.Prefer tools over prose.
Then summarize your findings.
"""


# 创建todo管理器
class TodoManager:
    def __init__(self):
        self.items = []
    def update(self, items: list) -> str:
        if len(items) > 20:
            raise ValueError("Max 20 todos allowed")
        validated = []
        in_progress_count = 0
        for i, item in enumerate(items):
            text = str(item.get("text", "")).strip()
            status = str(item.get("status","pending")).lower()
            item_id = str(item.get("id", str(i+1)))

            if not text:
                raise ValueError(f"Item {item_id}: text required")
            if status not in {"pending", "in_progress", "completed"}:
                raise ValueError(f"Item {item_id}: invalid status {status}")
            if status == "in_progress":
                in_progress_count += 1
            validated.append({"id": item_id, "text": text, "status": status})

        if in_progress_count > 1:
            raise ValueError("Only one task can be in_progress at a time")
        self.items = validated
        return self.render()

    def render(self) -> str:
        if not self.items:
            return "Todo list is empty."
        lines = []
        for item in self.items:
            prefix = {"pending": "[ ]", "in_progress": "[>]", "completed": "[x]"}[item["status"]]
            lines.append(f"{prefix} {item['id']}: {item['text']}")
        done = sum(1 for t in self.items if t["status"] == "completed")
        lines.append(f"\n({done}/{len(self.items)} completed)")

        return "\n".join(lines)

TODO = TodoManager()
        

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

# --dispatch map: {tool_name: handler} --
TOOL_HANDLERS = {
    "bash":             lambda **kwargs: run_bash(kwargs["command"]),
    "read_file":        lambda **kwargs: run_read(kwargs["file_path"], kwargs.get("limit")),
    "write_file":       lambda **kwargs: run_write(kwargs["file_path"], kwargs["content"]),
    "edit_file":        lambda **kwargs: run_edit(kwargs["file_path"], kwargs["old_content"], kwargs["new_content"]),
    "todo":             lambda **kwargs: TODO.update(kwargs["items"]),
}

# -- 并发安全分级 --
# 只读类工具（只看不改）可以放心地并行运行；
# 而修改类工具（会动数据的）必须串行执行（一个接一个排队）。

CONCURRENCY_SAFE = {"read_file"}
CONCURRENCY_UNSAFE = {"write_file", "edit_file"}


# 子智能体，纯净的上下文，只做总结
def run_subagent(prompt: str) -> str:
    rounds_since_todo = 0  # 初始化变量
    # 显式声明 sub_messages 的类型
    sub_messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
    for _ in range(30):  # 最多5轮
        # 调用模型生成回复
        response = client.messages.create(
            model=MODEL,
            system=SUBAGENT_SYSTEM,
            messages=normalize_messages(sub_messages),
            tools=CHILD_TOOLS,
            max_tokens=8000,
        )

        # 追加assitant回复
        sub_messages.append({"role": "assistant", "content": response.content})
        print("stop_reason:", response.stop_reason)
        if response.stop_reason != "tool_use":
            break  # 如果模型没有使用工具，就结束本轮对话
    
        # 执行工具
        results = []
        used_todo = False

        for block in response.content:
            if block.type == "tool_use":
                handler = TOOL_HANDLERS.get(block.name)
                if handler:
                    # 动态调用函数，并传入参数。block.input：是 AI 提供的参数字典
                    # **block.input (解包操作)：将字典中的键值对作为独立的参数传递给函数。
                    output = handler(**block.input)
                else:
                    output = f"Tool not found: {block.name}"
                if block.name == "todo":
                    used_todo = True
                print(f"> {block.name}:")
                print(output[:200])

                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(output)
                })

        rounds_since_todo = 0 if used_todo else rounds_since_todo + 1
        if rounds_since_todo >= 3:
            results.append({"type": "text", "text": "<reminder>Update your todos.</reminder>"})
        sub_messages.append({"role": "user", "content": results})
    # 最后总结输出
    return "".join(
        block.text for block in response.content 
        if block.type == "text" # 明确只取文本块
    ) or "(no summary)"


# 主智能体循环,处理用户输入和工具调用,以及任务分配
def agent_loop(messages: list):
    while True:
        # 调用模型生成回复
        response = client.messages.create(
            model=MODEL,
            system=SYSTEM,
            messages=normalize_messages(messages),
            tools=PARENT_TOOLS,
            max_tokens=8000,
        )

        # 追加assitant回复
        messages.append({"role": "assistant", "content": response.content})
        print("stop_reason:", response.stop_reason)
        if response.stop_reason != "tool_use":
            return  # 如果模型没有使用工具，就结束本轮对话
    
        # 执行工具
        results = []

        for block in response.content:
            if block.type == "tool_use":
                if block.name == "task":
                    # 强制将 block.input 视为字典
                    tool_input = cast(dict[str, Any], block.input)
                    desc = tool_input.get("description", "subtask")
                    prompt = tool_input.get("prompt", "")
                    # 使用明显的分割线表示进入子代理
                    print(f"\n\033[34m[PARENT] Delegating Task: {desc}\033[0m")
                    print(f"\033[34m[PARENT] Prompt: {prompt[:80]}...\033[0m")
                    output = run_subagent(prompt)
                    # 打印收到的汇报
                    print(f"\033[32m[PARENT] Subagent reported: {len(output)} chars.\033[0m\n")

                else:
                    handler = TOOL_HANDLERS.get(block.name)
                    if handler:
                    # 动态调用函数，并传入参数。block.input：是 AI 提供的参数字典
                    # **block.input (解包操作)：将字典中的键值对作为独立的参数传递给函数。
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
        # print("messages:",messages)
            

if __name__ == "__main__":
    history = []

    while True:
        try:
            query = input("\033[36mQlunee_code_v04 >> \033[0m")
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
    
