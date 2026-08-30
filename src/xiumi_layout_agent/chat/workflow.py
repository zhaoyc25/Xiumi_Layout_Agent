"""工作流状态机：开新项目→收模板→收新稿→确认分级→替换→交付。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, unique


@unique
class Stage(str, Enum):
    IDLE = "idle"                    # 等待开新项目
    COLLECT_TEMPLATE = "collect_template"  # 收模板文字稿 + 模板 HTML
    COLLECT_DRAFT = "collect_draft"        # 收新文字稿 + 图片
    CONFIRM_LEVELS = "confirm_levels"      # 确认分级
    REPLACE = "replace"                    # 替换生成 result.html
    DELIVERED = "delivered"                # 已交付


_LEGAL = {
    Stage.IDLE: [Stage.COLLECT_TEMPLATE],
    Stage.COLLECT_TEMPLATE: [Stage.COLLECT_DRAFT],
    Stage.COLLECT_DRAFT: [Stage.CONFIRM_LEVELS],
    Stage.CONFIRM_LEVELS: [Stage.REPLACE],
    Stage.REPLACE: [Stage.DELIVERED],
    Stage.DELIVERED: [Stage.IDLE],  # 开下一个新项目
}

_STAGE_HINT = {
    Stage.IDLE: "等客户说开新项目",
    Stage.COLLECT_TEMPLATE: "请客户把 模板文字稿 和 模板HTML 逐个放进 inbox 文件夹",
    Stage.COLLECT_DRAFT: "请客户把 新文字稿 和 要用的图片 逐个放进 inbox 文件夹",
    Stage.CONFIRM_LEVELS: "把分级结果逐条念给客户听，请客户确认或改",
    Stage.REPLACE: "正在套模板生成 result.html",
    Stage.DELIVERED: "成果已交付，提醒客户上传秀米并手机预览",
}


@dataclass
class WorkflowState:
    stage: Stage = Stage.IDLE
    task_id: str = ""

    def advance(self, to: Stage) -> None:
        if to not in _LEGAL[self.stage]:
            raise WorkflowError(
                f"当前阶段是「{self.stage.value}」，还不能跳到「{to.value}」。"
                f"提示：{_STAGE_HINT[self.stage]}"
            )
        self.stage = to

    def can_go(self, to: Stage) -> bool:
        return to in _LEGAL[self.stage]


class WorkflowError(Exception):
    pass
