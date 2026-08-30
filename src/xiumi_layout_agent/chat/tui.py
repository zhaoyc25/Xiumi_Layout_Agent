"""TUI：开场即固定引导（零 LLM），收齐材料后才交 LLM 主管开工。"""

from __future__ import annotations

import sys
from datetime import UTC
from pathlib import Path

from .agent import Agent
from .guide import Guide
from .llm import LLMClient, MockLLM
from .tools import Session, build_default_registry
from .workflow import Stage, WorkflowState

_QUIT = {"退出", "exit", "quit"}
_YES = {"y", "yes", "y。", "好", "好了", "放好了"}
_NONE = {"没有", "没放", "还没", "无"}

_ORDER = [Stage.IDLE, Stage.COLLECT_TEMPLATE, Stage.COLLECT_DRAFT,
          Stage.CONFIRM_LEVELS, Stage.REPLACE, Stage.DELIVERED]


def _next_stage(cur: Stage) -> Stage:
    return _ORDER[_ORDER.index(cur) + 1]


def run_tui(llm: LLMClient | None = None, inbox: Path | None = None) -> None:
    if llm is None:
        try:
            from .llm import create_llm
            llm = create_llm()
        except RuntimeError as e:
            print(f"[提示] {e}")
            print("[提示] 本次以离线演示模式运行（MockLLM），只能测试流程不能真正对话。")
            llm = MockLLM(replies=["好的，材料齐了，咱们开始！"])

    if inbox is None:
        from .config import _REPO_ROOT
        inbox = _REPO_ROOT / "inbox"
    inbox.mkdir(exist_ok=True)

    session = Session()
    workflow = WorkflowState()
    agent = Agent(llm, build_default_registry(session), session, workflow)
    guide = Guide(inbox)
    guided = True

    # 开场白：固定一句话，不调 LLM
    print("排版小助手：按 y 开始新项目")
    for line in sys.stdin:
        text = line.strip()
        if not text:
            continue
        if text in _QUIT:
            print("再见！")
            break

        # ---- 固定引导模式（收材料，零 LLM） ----
        if guided:
            if text.lower() in _YES:
                if workflow.stage is Stage.IDLE:
                    # 开始新项目：登记任务号（本地生成，不调 LLM）
                    session.data["task_id"] = _new_task_id()
                    workflow.advance(Stage.COLLECT_TEMPLATE)
                    print(f"助手：{guide.begin_stage(workflow.stage)}")
                else:
                    done, msg = guide.confirm()
                    print(f"助手：{msg}")
                    if done:
                        guided = _finish_stage(inbox, session, workflow, guide, agent)
            elif text.lower() in _NONE:
                if guide.skip_optional():
                    guided = _finish_stage(inbox, session, workflow, guide, agent)
                else:
                    print(f"助手：好的，不着急。{guide.next_prompt()}")
            else:
                print(f"助手：没听清。{guide.next_prompt()}如果暂时没有，请输入：没有")
            continue

        # ---- 普通模式：交给 LLM 主管 ----
        print("（AI 正在思考……）")
        print(f"助手：{agent.handle(text)}")


def _finish_stage(inbox: Path, session: Session, workflow: WorkflowState,
                  guide: Guide, agent: Agent) -> bool:
    """本阶段材料收齐：归档、推进状态机；无下一阶段可引导则交棒 LLM。
    返回是否仍处于固定引导模式。"""
    archived = _archive(inbox, session, guide)
    print(f"（材料已存到 {archived}）")
    workflow.advance(_next_stage(workflow.stage))
    opening = guide.begin_stage(workflow.stage)
    if opening:
        print(f"助手：{opening}")
        return True
    # 材料全齐：现在才让 LLM 上场检查、开工
    print("（接下来：材料收齐，AI 开始检查处理，请稍候……）")
    print("（AI 正在思考……）")
    print(f"助手：{agent.handle(_kickoff_msg(session))}")
    return False


def _kickoff_msg(session: Session) -> str:
    """材料收齐后给 LLM 的开工通知：告知归档结构，让它知道去哪找什么。"""
    task_id = session.data.get("task_id", "untitled")
    return (
        f"（系统：所有材料已收齐并归档到 workspace/{task_id}/input/ 下，"
        "其中 template/ 是模板材料（文字稿+网页文件），draft/ 是新文字稿，"
        "images/ 是图片（可能没有）。请从阶段一【检查材料】开始工作。）"
    )


def _new_task_id() -> str:
    import time
    from datetime import datetime
    return f"{datetime.now(tz=UTC).date():%Y%m%d}_{int(time.time()) % 10000}"


def _archive(inbox: Path, session: Session, guide: Guide) -> Path:
    """把已收讫的文件从 inbox 按 类别/阶段 归档到
    workspace/<task_id>/input/<template|draft|images>/，返回归档根目录。

    guide.state.received 的 key 即类别（template_text/template_html/draft_text/images），
    LLM 通过目录名即可区分模板与新稿，无需猜文件名。
    """
    task_id = session.data.get("task_id", "untitled")
    base = inbox.parent / "workspace" / task_id / "input"
    group_of = {
        "template_text": "template",
        "template_html": "template",
        "draft_text": "draft",
        "images": "images",
    }
    for key, name in guide.state.received.items():
        dest_dir = base / group_of.get(key, "misc")
        dest_dir.mkdir(parents=True, exist_ok=True)
        src = inbox / name
        if src.exists():
            src.rename(dest_dir / name)
    return base
