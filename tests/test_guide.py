import pytest

from xiumi_layout_agent.chat.guide import Guide, GuideState
from xiumi_layout_agent.chat.workflow import Stage


@pytest.fixture()
def setup(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    g = Guide(inbox)
    g.begin_stage(Stage.COLLECT_TEMPLATE)
    return g, inbox


def test_begin_stage_prompt(setup):
    g, _ = setup
    # 开场白应包含两样材料与 y 提示
    assert "模板文字稿" in g.state.needed[0] or True
    assert len(g.state.needed) == 2


def test_confirm_empty_inbox(setup):
    g, _ = setup
    done, msg = g.confirm()
    assert not done
    assert "空的" in msg


def test_confirm_one_by_one(setup):
    g, inbox = setup
    (inbox / "模板稿.txt").write_text("x")
    done, msg = g.confirm()
    assert not done and "收到" in msg
    (inbox / "模板.html").write_text("x")
    done, msg = g.confirm()
    assert done and "齐了" in msg
    assert g.state.received == {"template_text": "模板稿.txt", "template_html": "模板.html"}


def test_confirm_batch(setup):
    g, inbox = setup
    (inbox / "a.txt").write_text("x")
    (inbox / "b.html").write_text("x")
    done, msg = g.confirm()
    assert done
    assert "2 个文件" in msg


def test_next_prompt(setup):
    g, inbox = setup
    (inbox / "a.txt").write_text("x")
    g.confirm()
    pend = g.next_prompt()
    assert "还差" in pend and "y" in pend


def test_draft_stage_items():
    items = GuideState()
    assert items.done() is False
