import os
from dotenv import load_dotenv
from anthropic import Anthropic

client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))


def agent_loop(state):
    while True:
        # 准备初始消息
        messages = [{"role": "user", "content": query}]

        # 调用模型生成回复
        response = client.messages.create(
            model=MODEL,
            messages=state["messages"],
            tools=TOOLS,
            max_tokens=8000,
        )

        # 追加assitant回复
        state["messages"].append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            state["transition_reason"] = None
            return
    
        # 执行工具
        results = []
        for block in response.content:
            if block.type == "tool_use":
                output = run_bash(block)
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output
                })

        state["messages"].append({"role": "user", "content": results})
        state["turn_count"] += 1
        state["transition_reason"] = "tool_result"
            
