"""工具注册表：每个工具 = 名称 + 参数 schema + 实现。现阶段全部是桩。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Tool:
    name: str
    description: str
    params_schema: dict[str, Any]          # JSON Schema（简化版：type/properties/required）
    func: Callable[[dict[str, Any]], str]

    def run(self, args: dict[str, Any]) -> str:
        try:
            return self.func(args)
        except Exception as e:  # noqa: BLE001  工具内部错误不能炸掉主管
            return f"工具 {self.name} 出错了：{e}。请把这情况告诉客户，并记下问题。"


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"工具重名：{tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)


@dataclass
class Session:
    """跨回合记忆（工具与主管共享）。"""
    data: dict[str, Any] = field(default_factory=dict)


def _stub(tool_name: str) -> Callable[[dict[str, Any]], str]:
    def f(args: dict[str, Any]) -> str:
        return f"（功能未实现：{tool_name} 还没有这个工具。请如实告诉老师：现在还没有「{tool_name}」工具，这个功能还没做好。）"
    return f


def build_default_registry(session: Session) -> ToolRegistry:
    """M1 全桩注册表。后续里程碑逐个替换为真实现。"""
    reg = ToolRegistry()

    def _new_project(args: dict[str, Any]) -> str:
        session.data["task_id"] = args["task_id"]
        return f"新项目已登记，任务号 {args['task_id']}。"

    reg.register(Tool(
        name="new_project",
        description="开一个新的排版项目。参数 task_id 形如 20260830_huiyi。",
        params_schema={
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
        },
        func=_new_project,
    ))

    def _reset_all(args: dict[str, Any]) -> str:
        import shutil

        from .config import _REPO_ROOT as root
        ws = root / "workspace"
        inbox = root / "inbox"
        removed = []
        if ws.exists():
            for child in sorted(ws.iterdir()):
                if child.name == ".gitkeep":
                    continue
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
                removed.append(child.name)
        if inbox.exists():
            for child in sorted(inbox.iterdir()):
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
                removed.append(f"inbox/{child.name}")
        session.data.clear()
        return ("已清空所有项目资料和收件箱。" if removed
                else "本来就是空的，没有需要清空的。") + f"（共清理 {len(removed)} 项）"

    reg.register(Tool(
        name="reset_all",
        description="清空之前所有项目（workspace 下所有任务目录 + inbox 收件箱 + 会话记忆）。"
                    "客户明确要求'清空所有项目/重来/清掉测试样例'时使用。此操作不可恢复。",
        params_schema={"type": "object", "properties": {}},
        func=_reset_all,
    ))

    scan_inbox_desc = (
        "检查 workspace/<task_id>/input/ 下已归档的材料："
        "template/ 应有模板文字稿和模板网页文件，draft/ 应有新文字稿，images/ 是图片（可能没有）。"
        "返回各目录文件清单，用于阶段一【检查材料】判断缺不缺。"
        "注意：归档已由系统完成，本工具不搬文件，只做检查"
    )
    stubs = [
        ("scan_inbox", scan_inbox_desc, {}),
        ("normalize_draft", "清洗新文字稿并按层级分级（大标题/二级标题/正文/图片位）", {}),
        ("review_levels", "把分级不明确的段落交给 AI 复核，给出建议", {}),
        ("build_template_map", "解析模板文字稿+模板HTML，生成标准格式文件", {}),
        ("replace_template", "把分级后的新稿套进模板，生成 result.html", {}),
        ("upload_images", "把图片上传图床，换取稳定外链", {}),
        ("deliver_result", "交付 result.html，提醒客户上传秀米并手机预览", {}),
    ]
    for name, desc, schema in stubs:
        reg.register(Tool(name=name, description=desc, params_schema=schema, func=_stub(name)))
    return reg
