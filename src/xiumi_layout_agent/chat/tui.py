"""TUI：放文件 → y → 自动提取分级替换 → 给 result.html。"""

from __future__ import annotations

import sys
from pathlib import Path

from .llm import LLMClient, MockLLM
from .tools import Session, build_default_registry

_QUIT = {"退出", "exit", "quit"}
_YES = {"y", "yes", "y。", "好", "好了", "放好了"}
_NONE = {"n", "no", "没有", "没放", "还没", "无"}

_TYPE_MAP = {
    ".html": "template", ".htm": "template",
    ".md": "draft",
    ".png": "images", ".jpg": "images", ".jpeg": "images",
    ".gif": "images", ".webp": "images", ".bmp": "images",
}
_JUNK_PATTERNS = (":Zone.Identifier", ".DS_Store", "Thumbs.db", "desktop.ini", "._")


def run_tui(llm: LLMClient | None = None, inbox: Path | None = None) -> None:
    if llm is None:
        try:
            from .llm import create_llm
            llm = create_llm()
        except RuntimeError as e:
            print(f"[提示] {e}")
            print("[提示] 本次以离线演示模式运行（MockLLM）。")
            llm = MockLLM(replies=["好的"])

    if inbox is None:
        from .config import _REPO_ROOT
        inbox = _REPO_ROOT / "inbox"
    inbox.mkdir(exist_ok=True)

    session = Session()
    registry = build_default_registry(session, llm)

    print("排版小助手：请把【模板HTML】和【新文字稿（.md）】放进 inbox 文件夹，放好后输入 y")
    for line in sys.stdin:
        text = line.strip()
        if not text:
            continue
        if text in _QUIT:
            print("再见！")
            break

        if text.lower() in _YES:
            _run_pipeline(inbox, session, registry)
        elif text.lower() in _NONE:
            print("助手：好的，不着急。放好后输入 y")
        else:
            print("助手：没听清。放好文件后输入 y，或输入 退出")


def _run_pipeline(inbox: Path, session: Session, registry) -> None:
    """归档 → 提取模板 → 分级映射 → 生成成品。"""
    task_id = _new_task_id()
    session.data["task_id"] = task_id

    archived = _archive_by_type(inbox, task_id)
    if not archived["template"]:
        print("助手：inbox 里没找到 HTML 文件。请把模板 HTML 放进 inbox，再输入 y")
        return
    if not archived["draft"]:
        print("助手：inbox 里没找到文字稿（.md）。请把新文字稿放进 inbox，再输入 y")
        return

    print(f"助手：收到 {len(archived['template'])} 个模板文件、{len(archived['draft'])} 个文字稿。开始处理...\n")

    print("（① 提取模板结构...）")
    registry.get("build_template_map").run({"task_id": task_id})

    print("（② 新稿分级映射...）")
    out = registry.get("normalize_draft").run({"task_id": task_id})
    print(f"   {out}")

    print("（③ 生成成品...）")
    out = registry.get("replace_template").run({"task_id": task_id})
    print(f"\n助手：{out}")


def _archive_by_type(inbox: Path, task_id: str) -> dict[str, list[str]]:
    """按扩展名归档到 workspace/<task_id>/input/{template,draft,images}/。"""
    from .config import _REPO_ROOT as root
    base = root / "workspace" / task_id / "input"
    archived: dict[str, list[str]] = {"template": [], "draft": [], "images": []}

    for f in sorted(inbox.iterdir()):
        # 清垃圾
        if f.name.startswith(".") or any(p in f.name for p in _JUNK_PATTERNS):
            try:
                f.unlink()
            except OSError:
                pass
            continue
        if not f.is_file():
            continue
        category = _TYPE_MAP.get(f.suffix.lower())
        if not category:
            continue
        dest = base / category
        dest.mkdir(parents=True, exist_ok=True)
        f.rename(dest / f.name)
        archived[category].append(f.name)

    return archived


def _new_task_id() -> str:
    import time
    from datetime import UTC, datetime
    return f"{datetime.now(tz=UTC).date():%Y%m%d}_{int(time.time()) % 10000}"
