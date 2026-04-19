from anthropic.types import ToolParam


"""
PS: 为什么工具输入参数必须是对象（字典）？
输入参数必须是一个对象object（字典），而不是单一字符串、数字或数组。
对于 bash 工具，输入必须是：
{
  "command": "ls -l"
}
"type": "object" 是为了让输入参数有结构化的定义和校验，保证传入的数据格式正确、可扩展。
"""


# subagent的工具列表  
CHILD_TOOLS :list[ToolParam] = [
    {
        "name": "bash",
        "description": "Run a shell command.",
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
        "description": "Read file contents.",
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
        "description": "Write content to a file.",
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
        "description": "Replace exact text in file.",
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
        "name": "todo",
        "description": "Update task list. Track progress on multi-step tasks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object", 
                        "properties": {
                            "id": {"type": "string"}, 
                            "text": {"type": "string"}, 
                            "status": {
                                "type": "string", 
                                "enum": ["pending", "in_progress", "completed"]}},
                "required": ["id", "text", "status"]}}}, 
            "required": ["items"]}
    }
]

# parentagent的工具列表
PARENT_TOOLS :list[ToolParam] = CHILD_TOOLS + [
    {
        "name": "task",
        "description": "Spawn a subagent with fresh context. It shares the filesystem but not conversation history.",
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "description": {"type": "string", "description": "Short description of the task"}}, 
            "required": ["prompt"]
        }
    },
]