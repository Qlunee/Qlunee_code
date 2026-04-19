import os
import time
import json
import subprocess # 用于执行终端命令
from pathlib import Path
from typing import Optional

from anthropic import Anthropic
from anthropic.types import ToolParam
from dotenv import load_dotenv

load_dotenv(override=True)

# if os.getenv("ANTHROPIC_BASE_URL"):
#     os.environ.pop("ANTHROPIC_API_KEY", None)

WORKDIR = Path.cwd()

client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"),api_key=os.getenv("ANTHROPIC_API_KEY") )
MODEL = os.environ["MODEL_ID"]

SYSTEM = f"You are a coding agent at {WORKDIR}. Use tools to solve tasks. Act, don't explain."

# 定义上下文压缩的参数
THRESHOLD = 2000
TRANSCRIPT_DIR = WORKDIR / ".transcripts"
KEEP_RECENT = 3
PRESERVE_RESULT_TOOLS = {"read_file"}

def estimate_token(messages: list) -> int:
    # 这里我们简单地用字符数来估算 token 数（实际情况可能更复杂）
    return len(str(messages))//4

# layer1: micro_compact 即时清理
def micro_compact(messages: list) -> list:
    # Collect (msg_index, part_index, tool_result_dict) for all tool_result entries
    # 搜寻目标
    tool_results = []
    for msg_idx, msg in enumerate(messages):
        if msg["role"] == "user" and isinstance(msg.get("content"), list):
            for part_idx, part in enumerate(msg["content"]):
                if isinstance(part, dict) and part.get("type") == "tool_result":
                    tool_results.append((msg_idx, part_idx, part))
    if len(tool_results) <= KEEP_RECENT:
        return messages
    # 建立ID映射
    tool_name_map = {}
    for msg in messages:
        if msg["role"] == "assistant":
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if hasattr(block, "type") and block.type == "tool_use":
                        tool_name_map[block.id] = block.name
                    
    # 筛选“老旧”数据
    to_clear = tool_results[:-KEEP_RECENT]
    for _, _, result in to_clear:
        if not isinstance(result.get("content"), str) or len(result["content"]) <= 100:
            continue
        tool_id = result.get("tool_use_id", "")
        tool_name = tool_name_map.get(tool_id, "unknown")
        if tool_name in PRESERVE_RESULT_TOOLS:
            continue
        result["content"] = f"[Previous: used {tool_name}]"
    return messages


# layer2: auto_compact 被动防御
def auto_compact(messages: list) -> list:
    # 建立“冷存储”
    TRANSCRIPT_DIR.mkdir(exist_ok=True)
    transcript_path = TRANSCRIPT_DIR / f"transcript_{int(time.time())}.jsonl"
    with open(transcript_path, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg, default=str) + "\n")
    print(f"[transcript saved: {transcript_path}]")

    # 提取“热数据”，利用llm进行总结
    conversation_text = json.dumps(messages, default=str)[-80000:]
    response = client.messages.create(
        model=MODEL,
        messages=[{"role": "user", "content":
            "Summarize this conversation for continuity. Include: "
            "1) What was accomplished, 2) Current state, 3) Key decisions made. "
            "Be concise but preserve critical details.\n\n" + conversation_text}],
        max_tokens=2000,
    )

    summary = next((block.text for block in response.content if hasattr(block, "text")), "")

    # --- 新增：在这里展示总结内容 ---
    print("\n" + "="*50)
    print("\033[1;35m【上下文自动压缩完成 - 记忆摘要】\033[0m")
    print(f"\033[3;37m{summary}\033[0m")
    print("="*50 + "\n")
    # ----------------------------
    
    if not summary:
        summary = "No summary generated."
    # Replace all messages with compressed summary
    return [
        {"role": "user", "content": f"[Conversation compressed. Transcript: {transcript_path}]\n\n{summary}"},
    ]

    # 彻底清空并“重启”

# layer3: manual_compact ai觉得需要清理时主动清理


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
    "compact":          lambda **kwargs: "Manual compression requested.",
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
    {
        "name": "compact",
        "description": "Trigger manual conversation compression.",
        "input_schema": {
            "type": "object",
            "properties": {
                "focus": 
                    {"type": "string",
                     "description": "What to preserve in the summary"}},
        }

    }
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
        
        # --- 防御 NoneType ---
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

    # 合并同角色消息 
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
        # layer 1: micro_compact 即时清理
        micro_compact(messages)

        # layer 2: auto_compact 被动防御
        current_tokens = estimate_token(messages)
        print(f"\033[32mDEBUG: Current history length: {len(json.dumps(messages, default=str))} characters\033[0m")
        if current_tokens > THRESHOLD:
            print("\033[31m[auto_compact triggered]\033[0m")
            messages[:] = auto_compact(messages)

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
        manual_compact = False
        for block in response.content:
            if block.type == "tool_use":
                if block.name == "compact":
                    manual_compact = True
                    output = "Compressing..."
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

        # layer3 manual_compact ai觉得需要清理时主动清理
        if manual_compact:
            print("\033[33m[manual_compact triggered]\033[0m")
            messages[:] = auto_compact(messages)

if __name__ == "__main__":
    history = []

    while True:
        try:
            query = input("\033[36mQlunee_code_v06 >> \033[0m")
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
    
