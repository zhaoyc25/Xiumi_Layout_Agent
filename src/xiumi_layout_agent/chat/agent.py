"""Agent 循环：LLM 决定说话或调工具，工具结果回灌，直到回合结束。"""

from __future__ import annotations

from .llm import LLMClient
from .prompt import system_prompt
from .tools import Session, ToolRegistry
from .workflow import WorkflowState

_MAX_TOOL_CALLS = 8  # 防失控


class Agent:
    def __init__(self, llm: LLMClient, registry: ToolRegistry,
                 session: Session | None = None,
                 workflow: WorkflowState | None = None):
        self.llm = llm
        self.registry = registry
        self.session = session or Session()
        self.workflow = workflow or WorkflowState()

    def handle(self, user_text: str) -> str:
        """处理客户一句话，返回主管的最终回复（中间的工具调用不外露）。

        收材料阶段由 TUI 的固定引导负责（不调 LLM），材料齐后才交到这里。
        """
        tools_brief = "、".join(self.registry.names())
        msgs: list[dict] = [
            {"role": "system", "content": system_prompt(self.workflow.stage, tools_brief)},
            {"role": "user", "content": user_text},
        ]
        for _ in range(_MAX_TOOL_CALLS):
            reply = self.llm.chat(msgs)
            tool_name, tool_args, speak = self._parse(reply)
            if speak is not None:
                return speak
            tool = self.registry.get(tool_name)  # type: ignore[arg-type]
            if tool is None:
                msgs.append({"role": "assistant", "content": reply})
                msgs.append({
                    "role": "user",
                    "content": f"（系统提示：没有叫 {tool_name} 的工具。可用：{tools_brief}。请直接答复客户。）",
                })
                continue
            result = tool.run(tool_args or {})
            msgs.append({"role": "assistant", "content": reply})
            msgs.append({"role": "user", "content": f"（工具 {tool_name} 结果：{result}）"})
        return "这一轮我转得太久了，先停一下。您刚才说什么，麻烦再说一遍？"

    @staticmethod
    def _parse(reply: str) -> tuple[str | None, dict | None, str | None]:
        """解析 LLM 回复，按优先级：
        1. <tool_call>{"name": ..., "arguments": {...}}</tool_call>（LLM 原生格式）
        2. CALL name {json}（自定义协议）
        3. SPEAK text（自定义协议）
        4. 其余视为直接说话（剥掉残余的 <tool_call> 标签）
        """
        import json
        import re

        text = reply.strip()

        m = re.search(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", text, re.DOTALL)
        if m:
            try:
                obj = json.loads(m.group(1))
                name = obj.get("name") or ""
                args = obj.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                if name:
                    return name, args, None
            except json.JSONDecodeError:
                pass

        if text.upper().startswith("CALL "):
            body = text[5:].strip()
            name, _, arg_str = body.partition(" ")
            args = {}
            if arg_str.strip():
                try:
                    args = json.loads(arg_str)
                except json.JSONDecodeError:
                    args = {}
            return name or None, args, None
        if text.upper().startswith("SPEAK "):
            return None, None, text[6:].strip()
        # 剥掉混在话里的残余工具调用标签再当作说话
        speak = re.sub(r"<tool_call>.*?</tool_call>", "", text, flags=re.DOTALL).strip()
        return None, None, speak or text
