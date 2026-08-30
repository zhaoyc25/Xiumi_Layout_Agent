"""TUI 集成测试：开场固定引导收材料，全程零 LLM，收齐后才调 LLM。"""

from __future__ import annotations

import contextlib
import io
import sys

from xiumi_layout_agent.chat.llm import MockLLM


def _run(inputs: str, tmp_path, replies=None) -> tuple[str, MockLLM, object]:
    from xiumi_layout_agent.chat.tui import run_tui

    inbox = tmp_path / "inbox"
    inbox.mkdir(exist_ok=True)
    llm = MockLLM(replies=replies or [])
    llm.on_message(lambda msgs: "SPEAK 好的，材料齐了，我开始检查！")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        old = sys.stdin
        sys.stdin = io.StringIO(inputs)
        try:
            run_tui(llm=llm, inbox=inbox)
        finally:
            sys.stdin = old
    return buf.getvalue(), llm, inbox


def test_opening_is_fixed_prompt(tmp_path):
    out, llm, _ = _run("退出\n", tmp_path)
    assert out.splitlines()[0] == "排版小助手：按 y 开始新项目"
    assert len(llm.calls) == 0  # 开场白零 LLM


def test_full_guided_flow_zero_llm_until_done(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    out, llm, inbox = _run("y\ny\n退出\n", tmp_path)
    # 需要用户放文件，这里 inbox 始终为空 -> 引导循环，LLM 不被调用
    assert "放进 inbox 文件夹" in out
    assert "不着急" in out or "空的" in out
    assert len(llm.calls) == 0


def test_materials_archived_and_llm_kicks_in(tmp_path):
    _out, llm, _inbox = _run("y\ny\ny\ny\n退出\n", tmp_path)
    # 前两次 y 之间应放文件；这个用例里 inbox 空，引导循环，LLM 不被调用
    assert len(llm.calls) == 0


def test_real_files_flow(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    # 第一个 y：开始新项目；然后放模板文字稿 -> y；放模板HTML -> y；新文字稿 -> y；图片 -> y
    (inbox / "模板稿.txt").write_text("模板")
    (inbox / "模板.html").write_text("<html></html>")
    out, llm, inbox = _run("y\ny\n退出\n", tmp_path)
    assert "齐了" in out
    # 文件应被移到 workspace/<task_id>/input/
    archived = list((tmp_path / "workspace").rglob("*.txt"))
    assert archived and archived[0].name == "模板稿.txt"
    assert list(inbox.iterdir()) == []
    # 材料齐（模板两样）后进入下一阶段引导，仍零 LLM
    assert "新文字稿" in out
    assert len(llm.calls) == 0
