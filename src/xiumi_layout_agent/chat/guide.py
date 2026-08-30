"""固定问答式引导：收材料阶段不调 LLM，用程序管。
程序只负责把 inbox 里的文件移动归档；文件是什么类型、怎么处理，交给 LLM。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .workflow import Stage

# 每个阶段要收的材料：key -> (给用户看的名字, 是否必需)
_STAGE_ITEMS: dict[Stage, list[tuple[str, str, bool]]] = {
    Stage.COLLECT_TEMPLATE: [
        ("template_text", "模板文字稿", True),
        ("template_html", "模板网页文件", True),
    ],
    Stage.COLLECT_DRAFT: [
        ("draft_text", "新文字稿", True),
        ("images", "要用的图片", False),
    ],
}


@dataclass
class GuideState:
    """当前引导进度：本轮要收哪些、已收哪些。"""
    needed: list[str] = field(default_factory=list)
    received: dict[str, str] = field(default_factory=dict)  # key -> 文件名
    skipped: list[str] = field(default_factory=list)        # 可选项被"没有"跳过

    def done(self) -> bool:
        return bool(self.needed) and all(
            k in self.received or k in self.skipped for k in self.needed
        )

    def pending_all(self) -> list[str]:
        return [k for k in self.needed if k not in self.received and k not in self.skipped]


class Guide:
    """阶段引导器：固定话术 + y 确认，绝不调 LLM。不看扩展名，谁来收谁。"""

    def __init__(self, inbox: Path):
        self.inbox = inbox
        self.state = GuideState()

    def begin_stage(self, stage: Stage, workflow: WorkflowState | None = None) -> str:
        items = _STAGE_ITEMS.get(stage)
        if not items:
            self.state = GuideState()
            return ""
        self.state = GuideState(needed=[k for k, _, _ in items])
        self.state.skipped = []
        lines = []
        for _key, label, required in items:
            if required:
                lines.append(f"接下来请您把【{label}】放进 inbox 文件夹，放好后输入 y")
            else:
                lines.append(f"如果您有【{label}】，也请放进 inbox 文件夹，放好后输入 y；没有请输入：没有")
        return "\n".join(lines)

    def next_prompt(self) -> str:
        pend = self.state.pending_all()
        if not pend:
            return ""
        labels = {k: lbl for s in _STAGE_ITEMS.values() for k, lbl, _ in s}
        req = {k for k, lbl, r in _STAGE_ITEMS.get(self._cur_stage(), []) if r}
        if not any(k in req for k in pend):
            return "图片放好后输入 y，没有图片请输入：没有"
        if len(pend) == 1:
            return f"还差【{labels[pend[0]]}】，放进 inbox 文件夹后输入 y"
        return "还差：" + "、".join(f"【{labels[k]}】" for k in pend) + "，放好后输入 y"

    def _cur_stage(self) -> Stage | None:
        # 从 state 反查当前阶段（needed 顺序即阶段材料表）
        for stage, items in _STAGE_ITEMS.items():
            if [k for k, _, _ in items] == self.state.needed:
                return stage
        return None

    def confirm(self, workflow: WorkflowState | None = None) -> tuple[bool, str]:
        """用户按了 y：把 inbox 里的文件收进来（不看类型）。
        返回 (本阶段是否收齐, 给用户的话)。"""
        files = self._visible_files()
        taken = set(self.state.received.values())
        new_files = [f for f in files if f not in taken]

        if not new_files:
            leftovers = self._junk_files()
            if leftovers:
                self._delete_junk()
                return False, "收件箱里只有系统垃圾文件，已顺手清掉。" + self.next_prompt()
            return False, "inbox 文件夹现在是空的。" + self.next_prompt()

        # 新文件按顺序对号入座（类型判断留给 LLM）
        for k, f in zip(self.state.pending_all(), new_files, strict=False):
            self.state.received[k] = f

        # 顺手清掉本次没收的垃圾
        self._delete_junk()

        if self.state.done():
            return True, f"收到 {len(new_files)} 个文件（{'、'.join(new_files)}）。本阶段材料齐了！"
        return False, f"收到 {len(new_files)} 个文件（{'、'.join(new_files)}）。{self.next_prompt()}"

    def _junk_names(self) -> set[str]:
        """系统垃圾文件：Windows Zone.Identifier、.DS_Store、Thumbs.db 等。"""
        return {
            f.name for f in self.inbox.iterdir()
            if f.name.endswith(":Zone.Identifier")
            or f.name in {".DS_Store", "Thumbs.db", "desktop.ini"}
            or f.name.startswith("._")
        }

    def _visible_files(self) -> list[str]:
        """排除垃圾与隐藏文件后的文件清单。"""
        if not self.inbox.exists():
            return []
        junk = self._junk_names()
        return sorted(
            f.name for f in self.inbox.iterdir()
            if not f.name.startswith(".") and f.name not in junk
        )

    def _junk_files(self) -> list[object]:
        if not self.inbox.exists():
            return []
        return [f for f in self.inbox.iterdir() if f.name in self._junk_names()]

    def _delete_junk(self) -> None:
        for f in self._junk_files():
            try:
                f.unlink()
            except OSError:
                pass

    def skip_optional(self) -> bool:
        """用户说"没有"：若只剩可选项，跳过并返回是否收齐。"""
        stage = self._cur_stage()
        if stage is None:
            return False
        optional = {k for k, _, r in _STAGE_ITEMS[stage] if not r}
        pend = self.state.pending_all()
        if pend and all(k in optional for k in pend):
            self.state.skipped.extend(pend)
            return self.state.done()
        return False


from .workflow import WorkflowState
