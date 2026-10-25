from dataclasses import dataclass
from typing import Any


@dataclass
class ToolCall:
    name: str
    args: Any


def collect_tools(messages) -> list[ToolCall]:
    tool_calls = []

    for m in messages:
        for p in m.parts:
            if p.part_kind != "tool-call":
                continue
            if p.tool_name == "final_result":
                continue
            tool_calls.append(ToolCall(p.tool_name, p.args_as_dict()))

    return tool_calls


async def run_agent_test(agent, user_prompt):
    result = await agent.run(user_prompt)

    print(f"\nQUESTION: {user_prompt}")
    for call in collect_tools(result.new_messages()):
        print(f"TOOL CALL: {call.name}({call.args})")
    print(f"ANSWER:\n{result.output}")

    return result
