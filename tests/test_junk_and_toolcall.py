"""垃圾文件过滤 + tool_call 原生格式解析 测试。"""

from __future__ import annotations

import pytest

from xiumi_layout_agent.chat.agent import Agent
from xiumi_layout_agent.chat.guide import Guide
from xiumi_layout_agent.chat.workflow import Stage, WorkflowState


@pytest.fixture()
def setup(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    wf = WorkflowState()
    wf.advance(Stage.COLLECT_TEMPLATE)
    g = Guide(inbox)
    g.begin_stage(Stage.COLLECT_TEMPLATE, wf)
    return g, inbox


def test_zone_identifier_ignored(setup):
    g, inbox = setup
    (inbox / "模板稿.txt").write_text("x")
    (inbox / "模板稿.txt:Zone.Identifier").write_text("junk")
    _done, msg = g.confirm(None)
    assert "Zone.Identifier" not in msg
    assert "模板稿.txt" in msg
    # 垃圾被顺手删掉
    assert not (inbox / "模板稿.txt:Zone.Identifier").exists()


def test_only_junk_says_cleaned(setup):
    g, inbox = setup
    (inbox / "x.html:Zone.Identifier").write_text("junk")
    (inbox / ".DS_Store").write_text("junk")
    done, msg = g.confirm(None)
    assert not done
    assert "垃圾" in msg
    assert list(inbox.iterdir()) == []


def test_hidden_files_ignored(setup):
    g, inbox = setup
    (inbox / ".hidden").write_text("x")
    _done, msg = g.confirm(None)
    assert "空的" in msg


# ---- Agent._parse 原生 <tool_call> 格式 ----

def test_parse_native_tool_call():
    reply = '我来处理一下\n\n<tool_call>\n{"name": "normalize_draft", "arguments": {}}\n</tool_call>'
    name, args, speak = Agent._parse(reply)
    assert name == "normalize_draft"
    assert args == {}
    assert speak is None


def test_parse_native_tool_call_with_args():
    reply = '<tool_call>{"name": "new_project", "arguments": {"task_id": "t1"}}</tool_call>'
    name, args, _ = Agent._parse(reply)
    assert name == "new_project"
    assert args == {"task_id": "t1"}


def test_parse_native_tool_call_string_args():
    reply = '<tool_call>{"name": "f", "arguments": "{\\"a\\": 1}"}</tool_call>'
    _name, args, _ = Agent._parse(reply)
    assert args == {"a": 1}


def test_parse_malformed_tool_call_falls_back_to_speak():
    reply = "<tool_call>{bad json}</tool_call>"
    name, _, speak = Agent._parse(reply)
    assert name is None
    assert "bad json" in speak  # 当作说话，标签被剥掉


def test_parse_speak_with_stray_tool_call_stripped():
    reply = "老师好！我马上开始。<tool_call>{}</tool_call>"
    _, _, speak = Agent._parse(reply)
    assert speak == "老师好！我马上开始。"
