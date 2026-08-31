"""工具注册表：每个工具 = 名称 + 参数 schema + 实现。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .llm import LLMClient


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


def build_default_registry(session: Session, llm: LLMClient | None = None) -> ToolRegistry:
    """工具注册表。llm 传入后 normalize_draft 可用；不传则该工具报错。"""
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

    def _scan_inbox(args: dict[str, Any]) -> str:
        from .config import _REPO_ROOT as root
        from .scan import scan_input

        task_id = args.get("task_id") or session.data.get("task_id")
        if not task_id:
            return "还没有任务号，没法检查材料。请先开新项目。"
        base = root / "workspace" / task_id / "input"
        if not base.exists():
            return f"没找到 workspace/{task_id}/input/，可能材料还没归档。"
        return scan_input(base, task_id).render()

    reg.register(Tool(
        name="scan_inbox",
        description=(
            "检查 workspace/<task_id>/input/ 下已归档的材料："
            "template/ 应有模板文字稿和模板网页文件，draft/ 应有新文字稿，images/ 是图片（可能没有）。"
            "返回各目录文件清单与缺件/错位判断，用于阶段一【检查材料】。"
            "归档已由系统完成，本工具不搬文件，只做检查。task_id 不传时用当前会话的任务号"
        ),
        params_schema={
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
        },
        func=_scan_inbox,
    ))

    def _build_template_map(args: dict[str, Any]) -> str:
        from ..template.extract import extract_template
        from .config import _REPO_ROOT as root

        task_id = args.get("task_id") or session.data.get("task_id")
        if not task_id:
            return "还没有任务号，没法提取模板结构。请先开新项目。"
        tpl_dir = root / "workspace" / task_id / "input" / "template"
        html_files = [f for f in tpl_dir.iterdir() if f.suffix in (".html", ".htm")] if tpl_dir.exists() else []
        if not html_files:
            return f"在 workspace/{task_id}/input/template/ 下没找到 HTML 文件。"
        ts = extract_template(html_files[0])
        session.data["template_structure"] = ts
        return ts.render_summary()

    reg.register(Tool(
        name="build_template_map",
        description=(
            "用 BeautifulSoup 解析模板HTML，按嵌入结构签名提取层级（不只用字号），"
            "产出层级信息（字号/颜色/HTML片段样例/内容样例）存在会话中。"
            "供 normalize_draft 映射和 replace_template 克隆使用。"
            "task_id 不传时用当前会话的任务号"
        ),
        params_schema={
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
        },
        func=_build_template_map,
    ))

    def _normalize_draft(args: dict[str, Any]) -> str:
        from ..normalize.level import level_draft
        from .config import _REPO_ROOT as root

        task_id = args.get("task_id") or session.data.get("task_id")
        if not task_id:
            return "还没有任务号，没法处理新稿。请先开新项目。"
        ts = session.data.get("template_structure")
        if ts is None:
            return "还没提取模板结构，请先调用 build_template_map。"
        if llm is None:
            return "没有可用的 LLM，无法对新稿分级映射。请配置 LLM 或使用 MockLLM。"
        draft_dir = root / "workspace" / task_id / "input" / "draft"
        md_files = sorted(f for f in draft_dir.iterdir() if f.suffix == ".md") if draft_dir.exists() else []
        if not md_files:
            return f"在 workspace/{task_id}/input/draft/ 下没找到 Markdown 文稿（.md）。"
        raw = md_files[0].read_text(encoding="utf-8")
        leveled = level_draft(raw, ts, llm)
        session.data["leveled_draft"] = leveled
        lines = [f"新稿分级完成，共 {len(leveled)} 块："]
        for i, blk in enumerate(leveled, 1):
            lines.append(f"  {i}. [层级{blk.get('level','?')}] {blk.get('text','')[:40]}")
        return "\n".join(lines)

    reg.register(Tool(
        name="normalize_draft",
        description=(
            "清洗新文字稿并用LLM分级映射到模板层级。需要先调用 build_template_map。"
            "LLM 同时看模板结构和新稿，输出每块对应的模板层级号。"
            "结果存在会话中，供 replace_template 使用。"
            "task_id 不传时用当前会话的任务号"
        ),
        params_schema={
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
        },
        func=_normalize_draft,
    ))

    stubs = [
        ("review_levels", "把分级结果逐条展示给客户确认，写展示文件到 outbox/", {}),
        ("replace_template", "按映射克隆模板节点替换文字，生成 result.html", {}),
        ("upload_images", "把图片上传图床，换取稳定外链", {}),
        ("deliver_result", "交付 result.html，提醒客户上传秀米并手机预览", {}),
    ]
    for name, desc, schema in stubs:
        reg.register(Tool(name=name, description=desc, params_schema=schema, func=_stub(name)))
    return reg
